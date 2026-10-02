---
name: kora-telemetry-metrics
description: "Kora 2.0 Micrometer metrics — io.koraframework:micrometer-module, MetricsModule (io.koraframework.micrometer.module), PrometheusMeterRegistry + injectable MeterRegistry, PrometheusMeterRegistryInitializer, MetricsTagsProvider, MetricsScraper, and the /metrics endpoint served by the SYSTEM HTTP server under httpServer.system.metricsPath. Covers the global metrics { enabled, tags } section, the per-component telemetry.metrics { enabled, slo, tags } keys — where enabled defaults to FALSE in 2.0 — the second MeterRegistry gate, the real 2.0 metric names (http.server.request.duration, db.client.operation.duration, cache.operation.duration, messaging.process.duration…), custom Counter/Gauge/Timer/DistributionSummary, and tag cardinality. Use when adding business metrics, wiring Prometheus scraping, or debugging an empty or JVM-only /metrics response."
license: Apache-2.0
metadata:
  kora-version: "2.x"
---

# Kora Telemetry Metrics

> **Kora sub-skill — obey the [kora-v2 meta rules](../../SKILL.md) on every task:** **R0** ground the workspace on Kora 2.0 refs before starting (framework source at tag `2.0.0.RC2` + `kora-examples` at `migration/2.0` + Kora 2.0 docs at koraframework.io/v2, which trail the source; 1.x `kora-docs` pages are never an authority) · **R1** read this sub-skill before writing code · **R2** Kora 2.0 APIs only — no Spring/Micronaut/Quarkus, no Kora 1.x APIs, no invented annotations or config keys · **R3** journal any incorrect Kora usage. Add comments/Javadoc only if asked.

| | |
|---|---|
| **Artifact** | `io.koraframework:micrometer-module` (BOM `io.koraframework:kora-bom`, `koraVersion=2.0.0.RC2`) |
| **Module** | `MetricsModule` — `io.koraframework.micrometer.module` |
| **Registry** | `io.micrometer.core.instrument.MeterRegistry` — a `PrometheusMeterRegistry` (or `NoopMeterRegistry` when `metrics.enabled = false`), published as `Wrapped<MeterRegistry>` |
| **Extension points** | `io.koraframework.micrometer.module.MetricsTagsProvider`, `io.koraframework.micrometer.module.PrometheusMeterRegistryInitializer`, `io.koraframework.telemetry.common.MetricsScraper` |
| **Endpoint** | `GET httpServer.system.metricsPath` (default `/metrics`) on the **system** server (default port **8085**) |
| **Config shape** | global `metrics { enabled, tags }` — `io.koraframework.micrometer.module.MetricsConfig`; per component `<component>.telemetry.metrics { enabled, slo, tags }` — `io.koraframework.telemetry.common.TelemetryConfig.MetricsConfig` |
| **Micrometer** | `1.17.1`; Prometheus client `1.9.0` (both come with the module — never add a registry artifact yourself) |

---

## ⚠ In Kora 2.0 component metrics are OFF by default — and the failure is silent

`TelemetryConfig` (`telemetry/telemetry-common`) sets:

| Sub-config | `enabled()` default |
|---|---|
| `TelemetryConfig.LoggingConfig` | **`false`** |
| `TelemetryConfig.MetricsConfig` | **`false`** |
| `TelemetryConfig.TracingConfig` | `true` — **except** under `httpServer.system`, where `SystemHttpServerTracingConfig` overrides it back to `false` |

Do not confuse these per-component flags with the **global** `metrics.enabled` key
(`io.koraframework.micrometer.module.MetricsConfig`, default `true`). The global key is a kill
switch for the whole registry, not an opt-in: setting it to `true` enables no component metric.

So `http.server.request.duration`, `http.client.request.duration`, `db.client.operation.duration` and
every other component metric **do not exist** until you switch them on per component:

```hocon
httpServer            { telemetry.metrics.enabled = true }
httpServer.system     { telemetry.metrics.enabled = true }   # optional: instrument the system server itself
httpClient.petApi     { telemetry.metrics.enabled = true }
jdbc                  { telemetry.metrics.enabled = true }
```

Nothing warns you. The app starts, `GET /metrics` answers **200**, and the JVM meters
(`jvm_*`, `process_*`, `system_*`, `kora_up`) are all there — so the endpoint looks healthy while
every component metric is missing. **Any example, template or dashboard that claims to demonstrate
metrics must enable them explicitly.**

