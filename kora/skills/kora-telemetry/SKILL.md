---
name: kora-telemetry
description: Observability in Kora: metrics (Micrometer/Prometheus), tracing (OpenTelemetry gRPC/HTTP), and logging (SLF4J/Logback). Configure telemetry for HTTP server/client, gRPC, database, and Kafka. Use for monitoring, distributed tracing, and structured logging. Triggers: MetricsModule, OpentelemetryGrpcExporterModule, OpentelemetryHttpExporterModule, LogbackModule, Micrometer, Prometheus, OpenTelemetry, OTLP, distributed tracing.
---

# Kora Telemetry — Observability in Kora Applications

A comprehensive guide to configuring observability in Kora:
1. **Metrics** — Micrometer with Prometheus
2. **Tracing** — OpenTelemetry (OTLP gRPC/HTTP)
3. **Logging** — SLF4J/Logback

**When to use:** performance monitoring, distributed tracing, structured logging, integration with Prometheus/Grafana/Jaeger/Zipkin

Read this first when:
- adding metrics collection with Micrometer and Prometheus scrape endpoint,
- configuring distributed tracing with OpenTelemetry OTLP exporter (gRPC/HTTP),
- setting up structured logging with SLF4J/Logback and MDC context,
- implementing health checks (liveness/readiness probes) for Kubernetes,
- instrumenting custom business metrics or tracing spans.

## Quick Start

### 1. Metrics (Micrometer + Prometheus)
**build.gradle:** `implementation "ru.tinkoff.kora:micrometer-module"` + `io.micrometer:micrometer-registry-prometheus`

**Application.java:**
```java
@KoraApp
public interface Application extends MetricsModule, HttpServerModule {
    static void main(String[] args) { KoraApplication.run(ApplicationGraph::graph); }
}
```

**application.conf:**
```hocon
httpServer { privateApiHttpMetricsPath = "/metrics" }
metrics { opentelemetrySpec = "V120" }
```

### 2. Tracing (OpenTelemetry)
**build.gradle:** `implementation "ru.tinkoff.kora:opentelemetry-tracing-exporter-grpc"`

**Application.java:**
```java
@KoraApp
public interface Application extends OpentelemetryGrpcExporterModule {
    static void main(String[] args) { KoraApplication.run(ApplicationGraph::graph); }
}
```

**application.conf:**
```hocon
tracing {
    exporter {
        endpoint = "http://localhost:4317"
        attributes { "service.name" = "my-service" }
    }
}
```

### 3. Logging (Logback)
**build.gradle:** `implementation "ru.tinkoff.kora:logging-logback"`

**Application.java:**
```java
@KoraApp
public interface Application extends LogbackModule {
    static void main(String[] args) { KoraApplication.run(ApplicationGraph::graph); }
}
```

**logback.xml:**
```xml
<configuration>
    <appender name="STDOUT" class="ch.qos.logback.core.ConsoleAppender">
        <encoder><pattern>%d{HH:mm:ss.SSS} %-5level [%thread] %logger{36} - %msg%n</pattern></encoder>
    </appender>
    <appender name="ASYNC" class="ru.tinkoff.kora.logging.logback.KoraAsyncAppender">
        <appender-ref ref="STDOUT"/>
        <bufferSize>8192</bufferSize>
    </appender>
    <root level="INFO"><appender-ref ref="ASYNC"/></root>
</configuration>
```

---

## Assets

**Java:** `build.gradle.{metrics,tracing,logging}.template` | `Application.{metrics,tracing,logging}.java.template` | `application.{metrics,tracing}.conf.template` | `logback.xml.template` | `CustomMetricsConfig.java.template` | `TracingInterceptor.java.template`

**Kotlin:** `build.gradle.kts.{metrics,tracing,logging}.template` | `Application.{metrics,tracing,logging}.kt.template` | `CustomMetricsConfig.kt.template` | `TracingInterceptor.kt.template`

---

## 📝 Core Concepts

### Metrics (Micrometer)
**Module:** `MetricsModule` | **Dependency:** `ru.tinkoff.kora:micrometer-module`

