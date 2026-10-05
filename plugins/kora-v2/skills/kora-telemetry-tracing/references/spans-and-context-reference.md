# Spans and Context Reference

Creating custom spans in Kora 2.0, how span context actually propagates now that Kora's own
`Context` type is gone, reading the current span, crossing thread and process boundaries, and
overriding the sampler.

## Contents

- [The one thing to get right: two types named Context](#the-one-thing-to-get-right-two-types-named-context)
- [How propagation works](#how-propagation-works)
- [KoraTracer — the default way to add a span](#koratracer--the-default-way-to-add-a-span)
- [Raw Tracer + ScopedValue — when you need the SpanBuilder](#raw-tracer--scopedvalue--when-you-need-the-spanbuilder)
- [Span attributes and semantic conventions](#span-attributes-and-semantic-conventions)
- [Span kinds](#span-kinds)
- [Reading the current span](#reading-the-current-span)
- [Crossing a thread boundary](#crossing-a-thread-boundary)
- [Crossing a process boundary (W3C trace context)](#crossing-a-process-boundary-w3c-trace-context)
- [Sampler override](#sampler-override)
- [Migrating a Kora 1.x manual span](#migrating-a-kora-1x-manual-span)
- [Best practices](#best-practices)

## The one thing to get right: two types named Context

Kora 2.0 removed `io.koraframework.common.Context` entirely — there is no `Context.current()`, no
`Context.fork()`, no `Context.Kotlin.asCoroutineContext(...)`, and no Kora context object to pass
around. Contracts are synchronous and run on virtual threads.

There are still two types you will see named `Context`, and they are unrelated to the removed one:

| Type | What it is |
|---|---|
| `io.opentelemetry.context.Context` | **The** context in 2.0. Standard OpenTelemetry immutable key/value context that carries the current `Span`. This is the type you use |
| `io.koraframework.common.telemetry.OpentelemetryContext` | Kora's `implements Context` wrapper in the `common` artifact. Its job is to hold `public static final ScopedValue<Context> VALUE` and to implement `wrap(...)`. You touch it only to name the `ScopedValue` |

A 1.x snippet that calls `OpentelemetryContext.get(ctx)`, `.set(ctx, …)`, `.add(span)`,
`.getContext()`, `OpentelemetryContext.getSpan()` or `OpentelemetryContext.getTraceId()` is dead
code — none of those members exist. The class in 2.0 has `VALUE`, a constructor, and the `Context`
interface methods.

## How propagation works

`core/common` registers `OpentelemetryContextStorageProvider` through
`META-INF/services/io.opentelemetry.context.ContextStorageProvider` and the `module-info`
`provides` clause, so **OpenTelemetry's own `Context.current()` is backed by a `ScopedValue`**:

```java
public class OpentelemetryContextStorage implements ContextStorage {
    @Override public Scope attach(Context toAttach) { throw new IllegalStateException(); }
    @Override public @Nullable Context current() {
        return OpentelemetryContext.VALUE.isBound() ? OpentelemetryContext.VALUE.get() : null;
    }
    @Override public Context root() { return new OpentelemetryContext(ContextStorage.super.root()); }
}
```

Three consequences:

1. **`Context.current()` and `Span.current()` work everywhere**, with no argument threading — they
   read the `ScopedValue`. This is what replaces passing a Kora `Context` around.
2. **`attach(...)` throws.** So `span.makeCurrent()`, `context.makeCurrent()` and every
   `try (Scope scope = …)` idiom from the OpenTelemetry documentation fail at runtime with
   `IllegalStateException`. Rebinding is done with `ScopedValue.where(...)`, which is lexically
   scoped and unwinds itself — there is nothing to close and nothing to restore in a `finally`.
3. **Derived contexts stay Kora's.** `OpentelemetryContext.with(key, value)` re-wraps, because only
   this class implements `wrap(...)` on top of the `ScopedValue`. `core/common`'s
   `OpentelemetryContextTest` pins both that and the exporter's internal suppression path.

Every framework integration binds the same way — HTTP server, HTTP client, gRPC, JDBC, Cassandra,
Kafka, Redis cache, scheduling, SOAP:

```java
ScopedValue.where(Observation.VALUE, observation)
    .where(OpentelemetryContext.VALUE, Context.current().with(observation.span()))
    .call(() -> { … });
```

The Kora annotation processor and KSP emit exactly this shape into generated code
(`CommonUtils` for Java, `KotlinPoetUtils.observe` for Kotlin), so your hand-written spans should
look the same.

## KoraTracer — the default way to add a span

`io.koraframework.opentelemetry.tracing.KoraTracer` is supplied as a `@DefaultComponent` by
`OpentelemetryTracingModule`. It starts the span, binds it into `OpentelemetryContext.VALUE` for the
callback, sets `StatusCode.OK` on normal return, records the exception and sets `StatusCode.ERROR`
on throw, and ends the span in a `finally`. Use it unless you need the `SpanBuilder`.

Public API:

| Method | Effect |
|---|---|
| `<T, E extends Throwable> T traceParent(String, TraceCallable<T, E>)` | Span nested under the current one, returns a value |
| `<E extends Throwable> void traceParent(String, TraceRunnable<E>)` | Same, no return value |
| `<T, E extends Throwable> T traceNew(String, TraceCallable<T, E>)` | `setNoParent()` + binds `Context.root().with(span)` — a detached root trace |
| `<E extends Throwable> void traceNew(String, TraceRunnable<E>)` | Same, no return value |
| `Tracer tracer()` | The underlying OpenTelemetry `Tracer` |

`TraceCallable<T, E>` is `T call(Span span) throws E`; `TraceRunnable<E>` is
`void run(Span span) throws E`. The callback receives the live `Span`, so attributes and events go
on it directly. The checked-exception type parameter propagates, so a callback that throws a checked
exception stays checked at the call site.

### Java

```java
import io.koraframework.common.annotation.Component;
import io.koraframework.opentelemetry.tracing.KoraTracer;

@Component
public final class OrderService {

    private final KoraTracer tracer;
    private final OrderRepository repository;

    public OrderService(KoraTracer tracer, OrderRepository repository) {
        this.tracer = tracer;
        this.repository = repository;
    }

    public Order processOrder(Order order) {
        return tracer.traceParent("order.process", span -> {
            span.setAttribute("order.id", order.id());
            span.setAttribute("order.items", order.items().size());
            var saved = repository.save(order);
            span.addEvent("order.persisted");
            return saved;
        });
    }
}
```

### Kotlin

Kotlin will not choose between the `TraceCallable` and `TraceRunnable` overloads from a bare lambda.
Use the explicit SAM constructor with both type arguments — the same pattern the migrated examples
use for `JdbcExecutor.SqlSupplier { … }` and `TransactionalConsumer<T, E> { … }`:

```kotlin
import io.koraframework.common.annotation.Component
import io.koraframework.opentelemetry.tracing.KoraTracer

@Component
class OrderService(
    private val tracer: KoraTracer,
    private val repository: OrderRepository
) {

    fun processOrder(order: Order): Order =
        tracer.traceParent("order.process", KoraTracer.TraceCallable<Order, RuntimeException> { span ->
            span.setAttribute("order.id", order.id)
            repository.save(order)
        })

    fun archive(order: Order) =
        tracer.traceParent("order.archive", KoraTracer.TraceRunnable<RuntimeException> { span ->
            span.setAttribute("order.id", order.id)
            repository.archive(order)
        })
}
```

### `traceParent` vs `traceNew`

`traceParent` uses `setParent(Context.current())`, so outside any request it produces a root span
anyway — it is the right default almost always. `traceNew` explicitly calls `setNoParent()` and
binds `Context.root().with(span)`; reach for it only when a unit of work must **not** be attributed
to the caller's trace, e.g. a background task kicked off from a request that outlives it.

## Raw Tracer + ScopedValue — when you need the SpanBuilder

`KoraTracer`'s `Consumer<SpanBuilder>` overloads are private, so it cannot set `SpanKind`, links, a
custom start timestamp, or an explicit parent. For those, inject `io.opentelemetry.api.trace.Tracer`
and bind the `ScopedValue` yourself.

```java
import io.koraframework.common.annotation.Component;
import io.koraframework.common.telemetry.OpentelemetryContext;
import io.opentelemetry.api.trace.SpanKind;
import io.opentelemetry.api.trace.StatusCode;
import io.opentelemetry.api.trace.Tracer;
import io.opentelemetry.context.Context;

@Component
public final class PaymentGateway {

    private final Tracer tracer;

    public PaymentGateway(Tracer tracer) {
        this.tracer = tracer;
    }

    public Receipt charge(Payment payment) {
        var span = tracer.spanBuilder("payment.charge")
                .setSpanKind(SpanKind.CLIENT)
                .setParent(Context.current())
                .setAttribute("payment.provider", payment.provider())
                .startSpan();

        return ScopedValue.where(OpentelemetryContext.VALUE, Context.current().with(span))
                .call(() -> {
                    try {
                        var receipt = doCharge(payment);
                        span.setStatus(StatusCode.OK);
                        return receipt;
                    } catch (RuntimeException e) {
                        span.recordException(e);
                        span.setStatus(StatusCode.ERROR, e.getMessage());
                        throw e;
                    } finally {
                        span.end();
                    }
                });
    }
}
```

Kotlin — `Carrier.call` takes the result type and the throwable type as explicit arguments, exactly
as the KSP generator emits:

```kotlin
val span = tracer.spanBuilder("payment.charge")
    .setSpanKind(SpanKind.CLIENT)
    .setParent(Context.current())
    .startSpan()

return ScopedValue.where(OpentelemetryContext.VALUE, Context.current().with(span))
    .call<Receipt, RuntimeException> {
        try {
            doCharge(payment).also { span.setStatus(StatusCode.OK) }
        } catch (e: RuntimeException) {
            span.recordException(e)
            span.setStatus(StatusCode.ERROR, e.message ?: "error")
            throw e
        } finally {
            span.end()
        }
    }
```

Use `.run(Runnable { … })` when there is no result — spell the `Runnable` out, because a bare
`carrier.run { … }` collides with Kotlin's stdlib `run` scope function.

The binding ends when the `ScopedValue` scope ends; you never restore a previous context by hand.
`span.end()` still belongs in a `finally` — the `ScopedValue` unwinds the binding, not the span.

## Span attributes and semantic conventions

Kora 2.0 depends on `io.opentelemetry.semconv:opentelemetry-semconv` and
`opentelemetry-semconv-incubating` through `opentelemetry-common`, and every framework span uses the
**typed** `AttributeKey` constants rather than raw strings:

```java
import io.opentelemetry.semconv.HttpAttributes;
import io.opentelemetry.semconv.ServerAttributes;
import io.opentelemetry.semconv.UrlAttributes;
import io.opentelemetry.semconv.ErrorAttributes;
import io.opentelemetry.semconv.DbAttributes;

span.setAttribute(HttpAttributes.HTTP_REQUEST_METHOD, "GET");
span.setAttribute(HttpAttributes.HTTP_ROUTE, "/orders/{id}");
span.setAttribute(ServerAttributes.SERVER_ADDRESS, host);
span.setAttribute(UrlAttributes.URL_SCHEME, "https");
span.setAttribute(DbAttributes.DB_SYSTEM_NAME, "postgresql");
```

Prefer the typed constants over string literals: they are the names the framework's own spans use,
so your spans stay queryable next to them. Free-form business attributes keep plain string keys
(`span.setAttribute("order.id", id)`).

The 1.x attribute names (`http.method`, `http.status_code`, `db.system`, `db.statement`) belong to
an older semantic-convention generation and no longer match what Kora emits — do not mix them into
new spans.

Never put personal data — user id, email, phone, tokens — in span names or attributes. Keep
attribute cardinality low on high-traffic spans; span names must be templates
(`GET /orders/{id}`), never interpolated identifiers.

## Span kinds

```java
var span = tracer.spanBuilder("order.process")
        .setSpanKind(SpanKind.INTERNAL)
        .startSpan();
```

| Kind | Use |
|---|---|
| `SERVER` | Inbound request — what the HTTP server and gRPC server set |
| `CLIENT` | Outbound call — HTTP client, DB query, cache, S3 |
| `PRODUCER` | Message publish (Kafka producer) |
| `CONSUMER` | Message receive (Kafka consumer) |
| `INTERNAL` | Business step inside the service — the default, and what `KoraTracer` produces |

## Reading the current span

```java
import io.opentelemetry.api.trace.Span;

var span = Span.current();                                 // never null; Span.getInvalid() if none
var traceId = span.getSpanContext().getTraceId();
var sampled = span.getSpanContext().isSampled();
if (span.getSpanContext().isValid()) {
    span.addEvent("cache.miss");
}
```

`Span.current()` resolves through `Context.current()` and therefore through the `ScopedValue`. Always
guard on `isValid()` before treating a trace id as meaningful — outside a traced scope, or with
tracing disabled, you get `Span.getInvalid()` and an all-zero trace id.

This is also how log correlation works, with no configuration: `KoraAsyncAppender` captures
`Span.current().getSpanContext()` on every event; the text encoder prints `traceId=<id> spanId=<id>`
and the JSON encoder writes `traceId` / `spanId` fields whenever that span context is valid (see
[kora-telemetry-logging](../../kora-telemetry-logging/SKILL.md)).

For the framework's own observation of the current unit of work there is
`io.koraframework.common.telemetry.Observation`, bound alongside the span
(`Observation.current(HttpServerObservation.class)`). It is a framework-facing contract — reach for
`Span.current()` in application code.

## Crossing a thread boundary

A `ScopedValue` binding is not inherited by an arbitrary thread you hand a task to, so the context
has to travel with the task. `OpentelemetryContext` implements every OpenTelemetry `wrap*` method on
top of `ScopedValue.where(...)`, which is exactly the mechanism to use:

```java
var context = Context.current();                       // capture inside the traced scope

executor.submit(context.wrap(() -> {
    // Context.current() and Span.current() see the captured context here
    doBackgroundWork();
}));

CompletableFuture.supplyAsync(context.wrapSupplier(this::computeSomething), executor);
```

`wrap(Runnable)`, `wrap(Callable)`, `wrapSupplier`, `wrapFunction` (unary and binary) and
`wrapConsumer` (unary and binary) are all implemented. Capture the `Context` on the originating
thread — calling `Context.current()` inside the task body is too late.

A span that outlives the submitting scope must be created before the hop and ended in the task (or
in the future's completion callback), because `ScopedValue` unwinds when the enclosing call returns.

Prefer not needing this at all: contracts in 2.0 are synchronous on virtual threads, so ordinary
sequential code is already traced end to end. Real parallelism belongs in `StructuredTaskScope`
(a preview API — see `kora-project-setup-java`/`-kotlin` for the flags), where each subtask still
needs `context.wrap(...)`.

## Crossing a process boundary (W3C trace context)

Incoming and outgoing HTTP, gRPC and Kafka propagation is handled by the framework — you do not
write it. The HTTP server does exactly this per request:

```java
var rootCtx = W3CTraceContextPropagator.getInstance()
        .extract(Context.root(), exchange.getRequestHeaders(), HttpServerExchangeMapGetter.INSTANCE);
// … route, observe, then inject the resulting context into the response headers
```

so `traceparent` on an inbound request continues the caller's trace automatically, and the response
carries the server span's context back.

You only need `W3CTraceContextPropagator` yourself for a transport Kora does not own — a custom
protocol, a job payload, a webhook envelope. Extract with `Context.root()` as the base, inject from
`Context.current()`, and bind the extracted context with `ScopedValue.where(...)` before doing the
work.

## Sampler override

Sampling is a component, not configuration. There is no `tracing.sampler` key and no
`tracing.exporter.sampler` key. `OpentelemetryTracingModule` declares:

```java
@DefaultComponent
default Sampler opentelemetryTracingSampler() {
    return Sampler.parentBased(Sampler.alwaysOn());
}
```

Override it on the `@KoraApp` interface. The `@Override` annotation is **load-bearing**, not
decoration: the `@KoraApp` annotation processor checks `getAnnotation(Override.class)` and removes
the overridden module method from the component set (`KoraAppUtils`), and KSP does the same on
`Modifier.OVERRIDE`. Drop `@Override` in Java and the module's declaration stays in the graph
alongside yours.

```java
import io.koraframework.application.graph.KoraApplication;
import io.koraframework.common.annotation.KoraApp;
import io.koraframework.config.hocon.HoconConfigModule;
import io.koraframework.opentelemetry.tracing.exporter.grpc.OpentelemetryGrpcExporterModule;
import io.opentelemetry.sdk.trace.samplers.Sampler;

@KoraApp
public interface Application extends HoconConfigModule, OpentelemetryGrpcExporterModule {

    // 10% of root traces; children follow the parent's decision.
    @Override
    default Sampler opentelemetryTracingSampler() {
        return Sampler.parentBased(Sampler.traceIdRatioBased(0.1));
    }

    static void main(String[] args) {
        KoraApplication.run(ApplicationGraph::graph);
    }
}
```

```kotlin
@KoraApp
interface Application : HoconConfigModule, OpentelemetryGrpcExporterModule {

    override fun opentelemetryTracingSampler(): Sampler =
        Sampler.parentBased(Sampler.traceIdRatioBased(0.1))
}
```

Factories on `io.opentelemetry.sdk.trace.samplers.Sampler`: `alwaysOn()`, `alwaysOff()`,
`traceIdRatioBased(double)`, `parentBased(Sampler)`. `parentBased` is what the framework default
uses, and keeping it in the chain is what makes a child span honour the caller's sampling decision
instead of re-rolling the dice and producing half-sampled traces.

To drive the ratio from config, take your own `@ConfigSource` interface as a parameter of the
override — it is an ordinary graph component method:

```java
default Sampler opentelemetryTracingSampler(SamplingConfig config) {
    return Sampler.parentBased(Sampler.traceIdRatioBased(config.ratio()));
}
```

`IdGenerator` and `Supplier<SpanLimits>` are `@DefaultComponent` too and are replaced the same way.

## Migrating a Kora 1.x manual span

| Kora 1.x | Kora 2.0 |
|---|---|
| `ru.tinkoff.kora.common.Context.current()` | removed — nothing replaces it; use `io.opentelemetry.context.Context.current()` for the span context |
| `Context.current().fork()` | removed — capture `Context.current()` and use `context.wrap(...)` |
| `Context.Kotlin.asCoroutineContext(ctx)` | removed — 2.0 has no `suspend` contracts |
| `OpentelemetryContext.get(ctx)` | `Context.current()` |
| `otctx.getContext()` / `otctx.context` | the `Context` itself |
| `OpentelemetryContext.set(ctx, otctx.add(span))` | `ScopedValue.where(OpentelemetryContext.VALUE, Context.current().with(span))` |
| `OpentelemetryContext.set(ctx, otctx)` in `finally` | nothing — the `ScopedValue` scope unwinds itself |
| `OpentelemetryContext.getSpan()` | `Span.current()` |
| `OpentelemetryContext.getTraceId()` | `Span.current().getSpanContext().getTraceId()` |
| hand-rolled `TracingService` wrapper | inject `KoraTracer` |
| `span.makeCurrent()` / `try (Scope …)` | `IllegalStateException` at runtime — use `ScopedValue.where(...)` |
| `ru.tinkoff.kora:opentelemetry-tracing-exporter-*` | `io.koraframework:opentelemetry-tracing-exporter-*` |

## Best practices

- Reach for `KoraTracer` first; drop to the raw `Tracer` only for `SpanKind`, links or an explicit
  parent.
- End every raw-`Tracer` span in a `finally`. `ScopedValue` unwinds the binding, not the span.
- Never call `makeCurrent()` / `attach()` — it throws in Kora.
- Name spans after operations and templates (`order.create`, `GET /orders/{id}`), never after
  methods, classes or interpolated ids.
- Record failures with `span.recordException(e)` **and** `span.setStatus(StatusCode.ERROR, msg)`;
  the exception alone does not fail the span.
- Do not wrap a single repository call in a manual span — JDBC, Cassandra, HTTP client, Kafka, gRPC,
  cache and S3 already emit their own.
- Guard on `Span.current().getSpanContext().isValid()` before logging or branching on a trace id.
- Keep attributes low-cardinality and free of personal data.
- Capture the `Context` before a thread hop and wrap the task; never call `Context.current()` inside
  the task body.
