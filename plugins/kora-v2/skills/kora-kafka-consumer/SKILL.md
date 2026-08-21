---
name: kora-kafka-consumer
description: "Kora Kafka consumers — @KafkaListener on a @Component method (KafkaModule), commit strategies, @Json deserialization, error handling, batch. Use when consuming Kafka messages or configuring kafka.consumer."
---

# Kora Kafka Consumer Skill

> **Kora sub-skill — obey the [kora-v1 meta rules](../../SKILL.md) on every task:** **R0** ensure `.kora-agent/` docs+examples are cloned · **R1** read this sub-skill before writing code · **R2** Kora APIs only — no Spring/Micronaut/Quarkus, no invented annotations or config keys · **R3** journal any incorrect Kora usage. Add comments/Javadoc only if asked.

**Languages:** Java, Kotlin | **Build:** Gradle

> **Level 1** — [Quick Start](#quick-start) | **Level 2** — [Signatures](#method-signatures) | **Level 3** — [Errors & Offset](#error-handling) | **Level 4** — [Batch & Rebalance](#batch-processing)

**References:** [Consumer config](references/kafka-consumer-reference.md) | [Listener signatures](references/kafka-listener-reference.md) | [Strategies](references/kafka-strategies-reference.md) | [Serialization](references/kafka-serialization-reference.md) | [Errors](references/kafka-error-handling-reference.md) | [Offset](references/kafka-offset-reference.md) | [Batch](references/kafka-batch-reference.md) | [Rebalance](references/kafka-rebalance-reference.md) | [Telemetry](references/kafka-telemetry-reference.md) | [Transactions (producer)](references/kafka-transactions-reference.md) | [Testing](references/kafka-testing-reference.md)

---

## Quick Start

**1. Dependencies** (Kora artifacts inherit their version from the `kora-parent` BOM — never pin them individually):
```groovy
dependencies {
    koraBom platform("ru.tinkoff.kora:kora-parent:1.2.19")
    annotationProcessor "ru.tinkoff.kora:annotation-processors"

    implementation "ru.tinkoff.kora:kafka"
    implementation "ru.tinkoff.kora:json-module"
    implementation "ru.tinkoff.kora:config-hocon"
    implementation "ru.tinkoff.kora:logging-logback"
}
```

**2. Application Module** (a `@KoraApp` interface `extends` each module — interfaces never use `implements`):
```java
@KoraApp
public interface Application extends KafkaModule, JsonModule, HoconConfigModule, LogbackModule {

    static void main(String[] args) {
        KoraApplication.run(ApplicationGraph::graph);
    }
}
```

**3. Simple Listener:**
```java
@Component
public final class UserEventListener {
    @KafkaListener("kafka.consumer.userEvents")
    void process(String value) {
        log.info("Received: {}", value);
    }
}
```

**4. Configuration:**
```hocon
kafka {
  consumer {
    userEvents {
      topics = ["user-events"]
      driverProperties {
        "bootstrap.servers" = ${KAFKA_BOOTSTRAP:"localhost:9092"}
        "group.id" = "user-service"
        "auto.offset.reset" = "earliest"
      }
    }
  }
}
```

---

## Method Signatures

| Signature | Commit | Use Case |
|-----------|--------|----------|
| `void process(String value)` | Auto | Simple processing |
| `void process(String key, String value)` | Auto | Key-aware |
| `void process(ConsumerRecord<K, V> record)` | Auto | Full metadata |
| `void process(ConsumerRecords<K, V> records)` | Auto/batch | Batch processing |
| `void process(..., Consumer consumer)` | Manual | Exactly-once |
| `void process(@Nullable T, @Nullable Exception)` | Auto | Error handling |

**JSON with Error Handling:**
```java
@Json record OrderEvent(String orderId, BigDecimal amount) {}

@KafkaListener("kafka.consumer.orders")
void process(@Nullable @Json OrderEvent event, @Nullable Exception error) {
    if (error != null) {
        log.error("Deserialization failed", error);
        return;
    }
    orderService.process(event);
}
```

**Full signatures:** [Listener Reference](references/kafka-listener-reference.md)

---

## Strategies

**Subscribe** (load balancing):
```hocon
driverProperties { "group.id" = "order-service"; "bootstrap.servers" = "localhost:9092" }
```

**Assign** (broadcast):
```hocon
driverProperties { "bootstrap.servers" = "localhost:9092" }  # No group.id
```

**Details:** [Strategies Reference](references/kafka-strategies-reference.md)

---

## Error Handling

**Deserialization:**
```java
@KafkaListener("kafka.consumer.events")
void process(@Nullable @Json Event event, @Nullable Exception error) {
    if (error != null) { log.error("Failed", error); return; }
    processEvent(event);
}
```

**Skip Invalid:**
```java
@KafkaListener("kafka.consumer.events")
void process(Event event) {
    if (event.orderId() == null)
        throw new KafkaSkipRecordException(new IllegalArgumentException("Missing orderId"));
    processEvent(event);
}
```

**DLQ:**
```java
@KafkaListener("kafka.consumer.events")
void process(@Nullable Event event, @Nullable Exception error) {
    if (error != null) { dlqPublisher.send("dlq", event, error.getMessage()); return; }
    processEvent(event);
}
```

**Details:** [Error Handling Reference](references/kafka-error-handling-reference.md)

---

## Offset Management

**Auto (Default):** Commit after each message/batch.

**Manual:**
```java
@KafkaListener("kafka.consumer.events")
void process(ConsumerRecord<String, String> record, Consumer<String, String> consumer) {
    try { process(record.value()); consumer.commitSync(); }
    catch (Exception e) { throw e; }
}
```

**Rebalance:** provide a `ConsumerAwareRebalanceListener` as a `@Component` carrying the
consumer's tag. Kora generates a tag per listener (`<Listener>Module.<Listener>ProcessTag`),
or you can declare your own via `@KafkaListener(value = "...", tag = MyTag.class)` and reuse it:
```java
@Tag(MyTag.class) @Component
final class RebalanceListener implements ConsumerAwareRebalanceListener {
    public void onPartitionsRevoked(Consumer<?, ?> c, Collection<TopicPartition> p) {
        c.commitSync();  // Commit before rebalance
    }
    public void onPartitionsAssigned(Consumer<?, ?> c, Collection<TopicPartition> p) { }
}
```

**Details:** [Offset Reference](references/kafka-offset-reference.md)

---

## Batch Processing

```java
@KafkaListener("kafka.consumer.orders")
void process(ConsumerRecords<String, OrderEvent> records) {
    for (ConsumerRecord<String, OrderEvent> record : records)
        orderService.process(record.value());
}
```

**Config:**
```hocon
kafka.consumer.batchProcessor {
  topics = ["high-volume"]
  threads = 4
  driverProperties { "max.poll.records" = 500; "fetch.min.bytes" = 1048576 }
}
```

**Details:** [Batch Reference](references/kafka-batch-reference.md)

---

## Rebalance Handling

```java
@Tag(MyTag.class) @Component
final class MyRebalanceListener implements ConsumerAwareRebalanceListener {
    public void onPartitionsRevoked(Consumer<?, ?> c, Collection<TopicPartition> p) {
        log.info("Revoked: {}", p); c.commitSync(); cache.clear();
    }
    public void onPartitionsAssigned(Consumer<?, ?> c, Collection<TopicPartition> p) {
        log.info("Assigned: {}", p);
    }
    public void onPartitionsLost(Consumer<?, ?> c, Collection<TopicPartition> p) {
        log.warn("Lost: {}", p);  // Don't commit
    }
}
```

**Details:** [Rebalance Reference](references/kafka-rebalance-reference.md)

---

## Configuration

**Required:**
```hocon
kafka.consumer.myListener {
  topics = ["topic1"]
  driverProperties { "bootstrap.servers" = "localhost:9092" }
}
```

**Optional:**

| Parameter | Default | Description |
|-----------|---------|-------------|
| `offset` | `latest` | `earliest`, `latest`, or duration (`5m`) |
| `pollTimeout` | `5s` | Max wait for messages |
| `backoffTimeout` | `15s` | Pause after exception |
| `threads` | `1` | Parallel threads |
| `shutdownWait` | `30s` | Graceful shutdown |

**Telemetry:**
```hocon
telemetry { logging {enabled=true}; metrics {enabled=true}; tracing {enabled=true} }
```

---

## Common Pitfalls

| Symptom | Cause | Fix |
|---------|-------|-----|
| `@KoraApp` does not compile | `interface Application implements KafkaModule` | An interface `extends` modules, never `implements` |
| `cannot find symbol KafkaSkipRecordException` | Wrong import | Import `ru.tinkoff.kora.kafka.common.exceptions.KafkaSkipRecordException` |
| Consumer never starts | `threads = 0` in config | Use `threads >= 1` (0 disables the consumer entirely) |
| Listener restarts in a loop | Handler throws an unhandled exception | Kora restarts the consumer on uncaught exceptions; throw `KafkaSkipRecordException` to skip, or handle and return |
| `offset = "5m"` ignored | `group.id` is set | `offset`/duration applies only in `assign` mode (no `group.id`); with a group, committed offsets win |
| Deserialization error crashes handler | Plain value signature | Add `@Nullable Exception` as the last parameter, or catch `RecordValueDeserializationException` when using `ConsumerRecord` |
| Rebalance listener never invoked | `@Tag` does not match the listener | Tag the listener (`@KafkaListener(tag = MyTag.class)`) and the `ConsumerAwareRebalanceListener` with the same tag |
| Nothing generated after refactor | Annotation processor stale | Clean `build/generated/`, rerun `./gradlew classes` |

Do not use field injection — Kora wires components through constructor injection at
compile time, and every consumer is a `@Component` with `@KafkaListener` methods.

---

## Templates

Assets: `ConsumerListener.java.template`, `JsonMessageListener.java.template`, `ConsumerListenerTests.java.template`, `application.conf.template`

See `assets/` for generator script.

---

## Testing

**Details:** [Testing Reference](references/kafka-testing-reference.md)

---

**Source of truth:** [Kafka doc](../../.kora-agent/kora-docs/mkdocs/docs/en/documentation/kafka.md) | [Messaging guide](../../.kora-agent/kora-docs/mkdocs/docs/en/guides/messaging-kafka.md) | [Example app](../../.kora-agent/kora-examples/examples/java/kora-java-kafka/)
