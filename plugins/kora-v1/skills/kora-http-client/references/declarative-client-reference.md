# Declarative HTTP Client Reference

Reference for [kora-http-client](../SKILL.md).

## Contents

- [@HttpClient](#httpclient)
- [@HttpRoute](#httproute)
- [Path parameter: @Path](#path-parameter-path)
- [Query parameter: @Query](#query-parameter-query)
- [Header: @Header](#header-header)
- [Cookie: @Cookie](#cookie-cookie)
- [JSON body: @Json](#json-body-json)
- [Form bodies](#form-bodies)
- [Custom body mapper: @Mapping](#custom-body-mapper-mapping)
- [Custom response mapper](#custom-response-mapper)
- [Status-aware decoding: @ResponseCodeMapper](#status-aware-decoding-responsecodemapper)
- [Response wrappers](#response-wrappers)
- [Method signatures](#method-signatures)
- [Client configuration](#client-configuration)

---

## @HttpClient

Marks an interface as a declarative HTTP client. The annotation processor generates the implementation and registers it as a component.

```java
@HttpClient(configPath = "httpClient.myApi")
public interface MyApiClient {
    // client methods
}
```

### Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `configPath` | `String` | Config path for this client (default: `httpClient.{lower-case class name}`) |
| `telemetry` | annotation | Optional telemetry overrides |

`@HttpClient` has **no** `baseUrl` parameter. The target URL is supplied by the `url` key in the resolved config block.

```java
@HttpClient                                      // resolves httpClient.myApiClient
public interface MyApiClient { }

@HttpClient(configPath = "httpClient.externalApi") // resolves httpClient.externalApi
public interface ExternalApiClient { }
```

```hocon
httpClient {
  externalApi {
    url = "https://api.external.com"
    requestTimeout = "30s"
  }
}
```

---

## @HttpRoute

Declares the HTTP method and path for a client method.

```java
@HttpRoute(method = HttpMethod.GET, path = "/users/{id}")
@Json
UserResponse getUser(@Path String id);
```

| Parameter | Description |
|-----------|-------------|
| `method` | `HttpMethod.GET`, `POST`, `PUT`, `DELETE`, `PATCH`, `HEAD`, `OPTIONS` |
| `path` | Resource path; supports `{pathVariable}` placeholders |

```java
@HttpRoute(method = HttpMethod.GET, path = "/items")
@Json
List<Item> listItems();

@HttpRoute(method = HttpMethod.POST, path = "/items")
@Json
Item createItem(@Json CreateItemRequest request);

@HttpRoute(method = HttpMethod.PUT, path = "/items/{id}")
@Json
Item updateItem(@Path String id, @Json UpdateItemRequest request);

@HttpRoute(method = HttpMethod.DELETE, path = "/items/{id}")
void deleteItem(@Path String id);
```

---

## Path parameter: @Path

Substitutes a value into the URL path. Import: `ru.tinkoff.kora.http.common.annotation.Path`.

```java
@HttpRoute(method = HttpMethod.GET, path = "/users/{id}")
@Json
UserResponse getUser(@Path String id);

@HttpRoute(method = HttpMethod.GET, path = "/users/{userId}/orders/{orderId}")
@Json
OrderResponse getOrder(@Path String userId, @Path String orderId);
```

The placeholder name defaults to the argument name. Override it explicitly:

```java
UserResponse getUser(@Path("userId") String id);
```

---

## Query parameter: @Query

Adds query parameters. Import: `ru.tinkoff.kora.http.common.annotation.Query`.

```java
@HttpRoute(method = HttpMethod.GET, path = "/items")
@Json
List<Item> searchItems(
    @Query("category") String category,
    @Query("page") int page,
    @Query("size") int size);
// GET /items?category=books&page=1&size=20
```

Optional parameters use `@Nullable`:

```java
@HttpRoute(method = HttpMethod.GET, path = "/items")
@Json
List<Item> searchItems(@Nullable @Query("sort") String sort);
```

`Map<String, ?>` sends key/value pairs (values via `String.valueOf()`); `List<String>` sends a repeated parameter:

```java
@HttpRoute(method = HttpMethod.GET, path = "/search")
@Json
List<Result> search(@Query Map<String, String> filters);

@HttpRoute(method = HttpMethod.GET, path = "/items")
@Json
List<Item> getItems(@Query("ids") List<String> ids); // /items?ids=1&ids=2&ids=3
```

---

## Header: @Header

Adds request headers. Import: `ru.tinkoff.kora.http.common.annotation.Header`.

```java
@HttpRoute(method = HttpMethod.GET, path = "/users/{id}")
@Json
UserResponse getUser(
    @Path String id,
    @Header("X-Request-ID") String requestId);
```

A `List<String>` sends a repeated header; `HttpHeaders` or `Map<String, String>` sends a whole set:

```java
@HttpRoute(method = HttpMethod.GET, path = "/items")
@Json
List<Item> getItems(@Header HttpHeaders headers);
```

---

## Cookie: @Cookie

Sends a cookie. Import: `ru.tinkoff.kora.http.common.annotation.Cookie`.

```java
@HttpRoute(method = HttpMethod.GET, path = "/profile")
@Json
ProfileResponse getProfile(@Cookie("sessionId") String sessionId);
```

---

## JSON body: @Json

`@Json` on a parameter writes it as the JSON request body; `@Json` on the method reads the response body as JSON. Requires `json-module` and `@Json` on the DTO.

```java
@HttpRoute(method = HttpMethod.POST, path = "/users")
@Json
UserResponse createUser(@Json CreateUserRequest request);

@Json
record CreateUserRequest(String email, String name, String password) {}

@Json
record UserResponse(String id, String email, String name) {}
```

A plain method argument with no annotation is a raw body; `byte[]`, `ByteBuffer`, and `String` are supported out of the box.

---

## Form bodies

Use `FormUrlEncoded` for `application/x-www-form-urlencoded` and `FormMultipart` for multipart bodies. Imports: `ru.tinkoff.kora.http.common.form.FormUrlEncoded` / `FormMultipart`.

```java
@HttpRoute(method = HttpMethod.POST, path = "/data/form")
String processForm(FormUrlEncoded body);

@HttpRoute(method = HttpMethod.POST, path = "/data/upload")
@Json
UploadResponse processUpload(FormMultipart body);
```

Building a multipart body:

```java
var body = new FormMultipart(List.of(
    FormMultipart.data("field1", "some data content"),
    FormMultipart.file("field2", "example1.txt", "text/plain",
        "some file content".getBytes(StandardCharsets.UTF_8))));
```

---

## Custom body mapper: @Mapping

For non-standard request bodies, implement `HttpClientRequestMapper<T>` and reference it with `@Mapping`. Imports: `ru.tinkoff.kora.common.Mapping`, `ru.tinkoff.kora.http.client.common.request.HttpClientRequestMapper`.

```java
record PlainTextBody(String content) {}

final class TextBodyMapper implements HttpClientRequestMapper<PlainTextBody> {
    @Override
    public HttpBodyOutput apply(Context ctx, PlainTextBody value) {
        return HttpBody.plaintext(value.content());
    }
}

@HttpRoute(method = HttpMethod.POST, path = "/text")
String sendText(@Mapping(TextBodyMapper.class) PlainTextBody body);
```

---

## Custom response mapper

Implement `HttpClientResponseMapper<T>` and reference it with `@Mapping` on the method. Import: `ru.tinkoff.kora.http.client.common.response.HttpClientResponseMapper`.

```java
final class StringResponseMapper implements HttpClientResponseMapper<String> {
    @Override
    public String apply(HttpClientResponse response) throws IOException, HttpClientDecoderException {
        try (var is = response.body().asInputStream()) {
            return new String(is.readAllBytes(), StandardCharsets.UTF_8);
        }
    }
}

@Mapping(StringResponseMapper.class)
@HttpRoute(method = HttpMethod.GET, path = "/text")
String getText();
```

---

## Status-aware decoding: @ResponseCodeMapper

Map different HTTP status codes to different response mappers. Use `ResponseCodeMapper.DEFAULT` for all unlisted codes. Import: `ru.tinkoff.kora.http.client.common.annotation.ResponseCodeMapper`.

```java
sealed interface UserResult permits UserFound, UserError {
    @Json record UserFound(String id, String name) implements UserResult {}
    @Json record UserError(int code, String message) implements UserResult {}
}

@ResponseCodeMapper(code = 200, mapper = UserFoundMapper.class)
@ResponseCodeMapper(code = ResponseCodeMapper.DEFAULT, mapper = UserErrorMapper.class)
@HttpRoute(method = HttpMethod.GET, path = "/users/{id}")
UserResult getUser(@Path String id);
```

A mapper can read the HTTP status from `response.code()` while decoding the body. See `assets/CustomMapperClient.java.template` for a complete example.

---

## Response wrappers

### HttpResponseEntity\<T>

Wraps the decoded body together with status code and headers. Import: `ru.tinkoff.kora.http.common.HttpResponseEntity`.

```java
@HttpRoute(method = HttpMethod.GET, path = "/users/{id}")
@Json
HttpResponseEntity<UserResponse> getUser(@Path String id);

// Usage:
HttpResponseEntity<UserResponse> response = client.getUser("123");
if (response.code() == 200) {
    return response.body();
} else if (response.code() == 404) {
    throw new IllegalStateException("User not found: " + id);
}
```

`HttpResponseEntity` exposes `code()`, `body()`, and `headers()`. Without a wrapper or a `@ResponseCodeMapper`, non-2xx responses throw `HttpClientResponseException`.

---

## Method signatures

Java:
- `T myMethod()`
- `CompletionStage<T> myMethod()`
- `Mono<T> myMethod()` (requires `io.projectreactor:reactor-core`)

Kotlin (`T`, `T?`, or `Unit`):
- `fun myMethod(): T`
- `suspend fun myMethod(): T` (requires `org.jetbrains.kotlinx:kotlinx-coroutines-core`)

See [async-client-reference](async-client-reference.md).

---

## Client configuration

### Per-client

```hocon
httpClient {
  myApi {                    # matches configPath or lower-case class name
    url = "http://localhost:8080"
    requestTimeout = "30s"
    telemetry {
      logging { enabled = true }
      metrics { enabled = true }
      tracing { enabled = true }
    }
  }
}
```

### Per-method

The path is `httpClient.{client}.{methodName}`:

```hocon
httpClient {
  myApi {
    url = "http://localhost:8080"
    getUser {                # method name
      requestTimeout = "10s"
      telemetry { logging { enabled = true } }
    }
  }
}
```

---

## See also

- [okhttp-transport-reference](okhttp-transport-reference.md)
- [async-client-reference](async-client-reference.md)
- [error-handling-guide](error-handling-guide.md)
- [interceptors-reference](interceptors-reference.md)
