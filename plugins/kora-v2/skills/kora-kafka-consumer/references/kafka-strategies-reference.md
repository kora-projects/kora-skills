# Kafka Consumption Strategies Reference (Kora 2.0)

Kora picks the container from one thing: whether `group.id` is present in `driverProperties`.

```java
if (config.driverProperties().getProperty(CommonClientConfigs.GROUP_ID_CONFIG) == null) {
    return new KafkaAssignConsumerContainer<>(...);
} else {
    return new KafkaSubscribeConsumerContainer<>(...);
}
```

Nothing else selects it — there is no `strategy` config key.

## Contents

- [Subscribe](#subscribe-groupid-set)
- [Assign](#assign-no-groupid)
- [Side-by-side](#side-by-side)
- [Choosing](#choosing)
- [Failure modes](#failure-modes)

---

## Subscribe (`group.id` set)

Ordinary consumer-group membership. The broker splits partitions across group members; each record
goes to exactly one member.

```hocon
kafka.consumer.orders {
  topics = ["orders"]
  driverProperties {
    "bootstrap.servers" = ${?KAFKA_BOOTSTRAP}
    "group.id" = "order-service"
    "auto.offset.reset" = "earliest"
  }
}
```

- Multiple topics are fine, and `topicsPattern` works here (it is the only mode that accepts it).
- A `ConsumerAwareRebalanceListener` tagged with the listener's tag is wired into
  `subscribe(...)` and receives revoke / assign / lost callbacks.
- Offsets are committed — by Kora, by the driver, or by you. See the
  [offset reference](kafka-offset-reference.md).
- The `offset` config key is **ignored**: committed offsets, or `auto.offset.reset` for a brand-new
  group, decide where reading starts.
- The constructor throws `IllegalArgumentException("Group id is required for subscribe container")`
  if it is ever built without one.

Scale by adding instances (or `threads`), up to the partition count. Beyond that the extras idle.

---

## Assign (no `group.id`)

Every instance assigns itself **all** partitions of every listed topic and reads everything. This is
the broadcast / local-cache shape.

```hocon
kafka.consumer.price-cache {
  topics = ["prices", "rates"]
  offset = "earliest"
  partitionRefreshInterval = 1m
  driverProperties {
    "bootstrap.servers" = ${?KAFKA_BOOTSTRAP}
  }
}
```

- **`topics` takes one or more topics.** The container reads `config.topics()` itself and tracks
  offsets per `TopicPartition`, so partition numbers of different topics never collide.
- **Validated in the constructor, fail-fast.** `KafkaAssignConsumerContainer` throws
  `IllegalArgumentException` while the graph is built, so the application does not start:
  - `topicsPattern` set → `@KafkaListener with assign strategy (when group.id is null) does not support topicsPattern, please specify topics instead`
    (a pattern needs the group rebalance protocol to resolve matches);
  - `topics` null or empty → `@KafkaListener with assign strategy (when group.id is null) requires at least one topic to subscribe, but received: ...`.
- The constructor is `(listenerConfig, listenerImpl, KafkaListenerConfig, keyDeserializer,
  valueDeserializer, telemetry, handler)` — there is no topic argument; the generated
  `<Listener>Module` calls it for you. Code that constructed the container by hand with a topic
  argument no longer compiles.
- **Nothing is ever committed.** The container calls `handler.handle(observation, records, consumer,
  false)` — `commitAllowed = false` — so neither Kora nor a `Consumer` parameter can commit
  meaningfully. Position is in-memory only and resets on restart to whatever `offset` says.
- `offset` decides the start position (`earliest` / `latest` / a `Duration` rewind via
  `offsetsForTimes`).
- Partitions of every listed topic are re-read every `partitionRefreshInterval` with a throwaway
  consumer so that new partitions are picked up; a change triggers a re-assign and re-seek to the last in-memory offset.
- The **consumer lag gauge** (`messaging.kafka.consumer.lag`) is reported only here — the subscribe
  container never calls `reportLag`.
- No rebalance listener: there is no group, so `ConsumerAwareRebalanceListener` is not consulted.

---

## Side-by-side

| | Subscribe | Assign |
|---|---|---|
| Trigger | `group.id` set | `group.id` absent |
| Delivery | one member per record | every instance gets every record |
| Topics | many, or a pattern | one or more, no pattern |
| Offsets | committed | never committed |
| `offset` config key | ignored | authoritative |
| `auto.offset.reset` | authoritative for a new group | irrelevant |
| Rebalance listener | wired | ignored |
| Lag gauge | not emitted | emitted |
| Restart behaviour | resumes at the committed offset | re-seeks per `offset` |

---

## Choosing

Use **subscribe** for anything that must be processed once: order processing, notifications, writes
to a shared database, work queues.

Use **assign** when every replica needs the same stream: refreshing an in-process cache, building a
per-instance index, a local routing table, a config stream. Accept that a restart replays from
`offset` and that there is no lag-based backpressure signal from committed offsets — only the gauge.

Two independent consumers of the same topic just need two different `group.id`s and two config
sections; they do not need assign mode.

---

## Failure modes

| Symptom | Cause | Fix |
|---|---|---|
| `assign strategy (when group.id is null) does not support topicsPattern` | `topicsPattern` without `group.id` | list the topics explicitly, or add `group.id` |
| `assign strategy (when group.id is null) requires at least one topic` | no `group.id`, `topics` missing or empty | list the topics, or add `group.id` |
| Every instance processes every record | `group.id` missing — you are in assign mode without meaning to be | add `group.id` |
| Records replayed on every restart | assign mode with `offset = "earliest"` | switch to subscribe, or accept the replay and make handlers idempotent |
| `consumer.commitSync()` appears to do nothing | assign mode: `commitAllowed = false` | commits are meaningless without a group |
| Rebalance listener never fires | assign mode, or a tag mismatch | subscribe mode + matching `@Tag` |
| Some instances idle | more members than partitions | add partitions or reduce `threads`/replicas |

---

## Related references

- [Consumer configuration](kafka-consumer-reference.md)
- [Offsets](kafka-offset-reference.md)
- [Rebalance](kafka-rebalance-reference.md)
- [Telemetry](kafka-telemetry-reference.md)

**Source:** framework tag `2.0.0.RC2` —
[KafkaSubscribeConsumerContainer](https://github.com/kora-projects/kora/blob/2.0.0.RC2/kafka/kafka/src/main/java/io/koraframework/kafka/common/consumer/containers/KafkaSubscribeConsumerContainer.java) ·
[KafkaAssignConsumerContainer](https://github.com/kora-projects/kora/blob/2.0.0.RC2/kafka/kafka/src/main/java/io/koraframework/kafka/common/consumer/containers/KafkaAssignConsumerContainer.java)
