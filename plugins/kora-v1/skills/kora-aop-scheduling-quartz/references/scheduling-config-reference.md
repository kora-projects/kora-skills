# Quartz Scheduling Configuration Reference

Configuration for `scheduling-quartz` (cron, custom triggers, JDBC persistence, clustering).
For plain fixed-rate/fixed-delay timers see the sibling skill
[kora-aop-scheduling-jdk](../../kora-aop-scheduling-jdk/SKILL.md).

## Contents

- [Module Configuration](#module-configuration)
- [Global Configuration](#global-configuration) — HOCON and YAML
- [Job-Specific Configuration](#job-specific-configuration)
- [Persistence (JDBC JobStore)](#persistence-jdbc-jobstore)
- [Telemetry Reference](#telemetry-reference)
- [Shutdown Configuration](#shutdown-configuration)

---

## Module Configuration

```java
@KoraApp
public interface Application extends
    HoconConfigModule,      // or YamlConfigModule
    LogbackModule,
    QuartzModule {
}
```

**Artifact (with mandatory BOM + processor):**
```groovy
dependencies {
    koraBom platform("ru.tinkoff.kora:kora-parent:1.2.19")
    annotationProcessor "ru.tinkoff.kora:annotation-processors"   // Kotlin: ksp "ru.tinkoff.kora:symbol-processors"
    implementation "ru.tinkoff.kora:scheduling-quartz"
}
```

---

## Global Configuration

Quartz properties pass through under the `quartz` node; scheduling-level shutdown behavior
lives under `scheduling`.

### HOCON (application.conf)

```hocon
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

Config has **priority over annotation parameters**. Point `@ScheduleWithCron(config = ...)`
at a node holding a `cron` field.

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

## Persistence (JDBC JobStore)

For persistent job state that survives restarts and cluster-wide single execution:

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

**Database tables:** Run the Quartz schema for your database (e.g. `tables_postgres.sql`).

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
| `scheduling.waitForJobComplete` | boolean | `false` | Block shutdown until jobs finish |

See [graceful-shutdown-reference.md](graceful-shutdown-reference.md) for interrupt-handling patterns.

---

## See Also

- Kora docs: `.kora-agent/kora-docs/mkdocs/docs/en/documentation/scheduling.md` — full scheduling documentation
- [quartz-scheduling-reference.md](quartz-scheduling-reference.md) — Quartz annotations and cron grammar
- [graceful-shutdown-reference.md](graceful-shutdown-reference.md) — Interrupt handling
