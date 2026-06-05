# Kafka Error Handling Reference

**Source:** [.kora-agent/kora-docs/mkdocs/docs/en/documentation/kafka.md](.kora-agent/kora-docs/mkdocs/docs/en/documentation/kafka.md)  
**Examples:** `.kora-agent/kora-examples/kora-java-kafka/`

Error handling in Kafka consumers and producers.

## Consumer errors

### Deserialization errors

```java
@KafkaListener("kafka.consumer.listener")
void process(@Nullable String value, @Nullable Exception error) {
    if (error != null) {
        // Handle deserialization error
        log.error("Deserialization error", error);
        return;
    }
    // Normal processing
    log.info("Received: {}", value);
}
```

### Skipping a message (Skip)

```java
@KafkaListener("kafka.consumer.listener")
void process(String value) {
    if ("skip".equals(value)) {
        throw new KafkaSkipRecordException(new IllegalArgumentException("Want to skip!"));
    }
    // Normal processing
}
```

`KafkaSkipRecordException` signals the container to skip the current message and move on to the next one.

### Custom skippable exceptions

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

```java
@KafkaListener("kafka.consumer.listener")
void process(String value) {
    if (shouldSkip(value)) {
        throw new MySkipException("Business reason to skip");
    }
}
```

### Dead Letter Queue (DLQ)


```java
@Component
public final class DlqListener {
    private final DlqPublisher dlqPublisher;
    
    @KafkaListener("kafka.consumer.listener")
    void process(@Nullable String value, @Nullable Exception error) {
        if (error != null) {
            log.error("Processing error, sending to DLQ", error);
            dlqPublisher.send("dlq-topic", value, error.getMessage());
            return;
        }
        // Normal processing
    }
}
```

## Producer errors

### KafkaPublishException

```java
try {
    publisher.send("key", "value");
} catch (KafkaPublishException e) {
    log.error("Publish error", e.getCause());
    // Handle error
}
```

### SerializationException

```java
try {
    publisher.send("key", invalidObject);
} catch (SerializationException e) {
    log.error("Serialization error", e);
    // Handle error
}
```

## Rebalance handling

### ConsumerAwareRebalanceListener

```java
@Tag(MyListenerTag.class)
@Component
public final class MyRebalanceListener implements ConsumerAwareRebalanceListener {
    
    @Override
    public void onPartitionsRevoked(Consumer<?, ?> consumer, Collection<TopicPartition> partitions) {
        // Save offsets before rebalance
        log.info("Partitions revoked: {}", partitions);
        
        // Commit current offsets
        consumer.commitSync();
        
        // Clear caches, close resources
    }
    
    @Override
    public void onPartitionsAssigned(Consumer<?, ?> consumer, Collection<TopicPartition> partitions) {
        // Log newly assigned partitions
        log.info("Partitions assigned: {}", partitions);
        
        // Initialize state for new partitions
    }
    
    @Override
    public void onPartitionsLost(Consumer<?, ?> consumer, Collection<TopicPartition> partitions) {
        // Partitions lost (e.g., the consumer was evicted from the group)
        log.warn("Partitions lost: {}", partitions);
        
        // Clean up resources without committing
    }
}
```

## Retry logic

### Backoff configuration

```hocon
kafka {
  consumer {
    myListener {
      backoffTimeout = "15s"  # Pause between errors
    }
  }
}
```

### Manual retry

```java
@KafkaListener("kafka.consumer.listener")
void process(String value) {
    int maxRetries = 3;
    int attempt = 0;
    
    while (attempt < maxRetries) {
        try {
            processMessage(value);
            break;
        } catch (Exception e) {
            attempt++;
            if (attempt >= maxRetries) {
                log.error("Max retries exceeded", e);
                throw e;  // Skip or send to DLQ
            }
            log.warn("Retry {}/{}", attempt, maxRetries, e);
        }
    }
}
```

## Graceful Shutdown

```hocon
kafka {
  consumer {
    myListener {
      shutdownWait = "30s"  # Time to finish processing before shutdown
    }
  }
}
```

On SIGTERM the container:
1. Stops polling for new messages
2. Allows `shutdownWait` time to finish processing current messages
3. Commits offsets
4. Closes the consumer

## Best Practices

1. **Always handle deserialization errors** — use the signature with `@Nullable Exception`
2. **Use DLQ for bad messages** — don't lose data
3. **Log rebalance events** — to debug consumption issues
4. **Configure graceful shutdown** — for clean termination
5. **Monitor lag** — to detect consumption problems
