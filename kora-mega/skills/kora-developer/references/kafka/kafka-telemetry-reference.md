# Kafka Telemetry Reference

**Source:** [.kora-agent/kora-docs/mkdocs/docs/en/documentation/kafka.md](.kora-agent/kora-docs/mkdocs/docs/en/documentation/kafka.md), [.kora-agent/kora-docs/mkdocs/docs/en/documentation/telemetry.md](.kora-agent/kora-docs/mkdocs/docs/en/documentation/telemetry.md)  
**Examples:** `.kora-agent/kora-examples/kora-java-kafka/`

Observability for Kafka in Kora: metrics, tracing, logging.

## Metrics (Micrometer)

### Consumer metrics

| Metric | Type | Description |
|--------|------|-------------|
| `kafka_consumer_records_consumed_total` | Counter | Number of consumed records |
| `kafka_consumer_records_lag` | Gauge | Consumer lag |
| `kafka_consumer_poll_duration` | Timer | Duration of poll() operations |
| `kafka_consumer_commit_duration` | Timer | Duration of commitSync() operations |
| `kafka_consumer_rebalance_total` | Counter | Number of rebalance events |

### Producer metrics

| Metric | Type | Description |
|--------|------|-------------|
| `kafka_producer_records_sent_total` | Counter | Number of sent records |
| `kafka_producer_send_duration` | Timer | Duration of send() operations |
| `kafka_producer_batch_size` | DistributionSummary | Batch sizes |
| `kafka_producer_compression_ratio` | Gauge | Compression ratio |

### SLO configuration

```hocon
kafka {
  consumer {
    myListener {
      telemetry {
        metrics {
          enabled = true
          slo = [1, 10, 50, 100, 200, 500, 1000, 2000, 5000, 10000]  # milliseconds
        }
      }
    }
  }
  producer {
    myPublisher {
      telemetry {
        metrics {
          enabled = true
          slo = [1, 10, 50, 100, 200, 500, 1000, 2000, 5000, 10000]  # milliseconds
        }
      }
    }
  }
}
```

## Tracing (OpenTelemetry)

### Consumer tracing

A span is created for each message with:
- `messaging.system = kafka`
- `messaging.destination = <topic>`
- `messaging.kafka.consumer.group = <group.id>`
- `messaging.kafka.partition = <partition>`
- `messaging.kafka.offset = <offset>`

The parent span is taken from the message headers (W3C trace context propagation).

### Producer tracing

A span is created for each send with:
- `messaging.system = kafka`
- `messaging.destination = <topic>`
- `messaging.kafka.message.key = <key>`

Trace context is added to message headers for downstream propagation.

### Configuration

```hocon
kafka {
  consumer {
    myListener {
      telemetry {
        tracing {
          enabled = true
        }
      }
    }
  }
  producer {
    myPublisher {
      telemetry {
        tracing {
          enabled = true
        }
      }
    }
  }
}
```

## Logging

### Configuration

```hocon
kafka {
  consumer {
    myListener {
      telemetry {
        logging {
          enabled = true
        }
      }
    }
  }
  producer {
    myPublisher {
      telemetry {
        logging {
          enabled = true
        }
      }
    }
  }
}
```

### Kora Kafka log levels

```
logging.level {
  "ru.tinkoff.kora.kafka": "DEBUG"
  "ru.tinkoff.kora.kafka.consumer": "TRACE"
  "ru.tinkoff.kora.kafka.producer": "TRACE"
}
```

### Example log entries

**Consumer start:**
```
INFO  KafkaConsumerContainer - Starting consumer for topics [my-topic], group.id=my-group
```

**Message processed:**
```
DEBUG KafkaConsumerContainer - Processed record: topic=my-topic, partition=0, offset=123
```

**Producer send:**
```
DEBUG KafkaProducer - Sent record to topic=my-topic, partition=1, offset=456
```

## Prometheus Export

To export metrics to Prometheus, add:

```groovy
implementation "ru.tinkoff.kora:metrics-prometheus"
```

And enable the HTTP server for scraping:

```hocon
httpServer {
  privateApiHttpPort = 8085
}

prometheus {
  path = "/metrics"
}
```

Metrics will be available at `http://localhost:8085/metrics`.

## Grafana Dashboard

Example queries for lag monitoring:

```promql
# Consumer lag by group
kafka_consumer_records_lag{group_id="my-group"}

# Message consumption rate
rate(kafka_consumer_records_consumed_total[5m])

# 95th percentile poll duration
histogram_quantile(0.95, rate(kafka_consumer_poll_duration_bucket[5m]))
```
