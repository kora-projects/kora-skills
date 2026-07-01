# Graceful Shutdown Reference

Handling interrupt signals and graceful shutdown for scheduled jobs.

## Contents

- [Overview](#overview)
- [JDK Shutdown](#jdk-shutdown) — config, interrupt handling, batch and resource patterns
- [Quartz Shutdown](#quartz-shutdown)
- [Shutdown Priority](#shutdown-priority)
- [Troubleshooting](#troubleshooting)

---

## Overview

Both JDK and Quartz schedulers invoke **interrupt** on running jobs at SIGTERM. Long-running jobs must check interrupt status and exit gracefully to avoid:
- Resource leaks
- Incomplete transactions
- Data corruption
- Extended shutdown times

---

## JDK Shutdown

### Configuration

```hocon
scheduling {
  shutdownWait = "30s"  # Grace period for in-flight jobs
}
```

```yaml
scheduling:
  shutdownWait: "30s"
```

**Behavior:**
1. SIGTERM received
2. Scheduler stops accepting new jobs
3. Interrupt sent to running jobs
4. Wait up to `shutdownWait` for jobs to complete
5. Force shutdown after timeout

### Interrupt Handling Pattern

```java
@Component
public class LongRunningJob {

    @ScheduleAtFixedRate(config = "jobs.batch")
    void processBatch() {
        while (!stopCondition()) {
            // Check interrupt status
            if (Thread.currentThread().isInterrupted()) {
                // Cleanup and exit
                log.info("Interrupted, exiting gracefully");
                return;
            }
            doWork();
        }
    }
}
```

### Batch Processing Pattern

```java
@ScheduleWithFixedDelay(config = "jobs.import")
void importLargeDataset() {
    List<Record> records = fetchRecords();
    
    for (Record record : records) {
        // Check interrupt before each item
        if (Thread.currentThread().isInterrupted()) {
            log.warn("Import interrupted, {} records remaining", records.size());
            return;  // Partial completion is OK
        }
        processRecord(record);
    }
}
```

### Resource Cleanup

```java
@ScheduleAtFixedRate(period = 1, unit = ChronoUnit.HOURS)
void processWithResources() {
    Connection conn = null;
    try {
        conn = dataSource.getConnection();
        
        while (processing) {
            if (Thread.currentThread().isInterrupted()) {
                // Cleanup before exit
                conn.close();
                return;
            }
            doWork(conn);
        }
    } catch (SQLException e) {
        log.error("Database error", e);
    } finally {
        if (conn != null) {
            try {
                conn.close();
            } catch (SQLException e) {
                log.warn("Failed to close connection", e);
            }
        }
    }
}
```

---

## Quartz Shutdown

### Configuration

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

### Interrupt Handling with @DisallowConcurrentExecution

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

### Stateful Jobs

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

## Shutdown Priority

### When to Check Interrupt

| Scenario | Check Frequency |
|----------|-----------------|
| Short tasks (< 1s) | Optional |
| Medium tasks (1-30s) | Every iteration / step |
| Long tasks (> 30s) | Before each unit of work |
| Infinite loops | Every iteration (required) |

### When to Use waitForJobComplete

| Scenario | Setting |
|----------|---------|
| Idempotent jobs | `false` (default) |
| Critical jobs (must complete) | `true` |
| Long batch processing | `true` + interrupt checks |
| Quick cleanup tasks | `false` |

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
1. Reduce `shutdownWait` for non-critical jobs
2. Add more frequent interrupt checks
3. Use `waitForJobComplete = false` for Quartz
4. Ensure resource cleanup in finally blocks

### Partial State After Shutdown

**Problem:** Job leaves data in inconsistent state.

**Solutions:**
1. Use transactions for atomicity
2. Check interrupt before committing
3. Implement idempotent operations
4. Use `@PersistJobDataAfterExecution` for Quartz

---

## See Also

- Kora docs: `.kora-agent/kora-docs/mkdocs/docs/en/documentation/scheduling.md` (section `#graceful-shutdown`)
- [jdk-scheduling-reference.md](jdk-scheduling-reference.md) — JDK scheduling annotations
- [quartz-scheduling-reference.md](quartz-scheduling-reference.md) — Quartz scheduling
- [scheduling-config-reference.md](scheduling-config-reference.md) — Configuration
