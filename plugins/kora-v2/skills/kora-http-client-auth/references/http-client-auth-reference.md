# HTTP Client Auth Reference

Every authentication scheme `io.koraframework:http-client-common` ships, wired end to end.

## Contents

- [Dependencies](#dependencies)
- [The contracts](#the-contracts)
- [Attaching an interceptor](#attaching-an-interceptor)
- [Basic authentication](#basic-authentication)
- [API-key authentication](#api-key-authentication)
- [Bearer token](#bearer-token)
- [Tagged interceptors for several clients](#tagged-interceptors-for-several-clients)
- [Configuration](#configuration)
- [Keeping the credential out of the logs](#keeping-the-credential-out-of-the-logs)
- [Migrating a 1.x auth interceptor](#migrating-a-1x-auth-interceptor)
- [See also](#see-also)

---

## Dependencies

```groovy
dependencies {
    koraBom platform("io.koraframework:kora-bom:$koraVersion")   // koraVersion=2.0.0.RC2

    annotationProcessor "io.koraframework:annotation-processors"  // Kotlin: ksp "io.koraframework:symbol-processors"

    implementation "io.koraframework:config-hocon"
    implementation "io.koraframework:http-client-common"          // the auth types live here
    implementation "io.koraframework:http-client-ok"              // or http-client-jdk / http-client-apache
}
```

- There is **no** `io.koraframework:http-client-auth` artifact, and there never was one under
  `ru.tinkoff.kora` either.
- `http-client-async` was **removed** in 2.0. The transports are `http-client-ok`
  (`OkHttpClientModule`), `http-client-jdk` (`JdkHttpClientModule`) and `http-client-apache`
  (`ApacheHttpClientModule`).
- `kora-bom` is resolved from plain `mavenCentral()`.
- Nothing in this skill depends on the transport: the auth header is added by interceptors before
  the transport sees the request. The transports drop only headers they own —
  `http-client-jdk` the JDK's restricted `connection`/`content-length`/`expect`/`host`/`upgrade`,
  `http-client-apache` `content-length`/`transfer-encoding` — and never `authorization`.

---

## The contracts

```java
package io.koraframework.http.client.common.auth;

public interface HttpClientTokenProvider {

    @Nullable String getToken(HttpClientRequest request);
}
```

```java
package io.koraframework.http.client.common.interceptor;

public interface HttpClientInterceptor {

    HttpClientResponse processRequest(InterceptChain chain, HttpClientRequest request) throws Exception;

    interface InterceptChain {
        HttpClientResponse process(HttpClientRequest request) throws Exception;
    }

    static HttpClientInterceptor noop() { … }
}
```

Both are synchronous. `getToken` is invoked once per request by the Basic and Bearer interceptors;
returning `null` means "no credential", and the request is forwarded unchanged.

In Kotlin, write the override as:

```kotlin
override fun getToken(request: HttpClientRequest): String? = …
```

`String?` is what the contract means and is required as soon as your implementation can return
null. A non-null `String` return also compiles — it is an ordinary covariant narrowing — so use it
only when the provider genuinely always has a token.

**Where the nullability does bite is the call site.** `@Nullable` on the method is honoured, so
Kotlin types `provider.getToken(request)` as `String?`:

```kotlin
val token: String = provider.getToken(request)
// error: initializer type mismatch: expected 'String', actual 'String?'
```

Handle it (`?: return request`) rather than asserting with `!!`.

Note what `@NullMarked` does and does not reach here: `http-client-common` and `http-common`
carry it on `module-info.java` only — neither has a `package-info.java`. With the jars on the
classpath, as a normal Gradle `implementation` dependency puts them, Kotlin therefore sees
*parameters* as platform types, and both `request: HttpClientRequest` and `request: HttpClientRequest?`
are accepted overrides. Explicit `@Nullable` annotations on individual members, like the one on
`getToken`, are read regardless.

`HttpClientTokenProvider` is a functional interface, so Kotlin SAM conversion works:
`HttpClientTokenProvider { null }`.

---

## Attaching an interceptor

```java
@InterceptWith(BearerAuthHttpClientInterceptor.class)          // every route of this client
@HttpClient("httpClient.secureApi")
public interface SecureApiClient {

    @HttpRoute(method = HttpMethod.GET, path = "/protected")
    @Json
    ProtectedResponse getProtected();

    @InterceptWith(AuditInterceptor.class)                     // this route, in addition
    @HttpRoute(method = HttpMethod.GET, path = "/health")
    void health();
}
```

- `io.koraframework.http.common.annotation.InterceptWith`, `@Repeatable`, targets `TYPE` and
  `METHOD`, attributes `Class<?> value()` and `Class<?> tag() default Tag.class`.
- Class-level interceptors run **before** method-level ones.
- `@HttpClient` has **no** `interceptors = {...}` attribute, and no `baseUrl` — the target address
  is `httpClient.<client>.url` in config.

### The interceptor must be a component — exactly one provider

The generated client class takes every `@InterceptWith` class as a **constructor parameter**.
Nothing in `http-client-common` constructs interceptors, so the graph must contain one:

```java
@Component                       // your own class: always, dependencies or not
public final class AuditInterceptor implements HttpClientInterceptor { … }
```

```java
@Module                          // framework classes: you cannot annotate them
public interface SecureApiAuthModule {

    default BearerAuthHttpClientInterceptor secureApiBearer(HttpClientTokenProvider provider) {
        return new BearerAuthHttpClientInterceptor(provider);
    }
}
```

A hand-written `@Module` has to be listed in `@KoraApp extends`. `@ConfigSource` interfaces and
`@HttpClient` interfaces do not — their processors register them through compiler extensions.

| Mistake | Error |
|---|---|
| Neither `@Component` nor a `@Module` factory | `No component found for dependency:` naming the interceptor type, with a `Fix:` block |
| Both `@Component` **and** a `@Module` factory | `Multiple components match dependency:` with a `Candidates:` list |

> The "a dependency-free class must **not** carry `@Component`" rule you may have read for
> **mappers** does not transfer to interceptors. Mappers have generated module factories that build
> the dependency-free ones; interceptors do not. The migrated upstream examples put `@Component` on
> interceptors with no constructor arguments at all.

---

## Basic authentication

`Authorization: Basic <base64(username:password)>`.

```java
@ConfigSource("auth.basic")
public interface BasicAuthConfig {

    String username();

    String password();
}
```

```java
@Module
public interface BasicAuthModule {

    default BasicAuthHttpClientInterceptor basicAuthInterceptor(BasicAuthConfig config) {
        return new BasicAuthHttpClientInterceptor(config.username(), config.password());
    }
}
```

```java
@InterceptWith(BasicAuthHttpClientInterceptor.class)
@HttpClient("httpClient.legacyApi")
public interface LegacyApiClient {

    @HttpRoute(method = HttpMethod.GET, path = "/hello/world")
    void hello();
}
```

```hocon
auth.basic {
  username = "svc-orders"
  password = ${BASIC_AUTH_PASSWORD}
}

httpClient.legacyApi.url = "https://legacy.example"
```

The two-argument constructor does the Base64 encoding. The other constructor takes an
`HttpClientTokenProvider` that must return the **already encoded** `username:password` — the
interceptor only prefixes `"Basic "`. `io.koraframework.http.client.common.auth.BasicAuthHttpClientTokenProvider`
is that encoder if you want to build one yourself.

**Null credentials are silent.** `BasicAuthHttpClientTokenProvider` returns `null` when either
argument is `null`, and the interceptor then sends the request with **no** `Authorization` header —
you learn about it from the upstream `401`. Declare `username()`/`password()` non-`@Nullable` so a
missing key fails at startup with `ConfigValueException` instead.

---

## API-key authentication

```java
public final class ApiKeyHttpClientInterceptor implements HttpClientInterceptor {

    public enum ApiKeyLocation { HEADER, QUERY, COOKIE }

    public ApiKeyHttpClientInterceptor(ApiKeyLocation parameterLocation, String parameterName, HttpClientTokenProvider tokenProvider) { … }

    public ApiKeyHttpClientInterceptor(ApiKeyLocation parameterLocation, String parameterName, String secret) { … }
}
```

`ApiKeyLocation` is nested inside the interceptor — reference it as
`ApiKeyHttpClientInterceptor.ApiKeyLocation.HEADER` or import it explicitly.

```java
@ConfigSource("auth.serviceA")
public interface ServiceAAuthConfig {

    String apiKey();
}
```

```java
@Module
public interface ServiceAAuthModule {

    default ApiKeyHttpClientInterceptor serviceAApiKeyInterceptor(ServiceAAuthConfig config) {
        return new ApiKeyHttpClientInterceptor(
                ApiKeyHttpClientInterceptor.ApiKeyLocation.HEADER, "X-API-KEY", config.apiKey());
    }
}
```

Behaviour per location, straight from the implementation:

| Location | Effect on the request |
|---|---|
| `HEADER` | `toBuilder().header(name, secret)` — **replaces** any existing header of that name |
| `QUERY` | `toBuilder().queryParam(name, secret)` — **appends**; running it twice sends the key twice |
| `COOKIE` | appends `Cookie.of(name, secret).toValue()` to the request's existing `Cookie` header (`existing + "; " + cookie`), or sets it when there is none |

The key is read from the provider on **every** request (the `String` constructor wraps it in a
constant provider). A `null` or blank key skips the parameter and forwards the request
unauthenticated — nothing fails at graph build, so make the config accessor non-`@Nullable` if a
missing key must stop startup. The parameter name is not checked.

---

## Bearer token

`Authorization: Bearer <token>`.

```java
@Module
public interface BearerAuthModule {

    default BearerAuthHttpClientInterceptor bearerAuthInterceptor(HttpClientTokenProvider provider) {
        return new BearerAuthHttpClientInterceptor(provider);
    }
}
```

```java
@Component
public final class StaticTokenProvider implements HttpClientTokenProvider {

    private final ApiTokenConfig config;

    public StaticTokenProvider(ApiTokenConfig config) {
        this.config = config;
    }

    @Override
    public String getToken(HttpClientRequest request) {
        return config.token();
    }
}
```

```java
@ConfigSource("auth.api")
public interface ApiTokenConfig {

    String token();
}
```

For a token that never changes, `new BearerAuthHttpClientInterceptor(config.token())` skips the
provider entirely. For a token that has to be fetched and refreshed, see
[jwt-token-provider-reference.md](jwt-token-provider-reference.md).

The provider returns the **bare** token — `BearerAuthHttpClientInterceptor` adds the `"Bearer "`
prefix. The OpenAPI-generated `ApiSecurity` interceptor does the same for `bearer`, `oauth2` and
`openId` schemes, so one provider serves both. See `SKILL.md` §7.

---

## Tagged interceptors for several clients

Two clients that need the same interceptor type with different credentials are disambiguated with
a tag, not with two component types:

```java
public final class OrdersApi {}
public final class BillingApi {}
```

```java
@Module
public interface ApiKeysModule {

    @Tag(OrdersApi.class)
    default ApiKeyHttpClientInterceptor ordersApiKey(ApiKeysConfig config) {
        return new ApiKeyHttpClientInterceptor(
                ApiKeyHttpClientInterceptor.ApiKeyLocation.HEADER, "X-API-KEY", config.orders());
    }

    @Tag(BillingApi.class)
    default ApiKeyHttpClientInterceptor billingApiKey(ApiKeysConfig config) {
        return new ApiKeyHttpClientInterceptor(
                ApiKeyHttpClientInterceptor.ApiKeyLocation.HEADER, "X-API-KEY", config.billing());
    }
}
```

```java
@InterceptWith(value = ApiKeyHttpClientInterceptor.class, tag = OrdersApi.class)
@HttpClient("httpClient.orders")
public interface OrdersClient { … }
```

Without the tags both factories match one claim and the build fails with
`Multiple components match dependency: ApiKeyHttpClientInterceptor (no tags)`.

---

## Configuration

Secrets belong in the environment, never in the file:

```hocon
auth {
  serviceA.apiKey = ${SERVICE_A_API_KEY}          // required — startup fails if unset
  serviceB.apiKey = "dev-key"
  serviceB.apiKey = ${?SERVICE_B_API_KEY}         // optional override, keeps the default
}

httpClient {
  serviceA {
    url = "https://api.service-a.example"
    requestTimeout = 10s
  }
  serviceB {
    url = "https://api.service-b.example"
  }
}
```

`@HttpClient` with no value defaults the config path to `httpClient.<clientInterfaceName>` with the
first letter lower-cased — `ServiceAClient` → `httpClient.serviceAClient`. Passing the path
explicitly, as above, is less surprising.

There is no `@Value` or `@ConfigValue` annotation in Kora. Bind a `@ConfigSource` interface and
inject it through the constructor; see [kora-config-hocon](../../kora-config-hocon/SKILL.md).

---

## Keeping the credential out of the logs

Client telemetry defaults: `telemetry.logging.enabled = false`,
`telemetry.metrics.enabled = false`, `telemetry.tracing.enabled = true`. Enabling logging is what
puts headers into the log:

```hocon
httpClient.serviceA {
  url = "https://api.service-a.example"
  telemetry.logging {
    enabled = true
    maskHeaders = ["authorization", "set-cookie", "cookie", "x-api-key"]
    maskQueries = ["api_key"]
  }
}
```

`HttpClientTelemetryConfig.HttpClientLoggingConfig` declares `maskHeaders()` defaulting to
`["authorization", "set-cookie", "cookie"]` and `maskQueries()` defaulting to empty. The logger
factory lower-cases both lists, and `HttpHeadersImpl` lower-cases every header name it stores.
Therefore:

- A config value **replaces** the default set. Writing `maskHeaders = ["x-api-key"]` leaves
  `authorization` unmasked.
- The case you write does not matter — `"X-API-KEY"` and `"x-api-key"` both match.
- Query parameters are matched lower-cased too, and nothing is masked until you list it.
- There is no `mask` key. The replacement text (default `***`) comes from a
  `@Tag(HttpClientTelemetry.class) MaskingStrategy` component; it receives the original value.
- Bodies are logged at `TRACE` and masked only by a `@Tag(HttpClientTelemetry.class) DataMasker`
  for their format — a `FormUrlencodedDataMasker` for a token request carrying `client_secret`, a
  `JsonDataMasker` for a response carrying `access_token`. See
  [kora-http-client → Log masking](../../kora-http-client/references/transports-reference.md#log-masking).

Per-operation overrides exist under `httpClient.<client>.<operation>.telemetry.logging.*` with the
same key names, all `@Nullable` so an unset one falls back to the client-level value.

---

## Migrating a 1.x auth interceptor

| Kora 1.x | Kora 2.0 |
|---|---|
| `ru.tinkoff.kora.http.client.common.*` | `io.koraframework.http.client.common.*` |
| `ru.tinkoff.kora.common.Component` | `io.koraframework.common.annotation.Component` |
| `jakarta.annotation.Nullable` | `org.jspecify.annotations.Nullable` (type-use) |
| `@HttpClient(configPath = "x")` | `@HttpClient("x")` |
| `CompletionStage<String> getToken(HttpClientRequest)` | `@Nullable String getToken(HttpClientRequest)` |
| `CompletionStage<HttpClientResponse> processRequest(Context, InterceptChain, HttpClientRequest)` | `HttpClientResponse processRequest(InterceptChain, HttpClientRequest)` |
| `chain.process(ctx, request)` | `chain.process(request)` |
| `ru.tinkoff.kora:json-module`, `@Json("access_token")` | `io.koraframework:json-common`, `@JsonField("access_token")` |
| `ru.tinkoff.kora:http-client-async` | removed — use `http-client-ok` / `-jdk` / `-apache` |
| `RootUriInterceptor` | **deleted** — no replacement type; set `httpClient.<client>.url` |

Every other type this reference names survived the move: `HttpClientTokenProvider`,
`BasicAuthHttpClientTokenProvider`, `HttpClientInterceptor`, `BasicAuthHttpClientInterceptor`,
`ApiKeyHttpClientInterceptor` and `BearerAuthHttpClientInterceptor` all exist in 2.0 under
`io.koraframework.http.client.common.{auth,interceptor}`, two of them with the changed signatures
above. `RootUriInterceptor` is the single class that `http-client-common/interceptor/` lost, and
nothing took its place — the generated client resolves each route against the configured
`httpClient.<client>.url`, which is what that interceptor used to do by hand.

`Context` has no replacement: it does not exist anywhere in Kora 2.0. Anything that used it to
carry per-request state has to be redesigned, not renamed. If you were passing a `Context` only to
hand it back to `chain.process`, delete it.

`thenApply` / `thenCompose` chains inside a token provider collapse into straight-line blocking
code. That is not a regression — the call runs on a virtual thread. In Kotlin do not replace the
chain with `suspend`, `runBlocking` or `withContext(Dispatchers.IO)`: `suspend` is not a Kora
contract, and the dispatcher hop buys nothing.

---

## See also

- [apikey-interceptor-reference.md](apikey-interceptor-reference.md) — hand-written interceptors
- [jwt-token-provider-reference.md](jwt-token-provider-reference.md) — refreshable tokens, 401 retry
- [token-cache-reference.md](token-cache-reference.md) — single-flight cache
- [oauth2-client-credentials-reference.md](oauth2-client-credentials-reference.md) — full OAuth2 CC setup
