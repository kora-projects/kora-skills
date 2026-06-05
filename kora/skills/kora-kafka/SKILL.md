---
name: kora-kafka
description: Apache Kafka integration in Kora: @KafkaListener for declarative consumers, @KafkaPublisher for typed producers, JSON serialization via @Json, error handling, rebalance listeners, transactional publishers, and telemetry (metrics, tracing, logging). Use when building event-driven microservices with Kafka. Triggers: @KafkaListener, @KafkaPublisher, Kafka consumers, Kafka producers, event-driven architecture, Kafka serialization, transactional messaging.
---

# Kora Kafka — Apache Kafka integration in Kora applications

Read this first when:
- creating Kafka consumers with `@KafkaListener` for message processing,
- creating Kafka producers with `@KafkaPublisher` for typed message publishing,
- configuring JSON serialization/deserialization for Kafka messages,
- implementing event-driven architectures (Event Sourcing, CQRS, Saga, Outbox),
- setting up transactional message publishing with exactly-once semantics,
- handling rebalance events and configuring error handling strategies.

## Purpose

Skill for working with Apache Kafka in Kora: `@KafkaListener` for declarative consumers | `@KafkaPublisher` for typed producers | configuration via HOCON/YAML | JSON serialization via `@Json` | error handling and rebalance events | transactional publishers | telemetry (metrics, tracing, logging).

**When to use:**
- When building event-driven microservices
- For integrating with Kafka topics (read/write)
- When implementing patterns: Event Sourcing, CQRS, Saga, Outbox
- For asynchronous communication between services

---

## Quick Start

### 1. Adding the dependency

```groovy
dependencies {
    koraBom platform("ru.tinkoff.kora:kora-parent:$koraVersion")
    annotationProcessor "ru.tinkoff.kora:annotation-processors"
    
    implementation "ru.tinkoff.kora:kafka"
    implementation "ru.tinkoff.kora:json-module"  // for JSON serialization
    implementation "ru.tinkoff.kora:config-hocon"  // or config-yaml
}
```

### 2. Connecting the module

```java
@KoraApp
public interface Application extends HoconConfigModule, JsonModule, KafkaModule {
    
    static void main(String[] args) {
        KoraApplication.run(ApplicationGraph::graph);
    }
}
```

### 3. Configuration

```hocon
kafka {
  consumer {
    my-listener {
      topics = ["my-topic"]
      pollTimeout = "5s"
      threads = 1
      driverProperties {
        "bootstrap.servers" = ${KAFKA_BOOTSTRAP_SERVERS}
        "group.id" = "my-consumer-group"
        "auto.offset.reset" = "latest"
      }
    }
  }
  producer {
    my-publisher {
      driverProperties {
        "bootstrap.servers" = ${KAFKA_BOOTSTRAP_SERVERS}
      }
      my-topic {
        topic = "my-topic"
      }
    }
  }
}
```

### 4. Consumer (message processing)

```java
@Component
public final class MyMessageListener {
    
    @KafkaListener("kafka.consumer.my-listener")
    void process(String value) {
        log.info("Received: {}", value);
    }
}
```

### 5. Producer (sending messages)

```java
@KafkaPublisher("kafka.producer.my-publisher")
public interface MyMessagePublisher {
    
    @KafkaPublisher.Topic("kafka.producer.my-topic")
    void send(String value);
    
    @KafkaPublisher.Topic("kafka.producer.my-topic")
    void send(String key, String value);
}
```

---

## Consumer (Receiving Messages)

### @KafkaListener annotation

`@KafkaListener` is placed on a method to create a Kafka consumer. The parameter specifies the path to the configuration.

```java
@Component
public final class MyService {
    
    @KafkaListener("kafka.consumer.myListener")
    void process(String key, String value) { }
    
    @KafkaListener("kafka.consumer.anotherListener")
    void processAnother(ConsumerRecord<String, String> record) { }
}
```

### Consumption strategies

**Subscribe strategy** (with `group.id`):
- Messages are distributed among application instances
- Each topic is read by only one instance in the group

```hocon
kafka {
  consumer {
    mySubscriber {
      topics = ["my-topic"]
      driverProperties {
        "group.id" = "my-group-id"  # Required for subscribe
        "bootstrap.servers" = "localhost:9093"
      }
    }
  }
}
```

**Assign strategy** (without `group.id`):
- Each instance reads all messages from the topic
- Use for broadcast scenarios

```hocon
kafka {
  consumer {
    myAssigner {
      topics = ["my-topic"]
      driverProperties {
        "bootstrap.servers" = "localhost:9093"
        # group.id NOT set — this is the assign strategy
      }
    }
  }
}
```

### Available method signatures

| Signature | Description |
|-----------|-------------|
| `void process(String value)` | Basic processing |
| `void process(String key, String value)` | Key-value pair |
| `void process(ConsumerRecord<K,V> record)` | Full access to metadata |
| `void process(ConsumerRecords<K,V> records)` | Batch processing |
| `void process(String value, Exception ex)` | With error handling |
| `void process(ConsumerRecord, Consumer)` | With manual commit |

