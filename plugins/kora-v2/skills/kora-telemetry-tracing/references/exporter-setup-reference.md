# Exporter Setup Reference

Kora 2.0 OTLP exporter modules, every configuration key with its real default, and backend wiring.

Everything here is derived from the framework source under
`telemetry/opentelemetry-tracing`, `telemetry/opentelemetry-tracing-exporter-grpc` and
`telemetry/opentelemetry-tracing-exporter-http`, and from the migrated `kora-*-telemetry` examples
and `*-guide-observability-app` guides.

## Contents

- [Modules and artifacts](#modules-and-artifacts)
- [What each module contributes](#what-each-module-contributes)
- [The `tracing` section](#the-tracing-section)
- [The `tracing.exporter` section](#the-tracingexporter-section)
- [Retry policy](#retry-policy)
- [Resource attributes](#resource-attributes)
- [Per-component tracing toggles](#per-component-tracing-toggles)
- [Backends](#backends)
- [Exporter self-metrics](#exporter-self-metrics)
- [Troubleshooting](#troubleshooting)

## Modules and artifacts

| Module interface | Artifact | Package | Protocol |
|---|---|---|---|
| `OpentelemetryTracingModule` | `io.koraframework:opentelemetry-tracing` | `io.koraframework.opentelemetry.tracing` | none — tracer only |
| `OpentelemetryGrpcExporterModule` | `io.koraframework:opentelemetry-tracing-exporter-grpc` | `io.koraframework.opentelemetry.tracing.exporter.grpc` | OTLP/gRPC |
| `OpentelemetryHttpExporterModule` | `io.koraframework:opentelemetry-tracing-exporter-http` | `io.koraframework.opentelemetry.tracing.exporter.http` | OTLP/HTTP |

Both exporter modules `extends OpentelemetryTracingModule`, so extending an exporter module gives
you the tracer as well. Extend **one** exporter module, never both.

```java
import io.koraframework.common.annotation.KoraApp;
import io.koraframework.opentelemetry.tracing.exporter.grpc.OpentelemetryGrpcExporterModule;

@KoraApp
public interface Application extends OpentelemetryGrpcExporterModule { }
```

Transport dependencies differ, which matters if you audit the dependency tree:

- **gRPC exporter** — `io.opentelemetry:opentelemetry-exporter-otlp` keeping the OkHttp sender, but
  with the transitive `com.squareup.okhttp3:okhttp-jvm` and `com.squareup.okio:okio` excluded and
  Kora's own versions (OkHttp `5.4.0`, Okio `3.18.1`) put back as `implementation`. OkHttp therefore
  lands on your runtime classpath.
- **HTTP exporter** — `io.opentelemetry:opentelemetry-exporter-otlp` with the OkHttp sender
  **excluded** and `io.opentelemetry:opentelemetry-exporter-sender-jdk` in its place, so it runs on
  the JDK HTTP client and pulls no OkHttp.

If your service must not ship OkHttp, that alone decides the exporter for you. Otherwise pick by
what the collector exposes; OTLP/gRPC is the more compact wire format.

Both are built against OpenTelemetry **1.66.0** (`gradle/libs.versions.toml`), with
`opentelemetry-semconv` 1.44.0 and `opentelemetry-semconv-incubating` 1.44.0-alpha carried by
`opentelemetry-common`.

### Using `opentelemetry-tracing` without an exporter

Legitimate and occasionally what you want. `OpentelemetryTracingModule` declares
`@Nullable SpanProcessor spanProcessor` as a dependency, so with no exporter module on the graph it
resolves to `null` and falls back to `SpanProcessor.composite()`. Real spans are still created and
sampled — which is enough for `traceId=…` to appear in Logback output — but nothing is exported.

## What each module contributes

`OpentelemetryTracingModule`:

| Component | Kind | Default |
|---|---|---|
| `OpentelemetryTracingConfig` | `@DefaultComponent` | mapped from the `tracing` path |
| `Resource` | `@DefaultComponent` | built from every `OpentelemetryTracingAttributesProvider`, then `tracing.attributes` (config wins) |
| `IdGenerator` | `@DefaultComponent` | `IdGenerator.random()` |
| `Supplier<SpanLimits>` | `@DefaultComponent` | `SpanLimits::getDefault` |
| `Sampler` | `@DefaultComponent` | `Sampler.parentBased(Sampler.alwaysOn())` |
| `LifecycleWrapper<TracerProvider>` | `@DefaultComponent` | `SdkTracerProvider`, or `TracerProvider.noop()` when `tracing.enabled = false` |
| `Tracer` | `@DefaultComponent` | `tracerBuilder("kora").build()` |
| `KoraTracer` | `@DefaultComponent` | wraps the `Tracer` |

Each exporter module adds, both as `@DefaultComponent`:

| Component | Behaviour |
|---|---|
| `SpanExporter` | `OtlpGrpcSpanExporter` / `OtlpHttpSpanExporter`, or `SpanExporter.composite()` when `endpoint` is `null` or `tracing.enabled = false` |
| `SpanProcessor` | `BatchSpanProcessor` over that exporter, or `SpanProcessor.composite()` under the same two conditions |

Because they are `@DefaultComponent`, declaring your own `SpanExporter`, `SpanProcessor`, `Sampler`,
`IdGenerator`, `Supplier<SpanLimits>`, `Resource` or `TracerProvider` on the `@KoraApp` interface
replaces the framework one. A replaced `Resource` no longer reads `tracing.attributes` or any
`OpentelemetryTracingAttributesProvider` — your factory is the whole resource.

## The `tracing` section

Mapped from `OpentelemetryTracingConfig` (`@ConfigMapper`, path `tracing`).

| Key | Type | Default | Meaning |
|---|---|---|---|
| `enabled` | boolean | **`true`** | Master switch. `false` → `TracerProvider.noop()` and both exporter components degrade to no-ops |
| `attributes` | map | `{}` | OTLP **resource** attributes attached to every span the process exports; applied after the `OpentelemetryTracingAttributesProvider` components, so these win on a key conflict |

Tracing being on by default is the opposite of the per-component `telemetry.logging.enabled` and
`telemetry.metrics.enabled`, which are both `false`. (The global `metrics.enabled` of
`MetricsModule` defaults to `true`, like `tracing.enabled`: both are kill switches.) Writing
`tracing.enabled = true` is a no-op; only `false` changes anything.

The whole `tracing` block is optional. `@ConfigMapper` defaults `mapNullAsEmptyObject` to `true`, so
an absent section is mapped as an empty object and every default applies — including `enabled = true`
with an unset `endpoint`, which is exactly the silent no-export state.

## The `tracing.exporter` section

`OpentelemetryGrpcExporterConfig` and `OpentelemetryHttpExporterConfig` are separate interfaces with
**identical key sets and identical defaults**, both mapped from `tracing.exporter`. Switching
exporters never requires touching the keys.

| Key | Type | Default | Meaning |
|---|---|---|---|
| `endpoint` | string | **none (nullable)** | OTLP endpoint. Unset → no export, silently |
| `exportTimeout` | duration | `3s` | Max time for a single export call |
| `batchExportTimeout` | duration | `30s` | Max time for one accumulated batch |
| `connectTimeout` | duration | none (nullable) | Connection establishment timeout; unset leaves the SDK default |
| `compression` | string | `"gzip"` | `gzip` or `none` |
| `scheduleDelay` | duration | `2s` | Delay between batch flushes |
| `maxExportBatchSize` | int | `512` | Spans per batch |
| `maxQueueSize` | int | `2048` | Spans buffered before drops |
| `exportUnsampledSpans` | boolean | `false` | Export spans the `Sampler` rejected |
| `retryPolicy` | object | see below | Export retry policy |

```hocon
tracing {
  exporter {
    endpoint = "http://collector:4317"
    connectTimeout = "10s"
    exportTimeout = "3s"
    batchExportTimeout = "30s"
    scheduleDelay = "2s"
    maxExportBatchSize = 512
    maxQueueSize = 2048
    compression = "gzip"
    exportUnsampledSpans = false
  }
  attributes {
    "service.name" = "order-service"
    "service.namespace" = "kora"
  }
}
```

Keys that do **not** exist — do not invent them:

- `tracing.exporter.protocol` — the protocol is the artifact you chose.
- `tracing.exporter.retry` — the key is `retryPolicy`.
- `tracing.exporter.headers` — there is no header configuration on either config interface. If the
  collector needs authentication headers, terminate it at a sidecar or gateway, or replace the
  `@DefaultComponent SpanExporter` with your own built `OtlpGrpcSpanExporter` / `OtlpHttpSpanExporter`.
- `tracing.sampler` — sampling is a component, see the
  [spans reference](spans-and-context-reference.md#sampler-override).
- `tracing.exporter.enabled` — the switch is `tracing.enabled`, and an unset `endpoint` is the
  practical off switch for export alone.

## Retry policy

Nested `@ConfigMapper` interface `RetryPolicy` under `tracing.exporter.retryPolicy`. The section is
optional; omitting it yields the defaults.

| Key | Type | Default |
|---|---|---|
| `maxAttempts` | int | `5` |
| `initialBackoff` | duration | `1s` |
| `maxBackoff` | duration | `5s` |
| `backoffMultiplier` | double | `1.5` |

```hocon
tracing.exporter.retryPolicy {
  maxAttempts = 3
  initialBackoff = "500ms"
  maxBackoff = "5s"
  backoffMultiplier = 2.0
}
```

## Resource attributes

`opentelemetryTracingResource(OpentelemetryTracingConfig, All<OpentelemetryTracingAttributesProvider>)`
starts from an empty `Resource.builder()`, puts every provider's `attributes()` on it, then puts
`config.attributes()` — last, so static configuration wins on a key conflict — and the result is
handed to `SdkTracerProvider.setResource(...)`:

```java
@DefaultComponent
default Resource opentelemetryTracingResource(OpentelemetryTracingConfig config, All<OpentelemetryTracingAttributesProvider> attributesProviders) {
    var resource = Resource.builder();
    for (var provider : attributesProviders) {
        for (var attribute : provider.attributes().entrySet()) {
            resource.put(attribute.getKey(), attribute.getValue());
        }
    }
    // config attributes are applied last so static configuration wins on key conflicts
    for (var attribute : config.attributes().entrySet()) {
        resource.put(attribute.getKey(), attribute.getValue());
    }
    return resource.build();
}
```

The resource therefore contains **exactly** those two sources — nothing is added for you, so with
no provider and an empty `tracing.attributes` your spans arrive with no service identity.

```hocon
tracing {
  attributes {
    "service.name" = ${SERVICE_NAME}
    "service.namespace" = "kora"
    "service.version" = ${?SERVICE_VERSION}
    "deployment.environment" = ${?ENV}
  }
}
```

Use OpenTelemetry resource semantic-convention names (`service.name`, `service.namespace`,
`service.version`, `service.instance.id`, `deployment.environment.name`). `service.name` is what
every trace UI groups by.

### `OpentelemetryTracingAttributesProvider`

```java
package io.koraframework.opentelemetry.tracing;

public interface OpentelemetryTracingAttributesProvider {
    Map<String, String> attributes();
}
```

For values computed at startup — the pod name, a build version read from the jar manifest, a
region from the environment. Register any number as components; all are injected through
`All<OpentelemetryTracingAttributesProvider>`, and each `attributes()` is called once, while the
graph builds the `Resource`. Templates:
[`AppTracingAttributesProvider.java.template`](../assets/AppTracingAttributesProvider.java.template) /
[`AppTracingAttributesProvider.kt.template`](../assets/AppTracingAttributesProvider.kt.template).

Do not confuse this with per-module `…telemetry.tracing.attributes`, which is a
`Map<String,String>` merged onto the **spans of that module only**, not onto the resource.

## Per-component tracing toggles

`TelemetryConfig.TracingConfig` — inherited by every module's telemetry config:

| Key | Default |
|---|---|
| `enabled` | `true` |
| `attributes` | `{}` |

Config roots, taken from the `*FactoryModule` constructor arguments in the module interfaces:

| Component | Section | Notes |
|---|---|---|
| Public HTTP server | `httpServer.telemetry.tracing` | plus `tracePathFull` (default `true`) → `url.path` attribute |
| System HTTP server | `httpServer.system.telemetry.tracing` | **`enabled` overridden to `false`** |
| Declarative HTTP client | `httpClient.<clientName>.telemetry.tracing` | `<clientName>` is the `@HttpClient` name with the first letter lower-cased, produced by `ConfigModuleGenerator` |
| JDBC | `jdbc.telemetry.tracing` | the 1.x root was `db` |
| Cassandra | `cassandra.telemetry.tracing` | |
| gRPC server | `grpcServer.telemetry.tracing` | |
| gRPC client | `grpcClient.<ServiceSimpleName>.telemetry.tracing` | from `config.get("grpcClient." + serviceSimpleName)` |

Other modules with telemetry (S3, Redis/Lettuce, Kafka, cache, scheduling, SOAP, Camunda) follow the
same `<module-section>.telemetry.tracing` shape; take the exact root from that module's own skill
rather than guessing it here.

A module emits spans only when both conditions hold — a `Tracer` exists in the graph **and** the
section's `enabled` is true. In `DefaultHttpServerTelemetryFactory`:

```java
var traceEnabled = this.tracer != null && config.tracing().enabled();
```

With no tracing module on the graph the injected `Tracer` is `null` and every component silently
falls back to a no-op tracer regardless of config.

## Backends

Kora 2.0 has **only OTLP exporters**. There is no Jaeger-native exporter module and no Zipkin
exporter module; the 1.x habit of pointing a Kora exporter at a Zipkin ingest URL does not apply.
Everything must speak OTLP, directly or behind an OpenTelemetry Collector.

Ports are the OTLP defaults: **4317** for gRPC, **4318** for HTTP, and the HTTP endpoint carries the
signal path `/v1/traces`.

### OpenTelemetry Collector (OTLP/gRPC)

The neutral choice — it re-exports to Jaeger, Tempo, Zipkin, a vendor, or several at once, and it
absorbs endpoint churn so the application config never changes. This is what the migrated
`kora-java-telemetry` / `kora-kotlin-telemetry` examples run against
(`otel/opentelemetry-collector`, port 4317).

```hocon
tracing {
  exporter { endpoint = ${OTLP_ENDPOINT} }   # http://otel:4317
  attributes { "service.name" = "order-service" }
}
```

### Jaeger (OTLP/HTTP)

Jaeger ingests OTLP directly once `COLLECTOR_OTLP_ENABLED` is on. This is the configuration in the
migrated `kora-java-guide-observability-app` / `kora-kotlin-guide-observability-app`, using
`OpentelemetryHttpExporterModule`:

```hocon
tracing {
  exporter { endpoint = "http://jaeger:4318/v1/traces" }
  attributes { "service.name" = "guide-observability-app" }
}
```

```yaml title="docker-compose.yml"
services:
  jaeger:
    image: jaegertracing/all-in-one:latest
    ports:
      - "16686:16686"   # UI
      - "4318:4318"     # OTLP HTTP
    environment:
      COLLECTOR_OTLP_ENABLED: "true"
```

Add `- "4317:4317"` and drop the `/v1/traces` path to use `OpentelemetryGrpcExporterModule` instead.

### Grafana Tempo (OTLP/gRPC)

Tempo ingests OTLP directly on its configured OTLP receiver.

```hocon
tracing {
  exporter { endpoint = "http://tempo:4317" }
  attributes { "service.name" = "order-service" }
}
```

### Zipkin — via a Collector

Zipkin's `/api/v2/spans` is the Zipkin JSON ingest, not OTLP; a Kora OTLP exporter cannot talk to
it. Export OTLP to a Collector and let the Collector's `zipkin` exporter forward:

```hocon
tracing {
  exporter { endpoint = "http://otel:4317" }
  attributes { "service.name" = "order-service" }
}
```

```yaml title="otel-collector-config.yaml"
receivers:
  otlp:
    protocols:
      grpc:
        endpoint: 0.0.0.0:4317
exporters:
  zipkin:
    endpoint: http://zipkin:9411/api/v2/spans
service:
  pipelines:
    traces:
      receivers: [otlp]
      exporters: [zipkin]
```

## Exporter self-metrics

Both exporter modules take an optional `@Nullable MeterProvider` and, when present, pass it to the
`OtlpSpanExporter` builder and to the `BatchSpanProcessor`, which then publish their own
queue/export counters. That `MeterProvider` is the `MicrometerMeterProvider` supplied by
`MetricsModule` (`io.koraframework:micrometer-module`), so adding metrics gets you exporter
instrumentation for free. Without `MetricsModule` the dependency is `null` and the exporter runs
uninstrumented — no error, no degradation of tracing itself.

## Troubleshooting

### Nothing arrives at the backend

1. **`tracing.exporter.endpoint` is unset.** Both `spanExporter(...)` and `spanProcessor(...)` start
   with `if (exporterConfig.endpoint() == null || !tracingConfig.enabled()) return …composite();`.
   No log line, no startup failure — check the resolved config first, especially if the value comes
   from `${ENV_VAR}`.
2. **Protocol/module mismatch.** gRPC module → `:4317`, no path. HTTP module → `:4318/v1/traces`.
3. **`tracing.enabled = false`** somewhere in an overriding config layer.
4. **The component you expected to trace has tracing off** — most often `httpServer.system`, whose
   default is `false`.
5. **No route matched.** The HTTP server builds a span only when `request.pathTemplate() != null`,
   so a 404 produces none.
6. Network reachability from the container to the collector.
7. Raise the exporter's own logging:
   ```hocon
   logging.levels {
     "io.koraframework.opentelemetry" = "DEBUG"
     "io.opentelemetry.exporter" = "DEBUG"
   }
   ```

### Spans arrive but the service is unnamed

Neither `tracing.attributes."service.name"` nor any `OpentelemetryTracingAttributesProvider`
supplies `service.name`. The resource is built solely from those two sources — or entirely by your
own `Resource` component, if you replaced the default one.

### Export timeouts / dropped spans under load

- Raise `exportTimeout` and `batchExportTimeout`.
- Raise `maxQueueSize`, or lower `maxExportBatchSize` so batches flush faster.
- Lower `scheduleDelay` to flush more often at the cost of more requests.
- Reduce volume with a ratio `Sampler` — see
  [spans-and-context-reference.md](spans-and-context-reference.md#sampler-override).

### Verifying export in a test

The migrated `kora-java-telemetry` example asserts on the collector container's own log rather than
on the application: it drives one HTTP request and waits for the collector to report the expected
span count. That pattern needs no trace-query API and is stable across backends.
