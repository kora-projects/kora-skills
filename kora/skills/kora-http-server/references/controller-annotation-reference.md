# Controller Annotation Reference

**Source:** [.kora-agent/kora-docs/mkdocs/docs/en/documentation/http-server.md](.kora-agent/kora-docs/mkdocs/docs/en/documentation/http-server.md)  
**Examples:** `.kora-agent/kora-examples/kora-java-http-server/`

## @HttpController

Marker annotation for classes that contain HTTP request handlers.

```java
@Component
@HttpController
public final class UserController {
    // Controller methods
}
```

**Requirements:**
- The class must be `public` and `final`
- Must be registered as a component (`@Component`)
- Handler methods must have `@HttpRoute`

## @HttpRoute

Defines the HTTP method and path for a handler.

```java
@HttpRoute(
    method = HttpMethod.POST,
    path = "/users/{id}/posts"
)
public PostResponse createPost(@Path String id, @Json PostRequest request) {
    // ...
}
```

### Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `method` | `HttpMethod` | Yes | HTTP method |
| `path` | `String` | Yes | URL path template |

### HTTP Methods

```java
HttpMethod.GET
HttpMethod.POST
HttpMethod.PUT
HttpMethod.PATCH
HttpMethod.DELETE
HttpMethod.HEAD
HttpMethod.OPTIONS
```

### Path Templates

```java
// Static path
@HttpRoute(method = HttpMethod.GET, path = "/health")

// Single path parameter
@HttpRoute(method = HttpMethod.GET, path = "/users/{id}")

// Multiple path parameters
@HttpRoute(method = HttpMethod.GET, path = "/users/{userId}/posts/{postId}")

// Path with fixed suffix
@HttpRoute(method = HttpMethod.GET, path = "/api/v1/users")
```

## @Component

Registers the controller in Kora's DI container.

```java
@Component
@HttpController
public final class UserController {
    
    private final UserService userService;
    
    // Constructor injection
    public UserController(UserService userService) {
        this.userService = userService;
    }
}
```

**Without `@Component` the controller will not be registered and requests will not be handled.**

## Return Types

### Primitive Types

```java
@HttpRoute(method = HttpMethod.GET, path = "/text")
public String getText() {
    return "plain text";
}

@HttpRoute(method = HttpMethod.GET, path = "/bytes")
public byte[] getBytes() {
    return new byte[]{1, 2, 3};
}
```

### HttpServerResponse

Full control over the HTTP response.

```java
@HttpRoute(method = HttpMethod.GET, path = "/custom")
public HttpServerResponse custom() {
    return HttpServerResponse.of(
        200,  // status code
        HttpHeaders.of("X-Custom", "value", "Content-Type", "application/json"),
        HttpBody.plaintext("{\"key\":\"value\"}")
    );
}
```

### HttpResponseEntity<T>

Response with body + custom headers.

```java
@HttpRoute(method = HttpMethod.GET, path = "/entity")
@Json
public HttpResponseEntity<UserResponse> entity() {
    return HttpResponseEntity.of(
        200,
        HttpHeaders.of("X-Request-Id", "abc123"),
        new UserResponse("1", "John")
    );
}
```

### CompletionStage (Async)

```java
@HttpRoute(method = HttpMethod.GET, path = "/async")
@Json
public CompletionStage<UserResponse> async() {
    return CompletableFuture.supplyAsync(() -> userService.findById(id));
}
```

> **Important:** Although Kora supports `CompletionStage` for asynchronous operations, **it is recommended to use synchronous signatures** (`T method()`) for simplicity and code readability. The asynchronous approach should be used only when genuinely necessary (for example, when integrating with a legacy async API).

### Kotlin Coroutines

```kotlin
@HttpRoute(method = HttpMethod.GET, path = "/suspend")
@Json
suspend fun getSuspend(): UserResponse {
    return userService.findById(id)
}
```

> **Important:** Kotlin coroutines require the additional `kora-kotlin` module. Use only if the project already uses coroutines.

## Method Signature Requirements

**Recommended signatures:**
- `T method()` — sync (primary approach)
- `CompletionStage<T> method()` — async (only when necessary)
- `suspend fun method()` — Kotlin coroutines (only if the project uses coroutines)

**Not recommended:**
- `Mono<T> method()` — Project Reactor requires additional dependencies, not recommended without a strong reason

**Invalid signatures:**
- `void method()` — void is not supported (use `HttpServerResponse` for an empty response)
- `List<T> method()` — use `List<T>` directly (no need to wrap in reactive types)
