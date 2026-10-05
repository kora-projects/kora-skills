---
name: kora-aop-scheduling-quartz
description: "Quartz-backed scheduling in Kora 2.x — io.koraframework.scheduling.quartz.QuartzModule from artifact scheduling-quartz (Quartz 2.5.2). Covers @ScheduleQuartzWithCron (cron, identity, config path) and @ScheduleQuartzWithTrigger(MyJob.class) taking a class tag that binds an org.quartz.Trigger from the graph, both from io.koraframework.scheduling.quartz.annotation together with @DisallowConcurrentExecution and @PersistJobDataAfterExecution; compile-time cron validation, the per-job enabled key, a @Tag(SchedulingModule.class) ZoneId for cron time zones, the org.quartz.JobExecutionContext argument, scheduling.quartz.properties / shutdownWait / cleanupOrphanedJobs / compareStartTime, the kora job group, shutdown that interrupts jobs through InterruptableJob, and JDBC JobStore clustering. Use for cron jobs, custom Quartz triggers, misfire policies or persistent job stores; for fixed-rate, fixed-delay and one-shot timers use kora-aop-scheduling-jdk; for one execution per cluster on a plain database table use kora-aop-scheduling-db."
license: Apache-2.0
metadata:
  kora-version: "2.x"
---

# Kora Quartz Scheduling

> **Kora sub-skill — obey the [kora-v2 meta rules](../../SKILL.md) on every task:** **R0** ground the workspace on Kora 2.0 refs before starting (framework source at tag `2.0.0.RC2` + `kora-examples` at `migration/2.0` + Kora 2.0 docs at koraframework.io/v2, which trail the source; 1.x `kora-docs` pages are never an authority) · **R1** read this sub-skill before writing code · **R2** Kora 2.0 APIs only — no Spring/Micronaut/Quarkus, no Kora 1.x APIs, no invented annotations or config keys · **R3** journal any incorrect Kora usage. Add comments/Javadoc only if asked.

| | |
|---|---|
| **Artifact** | `io.koraframework:scheduling-quartz` (BOM `io.koraframework:kora-bom:2.0.0.RC2`) |
| **Module** | `io.koraframework.scheduling.quartz.QuartzModule` (extends `io.koraframework.scheduling.common.SchedulingModule`) |
| **Annotations** | `io.koraframework.scheduling.quartz.annotation.*` — `ScheduleQuartzWithCron`, `ScheduleQuartzWithTrigger`, `DisallowConcurrentExecution`, `PersistJobDataAfterExecution` |
| **Config** | `io.koraframework.scheduling.quartz.QuartzConfig` at `scheduling.quartz` · `scheduling.quartz.properties` · `scheduling.telemetry` |
| **Quartz** | `org.quartz-scheduler:quartz:2.5.2`, pulled in transitively (`api`) |
| **Processor** | `annotation-processors` (Java) / `symbol-processors` (KSP) |

Annotate a method on a graph component with `@ScheduleQuartzWithCron` or
`@ScheduleQuartzWithTrigger`. The processor generates a `$<Class>_<method>_Job` wrapper plus a
`$<Class>_SchedulingModule` `@Module`; `KoraQuartzJobRegistrar` registers every generated job with
the Quartz `Scheduler` at graph init, in the Quartz job group **`kora`**.

**This is not an AOP proxy.** The generated job holds a reference to your component and calls
the method directly, so the class may stay `final` (Java) / non-`open` (Kotlin) — the canonical
examples do exactly that. `open` is only needed if you *also* stack a method-wrapping aspect
(`@Log`, `@Retryable`, `@Timeout`) on the same class.

---

## Quick start

### 1. Dependencies

```groovy
// build.gradle (Java)
dependencies {
    koraBom platform("io.koraframework:kora-bom:$koraVersion")   // koraVersion=2.0.0.RC2
    annotationProcessor "io.koraframework:annotation-processors"

    implementation "io.koraframework:scheduling-quartz"
    implementation "io.koraframework:config-hocon"
    implementation "io.koraframework:logging-logback"
}
```

```kotlin
// build.gradle.kts (Kotlin)
dependencies {
    implementation(platform("io.koraframework:kora-bom:${property("koraVersion")}"))
    ksp("io.koraframework:symbol-processors:${property("koraVersion")}")

    implementation("io.koraframework:scheduling-quartz")
    implementation("io.koraframework:config-hocon")
    implementation("io.koraframework:logging-logback")
}
```

