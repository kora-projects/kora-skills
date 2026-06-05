# Request Parameters Reference

**Source:** [.kora-agent/kora-docs/mkdocs/docs/en/documentation/http-server.md](.kora-agent/kora-docs/mkdocs/docs/en/documentation/http-server.md)  
**Examples:** `.kora-agent/kora-examples/kora-java-http-server/`

## Parameter Annotations

### @Path

Extracts a value from the URL path template.

```java
@HttpRoute(method = HttpMethod.GET, path = "/users/{id}")
@Json
public UserResponse getById(@Path("id") String userId) {
    // userId is extracted from /users/123
}
```

**Rules:**
- The name in `@Path("name")` must match the name in the path template
- If no name is specified — the method parameter name is used
- Parameters are required by default

```java
// Name matches the parameter name
@HttpRoute(method = HttpMethod.GET, path = "/users/{id}")
@Json
public UserResponse getById(@Path String id) { ... }

// Explicit name
@HttpRoute(method = HttpMethod.GET, path = "/users/{user_id}")
@Json
public UserResponse getById(@Path("user_id") String id) { ... }
```

### @Query

Extracts a value from the query string.

```java
@HttpRoute(method = HttpMethod.GET, path = "/users")
@Json
public List<UserResponse> search(
    @Query("name") String name,
    @Query("limit") Integer limit,
    @Query("offset") @Nullable Integer offset
) { ... }
```

**List query parameters:**
```java
@HttpRoute(method = HttpMethod.GET, path = "/users")
@Json
public List<UserResponse> filter(
    @Query("status") List<String> statuses  // ?status=active&status=pending
) { ... }
```

### @Header

Extracts a value from an HTTP header.

```java
@HttpRoute(method = HttpMethod.GET, path = "/users/{id}")
@Json
public UserResponse getById(
    @Path String id,
    @Header("X-Trace-Id") String traceId,
    @Header("Authorization") @Nullable String auth
) { ... }
```

**Common headers:**
```java
@Header("Content-Type") String contentType
@Header("Accept") String accept
@Header("Authorization") @Nullable String auth
@Header("X-Request-Id") String requestId
@Header("User-Agent") String userAgent
```

### @Cookie

Extracts a value from a cookie.

```java
@HttpRoute(method = HttpMethod.GET, path = "/session")
@Json
public SessionResponse getSession(
    @Cookie("session_id") String sessionId
) { ... }
```

### @Json

Indicates that the request body should be deserialized from JSON.

```java
@Component
@HttpController
public final class UserController {
    
    @Json
    public record UserRequest(String name, String email) {}
    
    @HttpRoute(method = HttpMethod.POST, path = "/users")
    @Json
    public UserResponse create(@Json UserRequest request) {
        // request is automatically deserialized
        return userService.create(request);
    }
}
```

**Requirements:**
- Requires `json-module` dependency
- The DTO must have the `@Json` annotation
- Kora generates `HttpRequestMapper<T>` tagged with `@Json`

### @Mapping

Uses a custom `HttpServerRequestMapper` to extract a parameter.

```java
public record AuthContext(String userId, String traceId) {}

public static final class AuthMapper implements HttpServerRequestMapper<AuthContext> {
    @Override
    public AuthContext apply(HttpServerRequest request) {
        return new AuthContext(
            request.headers().getFirst("X-User-Id"),
            request.headers().getFirst("X-Trace-Id")
        );
    }
}

@HttpRoute(method = HttpMethod.POST, path = "/auth")
public String authenticate(@Mapping(AuthMapper.class) AuthContext ctx) {
    return "Authenticated as " + ctx.userId();
}
```

## Optional Parameters

By default all parameters are **required**. Use `@Nullable` for optional parameters.

```java
@HttpRoute(method = HttpMethod.GET, path = "/users")
@Json
public List<UserResponse> search(
    @Query("name") String name,           // required
    @Query("limit") @Nullable Integer limit,  // optional
    @Query("offset") @Nullable Integer offset // optional
) { ... }
```

**Kotlin nullability:**
```kotlin
@HttpRoute(method = HttpMethod.GET, path = "/users")
@Json
fun search(
    @Query("name") name: String,        // required
    @Query("limit") limit: Int? = null  // optional
): List<UserResponse> { ... }
```

## Parameter Validation

```java
@HttpRoute(method = HttpMethod.POST, path = "/users")
@Json
public UserResponse create(
    @Query("name") @MinLength(3) String name,
    @Query("age") @Min(18) Integer age
) { ... }
```

Requires `validation-module` dependency.

## Form Parameters

### Form UrlEncoded

```java
@HttpRoute(method = HttpMethod.POST, path = "/login")
public String login(FormUrlEncoded form) {
    String username = form.get("username");
    String password = form.get("password");
    // ...
}
```

### Form Multipart

```java
@HttpRoute(method = HttpMethod.POST, path = "/upload")
public String upload(FormMultipart form) {
    for (FormMultipart.Part part : form.parts()) {
        if (part.name().equals("file")) {
            byte[] content = part.body();
            // ...
        }
    }
}
```

## Request Body Types

| Type | Description |
|------|-------------|
| `String` | Plain text body |
| `byte[]` | Binary body |
| `ByteBuffer` | NIO ByteBuffer |
| `@Json T` | JSON body (requires json-module) |
| `FormUrlEncoded` | application/x-www-form-urlencoded |
| `FormMultipart` | multipart/form-data |
| `@Mapping(Mapper.class) T` | Custom mapper |
