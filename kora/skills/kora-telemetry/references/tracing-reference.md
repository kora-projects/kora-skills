# Kora Tracing Reference

**Source:** [.kora-agent/kora-docs/mkdocs/docs/en/documentation/tracing.md](.kora-agent/kora-docs/mkdocs/docs/en/documentation/tracing.md)  
**Examples:** `.kora-agent/kora-examples/kora-java-tracing-opentelemetry/`

Full reference for tracing in Kora applications.

## Modules

### OpentelemetryGrpcExporterModule

**Dependency:** `ru.tinkoff.kora:opentelemetry-tracing-exporter-grpc`

**Module:** `ru.tinkoff.kora.opentelemetry.module.OpentelemetryGrpcExporterModule`

**Configuration:**
```hocon
tracing {
    exporter {
        endpoint = "http://localhost:4317"
        connectTimeout = "60s"
        exportTimeout = "3s"
        compression = "gzip"
        attributes {
            "service.name" = "my-service"
        }
    }
}
```

### OpentelemetryHttpExporterModule

**Dependency:** `ru.tinkoff.kora:opentelemetry-tracing-exporter-http`

**Module:** `ru.tinkoff.kora.opentelemetry.module.OpentelemetryHttpExporterModule`

**Configuration:**
```hocon
tracing {
    exporter {
        endpoint = "http://localhost:4318/v1/traces"
    }
}
```

## Configuration

### Required Parameters

| Parameter | Description | Example |
|-----------|-------------|---------|
| `endpoint` | OTLP endpoint | `http://jaeger:4317` |

### Optional Parameters

| Parameter | Description | Default | Example |
|-----------|-------------|---------|---------|
| `connectTimeout` | Connection timeout | `60s` | `30s` |
| `exportTimeout` | Export timeout | `3s` | `5s` |
| `compression` | Compression (gzip/none) | `gzip` | `none` |
| `attributes` | Attributes for all spans | `{}` | see below |

### Attributes

**Recommended:**
```hocon
attributes {
    "service.name" = "my-service"
    "service.namespace" = "kora"
    "service.version" = "1.0.0"
    "deployment.environment" = "production"
}
```

**All standard attributes:**
- `service.name` — Service name
- `service.namespace` — Service namespace
- `service.version` — Service version
- `service.instance.id` — Unique instance ID
- `deployment.environment` — Environment (production, staging)

## Custom Spans

### Java

