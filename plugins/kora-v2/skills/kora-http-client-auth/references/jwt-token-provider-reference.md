# Bearer / JWT Token Provider Reference

Implementing `HttpClientTokenProvider` so `BearerAuthHttpClientInterceptor` always sends a valid
token.

## Contents

- [The contract](#the-contract)
- [Static token](#static-token)
- [The auth client](#the-auth-client)
- [The caching provider](#the-caching-provider)
- [Wiring](#wiring)
- [Configuration](#configuration)
- [Retrying a 401](#retrying-a-401)
- [Kotlin](#kotlin)
- [Testing](#testing)
- [Porting a 1.x provider](#porting-a-1x-provider)
- [See also](#see-also)

---

## The contract

```java
package io.koraframework.http.client.common.auth;

public interface HttpClientTokenProvider {

    @Nullable String getToken(HttpClientRequest request);
}
```

`BearerAuthHttpClientInterceptor` calls it **once per request** and then sets
`authorization: Bearer <token>`. Return the bare token; the interceptor adds the prefix.

Returning `null` makes the interceptor forward the request **with no `Authorization` header**. Use
that deliberately (a scheme that does not apply to this request) and never as an error path — a
failed token fetch should throw, so the caller sees the real cause instead of an upstream `401`.

Because `getToken` receives the `HttpClientRequest`, a single provider can serve different tokens
per route:

```java
@Override
public String getToken(HttpClientRequest request) {
    return request.uriTemplate().startsWith("/admin")
            ? tokens.getOrRefresh(this::fetchAdminToken)
            : tokens.getOrRefresh(this::fetchUserToken);
}
```

`uriTemplate()` is the un-substituted path (`/users/{id}`), which is what you want for routing
decisions; `uri()` is the resolved absolute `URI`.

---

## Static token

When the token comes from the environment and never changes, no provider is needed:

```java
@ConfigSource("auth.api")
public interface ApiTokenConfig {

    String token();
}
```

```java
@Module
public interface BearerAuthModule {

    default BearerAuthHttpClientInterceptor bearerAuthInterceptor(ApiTokenConfig config) {
        return new BearerAuthHttpClientInterceptor(config.token());
    }
}
```

Declare `token()` non-`@Nullable`: a missing key then fails at startup with `ConfigValueException`
instead of silently sending unauthenticated requests.

---

## The auth client

The token endpoint is just another declarative client. Client credentials go in `Authorization:
Basic` via the built-in interceptor, and the body is a form:

```java
@InterceptWith(BasicAuthHttpClientInterceptor.class)
@HttpClient("httpClient.auth")
public interface AuthClient {

    @HttpRoute(method = HttpMethod.POST, path = "/oauth2/token")
    @Json
    TokenResponse requestToken(FormUrlEncoded form);

    default TokenResponse requestToken() {
        return requestToken(new FormUrlEncoded(
                new FormUrlEncoded.FormPart("grant_type", "client_credentials")));
    }

    @Json
    record TokenResponse(
            @JsonField("access_token") String accessToken,
            @JsonField("token_type") String tokenType,
            @JsonField("expires_in") long expiresIn) {}
}
```

- `io.koraframework.http.common.form.FormUrlEncoded`, with the nested record
  `FormUrlEncoded.FormPart(String name, String value)`. The `FormUrlEncoded` request mapper is a
  `@DefaultComponent` of `HttpClientRequestMapperModule`, so nothing extra is wired.
- JSON field renaming is `@JsonField("access_token")` from
  `io.koraframework.json.common.annotation` — **not** `@Json("access_token")`. `@Json` marks the
  type; `@JsonField` renames a component. The artifact is `io.koraframework:json-common`
  (`json-module` does not exist in 2.0).
- The method returns `TokenResponse` directly. `CompletionStage` and `Mono` are not Kora 2.0
  contracts, and in Kotlin neither is `suspend`.
- The auth client and the business client are separate `@HttpClient` interfaces with separate
  config paths. Do not attach the Bearer interceptor to the auth client — that is how you get an
  infinite token-fetch recursion.

---

## The caching provider

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

    public void invalidate() {
        cache.invalidate();
    }
}
```

The fetch blocks the calling virtual thread — correct in 2.0, and cheap. What is **not** optional is
that concurrent callers must produce one fetch: `TokenCache.getOrRefresh` reads without a lock, then
takes a `ReentrantLock` and re-checks. See
[token-cache-reference.md](token-cache-reference.md); do not re-derive it inline.

The token's real lifetime comes from `expires_in`, and the cache refreshes 60 s before it. Never
hard-code an assumed lifetime.

---

## Wiring

```java
@Module
public interface SecureApiAuthModule {

    default BearerAuthHttpClientInterceptor secureApiBearer(HttpClientTokenProvider provider) {
        return new BearerAuthHttpClientInterceptor(provider);
    }

    default BasicAuthHttpClientInterceptor authClientBasic(OAuth2Config config) {
        return new BasicAuthHttpClientInterceptor(config.clientId(), config.clientSecret());
    }
}
```

```java
@InterceptWith(BearerAuthHttpClientInterceptor.class)
@HttpClient("httpClient.secureApi")
public interface SecureApiClient {

    @HttpRoute(method = HttpMethod.GET, path = "/protected")
    @Json
    ProtectedResponse getProtected();
}
```

```java
@KoraApp
public interface Application extends
        HoconConfigModule,
        JsonModule,
        LogbackModule,
        OkHttpClientModule,
        SecureApiAuthModule {

    static void main(String[] args) {
        KoraApplication.run(ApplicationGraph::graph);
    }
}
```

`SecureApiAuthModule` is hand-written and **must** appear in `@KoraApp extends`. `CachingTokenProvider`
carries `@Component`, and `AuthClient`, `SecureApiClient` and the `@ConfigSource` interfaces are
registered by their processors — none of those go in the `extends` list.

---

## Configuration

```hocon
oauth2 {
  clientId     = "my-service"
  clientSecret = ${OAUTH2_CLIENT_SECRET}
}

httpClient {
  auth {
    url = "https://auth.example"
    requestTimeout = 5s
  }
  secureApi {
    url = "https://api.example"
    requestTimeout = 10s
  }
}
```

Give the auth client a **shorter** `requestTimeout` than the business client: its call happens
inside the business request's own budget, under a lock that other callers are queued on.

---

## Retrying a 401

The token can be revoked, or invalidated server-side, before the refresh margin elapses. Handle it
in a small interceptor that replaces `BearerAuthHttpClientInterceptor` rather than sitting next to
it — otherwise both write the `Authorization` header:

```java
@Component
public final class BearerRetryInterceptor implements HttpClientInterceptor {

    private final CachingTokenProvider tokens;

    public BearerRetryInterceptor(CachingTokenProvider tokens) {
        this.tokens = tokens;
    }

    @Override
    public HttpClientResponse processRequest(InterceptChain chain, HttpClientRequest request) throws Exception {
        var response = chain.process(authorized(request));
        if (response.code() != 401) {
            return response;
        }
        response.close();
        tokens.invalidate();
        return chain.process(authorized(request));      // exactly one retry
    }

    private HttpClientRequest authorized(HttpClientRequest request) {
        return request.toBuilder()
                .header("authorization", "Bearer " + tokens.getToken(request))
                .build();
    }
}
```

```java
@InterceptWith(BearerRetryInterceptor.class)
@HttpClient("httpClient.secureApi")
public interface SecureApiClient { … }
```

Three things this gets right and a naive version does not:

1. **The discarded response is closed.** `HttpClientResponse` is `Closeable`; the generated client
   only closes the response it finally returns. Skipping `close()` leaks the connection back to the
   pool's limit.
2. **The request is rebuilt from the original**, not from the already-authorized one. `header(...)`
   replaces, so re-authorizing the same object also works — but a query- or cookie-based scheme
   appends, and rebuilding from the original is the habit that stays correct there.
3. **One retry, not a loop.** A revoked credential in a retry loop is a request storm against the
   auth server, and it fails the same way each time.

Do not retry a `403`: that is "this token is not allowed to do this", and a fresh token will be
just as unauthorized.

---

## Kotlin

```kotlin
@Component
class CachingTokenProvider(
    private val cache: TokenCache,
    private val authClient: AuthClient
) : HttpClientTokenProvider {

    override fun getToken(request: HttpClientRequest): String? = cache.getOrRefresh {
        val response = authClient.requestToken()
        TokenCache.Token.of(response.accessToken, Duration.ofSeconds(response.expiresIn))
    }

    fun invalidate() = cache.invalidate()
}
```

Declare the return type `String?`. That is what the contract means, and it is required the moment
the implementation can return null. A non-null `String` return also compiles — narrowing a nullable
return is ordinary Kotlin variance — so keep `String` only for a provider that always has a token.

The nullability is enforced on the **calling** side instead: `@Nullable` on `getToken` is read from
the class file, so Kotlin types the result `String?` and
`val token: String = provider.getToken(request)` fails with
`initializer type mismatch: expected 'String', actual 'String?'`. Handle it with `?:`, not `!!`.

(`http-client-common` carries `@NullMarked` on `module-info.java` and has no
`package-info.java`, so with the jar on the classpath Kotlin sees *parameters* as platform types —
`request: HttpClientRequest` and `request: HttpClientRequest?` are both accepted. The per-member
`@Nullable` on the return value is honoured either way.)

```kotlin
@InterceptWith(BasicAuthHttpClientInterceptor::class)
@HttpClient("httpClient.auth")
interface AuthClient {

    @HttpRoute(method = HttpMethod.POST, path = "/oauth2/token")
    @Json
    fun requestToken(form: FormUrlEncoded): TokenResponse

    fun requestToken(): TokenResponse = requestToken(
        FormUrlEncoded(FormUrlEncoded.FormPart("grant_type", "client_credentials"))
    )

    @Json
    data class TokenResponse(
        @JsonField("access_token") val accessToken: String,
        @JsonField("token_type") val tokenType: String,
        @JsonField("expires_in") val expiresIn: Long
    )
}
```

`HttpClientTokenProvider` is a single-method interface, so a trivial one is a SAM lambda:
`HttpClientTokenProvider { null }`.

---

## Testing

Test the provider without a network by replacing the auth client, and test the wiring by replacing
the provider:

```java
@KoraAppTest(Application.class)
class SecureApiClientTest implements KoraAppTestGraphModifier {

    @Override
    public KoraGraphModification graph() {
        return KoraGraphModification.create()
                .replaceComponent(HttpClientTokenProvider.class,
                        () -> (HttpClientTokenProvider) request -> "test-token");
    }

    @Test
    void callsTheProtectedRoute(@TestComponent SecureApiClient client) {
        assertThat(client.getProtected()).isNotNull();
    }
}
```

`io.koraframework.test.extension.junit5.{KoraAppTest, TestComponent, KoraAppTestGraphModifier, KoraGraphModification}`.
`@TestComponent` targets **fields and parameters** — it pulls a component out of the graph; it does
not declare one. Adding it to a class does nothing.

Asserting that the header actually left the process needs a stub upstream — see
[kora-testing-blackbox](../../kora-testing-blackbox/SKILL.md).

---

## Porting a 1.x provider

```java
// Kora 1.x
@Override
public CompletionStage<String> getToken(HttpClientRequest request) {
    var cached = cache.get();
    if (cached != null && !cache.isExpiringSoon(MARGIN)) {
        return CompletableFuture.completedFuture(cached);
    }
    return authClient.fetchToken()
            .thenApply(rs -> { cache.set(rs.accessToken(), Duration.ofSeconds(rs.expiresIn())); return rs.accessToken(); });
}
```

```java
// Kora 2.0
@Override
public String getToken(HttpClientRequest request) {
    return cache.getOrRefresh(() -> {
        var rs = authClient.requestToken();
        return TokenCache.Token.of(rs.accessToken(), Duration.ofSeconds(rs.expiresIn()));
    });
}
```

| 1.x | 2.0 |
|---|---|
| `CompletionStage<String> getToken(...)` | `@Nullable String getToken(...)` |
| `thenApply` / `thenCompose` refresh chain | straight-line blocking code on a virtual thread |
| Kotlin `suspend` provider, `Dispatchers.IO` | plain function; no dispatcher, no `runBlocking` |
| `ru.tinkoff.kora.http.client.common.auth.HttpClientTokenProvider` | `io.koraframework.http.client.common.auth.HttpClientTokenProvider` |
| `jakarta.annotation.Nullable` | `org.jspecify.annotations.Nullable` (type-use) |
| `@Json("access_token")` on a component | `@JsonField("access_token")` |
| `@HttpClient(configPath = "httpClient.auth")` | `@HttpClient("httpClient.auth")` |

The 1.x cache's `getOrRefresh(Supplier<CompletionStage<String>>)` cannot be mechanically unwrapped:
it took the lock and then returned an *unfinished* future from inside it, so the lock was released
before the fetch completed and the single-flight guarantee it appeared to give was never real.
Replace it with the synchronous cache rather than deleting the `CompletionStage` from its signature.

---

## See also

- [token-cache-reference.md](token-cache-reference.md) — the cache this provider is built on
- [oauth2-client-credentials-reference.md](oauth2-client-credentials-reference.md) — the full flow with scopes
- [http-client-auth-reference.md](http-client-auth-reference.md) — attaching the interceptor
- [apikey-interceptor-reference.md](apikey-interceptor-reference.md) — hand-written interceptors
