---
name: kora-telemetry-tracing
description: "Kora 2.0 OpenTelemetry tracing — artifact opentelemetry-tracing plus the two OTLP exporters opentelemetry-tracing-exporter-grpc and opentelemetry-tracing-exporter-http, the OpentelemetryTracingModule / OpentelemetryGrpcExporterModule / OpentelemetryHttpExporterModule graph modules, the tracing and tracing.exporter config keys, OpentelemetryTracingAttributesProvider resource attributes, custom spans through the injected KoraTracer or io.opentelemetry.api.trace.Tracer, and span-context propagation through the ScopedValue-backed io.koraframework.common.telemetry.OpentelemetryContext. Use when exporting traces to an OTLP backend (OpenTelemetry Collector, Jaeger, Grafana Tempo), adding business spans, overriding the Sampler, or debugging spans that never appear."
license: Apache-2.0
metadata:
  kora-version: "2.x"
---

# Kora Telemetry Tracing

> **Kora sub-skill — obey the [kora-v2 meta rules](../../SKILL.md) on every task:** **R0** ground the workspace on Kora 2.0 refs before starting (framework source at tag `2.0.0.RC2` + `kora-examples` at `migration/2.0` + Kora 2.0 docs at koraframework.io/v2, which trail the source; 1.x `kora-docs` pages are never an authority) · **R1** read this sub-skill before writing code · **R2** Kora 2.0 APIs only — no Spring/Micronaut/Quarkus, no Kora 1.x APIs, no invented annotations or config keys · **R3** journal any incorrect Kora usage. Add comments/Javadoc only if asked.

**Version:** Kora 2.0 (`io.koraframework`, `2.0.0.RC2` on Maven Central) | **Java:** 25 | **OpenTelemetry:** 1.66.0 | **Gradle:** 9.8.0

Kora 2.0 produces OpenTelemetry spans and exports them in OTLP. Modules that carry telemetry (HTTP
server/client, JDBC, Cassandra, Kafka, gRPC, cache, scheduling, SOAP, S3) already emit their own
spans; you add one exporter module, point it at an OTLP endpoint, and add business spans where the
framework cannot infer them.

**Read this when:**

- adding OTLP export — `OpentelemetryGrpcExporterModule` or `OpentelemetryHttpExporterModule`,
- configuring the `tracing` / `tracing.exporter` sections,
- adding OTLP resource attributes computed at startup with `OpentelemetryTracingAttributesProvider`,
- writing a custom span with the injected `KoraTracer` or the raw `Tracer`,
- propagating span context to another thread or across a boundary the framework does not own,
- overriding the `Sampler`,
- debugging "the app is up, tracing is on, and there are no spans".

---

## 1. Three things to know before writing anything

**Tracing is ON by default.** `OpentelemetryTracingConfig.enabled()` returns `true`, and so does
the per-component `TelemetryConfig.TracingConfig.enabled()`. This is the opposite of the
per-component `telemetry.metrics.enabled` and `telemetry.logging.enabled`, which default to `false`.
You never write `tracing.enabled = true`; you only ever write `false` to switch it off.
`tracing.enabled = false` swaps in `TracerProvider.noop()` and turns both exporter components into
no-ops: nothing is recorded or exported.

**The one place where it is OFF: the system server.**
`SystemHttpServerConfig.SystemHttpServerTelemetryConfig.SystemHttpServerTracingConfig` overrides
`enabled()` to `false`, so nothing under `httpServer.system` — liveness, readiness, `/metrics` —
produces spans. Probe traffic showing up as "no spans" is correct behaviour, not a bug. Set
`httpServer.system.telemetry.tracing.enabled = true` if you actually want probe spans.

