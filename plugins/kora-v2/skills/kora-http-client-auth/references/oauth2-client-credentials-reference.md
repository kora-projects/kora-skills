# OAuth2 Client Credentials Reference

Service-to-service authentication with the OAuth2 client-credentials grant. Kora
does not ship a ready-made OAuth2 flow; you assemble it from `HttpClientTokenProvider`,
a declarative auth `@HttpClient`, and a token cache.

## Contents

- [The flow](#the-flow)
- [Token response DTO](#token-response-dto)
- [Auth client](#auth-client)
- [Token provider](#token-provider)
- [Module wiring](#module-wiring)
- [Secured client](#secured-client)
- [Configuration](#configuration)
- [Testing](#testing)
- [See also](#see-also)

Source of truth: `.kora-agent/kora-docs/mkdocs/docs/en/documentation/http-client.md` (OAuth/Bearer sections).

---

## The flow

1. POST `client_id` + `client_secret` + `grant_type=client_credentials` to the
   token endpoint.
2. Receive `access_token`, `token_type`, `expires_in`.
3. Send `Authorization: Bearer <access_token>` to the resource server.
4. Cache the token; refresh before `expires_in` elapses.

---

## Token response DTO

```java
@Json
public record OAuth2TokenResponse(
        @Json(value = "access_token") String accessToken,
        @Json(value = "token_type") String tokenType,
        @Json(value = "expires_in") long expiresIn,
        @Json(value = "scope") String scope) {}
```

---

## Auth client

A declarative client that authenticates with the client_id/secret via BasicAuth and
posts form parameters:

```java
@HttpClient(configPath = "httpClient.oauth2")
public interface OAuth2AuthClient {

    @InterceptWith(BasicAuthHttpClientInterceptor.class)
    @HttpRoute(method = HttpMethod.POST, path = "/oauth2/token")
    @Json
    CompletionStage<OAuth2TokenResponse> requestToken(FormUrlEncoded form);

    default CompletionStage<OAuth2TokenResponse> requestClientCredentialsToken(String scope) {
        return requestToken(new FormUrlEncoded(
                new FormUrlEncoded.FormPart("grant_type", "client_credentials"),
                new FormUrlEncoded.FormPart("scope", scope)));
    }
}
```

Register the BasicAuth interceptor with the client_id/secret:

```java
@Module
public interface OAuth2AuthModule {

    @ConfigSource("oauth2")
    interface OAuth2Config {
        String clientId();
        String clientSecret();
        default String scopes() { return ""; }
    }

    default BasicAuthHttpClientInterceptor oauth2BasicAuth(OAuth2Config config) {
        return new BasicAuthHttpClientInterceptor(config.clientId(), config.clientSecret());
    }
}
```

---

## Token provider

```java
@Component
public final class OAuth2ClientCredentialsProvider implements HttpClientTokenProvider {

    private final TokenCache cache;
    private final OAuth2AuthClient authClient;
    private final String scopes;

    public OAuth2ClientCredentialsProvider(
            TokenCache cache, OAuth2AuthClient authClient, OAuth2AuthModule.OAuth2Config config) {
        this.cache = cache;
        this.authClient = authClient;
        this.scopes = config.scopes();
    }

    @Override
    public CompletionStage<String> getToken(HttpClientRequest request) {
        return cache.getOrRefresh(() ->
                authClient.requestClientCredentialsToken(scopes)
                        .thenApply(response -> {
                            cache.set(response.accessToken(),
                                    Duration.ofSeconds(response.expiresIn()));
                            return response.accessToken();
                        }));
    }
}
```

`TokenCache.getOrRefresh` performs the double-checked locking so concurrent
requests never trigger more than one token fetch. See
[token-cache-reference.md](token-cache-reference.md).

---

## Module wiring

```java
@Module
public interface BearerAuthModule {

    default BearerAuthHttpClientInterceptor bearerAuther(HttpClientTokenProvider tokenProvider) {
        return new BearerAuthHttpClientInterceptor(tokenProvider);
    }
}
```

---

## Secured client

```java
@HttpClient(configPath = "httpClient.secureApi")
public interface SecureApiClient {

    @InterceptWith(BearerAuthHttpClientInterceptor.class)
    @HttpRoute(method = HttpMethod.GET, path = "/protected/resource")
    @Json
    CompletionStage<Resource> getResource();
}
```

---

## Configuration

```hocon
oauth2 {
    clientId = "my-service-client"
    clientSecret = ${OAUTH2_CLIENT_SECRET}   // environment variable
    scopes = "api:read api:write"
}

httpClient {
    oauth2    { url = "https://auth.example.com" }
    secureApi { url = "https://api.example.com" }
}
```

---

## Testing

```java
@TestComponent
public final class TestOAuth2Provider implements HttpClientTokenProvider {
    @Override
    public CompletionStage<String> getToken(HttpClientRequest request) {
        return CompletableFuture.completedFuture("test-access-token");
    }
}
```

```java
@KoraAppTest(Application.class)
class OAuth2ClientCredentialsTest {

    @Test
    void callsResourceServer(@TestComponent SecureApiClient client) {
        var response = client.getResource().toCompletableFuture().join();
        assertThat(response).isNotNull();
    }
}
```

---

## See also

- [token-cache-reference.md](token-cache-reference.md)
- [jwt-token-provider-reference.md](jwt-token-provider-reference.md)
- [http-client-auth-reference.md](http-client-auth-reference.md)
