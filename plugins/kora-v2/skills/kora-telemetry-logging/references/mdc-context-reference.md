# MDC Context Reference

**Sources:**
- `.kora-agent/kora-docs/mkdocs/docs/en/documentation/logging-slf4j.md`
- `.kora-agent/kora-docs/mkdocs/docs/en/documentation/http-server.md`

## Contents

- [Two MDC classes](#two-mdc-classes)
- [Kora MDC (structured, async-safe)](#kora-mdc-structured-async-safe)
- [SLF4J MDC (string-only)](#slf4j-mdc-string-only)
- [HTTP interceptor for trace context](#http-interceptor-for-trace-context)
- [Common MDC keys](#common-mdc-keys)
- [Best practices](#best-practices)

For the `@Mdc` aspect, see [logging-aspect-reference.md](logging-aspect-reference.md).

## Two MDC classes

| Class | Values | API | Async propagation |
|-------|--------|-----|-------------------|
| `ru.tinkoff.kora.logging.common.MDC` | structured (String/Integer/Long/Boolean/writer) | static `put` / `remove` | propagated by `KoraAsyncAppender` |
| `org.slf4j.MDC` | strings only | `put` / `remove` / `clear` / `putCloseable` | not propagated automatically |

Pick one per file — importing both `MDC` types in the same file is a compile error.

## Kora MDC (structured, async-safe)

`ru.tinkoff.kora.logging.common.MDC` attaches structured values to every record in the current
context and is the form `KoraAsyncAppender` carries through to the async record. It is a static
put/remove API; there is no `clear()` and no auto-closing handle, so remove what you put.

===! "Java"

    ```java
    import ru.tinkoff.kora.logging.common.MDC;

    MDC.put("traceId", traceId);        // String / Integer / Long / Boolean overloads
    MDC.put("attempt", attempt);        // Integer
    try {
        logger.info("Processing request");   // traceId and attempt attached to the record
    } finally {
        MDC.remove("traceId");
        MDC.remove("attempt");
    }
    ```

=== "Kotlin"

    ```kotlin
    import ru.tinkoff.kora.logging.common.MDC

    MDC.put("traceId", traceId)
    try {
        logger.info("Processing request")
    } finally {
        MDC.remove("traceId")
    }
    ```

A structured value can also be written explicitly:

```java
MDC.put("user", gen -> gen.writeString(userId));
```

## SLF4J MDC (string-only)

Because Kora speaks SLF4J, the standard `org.slf4j.MDC` works for simple string context. Prefer
try-with-resources so the key is always cleared. Note this MDC is not automatically propagated by
`KoraAsyncAppender`; use the Kora `MDC` for structured/async-safe context.

```java
import org.slf4j.MDC;

try (MDC.MDCCloseable t = MDC.putCloseable("traceId", traceId);
     MDC.MDCCloseable u = MDC.putCloseable("userId", userId)) {
    logger.info("Processing request");
}  // both keys cleared automatically
```

## HTTP interceptor for trace context

A `ru.tinkoff.kora.http.server.common.HttpServerInterceptor` can seed MDC from
request headers for every request. The real signature returns a
`CompletionStage<HttpServerResponse>` and receives a `Context`, the request, and an
`InterceptChain`. Tag it with `@Tag(HttpServerModule.class)` to apply it to all controllers.
Read a single header with `request.headers().getFirst(name)` (header names are lower-cased).

```java
import ru.tinkoff.kora.common.Component;
import ru.tinkoff.kora.common.Context;
import ru.tinkoff.kora.common.Tag;
import ru.tinkoff.kora.http.server.common.HttpServerModule;
import ru.tinkoff.kora.http.server.common.HttpServerResponse;
import ru.tinkoff.kora.http.server.common.HttpServerInterceptor;
import ru.tinkoff.kora.http.server.common.HttpServerRequest;
import ru.tinkoff.kora.logging.common.MDC;

import java.util.UUID;
import java.util.concurrent.CompletionStage;

@Tag(HttpServerModule.class)
@Component
public final class LoggingInterceptor implements HttpServerInterceptor {

    @Override
    public CompletionStage<HttpServerResponse> intercept(Context context,
                                                         HttpServerRequest request,
                                                         InterceptChain chain) throws Exception {
        var traceId = headerOrRandom(request, "x-trace-id");
        var requestId = headerOrRandom(request, "x-request-id");

        MDC.put("traceId", traceId);
        MDC.put("requestId", requestId);
        try {
            return chain.process(context, request);
        } finally {
            MDC.remove("traceId");
            MDC.remove("requestId");
        }
    }

    private static String headerOrRandom(HttpServerRequest request, String name) {
        var value = request.headers().getFirst(name);
        return value != null ? value : UUID.randomUUID().toString();
    }
}
```

## Common MDC keys

| Key | Description | Source |
|-----|-------------|--------|
| `traceId` | Distributed tracing id | header or generated |
| `requestId` | Request identifier | header or generated |
| `userId` | User identifier | auth context |
| `spanId` | Span id | tracing module |

## Best practices

- Remove every key you put (Kora `MDC`) or use try-with-resources (SLF4J `MDC`).
- Generate correlation ids at the request entry point (interceptor).
- Do not place secrets/PII in MDC.
- Standardize key names across services.
