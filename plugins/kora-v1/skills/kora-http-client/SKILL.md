---
name: kora-http-client
description: "Declarative Kora HTTP clients - @HttpClient interface with @HttpRoute, parameter mapping (@Path/@Query/@Header/@Cookie), @Json bodies, HttpResponseEntity, @Mapping and @ResponseCodeMapper, @InterceptWith interceptors, and OkHttp/AsyncHttpClient/JDK transports. Use when building a typed outbound HTTP client in a Kora service, wiring auth interceptors (Basic/ApiKey/Bearer), configuring per-client timeouts and telemetry under httpClient.*, or handling HttpClientResponseException. Not for OpenAPI-generated clients (use kora-openapi-generator-client) or for the inbound @HttpController server (use kora-http-server)."
---

# Kora HTTP Client

Declarative, compile-time HTTP clients: annotate an interface with `@HttpClient`, declare methods with `@HttpRoute`, and the annotation processor generates the implementation. No reflection, no runtime proxies. Inject the client interface like any other Kora component.

**Dependencies:** `http-client-ok` (transport) + `json-module` (for `@Json`) + `annotation-processors`.

All Kora artifacts inherit their version from the `ru.tinkoff.kora:kora-parent` BOM (the examples pin `1.2.17`). Never version individual `ru.tinkoff.kora:*` artifacts.

---

## Quick Start

### 1. Dependencies (Java)

```groovy
dependencies {
    koraBom platform("ru.tinkoff.kora:kora-parent:1.2.17")

    annotationProcessor "ru.tinkoff.kora:annotation-processors"

    implementation "ru.tinkoff.kora:http-client-ok"
    implementation "ru.tinkoff.kora:json-module"
    implementation "ru.tinkoff.kora:config-hocon"
}
```

For Kotlin, use `ksp "ru.tinkoff.kora:symbol-processors"` instead of `annotationProcessor`.

### 2. Plug the transport module into `@KoraApp`

```java
@KoraApp
public interface Application extends
        HoconConfigModule,
        JsonModule,
        OkHttpClientModule {
}
```

### 3. Declare the client interface

```java
@HttpClient(configPath = "httpClient.userApi")
public interface UserApiClient {

    @HttpRoute(method = HttpMethod.GET, path = "/users/{userId}")
    @Json
    UserResponse getUser(@Path String userId);

    @HttpRoute(method = HttpMethod.GET, path = "/users")
    @Json
    List<UserResponse> listUsers(@Query("page") int page, @Query("size") int size);

    @HttpRoute(method = HttpMethod.POST, path = "/users")
    @Json
    HttpResponseEntity<UserResponse> createUser(@Json CreateUserRequest request);

    @HttpRoute(method = HttpMethod.DELETE, path = "/users/{userId}")
    void deleteUser(@Path String userId);
}
```

### 4. Configuration (HOCON)

The client resolves config at `httpClient.{lower-case class name}` by default, or at the path given in `configPath`. The `url` key is required.

```hocon
httpClient {
  userApi {
    url = "http://localhost:8080"
    url = ${?USER_API_URL}
    requestTimeout = "10s"
  }
}
```

### 5. Inject and use

```java
@Component
public final class UserService {

    private final UserApiClient client;

    public UserService(UserApiClient client) {
        this.client = client;
    }

    public UserResponse getUser(String id) {
        return client.getUser(id);
    }
}
```

---

## What's in `references/` and `assets/`

| File | Purpose |
|------|---------|
| `references/declarative-client-reference.md` | `@HttpClient`, `@HttpRoute`, parameter & body mapping, `@Mapping`, `@ResponseCodeMapper`, signatures, per-client/per-method config |
| `references/async-client-reference.md` | `CompletionStage`, Project Reactor `Mono`, Kotlin `suspend`, AsyncHttpClient/JDK transports |
| `references/error-handling-guide.md` | `HttpClientResponseException`, `HttpClientDecoderException`, `HttpResponseEntity`, status-aware decoding |
| `references/interceptors-reference.md` | `HttpClientInterceptor`, `@InterceptWith`, built-in Basic/ApiKey/Bearer auth, resilience |
| `references/okhttp-transport-reference.md` | OkHttp config keys, HTTP versions, proxy, `OkHttpConfigurer`, telemetry |
| `assets/UserApiClient.java.template` | Base CRUD client (Java) |
| `assets/UserApiClient.kt.template` | Base CRUD client (Kotlin) |
| `assets/ResilientApiClient.java.template` | Client with `@Retry`/`@CircuitBreaker`/`@Timeout`/`@Fallback` |
| `assets/AsyncApiClient.java.template` | Async client returning `CompletionStage` |
| `assets/CustomMapperClient.java.template` | `@Mapping` request body + `@ResponseCodeMapper` |
| `assets/ApiKeyAuthInterceptor.java.template` | Custom `HttpClientInterceptor` for API key auth |

