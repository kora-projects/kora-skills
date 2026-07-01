# Exporter Setup Reference

OTLP exporter modules, configuration keys, and backend wiring for Kora tracing.

## Contents

- [Modules](#modules)
- [Configuration keys](#configuration-keys)
- [Retry policy](#retry-policy)
- [Service attributes](#service-attributes)
- [Backends](#backends)
- [Troubleshooting](#troubleshooting)

## Modules

Pick exactly one exporter module. The protocol is determined by the module, not by a config key.

| Module | Artifact | Package | Protocol |
|--------|----------|---------|----------|
| `OpentelemetryGrpcExporterModule` | `ru.tinkoff.kora:opentelemetry-tracing-exporter-grpc` | `ru.tinkoff.kora.opentelemetry.tracing.exporter.grpc` | OTLP/gRPC |
| `OpentelemetryHttpExporterModule` | `ru.tinkoff.kora:opentelemetry-tracing-exporter-http` | `ru.tinkoff.kora.opentelemetry.tracing.exporter.http` | OTLP/HTTP |

```java
import ru.tinkoff.kora.common.KoraApp;
import ru.tinkoff.kora.opentelemetry.tracing.exporter.grpc.OpentelemetryGrpcExporterModule;

@KoraApp
public interface Application extends OpentelemetryGrpcExporterModule { }
```

All Kora artifacts are versioned by the `ru.tinkoff.kora:kora-parent` BOM; never pin an individual `ru.tinkoff.kora:*` version. Annotation processors are mandatory: Java `annotationProcessor "ru.tinkoff.kora:annotation-processors"`, Kotlin `ksp "ru.tinkoff.kora:symbol-processors"`.

## Configuration keys

All keys live under `tracing.exporter` (from `OpentelemetryGrpcExporterConfig` / `OpentelemetryHttpExporterConfig`); `tracing.attributes` comes from `OpentelemetryResourceConfig`. `endpoint` is the only mandatory key.

| Key | Default | Description |
|-----|---------|-------------|
| `endpoint` | — (required) | OTLP collector URL |
| `connectTimeout` | unset | Time to wait for a connection to the exporter |
| `exportTimeout` | `3s` | Max time for the collector to process telemetry |
| `scheduleDelay` | `2s` | Delay between export batches |
| `maxExportBatchSize` | `512` | Max spans per export batch |
| `maxQueueSize` | `2048` | Max unsent spans buffered |
| `batchExportTimeout` | `30s` | Max wait time for a batch export |
| `compression` | `gzip` | Compression on export (`gzip` or `none`) |
| `exportUnsampledSpans` | `false` | Whether unsampled spans are exported |

```hocon
tracing {
  exporter {
    endpoint = "http://localhost:4317"
    connectTimeout = "60s"
    exportTimeout = "3s"
    scheduleDelay = "2s"
    maxExportBatchSize = 512
    maxQueueSize = 2048
    batchExportTimeout = "30s"
    compression = "gzip"
    exportUnsampledSpans = false
  }
  attributes {
    "service.name" = "example-service"
    "service.namespace" = "kora"
  }
}
```

There is no `tracing.exporter.protocol` key and no `tracing.sampler` key. Protocol is chosen by the module; sampling is controlled in code (see [spans-and-context-reference.md](spans-and-context-reference.md#sampler-override)).

## Retry policy

Export retries are configured under `tracing.exporter.retry` (mapped from `RetryPolicy`).

| Key | Default |
|-----|---------|
| `maxAttempts` | `5` |
| `initialBackoff` | `1s` |
| `maxBackoff` | `5s` |
| `backoffMultiplier` | `1.5` |

```hocon
tracing {
  exporter {
    retry {
      maxAttempts = 5
      initialBackoff = "1s"
      maxBackoff = "5s"
      backoffMultiplier = 1.5
    }
  }
}
```

## Service attributes

Attributes under `tracing.attributes` are added as OpenTelemetry resource attributes on every span. Use environment substitution for per-environment values.

```hocon
tracing {
  attributes {
    "service.name" = ${SERVICE_NAME}
    "service.namespace" = "kora"
    "service.version" = ${?SERVICE_VERSION}
    "deployment.environment" = ${?ENV}
  }
}
```

`service.name` is required to find the service in the trace UI.

## Backends

### Jaeger (OTLP/gRPC)

```hocon
tracing {
  exporter {
    endpoint = "http://jaeger:4317"
    compression = "gzip"
  }
  attributes { "service.name" = "my-service" }
}
```

```yaml title="docker-compose.yml"
services:
  jaeger:
    image: jaegertracing/all-in-one:1.57
    ports:
      - "16686:16686"   # UI
      - "4317:4317"     # OTLP gRPC
      - "4318:4318"     # OTLP HTTP
    environment:
      COLLECTOR_OTLP_ENABLED: "true"
```

### Jaeger (OTLP/HTTP)

Use `OpentelemetryHttpExporterModule` and target the OTLP HTTP path on port 4318:

```hocon
tracing {
  exporter { endpoint = "http://jaeger:4318/v1/traces" }
  attributes { "service.name" = "my-service" }
}
```

### Zipkin (OTLP/HTTP)

```hocon
tracing {
  exporter {
    endpoint = "http://zipkin:9411/api/v2/spans"
    compression = "none"
  }
  attributes { "service.name" = "my-service" }
}
```

```yaml title="docker-compose.yml"
services:
  zipkin:
    image: openzipkin/zipkin:2.24
    ports:
      - "9411:9411"
```

### Grafana Tempo (OTLP/gRPC)

```hocon
tracing {
  exporter {
    endpoint = "http://tempo:4317"
    compression = "none"
  }
  attributes { "service.name" = "my-service" }
}
```

## Troubleshooting

### No spans in the backend

1. Verify `endpoint` and the port — OTLP/gRPC is `4317`, OTLP/HTTP is `4318`.
2. Confirm the chosen module matches the endpoint (gRPC module → 4317, HTTP module → 4318).
3. Check network connectivity to the collector.
4. Enable debug logging:
   ```hocon
   logging.level {
     "ru.tinkoff.kora.opentelemetry" = "DEBUG"
   }
   ```

### Export timeouts

1. Increase `exportTimeout` / `batchExportTimeout`.
2. Lower `maxExportBatchSize`.
3. Check collector availability.

### High overhead

1. Prefer the gRPC exporter (binary, more efficient than HTTP).
2. Reduce per-span attribute count.
3. Reduce sampling (see [spans-and-context-reference.md](spans-and-context-reference.md#sampler-override)).
