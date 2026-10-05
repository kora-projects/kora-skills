# Error Handling Reference

Per-route errors via `HttpServerResponseException`, and centralized translation via an
`HttpServerInterceptor`. Kora has no `@ControllerAdvice` equivalent — global error handling is an
interceptor concern.

## Contents

- [HttpServerResponseException](#httpserverresponseexception)
- [Automatic 400s](#automatic-400s)
- [Global error interceptor](#global-error-interceptor)
- [Kotlin](#kotlin)
- [Per-route error responses](#per-route-error-responses)
- [Migration from 1.x](#migration-from-1x)

---

## HttpServerResponseException

`io.koraframework.http.server.common.response.HttpServerResponseException`

```java
public class HttpServerResponseException extends RuntimeException implements HttpServerResponse
```

It **is** a response. That single fact shapes the whole error-handling story: an interceptor can
`return` a caught `HttpServerResponseException` directly and the client sees exactly the status,
headers and body the handler intended.

Factories:

```java
of(int code, String text)
of(int code, Throwable throwable)
of(int code, String text, HttpHeaders headers)
of(int code, Throwable throwable, HttpHeaders headers)
of(@Nullable Throwable cause, int code, String text)
of(@Nullable Throwable cause, int code, String text, HttpHeaders headers)
```

```java
@HttpRoute(method = HttpMethod.GET, path = "/users/{id}")
@Json
public UserResponse get(@Path String id) {
    return userService.getUser(id)
        .orElseThrow(() -> HttpServerResponseException.of(404, "User not found: " + id));
}
```

Accessors: `code()`, `headers()`, `body()`, `getMessage()`. There are no `notFound()` /
`badRequest()` helpers.

---

## Automatic 400s

You do not need to handle malformed input yourself. The generated handler wraps every parameter
parse and body deserialization, converting any failure into `HttpServerResponseException.of(400, e)`
— unless the thrown value is itself an `HttpServerResponse`, which is rethrown unchanged. So a
custom `HttpServerRequestMapper` can pick its own status by throwing an
`HttpServerResponseException`.

---

## Global error interceptor

Tag it `@Tag(HttpServer.class)` so it applies to every route on the public server, and catch around
`chain.process(request)`. Inject a `JsonWriter<T>` to emit a JSON error body.

```java
package com.example.interceptor;

import io.koraframework.common.annotation.Component;
import io.koraframework.common.annotation.Tag;
import io.koraframework.http.common.body.HttpBody;
import io.koraframework.http.server.common.HttpServer;
import io.koraframework.http.server.common.interceptor.HttpServerInterceptor;
import io.koraframework.http.server.common.request.HttpServerRequest;
import io.koraframework.http.server.common.response.HttpServerResponse;
import io.koraframework.http.server.common.response.HttpServerResponseException;
import io.koraframework.json.common.JsonWriter;
import io.koraframework.json.common.annotation.Json;

@Tag(HttpServer.class)
@Component
public final class ErrorInterceptor implements HttpServerInterceptor {

    @Json
    public record ErrorResponse(String code, String message) {}

    private final JsonWriter<ErrorResponse> errorWriter;

    public ErrorInterceptor(JsonWriter<ErrorResponse> errorWriter) {
        this.errorWriter = errorWriter;
    }

    @Override
    public HttpServerResponse intercept(HttpServerRequest request, InterceptChain chain) throws Exception {
        try {
            return chain.process(request);
        } catch (HttpServerResponseException e) {
            return e;   // already a response: preserves the handler's status and body
        } catch (IllegalArgumentException e) {
            return json(400, "BAD_REQUEST", e.getMessage());
        } catch (Exception e) {
            return json(500, "INTERNAL_ERROR", "An unexpected error occurred");
        }
    }

    private HttpServerResponse json(int code, String errorCode, String message) {
        return HttpServerResponse.of(code,
                HttpBody.json(errorWriter.toByteArray(new ErrorResponse(errorCode, message))));
    }
}
```

Three details that differ from the 1.x version of this template:

1. **No `CompletionException` unwrapping.** The call is synchronous; the exception you catch is the
   one that was thrown.
2. **No `try/catch (IOException)` around `toByteArray`.** `JsonWriter.toByteArray` declares
   only `throws JacksonException` (unchecked, Jackson 3), so catching `IOException` is
   `error: exception IOException is never thrown in body of corresponding try statement`.
   The `*Unchecked` method variants no longer exist either.
3. **`@Tag(HttpServer.class)`, not `@Tag(HttpServerModule.class)`.** The old tag compiles and the
   interceptor is silently never invoked — see [Interceptors](interceptors-reference.md#the-tag-that-changed--read-this-first).

Catching `Exception` here is deliberate: `intercept` declares `throws Exception`, so anything the
handler throws arrives intact.

---

## Kotlin

```kotlin
@Tag(HttpServer::class)
@Component
class ErrorInterceptor(private val errorWriter: JsonWriter<ErrorResponse>) : HttpServerInterceptor {

    @Json
    data class ErrorResponse(val code: String, val message: String?)

    override fun intercept(
        request: HttpServerRequest,
        chain: HttpServerInterceptor.InterceptChain
    ): HttpServerResponse {
        try {
            return chain.process(request)
        } catch (e: HttpServerResponseException) {
            return e
        } catch (e: Exception) {
            val code = if (e is IllegalArgumentException) 400 else 500
            val error = ErrorResponse(if (code == 400) "BAD_REQUEST" else "INTERNAL_ERROR", e.message)
            return HttpServerResponse.of(code, HttpBody.json(errorWriter.toByteArray(error)))
        }
    }
}
```

Kotlin has no checked exceptions, so the `throws Exception` on the contract simply disappears from
the override.

---

## Per-route error responses

When only one route needs it, return a response instead of throwing:

```java
@HttpRoute(method = HttpMethod.POST, path = "/users")
@Json
public HttpResponseEntity<ErrorResponse> create(@Json UserRequest request) {
    if (request.email() == null || request.email().isBlank()) {
        return HttpResponseEntity.of(400, HttpHeaders.of(), new ErrorResponse("BAD_REQUEST", "Email is required"));
    }
    // ... success path
}
```

---

## Migration from 1.x

| 1.x | 2.0 |
|---|---|
| `ru.tinkoff.kora.http.server.common.HttpServerResponseException` | `io.koraframework.http.server.common.response.HttpServerResponseException` |
| `@Tag(HttpServerModule.class)` on the error interceptor | `@Tag(HttpServer.class)` |
| `chain.process(ctx, req).exceptionally(t -> …)` | `try { chain.process(req) } catch (Exception e) { … }` |
| unwrap `CompletionException` | not needed — synchronous |
| `writer.toByteArrayUnchecked(v)` | `writer.toByteArray(v)` |
| `try { … } catch (IOException e)` around it | remove the `catch` entirely |

**See also:** [Interceptors](interceptors-reference.md), [Response Types](response-types-reference.md).