---

## When to use vs NOT

**Use this skill when:**
- Building a typed outbound HTTP client interface with `@HttpClient` + `@HttpRoute`.
- Mapping parameters via `@Path`, `@Query`, `@Header`, `@Cookie`, `@Json`.
- Adding `@InterceptWith` interceptors for auth, logging, or tracing.
- Configuring per-client timeouts, proxy, HTTP version, or telemetry under `httpClient.*`.

**Do NOT use when:**
- You have an OpenAPI contract and want a generated client - use `kora-openapi-generator-client`.
- You need the inbound HTTP server (`@HttpController`) - use `kora-http-server`.
- You need only the raw imperative `HttpClient.execute(request)` API - that is covered briefly below and in full in the docs.

---

## Core patterns

### Parameter mapping

| Annotation | Import | Example |
|------------|--------|---------|
| `@Path` | `ru.tinkoff.kora.http.common.annotation.Path` | `@Path String id` -> `/users/{id}` |
| `@Query` | `ru.tinkoff.kora.http.common.annotation.Query` | `@Query("page") int p` -> `?page=1` |
| `@Header` | `ru.tinkoff.kora.http.common.annotation.Header` | `@Header("X-Trace-ID") String tid` |
| `@Cookie` | `ru.tinkoff.kora.http.common.annotation.Cookie` | `@Cookie("sessionId") String sid` |
| `@Json` | `ru.tinkoff.kora.json.common.annotation.Json` | `@Json CreateUserRequest req` |
| `@Mapping` | `ru.tinkoff.kora.common.Mapping` | `@Mapping(TextMapper.class) Body b` |

The parameter name defaults to the method argument name; override it with `value` (e.g. `@Path("userId")`). Arguments are required by default; mark `@Nullable` to make them optional.

### Response handling

By default the response is decoded for `2xx` status codes; any other status throws `HttpClientResponseException` (carrying `code()`, the body, and headers). To inspect the status and headers yourself, return `HttpResponseEntity<T>`:

```java
@HttpRoute(method = HttpMethod.GET, path = "/users/{userId}")
@Json
HttpResponseEntity<UserResponse> getUser(@Path String userId);

// In the caller:
HttpResponseEntity<UserResponse> response = client.getUser("123");
if (response.code() == 200) {
    return response.body();
}
```

`HttpResponseEntity` exposes `code()`, `body()`, and `headers()`. See [error-handling-guide](references/error-handling-guide.md).

### JSON bodies

`@Json` on a parameter writes it as JSON; `@Json` on the method reads the response as JSON. The `json-module` dependency is required.

```java
@HttpRoute(method = HttpMethod.POST, path = "/users")
@Json
UserResponse createUser(@Json CreateUserRequest request);

@Json
record CreateUserRequest(String email, String name) {}

@Json
record UserResponse(String id, String email, String name) {}
```

### Interceptors

Implement `HttpClientInterceptor` and attach it with `@InterceptWith` on the interface (client-wide) or a single method. Mutate the request via `request.toBuilder()` - mutating in place has no effect.

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
public interface DataApiClient { }
```

`@InterceptWith` imports from `ru.tinkoff.kora.http.common.annotation.InterceptWith`. Kora also ships built-in auth interceptors (`BasicAuthHttpClientInterceptor`, `ApiKeyHttpClientInterceptor`, `BearerAuthHttpClientInterceptor`) - see [interceptors-reference](references/interceptors-reference.md).

### Async signatures

Methods may return `T`, `CompletionStage<T>`, or (with `reactor-core`) `Mono<T>`. In Kotlin a method may be `suspend` (requires `kotlinx-coroutines-core`).

```java
@HttpRoute(method = HttpMethod.GET, path = "/items/{id}")
@Json
CompletionStage<ItemResponse> getItemAsync(@Path String id);
```

See [async-client-reference](references/async-client-reference.md).

### Resilience

Resilience comes from the separate `resilient-kora` module (`ResilientModule`), not from the HTTP client itself. Its aspect annotations take a single config name; the actual values live under `resilient.*` in config.

```groovy
implementation "ru.tinkoff.kora:resilient-kora"
```

```java
@HttpClient(configPath = "httpClient.itemApi")
public interface ItemApiClient {

