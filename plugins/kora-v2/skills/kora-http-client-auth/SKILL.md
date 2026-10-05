---
name: kora-http-client-auth
description: "Authenticating outgoing Kora 2.0 HTTP clients — the built-in BasicAuthHttpClientInterceptor / ApiKeyHttpClientInterceptor / BearerAuthHttpClientInterceptor from io.koraframework:http-client-common, the synchronous HttpClientTokenProvider, hand-written HttpClientInterceptor, @InterceptWith wiring, OAuth2 client-credentials token caching and 401 retry. Use when a @HttpClient must send Basic / API-key / Bearer credentials, when porting a 1.x Context/CompletionStage token flow to the synchronous 2.0 contract, or when an outbound call returns 401. For inbound request auth see kora-http-server-auth."
license: Apache-2.0
metadata:
  version: "0.1.0"
  kora-version: "2.x"
---

# Kora HTTP Client Auth

> **Kora sub-skill — obey the [kora-v2 meta rules](../../SKILL.md) on every task:** **R0** ground the workspace on Kora 2.0 refs before starting (framework source at tag `2.0.0.RC2` + `kora-examples` at `migration/2.0` + Kora 2.0 docs at koraframework.io/v2, which trail the source; 1.x `kora-docs` pages are never an authority) · **R1** read this sub-skill before writing code · **R2** Kora 2.0 APIs only — no Spring/Micronaut/Quarkus, no Kora 1.x APIs, no invented annotations or config keys · **R3** journal any incorrect Kora usage. Add comments/Javadoc only if asked.

| | |
|---|---|
| **Artifact** | `io.koraframework:http-client-common` (+ one transport: `http-client-ok`, `http-client-jdk`, `http-client-apache`). There is **no** `http-client-auth` artifact |
| **Token contract** | `io.koraframework.http.client.common.auth.HttpClientTokenProvider` |
| **Built-in interceptors** | `io.koraframework.http.client.common.interceptor.{BasicAuthHttpClientInterceptor, ApiKeyHttpClientInterceptor, BearerAuthHttpClientInterceptor}` |
| **Interceptor contract** | `io.koraframework.http.client.common.interceptor.HttpClientInterceptor` |
| **Attach with** | `io.koraframework.http.common.annotation.InterceptWith` |
| **Client annotation** | `io.koraframework.http.client.common.annotation.HttpClient` — `@HttpClient("httpClient.myApi")` |
| **Exceptions** | `io.koraframework.http.client.common.exception.{HttpClientResponseException, HttpClientDecoderException}` |

