# Kafka Telemetry Reference

**Source:** [.kora-agent/kora-docs/mkdocs/docs/en/documentation/kafka.md](../../../.kora-agent/kora-docs/mkdocs/docs/en/documentation/kafka.md)

Telemetry (logging, metrics, tracing) for Kafka consumers in Kora.

## Contents

- [Configuration](#configuration)
- [Logging](#logging)
- [Metrics](#metrics)
- [Tracing](#tracing)
- [Health Checks](#health-checks)
- [Tags/Attributes](#tagsattributes)
- [Monitoring Dashboard](#monitoring-dashboard)
- [Best Practices](#best-practices)

---

## Configuration

### Enable Telemetry

```hocon
kafka {
  consumer {
    myListener {
      topics = ["my-topic"]
      driverProperties {
        "bootstrap.servers" = "localhost:9092"
      }
      telemetry {
        logging {
          enabled = true
        }
        metrics {
          enabled = true
          slo = [1, 10, 50, 100, 200, 500, 1000, 2000, 5000, 10000]
          tags = {
            "consumer-type" = "user-events"
            "environment" = "production"
          }
        }
        tracing {
          enabled = true
          attributes = {
            "service.name" = "user-service"
          }
        }
      }
    }
  }
}
```

---

## Logging

### Configuration

```hocon
telemetry {
  logging {
    enabled = true
  }
}
```

### What Gets Logged

- Consumer start/stop events
- Message consumption (optional, configure in Kafka driver)
- Errors and exceptions
- Rebalance events
- Offset commits (optional)

### Log Levels

- `INFO` - Consumer lifecycle events, rebalance
- `DEBUG` - Message consumption details, offset commits
- `ERROR` - Processing exceptions, deserialization errors

### Configure Kafka Client Logging

```hocon
logging.level {
  "org.apache.kafka.clients.consumer" = "DEBUG"
  "org.apache.kafka.common" = "INFO"
}
```

---

## Metrics

### Configuration

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

### Built-in Metrics

These are the metrics Kora actually emits for Kafka (see the [Metrics doc, Kafka
section](../../../.kora-agent/kora-docs/mkdocs/docs/en/documentation/metrics.md)). The
left column is the Micrometer meter name; the right column is the Prometheus name.

| Meter | Prometheus | Description |
|-------|-----------|-------------|
| `messaging.receive.duration` | `messaging_receive_duration_milliseconds` | Single message processing duration |
| `messaging.process.batch.duration` | `messaging_process_batch_duration_milliseconds` | Batch processing duration |
| `messaging.publish.duration` | `messaging_publish_duration_milliseconds` | Producer send duration |
| `messaging.kafka.consumer.lag` | `messaging_kafka_consumer_lag` | Consumer lag per partition (gauge) |

Tags include `messaging.system`, `messaging.destination`, `messaging.operation`,
`messaging.partition_id`, `messaging.consumer_group`, and `error.type`.

### Custom Metrics

Add business metrics to your listener:

```java
@Component
public final class UserEventListener {
    
    private final MeterRegistry meterRegistry;
    
    public UserEventListener(MeterRegistry meterRegistry) {
        this.meterRegistry = meterRegistry;
    }
    
    @KafkaListener("kafka.consumer.userEvents")
    void process(@Json UserEvent event) {
        Timer.Sample sample = Timer.start(meterRegistry);
        
        try {
            processEvent(event);
            sample.stop(Timer.builder("user.event.processing.time")
                .tag("event.type", event.eventType())
                .register(meterRegistry));
        } catch (Exception e) {
            meterRegistry.counter("user.event.processing.errors",
                "event.type", event.eventType()).increment();
            throw e;
        }
    }
}
```

---

## Tracing

### Configuration

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

### What Gets Traced

- Consumer record processing (one span per record or batch)
- Deserialization errors
- Rebalance events

### Trace Context Propagation

Kora automatically propagates trace context through Kafka headers.

**Producer side:**
```java
@KafkaPublisher("kafka.publisher")
interface Publisher {
    @KafkaPublisher.Topic("my-topic")
    void send(String key, @Json MyEvent event);
}
```

**Consumer side:**
```java
@KafkaListener("kafka.consumer.listener")
void process(@Json MyEvent event) {
    // Span is automatically created with parent context from headers
    log.info("Processing in trace: {}", Span.current().getSpanContext().getTraceId());
}
```

### Manual Span Creation

```java
@KafkaListener("kafka.consumer.listener")
void process(@Json MyEvent event) {
    Tracer tracer = getTracer();  // Inject your tracer
    
    Span span = tracer.spanBuilder("process-user-event")
        .setSpanKind(SpanKind.CONSUMER)
        .setAttribute("event.id", event.id())
        .setAttribute("event.type", event.eventType())
        .startSpan();
    
    try (Scope scope = span.makeCurrent()) {
        processEvent(event);
    } catch (Exception e) {
        span.recordException(e);
        span.setStatus(StatusCode.ERROR);
        throw e;
    } finally {
        span.end();
    }
}
```

---

## Health Checks

### Liveness/Readiness Probes

Kora exposes liveness/readiness on the private HTTP port via the `ProbesModule`. Probes
are a separate module — see the
[probes doc](../../../.kora-agent/kora-docs/mkdocs/docs/en/documentation/probes.md) for
details. Add it to the application:

```java
@KoraApp
public interface Application extends
    KafkaModule,
    ProbesModule {}
```

The private API port carries probes and metrics; keep it distinct from the public
traffic port:

```hocon
httpServer {
  privateApiHttpPort = 8085
  # Default probe paths (configurable):
  privateApiHttpLivenessPath = "/system/liveness"
  privateApiHttpReadinessPath = "/system/readiness"
}
```

**Default probe paths:**
- `/system/liveness` — liveness
- `/system/readiness` — readiness

---

## Tags/Attributes

### Metric Tags

```hocon
telemetry {
  metrics {
    tags = {
      "consumer-type" = "user-events"
      "environment" = "production"
      "team" = "user-team"
    }
  }
}
```

### Trace Attributes

```hocon
telemetry {
  tracing {
    attributes = {
      "service.name" = "user-service"
      "deployment.environment" = "production"
    }
  }
}
```

---

## Monitoring Dashboard

Kora exposes a Prometheus scrape endpoint on the **private** HTTP port through the
metrics module. Point Prometheus at that port (see the
[metrics doc](../../../.kora-agent/kora-docs/mkdocs/docs/en/documentation/metrics.md)
for the exact path and module setup).

### Key Metrics to Monitor

| Prometheus metric | What it signals |
|-------------------|-----------------|
| `messaging_kafka_consumer_lag` | Backlog per partition — rising lag means the consumer can't keep up |
| `messaging_receive_duration_milliseconds_count` with `error.type` | Failure rate of message processing |
| `messaging_receive_duration_milliseconds` buckets/max | Per-message latency |
| `messaging_process_batch_duration_milliseconds` | Batch processing latency |

### Example PromQL

**Consumer lag:**
```promql
messaging_kafka_consumer_lag{messaging_destination="user-events"}
```

**Processing rate:**
```promql
rate(messaging_receive_duration_milliseconds_count{messaging_destination="user-events"}[5m])
```

**Error rate:**
```promql
rate(messaging_receive_duration_milliseconds_count{error_type!=""}[5m])
```

---

## Best Practices

### 1. Enable All Telemetry Types

```hocon
telemetry {
  logging { enabled = true }
  metrics { enabled = true }
  tracing { enabled = true }
}
```

### 2. Use Meaningful Tags

```hocon
telemetry {
  metrics {
    tags = {
      "consumer-type" = "user-events"
      "environment" = "production"
    }
  }
}
```

### 3. Monitor Consumer Lag

Consumer lag is a key indicator of processing health.

### 4. Trace End-to-End

Ensure trace context propagates from producer to consumer.

### 5. Log Rebalance Events

Rebalance logging helps debug consumption issues:

```java
@Tag(MyListenerProcessTag.class)
@Component
public final class MyRebalanceListener implements ConsumerAwareRebalanceListener {
    
    @Override
    public void onPartitionsAssigned(Consumer<?, ?> consumer, Collection<TopicPartition> partitions) {
        log.info("Partitions assigned: {}", partitions);
    }
}
```

---

## Related References

- [Kafka Consumer Reference](kafka-consumer-reference.md)
- [Kafka Error Handling Reference](kafka-error-handling-reference.md)
- [Metrics doc](../../../.kora-agent/kora-docs/mkdocs/docs/en/documentation/metrics.md)
- [Tracing doc](../../../.kora-agent/kora-docs/mkdocs/docs/en/documentation/tracing.md)
