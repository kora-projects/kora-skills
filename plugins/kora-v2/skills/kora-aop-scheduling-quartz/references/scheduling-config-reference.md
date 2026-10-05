# Quartz Scheduling Configuration Reference (Kora 2.0)

Configuration for `io.koraframework:scheduling-quartz`. For fixed-rate / fixed-delay / one-shot
timers and the JDK cron see [kora-aop-scheduling-jdk](../../kora-aop-scheduling-jdk/SKILL.md).

## Contents

- [Key map](#key-map)
- [Module setup](#module-setup)
- [Quartz properties](#quartz-properties)
- [Per-job configuration](#per-job-configuration)
- [Time zone](#time-zone)
- [Telemetry](#telemetry)
- [Shutdown](#shutdown)
- [Persistence (JDBC JobStore)](#persistence-jdbc-jobstore)
- [Clustering](#clustering)
- [Keys removed or renamed](#keys-removed-or-renamed)
- [See also](#see-also)

---

## Key map

Every key below is read by a specific factory method — nothing else under `scheduling` is
consumed by this module.

| Key | Type | Default | Read by |
|---|---|---|---|
| `scheduling.quartz.properties` | object of `org.quartz.*` strings | Quartz jar defaults | `QuartzModule.quartzProperties` |
| `scheduling.quartz.shutdownWait` | duration | **`30s`** | `QuartzConfig` |
| `scheduling.quartz.compareStartTime` | boolean | `false` | `QuartzConfig` |
| `scheduling.quartz.cleanupOrphanedJobs` | boolean | `false` | `QuartzConfig` |
| `scheduling.telemetry.logging.enabled` | boolean | **`false`** | `SchedulingModule.schedulingTelemetryConfig` |
| `scheduling.telemetry.metrics.enabled` | boolean | **`false`** | same |
| `scheduling.telemetry.metrics.slo` | duration array | 14 buckets, 1 ms … 90 s | same |
| `scheduling.telemetry.metrics.tags` | object | `{}` | same |
| `scheduling.telemetry.tracing.enabled` | boolean | **`true`** | same |
| `scheduling.telemetry.tracing.attributes` | object | `{}` | same |
| `<job config path>.cron` | string | annotation `value()` when present | generated `*CronConfig` |
| `<job config path>.enabled` | boolean | `true` | generated `*CronConfig` (`SchedulingJobConfig.enabled()`) |
| `<job config path>.telemetry.*` | object | falls back to `scheduling.telemetry` | generated `*CronConfig` |

Unknown keys anywhere in this tree are ignored without a warning. A typo therefore looks like a
clean startup on defaults.

---

## Module setup

```java
@KoraApp
public interface Application extends
    HoconConfigModule,      // or YamlConfigModule
    LogbackModule,
    QuartzModule {
}
```

```groovy
dependencies {
    koraBom platform("io.koraframework:kora-bom:$koraVersion")   // koraVersion=2.0.0.RC2
    annotationProcessor "io.koraframework:annotation-processors" // Kotlin: ksp "io.koraframework:symbol-processors"

    implementation "io.koraframework:scheduling-quartz"
    implementation "io.koraframework:config-hocon"
}
```

---

## Quartz properties

Raw `org.quartz.*` properties go under **`scheduling.quartz.properties`** and are handed to
`StdSchedulerFactory.initialize(Properties)` unchanged.

### HOCON

```hocon
scheduling.quartz.properties {
  "org.quartz.scheduler.instanceName" = "my-service-scheduler"
  "org.quartz.threadPool.threadCount" = "20"
  "org.quartz.threadPool.threadPriority" = "5"
  "org.quartz.jobStore.misfireThreshold" = "60000"
}
```

### YAML

```yaml
scheduling:
  quartz:
    properties:
      org.quartz.scheduler.instanceName: "my-service-scheduler"
      org.quartz.threadPool.threadCount: "20"
      org.quartz.threadPool.threadPriority: "5"
      org.quartz.jobStore.misfireThreshold: "60000"
```

Values are Quartz properties — keep them **strings**, including numbers.

### Resolution order

`QuartzModule.quartzProperties` builds a defaults set, then lets your config override it:

1. everything in `org/quartz/quartz.properties` bundled inside the Quartz jar;
2. `org.quartz.scheduler.instanceName = kora-quartz-scheduler` (overriding Quartz's
   `DefaultQuartzScheduler`);
3. `org.quartz.scheduler.instanceId = AUTO`;
4. every key present in `scheduling.quartz.properties` wins over 1–3.

Effective defaults inherited from the Quartz jar at 2.5.2:

| Property | Default |
|---|---|
| `org.quartz.threadPool.class` | `org.quartz.simpl.SimpleThreadPool` |
| `org.quartz.threadPool.threadCount` | `10` |
| `org.quartz.threadPool.threadPriority` | `5` |
| `org.quartz.threadPool.threadsInheritContextClassLoaderOfInitializingThread` | `true` |
| `org.quartz.jobStore.class` | `org.quartz.simpl.RAMJobStore` |
| `org.quartz.jobStore.misfireThreshold` | `60000` |
| `org.quartz.scheduler.rmi.export` / `.proxy` | `false` |
| `org.quartz.scheduler.wrapJobExecutionInUserTransaction` | `false` |

`threadCount` is the ceiling on concurrent job executions across the whole application — see
[the thread model](quartz-scheduling-reference.md#thread-model).

---

## Per-job configuration

`@ScheduleQuartzWithCron(config = "<path>")` generates a `@ConfigMapper` interface extending
`SchedulingJobConfig`, bound to `<path>`. The node may be a **string** or an **object**.

```java
@ScheduleQuartzWithCron(config = "jobs.nightly")
void nightlyReport() { }

@ScheduleQuartzWithCron(config = "jobs.hourly")
void hourlyCheck() { }

@ScheduleQuartzWithCron(value = "0 */15 * * * ?", config = "jobs.sync")
void sync() { }
```

```hocon
jobs {
  # string form — cron only
  nightly = "0 0 3 * * ?"

  # object form — cron, on/off switch and per-job telemetry
  hourly {
    cron = "0 0 * * * ?"
    enabled = true
    telemetry {
      logging.enabled = true
      metrics.enabled = true
      metrics.tags { component = "billing" }
      tracing.enabled = false
    }
  }

  # switch a job off without a rebuild; the annotation value stays the cron default
  sync.enabled = false
}
```

```yaml
jobs:
  nightly: "0 0 3 * * ?"
  hourly:
    cron: "0 0 * * * ?"
    enabled: true
    telemetry:
      logging:
        enabled: true
      metrics:
        enabled: true
        tags:
          component: "billing"
      tracing:
        enabled: false
  sync:
    enabled: false
```

- If the annotation also carries `value`, that expression is the fallback used when the node is
  absent; a present node always wins. An object node without `cron` also falls back to `value`.
- If the annotation carries no `value`, the node is required — an absent one raises
  `ConfigValueException` during graph build, and an object node must contain `cron`.
- A cron from config is validated at graph init: `IllegalArgumentException: Invalid CRON
  expression '…' for Quartz job '<Class>#<method>': …` with the expected field layout.
- **`enabled = false`** builds the job with no triggers. The registrar still registers the job,
  logs `Quartz Job '<job class>' has no triggers and is not scheduled` at INFO, and unschedules
  any trigger a persistent job store still holds for it. The string form cannot carry `enabled`;
  use the object form.
- Every field under `telemetry` is nullable and falls back to `scheduling.telemetry`; an omitted
  `telemetry` block is fine.
- **Per-job telemetry and `enabled` are only available through `config`.** Jobs declared with an
  inline cron or with `@ScheduleQuartzWithTrigger` get the global `scheduling.telemetry` settings;
  the generated code passes `null` for the per-job config in those branches.

---

## Time zone

Cron triggers run in the JVM default zone unless the graph has a `ZoneId` tagged with
`io.koraframework.scheduling.common.SchedulingModule`:

```java
@Tag(SchedulingModule.class)
default ZoneId schedulingZone() {
    return ZoneId.of("Europe/Moscow");
}
```

```kotlin
@Tag(SchedulingModule::class)
fun schedulingZone(): ZoneId = ZoneId.of("Europe/Moscow")
```

The parameter is `@Nullable` on every generated cron factory, so leaving it out is fine. It is one
component for all three Kora schedulers, not a Quartz-only setting. The zone is part of the
persisted-trigger comparison: changing it reschedules stored cron triggers at the next start.
Triggers you build yourself for `@ScheduleQuartzWithTrigger` are not touched — set their zone on
the `CronScheduleBuilder` yourself.

---

## Telemetry

Defaults come from `io.koraframework.telemetry.common.TelemetryConfig`: **logging `false`,
metrics `false`, tracing `true`**. Nothing is reported until you turn it on.

```hocon
scheduling.telemetry {
  logging.enabled = true
  metrics {
    enabled = true
    slo = ["100ms", "500ms", "1s", "10s", "1m"]
    tags { service = "billing" }
  }
  tracing {
    enabled = true
    attributes { deployment = "prod" }
  }
}
```

### Metrics

One Micrometer **`Timer`** named **`scheduling.job.duration`**, recorded once per execution.

| Tag | Value |
|---|---|
| `scheduling.system` | `quartz` (`jdk` / `dbscheduler` for the other schedulers) |
| `code.function.name` | `<fully.qualified.Class>#<method>` |
| `system.name.simple` | `<SimpleClass>#<method>` |
| `system.name.canonical` | `<fully.qualified.Class>#<method>` |
| `error.type` | canonical exception class name, or `""` on success |
| `system.config` | the `config` path — only present for `@ScheduleQuartzWithCron(config = "…")` |
| … | everything in `scheduling.telemetry.metrics.tags` (or the per-job override) |

Buckets come from `metrics.slo`; the default array is 1, 10, 50, 100, 200, 500, 1000, 2000,
5000, 10000, 20000, 30000, 60000, 90000 ms.

Metrics also need a `MeterRegistry` in the graph (`micrometer-module`) — with the flag on but no
registry the telemetry degrades to a no-op.

### Tracing

Span name `scheduling <fully.qualified.Class>#<method>`, with attributes `scheduling.system`
(`quartz`), `code.function.name`, `system.name.simple`, `system.name.canonical`, optionally
`system.config`, plus everything in `tracing.attributes`. Requires an OpenTelemetry `Tracer` in
the graph.

### Logging

| Event | Level | Message |
|---|---|---|
| start | DEBUG | `Scheduled Job execution started` |
| success | INFO | `Scheduled Job execution completed` |
| failure | WARN | `Scheduled Job execution failed with error` |

Key-values: `schedulerType` (`quartz`), `jobClass`, `jobMethod`, `duration` (ms), plus
`jobConfigPath` when the job uses `config`, plus `exceptionType` / `exceptionMessage` on failure.

The **logger name is `<fully.qualified.Class>#<method>`**. Logback splits the hierarchy on `.`,
so `Foo#nightly` is one segment: a `logging.levels` entry for the class alone does not match it.
Target the package, or the exact `Class#method` string:

```hocon
logging.levels {
  "com.example.jobs" = "DEBUG"                       # matches every job in the package
  "com.example.jobs.Reports#nightly" = "DEBUG"       # matches exactly one job
}
```

### Custom telemetry factory

`SchedulingTelemetryFactory.get` takes the scheduler type first:
`get(String schedulerType, @Nullable String jobConfigPath, @Nullable JobTelemetryConfig
jobTelemetryConfig, Class<?> jobClass, String jobMethod)`. A factory written against the RC1-era
four-argument signature no longer compiles.

---

## Shutdown

| Key | Type | Default |
|---|---|---|
| `scheduling.quartz.shutdownWait` | duration | **`30s`** |

`KoraQuartzScheduler.release()`:

1. `scheduler.standby()` — no new firings;
2. waits up to `shutdownWait` for running jobs;
3. interrupts the threads of jobs still running (`KoraQuartzJob` is an
   `org.quartz.InterruptableJob`) and logs `KoraQuartzScheduler interrupting jobs [...] still
   running after <shutdownWait>` at WARN;
4. waits up to `shutdownWait` again, then logs `KoraQuartzScheduler stopped while jobs [...] are
   still running after interruption` at WARN if any are left;
5. `scheduler.shutdown(false)`.

| Value | Effect |
|---|---|
| `30s` (default) | up to ~60 s in total for a job that ignores the interrupt |
| `0s` | interrupts running jobs immediately |
| `365d` | effectively waits for completion — keep the platform grace period (Kubernetes `terminationGracePeriodSeconds`) at least as long |

See [graceful-shutdown-reference.md](graceful-shutdown-reference.md).

---

## Persistence (JDBC JobStore)

Kora passes the properties straight to `StdSchedulerFactory`, so any Quartz job store is
configurable — but Kora supplies **nothing** beyond that. A JDBC job store is entirely the
application's responsibility:

1. **A JDBC driver** on the runtime classpath (`org.postgresql:postgresql`, …). Kora's own
   `database-jdbc` datasource is *not* wired into Quartz; Quartz manages its own connections.
2. **A Quartz connection provider.** Quartz's `HikariCpPoolingConnectionProvider` needs
   `com.zaxxer:HikariCP` and `C3p0PoolingConnectionProvider` needs `com.mchange:c3p0`. Both are
   `provided` scope in the Quartz POM *and* excluded by `scheduling-quartz/build.gradle`, so
   neither is on the classpath until the application adds it.
3. **The `QRTZ_*` tables**, created from Quartz's DDL for the database (`tables_postgres.sql`
   and friends, shipped in the Quartz distribution). Kora runs no migration for them — add them
   to your Flyway/Liquibase changelog, or apply them out of band.

```groovy
dependencies {
    implementation "io.koraframework:scheduling-quartz"
    runtimeOnly    "org.postgresql:postgresql:42.7.13"
    // Quartz 2.5.2 compiles HikariCpPoolingConnectionProvider against HikariCP 5.0.1;
    // pin whatever line you have verified against it.
    implementation "com.zaxxer:HikariCP:5.0.1"
}
```

```hocon
scheduling.quartz.properties {
  "org.quartz.jobStore.class"                = "org.quartz.impl.jdbcjobstore.JobStoreTX"
  "org.quartz.jobStore.driverDelegateClass"  = "org.quartz.impl.jdbcjobstore.PostgreSQLDelegate"
  "org.quartz.jobStore.tablePrefix"          = "QRTZ_"
  "org.quartz.jobStore.dataSource"           = "quartzDs"

  "org.quartz.dataSource.quartzDs.provider"  = "hikaricp"
  "org.quartz.dataSource.quartzDs.driver"    = "org.postgresql.Driver"
  "org.quartz.dataSource.quartzDs.URL"       = ${DB_URL}
  "org.quartz.dataSource.quartzDs.user"      = ${DB_USER}
  "org.quartz.dataSource.quartzDs.password"  = ${DB_PASSWORD}
  "org.quartz.dataSource.quartzDs.maxConnections" = "5"
}
```

Only with a persistent store does `@PersistJobDataAfterExecution` mean anything: with the
default `RAMJobStore` the `JobDataMap` lives in memory and dies with the process.

### What Kora stores, and when it reschedules

- Jobs are stored under the group **`kora`**, named by the generated job class's canonical name
  (`kora.com.example.$Reports_nightly_Job`). A job of a known class still in the `DEFAULT` group
  — how Kora 1.x and RC1 stored it — is deleted there with its triggers and re-registered under
  `kora` at start.
- A persisted trigger is **kept as is** at restart unless its schedule (cron expression, simple
  repeat interval/count), end time or cron time zone changed. Quartz sets the start time of a
  trigger built without `startAt()` to the moment it is built, so comparing it would reschedule
  every trigger on every start, losing misfire handling for firings missed while the service was
  down and shifting simple-trigger phases.

| Key | Default | Turn it on when |
|---|---|---|
| `scheduling.quartz.compareStartTime` | `false` | every trigger uses a fixed `startAt()` and changing it must reschedule the trigger |
| `scheduling.quartz.cleanupOrphanedJobs` | `false` | the store belongs to one application and deployments never run two versions at once |

`cleanupOrphanedJobs` runs **before** the scheduler starts and removes Kora jobs (group `kora`,
plus `DEFAULT`-group jobs named like generated `$Type_method_Job` classes) that the starting
instance does not know, with their triggers; jobs you added to the `Scheduler` yourself are kept.
It is the cure for `JobPersistenceException: Couldn't retrieve job because a required class was
not found` after a job class is deleted or renamed. It is **unsafe** when:

- several applications share the Quartz tables under the same scheduler name
  (`kora-quartz-scheduler` by default) — each removes the others' jobs;
- instances of different versions run at once, e.g. a rolling deployment — an old instance
  starting after a new one removes the jobs the new version added, and they return only after a
  new instance restarts.

---

## Clustering

Clustering is Quartz's own feature, configured through the same passthrough:

```hocon
scheduling.quartz.properties {
  "org.quartz.jobStore.class"       = "org.quartz.impl.jdbcjobstore.JobStoreTX"
  "org.quartz.jobStore.isClustered" = "true"
  "org.quartz.jobStore.clusterCheckinInterval" = "20000"
  # instanceName must be identical on every node; instanceId must differ
  "org.quartz.scheduler.instanceName" = "my-service-scheduler"
  "org.quartz.scheduler.instanceId"   = "AUTO"
}
```

Kora already defaults `instanceId` to `AUTO` and `instanceName` to `kora-quartz-scheduler`, so a
cluster works on the defaults as long as every node runs the same configuration. Clustering
requires a JDBC job store — `RAMJobStore` cannot cluster.

Constraints that follow from how Kora registers jobs (`KoraQuartzJobRegistrar` /
`KoraQuartzJobFactory`):

- **Every node must run the same build.** Job instances are resolved from the DI graph by the
  generated job class; unknown classes fall through to Quartz's `PropertySettingJobFactory`,
  which needs a no-arg constructor that generated job classes do not have. A node cannot execute
  a job class it does not itself carry.
- **The registrar is the source of truth for triggers.** At every `init()` and `graphRefreshed()`
  it re-adds each job durably and reconciles its triggers against the compiled/config state,
  unscheduling any others. A trigger row edited directly in `QRTZ_TRIGGERS` is replaced when its
  schedule, end time or zone no longer matches.
- **Trigger identities must be unique** across all jobs; a duplicate fails startup with
  `IllegalStateException: Quartz trigger '…' is declared more than once, by jobs '…' and '…'`.
- Jobs are keyed by the generated job class's canonical name, so renaming a job class or its
  method orphans the old rows in the job store — see `cleanupOrphanedJobs` above, with its
  rolling-deploy caveat.

---

## Keys removed or renamed

| Old key | Now | Failure mode |
|---|---|---|
| `quartz { "org.quartz.*" = … }` (Kora 1.x root) | `scheduling.quartz.properties { … }` | silent — Quartz starts on its own defaults |
| `scheduling.waitForJobComplete` (Kora 1.x) | `scheduling.quartz.shutdownWait` | silent — the 30 s default applies |
| `scheduling.quartz.waitForJobComplete` (RC1 / earlier 2.0 snapshots) | `scheduling.quartz.shutdownWait` | silent — the 30 s default applies; jobs are now interrupted after it |
| `ru.tinkoff.kora:scheduling-quartz` | `io.koraframework:scheduling-quartz` | dependency resolution failure |
| `ru.tinkoff.kora:kora-parent` | `io.koraframework:kora-bom` | dependency resolution failure |

The 1.x claim that `scheduling.telemetry.metrics.enabled` defaults to `true` no longer holds:
in 2.0 both metrics and logging default to `false`.

---

## See also

- [quartz-scheduling-reference.md](quartz-scheduling-reference.md) — annotations, generated code, cron grammar
- [graceful-shutdown-reference.md](graceful-shutdown-reference.md) — shutdown semantics
- [kora-config-hocon](../../kora-config-hocon/SKILL.md) — HOCON substitution and typed config
- [kora-telemetry-metrics](../../kora-telemetry-metrics/SKILL.md) — wiring a `MeterRegistry`
- [Quartz configuration reference](https://www.quartz-scheduler.org/documentation/quartz-2.3.0/configuration/) — upstream property list
