# Scheduling Configuration Reference

Complete configuration reference for both JDK and Quartz scheduling.

## Contents

- [Module Configuration](#module-configuration)
- [Global Configuration](#global-configuration)
- [Job-Specific Configuration](#job-specific-configuration)
- [Quartz Persistence (JDBC JobStore)](#quartz-persistence-jdbc-jobstore)
- [Telemetry Reference](#telemetry-reference)
- [Shutdown Configuration](#shutdown-configuration)
- [See Also](#see-also)

---

## Module Configuration

### JDK Module

```java
@KoraApp
public interface Application extends
    HoconConfigModule,      // or YamlConfigModule
    LogbackModule,
    SchedulingJdkModule {
}
```

**Artifact:**
```groovy
implementation "ru.tinkoff.kora:scheduling-jdk"
```

### Quartz Module

```java
@KoraApp
public interface Application extends
    HoconConfigModule,
    LogbackModule,
    QuartzModule {
}
```

**Artifact:**
```groovy
implementation "ru.tinkoff.kora:scheduling-quartz"
```

---

## Global Configuration

### HOCON (application.conf)

```hocon
# JDK Configuration
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

# Quartz Configuration
quartz {
  "org.quartz.scheduler.instanceName" = "MyScheduler"
  "org.quartz.threadPool.threadCount" = "10"
  "org.quartz.threadPool.threadPriority" = "5"
  "org.quartz.jobStore.misfireThreshold" = "60000"
}

scheduling {
  waitForJobComplete = true      # Block shutdown until jobs finish
}
```

### YAML (application.yml)

```yaml
# JDK Configuration
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

# Quartz Configuration
quartz:
  org.quartz.scheduler.instanceName: "MyScheduler"
  org.quartz.threadPool.threadCount: "10"
  org.quartz.threadPool.threadPriority: "5"
  org.quartz.jobStore.misfireThreshold: "60000"

scheduling:
  waitForJobComplete: true
```

---

## Job-Specific Configuration

Config has **priority over annotation parameters**. Annotation values become defaults.

### JDK Jobs

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

### Quartz Jobs

```java
@ScheduleWithCron(config = "jobs.nightly")
void nightlyReport() { ... }

@ScheduleWithCron(config = "jobs.hourly")
void hourlyCheck() { ... }
```

**HOCON:**
```hocon
jobs {
  nightly {
    cron = "0 0 3 * * ?"
  }
  hourly {
    cron = "0 0 * * * ?"
  }
}
```

**YAML:**
```yaml
jobs:
  nightly:
    cron: "0 0 3 * * ?"
  hourly:
    cron: "0 0 * * * ?"
```

---

## Quartz Persistence (JDBC JobStore)

For persistent job state that survives restarts:

```hocon
quartz {
  "org.quartz.jobStore.class" = "org.quartz.impl.jdbcjobstore.JobStoreTX"
  "org.quartz.jobStore.driverDelegateClass" = "org.quartz.impl.jdbcjobstore.PostgreSQLDelegate"
  "org.quartz.jobStore.dataSource" = "myDS"
  "org.quartz.jobStore.tablePrefix" = "QRTZ_"
  "org.quartz.jobStore.isClustered" = "true"
  "org.quartz.scheduler.instanceId" = "AUTO"
}
```

**Database tables:** Run Quartz schema for your database (e.g., `tables_postgres.sql`).

---

## Telemetry Reference

### Metrics

| Property | Type | Default | Description |
|----------|------|---------|-------------|
| `scheduling.telemetry.metrics.enabled` | boolean | `true` | Enable Micrometer metrics |
| `scheduling.telemetry.metrics.slo` | array | `[]` | Histogram buckets (ms) |
| `scheduling.telemetry.metrics.tags` | object | `{}` | Additional tags |

**Metric:** `scheduling.job.duration` (DistributionSummary)

### Tracing

| Property | Type | Default | Description |
|----------|------|---------|-------------|
| `scheduling.telemetry.tracing.enabled` | boolean | `true` | Enable OpenTelemetry spans |
| `scheduling.telemetry.tracing.attributes` | object | `{}` | Additional span attributes |

**Span:** `{class}.{method}` with attributes `job`, `method`, `class`

### Logging

| Property | Type | Default | Description |
|----------|------|---------|-------------|
| `scheduling.telemetry.logging.enabled` | boolean | `false` | Enable job execution logging |

---

## Shutdown Configuration

### JDK

| Property | Type | Default | Description |
|----------|------|---------|-------------|
| `scheduling.shutdownWait` | duration | `30s` | Grace period for in-flight jobs |

### Quartz

| Property | Type | Default | Description |
|----------|------|---------|-------------|
| `scheduling.waitForJobComplete` | boolean | `false` | Block shutdown until jobs finish |

---

## See Also

- [Official Kora Documentation](../../../.kora-agent/kora-docs/mkdocs/docs/en/documentation/scheduling.md) — Full scheduling documentation
- [jdk-scheduling-reference.md](jdk-scheduling-reference.md) — JDK scheduling annotations
- [quartz-scheduling-reference.md](quartz-scheduling-reference.md) — Quartz scheduling
- [graceful-shutdown-reference.md](graceful-shutdown-reference.md) — Interrupt handling
