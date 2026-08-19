# JDK Scheduling Configuration Reference

Configuration for `scheduling-jdk` (in-process `ScheduledExecutorService`). For Quartz
(cron, persistence, clustering) see the sibling skill
[kora-aop-scheduling-quartz](../../kora-aop-scheduling-quartz/SKILL.md).

## Contents

- [Module Configuration](#module-configuration)
- [Global Configuration](#global-configuration) — HOCON and YAML
- [Job-Specific Configuration](#job-specific-configuration)
- [Telemetry Reference](#telemetry-reference)
- [Shutdown Configuration](#shutdown-configuration)

---

## Module Configuration

```java
@KoraApp
public interface Application extends
    HoconConfigModule,      // or YamlConfigModule
    LogbackModule,
    SchedulingJdkModule {
}
```

**Artifact (with mandatory BOM + processor):**
```groovy
dependencies {
    koraBom platform("ru.tinkoff.kora:kora-parent:1.2.19")
    annotationProcessor "ru.tinkoff.kora:annotation-processors"   // Kotlin: ksp "ru.tinkoff.kora:symbol-processors"
    implementation "ru.tinkoff.kora:scheduling-jdk"
}
```

---

## Global Configuration

### HOCON (application.conf)

```hocon
scheduling {
  threads = 2                    # ScheduledExecutorService pool size
  shutdownWait = "30s"           # Grace period for SIGTERM

  telemetry {
    logging {
      enabled = false            # Job execution logging
    }
    metrics {
      enabled = true             # Micrometer metrics
      slo = [1, 10, 50, 100, 500, 1000, 5000, 10000]  # Histogram buckets (ms)
      tags = {                   # Additional metric tags
        "env" = "prod"
      }
    }
    tracing {
      enabled = true             # OpenTelemetry spans
      attributes = {             # Additional span attributes
        "service" = "my-service"
      }
    }
  }
}
```

### YAML (application.yml)

```yaml
scheduling:
  threads: 2
  shutdownWait: "30s"
  telemetry:
    logging:
      enabled: false
    metrics:
      enabled: true
      slo: [1, 10, 50, 100, 500, 1000, 5000, 10000]
      tags:
        env: "prod"
    tracing:
      enabled: true
      attributes:
        service: "my-service"
```

---

## Job-Specific Configuration

Config has **priority over annotation parameters**. Annotation values become defaults.

```java
@ScheduleAtFixedRate(config = "jobs.heartbeat")
void heartbeat() { ... }

@ScheduleWithFixedDelay(config = "jobs.cleanup")
void cleanup() { ... }

@ScheduleOnce(config = "jobs.warmup")
void warmup() { ... }
```

**HOCON:**
```hocon
jobs {
  heartbeat {
    initialDelay = "10s"
    period = "30s"
  }
  cleanup {
    initialDelay = "30s"
    delay = "5m"
  }
  warmup {
    delay = "5m"
  }
}
```

**YAML:**
```yaml
jobs:
  heartbeat:
    initialDelay: "10s"
    period: "30s"
  cleanup:
    initialDelay: "30s"
    delay: "5m"
  warmup:
    delay: "5m"
```

---

## Telemetry Reference

### Metrics

| Property | Type | Default | Description |
|----------|------|---------|-------------|
| `scheduling.telemetry.metrics.enabled` | boolean | `true` | Enable Micrometer metrics |
| `scheduling.telemetry.metrics.slo` | array | `[]` | Histogram buckets (ms) |
| `scheduling.telemetry.metrics.tags` | object | `{}` | Additional tags |

**Metric:** `scheduling.job.duration` (DistributionSummary)

**Metric tags:** `code.class`, `code.function`, `error.type` (see `metrics.md` section `#scheduling`).

### Tracing

| Property | Type | Default | Description |
|----------|------|---------|-------------|
| `scheduling.telemetry.tracing.enabled` | boolean | `true` | Enable OpenTelemetry spans |
| `scheduling.telemetry.tracing.attributes` | object | `{}` | Additional span attributes |

### Logging

| Property | Type | Default | Description |
|----------|------|---------|-------------|
| `scheduling.telemetry.logging.enabled` | boolean | `false` | Enable job execution logging |

---

## Shutdown Configuration

| Property | Type | Default | Description |
|----------|------|---------|-------------|
| `scheduling.shutdownWait` | duration | `30s` | Grace period for in-flight jobs |

See [graceful-shutdown-reference.md](graceful-shutdown-reference.md) for interrupt-handling patterns.

---

## See Also

- Kora docs: `.kora-agent/kora-docs/mkdocs/docs/en/documentation/scheduling.md` (section `#native`)
- [jdk-scheduling-reference.md](jdk-scheduling-reference.md) — JDK scheduling annotations
- [graceful-shutdown-reference.md](graceful-shutdown-reference.md) — Interrupt handling
