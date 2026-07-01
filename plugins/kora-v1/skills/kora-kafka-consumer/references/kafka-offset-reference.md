# Kafka Offset Management Reference

**Source:** [.kora-agent/kora-docs/mkdocs/docs/en/documentation/kafka.md](../../../.kora-agent/kora-docs/mkdocs/docs/en/documentation/kafka.md)

Complete reference for Kafka offset management: auto-commit, manual commit, and rebalance handling.

## Contents

- [Overview](#overview)
- [Auto-Commit (Default)](#auto-commit-default)
- [Manual Commit](#manual-commit)
- [Manual Commit for Batches](#manual-commit-for-batches)
- [Offset Configuration](#offset-configuration)
- [Rebalance and Offset Commit](#rebalance-and-offset-commit)
- [Common Pitfalls](#common-pitfalls)
- [Best Practices](#best-practices)

---

## Overview

Kora provides flexible offset management strategies:

| Strategy | Description | Use Case |
|----------|-------------|----------|
| **Auto-commit** (default) | Offset committed after processing | Most use cases |
| **Manual commit** | Developer controls commit timing | Exactly-once semantics |
| **Rebalance commit** | Commit on partition revocation | Prevent message loss |

---

## Auto-Commit (Default)

Kora automatically commits offset after successful processing.

### Commit Timing by Signature

| Method Signature | Commit Timing |
|-----------------|---------------|
| `void process(String value)` | After each message |
| `void process(ConsumerRecords<?, ?> records)` | After entire batch |
| `void process(ConsumerRecord<?, ?> record)` | After each message |

### Example

```java
@KafkaListener("kafka.consumer.userEvents")
void process(String value) {
    userService.handle(value);
    // commitSync() called automatically after return
}
```

> **Risk:** If application crashes after processing but before commit — message will be reprocessed.

---

## Manual Commit

For manual control, add `Consumer` parameter to method signature.

### Basic Manual Commit

```java
@KafkaListener("kafka.consumer.userEvents")
void process(ConsumerRecord<String, String> record, Consumer<String, String> consumer) {
    try {
        userService.handle(record.value());
        
        // Commit after successful processing
        consumer.commitSync();
        
    } catch (Exception e) {
        log.error("Processing failed, offset not committed", e);
        // Don't commit — message will be reprocessed
        throw e;
    }
}
```

### Use Cases for Manual Commit

- Exactly-once semantics
- Batch processing with intermediate commits
- Sync with database transactions

---

## Manual Commit for Batches

### Intermediate Commit Pattern

```java
@KafkaListener("kafka.consumer.orders")
void process(ConsumerRecords<String, OrderEvent> records, 
             Consumer<String, OrderEvent> consumer) {
    
    int processed = 0;
    int batchSize = 50;
    
    for (ConsumerRecord<String, OrderEvent> record : records) {
        try {
            orderService.process(record.value());
            processed++;
            
            // Intermediate commit every N messages
            if (processed % batchSize == 0) {
                consumer.commitSync();
                log.info("Committed after {} messages", processed);
            }
        } catch (Exception e) {
            log.error("Failed at offset={}", record.offset(), e);
            // Commit processed before throwing
            if (processed > 0) {
                consumer.commitSync();
            }
            throw e;
        }
    }
    
    // Final commit
    consumer.commitSync();
}
```

---

## Offset Configuration

### Starting Position

Configure initial position in consumer configuration.

```hocon
kafka {
  consumer {
    userEvents {
      topics = ["user-events"]
      
      # Starting position
      offset = "earliest"  // earliest, latest, or duration
      # offset = "5m"     // 5 minutes ago
      # offset = "1h"     // 1 hour ago
      
      driverProperties {
        "bootstrap.servers" = "localhost:9092"
        "group.id" = "user-service"
        "auto.offset.reset" = "earliest"  # For new consumer groups
      }
    }
  }
}
```

### Duration-based Offset

| Value | Description |
|-------|-------------|
| `"earliest"` | Start from beginning of topic |
| `"latest"` | Start from current position (new messages only) |
| `"5m"` | Start from 5 minutes ago |
| `"1h"` | Start from 1 hour ago |
| `"24h"` | Start from 24 hours ago |

> **Note:** Duration-based offset works only if `group.id` is not specified (no committed offsets exist).

---

## Rebalance and Offset Commit

Commit offsets in `onPartitionsRevoked` to prevent data loss.

### Rebalance Listener Implementation

```java
@Tag(UserEventsTag.class)  // Same tag class the listener is annotated with
@Component
public final class UserEventsRebalanceListener implements ConsumerAwareRebalanceListener {
    
    @Override
    public void onPartitionsRevoked(Consumer<?, ?> consumer, 
                                     Collection<TopicPartition> partitions) {
        log.info("Partitions revoked: {}", partitions);
        
        // Commit current offsets before rebalance
        consumer.commitSync();
        
        // Clear caches, close resources
        cache.clear();
    }
    
    @Override
    public void onPartitionsAssigned(Consumer<?, ?> consumer, 
                                      Collection<TopicPartition> partitions) {
        log.info("Partitions assigned: {}", partitions);
        // Initialize state for new partitions
    }
    
    @Override
    public void onPartitionsLost(Consumer<?, ?> consumer, 
                                  Collection<TopicPartition> partitions) {
        log.warn("Partitions lost (consumer evicted): {}", partitions);
        // Don't commit — consumer no longer owns these partitions
    }
}
```

### Key Points

| Method | Action | Reason |
|--------|--------|--------|
| `onPartitionsRevoked` | Commit offsets | Prevent message loss |
| `onPartitionsAssigned` | Initialize state | Prepare for processing |
| `onPartitionsLost` | Don't commit | Consumer evicted, can't commit |

---

## Common Pitfalls

| Problem | Cause | Solution |
|---------|-------|----------|
| **Message loss** | Offset not committed before crash | Use manual commit or commit in `onPartitionsRevoked` |
| **Duplicate processing** | Offset committed before processing completes | Commit after business logic, implement idempotency |
| **Wrong start position** | Default `latest` when `earliest` needed | Set `offset = "earliest"` explicitly |
| **Rebalance storm** | Long processing without heartbeat | Increase `max.poll.interval.ms` |

---

## Best Practices

### 1. Commit After Processing

Never commit before business logic completes:

```java
// GOOD
@KafkaListener("kafka.consumer.events")
void process(ConsumerRecord<String, String> record, Consumer<String, String> consumer) {
    saveToDatabase(record.value());
    consumer.commitSync();  // Commit after save
}
```

### 2. Implement Idempotency

Handle duplicate messages safely:

```java
@KafkaListener("kafka.consumer.events")
void process(ConsumerRecord<String, String> record, Consumer<String, String> consumer) {
    if (isDuplicate(record.value())) {
        log.debug("Duplicate, skipping: {}", record.offset());
        consumer.commitSync();
        return;
    }
    // Process
    consumer.commitSync();
}
```

### 3. Test Offset Behavior

Verify `earliest` vs `latest` in staging environment:

```hocon
# Development - start from beginning
offset = "earliest"

# Production - only new messages
offset = "latest"
```

---

## Related References

- [Kafka Consumer Reference](kafka-consumer-reference.md) — Basic configuration
- [Kafka Rebalance Reference](kafka-rebalance-reference.md) — Rebalance handling
- [Kafka Batch Reference](kafka-batch-reference.md) — Batch processing with commits
