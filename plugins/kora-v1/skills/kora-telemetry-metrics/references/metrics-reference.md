# Kora Built-in Metrics Reference

**Local source:** `.kora-agent/kora-docs/mkdocs/docs/en/documentation/metrics.md`
**Local example:** `.kora-agent/kora-examples/examples/java/kora-java-telemetry/`

Catalogue of metrics Kora registers automatically once `MetricsModule` is connected. All names and tags follow [OpenTelemetry semantic conventions](https://opentelemetry.io/docs/specs/semconv/). In Prometheus output, dots become underscores and duration metrics gain `_count` / `_sum` / `_bucket` / `_max` suffixes.

## Contents

- [Module: MetricsModule](#metricsmodule)
- [HTTP server](#http-server)
- [HTTP client](#http-client)
- [Database](#database)
- [Kafka](#kafka)
- [gRPC server](#grpc-server)
- [gRPC client](#grpc-client)
- [Scheduling](#scheduling)
- [Cache](#cache)
- [Resilience](#resilience)
- [S3 client](#s3-client)
- [System and JVM](#system-and-jvm)

---

## MetricsModule

**Dependency:** `ru.tinkoff.kora:micrometer-module` (registers `PrometheusMeterRegistry`; no separate registry artifact needed)
**Module:** `ru.tinkoff.kora.micrometer.module.MetricsModule`

```hocon
metrics {
    opentelemetrySpec = "V120"  # or "V123"
}
```

The module instruments all connected Kora modules and adds JVM metrics. The tables below list the metric, its Micrometer type, and the OpenTelemetry tag keys.

---

## HTTP server

| Metric | Type | Tags |
|--------|------|------|
| `http.server.request.duration` | DistributionSummary | `http.request.method`, `http.response.status_code`, `http.route`, `url.scheme`, `server.address`, `error.type` |
| `http.server.active_requests` | Gauge | `http.request.method`, `http.route`, `server.address`, `url.scheme` |

---

## HTTP client

| Metric | Type | Tags |
|--------|------|------|
| `http.client.request.duration` | DistributionSummary | `http.request.method`, `http.response.status_code`, `server.address`, `url.scheme`, `http.route`, `error.type` |

---

## Database

| Metric | Type | Tags |
|--------|------|------|
| `db.client.request.duration` | DistributionSummary | `db.pool.name`, `db.statement`, `db.operation`, `error.type` |

---

## Kafka

| Metric | Type | Tags |
|--------|------|------|
| `messaging.receive.duration` | DistributionSummary | `messaging.system`, `messaging.destination`, `messaging.operation`, `error.type` |
| `messaging.publish.duration` | DistributionSummary | `messaging.system`, `messaging.destination`, `messaging.partition_id`, `error.type` |
| `messaging.process.batch.duration` | DistributionSummary | `messaging.system`, `messaging.destination`, `error.type` |
| `messaging.kafka.consumer.lag` | Gauge | `messaging.system`, `messaging.destination`, `messaging.partition_id`, `messaging.consumer_group` |

---

## gRPC server

| Metric | Type | Tags |
|--------|------|------|
| `rpc.server.duration` | DistributionSummary | `rpc.service`, `rpc.method`, `rpc.status`, `error.type` |
| `rpc.server.requests_per_rpc` | Counter | `rpc.service`, `rpc.method` |
| `rpc.server.responses_per_rpc` | Counter | `rpc.service`, `rpc.method` |

---

## gRPC client

| Metric | Type | Tags |
|--------|------|------|
| `rpc.client.duration` | DistributionSummary | `rpc.service`, `rpc.method`, `rpc.status`, `error.type`, `server.address` |
| `rpc.client.requests_per_rpc` | Counter | `rpc.service`, `rpc.method`, `server.address` |
| `rpc.client.responses_per_rpc` | Counter | `rpc.service`, `rpc.method`, `server.address` |

---

## Scheduling

| Metric | Type | Tags |
|--------|------|------|
| `scheduling.job.duration` | DistributionSummary | `code.class`, `code.function`, `error.type` |

---

## Cache

| Metric | Type | Tags |
|--------|------|------|
| `cache.duration` | DistributionSummary | `cache`, `operation`, `origin`, `status` |
| `cache.ratio` | Counter | `cache`, `origin`, `type` |

When using Caffeine, standard Micrometer cache meters are also registered: `cache.gets`, `cache.puts`, `cache.evictions` (Counter), `cache.size` (Gauge).

---

## Resilience

| Metric | Type | Tags |
|--------|------|------|
| `resilient.circuitbreaker.state` | Gauge | `name` (0=CLOSED, 1=HALF_OPEN, 2=OPEN) |
| `resilient.circuitbreaker.transition` | Counter | `name`, `state` |
| `resilient.circuitbreaker.call.acquire` | Counter | `name`, `state`, `status` |
| `resilient.retry.attempts` | Counter | `name` |
| `resilient.retry.exhausted` | Counter | `name` |
| `resilient.timeout.exhausted` | Counter | `name` |
| `resilient.fallback.attempts` | Counter | `name`, `type` |

---

## S3 client

| Metric | Type | Tags |
|--------|------|------|
| `s3.client.duration` | DistributionSummary | `aws.s3.bucket`, `aws.operation.name`, `error.type` |
| `s3.kora.client.duration` | DistributionSummary | `aws.client.name`, `aws.s3.bucket`, `aws.operation.name`, `error.type` |

---

## System and JVM

| Metric | Type | Tags |
|--------|------|------|
| `kora.up` | Gauge | `version` (value = 1 while running) |
| `jvm.gc.pause` | DistributionSummary | `action`, `cause` |
| `jvm.gc.memory.allocated` | Counter | — |
| `jvm.memory.used` | Gauge | `area`, `id` |
| `jvm.memory.committed` | Gauge | `area`, `id` |
| `jvm.memory.max` | Gauge | `area`, `id` |
| `jvm.threads.live` | Gauge | — |
| `jvm.threads.daemon` | Gauge | — |
| `jvm.threads.peak` | Gauge | — |
| `jvm.threads.states` | Gauge | `state` |
| `process.cpu.usage` | Gauge | — |
| `system.cpu.usage` | Gauge | — |
| `system.cpu.count` | Gauge | — |
| `process.files.open` | Gauge | — |
| `process.files.max` | Gauge | — |
| `process.uptime` | Gauge | — |
| `logback.events` | Counter | `level` |
| `jvm.classes.loaded` | Gauge | — |

For the complete list (Camunda, JMS, SOAP, Redis/Lettuce, additional JVM gauges) see the local docs at `.kora-agent/kora-docs/mkdocs/docs/en/documentation/metrics.md`.

---

## Naming custom metrics

Match the framework style:

| Pattern | Example | Type |
|---------|---------|------|
| `<noun>.<action>.duration` | `user.creation.duration` | Timer |
| `<noun>.<action>.total` | `user.creation.total` | Counter |
| `<noun>.<attribute>` | `payment.amount` | DistributionSummary |

Use dots as separators, end durations with `.duration`, end monotonic counts with `.total`, and set `baseUnit(...)` for size summaries. See [Custom Metrics Reference](custom-metrics-reference.md).
