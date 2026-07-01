# Async HTTP Client Reference

Reference for [kora-http-client](../SKILL.md).

## Contents

- [Overview](#overview)
- [CompletionStage (Java)](#completionstage-java)
- [Parallel requests](#parallel-requests)
- [Project Reactor (Mono/Flux)](#project-reactor-monoflux)
- [Kotlin coroutines](#kotlin-coroutines)
- [Async with HttpResponseEntity](#async-with-httpresponseentity)
- [Async with interceptors](#async-with-interceptors)
- [Transport implementations](#transport-implementations)
- [Best practices](#best-practices)

---

## Overview

Declarative client methods may return an async type instead of the plain value. Use this for parallel fan-out calls, reactive pipelines, or non-blocking request handling. The transport (OkHttp/AsyncHttpClient/JDK) is always non-blocking underneath; the return type just controls how the result is surfaced.

---

## CompletionStage (Java)

```java
@HttpClient(configPath = "httpClient.itemApi")
public interface AsyncApiClient {

    @HttpRoute(method = HttpMethod.GET, path = "/items/{id}")
    @Json
    CompletionStage<ItemResponse> getItemAsync(@Path String id);

    @HttpRoute(method = HttpMethod.POST, path = "/items")
    @Json
    CompletionStage<ItemResponse> createItemAsync(@Json CreateItemRequest request);

    @HttpRoute(method = HttpMethod.DELETE, path = "/items/{id}")
    CompletionStage<Void> deleteItemAsync(@Path String id);
}
```

Usage:

```java
@Component
public final class ItemService {

    private final AsyncApiClient client;

    public ItemService(AsyncApiClient client) {
        this.client = client;
    }

    public CompletableFuture<ItemResponse> getItem(String id) {
        return client.getItemAsync(id).toCompletableFuture();
    }
}
```

---

## Parallel requests

Fan out and join:

```java
public CompletableFuture<List<ItemResponse>> getItems(List<String> ids) {
    List<CompletableFuture<ItemResponse>> futures = ids.stream()
        .map(id -> client.getItemAsync(id).toCompletableFuture())
        .toList();

    return CompletableFuture
        .allOf(futures.toArray(CompletableFuture[]::new))
        .thenApply(v -> futures.stream()
            .map(CompletableFuture::join)
            .toList());
}
```

Tolerate per-item failures with `exceptionally`:

```java
public CompletableFuture<List<ItemResponse>> getItemsResilient(List<String> ids) {
    List<CompletableFuture<ItemResponse>> futures = ids.stream()
        .map(id -> client.getItemAsync(id)
            .exceptionally(ex -> null)
            .toCompletableFuture())
        .toList();

    return CompletableFuture
        .allOf(futures.toArray(CompletableFuture[]::new))
        .thenApply(v -> futures.stream()
            .map(CompletableFuture::join)
            .filter(Objects::nonNull)
            .toList());
}
```

---

## Project Reactor (Mono/Flux)

Add the dependency:

```groovy
implementation "io.projectreactor:reactor-core"
```

```java
@HttpClient(configPath = "httpClient.itemApi")
public interface ReactiveApiClient {

    @HttpRoute(method = HttpMethod.GET, path = "/items/{id}")
    @Json
    Mono<ItemResponse> getItemReactive(@Path String id);
}
```

```java
public Flux<ItemResponse> getItems(List<String> ids) {
    return Flux.fromIterable(ids)
        .flatMap(client::getItemReactive);
}
```

---

## Kotlin coroutines

Add `org.jetbrains.kotlinx:kotlinx-coroutines-core` and use `suspend`:

```kotlin
@HttpClient(configPath = "httpClient.itemApi")
interface CoroutinesApiClient {

    @HttpRoute(method = HttpMethod.GET, path = "/items/{id}")
    @Json
    suspend fun getItem(@Path id: String): ItemResponse
}
```

```kotlin
@Component
class CoroutinesItemService(private val client: CoroutinesApiClient) {

    suspend fun getItems(ids: List<String>): List<ItemResponse> = coroutineScope {
        ids.map { id -> async { client.getItem(id) } }.awaitAll()
    }
}
```

---

## Async with HttpResponseEntity

```java
@HttpRoute(method = HttpMethod.GET, path = "/items/{id}")
@Json
CompletionStage<HttpResponseEntity<ItemResponse>> getItemWithStatus(@Path String id);

// Usage:
public CompletableFuture<ItemResponse> getItem(String id) {
    return client.getItemWithStatus(id)
        .thenApply(response -> {
            if (response.code() == 200) {
                return response.body();
            }
            throw new IllegalStateException("Unexpected status: " + response.code());
        })
        .toCompletableFuture();
}
```

---

## Async with interceptors

Interceptors are async by design - `processRequest` returns a `CompletionStage`. The same interceptor works for blocking and async methods.

```java
final class LoggingInterceptor implements HttpClientInterceptor {

    private static final Logger log = LoggerFactory.getLogger(LoggingInterceptor.class);

    @Override
    public CompletionStage<HttpClientResponse> processRequest(
            Context ctx, InterceptChain chain, HttpClientRequest request) {
        log.info("HTTP call: {} {}", request.method(), request.path());
        return chain.process(ctx, request);
    }
}

@HttpClient(configPath = "httpClient.itemApi")
@InterceptWith(LoggingInterceptor.class)
public interface AsyncApiClient {

    @HttpRoute(method = HttpMethod.GET, path = "/items/{id}")
    @Json
    CompletionStage<ItemResponse> getItemAsync(@Path String id);
}
```

---

## Transport implementations

| Capability | OkHttp (`http-client-ok`) | AsyncHttpClient (`http-client-async`) | JDK (`http-client-jdk`) |
|------------|---------------------------|---------------------------------------|-------------------------|
| Async return types | yes | yes | yes |
| HTTP/2 | yes | no | yes |
| HTTP/3 | yes | no | no |
| Module | `OkHttpClientModule` | `AsyncHttpClientModule` | `JdkHttpClientModule` |
| Recommendation | Default choice | Async HTTP Client based | JDK built-in |

AsyncHttpClient module setup:

```java
@KoraApp
public interface Application extends AsyncHttpClientModule, JsonModule { }
```

```hocon
httpClient {
  async { followRedirects = true }
  connectTimeout = "5s"
  readTimeout = "2m"
}
```

---

## Best practices

1. **Never block inside an async chain** - no `Thread.sleep` or `.join()` in a `thenApply`. Compose with `thenApply`/`thenCompose`.
2. **Handle failures** with `exceptionally` or, for declarative resilience, the `resilient-kora` annotations (`@Retry`, `@CircuitBreaker`, `@Fallback`).
3. **Bound the call** with `requestTimeout` in the client config rather than ad-hoc timeouts.

---

## See also

- [declarative-client-reference](declarative-client-reference.md)
- [okhttp-transport-reference](okhttp-transport-reference.md)
- [error-handling-guide](error-handling-guide.md)
- [interceptors-reference](interceptors-reference.md)
