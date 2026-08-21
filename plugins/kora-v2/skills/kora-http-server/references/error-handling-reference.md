# Error Handling Reference

Per-route errors via `HttpServerResponseException`, and centralized error translation via a global
`HttpServerInterceptor`. There is no separate "exception handler" type in Kora — global error
handling is an interceptor concern.

## Contents

- [HttpServerResponseException](#httpserverresponseexception)
- [Global error interceptor](#global-error-interceptor)
- [Per-route error responses](#per-route-error-responses)

---

## HttpServerResponseException

Throw it from a handler to short-circuit with a status code and message:

```java
import ru.tinkoff.kora.http.server.common.HttpServerResponseException;

@HttpRoute(method = HttpMethod.GET, path = "/users/{id}")
@Json
public UserResponse get(@Path String id) {
    return userService.getUser(id)
        .orElseThrow(() -> HttpServerResponseException.of(404, "User not found: " + id));
}
```

`HttpServerResponseException.of(int code, String message)` is the factory. The exception exposes
`code()` and `getMessage()`, which a global interceptor can read.

---

## Global error interceptor

Tag a single interceptor with `@Tag(HttpServerModule.class)`, chain `.exceptionally(...)`, and map
exception types to responses. Inject a `JsonWriter<ErrorResponse>` to emit a JSON error body.
Adapted from the advanced HTTP server guide.

```java
import java.util.concurrent.CompletionException;
import java.util.concurrent.CompletionStage;
import ru.tinkoff.kora.common.Component;
import ru.tinkoff.kora.common.Context;
import ru.tinkoff.kora.common.Tag;
import ru.tinkoff.kora.http.common.body.HttpBody;
import ru.tinkoff.kora.http.server.common.HttpServerInterceptor;
import ru.tinkoff.kora.http.server.common.HttpServerModule;
import ru.tinkoff.kora.http.server.common.HttpServerRequest;
import ru.tinkoff.kora.http.server.common.HttpServerResponse;
import ru.tinkoff.kora.http.server.common.HttpServerResponseException;
import ru.tinkoff.kora.json.common.JsonWriter;

@Tag(HttpServerModule.class)
@Component
public final class ErrorInterceptor implements HttpServerInterceptor {

    public record ErrorResponse(String message) {}

    private final JsonWriter<ErrorResponse> errorWriter;

    public ErrorInterceptor(JsonWriter<ErrorResponse> errorWriter) {
        this.errorWriter = errorWriter;
    }

    @Override
    public CompletionStage<HttpServerResponse> intercept(Context context,
                                                         HttpServerRequest request,
                                                         InterceptChain chain) throws Exception {
        return chain.process(context, request).exceptionally(throwable -> {
            Throwable cause = unwrap(throwable);
            if (cause instanceof HttpServerResponseException e) {
                return json(e.code(), e.getMessage());
            }
            if (cause instanceof IllegalArgumentException) {
                return json(400, "Invalid request parameters");
            }
            return json(500, "An unexpected error occurred");
        });
    }

    private HttpServerResponse json(int code, String message) {
        return HttpServerResponse.of(code, HttpBody.json(errorWriter.toByteArrayUnchecked(new ErrorResponse(message))));
    }

    private static Throwable unwrap(Throwable t) {
        Throwable c = t;
        while (c instanceof CompletionException && c.getCause() != null) {
            c = c.getCause();
        }
        return c;
    }
}
```

The async result is completed exceptionally, so unwrap `CompletionException` before inspecting the
real cause. Re-emit `HttpServerResponseException` with its own `code()` so explicit per-route
statuses are preserved.

---

## Per-route error responses

When you only need an error for one route, return an `HttpResponseEntity`/`HttpServerResponse`
directly instead of throwing:

```java
@HttpRoute(method = HttpMethod.POST, path = "/users")
@Json
public HttpResponseEntity<ErrorResponse> create(@Json UserRequest request) {
    if (request.email() == null || request.email().isBlank()) {
        return HttpResponseEntity.of(400, HttpHeaders.of(), new ErrorResponse("Email is required"));
    }
    // ... success path
}

public record ErrorResponse(String message) {}
```

**See also:** [Interceptors](interceptors-reference.md), [Response Types](response-types-reference.md).