### There is a second, independent gate: a `MeterRegistry` must be in the graph

Every telemetry factory computes the flag as an **AND** of two conditions. From
`DefaultHttpServerTelemetryFactory.get(...)`:

```java
var metricEnabled = this.meterRegistry != null && config.metrics().enabled();
```

`HttpServerModule` injects it as `@Nullable MeterRegistry`, and the only thing that supplies one is
`MetricsModule`. So:

| `MetricsModule` on `@KoraApp` | `telemetry.metrics.enabled` | Result |
|---|---|---|
| no | `true` | **no metrics** — `meterRegistry == null`, the flag is inert |
| yes | `false` (default) | **no component metrics** — JVM meters only |
| no | `false` | no metrics, and `/metrics` answers `# Metric Scraper disabled` |
| **yes** | **`true`** | metrics recorded |
| yes, with global `metrics.enabled = false` | any | **nothing** — the registry is `NoopMeterRegistry`, `/metrics` answers 200 with an **empty** body |

The same `meterRegistry != null && config.metrics().enabled()` line appears in every
`Default*TelemetryFactory` (HTTP client, database, Kafka, cache, gRPC, scheduling, resilient, S3,
SOAP, JMS). Details and the full config-root table: [metrics-config-reference.md](references/metrics-config-reference.md).

---

## Changed in 2.0 — check this before porting 1.x metrics code

| Kora 1.x | Kora 2.0 |
|---|---|
| `ru.tinkoff.kora:micrometer-module` | **`io.koraframework:micrometer-module`** |
| `ru.tinkoff.kora:kora-parent` BOM | **`io.koraframework:kora-bom`** |
| `ru.tinkoff.kora.micrometer.module.MetricsModule` | **`io.koraframework.micrometer.module.MetricsModule`** |
| `ru.tinkoff.kora.common.{Component, Module}` | **`io.koraframework.common.annotation.{Component, Module}`** |
| `UndertowHttpServerModule` | **`UndertowPublicHttpServerModule`** (it already extends `UndertowSystemHttpServerModule`) |
| `httpServer.privateApiHttpPort` | **`httpServer.system.port`** (default `8085`) |
| `httpServer.privateApiHttpMetricsPath` | **`httpServer.system.metricsPath`** (default `/metrics`) |
| `httpServer.publicApiHttpPort` | **`httpServer.port`** (default `8080`) |
| `metrics { opentelemetrySpec = "V120" \| "V123" }` | **removed** — the global `metrics` section holds only `enabled` and `tags` |
| metrics/logging telemetry effectively on | **`enabled` defaults to `false`** — see above |
| `db { … }` JDBC section | **`jdbc { … }`** |
| `ru.tinkoff.kora.http.server.common.{Readiness,Liveness}Probe` with `check()`/`Result` | **`io.koraframework.common.readiness.ReadinessProbe`** / **`io.koraframework.common.liveness.LivenessProbe`** with `probe()` returning a nullable `*ProbeFailure` |

The `opentelemetrySpec` switch is gone: `grep -r opentelemetrySpec` over the 2.0 source returns
nothing. The top-level `metrics` path is read only by `MetricsModule.metricsConfig(...)`, and
`MetricsConfig` declares `enabled` and `tags`, nothing else. 2.0 emits one fixed naming scheme —
the one 1.x called `V123` — and several meter names moved on top of that. Do not carry a 1.x metric
list into a 2.0 dashboard; see [metrics-reference.md](references/metrics-reference.md).

---

## Quick start

### 1. Dependencies

`micrometer-module` already brings `PrometheusMeterRegistry`; adding
`io.micrometer:micrometer-registry-prometheus` yourself only risks a version clash. Versions come
from the BOM — never pin a `io.koraframework:*` artifact.

Java (`build.gradle`, with `koraVersion=2.0.0.RC2` in `gradle.properties`):

```groovy
repositories { mavenCentral() }

dependencies {
    koraBom platform("io.koraframework:kora-bom:$koraVersion")
    annotationProcessor "io.koraframework:annotation-processors"

    implementation "io.koraframework:micrometer-module"
    implementation "io.koraframework:http-server-undertow"
    implementation "io.koraframework:config-hocon"
    implementation "io.koraframework:logging-logback"
}
```

