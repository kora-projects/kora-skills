# HTTP Server Configuration Reference

**Source:** [.kora-agent/kora-docs/mkdocs/docs/en/documentation/http-server.md](.kora-agent/kora-docs/mkdocs/docs/en/documentation/http-server.md)  
**Examples:** `.kora-agent/kora-examples/kora-java-http-server-undertow/`

## Basic Configuration

```hocon
httpServer {
  publicApiHttpPort = 8080        # Public API port
  privateApiHttpPort = 8085       # Private API port (metrics, health)
}
```

## Full Configuration

```hocon
httpServer {
  # Ports
  publicApiHttpPort = 8080                    # (1) Public server port
  privateApiHttpPort = 8085                   # (2) Private server port
  
  # System endpoints (on private port)
  privateApiHttpMetricsPath = "/metrics"      # (3) Prometheus metrics
  privateApiHttpReadinessPath = "/system/readiness"  # (4) Readiness probe
  privateApiHttpLivenessPath = "/system/liveness"    # (5) Liveness probe
  
  # Path matching
  ignoreTrailingSlash = false                 # (6) /path == /path/
  
  # Thread pools
  ioThreads = 2                               # (7) Network threads
  blockingThreads = 2                         # (8) Worker threads
  virtualThreadsEnabled = false               # (14) Java 15+ virtual threads
  
  # Timeouts
  shutdownWait = "30s"                        # (9) Graceful shutdown
  threadKeepAliveTimeout = "60s"              # (10) Thread keep-alive
  socketReadTimeout = "0s"                    # (11) Socket read timeout
  socketWriteTimeout = "0s"                   # (12) Socket write timeout
  
  # Socket options
  socketKeepAliveEnabled = false              # (13) TCP keep-alive
  
  # Request limits
  maxRequestBodySize = "256MiB"               # (15) Max request body
  
  # Telemetry
  telemetry {
    logging {
      enabled = false                         # (16) Request logging
      stacktrace = true                       # (17) Log stack traces
      mask = "***"                            # (18) Mask value
      maskQueries = []                        # (19) Masked query params
      maskHeaders = ["authorization", "cookie", "set-cookie"]  # (20)
      pathTemplate = true                     # (21) Log path template
    }
    metrics {
      enabled = true                          # (22) Prometheus metrics
      slo = [1, 10, 50, 100, 200, 500, 1000, 2000, 5000, 10000]  # (23)
    }
    tracing {
      enabled = true                          # (24) Distributed tracing
    }
  }
}
```

**Parameter descriptions:**

1. **publicApiHttpPort** — port for the public API
2. **privateApiHttpPort** — port for system endpoints (metrics, health)
3. **privateApiHttpMetricsPath** — path to Prometheus metrics
4. **privateApiHttpReadinessPath** — readiness probe for Kubernetes
5. **privateApiHttpLivenessPath** — liveness probe for Kubernetes
6. **ignoreTrailingSlash** — ignore trailing slash in the path
7. **ioThreads** — number of network threads (default: CPU cores, min 2)
8. **blockingThreads** — number of worker threads (default: CPU cores * 2)
9. **shutdownWait** — graceful shutdown wait time
10. **threadKeepAliveTimeout** — idle thread keep-alive time
11. **socketReadTimeout** — socket read timeout (0 = no timeout)
12. **socketWriteTimeout** — socket write timeout (0 = no timeout)
13. **socketKeepAliveEnabled** — TCP keep-alive
14. **virtualThreadsEnabled** — virtual threads (Java 15+)
15. **maxRequestBodySize** — maximum request body size
16. **telemetry.logging.enabled** — enable request logging
17. **telemetry.logging.stacktrace** — log error stack traces
18. **telemetry.logging.mask** — mask value for hidden fields
19. **telemetry.logging.maskQueries** — query parameters to mask
20. **telemetry.logging.maskHeaders** — headers to mask
21. **telemetry.logging.pathTemplate** — use path template in logs
22. **telemetry.metrics.enabled** — enable metrics
23. **telemetry.metrics.slo** — SLO buckets for DistributionSummary
24. **telemetry.tracing.enabled** — enable distributed tracing

