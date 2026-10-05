# Metrics Configuration Reference (Kora 2.0)

Everything that decides whether a metric is recorded, and where its config lives.

## Contents

- [The global `metrics` section](#global-metrics)
- [The two gates](#the-two-gates)
- [Module setup](#module-setup)
- [The complete `telemetry.metrics` key set](#key-set)
- [Per-component config roots](#config-roots)
- [`slo` — histogram buckets](#slo)
- [`tags` — extra static tags](#tags)
- [`driverMetrics` — the third-party pool/client meters](#driver-metrics)
- [The system server](#system-server)
- [Common tags: `metrics.tags`, `MetricsTagsProvider`, `PrometheusMeterRegistryInitializer`](#common-tags)
- [Replacing the registry or the scraper](#replacing-the-registry)
- [Keys that no longer exist](#removed-keys)
- [Verification](#verification)

---

## The global `metrics` section { #global-metrics }

`MetricsModule` maps the top-level `metrics` path:

```java
@DefaultComponent
default MetricsConfig metricsConfig(Config config, ConfigValueMapper<MetricsConfig> mapper) {
    return mapper.mapOrThrow(config.get("metrics"));
}
```

`io.koraframework.micrometer.module.MetricsConfig` — not to be confused with the per-component
`io.koraframework.telemetry.common.TelemetryConfig.MetricsConfig` below:

```java
@ConfigMapper
public interface MetricsConfig {
    default boolean enabled() { return true; }
    default Map<String, String> tags() { return Map.of(); }
}
```

| Key | Default | Effect |
|---|---|---|
| `metrics.enabled` | `true` | `false` makes `prometheusMeterRegistry(...)` return `NoopMeterRegistry.INSTANCE`: no `PrometheusMeterRegistryWrapper`, no JVM binders, no `kora_up`, no initializers applied, every meter discarded, and `prometheusMetricsScraper` falls to its no-op branch — `/metrics` answers **200 with an empty body** |
| `metrics.tags` | `{}` | common tags on every meter in the registry; merged with the `MetricsTagsProvider` components, config wins on a key conflict — see [common tags](#common-tags) |

`metrics.enabled` is a kill switch, not an opt-in. It never turns a component's metrics on; that is
still `<component>.telemetry.metrics.enabled` (gate 1 below), whose default is `false`.

```hocon
metrics {
  # enabled = false       # kill switch: registry becomes NoopMeterRegistry
  tags {
    "service" = "order-service"
    "deployment.environment" = ${?ENV}
  }
}
```

---

## The two gates { #the-two-gates }

With the global switch at its `true` default, a Kora component records metrics only when **both**
conditions hold.

### Gate 1 — `<component>.telemetry.metrics.enabled`, which defaults to `false`

`io.koraframework.telemetry.common.TelemetryConfig`:

```java
@ConfigMapper
interface LoggingConfig { default boolean enabled() { return false; } }

@ConfigMapper
interface TracingConfig { default boolean enabled() { return true; } … }

@ConfigMapper
interface MetricsConfig {
    Duration[] DEFAULT_SLO = { /* 1, 10, 50, 100, 200, 500, 1000, 2000, 5000, 10000, 20000, 30000, 60000, 90000 ms */ };
    default boolean enabled() { return false; }
    default Duration[] slo() { return DEFAULT_SLO; }
    default Map<String, String> tags() { return Map.of(); }
}
```

Metrics **and** logging are off; tracing is on. There is one documented exception to the tracing
default: `SystemHttpServerConfig.SystemHttpServerTelemetryConfig.SystemHttpServerTracingConfig`
overrides `enabled()` back to `false`, so the system server is not traced unless you say so.

### Gate 2 — a `MeterRegistry` must exist in the graph

Every `Default*TelemetryFactory` takes `@Nullable MeterRegistry` and computes:

```java
var metricEnabled = this.meterRegistry != null && config.metrics().enabled();
```

`HttpServerModule.defaultHttpServerTelemetryFactory(@Nullable MeterRegistry meterRegistry, …)` is
how it reaches the factory, and the only component that supplies a `MeterRegistry` is
`MetricsModule`. Without the module the parameter is `null` and the config flag is inert — no error,
no warning.

When either gate fails the factory substitutes `NoopMeterRegistry.INSTANCE`
(`io.koraframework.micrometer.common.NoopMeterRegistry`) and a `Noop*MetricsFactory`, so every
recording call still executes and silently discards its value. That is why nothing ever fails
loudly.

### Truth table

| `MetricsModule` on `@KoraApp` | `telemetry.metrics.enabled` | Component metrics | `/metrics` body |
|---|---|---|---|
| no | not set (`false`) | none | `# Metric Scraper disabled` |
| no | `true` | **none** | `# Metric Scraper disabled` |
| yes | not set (`false`) | **none** | `kora_up` + JVM meters only |
| yes | `true` | recorded | `kora_up` + JVM + component meters |
| yes, global `metrics.enabled = false` | any | discarded by `NoopMeterRegistry` | empty |

With `metrics.enabled = false` gate 2 technically passes — the injected `MeterRegistry` is
`NoopMeterRegistry`, not `null` — so component factories build their real metrics objects and
record into a registry that drops everything.

---

## Module setup { #module-setup }

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

`MetricsModule` contributes five components; all but the common-tags initializer are `@DefaultComponent` and replaceable:

| Method | Provides | Notes |
|---|---|---|
| `metricsConfig(Config, ConfigValueMapper<MetricsConfig>)` | `@DefaultComponent MetricsConfig` | the global `metrics` section |
| `prometheusMeterRegistry(MetricsConfig, All<PrometheusMeterRegistryInitializer>)` | `@Root @DefaultComponent Wrapped<MeterRegistry>` | a `PrometheusMeterRegistryWrapper`, or `NoopMeterRegistry` when `metrics.enabled = false`; `@Root` so it starts even if nothing injects it |
| `commonTagsMeterRegistryInitializer(MetricsConfig, All<MetricsTagsProvider>)` | `PrometheusMeterRegistryInitializer` (**not** `@DefaultComponent` since RC2, #935) | installs `MeterFilter.commonTags(...)` with the merged tags; an identity function when there are none. Always part of `All<PrometheusMeterRegistryInitializer>`, next to yours |
| `prometheusMetricsScraper(MeterRegistry)` | `@DefaultComponent MetricsScraper` | `prometheus::scrape` for a `PrometheusMeterRegistry`, otherwise a no-op writer |
| `micrometerMeterProvider(MeterRegistry, @Nullable CallbackRegistrar)` | `@DefaultComponent MicrometerMeterProvider` | the OpenTelemetry ↔ Micrometer bridge |

An HTTP server module is required for the scrape endpoint; `UndertowPublicHttpServerModule`
already extends `UndertowSystemHttpServerModule`, which registers it.

---

## The complete `telemetry.metrics` key set { #key-set }

`TelemetryConfig.MetricsConfig` declares exactly three settings. Every component's `*MetricsConfig`
extends it, and only two add anything.

| Key | Type | Default | Applies to |
|---|---|---|---|
| `enabled` | boolean | `false` | every component |
| `slo` | duration array | `MetricsConfig.DEFAULT_SLO` (14 buckets, 1 ms … 90 s) | every component that records a Timer |
| `tags` | map<string,string> | `{}` | every component |
| `driverMetrics` | boolean | **`true`** | `jdbc`, `cassandra` (`DatabaseMetricsConfig`) |
| `driverMetrics` | boolean | **`false`** | Kafka consumer and publisher |
| `engineMetrics` | boolean | `false` | `camunda.engine.bpmn` (experimental) |

There is **no** `histogram`, `percentiles`, `prefix`, `disabled`, `opentelemetrySpec` or
`registry` key. If a config key is not in this table, it does not exist.

Full shape:

```hocon
httpServer.telemetry.metrics {
  enabled = true
  slo = [ 1, 10, 50, 100, 200, 500, 1000, 2000, 5000, 10000, 20000, 30000, 60000, 90000 ]
  tags {
    "deployment.environment" = "production"
    "service.instance.id" = ${?HOSTNAME}
  }
}
```

---

## Per-component config roots { #config-roots }

`telemetry.metrics` hangs off each component's own config root. Verified from the module that
resolves each path:

| Component | Config root | Resolved in |
|---|---|---|
| HTTP server (public) | `httpServer` | `UndertowPublicHttpServerModule` → `UndertowHttpServerFactoryModule("kora-undertow", "httpServer")` |
| HTTP server (system) | `httpServer.system` | `UndertowSystemHttpServerModule` / `SystemHttpServerModule` |
| HTTP client | `httpClient.<name>` | `@HttpClient("name")`; OkHttp/JDK/Apache modules all use the `httpClient` prefix |
| JDBC | `jdbc` | `JdbcDatabaseModule` → `JdbcDatabaseFactoryModule("jdbc")` |
| Cassandra | `cassandra` | `CassandraDatabaseModule` → `CassandraDatabaseFactoryModule("cassandra")` |
| gRPC server | `grpcServer` | `GrpcServerModule` → `GrpcServerFactoryModule("kora-grpc", "grpcServer")` |
| gRPC client | `grpcClient.<ServiceSimpleName>` | `GrpcClientConfig` → `config.get("grpcClient." + serviceSimpleName)` |
| Kafka consumer | the `@KafkaListener("path")` value | annotation javadoc: *"@return config path"* |
| Kafka publisher | the `@KafkaPublisher("path")` value | annotation javadoc: *"@return path to config"* |
| Cache (Caffeine / Redis) | the `@Cache("path")` value | annotation javadoc: *"path for cache config (cache name)"* |
| Scheduling | `scheduling.telemetry` | `SchedulingModule` → `config.get("scheduling.telemetry")` |
| Resilience (global) | `resilient.telemetry` | `ResilientModule` → `config.get("resilient.telemetry")` |
| Resilience (per operation) | `resilient.<kind>.<name>.telemetry` | merged over the global section, operation values win |
| Redis / Lettuce | `lettuce` | `LettuceModule` → `LettuceFactoryModule("lettuce")` |
| S3 (AWS SDK) | `s3client.aws` | `AwsS3ClientModule` |
| JMS | the listener's config path | `JmsConsumerTelemetryConfig` |

A realistic "turn everything on" block:

```hocon
httpServer {
  port = 8080
  system.port = 8085
  telemetry.metrics.enabled = true
}

httpClient.petApi {
  url = "http://pets:8080"
  telemetry.metrics.enabled = true
}

jdbc {
  jdbcUrl = ${POSTGRES_JDBC_URL}
  username = ${POSTGRES_USER}
  password = ${POSTGRES_PASS}
  poolName = "orders"
  telemetry.metrics.enabled = true
}

scheduling.telemetry.metrics.enabled = true
resilient.telemetry.metrics.enabled = true
```

> Named resilience sections **do not inherit** from a `default` section in 2.0 — each stands alone
> and unset fields fall back to the type's defaults. See [kora-aop-resilient](../../kora-aop-resilient/SKILL.md).

---

## `slo` — histogram buckets { #slo }

`slo()` returns `Duration[]` and is passed straight to Micrometer:

```java
return Timer.builder("http.server.request.duration")
    .serviceLevelObjectives(this.context.config().metrics().slo())
    .tags(Tags.of(staticTags));
```

`DurationConfigValueMapper` decides how each element is read:

| HOCON element | Parsed as |
|---|---|
| `100` (bare number) | **100 milliseconds** — `Duration.ofMillis(number.longValue())` |
| `"250ms"`, `"1s"`, `"2m"`, `"1h"`, `"3d"` | HOCON-style duration (`ns`, `us`, `ms`, `s`, `m`, `h`, `d`) |
| `"PT1.5S"` | ISO-8601, tried first via `Duration.parse` |
| `null` inside the array | `ConfigValueException` — the array mapper rejects null elements |

So a 1.x millisecond array carries over unchanged. Buckets are cumulative: each `_bucket{le="…"}`
series counts observations at or below that boundary, which is what
`histogram_quantile` needs.

```hocon
# a tight web-facing SLO set instead of the 14 defaults
httpServer.telemetry.metrics {
  enabled = true                                   # slo does nothing without this
  slo = [ 5, 25, 50, 100, 250, 500, 1000, 5000 ]
}
```

Fewer buckets means fewer time series. The default 14 buckets multiply every distinct tag
combination by 14 `_bucket` series plus `_count`/`_sum`/`_max` — trim them for high-cardinality
routes.

For **your own** meters, set buckets on the builder — the config key governs Kora's meters only:

```java
Timer.builder("api.request.duration")
    .serviceLevelObjectives(Duration.ofMillis(50), Duration.ofMillis(100), Duration.ofSeconds(1))
    .register(registry);
```

`publishPercentiles(...)` computes percentiles inside the process and costs CPU and memory; with
Prometheus prefer SLO buckets and `histogram_quantile` server-side.

---

## `tags` — extra static tags { #tags }

Every factory appends `config.metrics().tags()` to the tag list of every meter it creates. The
tags are **static per component** — they are read when the meter is registered, so a changing value
would create a new series.

```hocon
jdbc.telemetry.metrics {
  enabled = true                 # tags do nothing without this
  tags {
    "db.role" = "primary"
    "team" = "orders"
  }
}
```

Use this for per-component labels. For labels that belong on *every* series in the process, use
the global [`metrics.tags` or a `MetricsTagsProvider`](#common-tags) instead — a common tag set
applied in fifteen config blocks is fifteen chances to drift.

---

## `driverMetrics` — third-party pool and client meters { #driver-metrics }

`DatabaseTelemetryConfig.DatabaseMetricsConfig` adds one key on top of the standard three:

```java
interface DatabaseMetricsConfig extends MetricsConfig {
    default boolean driverMetrics() { return true; }
}
```

`JdbcDataSource`:

```java
this.dataSource = new HikariDataSource(JdbcDatabaseConfig.toHikariConfig(this.databaseConfig, configurer));
if (this.databaseConfig.telemetry().metrics().driverMetrics()) {
    this.dataSource.setMetricRegistry(this.telemetry.meterRegistry());
}
```

**The trap:** `driverMetrics` defaults to `true`, but `telemetry.meterRegistry()` is the registry
the *telemetry factory* produced. With `jdbc.telemetry.metrics.enabled = false` the factory returned
`NoopDatabaseTelemetry`, whose `meterRegistry()` is `DefaultDatabaseTelemetryFactory.NOOP_METER_REGISTRY`.
Hikari dutifully registers its meters into a registry that throws them away. So:

```hocon
jdbc.telemetry.metrics {
  enabled = true        # REQUIRED, even though driverMetrics is already true
  driverMetrics = true  # default; set false to skip Hikari's own meters
}
```

Kafka's `driverMetrics` defaults to **`false`** on both the consumer and the publisher — turn it on
explicitly if you want the Kafka client's own meters.

---

## The system server { #system-server }

`SystemHttpServerConfig extends HttpServerConfig`:

```java
@Override default int port()  { return 8085; }
default String metricsPath()   { return "/metrics"; }
default String readinessPath() { return "/system/readiness"; }
default String livenessPath()  { return "/system/liveness"; }
```

```hocon
httpServer.system {
  port = 8085
  metricsPath = "/metrics"
  readinessPath = "/system/readiness"
  livenessPath = "/system/liveness"

  # optional: instrument the system server itself
  telemetry.metrics.enabled = true
  telemetry.tracing.enabled = true   # its tracing default is false, unlike every other component
}
```

A stale 1.x key (`privateApiHttpPort`, `privateApiHttpMetricsPath`, …) is an unrecognised HOCON key.
It is ignored with no warning, both servers fall back to their own defaults (8080 / 8085), and a
service that deliberately used custom ports comes up green on the wrong ones.

---

## Common tags: `metrics.tags`, `MetricsTagsProvider`, `PrometheusMeterRegistryInitializer` { #common-tags }

`MetricsModule` ships an initializer (a plain module component, deliberately **not**
`@DefaultComponent`) that merges two sources into one global `MeterFilter`:

```java
default PrometheusMeterRegistryInitializer commonTagsMeterRegistryInitializer(MetricsConfig config, All<MetricsTagsProvider> tagsProviders) {
    var merged = new LinkedHashMap<String, String>();
    for (var provider : tagsProviders) {
        merged.putAll(provider.tags());
    }
    // config tags are applied last so static configuration wins on key conflicts
    merged.putAll(config.tags());
    if (merged.isEmpty()) {
        return registry -> registry;
    }
    var tags = Tags.of(merged.entrySet().stream()
        .map(e -> Tag.of(e.getKey(), e.getValue()))
        .toList());
    return registry -> {
        registry.config().meterFilter(MeterFilter.commonTags(tags));
        return registry;
    };
}
```

| Source | When to use | Precedence |
|---|---|---|
| `metrics.tags { … }` | static values known at deploy time | wins on a key conflict |
| `MetricsTagsProvider` components | values computed at startup (region from the environment, build version, …) | merged in graph order, overridden by config |

The initializers run in `PrometheusMeterRegistryWrapper.init()` **before** the JVM binders are bound
and `kora.up` is registered, so the common tags land on those meters too:

```java
var meterRegistry = new PrometheusMeterRegistry(PrometheusConfig.DEFAULT);
for (var initializer : initializers) {
    meterRegistry = initializer.apply(meterRegistry);
}
this.gcMetrics = new JvmGcMetrics();
new ClassLoaderMetrics().bindTo(meterRegistry);
…
```

### `MetricsTagsProvider`

```java
package io.koraframework.micrometer.module;

public interface MetricsTagsProvider {
    Map<String, String> tags();
}
```

Register any number as components. `tags()` is called once, while the graph builds the
initializer — a value that changes afterwards is never seen. Templates:
[`AppMetricsTagsProvider.java.template`](../assets/AppMetricsTagsProvider.java.template) /
[`AppMetricsTagsProvider.kt.template`](../assets/AppMetricsTagsProvider.kt.template).

```hocon
metrics.tags {
  "service" = "order-service"
  "region" = "eu-1"          # beats a provider that also returns "region"
}
```

### Your own `PrometheusMeterRegistryInitializer`

The type is `Function<PrometheusMeterRegistry, PrometheusMeterRegistry>`, so it **must return the
registry** — returning `void`, or a fresh registry you did not derive from the argument, breaks the
chain. It is the hook onto `registry.config()`: `meterFilter(io.micrometer.core.instrument.config.MeterFilter)`,
`namingConvention(...)`, deny and rename rules. Cardinality caps and rename/deny rules are
`MeterFilter`s; consult the
[Micrometer meter-filter documentation](https://docs.micrometer.io/micrometer/reference/concepts/meter-filters.html)
for the factory you need, since those APIs belong to Micrometer, not Kora.

**Declaring one does not displace the common-tags initializer.** Since 2.0.0.RC2 (#935)
`commonTagsMeterRegistryInitializer` is a regular component, so `All<PrometheusMeterRegistryInitializer>`
always contains it next to yours — `metrics.tags` and every `MetricsTagsProvider` keep applying. (In
RC1 it was `@DefaultComponent`, and `All<T>` drops a default candidate when a non-default one exists,
so a custom initializer silently removed the common tags; do not copy the RC1 workaround that
re-merged `MetricsConfig.tags()` and `All<MetricsTagsProvider>` by hand — it now installs the same
filter twice.) Your initializer only adds its own rules:

Java:

```java
package com.example;

import io.koraframework.common.annotation.Module;
import io.koraframework.micrometer.module.PrometheusMeterRegistryInitializer;
import io.micrometer.core.instrument.config.MeterFilter;

@Module
public interface CustomMetricsConfig {

    default PrometheusMeterRegistryInitializer meterFiltersInit() {
        return registry -> {
            registry.config().meterFilter(MeterFilter.denyNameStartsWith("jvm.buffer"));
            return registry;
        };
    }
}
```

Kotlin:

```kotlin
package com.example

import io.koraframework.common.annotation.Module
import io.koraframework.micrometer.module.PrometheusMeterRegistryInitializer
import io.micrometer.core.instrument.config.MeterFilter

@Module
interface CustomMetricsConfig {

    fun meterFiltersInit(): PrometheusMeterRegistryInitializer =
        PrometheusMeterRegistryInitializer { registry ->
            registry.config().meterFilter(MeterFilter.denyNameStartsWith("jvm.buffer"))
            registry
        }
}
```

Multiple initializers of your own are allowed and are applied in graph order.

Useful common tags: `service`, `environment`, `version`, `region`. Keep them bounded — they multiply
onto every series in the process.

---

## Replacing the registry or the scraper { #replacing-the-registry }

`prometheusMeterRegistry` and `prometheusMetricsScraper` are `@DefaultComponent`, so a `@Component` of
the same type in your graph wins. Two consequences worth knowing:

- Supplying a non-Prometheus `MeterRegistry` leaves `prometheusMetricsScraper` matching the
  `else` branch, which returns `os -> {}`. `/metrics` then answers **200 with an empty body**.
  Supply your own `MetricsScraper` alongside the registry.
- `MetricsScraper` is a single-method contract:

  ```java
  public interface MetricsScraper {
      void scrape(OutputStream os) throws IOException;
  }
  ```

  `MetricsHandler` resolves it as `ValueOf<Optional<MetricsScraper>>`, so an absent scraper is not a
  graph error — it is the `# Metric Scraper disabled` response.

---

## Keys that no longer exist { #removed-keys }

| 1.x key | Status in 2.0 |
|---|---|
| `metrics.opentelemetrySpec` (`V120` / `V123`) | **removed** — the top-level `metrics` section maps onto `MetricsConfig`, which declares only `enabled` and `tags` |
| `httpServer.publicApiHttpPort` | → `httpServer.port` |
| `httpServer.privateApiHttpPort` | → `httpServer.system.port` |
| `httpServer.privateApiHttpMetricsPath` | → `httpServer.system.metricsPath` |
| `httpServer.privateApiHttpLivenessPath` / `…ReadinessPath` | → `httpServer.system.livenessPath` / `…readinessPath` |
| `db { … }` | → `jdbc { … }` |

2.0 emits a single fixed naming scheme — the one 1.x called `V123` — with several meter names
changed on top of it. Setting `opentelemetrySpec` in a 2.0 config silently does nothing.

---

## Verification { #verification }

```bash
# 1. the registry is bound at all
curl -s http://localhost:8085/metrics | head -1
#    "# Metric Scraper disabled"  -> MetricsModule missing
#    (nothing at all)             -> metrics.enabled = false

# 2. component instrumentation is actually on
curl -s http://localhost:8080/your/route > /dev/null
curl -s http://localhost:8085/metrics | grep -c '^http_server_request_duration'
#    0 -> httpServer.telemetry.metrics.enabled is still false

# 3. common tags landed
curl -s http://localhost:8085/metrics | grep '^kora_up'
```

In a JUnit test, assert on the body rather than the status code — a 200 from `/metrics` proves only
that the system server is up:

```java
assertTrue(body.contains("http_server_request_duration") || body.contains("http_server_active_requests"));
assertFalse(body.contains("# Metric Scraper disabled"));
```

---

## References

- [metrics-reference.md](metrics-reference.md) — what each enabled component actually emits
- [metrics-export-reference.md](metrics-export-reference.md) — scraping and forwarding
- [probes-reference.md](probes-reference.md) — the other endpoints on the same system server
- [Micrometer concepts](https://docs.micrometer.io/micrometer/reference/concepts.html)
