# Kora Telemetry

Observability: metrics (Micrometer/Prometheus), tracing (OpenTelemetry), logging (SLF4J/Logback).

## When to use

- Configuring metrics and dashboards
- Distributed tracing (gRPC/HTTP)
- Structured logging
- Health checks, readiness/liveness probes

## Quick Start

```bash
/kora-telemetry --metrics prometheus --tracing otlp
```

## Key Features

- Micrometer metrics (Prometheus)
- OpenTelemetry tracing (gRPC/HTTP exporter)
- SLF4J/Logback logging
- Automatic telemetry for HTTP/gRPC/DB/Kafka
- Custom metrics and spans

## Triggers

metrics, tracing, OpenTelemetry, Micrometer, Prometheus, structured logging, health check

## Resources

- **SKILL.md** — full documentation
- **references/** — 18 assets (Java + Kotlin)
- **evals/** — 20 test scenarios
