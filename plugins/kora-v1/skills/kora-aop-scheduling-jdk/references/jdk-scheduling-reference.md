# JDK Scheduling Reference

**Artifact:** `scheduling-jdk`  
**Module:** `SchedulingJdkModule`  
**Package:** `ru.tinkoff.kora.scheduling.jdk.annotation.*`

JDK scheduling uses `ScheduledExecutorService` for in-process, non-persistent task execution.

## Contents

- [Annotations](#annotations) — `@ScheduleAtFixedRate`, `@ScheduleWithFixedDelay`, `@ScheduleOnce`
- [Configuration](#configuration) — module setup, global settings, per-job config
- [Error Handling](#error-handling)
- [Telemetry](#telemetry)

---

## Annotations

### `@ScheduleAtFixedRate`

Executes every `period` regardless of previous task completion time.

**Parameters:**
- `initialDelay` — delay before first execution (default: 0)
- `period` — interval between executions
- `unit` — time unit (`ChronoUnit`)
- `config` — config path for externalized parameters

**Behavior:**
- **Concurrent overlap possible** if task execution exceeds period
- Next invocation starts at fixed intervals regardless of previous completion

**Use when:** Task must run at fixed intervals (metrics collection, heartbeat, health checks).

```java
@Component
public class CleanupJob {

    @ScheduleAtFixedRate(initialDelay = 30, period = 60, unit = ChronoUnit.SECONDS)
    void cleanup() {
        // Runs every 60s, even if previous execution is still running
    }
}
```

**Config override:**
```java
@ScheduleAtFixedRate(config = "jobs.cleanup")
void cleanup() { ... }
```
```hocon
jobs.cleanup {
  initialDelay = "30s"
  period = "60s"
}
```

---

### `@ScheduleWithFixedDelay`

Waits `delay` after previous task **completes** before next execution.

**Parameters:**
- `initialDelay` — delay before first execution (default: 0)
- `delay` — delay after completion
- `unit` — time unit (`ChronoUnit`)
- `config` — config path for externalized parameters

**Behavior:**
- **Never overlaps** — waits for completion + delay
- Safe for long-running tasks

**Use when:** Task must complete before next execution starts (batch processing, data sync).

```java
@Component
public class DataSyncJob {

    @ScheduleWithFixedDelay(initialDelay = 30, delay = 120, unit = ChronoUnit.SECONDS)
    void syncData() {
        // Runs 120s after previous execution completes
    }
}
```

**Config override:**
```hocon
jobs.sync {
  initialDelay = "30s"
  delay = "2m"
}
```

---

### `@ScheduleOnce`

Single execution after specified delay.

**Parameters:**
- `delay` — delay before execution
- `unit` — time unit (`ChronoUnit`)
- `config` — config path for externalized delay

**Use when:** One-time delayed execution (cache warming, startup tasks, late binding).

```java
@Component
public class CacheWarmer {

    @ScheduleOnce(delay = 5, unit = ChronoUnit.MINUTES)
    void warmup() {
        // Runs once after 5 minutes
    }
}
```

---

## Configuration

### Module Setup

```java
@KoraApp
public interface Application extends
    HoconConfigModule,      // or YamlConfigModule
    LogbackModule,
    SchedulingJdkModule {
}
```

### Global Settings

```hocon
scheduling {
  threads = 2                    # ScheduledExecutorService pool size (default: 2)
  shutdownWait = "30s"           # Grace period for in-flight jobs on SIGTERM
  telemetry {
    logging.enabled = false      # Job execution logging (default: false)
    metrics.enabled = true       # Micrometer metrics (default: true)
    tracing.enabled = true       # OpenTelemetry tracing (default: true)
  }
}
```

```yaml
scheduling:
  threads: 2
  shutdownWait: "30s"
  telemetry:
    logging:
      enabled: false
    metrics:
      enabled: true
    tracing:
      enabled: true
```

### Job-Specific Configuration

Annotation parameters become defaults; **config values override annotation**.

```java
@ScheduleAtFixedRate(config = "jobs.heartbeat")
void heartbeat() { ... }
```

```hocon
jobs.heartbeat {
  initialDelay = "10s"
  period = "30s"
}
```

```yaml
jobs:
  heartbeat:
    initialDelay: "10s"
    period: "30s"
```

---

## Error Handling

**JDK behavior:**
- Exception is logged via SLF4J
- Next invocation continues normally
- No automatic retry

**Recommended pattern:**
```java
@ScheduleAtFixedRate(period = 60, unit = ChronoUnit.SECONDS)
void process() {
    try {
        doWork();
    } catch (Exception e) {
        log.error("Scheduled task failed", e);
        // Don't rethrow - prevents next execution
    }
}
```

---

## Telemetry

### Metrics (Micrometer)
- **Metric:** `scheduling.job.duration` (exported as `scheduling_job_duration_milliseconds` / `_count` / `_sum` / `_bucket` / `_max`)
- **Type:** DistributionSummary — scheduled job execution duration
- **Tags:** `code.class`, `code.function`, `error.type` (per the Metrics module reference)
- **SLO buckets:** configurable via `scheduling.telemetry.metrics.slo`
- **Toggle:** `scheduling.telemetry.metrics.enabled` (default `true`)

### Tracing (OpenTelemetry)
- **Toggle:** `scheduling.telemetry.tracing.enabled` (default `true`)
- **Custom attributes:** `scheduling.telemetry.tracing.attributes`

### Logging
- **Toggle:** `scheduling.telemetry.logging.enabled` (default `false`)

---

## See Also

- Kora docs: `.kora-agent/kora-docs/mkdocs/docs/en/documentation/scheduling.md` (section `#native`)
- Metric details: `.kora-agent/kora-docs/mkdocs/docs/en/documentation/metrics.md` (section `#scheduling`)
- [scheduling-config-reference.md](scheduling-config-reference.md) — Full configuration reference
- [graceful-shutdown-reference.md](graceful-shutdown-reference.md) — Interrupt handling and shutdown