```java
@Component
public class MyService {
    private final Tracer tracer;

    public MyService(Tracer tracer) {
        this.tracer = tracer;
    }

    public String doWork() {
        var ctx = Context.current();
        var otctx = OpentelemetryContext.get(ctx);

        var span = tracer.spanBuilder("myOperation")
                .setParent(otctx.getContext())
                .setAttribute("custom.attribute", "value")
                .startSpan();

        OpentelemetryContext.set(ctx, otctx.add(span));

        try {
            var result = doActualWork();
            span.setStatus(StatusCode.OK);
            return result;
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

### Kotlin

```kotlin
@Component
class MyService(
    private val tracer: Tracer
) {

    fun doWork(): String {
        val ctx = Context.current()
        val otctx = OpentelemetryContext.get(ctx)

        val span = tracer.spanBuilder("myOperation")
            .setParent(otctx.context)
            .setAttribute("custom.attribute", "value")
            .startSpan()

        OpentelemetryContext.set(ctx, otctx.add(span))

        return try {
            val result = doActualWork()
            span.setStatus(StatusCode.OK)
            result
        } catch (e: Exception) {
            span.recordException(e)
            span.setStatus(StatusCode.ERROR, e.message)
            throw e
        } finally {
            span.end()
            OpentelemetryContext.set(ctx, otctx)
        }
    }
}
```

## Span Attributes

### HTTP

| Attribute | Type | Description |
|-----------|------|-------------|
| `http.method` | String | HTTP method |
| `http.url` | String | Full URL |
| `http.target` | String | Path + query |
| `http.status_code` | Int | HTTP status |
| `http.scheme` | String | http/https |
| `http.host` | String | Host header |
| `http.flavor` | String | HTTP version |
| `http.user_agent` | String | User-Agent |
| `http.client_ip` | String | Client IP |
| `http.server_name` | String | Server name |

### gRPC

| Attribute | Type | Description |
|-----------|------|-------------|
| `rpc.system` | String | grpc |
| `rpc.service` | String | Service name |
| `rpc.method` | String | Method name |
| `rpc.grpc.status_code` | Int | gRPC status code |

### Database

| Attribute | Type | Description |
|-----------|------|-------------|
| `db.system` | String | DBMS (postgresql, mysql) |
| `db.connection_string` | String | Connection string |
| `db.user` | String | Database user |
| `db.statement` | String | SQL query |
| `db.operation` | String | SELECT, INSERT, etc. |
| `db.name` | String | Database name |

### Messaging (Kafka)

| Attribute | Type | Description |
|-----------|------|-------------|
| `messaging.system` | String | kafka |
| `messaging.destination` | String | Topic |
| `messaging.operation` | String | send/receive |
| `messaging.message_id` | String | Message ID |

## Propagation

### HTTP Headers

**W3C Trace Context:**
- `traceparent` — `{version}-{trace-id}-{span-id}-{flags}`
- `tracestate` — Optional vendor-specific data

**Example:**
```
traceparent: 00-0af7651916cd43dd8448eb211c80319c-b7ad6b7169203331-01
```

### gRPC Metadata

- `traceparent` — W3C Trace Context
- `tracestate` — Vendor-specific

### Kafka Headers

- `traceparent` — W3C Trace Context
- `tracestate` — Vendor-specific

## Backend Integration

### Jaeger

**build.gradle:**
```groovy
implementation "ru.tinkoff.kora:opentelemetry-tracing-exporter-grpc"
```

**application.conf:**
```hocon
tracing {
    exporter {
        endpoint = "http://jaeger:4317"
        attributes {
            "service.name" = "my-service"
        }
    }
}
```

**Docker Compose:**
```yaml
version: '3'
services:
  jaeger:
    image: jaegertracing/all-in-one:1.53
    ports:
      - "16686:16686"  # UI
      - "4317:4317"    # OTLP gRPC
      - "4318:4318"    # OTLP HTTP
    environment:
      - COLLECTOR_OTLP_ENABLED=true
```

### Zipkin

**build.gradle:**
```groovy
implementation "ru.tinkoff.kora:opentelemetry-tracing-exporter-http"
```

**application.conf:**
```hocon
tracing {
    exporter {
        endpoint = "http://zipkin:9411/api/v2/spans"
        attributes {
            "service.name" = "my-service"
        }
    }
}
```

**Docker Compose:**
```yaml
version: '3'
services:
  zipkin:
    image: openzipkin/zipkin:2.24
    ports:
      - "9411:9411"
```

### Grafana Tempo

**application.conf:**
```hocon
tracing {
    exporter {
        endpoint = "http://tempo:4317"
        compression = "none"  # Tempo does not support gzip
        attributes {
            "service.name" = "my-service"
        }
    }
}
```

## Best Practices

1. **Use gRPC exporter** for efficiency (less overhead)
2. **Minimize attribute count** for high-traffic services (fewer attributes = less overhead)
3. **Add the service.name** attribute for identification
4. **Use standard attributes** (http.method, db.system, etc.)
5. **Avoid PII in attributes** (userId, email, phone)
6. **Record exceptions** via `span.recordException(e)`
7. **Set status** (OK/ERROR) explicitly
8. **Close spans** in a finally block

## Troubleshooting

### Span is not exported

1. Check the `endpoint` configuration
2. Check network connectivity (backend reachability)
3. Enable debug logging:
   ```hocon
   logging {
     levels {
       "ru.tinkoff.kora.opentelemetry" = "DEBUG"
     }
   }
   ```

### High overhead

1. Reduce the number of attributes in spans
2. Disable tracing for health-check endpoints
3. Use gRPC exporter instead of HTTP (less overhead)

### Missing spans

1. Check `exportTimeout` (increase if needed)
2. Check `connectTimeout` for cold start
3. Ensure the application does not shut down before spans are exported
