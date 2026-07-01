---
name: kora-http-client-auth
description: "Authentication for outgoing Kora HTTP clients. Covers the built-in BasicAuthHttpClientInterceptor, ApiKeyHttpClientInterceptor and BearerAuthHttpClientInterceptor, the HttpClientTokenProvider interface, attaching them with @InterceptWith, and hand-written HttpClientInterceptor classes for custom schemes (OAuth2 client credentials, JWT with caching/refresh). Use when adding Basic/Bearer/API-key authorization to a @HttpClient, implementing token refresh for service-to-service calls, or debugging 401 responses from an external API. Not for server-side auth (use kora-http-server-auth)."
---

# Kora HTTP Client Auth

Authenticate outgoing requests from a declarative `@HttpClient`. Kora ships
ready-made `HttpClientInterceptor` implementations for Basic, API-key and Bearer
schemes; attach any interceptor with `@InterceptWith`. For dynamic tokens
(OAuth2 client credentials, refreshable JWT) you implement `HttpClientTokenProvider`
or write your own `HttpClientInterceptor`.

**Level:** Intermediate (requires `kora-http-client` and `kora-di-compile`).

**Key facts (verify against the source of truth):**
- There is **no** `ru.tinkoff.kora:http-client-auth` artifact. Auth lives in
  `http-client-common` and is wired through interceptors.
- Built-in interceptors: `BasicAuthHttpClientInterceptor`,
  `ApiKeyHttpClientInterceptor`, `BearerAuthHttpClientInterceptor`.
- `HttpClientTokenProvider` is the extension point for Bearer tokens; the
  Bearer interceptor calls it on every request.
- Interceptors are attached with `@InterceptWith(...)`, **not** an
  `interceptors = {...}` attribute on `@HttpClient`.
- The target URL is set in config (`httpClient.<client>.url`), **not** a
  `baseUrl` annotation attribute.

---

## Quick Start

`build.gradle` — note the mandatory annotation processor:

```groovy
dependencies {
    koraBom platform("ru.tinkoff.kora:kora-parent:1.2.17")

    annotationProcessor "ru.tinkoff.kora:annotation-processors"

    implementation "ru.tinkoff.kora:config-hocon"
    implementation "ru.tinkoff.kora:http-client-common"
    implementation "ru.tinkoff.kora:http-client-ok"   // OkHttp transport
    implementation "ru.tinkoff.kora:json-module"
    implementation "ru.tinkoff.kora:logging-logback"
}
```

```java
@KoraApp
public interface Application extends
    HoconConfigModule,
    JsonModule,
    LogbackModule,
    OkHttpClientModule,
    BearerAuthModule { }
```

Provide a token, register the built-in Bearer interceptor in a `@Module`, and
attach it to the client:

```java
@Component
public final class StaticTokenProvider implements HttpClientTokenProvider {

    private final ApiTokenConfig config;

    public StaticTokenProvider(ApiTokenConfig config) {
        this.config = config;
    }

    @Override
    public CompletionStage<String> getToken(HttpClientRequest request) {
        return CompletableFuture.completedFuture(config.token());
    }
}
```

```java
@Module
public interface BearerAuthModule {

    default BearerAuthHttpClientInterceptor bearerAuther(HttpClientTokenProvider tokenProvider) {
        return new BearerAuthHttpClientInterceptor(tokenProvider);
    }
}
```

```java
@HttpClient(configPath = "httpClient.secureApi")
public interface SecureApiClient {

    @InterceptWith(BearerAuthHttpClientInterceptor.class)
    @HttpRoute(method = HttpMethod.GET, path = "/protected")
    @Json
    ProtectedResponse getProtected();
}
```

```hocon
httpClient.secureApi {
    url = "https://api.example.com"
}
api.token = ${API_TOKEN}   // externalize the secret
```

`@ConfigSource` for the token:

```java
@ConfigSource("api")
public interface ApiTokenConfig {
    String token();
}
```

---

## When to use vs NOT

Use this skill when you:
- add `Authorization: Basic`/`Bearer` or an API-key header to outbound requests;
- implement `HttpClientTokenProvider` for OAuth2 client-credentials or JWT refresh;
- write a custom `HttpClientInterceptor` for a non-standard scheme;
- get `401 Unauthorized` from an external API and need to fix the credentials flow.

Do **not** use this skill when you:
- authenticate requests **on the server** — see `kora-http-server-auth`;
- need OAuth2 with a user context (authorization-code flow) — Kora ships only the
  building blocks; the client-credentials pattern here is service-to-service.

---

## Reference files

| Topic | Reference |
|-------|-----------|
| Built-in interceptors (Basic / API-key / Bearer), `@InterceptWith` placement, config | [references/http-client-auth-reference.md](references/http-client-auth-reference.md) |
| Custom `HttpClientInterceptor` (header & query-param API key) | [references/apikey-interceptor-reference.md](references/apikey-interceptor-reference.md) |
| `HttpClientTokenProvider` with caching/refresh | [references/jwt-token-provider-reference.md](references/jwt-token-provider-reference.md) |
| Thread-safe token cache | [references/token-cache-reference.md](references/token-cache-reference.md) |
| OAuth2 client-credentials end-to-end | [references/oauth2-client-credentials-reference.md](references/oauth2-client-credentials-reference.md) |

