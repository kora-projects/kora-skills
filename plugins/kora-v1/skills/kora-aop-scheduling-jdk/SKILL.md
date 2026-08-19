---
name: kora-aop-scheduling-jdk
description: "In-process scheduled jobs in Kora — @ScheduleAtFixedRate/@ScheduleWithFixedDelay/@ScheduleOnce (scheduling-jdk). Use for periodic/heartbeat/cleanup jobs; for cron or clustered jobs use kora-aop-scheduling-quartz."
---

# Kora AOP Scheduling (JDK)

> **Kora sub-skill — obey the [kora-v1 meta rules](../../SKILL.md) on every task:** **R0** ensure `.kora-agent/` docs+examples are cloned · **R1** read this sub-skill before writing code · **R2** Kora APIs only — no Spring/Micronaut/Quarkus, no invented annotations or config keys · **R3** journal any incorrect Kora usage. Add comments/Javadoc only if asked.

**Artifact:** `ru.tinkoff.kora:scheduling-jdk`
**Module:** `SchedulingJdkModule`
**Annotation package:** `ru.tinkoff.kora.scheduling.jdk.annotation.*`

Aspect-driven scheduling on top of the JVM `ScheduledExecutorService`. The annotations mirror the `scheduleAtFixedRate`, `scheduleWithFixedDelay`, and `schedule` method signatures. No external scheduler, no persistence — jobs live only for the lifetime of the process. For cron, persistent state, custom triggers, or cluster-wide single execution, use the sibling skill [kora-aop-scheduling-quartz](../kora-aop-scheduling-quartz/SKILL.md).

**Aspect requirement:** the bearing class must be non-`final` (Java) / `open` (Kotlin), otherwise the annotation processor cannot generate the scheduling aspect.

---

## Quick Start

### 1. Add dependency

All Kora artifacts inherit their version from the `kora-parent` BOM — never version individual `ru.tinkoff.kora:*` deps.

```groovy
dependencies {
    koraBom platform("ru.tinkoff.kora:kora-parent:1.2.19")
    annotationProcessor "ru.tinkoff.kora:annotation-processors"   // mandatory — generates the aspect

    implementation "ru.tinkoff.kora:scheduling-jdk"
    implementation "ru.tinkoff.kora:config-hocon"
    implementation "ru.tinkoff.kora:logging-logback"
}
```

Kotlin uses `ksp "ru.tinkoff.kora:symbol-processors"` instead of `annotationProcessor`.

### 2. Plug the module into `@KoraApp`

```java
@KoraApp
public interface Application extends
    HoconConfigModule,
    LogbackModule,
    SchedulingJdkModule {
}
```

### 3. Declare a scheduled component

```java
package com.example.app.jobs;

import ru.tinkoff.kora.common.Component;
import ru.tinkoff.kora.scheduling.jdk.annotation.ScheduleAtFixedRate;
import java.time.temporal.ChronoUnit;

@Component
public class ScheduledJobs {   // non-final: required for aspect generation

    @ScheduleAtFixedRate(initialDelay = 30, period = 60, unit = ChronoUnit.SECONDS)
    void heartbeat() {
        // Lightweight task every 60 seconds
    }
}
```

---

## JDK Annotations

| Annotation | Description | Overlap |
|------------|-------------|---------|
| `@ScheduleAtFixedRate` | Fixed interval regardless of execution time | **Possible** |
| `@ScheduleWithFixedDelay` | Delay after previous completion | **Never** |
| `@ScheduleOnce` | Single execution after delay | N/A |

### @ScheduleAtFixedRate

Runs at fixed intervals. If task takes longer than period, next execution starts immediately after completion.

```java
@ScheduleAtFixedRate(initialDelay = 30, period = 60, unit = ChronoUnit.SECONDS)
void heartbeat() {
    // Runs every 60s (may overlap if task > 60s)
}
```

### @ScheduleWithFixedDelay

Waits for delay after task completion. No overlap possible.

```java
@ScheduleWithFixedDelay(initialDelay = 30, delay = 60, unit = ChronoUnit.SECONDS)
void syncData() {
    // Completes → wait 60s → run again
}
```

### @ScheduleOnce

Single execution after specified delay.

