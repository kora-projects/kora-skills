# Kafka Batch Processing Reference (Kora 2.0)

Consuming a whole poll at once with `ConsumerRecords<K, V>`.

## Contents

- [What a batch listener is](#what-a-batch-listener-is)
- [Accepted parameters](#accepted-parameters)
- [Commit semantics](#commit-semantics)
- [Deserialization inside a batch](#deserialization-inside-a-batch)
- [Error handling](#error-handling)
- [Batch database writes](#batch-database-writes)
- [Empty polls](#empty-polls)
- [Tuning](#tuning)
- [Pitfalls](#pitfalls)

---

## What a batch listener is

Declaring a `ConsumerRecords<K, V>` parameter switches the generated handler from
`KafkaRecordHandler` to `KafkaRecordsHandler`: your method is called **once per poll** with
everything that poll returned.

```java
@Component
public final class OrderBatchListener {

    @KafkaListener("kafka.consumer.orders")
    void process(ConsumerRecords<String, String> records) {
        for (ConsumerRecord<String, String> record : records) {
            orderService.handle(record.value());
        }
    }
}
```

```kotlin
@Component
class OrderBatchListener {
    @KafkaListener("kafka.consumer.orders")
    fun process(records: ConsumerRecords<String, String>) {
        records.forEach { orderService.handle(it.value()) }
    }
}
```

Batch size is `max.poll.records` (Kafka's default is 500) bounded by `pollTimeout`, `fetch.min.bytes`
and `fetch.max.wait.ms`. It is never larger than one poll — there is no accumulation across polls.

---

## Accepted parameters

Only two:

| Parameter | Effect |
|---|---|
| `ConsumerRecords<K, V>` | required — the batch |
| `Consumer<K, V>` | optional — disables Kora's automatic commit |

Everything else fails with `Kafka records listener method has unsupported parameter`, including
`Headers` and any exception parameter. Group by partition through the API instead:

```java
for (TopicPartition partition : records.partitions()) {
    for (ConsumerRecord<String, String> record : records.records(partition)) {
        record.headers();   // per-record headers
    }
}
```

`ConsumerRecords<?, V>` is accepted and delivers keys as `byte[]`.

---

## Commit semantics

| `Consumer` parameter | `enable.auto.commit` | Who commits |
|---|---|---|
| absent | unset / `false` | **Kora**, one `consumer.commitSync()` after your method returns |
| absent | `true` | the driver's timer |
| present | any | **you** |

Kora's batch commit is all-or-nothing: if your method throws halfway through, **nothing** is
committed and the whole poll is redelivered. Partial progress must therefore be idempotent, or you
must commit explicit offsets yourself — see the [offset reference](kafka-offset-reference.md).

---

## Deserialization inside a batch

Records are still `ConsumerRecordWrapper`s, so `record.key()` / `record.value()` decode lazily and
throw `RecordKeyDeserializationException` / `RecordValueDeserializationException` **inside your
loop**. There is no exception parameter to catch it for you:

```java
@KafkaListener("kafka.consumer.orders")
void process(ConsumerRecords<String, @Json OrderEvent> records) {
    for (var record : records) {
        try {
            orderService.handle(record.value());
        } catch (RecordValueDeserializationException e) {
            dlq.send(e.getRecord().key(), e.getRecord().value());
        }
    }
}
```

Without that try/catch one corrupt record aborts the batch, nothing is committed, and the whole poll
replays — repeatedly.

---

## Error handling

`RecordsHandler` observes the error and rethrows it. It has **no** skip branch, so
`KafkaSkipRecordException` and `SkippableRecordException` are ordinary exceptions in a batch listener.
Filter explicitly:

```java
for (var record : records) {
    if (!isProcessable(record)) {
        skipped.increment();
        continue;
    }
    handle(record);
}
```

An exception that escapes ends the poll loop, triggers the `backoffTimeout` backoff and rebuilds the
consumer. See the [error handling reference](kafka-error-handling-reference.md).

---

## Batch database writes

The reason to use a batch listener: one round-trip instead of N.

```java
@Component
public final class OrderBatchListener {

    private final OrderRepository repository;

    public OrderBatchListener(OrderRepository repository) {
        this.repository = repository;
    }

    @KafkaListener("kafka.consumer.orders")
    void process(ConsumerRecords<String, @Json OrderEvent> records) {
        var batch = new ArrayList<OrderEvent>(records.count());
        for (var record : records) {
            batch.add(record.value());
        }
        if (!batch.isEmpty()) {
            repository.insertAll(batch);   // @Batch repository method
        }
    }
}
```

Kora repositories are synchronous, so this runs on the poll thread. Keep the total under
`max.poll.interval.ms` — with `max.poll.records = 500` and a 300 s interval you have 600 ms per
record before the broker evicts the consumer. See
[kora-database-jdbc](../../kora-database-jdbc/SKILL.md) for `@Batch`.

---

## Empty polls

`RecordsHandler` returns immediately on an empty `ConsumerRecords` unless `allowEmptyRecords = true`:

```hocon
kafka.consumer.orders {
  allowEmptyRecords = true
}
```

Use it only for a heartbeat or a flush tick; it makes your method run on every `pollTimeout` even
when nothing arrived. The flag has no effect on single-record listeners.

---

## Tuning

| `driverProperties` key | Effect |
|---|---|
| `max.poll.records` | upper bound on batch size (default 500) |
| `fetch.min.bytes` | broker waits for this much data before answering — raise for fuller batches |
| `fetch.max.wait.ms` | cap on that wait |
| `max.partition.fetch.bytes` | per-partition response cap |
| `max.poll.interval.ms` | eviction deadline for one batch |

| Kora key | Effect |
|---|---|
| `pollTimeout` | client-side wait per poll (default `5s`) |
| `threads` | independent consumers, each polling its own batch |
| `allowEmptyRecords` | deliver empty polls |

Throughput setup: raise `fetch.min.bytes` (e.g. 1 MiB) and `max.poll.records`, keep
`fetch.max.wait.ms` modest so latency stays bounded. Latency setup: leave `fetch.min.bytes = 1` and
lower `pollTimeout`.

---

## Pitfalls

| Symptom | Cause | Fix |
|---|---|---|
| `Kafka records listener method has unsupported parameter` | `Headers` or an exception parameter on a batch listener | use `record.headers()`; try/catch inside the loop |
| Whole batch replays after one bad record | batch commit is all-or-nothing | try/catch per record, or commit explicit offsets |
| `KafkaSkipRecordException` does not skip | batch handler has no skip branch | `continue` in the loop |
| Consumer evicted, endless rebalance | batch takes longer than `max.poll.interval.ms` | lower `max.poll.records` or raise the interval |
| Batches are always tiny | `fetch.min.bytes = 1` | raise it and `fetch.max.wait.ms` |
| Method never called although records arrive | `threads = 0` | `threads >= 1` |
| Method called constantly with 0 records | `allowEmptyRecords = true` | set it back to `false` |
| Mid-batch `commitSync()` commits too much | the no-arg overload commits the poll position | pass an explicit offset map |

---

## Related references

- [Listener signatures](kafka-listener-reference.md)
- [Offsets](kafka-offset-reference.md)
- [Error handling](kafka-error-handling-reference.md)
- [Consumer configuration](kafka-consumer-reference.md)

**Source:** framework tag `2.0.0.RC2` —
[RecordsHandler](https://github.com/kora-projects/kora/blob/2.0.0.RC2/kafka/kafka/src/main/java/io/koraframework/kafka/common/consumer/containers/handlers/impl/RecordsHandler.java) ·
[HandlerWrapper](https://github.com/kora-projects/kora/blob/2.0.0.RC2/kafka/kafka/src/main/java/io/koraframework/kafka/common/consumer/containers/handlers/wrapper/HandlerWrapper.java);
[Apache Kafka consumer configs](https://kafka.apache.org/documentation/#consumerconfigs)
