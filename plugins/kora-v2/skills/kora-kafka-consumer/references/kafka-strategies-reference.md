# Kafka Consumer Strategies Reference

**Source:** [.kora-agent/kora-docs/mkdocs/docs/en/documentation/kafka.md](../../../.kora-agent/kora-docs/mkdocs/docs/en/documentation/kafka.md)

Complete reference for Kafka consumption strategies: subscribe vs assign.

## Contents

- [Overview](#overview)
- [Subscribe Strategy (Consumer Groups)](#subscribe-strategy-consumer-groups)
- [Assign Strategy (Partition Assignment)](#assign-strategy-partition-assignment)
- [Strategy Comparison](#strategy-comparison)
- [Configuration Examples](#configuration-examples)
- [Best Practices](#best-practices)

---

## Overview

Kora supports two consumption strategies that determine how messages are distributed across application instances.

**Quick decision:**
- **Subscribe** (with `group.id`) — load balancing between instances (recommended for most cases)
- **Assign** (without `group.id`) — broadcast/pub-sub, each instance receives all messages

---

## Subscribe Strategy (Consumer Groups)

**Use when:** Messages should be distributed among instances (load balancing).

Each message is processed by exactly one instance in the consumer group.

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

### Characteristics

| Property | Description |
|----------|-------------|
| Message distribution | Distributed across instances |
| Horizontal scaling | Add more instances |
| Pattern | Task-queue processing |
| Recommendation | Use for most use cases |

### Consumer Group Behavior

| Instances | Partitions | Messages per instance |
|-----------|------------|----------------------|
| 1         | 3          | All messages         |
| 2         | 3          | ~50% each            |
| 3         | 3          | ~33% each            |
| 4         | 3          | 3 active, 1 idle     |

> **Note:** If there are more instances than partitions, excess instances will be idle.

---

## Assign Strategy (Partition Assignment)

**Use when:** Every instance should receive all messages (broadcast/pub-sub).

Each instance reads all messages from the topic independently.

```hocon
kafka {
  consumer {
    myAssigner {
      topics = ["my-topic"]
      driverProperties {
        "bootstrap.servers" = "localhost:9093"
        # group.id NOT specified - this triggers assign mode
      }
    }
  }
}
```

### Characteristics

| Property | Description |
|----------|-------------|
| Message distribution | Duplicated across all instances |
| Topics | Only one topic at a time |
| Pattern | Broadcast/pub-sub |
| Coordination | No consumer group coordination |

### Typical Use Cases

- **Local cache** — each instance builds its own cache
- **Indexing** — each instance builds its own index
- **Audit log** — each instance logs all messages

---

## Strategy Comparison

| Aspect | Subscribe | Assign |
|--------|-----------|--------|
| `group.id` | Required | Not specified |
| Message delivery | One instance per message | All instances receive |
| Scaling | Horizontal (load balancing) | Vertical (more instances = more copies) |
| Topics | Multiple topics | Single topic only |
| Use case | Task queue, processing | Broadcast, caching, indexing |

---

## Configuration Examples

### Subscribe: Multiple Consumers with Different Groups

```hocon
kafka {
  consumer {
    orderProcessor {
      topics = ["orders"]
      driverProperties {
        "group.id" = "order-processor"
        "bootstrap.servers" = "localhost:9092"
      }
    }
    
    orderAnalytics {
      topics = ["orders"]
      driverProperties {
        "group.id" = "order-analytics"
        "bootstrap.servers" = "localhost:9092"
      }
    }
  }
}
```

Both consumers receive all messages but from different group perspectives.

### Assign: Independent Processing

```hocon
kafka {
  consumer {
    cacheBuilder {
      topics = ["events"]
      driverProperties {
        "bootstrap.servers" = "localhost:9092"
        # No group.id - each instance gets all messages
      }
    }
  }
}
```

Each instance builds its own cache from all events.

---

## Best Practices

### 1. Use Subscribe by Default

For most business logic processing, use subscribe with `group.id`:

```hocon
driverProperties {
  "group.id" = "my-service-consumer"
  "bootstrap.servers" = "localhost:9092"
}
```

### 2. Naming Convention for Consumer Groups

Use `<service>-<purpose>` format:

```hocon
"group.id" = "order-service-orders"
"group.id" = "order-service-dlq"
"group.id" = "notification-service-email"
```

### 3. Partition Count Planning

Set partitions >= max expected instances for horizontal scaling:

```bash
# Create topic with enough partitions for future scaling
kafka-topics.sh --create --topic orders --partitions 6 --replication-factor 3
```

### 4. Monitor Consumer Lag

Track consumer lag metrics to detect consumption problems:

```hocon
telemetry {
  metrics {
    enabled = true
    tags = {
      "consumer-group" = "order-service"
    }
  }
}
```

---

## Related References

- [Kafka Consumer Reference](kafka-consumer-reference.md) — Basic configuration
- [Kafka Rebalance Reference](kafka-rebalance-reference.md) — Partition rebalancing
- [Kafka Offset Reference](kafka-offset-reference.md) — Offset management
