# Spans and Context Reference

Creating manual spans, setting attributes, propagating `OpentelemetryContext` across async boundaries, reading the current span, and overriding the sampler.

## Contents

- [Tracer injection](#tracer-injection)
- [Manual span lifecycle](#manual-span-lifecycle)
- [Span attributes](#span-attributes)
- [Span kinds](#span-kinds)
- [Reading the current span](#reading-the-current-span)
- [Async propagation (CompletableFuture)](#async-propagation-completablefuture)
- [Coroutine propagation (Kotlin)](#coroutine-propagation-kotlin)
- [Reusable wrapper component](#reusable-wrapper-component)
- [Sampler override](#sampler-override)
- [Best practices](#best-practices)

## Tracer injection

Inject `io.opentelemetry.api.trace.Tracer` via the constructor. The framework provides it once an exporter module is connected.

```java
@Component
public final class OrderService {
    private final Tracer tracer;

    public OrderService(Tracer tracer) {
        this.tracer = tracer;
    }
}
```

Use constructor injection. Kora has no field injection.

## Manual span lifecycle

The correct lifecycle for a span tied to the current Kora request:

1. `Context.current()` — the Kora request context.
2. `OpentelemetryContext.get(ctx)` — the OpenTelemetry context inside it.
3. `tracer.spanBuilder(name).setParent(otctx.getContext()).startSpan()` — parent on the request.
4. `OpentelemetryContext.set(ctx, otctx.add(span))` — make this span current.
5. work; `span.setStatus(StatusCode.OK)` on success.
6. on error: `span.recordException(e)` + `span.setStatus(StatusCode.ERROR, e.getMessage())`.
7. in `finally`: `span.end()` and restore with `OpentelemetryContext.set(ctx, otctx)`.

```java
public Order processOrder(Order order) {
    var ctx = Context.current();
    var otctx = OpentelemetryContext.get(ctx);
    var span = tracer.spanBuilder("order.process")
            .setParent(otctx.getContext())
            .setAttribute("order.id", order.id())
            .startSpan();

    OpentelemetryContext.set(ctx, otctx.add(span));
    try {
        var result = doProcess(order);
        span.setStatus(StatusCode.OK);
        return result;
    } catch (RuntimeException e) {
        span.recordException(e);
        span.setStatus(StatusCode.ERROR, e.getMessage());
        throw e;
    } finally {
        span.end();
        OpentelemetryContext.set(ctx, otctx);
    }
}
```

Skipping `setParent(otctx.getContext())` makes the span a new root trace, disconnected from the incoming request.

## Span attributes

```java
span.setAttribute("custom.operation", "processOrder");
span.setAttribute("http.method", "GET");
span.setAttribute("http.status_code", 200);
span.setAttribute("db.system", "postgresql");
```

Use OpenTelemetry semantic-convention names where they exist.

| Category | Attributes |
|----------|------------|
| HTTP | `http.method`, `http.url`, `http.target`, `http.status_code`, `http.scheme`, `http.host` |
| gRPC | `rpc.system`, `rpc.service`, `rpc.method`, `rpc.grpc.status_code` |
| Database | `db.system`, `db.statement`, `db.operation`, `db.name`, `db.user` |
| Messaging | `messaging.system`, `messaging.destination`, `messaging.operation` |

Never put personal data (user id, email, phone) in span names or attributes.

## Span kinds

```java
var span = tracer.spanBuilder("order.process")
        .setSpanKind(SpanKind.INTERNAL)
        .startSpan();
```

| Kind | Use case |
|------|----------|
| `SERVER` | Inbound request (HTTP endpoint, gRPC handler) |
| `CLIENT` | Outbound call (HTTP client, DB query) |
| `PRODUCER` | Message send (Kafka producer) |
| `CONSUMER` | Message receive (Kafka consumer) |
| `INTERNAL` | Internal business operation (default) |

## Reading the current span

`OpentelemetryContext` exposes static accessors for the current request:

```java
var span = OpentelemetryContext.getSpan();
var traceId = OpentelemetryContext.getTraceId();
```

## Async propagation (CompletableFuture)

When work moves to another thread, `fork()` the Kora `Context` before the hop so the child execution carries its own copy, and register the span inside the async body.

```java
public CompletionStage<Order> processOrderAsync(Order order) {
    var ctx = Context.current().fork();
    var otctx = OpentelemetryContext.get(ctx);
    var span = tracer.spanBuilder("order.process.async")
            .setParent(otctx.getContext())
            .startSpan();

    return CompletableFuture.supplyAsync(() -> {
                OpentelemetryContext.set(ctx, otctx.add(span));
                return doProcess(order);
            })
            .whenComplete((r, e) -> {
                if (e != null) {
                    span.recordException(e);
                    span.setStatus(StatusCode.ERROR, e.getMessage());
                } else {
                    span.setStatus(StatusCode.OK);
                }
                span.end();
            });
}
```

## Coroutine propagation (Kotlin)

For `suspend` functions, attach the Kora `Context` to the coroutine context via `Context.Kotlin.asCoroutineContext(ctx)`.

```kotlin
suspend fun processOrder(order: Order): Order {
    val ctx = Context.current()
    val otctx = OpentelemetryContext.get(ctx)
    val span = tracer.spanBuilder("order.process")
        .setParent(otctx.context)
        .startSpan()

    OpentelemetryContext.set(ctx, otctx.add(span))
    return withContext(Context.Kotlin.asCoroutineContext(ctx)) {
        try {
            val result = doProcess(order)
            span.setStatus(StatusCode.OK)
            result
        } catch (e: Exception) {
            span.recordException(e)
            span.setStatus(StatusCode.ERROR, e.message ?: "error")
            throw e
        } finally {
            span.end()
            OpentelemetryContext.set(ctx, otctx)
        }
    }
}
```

## Reusable wrapper component

Centralize the span lifecycle in one `@Component` so call sites pass only a name and a lambda.

```java
@Component
public final class TracingService {

    private final Tracer tracer;

    public TracingService(Tracer tracer) {
        this.tracer = tracer;
    }

    public <T> T trace(String operationName, Supplier<T> operation) {
        var ctx = Context.current();
        var otctx = OpentelemetryContext.get(ctx);
        var span = tracer.spanBuilder(operationName)
                .setParent(otctx.getContext())
                .startSpan();

        OpentelemetryContext.set(ctx, otctx.add(span));
        try {
            T result = operation.get();
            span.setStatus(StatusCode.OK);
            return result;
        } catch (RuntimeException e) {
            span.recordException(e);
            span.setStatus(StatusCode.ERROR, e.getMessage());
            throw e;
        } finally {
            span.end();
            OpentelemetryContext.set(ctx, otctx);
        }
    }
}
```

Call site:

```java
public Order createOrder(OrderRequest request) {
    return tracingService.trace("order.create", () -> repository.save(request));
}
```

## Sampler override

Sampling is **not** a config key. The default sampler is `Sampler.parentBased(Sampler.alwaysOn())`, provided by `OpentelemetryTracingModule#opentelemetryTracingSampler()` as a `@DefaultComponent`. Override it by declaring a method with the same return type in the `@KoraApp` interface (a non-default component shadows the default one).

```java
import io.opentelemetry.sdk.trace.samplers.Sampler;
import ru.tinkoff.kora.common.KoraApp;
import ru.tinkoff.kora.opentelemetry.tracing.exporter.grpc.OpentelemetryGrpcExporterModule;

@KoraApp
public interface Application extends OpentelemetryGrpcExporterModule {

    // Sample 10% of root traces; follow the parent decision for child spans.
    default Sampler opentelemetryTracingSampler() {
        return Sampler.parentBased(Sampler.traceIdRatioBased(0.1));
    }

    static void main(String[] args) {
        KoraApplication.run(ApplicationGraph::graph);
    }
}
```

`Sampler` comes from the OpenTelemetry SDK (`io.opentelemetry.sdk.trace.samplers.Sampler`); useful factories: `alwaysOn()`, `alwaysOff()`, `traceIdRatioBased(double)`, `parentBased(Sampler)`.

## Best practices

- Always `span.end()` in `finally`.
- Record exceptions with `span.recordException(e)` and set `StatusCode.ERROR`.
- Restore the previous `OpentelemetryContext` after a manual span.
- Name spans after operations (`order.create`), not method or class names.
- Keep attribute cardinality low on high-traffic spans.
- `fork()` the Kora `Context` before async hops.
- Do not create a parentless span inside an active request.
