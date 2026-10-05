# Kafka Consumer Configuration Reference (Kora 2.0)

Every key of `io.koraframework.kafka.common.consumer.KafkaListenerConfig`, taken from the interface
at tag `2.0.0.RC2`.

## Contents

- [Where the config lives](#where-the-config-lives)
- [Required keys](#required-keys)
- [Optional keys](#optional-keys)
- [Telemetry keys](#telemetry-keys)
- [driverProperties](#driverproperties)
- [Threads](#threads)
- [Startup and shutdown](#startup-and-shutdown)
- [Full example](#full-example)

---

## Where the config lives

`@KafkaListener("<path>")` is the **complete** config path. The generated module does
`mapper.mapOrThrow(config.get("<path>"))`, so a missing section fails the graph build with
`ConfigValueException: Config expected value, but got null at path: 'ROOT.<path>'`.

`kafka.consumer.<name>` and `kafka.producer.<name>` are the convention used by every Kora 2.0
example, not a framework rule.

---

## Required keys

```hocon
kafka.consumer.orders {
  topics = ["orders"]
  driverProperties {
    "bootstrap.servers" = "localhost:9092"
  }
}
```

| Key | Type | Notes |
|---|---|---|
| `driverProperties` | `Properties` | required — has no default; an empty block still satisfies the mapper but the Kafka client will fail without `bootstrap.servers` |
| `topics` | `List<String>` (`@Nullable`) | a single scalar is accepted by HOCON: `topics = "orders"` |
| `topicsPattern` | `Pattern` (`@Nullable`) | regex subscription, **subscribe mode only** |

`topics` or `topicsPattern` must be set. In assign mode (no `group.id`) `topics` is required (one or
more topics) and `topicsPattern` is rejected at startup — see the
[strategies reference](kafka-strategies-reference.md).

---

## Optional keys

| Key | Type | Default | Meaning |
|---|---|---|---|
| `partitions` | `List<String>` | `null` | used only for naming the consumer when `group.id`, `topics` and `topicsPattern` are all absent |
| `offset` | `earliest` \| `latest` \| `Duration` | `latest` | initial seek position — **assign mode only** |
| `pollTimeout` | `Duration` | `5s` | how long each `poll()` waits |
| `backoffTimeout` | `Duration` | `15s` | first pause after an unhandled error; doubles on repeats, capped at 60s |
| `threads` | `int` | `1` | consumers started for this listener; `0` disables it |
| `partitionRefreshInterval` | `Duration` | `1m` | assign mode partition rediscovery |
| `shutdownWait` | `Duration` | `30s` | graceful-shutdown budget |
| `allowEmptyRecords` | `boolean` | `false` | call a **batch** listener with an empty `ConsumerRecords` |
| `initializationFailTimeout` | `Duration` (`@Nullable`) | `null` | if set, `init()` throws when the first poll has not happened in time |

### `offset`

Declared as `Either<Duration, Offset>`, defaulting to `Offset.latest`.

| Value | Effect |
|---|---|
| `"earliest"` | `consumer.seekToBeginning(partition)` |
| `"latest"` | `consumer.seekToEnd(partition)` |
| `"5m"`, `"1h"`, `"24h"` | `offsetsForTimes(now - duration)` then `seek(...)` |

Only the assign container seeks. With a `group.id` the broker's committed offsets win, and the
Kafka driver property `auto.offset.reset` decides where a brand-new group starts.

### `allowEmptyRecords`

Only reaches a batch listener. `RecordHandler` (single-record shape) returns immediately on an empty
poll regardless of this flag.

---

## Telemetry keys

`KafkaConsumerTelemetryConfig` extends the framework-wide `TelemetryConfig`:

| Key | Default | |
|---|---|---|
| `telemetry.logging.enabled` | **`false`** | |
| `telemetry.logging.maskHeaders` | `["authorization", "cookie", "set-cookie"]` | header names (case-insensitive) masked in TRACE record logs |
| `telemetry.metrics.enabled` | **`false`** | |
| `telemetry.metrics.driverMetrics` | `false` | bind Micrometer's `KafkaClientMetrics` for the underlying client |
| `telemetry.metrics.slo` | 1,10,50,100,200,500,1000,2000,5000,10000,20000,30000,60000,90000 ms | timer buckets |
| `telemetry.metrics.tags` | `{}` | extra tags on every consumer meter |
| `telemetry.tracing.enabled` | `true` | |
| `telemetry.tracing.attributes` | `{}` | extra span attributes |

Logging and metrics are **off by default in Kora 2.0**. `telemetry.logging.enabled` also gates the
container's own lifecycle log lines — with it `false` the container installs a NOP logger, so
"KafkaListener started" never appears. See the [telemetry reference](kafka-telemetry-reference.md).

---

## driverProperties

Passed straight to `org.apache.kafka.clients.consumer.KafkaConsumer`. Kora 2.0 ships Kafka clients
**4.3.1**; check names against the
[Apache Kafka consumer configs](https://kafka.apache.org/documentation/#consumerconfigs) for that
line rather than against a 3.x memory.

Kora reads three of them itself:

| Property | What Kora does with it |
|---|---|
| `group.id` | present → subscribe container; absent → assign container |
| `enable.auto.commit` | absent → forced to `false` and Kora commits; `true` → the driver commits and Kora does not |
| `client.id` | copied into telemetry tags and spans |

**Do not set `key.deserializer` / `value.deserializer`.** The container always constructs the client
with `ByteArrayDeserializer` for both and wraps it in a `ConsumerWrapper` that applies the Kora
`Deserializer` beans chosen from your method signature. Setting them has no effect on what your
listener receives.

```hocon
driverProperties {
  "bootstrap.servers" = "localhost:9092"
  "bootstrap.servers" = ${?KAFKA_BOOTSTRAP}
  "group.id" = "order-service"
  "auto.offset.reset" = "earliest"
  "max.poll.records" = 500
  "max.poll.interval.ms" = 300000
  "session.timeout.ms" = 45000
  "heartbeat.interval.ms" = 3000
  "isolation.level" = "read_committed"
}
```

HOCON has **no** `${VAR:default}` placeholder. Assign the literal first and override it with
`${?VAR}` on the next line, as above; `${VAR}` alone is a required substitution that aborts startup
when unset.

---

## Threads

`threads = N` starts N independent consumers in one fixed thread pool named `kafka-listener-<path>N`.
They are separate group members, so partitions are split between them exactly as they would be
between separate pods. `threads = 0` starts nothing and logs nothing — a silent no-op that is easy
to mistake for a broker problem.

Parallelism is bounded by partition count: more threads than partitions leaves the extras idle.

---

## Startup and shutdown

**Startup.** Each thread loops: build a consumer, subscribe, poll. If construction throws it is
logged, the thread sleeps 250 ms and retries forever — the application still comes up. Set
`initializationFailTimeout` to turn that into a startup failure instead.

**Shutdown.** `release()` calls `wakeup()` on every consumer, then shuts the pool down and waits
`shutdownWait`. In-flight records finish; anything still running when the budget expires is
interrupted and a warning is logged. Kora does **not** issue a final commit on shutdown — a record
whose handler was interrupted is redelivered.

---

## Full example

```hocon
kafka {
  consumer {
    orders {
      topics = ["orders", "orders-retry"]
      pollTimeout = 250ms
      backoffTimeout = 15s
      shutdownWait = 30s
      threads = 2
      allowEmptyRecords = false

      driverProperties {
        "bootstrap.servers" = "localhost:9092"
        "bootstrap.servers" = ${?KAFKA_BOOTSTRAP}
        "group.id" = "order-service"
        "auto.offset.reset" = "earliest"
        "max.poll.records" = 500
      }

      telemetry {
        logging.enabled = true
        metrics {
          enabled = true
          driverMetrics = false
          slo = [1, 10, 50, 100, 200, 500, 1000, 2000, 5000, 10000]
          tags { "consumer-type" = "orders" }
        }
        tracing.enabled = true
      }
    }

    # assign strategy: no group.id, one or more topics, no topicsPattern
    price-cache {
      topics = ["prices", "rates"]
      offset = "earliest"
      partitionRefreshInterval = 1m
      driverProperties {
        "bootstrap.servers" = ${?KAFKA_BOOTSTRAP}
      }
    }
  }
}

logging.levels {
  "ROOT" = "INFO"
  "io.koraframework" = "INFO"
}
```

The logging section is `logging.levels` (`LoggingConfig.levels()`), not `logging.level`.

---

## Related references

- [Listener signatures](kafka-listener-reference.md)
- [Strategies](kafka-strategies-reference.md)
- [Offsets](kafka-offset-reference.md)
- [Telemetry](kafka-telemetry-reference.md)

**Source:** framework tag `2.0.0.RC2` —
[KafkaListenerConfig](https://github.com/kora-projects/kora/blob/2.0.0.RC2/kafka/kafka/src/main/java/io/koraframework/kafka/common/consumer/KafkaListenerConfig.java) ·
[consumer containers](https://github.com/kora-projects/kora/tree/2.0.0.RC2/kafka/kafka/src/main/java/io/koraframework/kafka/common/consumer/containers);
migrated examples on `migration/2.0` —
[kora-java-kafka](https://github.com/kora-projects/kora-examples/tree/migration/2.0/examples/java/kora-java-kafka)
