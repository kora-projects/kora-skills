# Kafka Transactions Reference (Kora 2.0)

Transactions are a **producer-side** feature. There is no transactional `@KafkaListener`, no
`@KoraTransaction` annotation and no transaction parameter — a consumer takes part in a
read-process-write flow through `isolation.level` and by handing its offsets to a producer
transaction.

## Contents

- [What Kora provides](#what-kora-provides)
- [Declaring a transactional publisher](#declaring-a-transactional-publisher)
- [inTx and withTx](#intx-and-withtx)
- [Manual control with begin](#manual-control-with-begin)
- [Read-process-write](#read-process-write)
- [Configuration](#configuration)
- [Consumer side: read_committed](#consumer-side-read_committed)
- [Pitfalls](#pitfalls)

---

## What Kora provides

`io.koraframework.kafka.common.producer.TransactionalPublisher<P>`:

| Member | Signature |
|---|---|
| `begin()` | `Transaction<? extends P> begin()` — initialises and begins a transaction |
| `inTx(...)` | `void inTx(TransactionalConsumer<P, E>)` / `R inTx(TransactionalFunction<P, E, R>)` — the callback receives the **publisher** |
| `withTx(...)` | `void withTx(TransactionConsumer<P, E>)` / `R withTx(TransactionFunction<P, E, R>)` — the callback receives the **`Transaction`** |

`Transaction<P> extends AutoCloseable`:

| Member | Purpose |
|---|---|
| `P publisher()` | the wrapped `@KafkaPublisher` interface |
| `Producer<byte[], byte[]> producer()` | the raw Kafka producer |
| `sendOffsetsToTransaction(Map<TopicPartition, OffsetAndMetadata>, ConsumerGroupMetadata)` | commit consumer offsets inside the transaction |
| `abort()` / `abort(@Nullable Throwable)` | abort |
| `flush()` | flush pending sends |
| `close()` | commits — this is what makes try-with-resources work |

`inTx` and `withTx` both `begin()`, run the callback, `abort()` on any `Throwable`, rethrow, and
commit via `close()` on the normal path.

---

## Declaring a transactional publisher

A transactional publisher wraps an ordinary one. Both are `@KafkaPublisher` interfaces:

```java
import io.koraframework.kafka.common.annotation.KafkaPublisher;
import io.koraframework.kafka.common.annotation.KafkaPublisher.Topic;
import io.koraframework.kafka.common.producer.TransactionalPublisher;

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

```kotlin
@KafkaPublisher("kafka.producer.my-transactional")
interface MyTransactionalPublisher : TransactionalPublisher<MyTransactionalPublisher.TopicPublisher> {

    @KafkaPublisher("kafka.producer.my-publisher")
    interface TopicPublisher {
        @Topic("kafka.producer.my-topic")
        fun send(value: String)
    }
}
```

Inject `MyTransactionalPublisher` like any other component.

---

## `inTx` and `withTx`

Use `inTx` when you only need to send:

```java
publisher.inTx(topicPublisher -> {
    topicPublisher.send("value-1");
    topicPublisher.send("value-2");
});
```

Use `withTx` when you need the `Transaction` itself — offsets, the raw producer, an explicit abort:

```java
publisher.withTx(transaction -> {
    transaction.publisher().send("value-1");
    transaction.producer().flush();
});
```

If the callback throws, the transaction is aborted and the exception propagates; a
`read_committed` consumer never sees the sends.

**Kotlin.** The four functional overloads are not distinguishable from a bare lambda, so the
migrated Kotlin example uses `begin().use { }` instead. If you want the callback form, pass an
explicit SAM constructor (`TransactionalPublisher.TransactionalConsumer { ... }`).

---

## Manual control with `begin`

`close()` commits, so try-with-resources is the commit:

```java
try (var transaction = publisher.begin()) {
    transaction.publisher().send("value");
    if (somethingWrong) {
        transaction.abort();
    }
}
```

```kotlin
publisher.begin().use { transaction ->
    transaction.publisher().send("value")
    if (somethingWrong) {
        transaction.abort()
    }
}
```

Forgetting the try-with-resources / `use` leaks a producer from the pool and never commits.

---

## Read-process-write

The only place a consumer touches a transaction: hand its offsets to the producer so the write and
the offset commit are atomic. This is the migrated example, verbatim in shape:

```java
@Component
public final class TransactionalPipelineListener {

    private final MyTransactionalPublisher publisher;

    public TransactionalPipelineListener(MyTransactionalPublisher publisher) {
        this.publisher = publisher;
    }

    @KafkaListener("kafka.consumer.transactional-pipeline")
    public void process(ConsumerRecord<String, String> record, Consumer<String, String> consumer) {
        publisher.withTx(transaction -> {
            transaction.publisher().send("processed:" + record.value());
            transaction.sendOffsetsToTransaction(
                Map.of(new TopicPartition(record.topic(), record.partition()),
                       new OffsetAndMetadata(record.offset() + 1)),
                consumer.groupMetadata());
        });
    }
}
```

```kotlin
@Component
class TransactionalPipelineListener(private val publisher: MyTransactionalPublisher) {

    @KafkaListener("kafka.consumer.transactional-pipeline")
    fun process(record: ConsumerRecord<String, String>, consumer: Consumer<String, String>) {
        publisher.begin().use { transaction ->
            transaction.publisher().send("processed:${record.value()}")
            transaction.sendOffsetsToTransaction(
                mapOf(TopicPartition(record.topic(), record.partition()) to
                          OffsetAndMetadata(record.offset() + 1)),
                consumer.groupMetadata())
        }
    }
}
```

The `Consumer` parameter is **required** — both to obtain `groupMetadata()` and to stop Kora from
committing the offset itself outside the transaction. The consumer must have a `group.id`
(subscribe mode); in assign mode there is no group metadata to send.

---

## Configuration

```hocon
kafka {
  producer {
    my-publisher {
      driverProperties {
        "bootstrap.servers" = ${?KAFKA_BOOTSTRAP}
      }
      telemetry.logging.enabled = true
    }

    my-transactional {
      idPrefix = "my-transaction"   # default "kora-app-"; a random UUID is appended
      maxPoolSize = 10              # transactional producer pool size
      maxWaitTime = 10s             # wait for a free producer from the pool
      telemetry.logging.enabled = true
    }

    my-topic {
      topic = "my-topic-producer"
    }
  }
}
```

`idPrefix` / `maxPoolSize` / `maxWaitTime` belong to `KafkaPublisherConfig.TransactionConfig` and are
read from the **transactional** section; `driverProperties` and `telemetry` come from the wrapped
publisher's own section.

---

## Consumer side: `read_committed`

A consumer that must not see aborted records sets the standard Kafka property:

```hocon
kafka.consumer.transactional-pipeline {
  topics = ["transactional-input"]
  driverProperties {
    "bootstrap.servers" = ${?KAFKA_BOOTSTRAP}
    "group.id" = "transactional-pipeline"
    "auto.offset.reset" = "earliest"
    "enable.auto.commit" = false
    "isolation.level" = "read_committed"
  }
}
```

The default is `read_uncommitted`, so without this the consumer sees records from transactions that
were later aborted. Nothing else about the listener changes — ordinary signatures apply.

---

## Pitfalls

| Symptom | Cause | Fix |
|---|---|---|
| Aborted records still consumed | default `read_uncommitted` | `"isolation.level" = "read_committed"` |
| Offsets committed outside the transaction | no `Consumer` parameter, so Kora commits after the handler | declare `Consumer<K, V>` and use `sendOffsetsToTransaction` |
| Transaction never commits | `begin()` without try-with-resources / `use` | `close()` is the commit |
| Producers exhausted after `maxWaitTime` | transactions left open | always close; raise `maxPoolSize` only after fixing leaks |
| Partial batch published | exception caught **inside** the callback | let it propagate so `inTx`/`withTx` aborts |
| Kotlin: ambiguous `inTx` overload | four functional overloads | use `begin().use { }` or an explicit SAM constructor |
| `groupMetadata()` fails | assign mode has no consumer group | give the consumer a `group.id` |
| Looking for `@KoraTransaction` | it does not exist | use `TransactionalPublisher` |

---

## Related references

- [Offsets](kafka-offset-reference.md)
- [Listener signatures](kafka-listener-reference.md)
- [kora-kafka-producer](../../kora-kafka-producer/SKILL.md)

**Source:** framework tag `2.0.0.RC2` —
[TransactionalPublisher](https://github.com/kora-projects/kora/blob/2.0.0.RC2/kafka/kafka/src/main/java/io/koraframework/kafka/common/producer/TransactionalPublisher.java) ·
[KafkaPublisherConfig](https://github.com/kora-projects/kora/blob/2.0.0.RC2/kafka/kafka/src/main/java/io/koraframework/kafka/common/producer/KafkaPublisherConfig.java);
migrated examples on `migration/2.0` —
[kora-java-kafka](https://github.com/kora-projects/kora-examples/tree/migration/2.0/examples/java/kora-java-kafka) ·
[kora-kotlin-kafka](https://github.com/kora-projects/kora-examples/tree/migration/2.0/examples/kotlin/kora-kotlin-kafka)