### 2. Plug the module into `@KoraApp`

```java
import io.koraframework.application.graph.KoraApplication;
import io.koraframework.common.annotation.KoraApp;
import io.koraframework.config.hocon.HoconConfigModule;
import io.koraframework.logging.logback.LogbackModule;
import io.koraframework.scheduling.quartz.QuartzModule;

@KoraApp
public interface Application extends HoconConfigModule, LogbackModule, QuartzModule {

    static void main(String[] args) {
        KoraApplication.run(ApplicationGraph::graph);
    }
}
```

### 3. A cron job

```java
import io.koraframework.common.annotation.Component;
import io.koraframework.scheduling.quartz.annotation.ScheduleQuartzWithCron;

@Component
public final class CronScheduler {

    @ScheduleQuartzWithCron("0 0 3 * * ?")   // daily at 03:00
    void nightlyReport() {
        // ...
    }
}
```

The method must be reachable from the generated code, which lands in the **same package** —
package-private (Java) / `internal` or public (Kotlin) is enough.

---

## What's in this skill

| File | Purpose |
|------|---------|
| [references/quartz-scheduling-reference.md](references/quartz-scheduling-reference.md) | Every annotation and its real attributes, generated code, `JobExecutionContext`, cron grammar and validation, error propagation |
| [references/scheduling-config-reference.md](references/scheduling-config-reference.md) | `scheduling.*` keys, Quartz property passthrough, per-job `enabled`, time zone, telemetry, JDBC JobStore and clustering |
| [references/graceful-shutdown-reference.md](references/graceful-shutdown-reference.md) | What shutdown does — `shutdownWait`, then an interrupt through `InterruptableJob` — and how to write a job that stops cleanly |
| [assets/ScheduledJobs.java.template](assets/ScheduledJobs.java.template) | Java starter |
| [assets/ScheduledJobs.kt.template](assets/ScheduledJobs.kt.template) | Kotlin starter |
| [scripts/setup-quartz.sh](scripts/setup-quartz.sh) | Scaffold deps, jobs class and config (`--dry-run` supported) |
| [scripts/create-cron-job.sh](scripts/create-cron-job.sh) | Generate one cron job class + config entry (`--dry-run` supported) |
| [scripts/validate-cron.sh](scripts/validate-cron.sh) | Sanity-check a Quartz cron expression (read-only) |

---

## Quartz, JDK or DB?

Each scheduler has **its own annotation names**, so the annotation you write decides the engine:

| Cron annotation | Package | Scheduler |
|---|---|---|
| `@ScheduleQuartzWithCron` | `io.koraframework.scheduling.quartz.annotation` | Quartz |
| `@ScheduleJdkWithCron` | `io.koraframework.scheduling.jdk.annotation` | JDK `VirtualThreadSchedulingJdkExecutor` (in-process) |
| `@ScheduleDbWithCron` | `io.koraframework.scheduling.db.scheduler.annotation` | db-scheduler (database table, cluster-wide) |

The three cron dialects differ (field count, `?` rules, day-of-week numbering); each annotation's
literal is checked at compile time against its own scheduler's rules.

| Need | Use |
|------|-----|
| Custom `org.quartz.Trigger` (`@ScheduleQuartzWithTrigger`) | **Quartz** |
| Misfire policies, Quartz calendars, `JobExecutionContext` / `JobDataMap` | **Quartz** |
| Persistent or clustered job store (JDBC) with Quartz semantics | **Quartz** |
| One execution per firing across replicas, no Quartz tables or triggers | **DB** — see [kora-aop-scheduling-db](../kora-aop-scheduling-db/SKILL.md) |
| Cron with no extra dependency | **JDK** — `@ScheduleJdkWithCron` (also accepts 5-field cron) |
| Fixed rate / fixed delay / run once | **JDK** — see [kora-aop-scheduling-jdk](../kora-aop-scheduling-jdk/SKILL.md) |

Same three-way table in all three scheduling sub-skills:

