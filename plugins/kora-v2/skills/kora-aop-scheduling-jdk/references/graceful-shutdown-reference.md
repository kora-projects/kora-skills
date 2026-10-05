# Graceful Shutdown Reference (JDK scheduler)

How `io.koraframework:scheduling-jdk` stops jobs, and what a job must do to be a good citizen during
shutdown.

For Quartz jobs see the sibling skill
[kora-aop-scheduling-quartz](../../kora-aop-scheduling-quartz/SKILL.md). Since Kora PR #952 Quartz has a
`scheduling.quartz.shutdownWait` of its own (default 30 s, replacing `waitForJobComplete`): it puts the
scheduler in standby, waits that long for running jobs, interrupts them through `InterruptableJob`, and
waits up to `shutdownWait` once more — so a Quartz shutdown can take up to twice the budget, where the
JDK executor below waits once and does not wait again after the interrupt.

## Contents

- [The shutdown path](#the-shutdown-path)
- [Handling the interrupt](#handling-the-interrupt)
- [What `shutdownWait` bounds](#what-shutdownwait-bounds)
- [Cooperative cancellation patterns](#cooperative-cancellation-patterns)
- [Resource cleanup](#resource-cleanup)
- [Choosing a work-unit size](#choosing-a-work-unit-size)
- [Complete example](#complete-example)
- [Troubleshooting](#troubleshooting)

---

## The shutdown path

Kora releases the graph in reverse dependency order: a node is released only after every node that
depends on it has been released. Each scheduled job depends on the `SchedulingJdkExecutor`, and the
executor depends on nothing but its config, so the order is fixed:

1. **The job releases first — and returns immediately.** `KoraJdkJob.release()` marks the job stopped
   and cancels its pending schedule with `cancel(false)`. It does not wait for an in-flight run and does not
   interrupt it; a run that is already executing keeps going, and no later run of that job starts.
2. **Then the executor releases** (`VirtualThreadSchedulingJdkExecutor.release()`):
   - stops accepting work and cancels every remaining periodic task;
   - shuts the timer thread down and waits for running job threads, both within one shared
     `scheduling.jdk.shutdownWait` budget (default 30 s);
   - if the budget expires: `shutdownNow()` — queued runs are dropped, **running job threads are
     interrupted**, outstanding futures are cancelled — and it logs
     `SchedulingJdkExecutor failed completing graceful shutdown in PT30S`;
   - it does not wait again after the interrupt; it logs `SchedulingJdkExecutor stopped in …` and
     returns.

```
SIGTERM
  └─ job.release()        → cancel(false) the next run; the current run keeps going
  └─ executor.release()   → stop accepting, cancel periodic tasks
                           → wait for running jobs, up to shutdownWait
                           → timeout: shutdownNow() → running jobs are interrupted
```

Two consequences:

- Shutdown latency caused by jobs is bounded by `shutdownWait`. A job that ignores the interrupt keeps
  running on a virtual thread, but it no longer holds up `release()`.
- Because the job's own `release()` returns at once, the components the job uses (repositories, a
  `JdbcDataSource`, HTTP clients) can be released while its last run is still draining in the
  executor. A run that is still busy late in shutdown may see closed resources — keep runs short.

---

## Handling the interrupt

The interrupt from `shutdownNow()` is the only signal a running job gets, and it only arrives once
`shutdownWait` has elapsed. Treat it as "stop now":

```java
@ScheduleJdkWithFixedDelay(config = "scheduling.jobs.import")
void importRecords() {
    for (var page : source.pages()) {
        if (Thread.currentThread().isInterrupted()) {
            return;                              // budget is gone, leave the rest for the next start
        }
        sink.upsert(page);
    }
}
```

Blocking calls that honour interrupts (`Thread.sleep`, `BlockingQueue.poll`, `Future.get`) throw `InterruptedException` or fail; restore the flag
(`Thread.currentThread().interrupt()`) and return. Do not swallow the interrupt and loop again.

Relying on the interrupt alone still wastes the whole budget, so prefer to be done **before** it
fires — that is what the patterns below are for.

---

## What `shutdownWait` bounds

```hocon
scheduling.jdk.shutdownWait = 30s   # default 30s
```

It is the executor's graceful drain budget: from the start of `release()`, how long running job runs
(and delayed one-shot tasks submitted directly to the executor) get to finish before `shutdownNow()`
interrupts them. Keep it comfortably below the container kill timeout so the interrupt path gets to
run: `terminationGracePeriodSeconds` in Kubernetes (default 30 s), `docker stop -t` (default 10 s).

A thread your job body started itself is **not** an executor worker: nothing waits for it and nothing
interrupts it. Own its lifecycle explicitly.

> The 1.x key `scheduling.shutdownWait` is not read. It is an unknown HOCON key: ignored silently, no
> warning, and the default 30 s applies.

---

## Cooperative cancellation patterns

The framework waits up to `shutdownWait` and then interrupts. The job decides whether it finishes
cleanly inside that window or is cut off.

### 1. Bound the batch — the default choice

Do a bounded slice of work per run instead of draining everything. The next run picks up where this one
left off, and shutdown never waits more than one slice.

```java
@Component
public final class OutboxPublisher {

    private static final int BATCH = 500;

    @ScheduleJdkWithFixedDelay(config = "scheduling.jobs.outbox")
    void publishPending() {
        var batch = outbox.takePending(BATCH);   // bounded by construction
        for (var message : batch) {
            broker.publish(message);
            outbox.markSent(message.id());
        }
    }
}
```

### 2. A deadline inside the run

When the batch size is not under your control, stop on the clock.

```java
@ScheduleJdkWithFixedDelay(config = "scheduling.jobs.import")
void importRecords() {
    var deadline = Instant.now().plus(Duration.ofSeconds(20));

    for (var record : source.stream()) {
        if (Instant.now().isAfter(deadline)) {
            log.info("import yielding at deadline, resuming next run");
            return;
        }
        importRecord(record);
    }
}
```

Keep the deadline below `scheduling.jdk.shutdownWait` and a run always finishes before the interrupt,
whatever the data looks like.

### 3. An owned stop flag, for a job that must poll

If the job genuinely has to loop, it can poll a flag that a `Lifecycle` component flips. Kora releases
the flag holder only after the jobs that depend on it.

```java
@Component
public final class ShutdownFlag implements Lifecycle {

    private volatile boolean stopping = false;

    public boolean stopping() { return stopping; }

    @Override public void init() { }
    @Override public void release() { stopping = true; }
}
```

The flag flips when `ShutdownFlag` is released, which happens **after** the jobs depending on it are
released — job release returns immediately, so this can be early in shutdown, but the ordering is not
guaranteed relative to the executor's wait. Use it for background threads a job spawned, not as the
primary mechanism. Prefer bounded batches, deadlines and the interrupt check.

### 4. Blocking calls

Every blocking call inside a job should carry a timeout, so shutdown latency is bounded even when the
peer is unresponsive:

```java
queue.poll(5, TimeUnit.SECONDS);        // not queue.take()
future.get(10, TimeUnit.SECONDS);       // not future.get()
httpClient.get(...)                     // with a per-request timeout configured
```

---

## Resource cleanup

Ordinary try-with-resources is enough: a run either finishes inside `shutdownWait` or is interrupted,
and in both cases `finally` executes on the way out.

```java
@ScheduleJdkAtFixedRate(config = "scheduling.jobs.report")
void buildReport() {
    try (var connection = dataSource.getConnection();
         var writer = Files.newBufferedWriter(target)) {
        writeReport(connection, writer);
    } catch (SQLException | IOException e) {
        log.error("report generation failed", e);
    }
}
```

Do **not** open a resource in one run and close it in the next — a one-shot `@ScheduleJdkOnce` or a
cancelled schedule may mean the next run never happens.

---

## Choosing a work-unit size

| Job duration | Recommended shape |
|---|---|
| < 1 s | Nothing to do — it returns before shutdown notices |
| 1–30 s | Fine as-is; make sure blocking calls have timeouts |
| > 30 s | Bounded batch or an in-run deadline; otherwise the run is interrupted once `shutdownWait` expires |
| Unbounded / streaming | Must not exist as a scheduled job. Bound it, or make it a `Lifecycle` component with its own thread and stop protocol |

Two numbers to stay under: `scheduling.jdk.shutdownWait` (after which the run is interrupted) and, above
it, the container kill timeout — `terminationGracePeriodSeconds` (Kubernetes, default 30 s) or
`docker stop -t` (default 10 s). Past the kill timeout it is not a graceful shutdown, it is a `SIGKILL`.

---

## Complete example

```java
package com.example.app.jobs;

import io.koraframework.common.annotation.Component;
import io.koraframework.scheduling.jdk.annotation.ScheduleJdkWithFixedDelay;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.time.Duration;
import java.time.Instant;

@Component
public final class DataImportJob {

    private static final Logger log = LoggerFactory.getLogger(DataImportJob.class);
    private static final Duration RUN_BUDGET = Duration.ofSeconds(20);
    private static final int PAGE = 200;

    private final ImportSource source;
    private final ImportSink sink;

    public DataImportJob(ImportSource source, ImportSink sink) {
        this.source = source;
        this.sink = sink;
    }

    @ScheduleJdkWithFixedDelay(config = "scheduling.jobs.import")
    void importExternalData() {
        var deadline = Instant.now().plus(RUN_BUDGET);
        var imported = 0;

        while (Instant.now().isBefore(deadline) && !Thread.currentThread().isInterrupted()) {
            var page = source.nextPage(PAGE);      // bounded, resumable
            if (page.isEmpty()) {
                break;
            }
            for (var record : page) {
                sink.upsert(record);               // idempotent
            }
            imported += page.size();
        }

        log.info("imported {} records, resuming next run", imported);
    }
}
```

```hocon
scheduling.jobs.import {
  initialDelay = 30s
  delay = 5m
  telemetry.logging.enabled = true
}
```

Three properties make this shutdown-safe: the run is time-bounded (20 s, inside the default 30 s
`shutdownWait`) and also stops on interrupt, each page is idempotent so a truncated run is not a lost
run, and progress is durable in the source cursor rather than in memory.

---

## Troubleshooting

### Shutdown takes `shutdownWait` every time

A run is still busy when release starts and uses the whole budget. Find it in a thread dump: the timer
thread is `kora-jdk-scheduler-timer`, job runs are virtual threads named `kora-jdk-scheduler-job-N`
(dump virtual threads with `jcmd <pid> Thread.dump_to_file`). Give the job a bounded batch or a
deadline below `shutdownWait`.

### `SchedulingJdkExecutor failed completing graceful shutdown in PT30S`

A run outlived `scheduling.jdk.shutdownWait` and was interrupted by `shutdownNow()`. Either bound the
run, or raise `scheduling.jdk.shutdownWait` if the work is legitimately that long — and keep it below
the container kill timeout.

### The job keeps running after that warning

It ignores the interrupt. Check `Thread.currentThread().isInterrupted()` in loops and do not swallow
`InterruptedException`. The executor does not wait after interrupting, so such a run only ends with
the JVM.

### A run is cut off mid-way and data is inconsistent

Shutdown is not the only way a run ends — an exception does too. Make each unit of work idempotent and
commit progress incrementally; do not treat "the run completed" as a transaction boundary.

### Setting `scheduling.shutdownWait` changed nothing

That is the 1.x key. Use `scheduling.jdk.shutdownWait`. Unknown keys are ignored silently.

---

## See Also

- [scheduling-config-reference.md](scheduling-config-reference.md) — every `scheduling.*` key
- [jdk-scheduling-reference.md](jdk-scheduling-reference.md) — annotations and telemetry
- [kora-di-runtime](../../kora-di-runtime/SKILL.md) — `Lifecycle`, init/release ordering, `@Root`