```java
@ScheduleOnce(delay = 5, unit = ChronoUnit.MINUTES)
void warmup() {
    // Runs once after 5 minutes
}
```

---

## Externalized parameters (`config`)

When the `config` attribute is set, the values come from that config path and **override** the annotation attributes (which then act only as defaults). The path is arbitrary; the example app nests jobs under `scheduling.jobs.*`.

```java
@ScheduleAtFixedRate(config = "scheduling.jobs.heartbeat")
void heartbeat() { ... }
```

```hocon
scheduling.jobs.heartbeat {
  initialDelay = "10s"
  period = "30s"
}
```

Keys per annotation: `@ScheduleAtFixedRate` → `initialDelay`, `period`; `@ScheduleWithFixedDelay` → `initialDelay`, `delay`; `@ScheduleOnce` → `delay`. Durations accept HOCON time strings (`"5ms"`, `"30s"`, `"2m"`).

---

## Module configuration

Defaults shown match `ScheduledExecutorServiceConfig`:

```hocon
scheduling {
  threads = 2                    # ScheduledExecutorService pool size (default: 2)
  shutdownWait = "30s"           # grace period for in-flight jobs on graceful shutdown
  telemetry {
    logging.enabled = false      # job execution logging (default: false)
    metrics.enabled = true       # Micrometer metrics (default: true)
    tracing.enabled = true       # OpenTelemetry tracing (default: true)
  }
}
```

See [scheduling-config-reference.md](references/scheduling-config-reference.md) for SLO buckets, metric tags, and tracing attributes.

---

## Graceful Shutdown

Long-running jobs must check interrupt status:

```java
@ScheduleWithFixedDelay(config = "scheduling.jobs.batch")
void processBatch() {
    while (!stopCondition()) {
        if (Thread.currentThread().isInterrupted()) {
            return;  // Exit on shutdown signal
        }
        doWork();
    }
}
```

---

## Error Handling

Exception is logged, next invocation continues normally.

**Pattern:** Wrap in try-catch to prevent logging noise.

```java
@ScheduleAtFixedRate(period = 60, unit = ChronoUnit.SECONDS)
void process() {
    try {
        doWork();
    } catch (Exception e) {
        log.error("Scheduled task failed", e);
    }
}
```

---

## Common Pitfalls

| Problem | Solution |
|---------|----------|
| **Task not running** | Ensure class is `@Component` and non-final (Java) / `open` (Kotlin) |
| **Concurrent execution** | Use `@ScheduleWithFixedDelay` instead of `@ScheduleAtFixedRate` |
| **Long-running task** | Check `Thread.currentThread().isInterrupted()` for graceful exit |
| **Config not applied** | Verify config path matches annotation |

---

## References, assets, scripts

| File | Purpose |
|------|---------|
| [references/jdk-scheduling-reference.md](references/jdk-scheduling-reference.md) | Per-annotation reference, error handling, telemetry |
| [references/scheduling-config-reference.md](references/scheduling-config-reference.md) | JDK scheduling configuration |
| [references/graceful-shutdown-reference.md](references/graceful-shutdown-reference.md) | Interrupt handling and shutdown patterns |
| [assets/ScheduledJobs.java.template](assets/ScheduledJobs.java.template) | Java scheduled-jobs starter |
| [assets/ScheduledJobs.kt.template](assets/ScheduledJobs.kt.template) | Kotlin scheduled-jobs starter |
| [scripts/setup-jdk.sh](scripts/setup-jdk.sh) | Add `scheduling-jdk`, template, and config to a project |

For cron expressions, custom triggers, and persistent/clustered jobs, use the sibling skill
[kora-aop-scheduling-quartz](../kora-aop-scheduling-quartz/SKILL.md).

Source of truth: `.kora-agent/kora-docs/mkdocs/docs/en/documentation/scheduling.md` (section `#native`) and `.kora-agent/kora-examples/examples/java/kora-java-scheduling-jdk`.

---

## Related skills

- [kora-aop-scheduling-quartz](../kora-aop-scheduling-quartz/SKILL.md) — cron, triggers, persistent and clustered jobs
- [kora-aop-logging](../kora-aop-logging/SKILL.md) — `@Log` / `@Mdc` for scheduled methods