## YAML Configuration

```yaml
httpServer:
  publicApiHttpPort: 8080
  privateApiHttpPort: 8085
  privateApiHttpMetricsPath: "/metrics"
  privateApiHttpReadinessPath: "/system/readiness"
  privateApiHttpLivenessPath: "/system/liveness"
  ignoreTrailingSlash: false
  ioThreads: 2
  blockingThreads: 2
  shutdownWait: "30s"
  threadKeepAliveTimeout: "60s"
  socketReadTimeout: "0s"
  socketWriteTimeout: "0s"
  socketKeepAliveEnabled: false
  virtualThreadsEnabled: false
  maxRequestBodySize: "256MiB"
  telemetry:
    logging:
      enabled: false
      stacktrace: true
      mask: "***"
      maskQueries: []
      maskHeaders:
        - "authorization"
        - "cookie"
        - "set-cookie"
      pathTemplate: true
    metrics:
      enabled: true
      slo:
        - 1
        - 10
        - 50
        - 100
        - 200
        - 500
        - 1000
        - 2000
        - 5000
        - 10000
    tracing:
      enabled: true
```

## Production Configuration

```hocon
httpServer {
  publicApiHttpPort = 8080
  privateApiHttpPort = 8085
  
  # Production thread pool
  ioThreads = 4
  blockingThreads = 16
  
  # Timeouts
  shutdownWait = "60s"
  socketReadTimeout = "30s"
  socketWriteTimeout = "30s"
  
  # Request limits
  maxRequestBodySize = "10MiB"
  
  # Telemetry
  telemetry {
    logging {
      enabled = true
      stacktrace = true
      mask = "***"
      maskHeaders = ["authorization", "cookie", "set-cookie"]
      pathTemplate = true
    }
    metrics.enabled = true
    tracing.enabled = true
  }
}
```

## Development Configuration

```hocon
httpServer {
  publicApiHttpPort = 8080
  privateApiHttpPort = 8085
  
  # Development logging
  telemetry {
    logging {
      enabled = true
      stacktrace = true
      pathTemplate = false  # Log full path for debugging
    }
    metrics.enabled = true
    tracing.enabled = false
  }
}

logging.level {
  "root": "INFO"
  "ru.tinkoff.kora": "DEBUG"
  "ru.tinkoff.kora.example": "DEBUG"
}
```

## Virtual Threads (Java 25+)

```hocon
httpServer {
  publicApiHttpPort = 8080
  privateApiHttpPort = 8085
  
  # Virtual threads
  virtualThreadsEnabled = true
  blockingThreads = 0  # Not used with virtual threads
  
  telemetry {
    logging.enabled = true
    metrics.enabled = true
    tracing.enabled = true
  }
}
```

## System Endpoints

After configuration the application automatically exposes the following endpoints:

| Endpoint | Port | Description |
|----------|------|-------------|
| `GET /metrics` | private | Prometheus metrics |
| `GET /system/readiness` | private | Readiness probe |
| `GET /system/liveness` | private | Liveness probe |

**Readiness probe example:**
```hocon
httpServer {
  privateApiHttpReadinessPath = "/health/ready"
}
```

**Liveness probe example:**
```hocon
httpServer {
  privateApiHttpLivenessPath = "/health/live"
}
```

## Custom Configurer

For advanced configuration use `UndertowConfigurer`:

```java
@Component
public final class CustomUndertowConfigurer implements UndertowConfigurer {
    @Override
    public void setConfig(Undertow.Builder builder) {
        builder.setBufferSize(1024 * 16)  // 16 KB buffer
               .setIoThreads(4)
               .setWorkerThreads(32);
    }
}
```
