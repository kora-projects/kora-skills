# HTTP Client Auth Reference

Authentication schemes for outgoing Kora HTTP clients.

## Contents

- [Authentication schemes overview](#authentication-schemes-overview)
- [Attaching interceptors](#attaching-interceptors)
- [Basic authentication](#basic-authentication)
- [API-key authentication](#api-key-authentication)
- [Bearer token](#bearer-token)
- [Correct dependencies](#correct-dependencies)
- [Config: @ConfigSource only](#config-configsource-only)
- [See also](#see-also)

Related references:
- [jwt-token-provider-reference.md](jwt-token-provider-reference.md) — `HttpClientTokenProvider` with caching/refresh
- [apikey-interceptor-reference.md](apikey-interceptor-reference.md) — custom header/query-param interceptor
- [token-cache-reference.md](token-cache-reference.md) — thread-safe token cache

Source of truth: `.kora-agent/kora-docs/mkdocs/docs/en/documentation/http-client.md` (Authorization section).

---

## Authentication schemes overview

| Scheme | Use case | Built-in interceptor |
|--------|----------|----------------------|
| Basic Auth | Simple username/password integrations | `BasicAuthHttpClientInterceptor` |
| Bearer / JWT | OAuth2 access tokens, session tokens | `BearerAuthHttpClientInterceptor` |
| API Key | Third-party APIs (header/query/cookie) | `ApiKeyHttpClientInterceptor` |

All three implement `HttpClientInterceptor` and ship in `http-client-common`.

---

## Attaching interceptors

Attach any interceptor with `@InterceptWith`. There is no `interceptors = {...}`
attribute on `@HttpClient`.

- On the interface — applies to every route.
- On a method — applies to that route only.

```java
@InterceptWith(BearerAuthHttpClientInterceptor.class)   // whole client
@HttpClient(configPath = "httpClient.secureApi")
public interface SecureApiClient {

    @HttpRoute(method = HttpMethod.GET, path = "/protected")
    void getProtected();

    @InterceptWith(MethodLoggingInterceptor.class)       // single route, in addition
    @HttpRoute(method = HttpMethod.GET, path = "/health")
    void health();
}
```

For an interceptor to be injectable it must be a component: either annotate the
class with `@Component`, or supply it from a `@Module` factory method (required for
the built-in interceptors, which are not annotated).

---

## Basic authentication

Format: `Authorization: Basic <base64(username:password)>`. The interceptor's
two-argument constructor performs the Base64 encoding.

```java
@Module
public interface BasicAuthModule {

    @ConfigSource("openapiAuth.basicAuth")
    interface BasicAuthConfig {
        String username();
        String password();
    }

    default BasicAuthHttpClientInterceptor basicAuther(BasicAuthConfig config) {
        return new BasicAuthHttpClientInterceptor(config.username(), config.password());
    }
}
```

```java
@HttpClient(configPath = "httpClient.someClient")
public interface SomeClient {

    @InterceptWith(BasicAuthHttpClientInterceptor.class)
    @HttpRoute(method = HttpMethod.GET, path = "/hello/world")
    void hello();
}
```

```hocon
openapiAuth.basicAuth {
    username = "myuser"
    password = ${BASIC_AUTH_PASSWORD}   // environment variable
}
```

`BasicAuthHttpClientInterceptor` also has a constructor accepting a custom
`HttpClientTokenProvider` if your secret-resolution rules differ.

---

## API-key authentication

Format: `X-API-KEY: <key>` (or query/cookie). The constructor takes the location,
the parameter name, and the secret.

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

`ApiKeyLocation` values: `HEADER`, `QUERY`, `COOKIE`.

```java
@HttpClient(configPath = "httpClient.someClient")
public interface SomeClient {

    @InterceptWith(ApiKeyHttpClientInterceptor.class)
    @HttpRoute(method = HttpMethod.GET, path = "/hello/world")
    void hello();
}
```

```hocon
openapiAuth.apiKeyAuth {
    apiKey = ${API_KEY}   // environment variable
}
```

For a non-standard header or query parameter that the built-in does not cover,
write a custom interceptor — see [apikey-interceptor-reference.md](apikey-interceptor-reference.md).

---

## Bearer token

Format: `Authorization: Bearer <token>`. Supply a token through
`HttpClientTokenProvider`, or a static token string via the single-arg constructor.

```java
@Module
public interface BearerAuthModule {

    default BearerAuthHttpClientInterceptor bearerAuther(HttpClientTokenProvider tokenProvider) {
        return new BearerAuthHttpClientInterceptor(tokenProvider);
    }
}
```

`HttpClientTokenProvider` (the published declarative API returns a
`CompletionStage<String>`, so token fetching can be asynchronous):

```java
public interface HttpClientTokenProvider {

    CompletionStage<String> getToken(HttpClientRequest request);
}
```

```java
@HttpClient(configPath = "httpClient.someClient")
public interface SomeClient {

    @InterceptWith(BearerAuthHttpClientInterceptor.class)
    @HttpRoute(method = HttpMethod.GET, path = "/hello/world")
    void hello();
}
```

A token provider that caches and refreshes is described in
[jwt-token-provider-reference.md](jwt-token-provider-reference.md). OAuth requires
the same building blocks — implement `HttpClientTokenProvider` and put it in the
container; see [oauth2-client-credentials-reference.md](oauth2-client-credentials-reference.md).

---

## Correct dependencies

```groovy
dependencies {
    koraBom platform("ru.tinkoff.kora:kora-parent:1.2.17")

    annotationProcessor "ru.tinkoff.kora:annotation-processors"

    implementation "ru.tinkoff.kora:http-client-common"   // interceptors live here
    implementation "ru.tinkoff.kora:http-client-ok"       // OkHttp transport
    // There is NO ru.tinkoff.kora:http-client-auth artifact.
}
```

---

## Config: @ConfigSource only

Kora resolves configuration through `@ConfigSource` interfaces injected as
components. There is no `@Value` or `@ConfigValue` annotation.

```java
// Correct
@ConfigSource("api")
public interface ApiConfig {
    String apiKey();
    String baseUrl();
}

public MyInterceptor(ApiConfig config) {
    this.apiKey = config.apiKey();
}
```

`@Value("${api.key}")` / `@ConfigValue("api.key")` do not exist in Kora — using
them is a hallucination. Bind a `@ConfigSource` interface instead.

---

## See also

- [apikey-interceptor-reference.md](apikey-interceptor-reference.md)
- [jwt-token-provider-reference.md](jwt-token-provider-reference.md)
- [token-cache-reference.md](token-cache-reference.md)
- [oauth2-client-credentials-reference.md](oauth2-client-credentials-reference.md)
