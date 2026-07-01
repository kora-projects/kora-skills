---
name: kora-telemetry-tracing
description: "Kora OpenTelemetry distributed tracing — OTLP exporter modules (OpentelemetryGrpcExporterModule / OpentelemetryHttpExporterModule), tracing.exporter config, Tracer injection, manual spans, and OpentelemetryContext propagation tied to the Kora request Context. Use when adding the ru.tinkoff.kora:opentelemetry-tracing-exporter-grpc or -http artifact, configuring an OTLP endpoint to Jaeger/Zipkin/Tempo, creating manual spans around business operations, propagating trace context across async/coroutine boundaries, or overriding the default Sampler in a @KoraApp."
---

# Kora Telemetry Tracing

Kora collects traces in the OpenTelemetry standard and exports them in OTLP format. The framework already emits baseline spans for supported modules (HTTP server/client, database, Kafka, gRPC); you add an exporter module, point it at a collector, and optionally create manual spans for business steps the framework cannot infer.

Read this when:
- adding an OTLP exporter (`OpentelemetryGrpcExporterModule` or `OpentelemetryHttpExporterModule`),
- configuring `tracing.exporter` toward Jaeger, Zipkin, or Grafana Tempo,
- creating manual spans with the injected `Tracer` and correct parent context,
- propagating `OpentelemetryContext` across async / coroutine boundaries,
- overriding the default `Sampler`.

## Quick Start

### 1. Dependency

The example repo pins the BOM via `kora-parent`; all Kora artifacts inherit that version, so never version a `ru.tinkoff.kora:*` artifact yourself.

=== "Java"
    ```groovy
    dependencies {
        koraBom platform("ru.tinkoff.kora:kora-parent:1.2.17")
        annotationProcessor "ru.tinkoff.kora:annotation-processors"

        // OTLP over gRPC (recommended)
        implementation "ru.tinkoff.kora:opentelemetry-tracing-exporter-grpc"
        // Alternative: OTLP over HTTP
        // implementation "ru.tinkoff.kora:opentelemetry-tracing-exporter-http"
    }
    ```

=== "Kotlin"
    ```groovy
    dependencies {
        koraBom platform("ru.tinkoff.kora:kora-parent:1.2.17")
        ksp "ru.tinkoff.kora:symbol-processors"

        implementation("ru.tinkoff.kora:opentelemetry-tracing-exporter-grpc")
        // implementation("ru.tinkoff.kora:opentelemetry-tracing-exporter-http")
    }
    ```

The OpenTelemetry API (`io.opentelemetry.api.trace.Tracer`, `Span`, `StatusCode`) is a transitive dependency of the exporter module — you do not add `io.opentelemetry:opentelemetry-api` separately.

### 2. Connect the module

=== "Java"
    ```java
    import ru.tinkoff.kora.common.KoraApp;
    import ru.tinkoff.kora.application.graph.KoraApplication;
    import ru.tinkoff.kora.config.hocon.HoconConfigModule;
    import ru.tinkoff.kora.opentelemetry.tracing.exporter.grpc.OpentelemetryGrpcExporterModule;

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
    import ru.tinkoff.kora.common.KoraApp
    import ru.tinkoff.kora.application.graph.KoraApplication
    import ru.tinkoff.kora.config.hocon.HoconConfigModule
    import ru.tinkoff.kora.opentelemetry.tracing.exporter.grpc.OpentelemetryGrpcExporterModule

    @KoraApp
    interface Application : HoconConfigModule, OpentelemetryGrpcExporterModule
    ```

For the HTTP exporter swap in `OpentelemetryHttpExporterModule` from package `ru.tinkoff.kora.opentelemetry.tracing.exporter.http`.

### 3. Configure the exporter

`endpoint` is the only required field. Attributes under `tracing.attributes` are attached to every span; `service.name` is how the service is found in the trace UI.

```hocon
tracing {
  exporter {
    endpoint = "http://localhost:4317"
  }
  attributes {
    "service.name" = "my-service"
    "service.namespace" = "kora"
  }
}
```

Externalize the endpoint per environment:

```hocon
tracing {
  exporter {
    endpoint = ${OTLP_ENDPOINT}
  }
}
```

### 4. Manual span

Manual spans wrap business steps. Read the current Kora `Context`, take the `OpentelemetryContext` out of it, parent the new span on it, register the span back into the context, and restore the previous context in `finally`.

