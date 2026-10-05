# OAuth2 Client Credentials Reference

Service-to-service authentication, assembled from the pieces `http-client-common` ships.

## Contents

- [What Kora provides and what it does not](#what-kora-provides-and-what-it-does-not)
- [The flow](#the-flow)
- [Token response](#token-response)
- [Auth client — credentials in the Basic header](#auth-client--credentials-in-the-basic-header)
- [Auth client — credentials in the body](#auth-client--credentials-in-the-body)
- [Token provider](#token-provider)
- [Module wiring](#module-wiring)
- [The secured client](#the-secured-client)
- [Configuration](#configuration)
- [Several audiences or scopes](#several-audiences-or-scopes)
- [OpenAPI-generated clients](#openapi-generated-clients)
- [Handling failures](#handling-failures)
- [Kotlin](#kotlin)
- [Testing](#testing)
- [See also](#see-also)

---

## What Kora provides and what it does not

`io.koraframework:http-client-common` ships `HttpClientTokenProvider`,
`BearerAuthHttpClientInterceptor` and `BasicAuthHttpClientInterceptor`. That is enough to build the
client-credentials grant, and it is all of it. There is **no** OAuth2 machinery in the framework:

| | |
|---|---|
| Kora gives you | The token contract, the Bearer/Basic interceptors, a declarative client for the token endpoint, `@InterceptWith` wiring |
| You write | The token request, the response DTO, the cache, the refresh policy, the retry |
| Kora has nothing for | Authorization-code / PKCE flows, refresh-token rotation, token introspection, JWT signature validation, mTLS client auth, dynamic client registration |

The last row is not an omission to work around: a user-consent flow needs a browser redirect and
session state, which a service-to-service HTTP client has no place for. Use a library, or the
identity provider's own SDK, and keep Kora out of it.

---

## The flow

1. `POST` `grant_type=client_credentials` (plus `scope`) to the token endpoint, authenticating with
   the client id and secret.
2. Read `access_token` and `expires_in`.
3. Send `Authorization: Bearer <access_token>` to the resource server.
4. Cache the token; refresh before `expires_in` elapses; invalidate on `401`.

All four steps are synchronous. Step 1 blocks the calling virtual thread, which is the intended
Kora 2.0 execution model — do not reach for `CompletionStage`, `Mono`, or Kotlin `suspend`.

---

## Token response

```java
@Json
public record OAuth2TokenResponse(
        @JsonField("access_token") String accessToken,
        @JsonField("token_type") String tokenType,
        @JsonField("expires_in") long expiresIn,
        @JsonField("scope") @Nullable String scope) {}
```

- `@Json` (`io.koraframework.json.common.annotation.Json`) marks the type;
  `@JsonField("access_token")` renames a component. `@Json("access_token")` is not a thing —
  `@Json` has no such attribute.
- `scope` is optional in RFC 6749 when it matches the request, so mark it `@Nullable`
  (`org.jspecify.annotations.Nullable`). A non-null field that the issuer omits fails deserialization.
- Artifact: `io.koraframework:json-common`, module `io.koraframework.json.common.JsonModule`.
  `json-module` and `ru.tinkoff.kora.json.module.JsonModule` do not exist in 2.0.

---

## Auth client — credentials in the Basic header

The RFC-preferred form: client id and secret go in `Authorization: Basic`, the grant in the body.

```java
@InterceptWith(BasicAuthHttpClientInterceptor.class)
@HttpClient("httpClient.oauth2")
public interface OAuth2AuthClient {

    @HttpRoute(method = HttpMethod.POST, path = "/oauth2/token")
    @Json
    OAuth2TokenResponse requestToken(FormUrlEncoded form);

    default OAuth2TokenResponse requestClientCredentialsToken(String scopes) {
        return scopes.isBlank()
                ? requestToken(new FormUrlEncoded(
                        new FormUrlEncoded.FormPart("grant_type", "client_credentials")))
                : requestToken(new FormUrlEncoded(
                        new FormUrlEncoded.FormPart("grant_type", "client_credentials"),
                        new FormUrlEncoded.FormPart("scope", scopes)));
    }
}
```

`io.koraframework.http.common.form.FormUrlEncoded`; `FormUrlEncoded.FormPart(String name, String value)`
is a nested record and the varargs constructor takes them directly. The
`FormUrlEncoded` request mapper is a `@DefaultComponent` of `HttpClientRequestMapperModule`, so no
mapper wiring is needed.

**Never attach a Bearer interceptor to this client.** It authenticates with the client secret;
giving it the token interceptor makes fetching a token require a token.

---

## Auth client — credentials in the body

Some issuers only accept `client_id`/`client_secret` as form fields. Then drop `@InterceptWith`
entirely and put them in the form:

```java
@HttpClient("httpClient.oauth2")
public interface OAuth2AuthClient {

    @HttpRoute(method = HttpMethod.POST, path = "/oauth2/token")
    @Json
    OAuth2TokenResponse requestToken(FormUrlEncoded form);
}
```

```java
var form = new FormUrlEncoded(
        new FormUrlEncoded.FormPart("grant_type", "client_credentials"),
        new FormUrlEncoded.FormPart("client_id", config.clientId()),
        new FormUrlEncoded.FormPart("client_secret", config.clientSecret()),
        new FormUrlEncoded.FormPart("scope", config.scopes()));
```

A secret in the body is not masked by `maskHeaders`, which covers headers only. With
`httpClient.oauth2.telemetry.logging.enabled` and the auth client's request logger at `TRACE`, the
form body — secret included — is logged verbatim unless a `@Tag(HttpClientTelemetry.class)`
`FormUrlencodedDataMasker` is in the graph (the token response's `access_token` likewise needs a
`JsonDataMasker`; see [http-client-auth-reference.md](http-client-auth-reference.md#keeping-the-credential-out-of-the-logs)).
Prefer the Basic-header form, where `authorization` is masked by default.

---

## Token provider

```java
@Component
public final class OAuth2ClientCredentialsProvider implements HttpClientTokenProvider {

    private final TokenCache cache;
    private final OAuth2AuthClient authClient;
    private final OAuth2Config config;

    public OAuth2ClientCredentialsProvider(TokenCache cache, OAuth2AuthClient authClient, OAuth2Config config) {
        this.cache = cache;
        this.authClient = authClient;
        this.config = config;
    }

    @Override
    public String getToken(HttpClientRequest request) {
        return cache.getOrRefresh(() -> {
            var response = authClient.requestClientCredentialsToken(config.scopes());
            return TokenCache.Token.of(response.accessToken(), Duration.ofSeconds(response.expiresIn()));
        });
    }

    public void invalidate() {
        cache.invalidate();
    }
}
```

The lifetime comes from `expires_in`; `TokenCache` refreshes 60 s before it and serialises
concurrent refreshes behind one lock so a burst of traffic produces one token request. See
[token-cache-reference.md](token-cache-reference.md).

---

## Module wiring

```java
@ConfigSource("oauth2")
public interface OAuth2Config {

    String clientId();

    String clientSecret();

    default String scopes() { return ""; }
}
```

```java
@Module
public interface OAuth2Module {

    default BasicAuthHttpClientInterceptor oauth2ClientCredentials(OAuth2Config config) {
        return new BasicAuthHttpClientInterceptor(config.clientId(), config.clientSecret());
    }

    default BearerAuthHttpClientInterceptor secureApiBearer(HttpClientTokenProvider provider) {
        return new BearerAuthHttpClientInterceptor(provider);
    }
}
```

```java
@KoraApp
public interface Application extends
        HoconConfigModule,
        JsonModule,
        LogbackModule,
        OkHttpClientModule,
        OAuth2Module {

    static void main(String[] args) {
        KoraApplication.run(ApplicationGraph::graph);
    }
}
```

Only `OAuth2Module` goes in `extends` — it is hand-written. `OAuth2Config`, `OAuth2AuthClient` and
`SecureApiClient` are registered by the config and HTTP-client processors;
`OAuth2ClientCredentialsProvider` and `TokenCache` carry `@Component`. Do not also declare them in a
`@Module`, or the build fails with `Multiple components match dependency:`.

Declare `clientId()` and `clientSecret()` non-`@Nullable`. A `@Nullable` secret reaching
`BasicAuthHttpClientInterceptor` makes its token provider return `null`, and the interceptor then
sends the token request **with no `Authorization` header** — the failure surfaces as a `401` from
the issuer instead of a startup error.

---

## The secured client

```java
@InterceptWith(BearerAuthHttpClientInterceptor.class)
@HttpClient("httpClient.secureApi")
public interface SecureApiClient {

    @HttpRoute(method = HttpMethod.GET, path = "/protected/resource")
    @Json
    Resource getResource();
}
```

---

## Configuration

```hocon
oauth2 {
  clientId     = "my-service-client"
  clientSecret = ${OAUTH2_CLIENT_SECRET}
  scopes       = "api:read api:write"
}

httpClient {
  oauth2 {
    url = "https://auth.example"
    requestTimeout = 5s
  }
  secureApi {
    url = "https://api.example"
    requestTimeout = 10s
    telemetry.logging {
      enabled     = true
      maskHeaders = ["authorization", "set-cookie", "cookie"]
    }
  }
}
```

- `${OAUTH2_CLIENT_SECRET}` is required — startup fails if it is unset. Use `${?VAR}` only where a
  default is genuinely acceptable.
- The auth client's `requestTimeout` should be **shorter** than the business client's: its call runs
  inside the business request's budget, holding the refresh lock.
- `maskHeaders` **replaces** the default `["authorization", "set-cookie", "cookie"]` rather than
  extending it; names are compared lower-cased, so their case does not matter. Restate the
  defaults whenever you set it. See [http-client-auth-reference.md](http-client-auth-reference.md#keeping-the-credential-out-of-the-logs).

---

## Several audiences or scopes

One token per audience. Do not share a `TokenCache` between them — a cache holds one token, so two
audiences sharing one cache overwrite each other on every request and each call carries the other's
token roughly half the time.

Give each audience its own tagged cache and provider:

```java
public final class OrdersApi {}
public final class BillingApi {}
```

```java
@Module
public interface AudienceModule {

    @Tag(OrdersApi.class)
    default TokenCache ordersTokenCache() {
        return new TokenCache();
    }

    @Tag(BillingApi.class)
    default TokenCache billingTokenCache() {
        return new TokenCache();
    }

    @Tag(OrdersApi.class)
    default BearerAuthHttpClientInterceptor ordersBearer(@Tag(OrdersApi.class) HttpClientTokenProvider provider) {
        return new BearerAuthHttpClientInterceptor(provider);
    }
}
```

```java
@Component
@Tag(OrdersApi.class)
public final class OrdersTokenProvider implements HttpClientTokenProvider {

    public OrdersTokenProvider(@Tag(OrdersApi.class) TokenCache cache, OAuth2AuthClient authClient) { … }
}
```

```java
@InterceptWith(value = BearerAuthHttpClientInterceptor.class, tag = OrdersApi.class)
@HttpClient("httpClient.orders")
public interface OrdersClient { … }
```

`@InterceptWith` takes `Class<?> tag()` for exactly this. Without the tags every claim matches every
candidate and the build fails with
`Multiple components match dependency: BearerAuthHttpClientInterceptor (no tags)`.

When `TokenCache` is provided from a `@Module` like this, remove `@Component` from the class.

---

## OpenAPI-generated clients

If the client is generated from an OpenAPI contract, the generator emits an `ApiSecurity` `@Module`
and you do not write interceptors at all. It supplies token providers for `http basic` and `apiKey`
schemes from generated config; for **`bearer` and `oauth2` schemes it supplies nothing**, and the
graph requires one provider per scheme that appears in an operation's `security` list — including
the alternatives that operation never actually takes, because the generated interceptor's
constructor asks for every scheme in every alternative. A scheme declared under
`components/securitySchemes` and referenced by no operation needs nothing:

```java
@KoraApp
public interface Application extends HoconConfigModule, JsonModule, LogbackModule, OkHttpClientModule {

    @Tag(ApiSecurity.OAuth.class)
    default HttpClientTokenProvider oAuthTokenProvider(OAuth2ClientCredentialsProvider provider) {
        return provider;                              // bare token; the interceptor adds "Bearer "
    }

    @Tag(ApiSecurity.BearerAuth.class)
    default HttpClientTokenProvider bearerAuthTokenProvider() {
        return request -> null;                       // scheme unused — must return null
    }
}
```

Three rules, all from the generated interceptor's own shape:

1. It evaluates the security **alternatives** in declaration order and applies the first one whose
   providers **all** returned non-null. A provider for an alternative you never use that returns
   anything non-null wins, and the request goes out with the wrong header, silently.
2. If no alternative comes out complete, the request is forwarded with **no** credential after a
   single `WARN Security schema is defined for api but no data was provided` — the call then fails
   as a `401` from the upstream, not as an error in your process.
3. It writes `authorization` with the scheme prefix itself — `"Basic "` for `http`/`basic`,
   `"Bearer "` for `http`/`bearer`, `oauth2` and `openId` — so the provider returns the **bare**
   token, the same contract as `BearerAuthHttpClientInterceptor`. Returning `"Bearer " + token`
   sends `Bearer Bearer …`.

Everything else about generated clients — the `ApiSecurity` tag names, the security config prefix,
the per-API config path — is [kora-openapi-generator-client](../../kora-openapi-generator-client/SKILL.md).

---

## Handling failures

| Failure | What you see | What to do |
|---|---|---|
| Issuer rejects the client secret | `HttpClientResponseException`, `getCode() == 401`, from the **auth** client | Fail loudly. Do not retry — the secret is wrong or revoked |
| Resource server rejects the token | `401` from the business client | `invalidate()` and retry **once**; see [jwt-token-provider-reference.md](jwt-token-provider-reference.md#retrying-a-401) |
| Resource server returns `403` | Scope/permission problem | Do not retry — a fresh token is just as unauthorized |
| Issuer unreachable | `HttpClientConnectionException` / `HttpClientTimeoutException` | Let it propagate; add `@CircuitBreakable`/`@Retryable` on the auth client if the issuer is flaky ([kora-aop-resilient](../../kora-aop-resilient/SKILL.md)) |
| Response missing `access_token` | `HttpClientDecoderException` | The endpoint or the DTO is wrong — check `@JsonField` names against the real payload |

The exception types are `io.koraframework.http.client.common.exception.*`
(`HttpClientResponseException`, `HttpClientDecoderException`, `HttpClientConnectionException`,
`HttpClientTimeoutException`), all extending `HttpClientException`.
`HttpClientResponseException.getCode()` gives the status, `getHeaders()` the response headers, and
`getBytes()` the body — the whole body when the transport already had it buffered, otherwise the
first 4 KiB it could read from the stream. Either way it is enough to log the issuer's
`error_description` without leaking the request.

---

## Kotlin

```kotlin
@Component
class OAuth2ClientCredentialsProvider(
    private val cache: TokenCache,
    private val authClient: OAuth2AuthClient,
    private val config: OAuth2Config
) : HttpClientTokenProvider {

    override fun getToken(request: HttpClientRequest): String? = cache.getOrRefresh {
        val response = authClient.requestClientCredentialsToken(config.scopes())
        TokenCache.Token.of(response.accessToken, Duration.ofSeconds(response.expiresIn))
    }

    fun invalidate() = cache.invalidate()
}
```

Declare the return type `String?` — that is what the `@Nullable` contract means, and it is required
once the implementation can return null (a non-null `String` return also compiles, as a covariant
narrowing). Callers get `String?` from `getToken` and must handle it; see
[jwt-token-provider-reference.md](jwt-token-provider-reference.md#kotlin).

No `suspend`, no `runBlocking`, no `Dispatchers.IO`: `suspend` is not a Kora contract and the call
is already on a virtual thread.

---

## Testing

```java
@KoraAppTest(Application.class)
class OAuth2ClientCredentialsTest implements KoraAppTestGraphModifier {

    @Override
    public KoraGraphModification graph() {
        return KoraGraphModification.create()
                .replaceComponent(HttpClientTokenProvider.class,
                        () -> (HttpClientTokenProvider) request -> "test-access-token");
    }

    @Test
    void callsTheResourceServer(@TestComponent SecureApiClient client) {
        assertThat(client.getResource()).isNotNull();
    }
}
```

Test the token flow itself against a stub issuer rather than by mocking — the parts that break are
the form encoding, the `@JsonField` names and the expiry arithmetic, none of which a mocked provider
exercises. See [kora-testing-blackbox](../../kora-testing-blackbox/SKILL.md).

---

## See also

- [jwt-token-provider-reference.md](jwt-token-provider-reference.md) — the provider and the 401 retry
- [token-cache-reference.md](token-cache-reference.md) — single-flight caching
- [http-client-auth-reference.md](http-client-auth-reference.md) — interceptors, tags, masking
- [apikey-interceptor-reference.md](apikey-interceptor-reference.md) — hand-written interceptors
