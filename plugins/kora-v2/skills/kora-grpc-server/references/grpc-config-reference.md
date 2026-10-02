# gRPC Server Configuration Reference — Kora 2.0

**Config interfaces (authority):** [`GrpcServerConfig`](https://github.com/kora-projects/kora/blob/2.0.0.RC2/grpc/grpc-server/src/main/java/io/koraframework/grpc/server/GrpcServerConfig.java) · [`GrpcServerTelemetryConfig`](https://github.com/kora-projects/kora/blob/2.0.0.RC2/grpc/grpc-server/src/main/java/io/koraframework/grpc/server/telemetry/GrpcServerTelemetryConfig.java) · [`TelemetryConfig`](https://github.com/kora-projects/kora/blob/2.0.0.RC2/telemetry/telemetry-common/src/main/java/io/koraframework/telemetry/common/TelemetryConfig.java)
**Migrated configs:** [`kora-java-grpc-server/application.conf`](https://github.com/kora-projects/kora-examples/blob/migration/2.0/examples/java/kora-java-grpc-server/src/main/resources/application.conf) · [`kora-java-guide-grpc-server-advanced-app/application.conf`](https://github.com/kora-projects/kora-examples/blob/migration/2.0/guides/java/kora-java-guide-grpc-server-advanced-app/src/main/resources/application.conf)

## Contents

1. Section name
2. Server properties
3. Telemetry properties and their real defaults
4. What the module actually emits
5. Full HOCON / YAML
6. Multiple gRPC servers
7. Common issues

---

## 1. Section name

`GrpcServerModule` builds `new GrpcServerFactoryModule("kora-grpc", "grpcServer")`, so the config
path is **`grpcServer`** and the telemetry component name is **`kora-grpc`** (it appears as the
`server.name` metric tag and the `serverName` log field).

The section is read with `mapper.mapOrThrow(config.get("grpcServer"))`. Every key below has a
default, so an app with no `grpcServer` section at all still starts — on port `8090`, with logging
and metrics off.

## 2. Server properties

Declared on `GrpcServerConfig`; the defaults are the interface's `default` method bodies.

| Property | Type | Default | Notes |
|---|---|---|---|
| `port` | `int` | **`8090`** | |
| `reflectionEnabled` | `boolean` | **`false`** | also needs `io.grpc:grpc-services` on the classpath, or it is ignored silently |
| `maxMessageSize` | `io.koraframework.common.util.Size` | **`4MiB`** | applied as `maxInboundMessageSize`; accepts `4MiB` / `4MB` / `1000Kb` / a byte count |
| `shutdownWait` | `Duration` | **`30s`** | graceful-shutdown grace period before `shutdownNow()` |
| `maxConnectionAge` | `Duration` (nullable) | **unset** | applied only when present; ±10% jitter |
| `maxConnectionAgeGrace` | `Duration` (nullable) | **unset** | applied only when present |
| `keepAliveTime` | `Duration` (nullable) | **unset** | interval between PING frames |
| `keepAliveTimeout` | `Duration` (nullable) | **unset** | PING acknowledgement timeout |
| `telemetry` | `GrpcServerTelemetryConfig` | see §3 | |

> The four connection-age / keep-alive keys are genuinely **nullable**, not `0s`. The module tests
> `if (config.maxConnectionAge() != null)` before applying each one. Writing `"0s"` does not mean
> "unlimited" — it sets an actual zero-length age. Omit the key instead.

`Size` lives in **`io.koraframework.common.util.Size`** in 2.0 (core `common`, not the config
package).

## 3. Telemetry properties and their real defaults

`GrpcServerTelemetryConfig extends TelemetryConfig`; the framework-wide `TelemetryConfig` defaults
apply verbatim, and the logging section adds one key, `maskHeaders`:

| Property | Type | Default | |
|---|---|---|---|
| `telemetry.logging.enabled` | `boolean` | **`false`** | ⚠ off |
| `telemetry.logging.maskHeaders` | `Set<String>` | `["authorization", "cookie", "set-cookie"]` | metadata keys whose values are masked in logs |
| `telemetry.metrics.enabled` | `boolean` | **`false`** | ⚠ off |
| `telemetry.metrics.slo` | `Duration[]` | `1, 10, 50, 100, 200, 500, 1000, 2000, 5000, 10000, 20000, 30000, 60000, 90000` ms | |
| `telemetry.metrics.tags` | `Map<String,String>` | `{}` | added to every metric |
| `telemetry.tracing.enabled` | `boolean` | **`true`** | on |
| `telemetry.tracing.attributes` | `Map<String,String>` | `{}` | added to every span |

**Logging and metrics are off by default in Kora 2.0.** Any example that claims to demonstrate
request logs or `rpc_server_call_duration` must enable them explicitly — this is the single most common
"it worked in 1.x" surprise on this module, because 1.x defaulted metrics to `true`.

Enablement is also gated on the corresponding component being in the graph:
`DefaultGrpcServerTelemetryFactory` computes `traceEnabled = tracer != null && config.tracing().enabled()`
and `metricEnabled = meterRegistry != null && config.metrics().enabled()`. So metrics need
`io.koraframework:micrometer-module` **and** the flag; tracing needs `opentelemetry-tracing` **and**
the flag. With all three subsystems off the module installs `NoopGrpcServerTelemetry` and the
interceptor costs nothing.

## 4. What the module actually emits

### Metrics — one

| Name | Micrometer type | Prometheus |
|---|---|---|
| `rpc.server.call.duration` | `Timer` (with the configured SLO boundaries) | `rpc_server_call_duration_seconds*` |

Tags on every sample:

| Tag | Value |
|---|---|
| `server.name` | `kora-grpc` |
| `server.port` | the configured port |
| `rpc.system.name` | `grpc` |
| `rpc.service` | the proto service name |
| `rpc.method` | the RPC method name |
| `rpc.response.status_code` | the `io.grpc.Status.Code` **name** (`OK`, `NOT_FOUND`, `UNAVAILABLE`, …) |
| `error.type` | `""` on success, otherwise the canonical class name of the exception that ended the call |
| …plus every entry of `telemetry.metrics.tags` | |

> There is **no** `rpc.server.requests_per_rpc` and **no** `rpc.server.responses_per_rpc` in Kora
> 2.0. `rpc.server.call.duration` is the only meter this module registers. 2.0.0.RC1 named it
> `rpc.server.duration` with tags `rpc.system` / numeric `rpc.grpc.status_code`; RC2 (#972) renamed
> them — update RC1 dashboards.

### Tracing

One `SERVER` span per call, named `<service>/<method>`. The parent context is extracted from the
call metadata with the W3C trace-context propagator, and the outgoing headers are injected on
response. Attributes: `server.port`, `server.name`, `rpc.system.name`, `rpc.service`, `rpc.method`,
`network.peer.address`, `rpc.response.status_code` (code name) on close, `error.type` when an exception
ended the call, plus every entry of
`telemetry.tracing.attributes`. A `rpc.message` span event is recorded per message.

### Logging

Two loggers, both under the `GrpcServer` canonical name:

| Logger | Level | Message | Structured key |
|---|---|---|---|
| `io.koraframework.grpc.server.GrpcServer.request` | `INFO` | `GrpcCall received` | `grpcRequest` |
| `io.koraframework.grpc.server.GrpcServer.response` | `INFO` (`WARN` on error) | `GrpcCall responded` | `grpcResponse` |

Field detail scales with the logger level:

- `INFO` — `serverName`, `serverPort`, `serviceName`, `operation`, and on the response
  `processingTime` (ms), `status`, `exceptionType`.
- `DEBUG` on the request logger — adds `headers` (the request metadata, one `key: value` line per
  value; `-bin` values Base64-encoded), with the `maskHeaders` keys masked.
- `TRACE` on either logger — adds `body` (the protobuf message rendered via
  `DefaultGrpcServerBodyConverter`).

```hocon
logging.levels {
  "io.koraframework.grpc.server.GrpcServer.request" = "DEBUG"
  "io.koraframework.grpc.server.GrpcServer.response" = "DEBUG"
}
```

Bodies are protobuf payloads: turning on `TRACE` will put request and response contents into the
log stream **unmasked**. Do not do that on a service handling personal data unless you replace the
body converter (below).

### Log masking

| What | Selected by | Masked by | Default |
|---|---|---|---|
| Metadata values (`DEBUG`) | `telemetry.logging.maskHeaders` | `@Tag(GrpcServerTelemetry.class) MaskingStrategy` | `authorization`, `cookie`, `set-cookie` → `***` |
| Message bodies (`TRACE`) | — | a `DefaultGrpcServerBodyConverter` you provide | protobuf `toString()`, nothing masked |

- `maskHeaders` **replaces** its default — restate `authorization`, `cookie`, `set-cookie` next to
  your own keys. Keys are lower-cased before matching; gRPC metadata keys are lower-case anyway.
  A binary key (`x-token-bin`) is matched by its full name and the strategy receives the raw
  `byte[]`.
- There is no `mask` key; the replacement text is the `MaskingStrategy`
  (`io.koraframework.logging.common.masking`, tag
  `io.koraframework.grpc.server.telemetry.GrpcServerTelemetry`). A tagged component of your own
  replaces the module's `@DefaultComponent`:

```java
@Tag(GrpcServerTelemetry.class)
default MaskingStrategy grpcServerMaskingStrategy() {
    return new MaskingKeepLast("***", 4);
}
```

```kotlin
@Tag(GrpcServerTelemetry::class)
fun grpcServerMaskingStrategy(): MaskingStrategy = MaskingKeepLast("***", 4)
```

- Payloads are not run through a `DataMasker`. To redact them, subclass
  `DefaultGrpcServerBodyConverter` (`io.koraframework.grpc.server.telemetry.impl`) and override
  `convertRequestMessage(String service, String method, Metadata requestHeaders, @Nullable Object requestMessage)`
  and `convertResponseMessage(Object message)` — or the shared `convertMessage(@Nullable Object)` —
  then return it from a factory method typed `DefaultGrpcServerBodyConverter`; the telemetry
  factory picks it up. Returning `null` omits the body.

The shared masking model (`MaskingStrategy`, ready-made strategies, `DataMasker` for JSON/XML
payloads on other transports) is described in
[kora-aop-logging → masking](../../kora-aop-logging/references/logging-masking.md).

## 5. Full HOCON / YAML

===! `HOCON` — `application.conf`

```hocon
grpcServer {
  port = 8090                       # default 8090
  maxMessageSize = "4MiB"           # default 4MiB
  reflectionEnabled = false         # default false; also needs io.grpc:grpc-services
  shutdownWait = "30s"              # default 30s

  # Omit these four entirely unless you need them — they have no default and
  # "0s" is a literal zero, not "unlimited".
  # maxConnectionAge = "30m"
  # maxConnectionAgeGrace = "10s"
  # keepAliveTime = "1m"
  # keepAliveTimeout = "20s"

  telemetry {
    logging {
      enabled = true                # DEFAULT false — must be set explicitly
      maskHeaders = [ "authorization", "cookie", "set-cookie", "x-api-key" ]   # replaces the default set
    }
    metrics {
      enabled = true                # DEFAULT false — must be set explicitly
      slo = [ 1, 10, 50, 100, 200, 500, 1000, 2000, 5000, 10000, 20000, 30000, 60000, 90000 ]
      tags { "service" = "user-service" }
    }
    tracing {
      enabled = true                # default true
      attributes { "deployment.environment" = "prod" }
    }
  }
}

logging.levels {
  "ROOT" = "WARN"
  "io.koraframework" = "INFO"
}
```

=== `YAML` — `application.yaml`

```yaml
grpcServer:
  port: 8090
  maxMessageSize: "4MiB"
  reflectionEnabled: false
  shutdownWait: "30s"
  telemetry:
    logging:
      enabled: true       # DEFAULT false
      maskHeaders: [ "authorization", "cookie", "set-cookie", "x-api-key" ]
    metrics:
      enabled: true       # DEFAULT false
      slo: [ 1, 10, 50, 100, 200, 500, 1000, 2000, 5000, 10000, 20000, 30000, 60000, 90000 ]
      tags:
        service: user-service
    tracing:
      enabled: true
      attributes:
        deployment.environment: prod

logging:
  levels:
    ROOT: WARN
    io.koraframework: INFO
```

Externalise the port the way the migrated examples do:

```hocon
grpcServer.port = ${GRPC_PORT}      # required — startup fails if unset
grpcServer.port = 8090
grpcServer.port = ${?GRPC_PORT}     # optional override of the literal above
```

## 6. Multiple gRPC servers

`GrpcServerModule` wires exactly one server, on one config path. A second server means a second
`@FactoryModule` method that returns its own `GrpcServerFactoryModule` with a different config path
and a `@Tag`; the `@Tag(Tag.Factory.class)` claims inside then resolve to **that** tag, so its
handlers and interceptors must carry the same tag. This is not a pattern any migrated example
exercises — verify it against
[`GrpcServerFactoryModule`](https://github.com/kora-projects/kora/blob/2.0.0.RC2/grpc/grpc-server/src/main/java/io/koraframework/grpc/server/GrpcServerFactoryModule.java)
before relying on it.

## 7. Common issues

| Symptom | Cause | Fix |
|---|---|---|
| No `rpc_server_call_duration` metric | `telemetry.metrics.enabled` defaults to `false` | set it, and add `io.koraframework:micrometer-module` |
| No request/response logs | `telemetry.logging.enabled` defaults to `false` | set it |
| Metrics enabled but still nothing | no `MeterRegistry` in the graph | add `micrometer-module` |
| Server on 8090 when you configured something else | the key is under `grpcServer`, not a foreign `server.port` | fix the section name |
| `maxConnectionAge = "0s"` kills connections instantly | `0s` is a literal duration, not "unlimited" | remove the key |
| `Config expected value, but got null at path 'ROOT.grpcServer.port'` | `${GRPC_PORT}` substitution with the variable unset | export it, or use `${?GRPC_PORT}` over a literal default |
| `netty { threads = … }` has no effect | 2.0 serves gRPC over OkHttp | see [grpc-server-reference.md](grpc-server-reference.md) §7 for the real hook |