**Configuration:**
```hocon
httpServer { privateApiHttpMetricsPath = "/metrics" }
metrics { opentelemetrySpec = "V120" }  # V120 or V123
```

**Customization (common tags):**
```java
@Module
public interface MetricsConfigModule {
    default PrometheusMeterRegistryInitializer commonTagsInit() {
        return registry -> {
            registry.config().commonTags("service", "my-service", "environment", "production");
            return registry;
        };
    }
}
```

**Metrics caching (Kora pattern):**
```java
record MetricKey(String cache, String op) {}
private final ConcurrentHashMap<MetricKey, Timer> timers = new ConcurrentHashMap<>();

public void record(String cache, String op, long duration) {
    var timer = timers.computeIfAbsent(new MetricKey(cache, op), k ->
        Timer.builder("custom.duration").tag("cache", k.cache).tag("op", k.op).register(registry));
    timer.record(duration, TimeUnit.NANOSECONDS);
}
```

### Tracing (OpenTelemetry)
**Modules:** `OpentelemetryGrpcExporterModule` (recommended) | `OpentelemetryHttpExporterModule`

**Dependencies:** `ru.tinkoff.kora:opentelemetry-tracing-exporter-grpc` | `ru.tinkoff.kora:opentelemetry-tracing-exporter-http`

**Configuration:**
```hocon
tracing {
    exporter {
        endpoint = "http://localhost:4317"  # gRPC:4317, HTTP:4318/v1/traces
        connectTimeout = "60s"
        exportTimeout = "3s"
        compression = "gzip"  # or "none" for Zipkin
        attributes {
            "service.name" = "my-service"
            "service.namespace" = "kora"
            "deployment.environment" = "production"
        }
    }
}
```

**Important:** Kora does not support Sampler configuration.

**Custom spans:**
```java
@Component
public class MyService {
    private final Tracer tracer;
    public MyService(Tracer tracer) { this.tracer = tracer; }
    
    public String doWork() {
        var ctx = Context.current();
        var otctx = OpentelemetryContext.get(ctx);
        var span = tracer.spanBuilder("myOperation").setParent(otctx.getContext()).startSpan();
        OpentelemetryContext.set(ctx, otctx.add(span));
        try {
            span.setStatus(StatusCode.OK);
            return doActualWork();
        } catch (Exception e) {
            span.recordException(e);
            span.setStatus(StatusCode.ERROR, e.getMessage());
            throw e;
        } finally {
            span.end();
            OpentelemetryContext.set(ctx, otctx);
        }
    }
}
```

### Logging (SLF4J/Logback)
**Module:** `LogbackModule` | **Dependency:** `ru.tinkoff.kora:logging-logback`

**Structured logging:**
```java
Logger logger = LoggerFactory.getLogger(getClass());
var marker = StructuredArgument.marker("userId", gen -> gen.writeString(userId));
logger.info(marker, "User action");
var param = StructuredArgument.arg("requestId", gen -> gen.writeString(requestId));
logger.info("Request {}", param);
```

**MDC context:**
```java
MDC.put("traceId", traceId);
try { logger.info("Processing"); } finally { MDC.clear(); }
```

---

## Advanced Patterns

### Telemetry for HTTP Server
```hocon
httpServer.telemetry.logging.enabled = true
httpServer.telemetry.metrics.enabled = true
httpServer.telemetry.tracing.enabled = true
httpServer.telemetry.logging.maskHeaders = ["X-Request-Id"]
```

### Telemetry for HTTP Client
```hocon
httpClient.MyClient.telemetry.logging.enabled = true
httpClient.MyClient.telemetry.metrics.enabled = true
httpClient.MyClient.telemetry.tracing.enabled = true
```

### Telemetry for gRPC
```hocon
grpcServer.telemetry.logging.enabled = true
grpcServer.telemetry.metrics.enabled = true
grpcServer.telemetry.tracing.enabled = true
grpcClient.MyService.telemetry.logging.enabled = true
grpcClient.MyService.telemetry.metrics.enabled = true
grpcClient.MyService.telemetry.tracing.enabled = true
```

