# JWT / Bearer Token Provider Reference

How to implement `HttpClientTokenProvider` so the `BearerAuthHttpClientInterceptor`
always sends a fresh token.

## Contents

- [HttpClientTokenProvider interface](#httpclienttokenprovider-interface)
- [Provider with caching](#provider-with-caching)
- [Auth client to fetch the token](#auth-client-to-fetch-the-token)
- [Wiring it together](#wiring-it-together)
- [Testing](#testing)
- [See also](#see-also)

Source of truth: `.kora-agent/kora-docs/mkdocs/docs/en/documentation/http-client.md` (Bearer section).

---

## HttpClientTokenProvider interface

The published declarative Bearer API returns a `CompletionStage<String>` so token
fetching stays non-blocking:

```java
public interface HttpClientTokenProvider {

    /**
     * Returns the authorization token asynchronously. Implementations should cache
     * and refresh the token internally.
     *
     * @param request the HTTP request being executed
     * @return a CompletionStage with the token value
     */
    CompletionStage<String> getToken(HttpClientRequest request);
}
```

Register a single implementation as a component; the `BearerAuthHttpClientInterceptor`
factory in your `@Module` receives it.

---

## Provider with caching

Keep a `TokenCache` (see [token-cache-reference.md](token-cache-reference.md)) and
refresh ahead of expiry with a margin so a token never expires mid-flight.

```java
@Component
public final class JwtTokenProvider implements HttpClientTokenProvider {

    private static final Duration REFRESH_MARGIN = Duration.ofSeconds(60);

    private final TokenCache tokenCache;
    private final AuthClient authClient;

    public JwtTokenProvider(TokenCache tokenCache, AuthClient authClient) {
        this.tokenCache = tokenCache;
        this.authClient = authClient;
    }

    @Override
    public CompletionStage<String> getToken(HttpClientRequest request) {
        String cached = tokenCache.get();
        if (cached != null && !tokenCache.isExpiringSoon(REFRESH_MARGIN)) {
            return CompletableFuture.completedFuture(cached);
        }
        return authClient.fetchToken()
                .thenApply(response -> {
                    tokenCache.set(response.accessToken(), Duration.ofSeconds(response.expiresIn()));
                    return response.accessToken();
                });
    }
}
```

Key points:
1. **Refresh margin** — refresh 60s before expiry.
2. **Caching** — avoid hammering the auth service.
3. **Thread safety** — `TokenCache` must be safe under concurrent access.
4. **Async** — return a `CompletionStage` for non-blocking work.

---

## Auth client to fetch the token

A separate declarative `@HttpClient` calls the token endpoint. Use BasicAuth for
the client_id/secret and form-encoded parameters.

```java
@HttpClient(configPath = "httpClient.auth")
public interface AuthClient {

    @InterceptWith(BasicAuthHttpClientInterceptor.class)
    @HttpRoute(method = HttpMethod.POST, path = "/oauth2/token")
    @Json
    CompletionStage<TokenResponse> fetchToken(FormUrlEncoded form);

    default CompletionStage<TokenResponse> fetchToken() {
        return fetchToken(new FormUrlEncoded(
                new FormUrlEncoded.FormPart("grant_type", "client_credentials")));
    }

    @Json
    record TokenResponse(
            @Json(value = "access_token") String accessToken,
            @Json(value = "token_type") String tokenType,
            @Json(value = "expires_in") long expiresIn) {}
}
```

```hocon
httpClient.auth {
    url = "https://auth.example.com"
}
openapiAuth.basicAuth {
    username = ${AUTH_CLIENT_ID}
    password = ${AUTH_CLIENT_SECRET}
}
```

The exact `FormUrlEncoded` factory methods are documented in `kora-http-client`;
adapt the constructor call to your Kora version if it differs.

---

## Wiring it together

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
    CompletionStage<ProtectedResponse> getProtected();
}
```

`BasicAuthHttpClientInterceptor` is also registered as a component (from a `@Module`
factory) so the `AuthClient` can reference it through `@InterceptWith`.

---

## Testing

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
class JwtTokenProviderTest {

    @Test
    void cachesToken(@TestComponent JwtTokenProvider provider) {
        var first = provider.getToken(null).toCompletableFuture().join();
        var second = provider.getToken(null).toCompletableFuture().join();
        assertThat(first).isEqualTo(second);
    }
}
```

---

## See also

- [token-cache-reference.md](token-cache-reference.md)
- [http-client-auth-reference.md](http-client-auth-reference.md)
- [oauth2-client-credentials-reference.md](oauth2-client-credentials-reference.md)
