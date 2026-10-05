---
name: kora-aop-scheduling-db
description: "Database-backed, cluster-wide scheduled jobs in Kora 2.x on db-scheduler — @ScheduleDbWithCron, @ScheduleDbWithFixedDelay, @ScheduleDbOnce from io.koraframework.scheduling.db.scheduler.annotation via DbSchedulerModule (artifact io.koraframework:scheduling-db-scheduler), run by the @Root KoraDbScheduler. Each firing runs on one replica and survives restarts in one table (default kora_scheduling_db_scheduler_jobs). Covers stable job names (CanonicalClassName#method, annotation-only, 350 chars), scheduling.dbScheduler keys (executionParallelism, polling FETCH/LOCK_AND_FETCH, prefetchMode, tableName, tableInitialize, shutdownWait), the bundled schema scripts and Liquibase changelog under db/kora/scheduling-db-scheduler, compile-time cron validation, the per-job enabled switch, the @Tag(SchedulingModule.class) ZoneId cron time zone and the renames since earlier 2.0 snapshots. Use for clustered jobs that must not run on every instance; for in-process timers use kora-aop-scheduling-jdk, for Quartz triggers use kora-aop-scheduling-quartz."
license: Apache-2.0
metadata:
  kora-version: "2.x"
---

# Kora AOP Scheduling (DB)

> **Kora sub-skill — obey the [kora-v2 meta rules](../../SKILL.md) on every task:** **R0** ground the workspace on Kora 2.0 refs before starting (framework source at tag `2.0.0.RC2` + `kora-examples` at `migration/2.0` + Kora 2.0 docs at koraframework.io/v2, which trail the source; 1.x `kora-docs` pages are never an authority) · **R1** read this sub-skill before writing code · **R2** Kora 2.0 APIs only — no Spring/Micronaut/Quarkus, no Kora 1.x APIs, no invented annotations or config keys · **R3** journal any incorrect Kora usage. Add comments/Javadoc only if asked.

| | |
|---|---|
| **Artifact** | `io.koraframework:scheduling-db-scheduler` (version from `io.koraframework:kora-bom`) — brings `com.github.kagkarlsson:db-scheduler:16.12.0` as `api` |
| **Module** | `io.koraframework.scheduling.db.scheduler.DbSchedulerModule` (extends `io.koraframework.scheduling.common.SchedulingModule`) |
| **Annotations** | `io.koraframework.scheduling.db.scheduler.annotation.{ScheduleDbWithCron, ScheduleDbWithFixedDelay, ScheduleDbOnce}` |
| **Runtime** | `io.koraframework.scheduling.db.scheduler.KoraDbScheduler` — `@Root`, `Lifecycle`, `Wrapped<Scheduler>` |
| **Processor** | Java `annotationProcessor "io.koraframework:annotation-processors"` · Kotlin `ksp("io.koraframework:symbol-processors")` |
| **Needs** | a `javax.sql.DataSource` in the graph — normally `JdbcDatabaseModule` ([kora-database-jdbc](../kora-database-jdbc/SKILL.md)) |
| **Config roots** | `scheduling.dbScheduler` · `scheduling.telemetry` · one arbitrary path per job via `config = "…"` |

Jobs are rows in a database table. Every replica polls the table; a due execution is picked by exactly
one replica, executed, and its next execution time is written back. A restart, a deploy or a crashed
node does not lose the schedule.

---

## Coming from earlier 2.0 snapshots

