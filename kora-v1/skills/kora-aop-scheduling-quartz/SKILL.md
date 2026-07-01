---
name: kora-aop-scheduling-quartz
description: "Quartz-backed declarative scheduling in Kora via the scheduling-quartz artifact and QuartzModule. Covers @ScheduleWithCron for cron expressions, @ScheduleWithTrigger(@Tag(...)) for a custom Quartz Trigger component, @DisallowConcurrentExecution to prevent overlap, and @PersistJobDataAfterExecution for stateful jobs. Use when scheduling cron jobs, externalizing a cron via config, wiring a Quartz Trigger, or controlling concurrency and graceful shutdown of scheduled methods. For plain fixed-rate/fixed-delay timers without cron use kora-aop-scheduling-jdk instead."
---

# Kora Quartz Scheduling

Annotation-driven scheduling backed by the Quartz library. Annotate a method on
a `@Component` with `@ScheduleWithCron` or `@ScheduleWithTrigger`; Kora generates
the aspect at compile time and registers the job with a Quartz `Scheduler`.

Use Quartz when you need **cron expressions** or a **custom Quartz `Trigger`**.
For simple fixed-rate / fixed-delay / one-shot timers, use the lighter
`scheduling-jdk` module instead — see [kora-aop-scheduling-jdk](../kora-aop-scheduling-jdk/SKILL.md).

**Class requirement:** the enclosing class must be a `@Component`. Kora generates
a separate Quartz `Job` wrapper at compile time, so the component class itself can
stay `final` (Java) / non-`open` (Kotlin) — the canonical examples use
`public final class ...Scheduler`. (The general "non-`final`/`open`" rule only
applies to AOP aspects that wrap the method body, such as `@Log` or `@Retry`.)

---

## Quick Start

### 1. Dependencies

The `kora-parent` BOM pins every Kora artifact — never version `ru.tinkoff.kora:*`
deps yourself.

```groovy
// build.gradle (Java)
dependencies {
    koraBom platform("ru.tinkoff.kora:kora-parent:1.2.17")
    annotationProcessor "ru.tinkoff.kora:annotation-processors"   // mandatory

    implementation "ru.tinkoff.kora:scheduling-quartz"
    implementation "ru.tinkoff.kora:config-hocon"
    implementation "ru.tinkoff.kora:logging-logback"
}
```

```kotlin
// build.gradle.kts (Kotlin)
dependencies {
    koraBom(platform("ru.tinkoff.kora:kora-parent:1.2.17"))
    ksp("ru.tinkoff.kora:symbol-processors")                      // mandatory

    implementation("ru.tinkoff.kora:scheduling-quartz")
    implementation("ru.tinkoff.kora:config-hocon")
    implementation("ru.tinkoff.kora:logging-logback")
}
```

### 2. Plug in the module

```java
import ru.tinkoff.kora.common.KoraApp;
import ru.tinkoff.kora.config.hocon.HoconConfigModule;
import ru.tinkoff.kora.logging.logback.LogbackModule;
import ru.tinkoff.kora.scheduling.quartz.QuartzModule;

@KoraApp
public interface Application extends
    HoconConfigModule,
    LogbackModule,
    QuartzModule { }
```

### 3. A cron job

```java
package com.example.app.jobs;

import ru.tinkoff.kora.common.Component;
import ru.tinkoff.kora.scheduling.quartz.ScheduleWithCron;

@Component
public class CronScheduler {

    @ScheduleWithCron("0 0 3 * * ?")   // daily at 03:00
    void nightlyReport() {
        // ...
    }
}
```

---

## What's in this skill

