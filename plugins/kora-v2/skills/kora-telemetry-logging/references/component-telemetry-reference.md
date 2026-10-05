# Component Telemetry Logging Reference

Kora components (HTTP server/client, JDBC, Kafka, gRPC, cache, scheduling, S3, SOAP, resilience)
emit their own log records through SLF4J. Whether you see them depends on **two independent
switches**, both verified in the framework source.

## Contents

- [The two switches](#the-two-switches)
- [Config paths per component](#config-paths-per-component)
- [Logger names per component](#logger-names-per-component)
- [Level ladders](#level-ladders)
- [Masking and body-size options](#masking-and-body-size-options)
- [Recipes](#recipes)

## The two switches

### Switch 1 — `<path>.telemetry.logging.enabled`

```java
// telemetry/telemetry-common/.../TelemetryConfig.java
@ConfigMapper
interface LoggingConfig {
    default boolean enabled() { return false; }   // ← FALSE
}
```

Every component telemetry factory consults it when building its telemetry, e.g.

```java
// http/http-server-common/.../DefaultHttpServerTelemetryFactory.java
if (config.logging().enabled()) {
    enabledLoggerFactory = this.loggerFactory != null ? this.loggerFactory : DefaultHttpServerLoggerFactory.INSTANCE;
} else {
    enabledLoggerFactory = NoopHttpServerLoggerFactory.INSTANCE;   // NOPLogger — writes nothing, ever
}
```

With `enabled = false` the component holds a `NOPLogger`. No SLF4J level, no appender, no pattern
can bring the records back.

Sibling defaults, so you do not generalise from one to another:
`TracingConfig.enabled()` → `true`, `MetricsConfig.enabled()` → `false`. The system HTTP server
overrides tracing to `false` under `httpServer.system`.

### Switch 2 — the SLF4J level of the component's own logger

Even with `enabled = true`, every logger guards itself. Example — the JDBC query logger:

```java
public void logQueryBegin(QueryContext query) {
    if (!this.logger.isDebugEnabled()) {
        return;                       // ← at INFO this returns immediately
    }
    …
}
```

So `jdbc.telemetry.logging.enabled = true` on its own yields nothing at the default `INFO`.
Both are required:

```hocon
jdbc {
  poolName = "kora"
  telemetry.logging.enabled = true
}

logging.levels {
  "io.koraframework.database.kora.query" = "DEBUG"
}
```

## Config paths per component

The path is the component's own config section; `telemetry.logging.enabled` hangs off it.

| Component | Config path root | Source |
|---|---|---|
| Public HTTP server | `httpServer` | `UndertowPublicHttpServerModule` → `new UndertowHttpServerFactoryModule("kora-undertow", "httpServer")` |
| System HTTP server | `httpServer.system` | `UndertowSystemHttpServerModule` → `("kora-undertow-system", "httpServer.system")` |
| Declarative HTTP client | `httpClient.<clientName>` — first letter lower-cased; `@HttpClient("my.path")` overrides | `ConfigModuleGenerator` → `configPath = "httpClient." + lowercaseName` |
| JDBC | `jdbc` | `JdbcDatabaseModule` → `new JdbcDatabaseFactoryModule("jdbc")` |
| Cassandra | `cassandra` | `CassandraDatabaseModule` → `new CassandraDatabaseFactoryModule("cassandra")` |
| Kafka listener | the `@KafkaListener("…")` value, e.g. `kafka.listener.user` | `KafkaConsumerConfigGenerator` → `config.get(configPath)` |
| Kafka publisher | the `@KafkaPublisher("…")` value, e.g. `kafka.publisher.task` | `KafkaPublisherGenerator` → `config.get(configPath)` |
| gRPC server | `grpcServer` | `GrpcServerModule` → `new GrpcServerFactoryModule("kora-grpc", "grpcServer")` |
| gRPC client | `grpcClient.<ServiceSimpleName>` | `GrpcClientConfig` → `config.get("grpcClient." + serviceSimpleName)` |
| SOAP client | `soapClient.<serviceName>` | `SoapClientImplGenerator` → `configPath = "soapClient." + serviceName` |
| Cache | the `@Cache("…")` value, e.g. `pet-cache` | `CacheAnnotationProcessor` → `config.get(configPath)` |
| Scheduling | `scheduling.telemetry` (one section for all jobs) | `SchedulingModule` → `config.get("scheduling.telemetry")` |
| Resilience | `resilient.telemetry` (one section for all aspects) | `ResilientModule` → `config.get("resilient.telemetry")` |
| S3 (AWS SDK) | `s3client.aws` | `AwsS3ClientModule` → `new AwsS3ClientFactoryModule("s3client.aws")` |
| S3 (declarative) | `s3` | `KoraS3ClientModule` → `new S3FactoryModule("s3")` |
| Lettuce (Redis) | `lettuce` | `LettuceModule` → `new LettuceFactoryModule("lettuce")` |

Scheduling and resilience take their telemetry config from a **single** section, so
`scheduling.telemetry.logging.enabled = true` turns logging on for every job at once, and
`resilient.telemetry.logging.enabled = true` for every retry / circuit breaker / timeout /
rate limiter / fallback.

## Logger names per component

These are the names you put on the left of a `logging.levels` entry.

| Component | Logger name(s) |
|---|---|
| HTTP server | `io.koraframework.http.server.common.HttpServer.request`, `…HttpServer.response` |
| HTTP client | `<client interface canonical name>.request`, `…​.response` — e.g. `com.example.PetApi.request` |
| SOAP client | `<client canonical name>.request`, `…​.response` |
| JDBC | `io.koraframework.database.<jdbc.poolName>.query` |
| Cassandra | `io.koraframework.database.<cassandra.basic.sessionName>.query` — defaults to `io.koraframework.database.cassandra.query` |
| Kafka listener | `<listener class canonical name>` |
| Kafka publisher | `<publisher interface canonical name>` |
| gRPC server | `io.koraframework.grpc.server.GrpcServer.request`, `…GrpcServer.response` |
| gRPC client | `<gRPC service name>.request`, `…​.response` — `ServiceDescriptor.getName()`, i.e. the name from the `.proto` (`example.PetService`), not a Java class |
| Cache (Caffeine / Redis) | `<cache interface canonical name>` |
| Scheduling | `<job name>` |
| S3 (both clients) | `<client canonical name>` |
| JMS | `io.koraframework.jms.consumer.<queueName>` |
| Retry | `io.koraframework.resilient.retry.Retry.<name>` |
| Circuit breaker | `io.koraframework.resilient.circuitbreaker.CircuitBreaker.<name>` |
| Timeout | `io.koraframework.resilient.timeout.Timeouter.<name>` |
| Rate limiter | `io.koraframework.resilient.ratelimiter.RateLimiter.<name>` |
| Fallback | `io.koraframework.resilient.fallback.annotation.Fallback.<name>` |

Because most client/listener/cache loggers are named after **your own** class, a blanket
`"io.koraframework" = "DEBUG"` does not raise them — you must name your own package.

## Level ladders

The level does not just gate the record, it selects **how much** goes into it.

### HTTP server (`DefaultHttpServerLoggerFactory`)

| Level of `…HttpServer.request` | Request record |
|---|---|
| below `INFO` | nothing |
| `INFO` | `serverName`, `serverPort`, `authority`, `operation` |
| `DEBUG` | + `queryParams`, `headers` (masked) |
| `TRACE` | + `body`, and `operation` uses the full path instead of the route template |

| Level of `…HttpServer.response` | Response record |
|---|---|
| below `WARN` | nothing |
| `WARN` | failed responses only (logged `atWarn`, with the stack trace when `stacktrace = true`) |
| `INFO` | + successful responses: `resultCode`, `processingTime` (ms), `statusCode` |
| `DEBUG` | + `headers` (masked) |
| `TRACE` | + `body` |

The HTTP client ladder is the same shape, on `<client>.request` / `<client>.response`, except that
the response record needs `INFO` (not `WARN`) and errors go through a separate `logError` at `WARN`.

### Other components

| Component | `TRACE` | `DEBUG` | `INFO` | `WARN` |
|---|---|---|---|---|
| JDBC / Cassandra query | + the `sql` text | "Executing query" / "Query executed" with `pool`, `operation`, `queryId`, `processingTime` | — | "Query failed" with `exceptionType` |
| Kafka listener | poll start, per-record details of the whole batch, + record headers (masked), key and value | record start / record end, batch received | poll end | poll or record failure |
| Kafka publisher | transaction offsets | record start, tx commit / rollback / end | record published | publish or tx failure |
| gRPC server | + request/response message bodies | + headers | request and successful response | failed response |
| Scheduling job | — | job start | job finished | job failed |
| Cache | operation start and completion, with `retrieved` / `missed` counts | nothing on its own — the completion record is written `atTrace()`/`atDebug()` but is gated by `isTraceEnabled()` | — | operation failed |
| Retry | retry loop start | retry attempts with delay | — | retries exhausted |

## Masking and body-size options

`HttpServerTelemetryConfig.HttpServerLoggingConfig` (and the matching client config) adds these
next to `enabled`:

| Key | Default | Meaning |
|---|---|---|
| `stacktrace` | `true` | Attach the exception stack trace to the failed-response record (server) |
| `maskHeaders` | `["authorization", "cookie", "set-cookie"]` | Header names whose values are masked (matched case-insensitively) |
| `maskQueries` | `[]` | Query parameter names whose values are masked |
| `pathFull` | unset (`@Nullable Boolean`) | Force the full path into `operation`; unset means "full path only at `TRACE`" |
| `maxRequestBodyLogSize` | `2 MiB` | Cap on the logged request body |
| `maxResponseBodyLogSize` | `2 MiB` | Cap on the logged response body |

gRPC server/client and Kafka listener/publisher logging configs carry `maskHeaders` with the same
default. There is **no `mask` key**: the replacement comes from a `MaskingStrategy` component
tagged with the transport's telemetry class (`@Tag(HttpServerTelemetry.class)`,
`@Tag(HttpClientTelemetry.class)`, …), whose default writes `***`. HTTP bodies and Kafka consumer
keys/values are masked only when a `DataMasker` component with the same tag is registered — none is
by default. The shared model, the tag table and examples are in the canonical
[logging-masking.md](../../kora-aop-logging/references/logging-masking.md); transport specifics are
in each transport skill.

```hocon
httpServer.telemetry.logging {
  enabled = true
  maskHeaders = ["authorization", "cookie", "set-cookie", "x-api-key"]
  maskQueries = ["token"]
  maxRequestBodyLogSize = "64KiB"
}
```

The HTTP **client** config additionally allows per-operation overrides that fall back to the
client-level values (`HttpClientOperationTelemetryConfig`); an unset operation value inherits, it
does not reset to the type default.

## Recipes

**"I enabled telemetry logging and still see nothing."** Check both switches, in this order:
the `enabled` key is under the component's own path (not under `logging`), and the logger name
from the table above is at the level that record uses.

**"I want HTTP request/response lines and nothing else."**

```hocon
httpServer.telemetry.logging.enabled = true

logging.levels {
  "ROOT" = "WARN"
  "io.koraframework.http.server.common.HttpServer.request" = "INFO"
  "io.koraframework.http.server.common.HttpServer.response" = "INFO"
}
```

**"I want SQL text in the log while debugging an integration test."**

```hocon
jdbc.telemetry.logging.enabled = true

logging.levels {
  "io.koraframework.database.kora.query" = "TRACE"
}
```

`TRACE` writes the raw SQL. Do not ship it — statement text routinely contains business data.

**"I want request bodies for one HTTP client only."**

```hocon
httpClient.petApi.telemetry.logging.enabled = true

logging.levels {
  "com.example.PetApi.request" = "TRACE"
}
```
