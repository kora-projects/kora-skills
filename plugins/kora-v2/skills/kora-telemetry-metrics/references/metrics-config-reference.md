# Metrics Configuration Reference

## Contents

- [Module setup](#module-setup)
- [HTTP server / scrape endpoint](#http-server-configuration)
- [OpenTelemetry standard (opentelemetrySpec)](#opentelemetry-standard)
- [Common tags via PrometheusMeterRegistryInitializer](#common-tags)
- [Per-module telemetry.metrics config (slo, tags, enabled)](#per-module-config)
- [Custom meter buckets and percentiles](#custom-meter-buckets)
- [Verification](#verification)

---

## Module setup { #module-setup }

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

`MetricsModule` adds a `PrometheusMeterRegistry` and publishes a `MeterRegistry` component for custom meters. The HTTP server module is required to serve the metrics endpoint.

---

## HTTP server configuration { #http-server-configuration }

```hocon
httpServer {
    publicApiHttpPort = 8080            # public API port
    privateApiHttpPort = 8085           # management / operations port
    privateApiHttpMetricsPath = "/metrics"  # Prometheus scrape endpoint
}
```

Always expose `/metrics` on the private port — metrics expose internal service state.

---

## OpenTelemetry standard { #opentelemetry-standard }

The `MetricsConfig` class controls the metric naming/tag standard:

```hocon
metrics {
    opentelemetrySpec = "V120"  # or "V123"
}
```

| Value | Meaning |
|-------|---------|
| `V120` | Original OpenTelemetry semantic conventions (the default) |
| `V123` | Newer conventions, available since Kora `1.1.0` |

`V123` updates some metric and tag names to the stabilized OpenTelemetry HTTP conventions. Pick one consistently across services so dashboards and alerts match.

---

## Common tags { #common-tags }

To attach shared labels to every metric, add a `PrometheusMeterRegistryInitializer` as a `default` method of a `@Module`. The initializer is a `Function<PrometheusMeterRegistry, PrometheusMeterRegistry>` and **must return the registry**. It runs exactly once at application initialization.

===! ":fontawesome-brands-java: `Java`"

    ```java
    import ru.tinkoff.kora.common.Module;
    import ru.tinkoff.kora.micrometer.module.PrometheusMeterRegistryInitializer;

    @Module
    public interface MetricsConfigModule {
        default PrometheusMeterRegistryInitializer commonTagsInit() {
            return registry -> {
                registry.config().commonTags(
                        "service", "order-service",
                        "environment", "production",
                        "version", "1.0.0");
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
                registry.config().commonTags(
                    "service", "order-service",
                    "environment", "production",
                    "version", "1.0.0")
                registry
            }
        }
    }
    ```

Useful common tags: `service`, `environment`, `version`, `region`. Keep them bounded — they multiply onto every series.

---

## Per-module config { #per-module-config }

Built-in module metrics are configured inside each module's `telemetry.metrics` section (not a global `micrometer` namespace). The keys are `enabled`, `slo` (histogram bucket boundaries in milliseconds), and `tags` (extra static tags). Example for the HTTP server:

```hocon
httpServer {
    telemetry {
        metrics {
            enabled = true
            slo = [ 1, 10, 50, 100, 200, 500, 1000, 2000, 5000, 10000, 20000, 30000, 60000, 90000 ]
            tags {
                "key1" = "value1"
            }
        }
    }
}
```

The same `telemetry.metrics { enabled, slo, tags }` shape applies to other instrumented modules (HTTP client, JDBC database, gRPC server/client, Kafka, etc.) under their own config roots. Consult the relevant module's documentation for the exact root path.

---

## Custom meter buckets { #custom-meter-buckets }

For application-defined meters, configure buckets on the Micrometer builder.

```java
Timer timer = Timer.builder("api.request.duration")
    .description("Request processing duration")
    .serviceLevelObjectives(
        Duration.ofMillis(50),
        Duration.ofMillis(100),
        Duration.ofMillis(250),
        Duration.ofMillis(500),
        Duration.ofSeconds(1))
    .register(registry);
```

```java
DistributionSummary summary = DistributionSummary.builder("response.size.bytes")
    .description("Response size distribution")
    .baseUnit("bytes")
    .serviceLevelObjectives(100, 1000, 10000, 100000, 1000000)
    .register(registry);
```

`publishPercentiles(...)` computes client-side percentiles but adds CPU and memory overhead; for Prometheus prefer SLO buckets and compute quantiles server-side.

---

## Verification { #verification }

```bash
curl http://localhost:8085/metrics
```

```
# HELP http_server_request_duration_milliseconds HTTP server request duration
# TYPE http_server_request_duration_milliseconds histogram
http_server_request_duration_milliseconds_bucket{http_request_method="GET",http_route="/api/users",http_response_status_code="200",le="100.0"} 42
http_server_request_duration_milliseconds_count{http_request_method="GET",http_route="/api/users",http_response_status_code="200"} 57
```

---

## References

- Local docs: `.kora-agent/kora-docs/mkdocs/docs/en/documentation/metrics.md`
- Local guide: `.kora-agent/kora-docs/mkdocs/docs/en/guides/observability-metrics.md`
- Local example: `.kora-agent/kora-examples/examples/java/kora-java-telemetry/`