    @Retry("itemApi")
    @HttpRoute(method = HttpMethod.GET, path = "/items/{id}")
    @Json
    ItemResponse getItem(@Path String id);

    @CircuitBreaker("itemApi")
    @HttpRoute(method = HttpMethod.POST, path = "/items")
    @Json
    ItemResponse createItem(@Json CreateItemRequest request);

    @Timeout("itemApi")
    @Fallback(value = "itemApi", method = "listItemsFallback()")
    @HttpRoute(method = HttpMethod.GET, path = "/items")
    @Json
    List<ItemResponse> listItems();

    default List<ItemResponse> listItemsFallback() {
        return List.of();
    }
}
```

```hocon
resilient {
  retry { itemApi { delay = "100ms", attempts = 3 } }
  circuitbreaker { itemApi { slidingWindowSize = 20, minimumRequiredCalls = 10, failureRateThreshold = 50 } }
  timeout { itemApi { duration = "5s" } }
}
```

> The annotation does **not** take `maxAttempts`, `failureThreshold`, or a `@Backoff`. There is no inline tuning - use the named `resilient.*` config block. See the `kora-aop-resilient` skill for the full configuration reference.

### Transport selection

| Module | Artifact | HTTP/2 | HTTP/3 | Note |
|--------|----------|--------|--------|------|
| `OkHttpClientModule` | `http-client-ok` | yes | yes | Default choice |
| `AsyncHttpClientModule` | `http-client-async` | no | no | Async HTTP Client based |
| `JdkHttpClientModule` | `http-client-jdk` | yes | no | JDK built-in client |

Only one transport module is plugged into `@KoraApp` at a time. See [okhttp-transport-reference](references/okhttp-transport-reference.md).

### Imperative client

Inject the base `HttpClient` and build requests by hand when a declarative interface does not fit:

```java
HttpClientRequest request = HttpClientRequest.of("POST", "http://localhost:8090/pets/{petId}")
        .templateParam("petId", "1")
        .queryParam("page", 1)
        .header("token", "12345")
        .body(HttpBody.plaintext("refresh"))
        .build();
CompletionStage<HttpClientResponse> response = httpClient.execute(request);
```

---

## Common pitfalls

| Symptom | Fix |
|---------|-----|
| `@HttpClient(baseUrl = ...)` does not compile | `@HttpClient` has no `baseUrl`. Use `configPath` and supply `url` in config. |
| "Required dependency not found" for the client | Plug a transport module (`OkHttpClientModule`) into `@KoraApp` and add `annotation-processors`. |
| `@Json` body not serialized | Add `json-module` and `JsonModule`; annotate the DTO with `@Json`. |
| Interceptor header change ignored | Build a new request with `request.toBuilder().header(...).build()`; do not mutate in place. |
| Wrong `@InterceptWith` import | It is `ru.tinkoff.kora.http.common.annotation.InterceptWith`. |
| Non-2xx silently swallowed | Non-2xx throws `HttpClientResponseException` unless you return `HttpResponseEntity<T>` or use `@ResponseCodeMapper`. |
| `@Retry(maxAttempts = ...)` rejected | Resilient annotations take a config name string; tune values under `resilient.*`. |

---

## References

- [declarative-client-reference](references/declarative-client-reference.md) - `@HttpClient`, `@HttpRoute`, parameters, mappers, config
- [async-client-reference](references/async-client-reference.md) - `CompletionStage`, Reactor, coroutines, transports
- [error-handling-guide](references/error-handling-guide.md) - exceptions, `HttpResponseEntity`, status-aware decoding
- [interceptors-reference](references/interceptors-reference.md) - interceptors, auth, request/response modification
- [okhttp-transport-reference](references/okhttp-transport-reference.md) - OkHttp config, HTTP versions, proxy

Source of truth: `.kora-agent/kora-docs/mkdocs/docs/en/documentation/http-client.md`; examples `.kora-agent/kora-examples/guides/java/kora-java-guide-http-client-app` and `kora-java-guide-http-client-advanced-app`.

## Related skills

- `kora-http-server` - inbound `@HttpController`
- `kora-openapi-generator-client` - generate clients from an OpenAPI spec
- `kora-aop-resilient` - `@Retry`, `@CircuitBreaker`, `@Timeout`, `@Fallback`
- `kora-json` - `@Json` DTOs
