# Response Types Reference

How a handler's return type maps to an HTTP response: raw types, `@Json`, `HttpResponseEntity<T>`,
`HttpServerResponse`, and custom response mappers.

## Contents

- [Raw and JSON bodies](#raw-and-json-bodies)
- [HttpResponseEntity](#httpresponseentity)
- [HttpServerResponse](#httpserverresponse)
- [HttpBody and HttpHeaders](#httpbody-and-httpheaders)
- [Custom response mapping](#custom-response-mapping)
- [Comparison](#comparison)

---

## Raw and JSON bodies

Returning `String`, `byte[]`, or `ByteBuffer` produces a `200 OK` with the matching content type:

```java
@HttpRoute(method = HttpMethod.GET, path = "/health")
public String health() {
    return "OK";   // 200, text/plain
}
```

Returning a typed object with `@Json` on the method serializes it to JSON (`json-module` required):

```java
@HttpRoute(method = HttpMethod.GET, path = "/users/{id}")
@Json
public UserResponse get(@Path String id) {
    return userService.getUser(id);   // 200, application/json
}
```

Async signatures are also supported: `CompletionStage<T>` / `Mono<T>` (Java), `suspend fun` (Kotlin).

---

## HttpResponseEntity

A wrapper over a body that adds a status code and headers, while the body is still serialized
(e.g. as JSON when `@Json` is present). Construct it with `HttpResponseEntity.of(...)`:

```java
@HttpRoute(method = HttpMethod.POST, path = "/users")
@Json
public HttpResponseEntity<UserResponse> create(@Json UserRequest request) {
    UserResponse user = userService.createUser(request);
    return HttpResponseEntity.of(201, HttpHeaders.of("Location", "/users/" + user.id()), user);
}

@HttpRoute(method = HttpMethod.PUT, path = "/users/{id}")
@Json
public HttpResponseEntity<UserResponse> update(@Path String id, @Json UserRequest request) {
    return HttpResponseEntity.of(
        200,
        HttpHeaders.of("X-Updated-At", Instant.now().toString()),
        userService.updateUser(id, request));
}
```

`HttpResponseEntity.of(int code, HttpHeaders headers, T body)` — there is no fluent
`.status().header().body()` builder.

---

## HttpServerResponse

Full manual control over status, headers and raw body. Build it with `HttpServerResponse.of(...)`:

```java
// status + headers + body
return HttpServerResponse.of(200, HttpHeaders.of("X-Trace", traceId), HttpBody.plaintext("OK"));

// status + body (no extra headers)
return HttpServerResponse.of(200, HttpBody.json(jsonBytes));

// empty body, e.g. 204 No Content
return HttpServerResponse.of(204, HttpBody.empty());
```

Use it for binary downloads, streaming, custom content types, or any non-JSON response.

---

## HttpBody and HttpHeaders

```java
HttpBody.plaintext(String text)
HttpBody.json(byte[] jsonBytes)
HttpBody.empty()
HttpBody.of(String contentType, byte[] data)

HttpHeaders.of(String... nameValuePairs)   // "name", "value", "name2", "value2", ...
```

To produce JSON bytes inside an interceptor or mapper, inject a `JsonWriter<T>` and call
`writer.toByteArrayUnchecked(value)`.

---

## Custom response mapping

Implement `HttpServerResponseMapper<T>` to turn a domain value into an `HttpServerResponse`, then
reference it with `@Mapping`:

```java
public record Hello(String greeting, String name) {}

public static final class ResponseMapper implements HttpServerResponseMapper<Hello> {
    @Override
    public HttpServerResponse apply(Context ctx, HttpServerRequest request, Hello result) {
        return HttpServerResponse.of(200, HttpBody.plaintext(result.greeting() + " - " + result.name()));
    }
}

@Mapping(ResponseMapper.class)
@HttpRoute(method = HttpMethod.GET, path = "/hello")
public Hello hello() {
    return new Hello("Hello", "Bob");
}
```

---

## Comparison

| Return type | Status | Body | Headers | When |
|---|---|---|---|---|
| `String` / `byte[]` / `ByteBuffer` | 200 | yes | default | plain text, raw bytes |
| `T` + `@Json` | 200 | yes (JSON) | default | simple JSON responses |
| `HttpResponseEntity<T>` + `@Json` | any | yes (JSON) | custom | JSON with status/headers |
| `HttpServerResponse` | any | optional | full | files, streaming, manual control |

**See also:** [Error Handling](error-handling-reference.md), [Request Mapping](request-mapping-reference.md).
