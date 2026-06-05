# @HttpClient Annotation Reference

**Source:** [.kora-agent/kora-docs/mkdocs/docs/en/documentation/http-client.md](.kora-agent/kora-docs/mkdocs/docs/en/documentation/http-client.md)  
**Examples:** `.kora-agent/kora-examples/kora-java-http-client/`

## Overview

`@HttpClient` for declarative HTTP clients — type-safe, compile-time checked interfaces.

```java
@HttpClient("client-name")  // Client identifier used for configuration lookup
public interface MyApiClient {
    @HttpRoute(method = HttpMethod.GET, path = "/api/users")
    @Json UserResponse getUsers();  // JSON response
}
```

**Configuration Lookup:**
```hocon
httpClient {
  my-client {
    basePath = "https://api.example.com"
    requestTimeout = "30s"
    telemetry { logging.enabled = true }
  }
}
```

## Supported Methods

**HTTP Methods:** `GET`, `POST`, `PUT`, `PATCH`, `DELETE`, `HEAD`, `OPTIONS` via `@HttpRoute(method, path)`.

**Return Types:** `T` (sync), `HttpResponseEntity<T>` (full response), `void` (no body), `List<T>` (list).

**Method signatures:** `T method()` — sync (recommended) | `CompletionStage<T> method()` — async (when necessary) | `suspend fun method()` — Kotlin coroutines | `Mono<T>` — not recommended unless strictly required.

> **Important:** Synchronous signatures are recommended for simplicity. Use async only when there is a real need.

## Request Parameters

| Annotation | Purpose | Example |
|-----------|------------|--------|
| `@Path("id")` | URL path | `/users/{id}` |
| `@Query("name")` | Query string | `?name=value` |
| `@Header("X-Trace")` | HTTP header | `X-Trace: abc` |
| `@Cookie("session")` | Cookie | `session=xyz` |
| `@Json` | JSON body | `{"name": "John"}` |
| `@FormParam("field")` | Form field | `field=value` |

**All parameters are required by default** — use `@Nullable` for optional parameters.

## Request Body Types

**JSON:** `@Json UserResponse create(@Json UserRequest request)`

**Form URL Encoded:** `@FormUrlEncoded LoginResponse login(@FormParam("username") String username, @FormParam("password") String password)`

**Form Multipart:** `@FormMultipart UploadResponse upload(@FormParam("file") byte[] file, @FormParam("description") String desc)`

**Raw:** `String postRaw(String body)`

## Response Handling

**@Json Response:** `@Json UserResponse getUser(@Path("id") String id)`

**HttpResponseEntity:** `HttpResponseEntity<UserResponse> getUserWithHeaders(@Path("id") String id)`

**@ResponseCodeMapper:** type-safe handling via sealed interfaces:
```java
@ResponseCodeMapper(code = 200, mapper = SuccessMapper.class)
@ResponseCodeMapper(code = 404, mapper = NotFoundMapper.class)
@ResponseCodeMapper(code = ResponseCodeMapper.DEFAULT, mapper = ErrorMapper.class)
UserResult getUser(@Path("id") String id);

public sealed interface UserResult permits UserResult.Success, UserResult.NotFound, UserResult.Error {
    record Success(UserResponse user) implements UserResult {}
    record NotFound() implements UserResult {}
    record Error(int code, String message) implements UserResult {}
}
```

## Module Registration & Interceptors

```java
@KoraApp
public interface Application extends JdkHttpClientModule, HttpClientModule, JsonModule {}
```

**Interceptors:** `@InterceptWith(LoggingInterceptor.class)` on a method | `@Tag(MyApiClient.class) @Component` — client-level (applied to all methods).

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Client not found | Check `@HttpClient("name")` against config |
| 404 Not Found | Check `@HttpRoute` path and method |
| JSON not serialized | Add `@Json` to the DTO and the method |
| Missing parameters | Check required vs `@Nullable` |
| Interceptor not applied | Check `@Tag` for client-level interceptor |

## Related

- [Interceptors Reference](interceptors-reference.md)
- [Configuration Reference](configuration-reference.md)
- [Advanced Patterns Reference](advanced-patterns-reference.md)
