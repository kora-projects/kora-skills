# Kafka Serialization Reference

**Source:** [.kora-agent/kora-docs/mkdocs/docs/en/documentation/kafka.md](../../../.kora-agent/kora-docs/mkdocs/docs/en/documentation/kafka.md)  
**Examples:** [.kora-agent/kora-examples/kora-java-kafka/](../../../.kora-agent/kora-examples/examples/java/kora-java-kafka/)

Serialization and deserialization patterns for Kafka messages in Kora.

## Contents

- [JSON Serialization with @Json](#json-serialization-with-json)
- [Custom Deserializers](#custom-deserializers)
- [Custom Serializers (Producer)](#custom-serializers-producer)
- [String Deserialization](#string-deserialization)
- [Byte Array Deserialization](#byte-array-deserialization)
- [Deserialization Error Handling](#deserialization-error-handling)
- [Configuration](#configuration)
- [Best Practices](#best-practices)

---

## JSON Serialization with @Json

### Basic JSON Deserialization

Use `@Json` for automatic JSON (de)serialization.

```java
@Component
public final class UserEventListener {
    
    @Json
    public record UserEvent(String userId, String eventType, LocalDateTime timestamp) {}
    
    @KafkaListener("kafka.consumer.userEvents")
    void process(@Json UserEvent event) {
        log.info("User {} performed {}", event.userId(), event.eventType());
    }
}
```

### JSON with Key-Value

```java
@KafkaListener("kafka.consumer.userEvents")
void process(String key, @Json UserEvent event) {
    log.info("Key: {}, Event: {}", key, event);
}
```

### JSON with ConsumerRecord

```java
@KafkaListener("kafka.consumer.userEvents")
void process(ConsumerRecord<String, @Json UserEvent> record) {
    log.info("Received: {}", record.value());
}
```

### JSON with ConsumerRecords (Batch)

```java
@KafkaListener("kafka.consumer.userEvents")
void process(ConsumerRecords<String, @Json UserEvent> records) {
    for (ConsumerRecord<String, UserEvent> record : records) {
        log.info("Processing: {}", record.value());
    }
}
```

---

## Custom Deserializers

### Implementing Deserializer

Create a custom deserializer by implementing `org.apache.kafka.common.serialization.Deserializer`.

```java
@Component
public final class CustomDeserializerListener {
    
    @Json
    public record MyEvent(String username, int code) {}
    
    @Tag(MyEvent.class)
    @Component
    public static class MyDeserializer implements Deserializer<MyEvent> {
        
        private final JsonReader<MyEvent> reader;
        
        public MyDeserializer(JsonReader<MyEvent> reader) {
            this.reader = reader;
        }
        
        @Override
        public MyEvent deserialize(String topic, byte[] data) {
            try {
                return reader.read(data);
            } catch (IOException e) {
                throw new IllegalArgumentException("Failed to deserialize", e);
            }
        }
    }
    
    @KafkaListener("kafka.consumer.custom")
    void process(@Tag(MyEvent.class) MyEvent value) {
        log.info("Received custom event: {}", value);
    }
}
```

### Using @Tag Annotation

The `@Tag` annotation specifies which deserializer to use.

```java
@KafkaListener("kafka.consumer.listener")
void process(@Tag(SomeTag1.class) String key, @Tag(SomeTag2.class) String value) {
    // Custom deserializers for key and value
}
```

### Tag on ConsumerRecord

```java
@KafkaListener("kafka.consumer.listener")
void process(ConsumerRecord<@Tag(SomeTag1.class) String, @Tag(SomeTag2.class) String> record) {
    // Custom deserializers
}
```

---

## Custom Serializers (Producer)

### Implementing Serializer

```java
@Component
public final class CustomSerializerPublisher {
    
    @Json
    public record MyEvent(String username, int code) {}
    
    @Tag(MyEvent.class)
    @Component
    public static class MySerializer implements Serializer<MyEvent> {
        
        private final JsonWriter<MyEvent> writer;
        
        public MySerializer(JsonWriter<MyEvent> writer) {
            this.writer = writer;
        }
        
        @Override
        public byte[] serialize(String topic, MyEvent data) {
            if (data == null) {
                return null;
            }
            try {
                return writer.write(data);
            } catch (IOException e) {
                throw new IllegalArgumentException("Failed to serialize", e);
            }
        }
    }
    
    @KafkaPublisher("kafka.customPublisher")
    interface CustomPublisher {
        @KafkaPublisher.Topic("kafka.customPublisher.topic")
        void send(@Tag(MyEvent.class) MyEvent event);
    }
}
```

---

## String Deserialization

### Default String Deserializer

For simple string messages, no special configuration is needed:

```java
@KafkaListener("kafka.consumer.listener")
void process(String value) {
    log.info("Received: {}", value);
}
```

Kora uses `StringDeserializer` by default for `String` parameters.

---

## Byte Array Deserialization

### Raw Bytes

For raw byte arrays:

```java
@KafkaListener("kafka.consumer.listener")
void process(byte[] value) {
    log.info("Received {} bytes", value.length);
}
```

---

## Deserialization Error Handling

### Nullable Pattern

```java
@KafkaListener("kafka.consumer.listener")
void process(@Nullable @Json MyEvent event, @Nullable Exception error) {
    if (error != null) {
        log.error("Deserialization failed", error);
        return;
    }
    // Process event
}
```

### Exception Types

- `RecordKeyDeserializationException` - key deserialization failed
- `RecordValueDeserializationException` - value deserialization failed

Both provide `getRecord()` to access the original `ConsumerRecord<byte[], byte[]>`.

### Handling Deserialization Exceptions

```java
@KafkaListener("kafka.consumer.listener")
void process(ConsumerRecord<String, String> record) {
    try {
        String value = record.value();
        log.info("Received: {}", value);
    } catch (RecordValueDeserializationException e) {
        log.error("Value deserialization failed", e);
        ConsumerRecord<byte[], byte[]> raw = e.getRecord();
        // Handle raw bytes (e.g., send to DLQ)
    }
}
```

---

## Configuration

### Kafka Driver Properties for Serialization

```hocon
kafka {
  consumer {
    myListener {
      topics = ["my-topic"]
      driverProperties {
        "bootstrap.servers" = "localhost:9092"
        "group.id" = "my-group"
        
        # String deserializer
        "key.deserializer" = "org.apache.kafka.common.serialization.StringDeserializer"
        "value.deserializer" = "org.apache.kafka.common.serialization.StringDeserializer"
        
        # Or custom deserializer
        # "value.deserializer" = "com.example.MyCustomDeserializer"
      }
    }
  }
}
```

---

## Best Practices

### 1. Use @Json for Complex Objects

```java
@Json
public record MyEvent(String id, String name, LocalDateTime timestamp) {}

@KafkaListener("kafka.consumer.events")
void process(@Json MyEvent event) {
    // Automatic JSON deserialization
}
```

### 2. Use @Tag for Custom Deserializers

```java
@Tag(MyEvent.class)
@Component
public static class MyDeserializer implements Deserializer<MyEvent> {
    // Custom logic
}

@KafkaListener("kafka.consumer.custom")
void process(@Tag(MyEvent.class) MyEvent event) {
    // Uses custom deserializer
}
```

### 3. Handle Deserialization Errors

Always handle deserialization errors explicitly:

```java
@KafkaListener("kafka.consumer.listener")
void process(@Nullable @Json MyEvent event, @Nullable Exception error) {
    if (error != null) {
        log.error("Deserialization failed", error);
        // Handle error
        return;
    }
    // Process event
}
```

### 4. Use Raw Bytes for DLQ

When sending failed messages to DLQ, preserve the raw bytes:

```java
catch (RecordValueDeserializationException e) {
    ConsumerRecord<byte[], byte[]> raw = e.getRecord();
    dlqPublisher.send("dlq-topic", raw.key(), raw.value(), e.getMessage());
}
```

---

## Related References

- [Kafka Consumer Reference](kafka-consumer-reference.md)
- [Kafka Error Handling Reference](kafka-error-handling-reference.md)
- [Kafka Producer Reference](../../kora-kafka-producer/references/kafka-producer-reference.md)