This module is **not in `2.0.0.RC1`** — it first appeared on the 2.0 snapshot line. Code written
against an earlier snapshot needs these changes (kora-projects/kora PRs #922 and #952):

| Earlier 2.0 snapshot | Now | Consequence if you skip it |
|---|---|---|
| `@ScheduleWithCron` / `@ScheduleWithFixedDelay` / `@ScheduleOnce` from `…db.scheduler.annotation` | `@ScheduleDbWithCron` / `@ScheduleDbWithFixedDelay` / `@ScheduleDbOnce`, same package | Compile error — loud |
| `DbSchedulerWrapper`, `@Tag(DbSchedulerWrapper.class) DataSource` | `KoraDbScheduler`, `@Tag(KoraDbScheduler.class) DataSource` | Compile error — the old class is gone |
| `job.AbstractJob` | `job.KoraDbJob` | Compile error in custom jobs |
| A `@Root` "starter" component injecting the wrapper | Not needed — `KoraDbScheduler` is `@Root` itself | A leftover starter is harmless; delete it |
| Default job name `SimpleClassName#method` | **`CanonicalClassName#method`** (`com.example.jobs.ReportJobs#hourly`) | Every job without an explicit `name` gets a **new row**: its state starts over and the old row is orphaned. Pin `name = "ReportJobs#hourly"` (the old value) to keep it |
| Config key `<path>.name` overrides the name | **Removed** — the name comes from the annotation only | An unknown HOCON key is ignored silently: the job runs under its default name |
| Any length | Name ≤ 350 characters, checked at compile time | Compile error naming the job |
| `scheduling.dbScheduler.initializeTable` | **`scheduling.dbScheduler.tableInitialize`** | Ignored silently — the table is not created |
| Table `kora_scheduling_db_jobs` | **`kora_scheduling_db_scheduler_jobs`** | Scheduler looks for a table that does not exist. Set `tableName = "kora_scheduling_db_jobs"` or migrate |
| `db/scheduling-db/flyway/<db>/V1__create_scheduled_tasks.sql`, `db/scheduling-db/liquibase/changelog.yaml` (table `scheduled_tasks`) | `db/kora/scheduling-db-scheduler/schema/<db>.sql` (plain scripts) and `db/kora/scheduling-db-scheduler/liquibase/changelog.yaml` | A Flyway location pointing at the old path finds nothing; a Liquibase `include` of it no longer resolves |
| Duplicate names fail inside db-scheduler (`Duplicate key …`) | Kora fails first, naming both jobs | — |
| Invalid cron fails at graph init | A cron **literal** fails at compile time | — |
| — | Per-job `enabled` key, optional `@Tag(SchedulingModule.class) ZoneId` for cron | — |
| `SchedulingTelemetryFactory.get(configPath, …)` | `get(schedulerType, configPath, …)`, `schedulerType = "dbscheduler"` | Compile error in a custom telemetry factory |

---

## Quick Start

### 1. Dependency

```groovy
// build.gradle (Java)
dependencies {
    koraBom platform("io.koraframework:kora-bom:$koraVersion")   // koraVersion=2.0.0.RC2
    annotationProcessor "io.koraframework:annotation-processors"

    implementation "io.koraframework:scheduling-db-scheduler"
    implementation "io.koraframework:database-jdbc"
    implementation "org.postgresql:postgresql"                  // your JDBC driver
    implementation "io.koraframework:config-hocon"
    implementation "io.koraframework:logging-logback"
}
```

```kotlin
// build.gradle.kts (Kotlin)
dependencies {
    implementation(platform("io.koraframework:kora-bom:${property("koraVersion")}"))
    ksp("io.koraframework:symbol-processors:${property("koraVersion")}")

    implementation("io.koraframework:scheduling-db-scheduler")
    implementation("io.koraframework:database-jdbc")
    implementation("org.postgresql:postgresql")
    implementation("io.koraframework:config-hocon")
    implementation("io.koraframework:logging-logback")
}
```

### 2. Plug the modules into `@KoraApp`

```java
@KoraApp
public interface Application extends
    HoconConfigModule,
    LogbackModule,
    JdbcDatabaseModule,
    DbSchedulerModule {

    static void main(String[] args) {
        KoraApplication.run(ApplicationGraph::graph);
    }
}
```

`DbSchedulerModule` declares `KoraDbScheduler` as `@Root @DefaultComponent`, so the scheduler starts
with the graph — no extra component is needed. It logs `KoraDbScheduler started in …` at INFO.

### 3. Create the table

db-scheduler needs its table before the scheduler starts. Copy the bundled script for your database
into your own migration (default table name **`kora_scheduling_db_scheduler_jobs`**) or include the
bundled Liquibase changelog — see [Table](#table). For a local run,
`scheduling.dbScheduler.tableInitialize = true` creates it for you.

### 4. Declare jobs

```java
@Component
public final class ReportJobs {

    @ScheduleDbWithCron(value = "0 0 * * * *", name = "hourly-report")
    void hourlyReport() {
        // runs on one replica per hour
    }
}
```

The processor emits a `$ReportJobs_SchedulingModule` with one `@Root` factory per method returning a
`DbSchedulerJob`. `KoraDbScheduler` collects them all at init and registers their tasks with
db-scheduler.

---

## Annotations

All three live in `io.koraframework.scheduling.db.scheduler.annotation`, target `METHOD`, and carry
`String name() default ""` and `String config() default ""`.

| Annotation | Attributes | db-scheduler task | Semantics |
|---|---|---|---|
| `@ScheduleDbWithCron` | `value` (cron, `""`), `name`, `config` | `RecurringTask`, `CronSchedule` | next run = next cron time after completion |
| `@ScheduleDbWithFixedDelay` | `initialDelay` (long, `0`), `delay` (long, `0`), `unit` (`ChronoUnit`, `MILLIS`), `name`, `config` | `RecurringTask`, `FixedDelay` | next run = completion + `delay`; `initialDelay` only for the very first execution |
| `@ScheduleDbOnce` | `delay` (long, `0`), `unit` (`ChronoUnit`, `MILLIS`), `name`, `config` | custom task, scheduled on startup | one execution `delay` after a startup; removed after it runs, **no retry on failure** |

There is **no fixed-rate** annotation in this module.

Either the primary attribute or `config` must be set; a `delay` of `0` or a blank `value` counts as
unset and the build fails with `Either delay() or config() annotation parameter must be provided`
(`value()` for cron).

The method rules are the ones of every Kora scheduler: a no-argument member method of a graph
component, not `private`, not `suspend`. No AOP proxy is generated, so the class may be `final` /
non-`open`.

### Job name — the persistent identity

`name` is the db-scheduler **task name**, the key of the job's row. It comes from the annotation
**only** — there is no config override. Blank means the default **`CanonicalClassName#methodName`**,
e.g. `com.example.jobs.ReportJobs#hourlyReport` (a nested class gives `com.example.Outer.Inner#m`).

- Renaming the class or method, **moving the class to another package**, or changing `name` creates a
  **new** job: the old row is orphaned and the new one starts from scratch (including `initialDelay`).
  Set an explicit `name` for anything you may refactor.
- At most **350 characters** (the `task_name` size in the bundled schema). A longer name fails the
  build: `Database scheduled job name '<name>' is <n> characters long, maximum is 350. Set a shorter
  name() in the annotation.`
- Two jobs with the same name fail startup in `KoraDbScheduler.init()`:
  `IllegalStateException: Database scheduled jobs '<a>' and '<b>' have the same name '<name>'; job
  names must be unique, set a unique name in @ScheduleDbWithCron(name = ...), …`.

### Cron

`@ScheduleDbWithCron` hands the expression to db-scheduler's `CronSchedule`: **Spring-style, exactly six
fields with seconds first** (`second minute hour day-of-month month day-of-week`), or a macro
(`@yearly`, `@monthly`, `@weekly`, `@daily`, `@hourly`), or `-`. `* ? , - / L W #` are supported.
Numeric days of the week start on **Monday** (`1` = MON, `0` and `7` = SUN) — unlike the JDK and Quartz
schedulers; prefer `MON-FRI`. This is not Kora's JDK `CronExpression` and not Quartz cron.

- A cron **literal** in the annotation is validated at **compile time**:
  `Invalid CRON expression '<expr>' in @ScheduleDbWithCron on '<fqcn>#<method>()': <reason>.` followed
  by the field diagram and examples. Five-field and seven-field expressions are rejected.
- A cron from **config** is validated when the graph builds:
  `IllegalArgumentException: Invalid CRON expression '<expr>' for database scheduled job
  '<fqcn>#<method>': …` with the same diagram.
- The special value `"-"` disables the job: on startup its pending execution is removed and nothing is
  scheduled.
- Time zone: the `ZoneId` component tagged `@Tag(SchedulingModule.class)`
  (`io.koraframework.scheduling.common.SchedulingModule`) if the graph has one, else the JVM default:

```java
@KoraApp
public interface Application extends JdbcDatabaseModule, DbSchedulerModule /* … */ {

    @Tag(SchedulingModule.class)
    default ZoneId schedulingZone() {
        return ZoneId.of("Europe/Moscow");
    }
}
```

The same component sets the zone of JDK and Quartz cron jobs. Details:
[references/db-scheduler-reference.md](references/db-scheduler-reference.md).

---

## Externalized parameters (`config`)

`config = "<path>"` generates a `SchedulingJobConfig` subtype bound to that path. Annotation values are
defaults, config wins, and an attribute you leave off becomes a required key.

| Annotation | Keys under the config path |
|---|---|
| `@ScheduleDbWithCron` | `cron`, `enabled` — or set the path itself to the cron string |
| `@ScheduleDbWithFixedDelay` | `initialDelay`, `delay`, `enabled` |
| `@ScheduleDbOnce` | `delay`, `enabled` |

`enabled` (default `true`) switches a job off without a code change: a disabled cron or fixed-delay job
has its pending execution removed on startup; a disabled `@ScheduleDbOnce` is not scheduled, and an
execution scheduled earlier is discarded without running the method. The plain-string cron form cannot
carry `enabled` — use the object form (`{ cron = "…", enabled = false }`) or the string `"-"`.

Each path also accepts a `telemetry { … }` block overriding `scheduling.telemetry` for that job. There
is **no `name` key**. Use a path outside `scheduling.dbScheduler` and `scheduling.telemetry`, e.g.
`scheduling.jobs.<name>`.

---

## Module configuration

```hocon
scheduling {
  dbScheduler {
    tableName = "kora_scheduling_db_scheduler_jobs"   # default
    tableInitialize = false                 # default; true = create the table at startup if missing
    executionParallelism = 10               # default; max job bodies running at once on this replica
    shutdownWait = 30s                      # default
    polling {
      strategy = "FETCH"                    # default; or LOCK_AND_FETCH
      prefetchMode = "DEFAULT"              # default; or BOUNDED, BUFFERED
      interval = 10s                        # default
    }
  }
}
```

The key is `tableInitialize` (`DbSchedulerConfig.tableInitialize()`). Up to 2.0.0.RC1 the module's own `README.md`
and the `DbSchedulerConfig` Javadoc example say `initializeTable` (corrected in `2.0.0.RC2` by
kora-projects/kora PR #966) — that key is unknown and ignored without a warning.

Every key has a default, so an absent `scheduling.dbScheduler` section is fine. Full reference, the
prefetch ratios and when to pick `LOCK_AND_FETCH`:
[references/db-scheduler-config-reference.md](references/db-scheduler-config-reference.md).

---

## Table

The module ships plain schema scripts — **not** versioned Flyway migrations — and an idempotent
Liquibase changelog, all creating the default table `kora_scheduling_db_scheduler_jobs` with object
names prefixed by it (`…_pk`, `…_execution_time_idx`, `…_last_heartbeat_idx`,
`…_priority_execution_time_idx`):

| Resource | Contents |
|---|---|
| `db/kora/scheduling-db-scheduler/schema/{postgresql,mysql,mariadb,mssql,oracle,hsql}.sql` | one script per database; `task_name`/`task_instance` are `varchar(350)` (PostgreSQL: `text`) |
| `db/kora/scheduling-db-scheduler/liquibase/changelog.yaml` | one `dbms`-guarded changeset per database, `logicalFilePath: kora/scheduling-db-scheduler/changelog.yaml`, ids `kora-scheduling-db-scheduler-jobs-create-table-<db>`, `MARK_RAN` when the table already exists |

| Approach | What to do |
|---|---|
| Flyway (recommended) | Copy the script for your database into **your** migration folder under the next free version, e.g. `V42__create_kora_scheduling_db_scheduler_jobs.sql` ([asset](assets/V2__create_kora_scheduling_db_scheduler_jobs.sql.template)). Adding `classpath:db/kora/...` as a Flyway location finds nothing — the files are not `V<n>__` migrations |
| Liquibase | `- include: { file: db/kora/scheduling-db-scheduler/liquibase/changelog.yaml }` in your master changelog. It creates the **default** table name only |
| `tableInitialize = true` | At startup `KoraDbScheduler` probes `select 1 from <tableName> where 1 = 0` and, if that fails, runs the script for the detected database with the table name substituted and the object names prefixed with it. Fine for dev and tests; production usually owns its schema |

A non-default `tableName` needs the copied script edited (table and object names), or
`tableInitialize`. With `FlywayJdbcDatabaseModule`/`LiquibaseJdbcDatabaseModule` the migration runs
when the `JdbcDataSource` initialises, which is before the scheduler starts.

---

## Thread model and concurrency

- db-scheduler's own threads poll the table (`polling.interval`, default 10 s) and heartbeat.
- Job bodies run on **fresh virtual threads** named `kora-db-scheduler-N` from a
  `LimitedVirtualThreadPerTaskExecutor`; `executionParallelism` (default 10) caps how many run at once on
  one replica and is also passed to db-scheduler as its thread count.
- One execution of a task instance runs on one replica at a time. A due execution can start up to one
  polling interval late.
- A `Configurer<SchedulerBuilder>` component (from `io.koraframework.common`) is applied last to the
  `SchedulerBuilder` for anything the config does not expose.

---

## Failures and dead executions

The job records the exception on the span/metric/log and **rethrows** it to db-scheduler:

- cron / fixed-delay jobs are rescheduled for their next regular time (db-scheduler
  `OnFailureReschedule`) — no immediate retry;
- `@ScheduleDbOnce` is removed on failure — it does not retry;
- if a replica dies mid-run, the execution stays picked until db-scheduler declares it dead (heartbeat
  every 5 min, dead after 6 missed by default) and another replica revives it.

Make job bodies idempotent: a revived execution runs the work again.

---

## Graceful shutdown

`KoraDbScheduler.release()` calls db-scheduler's `Scheduler.stop()`: polling stops, then running
executions get `scheduling.dbScheduler.shutdownWait` (default 30 s) to finish; after that their virtual
threads are **interrupted** and db-scheduler waits up to another `shutdownWait`. So worst case is about
2× `shutdownWait`. The scheduler depends on the jobs and the `DataSource`, so it is released before
them — a running job still has its resources while it drains. Bound long jobs (batch cap, deadline) and
honour `Thread.currentThread().isInterrupted()`.

---

## Telemetry

Shared with the other schedulers through `scheduling-common`: the same `scheduling.telemetry` block
(`logging.enabled` default `false`, `metrics.enabled` default `false`, `tracing.enabled` default
`true`), the `scheduling.job.duration` timer, span `scheduling <fqcn>#<method>` from a root context, and
per-job overrides under `<config-path>.telemetry`. The metric tag and span attribute
`scheduling.system` is `dbscheduler` (`jdk` / `quartz` for the other schedulers), and log lines carry a
`schedulerType` key. The job `name` is **not** a tag; jobs are identified by class and method. See
[kora-aop-scheduling-jdk telemetry](../kora-aop-scheduling-jdk/references/jdk-scheduling-reference.md#telemetry).

---

## Common pitfalls

| Symptom | Cause / fix |
|---|---|
| App starts, logs `Unexpected error while executing OnStartup tasks. Continuing.` and SQL errors about the job table; jobs never run | Table missing or named differently from `scheduling.dbScheduler.tableName` (default `kora_scheduling_db_scheduler_jobs`) — db-scheduler logs and carries on. Fix the table, then restart so the startup tasks are registered |
| `initializeTable = true` has no effect, the table is never created | The key is `tableInitialize`; `initializeTable` (the name in the module README and Javadoc up to 2.0.0.RC1) is unknown and ignored |
| Jobs restarted from scratch after upgrading from an earlier 2.0 snapshot, old rows linger | The default name changed from `SimpleClassName#method` to `CanonicalClassName#method`. Pin `name` to the old value |
| `<path>.name = "…"` in config has no effect | The name is annotation-only now; the key is unknown and ignored |
| `No component found` for `DataSource` | No JDBC module in the graph; add `JdbcDatabaseModule` (or a `@Tag(KoraDbScheduler.class) DataSource`) |
| `IllegalStateException: Database scheduled jobs '…' and '…' have the same name '…'` | Two jobs resolve to the same task name — set distinct `name`s |
| `IllegalStateException: Duplicate key <name>` | A `Configurer<SchedulerBuilder>` registers a Kora task again via `startTasks(...)` — Kora already registers every startup task itself |
| Both job names in an error are `'java.lang.Void#noop'` | Job logging and metrics are off (the 2.0 defaults) and tracing does not apply (no `Tracer` component, or `tracing.enabled = false`), so `DefaultSchedulingTelemetryFactory` returns the shared `NoopSchedulingTelemetry.INSTANCE`, whose class is `Void` and method `noop`, and `KoraDbJob.toString()` reads it — the duplicate-name and invalid-config-cron errors lose the job identity. Fixed in `2.0.0.RC2` (kora-projects/kora PR #961) — only `2.0.0.RC1` is affected; on RC1 set `scheduling.telemetry.logging.enabled = true` (or `<config-path>.telemetry.logging.enabled`), or locate the job by the name in the message |
| Every run of a job fails with `Graph node value was not initialized because condition failed: …`, silently with job logging off | The scheduled method sits on a `@Conditional` component whose condition failed. The generated `@Root` job factory does not carry the condition, so the task is still registered and every run fails in `ValueOf.get()` (and is rescheduled). Fixed in `2.0.0.RC2` (kora-projects/kora PR #962) — only `2.0.0.RC1` is affected; on RC1 keep the scheduled method on an unconditional component; if it must reach the conditional one, inject `All<T>` and return when it is empty (a `@Nullable T` dependency hits PR #960 on RC1) |
| Changed `initialDelay` has no effect | It applies only when the job's row is first created |
| Longer `delay` in config has no effect until the next run | db-scheduler only moves an existing execution **earlier** on startup; cron changes are applied immediately |
| `@ScheduleDbOnce` ran again after a restart | It is scheduled on every startup when no execution is pending; guard the work if it must happen once ever |
| `Invalid CRON expression '0 0 3 * * ? 2027' in @ScheduleDbWithCron …` | db-scheduler cron is Spring-style six fields; no year field, no five-field form |
| Weekday job fires on the wrong day | Numeric day-of-week counts from Monday here (`1` = MON); a JDK/Quartz expression with `2-6` is shifted by one. Use `MON-FRI` |
| Job runs on every replica | Wrong annotation — `@ScheduleJdkWithCron` or `@ScheduleQuartzWithCron` instead of `@ScheduleDbWithCron` |

---

## Which scheduler?

Same table in all three scheduling sub-skills:

| Need | JDK | Quartz | DB (this skill) |
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

## References, assets

| File | Purpose |
|---|---|
| [references/db-scheduler-reference.md](references/db-scheduler-reference.md) | Annotations, generated code, cron, task lifecycle on restart, failures, custom `DbSchedulerJob` |
| [references/db-scheduler-config-reference.md](references/db-scheduler-config-reference.md) | Every `scheduling.dbScheduler` key, polling/prefetch, schema resources, per-job config, HOCON + YAML |
| [assets/DbScheduledJobs.java.template](assets/DbScheduledJobs.java.template) | Java jobs |
| [assets/DbScheduledJobs.kt.template](assets/DbScheduledJobs.kt.template) | Kotlin jobs |
| [assets/application.conf.template](assets/application.conf.template) | `scheduling.dbScheduler`, telemetry and per-job config |
| [assets/V2__create_kora_scheduling_db_scheduler_jobs.sql.template](assets/V2__create_kora_scheduling_db_scheduler_jobs.sql.template) | PostgreSQL Flyway migration for the default table name, copied from the bundled script |

---

## Related skills

- [kora-aop-scheduling-jdk](../kora-aop-scheduling-jdk/SKILL.md) — in-process timers and cron, every replica
- [kora-aop-scheduling-quartz](../kora-aop-scheduling-quartz/SKILL.md) — Quartz triggers, misfire policies, JDBC JobStore
- [kora-database-jdbc](../kora-database-jdbc/SKILL.md) — the `JdbcDatabaseModule` / `DataSource` the scheduler uses
- [kora-database-migration](../kora-database-migration/SKILL.md) — Flyway / Liquibase for the scheduler table
- [kora-di-runtime](../kora-di-runtime/SKILL.md) — `@Root`, `@Conditional`, `All<T>`, release order
- [kora-telemetry-metrics](../kora-telemetry-metrics/SKILL.md) — the `MeterRegistry` job metrics need
