# HTTP Client Interceptors Reference

Reference for [kora-http-client](../SKILL.md).

## Contents

- [Overview](#overview)
- [HttpClientInterceptor interface](#httpclientinterceptor-interface)
- [Method-level interceptor](#method-level-interceptor)
- [Client-level interceptor](#client-level-interceptor)
- [Interceptors with dependencies](#interceptors-with-dependencies)
- [Built-in auth interceptors](#built-in-auth-interceptors)
- [Interceptor chain](#interceptor-chain)
- [Request modification](#request-modification)
- [Troubleshooting](#troubleshooting)

---

## Overview

Interceptors add cross-cutting behavior (auth, logging, tracing, custom headers) around HTTP calls without changing client code. They are wired with `@InterceptWith` on the whole `@HttpClient` interface or on a single method.

Import: `ru.tinkoff.kora.http.common.annotation.InterceptWith`.

---

## HttpClientInterceptor interface

```java
public interface HttpClientInterceptor {

    CompletionStage<HttpClientResponse> processRequest(
        Context ctx,
        InterceptChain chain,
        HttpClientRequest request) throws Exception;
}
```

| Parameter | Description |
|-----------|-------------|
| `ctx` | Kora `Context` propagating tracing/logging state |
| `chain` | Call `chain.process(ctx, request)` to invoke the next interceptor / the real call |
| `request` | The outgoing request; rebuild it with `request.toBuilder()` to modify |

Import: `ru.tinkoff.kora.http.client.common.interceptor.HttpClientInterceptor` (the nested `InterceptChain` is on that interface).

---

## Method-level interceptor

```java
@HttpClient(configPath = "httpClient.itemApi")
public interface ItemApiClient {

    final class LoggingInterceptor implements HttpClientInterceptor {

        private static final Logger log = LoggerFactory.getLogger(LoggingInterceptor.class);

        @Override
        public CompletionStage<HttpClientResponse> processRequest(
                Context ctx, InterceptChain chain, HttpClientRequest request) throws Exception {
            log.info("HTTP call: {} {}", request.method(), request.path());
            return chain.process(ctx, request)
                .whenComplete((response, error) ->
                    log.info("HTTP done: {} {}", request.method(), request.path()));
        }
    }

    @InterceptWith(LoggingInterceptor.class)
    @HttpRoute(method = HttpMethod.GET, path = "/items/{id}")
    @Json
    ItemResponse getItem(@Path String id);
}
```

---

## Client-level interceptor

Annotate the interface to apply the interceptor to every method:

```java
@Component
public final class ApiKeyAuthInterceptor implements HttpClientInterceptor {

    private final ApiKeyAuthConfig config;

    public ApiKeyAuthInterceptor(ApiKeyAuthConfig config) {
        this.config = config;
    }

    @Override
    public CompletionStage<HttpClientResponse> processRequest(
            Context ctx, InterceptChain chain, HttpClientRequest request) throws Exception {
        var authorized = request.toBuilder()
            .header("Authorization", config.value())
            .build();
        return chain.process(ctx, authorized);
    }
}

@InterceptWith(ApiKeyAuthInterceptor.class)
@HttpClient(configPath = "httpClient.dataApi")
public interface DataApiClient {

    @HttpRoute(method = HttpMethod.GET, path = "/items/{id}")
    @Json
    ItemResponse getItem(@Path String id);
}
```

```hocon
auth {
  apiKey { value = "secret-key-123", value = ${?API_KEY} }
}
```

---

## Interceptors with dependencies

A `@Component` interceptor receives any component via constructor injection - including a `@ConfigSource` config interface.

```java
@ConfigSource("auth.apiKey")
public interface ApiKeyAuthConfig {
    String value();
}
```

Kora has no `@ConfigValue` annotation; inject a `@ConfigSource` interface (as above) for typed config.

---

## Built-in auth interceptors

Kora ships interceptors for Basic, ApiKey, and Bearer/OAuth authorization. Expose one as a component (typically via a `default` method in a `@Module`), then attach it with `@InterceptWith`.

### Basic

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

@InterceptWith(BasicAuthHttpClientInterceptor.class)
@HttpClient(configPath = "httpClient.someClient")
public interface SomeClient { }
```

### ApiKey

`ApiKeyHttpClientInterceptor` takes the location (`ApiKeyLocation.HEADER` / `QUERY` / `COOKIE`), the parameter name, and the key value.

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

### Bearer / OAuth

`BearerAuthHttpClientInterceptor` takes an `HttpClientTokenProvider` (or a static token).

```java
public interface HttpClientTokenProvider {
    CompletionStage<String> getToken(HttpClientRequest request);
}

@Module
public interface BearerAuthModule {
    default BearerAuthHttpClientInterceptor bearerAuther(HttpClientTokenProvider provider) {
        return new BearerAuthHttpClientInterceptor(provider);
    }
}
```

OAuth uses the same mechanism: implement `HttpClientTokenProvider` and place it in the container.

---

## Interceptor chain

Multiple `@InterceptWith` annotations apply in declaration order. Each interceptor wraps the next via `chain.process`:

```java
@InterceptWith(LoggingInterceptor.class)
@InterceptWith(ApiKeyAuthInterceptor.class)
@HttpClient(configPath = "httpClient.someClient")
public interface SomeClient { }
```

`LoggingInterceptor` runs first (outermost), then `ApiKeyAuthInterceptor`, then the real call; responses unwind in reverse.

---

## Request modification

Always rebuild the request - the request object is not mutated in place.

```java
var modified = request.toBuilder()
    .header("X-Request-ID", UUID.randomUUID().toString())
    .build();
return chain.process(ctx, modified);
```

Conditional behavior can branch on the request:

```java
if (request.method().equals("POST")) {
    log.info("POST request: {}", request.path());
}
return chain.process(ctx, request);
```

---

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| Interceptor never runs | It must be a component (`@Component` or a `default` method in a `@Module`) and referenced by `@InterceptWith`. |
| Dependency not injected | Add a constructor that takes the dependency; the interceptor must be a component. |
| Header change has no effect | Build a new request with `request.toBuilder().header(...).build()` and pass it to `chain.process`. |
| Wrong `@InterceptWith` import | Use `ru.tinkoff.kora.http.common.annotation.InterceptWith`. |

---

## See also

- [declarative-client-reference](declarative-client-reference.md)
- [okhttp-transport-reference](okhttp-transport-reference.md)
- [error-handling-guide](error-handling-guide.md)
- [async-client-reference](async-client-reference.md)
