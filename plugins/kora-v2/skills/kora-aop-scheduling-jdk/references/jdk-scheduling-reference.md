# JDK Scheduling Reference

**Artifact:** `io.koraframework:scheduling-jdk`
**Module:** `io.koraframework.scheduling.jdk.SchedulingJdkModule`
**Annotations:** `io.koraframework.scheduling.jdk.annotation.*`
**Runtime:** `VirtualThreadSchedulingJdkExecutor` — one platform timer thread, a fresh virtual thread per run; in-process, non-persistent

## Contents

- [Annotations](#annotations) — `@ScheduleJdkAtFixedRate`, `@ScheduleJdkWithFixedDelay`, `@ScheduleJdkOnce`, `@ScheduleJdkWithCron`
- [What the processor generates](#what-the-processor-generates)
- [Method requirements](#method-requirements)
- [Cron syntax](#cron-syntax)
- [JDK vs Quartz vs DB](#jdk-vs-quartz-vs-db)
- [Error handling](#error-handling)
- [Telemetry](#telemetry)

---

## Annotations

All four target `METHOD`, have `RetentionPolicy.CLASS`, and expose `String config() default ""`. Before
Kora PR #952 (that is, in `2.0.0.RC1`) they were `@ScheduleAtFixedRate`, `@ScheduleWithFixedDelay`,
`@ScheduleOnce` and `@ScheduleWithCron`; those names no longer exist.

### `@ScheduleJdkAtFixedRate`

| Attribute | Type | Default |
|---|---|---|
| `initialDelay` | `long` | `0` |
| `period` | `long` | `0` |
| `unit` | `ChronoUnit` | `MILLIS` |
| `config` | `String` | `""` |

The period is measured **start → start** against the original timetable. The executor schedules the
next run only after the current one returns, so if a run overruns the period the next run starts as
soon as it finishes (catching up) — never concurrently. Each job also serialises its runs behind a
per-job lock. A `period` of 0 or less is rejected by the executor with `IllegalArgumentException`.

Use for a cadence you want to keep: heartbeat, metric scrape, health poll, cache refresh.

```java
@Component
public final class HeartbeatJob {

    @ScheduleJdkAtFixedRate(initialDelay = 30, period = 60, unit = ChronoUnit.SECONDS)
    void heartbeat() { }
}
```

### `@ScheduleJdkWithFixedDelay`

| Attribute | Type | Default |
|---|---|---|
| `initialDelay` | `long` | `0` |
| `delay` | `long` | `0` |
| `unit` | `ChronoUnit` | `MILLIS` |
| `config` | `String` | `""` |

The delay is measured **end → start** — a full `delay` of idle time after the previous run returned.
The cadence therefore drifts with execution time, which is what you want when the work is long or its
duration varies.

```java
@ScheduleJdkWithFixedDelay(initialDelay = 30, delay = 120, unit = ChronoUnit.SECONDS)
void syncData() { }
```

### `@ScheduleJdkOnce`

| Attribute | Type | Default |
|---|---|---|
| `delay` | `long` | `0` |
| `unit` | `ChronoUnit` | `MILLIS` |
| `config` | `String` | `""` |

One execution, `delay` after the graph starts the job. Use for cache warm-up, late binding, a one-shot
startup task that must not block graph initialisation.

```java
@ScheduleJdkOnce(delay = 5, unit = ChronoUnit.MINUTES)
void warmup() { }
```

### `@ScheduleJdkWithCron`

| Attribute | Type | Default |
|---|---|---|
| `value` | `String` | `""` |
| `config` | `String` | `""` |

An in-process cron evaluator (`io.koraframework.scheduling.jdk.util.CronExpression`; RC1 had it in
`io.koraframework.scheduling.jdk`) with no Quartz dependency. After each run the job computes the next
fire time from the current time in the **scheduling time zone**: the `java.time.ZoneId` component tagged
`@Tag(io.koraframework.scheduling.common.SchedulingModule.class)` if the graph has one, otherwise the JVM
default zone (`Clock.systemDefaultZone()`). The generated factory receives it as a
`@Tag(SchedulingModule.class) @Nullable ZoneId` parameter, so the component is optional. The delay to the
next fire time is kept in nanoseconds, so sub-millisecond remainders are not lost.

```java
@ScheduleJdkWithCron("0 0 3 * * ?")
void nightlyCompaction() { }
```

Validation happens twice:

| Cron source | Checked | Failure |
|---|---|---|
| annotation `value` | at **compile time** by the processor (`CronValidator`, JDK dialect) | build error `Invalid CRON expression '<expr>' in @ScheduleJdkWithCron on '<fqcn>#<method>()': <reason>.`, then the field diagram, two examples and `See the Javadoc of @ScheduleJdkWithCron for details.` |
| config (`cron` key or a bare string) | at graph init, when `CronJob` is constructed | startup error `IllegalArgumentException: Invalid CRON expression '<expr>' for JDK job '<fqcn>#<method>': <parser message>`, then the same field diagram |

The compile-time check is deliberately incomplete: it reports only errors the JDK parser rejects as
well (field count, ranges, reversed ranges, steps of `0`, `L`/`W`/`#`/`C` — `… modifier L in L is not
supported by the JDK scheduler`) and leaves anything it does not model to the parser at startup.
If the expression can never fire again before the year 2100, the job logs
`JDK Job '<fqcn>#<method>' won't be scheduled because it has no next fire time` at WARN instead of
throwing.

---

## Required parameter rule

Every annotation needs either its primary attribute or a `config` path. A `period`/`delay` of `0` and a
blank cron `value` count as **unset**, and the build fails:

```
Either period() or config() annotation parameter must be provided
```

The Kotlin processor prints the long form:

```
Invalid `@ScheduleJdkAtFixedRate` configuration on `com.example.Jobs.heartbeat`.

The annotation must define either `period` directly or `config` with a config path.
A zero or blank `period` is treated as missing.

Fix: set `period` on the annotation, or set `config` and provide scheduling settings in application config.
```

---

## What the processor generates

For every class holding scheduled methods the processor writes one `@Module` interface next to it:

```
$<ClassName>_SchedulingModule
```

with one `@Root` factory method per scheduled method:

```
$<ClassName>_<methodName>_Job
```

returning `FixedRateJob`, `FixedDelayJob`, `RunOnceJob` or `CronJob` from
`io.koraframework.scheduling.jdk.job` (all extend `KoraJdkJob`, RC1's `AbstractJob`). The factory takes
`SchedulingTelemetryFactory`, `SchedulingJdkExecutor` and `ValueOf<YourClass>` — plus the optional
`@Tag(SchedulingModule.class) ZoneId` for a cron job and the generated config for a `config` job — and
the job body is a lambda `() -> target.get().yourMethod()`.

Two things follow from that shape:

1. **No AOP proxy is created.** Your class is called directly through `ValueOf`, so it does not have to
   be non-`final` (Java) or `open` (Kotlin) for scheduling to work.
2. The job component is annotated `@Root`, so it is never pruned out of the graph even though nothing
   depends on it.
3. The factory carries **no** `@Conditional`. On a `@Conditional` component whose condition fails the
   job is still created and scheduled, and every run fails in `ValueOf.get()` with
   `IllegalStateException: Graph node value was not initialized because condition failed: <reason>` —
   recorded as a job error, invisible with job logging off. Fixed in `2.0.0.RC2`
   (kora-projects/kora PR #962), which copies the class's `@Conditional` onto the job factory — only
   `2.0.0.RC1` is affected; on RC1 keep the
   scheduled method on an unconditional component and reach the conditional one through `All<T>`
   (condition-failed members are skipped); on RC1 a `@Nullable T` dependency hits the same exception (PR #960).

When the annotation carries `config = "<path>"` the processor additionally writes a
`@ConfigMapper` interface

```
$<ClassName>_<methodName>_Config extends SchedulingJobConfig
```

and a factory method binding it to `<path>`. Annotation attributes become `default` methods on that
interface (so config overrides them); an attribute left unset becomes an **abstract** method, which
makes the corresponding config key mandatory. `SchedulingJobConfig` adds `enabled()` (default `true`)
and `telemetry()`; the job is constructed with `config.enabled()`, and a disabled job's `init()` logs
`JDK Job '<fqcn>#<method>' is disabled by configuration and won't be scheduled` at INFO and schedules
nothing. Jobs without `config` are always enabled.

For `@ScheduleJdkWithCron` the binding method accepts either form at the path: a string becomes
`{ cron = "<string>" }`, an object is mapped as is, anything else fails with `ConfigValueException`.
When the annotation also has a `value` and the path is absent, the annotation expression is used.

`@KoraAppTest` needs the job type in `components` to pull the job into the test graph:

```java
import io.koraframework.scheduling.jdk.job.FixedRateJob;

@KoraAppTest(value = Application.class, components = FixedRateJob.class)
```

---

## Method requirements

| Rule | Enforced how |
|---|---|
| Member method of a class (not top-level, not local) | KSP: `Invalid scheduled function: … can be applied only to member functions` |
| No arguments | Generated call site passes none; a parameter breaks compilation |
| Not `suspend` | KSP: `Suspend methods are not supported by the scheduling generator` |
| Not reactive (`Mono`/`Flux`/`CompletionStage`) | Those types are not Kora 2.0 contracts at all |
| Visible from its own package | `private` breaks compilation of the generated module |
| Bearing class present in the graph | Missing `@Component` → the job simply never exists |

`final`/non-`open` is **not** on this list. The migrated examples use `@Component public final class`
(Java) and `@Component class` (Kotlin).

For real parallelism inside a job, the KSP error message points at `StructuredTaskScope` (a JDK preview
API — `--enable-preview` on javac, the Kotlin compiler, tests and the launcher):

```kotlin
fun refreshCaches() =
    StructuredTaskScope.open(
        StructuredTaskScope.Joiner.awaitAllSuccessfulOrThrow<Any>(),
    ).use { scope ->
        scope.fork(Callable { userCache.refresh() })
        scope.fork(Callable { productCache.refresh() })
        scope.join()
    }
```

---

## Cron syntax

Five, six or seven space-separated fields:

```
5 fields: minute hour day-of-month month day-of-week
6 fields: second minute hour day-of-month month day-of-week
7 fields: second minute hour day-of-month month day-of-week year

┌───────────── second (0-59)
│ ┌───────────── minute (0-59)
│ │ ┌───────────── hour (0-23)
│ │ │ ┌───────────── day of the month (1-31)
│ │ │ │ ┌───────────── month (1-12 or JAN-DEC)
│ │ │ │ │ ┌───────────── day of the week (1-7 or SUN-SAT)
│ │ │ │ │ │ ┌───────────── year (empty, 1970-2099, ?)
* * * * * * *
```

Five-field expressions are evaluated with `0` seconds. A missing year field means 1970–2099.
Day-of-week also accepts `0` for Sunday (`0` and `1` are both Sunday).

| Character | Meaning |
|---|---|
| `*` | every value in the field |
| `?` | no specific value — day-of-month, day-of-week and year only |
| `,` | explicit list, e.g. `6,18` |
| `-` | inclusive range, e.g. `MON-FRI`, `9-17` |
| `/` | step, e.g. `*/10` or `5/10` |

Month (`JAN`–`DEC`) and day-of-week (`SUN`–`SAT`) aliases work everywhere a number does: single values,
lists (`JUL,DEC`), ranges (`JUL-OCT`, `WED-FRI`) and steps (`JUL/2`).

**Not supported:** the Quartz modifiers `L`, `W`, `#`, `C` — a literal using them fails the build. Those
still require [kora-aop-scheduling-quartz](../../kora-aop-scheduling-quartz/SKILL.md).

| Expression | Fires |
|---|---|
| `0 * * * * *` | top of every minute |
| `*/10 * * * * *` | every ten seconds |
| `0 0 * * * ?` | top of every hour |
| `0 0 6,19 * * ?` | 06:00 and 19:00 daily |
| `0 0/30 8-10 * * ?` | every 30 min from 08:00 through 10:30 |
| `0 0 9-17 ? * MON-FRI` | hourly 09:00–17:00 on weekdays |
| `0 0 0 25 DEC ?` | Christmas Day, midnight |
| `0 0 0 1 JAN ? 2027` | 1 Jan 2027, midnight |

### Daylight-saving transitions

Fire times are searched per constant-offset interval of the scheduling zone (the tagged `ZoneId`, else
the JVM default), so transitions behave predictably:

| Transition | Effect on `0 30 2 * * ?` (`Europe/Berlin`) |
|---|---|
| Spring forward — 02:00–02:59 does not exist | that day's 02:30 is **skipped**; next fire is 02:30 the following day |
| Fall back — 02:00–02:59 happens twice | fires at 02:30+02:00 **and** again at 02:30+01:00 |
| Every-second / every-minute expressions across the jump | no fire time exactly at the transition is lost |

Offsets that are not whole hours (e.g. `Australia/Lord_Howe`, 30 minutes) follow the same rule. If a
job must run exactly once per day, schedule it outside 01:00–03:00 local time or declare a UTC
`@Tag(SchedulingModule.class) ZoneId` component.

Cron can also come from config:

```java
@ScheduleJdkWithCron(config = "scheduling.jobs.compaction")
void nightlyCompaction() { }
```

```hocon
# either form works
scheduling.jobs.compaction = "0 0 3 * * ?"

scheduling.jobs.compaction {
  cron = "0 0 3 * * ?"
  enabled = true                 # default; only the object form can switch the job off
  telemetry.logging.enabled = true
}
```

With no `value` on the annotation, the `cron` key is mandatory.

---

## JDK vs Quartz vs DB

| Need | Module |
|---|---|
| fixed rate / fixed delay / one-shot, in-process | **JDK** |
| plain cron, in-process, every replica runs it | **JDK** — `@ScheduleJdkWithCron` |
| exactly one execution per firing across replicas, surviving restarts | **DB** — [kora-aop-scheduling-db](../../kora-aop-scheduling-db/SKILL.md) |
| cron with `L` / `W` / `#` / `C` | Quartz |
| misfire policy, custom `Trigger` via `@ScheduleQuartzWithTrigger` | Quartz |
| `@DisallowConcurrentExecution` / `@PersistJobDataAfterExecution` | Quartz |

The JDK scheduler holds no state anywhere: every replica of your service runs every job. The full
three-way table is in the [skill](../SKILL.md#which-scheduler).

---

## Error handling

A throwable escaping the method is caught by the job wrapper, which records it on the span
(`StatusCode.ERROR` + `recordException`), tags the duration metric with `error.type`, and logs at WARN:

```
Scheduled Job execution failed with error   schedulerType=jdk jobClass=… jobMethod=… duration=… exceptionType=… exceptionMessage=…
```

The schedule is **not** cancelled — the next run happens as planned, for all four annotations. (This is
the wrapper's doing; a raw `ScheduledExecutorService` would have cancelled a periodic task.)

Kora does not retry. Options:

```java
@ScheduleJdkWithFixedDelay(config = "scheduling.jobs.import")
void importData() {
    try {
        doWork();
    } catch (Exception e) {
        log.error("import failed", e);   // swallow: keep your own log shape
    }
}
```

or delegate the work to a method carrying [`@Retryable`](../../kora-aop-resilient/SKILL.md) — that
aspect *is* proxy-based, so its own `open`/non-`final` rules apply to the class holding it.

---

## Telemetry

Toggles live under `scheduling.telemetry` and can be overridden per job under the job's own `config`
path. Full key list in [scheduling-config-reference.md](scheduling-config-reference.md).

If tracing, metrics and logging are all disabled for a job, Kora installs a no-op telemetry and the job
costs nothing. Tracing counts as disabled when no `Tracer` component exists, so with the 2.0 defaults
(logging and metrics off) a service without a tracer always gets the no-op.

That no-op is a single shared `NoopSchedulingTelemetry.INSTANCE` whose `jobClass()` is `Void` and
`jobMethod()` is `noop`, and `KoraJdkJob` takes its logger and its lifecycle messages from the
telemetry. Every job therefore logs `JDK Job 'java.lang.Void#noop' started in …`, `… stopped in …` and
`… is disabled by configuration …` under the logger `java.lang.Void`, and an invalid config cron is
reported for `JDK job 'java.lang.Void#noop'`. Fixed in `2.0.0.RC2` (kora-projects/kora
PR #961), which makes the no-op carry the job's class and method — only `2.0.0.RC1` is affected; on
RC1 enable
`scheduling.telemetry.logging.enabled` (or `<config-path>.telemetry.logging.enabled` for one job); the
side effect is an INFO `Scheduled Job execution completed` line per run.

`SchedulingTelemetryFactory.get` takes the scheduler type first —
`get(String schedulerType, @Nullable String jobConfigPath, @Nullable JobTelemetryConfig jobTelemetryConfig, Class<?> jobClass, String jobMethod)`
— where RC1 had no `schedulerType`. A custom factory must implement the new signature; the generated
JDK jobs pass `"jdk"`.

### Metrics (Micrometer)

- **Meter:** `scheduling.job.duration` — a **`Timer`**. With the default Prometheus registry naming that
  is exposed as `scheduling_job_duration_seconds_*`; other registries name it their own way.
- **Enabled:** `scheduling.telemetry.metrics.enabled`, default **`false`**. A `MeterRegistry` component
  must also exist.
- **Tags:** `scheduling.system` (`jdk`; `quartz` / `dbscheduler` for the other schedulers),
  `code.function.name`, `system.name.simple` (`Class#method`), `system.name.canonical` (`fqcn#method`),
  `error.type` (empty string on success), anything in `metrics.tags`, and `system.config` only for jobs
  declared with `config` — see [below](#the-systemconfig-tag).
- **SLO:** `metrics.slo`, a list of durations; the default is the framework-wide 14-bucket ladder
  (1 ms → 90 s).

### Tracing (OpenTelemetry)

- **Enabled:** `scheduling.telemetry.tracing.enabled`, default **`true`** — but it is a no-op unless a
  `Tracer` component is in the graph.
- **Span:** name `scheduling <fqcn>#<method>`, kind `INTERNAL`, started from a **root** context (a
  scheduled run never continues an inbound trace).
- **Attributes:** `scheduling.system` (`jdk`), `code.function.name`, `system.name.simple`,
  `system.name.canonical`, anything in `tracing.attributes`, and `system.config` only for jobs declared
  with `config` — see [below](#the-systemconfig-tag).

### Logging

- **Enabled:** `scheduling.telemetry.logging.enabled`, default **`false`**.
- Start: DEBUG `Scheduled Job execution started`. End: INFO `Scheduled Job execution completed`, or
  WARN `Scheduled Job execution failed with error`.
- Structured key-values: `schedulerType` (`jdk`), `jobClass`, `jobMethod`, `duration` (ms), optional
  `jobConfigPath`, and `exceptionType` / `exceptionMessage` on failure.
- **Logger name is `<fqcn>#<method>`**, not the class name. Logback splits logger names on `.`, so
  `com.example` covers it but `com.example.Jobs` does **not**. Set the level on a package prefix.

### The `system.config` tag

The value is the job's config path: a job declared with `config = "<path>"` carries
`system.config = <path>`, a job without `config` carries no `system.config` at all — the same in Java
and Kotlin, for all four annotations. (Before Kora PR #952 the Java processor passed `<fqcn>#<method>`
as a fake config path for config-less timer jobs, so older dashboards may still group by that.) Group by
`system.name.canonical` to address every job, and give jobs a `config` path when you want
`system.config` to mean something.

---

## See Also

- [scheduling-config-reference.md](scheduling-config-reference.md) — complete configuration reference
- [graceful-shutdown-reference.md](graceful-shutdown-reference.md) — the shutdown path and what `shutdownWait` bounds
- [kora-aop-scheduling-quartz](../../kora-aop-scheduling-quartz/SKILL.md) — custom triggers, misfire policies, Quartz cron
- [kora-aop-scheduling-db](../../kora-aop-scheduling-db/SKILL.md) — one execution per cluster, persisted in your database
- [kora-telemetry-metrics](../../kora-telemetry-metrics/SKILL.md) — wiring the `MeterRegistry`
