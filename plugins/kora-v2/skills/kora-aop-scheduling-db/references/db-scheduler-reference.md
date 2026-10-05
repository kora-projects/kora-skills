# DB Scheduling Reference

**Artifact:** `io.koraframework:scheduling-db-scheduler` (`com.github.kagkarlsson:db-scheduler:16.12.0` as `api`)
**Module:** `io.koraframework.scheduling.db.scheduler.DbSchedulerModule`
**Annotations:** `io.koraframework.scheduling.db.scheduler.annotation.*`
**Runtime:** db-scheduler `Scheduler`, wrapped by `KoraDbScheduler` (`@Root`, `Lifecycle`, `Wrapped<Scheduler>`)

## Contents

- [What the module provides](#what-the-module-provides)
- [What the processor generates](#what-the-processor-generates)
- [Annotations](#annotations)
- [Cron syntax](#cron-syntax)
- [What happens on restart](#what-happens-on-restart)
- [Failures and dead executions](#failures-and-dead-executions)
- [Graceful shutdown](#graceful-shutdown)
- [Custom `DbSchedulerJob`](#custom-dbschedulerjob)
- [Telemetry](#telemetry)

---

## What the module provides

| Component | Factory | Notes |
|---|---|---|
| `DbSchedulerConfig` | `dbSchedulerConfig` | mapped from `scheduling.dbScheduler` |
| `@Tag(KoraDbScheduler.class) DataSource` | `dbSchedulerDataSource(DataSource)`, `@DefaultComponent` | returns the untagged `DataSource`; supply your own tagged one to use a different database |
| `KoraDbScheduler` | `koraDbScheduler(...)`, `@Root @DefaultComponent` | takes the tagged `DataSource`, the config, `All<ValueOf<DbSchedulerJob>>` and an optional `Configurer<SchedulerBuilder>` |
| `SchedulingTelemetryFactory`, `SchedulingTelemetryConfig` | inherited from `SchedulingModule` | shared with the JDK and Quartz schedulers |

`KoraDbScheduler` is `@Root` (kora-projects/kora PR #922), so extending `DbSchedulerModule` is enough
to start the scheduler. Earlier 2.0 snapshots needed a hand-written `@Root` component injecting the
wrapper; it is no longer needed.

Injecting `com.github.kagkarlsson.scheduler.Scheduler` (`KoraDbScheduler` is `Wrapped<Scheduler>`)
gives you the db-scheduler client API (`getScheduledExecutions`, `reschedule`, `cancel`) for
operational tooling.

`JdbcDatabaseModule` satisfies the `DataSource` dependency: its `JdbcDataSource` is a
`Wrapped<DataSource>`.

### `init()`

1. If `tableInitialize` is `true`, create `tableName` when it is missing (see
   [db-scheduler-config-reference.md](db-scheduler-config-reference.md#tableinitialize)).
2. Collect every `DbSchedulerJob` and take its `task()`. Two tasks with the same name fail here with
   `IllegalStateException: Database scheduled jobs '<a>' and '<b>' have the same name '<name>'; job
   names must be unique, set a unique name in @ScheduleDbWithCron(name = ...),
   @ScheduleDbWithFixedDelay(name = ...) or @ScheduleDbOnce(name = ...)`. Tasks that implement db-scheduler's
   `OnStartup` (all three annotation kinds) are registered through `startTasks(...)`, the rest as
   plain known tasks — each task exactly once.
3. Build the `Scheduler`: `threads(executionParallelism)`, a `LimitedVirtualThreadPerTaskExecutor`
   named `kora-db-scheduler` as the executor service, `pollingInterval`, `shutdownMaxWait =
   shutdownWait`, `tableName`, and the polling strategy with the prefetch ratios.
4. Apply `Configurer<SchedulerBuilder>` if one exists — last, so it can override anything above.
5. `scheduler.start()` and log `KoraDbScheduler started in …`.

---

## What the processor generates

For each class holding DB-scheduled methods, one `@Module` interface `$<ClassName>_SchedulingModule`
with a `@Root` factory `$<ClassName>_<method>_Job` per method. The factory takes
`SchedulingTelemetryFactory` and `ValueOf<YourClass>` (cron jobs also a nullable
`@Tag(SchedulingModule.class) ZoneId`) and returns a `DbSchedulerJob` — `CronJob`, `FixedDelayJob` or
`RunOnceJob` from `io.koraframework.scheduling.db.scheduler.job`, all extending `KoraDbJob`. The job
body is `target.get().yourMethod()`; no AOP proxy is involved. The job name is resolved at compile
time and passed as a string literal.

With `config = "<path>"` it also generates `$<ClassName>_<method>_Config extends SchedulingJobConfig`
(`@ConfigMapper`) with the timing keys plus the inherited `enabled()` (default `true`) and
`telemetry()`, and a factory binding it to `<path>`. Annotation values become `default` methods; an
unset one becomes abstract, i.e. a required key. There is no `name()` — the name is annotation-only.

The factory carries no `@Conditional`, even when the target class has one. If that condition fails,
the job is still registered and every run fails in `ValueOf.get()` with `IllegalStateException: Graph
node value was not initialized because condition failed: <reason>` (rethrown, so db-scheduler
reschedules it). Fixed in `2.0.0.RC2` (kora-projects/kora PR #962) — only `2.0.0.RC1` is affected; on
RC1 keep scheduled methods on unconditional components.

---

## Annotations

### `@ScheduleDbWithCron`

| Attribute | Type | Default |
|---|---|---|
| `value` | `String` | `""` |
| `name` | `String` | `""` |
| `config` | `String` | `""` |

`value` is required without `config`. With `config`, the path may be a plain string (the cron) or an
object with `cron`, `enabled` and `telemetry`; a non-blank `value` is the default `cron`, used when the
path is absent.

```java
@ScheduleDbWithCron(value = "0 0 2 * * *", name = "nightly-cleanup", config = "scheduling.jobs.cleanup")
void cleanup() { }
```

### `@ScheduleDbWithFixedDelay`

| Attribute | Type | Default |
|---|---|---|
| `initialDelay` | `long` | `0` |
| `delay` | `long` | `0` |
| `unit` | `ChronoUnit` | `MILLIS` |
| `name` | `String` | `""` |
| `config` | `String` | `""` |

The next execution is `delay` after the previous one **completed**. `initialDelay` is added only when
the job's row is first created — see [What happens on restart](#what-happens-on-restart).

```java
@ScheduleDbWithFixedDelay(initialDelay = 1, delay = 5, unit = ChronoUnit.MINUTES, name = "outbox-relay")
void relayOutbox() { }
```

### `@ScheduleDbOnce`

| Attribute | Type | Default |
|---|---|---|
| `delay` | `long` | `0` |
| `unit` | `ChronoUnit` | `MILLIS` |
| `name` | `String` | `""` |
| `config` | `String` | `""` |

Registered as a db-scheduler startup task with instance id = task name. On each startup of any
replica, if no execution of it is pending, one is created at `now + delay`; concurrent startups create
only one. After it runs — successfully or not — the row is removed. Consequences:

- one run per "startup wave", not one run ever: a restart after the run schedules it again;
- a failure is not retried.

For a one-time data fix that must never repeat, record completion in your own table and make the method
a no-op once done.

With `enabled = false` in its config the job is not scheduled on startup, and an execution scheduled
earlier is removed without calling the method when it fires.

### Task names

The task name is the annotation `name`, else `CanonicalClassName#method` (Java
`TypeElement.getQualifiedName()`, KSP `qualifiedName`: `com.example.jobs.ReportJobs#hourly`, nested
`com.example.Outer.Inner#m`). Config cannot override it. It is the job's key in the table, so moving the
class to another package changes it too. More than 350 characters fails the build:
`Database scheduled job name '<name>' is <n> characters long, maximum is 350. Set a shorter name() in
the annotation.` Duplicate names fail `KoraDbScheduler.init()` (see above).

A renamed task leaves the old row behind as an unresolved execution (db-scheduler logs
`Found execution with unknown task-name …`); db-scheduler deletes unresolved rows after 14 days by
default. Earlier 2.0 snapshots defaulted to `SimpleClassName#method`: to keep the state of an unnamed
job across that upgrade, set `name` to the old value.

---

## Cron syntax

db-scheduler `CronSchedule(pattern, zone)` — cron-utils with the Spring 5.3 definition:

```
┌───────────── second (0-59)
│ ┌───────────── minute (0-59)
│ │ ┌───────────── hour (0-23)
│ │ │ ┌───────────── day of the month (1-31, L, W or ?)
│ │ │ │ ┌───────────── month (1-12 or JAN-DEC)
│ │ │ │ │ ┌───────────── day of the week (0-7 or MON-SUN, 0 and 7 are Sunday, L, # or ?)
* * * * * *
```

Exactly six fields, seconds first, no year; or a macro `@yearly`, `@monthly`, `@weekly`, `@daily`,
`@hourly`. Special characters `* ? , - /`, and `L` (`L`, `L-3`, `5L`), `W` (`1W`, `LW`), `#`
(`MON#2`). Numeric day-of-week starts on **Monday** — `1` is MON, `5` is FRI, `0` and `7` are SUN —
the opposite of the JDK and Quartz schedulers, where `1` is Sunday. Prefer day names.

**Validation.** The processor checks a cron literal at compile time and fails with
`Invalid CRON expression '<expr>' in @ScheduleDbWithCron on '<fqcn>#<method>()': <reason>.` plus the
field diagram and two examples (`'0 0 15 * * *'`, `'0 0 9-17 * * MON-FRI'`). The check reports only
errors db-scheduler rejects too. A cron that comes from config is parsed when the job component is
built during graph init: `IllegalArgumentException: Invalid CRON expression '<expr>' for database
scheduled job '<fqcn>#<method>': …` with the same hint.

**Time zone.** The `ZoneId` component tagged `@Tag(SchedulingModule.class)`, else the JVM default —
shared with JDK and Quartz cron jobs.

**Disabling.** `"-"` is db-scheduler's *disabled* schedule: on startup the pending execution is removed
and nothing new is scheduled. `enabled = false` in the job's config does the same (Kora passes `"-"`
for you):

```hocon
scheduling.jobs.cleanup = "-"                                     # string form
scheduling.jobs.cleanup { cron = "0 0 2 * * *", enabled = false }  # object form
```

Do not reuse a JDK (5/7-field) or Quartz (year field, Sunday = 1) expression blindly — check it against
the Spring format.

---

## What happens on restart

For cron and fixed-delay jobs db-scheduler runs its recurring-startup check on every start:

| Row state | Effect |
|---|---|
| no row | create one at `now + initialDelay` (fixed delay) or the next cron time |
| row exists, cron changed | if the stored time differs from the new next cron time by more than 1 s, **reschedule** to the new time |
| row exists, fixed delay shortened | if the stored time is later than `now + delay`, move it **earlier** |
| row exists, fixed delay lengthened | kept; the new delay applies after the next run |
| stored time within 10 s of now | left alone |
| schedule disabled (`"-"` or `enabled = false`) | row removed |

`initialDelay` therefore affects only the first deployment of a job name.

---

## Failures and dead executions

`KoraDbJob.runJob()` installs a fresh MDC and root OpenTelemetry context, observes the run, and
**rethrows** any exception after recording it. db-scheduler then applies the task's failure handler
and logs the failure (WARN by default):

| Job | On failure |
|---|---|
| `@ScheduleDbWithCron`, `@ScheduleDbWithFixedDelay` | `OnFailureReschedule` — next regular execution time, `consecutive_failures` incremented |
| `@ScheduleDbOnce` | execution removed — no retry |

Each replica heartbeats its picked executions (every 5 min by default). An execution whose owner missed
6 heartbeats is considered dead; recurring tasks are revived and run again elsewhere. Idempotent job
bodies make that safe.

---

## Graceful shutdown

`KoraDbScheduler.release()` → `Scheduler.stop()`:

1. stop the polling thread;
2. `shutdown()` the job executor and wait `shutdownWait` for running executions;
3. if they are still running: `shutdownNow()` — the job's virtual thread is **interrupted** — and wait
   up to another `shutdownWait`;
4. stop heartbeating.

db-scheduler logs `Letting running executions finish. Will wait up to 2x…`. The wrapper is released
before the jobs and the `DataSource` it depends on, so a draining run keeps its database pool. An
interrupted execution that did not complete is picked up by the dead-execution check on another
replica later.

---

## Custom `DbSchedulerJob`

For task data, custom failure handling or db-scheduler features the annotations do not expose,
implement `io.koraframework.scheduling.db.scheduler.job.DbSchedulerJob` (single method
`Task<?> task()`) as a `@Root` component — extending `KoraDbJob` gives you the telemetry and context
handling of the generated jobs. `KoraDbScheduler` registers it with the annotated jobs; if the task
implements `OnStartup` it goes through `startTasks`. Keep the task name stable, and do not register the
same task again from a `Configurer<SchedulerBuilder>`.

---

## Telemetry

Identical model to the JDK scheduler (`scheduling-common`): `scheduling.telemetry` toggles, the
`scheduling.job.duration` timer, span `scheduling <fqcn>#<method>` (kind `INTERNAL`, root context), log
lines `Scheduled Job execution started/completed/failed with error`, per-job overrides under
`<config-path>.telemetry`. The `scheduling.system` tag and span attribute is `dbscheduler`, and log
lines carry `schedulerType`. Jobs declared without `config` get no `system.config` tag (Java and
Kotlin); with `config` it carries the path. Tags and attributes identify the class and method, not
the task `name`.

A custom `SchedulingTelemetryFactory` implements
`get(String schedulerType, @Nullable String jobConfigPath, @Nullable JobTelemetryConfig, Class<?> jobClass, String jobMethod)`
— `schedulerType` was added in front of the earlier snapshot signature.

**Job identity with telemetry off.** When job logging and metrics are off (the 2.0 defaults) and
tracing does not apply (no `Tracer` component, or `tracing.enabled = false`),
`DefaultSchedulingTelemetryFactory` returns the shared `NoopSchedulingTelemetry.INSTANCE`, whose
`jobClass()` is `Void` and `jobMethod()` is `noop`. `KoraDbJob.toString()` reads it, so the
duplicate-name and invalid-config-cron errors name the job `'java.lang.Void#noop'`. Fixed in
`2.0.0.RC2` (kora-projects/kora PR #961) — only `2.0.0.RC1` is affected; on RC1 enable
`scheduling.telemetry.logging.enabled` (or per job `<config-path>.telemetry.logging.enabled`), or find
the job by the task name in the message.

Full key list and metric/span details:
[kora-aop-scheduling-jdk telemetry](../../kora-aop-scheduling-jdk/references/jdk-scheduling-reference.md#telemetry).

---

## See Also

- [db-scheduler-config-reference.md](db-scheduler-config-reference.md) — every `scheduling.dbScheduler` key
- [kora-aop-scheduling-jdk](../../kora-aop-scheduling-jdk/SKILL.md) — in-process scheduler
- [kora-aop-scheduling-quartz](../../kora-aop-scheduling-quartz/SKILL.md) — Quartz scheduler
- [kora-database-migration](../../kora-database-migration/SKILL.md) — Flyway / Liquibase for the table