| File | Purpose |
|------|---------|
| [references/quartz-scheduling-reference.md](references/quartz-scheduling-reference.md) | Every Quartz annotation, cron grammar, config, error handling |
| [references/scheduling-config-reference.md](references/scheduling-config-reference.md) | Full HOCON/YAML config, telemetry, JDBC JobStore, shutdown |
| [references/graceful-shutdown-reference.md](references/graceful-shutdown-reference.md) | Interrupt handling for long-running jobs |
| [references/jdk-scheduling-reference.md](references/jdk-scheduling-reference.md) | JDK alternative (fixed-rate/delay/once) for comparison |
| [assets/ScheduledJobs.java.template](assets/ScheduledJobs.java.template) | Java jobs starter (JDK + Quartz) |
| [assets/ScheduledJobs.kt.template](assets/ScheduledJobs.kt.template) | Kotlin jobs starter |
| [scripts/create-cron-job.sh](scripts/create-cron-job.sh) | Generate a cron job class + config entry |
| [scripts/validate-cron.sh](scripts/validate-cron.sh) | Sanity-check a Quartz cron expression |
| [scripts/setup-quartz.sh](scripts/setup-quartz.sh) | Scaffold Quartz deps, module, config |

---

## When to use Quartz vs JDK

| Need | Use |
|------|-----|
| Cron expression (`@ScheduleWithCron`) | **Quartz** |
| Custom Quartz `Trigger` (`@ScheduleWithTrigger`) | **Quartz** |
| Misfire policies, calendar exclusions | **Quartz** |
| Fixed rate / fixed delay / run-once | **JDK** (`scheduling-jdk`) |

Don't pull in `scheduling-quartz` only to run something every N seconds —
`@ScheduleAtFixedRate` / `@ScheduleWithFixedDelay` from `scheduling-jdk` are
lighter. See [jdk-scheduling-reference.md](references/jdk-scheduling-reference.md).

---

## Annotations

All Quartz annotations live in `ru.tinkoff.kora.scheduling.quartz.*`.

| Annotation | Purpose |
|------------|---------|
| `@ScheduleWithCron` | Run on a Quartz cron expression |
| `@ScheduleWithTrigger` | Run on a custom `org.quartz.Trigger` component, referenced by `@Tag` |
| `@DisallowConcurrentExecution` | Forbid overlapping executions of the same job |
| `@PersistJobDataAfterExecution` | Re-save `org.quartz.JobDataMap` after each run (use with `@DisallowConcurrentExecution`) |

### `@ScheduleWithCron`

```java
@Component
public class CronScheduler {

    // Inline expression — every second (Quartz 7-field form)
    @ScheduleWithCron("* * * ? * * *")
    void everySecond() { }

    // 9 AM on weekdays
    @ScheduleWithCron("0 0 9 ? * MON-FRI")
    void morningReport() { }
}
```

