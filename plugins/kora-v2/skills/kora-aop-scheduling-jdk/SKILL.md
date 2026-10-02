---
name: kora-aop-scheduling-jdk
description: "In-process scheduled jobs in Kora 2.x — @ScheduleJdkAtFixedRate, @ScheduleJdkWithFixedDelay, @ScheduleJdkOnce and @ScheduleJdkWithCron from io.koraframework.scheduling.jdk.annotation, contributed by SchedulingJdkModule (artifact io.koraframework:scheduling-jdk): one platform timer thread dispatches each run onto a fresh virtual thread. Covers the config attribute for externalising timings and switching a job off (enabled), the scheduling.jdk.shutdownWait / executionParallelism and scheduling.telemetry keys, compile-time cron validation, the @Tag(SchedulingModule.class) ZoneId cron time zone, cron DST handling, per-job telemetry overrides, the RC1 → master renames, and why a scheduled method must be a no-argument, non-suspend member of a @Component. Use for heartbeat, cleanup, cache-warm and in-process cron jobs. For one execution per cluster use kora-aop-scheduling-db; for Quartz triggers, misfire policies or L/W/# cron use kora-aop-scheduling-quartz."
license: Apache-2.0
metadata:
  kora-version: "2.x"
---

# Kora AOP Scheduling (JDK)

> **Kora sub-skill — obey the [kora-v2 meta rules](../../SKILL.md) on every task:** **R0** ground the workspace on Kora 2.0 refs before starting (framework source at tag `2.0.0.RC2` + `kora-examples` at `migration/2.0` + Kora 2.0 docs at koraframework.io/v2, which trail the source; 1.x `kora-docs` pages are never an authority) · **R1** read this sub-skill before writing code · **R2** Kora 2.0 APIs only — no Spring/Micronaut/Quarkus, no Kora 1.x APIs, no invented annotations or config keys · **R3** journal any incorrect Kora usage. Add comments/Javadoc only if asked.

| | |
|---|---|
| **Artifact** | `io.koraframework:scheduling-jdk` (version from `io.koraframework:kora-bom`) |
| **Module** | `io.koraframework.scheduling.jdk.SchedulingJdkModule` (extends `io.koraframework.scheduling.common.SchedulingModule`) |
| **Annotations** | `io.koraframework.scheduling.jdk.annotation.*` |
| **Processor** | Java `annotationProcessor "io.koraframework:annotation-processors"` · Kotlin `ksp("io.koraframework:symbol-processors")` |
| **Config roots** | `scheduling.jdk` · `scheduling.telemetry` · one arbitrary path per job via `config = "…"` |
| **Runtime** | `VirtualThreadSchedulingJdkExecutor` — one platform timer thread, one fresh virtual thread per run |

In-process scheduling: a single platform timer thread decides *when*, and every run executes on its
own virtual thread. No external scheduler, no job store — jobs live for the lifetime of the process
only, and every replica runs every job. The module has its **own cron evaluator**, so a plain cron job
does not require Quartz.

---

## What changed from Kora 1.x

Read this before porting a 1.x service: none of it is covered by the migration guides, which mention
only the Quartz trigger annotation change.

