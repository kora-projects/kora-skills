# Quartz Scheduling Reference (Kora 2.0)

**Artifact:** `io.koraframework:scheduling-quartz`
**Module:** `io.koraframework.scheduling.quartz.QuartzModule` (extends `io.koraframework.scheduling.common.SchedulingModule`)
**Annotation package:** `io.koraframework.scheduling.quartz.annotation`
**Quartz:** `org.quartz-scheduler:quartz:2.5.2`

## Contents

- [Module contents](#module-contents)
- [Annotations](#annotations)
- [Generated code](#generated-code)
- [The JobExecutionContext argument](#the-jobexecutioncontext-argument)
- [Contract rules](#contract-rules)
- [Thread model](#thread-model)
- [Error propagation](#error-propagation)
- [Cron expression reference](#cron-expression-reference)
- [Scheduled method on a `@Conditional` component](#scheduled-method-on-a-conditional-component)
- [Migrating from RC1 / earlier 2.0 snapshots](#migrating-from-rc1--earlier-20-snapshots)
- [Migrating from Kora 1.x](#migrating-from-kora-1x)
- [See also](#see-also)

---

## Module contents

`QuartzModule` contributes five factory methods:

| Component | Notes |
|---|---|
| `@Tag(QuartzModule.class) Properties` | merged Quartz properties, read from `scheduling.quartz.properties` |
| `QuartzConfig` | read from `scheduling.quartz` — `shutdownWait`, `cleanupOrphanedJobs`, `compareStartTime` |
| `KoraQuartzJobFactory` | resolves `KoraQuartzJob` instances out of the graph by class |
| `@Root KoraQuartzScheduler` | `Wrapped<org.quartz.Scheduler>` + `Lifecycle`; starts/stops the scheduler |
| `@Root KoraQuartzJobRegistrar` | `Lifecycle` + `RefreshListener`; registers jobs and triggers |

Because `KoraQuartzScheduler` is `Wrapped<Scheduler>`, **`org.quartz.Scheduler` is injectable**
into any component — useful for `standby()`, `pauseAll()`, `triggerJob(...)` from an admin
endpoint. `SchedulingModule` additionally supplies `SchedulingTelemetryConfig` and a
`@DefaultComponent SchedulingTelemetryFactory`.

Consumed transitively via `api`: Quartz 2.5.2. Kora's `scheduling-quartz/build.gradle` excludes
`com.mchange:c3p0`, `com.mchange:mchange-commons-java`, `com.zaxxer:HikariCP-java7` and
`org.slf4j:slf4j-api` from it. Quartz's own POM already marks `c3p0` and `HikariCP` as
`provided`, so neither connection pool reaches an application classpath — that matters only for
a [JDBC JobStore](scheduling-config-reference.md#persistence-jdbc-jobstore).

---

## Annotations

All four are in `io.koraframework.scheduling.quartz.annotation`.

### `@ScheduleQuartzWithCron`

```java
public @interface ScheduleQuartzWithCron {
    String value() default "";      // cron expression
    String identity() default "";   // Quartz TriggerBuilder.withIdentity(...)
    String config() default "";     // config path holding the cron
}
```

```java
@Component
public final class Reports {

    @ScheduleQuartzWithCron("0 0 3 * * ?")
    void nightly() { }

    @ScheduleQuartzWithCron(value = "0 0 * * * ?", identity = "hourly-check")
    void hourly() { }

    @ScheduleQuartzWithCron(config = "jobs.weekly")
    void weekly() { }
}
```

`identity` defaults to `<fully.qualified.Class>#<method>`. Two jobs that both leave `identity`
empty never collide, because the default already carries the class and method. Two jobs with the
**same explicit** identity fail startup in `KoraQuartzJobRegistrar`:

```
IllegalStateException: Quartz trigger 'DEFAULT.hourly-check' is declared more than once, by jobs
'com.example.$Reports_hourly_Job' and 'com.example.$Audit_hourly_Job'; trigger identities must be
unique, set a unique identity in @ScheduleQuartzWithCron(identity = ...) or in TriggerBuilder.withIdentity(...)
```

The same check covers triggers supplied through `@ScheduleQuartzWithTrigger`.

**`value` / `config` interaction**, exactly as the generator builds it:

| `value` | `config` | Behaviour |
|---|---|---|
| set | empty | cron is baked into the generated trigger; the literal is validated at compile time |
| empty | empty | Java: compile error *"Quartz @ScheduleQuartzWithCron on '…' has no cron source."*. **Kotlin: no compile error** — the KSP generator has no such guard and emits `cronSchedule("", …)`, which fails at graph init with `IllegalArgumentException: Invalid CRON expression '' for Quartz job '…'` |
| set | set | config node wins; when the node is absent the `value` is used |
| empty | set | config node is **required** — an absent one throws `ConfigValueException` during graph build |

The config node may be a bare string or an object with `cron`, `enabled` and `telemetry`; see
[per-job configuration](scheduling-config-reference.md#per-job-configuration).

### `@ScheduleQuartzWithTrigger`

```java
@Target(ElementType.METHOD)
@Retention(RetentionPolicy.CLASS)
public @interface ScheduleQuartzWithTrigger {
    Class<?> value();               // tag selecting the org.quartz.Trigger
}
```

The class is used as a **`@Tag`** on the `org.quartz.Trigger` parameter of the generated factory
method. Supply the trigger anywhere in the graph under the same tag:

```java
@KoraApp
public interface Application extends QuartzModule {

    @Tag(RapidCheckJob.class)
    default Trigger rapidCheckTrigger() {
        return TriggerBuilder.newTrigger()
            .withIdentity("rapidCheck")
            .startNow()
            .withSchedule(SimpleScheduleBuilder.simpleSchedule()
                .withIntervalInSeconds(5)
                .repeatForever())
            .build();
    }
}

@Component
public final class RapidCheckJob {

    @ScheduleQuartzWithTrigger(RapidCheckJob.class)
    void checkStatus() { }
}
```

```kotlin
@Component
class RapidCheckJob {

    @ScheduleQuartzWithTrigger(RapidCheckJob::class)
    fun checkStatus() { }
}
```

A missing trigger is a normal DI failure ("no component found" for the tagged `Trigger`), not a
silent no-op. The tag class is arbitrary — tagging with the job class is only a convention that
keeps the two ends readable. `@ScheduleQuartzWithTrigger` has no `config`, so it has no per-job
`enabled` switch and no per-job telemetry.

A `KoraQuartzJob` can carry several triggers (`KoraQuartzJob.getTriggers()` returns a list), but
the generated code always builds a single-trigger job (or none, when a config-declared cron job is
disabled); multiple triggers per method are not expressible through the annotations.

### `@DisallowConcurrentExecution` and `@PersistJobDataAfterExecution`

Both are **Kora's own** annotations in `io.koraframework.scheduling.quartz.annotation`,
`@Target(METHOD)`, `@Retention(RUNTIME)`. They carry no attributes. The generator also honours the
Quartz originals — but the placement rules differ and are not interchangeable:

| Annotation | Where the generator looks |
|---|---|
| `io.koraframework.scheduling.quartz.annotation.DisallowConcurrentExecution` | on the **method** |
| `org.quartz.DisallowConcurrentExecution` | on the **class** |
| `io.koraframework.scheduling.quartz.annotation.PersistJobDataAfterExecution` | on the **method** |
| `org.quartz.PersistJobDataAfterExecution` | on the **class** |

Either form results in the corresponding `org.quartz.*` annotation being placed on the generated
job class. Neither annotation can be moved to the other's position: the Quartz originals are
`@Target(TYPE)` and the Kora ones are `@Target(METHOD)`, so a misplaced one is a compile error
rather than a silently ignored annotation.

```java
@Component
public final class HourlyJob {

    @DisallowConcurrentExecution                 // Kora's, on the method
    @ScheduleQuartzWithCron("0 0 * * * ?")
    void hourly() { }
}
```

```java
@org.quartz.DisallowConcurrentExecution          // Quartz's, on the class
@Component
public final class AllJobsSerial {

    @ScheduleQuartzWithCron("0 0 * * * ?")
    void hourly() { }
}
```

`@PersistJobDataAfterExecution` asks Quartz to re-store the `JobDataMap` after each execution.
It only means something with a persistent job store — with the default `RAMJobStore` the map
dies with the process. Kora never reads or writes the map for you: the job body must do that
through the `JobExecutionContext` argument. Pair it with `@DisallowConcurrentExecution` to avoid
lost updates.

---

## Generated code

Per annotated class, in the class's own package:

| Generated type | Shape |
|---|---|
| `$<Class>_SchedulingModule` | `@Module` interface, one factory method per scheduled method |
| `$<Class>_<method>_Job` | `public final class … extends KoraQuartzJob` |
| a `*CronConfig` interface | only for `@ScheduleQuartzWithCron(config = "…")`; `@ConfigMapper`, extends `SchedulingJobConfig` |

The factory method takes `SchedulingTelemetryFactory`, your component **directly** (not
`ValueOf`), an optional `@Tag(SchedulingModule.class) ZoneId` for cron jobs, the generated
config for `config` jobs and — for `@ScheduleQuartzWithTrigger` — the tagged `org.quartz.Trigger`.
A config-declared cron job whose `enabled` is `false` is built with an empty trigger list.

`KoraQuartzJobRegistrar` then registers each job as a durable Quartz `JobDetail` with the key
**`kora.<generated job class canonical name>`** (group `KoraQuartzJobRegistrar.JOB_GROUP` =
`kora`), and reconciles triggers: triggers already stored for that job are compared and replaced
only when they differ, and stored triggers the job no longer declares are unscheduled. This also
runs on `graphRefreshed()`. Two triggers compare equal when they have the same class and end time
and — cron — the same expression and time zone, or — simple — the same repeat count and
interval; the start time is compared only with `scheduling.quartz.compareStartTime = true`. Other
trigger types are compared on class and end time only.

Consequences worth knowing:

- A persisted trigger survives a restart untouched unless its schedule, end time or time zone
  changed, so Quartz's misfire handling applies to firings missed while the service was down.
- Trigger edits made directly in a persistent job store for a schedule Kora also declares are
  reverted at the next startup or graph refresh when they differ from the compiled/config state.
- A job of a known class still sitting in the `DEFAULT` group (Kora 1.x or RC1) is deleted there
  with its triggers and re-registered under `kora`: `Quartz Job '…' moved from the DEFAULT group
  to the kora group`.
- A job with no triggers stays registered and logs `Quartz Job '…' has no triggers and is not
  scheduled` at INFO.
- `KoraQuartzJobFactory` maps job classes to graph instances and falls back to Quartz's
  `PropertySettingJobFactory` for unknown classes. Generated job classes have only a three-arg
  constructor, so a node cannot instantiate a job class it does not itself carry — in a cluster
  every node must run the same build.
- Two `KoraQuartzJob` components of the same class fail fast at factory construction:
  *"Duplicate Quartz job class registered: …"*.

---

## The `JobExecutionContext` argument

A scheduled method may declare a single `org.quartz.JobExecutionContext` parameter. The
generator emits `object::method` (Java) / `{ ctx -> target.method(ctx) }` (Kotlin) instead of the
no-arg form.

```java
@Component
public final class StatefulJob {

    @PersistJobDataAfterExecution
    @DisallowConcurrentExecution
    @ScheduleQuartzWithCron("0 */10 * * * ?")
    void process(JobExecutionContext ctx) {
        var data = ctx.getJobDetail().getJobDataMap();
        int cursor = data.getInt("cursor");
        // ... work ...
        data.put("cursor", cursor + processed);   // re-stored thanks to @PersistJobDataAfterExecution
    }
}
```

Useful accessors: `ctx.getFireTime()`, `ctx.getScheduledFireTime()`,
`ctx.getPreviousFireTime()`, `ctx.getNextFireTime()`, `ctx.getRefireCount()`,
`ctx.getTrigger()`, `ctx.getMergedJobDataMap()`.

---

## Contract rules

- Return `void` / `Unit`. The generated wrapper is a `Consumer<JobExecutionContext>`; any return
  value is silently discarded.
- Zero arguments, or exactly one `JobExecutionContext`.
- No `suspend`. KSP rejects it before generation:

  ```
  Suspend methods are not supported by the scheduling generator.
  … For structured concurrency, enable Java preview features with --enable-preview
  and use StructuredTaskScope …
  Fix: remove suspend from the function.
  ```

- No `Mono`, `Flux` or `CompletionStage` — they are not Kora 2.0 contracts anywhere.
- No `Context`: the type was removed from the framework. Fire-time data comes from
  `JobExecutionContext`; correlation data from the Kora `MDC` that `KoraQuartzJob` installs.
- Only member functions. KSP rejects a top-level or local function with *"`@ScheduleQuartzWithTrigger`
  can be applied only to member functions."* (the annotation's simple name is substituted).
- The enclosing class must be a graph component; the generated factory takes it as a direct
  dependency.
- The class does **not** need to be non-`final` / `open`. The generated job calls the method on a
  held reference rather than subclassing it — the migrated Java example is
  `public final class TriggerScheduler`, and Kora's own KSP tests compile a plain Kotlin `class`.
  `open` becomes necessary only when a method-wrapping aspect (`@Log`, `@Retryable`, `@Timeout`,
  `@Cacheable`) is stacked on the same class.

---

## Thread model

`KoraQuartzScheduler.init()` builds a plain `StdSchedulerFactory` from the merged properties. No
executor is injected, so job execution uses whatever `org.quartz.threadPool.class` resolves to —
by default `org.quartz.simpl.SimpleThreadPool` with `threadCount = 10` and `threadPriority = 5`.

- Those are **platform** threads, named `kora-quartz-scheduler_Worker-N`, and non-daemon
  (`makeThreadsDaemons` defaults to `false`).
- Kora 2.0 running synchronous contracts on virtual threads does not apply here — a Quartz job
  body runs on a Quartz worker.
- `threadCount` caps concurrent executions across every Quartz job in the application. Fewer
  threads than simultaneously-due jobs means delayed firings and misfires.

`KoraQuartzJob.execute` is `final`. It records the executing thread (so `interrupt()` can reach
it on shutdown) and binds, per execution: a fresh Kora `io.koraframework.logging.common.MDC`, a
root OpenTelemetry context, and the scheduling `Observation` — so `@Log`-style MDC keys, tracing
and the scheduling telemetry all work inside the body despite the foreign thread.

---

## Error propagation

```java
// KoraQuartzJob.execute, simplified
observation.observeRun();
try {
    this.job.accept(jobExecutionContext);
} catch (Throwable e) {
    observation.observeError(e);
    throw e;                      // rethrown into Quartz
} finally {
    observation.end();
}
```

The exception reaches Quartz, which applies the trigger's misfire/refire policy and logs it
through its own SLF4J logger. Kora additionally logs it at WARN — *"Scheduled Job execution
failed with error"* with `exceptionType` and `exceptionMessage` — when
`scheduling.telemetry.logging.enabled = true` (it is `false` by default).

Catch inside the method when the failure should not surface as a Quartz job failure:

```java
@ScheduleQuartzWithCron("0 0 * * * ?")
void hourly() {
    try {
        doWork();
    } catch (Exception e) {
        log.error("Hourly job failed", e);
    }
}
```

Startup failures are reported by `KoraQuartzJobRegistrar` as
*"Quartz job '<class>' failed to start: …; check job triggers and Quartz scheduler
configuration"*.

---

## Cron expression reference

Quartz's own parser (`org.quartz.CronExpression`, built by `QuartzCronUtils.cronSchedule`),
documented on `@ScheduleQuartzWithCron`:

```
┌───────────── second (0-59)
│ ┌───────────── minute (0-59)
│ │ ┌───────────── hour (0-23)
│ │ │ ┌───────────── day of month (1-31, L, W or ?)
│ │ │ │ ┌───────────── month (1-12 or JAN-DEC)
│ │ │ │ │ ┌───────────── day of week (1-7 or SUN-SAT, 1 is Sunday, L, # or ?)
│ │ │ │ │ │ ┌───────────── year (optional)
│ │ │ │ │ │ │
* * * ? * * *
```

Six or seven fields. Day-of-month and day-of-week are mutually exclusive — exactly one of the two
must be `?`.

> The JDK scheduler's `@ScheduleJdkWithCron` uses Kora's own `CronExpression` and accepts
> **five**, six or seven fields; the DB scheduler's `@ScheduleDbWithCron` takes exactly six with
> `1` = Monday. A 5-field expression that works on the JDK scheduler is rejected by Quartz.

### Validation

| Where the cron comes from | When it is checked | Error |
|---|---|---|
| annotation `value` | compile time (Java processor and KSP) | `Invalid CRON expression '<expr>' in @ScheduleQuartzWithCron on '<Class>#<method>()': <reason>.` + field layout + examples + *"See the Javadoc of @ScheduleQuartzWithCron for details."* |
| config node (`cron`) | graph init, `QuartzCronUtils.cronSchedule` | `IllegalArgumentException: Invalid CRON expression '<expr>' for Quartz job '<Class>#<method>': <Quartz message>` + the same layout |

The compile-time check is deliberately incomplete: it reports only errors Quartz would also
reject (field count, ranges, reversed ranges, steps, `?` placement — e.g. *"'?' must be used in
exactly one of the day-of-month and day-of-week fields"* for `0 0 12 * * *`) and lets everything
it does not model through to Quartz at startup.

### Time zone

There is no time-zone attribute on the annotation. `QuartzCronUtils` sets the expression's zone
from an optional `@Tag(io.koraframework.scheduling.common.SchedulingModule.class) ZoneId`
component; without one the JVM default zone is used. The component applies to every cron job of
every Kora scheduler in the application. Changing it reschedules persisted cron triggers at the
next start (the zone is part of the trigger comparison).

### Special characters

| Char | Meaning | Example |
|------|---------|---------|
| `*` | all values | `*` in minute = every minute |
| `?` | no specific value | `0 0 10 ? * MON` |
| `-` | range | `MON-FRI` |
| `,` | list | `MON,WED,FRI` |
| `/` | step | `*/10` = every 10 |
| `L` | last | `L` in day-of-month = last day |
| `W` | nearest weekday | `1W` = first weekday of the month |
| `#` | nth weekday | `6#2` = second Friday (day-of-week is 1-7 = SUN-SAT, so 6 = FRI) |

### Common expressions

| Expression | Description |
|------------|-------------|
| `* * * ? * * *` | every second |
| `0 * * * * ?` | every minute |
| `0 */10 * * * ?` | every 10 minutes |
| `0 0 * * * ?` | every hour at :00 |
| `0 0 8-17 * * ?` | hourly from 08:00 to 17:00 |
| `0 0 9 ? * MON-FRI` | 09:00 on weekdays |
| `0 0 0 * * ?` | midnight daily |
| `0 0 0 L * ?` | last day of the month at midnight |
| `0 0 0 1W * ?` | first weekday of the month at midnight |
| `0 0 0 ? * 6#2` | second Friday of the month at midnight |
| `0 0 0 25 12 ?` | every 25 December at midnight |

---

## Scheduled method on a `@Conditional` component

The generated job factory takes the component directly and carries no condition. When the
component's `@Conditional` fails, the job node still asks for it and **graph initialisation
fails** with `IllegalStateException: Graph node value was not initialized because condition
failed: <reason>`. Fixed in `2.0.0.RC2` (kora-projects/kora PR #962): the generated job component
carries the `@Conditional` of its class and drops out with it. Only `2.0.0.RC1` is affected.

On RC1, keep the scheduled method on an unconditional component. If it has to reach the
conditional one, inject `All<T>` (condition-failed members are skipped) and return when it is
empty; on RC1 a `@Nullable T` dependency hits a separate bug, kora-projects/kora PR #960.

---

## Migrating from RC1 / earlier 2.0 snapshots

| RC1 / earlier snapshot | Now |
|---|---|
| `io.koraframework.scheduling.quartz.ScheduleWithCron` | `io.koraframework.scheduling.quartz.annotation.ScheduleQuartzWithCron` |
| `io.koraframework.scheduling.quartz.ScheduleWithTrigger` | `io.koraframework.scheduling.quartz.annotation.ScheduleQuartzWithTrigger` |
| `io.koraframework.scheduling.quartz.DisallowConcurrentExecution` | `io.koraframework.scheduling.quartz.annotation.DisallowConcurrentExecution` |
| `io.koraframework.scheduling.quartz.PersistJobDataAfterExecution` | `io.koraframework.scheduling.quartz.annotation.PersistJobDataAfterExecution` |
| `SchedulingQuartzConfig.waitForJobComplete()` | `QuartzConfig.shutdownWait()` — see [graceful-shutdown-reference.md](graceful-shutdown-reference.md) |
| job key `DEFAULT.<job class>` | `kora.<job class>`, moved automatically |
| every persisted trigger rescheduled at start (new start time) | rescheduled only on a real schedule/end-time/zone change; `compareStartTime` |
| cron always in the JVM default zone | `@Tag(SchedulingModule.class) ZoneId` |
| cron errors at graph init only | literal checked at compile time |
| no per-job switch | `<config path>.enabled = false` |

---

## Migrating from Kora 1.x

| 1.x | 2.0 |
|---|---|
| `ru.tinkoff.kora.scheduling.quartz.*` | `io.koraframework.scheduling.quartz.annotation.*` (annotations), `io.koraframework.scheduling.quartz.*` (module, runtime) |
| `ru.tinkoff.kora:scheduling-quartz` | `io.koraframework:scheduling-quartz` |
| `ru.tinkoff.kora:kora-parent` BOM | `io.koraframework:kora-bom` |
| `@ScheduleWithCron(...)` | **`@ScheduleQuartzWithCron(...)`** |
| `@ScheduleWithTrigger(@Tag(MyJob.class))` | **`@ScheduleQuartzWithTrigger(MyJob.class)`** |
| `@ScheduleWithTrigger(Tag(MyJob::class))` | **`@ScheduleQuartzWithTrigger(MyJob::class)`** |
| root `quartz { "org.quartz.*" }` | `scheduling.quartz.properties { "org.quartz.*" }` |
| `scheduling.waitForJobComplete` | `scheduling.quartz.shutdownWait` (duration, default `30s`) |
| jobs in the Quartz `DEFAULT` group | group `kora`; moved automatically at start |
| `ru.tinkoff.kora.common.Component` / `Tag` | `io.koraframework.common.annotation.Component` / `Tag` |
| `Thread.currentThread().isInterrupted()` shutdown checks | work — the job is interrupted once `shutdownWait` elapses, see [graceful-shutdown-reference.md](graceful-shutdown-reference.md) |
| `suspend fun` scheduled method | rejected by KSP; make it a plain function |

The nested-`@Tag` form is a hard compile error in 2.0 —
`error: annotation not valid for an element of type Class<?>` — because the attribute type is
`Class<?>`. The config renames are **silent**: unknown HOCON keys are ignored without a warning.

---

## See also

- [scheduling-config-reference.md](scheduling-config-reference.md) — config keys, telemetry, JDBC JobStore, clustering
- [graceful-shutdown-reference.md](graceful-shutdown-reference.md) — shutdown semantics
- [kora-aop-scheduling-jdk](../../kora-aop-scheduling-jdk/SKILL.md) — the JDK scheduler
- [kora-aop-scheduling-db](../../kora-aop-scheduling-db/SKILL.md) — cluster-wide jobs on db-scheduler, without Quartz
- [Quartz cron trigger tutorial](https://www.quartz-scheduler.org/documentation/quartz-2.3.0/tutorials/crontrigger.html) — upstream cron grammar
