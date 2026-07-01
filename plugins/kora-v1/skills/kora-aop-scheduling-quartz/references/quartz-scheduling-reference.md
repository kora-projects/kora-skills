# Quartz Scheduling Reference

**Artifact:** `ru.tinkoff.kora:scheduling-quartz`
**Module:** `QuartzModule`
**Package:** `ru.tinkoff.kora.scheduling.quartz.*`

Quartz scheduling provides cron expressions, persistent job state, and custom trigger support.

## Contents

- [When to use Quartz](#when-to-use-quartz)
- [Annotations](#annotations)
- [Configuration](#configuration)
- [Cron expression reference](#cron-expression-reference)
- [Error handling](#error-handling)
- [See also](#see-also)

---

## When to Use Quartz

Use Quartz **only** when you need:
- Cron-based scheduling (`@ScheduleWithCron`)
- Custom trigger logic (`@ScheduleWithTrigger`)
- Persistent job state (survives restarts via JDBC JobStore)
- Cluster-wide scheduling (single execution across nodes)

**Default:** Use JDK scheduling for simple fixed intervals.

---

## Annotations

### `@ScheduleWithCron`

Cron-based scheduling using Quartz cron expressions.

**Parameters:**
- `value` — cron expression string
- `identity` — optional job identity name
- `config` — config path for externalized cron

**Use when:** Complex time-based schedules (daily reports, hourly checks).

```java
@Component
public class NightlyReport {

    @ScheduleWithCron("0 0 3 * * ?")  // Daily at 03:00
    void runReport() {
        // Executes daily at 3 AM
    }
}
```

**Config override:**
```java
@ScheduleWithCron(config = "jobs.nightly")
void run() { ... }
```
```hocon
jobs.nightly.cron = "0 0 3 * * ?"
```

---

### `@ScheduleWithTrigger`

Reference a custom `org.quartz.Trigger` component for complex scheduling logic.

**Parameters:**
- `@Tag` — references the `Trigger` component by tag (the same `@Tag` value used
  when declaring the `Trigger` on the `@KoraApp` interface). It is **not** a string name.

**Use when:** Programmatic trigger definition beyond cron (dynamic intervals, calendar-based).

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
public class RapidCheckJob {

    @ScheduleWithTrigger(@Tag(RapidCheckJob.class))
    void checkStatus() {
        // Executes per custom trigger every 5 seconds
    }
}
```

---

### `@DisallowConcurrentExecution`

Prevents parallel execution of the same job.

**Use when:** Job execution time may exceed scheduling interval.

```java
@Component
public class HourlyJob {

    @DisallowConcurrentExecution
    @ScheduleWithCron("0 0 * * * ?")  // Every hour
    void hourly() {
        // Never runs two instances simultaneously
    }
}
```

---

### `@PersistJobDataAfterExecution`

Forces Quartz to re-save `org.quartz.JobDataMap` after execution. **Recommended**
to use together with `@DisallowConcurrentExecution` to avoid lost-update conflicts
on the map during concurrent execution.

**Use when:** Job maintains state across executions (requires JDBC JobStore).

```java
@Component
public class StatefulJob {

    @PersistJobDataAfterExecution
    @DisallowConcurrentExecution
    @ScheduleWithCron("0 0 * * * ?")
    void process() {
        // State persisted after each run
    }
}
```

---

## Configuration

### Module Setup

```java
@KoraApp
public interface Application extends
    HoconConfigModule,
    LogbackModule,
    QuartzModule {
}
```

### Quartz Properties

```hocon
quartz {
  "org.quartz.scheduler.instanceName" = "MyScheduler"
  "org.quartz.threadPool.threadCount" = "10"
  "org.quartz.threadPool.threadPriority" = "5"
  "org.quartz.jobStore.misfireThreshold" = "60000"
  
  # For persistence (JDBC JobStore):
  # "org.quartz.jobStore.class" = "org.quartz.impl.jdbcjobstore.JobStoreTX"
  # "org.quartz.jobStore.driverDelegateClass" = "org.quartz.impl.jdbcjobstore.PostgreSQLDelegate"
  # "org.quartz.jobStore.dataSource" = "myDS"
}

scheduling {
  waitForJobComplete = true      # Block shutdown until jobs finish
  telemetry {
    logging.enabled = false
    metrics.enabled = true
    tracing.enabled = true
  }
}
```

```yaml
quartz:
  org.quartz.scheduler.instanceName: "MyScheduler"
  org.quartz.threadPool.threadCount: "10"
  org.quartz.threadPool.threadPriority: "5"
  org.quartz.jobStore.misfireThreshold: "60000"

scheduling:
  waitForJobComplete: true
  telemetry:
    logging:
      enabled: false
    metrics:
      enabled: true
    tracing:
      enabled: true
```

**Defaults:**
- `threadCount = 10`
- `jobStore.class = RAMJobStore` (in-memory)

---

## Cron Expression Reference

### Format

```
┌───────────── second (0-59)
│ ┌───────────── minute (0-59)
│ │ ┌───────────── hour (0-23)
│ │ │ ┌───────────── day of month (1-31)
│ │ │ │ ┌───────────── month (1-12 or JAN-DEC)
│ │ │ │ │ ┌───────────── day of week (1-7 or SUN-SAT)
│ │ │ │ │ │ ┌───────────── year (optional, 1970-2099)
│ │ │ │ │ │ │
* * * ? * * *
```

Day-of-month and day-of-week are mutually exclusive: when one is specified the
other must be `?`.

### Special Characters

| Char | Meaning | Example |
|------|---------|---------|
| `*` | All values | `*` in minute = every minute |
| `?` | No specific value | `0 0 10 ? * MON` |
| `-` | Range | `1-5` = Mon-Fri |
| `,` | List | `1,3,5` = Mon, Wed, Fri |
| `/` | Step | `*/10` = every 10 minutes |
| `L` | Last | `L` in day-of-month = last day |
| `W` | Weekday | `1W` = first weekday of month |
| `#` | Nth occurrence | `5#2` = second Friday of the month |

### Common Expressions

| Expression | Description |
|------------|-------------|
| `0 0 * * * ?` | Every hour at :00 |
| `0 */10 * * * ?` | Every 10 minutes |
| `0 0 8-17 * * ?` | Every hour 8 AM to 5 PM |
| `0 0 9 ? * MON-FRI` | 9 AM on weekdays |
| `0 0 0 * * ?` | Midnight daily |
| `0 0 0 L * ?` | Last day of month at midnight |
| `0 0 0 1W * ?` | First weekday of month at midnight |
| `0 0 0 ? * 5#2` | Second Friday of the month at midnight |
| `0 0 0 ? * MON#1` | First Monday of the month at midnight |

---

## Error Handling

**Quartz behavior:**
- Exception is logged via SLF4J
- With `@DisallowConcurrentExecution`: job may pause depending on config
- Misfire threshold controls late job handling

**Recommended pattern:**
```java
@DisallowConcurrentExecution
@ScheduleWithCron("0 0 * * * ?")
void process() {
    try {
        doWork();
    } catch (Exception e) {
        log.error("Scheduled job failed", e);
        // Don't rethrow - prevents Quartz pause
    }
}
```

---

## See Also

- [Official Kora Documentation](../../../.kora-agent/kora-docs/mkdocs/docs/en/documentation/scheduling.md#quartz) — Quartz scheduling
- [scheduling-config-reference.md](scheduling-config-reference.md) — Full configuration reference
- [graceful-shutdown-reference.md](graceful-shutdown-reference.md) — Interrupt handling
- [jdk-scheduling-reference.md](jdk-scheduling-reference.md) — JDK scheduling alternative