Everything in this skill is verified against the framework source at tag `2.0.0.RC2` and the
migrated examples on `migration/2.0` — see [Source of truth](#source-of-truth).

---

## 1. The three signatures that decide everything

```java
public interface HttpClientTokenProvider {
    @Nullable String getToken(HttpClientRequest request);      // synchronous, one argument
}

public interface HttpClientInterceptor {
    HttpClientResponse processRequest(InterceptChain chain, HttpClientRequest request) throws Exception;

    interface InterceptChain {
        HttpClientResponse process(HttpClientRequest request) throws Exception;
    }
}
```

Three consequences, and every 1.x auth flow has to be redesigned around them:

1. **No `Context`.** `Context` was removed from the whole framework — there is no first parameter
   to thread and nothing to migrate it to. Telemetry propagation is handled by
   `TelemetryInterceptor` through `ScopedValue`, not by anything you write.
2. **No `CompletionStage`.** `getToken` returns a `String`, `processRequest` returns a
   `HttpClientResponse`. A token fetch **blocks**, which is correct: Kora 2.0 contracts run on
   virtual threads. In Kotlin do **not** reach for `suspend`, `runBlocking` or `Dispatchers.IO` —
   `suspend` is not a Kora contract and the dispatcher wrapper is pure overhead.
3. **The chain comes first.** `processRequest(chain, request)` — a mechanical port of the 1.x
   `(ctx, chain, request)` order that only deletes `ctx` puts the arguments in the right places by
   luck; check them.

`getToken` may return `null` (or a blank string), and `BasicAuthHttpClientInterceptor`,
`BearerAuthHttpClientInterceptor` and `ApiKeyHttpClientInterceptor` then forward the request
**with no credential at all**.
That is the intended way to say "this scheme does not apply here" — and the reason a
misconfigured secret shows up as an upstream `401` rather than a startup failure.

---

## 2. Quick start — API key on every request

`build.gradle` (`koraVersion=2.0.0.RC2` in `gradle.properties`, resolved from plain `mavenCentral()`):

```groovy
dependencies {
    koraBom platform("io.koraframework:kora-bom:$koraVersion")

    annotationProcessor "io.koraframework:annotation-processors"

    implementation "io.koraframework:config-hocon"
    implementation "io.koraframework:http-client-common"
    implementation "io.koraframework:http-client-ok"
    implementation "io.koraframework:json-common"
    implementation "io.koraframework:logging-logback"
}
```

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

```java
@InterceptWith(ApiKeyHttpClientInterceptor.class)
@HttpClient("httpClient.serviceA")
public interface ServiceAClient {

    @HttpRoute(method = HttpMethod.GET, path = "/resource")
    @Json
    Resource getResource();
}
```

```java
@KoraApp
public interface Application extends
        HoconConfigModule,
        JsonModule,
        LogbackModule,
        OkHttpClientModule,
        ServiceAAuthModule {

    static void main(String[] args) {
        KoraApplication.run(ApplicationGraph::graph);
    }
}
```

```hocon
auth.serviceA.apiKey = ${SERVICE_A_API_KEY}

httpClient.serviceA {
  url = "https://api.service-a.example"
  telemetry.logging.maskHeaders = ["authorization", "set-cookie", "cookie", "x-api-key"]
}
```

`ServiceAAuthModule` is hand-written, so it **must** be listed in `@KoraApp extends`.
`ServiceAAuthConfig` and `ServiceAClient` must **not** be — the config and HTTP-client processors
register those through compiler extensions, exactly as in the upstream examples.

Kotlin is the same wiring with KSP instead of the annotation processor:

```kotlin
@ConfigSource("auth.serviceA")
interface ServiceAAuthConfig {
    fun apiKey(): String
}

@Module
interface ServiceAAuthModule {
    fun serviceAApiKeyInterceptor(config: ServiceAAuthConfig) = ApiKeyHttpClientInterceptor(
        ApiKeyHttpClientInterceptor.ApiKeyLocation.HEADER, "X-API-KEY", config.apiKey()
    )
}
```

---

## 3. Use this skill / do not

**Use it when you** attach `Authorization: Basic|Bearer` or an API key to outbound requests,
implement `HttpClientTokenProvider` for OAuth2 client credentials or a refreshable JWT, write a
custom `HttpClientInterceptor` for a non-standard scheme, retry a request after a `401`, or port a
1.x `Context`/`CompletionStage` token flow.

**Do not use it when you**:

| Task | Skill |
|---|---|
| Authenticate **incoming** requests, principals, 401/403 responses | [kora-http-server-auth](../kora-http-server-auth/SKILL.md) |
| Declare the client itself — routes, parameters, body and response mappers, timeouts, transports | [kora-http-client](../kora-http-client/SKILL.md) |
| Wire security schemes of an **OpenAPI-generated** client (`ApiSecurity`) | [kora-openapi-generator-client](../kora-openapi-generator-client/SKILL.md) — §7 below covers only the token providers it asks you to supply |
| Bind the secret itself, `${VAR}` substitution, `@ConfigSource` shapes | [kora-config-hocon](../kora-config-hocon/SKILL.md) |

Kora ships the building blocks for service-to-service auth only. There is no authorization-code /
user-consent OAuth2 flow anywhere in `http-client-common`; assemble it yourself or use a library.

---

## 4. Attaching an interceptor

`@InterceptWith(SomeInterceptor.class)` on the interface applies to every route; on a method it
applies to that route in addition to the class-level ones. Class-level interceptors run **first**.
The annotation is `@Repeatable`, and `@InterceptWith(value = X.class, tag = Y.class)` selects a
tagged component. There is no `interceptors = {...}` attribute on `@HttpClient`.

**The named class must be a graph component, and must have exactly one provider.** The generated
client takes each interceptor as a constructor parameter and nothing in the framework constructs
one for you:

- Your own interceptor class → put `@Component` on it. This holds **whether or not it has
  constructor dependencies** — the migrated examples annotate dependency-free interceptors too.
  (The "no dependencies ⇒ no `@Component`" rule applies to **mappers**, whose generated modules do
  build them; it does not apply to interceptors.)
- A framework interceptor (`BasicAuthHttpClientInterceptor`, `ApiKeyHttpClientInterceptor`,
  `BearerAuthHttpClientInterceptor`) → you cannot annotate it, so supply it from a `@Module`
  factory method.
- Never both. `@Component` on a class that a `@Module` also provides gives
  `Multiple components match dependency:` with a `Candidates:` list.
- Neither gives `No component found for dependency:` naming the interceptor type.

---

## 5. Choosing the built-in

| Scheme | Type | Constructors |
|---|---|---|
| `Authorization: Basic <base64>` | `BasicAuthHttpClientInterceptor` | `(String username, String password)` — encodes for you — or `(HttpClientTokenProvider)` returning the **already Base64-encoded** credentials |
| API key in header / query / cookie | `ApiKeyHttpClientInterceptor` | `(ApiKeyLocation location, String parameterName, String secret)` for a fixed key, or `(ApiKeyLocation, String, HttpClientTokenProvider)` for a rotating one; `ApiKeyLocation` is the nested enum `HEADER`, `QUERY`, `COOKIE` |
| `Authorization: Bearer <token>` | `BearerAuthHttpClientInterceptor` | `(HttpClientTokenProvider)` for a dynamic token, or `(String token)` for a fixed one |

None of the three validates its credential at graph init: a `null` or blank value skips the
credential on each request (§1). Make the config accessor non-`@Nullable` so a missing key fails as
`ConfigValueException` at startup instead. `COOKIE` appends `name=value` to an existing `Cookie`
header rather than replacing it.

Full walk-through with config: [references/http-client-auth-reference.md](references/http-client-auth-reference.md).

---

## 6. Dynamic tokens

Implement `HttpClientTokenProvider`, cache the token, and refresh ahead of expiry:

```java
@Component
public final class CachingTokenProvider implements HttpClientTokenProvider {

    private final TokenCache cache;
    private final AuthClient authClient;

    public CachingTokenProvider(TokenCache cache, AuthClient authClient) {
        this.cache = cache;
        this.authClient = authClient;
    }

    @Override
    public String getToken(HttpClientRequest request) {
        return cache.getOrRefresh(() -> {
            var response = authClient.requestToken();
            return TokenCache.Token.of(response.accessToken(), Duration.ofSeconds(response.expiresIn()));
        });
    }
}
```

The fetch blocks the calling virtual thread, which is what you want; the only thing that needs care
is that concurrent callers must not all fetch. `TokenCache` does a lock-free read, then a
`ReentrantLock` with a re-check — see [references/token-cache-reference.md](references/token-cache-reference.md).

- Refresh flow, refresh margin, and retrying a `401`:
  [references/jwt-token-provider-reference.md](references/jwt-token-provider-reference.md)
- Whole OAuth2 client-credentials setup:
  [references/oauth2-client-credentials-reference.md](references/oauth2-client-credentials-reference.md)

---

## 7. Token providers for an OpenAPI-generated client

The `kora` OpenAPI generator emits an `ApiSecurity` `@Module` next to the generated API. For
`http basic` and `apiKey` schemes it supplies the token provider itself from generated config; for
**`bearer` and `oauth2` schemes it supplies nothing** and the graph asks you for

```java
@Tag(ApiSecurity.BearerAuth.class)
default HttpClientTokenProvider bearerAuthTokenProvider() { … }
```

one per scheme that appears in an operation's `security` list — **including the alternatives that
operation never actually takes**, because the generated interceptor's constructor asks for every
scheme in every alternative. A scheme declared under `components/securitySchemes` but referenced by
no operation needs nothing.

That interceptor evaluates the alternatives in declaration order and uses the **first one whose
providers all returned non-null**. So a provider for an alternative you do not use must return
`null` — otherwise it wins and the request goes out with the wrong header. If no alternative comes
out complete, the request is forwarded with **no** credential and a single
`WARN Security schema is defined for api but no data was provided`.

The generated interceptor writes the `authorization` header with the scheme prefix itself —
`"Basic "` for `http`/`basic`, `"Bearer "` for `http`/`bearer`, `oauth2` and `openId` — so a
provider returns the **bare** token, exactly as for `BearerAuthHttpClientInterceptor`. The same
`OAuth2ClientCredentialsProvider` therefore serves both. Only an `http` scheme other than basic or
bearer gets the provider value verbatim. The generated basic-auth provider (built from the
generated security config) is a `@DefaultComponent`, so a provider of your own under the same tag
replaces it.

Everything else about generated clients — config paths, `ApiSecurity` tag names, the security
config prefix — belongs to [kora-openapi-generator-client](../kora-openapi-generator-client/SKILL.md).

---

## 8. Do not log the credential

Client telemetry is **off by default** in Kora 2.0 (`telemetry.logging.enabled` and
`telemetry.metrics.enabled` default to `false`; tracing defaults to `true`). Turning client logging
on is what exposes headers:

```hocon
httpClient.serviceA.telemetry.logging.enabled = true
```

The client logger masks headers through `maskHeaders`, whose default is
`["authorization", "set-cookie", "cookie"]`. **Setting `maskHeaders` replaces the default, it does
not extend it** — adding `"x-api-key"` alone silently unmasks `authorization`, so list the defaults
again alongside your own. Names are lower-cased on both sides before matching, so `"X-API-KEY"` and
`"x-api-key"` are equivalent.

An API key in a **query parameter** is not masked by anything by default — `maskQueries` starts
empty. Add the parameter name if you enable logging.

There is no `mask` key: the replacement (`***` by default) is a
`@Tag(HttpClientTelemetry.class) MaskingStrategy` component. Request and response **bodies** —
where a token endpoint's `client_secret` or `access_token` travels — are logged at `TRACE` and are
masked only by a `@Tag(HttpClientTelemetry.class) DataMasker` for their format (`form-urlencoded`,
`json`, `xml`). See [kora-http-client → Log masking](../kora-http-client/references/transports-reference.md#log-masking).

---

## 9. Pitfalls

| Symptom | Cause | Fix |
|---|---|---|
| `cannot find symbol: method configPath()` on `@HttpClient` | 1.x attribute | `@HttpClient("httpClient.myApi")` — the attribute is `value()` |
| `cannot find symbol: class Context` in an interceptor | `Context` was removed from the framework | Delete the parameter; `processRequest(chain, request)` has no context to thread |
| `'processRequest' overrides nothing` (Kotlin) | Signature still returns `CompletionStage`, or the nested type is unqualified | `override fun processRequest(chain: HttpClientInterceptor.InterceptChain, request: HttpClientRequest): HttpClientResponse` |
| Kotlin NPE on `"Bearer " + provider.getToken(rq)` | `getToken` is `@Nullable`, so Kotlin types the result `String?` | Handle the null: `val token = provider.getToken(rq) ?: return request` |
| `No component found for dependency: …Interceptor` | Interceptor named by `@InterceptWith` is not in the graph | `@Component` on your class, or a `@Module` factory for a framework one |
| `Multiple components match dependency: …Interceptor` | Both `@Component` and a `@Module` factory provide it | Keep exactly one |
| Build fails on `io.koraframework:http-client-async` | Removed in 2.0 with no replacement | `http-client-ok`, `http-client-jdk` or `http-client-apache` |
| `cannot find symbol: class RootUriInterceptor` | The one interceptor that **was** deleted from `http-client-common` in 2.0 | Nothing replaces it — set the base address as `httpClient.<client>.url`, which the generated client already prefixes |
| `Required dependency … http-client-auth` | That artifact has never existed | `http-client-common` + a transport |
| Upstream returns 401, no error at startup | Credential resolved to `null` or blank; Basic/Bearer/ApiKey then send no credential at all | Declare the config accessor non-`@Nullable` so a missing key fails as `ConfigValueException` during startup |
| Retried request carries the API key twice | `queryParam(name, value)` **appends**, unlike `header(name, value)` which **replaces** | `queryParamRemove(name)` before re-adding |
| Secret appears in logs | `maskHeaders` overridden without the defaults, the key travels in a query parameter not listed in `maskQueries`, or it is in a `TRACE`-logged body with no `DataMasker` | See §8 |
| Generated client sends `Authorization: Bearer Bearer …` | The `ApiSecurity` provider returns `"Bearer " + token`; the generated interceptor adds the prefix itself | Return the bare token |
| A discarded 401 response leaks a connection | `HttpClientResponse` is `Closeable`; only the response the client finally returns is auto-closed | Close the response you throw away before retrying |

---

## 10. Testing

Swap the provider through `KoraAppTestGraphModifier` so no token endpoint is called:

```java
@KoraAppTest(Application.class)
class SecureApiClientTest implements KoraAppTestGraphModifier {

    @Override
    public KoraGraphModification graph() {
        return KoraGraphModification.create()
                .replaceComponent(HttpClientTokenProvider.class, () -> (HttpClientTokenProvider) request -> "test-token");
    }

    @Test
    void sendsAuthorization(@TestComponent SecureApiClient client) {
        assertThat(client.getResource()).isNotNull();
    }
}
```

`@TestComponent` targets fields and parameters only — it injects a component out of the graph, it
does not declare one. Asserting that the header actually reached the server needs a stub upstream;
see [kora-testing-junit-java](../kora-testing-junit-java/SKILL.md) and
[kora-testing-blackbox](../kora-testing-blackbox/SKILL.md).

---

## References & assets

| File | Purpose |
|---|---|
| [references/http-client-auth-reference.md](references/http-client-auth-reference.md) | Built-in Basic / API-key / Bearer end to end, `@InterceptWith` placement and tags, dependencies, telemetry masking |
| [references/apikey-interceptor-reference.md](references/apikey-interceptor-reference.md) | Hand-written `HttpClientInterceptor` — header, query, cookie, ordering, response lifetime |
| [references/jwt-token-provider-reference.md](references/jwt-token-provider-reference.md) | `HttpClientTokenProvider` with refresh margin, the auth client, 401 retry |
| [references/token-cache-reference.md](references/token-cache-reference.md) | Single-flight thread-safe token cache (Java and Kotlin) |
| [references/oauth2-client-credentials-reference.md](references/oauth2-client-credentials-reference.md) | OAuth2 client-credentials, complete wiring and config |
| `assets/OAuth2Config.{java,kt}.template` | `@ConfigSource("oauth2")` — client id, secret, scopes |
| `assets/OAuth2AuthClient.{java,kt}.template` | Declarative token-endpoint client, `FormUrlEncoded` body, `@JsonField` response |
| `assets/TokenCache.{java,kt}.template` | Single-flight, thread-safe token cache |
| `assets/OAuth2ClientCredentialsProvider.{java,kt}.template` | `HttpClientTokenProvider` over the cache |
| `assets/OAuth2AuthModule.{java,kt}.template` | `@Module` supplying the Basic and Bearer interceptors |
| `assets/CustomAuthInterceptor.{java,kt}.template` | Hand-written interceptor with a single 401 retry |
| `scripts/generate-auth-templates.sh` | Renders one scheme into a project package — `--scheme oauth2\|interceptor\|all`, `--lang java\|kotlin`, `--dry-run` |

Every template exists in both languages.

Basic auth, API-key and static-Bearer wiring have no templates on purpose — each is one line inside
a `@Module` you already own:

```java
new BasicAuthHttpClientInterceptor(config.username(), config.password());
new ApiKeyHttpClientInterceptor(ApiKeyHttpClientInterceptor.ApiKeyLocation.HEADER, "X-API-KEY", config.apiKey());
new BearerAuthHttpClientInterceptor(config.token());
```

## Related skills

- [kora-http-client](../kora-http-client/SKILL.md) — the client itself: routes, mappers, transports, timeouts
- [kora-http-server-auth](../kora-http-server-auth/SKILL.md) — the inbound side
- [kora-openapi-generator-client](../kora-openapi-generator-client/SKILL.md) — generated `ApiSecurity`
- [kora-config-hocon](../kora-config-hocon/SKILL.md) — `@ConfigSource`, `${VAR}` substitution
- [kora-json](../kora-json/SKILL.md) — `@Json` / `@JsonField` on token-endpoint payloads
- [kora-telemetry-logging](../kora-telemetry-logging/SKILL.md) — enabling and shaping client logs
- [kora-di-compile](../kora-di-compile/SKILL.md) — `@Component`, `@Module`, `@Tag`, graph errors

## Source of truth

Framework source and tests outrank everything else; the Kora 2.0 docs
([koraframework.io/v2/en](https://koraframework.io/v2/en/)) are a secondary reference, and the 1.x
docs are background only. This skill was verified against:

- Framework source, tag `2.0.0.RC2`:
  [http-client-common](https://github.com/kora-projects/kora/tree/2.0.0.RC2/http/http-client-common)
  (`auth/`, `interceptor/`, `request/`, `telemetry/`) ·
  [http-common](https://github.com/kora-projects/kora/tree/2.0.0.RC2/http/http-common)
  (`annotation/InterceptWith`, `telemetry/MaskingUtils`) ·
  [http-client-annotation-processor](https://github.com/kora-projects/kora/tree/2.0.0.RC2/http/http-client-annotation-processor) ·
  [openapi-generator](https://github.com/kora-projects/kora/tree/2.0.0.RC2/openapi/openapi-generator)
  (`ClientSecuritySchemaGenerator`)
- Migrated examples, branch `migration/2.0`:
  [kora-java-http-client](https://github.com/kora-projects/kora-examples/tree/migration/2.0/examples/java/kora-java-http-client) ·
  [kora-kotlin-http-client](https://github.com/kora-projects/kora-examples/tree/migration/2.0/examples/kotlin/kora-kotlin-http-client) ·
  [kora-java-openapi-generator-http-client](https://github.com/kora-projects/kora-examples/tree/migration/2.0/examples/java/kora-java-openapi-generator-http-client)
- Migrated guide apps, branch `migration/2.0`:
  [kora-java-guide-http-client-advanced-app](https://github.com/kora-projects/kora-examples/tree/migration/2.0/guides/java/kora-java-guide-http-client-advanced-app) ·
  [kora-kotlin-guide-http-client-advanced-app](https://github.com/kora-projects/kora-examples/tree/migration/2.0/guides/kotlin/kora-kotlin-guide-http-client-advanced-app)
