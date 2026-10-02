# Configuration Reference

Three config sections belong to the HTTP server, and 1.x used different names for most of them.

| Section | Bound by | Contents |
|---|---|---|
| `httpServer` | `UndertowPublicHttpServerModule` | the public application server |
| `httpServer.system` | `UndertowSystemHttpServerModule` | probes and metrics |
| `httpServer.undertow` | `UndertowSystemHttpServerModule` | transport tuning, shared by both servers |

## Contents

- [Port migration from 1.x — silent failure](#port-migration-from-1x--silent-failure)
- [httpServer](#httpserver)
- [httpServer.system](#httpserversystem)
- [httpServer.undertow](#httpserverundertow)
- [Telemetry](#telemetry)
- [Log masking](#log-masking)
- [Environment substitution](#environment-substitution)
- [Full key rename table](#full-key-rename-table)

---

## Port migration from 1.x — silent failure

```hocon
# Kora 1.x                          # Kora 2.0
httpServer {                        httpServer {
  publicApiHttpPort = 8080            port = 8080
  privateApiHttpPort = 8085           system.port = 8085
}                                   }
```

A stale 1.x key is simply an **unrecognised HOCON key**. It is ignored without a warning, so each
server falls back to its own default:

- `HttpServerConfig.port()` → **8080**
- `SystemHttpServerConfig.port()` **overrides it** → **8085**

So a service that deliberately ran on non-default ports comes up **green, on the wrong ports** —
the process is healthy, the logs are clean, and probes, scrapers and load balancers hit nothing.
This is the dangerous case, and it is easy to miss precisely because nothing fails.

`Address already in use` only appears in the narrower situation where stale keys collapse both
servers onto one port.

> Older migration notes claim `SystemHttpServerConfig` inherits `port() = 8080` so both servers
> collide. That describes a pre-release alpha; every 2.0 release carries the override to `8085`.
> Do not repeat the "both bind 8080" story.

**Verify after migrating** rather than trusting a clean startup: `curl` the public port and
`GET /system/readiness` on the system port and check both answer.

---

## httpServer

Every key below exists on `HttpServerConfig`; defaults are the interface's default methods.

```hocon
httpServer {
  port = 8080                        # default 8080
  ignoreTrailingSlash = false        # /path and /path/ as one route
  socketReadTimeout = "0s"           # zero disables
  socketWriteTimeout = "0s"          # zero disables
  socketKeepAliveEnabled = false
  headerKeepAliveEnabled = false     # always send Connection: keep-alive
  headerServerNameEnabled = false    # send `Server: Kora`
  headerServerDateEnabled = true     # send `Date`
  shutdownWait = "30s"               # graceful shutdown grace period
  maxRequestBodySize = "256MiB"

  telemetry { … }                    # see below
}
```

There is **no** `virtualThreadsEnabled` key. Kora 2.0 always dispatches requests onto virtual
threads (`KoraVirtualThreadPerConnectionDispatchHttpHandler`); the 1.x toggle no longer exists. Nor
are there `tls`, `cors` or `blockingThreads` keys — do not invent them.

### Response headers the server owns

| Key | Default | Effect |
|---|---|---|
| `headerServerNameEnabled` | **`false`** | When `true`, every response carries `Server: Kora`. Off by default so the stack is not advertised |
| `headerServerDateEnabled` | `true` | Undertow's `ALWAYS_SET_DATE`: a `Date` header on every response |
| `headerKeepAliveEnabled` | `false` | Undertow's `ALWAYS_SET_KEEP_ALIVE`: an explicit `Connection: keep-alive` header |

The `Server` value is fixed — there is no key for a custom name. A `server` header put on an
`HttpServerResponse` (or `HttpResponseEntity`) by a handler or interceptor is **dropped**, as are
`content-length` and `transfer-encoding`, and `content-type` when the body declares its own type.
The same keys exist under `httpServer.system`.

---

## httpServer.system

`SystemHttpServerConfig` extends `HttpServerConfig`, so every key above is also valid here, plus:

```hocon
httpServer.system {
  port = 8085                            # overridden default, NOT inherited 8080
  metricsPath   = "/metrics"
  readinessPath = "/system/readiness"
  livenessPath  = "/system/liveness"
}
```

| Endpoint | Default path | Served by |
|---|---|---|
| Metrics | `/metrics` | `MetricsHandler`, from the `MetricsScraper` in the graph |
| Readiness | `/system/readiness` | `ReadinessHandler`, over all `ReadinessProbe`s |
| Liveness | `/system/liveness` | `LivenessHandler`, over all `LivenessProbe`s |

Plugging `UndertowPublicHttpServerModule` into `@KoraApp` starts both servers — it extends
`UndertowSystemHttpServerModule`. There is no way to get the public server without the system one
via that module, and no `UndertowHttpServerModule` any more.

Server-scoped interceptors (`@Tag(HttpServer.class)`) do **not** apply to this server. Its router
is built by the `@SystemApi`-tagged factory module and therefore collects `@Tag(SystemApi.class)`
interceptors instead — a different tag, so probes and metrics run unintercepted. Restrict this port
with a network policy rather than trying to authenticate it.

---

## httpServer.undertow

Transport tuning moved out of `httpServer` into its own section, bound once and shared by both
servers (`UndertowConfig`):

```hocon
httpServer.undertow {
  ioThreads = 8                     # default: max(availableProcessors, 2)
  threadKeepAliveTimeout = "60s"
}
```

`ioThreads` and `threadKeepAliveTimeout` under `httpServer` directly are ignored — that is the
1.x location.

That is the whole transport surface: there is **no response-compression option** on either server
(`HttpServerConfig`, `SystemHttpServerConfig` and `UndertowConfig` have no such key, and the Undertow
handler chain has no encoding handler), so `/metrics` and every API response are sent uncompressed.
Compress at the reverse proxy or ingress.

---

## Telemetry

`logging.enabled` and `metrics.enabled` default to **`false`**. Component metrics such as
`http_server_*` simply do not appear until you switch them on. With metrics on, the timer
`http.server.request.duration` is tagged `server.name`, `server.port`, `http.request.method`,
`http.response.status_code`, `http.route` (the route template), `url.scheme`, `server.address` and
`error.type`; the gauge `http.server.active_requests` carries the same tags minus status and error.

**This is a change from 1.x, and it is silent.** In Kora 1.x `httpServer.telemetry.metrics.enabled`
defaulted to `true`, so a config that never mentioned metrics still produced them. In 2.0 the same
config produces none — dashboards and alerts go blank without a single error. Enable it explicitly:

```hocon
httpServer.telemetry {
  logging {
    enabled = true                  # default FALSE
    stacktrace = true
    maskQueries = [ ]
    maskHeaders = [ "authorization", "cookie", "set-cookie" ]
    maxRequestBodyLogSize  = "2MiB"
    maxResponseBodyLogSize = "2MiB"
    # pathFull — nullable Boolean, log the full path instead of the route template
  }
  metrics {
    enabled = true                  # default FALSE
    slo = [ "1ms", "10ms", "50ms", "100ms", "200ms", "500ms",
            "1s", "2s", "5s", "10s", "20s", "30s", "60s", "90s" ]
    tags { app = "my-service" }     # extra tags on every metric
  }
  tracing {
    enabled = true                  # default true on httpServer
    tracePathFull = true
    attributes { env = "prod" }     # extra attributes on every span
  }
}
```

`slo` is a `Duration[]` in 2.0 (it was a `double[]` in 1.x). `DurationConfigValueMapper` accepts
both a duration string (`"100ms"`) and a bare number, which it reads as **milliseconds**, so the
1.x millisecond form keeps working. What does not survive is a 1.x config written against
`OpentelemetrySpec.V123`, where the values were **seconds** (`0.001`, `0.010`, …): each truncates to
`Duration.ofMillis(0)` and the histogram silently collapses. `OpentelemetrySpec` is gone in 2.0.

**Tracing is the exception on the system server.** `SystemHttpServerTracingConfig` overrides
`enabled()` to `false`, so the "tracing defaults to true" rule does not hold under
`httpServer.system` — probe and metrics traffic is not traced unless you ask for it.

Any example claiming to demonstrate request logging or HTTP metrics must enable them explicitly.

---

## Log masking

Request/response logging (`telemetry.logging.enabled = true`) masks at three places. Config picks
**what** is masked; graph components tagged `@Tag(HttpServerTelemetry.class)`
(`io.koraframework.http.server.common.telemetry.HttpServerTelemetry`) decide **how**.

| What | Selected by | Masked by | Default |
|---|---|---|---|
| Header values (request and response, logged at `DEBUG`) | `logging.maskHeaders` | `@Tag(HttpServerTelemetry.class) MaskingStrategy` | `authorization`, `cookie`, `set-cookie` → `***` |
| Query parameter values (logged at `DEBUG`) | `logging.maskQueries` | the same `MaskingStrategy` | none |
| Request/response bodies (logged at `TRACE` only) | the body `Content-Type` → format `json` / `xml` / `form-urlencoded` | `@Tag(HttpServerTelemetry.class) DataMasker` whose `format()` matches | **none — the body is logged as is** |

- `maskHeaders` / `maskQueries` **replace** their defaults; restate `authorization`, `cookie`,
  `set-cookie` when you add a name. Names are compared lower-cased on both sides, so the case you
  write in config does not matter.
- There is **no `mask` key**. The replacement text comes from the `MaskingStrategy`, which receives
  the original value — so it can keep a prefix/suffix. `MaskingFull`, `MaskingKeepFirst` and
  `MaskingKeepLast` (`io.koraframework.logging.common.masking`) are ready-made strategies.
- Body maskers are picked by media type: `application/x-www-form-urlencoded` → `form-urlencoded`,
  `*/json` and `*+json` → `json`, `*/xml` and `*+xml` → `xml`. Other types (`text/plain`, binary)
  are never passed to a masker. One masker per format; the rules come from `MaskingPathRules`.

```java
@KoraApp
public interface Application extends HoconConfigModule, LogbackModule, JsonModule,
        UndertowPublicHttpServerModule {

    @Tag(HttpServerTelemetry.class)
    default MaskingStrategy httpServerMaskingStrategy() {
        return new MaskingKeepLast("***", 4);          // "Bearer eyJ…abcd" -> "***abcd"
    }

    @Tag(HttpServerTelemetry.class)
    default DataMasker httpServerJsonBodyMasker() {
        return new JsonDataMasker(MaskingPathRules.builder()
                .mask("password", new MaskingFull())
                .mask("card.number", new MaskingKeepLast())
                .build());
    }
}
```

```kotlin
@KoraApp
interface Application : HoconConfigModule, LogbackModule, JsonModule, UndertowPublicHttpServerModule {

    @Tag(HttpServerTelemetry::class)
    fun httpServerMaskingStrategy(): MaskingStrategy = MaskingKeepLast("***", 4)

    @Tag(HttpServerTelemetry::class)
    fun httpServerJsonBodyMasker(): DataMasker = JsonDataMasker(
        MaskingPathRules.builder()
            .mask("password", MaskingFull())
            .mask("card.number", MaskingKeepLast())
            .build()
    )
}
```

The tagged `MaskingStrategy` replaces the module's `@DefaultComponent`. `DataMasker`,
`JsonDataMasker`, `XmlDataMasker`, `FormUrlencodedDataMasker` live in
`io.koraframework.logging.common.masking.raw`; path syntax, fail-closed behaviour and size limits are
explained once in [kora-aop-logging → masking](../../kora-aop-logging/references/logging-masking.md).
For per-request selection, subclass `DefaultHttpServerBodyConverter`, override
`selectRequestDataMasker` / `selectResponseDataMasker`, and return it from a factory method typed
`DefaultHttpServerBodyConverter` — that replaces the module's `@DefaultComponent`.

---

## Environment substitution

HOCON substitution is unchanged from 1.x:

```hocon
httpServer {
  port = 8080
  port = ${?HTTP_PORT}                     # override when the variable is set
  system.port = ${?HTTP_SYSTEM_PORT}
  maxRequestBodySize = ${?MAX_BODY_SIZE}
}
```

- `${VAR}` — required; startup fails if absent
- `${?VAR}` — optional; the assignment is skipped when absent, so write the default on the line
  above and let the substitution override it

---

## Full key rename table

| Kora 1.x | Kora 2.0 |
|---|---|
| `httpServer.publicApiHttpPort` | `httpServer.port` |
| `httpServer.privateApiHttpPort` | `httpServer.system.port` |
| `httpServer.privateApiHttpMetricsPath` | `httpServer.system.metricsPath` |
| `httpServer.privateApiHttpReadinessPath` | `httpServer.system.readinessPath` |
| `httpServer.privateApiHttpLivenessPath` | `httpServer.system.livenessPath` |
| `httpServer.ioThreads` | `httpServer.undertow.ioThreads` |
| `httpServer.threadKeepAliveTimeout` | `httpServer.undertow.threadKeepAliveTimeout` |
| `httpServer.blockingThreads` | removed — virtual threads are unconditional |
| `httpServer.virtualThreadsEnabled` | removed — always on |
| `httpServer.telemetry.logging.pathTemplate` | `httpServer.telemetry.logging.pathFull` — same knob, **opposite polarity** (`pathTemplate = true` ⇔ `pathFull = false`); both are optional/nullable |
| `httpServer.telemetry.metrics.enabled` default `true` | default **`false`** — must be set explicitly |

The same keys apply to YAML (`config-yaml`) with YAML syntax.

Embedded HOCON in tests counts too: `KoraConfigModification.ofString("""…""")` blocks carry the
same keys and are missed by any scan that only looks at `.conf` and `.yaml` files.

**See also:** [Controller & Routing](controller-routing-reference.md), [Interceptors](interceptors-reference.md).
