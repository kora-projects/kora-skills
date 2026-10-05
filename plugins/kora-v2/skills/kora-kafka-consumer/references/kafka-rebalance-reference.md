# Kafka Rebalance Reference (Kora 2.0)

Reacting to partition assignment changes with `ConsumerAwareRebalanceListener`.

## Contents

- [The contract](#the-contract)
- [How Kora finds your listener](#how-kora-finds-your-listener)
- [Subscribe only](#subscribe-only)
- [Implementation](#implementation)
- [What to do in each callback](#what-to-do-in-each-callback)
- [Tuning rebalance behaviour](#tuning-rebalance-behaviour)
- [Pitfalls](#pitfalls)

---

## The contract

```java
package io.koraframework.kafka.common.consumer;

public interface ConsumerAwareRebalanceListener {

    void onPartitionsRevoked(Consumer<?, ?> consumer, Collection<TopicPartition> partitions);

    void onPartitionsAssigned(Consumer<?, ?> consumer, Collection<TopicPartition> partitions);

    default void onPartitionsLost(Consumer<?, ?> consumer, Collection<TopicPartition> partitions) {
        onPartitionsRevoked(consumer, partitions);
    }
}
```

It is Kora's own interface, not `org.apache.kafka.clients.consumer.ConsumerRebalanceListener` — the
container adapts one to the other so that you also receive the `Consumer`. Only `onPartitionsLost`
has a default, and **its default delegates to `onPartitionsRevoked`**. If your revoke path commits,
override `onPartitionsLost` explicitly — otherwise a lost assignment attempts a commit it no longer
owns.

The `Consumer` handed to the callbacks is the same `ConsumerWrapper` the listener sees.

---

## How Kora finds your listener

The generated container method declares:

```java
@Tag(OrderListenerModule.OrderListenerProcessTag.class)
@Nullable ConsumerAwareRebalanceListener rebalanceListener
```

So the binding is **by tag**, and the parameter is `@Nullable` — a missing listener is not an error,
it simply never fires. Two ways to match the tag:

**Generated tag** — `<Class>Module.<Class><Method>Tag`:

```java
@Tag(OrderListenerModule.OrderListenerProcessTag.class)
@Component
public final class OrderRebalanceListener implements ConsumerAwareRebalanceListener { ... }
```

**Explicit tag** — clearer, and independent of the class and method names:

```java
public final class OrdersTag {}

@Component
public final class OrderListener {
    @KafkaListener(value = "kafka.consumer.orders", tag = OrdersTag.class)
    void process(String value) { }
}

@Tag(OrdersTag.class)
@Component
public final class OrderRebalanceListener implements ConsumerAwareRebalanceListener { ... }
```

One listener per tag. A `ConsumerAwareRebalanceListener` with no tag, or with the wrong tag, is
silently unused — there is no warning.

---

## Subscribe only

Only `KafkaSubscribeConsumerContainer` uses it, and only there because `subscribe(topics, callback)`
takes a callback. In assign mode (no `group.id`) there is no group, no rebalance and no callback;
`KafkaAssignConsumerContainer` does not even accept the parameter.

---

## Implementation

```java
@Tag(OrdersTag.class)
@Component
public final class OrderRebalanceListener implements ConsumerAwareRebalanceListener {

    private static final Logger log = LoggerFactory.getLogger(OrderRebalanceListener.class);

    private final PartitionCache cache;

    public OrderRebalanceListener(PartitionCache cache) {
        this.cache = cache;
    }

    @Override
    public void onPartitionsRevoked(Consumer<?, ?> consumer, Collection<TopicPartition> partitions) {
        log.info("Partitions revoked: {}", partitions);
        consumer.commitSync();          // only if you own commits
        partitions.forEach(cache::evict);
    }

    @Override
    public void onPartitionsAssigned(Consumer<?, ?> consumer, Collection<TopicPartition> partitions) {
        log.info("Partitions assigned: {}", partitions);
        partitions.forEach(cache::prepare);
    }

    @Override
    public void onPartitionsLost(Consumer<?, ?> consumer, Collection<TopicPartition> partitions) {
        log.warn("Partitions lost: {}", partitions);
        partitions.forEach(cache::evict);   // no commit — the partitions are already gone
    }
}
```

```kotlin
@Tag(OrdersTag::class)
@Component
class OrderRebalanceListener(private val cache: PartitionCache) : ConsumerAwareRebalanceListener {

    override fun onPartitionsRevoked(consumer: Consumer<*, *>, partitions: Collection<TopicPartition>) {
        consumer.commitSync()
        partitions.forEach(cache::evict)
    }

    override fun onPartitionsAssigned(consumer: Consumer<*, *>, partitions: Collection<TopicPartition>) {
        partitions.forEach(cache::prepare)
    }

    override fun onPartitionsLost(consumer: Consumer<*, *>, partitions: Collection<TopicPartition>) {
        partitions.forEach(cache::evict)
    }
}
```

The callbacks run **on the poll thread**, between polls. Time spent here counts against
`max.poll.interval.ms` and delays the whole group's rebalance — keep them short.

---

## What to do in each callback

| Callback | Do | Do not |
|---|---|---|
| `onPartitionsRevoked` | commit if you own commits, flush buffers, drop partition-scoped state | long I/O, blocking network calls |
| `onPartitionsAssigned` | warm caches, log the assignment, reset counters | assume the set is a delta — it is the full new assignment |
| `onPartitionsLost` | drop state only | **commit** — the partitions are already reassigned |

With Kora-managed commits (no `Consumer` parameter, `enable.auto.commit` unset) every completed
record is already committed, so `onPartitionsRevoked` does not need to commit at all. The callback
then exists purely for state cleanup.

---

## Tuning rebalance behaviour

All `driverProperties`, all standard Kafka:

| Property | Meaning |
|---|---|
| `max.poll.interval.ms` | deadline for processing one poll before eviction (default 5 min) |
| `session.timeout.ms` | heartbeat deadline (default 45 s in the 4.x line) |
| `heartbeat.interval.ms` | heartbeat period, roughly a third of the session timeout |
| `partition.assignment.strategy` | e.g. `CooperativeStickyAssignor` for incremental rebalances |
| `group.instance.id` | static membership — a restart within the session timeout does not rebalance |

Reducing rebalance impact is mostly about **not being slow**: shrink `max.poll.records`, cap retry
time inside handlers, and keep the rebalance callbacks trivial. Note that a consumer that dies on a
poison record restarts and rejoins, rebalancing the group each time — see the
[error handling reference](kafka-error-handling-reference.md).

---

## Pitfalls

| Symptom | Cause | Fix |
|---|---|---|
| Callback never fires | tag mismatch — the parameter is `@Nullable`, so nothing complains | tag both listener and rebalance listener with the same class |
| Callback never fires | assign mode (no `group.id`) | rebalance exists only for consumer groups |
| Callback never fires | the class is not a `@Component` | register it |
| `Multiple components match ConsumerAwareRebalanceListener` | two components share one tag | one per tag |
| Commit fails inside `onPartitionsLost` | the default delegates to `onPartitionsRevoked`, which commits | override `onPartitionsLost` |
| Rebalances take minutes | slow callbacks or a slow handler | shorten both; consider `CooperativeStickyAssignor` |
| Duplicates after every rebalance | manual commits that never ran before revocation | commit in `onPartitionsRevoked`, or let Kora commit |
| Rolling restarts churn the group | no static membership | set `group.instance.id` per replica |

---

## Related references

- [Listener signatures](kafka-listener-reference.md) — how the tag is generated
- [Strategies](kafka-strategies-reference.md) — subscribe vs assign
- [Offsets](kafka-offset-reference.md)
- [Error handling](kafka-error-handling-reference.md)

**Source:** framework tag `2.0.0.RC2` —
[ConsumerAwareRebalanceListener](https://github.com/kora-projects/kora/blob/2.0.0.RC2/kafka/kafka/src/main/java/io/koraframework/kafka/common/consumer/ConsumerAwareRebalanceListener.java) ·
[KafkaSubscribeConsumerContainer](https://github.com/kora-projects/kora/blob/2.0.0.RC2/kafka/kafka/src/main/java/io/koraframework/kafka/common/consumer/containers/KafkaSubscribeConsumerContainer.java)
