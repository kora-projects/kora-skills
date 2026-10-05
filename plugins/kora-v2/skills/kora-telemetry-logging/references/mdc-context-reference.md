# MDC Reference

Kora 2.0 has **two** MDCs, and they are not interchangeable. This file covers the values; for the
declarative `@Mdc` aspect see [`kora-aop-logging`](../../kora-aop-logging/SKILL.md).

## Contents

- [Kora MDC vs SLF4J MDC](#kora-mdc-vs-slf4j-mdc)
- [Kora MDC is a ScopedValue](#kora-mdc-is-a-scopedvalue)
- [Where a scope is bound](#where-a-scope-is-bound)
- [Using Kora MDC](#using-kora-mdc)
- [SLF4J MDC](#slf4j-mdc)
- [Seeding MDC from an HTTP interceptor](#seeding-mdc-from-an-http-interceptor)
- [Porting a Kora 1.x Context-based helper](#porting-a-kora-1x-context-based-helper)
- [Best practices](#best-practices)

## Kora MDC vs SLF4J MDC

| | `io.koraframework.logging.common.MDC` | `org.slf4j.MDC` |
|---|---|---|
| Value type | structured — `String`, `Integer`, `Long`, `Boolean`, `StructuredArgumentWriter` (written as JSON) | `String` only |
| Storage | `ScopedValue<MDC>` holding a mutable `MDC` object | thread-local map |
| API | static `put` / `remove`, instance `put0` / `remove0` / `fork` / `values` | `put` / `remove` / `clear` / `putCloseable` |
| Carried across `KoraAsyncAppender` | yes — snapshotted into `KoraLoggingEvent.koraMdc()` | yes — Logback copies `getMDCPropertyMap()` |
| Rendered by `ConsoleTextRecordEncoder` | yes, as `key=<json>` | yes, as `key=value` |
| Rendered by `JsonRecordEncoder` | yes, inside `mdc` with its JSON type | yes, inside `mdc` as a string; a Kora key of the same name wins |
| Readable by a `%X{key}` pattern | **no** (use `KoraMdcConverter`) | yes |

Both are printed by the Kora encoders; the difference that matters day to day is that
`%X{}` only sees the SLF4J one, and only the Kora one can hold non-string values.

Do not import both under the bare name `MDC` in one file — one of them has to be fully qualified.

## Kora MDC is a `ScopedValue`

```java
public class MDC {
    public static final ScopedValue<MDC> VALUE = ScopedValue.newInstance();

    public static MDC get() { return VALUE.get(); }
    public static void put(String key, String value) { get().put0(key, value); }
    …
}
```

`MDC.get()` therefore throws **`java.util.NoSuchElementException`** when the scoped value is
unbound — during graph initialization, in a shutdown hook, or in a plain unit test that is not
inside a Kora-managed scope (`ScopedValue.get()` is specified to throw it when not bound). Kora's own code
guards for it; yours should too where the call site can run outside a request:

```java
var snapshot = MDC.VALUE.isBound() ? Map.copyOf(MDC.get().values()) : Map.<String, StructuredArgumentWriter>of();
```

`KoraAsyncAppender.append` does exactly this — reading an unbound `ScopedValue` there would throw
inside the appender and drop the event.

## Where a scope is bound

Kora binds a fresh `MDC` at the entry of every unit of work. Inside these, `MDC.put(...)` just
works; outside them it throws.

| Scope | Bound by |
|---|---|
| HTTP request (Undertow) | `KoraRequestProcessingHttpHandler.handleRequest` — `ScopedValue.where(MDC.VALUE, new MDC())` around the whole exchange |
| gRPC call | `VirtualThreadExecutorTransportFilter` |
| Kafka record / batch | `RecordHandler` / `RecordsHandler` (a per-record handler `fork()`s the batch MDC) |
| Kafka publish | `DefaultKafkaPublisherRecordObservation` — forks the bound MDC, or creates an empty one if none |
| Scheduled job | `KoraJdkJob` (JDK), `KoraQuartzJob` (Quartz), `KoraDbJob` (db-scheduler) |
| JMS message | `JmsMessageListenerContainer` |

Because the `MDC` instance is created per unit of work and discarded with it, removing your keys at
the end is optional hygiene rather than a leak fix. `fork()` produces an independent copy — use it
when handing context to work that outlives the current scope.

## Using Kora MDC

===! "Java"

    ```java
    import io.koraframework.logging.common.MDC;

    MDC.put("orderId", orderId);          // String
    MDC.put("attempt", attempt);          // Integer
    MDC.put("retryable", true);           // Boolean
    MDC.put("payload", gen -> {           // StructuredArgumentWriter — arbitrary JSON
        gen.writeStartObject();
        gen.writeStringProperty("kind", kind);
        gen.writeEndObject();
    });

    log.info("Processing order");         // all four keys attached to this and later records
    MDC.remove("payload");
    ```

=== "Kotlin"

    ```kotlin
    import io.koraframework.logging.common.MDC

    MDC.put("orderId", orderId)
    MDC.put("attempt", attempt)
    log.info("Processing order")
    MDC.remove("attempt")
    ```

Overloads accept `String`, `Integer`, `Long`, `Boolean` and `StructuredArgumentWriter`; a `null`
value is stored as JSON `null` rather than removing the key.

## SLF4J MDC

Plain SLF4J works because Kora logs through SLF4J. Use it for simple string context that a
`%X{key}` pattern must be able to read.

```java
import org.slf4j.MDC;

try (var t = MDC.putCloseable("traceId", traceId);
     var u = MDC.putCloseable("userId", userId)) {
    log.info("Processing request");
}
```

Note that the Undertow handler calls `org.slf4j.MDC.clear()` at the start of every request, so a
stale thread-local from a pooled/carrier thread cannot leak into the next request.

## Seeding MDC from an HTTP interceptor

A global interceptor is a `@Component` tagged with `@Tag(HttpServer.class)` — `HttpServerModule`
injects them as `@Tag(HttpServer.class) All<HttpServerInterceptor>`, so several may coexist. The
2.0 contract is synchronous:

```java
public interface HttpServerInterceptor {
    HttpServerResponse intercept(HttpServerRequest request, InterceptChain chain) throws Exception;

    interface InterceptChain {
        HttpServerResponse process(HttpServerRequest request) throws Exception;
    }
}
```

```java
import io.koraframework.common.annotation.Component;
import io.koraframework.common.annotation.Tag;
import io.koraframework.http.server.common.HttpServer;
import io.koraframework.http.server.common.interceptor.HttpServerInterceptor;
import io.koraframework.http.server.common.request.HttpServerRequest;
import io.koraframework.http.server.common.response.HttpServerResponse;
import io.koraframework.logging.common.MDC;

import java.util.UUID;

@Tag(HttpServer.class)
@Component
public final class LoggingInterceptor implements HttpServerInterceptor {

    @Override
    public HttpServerResponse intercept(HttpServerRequest request, InterceptChain chain) throws Exception {
        MDC.put("requestId", headerOrRandom(request, "x-request-id"));
        return chain.process(request);
    }

    private static String headerOrRandom(HttpServerRequest request, String name) {
        var value = request.headers().getFirst(name);   // @Nullable; header names are lower-cased
        return value != null ? value : UUID.randomUUID().toString();
    }
}
```

`@Tag(HttpServerModule.class)` — the Kora 1.x tag — still compiles, because `HttpServerModule`
exists, but nothing looks interceptors up by it. The interceptor is then silently never invoked.
Cover it with a test.

Do not put `traceId` / `spanId` in MDC by hand: `KoraAsyncAppender` captures
`Span.current().getSpanContext()` into the event, and `ConsoleTextRecordEncoder` / `JsonRecordEncoder`
write `traceId` and `spanId` from it whenever the span context is valid.

## Porting a Kora 1.x `Context`-based helper

`ru.tinkoff.kora.common.Context` **does not exist in Kora 2.0** — the class was removed from the
whole framework, not just from the HTTP APIs. Any 1.x helper shaped like
`Context.current().set(key, value)` or a `Context`-keyed MDC bridge has nothing to port onto.

| Kora 1.x | Kora 2.0 |
|---|---|
| `Context` passed into interceptors / mappers | removed — the interceptor takes only the request and the chain |
| custom `Context.Key<T>` for request-scoped state | your own `ScopedValue<T>`, bound with `ScopedValue.where(...)` |
| `Context`-backed MDC helper | `io.koraframework.logging.common.MDC` directly, inside a framework-bound scope |

## Best practices

- Put correlation ids in at the entry point (interceptor, listener, job), not deep in the stack.
- Never put secrets or PII in MDC — MDC values go into every record of the scope.
- Standardise key names across services; a structured MDC is only useful if keys are stable.
- Guard `MDC.get()` with `MDC.VALUE.isBound()` in code that can also run outside a request.
- Use SLF4J MDC when a `%X{}` pattern has to read the value; use Kora MDC for anything typed.
