# Metrics Export Reference (Kora 2.0)

How Kora exposes metrics, how to scrape them, and how to get them somewhere else.

## Contents

- [The export model](#export-model)
- [Where the endpoint lives](#endpoint)
- [The `MetricsScraper` contract](#scraper)
- [Prometheus scrape configuration](#scrape-config)
- [Kubernetes](#kubernetes)
- [Forwarding to other backends](#forwarding)
- [Replacing the registry](#replacing)
- [Troubleshooting](#troubleshooting)

---

## The export model { #export-model }

`micrometer-module` creates one `PrometheusMeterRegistry` and serves it over HTTP in Prometheus text
format. The model is **pull**: an agent scrapes the endpoint.

Kora exposes **no** configuration for a push exporter — there is no `micrometer.statsd`,
no `micrometer.otlp`, no `metrics.export.*`. To deliver metrics to another backend, scrape
`/metrics` with an agent and forward from there.

> Trace export (OTLP over gRPC or HTTP) is an entirely separate mechanism, configured under
> `tracing.exporter` by `opentelemetry-tracing-exporter-grpc` / `-http`. It has no effect on the
> meter registry. See [kora-telemetry-tracing](../../kora-telemetry-tracing/SKILL.md).

`MetricsModule` also publishes a `MicrometerMeterProvider` (the OpenTelemetry ↔ Micrometer bridge)
as a `@DefaultComponent`. It routes OTel metric instruments into the same Micrometer registry — it
does **not** turn on an OTLP metrics exporter.

---

## Where the endpoint lives { #endpoint }

On the **system** HTTP server, never the public one:

| | Public server | System server |
|---|---|---|
| Config root | `httpServer` | `httpServer.system` |
| Default port | `8080` | **`8085`** |
| Serves | your `@HttpController`s | `/metrics`, `/system/liveness`, `/system/readiness` |
| Transport name in metrics | `kora-undertow` | `kora-undertow-system` |

`SystemHttpServerConfig.metricsPath()` defaults to `"/metrics"`. There is no key that moves the
endpoint onto the public port, and you should not want one — metrics expose internal state,
route templates and error class names.

```hocon
httpServer {
  port = 8080
  system.port = 8085
  system.metricsPath = "/metrics"
  telemetry.metrics.enabled = true     # otherwise only JVM meters are exported
}
```

### Dependencies

```groovy
dependencies {
    koraBom platform("io.koraframework:kora-bom:$koraVersion")   // koraVersion=2.0.0.RC2
    annotationProcessor "io.koraframework:annotation-processors"

    implementation "io.koraframework:micrometer-module"
    implementation "io.koraframework:http-server-undertow"
}
```

`micrometer-module` pulls `io.micrometer:micrometer-registry-prometheus` (`1.17.1`) and the
`io.prometheus:prometheus-metrics-*` stack (`1.9.0`) transitively. Adding either yourself only
risks a version clash.

---

## The `MetricsScraper` contract { #scraper }

```java
package io.koraframework.telemetry.common;

public interface MetricsScraper {
    void scrape(OutputStream os) throws IOException;
}
```

`MetricsHandler` resolves it as `ValueOf<Optional<MetricsScraper>>` and **always answers 200**:

```java
var registry = this.meterRegistry.get().orElse(null);
if (registry == null) {
    return HttpServerResponse.of(200, HttpBody.plaintext("# Metric Scraper disabled"));
}
return HttpServerResponse.of(200, HttpBodyOutput.of("text/plain", registry::scrape));
```

So **a 200 from `/metrics` proves nothing.** Four distinct outcomes share one status code:

| Body | Meaning |
|---|---|
| `# Metric Scraper disabled` | No `MetricsScraper` in the graph — `MetricsModule` is missing |
| empty | A `MetricsScraper` exists but writes nothing — the registry is not a `PrometheusMeterRegistry`: global `metrics.enabled = false` (`NoopMeterRegistry`) or a replacement registry without its own scraper |
| `kora_up`, `jvm_*`, `process_*` and nothing else | Registry bound, but every component's `telemetry.metrics.enabled` is still `false` |
| `kora_up` + `http_server_*` + `db_*` + … | Working |

The response body is streamed straight from `PrometheusMeterRegistry.scrape(OutputStream)`, so the
content type is `text/plain` and the format is whatever the pinned Prometheus client emits.

---

## Prometheus scrape configuration { #scrape-config }

```yaml
# prometheus.yml
scrape_configs:
  - job_name: 'order-service'
    scrape_interval: 15s
    metrics_path: '/metrics'
    static_configs:
      - targets: ['order-service:8085']    # the SYSTEM port, not 8080
```

Kubernetes service discovery:

```yaml
scrape_configs:
  - job_name: 'kora-services'
    kubernetes_sd_configs:
      - role: pod
    relabel_configs:
      - source_labels: [__meta_kubernetes_pod_annotation_prometheus_io_scrape]
        action: keep
        regex: "true"
      - source_labels: [__meta_kubernetes_pod_annotation_prometheus_io_port]
        target_label: __address__
        regex: (.+)
        replacement: $1
```

### Verify a scrape

```bash
curl -s http://localhost:8085/metrics | head -5
curl -s http://localhost:8085/metrics | grep '^kora_up'
```

`kora_up` is a constant-`1` gauge carrying a `version` label read from the classpath resource
`META-INF/kora/version/common` (or `UNKNOWN` when the resource is absent). It is the cheapest
"is this pod alive and which build is it" signal you have.

Before hard-coding any series name into a dashboard, read it off the running process — the
Prometheus exposition name is derived by Micrometer from the meter name plus a base-unit suffix:

```bash
curl -s http://localhost:8085/metrics | grep '^# TYPE'
```

---

## Kubernetes { #kubernetes }

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: order-service
  annotations:
    prometheus.io/scrape: "true"
    prometheus.io/port: "8085"
    prometheus.io/path: "/metrics"
spec:
  containers:
    - name: app
      image: order-service:latest
      ports:
        - name: http
          containerPort: 8080
        - name: system
          containerPort: 8085
      livenessProbe:
        httpGet: { path: /system/liveness, port: system }
        initialDelaySeconds: 30
        periodSeconds: 10
      readinessProbe:
        httpGet: { path: /system/readiness, port: system }
        initialDelaySeconds: 5
        periodSeconds: 5
```

Expose the system port to the cluster's monitoring namespace only — do not put it behind a public
Ingress. See [probes-reference.md](probes-reference.md).

---

## Forwarding to other backends { #forwarding }

Because the registry is pull-based, integration with other systems happens at the scraping layer,
not inside the Kora application:

| Target backend | How to deliver |
|---|---|
| Prometheus / Thanos / Mimir | direct scrape of `/metrics` |
| OpenTelemetry Collector | the Collector's `prometheus` receiver scrapes `/metrics`, then exports onward (OTLP, Datadog, …) |
| VictoriaMetrics | `vmagent` scrapes `/metrics` |
| Grafana Cloud / hosted Prometheus | a remote-write agent scrapes and remote-writes |
| Datadog | the Datadog Agent's OpenMetrics check scrapes `/metrics` |

Choose the export protocol in the agent, not in the Kora application config. Asking for a Kora key
that pushes to StatsD or OTLP means looking for something that does not exist.

---

## Replacing the registry { #replacing }

`MetricsModule` declares both the registry and the scraper as `@DefaultComponent`, so your own
`@Component` of the same type wins:

```java
@Component
public final class CustomRegistry implements Wrapped<MeterRegistry>, Lifecycle { … }
```

Two things to get right when you do:

1. `prometheusMetricsScraper(MeterRegistry)` only produces a real scraper for a
   `PrometheusMeterRegistry`; for anything else it returns `os -> {}`. Supply your own
   `MetricsScraper` alongside a non-Prometheus registry, or `/metrics` answers 200 with an empty
   body.
2. `PrometheusMeterRegistryWrapper` is what binds the seven JVM/system meter binders and registers
   `kora.up`. A replacement registry inherits none of that — bind what you need yourself.

The much lighter customisation point is `PrometheusMeterRegistryInitializer`, which mutates the
registry Kora already built. Prefer it unless you genuinely need a different registry
implementation. See [metrics-config-reference.md](metrics-config-reference.md#common-tags).

---

## Troubleshooting { #troubleshooting }

| Problem | Cause | Fix |
|---|---|---|
| Body is `# Metric Scraper disabled` | No `MetricsScraper` in the graph | Add `MetricsModule` to `@KoraApp extends …` |
| Body has only `jvm_*` / `kora_up` | `telemetry.metrics.enabled` left at `false` | Enable it per component |
| Body is empty | Global `metrics.enabled = false`, or a non-Prometheus registry replaced the default without a matching `MetricsScraper` | Remove the kill switch / supply a `MetricsScraper` |
| 404 on port 8080 | Scraping the public server | Scrape `httpServer.system.port` |
| `privateApiHttpMetricsPath` ignored | Removed 1.x key, silently unrecognised | `httpServer.system.metricsPath` |
| Agent cannot reach the endpoint | System port not published/reachable | Expose `httpServer.system.port` to the scraper's network |
| Missing common tags | `metrics.tags` / `MetricsTagsProvider` not set, a `MeterFilter` of your own removes the key, or (RC1 only, fixed by #935) an app-level `PrometheusMeterRegistryInitializer` displaced the common-tags initializer | See [common tags](metrics-config-reference.md#common-tags) |
| Duplicate/clashing Prometheus classes | A hand-added `micrometer-registry-prometheus` at a different version | Remove it; the BOM pins `1.17.1` transitively |

---

## References

- [metrics-config-reference.md](metrics-config-reference.md) — the two gates and every config key
- [metrics-reference.md](metrics-reference.md) — what gets exported once metrics are on
- [Micrometer concepts](https://docs.micrometer.io/micrometer/reference/concepts.html)
- [Prometheus data model](https://prometheus.io/docs/concepts/data_model/)
- [Prometheus scrape configuration](https://prometheus.io/docs/prometheus/latest/configuration/configuration/#scrape_config)
