# Shutdown Reference (Quartz, Kora 2.0)

What happens to a running Quartz job when a Kora 2.0 service stops, and how to write a long job
that stops cleanly.

**Shutdown is not shared code between the Kora schedulers.** `scheduling-common` contains only
`SchedulingJobConfig`, `SchedulingModule` and the `telemetry/` package — no `Lifecycle`, no
shutdown code. Each backend owns its own teardown. Everything on this page is Quartz-only; for the
JDK scheduler see [kora-aop-scheduling-jdk](../../kora-aop-scheduling-jdk/SKILL.md), for
db-scheduler [kora-aop-scheduling-db](../../kora-aop-scheduling-db/SKILL.md).

## Contents

- [What shutdown does](#what-shutdown-does)
- [How the other schedulers compare](#how-the-other-schedulers-compare)
- [Configuration](#configuration)
- [Reacting to the interrupt](#reacting-to-the-interrupt)
- [Bounding a long job](#bounding-a-long-job)
- [Release order](#release-order)
- [Resumable jobs](#resumable-jobs)
- [Operational control through the Scheduler](#operational-control-through-the-scheduler)
- [Troubleshooting](#troubleshooting)
- [See also](#see-also)

---

## What shutdown does

`KoraQuartzScheduler` is a `Lifecycle`, so the graph calls `release()` on it during shutdown:

```java
// KoraQuartzScheduler.release(), simplified
scheduler.standby();                                   // no new firings
var running = awaitRunningJobs(scheduler, shutdownWait);
if (!running.isEmpty()) {
    log.warn("KoraQuartzScheduler interrupting jobs {} still running after {}", keys, shutdownWait);
    running.forEach(ctx -> ((InterruptableJob) ctx.getJobInstance()).interrupt());
    running = awaitRunningJobs(scheduler, shutdownWait);
    if (!running.isEmpty()) {
        log.warn("KoraQuartzScheduler stopped while jobs {} are still running after interruption", keys);
    }
}
scheduler.shutdown(false);
```

- `shutdownWait` is `scheduling.quartz.shutdownWait`, default **30 s**.
- Every generated job extends `KoraQuartzJob`, which implements `org.quartz.InterruptableJob`.
  It tracks the threads currently executing it, and `interrupt()` interrupts every one of them.
- The worst case is therefore about **2 × `shutdownWait`**: one wait before the interrupt, one
  after it.
- `scheduler.shutdown(false)` does not wait any further. A job that ignored the interrupt keeps
  running on its Quartz worker — a non-daemon platform thread — while the rest of the graph is
  released.

Kora's own tests pin both paths: a job that sleeps for a minute is interrupted and `release()`
returns within seconds when `shutdownWait` is 200 ms; a job that finishes in 500 ms with a 30 s
budget completes without being interrupted.

---

## How the other schedulers compare

| | Quartz (`scheduling-quartz`) | JDK (`scheduling-jdk`) | DB (`scheduling-db-scheduler`) |
|---|---|---|---|
| Component | `KoraQuartzScheduler.release()` | `VirtualThreadSchedulingJdkExecutor.release()` | `KoraDbScheduler.release()` → db-scheduler `Scheduler.stop()` |
| Threads | Quartz `SimpleThreadPool` platform workers | one platform timer thread + a virtual thread per run | virtual threads |
| Config key | `scheduling.quartz.shutdownWait` | `scheduling.jdk.shutdownWait` | `scheduling.dbScheduler.shutdownWait` |
| Default | `30s` | `30s` | `30s` |
| Running job interrupted | **yes**, after `shutdownWait`, through `InterruptableJob` | **yes**, after `shutdownWait` (`shutdownNow()`) | **yes**, after `shutdownWait` |
| Waits after the interrupt | up to `shutdownWait` again | no | up to `shutdownWait` again |

So `Thread.currentThread().isInterrupted()` / `InterruptedException` is a real shutdown signal on
all three schedulers.

---

## Configuration

```hocon
scheduling.quartz.shutdownWait = 30s    # default
```

```yaml
scheduling:
  quartz:
    shutdownWait: 30s
```

| Value | Behaviour |
|---|---|
| `30s` (default) | running jobs get 30 s, are then interrupted, and get another 30 s |
| `0s` | running jobs are interrupted immediately; `release()` still waits up to 0 s afterwards |
| a large value such as `365d` | waits for running jobs to complete regardless of time |

With a large value, make sure the platform's own grace period — Kubernetes
`terminationGracePeriodSeconds`, a systemd `TimeoutStopSec` — is not shorter, or the process is
killed mid-job anyway.

**`waitForJobComplete` is gone.** Neither `scheduling.waitForJobComplete` (Kora 1.x) nor
`scheduling.quartz.waitForJobComplete` (RC1 / earlier 2.0 snapshots) is read; an unknown HOCON
key is ignored silently and the 30 s default applies.

---

## Reacting to the interrupt

The interrupt reaches the job's own thread, so the usual Java rules apply:

- a blocking call that honours interrupts (`Thread.sleep`, `BlockingQueue.take`,
  `Future.get`, `Object.wait`, interruptible channels) throws `InterruptedException`;
- a CPU-bound loop must poll `Thread.currentThread().isInterrupted()`;
- a blocking call that does not react to interrupts keeps going — give it its own timeout.

```java
@Component
public final class BatchJob {

    @DisallowConcurrentExecution
    @ScheduleQuartzWithCron("0 */5 * * * ?")
    void processBatch() {
        for (var item : repository.findPending(500)) {
            if (Thread.currentThread().isInterrupted()) {
                log.info("Shutdown requested, stopping; the rest is picked up on the next fire");
                return;
            }
            process(item);
        }
    }
}
```

```kotlin
@Component
class BatchJob(private val repository: PendingRepository) {

    @DisallowConcurrentExecution
    @ScheduleQuartzWithCron("0 */5 * * * ?")
    fun processBatch() {
        for (item in repository.findPending(500)) {
            if (Thread.currentThread().isInterrupted) {
                log.info("Shutdown requested, stopping; the rest is picked up on the next fire")
                return
            }
            process(item)
        }
    }
}
```

If you catch `InterruptedException` and cannot stop right away, restore the flag with
`Thread.currentThread().interrupt()` so the outer loop still sees it. Do not swallow it.

---

## Bounding a long job

The interrupt is the last resort. A job that has a known upper bound per execution — a deadline
or a batch cap — finishes inside `shutdownWait` and is never interrupted:

```java
@Component
public final class BatchJob {

    private static final Duration BUDGET = Duration.ofSeconds(20);

    @DisallowConcurrentExecution
    @ScheduleQuartzWithCron("0 */5 * * * ?")
    void processBatch() {
        var deadline = Instant.now().plus(BUDGET);
        for (var item : repository.findPending(500)) {
            if (Instant.now().isAfter(deadline) || Thread.currentThread().isInterrupted()) {
                log.info("Stopping early, resuming on the next fire");
                return;
            }
            process(item);
        }
    }
}
```

Keep the budget below `shutdownWait`. `@DisallowConcurrentExecution` keeps the next firing from
overlapping while the previous one is still draining the backlog.

---

## Release order

`KoraQuartzScheduler` depends on `KoraQuartzJobFactory`, which depends on every generated job,
which depends on your component. The graph releases in reverse initialisation order, so the
scheduler is released **before** the jobs and the components they use: while `release()` waits
and interrupts, the job's data sources and clients are still alive.

That also means a `Lifecycle` component the job depends on cannot serve as a "stopping" flag —
its `release()` runs only after the scheduler has finished waiting. The interrupt is the signal;
you do not need your own.

---

## Resumable jobs

Because a job can be cut short by its own budget, by the interrupt, or by the process dying
mid-run, make progress durable rather than in-memory:

```java
@Component
public final class ResumableJob {

    @PersistJobDataAfterExecution     // needs a JDBC JobStore to survive a restart
    @DisallowConcurrentExecution
    @ScheduleQuartzWithCron("0 */10 * * * ?")
    void process(JobExecutionContext ctx) {
        var data = ctx.getJobDetail().getJobDataMap();
        long cursor = data.getLong("cursor");

        var deadline = Instant.now().plusSeconds(20);
        for (var item : repository.findAfter(cursor, 500)) {
            if (Instant.now().isAfter(deadline) || Thread.currentThread().isInterrupted()) break;
            process(item);
            cursor = item.id();
        }
        data.put("cursor", cursor);
    }
}
```

`@PersistJobDataAfterExecution` only survives a restart with a persistent job store — with the
default `RAMJobStore` the map is in-memory. See
[scheduling-config-reference.md](scheduling-config-reference.md#persistence-jdbc-jobstore).
A cursor in your own database works regardless of job store and is usually the better choice.

---

## Operational control through the `Scheduler`

`KoraQuartzScheduler` is `Wrapped<org.quartz.Scheduler>`, so `org.quartz.Scheduler` is
injectable. That is the supported way to pause or fire jobs on demand:

```java
@Component
public final class SchedulerAdmin {

    private final Scheduler scheduler;

    SchedulerAdmin(Scheduler scheduler) {
        this.scheduler = scheduler;
    }

    public void drain() throws SchedulerException {
        scheduler.standby();          // stop firing, keep the scheduler alive
    }

    public void resume() throws SchedulerException {
        scheduler.start();
    }
}
```

`standby()` stops new firings without touching jobs already running — it is the first step of
Kora's own shutdown. `Scheduler.interrupt(JobKey)` now reaches Kora jobs too, because
`KoraQuartzJob` is an `InterruptableJob`.

---

## Troubleshooting

### Shutdown takes about a minute

**Cause:** a job outlived `shutdownWait` (30 s), was interrupted, ignored the interrupt and ran
through the second wait as well.
**Fix:** honour `isInterrupted()` / `InterruptedException`, put timeouts on blocking calls, and
bound the body below `shutdownWait`.

### `KoraQuartzScheduler interrupting jobs [...] still running after PT30S`

Expected when a run is longer than `shutdownWait`. Either bound the job or raise `shutdownWait`
(together with the platform grace period).

### `KoraQuartzScheduler stopped while jobs [...] are still running after interruption`

The job ignored the interrupt for another full `shutdownWait`. It is still running on a
non-daemon worker while the graph is released — expect errors from released dependencies. Make
the job interruptible.

### `waitForJobComplete` has no effect

The key no longer exists. Use `scheduling.quartz.shutdownWait`.

### A job restarted mid-batch reprocesses items

**Cause:** progress was only in memory, or in a `JobDataMap` backed by `RAMJobStore`.
**Fix:** persist the cursor in your own database, and make each unit idempotent.

---

## See also

- [quartz-scheduling-reference.md](quartz-scheduling-reference.md) — annotations and generated code
- [scheduling-config-reference.md](scheduling-config-reference.md) — `scheduling.quartz.*` keys
- [kora-di-runtime](../../kora-di-runtime/SKILL.md) — `Lifecycle`, `@Root` and graph release order
- [kora-aop-scheduling-db](../../kora-aop-scheduling-db/SKILL.md) — db-scheduler shutdown (`scheduling.dbScheduler.shutdownWait`, then interrupt)
