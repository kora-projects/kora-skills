# Kafka Transactions Reference

**Source:** [.kora-agent/kora-docs/mkdocs/docs/en/documentation/kafka.md](../../../.kora-agent/kora-docs/mkdocs/docs/en/documentation/kafka.md)
**Examples:** [.kora-agent/kora-examples/examples/java/kora-java-kafka/](../../../.kora-agent/kora-examples/examples/java/kora-java-kafka/)

In Kora, Kafka transactions are a **producer-side** feature. There is no special
transactional consumer annotation: a consumer participates in a read-process-write
flow only by configuring `isolation.level = read_committed` so it ignores aborted
records, while the atomic write is performed by a transactional `@KafkaPublisher`.

## Contents

- [What Kora provides](#what-kora-provides)
- [Transactional publisher](#transactional-publisher)
- [Sending in a transaction with inTx](#sending-in-a-transaction-with-intx)
- [Manual transaction control](#manual-transaction-control)
- [Configuration](#configuration)
- [Consumer side: read_committed](#consumer-side-read_committed)
- [Pitfalls](#pitfalls)
- [Related references](#related-references)

---

## What Kora provides

| Token | Kind | Purpose |
|-------|------|---------|
| `TransactionalPublisher<P>` | interface (extend it) | Marks a `@KafkaPublisher` interface as transactional, wrapping a plain publisher `P` |
| `inTx(...)` | method | Runs a lambda; all sends commit on success, abort on exception |
| `begin()` | method | Opens a transaction in a try-with-resources block; commit on close |
| `abort()` | method | Aborts the open transaction |
| `KafkaPublisherConfig.TransactionConfig` | config class | `idPrefix`, `maxPoolSize`, `maxWaitTime` |

Transactions are NOT declared on a `@KafkaListener`. Do not look for a
`@KoraTransaction` annotation or a `KafkaTransactionContext` parameter — they do not
exist in Kora.

---

## Transactional publisher

First declare a regular publisher, then a transactional publisher that extends
`TransactionalPublisher` parameterized with it. This mirrors the example app:

```java
import ru.tinkoff.kora.kafka.common.annotation.KafkaPublisher;
import ru.tinkoff.kora.kafka.common.annotation.KafkaPublisher.Topic;
import ru.tinkoff.kora.kafka.common.producer.TransactionalPublisher;

@KafkaPublisher("kafka.producer.my-transactional")
public interface MyTransactionalPublisher
        extends TransactionalPublisher<MyTransactionalPublisher.TopicPublisher> {

    @KafkaPublisher("kafka.producer.my-publisher")
    interface TopicPublisher {

        @Topic("kafka.producer.my-topic")
        void send(String value);
    }
}
```

`MyTransactionalPublisher` is injectable as a `@Component` dependency like any other
publisher.

---

## Sending in a transaction with inTx

`inTx` accepts a lambda receiving the wrapped publisher. Every send inside the lambda
commits atomically if the lambda returns normally, and is aborted if it throws:

```java
publisher.inTx(producer -> {
    producer.send("value-1");
    producer.send("value-2");
});
```

If the lambda throws, none of the sends are visible to `read_committed` consumers:

```java
publisher.inTx(producer -> {
    producer.send("value-1");
    if (somethingWrong) {
        throw new IllegalStateException("abort the whole batch");
    }
    producer.send("value-2");
});
// IllegalStateException propagates; both sends are aborted
```

Kotlin uses a `TransactionalConsumer` functional interface:

```kotlin
transactionalPublisher.inTx(TransactionalConsumer {
    it.send("value-1")
    it.send("value-2")
})
```

---

## Manual transaction control

For finer control, open the transaction explicitly. The commit happens on
try-with-resources close; call `abort()` to roll back instead:

```java
try (var transaction = transactionalPublisher.begin()) {
    transaction.producer().send(record);
    if (somethingBad) {
        transaction.abort();
    }
}
```

```kotlin
transactionalPublisher.begin().use {
    it.producer().send(record)
    if (somethingBad) {
        it.abort()
    }
}
```

---

## Configuration

A transactional publisher is configured with `KafkaPublisherConfig.TransactionConfig`:

```hocon
kafka {
  producer {
    my-transactional {
      idPrefix = "kafka-app-"   # transaction identifier prefix
      maxPoolSize = 10          # connection-set size for transactions
      maxWaitTime = "10s"       # maximum transaction waiting time
    }
  }
}
```

The wrapped plain publisher (`my-publisher` above) keeps its own
`driverProperties` / `telemetry` block as usual. Only the transactional wrapper uses
`idPrefix` / `maxPoolSize` / `maxWaitTime`.

---

## Consumer side: read_committed

A consumer that should only see committed records sets `isolation.level`:

```hocon
kafka {
  consumer {
    my-listener {
      topics = ["my-topic"]
      driverProperties {
        "bootstrap.servers" = ${KAFKA_BOOTSTRAP}
        "group.id" = "my-group-id"
        "isolation.level" = "read_committed"
      }
    }
  }
}
```

The consumer itself uses the ordinary `@KafkaListener` signatures from
[the listener reference](kafka-listener-reference.md). There is no transactional
consumer container — only this driver property changes its visibility behavior.

---

## Pitfalls

| Symptom | Cause | Fix |
|---------|-------|-----|
| Aborted records still consumed | Consumer left at default isolation | Set `"isolation.level" = "read_committed"` |
| `inTx` partially applied | Caught the exception inside the lambda | Let the exception propagate so Kora aborts the whole batch |
| Looking for `@KoraTransaction` | That annotation does not exist | Use a `TransactionalPublisher` and `inTx` / `begin` |
| Transaction never commits with `begin()` | Forgot try-with-resources | `begin()` commits on close; always use it in a `try (...)` block |

---

## Related references

- [Kafka Listener Reference](kafka-listener-reference.md)
- [Kafka Error Handling Reference](kafka-error-handling-reference.md)
- [Kafka Producer Reference](../../kora-kafka-producer/references/kafka-producer-reference.md)
