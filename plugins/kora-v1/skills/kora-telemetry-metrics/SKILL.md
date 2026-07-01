---
name: kora-telemetry-metrics
description: "Kora Micrometer metrics via the micrometer-module — MetricsModule wires a PrometheusMeterRegistry and a MeterRegistry into the graph for custom Counter/Gauge/Timer/DistributionSummary, exposed in Prometheus format on the private HTTP port (privateApiHttpMetricsPath). Covers MetricsConfig (metrics.opentelemetrySpec V120/V123), per-module telemetry.metrics.slo buckets, PrometheusMeterRegistryInitializer for common tags, and tag-cardinality safety. Use when adding business metrics, configuring the /metrics scrape endpoint, tuning latency buckets, or debugging missing/high-cardinality metrics."
---

# Kora Telemetry Metrics

Kora collects metrics with [Micrometer](https://docs.micrometer.io/micrometer/reference/concepts.html). Adding `MetricsModule` registers a `PrometheusMeterRegistry`, instruments every Kora module (HTTP, gRPC, JDBC, Kafka, cache, JVM), and publishes a `MeterRegistry` component you inject to record custom business metrics. Metrics are served in Prometheus text format on the **private** HTTP port — never the public one.

---

## Quick Start

### 1. Add the dependency

The `micrometer-module` already brings the `PrometheusMeterRegistry`; no separate registry artifact is needed. All `ru.tinkoff.kora:*` versions come from the `kora-parent` BOM — never pin them individually.

===! ":fontawesome-brands-java: `Java`"

    ```groovy
    dependencies {
        koraBom platform("ru.tinkoff.kora:kora-parent:1.2.17")
        annotationProcessor "ru.tinkoff.kora:annotation-processors"

        implementation "ru.tinkoff.kora:micrometer-module"
        implementation "ru.tinkoff.kora:http-server-undertow"
        implementation "ru.tinkoff.kora:config-hocon"
        implementation "ru.tinkoff.kora:logging-logback"
    }
    ```

=== ":simple-kotlin: `Kotlin`"

    ```kotlin
    dependencies {
        koraBom(platform("ru.tinkoff.kora:kora-parent:1.2.17"))
        ksp("ru.tinkoff.kora:symbol-processors")

        implementation("ru.tinkoff.kora:micrometer-module")
        implementation("ru.tinkoff.kora:http-server-undertow")
        implementation("ru.tinkoff.kora:config-hocon")
        implementation("ru.tinkoff.kora:logging-logback")
    }
    ```

### 2. Add `MetricsModule` to the graph

===! ":fontawesome-brands-java: `Java`"

    ```java
    import ru.tinkoff.kora.application.graph.KoraApplication;
    import ru.tinkoff.kora.common.KoraApp;
    import ru.tinkoff.kora.config.hocon.HoconConfigModule;
    import ru.tinkoff.kora.http.server.undertow.UndertowHttpServerModule;
    import ru.tinkoff.kora.logging.logback.LogbackModule;
    import ru.tinkoff.kora.micrometer.module.MetricsModule;

    @KoraApp
    public interface Application extends
            HoconConfigModule,
            LogbackModule,
            MetricsModule,
            UndertowHttpServerModule {

        static void main(String[] args) {
            KoraApplication.run(ApplicationGraph::graph);
        }
    }
    ```

=== ":simple-kotlin: `Kotlin`"

    ```kotlin
    import ru.tinkoff.kora.common.KoraApp
    import ru.tinkoff.kora.config.hocon.HoconConfigModule
    import ru.tinkoff.kora.http.server.undertow.UndertowHttpServerModule
    import ru.tinkoff.kora.logging.logback.LogbackModule
    import ru.tinkoff.kora.micrometer.module.MetricsModule

    @KoraApp
    interface Application :
        HoconConfigModule,
        LogbackModule,
        MetricsModule,
        UndertowHttpServerModule
    ```

### 3. Expose the scrape endpoint on the private port

```hocon
httpServer {
  publicApiHttpPort = 8080   # business traffic
  privateApiHttpPort = 8085  # metrics, probes, admin
  privateApiHttpMetricsPath = "/metrics"
}

metrics {
  opentelemetrySpec = "V120"  # or "V123"
}
```

Scrape and verify:

```bash
curl http://localhost:8085/metrics
```

### 4. Record a custom metric

Inject `MeterRegistry` through the constructor (it is a normal graph component) and register meters once.

```java
import io.micrometer.core.instrument.Counter;
import io.micrometer.core.instrument.MeterRegistry;
import io.micrometer.core.instrument.Timer;
import ru.tinkoff.kora.common.Component;

import java.time.Duration;

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

    public void createUser(Runnable work) {
        userCreationTimer.record(work);
        userCreationCounter.increment();
    }
}
```

---

## What's in `references/` and `assets/`

| File | Purpose |
|------|---------|
| [references/micrometer-types-reference.md](references/micrometer-types-reference.md) | Choosing Counter / Gauge / Timer / DistributionSummary, builder APIs |
| [references/custom-metrics-reference.md](references/custom-metrics-reference.md) | Business-metric patterns, dynamic-tag caching, full payment example |
| [references/metrics-config-reference.md](references/metrics-config-reference.md) | `metrics.opentelemetrySpec`, `PrometheusMeterRegistryInitializer`, per-module `telemetry.metrics` |
| [references/metrics-cardinality-reference.md](references/metrics-cardinality-reference.md) | Good vs bad tags, memory-leak prevention, cardinality checklist |
| [references/metrics-export-reference.md](references/metrics-export-reference.md) | Prometheus pull model, scrape config, verification |
| [references/metrics-reference.md](references/metrics-reference.md) | Catalogue of built-in Kora metrics with real OpenTelemetry tag names |
| [assets/](assets/README.md) | Application, config, service, and monitoring templates |

---

## Metric Types

| Type | Use Case | Example |
|------|----------|---------|
| **Counter** | Monotonically increasing event count | `Counter.builder("requests.total").register(registry).increment()` |
| **Gauge** | Current point-in-time value | `Gauge.builder("queue.size", queue, Queue::size).register(registry)` |
| **Timer** | Duration / latency | `Timer.builder("request.duration").register(registry).record(() -> {...})` |
| **DistributionSummary** | Distribution of arbitrary values (sizes) | `summary.record(payloadBytes)` |

See [Micrometer Types Reference](references/micrometer-types-reference.md).

---

## Common tags for all metrics

To stamp every metric with shared labels, add a `PrometheusMeterRegistryInitializer` as a `default` method in a `@Module`. It is a `Function<PrometheusMeterRegistry, PrometheusMeterRegistry>`, so it **must return the registry**. It is applied exactly once at application start.

===! ":fontawesome-brands-java: `Java`"

    ```java
    import ru.tinkoff.kora.common.Module;
    import ru.tinkoff.kora.micrometer.module.PrometheusMeterRegistryInitializer;

    @Module
    public interface MetricsConfigModule {
        default PrometheusMeterRegistryInitializer commonTagsInit() {
            return registry -> {
                registry.config().commonTags("service", "order-service", "environment", "production");
                return registry;
            };
        }
    }
    ```

=== ":simple-kotlin: `Kotlin`"

    ```kotlin
    import ru.tinkoff.kora.common.Module
    import ru.tinkoff.kora.micrometer.module.PrometheusMeterRegistryInitializer

    @Module
    interface MetricsConfigModule {
        fun commonTagsInit(): PrometheusMeterRegistryInitializer {
            return PrometheusMeterRegistryInitializer { registry ->
                registry.config().commonTags("service", "order-service", "environment", "production")
                registry
            }
        }
    }
    ```

---

## Histogram buckets (SLO targets)

Bucketed measurements let monitoring compute "how many calls were under 100 ms?" and percentile estimates. Configure them with `serviceLevelObjectives(...)` on the builder; the values are your business latency targets, not universal defaults.

```java
Timer.builder("api.request.duration")
    .serviceLevelObjectives(
        Duration.ofMillis(50),
        Duration.ofMillis(100),
        Duration.ofMillis(250),
        Duration.ofMillis(500),
        Duration.ofSeconds(1))
    .register(registry);
```

Built-in Kora module metrics expose the same control through config as a millisecond array: `<module>.telemetry.metrics.slo = [ 1, 10, 50, 100, 200, 500, 1000, ... ]`. See [Metrics Config Reference](references/metrics-config-reference.md).

---

## Tag cardinality (critical)

Each unique tag-value combination creates a separate time series. Tag values must be a **bounded, finite set**, otherwise the registry grows without limit and the process leaks memory.

| Safe tags (bounded)                   | Dangerous tags (unbounded) |
|---------------------------------------|----------------------------|
| `method` (GET, POST)                  | `userId` |
| `status` (200, 404, 500)              | `requestId` (UUID per call) |
| `http.route` template (`/users/{id}`) | raw path (`/users/128734`) |
| `provider` (gmail.com, yahoo.com)     | `email` (one per user) |

For a runtime tag with a bounded value set, cache the meter per value instead of rebuilding it on every call:

```java
private final ConcurrentHashMap<String, Counter> counters = new ConcurrentHashMap<>();

private Counter counter(String provider) {
    return counters.computeIfAbsent(provider, p ->
        Counter.builder("user.creation.total")
            .tag("email.provider", p)
            .register(registry));
}
```

See [Cardinality Reference](references/metrics-cardinality-reference.md) and [Custom Metrics Reference](references/custom-metrics-reference.md).

---

## Export model — Prometheus pull only

Kora's `micrometer-module` registers a `PrometheusMeterRegistry` and serves it on `privateApiHttpMetricsPath`. The export model is **pull**: a Prometheus server scrapes the private port. There is no Kora configuration for switching the registry to a push exporter (StatsD/OTLP/etc.) — to ship to another backend, scrape the endpoint with an agent (Prometheus, OpenTelemetry Collector, vmagent) and forward from there. For distributed tracing export, use the separate tracing modules (`kora-telemetry-tracing`), which are unrelated to the metric registry.

```yaml
# prometheus.yml
scrape_configs:
  - job_name: 'order-service'
    scrape_interval: 15s
    metrics_path: '/metrics'
    static_configs:
      - targets: ['order-service:8085']
```

See [Metrics Export Reference](references/metrics-export-reference.md).

---

## Built-in Kora metrics

After `MetricsModule` is connected, Kora instruments its modules automatically using OpenTelemetry semantic-convention names and tags.

| Module | Key metric | Type |
|--------|------------|------|
| HTTP Server | `http.server.request.duration`, `http.server.active_requests` | DistributionSummary, Gauge |
| HTTP Client | `http.client.request.duration` | DistributionSummary |
| Database | `db.client.request.duration` | DistributionSummary |
| Kafka | `messaging.receive.duration`, `messaging.publish.duration`, `messaging.kafka.consumer.lag` | DistributionSummary, Gauge |
| gRPC | `rpc.server.duration`, `rpc.client.duration` | DistributionSummary |
| Cache | `cache.duration`, `cache.ratio` | DistributionSummary, Counter |
| System | `kora.up`, `jvm.memory.used`, `jvm.gc.pause`, `process.cpu.usage` | Gauge / DistributionSummary |

The full catalogue with exact tag names is in [Metrics Reference](references/metrics-reference.md).

---

## Common pitfalls

| Symptom | Fix |
|---------|-----|
| `/metrics` returns 404 | Add the HTTP server module and set `privateApiHttpMetricsPath`; scrape the **private** port |
| Metrics not appearing | Confirm `MetricsModule` is in `@KoraApp extends ...` and `MeterRegistry` is injected |
| Memory grows continuously | Unbounded tag (userId, requestId, raw URL) — drop it or map to a bounded value |
| Initializer doesn't compile | `PrometheusMeterRegistryInitializer` must `return` the registry |
| Wrong metric type | Counter/Gauge/Timer/DistributionSummary — choose based on metric semantics |
| Metrics on the public port | Always keep `/metrics` on `privateApiHttpPort` |
| Looking for `probes` module | No such module — probes are in HTTP server module (see [Probes Reference](references/probes-reference.md)) |

---

## Verification

After build (annotation processors generate `ApplicationGraph`), run the service and:

```bash
curl -s http://localhost:8085/metrics | grep kora_up
```

`kora_up 1.0` confirms the framework is running and the registry is exposed.
