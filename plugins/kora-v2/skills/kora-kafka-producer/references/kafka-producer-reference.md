# Kafka Producer Reference

**Source:** [../../../.kora-agent/kora-docs/mkdocs/docs/en/documentation/kafka.md](../../../.kora-agent/kora-docs/mkdocs/docs/en/documentation/kafka.md)

Complete reference for Kafka producers in Kora.

## Contents

- [@KafkaPublisher annotation](#kafkapublisher-annotation)
- [Method signatures](#method-signatures)
- [Configuration](#configuration)
- [Configuration recommendations](#configuration-recommendations)
- [Producer injection](#producer-injection)

## Quick Navigation

- [Serialization](kafka-serialization-reference.md) — JSON, @Json, @Tag serializers
- [Error Handling](kafka-error-handling-reference.md) — Exceptions, retry, DLQ patterns
- [Transactions](kafka-transactions-reference.md) — TransactionalPublisher, atomic sends

## @KafkaPublisher annotation

Placed on an interface to create a typed producer. The annotation value is the
config path for the producer.

```java
import ru.tinkoff.kora.kafka.common.annotation.KafkaPublisher;
import ru.tinkoff.kora.kafka.common.annotation.KafkaPublisher.Topic;

@KafkaPublisher("kafka.producer.myPublisher")
public interface MyPublisher {
    @Topic("kafka.producer.myTopic")
    void send(String value);
}
```

`@Topic` is the nested annotation `@KafkaPublisher.Topic`. Import the nested
type to write `@Topic`, or write `@KafkaPublisher.Topic` in full — both refer to
the same annotation.

## Method signatures

### 1. Basic send

```java
@KafkaPublisher("kafka.producer.myPublisher")
public interface MyPublisher {
    @Topic("kafka.producer.myTopic")
    void send(String value);
}
```

### 2. With key

```java
@Topic("kafka.producer.myTopic")
void send(String key, String value);
```

### 3. With headers

```java
@Topic("kafka.producer.myTopic")
void send(String key, String value, Headers headers);
```

### 4. With RecordMetadata return

```java
@Topic("kafka.producer.myTopic")
RecordMetadata sendWithMeta(String value);
```

### 5. Async with Future

```java
@Topic("kafka.producer.myTopic")
Future<RecordMetadata> sendAsync(String value);
```

### 6. Async with CompletionStage

```java
@Topic("kafka.producer.myTopic")
CompletionStage<RecordMetadata> sendStage(String value);
```

### 7. ProducerRecord

```java
@KafkaPublisher("kafka.producer.myPublisher")
public interface MyPublisher {
    void send(ProducerRecord<String, String> record);
    void send(ProducerRecord<String, String> record, Callback callback);
}
```

### 8. Kotlin suspend

```kotlin
@KafkaPublisher("kafka.producer.myPublisher")
interface MyPublisher {
    @Topic("kafka.producer.myTopic")
    suspend fun send(value: String): RecordMetadata
}
```

## Configuration

The `@KafkaPublisher` value and each `@Topic` value are full config paths. A
typical layout keeps the producer section and the topic section as siblings
under `kafka.producer`, matching the paths used in the annotations:

### Basic producer configuration

```hocon
kafka {
  producer {
    # matches @KafkaPublisher("kafka.producer.myPublisher")
    myPublisher {
      # Kafka driver properties (required)
      driverProperties {
        "bootstrap.servers" = "localhost:9093"
        "acks" = "all"
        "retries" = 3
        "linger.ms" = 5
        "batch.size" = 16384
        "buffer.memory" = 33554432
      }
    }

    # matches @Topic("kafka.producer.myTopic")
    myTopic {
      topic = "my-topic-name"
      partition = 0  # optional
    }
  }
}
```

### Driver Properties

Standard Kafka producer properties:

```hocon
driverProperties {
  "bootstrap.servers" = "localhost:9093"
  "acks" = "all"           # 0, 1, all
  "retries" = 3
  "retry.backoff.ms" = 100
  "linger.ms" = 5
  "batch.size" = 16384
  "buffer.memory" = 33554432
  "compression.type" = "snappy"  # none, gzip, snappy, lz4, zstd
  "max.in.flight.requests.per.connection" = 5
}
```

### Topic configuration

The topic section (described by `KafkaPublisherConfig.TopicConfig`) is resolved
from the `@Topic` path. `topic` is required; `partition` is optional.

```hocon
kafka {
  producer {
    myTopic {
      topic = "my-topic-name"
      partition = 0  # optional, to explicitly target a partition
    }
  }
}
```

## Configuration recommendations

### Reliability (acks=all)

```hocon
driverProperties {
  "acks" = "all"
  "retries" = 2147483647  # Max int
  "min.insync.replicas" = 2
}
```

### Performance (acks=1)

```hocon
driverProperties {
  "acks" = 1
  "linger.ms" = 20
  "batch.size" = 65536
  "compression.type" = "lz4"
}
```

### Low latency (acks=0)

```hocon
driverProperties {
  "acks" = 0
  "linger.ms" = 0
  "max.in.flight.requests.per.connection" = 10
}
```

## Producer injection

```java
@Component
public final class MyService {
    private final MyPublisher publisher;
    
    public MyService(MyPublisher publisher) {
        this.publisher = publisher;
    }
    
    public void doSomething() {
        publisher.send("key", "value");
    }
}
```