Kotlin (`build.gradle.kts`):

```kotlin
repositories { mavenCentral() }

dependencies {
    implementation(platform("io.koraframework:kora-bom:${property("koraVersion")}"))
    ksp("io.koraframework:symbol-processors:${property("koraVersion")}")

    implementation("io.koraframework:micrometer-module")
    implementation("io.koraframework:http-server-undertow")
    implementation("io.koraframework:config-hocon")
    implementation("io.koraframework:logging-logback")
}
```

Full build wiring (`configurations { koraBom … }`, toolchain 25): [kora-project-setup-java](../kora-project-setup-java/SKILL.md) / [kora-project-setup-kotlin](../kora-project-setup-kotlin/SKILL.md).

### 2. Put `MetricsModule` on the graph

Java:

```java
package com.example;

import io.koraframework.application.graph.KoraApplication;
import io.koraframework.common.annotation.KoraApp;
import io.koraframework.config.hocon.HoconConfigModule;
import io.koraframework.http.server.undertow.UndertowPublicHttpServerModule;
import io.koraframework.logging.logback.LogbackModule;
import io.koraframework.micrometer.module.MetricsModule;

@KoraApp
public interface Application extends
        HoconConfigModule,
        LogbackModule,
        MetricsModule,
        UndertowPublicHttpServerModule {

    static void main(String[] args) {
        KoraApplication.run(ApplicationGraph::graph);
    }
}
```

Kotlin:

```kotlin
package com.example

import io.koraframework.application.graph.KoraApplication
import io.koraframework.common.annotation.KoraApp
import io.koraframework.config.hocon.HoconConfigModule
import io.koraframework.http.server.undertow.UndertowPublicHttpServerModule
import io.koraframework.logging.logback.LogbackModule
import io.koraframework.micrometer.module.MetricsModule

@KoraApp
interface Application :
    HoconConfigModule,
    LogbackModule,
    MetricsModule,
    UndertowPublicHttpServerModule

fun main() {
    KoraApplication.run(ApplicationGraph::graph)
}
```

`UndertowPublicHttpServerModule extends UndertowSystemHttpServerModule`, so the system server —
and with it `/metrics`, `/system/liveness`, `/system/readiness` — comes along automatically.

### 3. Enable metrics and expose the endpoint

```hocon
httpServer {
  port = 8080                          # public business traffic
  system.port = 8085                   # system server: metrics + probes
  system.metricsPath = "/metrics"      # default; shown for clarity

  # WITHOUT THIS LINE no http.server.* metric is ever recorded
  telemetry.metrics.enabled = true
}
```

### 4. Record a custom metric

Inject `MeterRegistry` through the constructor and register each meter **once**.

Java:

```java
package com.example;

import io.koraframework.common.annotation.Component;
import io.micrometer.core.instrument.Counter;
import io.micrometer.core.instrument.MeterRegistry;
import io.micrometer.core.instrument.Timer;

import java.time.Duration;
import java.util.concurrent.Callable;

@Component
public final class MetricsService {

    private final Timer userCreationTimer;
    private final Counter userCreationCounter;

    public MetricsService(MeterRegistry meterRegistry) {
        this.userCreationTimer = Timer.builder("user.creation.duration")
                .description("Time taken to create users")
                .serviceLevelObjectives(
                        Duration.ofMillis(50),
                        Duration.ofMillis(100),
                        Duration.ofMillis(250),
                        Duration.ofMillis(500))
                .register(meterRegistry);
        this.userCreationCounter = Counter.builder("user.creation.total")
                .description("Total number of users created")
                .register(meterRegistry);
    }

    public <T> T recordUserCreation(Callable<T> action) throws Exception {
        var result = this.userCreationTimer.recordCallable(action);
        this.userCreationCounter.increment();
        return result;
    }
}
```

Custom meters need only `MetricsModule` — they are registered directly on the `MeterRegistry` and
are **not** gated by any `telemetry.metrics.enabled` flag. Those flags govern Kora's own component
instrumentation. The global `metrics.enabled = false` does reach them: the injected registry is then
`NoopMeterRegistry`, so your meters register and record without error and are never exported.

### 5. Verify

```bash
curl -s http://localhost:8085/metrics | head -5          # framework alive + registry bound
curl -s http://localhost:8085/metrics | grep '^kora_up'
curl -s http://localhost:8085/metrics | grep http_server_request_duration
```

