# Kafka Listener Reference

**Source:** [.kora-agent/kora-docs/mkdocs/docs/en/documentation/kafka.md](../../../.kora-agent/kora-docs/mkdocs/docs/en/documentation/kafka.md)

Complete reference for `@KafkaListener` method signatures and usage patterns.

## Contents

- [@KafkaListener Annotation](#kafkalistener-annotation)
- [Method Signatures](#method-signatures)
- [Signature Selection Table](#signature-selection-table)
- [Custom Tag on Listener](#custom-tag-on-listener)

---

## @KafkaListener Annotation

The `@KafkaListener` annotation creates a declarative Kafka consumer from a method.

```java
@Component
public final class MyService {
    
    @KafkaListener("kafka.consumer.myListener")
    void process(String value) {
        // Processing logic
    }
}
```

**Key points:**
- The annotation parameter specifies the configuration path in `application.conf`
- The method can have various signatures (see below)
- Kora generates the consumer container at compile time
- The listener is managed by the application lifecycle

---

## Method Signatures

### 1. Simple Value Processing

Auto-commits after each message.

```java
@KafkaListener("kafka.consumer.listener")
void process(String value) { }
```

**Use case:** Simple message processing without key access.

---

### 2. Key-Value Pair

Auto-commits after each message.

```java
@KafkaListener("kafka.consumer.listener")
void process(String key, String value) { }
```

**Use case:** Processing with access to message key.

---

### 3. With Headers

```java
@KafkaListener("kafka.consumer.listener")
void process(String key, String value, Headers headers) { }
```

**Use case:** Access to Kafka headers for correlation IDs, tracing.

---

### 4. ConsumerRecord (Full Access)

Access to metadata: topic, partition, offset, timestamp, headers.

```java
@KafkaListener("kafka.consumer.listener")
void process(ConsumerRecord<String, String> record) {
    log.info("Topic: {}, Partition: {}, Offset: {}",
        record.topic(), record.partition(), record.offset());
}
```

Auto-commits after each message.

**Use case:** Full metadata access for debugging, custom processing.

---

### 5. ConsumerRecords (Batch Processing)

Auto-commits after the entire batch.

```java
@KafkaListener("kafka.consumer.listener")
void process(ConsumerRecords<String, String> records) {
    log.info("Received {} records", records.count());
    for (ConsumerRecord<String, String> record : records) {
        // Process each message
    }
    // commitSync() called automatically after batch
}
```

**Use case:** High-throughput batch processing.

---

### 6. With Deserialization Error Handling

Both parameters become nullable — either event OR error is present.

```java
@KafkaListener("kafka.consumer.listener")
void process(@Nullable String value, @Nullable Exception error) {
    if (error != null) {
        log.error("Deserialization error", error);
        return;
    }
    // Normal processing
    log.info("Received: {}", value);
}
```

**Use case:** Handling deserialization errors gracefully.

---

### 7. With Manual Commit

```java
@KafkaListener("kafka.consumer.listener")
void process(ConsumerRecord<String, String> record, Consumer<String, String> consumer) {
    // Processing
    saveToDatabase(record.value());
    consumer.commitSync();  // Manual commit
}
```

**Use case:** Exactly-once semantics, sync with DB transactions.

---

### 8. With Telemetry Context

The telemetry context types are nested inside `KafkaConsumerTelemetry` — use the
parameterized nested type:

```java
import ru.tinkoff.kora.kafka.common.consumer.telemetry.KafkaConsumerTelemetry;

@KafkaListener("kafka.consumer.listener")
void process(ConsumerRecord<String, String> record,
             KafkaConsumerTelemetry.KafkaConsumerRecordTelemetryContext<String, String> ctx) {
    // Access to telemetry context for this record
}
```

For the batch signature, use `KafkaConsumerTelemetry.KafkaConsumerRecordsTelemetryContext<K, V>`
and call `ctx.get(record)` per record, then `close(null)`.

**Use case:** Custom telemetry integration.

---

## Signature Selection Table

| Signature | Commit | Use Case |
|-----------|--------|----------|
| `void process(String value)` | Auto, per message | Simple processing |
| `void process(String key, String value)` | Auto, per message | Key-aware processing |
| `void process(String key, String value, Headers headers)` | Auto, per message | Correlation/tracing |
| `void process(ConsumerRecord<K, V> record)` | Auto, per message | Full metadata access |
| `void process(ConsumerRecords<K, V> records)` | Auto, per batch | Batch processing |
| `void process(..., Consumer<K, V> consumer)` | Manual | Exactly-once semantics |
| `void process(@Nullable T, @Nullable Exception)` | Auto, per message | Error handling |

---

## Custom Tag on Listener

Override the auto-generated tag:

```java
@Component
public final class ConsumerService {

    @KafkaListener(value = "kafka.someConsumer", tag = ConsumerService.class)
    public void process(String value) {
        // Handler code
    }
}
```

---

## Related References

- [Kafka Serialization Reference](kafka-serialization-reference.md) — @Json, custom deserializers
- [Kafka Error Handling Reference](kafka-error-handling-reference.md) — DLQ, skip exceptions
- [Kafka Consumer Reference](kafka-consumer-reference.md) — Configuration options
