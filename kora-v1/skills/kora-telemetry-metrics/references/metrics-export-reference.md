# Metrics Export Reference

**Focus:** How Kora exposes metrics and how to scrape them.

Kora's `micrometer-module` registers a `PrometheusMeterRegistry` and serves it in Prometheus text format on the private HTTP server. The model is **pull**: a Prometheus-compatible agent scrapes the endpoint. Kora does not provide configuration to swap the registry for a push exporter (StatsD, OTLP, etc.). To deliver metrics to a different backend, scrape the `/metrics` endpoint with an agent and forward from there.

> Distributed tracing export (OTLP over gRPC/HTTP) is a separate concern handled by the tracing modules — see `kora-telemetry-tracing`. It does not affect the metric registry.

---

## Prometheus (pull model)

### Module and configuration

```groovy
dependencies {
    annotationProcessor "ru.tinkoff.kora:annotation-processors"
    implementation "ru.tinkoff.kora:micrometer-module"
    implementation "ru.tinkoff.kora:http-server-undertow"
}
```

```hocon
httpServer {
    publicApiHttpPort = 8080            # public business traffic
    privateApiHttpPort = 8085           # management / operations port
    privateApiHttpMetricsPath = "/metrics"  # Prometheus scrape endpoint
}
```

Keep `/metrics` on the private port — it exposes internal service state and should not be reachable by business clients.

### Prometheus scrape config

```yaml
# prometheus.yml
scrape_configs:
  - job_name: 'order-service'
    scrape_interval: 15s
    metrics_path: '/metrics'
    static_configs:
      - targets: ['order-service:8085']
```

### Verify

```bash
curl http://localhost:8085/metrics
```

Expected (truncated) output uses OpenTelemetry semantic-convention names rendered in Prometheus form:

```
# HELP kora_up Application status indicator
# TYPE kora_up gauge
kora_up{version="1.2.17"} 1.0
# HELP http_server_request_duration_milliseconds HTTP server request duration
# TYPE http_server_request_duration_milliseconds histogram
http_server_request_duration_milliseconds_bucket{http_request_method="GET",http_route="/api/users",http_response_status_code="200",le="100.0"} 42
```

---

## Forwarding to other backends

Because the registry is Prometheus pull-based, integration with other systems happens at the scraping layer, not inside Kora:

| Target backend | How to deliver |
|----------------|----------------|
| Prometheus / Thanos / Mimir | Native scrape of `/metrics` |
| OpenTelemetry Collector | Collector `prometheus` receiver scrapes `/metrics`, then exports onward |
| VictoriaMetrics | `vmagent` scrapes `/metrics` |
| Grafana Cloud / hosted Prometheus | Remote-write agent scrapes `/metrics` and remote-writes |

Choose the export protocol in the agent, not in the Kora application config.

---

## OpenTelemetry metric naming

The shape of metric names and tags follows the OpenTelemetry standard selected by `metrics.opentelemetrySpec` (`V120` or `V123`). This controls naming conventions only; it is unrelated to the export transport. See [Metrics Config Reference](metrics-config-reference.md).

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| `/metrics` returns 404 | Add the HTTP server module and set `privateApiHttpMetricsPath`; scrape the private port, not the public one |
| Scrape returns empty body | Confirm `MetricsModule` is in `@KoraApp extends ...` |
| Agent cannot reach endpoint | Check that `privateApiHttpPort` is published/reachable from the agent's network |
| Missing common tags | Register a `PrometheusMeterRegistryInitializer` (see config reference) |

---

## References

- [Micrometer concepts](https://docs.micrometer.io/micrometer/reference/concepts.html)
- [OpenTelemetry semantic conventions](https://opentelemetry.io/docs/specs/semconv/)
- [Prometheus data model](https://prometheus.io/docs/concepts/data_model/)
