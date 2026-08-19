# Graceful Shutdown Reference (Quartz)

Handling interrupt signals and graceful shutdown for `scheduling-quartz` jobs. For plain
JDK timer jobs see the sibling skill
[kora-aop-scheduling-jdk](../../kora-aop-scheduling-jdk/SKILL.md).

## Contents

- [Overview](#overview)
- [Configuration](#configuration)
- [Interrupt Handling with @DisallowConcurrentExecution](#interrupt-handling-with-disallowconcurrentexecution)
- [Stateful Jobs](#stateful-jobs)
- [When to Use waitForJobComplete](#when-to-use-waitforjobcomplete)
- [Troubleshooting](#troubleshooting)

---

## Overview

The Quartz scheduler invokes **interrupt** on running jobs at SIGTERM. Long-running jobs must
check interrupt status and exit gracefully to avoid resource leaks, incomplete transactions,
data corruption, and extended shutdown times.

---

## Configuration

```hocon
scheduling {
  waitForJobComplete = true  # Block shutdown until jobs finish
}
```

```yaml
scheduling:
  waitForJobComplete: true
```

**Behavior:**
1. SIGTERM received
2. Scheduler stops triggering new jobs
3. If `waitForJobComplete = true`: block until current job completes
4. Interrupt sent if job doesn't complete
5. Shutdown proceeds

---

## Interrupt Handling with @DisallowConcurrentExecution

```java
@Component
public class HourlyReport {

    @DisallowConcurrentExecution
    @ScheduleWithCron("0 0 * * * ?")
    void generateReport() {
        while (generating) {
            if (Thread.currentThread().isInterrupted()) {
                // Save partial progress if needed
                saveProgress(currentStep);
                log.info("Report generation interrupted");
                return;
            }
            generateNextSection();
        }
    }
}
```

---

## Stateful Jobs

```java
@Component
public class StatefulBatchJob {

    @PersistJobDataAfterExecution
    @DisallowConcurrentExecution
    @ScheduleWithCron("0 */10 * * * ?")
    void processBatch() {
        int processed = 0;

        for (Item item : items) {
            if (Thread.currentThread().isInterrupted()) {
                // State will be persisted due to annotation
                saveState(processed);
                return;
            }
            processItem(item);
            processed++;
        }
    }
}
```

---

## When to Use waitForJobComplete

| Scenario | Setting |
|----------|---------|
| Idempotent jobs | `false` (default) |
| Critical jobs (must complete) | `true` |
| Long batch processing | `true` + interrupt checks |
| Quick cleanup tasks | `false` |

**Interrupt-check frequency:** short tasks (< 1s) optional; medium (1-30s) every step;
long (> 30s) before each unit of work; infinite loops every iteration (required).

---

## Troubleshooting

### Job Doesn't Respond to Interrupt

**Problem:** Job continues running after SIGTERM.

**Solution:** Add interrupt checks in loops:
```java
// BAD: No interrupt check
for (Item item : items) {
    process(item);  // May run for minutes
}

// GOOD: Check interrupt
for (Item item : items) {
    if (Thread.currentThread().isInterrupted()) {
        return;
    }
    process(item);
}
```

### Shutdown Takes Too Long

**Problem:** Application hangs during shutdown.

**Solutions:**
1. Use `waitForJobComplete = false` for non-critical jobs
2. Add more frequent interrupt checks
3. Ensure resource cleanup in finally blocks

### Partial State After Shutdown

**Problem:** Job leaves data in inconsistent state.

**Solutions:**
1. Use transactions for atomicity
2. Check interrupt before committing
3. Use `@PersistJobDataAfterExecution` to persist progress across restarts

---

## See Also

- [Official Kora Documentation](../../../.kora-agent/kora-docs/mkdocs/docs/en/documentation/scheduling.md#graceful-shutdown) — Graceful shutdown
- [quartz-scheduling-reference.md](quartz-scheduling-reference.md) — Quartz annotations
- [scheduling-config-reference.md](scheduling-config-reference.md) — Configuration