=== "Java"
    ```java
    import io.opentelemetry.api.trace.StatusCode;
    import io.opentelemetry.api.trace.Tracer;
    import ru.tinkoff.kora.common.Component;
    import ru.tinkoff.kora.common.Context;
    import ru.tinkoff.kora.opentelemetry.common.OpentelemetryContext;

    @Component
    public final class OrderService {

        private final Tracer tracer;

        public OrderService(Tracer tracer) {
            this.tracer = tracer;
        }

        public Order processOrder(Order order) {
            var ctx = Context.current();
            var otctx = OpentelemetryContext.get(ctx);
            var span = tracer.spanBuilder("order.process")
                    .setParent(otctx.getContext())
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
    }
    ```

=== "Kotlin"
    ```kotlin
    import io.opentelemetry.api.trace.StatusCode
    import io.opentelemetry.api.trace.Tracer
    import ru.tinkoff.kora.common.Component
    import ru.tinkoff.kora.common.Context
    import ru.tinkoff.kora.opentelemetry.common.OpentelemetryContext

    @Component
    class OrderService(private val tracer: Tracer) {

        fun processOrder(order: Order): Order {
            val ctx = Context.current()
            val otctx = OpentelemetryContext.get(ctx)
            val span = tracer.spanBuilder("order.process")
                .setParent(otctx.context)
                .startSpan()

            OpentelemetryContext.set(ctx, otctx.add(span))
            try {
                val result = doProcess(order)
                span.setStatus(StatusCode.OK)
                return result
            } catch (e: RuntimeException) {
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

## Key types

| Type | Package | Role |
|------|---------|------|
| `OpentelemetryGrpcExporterModule` | `ru.tinkoff.kora.opentelemetry.tracing.exporter.grpc` | OTLP over gRPC |
| `OpentelemetryHttpExporterModule` | `ru.tinkoff.kora.opentelemetry.tracing.exporter.http` | OTLP over HTTP |
| `Tracer` | `io.opentelemetry.api.trace` | Span factory, injected from the graph |
| `Span` / `StatusCode` | `io.opentelemetry.api.trace` | A measured step and its status |
| `Context` | `ru.tinkoff.kora.common` | Kora request context (use `Context.current()`, `.fork()`) |
| `OpentelemetryContext` | `ru.tinkoff.kora.opentelemetry.common` | Bridge between Kora `Context` and OpenTelemetry context |

`OpentelemetryContext` static accessors for the current request: `OpentelemetryContext.getSpan()` and `OpentelemetryContext.getTraceId()`.

## References

| Topic | File |
|-------|------|
| Exporter modules, OTLP config keys, Jaeger/Zipkin/Tempo backends | [references/exporter-setup-reference.md](references/exporter-setup-reference.md) |
| Manual spans, attributes, async/coroutine propagation, sampler override | [references/spans-and-context-reference.md](references/spans-and-context-reference.md) |

## Assets

Templates in `assets/` (see [assets/README.md](assets/README.md)):

| File | Purpose |
|------|---------|
| `Application.tracing.java.template` | `@KoraApp` with the gRPC exporter (Java) |
| `Application.tracing.kt.template` | `@KoraApp` with the gRPC exporter (Kotlin) |
| `build.gradle.tracing.template` | Gradle dependency snippet (BOM + processor) |
| `application.tracing.conf.template` | HOCON `tracing` block |
| `TracingService.java.template` | Reusable manual-span wrapper (Java) |
| `TracingService.kt.template` | Reusable manual-span wrapper (Kotlin) |

## Backends

| Backend | Module | Endpoint example | Notes |
|---------|--------|------------------|-------|
| Jaeger | gRPC | `http://jaeger:4317` | enable `COLLECTOR_OTLP_ENABLED` |
| Jaeger | HTTP | `http://jaeger:4318/v1/traces` | OTLP HTTP path |
| Zipkin | HTTP | `http://zipkin:9411/api/v2/spans` | set `compression = "none"` |
| Grafana Tempo | gRPC | `http://tempo:4317` | set `compression = "none"` |

## Common pitfalls

| Symptom | Cause / fix |
|---------|-------------|
| Span shows as a separate trace | Missing parent — `setParent(otctx.getContext())` and restore context in `finally` |
| No traces in the backend | Wrong `endpoint` or port; gRPC is 4317, OTLP HTTP is 4318 |
| Spans never appear / leak | `span.end()` missing — always end in `finally` |
| Lost context in async code | `fork()` the Kora `Context` before the async hop and `OpentelemetryContext.set` inside it (see references) |
| Service absent in the UI | `tracing.attributes."service.name"` not set |
| Tried `tracing.sampler { ... }` | Sampling is not a config key — override `opentelemetryTracingSampler()` in `@KoraApp` (see references) |

## What this skill does NOT cover

- Metrics (Micrometer/Prometheus) — see `kora-telemetry-metrics`.
- Structured logging / Logback — see `kora-telemetry-logging`.
- Per-module telemetry toggles (e.g. `httpServer.telemetry.*`) live in the respective communication modules.