A 200 alone proves nothing — see [Diagnosing an empty `/metrics`](#diagnosing-an-empty-metrics).

---

## What's in `references/` and `assets/`

| File | Purpose |
|------|---------|
| [references/metrics-config-reference.md](references/metrics-config-reference.md) | The global `metrics` section, the two per-component gates, the complete `telemetry.metrics` key set, per-component config roots, `slo` / `tags`, `MetricsTagsProvider`, custom registries |
| [references/metrics-reference.md](references/metrics-reference.md) | The 2.0 built-in metric catalogue read out of the source that emits it, with tag keys and Prometheus names |
| [references/custom-metrics-reference.md](references/custom-metrics-reference.md) | Business-metric patterns, meter caching for dynamic tags, full payment example |
| [references/micrometer-types-reference.md](references/micrometer-types-reference.md) | Counter / Gauge / Timer / DistributionSummary, builder APIs, Prometheus mapping |
| [references/metrics-cardinality-reference.md](references/metrics-cardinality-reference.md) | Bounded vs unbounded tags, the leak pattern, cardinality checklist |
| [references/metrics-export-reference.md](references/metrics-export-reference.md) | Pull-only export model, scrape config, forwarding to other backends, `MetricsScraper` |
| [references/probes-reference.md](references/probes-reference.md) | `LivenessProbe` / `ReadinessProbe` on the same system server — 2.0 API and status codes |
| `assets/` | Application, build, config, service, `MetricsTagsProvider` (`AppMetricsTagsProvider.{java,kt}.template`), Grafana and Prometheus templates (all metrics-enabled) |
| `scripts/setup-metrics.sh` | Dry-run-by-default helper that prints/appends the 2.0 dependency and config snippets |

---

## Where `/metrics` lives

`MetricsHandler` is registered by `SystemHttpServerModule`, which
`UndertowSystemHttpServerModule` binds to the config path **`httpServer.system`**:

```java
default HttpServerRequestHandler systemMetricsHttpServerRequestHandler(
        @SystemApi SystemHttpServerConfig config, ValueOf<Optional<MetricsScraper>> meterRegistry) {
    return new MetricsHandler(config, meterRegistry);
}
```

`SystemHttpServerConfig` defaults: `port() = 8085`, `metricsPath() = "/metrics"`,
`readinessPath() = "/system/readiness"`, `livenessPath() = "/system/liveness"`.

The endpoint is **never** on the public port, and there is no config key to move it there.
Keep it that way — metrics expose internal state.

A stale 1.x key such as `privateApiHttpMetricsPath` is simply an **unrecognised HOCON key**: it is
ignored without a warning, the system server falls back to `8085` + `/metrics`, and a service that
deliberately used a custom port comes up green on the wrong one.

---

## Diagnosing an empty `/metrics`

`MetricsHandler.handle` returns **200 in every case**:

```java
var registry = this.meterRegistry.get().orElse(null);
if (registry == null) {
    return HttpServerResponse.of(200, HttpBody.plaintext("# Metric Scraper disabled"));
}
return HttpServerResponse.of(200, HttpBodyOutput.of("text/plain", registry::scrape));
```

So read the **body**, not the status code:

| Body | Meaning | Fix |
|---|---|---|
| `# Metric Scraper disabled` | No `MetricsScraper` in the graph | Add `MetricsModule` to the `@KoraApp` interface |
| empty | Global `metrics.enabled = false`, or a non-Prometheus registry without its own `MetricsScraper` | Remove the kill switch / supply a `MetricsScraper` |
| `kora_up`, `jvm_*`, `process_*` only | Registry is bound, component metrics are off | Set `telemetry.metrics.enabled = true` on each component |
| `kora_up` + `http_server_*` + … | Working | — |

`MetricsModule` supplies the scraper as a `@DefaultComponent`:
`prometheusMetricsScraper(MeterRegistry)` returns `prometheus::scrape` for a
`PrometheusMeterRegistry` and a no-op writer for any other registry. `metrics.enabled = false` makes
`prometheusMeterRegistry(...)` return `NoopMeterRegistry.INSTANCE` instead of the Prometheus wrapper,
so it lands in that no-op branch too: an empty (but still 200) body, no `kora_up`, no JVM meters.

---

## Built-in metric names in 2.0

Read from the `*MetricsFactory` classes that register them. Dots become underscores in Prometheus,
and timers gain `_count` / `_sum` / `_bucket` / `_max`.

| Component | Meter | Type |
|---|---|---|
| HTTP server | `http.server.request.duration`, `http.server.active_requests` | Timer, Gauge |
| HTTP client | `http.client.request.duration` | Timer |
| Database | `db.client.operation.duration` | Timer |
| Kafka consumer | `messaging.process.duration`, `messaging.process.batch.duration`, `messaging.kafka.consumer.lag` | Timer, Timer, Gauge |
| Kafka publisher | `messaging.client.operation.duration`, `messaging.client.sent.messages` | Timer, Counter |
| gRPC | `rpc.server.call.duration`, `rpc.client.call.duration` | Timer |
| Cache | `cache.operation.duration`, `cache.requests` (tag `cache.result` = hit/miss) | Timer, Counter |
| Scheduling | `scheduling.job.duration` | Timer |
| Resilience | `resilient.circuitbreaker.*`, `resilient.retry.*`, `resilient.timeout.exhausted`, `resilient.ratelimiter.acquire`, `resilient.fallback.attempts` | Gauge, Counter |
| S3 / SOAP | `rpc.client.call.duration` (distinguished by the `rpc.system.name` tag) | Timer |
| JMS consumer | `messaging.process.duration` (`messaging.system = jms`) | Timer |
| Redis (Lettuce) | `db.client.operation.duration` (`db.system.name = redis`), `lettuce.command.firstresponse.duration` | Timer |
| Framework | `kora.up` (gauge, tag `version`) | Gauge |

Several of these were renamed relative to 1.x (`db.client.request.duration` →
`db.client.operation.duration`, `cache.duration` → `cache.operation.duration`,
`messaging.receive/publish.duration` → the `messaging.process.*` / `messaging.client.*` pair,
`s3.client.duration` → `rpc.client.call.duration`), and `rpc.*.requests_per_rpc` /
`responses_per_rpc` **do not exist in 2.0 at all**. Full tables with tag keys, plus the JVM binder
list: [metrics-reference.md](references/metrics-reference.md). 2.0.0.RC2 (#972) also renamed RC1 names:
`rpc.*.duration` → `rpc.*.call.duration` (tag `rpc.system.name`, status tag `rpc.response.status_code`
with the gRPC code name), `cache.ratio` → `cache.requests`, cache tags → `cache.origin` /
`cache.operation` / `cache.result`, resilience tags → `resilient.name` / `resilient.state` / … — fix
dashboards built on RC1.

**The HTTP server duration timer tags:** `server.name`, `server.port`, `http.request.method`,
`http.response.status_code`, `http.route`, `url.scheme`, `server.address`, `error.type`. The status
code is the code of the response actually sent, so a 5xx panel filters on
`http_response_status_code=~"5.."`; `error_type!=""` separately catches requests that ended in an
exception. `http.server.active_requests` has no status code — the request is still in flight.

---

## Configuration keys

### Global: `metrics`

`MetricsModule.metricsConfig(...)` maps the top-level `metrics` path onto
`io.koraframework.micrometer.module.MetricsConfig`:

| Key | Type | Default | Effect |
|---|---|---|---|
| `enabled` | boolean | `true` | `false` swaps the Prometheus registry for `NoopMeterRegistry` — every meter, component or custom, is discarded |
| `tags` | map<string,string> | `{}` | common tags stamped on **every** meter in the registry (JVM meters and `kora_up` included) |

```hocon
metrics {
  tags {
    "service" = "order-service"
    "deployment.environment" = ${?ENV}
  }
}
```

### Per component: `<component>.telemetry.metrics`

`TelemetryConfig.MetricsConfig` declares exactly three settings, and every component inherits them:

| Key | Type | Default |
|---|---|---|
| `enabled` | boolean | **`false`** |
| `slo` | duration array | `[1, 10, 50, 100, 200, 500, 1000, 2000, 5000, 10000, 20000, 30000, 60000, 90000]` ms (`MetricsConfig.DEFAULT_SLO`) |
| `tags` | map<string,string> | `{}` — extra static tags stamped on that component's meters |

Two components add one key each on top: `jdbc.telemetry.metrics.driverMetrics` (default **`true`**,
binds Hikari's own pool meters) and the Kafka consumer/publisher `driverMetrics` (default `false`).

Bare numbers in `slo` are **milliseconds** (`DurationConfigValueMapper` maps a `NumberValue` with
`Duration.ofMillis`); strings accept `"250ms"`, `"1s"`, `"PT1S"`.

```hocon
httpServer.telemetry.metrics {
  enabled = true
  slo = [ 5, 25, 100, 250, 500, 1000, 5000 ]
  tags { "deployment.environment" = "production" }
}
```

Config roots differ per component (`httpServer`, `httpServer.system`, `httpClient.<name>`, `jdbc`,
`cassandra`, `grpcServer`, `grpcClient.<Service>`, `scheduling.telemetry`, `resilient.telemetry`,
`lettuce`, and the annotation-chosen paths for `@KafkaListener` / `@KafkaPublisher` / `@Cache`) —
the complete table is in [metrics-config-reference.md](references/metrics-config-reference.md).

---

## Common tags on every metric

Two sources feed one global `MeterFilter.commonTags(...)`, installed by the `@DefaultComponent`
`MetricsModule.commonTagsMeterRegistryInitializer(MetricsConfig, All<MetricsTagsProvider>)`:

1. every `MetricsTagsProvider` component — for values computed at startup;
2. the static `metrics.tags` map — applied **last**, so on a key conflict **config wins**.

`MetricsTagsProvider` (`io.koraframework.micrometer.module`) has one method,
`Map<String, String> tags()`. Register any number of them as components; each is called once, during
graph initialization — a value that changes later is not picked up.

Java:

```java
package com.example;

import io.koraframework.common.annotation.Component;
import io.koraframework.micrometer.module.MetricsTagsProvider;

import java.util.Map;

@Component
public final class RegionMetricsTagsProvider implements MetricsTagsProvider {

    @Override
    public Map<String, String> tags() {
        return Map.of("region", System.getenv().getOrDefault("REGION", "unknown"));
    }
}
```

Kotlin:

```kotlin
package com.example

import io.koraframework.common.annotation.Component
import io.koraframework.micrometer.module.MetricsTagsProvider

@Component
class RegionMetricsTagsProvider : MetricsTagsProvider {

    override fun tags(): Map<String, String> =
        mapOf("region" to (System.getenv("REGION") ?: "unknown"))
}
```

Keep the values bounded — they multiply onto every series.

### `PrometheusMeterRegistryInitializer` — everything else on `registry.config()`

`PrometheusMeterRegistryWrapper.init()` applies every initializer once, in graph order, before the
JVM binders run. `PrometheusMeterRegistryInitializer extends Function<PrometheusMeterRegistry, PrometheusMeterRegistry>`,
so it **must return the registry**. Use it for meter filters, deny rules and naming conventions.

**Your own initializer runs next to the built-in common-tags one, not instead of it.** Since
2.0.0.RC2 (#935) `commonTagsMeterRegistryInitializer` is not a `@DefaultComponent`, so it stays in
`All<PrometheusMeterRegistryInitializer>` and `metrics.tags` / `MetricsTagsProvider` keep applying.
Do not re-merge the common tags in your initializer (the RC1 workaround) — that only installs the
same filter twice. [`assets/CustomMetricsConfig.java.template`](assets/CustomMetricsConfig.java.template)
/ [`.kt.template`](assets/CustomMetricsConfig.kt.template) add a deny rule only.

---

## Tag cardinality

Each unique tag-value combination is one time series. Tag values must be a **bounded, finite set**,
otherwise the registry grows without limit and the process leaks memory.

| Safe (bounded) | Dangerous (unbounded) |
|---|---|
| `http.request.method` (GET, POST) | `userId` |
| `http.route` template (`/users/{id}`) | raw path (`/users/128734`) |
| `error.type` (a finite set of exception classes) | `requestId` (UUID per call) |
| `provider` (gmail.com, yahoo.com) | `email` (one per user) |

For a runtime tag with a bounded value set, cache the meter per value instead of rebuilding it:

```java
private final ConcurrentHashMap<String, Counter> counters = new ConcurrentHashMap<>();

private Counter counter(String provider) {
    return counters.computeIfAbsent(provider, p ->
        Counter.builder("user.creation.total")
            .tag("email.provider", p)
            .register(registry));
}
```

Kora's own factories do exactly this — see the `requestDurationCache` /
`activeRequestsCache` maps in `DefaultHttpServerMetricsFactory`, guarded by the source comment
`DO NOT ADD DYNAMIC TAGS IN BUILDER, use metric key instead of metric collision will happen`.

See [metrics-cardinality-reference.md](references/metrics-cardinality-reference.md).

---

## Export model — Prometheus pull only

The registry is a `PrometheusMeterRegistry` scraped over HTTP. Kora exposes no configuration to
swap it for a push exporter (StatsD, OTLP, …). To reach another backend, scrape `/metrics` with an
agent (Prometheus, OpenTelemetry Collector, vmagent) and forward from there.

```yaml
# prometheus.yml
scrape_configs:
  - job_name: 'order-service'
    scrape_interval: 15s
    metrics_path: '/metrics'
    static_configs:
      - targets: ['order-service:8085']   # the SYSTEM port
```

Trace export is a separate concern handled by `opentelemetry-tracing-exporter-{grpc,http}` and does
not affect the meter registry — see [kora-telemetry-tracing](../kora-telemetry-tracing/SKILL.md).
For structured logs see [kora-telemetry-logging](../kora-telemetry-logging/SKILL.md).

Replacing the registry itself is possible: both `prometheusMeterRegistry` and
`prometheusMetricsScraper` are `@DefaultComponent`s, so your own `@Component` wins.
See [metrics-export-reference.md](references/metrics-export-reference.md).

---

## Common pitfalls

| Symptom | Cause | Fix |
|---|---|---|
| `/metrics` body is `# Metric Scraper disabled` | No `MetricsScraper` in the graph | Add `MetricsModule` to `@KoraApp extends …` |
| `/metrics` returns 200 but only `jvm_*` / `kora_up` | `telemetry.metrics.enabled` left at its `false` default | Enable it per component |
| `/metrics` returns 200 with an empty body | Global `metrics.enabled = false` put `NoopMeterRegistry` in the graph | Remove it; the default is `true` |
| `metrics.tags` / `MetricsTagsProvider` tags missing from every series | On RC1 only: an app-level `PrometheusMeterRegistryInitializer` displaced the `@DefaultComponent` common-tags initializer (fixed in RC2, #935) | Upgrade to RC2+; on RC2+ check the key is not removed by your own `MeterFilter` |
| A provider's tag value is ignored | The same key is in `metrics.tags` — config wins | Drop one of them |
| Config flag set, still nothing | No `MeterRegistry` — `MetricsModule` missing | Both gates must pass |
| `/metrics` returns 404 on port 8080 | Scraping the public port | Scrape `httpServer.system.port` (default 8085) |
| `privateApiHttpMetricsPath` / `privateApiHttpPort` have no effect | Unknown 1.x keys, silently ignored | `httpServer.system.metricsPath` / `httpServer.system.port` |
| `metrics { opentelemetrySpec = … }` has no effect | The key does not exist in 2.0 | Remove it; 2.0 has one fixed naming scheme |
| `No component found for dependency: MeterRegistry` | Injecting `MeterRegistry` without `MetricsModule` | Add the module |
| `hikaricp_*` pool metrics missing | `jdbc.telemetry.metrics.enabled = false` hands Hikari a `NoopMeterRegistry` | Enable JDBC metrics; `driverMetrics` alone is not enough |
| Memory grows continuously | Unbounded tag (`userId`, `requestId`, raw URL) | Drop it or map to a bounded value |
| Initializer doesn't compile | `PrometheusMeterRegistryInitializer` must **return** the registry | `return registry;` |
| Looking for a `probes` module | There is none — probes ship with the HTTP server | [probes-reference.md](references/probes-reference.md) |

---

## Verification

```bash
# 1. registry bound + framework version
curl -s http://localhost:8085/metrics | grep '^kora_up'

# 2. component instrumentation actually on (make a request first)
curl -s http://localhost:8080/your/route > /dev/null
curl -s http://localhost:8085/metrics | grep -E '^http_server_(request_duration|active_requests)'

# 3. exact exported series name, before you hard-code it into a dashboard
curl -s http://localhost:8085/metrics | grep '^# TYPE http_server_request_duration'
```

Step 2 is the one that matters: it is the only check that distinguishes "endpoint answers" from
"metrics are being recorded".