**Examples:** [references/kafka-consumer-reference.md](references/kafka-consumer-reference.md#available-method-signatures)

### JSON deserialization

Use `@Json` for automatic deserialization of JSON into POJOs:

```java
@Component
public final class JsonMessageListener {
    
    @Json
    public record MyEvent(String name, Integer code, Instant timestamp) {}
    
    @KafkaListener("kafka.consumer.jsonListener")
    void process(String key, @Json MyEvent event) {
        log.info("Event: {} = {}", key, event);
    }
}
```

### Error handling

**Skipping a message:**

```java
@KafkaListener("kafka.consumer.listener")
void process(String value) {
    if ("skip".equals(value)) {
        throw new KafkaSkipRecordException(new IllegalArgumentException("Want to skip!"));
    }
}
```

**Handling deserialization errors:**

```java
@KafkaListener("kafka.consumer.listener")
void process(@Nullable String value, @Nullable RecordValueDeserializationException ex) {
    if (ex != null) {
        log.error("Bad message", ex);
    } else {
        // Normal processing
    }
}
```

### Rebalance events

To react to rebalance events, implement `ConsumerAwareRebalanceListener`:

```java
@Tag(MyListenerTag.class)
@Component
public final class MyRebalanceListener implements ConsumerAwareRebalanceListener {
    
    @Override
    public void onPartitionsRevoked(Consumer<?, ?> consumer, Collection<TopicPartition> partitions) {
        log.info("Partitions revoked: {}", partitions);
    }
    
    @Override
    public void onPartitionsAssigned(Consumer<?, ?> consumer, Collection<TopicPartition> partitions) {
        log.info("Partitions assigned: {}", partitions);
    }
}
```

**More details:** [references/kafka-consumer-reference.md](references/kafka-consumer-reference.md) | [references/kafka-error-handling-reference.md](references/kafka-error-handling-reference.md)

---

## Producer (Sending Messages)

### Method signatures

```java
@KafkaPublisher("kafka.producer.myPublisher")
public interface MyPublisher {
    void send(String value);                    // Basic
    void send(String key, String value);        // With key
    RecordMetadata sendWithMeta(String value);  // With metadata
    Future<RecordMetadata> sendAsync(String value);  // Async
    void send(ProducerRecord<String, String> record);  // ProducerRecord
}
```

### JSON serialization

```java
@KafkaPublisher("kafka.producer.myPublisher")
public interface EventPublisher {
    
    @Json
    record MyEvent(String name, Integer code, Instant timestamp) {}
    
    @KafkaPublisher.Topic("kafka.producer.events")
    void send(@Json MyEvent event);
    
    @KafkaPublisher.Topic("kafka.producer.events")
    void send(String key, @Json MyEvent event);
}
```

**More details:** [references/kafka-producer-reference.md](references/kafka-producer-reference.md) | [references/kafka-serialization-reference.md](references/kafka-serialization-reference.md)

---

## Transactional Publishers

To send messages within a transaction, use `TransactionalPublisher`:

```java
@KafkaPublisher("kafka.producer.myTransactionalPublisher")
public interface MyTransactionalPublisher extends TransactionalPublisher<MyPublisher> {}
```

**Usage:**

```java
private final MyTransactionalPublisher txPublisher;

public void sendInTransaction() {
    txPublisher.inTx(p -> {
        p.send("key1", "value1");
        p.send("key2", "value2");
    });
}
```

**Configuration:**

```hocon
kafka {
  producer {
    myTransactionalPublisher {
      idPrefix = "my-app-"
      maxPoolSize = 10
      maxWaitTime = "10s"
      driverProperties { "bootstrap.servers" = "localhost:9093" }
    }
  }
}
```

**More details:** [references/kafka-transactions-reference.md](references/kafka-transactions-reference.md)

---

## Configuration

### Consumer configuration

```hocon
kafka {
  consumer {
    myListener {
      topics = ["topic1"]
      pollTimeout = "5s"
      threads = 1
      driverProperties {
        "bootstrap.servers" = ${KAFKA_BOOTSTRAP_SERVERS}
        "group.id" = "my-group-id"
        "auto.offset.reset" = "latest"
      }
    }
  }
}
```

### Producer configuration

```hocon
kafka {
  producer {
    myPublisher {
      driverProperties {
        "bootstrap.servers" = ${KAFKA_BOOTSTRAP_SERVERS}
        "acks" = "all"
      }
      myTopic { topic = "my-topic-name" }
    }
  }
}
```

**More details:** [references/kafka-consumer-reference.md](references/kafka-consumer-reference.md) | [references/kafka-producer-reference.md](references/kafka-producer-reference.md)

---

## Tags for serializers

For custom serializers, use `@Tag`:

```java
@Component
public final class TaggedListener {
    
    @KafkaListener("kafka.consumer.listener1")
    void process(@Tag(MyKeyTag.class) String key, @Tag(MyValueTag.class) String value) { }
}

@KafkaPublisher("kafka.producer.publisher")
public interface TaggedPublisher {
    
    @KafkaPublisher.Topic("kafka.producer.topic")
    void send(@Tag(MyKeyTag.class) String key, @Tag(MyValueTag.class) String value);
}
```

---

## Telemetry

The Kafka module automatically exports metrics and tracing via Micrometer and OpenTelemetry:

**Consumer metrics:** `kafka_consumer_records_consumed_total`, `kafka_consumer_records_lag`, `kafka_consumer_poll_duration`
**Producer metrics:** `kafka_producer_records_sent_total`, `kafka_producer_send_duration`
**Tracing:** Distributed tracing with propagation via headers (consumer/producer spans)
**Logging:** Enable via `telemetry.logging.enabled = true`
**More details:** [references/kafka-telemetry-reference.md](references/kafka-telemetry-reference.md)

---

## Testing

> **💡 Tip:** Use the ready-made test templates from `assets/`:
> - `ConsumerListenerTests.java.template` / `.kt.template` — consumer tests
> - `MessagePublisherTests.java.template` / `.kt.template` — producer tests
> 
> Templates include: @TestcontainersKafka, @KoraAppTest, @ConnectionKafka, Awaitility assertions.

**Quick start with a template:**

```bash
# Generate consumer with test
python kora-kafka/scripts/generate_consumer.py --name MyListener --topics my-topic

# Generate producer with test
python kora-kafka/scripts/generate_producer.py --name MyPublisher --topics my-topic
```

**More details:** [references/kafka-testing-reference.md](references/kafka-testing-reference.md)

---

## Common Errors

| Problem | Solution |
|---------|----------|
| Consumer does not start | Check `threads > 0` and `@Root` for long-running components |
| Messages are not committed | Use the signature with `Consumer` for manual commit |
| Message duplication | Set `enable.auto.commit = false` and commit after processing |
| Serialization errors | Use the `@Nullable Exception` parameter for handling |
| Producer blocks | Configure `acks`, `retries`, `linger.ms` correctly |
| Transactions do not work | Ensure `transactional.id` is unique for each instance |

---

## Assets

| File | Description |
|------|-------------|
| `build.gradle.template` | Gradle configuration with kafka dependency and tests |
| `Application.java.template` | Application interface with KafkaModule |
| `application.conf.template` | Example of full consumer/producer configuration |
| `ConsumerListener.java.template` | Consumer template with various method signatures |
| `MessagePublisher.java.template` | Producer template with typed methods |
| `JsonMessageListener.java.template` | Consumer with JSON deserialization |
| `JsonMessagePublisher.java.template` | Producer with JSON serialization |
| `TransactionalPublisher.java.template` | Transactional publisher |
| `ConsumerListenerTests.java.template` | Consumer tests with Testcontainers |
| `ConsumerListenerTests.kt.template` | Consumer tests (Kotlin) |
| `MessagePublisherTests.java.template` | Producer tests with Testcontainers |
| `MessagePublisherTests.kt.template` | Producer tests (Kotlin) |

---

## Reference Files

| File | Description |
|------|-------------|
| [references/kafka-consumer-reference.md](references/kafka-consumer-reference.md) | Complete reference for Kafka consumers |
| [references/kafka-producer-reference.md](references/kafka-producer-reference.md) | Complete reference for Kafka producers |
| [references/kafka-serialization-reference.md](references/kafka-serialization-reference.md) | JSON serialization/deserialization |
| [references/kafka-transactions-reference.md](references/kafka-transactions-reference.md) | Transactional publishers |
| [references/kafka-telemetry-reference.md](references/kafka-telemetry-reference.md) | Metrics, tracing, logging |
| [references/kafka-error-handling-reference.md](references/kafka-error-handling-reference.md) | Error handling and rebalance |
| [references/kafka-testing-reference.md](references/kafka-testing-reference.md) | Testing with Testcontainers |

---

## Scripts

```bash
# Validate configuration
python kora-kafka/scripts/validate_config.py --config application.conf

# Generate templates
python kora-kafka/scripts/generate_consumer.py --name MyListener --topics my-topic
python kora-kafka/scripts/generate_producer.py --name MyPublisher --topics my-topic
```

---

## Related skills

- **[kora-json](../kora-json/SKILL.md)** — JSON serialization for Kafka messages
- **[kora-telemetry](../kora-telemetry/SKILL.md)** — Observability (metrics, tracing, logging)
- **[kora-config](../kora-bootstrap/SKILL.md)** — HOCON/YAML configuration

---

## Common Pitfalls

- **Missing `@KafkaListener` or `@Component`** → consumer not discovered. Both required.
- **Wrong deserializer** → match `keyDeserializer`/`valueDeserializer` to actual data format.
- **Missing `@Tag` for multiple listeners** → tag listeners consuming same topic with different groups.
- **Publisher without `@Component`** → generated publishers need `@Component`.
- **No error handling** → implement `ErrorHandler` or use `errorHandler` config for failed messages.
- **Transaction without `enableIdempotence`** → enable for exactly-once semantics.