| Need | JDK | Quartz (this skill) | DB (db-scheduler) |
|---|---|---|---|
| Extra infrastructure | none | none; a JDBC JobStore + Quartz tables for persistence/clustering | a JDBC `DataSource` + one table |
| Who runs a firing | every replica | every replica (`RAMJobStore`); one node when clustered on a JDBC JobStore | one replica, cluster-wide |
| Survives restart | no | only with a JDBC JobStore | yes — the next execution time lives in the table |
| Fixed rate | `@ScheduleJdkAtFixedRate` | via a custom `Trigger` | no |
| Fixed delay | `@ScheduleJdkWithFixedDelay` | via a custom `Trigger` | `@ScheduleDbWithFixedDelay` |
| One-shot | `@ScheduleJdkOnce`, every process start | via a custom `Trigger` | `@ScheduleDbOnce`, one pending execution cluster-wide |
| Cron | `@ScheduleJdkWithCron` — Kora `CronExpression`, 5/6/7 fields, no `L W # C` | `@ScheduleQuartzWithCron` — Quartz cron, 6/7 fields, `L W # C` | `@ScheduleDbWithCron` — db-scheduler `CronSchedule`, Spring-style 6 fields |
| Cron literal checked at compile time | yes | yes | yes |
| Cron time zone | `@Tag(SchedulingModule.class) ZoneId` component, else the JVM default | same | same |
| Switch a job off | `enabled = false` under its `config` path | same — the job loses its triggers | same — its pending execution is removed |
| Custom trigger, misfire policy, `JobDataMap` | no | yes | no |
| Runs on | virtual threads, cap `executionParallelism` (unlimited) | Quartz `SimpleThreadPool` platform threads (10) | virtual threads, cap `executionParallelism` (10) |
| Shutdown | waits `shutdownWait`, then interrupts | waits `shutdownWait`, interrupts via `InterruptableJob`, waits `shutdownWait` again | waits `shutdownWait`, then interrupts |

---

## Annotations

All four live in `io.koraframework.scheduling.quartz.annotation`.

| Annotation | Target | Attributes |
|------------|--------|------------|
| `@ScheduleQuartzWithCron` | method | `value` (cron), `identity` (trigger identity), `config` (config path) — all `String`, all default `""` |
| `@ScheduleQuartzWithTrigger` | method | `Class<?> value()` — a **class tag**, not a nested `@Tag`, not a string |
| `@DisallowConcurrentExecution` | method | none |
| `@PersistJobDataAfterExecution` | method | none |

`@DisallowConcurrentExecution` and `@PersistJobDataAfterExecution` are **Kora's own**
annotations — not re-exports. The generators also accept the Quartz originals
(`org.quartz.DisallowConcurrentExecution`, `org.quartz.PersistJobDataAfterExecution`), but only
**on the class**; the Kora ones are read **on the method only**. Either form ends up as the
`org.quartz.*` annotation on the generated job class.

### `@ScheduleQuartzWithTrigger` — the 2.0 signature

```java
@KoraApp
public interface Application extends QuartzModule {

    @Tag(TriggerScheduler.class)
    default Trigger myTrigger() {
        return TriggerBuilder.newTrigger()
            .withIdentity("myTrigger")
            .startNow()
            .withSchedule(SimpleScheduleBuilder.simpleSchedule()
                .withIntervalInSeconds(5)
                .repeatForever())
            .build();
    }
}

@Component
public final class TriggerScheduler {

    @ScheduleQuartzWithTrigger(TriggerScheduler.class)   // class tag passed directly
    void schedule() { }
}
```

```kotlin
@ScheduleQuartzWithTrigger(TriggerScheduler::class)
fun schedule() { }
```

The class you pass becomes a `@Tag` on the `org.quartz.Trigger` parameter of the generated
factory method, so the graph must contain a `Trigger` under exactly that tag. The convention is
to tag with the job class itself.

**Kora 1.x wrote `@ScheduleWithTrigger(@Tag(MyJob.class))`.** In 2.0 the attribute is
`Class<?>`, so the nested form fails at compile time:
`error: annotation not valid for an element of type Class<?>`.

### `@ScheduleQuartzWithCron`

```java
@ScheduleQuartzWithCron("0 0 9 ? * MON-FRI")                 // 09:00 on weekdays
void morningReport() { }

@ScheduleQuartzWithCron(value = "0 0 * * * ?", identity = "hourly")
void hourly() { }

@ScheduleQuartzWithCron(config = "jobs.nightly")             // cron comes from config
void nightly() { }
```