Templates and a generator script live in [assets/](assets/README.md).

---

## Core patterns

### 1. Built-in Basic / API-key / Bearer

Register the interceptor as a component in a `@Module`, then attach it.

```java
@Module
public interface ApiKeyAuthModule {

    @ConfigSource("openapiAuth.apiKeyAuth")
    interface ApiKeyAuthConfig {
        String apiKey();
    }

    default ApiKeyHttpClientInterceptor apiKeyAuther(ApiKeyAuthConfig config) {
        return new ApiKeyHttpClientInterceptor(ApiKeyLocation.HEADER, "X-API-KEY", config.apiKey());
    }
}
```

```java
@HttpClient(configPath = "httpClient.someClient")
public interface SomeClient {

    @InterceptWith(ApiKeyHttpClientInterceptor.class)
    @HttpRoute(method = HttpMethod.GET, path = "/hello/world")
    void hello();
}
```

`@InterceptWith` may sit on the interface (applies to every method) or on a single
method. `ApiKeyLocation` is `HEADER`, `QUERY`, or `COOKIE`.

`BasicAuthHttpClientInterceptor(username, password)` Base64-encodes the credentials
for you. `BearerAuthHttpClientInterceptor` takes an `HttpClientTokenProvider` (or a
static token string) and adds the `Authorization` header per request.

### 2. Custom interceptor for a non-standard scheme

Implement `HttpClientInterceptor` directly when the built-ins do not fit. The
signature returns a `CompletionStage<HttpClientResponse>` and you must call
`chain.process(...)`:

```java
@Component
public final class CustomHeaderInterceptor implements HttpClientInterceptor {

    private final ApiKeyAuthConfig config;

    public CustomHeaderInterceptor(ApiKeyAuthConfig config) {
        this.config = config;
    }

    @Override
    public CompletionStage<HttpClientResponse> processRequest(
            Context ctx, InterceptChain chain, HttpClientRequest request) throws Exception {
        var authorized = request.toBuilder()
                .header("X-Custom-Token", config.value())
                .build();
        return chain.process(ctx, authorized);
    }
}
```

Use `request.toBuilder().header(name, value)` for headers and
`.queryParam(name, value)` for query parameters; never mutate the original request.

### 3. Dynamic token via `HttpClientTokenProvider`

For tokens that must be fetched and refreshed (OAuth2 client credentials, JWT),
implement `HttpClientTokenProvider` and return a `CompletionStage<String>` so the
fetch stays non-blocking. Cache the token and refresh ahead of expiry. See
[references/jwt-token-provider-reference.md](references/jwt-token-provider-reference.md)
and [references/oauth2-client-credentials-reference.md](references/oauth2-client-credentials-reference.md).

---

## Common pitfalls

| Symptom | Cause | Fix |
|---------|-------|-----|
| `Required dependency not found: ...http-client-auth` | The artifact does not exist | Depend on `http-client-common` + a transport (`http-client-ok`); use interceptors |
| Interceptor never runs | Used a non-existent `interceptors = {...}` attribute | Attach with `@InterceptWith(YourInterceptor.class)` |
| `cannot find symbol: method baseUrl()` | `@HttpClient` has no `baseUrl` attribute | Set `httpClient.<client>.url` in config (or `configPath`) |
| `@Value`/`@ConfigValue` not resolved | Those annotations do not exist in Kora | Bind a `@ConfigSource` interface and inject it via the constructor |
| `401` after refresh | Token expired mid-flight | Refresh ahead of expiry with a margin (e.g. 60s); see token cache reference |
| Duplicate token fetches under load | Concurrent refresh | Double-check + lock (or volatile fields); see token cache reference |
| Secret committed to VCS | Hard-coded credentials | Externalize with `${VAR}` substitution in config |

---

## Testing

Replace the real provider with a `@TestComponent` so no network call is made:

```java
@TestComponent
public final class TestTokenProvider implements HttpClientTokenProvider {
    @Override
    public CompletionStage<String> getToken(HttpClientRequest request) {
        return CompletableFuture.completedFuture("test-token-12345");
    }
}
```

```java
@KoraAppTest(Application.class)
class SecureApiClientTest {

    @Test
    void addsAuthorization(@TestComponent SecureApiClient client) {
        // Drive the client against a stub server (e.g. Testcontainers/WireMock)
        // and assert the upstream received the Authorization header.
        assertThat(client.getProtected()).isNotNull();
    }
}
```

See `kora-testing-junit-java` and `kora-testing-blackbox` for the full setup.

---

## Related skills

- `kora-http-client` — declarative HTTP clients, `@HttpRoute`, interceptors
- `kora-http-server-auth` — server-side Basic/Bearer/API-key
- `kora-config-hocon` — `@ConfigSource`, env substitution
- `kora-aop-logging` — `@Log` for client calls
- `kora-telemetry-tracing` — distributed tracing for outbound calls

## Source of truth

- Doc: `.kora-agent/kora-docs/mkdocs/docs/en/documentation/http-client.md` (Authorization section)
- Guide: `.kora-agent/kora-docs/mkdocs/docs/en/guides/http-client-advanced.md`
- Example: `.kora-agent/kora-examples/guides/java/kora-java-guide-http-client-advanced-app`
- Example: `.kora-agent/kora-examples/examples/java/kora-java-http-client`