### Telemetry for Database
```hocon
db.telemetry.logging.enabled = true
db.telemetry.metrics.enabled = true
db.telemetry.tracing.enabled = true
```

### Prometheus Integration
**build.gradle:** `implementation "io.micrometer:micrometer-registry-prometheus"`

**application.conf:** `httpServer { privateApiHttpMetricsPath = "/metrics" }`

**prometheus.yml:**
```yaml
scrape_configs:
  - job_name: 'my-service'
    scrape_interval: 15s
    metrics_path: '/metrics'
    static_configs: [{ targets: ['localhost:8080'] }]
```

### Jaeger/Zipkin Integration
**build.gradle:** `ru.tinkoff.kora:opentelemetry-tracing-exporter-grpc` (Jaeger) | `opentelemetry-tracing-exporter-http` (Zipkin)

**application.conf:**
```hocon
tracing {
    exporter {
        endpoint = "http://jaeger:4317"  # Zipkin: http://zipkin:9411/api/v2/spans
        compression = "gzip"  # "none" for Zipkin
        attributes { "service.name" = "my-service" }
    }
}
```

---

## Metrics Reference

| Metric | Type | Description | Tags |
|--------|------|-------------|------|
| `http.server.request.duration` | DistributionSummary | HTTP request duration | `method`, `status`, `route`, `scheme` |
| `http.server.active.requests` | Gauge | Active HTTP requests | `method`, `route` |
| `http.client.request.duration` | DistributionSummary | HTTP client duration | `method`, `status`, `server` |
| `rpc.server.duration` | DistributionSummary | gRPC server duration | `service`, `method`, `status` |
| `rpc.client.duration` | DistributionSummary | gRPC client duration | `service`, `method`, `status` |
| `db.client.request.duration` | DistributionSummary | DB operation duration | `pool`, `operation` |
| `jvm.gc.pause` | DistributionSummary | GC pause | `cause`, `action` |
| `jvm.memory.used` | Gauge | Memory usage | `area`, `id` |
| `jvm.threads.live` | Gauge | Active threads | - |
| `process.cpu.usage` | Gauge | CPU usage | - |

Full reference: [metrics-reference.md](references/metrics-reference.md)

---

## 🔍 Tracing Reference

**Span Attributes:** `service.name`, `service.namespace`, `http.method`, `http.status_code`, `http.url`, `db.statement`, `rpc.service`, `rpc.method`

**Propagation:** HTTP (`traceparent`, `tracestate`), gRPC metadata, Kafka headers

Full reference: [tracing-reference.md](references/tracing-reference.md)

---

## Quick Reference

```java
// Modules: MetricsModule / OpentelemetryGrpcExporterModule / LogbackModule
// Dependencies: micrometer-module / opentelemetry-tracing-exporter-grpc / logging-logback
// Metrics: http.server.request.duration, rpc.server.duration, db.client.request.duration
// Tracing: Tracer tracer, OpentelemetryContext.getSpan(), span.setStatus(StatusCode.OK/ERROR)
// Logging: Logger logger, StructuredArgument.marker(), MDC.put()
// Config: httpServer.privateApiHttpMetricsPath="/metrics", tracing.exporter.endpoint="http://jaeger:4317"
```

**Templates:** `assets/` — templates for metrics, tracing, logging.

**References:** [metrics-reference.md](references/metrics-reference.md) | [tracing-reference.md](references/tracing-reference.md) | [logging-reference.md](references/logging-reference.md)

---

## Evals
See `evals/evals.json` — tests: metrics setup, tracing setup, logging setup, HTTP/gRPC/DB telemetry, custom metrics/spans.

---

## Common Pitfalls

- **Metrics not exported** → add registry dependency (e.g., `micrometer-registry-prometheus`).
- **Tracing not flowing** → use `@Trace` on async boundaries; check propagator config.
- **SLF4J MDC vs Kora MDC** → use `ru.tinkoff.kora.logging.common.MDC`, not `org.slf4j.MDC`.
- **Missing `@Component` on custom metrics** → metric providers must be `@Component`.
- **OTLP endpoint misconfigured** → verify `otel.exporter.otlp.endpoint` and auth headers.
