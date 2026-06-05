# HttpClientInterceptor Reference

**Source:** [.kora-agent/kora-docs/mkdocs/docs/en/documentation/http-client.md](.kora-agent/kora-docs/mkdocs/docs/en/documentation/http-client.md)  
**Examples:** `.kora-agent/kora-examples/kora-java-http-client/`

## Overview

`HttpClientInterceptor` for intercepting and modifying HTTP requests/responses: authentication, logging, metrics, error handling.

```java
public interface HttpClientInterceptor {
    CompletionStage<HttpClientResponse> intercept(Context context, HttpClientRequest request, InterceptChain chain);
}
```

> **Important:** Interceptors use `CompletionStage` for asynchronous processing. Declarative clients use synchronous signatures (`T method()`). Imperative clients use `CompletionStage` (non-blocking) or `.toCompletableFuture().join()` (synchronous).

## Interceptor Types

### Authentication Interceptors

**Basic Auth:**
```java
public final class BasicAuthHttpClientInterceptor implements HttpClientInterceptor {
    private final String credentials;
    public BasicAuthHttpClientInterceptor(String username, String password) {
        this.credentials = Base64.getEncoder().encodeToString((username + ":" + password).getBytes(StandardCharsets.UTF_8));
    }
    @Override
    public CompletionStage<HttpClientResponse> intercept(Context context, HttpClientRequest request, InterceptChain chain) {
        HttpClientRequest authRequest = request.toBuilder().header("Authorization", "Basic " + credentials).build();
        return chain.process(context, authRequest);
    }
}
```

**API Key:**
```java
public final class ApiKeyAuthHttpClientInterceptor implements HttpClientInterceptor {
    private final String apiKey, headerName;
    public ApiKeyAuthHttpClientInterceptor(String apiKey, String headerName) { this.apiKey = apiKey; this.headerName = headerName; }
    @Override
    public CompletionStage<HttpClientResponse> intercept(Context context, HttpClientRequest request, InterceptChain chain) {
        HttpClientRequest authRequest = request.toBuilder().header(headerName, apiKey).build();
        return chain.process(context, authRequest);
    }
}
```

**Bearer Token:**
```java
public final class BearerAuthHttpClientInterceptor implements HttpClientInterceptor {
    private final Supplier<String> tokenSupplier;
    public BearerAuthHttpClientInterceptor(Supplier<String> tokenSupplier) { this.tokenSupplier = tokenSupplier; }
    @Override
    public CompletionStage<HttpClientResponse> intercept(Context context, HttpClientRequest request, InterceptChain chain) {
        HttpClientRequest authRequest = request.toBuilder().header("Authorization", "Bearer " + tokenSupplier.get()).build();
        return chain.process(context, authRequest);
    }
}
```

### Logging Interceptor

```java
@Tag(MyApiClient.class) @Component
public final class LoggingHttpClientInterceptor implements HttpClientInterceptor {
    private static final Logger log = LoggerFactory.getLogger(LoggingHttpClientInterceptor.class);
    
    @Override
    public CompletionStage<HttpClientResponse> intercept(Context context, HttpClientRequest request, InterceptChain chain) {
        long startTime = System.nanoTime();
        log.debug("Request: {} {}", request.method(), request.uri());
        log.debug("Headers: {}", request.headers());
        return chain.process(context, request).thenApply(response -> {
            log.debug("Response: {} in {}ms", response.code(), (System.nanoTime() - startTime) / 1_000_000);
            return response;
        });
    }
}
```

## Registration

**Module-Level:**
```java
@Module
public interface HttpClientInterceptorsModule {
    @ConfigSource("httpClient.my-api.auth")
    interface AuthConfig { String username(); String password(); }
    
    @DefaultComponent
    default BasicAuthHttpClientInterceptor basicAuthInterceptor(AuthConfig config) {
        return new BasicAuthHttpClientInterceptor(config.username(), config.password());
    }
    @DefaultComponent
    default LoggingHttpClientInterceptor loggingInterceptor() { return new LoggingHttpClientInterceptor(); }
}
```

**Method-Level:** `@InterceptWith(LoggingInterceptor.class)` on a client method.

**Client-Level:** `@Tag(MyApiClient.class) @Component` — applied to all methods of the client.

**Global:** `@Tag(HttpClientModule.class) @Component` — applied to all HTTP clients.

## Interceptor Chain

Call order: 1) Global (`@Tag(HttpClientModule.class)`), 2) Client-level (`@Tag(MyApiClient.class)`), 3) Method-level (`@InterceptWith`), 4) HTTP request.

## Best Practices

1. **Focused** — single responsibility
2. **Error handling** — do not swallow exceptions
3. **Preserve context** — propagate `Context` through the chain
4. **Fast** — avoid blocking operations

## Related

- [Client Annotation Reference](client-annotation-reference.md)
- [Configuration Reference](configuration-reference.md)
