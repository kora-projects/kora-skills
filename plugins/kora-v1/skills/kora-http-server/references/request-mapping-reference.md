# Request Mapping Reference

Binding request data to handler parameters: `@Path`, `@Query`, `@Header`, `@Cookie`, request
bodies (`@Json`, form data), optional parameters, and custom `@Mapping`.

## Contents

- [@Path](#path)
- [@Query](#query)
- [@Header](#header)
- [@Cookie](#cookie)
- [Request body](#request-body)
- [Optional parameters](#optional-parameters)
- [Type conversion](#type-conversion)
- [Custom parameter mapping](#custom-parameter-mapping)

---

## @Path

Extracts a `{...}` path segment. The name defaults to the argument name.

```java
@HttpRoute(method = HttpMethod.GET, path = "/users/{userId}/orders/{orderId}")
public OrderResponse getOrder(@Path String userId, @Path String orderId) { /* ... */ }
```

Use `@Path("name")` only when the argument name differs from the segment. The name must match a
`{...}` segment in the route.

---

## @Query

Extracts a query parameter; the name defaults to the argument name.

```java
@HttpRoute(method = HttpMethod.GET, path = "/users")
public List<UserResponse> list(@Query("page") int page,
                               @Query("ids") List<String> ids) { /* ... */ }
// GET /users?page=1&ids=1&ids=2
```

`List<T>` collects repeated query parameters.

---

## @Header

Extracts a request header value.

```java
@HttpRoute(method = HttpMethod.GET, path = "/users")
public UserResponse get(@Header("Authorization") String auth,
                        @Nullable @Header("X-Request-Id") String requestId) { /* ... */ }
```

`List<String>` collects repeated header values.

---

## @Cookie

Extracts a cookie value.

```java
@HttpRoute(method = HttpMethod.GET, path = "/me")
public UserResponse me(@Cookie("sessionId") String sessionId) { /* ... */ }
```

---

## Request body

A method argument without a binding annotation is treated as the request body. Supported raw
types out of the box: `byte[]`, `ByteBuffer`, `String`.

### JSON

Annotate the body parameter with `@Json` (and the method with `@Json` for the response). Requires
the `json-module` dependency.

```java
@HttpRoute(method = HttpMethod.POST, path = "/users")
@Json
public UserResponse create(@Json UserRequest request) {
    return userService.createUser(request);
}

public record UserRequest(String email, String name) {}
```

### Form data

Use `FormUrlEncoded` for `application/x-www-form-urlencoded` bodies, or `FormMultipart` for
multipart bodies:

```java
@HttpRoute(method = HttpMethod.POST, path = "/submit")
public String submit(FormUrlEncoded form) { /* ... */ }

@HttpRoute(method = HttpMethod.POST, path = "/upload")
public String upload(FormMultipart form) { /* ... */ }
```

---

## Optional parameters

Parameters are **required (NotNull)** by default. Mark optional ones with `@Nullable` (any
`jakarta.annotation.Nullable` / `javax.annotation.Nullable` / `org.jetbrains.annotations.Nullable`
will do); in Kotlin use a nullable type.

```java
// Java
@HttpRoute(method = HttpMethod.GET, path = "/users")
public List<UserResponse> list(@Nullable @Query("page") Integer page,
                               @Nullable @Query("size") Integer size) {
    int pageNum = page == null ? 0 : page;
    int pageSize = size == null ? 10 : size;
    return userService.getUsers(pageNum, pageSize);
}
```

```kotlin
// Kotlin
@HttpRoute(method = HttpMethod.GET, path = "/users")
fun list(@Query("page") page: Int?, @Query("size") size: Int?): List<UserResponse> =
    userService.getUsers(page ?: 0, size ?: 10)
```

There is no `required` attribute on `@Query`/`@Header`/`@Cookie`; nullability controls
optionality.

---

## Type conversion

Kora converts the raw string parameter into the target type at compile time:

| Type | Example |
|---|---|
| `String` | `@Query String name` |
| `int` / `Integer` | `@Query Integer page` |
| `long` / `Long` | `@Query Long offset` |
| `boolean` / `Boolean` | `@Query Boolean active` |
| `List<T>` | `@Query List<String> ids` (repeated params) |

---

## Custom parameter mapping

Implement `HttpServerRequestMapper<T>` and reference it with `@Mapping` to build a value from the
raw request:

```java
public record UserContext(String userId, String traceId) {}

public static final class RequestMapper implements HttpServerRequestMapper<UserContext> {
    @Override
    public UserContext apply(HttpServerRequest request) {
        return new UserContext(
            request.headers().getFirst("x-user-id"),
            request.headers().getFirst("x-trace-id"));
    }
}

@HttpRoute(method = HttpMethod.GET, path = "/ctx")
public String handle(@Mapping(RequestMapper.class) UserContext context) { /* ... */ }
```

**See also:** [Response Types](response-types-reference.md), [Controller & Routing](controller-routing-reference.md).
