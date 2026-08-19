# Graceful Shutdown Reference (JDK)

Handling interrupt signals and graceful shutdown for `scheduling-jdk` jobs. For Quartz jobs
see the sibling skill [kora-aop-scheduling-quartz](../../kora-aop-scheduling-quartz/SKILL.md).

## Contents

- [Overview](#overview)
- [Configuration](#configuration)
- [Interrupt Handling Pattern](#interrupt-handling-pattern)
- [Batch Processing Pattern](#batch-processing-pattern)
- [Resource Cleanup](#resource-cleanup)
- [When to Check Interrupt](#when-to-check-interrupt)
- [Complete Example](#complete-example)
- [Troubleshooting](#troubleshooting)

---

## Overview

The JDK scheduler invokes **interrupt** on running jobs at SIGTERM. Long-running jobs must
check interrupt status and exit gracefully to avoid resource leaks, incomplete transactions,
data corruption, and extended shutdown times.

---

## Configuration

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

---

## Interrupt Handling Pattern

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

---

## Batch Processing Pattern

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

---

## Resource Cleanup

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

## When to Check Interrupt

| Scenario | Check Frequency |
|----------|-----------------|
| Short tasks (< 1s) | Optional |
| Medium tasks (1-30s) | Every iteration / step |
| Long tasks (> 30s) | Before each unit of work |
| Infinite loops | Every iteration (required) |

---

## Complete Example

```java
package com.example.app.jobs;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import ru.tinkoff.kora.common.Component;
import ru.tinkoff.kora.scheduling.jdk.annotation.ScheduleWithFixedDelay;

import java.time.temporal.ChronoUnit;

@Component
public class DataImportJob {

    private static final Logger log = LoggerFactory.getLogger(DataImportJob.class);

    @ScheduleWithFixedDelay(initialDelay = 30, delay = 5, unit = ChronoUnit.MINUTES)
    void importExternalData() {
        log.info("Starting data import");

        try {
            // Fetch data to import
            var records = fetchRecordsFromApi();
            log.info("Fetched {} records", records.size());

            int imported = 0;
            for (var record : records) {
                // CRITICAL: Check interrupt before each record
                if (Thread.currentThread().isInterrupted()) {
                    log.warn("Import interrupted after {} records", imported);
                    return;  // Graceful exit
                }

                importRecord(record);
                imported++;
            }

            log.info("Import completed: {} records", imported);

        } catch (Exception e) {
            if (Thread.currentThread().isInterrupted()) {
                log.warn("Import interrupted during execution");
            } else {
                log.error("Import failed", e);
            }
        }
    }

    private List<Record> fetchRecordsFromApi() {
        // ... fetch logic ...
        return List.of();
    }

    private void importRecord(Record record) {
        // ... import logic ...
    }
}
```

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
3. Ensure resource cleanup in finally blocks

### Partial State After Shutdown

**Problem:** Job leaves data in inconsistent state.

**Solutions:**
1. Use transactions for atomicity
2. Check interrupt before committing
3. Implement idempotent operations

---

## See Also

- [Official Kora Documentation](../../../.kora-agent/kora-docs/mkdocs/docs/en/documentation/scheduling.md#graceful-shutdown) — Graceful shutdown
- [jdk-scheduling-reference.md](jdk-scheduling-reference.md) — JDK scheduling annotations
- [scheduling-config-reference.md](scheduling-config-reference.md) — Configuration
