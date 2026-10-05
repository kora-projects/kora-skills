# Request Mapping Reference

Binding request data to handler parameters: `@Path`, `@Query`, `@Header`, `@Cookie`, request
bodies, optionality, and custom `HttpServerRequestMapper`.

All four binding annotations live in **`io.koraframework.http.common.annotation`**.

## Contents

- [@Path](#path)
- [@Query](#query)
- [@Header](#header)
- [@Cookie](#cookie)
- [Optional parameters](#optional-parameters)
- [Request body](#request-body)
- [Custom request mapping](#custom-request-mapping)
- [Reading the raw request](#reading-the-raw-request)
- [Parameter errors are 400](#parameter-errors-are-400)

---

## @Path

Extracts a `{...}` path segment. The name defaults to the argument name; use `@Path("name")` only
when they differ.

```java
@HttpRoute(method = HttpMethod.GET, path = "/users/{userId}/orders/{orderId}")
public OrderResponse getOrder(@Path String userId, @Path String orderId) { /* ... */ }
```

Supported types (the processor emits a dedicated parser per type):

| Type | Notes |
|---|---|
| `String` | |
| `int` / `long` / `double` | primitives |
| `boolean` | |
| `UUID` | |

A path segment always exists once the route matched, so `@Path` parameters are never optional and
collections are not supported.

---

## @Query

Extracts a query parameter; the name defaults to the argument name.

```java
@HttpRoute(method = HttpMethod.GET, path = "/users")
public List<UserResponse> list(@Query int page,
                               @Query("ids") List<String> ids) { /* ... */ }
// GET /users?page=1&ids=1&ids=2
```

Kora binds a parameter in one of two ways:

**Direct parsers** — `String`, `Integer`/`int`, `Long`/`long`, `Double`/`double`,
`Boolean`/`boolean`, `UUID`, plus `List<T>` and **`Set<T>`** of each. `List`/`Set` collect
repeated parameters.

**Anything else** resolves through an `HttpServerParameterReader<T>` from the graph.
`HttpServerParameterReaderModule` supplies these as `@DefaultComponent`s, so they need no wiring:

| Reader | Types |
|---|---|
| enums | any `T extends Enum<T>`, matched on `Enum::name` |
| date/time | `LocalDate`, `LocalTime`, `LocalDateTime`, `OffsetTime`, `OffsetDateTime`, `ZonedDateTime`, `Duration` |
| numeric | `Float`, `BigInteger`, `BigDecimal` |
| JSON | any `T` that has a generated `JsonReader<T>` |

Supply your own for a domain type by declaring a `@Component` `HttpServerParameterReader<T>`; a
reader that throws produces a `400` with the message you give
`HttpServerParameterReader.of(converter, message)`.

> A `Boolean` path or query value must be `true` or `false` (case-insensitive); anything else,
> including a blank value, is a `400`. It is never silently read as `false`.

---

## @Header

Extracts a request header value.

```java
@HttpRoute(method = HttpMethod.GET, path = "/users")
public UserResponse get(@Header("Authorization") String auth,
                        @Nullable @Header("X-Request-Id") String requestId) { /* ... */ }
```

Supported: `String`, `Integer`, `Long`, `Double`, `UUID`, plus `List<T>`/`Set<T>` of each, and any
type with an `HttpServerParameterReader<T>` in the graph.

---

## @Cookie

Extracts a cookie. Two shapes are supported: the raw
`io.koraframework.http.common.cookie.Cookie`, or its value as a `String`.

```java
@HttpRoute(method = HttpMethod.GET, path = "/me")
public UserResponse me(@Cookie("sessionId") String sessionId) { /* ... */ }

@HttpRoute(method = HttpMethod.GET, path = "/me/raw")
public UserResponse raw(@Cookie("sessionId") Cookie cookie) { /* ... */ }
```

The request `Cookie` header is parsed without allowing `=` inside a value, with one exception: a
run of `=` at the **end** of a value (base64 padding, `token=YWJj==`) stays part of the value. An
`=` followed by more characters still splits the value, so URL-encode cookie values that can carry
an inner `=`.

---

## Optional parameters

Parameters are **required** by default; a missing required parameter produces a `400`. There is no
`required = false` attribute anywhere — nullability alone controls optionality.

**Java** uses JSpecify, which ships with Kora 2.0:

```java
import org.jspecify.annotations.Nullable;

@HttpRoute(method = HttpMethod.GET, path = "/users")
public List<UserResponse> list(@Nullable @Query Integer page,
                               @Nullable @Query Integer size) {
    return userService.findAll(page == null ? 0 : page, size == null ? 10 : size);
}
```

Use the boxed type (`Integer`, not `int`) for an optional parameter — a primitive cannot be null.
JSpecify's `@Nullable` is a **type-use** annotation, so position matters on nested and array types
(`List<@Nullable String>`, `String @Nullable []`); a wrong position is a compile error.

**Kotlin** uses a nullable type and no annotation at all:

```kotlin
@HttpRoute(method = HttpMethod.GET, path = "/users")
fun list(@Query page: Int?, @Query size: Int?): List<UserResponse> =
    userService.findAll(page ?: 0, size ?: 10)
```

Do not carry Java nullability annotations into Kotlin — `@field:Nullable` is not a valid target
under Kotlin 2.4.

---

## Request body

A method argument without a binding annotation is treated as the request body. Mappers supplied
out of the box (`HttpServerRequestMapperModule`):

| Body type | Notes |
|---|---|
| `byte[]`, `ByteBuffer` | raw bytes |
| `String` | decoded text |
| `InputStream` | streamed |
| `HttpBodyInput` | the raw body handle |
| `HttpServerRequest` | the whole request |
| `FormUrlEncoded` | `application/x-www-form-urlencoded` |
| `FormMultipart` | `multipart/form-data` |
| any `T` with `@Json` | via the generated `JsonReader<T>` |

### JSON

Annotate the body parameter with `@Json`, and the method with `@Json` for a JSON response.
Requires `io.koraframework:json-common` — the 1.x artifact `json-module` does not exist in 2.0.

```java
@HttpRoute(method = HttpMethod.POST, path = "/users")
@Json
public UserResponse create(@Json UserRequest request) {
    return userService.create(request);
}

@Json
public record UserRequest(String email, String name) {}
```

### Forms

```java
@HttpRoute(method = HttpMethod.POST, path = "/submit")
public String submit(FormUrlEncoded form) { /* ... */ }

@HttpRoute(method = HttpMethod.POST, path = "/upload")
public String upload(FormMultipart form) { /* ... */ }
```

---

## Custom request mapping

```java
public interface HttpServerRequestMapper<T> extends Mapping.MappingFunction {
    @Nullable T apply(HttpServerRequest request) throws Exception;
}
```

Implement it and reference it with `@Mapping` to build a value from the raw request:

```java
public record UserContext(String userId, String traceId) {}

@Component                                   // required — see below
public static final class UserContextRequestMapper implements HttpServerRequestMapper<UserContext> {
    @Override
    public UserContext apply(HttpServerRequest request) {
        return new UserContext(
            request.headers().getFirst("x-user-id"),
            request.headers().getFirst("x-trace-id"));
    }
}

@HttpRoute(method = HttpMethod.GET, path = "/ctx")
public HttpServerResponse handle(@Mapping(UserContextRequestMapper.class) UserContext context) {
    /* ... */
}
```

**`@Mapping(X.class)` makes the generated module ask the graph for `X` itself**, not for
`HttpServerRequestMapper<T>`. So `X` must be a component — `@Component` on the class, or a module
method returning it — **even when it has no constructor dependencies**. Omitting it fails at
compile time:

```
error: No component found for dependency:
    com.example.UserContextRequestMapper (no tags)
  Fix:
    - Add @Component to an implementation of com.example.UserContextRequestMapper.
```

In Kotlin the `apply` parameter follows the contract exactly; the return type is nullable:

```kotlin
@Component
class UserContextRequestMapper : HttpServerRequestMapper<UserContext> {
    override fun apply(request: HttpServerRequest): UserContext =
        UserContext(request.headers().getFirst("x-user-id"), request.headers().getFirst("x-trace-id"))
}
```

---

## Reading the raw request

`HttpServerRequest` (`io.koraframework.http.server.common.request`) exposes:

```java
String host();  String scheme();  String method();  String path();
@Nullable String pathTemplate();          // the matched route template, null when unrouted
Map<String, String> pathParams();
HttpHeaders headers();
List<Cookie> cookies();
Map<String, List<String>> queryParams();
HttpBodyInput body();
long requestStartTimeInNanos();
HttpServerRequestBuilder toBuilder();     // derive a modified request
```

There is **no attribute map** on the request and no `Context` — see
[Request Enrichment](context-propagation-reference.md) for passing values from an interceptor to a
handler.

---

## Parameter errors are 400

The generated handler wraps every parameter parse in a `try/catch`:

```java
try {
    userId = HttpRequestHandlerUtils.parsePathString(_request, "userId");
} catch (Exception _e) {
    if (_e instanceof HttpServerResponse) throw _e;
    else throw HttpServerResponseException.of(400, _e);
}
```

So a malformed `int`, a missing required `@Query`, or a body that fails to deserialize becomes a
`400` automatically. Throwing something that *is* an `HttpServerResponse` (such as
`HttpServerResponseException`) from a custom mapper preserves your own status code instead.

**See also:** [Response Types](response-types-reference.md), [Controller & Routing](controller-routing-reference.md).
