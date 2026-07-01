# Kafka Rebalance Listener Reference

**Source:** [.kora-agent/kora-docs/mkdocs/docs/en/documentation/kafka.md](../../../.kora-agent/kora-docs/mkdocs/docs/en/documentation/kafka.md)

Partition rebalance handling for Kafka consumers in Kora.

## Contents

- [Overview](#overview)
- [ConsumerAwareRebalanceListener Interface](#consumerawarerebalancelistener-interface)
- [Implementation](#implementation)
- [Method Details](#method-details)
- [Common Patterns](#common-patterns)
- [Configuration](#configuration)
- [Best Practices](#best-practices)
- [Troubleshooting](#troubleshooting)

---

## Overview

Partition rebalancing occurs when:
- Consumer group members join or leave
- Topics are added or removed
- Partitions are added to topics
- Consumer session times out

Kora provides `ConsumerAwareRebalanceListener` interface to react to rebalance events.

---

## ConsumerAwareRebalanceListener Interface

```java
public interface ConsumerAwareRebalanceListener {
    
    void onPartitionsRevoked(Consumer<?, ?> consumer, Collection<TopicPartition> partitions);
    
    void onPartitionsAssigned(Consumer<?, ?> consumer, Collection<TopicPartition> partitions);
    
    void onPartitionsLost(Consumer<?, ?> consumer, Collection<TopicPartition> partitions);
}
```

---

## Implementation

### Basic Rebalance Listener

```java
@Tag(UserEventsTag.class)  // Same tag class the listener is annotated with
@Component
public final class UserEventsRebalanceListener implements ConsumerAwareRebalanceListener {
    
    private static final Logger log = LoggerFactory.getLogger(UserEventsRebalanceListener.class);
    
    @Override
    public void onPartitionsRevoked(Consumer<?, ?> consumer, Collection<TopicPartition> partitions) {
        log.info("Partitions revoked: {}", partitions);
        
        // Commit current offsets before rebalance
        consumer.commitSync();
        
        // Clear caches for these partitions
        // Save processing state
    }
    
    @Override
    public void onPartitionsAssigned(Consumer<?, ?> consumer, Collection<TopicPartition> partitions) {
        log.info("Partitions assigned: {}", partitions);
        
        // Initialize state for new partitions
        // Log assignment for monitoring
    }
    
    @Override
    public void onPartitionsLost(Consumer<?, ?> consumer, Collection<TopicPartition> partitions) {
        log.warn("Partitions lost (consumer evicted): {}", partitions);
        
        // Clean up resources without committing
        // The consumer no longer owns these partitions
    }
}
```

### Tag Matching

Kora binds the rebalance listener to a consumer by **tag**. Each `@KafkaListener`
gets an auto-generated tag (`<Listener>Module.<Listener>ProcessTag`, visible in the
generated module), but the clearest approach is to declare your own tag class and put
it on both the listener and the rebalance listener:

```java
// A shared tag class
public final class UserEventsTag { }

// Listener uses the explicit tag
@Component
public final class UserEventsListener {
    @KafkaListener(value = "kafka.consumer.userEvents", tag = UserEventsTag.class)
    void process(String value) { }
}

// Rebalance listener carries the same tag
@Tag(UserEventsTag.class)
@Component
public final class UserEventsRebalanceListener implements ConsumerAwareRebalanceListener {
    // ...
}
```

---

## Method Details

### onPartitionsRevoked

**Called when:** Partitions are about to be revoked from this consumer.

**Use cases:**
- Commit current offsets (if not using auto-commit)
- Flush pending writes
- Clear partition-specific caches
- Save processing state
- Close partition-specific resources

```java
@Override
public void onPartitionsRevoked(Consumer<?, ?> consumer, Collection<TopicPartition> partitions) {
    log.info("Partitions revoked: {}", partitions);
    
    // Commit offsets synchronously
    consumer.commitSync();
    
    // Clear caches
    partitionCaches.keySet().removeAll(partitions);
    
    // Save state
    stateManager.saveState();
}
```

### onPartitionsAssigned

**Called when:** Partitions are assigned to this consumer.

**Use cases:**
- Initialize partition state
- Load cached data for partitions
- Log assignment for monitoring
- Set up partition-specific resources

```java
@Override
public void onPartitionsAssigned(Consumer<?, ?> consumer, Collection<TopicPartition> partitions) {
    log.info("Partitions assigned: {}", partitions);
    
    // Initialize state for new partitions
    for (TopicPartition partition : partitions) {
        partitionCaches.put(partition, new PartitionCache());
        log.info("Initialized cache for partition: {}", partition);
    }
}
```

### onPartitionsLost

**Called when:** Partitions are lost without a clean revocation (consumer evicted).

**Key difference:** Do NOT commit offsets - the consumer no longer owns these partitions.

**Use cases:**
- Clean up resources
- Log the event for debugging
- Alert on unexpected loss

```java
@Override
public void onPartitionsLost(Consumer<?, ?> consumer, Collection<TopicPartition> partitions) {
    log.warn("Partitions lost (consumer evicted from group): {}", partitions);
    
    // Clean up without committing
    partitionCaches.keySet().removeAll(partitions);
    
    // Optionally alert
    monitoringService.alertPartitionLoss(partitions);
}
```

---

## Common Patterns

### State Management

```java
@Tag(MyListener.class)
@Component
public final class StatefulRebalanceListener implements ConsumerAwareRebalanceListener {
    
    private final Map<TopicPartition, ProcessingState> stateMap = new ConcurrentHashMap<>();
    private final ProcessingStateManager stateManager;
    
    public StatefulRebalanceListener(ProcessingStateManager stateManager) {
        this.stateManager = stateManager;
    }
    
    @Override
    public void onPartitionsRevoked(Consumer<?, ?> consumer, Collection<TopicPartition> partitions) {
        // Save state for revoked partitions
        for (TopicPartition partition : partitions) {
            ProcessingState state = stateMap.remove(partition);
            if (state != null) {
                stateManager.saveState(partition, state);
            }
        }
    }
    
    @Override
    public void onPartitionsAssigned(Consumer<?, ?> consumer, Collection<TopicPartition> partitions) {
        // Load state for assigned partitions
        for (TopicPartition partition : partitions) {
            ProcessingState state = stateManager.loadState(partition);
            if (state != null) {
                stateMap.put(partition, state);
            }
        }
    }
    
    @Override
    public void onPartitionsLost(Consumer<?, ?> consumer, Collection<TopicPartition> partitions) {
        // Partitions lost - state may be processed by another consumer
        partitions.forEach(stateMap::remove);
    }
}
```

### Cache Management

```java
@Tag(CachedListener.class)
@Component
public final class CacheRebalanceListener implements ConsumerAwareRebalanceListener {
    
    private final LocalCache cache;
    
    public CacheRebalanceListener(LocalCache cache) {
        this.cache = cache;
    }
    
    @Override
    public void onPartitionsRevoked(Consumer<?, ?> consumer, Collection<TopicPartition> partitions) {
        // Clear cache entries for revoked partitions
        for (TopicPartition partition : partitions) {
            cache.invalidateForPartition(partition);
        }
    }
    
    @Override
    public void onPartitionsAssigned(Consumer<?, ?> consumer, Collection<TopicPartition> partitions) {
        // Pre-load cache for new partitions (optional)
        for (TopicPartition partition : partitions) {
            cache.preloadForPartition(partition);
        }
    }
    
    @Override
    public void onPartitionsLost(Consumer<?, ?> consumer, Collection<TopicPartition> partitions) {
        // Invalidate cache for lost partitions
        partitions.forEach(cache::invalidateForPartition);
    }
}
```

### Metrics Tracking

```java
@Tag(MetricsListener.class)
@Component
public final class MetricsRebalanceListener implements ConsumerAwareRebalanceListener {
    
    private final MeterRegistry meterRegistry;
    private final AtomicInteger assignedCount = new AtomicInteger();
    private final AtomicInteger revokedCount = new AtomicInteger();
    
    public MetricsRebalanceListener(MeterRegistry meterRegistry) {
        this.meterRegistry = meterRegistry;
    }
    
    @Override
    public void onPartitionsRevoked(Consumer<?, ?> consumer, Collection<TopicPartition> partitions) {
        revokedCount.addAndGet(partitions.size());
        meterRegistry.counter("kafka.rebalance.partitions.revoked")
            .increment(partitions.size());
        log.info("Partitions revoked: {} (total: {})", partitions.size(), revokedCount.get());
    }
    
    @Override
    public void onPartitionsAssigned(Consumer<?, ?> consumer, Collection<TopicPartition> partitions) {
        assignedCount.addAndGet(partitions.size());
        meterRegistry.counter("kafka.rebalance.partitions.assigned")
            .increment(partitions.size());
        log.info("Partitions assigned: {} (total: {})", partitions.size(), assignedCount.get());
    }
    
    @Override
    public void onPartitionsLost(Consumer<?, ?> consumer, Collection<TopicPartition> partitions) {
        meterRegistry.counter("kafka.rebalance.partitions.lost")
            .increment(partitions.size());
        log.warn("Partitions lost: {}", partitions.size());
    }
}
```

---

## Configuration

### Enable Rebalance Listener

No special configuration needed - the listener is auto-detected by the `@Tag` annotation.

```hocon
kafka {
  consumer {
    myListener {
      topics = ["my-topic"]
      driverProperties {
        "bootstrap.servers" = "localhost:9092"
        "group.id" = "my-group"
      }
      # Rebalance listener auto-detected by @Tag
    }
  }
}
```

### Tune Rebalance Behavior

```hocon
kafka {
  consumer {
    myListener {
      topics = ["my-topic"]
      driverProperties {
        "bootstrap.servers" = "localhost:9092"
        "group.id" = "my-group"
        
        # Rebalance tuning
        "session.timeout.ms" = 30000           # Time before considered dead
        "heartbeat.interval.ms" = 10000        # Heartbeat frequency
        "max.poll.interval.ms" = 300000        # Max time between polls
        "rebalance.timeout.ms" = 60000         # Max time for rebalance
      }
    }
  }
}
```

---

## Best Practices

### 1. Keep Handlers Fast

Rebalance handlers should be quick - avoid long-running operations:

```java
// BAD: Long operation blocks rebalance
@Override
public void onPartitionsRevoked(...) {
    processAllPendingMessages();  // Takes too long!
}

// GOOD: Quick cleanup
@Override
public void onPartitionsRevoked(...) {
    commitSync();
    clearCaches();
}
```

### 2. Commit Offsets on Revoke

Always commit offsets when partitions are revoked:

```java
@Override
public void onPartitionsRevoked(Consumer<?, ?> consumer, Collection<TopicPartition> partitions) {
    consumer.commitSync();  // Ensure offsets are saved
}
```

### 3. Don't Commit on Lost

Never commit offsets in `onPartitionsLost`:

```java
// WRONG: Consumer no longer owns partitions
@Override
public void onPartitionsLost(Consumer<?, ?> consumer, Collection<TopicPartition> partitions) {
    consumer.commitSync();  // Will fail or commit wrong offsets!
}

// RIGHT: Clean up only
@Override
public void onPartitionsLost(Consumer<?, ?> consumer, Collection<TopicPartition> partitions) {
    cleanupResources(partitions);
}
```

### 4. Log Rebalance Events

Rebalance logging is crucial for debugging:

```java
private static final Logger log = LoggerFactory.getLogger(MyRebalanceListener.class);

@Override
public void onPartitionsAssigned(Consumer<?, ?> consumer, Collection<TopicPartition> partitions) {
    log.info("Partitions assigned: {}", partitions);
}
```

### 5. Handle Rebalance Storms

If rebalances happen frequently, investigate the root cause:
- Check `session.timeout.ms` and `heartbeat.interval.ms`
- Ensure processing completes within `max.poll.interval.ms`
- Consider increasing timeouts
- Check network stability

---

## Troubleshooting

### Frequent Rebalances

**Symptoms:** Constant rebalancing, messages processed multiple times.

**Causes:**
- Processing takes longer than `max.poll.interval.ms`
- Consumer can't send heartbeats in time
- Network issues

**Solutions:**
```hocon
driverProperties {
  "max.poll.interval.ms" = 600000  # Increase max poll interval
  "session.timeout.ms" = 60000     # Increase session timeout
  "heartbeat.interval.ms" = 15000  # Adjust heartbeat
}
```

### Message Duplication

**Symptoms:** Same message processed multiple times.

**Cause:** Offsets not committed before rebalance.

**Solution:** Commit in `onPartitionsRevoked`:
```java
@Override
public void onPartitionsRevoked(Consumer<?, ?> consumer, Collection<TopicPartition> partitions) {
    consumer.commitSync();
}
```

### Partition Starvation

**Symptoms:** Some partitions not being consumed.

**Cause:** Uneven partition distribution.

**Solution:** Check partition assignment and consumer group size.

---

## Related References

- [Kafka Consumer Reference](kafka-consumer-reference.md)
- [Kafka Error Handling Reference](kafka-error-handling-reference.md)
- [Kafka Telemetry Reference](kafka-telemetry-reference.md)
