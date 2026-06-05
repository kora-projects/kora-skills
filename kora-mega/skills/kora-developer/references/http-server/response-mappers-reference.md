# Response Mappers Reference

**Source:** [.kora-agent/kora-docs/mkdocs/docs/en/documentation/http-server.md](.kora-agent/kora-docs/mkdocs/docs/en/documentation/http-server.md)  
**Examples:** `.kora-agent/kora-examples/kora-java-http-server/`

## Built-in Response Types

### String

```java
@HttpRoute(method = HttpMethod.GET, path = "/text")
public String getText() {
    return "Hello World";
}
// Response: 200 OK, Content-Type: text/plain, Body: "Hello World"
```

### byte[]

```java
@HttpRoute(method = HttpMethod.GET, path = "/bytes")
public byte[] getBytes() {
    return new byte[]{1, 2, 3};
}
// Response: 200 OK, Content-Type: application/octet-stream
```

### ByteBuffer

```java
@HttpRoute(method = HttpMethod.GET, path = "/buffer")
public ByteBuffer getBuffer() {
    return ByteBuffer.wrap(new byte[]{1, 2, 3});
}
```

### HttpServerResponse

Full control over the response.

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

**HttpBody factories:**
```java
HttpBody.plaintext(String)           // text/plain
HttpBody.json(byte[])                // application/json
HttpBody.octetStream(byte[])         // application/octet-stream
HttpBody.html(String)                // text/html
HttpBody.xml(String)                 // application/xml
```

### HttpResponseEntity<T>

Wrapper for a response with custom headers.

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

## @Json Response

Automatic JSON serialization.

```java
@Component
@HttpController
public final class UserController {
    
    @Json
    public record UserResponse(String id, String name) {}
    
    @HttpRoute(method = HttpMethod.GET, path = "/users/{id}")
    @Json
    public UserResponse getById(@Path String id) {
        return new UserResponse(id, "John");
    }
}
```

**How it works:**
1. Kora looks for `HttpResultMapper<UserResponse>` tagged with `@Json`
2. If not found — generates one via `JsonWriter<UserResponse>`
3. Requires `json-module` dependency

**Important:** The DTO must have the `@Json` annotation for mapper generation.

## Custom Response Mapper

Implement `HttpServerResponseMapper<T>` for custom serialization.

```java
public record XmlData(String value) {}

public static final class XmlMapper implements HttpServerResponseMapper<XmlData> {
    @Override
    public HttpServerResponse apply(Context ctx, HttpServerRequest request, XmlData result) {
        String xml = "<data>" + escapeXml(result.value()) + "</data>";
        return HttpServerResponse.of(
            200,
            HttpHeaders.of("Content-Type", "application/xml"),
            HttpBody.plaintext(xml)
        );
    }
    
    private String escapeXml(String value) {
        return value.replace("&", "&amp;")
                    .replace("<", "&lt;")
                    .replace(">", "&gt;");
    }
}

@Component
@HttpController
public final class XmlController {
    
    @Mapping(XmlMapper.class)
    @HttpRoute(method = HttpMethod.GET, path = "/xml")
    public XmlData getXml() {
        return new XmlData("test");
    }
}
```

## Error Responses

### HttpServerResponseException

```java
@HttpRoute(method = HttpMethod.GET, path = "/users/{id}")
@Json
public UserResponse getById(@Path String id) {
    if (id == null || id.isBlank()) {
        throw HttpServerResponseException.of(400, "Invalid ID");
    }
    if ("notfound".equals(id)) {
        throw HttpServerResponseException.of(404, "User not found");
    }
    return new UserResponse(id, "John");
}
```

### HttpResponseEntity with error status

```java
@HttpRoute(method = HttpMethod.GET, path = "/users/{id}")
@Json
public HttpResponseEntity<UserResponse> getById(@Path String id) {
    if ("notfound".equals(id)) {
        return HttpResponseEntity.of(
            404,
            HttpHeaders.of("X-Error-Code", "USER_NOT_FOUND"),
            new UserResponse(id, "Not Found")
        );
    }
    return HttpResponseEntity.of(
        200,
        HttpHeaders.empty(),
        new UserResponse(id, "John")
    );
}
```

## Reactive Responses

### Project Reactor Mono

```java
@HttpRoute(method = HttpMethod.GET, path = "/users/{id}")
@Json
public Mono<UserResponse> getById(@Path String id) {
    return userService.findById(id)
        .switchIfEmpty(Mono.error(
            HttpServerResponseException.of(404, "User not found")
        ));
}
```

### CompletableFuture

```java
@HttpRoute(method = HttpMethod.GET, path = "/users/{id}")
@Json
public CompletableFuture<UserResponse> getById(@Path String id) {
    return userService.findByIdAsync(id)
        .thenApply(Optional::orElseThrow)
        .exceptionally(e -> {
            throw HttpServerResponseException.of(500, e.getMessage());
        });
}
```

### Kotlin Coroutines

```kotlin
@HttpRoute(method = HttpMethod.GET, path = "/users/{id}")
@Json
suspend fun getById(@Path id: String): UserResponse {
    return userService.findById(id) 
        ?: throw HttpServerResponseException.of(404, "User not found")
}
```

## Response Headers

```java
@HttpRoute(method = HttpMethod.GET, path = "/users/{id}")
@Json
public HttpResponseEntity<UserResponse> getById(@Path String id) {
    return HttpResponseEntity.of(
        200,
        HttpHeaders.of(
            "X-Request-Id", "abc123",
            "Cache-Control", "no-cache",
            "X-Rate-Limit-Remaining", "100"
        ),
        new UserResponse(id, "John")
    );
}
```

## Content Negotiation

```java
@HttpRoute(method = HttpMethod.GET, path = "/users/{id}")
public HttpServerResponse getById(
    @Path String id,
    @Header("Accept") @Nullable String accept
) {
    UserResponse user = userService.findById(id);
    
    if (accept != null && accept.contains("application/xml")) {
        return HttpServerResponse.of(
            200,
            HttpHeaders.of("Content-Type", "application/xml"),
            HttpBody.plaintext(toXml(user))
        );
    }
    
    // Default JSON
    return HttpServerResponse.of(
        200,
        HttpHeaders.of("Content-Type", "application/json"),
        HttpBody.json(toJson(user))
    );
}
```
