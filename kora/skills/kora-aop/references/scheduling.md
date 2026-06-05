# Kora scheduling — distilled reference

**Source:** [.kora-agent/kora-docs/mkdocs/docs/en/documentation/scheduling.md](.kora-agent/kora-docs/mkdocs/docs/en/documentation/scheduling.md)  
**Examples:** `.kora-agent/kora-examples/kora-java-scheduling-jdk/`, `.kora-agent/kora-examples/kora-java-scheduling-quartz/`

Focused condensation of `kora-docs/.../documentation/scheduling.md`.

## Two implementations

| Implementation | Artifact | Module | Annotations |
|----------------|----------|--------|-------------|
| JDK `ScheduledExecutorService` | `scheduling-jdk` | `SchedulingJdkModule` | `@ScheduleAtFixedRate`, `@ScheduleWithFixedDelay`, `@ScheduleOnce` |
| Quartz | `scheduling-quartz` | `QuartzModule` | also `@ScheduleWithCron`, `@ScheduleWithTrigger` |

Use JDK by default. Switch to Quartz only when you need cron expressions, persistent state, or custom triggers. Annotations are not interchangeable — `@ScheduleAtFixedRate` works only with JDK; `@ScheduleWithCron` only with Quartz.

All annotations under `ru.tinkoff.kora.scheduling.{jdk|quartz}.annotation.*` (JDK) or `ru.tinkoff.kora.scheduling.quartz.*` (Quartz cron / trigger annotations live directly in the package without `annotation/`).

## JDK setup

```groovy
implementation "ru.tinkoff.kora:scheduling-jdk"
```

```java
@KoraApp
public interface Application extends SchedulingJdkModule, /* ... */ { }
```

### Common JDK config (`scheduling.*`)

```hocon
scheduling {
  threads        = 2                  # ScheduledExecutorService pool size
  shutdownWait   = "30s"              # grace period for in-flight jobs on SIGTERM
  telemetry {
    logging.enabled = false
    metrics.enabled = true
    tracing.enabled = true
  }
}
```

## `@ScheduleAtFixedRate`

Runs every `period`, regardless of previous task completion. Concurrent overlap possible if the task is slower than the period.

```java
@Component
public class CleanupJob {
    @ScheduleAtFixedRate(initialDelay = 30, period = 60, unit = ChronoUnit.SECONDS)
    public void cleanup() { ... }
}
```

Or with config:

```java
@ScheduleAtFixedRate(config = "jobs.cleanup")
public void cleanup() { ... }
```

```hocon
jobs.cleanup { initialDelay = "30s", period = "60s" }
```

When `config` is set, **config values override the annotation** (annotation params become defaults).

## `@ScheduleWithFixedDelay`

Runs `delay` after the previous task **completes**. Never overlaps.

```java
@ScheduleWithFixedDelay(initialDelay = 30, delay = 60, unit = ChronoUnit.SECONDS)
public void afterPrevious() { ... }
```

Config form:

```hocon
jobs.cleanup { initialDelay = "30s", delay = "60s" }
```

## `@ScheduleOnce`

Single run after `delay`.

```java
@ScheduleOnce(delay = 5, unit = ChronoUnit.MINUTES)
public void warmup() { ... }
```

Useful for cache priming, late binding of expensive resources after startup.

## Quartz

```groovy
implementation "ru.tinkoff.kora:scheduling-quartz"
```

```java
@KoraApp
public interface Application extends QuartzModule, /* ... */ { }
```

### Quartz config

```hocon
quartz {
  "org.quartz.threadPool.threadCount" = "10"
  # ... any standard Quartz property
}
scheduling {
  waitForJobComplete = true              # block shutdown until jobs finish
  telemetry { /* same as JDK */ }
}
```

Defaults (from `quartz.properties` inside Quartz):
- `org.quartz.threadPool.threadCount = 10`
- `org.quartz.jobStore.class = org.quartz.simpl.RAMJobStore` (in-memory; switch to JDBC store for persistence)

### `@ScheduleWithCron`

```java
@Component
public class NightlyReport {
    @ScheduleWithCron("0 0 3 * * ?")           // daily at 03:00
    public void run() { ... }
}
```

[Quartz cron syntax](http://www.quartz-scheduler.org/documentation/quartz-2.3.0/tutorials/crontrigger.html) — 7 fields (sec min hour dom month dow [year]).

Config form:

```java
@ScheduleWithCron(config = "jobs.nightly")
public void run() { ... }
```

```hocon
jobs.nightly.cron = "0 0 3 * * ?"
```

### `@ScheduleWithTrigger` (custom `Trigger`)

```java
@KoraApp
public interface Application extends QuartzModule {

    @Tag(MyJobTrigger.class)
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
public class MyJob {
    @ScheduleWithTrigger(@Tag(MyJobTrigger.class))
    public void run() { ... }
}
```

Tag matches the trigger factory's `@Tag` to the scheduled method.

### Quartz-only modifiers

```java
@DisallowConcurrentExecution           // never run two of this job at once
@ScheduleWithCron("0 0 * * * ?")
public void hourly() { ... }

@PersistJobDataAfterExecution          // persist JobDataMap after run (with JDBC store)
@DisallowConcurrentExecution
@ScheduleWithCron("0 0 * * * ?")
public void hourly() { ... }
```

## Graceful shutdown

Both JDK and Quartz invoke an interrupt on running jobs at SIGTERM (after `shutdownWait` / `waitForJobComplete`). Long-running jobs should check `Thread.currentThread().isInterrupted()` and exit:

```java
@ScheduleAtFixedRate(config = "jobs.cleanup")
public void cleanup() {
    while (!stopCondition()) {
        if (Thread.currentThread().isInterrupted()) return;
        doWork();
    }
}
```

## Choosing between JDK and Quartz

| Need | Choose |
|------|--------|
| Fixed interval, in-process, no persistence | JDK |
| Cron schedules | Quartz |
| Persistent jobs (survive restart) | Quartz + JDBC store |
| Cluster-wide scheduling (one node runs at a time) | Quartz + JDBC store + cluster config |
| Lowest startup overhead | JDK |
| Custom complex trigger logic | Quartz + `@ScheduleWithTrigger` |

For most workloads JDK is enough. Reach for Quartz only when you genuinely need its features — it brings a larger dependency footprint and more failure modes.

## Signatures

`void method()` — the only standard signature. Return values are discarded. Throwing inside a scheduled method:
- JDK: exception is logged; next invocation continues.
- Quartz: exception is logged; `@DisallowConcurrentExecution` jobs may be paused depending on Quartz config.
