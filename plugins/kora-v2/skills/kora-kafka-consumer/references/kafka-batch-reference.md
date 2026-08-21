# Kafka Batch Processing Reference

**Source:** [.kora-agent/kora-docs/mkdocs/docs/en/documentation/kafka.md](../../../.kora-agent/kora-docs/mkdocs/docs/en/documentation/kafka.md)

Complete reference for batch processing patterns in Kafka consumers.

## Contents

- [When to Use Batch Processing](#when-to-use-batch-processing)
- [Basic Batch Processing](#basic-batch-processing)
- [Batch with Metadata Access](#batch-with-metadata-access)
- [Batch Insert to Database](#batch-insert-to-database)
- [Batch with Manual Commit and Intermediate Processing](#batch-with-manual-commit-and-intermediate-processing)
- [Batch Aggregation Pattern](#batch-aggregation-pattern)
- [Configuration for Batch Processing](#configuration-for-batch-processing)
- [Multi-Threaded Batch Processing](#multi-threaded-batch-processing)
- [Best Practices](#best-practices)

---

## When to Use Batch Processing

Use batch processing for:

- **High throughput** — process messages in batches
- **Batch DB operations** — bulk insert/update
- **Data aggregation** — aggregate before processing

---

## Basic Batch Processing

Method receives `ConsumerRecords<K, V>` — all messages from one poll:

```java
@KafkaListener("kafka.consumer.orders")
void process(ConsumerRecords<String, OrderEvent> records) {
    log.info("Received batch: {} records", records.count());
    
    for (ConsumerRecord<String, OrderEvent> record : records) {
        OrderEvent event = record.value();
        orderService.process(event);
    }
    
    // commitSync() called automatically after batch
}
```

---

## Batch with Metadata Access

Access partition, offset, timestamp for each message:

```java
@KafkaListener("kafka.consumer.orders")
void process(ConsumerRecords<String, OrderEvent> records) {
    // Group by partitions
    for (TopicPartition partition : records.partitions()) {
        List<ConsumerRecord<String, OrderEvent>> partitionRecords = 
            records.records(partition);
        
        log.info("Partition {}: {} records", partition, partitionRecords.size());
        
        for (ConsumerRecord<String, OrderEvent> record : partitionRecords) {
            log.debug("Offset={}, Key={}, Value={}", 
                record.offset(), record.key(), record.value());
        }
    }
}
```

---

## Batch Insert to Database

Collect the whole poll into a list and hand it to a Kora `@Repository` `@Query` that
accepts a `List` parameter, so the repository issues a single batched statement instead
of N round-trips. See the `kora-database-jdbc` skill for repository details.

```java
@Component
public final class OrderBatchProcessor {

    private final OrderRepository repository;

    public OrderBatchProcessor(OrderRepository repository) {
        this.repository = repository;
    }

    @KafkaListener("kafka.consumer.orders")
    void process(ConsumerRecords<String, OrderEvent> records) {
        List<OrderEvent> batch = new ArrayList<>();
        for (ConsumerRecord<String, OrderEvent> record : records) {
            batch.add(record.value());
        }

        // Single batched insert via a repository @Query that takes the whole list
        repository.insertAll(batch);
        // commitSync() is called automatically after the batch
    }
}
```

---

## Batch with Manual Commit and Intermediate Processing

### Manual Commit with Intermediate Commits

```java
@KafkaListener("kafka.consumer.analytics")
void process(ConsumerRecords<String, AnalyticsEvent> records, 
             Consumer<String, AnalyticsEvent> consumer) {
    
    int total = records.count();
    int processed = 0;
    int commitBatch = 100;
    
    for (ConsumerRecord<String, AnalyticsEvent> record : records) {
        try {
            analyticsService.process(record.value());
            processed++;
            
            // Intermediate commit every N messages
            if (processed % commitBatch == 0) {
                consumer.commitSync();
                log.info("Committed {}/{} records", processed, total);
            }
        } catch (Exception e) {
            log.error("Failed at offset={}", record.offset(), e);
            
            // Commit successful messages before error
            if (processed > 0) {
                consumer.commitSync();
            }
            throw e;  // Trigger backoff
        }
    }
    
    // Final commit
    consumer.commitSync();
    log.info("Batch complete: {} records", total);
}
```

---

## Batch Aggregation Pattern

Aggregate data before processing:

```java
@Component
public final class MetricsAggregator {
    
    private final MetricsRepository metricsRepo;
    
    @KafkaListener("kafka.consumer.metrics")
    void process(ConsumerRecords<String, MetricEvent> records) {
        // Group by metric name
        Map<String, List<MetricEvent>> grouped = records.stream()
            .collect(Collectors.groupingBy(
                r -> r.value().metricName(),
                Collectors.mapping(ConsumerRecord::value, Collectors.toList())
            ));
        
        // Aggregate and save
        for (Map.Entry<String, List<MetricEvent>> entry : grouped.entrySet()) {
            String metricName = entry.getKey();
            List<MetricEvent> events = entry.getValue();
            
            double sum = events.stream()
                .mapToDouble(MetricEvent::value)
                .sum();
            
            double avg = sum / events.size();
            
            metricsRepo.saveAggregation(metricName, 
                avg, sum, events.size(), Instant.now());
        }
    }
}
```

---

## Configuration for Batch Processing

### Basic Configuration

```hocon
kafka {
  consumer {
    batchProcessor {
      topics = ["high-volume-topic"]
      
      # Timeouts
      pollTimeout = "10s"         # Max wait time for batch
      backoffTimeout = "30s"      # Pause on error
      
      # Batch size (via Kafka driver properties)
      driverProperties {
        "bootstrap.servers" = "localhost:9092"
        "group.id" = "batch-processor"
        "max.poll.records" = 500      # Max messages per poll
        "fetch.min.bytes" = 1048576   # Min batch size (1MB)
        "fetch.max.wait.ms" = 500     # Max wait for batch fill
      }
      
      # Multi-threaded processing within batch
      threads = 4
      
      telemetry {
        metrics {
          enabled = true
          slo = [10, 50, 100, 500, 1000, 5000, 10000]
        }
      }
    }
  }
}
```

### Key Driver Properties

| Property | Description | Recommended |
|----------|-------------|-------------|
| `max.poll.records` | Max messages per poll | 500-1000 |
| `fetch.min.bytes` | Min bytes to fetch | 1MB (1048576) |
| `fetch.max.wait.ms` | Max wait for batch | 500ms |
| `max.poll.interval.ms` | Max time between polls | 300000 (5min) |

---

## Multi-Threaded Batch Processing

Configure parallel processing within batch:

```hocon
kafka {
  consumer {
    parallelProcessor {
      topics = ["events"]
      threads = 4  # 4 parallel threads
      
      driverProperties {
        "bootstrap.servers" = "localhost:9092"
        "group.id" = "parallel-group"
        "max.poll.records" = 1000
      }
    }
  }
}
```

---

## Best Practices

### 1. Tune Batch Size

Balance throughput vs latency:

```hocon
# High throughput (larger batches)
max.poll.records = 1000
fetch.min.bytes = 1048576  # 1MB

# Low latency (smaller batches)
max.poll.records = 100
fetch.min.bytes = 1
```

### 2. Handle Empty Batches

Configure if empty batches should be processed:

```hocon
kafka {
  consumer {
    myListener {
      allowEmptyRecords = true  # Process empty batches
      topics = ["my-topic"]
    }
  }
}
```

### 3. Commit Progress

For long batches, commit intermediate progress:

```java
int commitEvery = 100;
for (int i = 0; i < records.size(); i++) {
    process(records.get(i));
    if ((i + 1) % commitEvery == 0) {
        consumer.commitSync();
    }
}
```

---

## Related References

- [Kafka Consumer Reference](kafka-consumer-reference.md) — Basic configuration
- [Kafka Offset Reference](kafka-offset-reference.md) — Manual commit patterns
- [Kafka Telemetry Reference](kafka-telemetry-reference.md) — Metrics for batch processing
