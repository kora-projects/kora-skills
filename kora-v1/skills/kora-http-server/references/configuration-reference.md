# Configuration Reference

The `httpServer` section configures the Undertow transport. All values below are documented in
`HttpServerConfig`; defaults are shown.

## Contents

- [Full configuration](#full-configuration)
- [Ports and paths](#ports-and-paths)
- [Threads and virtual threads](#threads-and-virtual-threads)
- [Telemetry](#telemetry)
- [Environment substitution](#environment-substitution)

---

## Full configuration

```hocon
httpServer {
  publicApiHttpPort = 8080                          # application traffic
  privateApiHttpPort = 8085                         # metrics / probes
  privateApiHttpMetricsPath  = "/metrics"
  privateApiHttpReadinessPath = "/system/readiness"
  privateApiHttpLivenessPath  = "/system/liveness"
  ignoreTrailingSlash = false                       # treat /path and /path/ the same
  ioThreads = 2                                      # network threads
  blockingThreads = 2                                # worker threads
  shutdownWait = "30s"                               # graceful shutdown wait
  threadKeepAliveTimeout = "60s"
  socketReadTimeout = "0s"
  socketWriteTimeout = "0s"
  socketKeepAliveEnabled = false
  virtualThreadsEnabled = false                      # true requires Java 21+
  maxRequestBodySize = "256MiB"
  telemetry {
    logging {
      enabled = false
      stacktrace = true
      mask = "***"
      maskQueries = [ ]
      maskHeaders = [ "authorization", "cookie", "set-cookie" ]
      pathTemplate = true
    }
    metrics {
      enabled = true
      slo = [ 1, 10, 50, 100, 200, 500, 1000, 2000, 5000, 10000, 20000, 30000, 60000, 90000 ]
    }
    tracing { enabled = true }
  }
}
```

YAML uses the same keys with YAML syntax (`httpServer:` then nested `key: value`).

---

## Ports and paths

- `publicApiHttpPort` — the port that serves application traffic (controllers).
- `privateApiHttpPort` — a separate port that serves metrics and probe endpoints. Keep it
  distinct from the public port so management traffic is isolated.
- Probe/metrics endpoints live on the private port: `privateApiHttpMetricsPath`,
  `privateApiHttpReadinessPath`, `privateApiHttpLivenessPath`.

| Endpoint | Port | Purpose |
|---|---|---|
| `/metrics` | private | Prometheus metrics |
| `/system/readiness` | private | readiness probe |
| `/system/liveness` | private | liveness probe |

---

## Threads and virtual threads

- `ioThreads` — number of network (NIO) threads; defaults to CPU cores (min 2).
- `blockingThreads` — worker threads for blocking handlers; defaults to CPU cores x 2 (min 2).
- `virtualThreadsEnabled = true` switches request handling to virtual threads instead of
  `blockingThreads`; requires Java 21+.

---

## Telemetry

- `telemetry.logging.enabled` — module request/response logging (default `false`).
  `maskHeaders` / `maskQueries` hide sensitive values with `mask`.
- `telemetry.metrics.enabled` — HTTP server metrics (default `true`); `slo` configures the
  distribution buckets.
- `telemetry.tracing.enabled` — distributed tracing spans (default `true`).

---

## Environment substitution

HOCON supports environment variables with defaults:

```hocon
httpServer {
  publicApiHttpPort = ${?HTTP_PORT}      # required env var if present
  privateApiHttpPort = 8085
  maxRequestBodySize = ${?MAX_BODY_SIZE} # override via env
}
```

Syntax:
- `${VAR}` — required variable (fails if missing)
- `${?VAR}` — optional; key is omitted if the variable is absent
- `${?VAR:default}` — optional with a fallback value

**See also:** [Controller & Routing](controller-routing-reference.md), [Interceptors](interceptors-reference.md).
