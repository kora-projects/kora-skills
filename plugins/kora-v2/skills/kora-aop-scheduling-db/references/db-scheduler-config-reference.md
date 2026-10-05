# DB Scheduling Configuration Reference

Every key read by `io.koraframework:scheduling-db-scheduler`. Defaults are the ones declared in
`DbSchedulerConfig`; the module maps it from the path **`scheduling.dbScheduler`**.

## Contents

- [Key map](#key-map)
- [Global configuration](#global-configuration) — HOCON and YAML
- [Reference table](#reference-table)
- [Polling strategy and prefetch](#polling-strategy-and-prefetch)
- [`tableInitialize`](#tableinitialize) and the bundled schema
- [Per-job configuration](#per-job-configuration)
- [Customising the `SchedulerBuilder`](#customising-the-schedulerbuilder)

---

## Key map

| Path | Read by | Contains |
|---|---|---|
| `scheduling.dbScheduler` | `DbSchedulerModule` | table, parallelism, polling, shutdown |
| `scheduling.telemetry` | `SchedulingModule` (shared with JDK and Quartz) | logging / metrics / tracing defaults for all jobs |
| whatever you write in `config = "…"` | the generated per-job config | that job's timing, `enabled`, and `telemetry` overrides |
| `jdbc` (by default) | `JdbcDatabaseModule` | the connection pool the scheduler uses — see [kora-database-jdbc](../../kora-database-jdbc/SKILL.md) |

---

## Global configuration

### HOCON (`application.conf`)

```hocon
scheduling {
  dbScheduler {
    tableName = "kora_scheduling_db_scheduler_jobs"
    tableInitialize = false
    executionParallelism = 10
    shutdownWait = 30s
    polling {
      strategy = "FETCH"
      prefetchMode = "DEFAULT"
      interval = 10s
    }
  }

  telemetry {
    logging.enabled = false
    metrics.enabled = false
    tracing.enabled = true
  }
}
```

### YAML (`application.yaml`)

```yaml
scheduling:
  dbScheduler:
    tableName: "kora_scheduling_db_scheduler_jobs"
    tableInitialize: false
    executionParallelism: 10
    shutdownWait: "30s"
    polling:
      strategy: "FETCH"
      prefetchMode: "DEFAULT"
      interval: "10s"
  telemetry:
    logging:
      enabled: false
    metrics:
      enabled: false
    tracing:
      enabled: true
```

---

## Reference table

| Key | Type | Default | Notes |
|---|---|---|---|
| `scheduling.dbScheduler.tableName` | string | `kora_scheduling_db_scheduler_jobs` | Used at runtime and by `tableInitialize`; the bundled scripts and changelog create this default name |
| `scheduling.dbScheduler.tableInitialize` | boolean | `false` | Create the table at startup if missing. Not `initializeTable` — the module README and the `DbSchedulerConfig` Javadoc example showed that name up to 2.0.0.RC1 (corrected by kora-projects/kora PR #966), but it is unknown and ignored |
| `scheduling.dbScheduler.executionParallelism` | int | `10` | Max job bodies running at once on this replica; db-scheduler thread count and the virtual-thread executor limit |
| `scheduling.dbScheduler.shutdownWait` | duration | `30s` | db-scheduler `shutdownMaxWait`: wait before interrupting running jobs, then up to the same again |
| `scheduling.dbScheduler.polling.strategy` | enum | `FETCH` | `FETCH` or `LOCK_AND_FETCH` |
| `scheduling.dbScheduler.polling.prefetchMode` | enum | `DEFAULT` | `DEFAULT`, `BOUNDED`, `BUFFERED` |
| `scheduling.dbScheduler.polling.interval` | duration | `10s` | Delay between polls; a due execution may start up to this late |

The section may be omitted entirely — every key has a default. There is no `enabled` switch: leave
`DbSchedulerModule` off the `@KoraApp` to disable the scheduler.

---

## Polling strategy and prefetch

| `strategy` | db-scheduler mode | Use when |
|---|---|---|
| `FETCH` | `pollUsingFetch` — select due executions, then claim each one with an optimistic update | default; works on every supported database |
| `LOCK_AND_FETCH` | `pollUsingLockAndFetch` — select and claim a batch in one round trip using row locks with `SKIP LOCKED` | many executions and many replicas, on a database db-scheduler supports lock-and-fetch for (check db-scheduler's documentation for yours) |

`prefetchMode` chooses the lower/upper *fraction-of-threads* limits db-scheduler uses to refill its
local queue, relative to `executionParallelism`:

| `prefetchMode` | lower / upper | Effect |
|---|---|---|
| `DEFAULT` | db-scheduler's own: `0.5 / 3.0` for `FETCH`, `0.5 / 1.0` for `LOCK_AND_FETCH` | unchanged db-scheduler behaviour |
| `BOUNDED` | `0.5 / 1.0` | local backlog stays close to `executionParallelism`; refill at about half |
| `BUFFERED` | `0.75 / 2.0` | a moderate local buffer, fewer idle gaps between executions |

With `LOCK_AND_FETCH` everything prefetched is already claimed by this replica, so a small upper limit
(`BOUNDED`) keeps work from piling up on one node.

---

## `tableInitialize`

With `tableInitialize = true`, `KoraDbScheduler.init()` opens a connection and runs
`select 1 from <tableName> where 1 = 0`. If that fails, it detects the database from the JDBC metadata
(PostgreSQL, MariaDB, MySQL, MS SQL Server, Oracle, HSQL — anything else throws
`IllegalStateException: Unsupported database for DbScheduler table initialization`), loads
`db/kora/scheduling-db-scheduler/schema/<db>.sql`, replaces `kora_scheduling_db_scheduler_jobs` with
`tableName` and prefixes the primary-key and index names with the table name (the part after the last
`.` for a schema-qualified `app.jobs`), and executes it statement by statement. Tables with different
names can live side by side in one schema.

It is a convenience for development and tests. The check-then-create is not coordinated between
replicas starting at the same time; production schemas belong in a migration — see the SQL asset
[V2__create_kora_scheduling_db_scheduler_jobs.sql.template](../assets/V2__create_kora_scheduling_db_scheduler_jobs.sql.template).

### Bundled schema resources

| Tool | Resource |
|---|---|
| Flyway | none to point at: `db/kora/scheduling-db-scheduler/schema/{postgresql,mysql,mariadb,mssql,oracle,hsql}.sql` are plain scripts, not `V<n>__` migrations, so a Flyway location over them finds nothing. Copy the script into your own migrations under the next free version — a bundled `V1__` would clash with your own version sequence |
| Liquibase | `db/kora/scheduling-db-scheduler/liquibase/changelog.yaml` — include it from your master changelog. Changesets `kora-scheduling-db-scheduler-jobs-create-table-<db>`, each guarded by `dbms`, `logicalFilePath: kora/scheduling-db-scheduler/changelog.yaml`, precondition `MARK_RAN` when the table already exists |

All of them create the default name `kora_scheduling_db_scheduler_jobs` with `…_pk`,
`…_execution_time_idx`, `…_last_heartbeat_idx` and `…_priority_execution_time_idx`. `task_name` and
`task_instance` are `varchar(350)` (PostgreSQL `text`), which is where the 350-character job-name limit
comes from. For another `tableName`, edit the copied script or use `tableInitialize`; the Liquibase
changelog always creates the default name.

Coming from an earlier 2.0 snapshot: the old resources `db/scheduling-db/flyway/<db>/V1__create_scheduled_tasks.sql`
and `db/scheduling-db/liquibase/changelog.yaml` (table `scheduled_tasks`) no longer exist, and the old
default table was `kora_scheduling_db_jobs`. Keep an existing table with `tableName = "kora_scheduling_db_jobs"`,
or migrate the rows.

---

## Per-job configuration

```java
@ScheduleDbWithCron(value = "0 0 2 * * *", name = "nightly-cleanup", config = "scheduling.jobs.cleanup")
void cleanup() { }

@ScheduleDbWithFixedDelay(config = "scheduling.jobs.outbox")              // delay required in config
void relayOutbox() { }

@ScheduleDbOnce(delay = 1, unit = ChronoUnit.MINUTES, config = "scheduling.jobs.warmup")
void warmup() { }
```

```hocon
scheduling.jobs {
  cleanup {
    cron = "0 30 2 * * *"
    telemetry.logging.enabled = true
  }
  outbox {
    initialDelay = 30s
    delay = 10s
  }
  warmup {
    delay = 5m
    enabled = false          # not scheduled; a pending execution is discarded without running
  }
}
```

| Annotation | Keys | Required when the annotation omits it |
|---|---|---|
| `@ScheduleDbWithCron` | `cron`, `enabled` (or the path is the cron string) | `cron` |
| `@ScheduleDbWithFixedDelay` | `initialDelay`, `delay`, `enabled` | `delay` |
| `@ScheduleDbOnce` | `delay`, `enabled` | `delay` |

For cron, a non-blank annotation `value` is used when the path is absent; a present path wins. The
string form (`scheduling.jobs.cleanup = "0 30 2 * * *"`) cannot carry `enabled` — use the object form,
or `"-"`. `enabled` defaults to `true`; `false` removes the job's pending execution on startup (cron,
fixed delay) or keeps it from being scheduled (once).

There is **no `name` key**: the job name is the annotation `name`, else `CanonicalClassName#method`,
and an old `name = "…"` under the path is an unknown key, ignored silently. Durations accept `30s`, `5m`, ISO-8601 or a bare
number of milliseconds. Every path also takes a `telemetry` block (`logging.enabled`,
`metrics.enabled`, `metrics.slo`, `metrics.tags`, `tracing.enabled`, `tracing.attributes`) that falls
back to `scheduling.telemetry`.

---

## Customising the `SchedulerBuilder`

Anything not in `DbSchedulerConfig` (heartbeat interval, scheduler name, immediate execution, failure
log level, …) goes through one `Configurer<SchedulerBuilder>` component, applied after Kora's own
settings:

```java
@Module
public interface SchedulerTuning {

    default Configurer<SchedulerBuilder> dbSchedulerConfigurer() {
        return builder -> builder
            .heartbeatInterval(Duration.ofMinutes(1))
            .enableImmediateExecution();
    }
}
```

Do not call `startTasks(...)` or `executorService(...)` there unless you mean to replace Kora's
registration or virtual-thread executor — re-registering a Kora task fails with a duplicate task name.
