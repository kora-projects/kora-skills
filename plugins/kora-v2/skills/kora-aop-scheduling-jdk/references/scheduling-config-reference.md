# JDK Scheduling Configuration Reference

Every configuration key read by `io.koraframework:scheduling-jdk` and the `scheduling-common` it
depends on. Defaults are the ones declared in the framework's own config interfaces.

For Quartz configuration (`scheduling.quartz.*`) see the sibling skill
[kora-aop-scheduling-quartz](../../kora-aop-scheduling-quartz/SKILL.md).

## Contents

- [Key map](#key-map)
- [Module setup](#module-setup)
- [Global configuration](#global-configuration) — HOCON and YAML
- [Per-job configuration](#per-job-configuration)
- [Per-job telemetry overrides](#per-job-telemetry-overrides)
- [Switching a job off](#switching-a-job-off)
- [Cron time zone](#cron-time-zone)
- [Keys that no longer exist](#keys-that-no-longer-exist)

---

## Key map

Three unrelated places carry scheduling configuration. Mixing them up is the single most common
scheduling config bug.

| Path | Read by | Contains |
|---|---|---|
| `scheduling.jdk` | `SchedulingJdkModule` | `shutdownWait`, `executionParallelism` |
| `scheduling.telemetry` | `SchedulingModule` (shared with Quartz and DB) | `logging` / `metrics` / `tracing` defaults for **all** jobs |
| whatever you write in `config = "…"` | the generated per-job config | that job's timing, its `enabled` switch and its own `telemetry` overrides |

The third path is arbitrary. It is **not** required to sit under `scheduling`; the official examples
use `scheduling.jobs.<name>`, which is safe because `jobs` collides with neither `jdk` nor `telemetry`.

---

## Module setup

```java
@KoraApp
public interface Application extends
    HoconConfigModule,      // or YamlConfigModule
    LogbackModule,
    SchedulingJdkModule {
}
```

```groovy
dependencies {
    koraBom platform("io.koraframework:kora-bom:$koraVersion")   // koraVersion=2.0.0.RC2
    annotationProcessor "io.koraframework:annotation-processors" // Kotlin: ksp("io.koraframework:symbol-processors")

    implementation "io.koraframework:scheduling-jdk"
    implementation "io.koraframework:config-hocon"               // or config-yaml
}
```

---

## Global configuration

### HOCON (`application.conf`)

```hocon
scheduling {

  jdk {
    shutdownWait = 30s           # graceful drain budget for running jobs; default 30s
    executionParallelism = 50    # cap on runs executing at once; default Integer.MAX_VALUE (unlimited)
  }

  telemetry {
    logging {
      enabled = false            # default false
    }
    metrics {
      enabled = false            # default false
      slo = ["1ms", "10ms", "50ms", "100ms", "200ms", "500ms", "1s", "2s", "5s", "10s", "20s", "30s", "60s", "90s"]
      tags {                     # extra tags on scheduling.job.duration
        env = "prod"
      }
    }
    tracing {
      enabled = true             # default true
      attributes {               # extra span attributes
        service = "my-service"
      }
    }
  }
}
```

### YAML (`application.yaml`)

```yaml
scheduling:
  jdk:
    shutdownWait: "30s"
    executionParallelism: 50
  telemetry:
    logging:
      enabled: false
    metrics:
      enabled: false
      slo: ["1ms", "10ms", "50ms", "100ms", "200ms", "500ms", "1s", "2s", "5s", "10s", "20s", "30s", "60s", "90s"]
      tags:
        env: "prod"
    tracing:
      enabled: true
      attributes:
        service: "my-service"
```

### Reference table

| Key | Type | Default | Notes |
|---|---|---|---|
| `scheduling.jdk.shutdownWait` | duration | `30s` | How long the executor lets running jobs finish at shutdown; after that it calls `shutdownNow()`, which interrupts them — see [graceful-shutdown-reference.md](graceful-shutdown-reference.md) |
| `scheduling.jdk.executionParallelism` | int | `Integer.MAX_VALUE` (unlimited) | Cap on job runs executing at once across all jobs; values below 1 act as 1; excess runs queue FIFO. Called `maxConcurrentExecutions` in post-RC1 snapshots |
| `scheduling.telemetry.logging.enabled` | boolean | `false` | Start/end job logs |
| `scheduling.telemetry.metrics.enabled` | boolean | `false` | `scheduling.job.duration` timer; also needs a `MeterRegistry` component |
| `scheduling.telemetry.metrics.slo` | duration list | 14 buckets, 1 ms → 90 s | Timer service-level objectives |
| `scheduling.telemetry.metrics.tags` | map | `{}` | Extra static tags |
| `scheduling.telemetry.tracing.enabled` | boolean | `true` | No-op unless a `Tracer` component exists |
| `scheduling.telemetry.tracing.attributes` | map | `{}` | Extra static span attributes |

**There is no thread-pool key.** Every run gets a fresh virtual thread and one platform timer thread
drives the schedule; the job count does not size anything. See the *Thread model* section of the
[skill](../SKILL.md#thread-model).

---

## Per-job configuration

`config = "<path>"` moves a job's timing into configuration. Annotation attributes become **defaults**
of the generated config interface; the config file wins. An attribute you leave off the annotation
becomes a **required** key.

```java
@ScheduleJdkAtFixedRate(config = "scheduling.jobs.heartbeat")                    // period is required in config
void heartbeat() { }

@ScheduleJdkWithFixedDelay(delay = 60, unit = ChronoUnit.SECONDS,
                           config = "scheduling.jobs.cleanup")                   // 60s unless config overrides
void cleanup() { }

@ScheduleJdkOnce(config = "scheduling.jobs.warmup")                              // delay is required in config
void warmup() { }

@ScheduleJdkWithCron(config = "scheduling.jobs.compaction")                      // cron is required in config
void compaction() { }
```

**HOCON:**

```hocon
scheduling.jobs {

  heartbeat {
    initialDelay = 10s
    period = 30s
  }

  cleanup {
    initialDelay = 30s
    delay = 5m
  }

  warmup {
    delay = 5m
  }

  compaction {
    cron = "0 0 3 * * ?"
  }
}
```

**YAML:**

```yaml
scheduling:
  jobs:
    heartbeat:
      initialDelay: "10s"
      period: "30s"
    cleanup:
      initialDelay: "30s"
      delay: "5m"
    warmup:
      delay: "5m"
    compaction:
      cron: "0 0 3 * * ?"
```

### Keys accepted per annotation

| Annotation | Keys | Required when the annotation omits the value |
|---|---|---|
| `@ScheduleJdkAtFixedRate` | `initialDelay`, `period`, `enabled` | `period` |
| `@ScheduleJdkWithFixedDelay` | `initialDelay`, `delay`, `enabled` | `delay` |
| `@ScheduleJdkOnce` | `delay`, `enabled` | `delay` |
| `@ScheduleJdkWithCron` | `cron`, `enabled` — or a bare string at the path | `cron` |

`initialDelay` always has a default (the annotation value, `0` if unset), so it is never required;
`enabled` defaults to `true`. `unit` is an annotation-only concept — in config, write real durations.

Duration values accept a HOCON-style string (`30s`, `5m`, `250ms`), an ISO-8601 string (`PT30S`), or a
bare number — **a bare number is milliseconds**, so `period = 30` is 30 ms, not 30 seconds.

A cron path may also be a bare string instead of an object:

```hocon
scheduling.jobs.compaction = "0 0 3 * * ?"
```

Both forms are handled; use the object form when you also want `enabled` or per-job telemetry. When the
annotation has a `value` too, it applies only if the path is absent altogether.

---

## Per-job telemetry overrides

Every per-job config path additionally accepts `telemetry`, with the same shape as the global block.
Unset keys fall through to `scheduling.telemetry`, which in turn falls through to the framework
defaults — this is a two-level merge, not a replacement.

```hocon
scheduling {
  telemetry.metrics.enabled = true          # on for every job

  jobs.compaction {
    cron = "0 0 3 * * ?"
    telemetry {
      logging.enabled = true                # …and log this one job
      metrics {
        slo = ["1s", "10s", "60s", "300s"]  # a nightly job needs coarser buckets
        tags { criticality = "high" }
      }
      tracing.attributes { job.owner = "platform" }
    }
  }
}
```

| Key under `<job-path>.telemetry` | Type | Falls back to |
|---|---|---|
| `logging.enabled` | boolean | `scheduling.telemetry.logging.enabled` |
| `metrics.enabled` | boolean | `scheduling.telemetry.metrics.enabled` |
| `metrics.slo` | duration list | `scheduling.telemetry.metrics.slo` |
| `metrics.tags` | map | `scheduling.telemetry.metrics.tags` |
| `tracing.enabled` | boolean | `scheduling.telemetry.tracing.enabled` |
| `tracing.attributes` | map | `scheduling.telemetry.tracing.attributes` |

Jobs **without** a `config` path cannot be tuned individually — they only see the global block, and
they cannot be switched off. That is a good reason to give production jobs a `config` path even when the
timings are static.

Jobs with a `config` path also get a `system.config` metric tag / span attribute carrying that path,
which lets dashboards address a job without hard-coding class names. Without a config path the tag is
absent — see *The `system.config` tag* in
[jdk-scheduling-reference.md](jdk-scheduling-reference.md#the-systemconfig-tag).

---

## Switching a job off

Every job declared with `config` reads `enabled` (default `true`) from `SchedulingJobConfig`. A
disabled job is never scheduled and logs at INFO on startup:

```
JDK Job 'com.example.Jobs#heartbeat' is disabled by configuration and won't be scheduled
```

```hocon
scheduling.jobs {
  heartbeat.enabled = false
  heartbeat.enabled = ${?HEARTBEAT_ENABLED}           # override from the environment
  compaction { cron = "0 0 3 * * ?", enabled = false } # a cron job needs the object form
}
```

A job without `config` has no such key — it is always enabled.

---

## Cron time zone

Not a config key: the zone is a graph component. Declare an optional `java.time.ZoneId` tagged
`@Tag(io.koraframework.scheduling.common.SchedulingModule.class)` and every cron job of every scheduler
(JDK, Quartz, DB) is evaluated in it; without it, the JVM default zone applies. To drive it from config,
read your own key in the factory:

```java
@Tag(SchedulingModule.class)
default ZoneId schedulingZone(Config config) {
    return ZoneId.of(config.get("app.timezone").asString());
}
```

---

## Keys that no longer exist

Unknown HOCON/YAML keys are **ignored without a warning**. A stale 1.x key therefore produces no error
at all — the setting simply stops applying.

| Stale 1.x key | Status in 2.0 |
|---|---|
| `scheduling.threads` | **Removed.** Runs are virtual threads; the optional cap is `scheduling.jdk.executionParallelism` |
| `scheduling.shutdownWait` | **Moved** to `scheduling.jdk.shutdownWait` |

| Stale 2.0 snapshot key | Status in `2.0.0.RC2` |
|---|---|
| `scheduling.jdk.maxConcurrentExecutions` | **Renamed** to `scheduling.jdk.executionParallelism` by Kora PR #952. The old key is ignored, so the cap silently disappears and runs are unlimited |

If you are porting a 1.x or snapshot `application.conf`, grep for all three and fix them explicitly —
nothing else will tell you.

---

## See Also

- [jdk-scheduling-reference.md](jdk-scheduling-reference.md) — annotations, generated code, telemetry details
- [graceful-shutdown-reference.md](graceful-shutdown-reference.md) — what `shutdownWait` actually bounds
- [kora-config-hocon](../../kora-config-hocon/SKILL.md) / [kora-config-yaml](../../kora-config-yaml/SKILL.md) — config sources and env substitution