| 1.x | 2.0 | Consequence if you skip it |
|---|---|---|
| `ru.tinkoff.kora.scheduling.jdk.annotation.ScheduleAtFixedRate` / `ScheduleWithFixedDelay` / `ScheduleOnce` | `io.koraframework.scheduling.jdk.annotation.ScheduleJdkAtFixedRate` / `ScheduleJdkWithFixedDelay` / `ScheduleJdkOnce` — package **and** simple name changed | Compile error `cannot find symbol` — loud, harmless |
| `ru.tinkoff.kora:scheduling-jdk`, BOM `kora-parent` | `io.koraframework:scheduling-jdk`, BOM `io.koraframework:kora-bom` | Unresolved dependency |
| Kotlin processor `scheduling-ksp` | `scheduling-symbol-processor`, normally via the aggregate `symbol-processors` | `scheduling-ksp` on Central is a 1.x leftover, **not** in the 2.0 BOM |
| `scheduling.shutdownWait` | **`scheduling.jdk.shutdownWait`** | Stale key is an unknown HOCON key: ignored silently, shutdown falls back to 30 s |
| `scheduling.threads` (pool size) | **removed** — runs are virtual threads; the optional cap is `scheduling.jdk.executionParallelism` (default unlimited) | Ignored silently (see [Thread model](#thread-model)) |
| Cron only via `scheduling-quartz` | **`@ScheduleJdkWithCron` in `scheduling-jdk`** | You may be pulling in Quartz for nothing |
| "fixed rate may overlap" | **never overlaps** | See [Overlap](#overlap-fixed-rate-does-not-overlap) |
| "class must be non-`final` / `open`" | **not required by scheduling** | See [What a scheduled method must satisfy](#what-a-scheduled-method-must-satisfy) |
| `telemetry.metrics.enabled` default `true` | **default `false`** | Job metrics silently absent |

---

## Coming from RC1 / earlier 2.0 snapshots

Kora PR #952 renamed the annotations and moved the job classes after `2.0.0.RC1`. Code written against
RC1 or an earlier `2.0.0-SNAPSHOT` does not compile on `2.0.0.RC2`. The `kora-examples`
`migration/2.0` scheduling apps (`kora-java-scheduling-jdk`, `kora-kotlin-scheduling-jdk`) were
written against RC1 and, at the time of writing, still use the old names — rename when copying from them.

| RC1 / earlier snapshot | master / RC2 | Consequence if you skip it |
|---|---|---|
| `@ScheduleAtFixedRate` | `@ScheduleJdkAtFixedRate` | `cannot find symbol` |
| `@ScheduleWithFixedDelay` | `@ScheduleJdkWithFixedDelay` | `cannot find symbol` |
| `@ScheduleOnce` | `@ScheduleJdkOnce` | `cannot find symbol` |
| `@ScheduleWithCron` (`…scheduling.jdk.annotation`) | `@ScheduleJdkWithCron` | `cannot find symbol` |
| `io.koraframework.scheduling.jdk.{FixedRateJob, FixedDelayJob, RunOnceJob, CronJob, AbstractJob}` | `io.koraframework.scheduling.jdk.job.{FixedRateJob, FixedDelayJob, RunOnceJob, CronJob, KoraJdkJob}` | `@KoraAppTest(components = …)` and custom jobs stop compiling |
| `io.koraframework.scheduling.jdk.CronExpression` | `io.koraframework.scheduling.jdk.util.CronExpression` | `cannot find symbol` |
| `scheduling.jdk.maxConcurrentExecutions` (post-RC1 snapshots only; RC1 had just `shutdownWait`) | `scheduling.jdk.executionParallelism` | Stale key ignored silently — the cap is gone, runs are unlimited |
| — | `enabled` key under every job `config` path | New: switch a job off without a rebuild |
| cron in the JVM default zone only | optional `@Tag(SchedulingModule.class) ZoneId` component | New: see [Time zone](#time-zone) |
| bad cron literal fails at startup | fails the **build** | New: compile-time cron check |
| `SchedulingTelemetryFactory.get(configPath, telemetryConfig, jobClass, jobMethod)` | `get(schedulerType, configPath, telemetryConfig, jobClass, jobMethod)` | A custom `SchedulingTelemetryFactory` stops compiling |
| metric tags / span attributes without the scheduler | `scheduling.system = jdk` on `scheduling.job.duration` and the span | Dashboards can split by scheduler |

---

## Quick Start

### 1. Dependency

Versions come from the BOM — never pin an individual `io.koraframework:*` artifact.

```groovy
// build.gradle (Java)
configurations {
    koraBom
    annotationProcessor.extendsFrom(koraBom); compileOnly.extendsFrom(koraBom); implementation.extendsFrom(koraBom)
    api.extendsFrom(koraBom); testImplementation.extendsFrom(koraBom); testAnnotationProcessor.extendsFrom(koraBom)
}

dependencies {
    koraBom platform("io.koraframework:kora-bom:$koraVersion")   // koraVersion=2.0.0.RC2
    annotationProcessor "io.koraframework:annotation-processors" // mandatory — generates the job module

    implementation "io.koraframework:scheduling-jdk"
    implementation "io.koraframework:config-hocon"
    implementation "io.koraframework:logging-logback"
}
```

```kotlin
// build.gradle.kts (Kotlin)
dependencies {
    implementation(platform("io.koraframework:kora-bom:${property("koraVersion")}"))
    ksp("io.koraframework:symbol-processors:${property("koraVersion")}")

    implementation("io.koraframework:scheduling-jdk")
    implementation("io.koraframework:config-hocon")
    implementation("io.koraframework:logging-logback")
}
```

### 2. Plug the module into `@KoraApp`

```java
@KoraApp
public interface Application extends
    HoconConfigModule,
    LogbackModule,
    SchedulingJdkModule {

    static void main(String[] args) {
        KoraApplication.run(ApplicationGraph::graph);
    }
}
```

### 3. Declare a scheduled component

```java
package com.example.app.jobs;

import io.koraframework.common.annotation.Component;
import io.koraframework.scheduling.jdk.annotation.ScheduleJdkAtFixedRate;

import java.time.temporal.ChronoUnit;

@Component
public final class ScheduledJobs {   // final is fine — scheduling does not proxy the class

    @ScheduleJdkAtFixedRate(initialDelay = 30, period = 60, unit = ChronoUnit.SECONDS)
    void heartbeat() {
        // runs every 60s
    }
}
```

The processor emits a `@Module` interface `$ScheduledJobs_SchedulingModule` next to your class; the
`@KoraApp` graph picks it up on its own. You never reference it by hand.

---

## Annotations

All four live in `io.koraframework.scheduling.jdk.annotation`, target `METHOD`, and carry a
`String config() default ""`.

| Annotation | Attributes | Interval measured | Overlap |
|---|---|---|---|
| `@ScheduleJdkAtFixedRate` | `initialDelay` (long, `0`), `period` (long, `0`), `unit` (`ChronoUnit`, `MILLIS`), `config` | start → start | never |
| `@ScheduleJdkWithFixedDelay` | `initialDelay` (long, `0`), `delay` (long, `0`), `unit` (`ChronoUnit`, `MILLIS`), `config` | end → start | never |
| `@ScheduleJdkOnce` | `delay` (long, `0`), `unit` (`ChronoUnit`, `MILLIS`), `config` | one run after `delay` | n/a |
| `@ScheduleJdkWithCron` | `value` (String, `""`), `config` | next cron fire time | never |

`unit` applies to the annotation's own numbers only; it is not a config key. Durations that come from
config are written as HOCON/YAML durations (`"30s"`, `5ms`, `2m`).

Either the primary attribute or `config` must be set. `period`/`delay` of `0` and a blank cron `value`
count as *unset*, and the build fails with, e.g.:

```
Either period() or config() annotation parameter must be provided
```

### Overlap: fixed rate does **not** overlap

`VirtualThreadSchedulingJdkExecutor` schedules the next periodic run only after the current one has
returned, and each job additionally serialises its runs behind a per-job lock. A fixed-rate job keeps
its original timetable: if a run overruns the period, the next run starts as soon as it returns
(catching up), never in parallel with it. The framework test
`fixedRateCatchesUpWithoutOverlappingExecutions` pins exactly that.

So the choice between the two periodic annotations is about **where the interval is measured**, not
about overlap:

- `@ScheduleJdkAtFixedRate` — tries to keep a fixed cadence; after an overrun it starts the next run late.
- `@ScheduleJdkWithFixedDelay` — always leaves `delay` idle after the previous run returned, so the cadence
  drifts with execution time.

Two *different* jobs can run at the same time — each run gets its own virtual thread, subject only to
the optional `executionParallelism` cap below.

### `@ScheduleJdkWithCron`

```java
@ScheduleJdkWithCron("0 0 3 * * ?")     // 03:00 every day, in the scheduling time zone
void nightlyCompaction() { }
```

5, 6 or 7 space-separated fields (`[second] minute hour day-of-month month day-of-week [year]`),
`* , - / ?`, month aliases `JAN`–`DEC` and day aliases `SUN`–`SAT` (including ranges, lists and steps
such as `JUL-OCT`, `JUL/2`, `WED-FRI`); day-of-week `0` and `1` are both Sunday. Quartz modifiers `L`,
`W`, `#`, `C` are **not** supported and `@ScheduleJdkWithCron` is still in-process only.

**A cron literal is checked at compile time.** The processor reports wrong field counts, out-of-range
values, reversed ranges and `L`/`W`/`#`/`C`, and fails the build. The check is deliberately incomplete —
it reports only what the JDK parser rejects too, and whatever it does not model is still parsed at
startup:

```
Invalid CRON expression '0 0 0 L * ?' in @ScheduleJdkWithCron on 'com.example.Jobs#monthEnd()': day-of-month modifier L in L is not supported by the JDK scheduler.
The JDK scheduler expects 5, 6 or 7 fields, the second and year fields are optional:
…
See the Javadoc of @ScheduleJdkWithCron for details.
```

A cron that comes from **config** is parsed while the graph is built, so it fails **startup** with
`IllegalArgumentException: Invalid CRON expression '…' for JDK job '<fqcn>#<method>': …` followed by
the same field diagram.

#### Time zone

Cron is evaluated in the zone of an optional `java.time.ZoneId` component tagged with
`io.koraframework.scheduling.common.SchedulingModule`; without one, in the JVM default zone. The
generated cron job factory takes it as `@Tag(SchedulingModule.class) @Nullable ZoneId`. One component
sets the zone for the cron jobs of all three schedulers:

```java
@KoraApp
public interface Application extends HoconConfigModule, LogbackModule, SchedulingJdkModule {

    @Tag(SchedulingModule.class)          // io.koraframework.common.annotation.Tag
    default ZoneId schedulingZone() {
        return ZoneId.of("Europe/Moscow");
    }
}
```

Fixed-rate, fixed-delay and one-shot jobs are durations and ignore it.

**Daylight-saving transitions** (in that zone): a local time that does not exist on the
spring-forward day is **skipped**, not shifted — `0 30 2 * * ?` in `Europe/Berlin` does not fire on the
day 02:30 is missing. A local time that occurs twice on the fall-back day fires **twice**, once per
occurrence, in instant order. Schedule daily jobs outside the transition hour, or use a zone without
DST (for example a `ZoneId.of("UTC")` scheduling component), if that matters.

Details, config form and the routing rule against Quartz:
[references/jdk-scheduling-reference.md](references/jdk-scheduling-reference.md).

---

## What a scheduled method must satisfy

The scheduling processor does **not** generate an AOP proxy. It generates a module whose factory
method takes `ValueOf<YourClass>` and calls `target.get().yourMethod()`. Therefore:

**Required**

- the bearing class is a graph component (`@Component`, or produced by a `@Module` factory method);
- the method is a **member** method (not top-level, not local) with **no arguments**;
- the method is visible from its own package — `private` will not compile;
- the method is **not** `suspend` (Kotlin) and not reactive. Kora 2.0 contracts are synchronous.

**Not required**

- the class does **not** have to be non-`final` (Java) or `open` (Kotlin). The migrated examples ship
  `@Component public final class FixRateScheduler` and `@Component class FixRateScheduler` and both
  schedule correctly.

`open`/non-`final` becomes necessary only if you stack a *proxy-based* aspect on the same class —
`@Log`, `@Retryable`, `@CircuitBreakable`, `@Timeout`, `@Cacheable`. That requirement belongs to those
aspects, not to scheduling; see [kora-aop-logging](../kora-aop-logging/SKILL.md) and
[kora-aop-resilient](../kora-aop-resilient/SKILL.md).

A `suspend` scheduled function is rejected at build time, not silently ignored:

```
Suspend methods are not supported by the scheduling generator.
…
For structured concurrency, enable Java preview features with --enable-preview and use StructuredTaskScope
…
Fix: remove suspend from the function.
```

---

## Externalized parameters (`config`)

With `config = "<path>"` the processor generates a `SchedulingJobConfig` subtype bound to that path.
Annotation attributes become **defaults** of the generated config; values in the config file win.
Omitting the annotation attribute entirely makes the config key **mandatory**.

```java
@ScheduleJdkAtFixedRate(config = "scheduling.jobs.heartbeat")
void heartbeat() { }
```

```hocon
scheduling.jobs.heartbeat {
  initialDelay = 10s
  period = 30s
  enabled = true      # default; false = the job is never scheduled
}
```

| Annotation | Keys under the config path |
|---|---|
| `@ScheduleJdkAtFixedRate` | `initialDelay`, `period`, `enabled` |
| `@ScheduleJdkWithFixedDelay` | `initialDelay`, `delay`, `enabled` |
| `@ScheduleJdkOnce` | `delay`, `enabled` |
| `@ScheduleJdkWithCron` | either a string (the expression) or an object with `cron`, `enabled` |

Every object form additionally accepts a `telemetry { … }` block that overrides the global scheduling
telemetry for that one job.

### Switching a job off — `enabled`

`enabled` (default `true`, from `SchedulingJobConfig`) exists only for jobs declared with `config`. A
disabled job is never scheduled; at startup it logs at INFO
`JDK Job '<fqcn>#<method>' is disabled by configuration and won't be scheduled`.

```hocon
scheduling.jobs.heartbeat.enabled = false
scheduling.jobs.heartbeat.enabled = ${?HEARTBEAT_ENABLED}

# a cron job: use the object form — the bare-string form has nowhere to put `enabled`
scheduling.jobs.compaction { cron = "0 0 3 * * ?", enabled = false }
```

For a cron job whose annotation also has a `value`, the annotation expression is used only when the
config path is absent altogether; a string at the path replaces it.

Pick a path that does not collide with the module's own sections. `scheduling.jobs.<name>` (as in the
official examples) is safe; `scheduling.jdk` and `scheduling.telemetry` are taken.

---

## Module configuration

Defaults below are the ones in source — nothing here is aspirational.

```hocon
scheduling {
  jdk {
    shutdownWait = 30s              # graceful drain budget for running jobs (default 30s)
    executionParallelism = 100      # cap on runs executing at once (default Integer.MAX_VALUE = unlimited)
  }

  telemetry {
    logging.enabled = false      # default false
    metrics.enabled = false      # default false
    tracing.enabled = true       # default true (no-op without a Tracer component)
  }
}
```

There is **no `scheduling.threads` key in Kora 2.0.** Writing one is not an error — it is an unknown
HOCON key, silently ignored. Runs are virtual threads, so there is no pool to size; the only knob is the
concurrency cap `scheduling.jdk.executionParallelism`. The same goes for `maxConcurrentExecutions`, its
name in post-RC1 snapshots: in `2.0.0.RC2` it is an unknown key and the cap silently disappears.

Full key list, per-job overrides, metric names and span attributes:
[references/scheduling-config-reference.md](references/scheduling-config-reference.md).

---

## Thread model

`SchedulingJdkModule` provides `VirtualThreadSchedulingJdkExecutor` as the default
`SchedulingJdkExecutor`:

- **one platform timer thread**, `kora-jdk-scheduler-timer` (non-daemon), only decides *when* a run is
  due;
- every run executes on a **fresh virtual thread** named `kora-jdk-scheduler-job-N` — threads are not
  reused and do not inherit `InheritableThreadLocal` values;
- `scheduling.jdk.executionParallelism` caps how many runs execute at once across **all** jobs.
  Default `Integer.MAX_VALUE` (unlimited); a value below 1 is treated as 1. Runs over the cap wait in a
  FIFO queue.

The executor does not depend on the jobs, and the job count does not size anything: one job or fifty,
annotation-only or `config`-driven, a slow job no longer delays the others. Blocking calls inside a job
(JDBC, HTTP clients) are ordinary blocking calls on a virtual thread.

Set `executionParallelism` only when the jobs share a scarce resource — for example to keep
concurrent jobs below the JDBC pool size.

---

## Graceful shutdown

1. Graph release runs in reverse dependency order, so every job is released before the executor it
   depends on. A job's `release()` cancels its future schedule with `cancel(false)` and returns at
   once — it does **not** wait for an in-flight run, and it does not interrupt it.
2. The executor's `release()` stops accepting work and cancels every periodic task, then waits up to
   `scheduling.jdk.shutdownWait` (default 30 s) for running jobs to finish.
3. If the budget runs out it calls `shutdownNow()`: queued runs are dropped and **running job threads
   are interrupted**, and it logs `SchedulingJdkExecutor failed completing graceful shutdown in PT30S`.
   `release()` then returns without waiting further.

So `shutdownWait` **does** bound shutdown, and an interrupt is the signal that the budget is gone. A
job should still be short or cooperatively bounded (batch cap, in-run deadline, timeouts on blocking
calls) so it finishes inside the budget, and it should handle `InterruptedException` /
`Thread.currentThread().isInterrupted()` by stopping cleanly. Because the job itself no longer blocks
release, components the job uses may be released while its last run is still draining — another reason
to keep runs short.

Patterns and the failure modes: [references/graceful-shutdown-reference.md](references/graceful-shutdown-reference.md).

---

## Error handling

A throwable escaping the job is caught by the job wrapper, recorded on the span, counted under the
`error.type` metric tag and — with `scheduling.telemetry.logging.enabled = true` — logged at WARN as
`Scheduled Job execution failed with error`. The schedule
survives — the next run happens as planned, for every annotation including `@ScheduleJdkWithCron`.

Kora does not retry the job for you. For retries put [`@Retryable`](../kora-aop-resilient/SKILL.md) on
an inner method (that one is proxy-based, so its `open`/non-`final` rules apply), or handle the failure
in the job body.

---

## Common pitfalls

| Symptom | Cause / fix |
|---|---|
| Job never fires | The class is not in the graph. Add `@Component` (or a `@Module` factory). `final`/non-`open` is **not** the cause |
| `cannot find symbol` on `ScheduleAtFixedRate` / `ScheduleWithFixedDelay` / `ScheduleOnce` / `ScheduleWithCron` | RC1-era names; in `2.0.0.RC2` they are `@ScheduleJdk*` — see [Coming from RC1](#coming-from-rc1--earlier-20-snapshots) |
| `Either period() or config() annotation parameter must be provided` | Annotation has neither a non-zero primary attribute nor `config` |
| Build fails with `Invalid CRON expression '…' in @ScheduleJdkWithCron on '…'` | The literal is not valid JDK cron — often a Quartz-only `L`/`W`/`#`/`C`, or a field count other than 5–7. Fix the expression, or move the job to Quartz |
| Startup fails with `Invalid CRON expression '…' for JDK job '…'` | Same check, for a cron that came from config |
| Job silently not scheduled, INFO `… is disabled by configuration and won't be scheduled` | `enabled = false` under the job's `config` path (often via an env substitution) |
| `Suspend methods are not supported by the scheduling generator` | Drop `suspend`; use `StructuredTaskScope` inside a plain function for parallelism |
| Timings from config ignored | The `config` path in the annotation and the path in the file disagree; or the key name is wrong for that annotation (`period` vs `delay`) |
| No job metrics | `scheduling.telemetry.metrics.enabled` defaults to **`false`** — and a `MeterRegistry` component must exist |
| Jobs wait for each other | `scheduling.jdk.executionParallelism` is set too low; the default is unlimited |
| `SchedulingJdkExecutor failed completing graceful shutdown` | A run outlived `scheduling.jdk.shutdownWait` and was interrupted — bound the run or raise the budget |
| Daily cron job ran twice / not at all | DST fall-back repeats the local time, spring-forward skips it; move the job out of the transition hour or use a UTC `@Tag(SchedulingModule.class) ZoneId` |
| Cron fires at the wrong hour | It runs in the JVM default zone unless a `@Tag(SchedulingModule.class) ZoneId` component exists — see [Time zone](#time-zone) |
| `scheduling.threads` / `scheduling.shutdownWait` / `scheduling.jdk.maxConcurrentExecutions` have no effect | The first two are 1.x keys, the third a post-RC1 snapshot key. Use `scheduling.jdk.shutdownWait`; the only concurrency knob is `scheduling.jdk.executionParallelism` |
| Every job logs `JDK Job 'java.lang.Void#noop' started in …` / `stopped` / `is disabled by configuration` under logger `java.lang.Void`; a bad config cron names `JDK job 'java.lang.Void#noop'` | With job logging and metrics off (the 2.0 defaults) and no tracing (no `Tracer` component, or `tracing.enabled = false`), `DefaultSchedulingTelemetryFactory` returns the shared `NoopSchedulingTelemetry.INSTANCE`, whose `jobClass()` is `Void` and `jobMethod()` is `noop`, and `KoraJdkJob` takes its logger and messages from it. Fixed in `2.0.0.RC2` (kora-projects/kora PR #961) — only `2.0.0.RC1` is affected; on RC1 set `scheduling.telemetry.logging.enabled = true` (or `<config-path>.telemetry.logging.enabled = true` per job) — every run then also logs `Scheduled Job execution completed` at INFO under the `<fqcn>#<method>` logger |
| Job on a `@Conditional` component runs although the condition failed, and every run fails with `IllegalStateException: Graph node value was not initialized because condition failed: <reason>` — invisible with job logging off | The generated `$X_SchedulingModule` factory is `@Root` and carries no condition, so the job is created and scheduled anyway and `ValueOf.get()` throws on each run. Fixed in `2.0.0.RC2` (kora-projects/kora PR #962) — only `2.0.0.RC1` is affected; on RC1 keep the scheduled method on an unconditional component; if it must reach the conditional one, inject `All<T>` (condition-failed members are skipped) and return when it is empty — not `@Nullable T`, which on RC1 hits PR #960 |

---

## Testing

The migrated examples drive the job component into the test graph explicitly and then poll:

```java
@KoraAppTest(value = Application.class, components = FixedRateJob.class)
class HeartbeatTests {

    @TestComponent
    private ScheduledJobs jobs;

    @Test
    void scheduled() {
        Awaitility.await().atMost(Duration.ofSeconds(3)).until(() -> jobs.getTicks() > 3);
    }
}
```

`components` takes the job wrapper type — `FixedRateJob`, `FixedDelayJob`, `RunOnceJob` or `CronJob`
from `io.koraframework.scheduling.jdk.job` (RC1 had them directly in `io.koraframework.scheduling.jdk`)
— matching the annotation under test. See
[kora-testing-junit-java](../kora-testing-junit-java/SKILL.md) /
[kora-testing-junit-kotlin](../kora-testing-junit-kotlin/SKILL.md).

---

## References, assets, scripts

| File | Purpose |
|---|---|
| [references/jdk-scheduling-reference.md](references/jdk-scheduling-reference.md) | Per-annotation reference, generated code, cron syntax, telemetry |
| [references/scheduling-config-reference.md](references/scheduling-config-reference.md) | Complete `scheduling.*` key set, HOCON + YAML, per-job overrides |
| [references/graceful-shutdown-reference.md](references/graceful-shutdown-reference.md) | The shutdown path, what `shutdownWait` bounds, cooperative-cancellation patterns |
| [assets/ScheduledJobs.java.template](assets/ScheduledJobs.java.template) | Java scheduled-jobs starter |
| [assets/ScheduledJobs.kt.template](assets/ScheduledJobs.kt.template) | Kotlin scheduled-jobs starter |
| [scripts/setup-jdk.sh](scripts/setup-jdk.sh) | Add `scheduling-jdk`, a job template and config to a project (`--dry-run` supported) |

---

## Which scheduler?

Kora ships three schedulers. Same table in all three scheduling sub-skills:

| Need | JDK (this skill) | Quartz | DB (db-scheduler) |
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
| Switch a job off | `enabled = false` under its `config` path | same; the job loses its triggers | same; its pending execution is removed |
| Custom trigger, misfire policy, `JobDataMap` | no | yes | no |
| Runs on | virtual threads, cap `executionParallelism` (unlimited) | Quartz `SimpleThreadPool` platform threads (10) | virtual threads, cap `executionParallelism` (10) |
| Shutdown | waits `shutdownWait`, then interrupts | waits `shutdownWait`, interrupts via `InterruptableJob`, waits `shutdownWait` again | waits `shutdownWait`, then interrupts |

---

## Related skills

- [kora-aop-scheduling-db](../kora-aop-scheduling-db/SKILL.md) — use it when a job must run **once per
  cluster** and survive restarts: db-scheduler on a table in your own database
- [kora-aop-scheduling-quartz](../kora-aop-scheduling-quartz/SKILL.md) — use it for
  **`@ScheduleQuartzWithTrigger` with a custom Quartz `Trigger`, misfire policies,
  `@DisallowConcurrentExecution` / `@PersistJobDataAfterExecution` (all in
  `io.koraframework.scheduling.quartz.annotation`), a Quartz JDBC JobStore, or the Quartz-only cron
  modifiers `L` `W` `#` `C`**. Plain in-process cron does not need it.
- [kora-di-runtime](../kora-di-runtime/SKILL.md) — `@Conditional`, `All<T>` and why a scheduled method on
  a conditional component misbehaves (see [Common pitfalls](#common-pitfalls))
- [kora-di-compile](../kora-di-compile/SKILL.md) — `@Component`, `@Module`, `@Root`, graph errors
- [kora-config-hocon](../kora-config-hocon/SKILL.md) / [kora-config-yaml](../kora-config-yaml/SKILL.md) — config sources for the `config` attribute
- [kora-aop-logging](../kora-aop-logging/SKILL.md) — `@Log` / `@Mdc` on job methods
- [kora-aop-resilient](../kora-aop-resilient/SKILL.md) — `@Retryable` / `@Timeout` around job work
- [kora-telemetry-metrics](../kora-telemetry-metrics/SKILL.md) — wiring the `MeterRegistry` the job metric needs
