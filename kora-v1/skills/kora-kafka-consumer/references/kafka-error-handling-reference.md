# Kafka Error Handling Reference

**Source:** [.kora-agent/kora-docs/mkdocs/docs/en/documentation/kafka.md](../../../.kora-agent/kora-docs/mkdocs/docs/en/documentation/kafka.md)  
**Examples:** [.kora-agent/kora-examples/kora-java-kafka/](../../../.kora-agent/kora-examples/examples/java/kora-java-kafka/)

Comprehensive error handling patterns for Kafka consumers in Kora.

## Contents

- [Consumer Errors](#consumer-errors)
- [Producer Errors](#producer-errors)
- [Rebalance Handling](#rebalance-handling)
- [Retry Logic](#retry-logic)
- [Graceful Shutdown](#graceful-shutdown)
- [Best Practices](#best-practices)

---

## Consumer Errors

### Deserialization Errors

When deserialization fails, Kora can pass the error to your listener using the nullable signature pattern.

#### Pattern 1: Nullable Event + Exception

```java
@KafkaListener("kafka.consumer.listener")
void process(@Nullable String value, @Nullable Exception error) {
    if (error != null) {
        // Handle deserialization error
        log.error("Deserialization error: {}", error.getMessage(), error);
        return;
    }
    // Normal processing
    log.info("Received: {}", value);
}
```

#### Pattern 2: Nullable Json Event + Exception

```java
@KafkaListener("kafka.consumer.listener")
void process(@Nullable @Json UserEvent event, @Nullable Exception error) {
    if (error != null) {
        // Handle JSON deserialization error
        log.error("Failed to deserialize UserEvent", error);
        // Option: Send to DLQ
        dlqPublisher.send("user-events-dlq", 
            "user-event", 
            error.getMessage());
        return;
    }
    if (event == null) {
        log.warn("Received null event without error");
        return;
    }
    // Normal processing
    log.info("Received event: userId={}, eventType={}", 
        event.userId(), event.eventType());
}
```

#### Pattern 3: ConsumerRecord with Exception Handling

When using `ConsumerRecord`, deserialization exceptions are thrown when accessing `key()` or `value()`:

```java
@KafkaListener("kafka.consumer.listener")
void process(ConsumerRecord<String, UserEvent> record) {
    try {
        UserEvent event = record.value();  // Throws RecordValueDeserializationException
        log.info("Received: {}", event);
    } catch (RecordValueDeserializationException e) {
        log.error("Value deserialization failed", e);
        // Access raw bytes for DLQ
        ConsumerRecord<byte[], byte[]> raw = e.getRecord();
        log.error("Raw key: {}, raw value: {}", 
            new String(raw.key()), 
            new String(raw.value()));
    }
}
```

**Exception types:**
- `RecordKeyDeserializationException` - key deserialization failed
- `RecordValueDeserializationException` - value deserialization failed

Both exceptions provide `getRecord()` to access the original `ConsumerRecord<byte[], byte[]>`.

---

### Skipping Messages (KafkaSkipRecordException)

Throw `KafkaSkipRecordException` to skip the current message and continue to the next.

```java
@KafkaListener("kafka.consumer.listener")
void process(String value) {
    if ("skip".equals(value)) {
        throw new KafkaSkipRecordException(
            new IllegalArgumentException("Want to skip!")
        );
    }
    // Normal processing
    log.info("Processing: {}", value);
}
```

**What happens:**
1. Container catches the exception
2. Logs the skip event
3. Commits offset for the skipped message
4. Continues to the next message
5. Records metrics (skipped count incremented)

---

### Custom Skippable Exceptions

Implement `SkippableRecordException` to create custom skippable exceptions.

```java
public class MySkipException extends RuntimeException implements SkippableRecordException {
    
    public MySkipException(String message) {
        super(message);
    }
    
    public MySkipException(String message, Throwable cause) {
        super(message, cause);
    }
}
```

**Usage:**

```java
@KafkaListener("kafka.consumer.listener")
void process(String value) {
    if (shouldSkip(value)) {
        throw new MySkipException("Business reason to skip");
    }
    // Normal processing
}
```

**Common use cases:**
- Duplicate event detection
- Business rule violations
- Non-critical validation failures
- Intentional filtering

---

### Dead Letter Queue (DLQ)

Implement a DLQ publisher for messages that cannot be processed.

#### DLQ Publisher Interface

```java
@KafkaPublisher("kafka.dlqPublisher")
public interface DlqPublisher {
    
    @KafkaPublisher.Topic("kafka.dlq.topic")
    void send(String originalTopic, String originalMessage, String errorMessage);
    
    @KafkaPublisher.Topic("kafka.dlq.topic")
    void send(String originalTopic, byte[] rawKey, byte[] rawValue, String errorMessage);
}
```

#### DLQ Handler Pattern

```java
@Component
public final class DlqHandler {
    
    private final DlqPublisher dlqPublisher;
    
    public DlqHandler(DlqPublisher dlqPublisher) {
        this.dlqPublisher = dlqPublisher;
    }
    
    @KafkaListener("kafka.consumer.listener")
    void process(@Nullable String value, @Nullable Exception error) {
        if (error != null) {
            log.error("Processing error, sending to DLQ", error);
            dlqPublisher.send("my-topic", 
                value != null ? value : "null",
                error.getMessage());
            return;
        }
        // Normal processing
        processMessage(value);
    }
    
    private void processMessage(String value) {
        // Business logic
    }
}
```

#### DLQ with Raw Bytes (Deserialization Errors)

```java
@Component
public final class DeserializationErrorHandler {
    
    private final DlqPublisher dlqPublisher;
    
    @KafkaListener("kafka.consumer.listener")
    void process(ConsumerRecord<String, String> record) {
        try {
            String value = record.value();  // May throw
            processValue(value);
        } catch (RecordValueDeserializationException e) {
            log.error("Deserialization failed", e);
            ConsumerRecord<byte[], byte[]> raw = e.getRecord();
            dlqPublisher.send(
                record.topic(),
                raw.key(),
                raw.value(),
                "Deserialization error: " + e.getMessage()
            );
        }
    }
}
```

---

## Producer Errors

### KafkaPublishException

Thrown when a message fails to publish.

```java
try {
    publisher.send("key", "value");
} catch (KafkaPublishException e) {
    log.error("Publish failed", e.getCause());
    // Handle error: retry, fallback, etc.
}
```

The actual Kafka exception is in `e.getCause()`.

### SerializationException

Thrown when serialization fails.

```java
try {
    publisher.send("key", invalidObject);
} catch (SerializationException e) {
    log.error("Serialization failed", e);
    // Handle error: fix object, skip, alert
}
```

---

## Rebalance Handling

Implement `ConsumerAwareRebalanceListener` to react to partition rebalance events.

### Interface

```java
public interface ConsumerAwareRebalanceListener {
    
    void onPartitionsRevoked(Consumer<?, ?> consumer, Collection<TopicPartition> partitions);
    
    void onPartitionsAssigned(Consumer<?, ?> consumer, Collection<TopicPartition> partitions);
    
    void onPartitionsLost(Consumer<?, ?> consumer, Collection<TopicPartition> partitions);
}
```

### Implementation Example

```java
@Tag(MyListenerProcessTag.class)  // Must match the listener's config path tag
@Component
public final class MyRebalanceListener implements ConsumerAwareRebalanceListener {
    
    private static final Logger log = LoggerFactory.getLogger(MyRebalanceListener.class);
    
    @Override
    public void onPartitionsRevoked(Consumer<?, ?> consumer, Collection<TopicPartition> partitions) {
        log.info("Partitions revoked: {}", partitions);
        
        // Commit current offsets before rebalance
        consumer.commitSync();
        
        // Clear caches
        // Save processing state
        // Close resources for these partitions
    }
    
    @Override
    public void onPartitionsAssigned(Consumer<?, ?> consumer, Collection<TopicPartition> partitions) {
        log.info("Partitions assigned: {}", partitions);
        
        // Log newly assigned partitions
        // Initialize state for new partitions
        // Load cached data if needed
    }
    
    @Override
    public void onPartitionsLost(Consumer<?, ?> consumer, Collection<TopicPartition> partitions) {
        log.warn("Partitions lost (consumer evicted): {}", partitions);
        
        // Clean up resources without committing
        // The consumer no longer owns these partitions
    }
}
```

### When to Use

- **onPartitionsRevoked:** Save state, commit offsets, clear caches
- **onPartitionsAssigned:** Initialize state, log assignment
- **onPartitionsLost:** Clean up without committing (consumer was evicted)

---

## Retry Logic

### Backoff Configuration

Configure automatic backoff between errors:

```hocon
kafka {
  consumer {
    myListener {
      backoffTimeout = "15s"  # Pause between unexpected exceptions
      topics = ["my-topic"]
      driverProperties {
        "bootstrap.servers" = "localhost:9092"
      }
    }
  }
}
```

### Manual Retry Pattern

```java
@KafkaListener("kafka.consumer.listener")
void process(String value) {
    int maxRetries = 3;
    int attempt = 0;
    
    while (attempt < maxRetries) {
        try {
            processMessage(value);
            break;  // Success
        } catch (Exception e) {
            attempt++;
            if (attempt >= maxRetries) {
                log.error("Max retries exceeded", e);
                throw e;  // Will trigger backoff or skip
            }
            log.warn("Retry {}/{}", attempt, maxRetries, e);
        }
    }
}
```

---

## Graceful Shutdown

Configure shutdown timeout for clean termination:

```hocon
kafka {
  consumer {
    myListener {
      shutdownWait = "30s"  # Time to finish processing before shutdown
      topics = ["my-topic"]
      driverProperties {
        "bootstrap.servers" = "localhost:9092"
      }
    }
  }
}
```

**Shutdown sequence:**
1. Container stops polling for new messages
2. Allows `shutdownWait` time to finish processing current messages
3. Commits offsets for processed messages
4. Closes the consumer

---

## Best Practices

### 1. Always Handle Deserialization Errors

Use the nullable signature pattern:

```java
@KafkaListener("kafka.consumer.listener")
void process(@Nullable @Json MyEvent event, @Nullable Exception error) {
    if (error != null) {
        log.error("Deserialization failed", error);
        // Handle or send to DLQ
        return;
    }
    // Process event
}
```

### 2. Use DLQ for Bad Messages

Never silently drop messages that failed to process:

```java
if (error != null) {
    log.error("Processing failed", error);
    dlqPublisher.send("my-topic", rawMessage, error.getMessage());
    return;
}
```

### 3. Log Rebalance Events

Rebalance logging helps debug consumption issues:

```java
@Override
public void onPartitionsAssigned(Consumer<?, ?> consumer, Collection<TopicPartition> partitions) {
    log.info("Partitions assigned: {}", partitions);
}
```

### 4. Configure Graceful Shutdown

Always set `shutdownWait` for clean termination:

```hocon
shutdownWait = "30s"
```

### 5. Monitor Consumer Lag

Set up metrics to detect consumption problems:

```hocon
telemetry {
  metrics {
    enabled = true
    slo = [1, 10, 50, 100, 200, 500, 1000, 2000, 5000, 10000]
  }
}
```

### 6. Make Consumers Idempotent

The same message may be delivered multiple times:

```java
void process(MyEvent event) {
    if (isDuplicate(event)) {
        log.debug("Duplicate event, skipping: {}", event.id());
        return;
    }
    processEvent(event);
}
```

---

## Related References

- [Kafka Consumer Reference](kafka-consumer-reference.md)
- [Kafka Serialization Reference](kafka-serialization-reference.md)
- [Kafka Transactions Reference](kafka-transactions-reference.md)
