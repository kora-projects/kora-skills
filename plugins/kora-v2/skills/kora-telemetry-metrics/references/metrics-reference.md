# Kora 2.0 Built-in Metrics Reference

Catalogue of the meters Kora registers itself. Every name below was read out of the
`Default*MetricsFactory` class that calls `Timer.builder(...)` / `Counter.builder(...)` /
`Gauge.builder(...)` in the Kora 2.0 source tree. Nothing here is carried over from the 1.x
documentation.

**Scope — read this before concluding a meter is not Kora's.** This catalogue covers the modules
published under the `io.koraframework` group. Kora also registers four meters from the
`io.koraframework.experimental` group, which no skill in this package covers and which are therefore
*not* listed below: `camunda.engine.delegate.duration`, `camunda.rest.request.duration`,
`camunda.rest.active_requests` (Camunda 7) and `zeebe.worker.handler.duration` (Camunda 8). If one of
those appears in your scrape it is a genuine Kora meter — go to the module source, not to this file.

> **None of these exist until you enable them.** `TelemetryConfig.MetricsConfig.enabled()` defaults
> to `false`, and each factory additionally requires a `MeterRegistry` in the graph. See
> [metrics-config-reference.md](metrics-config-reference.md).

## Contents

- [How a meter name becomes a Prometheus series](#exposition)
- [HTTP server](#http-server)
- [HTTP client](#http-client)
- [Database](#database)
- [Kafka](#kafka)
- [gRPC](#grpc)
- [Cache](#cache)
- [Scheduling](#scheduling)
- [Resilience](#resilience)
- [S3, SOAP, JMS, Redis](#s3-soap-jms-redis)
- [Framework, JVM and system](#framework-jvm-and-system)
- [Renamed and removed relative to 1.x](#renamed-and-removed-relative-to-1x)
- [Naming your own metrics](#naming-your-own-metrics)

---

## How a meter name becomes a Prometheus series { #exposition }

Kora registers meters under dotted OpenTelemetry-style names. Micrometer's
`PrometheusMeterRegistry` performs the translation:

1. dots and dashes become underscores — `http.server.request.duration` → `http_server_request_duration`;
2. a base-unit suffix is appended — `_seconds` for `Timer`, `_bytes` for a summary with
   `baseUnit("bytes")`;
3. distribution meters expand into `_count`, `_sum`, `_bucket`, `_max` series;
4. counters gain `_total` — Micrometer does not double it, so a meter already named
   `user.creation.total` exports as `user_creation_total`, not `user_creation_total_total`.

**Read the exact series name off a running process before wiring a dashboard:**

```bash
curl -s http://localhost:8085/metrics | grep '^# TYPE http_server_request_duration'
```

Steps 1 and 2 are Micrometer's behaviour, not Kora's, so the suffix follows the Micrometer version
on your classpath (`1.17.1` via the BOM). The prefix `http_server_request_duration` and the
suffixed forms `jvm_memory_used_bytes` / `process_cpu_usage` / `logback_events_total` appear
verbatim in the migrated observability guide's container smoke test, so the mechanism is confirmed
against real 2.0 output.

### Tag keys

Kora passes OpenTelemetry semantic-convention constants — `HttpAttributes.HTTP_ROUTE`,
`ErrorAttributes.ERROR_TYPE`, `DbAttributes.DB_OPERATION_NAME`, … — as tag keys. The literal label
string is whatever that constant resolves to in the semconv artifacts the BOM pins
(`io.opentelemetry.semconv:opentelemetry-semconv:1.44.0` and
`opentelemetry-semconv-incubating:1.44.0-alpha`), which is why the tables below give the constant
alongside the label. Tags that Kora hard-codes as string literals (`server.name`, `system.config`,
`system.name.simple`, `system.name.canonical`, `cache.origin`, `cache.operation`, `cache.result`,
`resilient.name`, `resilient.state`, `resilient.status`, `resilient.reason`, `resilient.type`) are exact.

Every metric additionally carries whatever you put in that component's
`telemetry.metrics.tags { … }`, plus the global common tags from `metrics.tags` and any
`MetricsTagsProvider` (see [metrics-config-reference.md](metrics-config-reference.md#common-tags)).

---

## HTTP server { #http-server }

Registered by `DefaultHttpServerMetricsFactory`. Config root `httpServer` (public) and
`httpServer.system` (system server).

| Meter | Type | Tags |
|---|---|---|
| `http.server.request.duration` | Timer (uses `metrics.slo()` as SLO buckets) | `server.name`, `ServerAttributes.SERVER_PORT` → `server.port`, `HttpAttributes.HTTP_REQUEST_METHOD` → `http.request.method`, `HttpAttributes.HTTP_RESPONSE_STATUS_CODE` → `http.response.status_code`, `HttpAttributes.HTTP_ROUTE` → `http.route`, `UrlAttributes.URL_SCHEME` → `url.scheme`, `ServerAttributes.SERVER_ADDRESS` → `server.address`, `ErrorAttributes.ERROR_TYPE` → `error.type` |
| `http.server.active_requests` | Gauge | `server.name`, `server.port`, `http.request.method`, `http.route`, `url.scheme`, `server.address` |

`http.response.status_code` is the code of the response that was sent (`response.code()`, part of
the `DurationKey` the timer is cached by), so every distinct status code of a route is its own series.
The active-requests gauge has no status code — the request has not finished.

```promql
# 5xx ratio
  sum(rate(http_server_request_duration_seconds_count{http_response_status_code=~"5.."}[5m]))
/ sum(rate(http_server_request_duration_seconds_count[5m]))

# requests that ended in an exception, whatever status was mapped
  sum(rate(http_server_request_duration_seconds_count{error_type!=""}[5m]))
```

`error.type` is `""` on success and the exception's canonical class name on failure;
`CompletionException` is unwrapped to its cause first. `http.route` falls back to the literal
`UNKNOWN_ROUTE` when no route template matched (404s, malformed paths) — a useful bounded bucket
rather than raw paths.

`server.name` is the transport name given to the factory module: `kora-undertow` for the public
server, `kora-undertow-system` for the system server.

---

## HTTP client { #http-client }

Registered by `DefaultHttpClientMetricsFactory`. Config root `httpClient.<name>`, where `<name>` is
the `@HttpClient("name")` value.

| Meter | Type | Tags |
|---|---|---|
| `http.client.request.duration` | Timer (SLO buckets) | `http.request.method`, `HttpAttributes.HTTP_RESPONSE_STATUS_CODE` → `http.response.status_code`, `server.address` (when the URI has a host), `server.port` (the URI port, else `80`/`443` by scheme; omitted when unknown), `url.scheme` (when present), `UrlIncubatingAttributes.URL_TEMPLATE` → `url.template` (the URI template — **not** `http.route`, which is a server-side attribute), `error.type`, plus `system.config`, `system.name.simple`, `system.name.canonical` |

Like the server timer, the client timer carries `http.response.status_code`.

The three `system.*` tags come from `DefaultHttpClientTelemetry`: the client's config path, its
simple class name and its canonical class name. They let you separate two clients that call the
same host.

---

## Database { #database }

Registered by `DefaultDatabaseMetricsFactory`, shared by JDBC and Cassandra. Config roots `jdbc`
and `cassandra`.

| Meter | Type | Tags |
|---|---|---|
| `db.client.operation.duration` | Timer (SLO buckets) | `DbIncubatingAttributes.DB_CLIENT_CONNECTION_POOL_NAME` → `db.client.connection.pool.name`, `DbAttributes.DB_SYSTEM_NAME` → `db.system.name`, `DbAttributes.DB_QUERY_TEXT` → `db.query.text`, `DbAttributes.DB_OPERATION_NAME` → `db.operation.name`, `error.type` |

`db.query.text` is the repository's *query id*, not the raw SQL, so it stays bounded.
`db.system.name` is derived from the JDBC URL (`jdbc:postgresql:…` → `postgresql`).

### Pool metrics

`jdbc.telemetry.metrics.driverMetrics` defaults to **`true`** and makes `JdbcDataSource` call
`dataSource.setMetricRegistry(telemetry.meterRegistry())`, which is what produces Hikari's own
`hikaricp_*` series.

But when `jdbc.telemetry.metrics.enabled` is `false` (the default), the factory returns
`NoopDatabaseTelemetry`, whose `meterRegistry()` is the `NoopMeterRegistry` — so Hikari is handed a
registry that discards everything. **`driverMetrics = true` alone gives you no pool metrics;**
`jdbc.telemetry.metrics.enabled = true` is the prerequisite.

Cassandra behaves the same way through `CassandraSessionBuilderUtils`.

---

## Kafka { #kafka }

Config roots are the paths you pass to `@KafkaListener("path")` and `@KafkaPublisher("path")`.

### Consumer — `DefaultKafkaConsumerMetricsFactory`

| Meter | Type | Tags |
|---|---|---|
| `messaging.process.duration` | Timer (SLO buckets) | `MESSAGING_SYSTEM` → `messaging.system` (= `kafka`), `MESSAGING_OPERATION_NAME` → `messaging.operation.name` (= `process`), `MESSAGING_CLIENT_ID`, `MESSAGING_CONSUMER_GROUP_NAME`, `system.config`, `system.name.simple`, `system.name.canonical`, `error.type`, `MESSAGING_DESTINATION_NAME`, `MESSAGING_DESTINATION_PARTITION_ID` |
| `messaging.process.batch.duration` | Timer (SLO buckets) | as above **without** destination/partition |
| `messaging.kafka.consumer.lag` | Gauge | `messaging.system`, client id, consumer group, the three `system.*` tags, destination name, partition id |

### Publisher — `DefaultKafkaPublisherMetricsFactory`

| Meter | Type | Tags |
|---|---|---|
| `messaging.client.operation.duration` | Timer (SLO buckets) | `messaging.system` (= `kafka`), `MESSAGING_CLIENT_ID`, `messaging.operation.name` (= `send`), `MESSAGING_OPERATION_TYPE` (= `send`), the three `system.*` tags, `error.type`, destination name, partition id |
| `messaging.client.sent.messages` | Counter | same tag set |

Both sides also expose the Kafka driver's own meters when
`telemetry.metrics.driverMetrics = true` — default **`false`** for Kafka, unlike JDBC.

---

## gRPC { #grpc }

| Meter | Type | Config root | Tags |
|---|---|---|---|
| `rpc.server.call.duration` | Timer (SLO buckets) | `grpcServer` | `server.name`, `server.port`, `RPC_SYSTEM_NAME` → `rpc.system.name` (= `grpc`), `RPC_SERVICE`, `RPC_METHOD`, `RPC_RESPONSE_STATUS_CODE` → `rpc.response.status_code`, `error.type` |
| `rpc.client.call.duration` | Timer (SLO buckets) | `grpcClient.<ServiceSimpleName>` | `rpc.system.name` (= `grpc`), `rpc.service`, `rpc.method`, `rpc.response.status_code`, `server.address`, `server.port`, `error.type` |

`rpc.response.status_code` is the `io.grpc.Status.Code` **name** (`OK`, `UNAVAILABLE`, …), not the
numeric code. `error.type` is `""` on success and the exception's canonical class name otherwise.

`rpc.server.requests_per_rpc` / `rpc.server.responses_per_rpc` and their client counterparts
**do not exist in Kora 2.0** — no source registers them.

---

## Cache { #cache }

Registered by `DefaultRedisCacheMetricsFactory`. Config root is the `@Cache("path")` value.
`DefaultCaffeineCacheMetricsFactory` exists but `DefaultCaffeineCacheTelemetry` never calls it, so a
Caffeine cache publishes only Micrometer's binder meters (below), not these two.

| Meter | Type | Tags |
|---|---|---|
| `cache.operation.duration` | Timer (SLO buckets) | `system.config`, `system.name.simple`, `system.name.canonical`, `cache.origin` (= `redis`), `cache.operation`, `error.type` |
| `cache.requests` | Counter | `system.config`, `system.name.simple`, `system.name.canonical`, `cache.origin`, `cache.operation`, `cache.result` |

`cache.operation` is the cache operation enum name (`GET`, `PUT`, …); `cache.result` on
`cache.requests` is the hit/miss discriminator. Both are bounded. Hit ratio:
`sum(rate(cache_requests_total{cache_result="hit"}[5m])) / sum(rate(cache_requests_total[5m]))`.

A **Caffeine** cache with `telemetry.metrics.enabled = true` is additionally built with
`recordStats()` and bound once through Micrometer's `CaffeineCacheMetrics.monitor(...)`
(`CaffeineFactory`), which publishes Micrometer's cache binder meters — `cache.gets`, `cache.puts`,
`cache.evictions`, `cache.eviction.weight`, `cache.size` — with the `@Cache` config path as the cache
name and the component's `telemetry.metrics.tags`. Their exact names and tags are Micrometer's.

---

## Scheduling { #scheduling }

Registered by `DefaultSchedulingMetricsFactory`. Telemetry config root `scheduling.telemetry`.

| Meter | Type | Tags |
|---|---|---|
| `scheduling.job.duration` | Timer (SLO buckets) | `scheduling.system` (`jdk` \| `quartz` \| `dbscheduler`), `CodeAttributes.CODE_FUNCTION_NAME` → `code.function.name` (the job name), `system.config` (when the job has a config path), `system.name.simple`, `system.name.canonical`, `error.type` |

---

## Resilience { #resilience }

Registered by the `Default*MetricsFactory` classes under `resilient/resilient-kora`. Global
telemetry root `resilient.telemetry`, merged with the per-operation
`resilient.<kind>.<name>.telemetry` section (operation values win over global ones).

| Meter | Type | Tags |
|---|---|---|
| `resilient.circuitbreaker.state` | Gauge | `resilient.name` |
| `resilient.circuitbreaker.transition` | Counter | `resilient.name`, `resilient.state` |
| `resilient.circuitbreaker.call.acquire` | Counter | `resilient.name`, `resilient.state`, `resilient.status` (the `CallAcquireStatus` enum name) |
| `resilient.circuitbreaker.call.result` | Counter | `resilient.name`, `resilient.state`, `resilient.status` (the `CallResult` enum name) |
| `resilient.retry.attempts` | Counter | `resilient.name` |
| `resilient.retry.exhausted` | Counter | `resilient.name`, `resilient.reason` (the `StopReason` enum name) |
| `resilient.timeout.exhausted` | Counter | `resilient.name` |
| `resilient.ratelimiter.acquire` | Counter | `resilient.name`, `resilient.status` |
| `resilient.fallback.attempts` | Counter | `resilient.name`, `resilient.type` |

Every resilience tag is prefixed with `resilient.` (Prometheus label `resilient_name`, …), so it never
collides with a common tag such as `name`.

`resilient.circuitbreaker.state` encodes the state numerically. Its description, verbatim from
source: `Circuit Breaker state metrics, where 0 -> CLOSED, 1 -> HALF_OPEN, 2 -> OPEN`.
Only one gauge exists per breaker `resilient.name` — the value is mutated, not re-registered per state.

`resilient.circuitbreaker.transition` is incremented **only** on a transition to `OPEN` or
`HALF_OPEN`, never on the return to `CLOSED`. `resilient.circuitbreaker.call.acquire` is
incremented only in `HALF_OPEN` (any status) and in `OPEN` when the call is `REJECTED` — so it is a
rejection/probe counter, not a total-calls counter. Use `resilient.circuitbreaker.call.result` for
per-call outcomes.

`resilient.circuitbreaker.call.result` and `resilient.ratelimiter.acquire` are new in 2.0.
Note that resilience **tracing** is off by default too: each `*TracingConfig` overrides
`enabled()` to `false`.

---

## S3, SOAP, JMS, Redis { #s3-soap-jms-redis }

| Meter | Type | Emitted by | Distinguishing tags |
|---|---|---|---|
| `rpc.client.call.duration` | Timer | `DefaultAwsS3ClientMetricsFactory` | `rpc.system.name` = **`s3`**, `rpc.method` (operation), `AwsIncubatingAttributes.AWS_S3_BUCKET`, `error.type`, the three `system.*` tags (`system.config` is the client's config path) |
| `rpc.client.call.duration` | Timer | `DefaultS3ClientMetricsFactory` (declarative client) | `rpc.system.name` = **`s3`**, same shape |
| `rpc.client.call.duration` | Timer | `DefaultSoapClientMetricsFactory` | `rpc.system.name` = **`soap`**, `rpc.service`, `rpc.method`, `server.address`, `server.port`, `http.response.status_code`, `error.type`, `soap.fault.code`, the three `system.*` tags |
| `messaging.process.duration` | Timer | `DefaultJmsConsumerMetricsFactory` | `messaging.system` = `jms`, `messaging.operation.name` = `process`, `MESSAGING_DESTINATION_NAME`, `error.type` |
| `db.client.operation.duration` | Timer | `DefaultLettuceTelemetry` (command completion) | `db.system.name` = `redis`, `db.operation.name` (the command), `server.address`, `server.port`, `lettuce.type`, `error.type` (the Redis error prefix such as `ERR` / `MOVED` / `WRONGTYPE`, not the full message); config root `lettuce` |
| `lettuce.command.firstresponse.duration` | Timer | `DefaultLettuceTelemetry` | same tags; config root `lettuce` |

The two S3 clients and SOAP share the meter name `rpc.client.call.duration` with gRPC; both S3
clients now report `rpc.system.name = s3`, so tell them apart by `system_config` /
`system_name_simple`, and **always filter by `rpc_system_name`** so S3, SOAP and gRPC latency are not
aggregated together. Likewise `db.client.operation.duration` is shared by JDBC, Cassandra and Lettuce
(split by `db_system_name`), and `messaging.process.duration` by Kafka and JMS (split by
`messaging_system`). `s3.client.duration` and `s3.kora.client.duration` from 1.x no longer exist.

---

## Framework, JVM and system { #framework-jvm-and-system }

`PrometheusMeterRegistryWrapper.init()` registers exactly one Kora meter and binds exactly seven
Micrometer binders — nothing else:

| Meter | Type | Tags |
|---|---|---|
| `kora.up` | Gauge, constant `1` | `version` — read from the classpath resource `META-INF/kora/version/common`, or `UNKNOWN` |

| Micrometer binder (all from `io.micrometer.core.instrument.binder`) | Covers |
|---|---|
| `ClassLoaderMetrics` | loaded/unloaded classes |
| `JvmMemoryMetrics` | heap and non-heap pools, buffers |
| `JvmGcMetrics` | GC pauses and allocation |
| `ProcessorMetrics` | CPU count / usage / load average |
| `JvmThreadMetrics` | live, daemon, peak, per-state thread counts |
| `FileDescriptorMetrics` | open / max file descriptors |
| `UptimeMetrics` | process uptime and start time |

The exact series each binder emits is defined by Micrometer `1.17.1`, not by Kora — check
[the Micrometer JVM/system binder docs](https://docs.micrometer.io/micrometer/reference/reference/jvm.html)
or read your own `/metrics`. The migrated observability guide's smoke test confirms
`jvm_memory_used_bytes` and `process_cpu_usage` in real 2.0 output.

Kora binds **no** Logback metrics binder. `logback_events_total` appears only if your application
registers `LogbackMetrics` itself.

`kora.up` is the cheapest liveness signal in a dashboard, and its `version` label is the fastest way
to see which Kora build a pod is actually running.

---

## Renamed and removed relative to 1.x { #renamed-and-removed-relative-to-1x }

Do not port a 1.x metric list. What changed:

| 1.x | 2.0 |
|---|---|
| `metrics { opentelemetrySpec = "V120" \| "V123" }` | **removed** — one fixed scheme; the global `metrics` section holds only `enabled` and `tags` |
| `db.client.request.duration` (`V123`) | **`db.client.operation.duration`** |
| tags `db.pool.name`, `db.statement`, `db.operation` | **`db.client.connection.pool.name`, `db.system.name`, `db.query.text`, `db.operation.name`** |
| `cache.duration` | **`cache.operation.duration`** |
| `messaging.receive.duration` | **`messaging.process.duration`** (Kafka and JMS) |
| `messaging.publish.duration` | **`messaging.client.operation.duration`** + **`messaging.client.sent.messages`** |
| `s3.client.duration`, `s3.kora.client.duration` | **`rpc.client.call.duration`** with `rpc.system.name` = `s3` |
| `rpc.server.duration`, `rpc.client.duration` (2.0 RC1) | **`rpc.server.call.duration`**, **`rpc.client.call.duration`**, tag `rpc.system` → `rpc.system.name` (2.0.0.RC2, #972) |
| `cache.ratio` with tags `origin`/`operation`/`type` (2.0 RC1) | **`cache.requests`** with `cache.origin`/`cache.operation`/`cache.result` (RC2) |
| resilience tags `name`/`state`/`status`/`reason`/`type` (2.0 RC1) | **`resilient.*`**-prefixed (RC2) |
| `lettuce.command.completion.duration` (2.0 RC1) | **`db.client.operation.duration`** with `db.system.name = redis` (RC2) |
| `rpc.*.requests_per_rpc`, `rpc.*.responses_per_rpc` | **removed** |
| `rpc.status` on gRPC | **`rpc.response.status_code`** (`RpcIncubatingAttributes.RPC_RESPONSE_STATUS_CODE`, the status code *name*) |
| — | **new:** `resilient.circuitbreaker.call.result`, `resilient.ratelimiter.acquire` |

---

## Naming your own metrics { #naming-your-own-metrics }

Match the framework style so your dashboards read consistently:

| Pattern | Example | Type |
|---|---|---|
| `<noun>.<action>.duration` | `user.creation.duration` | Timer |
| `<noun>.<action>.total` | `user.creation.total` | Counter |
| `<noun>.<attribute>` | `payment.amount` | DistributionSummary with `baseUnit(...)` |

Dots as separators, `.duration` for latencies, `.total` for monotonic counts, `baseUnit(...)` for
size summaries. See [custom-metrics-reference.md](custom-metrics-reference.md).

---

## References

- [Micrometer concepts](https://docs.micrometer.io/micrometer/reference/concepts.html)
- [OpenTelemetry semantic conventions](https://opentelemetry.io/docs/specs/semconv/)
- [Prometheus naming practices](https://prometheus.io/docs/practices/naming/)
