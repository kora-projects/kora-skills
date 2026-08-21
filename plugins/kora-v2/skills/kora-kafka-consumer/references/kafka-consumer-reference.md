# Kafka Consumer Reference

**Source:** [.kora-agent/kora-docs/mkdocs/docs/en/documentation/kafka.md](../../../.kora-agent/kora-docs/mkdocs/docs/en/documentation/kafka.md)  
**Examples:** [.kora-agent/kora-examples/kora-java-kafka/](../../../.kora-agent/kora-examples/examples/java/kora-java-kafka/)

Complete reference for Kafka consumers in Kora Framework.

## Contents

- [@KafkaListener Annotation](#kafkalistener-annotation)
- [Consumption Strategies](#consumption-strategies)
- [Method Signatures](#method-signatures)
- [Configuration](#configuration)
- [Offset Strategies](#offset-strategies)
- [Multi-Threaded Processing](#multi-threaded-processing)
- [Telemetry Configuration](#telemetry-configuration)
- [Graceful Shutdown](#graceful-shutdown)
- [Full Configuration Example](#full-configuration-example)

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

## Consumption Strategies

### Subscribe Strategy (with group.id)

Messages are distributed among instances in the consumer group.

```hocon
kafka {
  consumer {
    mySubscriber {
      topics = ["my-topic"]
      driverProperties {
        "group.id" = "my-group-id"
        "bootstrap.servers" = "localhost:9093"
      }
    }
  }
}
```

**Characteristics:**
- Each topic is read by only one instance in the group
- Scale horizontally by adding instances
- Use for task-queue processing
- Recommended for most use cases

### Assign Strategy (without group.id)

Each instance reads all messages from the topic.

```hocon
kafka {
  consumer {
    myAssigner {
      topics = ["my-topic"]
      driverProperties {
        "bootstrap.servers" = "localhost:9093"
        # group.id NOT set
      }
    }
  }
}
```

**Characteristics:**
- Messages are duplicated across all instances
- Only one topic at a time
- Use for broadcast/pub-sub scenarios
- No consumer group coordination

---

## Method Signatures

### 1. Simple Value Processing

Auto-commits after each message.

```java
@KafkaListener("kafka.consumer.listener")
void process(String value) { }
```

### 2. Key-Value Pair

Auto-commits after each message.

```java
@KafkaListener("kafka.consumer.listener")
void process(String key, String value) { }
```

### 3. With Headers

```java
@KafkaListener("kafka.consumer.listener")
void process(String key, String value, Headers headers) { }
```

### 4. ConsumerRecord (Full Access)

Access to metadata: topic, partition, offset, timestamp, headers.

```java
@KafkaListener("kafka.consumer.listener")
void process(ConsumerRecord<String, String> record) {
    log.info("Topic: {}, Partition: {}, Offset: {}",
        record.topic(), record.partition(), record.offset());
}
```

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

### 6. With Deserialization Error Handling

Both parameters become nullable - either event OR error is present.

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

### 7. With Manual Commit

```java
@KafkaListener("kafka.consumer.listener")
void process(ConsumerRecord<String, String> record, Consumer<String, String> consumer) {
    // Processing
    saveToDatabase(record.value());
    consumer.commitSync();  // Manual commit
}
```

### 8. With Telemetry Context

```java
import ru.tinkoff.kora.kafka.common.consumer.telemetry.KafkaConsumerTelemetry;

@KafkaListener("kafka.consumer.listener")
void process(ConsumerRecord<String, String> record,
             KafkaConsumerTelemetry.KafkaConsumerRecordTelemetryContext<String, String> ctx) {
    // Access to telemetry context
}
```

---

## Configuration

### Required Parameters

```hocon
kafka {
  consumer {
    myListener {
      # Topics (either topics or topicsPattern is required)
      topics = ["topic1"]
      # OR
      topicsPattern = "topic-*"
      
      # Kafka driver properties (required)
      driverProperties {
        "bootstrap.servers" = "localhost:9093"
      }
    }
  }
}
```

### Optional Parameters

| Parameter | Description | Default |
|-----------|-------------|---------|
| `topics` | List of topics to subscribe to | - |
| `topicsPattern` | Pattern for topic subscription | - |
| `allowEmptyRecords` | Process empty ConsumerRecords | `false` |
| `offset` | Starting position: `earliest`, `latest`, or Duration | `latest` |
| `pollTimeout` | Max time waiting for messages in poll() | `5s` |
| `backoffTimeout` | Pause after unexpected exception | `15s` |
| `partitionRefreshInterval` | Partition refresh interval (assign mode) | `1m` |
| `threads` | Number of parallel processing threads | `1` |
| `shutdownWait` | Graceful shutdown timeout | `30s` |

### Driver Properties

Standard Kafka consumer properties from [Apache Kafka documentation](https://kafka.apache.org/documentation/#consumerconfigs):

```hocon
driverProperties {
  "bootstrap.servers" = "localhost:9092"
  "group.id" = "my-group"
  "auto.offset.reset" = "latest"
  "enable.auto.commit" = true
  "max.poll.records" = 500
  "session.timeout.ms" = 30000
  "heartbeat.interval.ms" = 10000
  "fetch.min.bytes" = 1
  "fetch.max.wait.ms" = 500
  "key.deserializer" = "org.apache.kafka.common.serialization.StringDeserializer"
  "value.deserializer" = "org.apache.kafka.common.serialization.StringDeserializer"
}
```

---

## Offset Strategies

### earliest

Start from the earliest available offset.

```hocon
offset = "earliest"
```

### latest

Start from the latest offset (new messages only).

```hocon
offset = "latest"
```

### Duration-based

Start from the offset at a specific time in the past.

```hocon
offset = "5m"   # 5 minutes ago
offset = "1h"   # 1 hour ago
offset = "24h"  # 24 hours ago
```

This works only if `group.id` is not specified (i.e., no committed offsets exist).

---

## Multi-Threaded Processing

```hocon
kafka {
  consumer {
    myListener {
      threads = 4  # 4 parallel threads for processing
      topics = ["my-topic"]
      driverProperties {
        "bootstrap.servers" = "localhost:9092"
        "group.id" = "my-group"
      }
    }
  }
}
```

**Important:**
- Each thread gets its own consumer instance
- Messages are distributed across threads
- Use for CPU-intensive processing

---

## Telemetry Configuration

### Logging

```hocon
telemetry {
  logging {
    enabled = true
  }
}
```

### Metrics

```hocon
telemetry {
  metrics {
    enabled = true
    slo = [1, 10, 50, 100, 200, 500, 1000, 2000, 5000, 10000]  # Latency buckets in ms
    tags = {
      "consumer-type" = "user-events"
      "environment" = "production"
    }
  }
}
```

### Tracing

```hocon
telemetry {
  tracing {
    enabled = true
    attributes = {
      "service.name" = "user-service"
    }
  }
}
```

---

## Graceful Shutdown

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
3. Commits offsets
4. Closes the consumer

---

## Full Configuration Example

```hocon
kafka {
  consumer {
    myListener {
      # Topics
      topics = ["topic1", "topic2"]
      # OR
      # topicsPattern = "topic-*"
      
      # Behavior
      allowEmptyRecords = false
      offset = "latest"
      pollTimeout = "5s"
      backoffTimeout = "15s"
      partitionRefreshInterval = "1m"
      threads = 1
      shutdownWait = "30s"
      
      # Driver properties
      driverProperties {
        "bootstrap.servers" = "localhost:9092"
        "group.id" = "my-group"
        "auto.offset.reset" = "earliest"
        "enable.auto.commit" = true
        "max.poll.records" = 500
        "session.timeout.ms" = 30000
        "heartbeat.interval.ms" = 10000
      }
      
      # Telemetry
      telemetry {
        logging {
          enabled = true
        }
        metrics {
          enabled = true
          slo = [1, 10, 50, 100, 200, 500, 1000, 2000, 5000, 10000]
          tags = {
            "key1" = "value1"
            "key2" = "value2"
          }
        }
        tracing {
          enabled = true
          attributes = {
            "key1" = "value1"
            "key2" = "value2"
          }
        }
      }
    }
  }
}
```

---

## Related References

- [Kafka Error Handling](kafka-error-handling-reference.md)
- [Kafka Serialization](kafka-serialization-reference.md)
- [Kafka Telemetry](kafka-telemetry-reference.md)