Cron grammar and a table of common expressions are in
[quartz-scheduling-reference.md](references/quartz-scheduling-reference.md#cron-expression-reference).

### `@ScheduleWithTrigger` — custom Trigger

Define a Quartz `Trigger` as a tagged component on the `@KoraApp` interface, then
reference it from the job method by the same `@Tag`. The tag is any class — the
convention is to tag with the job class itself.

```java
import org.quartz.SimpleScheduleBuilder;
import org.quartz.Trigger;
import org.quartz.TriggerBuilder;
import ru.tinkoff.kora.common.Tag;

@KoraApp
public interface Application extends QuartzModule {

    @Tag(TriggerScheduler.class)
    default Trigger myTrigger() {
        return TriggerBuilder.newTrigger()
            .withIdentity("myTrigger")
            .startNow()
            .withSchedule(SimpleScheduleBuilder.simpleSchedule()
                .withIntervalInMilliseconds(50)
                .repeatForever())
            .build();
    }
}

@Component
public class TriggerScheduler {

    @ScheduleWithTrigger(@Tag(TriggerScheduler.class))
    void schedule() { }
}
```

`@ScheduleWithTrigger` takes a `@Tag(...)` referencing the trigger component — it
does **not** take a string name.

### `@DisallowConcurrentExecution`

Prevents the same job from running twice in parallel (e.g. when a run exceeds the
trigger interval).

```java
@Component
public class HourlyScheduler {

    @DisallowConcurrentExecution
    @ScheduleWithCron("0 0 * * * ?")   // top of every hour
    void hourly() { }
}
```

### `@PersistJobDataAfterExecution`

Forces Quartz to re-save the `org.quartz.JobDataMap` after execution. Pair with
`@DisallowConcurrentExecution` to avoid lost-update conflicts on the map.

```java
@PersistJobDataAfterExecution
@DisallowConcurrentExecution
@ScheduleWithCron(config = "job")
void stateful() { }
```

---

## Externalize cron via config

Config takes priority over the annotation value, so the schedule can be changed
without recompiling. Point `config` at a node; Quartz reads its `cron` field.

```java
@Component
public class ConfigScheduler {

    @ScheduleWithCron(config = "job")
    void schedule() { }
}
```

```hocon
job {
  cron = "0 0 3 * * ?"   # daily at 03:00
}
```

You can also point `config` straight at a string node holding the expression
(e.g. `@ScheduleWithCron(config = "scheduling.jobs.quartz.cron")` with
`scheduling.jobs.quartz.cron = "..."`).

---

## Configuration essentials

Quartz native settings go under `quartz` as `org.quartz.*` properties; Kora
scheduler behaviour and telemetry go under `scheduling`.

```hocon
quartz {
  "org.quartz.threadPool.threadCount" = "10"   # default 10, RAMJobStore by default
}
scheduling {
  waitForJobComplete = true   # block graceful shutdown until current jobs finish (default false)
  telemetry {
    logging.enabled = false   # default false
    metrics.enabled = true    # default true
    tracing.enabled = true    # default true
  }
}
```

For JDBC JobStore persistence, clustering, telemetry tags/attributes and the full
property table see
[scheduling-config-reference.md](references/scheduling-config-reference.md).

---

## Graceful shutdown

With `scheduling.waitForJobComplete = true`, a graceful shutdown blocks until the
running job finishes; otherwise the job thread is interrupted. Long-running jobs
should check the interrupt flag and exit early:

```java
@DisallowConcurrentExecution
@ScheduleWithCron(config = "job")
void processBatch() {
    for (var item : items) {
        if (Thread.currentThread().isInterrupted()) {
            return;   // graceful exit on shutdown
        }
        process(item);
    }
}
```

Full patterns (resource cleanup, partial progress, stateful jobs) are in
[graceful-shutdown-reference.md](references/graceful-shutdown-reference.md).

---

## Error handling

An exception thrown from the job is logged via SLF4J. Wrap the body in try/catch
when you don't want the exception to surface as a Quartz job failure:

```java
@ScheduleWithCron("0 0 * * * ?")
void hourly() {
    try {
        doWork();
    } catch (Exception e) {
        log.error("Hourly job failed", e);
    }
}
```

---

## Common pitfalls

| Symptom | Cause / fix |
|---------|-------------|
| Job never fires | Class not a `@Component`, `QuartzModule` not added to `@KoraApp`, or annotation processor missing |
| `@ScheduleWithTrigger("name")` won't compile | It takes `@Tag(SomeClass.class)`, not a string |
| Trigger never resolves | Tag on the `Trigger` component and on `@ScheduleWithTrigger` must match exactly |
| Overlapping runs | Add `@DisallowConcurrentExecution` |
| Config change ignored | The `config` path must match a node holding `cron` (or a string node) |
| Wrong fire time | Quartz uses the JVM default time zone; set it explicitly if needed |
| State lost between runs | Use JDBC JobStore + `@PersistJobDataAfterExecution` with `@DisallowConcurrentExecution` |

---

## Related skills

- [kora-aop-scheduling-jdk](../kora-aop-scheduling-jdk/SKILL.md) — fixed-rate/delay/once timers
- [kora-aop-logging](../kora-aop-logging/SKILL.md) — `@Log` for scheduled methods
- [kora-config-hocon](../kora-config-hocon/SKILL.md) — typed config for externalized cron
