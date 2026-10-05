# Kafka Offset Reference (Kora 2.0)

Who commits, when, and what happens when nobody does.

## Contents

- [The decision table](#the-decision-table)
- [Kora-managed commits](#kora-managed-commits)
- [Driver auto-commit](#driver-auto-commit)
- [Manual commits](#manual-commits)
- [Assign mode](#assign-mode)
- [Where reading starts](#where-reading-starts)
- [Rebalance and shutdown](#rebalance-and-shutdown)
- [Pitfalls](#pitfalls)

---

## The decision table

Two independent switches. The **signature** decides whether Kora commits at all
(`shouldCommit = <no Consumer parameter>`, fixed at compile time); the **driver property** decides
whether commits are allowed (`commitAllowed = !enable.auto.commit`, evaluated in the container).

| `Consumer` parameter | `enable.auto.commit` | Who commits | When |
|---|---|---|---|
| absent | unset | **Kora** | after each record (record/key-value shape) or after the poll (batch shape) |
| absent | `false` | **Kora** | as above |
| absent | `true` | **Kafka driver** | on its own timer, independent of your handler |
| present | any | **you** | wherever you call `commitSync()` |
| any | any, assign mode | **nobody** | commits are disabled |

If `enable.auto.commit` is absent the subscribe container rewrites the properties with
`enable.auto.commit = false` before creating the client, so the default is Kora-managed commits.

---

## Kora-managed commits

The natural, safest shape: no `Consumer` parameter, no `enable.auto.commit`.

```java
@KafkaListener("kafka.consumer.orders")
void process(String value) {
    orderService.handle(value);
}   // Kora commits offset+1 for this record here
```

**Single-record shape** — `RecordHandler` commits per record, after your method returns:

```java
consumer.commitSync(Map.of(
    new TopicPartition(record.topic(), record.partition()),
    new OffsetAndMetadata(record.offset() + 1, record.leaderEpoch(), NO_METADATA)));
```

The committed value is `offset + 1` — the next record to read. If the commit throws `WakeupException`
(shutdown racing the commit) it is retried once and then rethrown.

**Batch shape** — `RecordsHandler` commits once, after your method returns, with a plain
`consumer.commitSync()` covering the whole poll.

A record that throws is **not** committed, so it is redelivered — unless it threw
`KafkaSkipRecordException` or a `SkippableRecordException`, which are swallowed and *do* commit.

Delivery is therefore **at-least-once**. Make handlers idempotent.

---

## Driver auto-commit

`"enable.auto.commit" = true` hands committing to the Kafka client's background timer. Kora then
skips its own commit entirely (`commitAllowed = false`).

This is what the Kora example applications use, because it is fast and the examples tolerate loss.
It is **not** the safe default for business processing: the driver can commit an offset whose record
your handler has not finished, so a crash loses it. Prefer leaving the key unset.

---

## Manual commits

Adding a `Consumer<K, V>` parameter switches Kora's automatic commit off for that listener — even if
you never call `commitSync()`. Forgetting the call means the group never advances and every restart
replays from the last committed position.

```java
@KafkaListener("kafka.consumer.orders")
void process(ConsumerRecord<String, String> record, Consumer<String, String> consumer) {
    orderRepository.insert(record.value());
    consumer.commitSync();
}
```

Do not swallow the exception before committing — if the write failed, not committing is the point.

**Batch with periodic commits.** `commitSync()` without arguments commits the consumer's current
position for all assigned partitions, which after iterating part of a batch is the position of the
last record *returned by the poll*, not the last one you processed. To checkpoint mid-batch
accurately, commit explicit offsets:

```java
@KafkaListener("kafka.consumer.analytics")
void process(ConsumerRecords<String, String> records, Consumer<String, String> consumer) {
    var pending = new HashMap<TopicPartition, OffsetAndMetadata>();
    int n = 0;
    for (var record : records) {
        analytics.handle(record.value());
        pending.put(new TopicPartition(record.topic(), record.partition()),
                    new OffsetAndMetadata(record.offset() + 1));
        if (++n % 100 == 0) {
            consumer.commitSync(pending);
            pending.clear();
        }
    }
    if (!pending.isEmpty()) {
        consumer.commitSync(pending);
    }
}
```

**Read-process-write.** To tie the commit to a Kafka write, commit through the producer transaction
instead of the consumer — `Transaction.sendOffsetsToTransaction(offsets, consumer.groupMetadata())`.
See the [transactions reference](kafka-transactions-reference.md).

---

## Assign mode

Without a `group.id` there is no group, no committed offset, and `commitAllowed` is hardcoded
`false`. The container tracks the last offset per partition **in memory** and re-seeks to it when
partitions are refreshed. A restart starts over from the `offset` config key.

---

## Where reading starts

| Mode | Key | Effect |
|---|---|---|
| Subscribe, group has committed offsets | — | resumes at the committed offset; `offset` and `auto.offset.reset` are both ignored |
| Subscribe, brand-new group | `auto.offset.reset` (`earliest` / `latest`) | driver property, **not** the Kora `offset` key |
| Assign | `offset` = `earliest` / `latest` / a `Duration` | Kora seeks explicitly on every assignment |

The most common misconfiguration is `offset = "earliest"` in a section that has a `group.id`: it does
nothing, and the group starts at `latest` because `auto.offset.reset` defaults to `latest`.

---

## Rebalance and shutdown

**Rebalance.** With Kora-managed commits the offset of every completed record is already committed,
so a rebalance loses nothing. With manual commits, commit in `onPartitionsRevoked` — see the
[rebalance reference](kafka-rebalance-reference.md). Never commit in `onPartitionsLost`; the
partitions are already gone.

**Shutdown.** `release()` wakes each consumer and waits `shutdownWait` for in-flight handlers.
There is no final "commit everything" step: a handler that was interrupted did not commit, and its
record is redelivered. `shutdownWait` should exceed your slowest handler.

---

## Pitfalls

| Symptom | Cause | Fix |
|---|---|---|
| Records reprocessed after every restart | a `Consumer` parameter is declared but `commitSync()` is never called | commit, or drop the parameter |
| Records lost on a crash | `"enable.auto.commit" = true` commits ahead of the handler | remove the key and let Kora commit |
| `offset = "earliest"` has no effect | `group.id` is set | use `auto.offset.reset = "earliest"` |
| Lag never decreases although processing succeeds | assign mode — nothing is committed | expected; use subscribe if you need committed offsets |
| Poison record replays forever | handler throws on every attempt, so it is never committed | `KafkaSkipRecordException`, or route to a DLQ and return |
| `WakeupException` in commit logs during shutdown | commit raced `release()` | Kora retries once; harmless |
| Mid-batch `commitSync()` commits too much | the no-arg overload commits the poll position | pass an explicit offset map |

---

## Related references

- [Listener signatures](kafka-listener-reference.md)
- [Strategies](kafka-strategies-reference.md)
- [Batch processing](kafka-batch-reference.md)
- [Rebalance](kafka-rebalance-reference.md)
- [Transactions](kafka-transactions-reference.md)

**Source:** framework tag `2.0.0.RC2` —
[RecordHandler](https://github.com/kora-projects/kora/blob/2.0.0.RC2/kafka/kafka/src/main/java/io/koraframework/kafka/common/consumer/containers/handlers/impl/RecordHandler.java) ·
[RecordsHandler](https://github.com/kora-projects/kora/blob/2.0.0.RC2/kafka/kafka/src/main/java/io/koraframework/kafka/common/consumer/containers/handlers/impl/RecordsHandler.java) ·
[KafkaSubscribeConsumerContainer](https://github.com/kora-projects/kora/blob/2.0.0.RC2/kafka/kafka/src/main/java/io/koraframework/kafka/common/consumer/containers/KafkaSubscribeConsumerContainer.java)