Quartz cron is the 6- or 7-field form (`sec min hour day-of-month month day-of-week [year]`);
exactly one of day-of-month and day-of-week must be `?`, and day-of-week counts `1` = Sunday.
`identity` defaults to `<fully.qualified.Class>#<method>`.

**The literal is validated at compile time.** `@ScheduleQuartzWithCron("0 0 12 * * *")` does not
build:

```
Invalid CRON expression '0 0 12 * * *' in @ScheduleQuartzWithCron on 'com.example.Jobs#run()':
'?' must be used in exactly one of the day-of-month and day-of-week fields.
```

followed by the expected field layout, two examples and a pointer to the annotation Javadoc. The
check reports only what Quartz itself would reject; a cron that comes from config is validated at
graph init by `QuartzCronUtils` with `IllegalArgumentException: Invalid CRON expression '…' for
Quartz job '<Class>#<method>': …` and the same hint.

With `config`, the node may be a bare string (`jobs.nightly = "0 0 3 * * ?"`) or an object with
`cron`, `enabled` and a per-job `telemetry` block. If `value` is also set it is the fallback used
when the config node is absent; if `value` is empty the config node is **required** and a missing
one fails the graph build. `enabled = false` registers the job **without triggers**, which also
unschedules triggers persisted by an earlier run. See
[scheduling-config-reference.md](references/scheduling-config-reference.md#per-job-configuration).

### Time zone

Cron triggers are evaluated in the time zone of an optional `ZoneId` component tagged with
`SchedulingModule`, otherwise in the JVM default zone. The same component drives the JDK and DB
schedulers:

```java
@KoraApp
public interface Application extends QuartzModule {

    @Tag(SchedulingModule.class)          // io.koraframework.scheduling.common.SchedulingModule
    default ZoneId schedulingZone() {
        return ZoneId.of("Europe/Moscow");
    }
}
```

Changing the zone reschedules a persisted cron trigger at the next start.

---

## Contracts

- **Synchronous only.** A scheduled method returns `void` / `Unit` and takes either no
  arguments or a single `org.quartz.JobExecutionContext`.
- Kotlin `suspend` is rejected by KSP: *"Suspend methods are not supported by the scheduling
  generator"* — the message points at `StructuredTaskScope` for real parallelism.
- `Mono`/`Flux`/`CompletionStage` are not Kora 2.0 contracts anywhere, scheduling included.
  `Context` no longer exists in the framework; use the `JobExecutionContext` argument for
  Quartz fire-time data.
- The enclosing class must be a graph component (`@Component`, or supplied by a `@Module`
  factory method) — the generated factory takes it as a direct dependency.

---

## Thread model

Quartz jobs do **not** run on Kora's virtual threads. `KoraQuartzScheduler` builds a plain
`StdSchedulerFactory`, so jobs run on Quartz's own `SimpleThreadPool`: platform threads named
`kora-quartz-scheduler_Worker-N`, `org.quartz.threadPool.threadCount` = 10 by default,
non-daemon. That thread count is the hard ceiling on concurrent job executions across the whole
application; oversubscribing it delays firings and produces misfires.

Kora still binds its own context around the call — `KoraQuartzJob.execute` installs the Kora
`MDC`, a fresh OpenTelemetry context and the scheduling `Observation` before invoking your
method, so logging and tracing work normally inside the job body.

---

## Configuration essentials

```hocon
scheduling {
  quartz {
    # raw org.quartz.* properties, passed to StdSchedulerFactory
    properties {
      "org.quartz.threadPool.threadCount" = "10"
    }
    shutdownWait = 30s            # default 30s — wait, interrupt, wait again
    compareStartTime = false      # default false — a changed start time does not reschedule a persisted trigger
    cleanupOrphanedJobs = false   # default false — true removes Kora jobs of deleted classes before start
  }

  telemetry {
    logging.enabled = true      # default false
    metrics.enabled = true      # default false
    tracing.enabled = true      # default true
  }
}
```

Kora forces `org.quartz.scheduler.instanceName = kora-quartz-scheduler` and
`org.quartz.scheduler.instanceId = AUTO` as *defaults* — both are overridable from
`scheduling.quartz.properties`. Everything else comes from the `org/quartz/quartz.properties`
bundled in the Quartz jar (`SimpleThreadPool`, `RAMJobStore`, `misfireThreshold = 60000`).

**Persistent job stores** (JDBC JobStore): Kora jobs live in the group `kora`, keyed by the
generated job class's canonical name. A persisted trigger is left alone at restart unless its
schedule (cron, repeat interval/count), end time or cron time zone changed — so misfire handling
for executions missed while the service was down is kept. Set `compareStartTime = true` only if
every trigger uses a fixed `startAt()`. `cleanupOrphanedJobs` is unsafe when several applications
share the Quartz tables under the same scheduler name, or during a rolling deploy that runs two
versions at once. Details in
[scheduling-config-reference.md](references/scheduling-config-reference.md#persistence-jdbc-jobstore).

**Keys that no longer exist.** The 1.x root `quartz { "org.quartz.*" }` block and
`scheduling.waitForJobComplete`, and the RC1-era `scheduling.quartz.waitForJobComplete`, are not
read. Unknown HOCON keys are ignored without a warning, so a stale config starts green on Quartz
defaults instead of your settings. Full table in
[scheduling-config-reference.md](references/scheduling-config-reference.md).

---

## Shutdown — wait, interrupt, wait

`KoraQuartzScheduler.release()` puts the scheduler on `standby()` (no new firings), waits up to
`scheduling.quartz.shutdownWait` (default 30 s) for running jobs, then **interrupts** the threads
still running a Kora job — `KoraQuartzJob` implements `org.quartz.InterruptableJob` — logs
`KoraQuartzScheduler interrupting jobs [...] still running after PT30S` at WARN, waits up to
`shutdownWait` once more and shuts Quartz down. Worst case is about 2× `shutdownWait`.

So a long job should honour `Thread.currentThread().isInterrupted()` / `InterruptedException`
and stop cleanly. `shutdownWait = 0s` interrupts immediately; a large value such as `365d` waits
for completion — keep the platform grace period (Kubernetes `terminationGracePeriodSeconds`) at
least as long. Patterns in
[graceful-shutdown-reference.md](references/graceful-shutdown-reference.md).

---

## Error handling

`KoraQuartzJob.execute` records the failure on the observation and **rethrows**, so the
exception reaches Quartz and the trigger's misfire/refire policy applies. With
`scheduling.telemetry.logging.enabled = true` Kora logs it at WARN with `exceptionType` and
`exceptionMessage`. Catch inside the method if a failure should not surface as a Quartz job
failure.

---

## Coming from RC1 / earlier 2.0 snapshots

Kora PR #952 renamed the Quartz API and changed several defaults after `2.0.0.RC1`. The old
names no longer exist, so code fails to compile — but the config renames are **silent**. The
`kora-examples` `migration/2.0` Quartz apps (`kora-java-scheduling-quartz`,
`kora-kotlin-scheduling-quartz`) were written against RC1 and, at the time of writing, still use the
old names — rename when copying from them.

| RC1 / earlier snapshot | Now | Consequence if you skip it |
|---|---|---|
| `io.koraframework.scheduling.quartz.ScheduleWithCron` | `io.koraframework.scheduling.quartz.annotation.ScheduleQuartzWithCron` | compile error |
| `io.koraframework.scheduling.quartz.ScheduleWithTrigger` | `io.koraframework.scheduling.quartz.annotation.ScheduleQuartzWithTrigger` | compile error |
| `io.koraframework.scheduling.quartz.DisallowConcurrentExecution` / `PersistJobDataAfterExecution` | same names in `io.koraframework.scheduling.quartz.annotation` | compile error |
| `SchedulingQuartzConfig` | `io.koraframework.scheduling.quartz.QuartzConfig` | compile error where referenced |
| `scheduling.quartz.waitForJobComplete` (boolean, `true`) | `scheduling.quartz.shutdownWait` (duration, `30s`) — wait, interrupt, wait again | old key ignored silently; shutdown is bounded and interrupts now |
| jobs in Quartz group `DEFAULT` | group `kora`; a Kora 1.x/RC1 job of a known class is moved automatically at start | none — logged as `Quartz Job '…' moved from the DEFAULT group to the kora group` |
| persisted triggers rescheduled on every start | kept unless schedule, end time or time zone changed; `compareStartTime = true` restores the start-time comparison | — |
| — | `cleanupOrphanedJobs` (default `false`) | opt-in |
| — | per-job `enabled` under the `config` path | opt-in |
| JVM default zone only | `@Tag(SchedulingModule.class) ZoneId` component | opt-in |
| cron errors only at graph init | literal cron validated at compile time | a bad literal no longer builds |
| `SchedulingTelemetryFactory.get(configPath, telemetryConfig, jobClass, jobMethod)` | `get(schedulerType, configPath, telemetryConfig, jobClass, jobMethod)` | a custom factory no longer compiles |

Metrics and spans gained a `scheduling.system` tag/attribute (`quartz`), and job log records a
`schedulerType` key.

---

## Common pitfalls

| Symptom | Cause / fix |
|---------|-------------|
| `cannot find symbol: class ScheduleWithCron` / unresolved `io.koraframework.scheduling.quartz.ScheduleWithCron` | RC1-era name — use `io.koraframework.scheduling.quartz.annotation.ScheduleQuartzWithCron` (same for `ScheduleWithTrigger` → `ScheduleQuartzWithTrigger`) |
| `annotation not valid for an element of type Class<?>` | 1.x `@ScheduleWithTrigger(@Tag(X.class))`; 2.0 takes `@ScheduleQuartzWithTrigger(X.class)` |
| `Invalid CRON expression '…' in @ScheduleQuartzWithCron on '…'` at compile time | The literal breaks Quartz rules — usually no `?` (`0 0 12 * * *`) or a 5-field Unix cron. Fix the expression; it would have failed at startup anyway |
| Job never fires, no error | Class is not a graph component, `QuartzModule` is missing from `@KoraApp`, the processor is not on the build — or `enabled = false` under its `config` path (logged at INFO as `Quartz Job '…' has no triggers and is not scheduled`) |
| `No component found` for `Trigger` | No `@Tag(X.class) Trigger` in the graph for the class passed to `@ScheduleQuartzWithTrigger` |
| `IllegalStateException: Quartz trigger '…' is declared more than once, by jobs '…' and '…'` at startup | Two jobs share a trigger identity — set a unique `@ScheduleQuartzWithCron(identity = …)` or `TriggerBuilder.withIdentity(…)` |
| Startup fails with `Graph node value was not initialized because condition failed: <reason>` | The scheduled method sits on a `@Conditional` component whose condition failed: the generated job factory takes the component directly and carries no condition. Fixed in `2.0.0.RC2` (kora-projects/kora PR #962) — the job then gets the same condition; only `2.0.0.RC1` is affected; on RC1 keep the scheduled method on an unconditional component; if it must reach the conditional one, inject `All<T>` and return when it is empty (`@Nullable T` hits kora-projects/kora PR #960 on RC1) |
| KSP: *Suspend methods are not supported* | Drop `suspend`; scheduled contracts are synchronous |
| Thread-count / property settings ignored | Config sits at the 1.x root `quartz { }` instead of `scheduling.quartz.properties { }` |
| `waitForJobComplete` has no effect | Gone; use `scheduling.quartz.shutdownWait` |
| Shutdown takes ~1 minute | A job outlived `shutdownWait` (30 s), was interrupted and ignored it — bound the body and honour the interrupt |
| `JobPersistenceException: Couldn't retrieve job because a required class was not found` on every start | A job class was deleted or renamed and its row stayed in the JDBC store — enable `cleanupOrphanedJobs` (single-application store, no mixed-version rollout) or delete the rows |
| No `scheduling.job.duration` metric | `scheduling.telemetry.metrics.enabled` defaults to **false** in 2.0 |
| `@PersistJobDataAfterExecution` loses state on restart | Default store is `RAMJobStore`; persistence needs a JDBC JobStore |
| Wrong fire time | Cron runs in the JVM default zone unless a `@Tag(SchedulingModule.class) ZoneId` component exists |

---

## Related skills

- [kora-aop-scheduling-jdk](../kora-aop-scheduling-jdk/SKILL.md) — fixed rate/delay/once and JDK cron
- [kora-aop-scheduling-db](../kora-aop-scheduling-db/SKILL.md) — cluster-wide single execution on db-scheduler, without Quartz
- [kora-aop-logging](../kora-aop-logging/SKILL.md) — `@Log` on a scheduled method (that one *does* need `open`)
- [kora-config-hocon](../kora-config-hocon/SKILL.md) — typed config for externalised cron
- [kora-di-runtime](../kora-di-runtime/SKILL.md) — `@Conditional`, `All<T>`, release order
- [kora-telemetry-metrics](../kora-telemetry-metrics/SKILL.md) — enabling the metrics that scheduling reports
