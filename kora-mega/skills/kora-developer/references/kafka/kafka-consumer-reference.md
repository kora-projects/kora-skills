# Kafka Consumer Reference

**Source:** [.kora-agent/kora-docs/mkdocs/docs/en/documentation/kafka.md](.kora-agent/kora-docs/mkdocs/docs/en/documentation/kafka.md)  
**Examples:** `.kora-agent/kora-examples/kora-java-kafka/`, `.kora-agent/kora-examples/kora-java-kafka-batch/`

Complete reference for Kafka consumers in Kora.

## @KafkaListener annotation

Placed on a method to create a declarative consumer.

```java
@Component
public final class MyService {
    @KafkaListener("kafka.consumer.myListener")
    void process(String value) { }
}
```

The parameter specifies the configuration path in `application.conf`.

## Consumption strategies

### Subscribe (with group.id)

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
- Scale by increasing the number of instances
- Use for task-queue processing

### Assign (without group.id)

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
- Use for broadcast/pub-sub scenarios
- Only one topic at a time

## Method signatures

### 1. Simple value processing

```java
@KafkaListener("kafka.consumer.listener")
void process(String value) { }
```

Auto-commit after each message.

### 2. Key-Value pair

```java
@KafkaListener("kafka.consumer.listener")
void process(String key, String value) { }
```

### 3. With headers

```java
@KafkaListener("kafka.consumer.listener")
void process(String key, String value, Headers headers) { }
```

### 4. ConsumerRecord

```java
@KafkaListener("kafka.consumer.listener")
void process(ConsumerRecord<String, String> record) { }
```

Full access to metadata: topic, partition, offset, timestamp.

### 5. ConsumerRecords (batch)

```java
@KafkaListener("kafka.consumer.listener")
void process(ConsumerRecords<String, String> records) { }
```

Auto-commit after the entire batch.

### 6. With error handling

```java
@KafkaListener("kafka.consumer.listener")
void process(@Nullable String value, @Nullable Exception error) { }
```

### 7. With manual commit

```java
@KafkaListener("kafka.consumer.listener")
void process(ConsumerRecord<String, String> record, Consumer<String, String> consumer) {
    // Processing
    consumer.commitSync();  // Manual commit
}
```

### 8. With telemetry context

```java
@KafkaListener("kafka.consumer.listener")
void process(ConsumerRecord<String, String> record, KafkaConsumerRecordTelemetryContext ctx) { }
```

## Configuration

### Required parameters

```hocon
kafka {
  consumer {
    myListener {
      # Topics (either topics or topicsPattern is required)
      topics = ["topic1"]
      # or
      topicsPattern = "topic-*"
      
      # Kafka driver properties (required)
      driverProperties {
        "bootstrap.servers" = "localhost:9093"
      }
    }
  }
}
```

### Optional parameters

| Parameter | Description | Default |
|-----------|-------------|---------|
| `topics` | List of topics | - |
| `topicsPattern` | Topic pattern | - |
| `allowEmptyRecords` | Process empty records | `false` |
| `offset` | Position: `earliest`, `latest`, Duration | `latest` |
| `pollTimeout` | poll() wait time | `5s` |
| `backoffTimeout` | Pause between errors | `15s` |
| `partitionRefreshInterval` | Partition refresh interval | `1m` |
| `threads` | Number of threads | `1` |
| `shutdownWait` | Graceful shutdown time | `30s` |

### Driver Properties

Standard Kafka consumer properties:

```hocon
driverProperties {
  "bootstrap.servers" = "localhost:9093"
  "group.id" = "my-group"
  "auto.offset.reset" = "latest"
  "enable.auto.commit" = true
  "max.poll.records" = 500
  "session.timeout.ms" = 30000
  "heartbeat.interval.ms" = 10000
}
```

## Offset strategies

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

### Duration

Start from the offset at the specified time ago.

```hocon
offset = "5m"  # 5 minutes ago
offset = "1h"  # 1 hour ago
```

## Multi-threaded processing

```hocon
kafka {
  consumer {
    myListener {
      threads = 4  # 4 threads for parallel processing
      topics = ["my-topic"]
      driverProperties {
        "bootstrap.servers" = "localhost:9093"
        "group.id" = "my-group"
      }
    }
  }
}
```