**Kora's own `Context` type is gone.** There is no `io.koraframework.common.Context`, no
`Context.current()`, no `Context.fork()`, no `OpentelemetryContext.get(ctx)` / `.set(ctx, …)`.
Contracts are synchronous on virtual threads and span context travels in a **`ScopedValue`**.
The type named `OpentelemetryContext` still exists but is a completely different thing:
`io.koraframework.common.telemetry.OpentelemetryContext` **implements**
`io.opentelemetry.context.Context` and exposes `ScopedValue<Context> VALUE`. See
[§4](#4-custom-spans) and the [spans reference](references/spans-and-context-reference.md).

---

## 2. Quick start

### 2.1 Dependency

Pick **one** exporter artifact. The protocol is fixed by the artifact, not by a config key.

| Artifact | Module interface | Wire protocol | Typical endpoint |
|---|---|---|---|
| `io.koraframework:opentelemetry-tracing-exporter-grpc` | `OpentelemetryGrpcExporterModule` | OTLP/gRPC | `http://collector:4317` |
| `io.koraframework:opentelemetry-tracing-exporter-http` | `OpentelemetryHttpExporterModule` | OTLP/HTTP | `http://collector:4318/v1/traces` |

Both `api`-depend on `io.koraframework:opentelemetry-tracing`, so the OpenTelemetry API
(`Tracer`, `Span`, `StatusCode`, `SpanKind`), the SDK trace package (`Sampler`) and the semantic
conventions come transitively — never add `io.opentelemetry:*` yourself.

=== "Java"
    ```groovy
    dependencies {
        koraBom platform("io.koraframework:kora-bom:$koraVersion")   // koraVersion=2.0.0.RC2
        annotationProcessor "io.koraframework:annotation-processors"

        implementation "io.koraframework:opentelemetry-tracing-exporter-grpc"
        // or: implementation "io.koraframework:opentelemetry-tracing-exporter-http"
    }
    ```

=== "Kotlin"
    ```kotlin
    dependencies {
        implementation(platform("io.koraframework:kora-bom:${property("koraVersion")}"))
        ksp("io.koraframework:symbol-processors:${property("koraVersion")}")

        implementation("io.koraframework:opentelemetry-tracing-exporter-grpc")
        // or: implementation("io.koraframework:opentelemetry-tracing-exporter-http")
    }
    ```

Never pin a version on an individual `io.koraframework:*` artifact — the BOM does it.

### 2.2 Connect the module

=== "Java"
    ```java
    import io.koraframework.application.graph.KoraApplication;
    import io.koraframework.common.annotation.KoraApp;
    import io.koraframework.config.hocon.HoconConfigModule;
    import io.koraframework.opentelemetry.tracing.exporter.grpc.OpentelemetryGrpcExporterModule;

    @KoraApp
    public interface Application extends
            HoconConfigModule,
            OpentelemetryGrpcExporterModule {

        static void main(String[] args) {
            KoraApplication.run(ApplicationGraph::graph);
        }
    }
    ```

=== "Kotlin"
    ```kotlin
    import io.koraframework.application.graph.KoraApplication
    import io.koraframework.common.annotation.KoraApp
    import io.koraframework.config.hocon.HoconConfigModule
    import io.koraframework.opentelemetry.tracing.exporter.grpc.OpentelemetryGrpcExporterModule

    @KoraApp
    interface Application : HoconConfigModule, OpentelemetryGrpcExporterModule

    fun main() {
        KoraApplication.run { ApplicationGraph.graph() }
    }
    ```

For OTLP/HTTP swap in `OpentelemetryHttpExporterModule` from
`io.koraframework.opentelemetry.tracing.exporter.http`. **Extend exactly one of them.** They are not
complementary: each declares its own `SpanExporter` and `SpanProcessor`, and each declares an
exporter-config method with the same name and the same erased signature but a different return type,
so inheriting both is a conflict rather than a merge.

### 2.3 Configure

```hocon
tracing {
  exporter {
    endpoint = ${OTLP_ENDPOINT}    # http://collector:4317 for gRPC
  }
  attributes {
    "service.name" = "order-service"
    "service.namespace" = "kora"
  }
}
```

`endpoint` is `@Nullable` with no default. Leaving it unset is **not** an error and **not** a
warning: `spanExporter(...)` returns `SpanExporter.composite()` and `spanProcessor(...)` returns
`SpanProcessor.composite()`, so spans are still created and sampled but nothing ever leaves the
process. That is the single most common cause of "tracing is enabled and I see nothing".

`opentelemetryTracingResource(...)` builds the OTLP resource from exactly two sources: every
`OpentelemetryTracingAttributesProvider` component, then `tracing.attributes` — applied last, so
**config wins** on a key conflict. Kora adds nothing on its own, so `"service.name"` must come from
one of them; every migrated example and guide sets it in `tracing.attributes`.

Full key set, defaults and per-backend wiring:
[references/exporter-setup-reference.md](references/exporter-setup-reference.md).

### 2.4 Attributes computed at startup

`OpentelemetryTracingAttributesProvider` (`io.koraframework.opentelemetry.tracing`) has one method,
`Map<String, String> attributes()`. Register any number as components; their attributes land on the
`Resource` and therefore on every exported span. Each is called once, while the graph builds the
`Resource`.

=== "Java"
    ```java
    import io.koraframework.common.annotation.Component;
    import io.koraframework.opentelemetry.tracing.OpentelemetryTracingAttributesProvider;

    import java.util.Map;

    @Component
    public final class InstanceTracingAttributesProvider implements OpentelemetryTracingAttributesProvider {

        @Override
        public Map<String, String> attributes() {
            return Map.of("service.instance.id", System.getenv().getOrDefault("HOSTNAME", "unknown"));
        }
    }
    ```

=== "Kotlin"
    ```kotlin
    import io.koraframework.common.annotation.Component
    import io.koraframework.opentelemetry.tracing.OpentelemetryTracingAttributesProvider

    @Component
    class InstanceTracingAttributesProvider : OpentelemetryTracingAttributesProvider {

        override fun attributes(): Map<String, String> =
            mapOf("service.instance.id" to (System.getenv("HOSTNAME") ?: "unknown"))
    }
    ```

A key that is also in `tracing.attributes` keeps the config value — the provider cannot override
static configuration.

---

## 3. Where framework spans come from

Every telemetry-carrying module resolves an **optional** `Tracer` from the graph and checks its own
`telemetry.tracing.enabled`. Both must hold:

```java
var traceEnabled = this.tracer != null && config.tracing().enabled();   // DefaultHttpServerTelemetryFactory
```

So a component emits spans when (a) `opentelemetry-tracing` is on the classpath and its module is on
the graph, and (b) its section does not disable tracing. Config roots, verified in the module
factories:

| Component | Section |
|---|---|
| Public HTTP server | `httpServer.telemetry.tracing` |
| System HTTP server | `httpServer.system.telemetry.tracing` — **`enabled` defaults to `false`** |
| HTTP clients | `httpClient.<name>.telemetry.tracing` |
| JDBC | `jdbc.telemetry.tracing` |
| Cassandra | `cassandra.telemetry.tracing` |
| gRPC server | `grpcServer.telemetry.tracing` |
| gRPC client | `grpcClient.<ServiceSimpleName>.telemetry.tracing` |

`TelemetryConfig.TracingConfig` offers exactly two keys — `enabled` (default `true`) and
`attributes` (a `Map<String,String>` merged onto that module's spans, default empty). The HTTP
server adds one more, `tracePathFull` (default `true`), which controls the `url.path` attribute.

The HTTP server names its span `"<METHOD> <pathTemplate>"` with `SpanKind.SERVER` and tags it with
typed semantic-convention keys (`HttpAttributes.HTTP_ROUTE`, `UrlAttributes.URL_SCHEME`,
`ServerAttributes.SERVER_ADDRESS`, …). It creates **no span for an unrouted request** —
`request.pathTemplate()` is `null` on a 404, so an unmatched URL produces nothing.

---

## 4. Custom spans

Inject **`KoraTracer`** (`io.koraframework.opentelemetry.tracing.KoraTracer`, supplied as a
`@DefaultComponent` by `OpentelemetryTracingModule`). It starts the span, binds it into the
`ScopedValue` for the duration of the callback, sets `StatusCode.OK`, records and rethrows on
failure, and ends the span — so there is no lifecycle to get wrong.

=== "Java"
    ```java
    import io.koraframework.common.annotation.Component;
    import io.koraframework.opentelemetry.tracing.KoraTracer;

    @Component
    public final class OrderService {

        private final KoraTracer tracer;

        public OrderService(KoraTracer tracer) {
            this.tracer = tracer;
        }

        public Order processOrder(Order order) {
            return tracer.traceParent("order.process", span -> {
                span.setAttribute("order.id", order.id());
                return doProcess(order);
            });
        }
    }
    ```

=== "Kotlin"
    ```kotlin
    import io.koraframework.common.annotation.Component
    import io.koraframework.opentelemetry.tracing.KoraTracer

    @Component
    class OrderService(private val tracer: KoraTracer) {

        fun processOrder(order: Order): Order =
            tracer.traceParent("order.process", KoraTracer.TraceCallable<Order, RuntimeException> { span ->
                span.setAttribute("order.id", order.id)
                doProcess(order)
            })
    }
    ```

    Kotlin needs the explicit SAM constructor: `traceParent` is overloaded on
    `TraceCallable`/`TraceRunnable` and a bare lambda does not pick one — the same shape as
    `JdbcExecutor.SqlSupplier { … }` in the migrated examples.

`traceParent(name, …)` nests under whatever span is current; `traceNew(name, …)` starts a detached
root trace. Both come in a value-returning (`TraceCallable`) and a void (`TraceRunnable`) form, and
both hand you the `Span` so you can add attributes and events.

`KoraTracer` cannot customise the `SpanBuilder` — the `Consumer<SpanBuilder>` overloads are private
— so `SpanKind`, links and an explicit parent need the raw `Tracer` plus a `ScopedValue` binding.
That pattern, plus reading the current span, propagating to another thread, and W3C header
propagation, is in [references/spans-and-context-reference.md](references/spans-and-context-reference.md).

**Never call `span.makeCurrent()` or `Context.makeCurrent()`.** Kora's `ContextStorage`
implementation throws `IllegalStateException` from `attach(...)` because a `ScopedValue` cannot be
imperatively attached. The standard OpenTelemetry `try (var scope = span.makeCurrent())` idiom is a
runtime failure in Kora 2.0.

---

## 5. Key types

| Type | Package / artifact | Role |
|---|---|---|
| `OpentelemetryTracingModule` | `io.koraframework.opentelemetry.tracing` · `opentelemetry-tracing` | Supplies `TracerProvider`, `Tracer`, `KoraTracer`, `Sampler`, `IdGenerator`, `Resource` — all `@DefaultComponent`. No export on its own |
| `OpentelemetryTracingAttributesProvider` | `io.koraframework.opentelemetry.tracing` | Component type; `attributes()` merged into the `Resource`, `tracing.attributes` wins on conflict |
| `OpentelemetryGrpcExporterModule` | `io.koraframework.opentelemetry.tracing.exporter.grpc` · `opentelemetry-tracing-exporter-grpc` | Adds an OTLP/gRPC `SpanExporter` + `BatchSpanProcessor` |
| `OpentelemetryHttpExporterModule` | `io.koraframework.opentelemetry.tracing.exporter.http` · `opentelemetry-tracing-exporter-http` | Adds an OTLP/HTTP `SpanExporter` + `BatchSpanProcessor` |
| `KoraTracer` | `io.koraframework.opentelemetry.tracing` | `traceParent` / `traceNew` span wrappers, `@DefaultComponent` |
| `Tracer`, `Span`, `SpanKind`, `StatusCode` | `io.opentelemetry.api.trace` | OpenTelemetry API, injected/used directly |
| `Sampler` | `io.opentelemetry.sdk.trace.samplers` | `@DefaultComponent`, overridable on `@KoraApp` |
| `OpentelemetryContext` | `io.koraframework.common.telemetry` · `common` | `implements io.opentelemetry.context.Context`; holds `ScopedValue<Context> VALUE` — the carrier |
| `Context` | **`io.opentelemetry.context`** | The OpenTelemetry context. There is no Kora `Context` in 2.0 |
| `Observation` | `io.koraframework.common.telemetry` | Framework observation bound alongside the span (`HttpServerObservation` and friends extend it) |

---

## 6. Backends

Kora 2.0 ships OTLP exporters and nothing else — there is no Jaeger-native and no Zipkin exporter
module. Anything you export to must accept OTLP, directly or through an OpenTelemetry Collector.

| Backend | How | Endpoint |
|---|---|---|
| OpenTelemetry Collector | native OTLP; the neutral choice, fans out to anything | `http://otel:4317` (gRPC) / `http://otel:4318/v1/traces` (HTTP) |
| Jaeger | native OTLP ingest, `COLLECTOR_OTLP_ENABLED=true` | `http://jaeger:4317` / `http://jaeger:4318/v1/traces` |
| Grafana Tempo | native OTLP ingest | `http://tempo:4317` / `http://tempo:4318/v1/traces` |
| Zipkin | **no OTLP ingest** — put a Collector in front with a `zipkin` exporter | Collector's OTLP port, never `:9411/api/v2/spans` |

The OTLP/HTTP endpoint includes the signal path `/v1/traces`; the OTLP/gRPC endpoint does not.

---

## 7. Common pitfalls

| Symptom | Cause / fix |
|---|---|
| App is up, `tracing.enabled` untouched, no spans anywhere | `tracing.exporter.endpoint` unset → the exporter and processor degrade to no-ops silently |
| Probe / metrics traffic produces no spans | Correct: `httpServer.system` overrides `tracing.enabled` to `false` |
| Spans arrive with no service name | `service.name` neither in `tracing.attributes` nor returned by an `OpentelemetryTracingAttributesProvider` — Kora adds no resource attribute itself |
| A provider's resource attribute is ignored | The same key is set in `tracing.attributes` — config is applied last and wins |
| `IllegalStateException` from `attach` | `span.makeCurrent()` / `Context.makeCurrent()` — unsupported, use `KoraTracer` or `ScopedValue.where(OpentelemetryContext.VALUE, …)` |
| Code will not compile: no `Context.current()` / `Context.fork()` / `OpentelemetryContext.get(ctx)` | Kora 1.x API. `Context` is removed; the only `Context` is `io.opentelemetry.context.Context` |
| Span is its own root trace | Started outside the `ScopedValue` binding, or `traceNew` used where `traceParent` was meant |
| Kotlin: "none of the following functions can be called with the arguments supplied" on `traceParent` | Overload does not infer — use `KoraTracer.TraceCallable<T, E> { … }` / `TraceRunnable<E> { … }` |
| `@KoraApp` extends both exporter modules | Not a supported combination — the two `SpanExporter`/`SpanProcessor` declarations and the identically-erased config methods collide. Keep one |
| Nothing exported to `:4318` with the gRPC module (or `:4317` with the HTTP one) | Protocol comes from the artifact; swap the module, not a config key |
| `tracing.sampler { … }` ignored | No such key. Sampling is code — override `opentelemetryTracingSampler()` |
| `tracing.exporter.retry { … }` ignored | The key is `retryPolicy`, not `retry` |

---

## 8. References

| Topic | File |
|---|---|
| Exporter modules, every `tracing.*` key with its default, resource attributes and `OpentelemetryTracingAttributesProvider`, retry policy, backends, troubleshooting | [references/exporter-setup-reference.md](references/exporter-setup-reference.md) |
| `KoraTracer`, raw `Tracer` + `ScopedValue`, span kinds and semconv attributes, reading the current span, cross-thread and W3C propagation, sampler override | [references/spans-and-context-reference.md](references/spans-and-context-reference.md) |

## 9. Assets

| File | Purpose |
|---|---|
| [`assets/Application.tracing.java.template`](assets/Application.tracing.java.template) | `@KoraApp` with the OTLP/gRPC exporter (Java) |
| [`assets/Application.tracing.kt.template`](assets/Application.tracing.kt.template) | `@KoraApp` with the OTLP/gRPC exporter (Kotlin) |
| [`assets/build.gradle.tracing.template`](assets/build.gradle.tracing.template) | Gradle dependency snippet (BOM + processor + exporter) |
| [`assets/application.tracing.conf.template`](assets/application.tracing.conf.template) | HOCON `tracing` block with real keys and defaults |
| [`assets/AppTracingAttributesProvider.java.template`](assets/AppTracingAttributesProvider.java.template) | `OpentelemetryTracingAttributesProvider` with startup-computed resource attributes (Java) |
| [`assets/AppTracingAttributesProvider.kt.template`](assets/AppTracingAttributesProvider.kt.template) | `OpentelemetryTracingAttributesProvider` with startup-computed resource attributes (Kotlin) |
| [`assets/TracingService.java.template`](assets/TracingService.java.template) | Raw-`Tracer` span wrapper with `SpanKind` support (Java) |
| [`assets/TracingService.kt.template`](assets/TracingService.kt.template) | Raw-`Tracer` span wrapper with `SpanKind` support (Kotlin) |

## 10. Not covered here

- Metrics (Micrometer / Prometheus) — `kora-telemetry-metrics`.
- Structured logging and Logback — `kora-telemetry-logging`. Trace correlation is automatic:
  `KoraAsyncAppender` captures `Span.current().getSpanContext()`; the text encoder prints
  `traceId=… spanId=…` and the JSON encoder writes `traceId` / `spanId` fields whenever the span
  context is valid.
- Liveness / readiness probes and the system server layout — `kora-http-server`.
- Per-component telemetry sections beyond `telemetry.tracing.*` — the owning module's skill.
