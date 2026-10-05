# Kafka Consumer Error Handling Reference (Kora 2.0)

What the container does with a thrown exception, and the patterns that follow from it.

## Contents

- [Exception types](#exception-types)
- [What the container does](#what-the-container-does)
- [Deserialization failures](#deserialization-failures)
- [Skipping a record](#skipping-a-record)
- [Dead letter queue](#dead-letter-queue)
- [Retry](#retry)
- [Backoff and restart](#backoff-and-restart)
- [Pitfalls](#pitfalls)

---

## Exception types

All in `io.koraframework.kafka.common.exceptions`:

| Type | Kind | Meaning |
|---|---|---|
| `RecordKeyDeserializationException` | `extends org.apache.kafka.common.errors.SerializationException` | key could not be decoded; `getRecord()` returns the raw `ConsumerRecord<byte[], byte[]>` |
| `RecordValueDeserializationException` | same | value could not be decoded; same `getRecord()` |
| `KafkaSkipRecordException` | `extends RuntimeException` | wrap a cause in it to report-and-skip the record |
| `SkippableRecordException` | **interface**, no methods | implement it on your own exception to get the same treatment |
| `KafkaPublishException` | `extends org.apache.kafka.common.KafkaException` | producer side; the real cause is in `getCause()` |

`KafkaSkipRecordException(Throwable cause)` — the cause is `@NonNull`; there is no message-only
constructor.

---

## What the container does

Single-record listeners run inside `RecordHandler`:

```java
try {
    recordObservation.observeHandle();
    handler.handle(consumer, recordObservation, record);
} catch (Throwable e) {
    recordObservation.observeError(e);
    if (!(e instanceof KafkaSkipRecordException) && !(e instanceof SkippableRecordException)) {
        throw e;
    }
}
if (shouldCommit && commitAllowed) { /* commit offset + 1 */ }
```

| Thrown | Telemetry | Offset | Loop |
|---|---|---|---|
| `KafkaSkipRecordException` | error recorded | **committed** | continues to the next record |
| an exception implementing `SkippableRecordException` | error recorded | **committed** | continues |
| anything else | error recorded | not committed | propagates to the poll loop |

`RecordsHandler` (batch) has **no** skip branch — every `Throwable` is observed and rethrown, so
`KafkaSkipRecordException` does nothing useful in a batch listener. Filter inside the loop instead.

When an exception reaches the poll loop, the container ends the observation, logs, sleeps
`backoffTimeout`, doubles it (capped at 60 s) and **breaks out of the loop**. The outer thread then
builds a brand-new consumer and starts polling again from the last committed offset — so every
uncommitted record in that poll is redelivered.

---

## Deserialization failures

Deserialization is lazy, so where the failure surfaces depends on the signature.

**Nullable payload + exception parameter** — the processor wraps the decode in a `try` and hands you
the failure. This is the production shape, and the one the migrated guide app uses:

```java
@KafkaListener("kafka.consumer.user-created")
public void process(@Json @Nullable UserCreatedEvent event, @Nullable Exception exception) {
    if (exception != null) {
        logger.warn("Failed to consume user creation event", exception);
        return;
    }
    if (event == null) {
        logger.warn("Received null event without exception");
        return;
    }
    userService.createUser(event);
}
```

`@Nullable` is `org.jspecify.annotations.Nullable` and is a **type-use** annotation. The processor
inspects the type element, so the annotation does not hide the parameter's role.

Narrow the parameter to catch only one side:

```java
void process(@Json @Nullable OrderEvent value, @Nullable RecordValueDeserializationException e)
```

With a key **and** a value parameter, either failure nulls both payload parameters. With only a value
parameter, a key failure is not caught at all — the value is still delivered.

**`ConsumerRecord` + try/catch** — decode yourself and reach the raw bytes:

```java
@KafkaListener("kafka.consumer.orders")
void process(ConsumerRecord<String, OrderEvent> record) {
    try {
        orderService.handle(record.value());
    } catch (RecordValueDeserializationException e) {
        ConsumerRecord<byte[], byte[]> raw = e.getRecord();
        dlq.send(raw.topic(), raw.key(), raw.value(), e.getMessage());
    }
}
```

**Neither** — a corrupt record throws out of the listener, is not committed, and is redelivered
forever after each `backoffTimeout`. That is the poison-pill loop.

---

## Skipping a record

```java
@KafkaListener("kafka.consumer.orders")
public void process(String value) {
    if (value.startsWith("skip:")) {
        throw new KafkaSkipRecordException(new IllegalArgumentException("Unsupported record: " + value));
    }
    orderService.handle(value);
}
```

The record is reported to telemetry as an error, the offset is committed, and the loop continues.

For a family of business exceptions, implement the marker instead:

```java
public class UnprocessableEventException extends RuntimeException implements SkippableRecordException {
    public UnprocessableEventException(String message) { super(message); }
}
```

Both only work in the single-record shape.

---

## Dead letter queue

Kora has no built-in DLQ. Declare a `@KafkaPublisher` and send from the error branch:

```java
@KafkaPublisher("kafka.producer.dlq")
public interface DlqPublisher {
    @KafkaPublisher.Topic("kafka.producer.dlq.topic")
    void send(byte[] key, byte[] value);
}

@Component
public final class OrderListener {

    private final DlqPublisher dlq;

    public OrderListener(DlqPublisher dlq) { this.dlq = dlq; }

    @KafkaListener("kafka.consumer.orders")
    void process(ConsumerRecord<String, OrderEvent> record) {
        try {
            orderService.handle(record.value());
        } catch (RecordValueDeserializationException e) {
            var raw = e.getRecord();
            dlq.send(raw.key(), raw.value());
        }
    }
}
```

Route the **raw bytes** from `getRecord()`, not a re-serialized object — the payload could not be
parsed, so there is nothing to re-serialize. Details of the publisher side:
[kora-kafka-producer](../../kora-kafka-producer/SKILL.md).

---

## Retry

Kora's resilience aspects apply to a listener method like any other. Declare a typed spec interface
and annotate the method — this is what the migrated example does:

```java
@RetrySpec("resilient.retry.kafka-listener")
public interface KafkaListenerRetry extends Retry {}

@Component
public class RetryListener {

    @Retryable(KafkaListenerRetry.class)
    @KafkaListener("kafka.consumer.retry-listener")
    public void process(String value) {
        externalService.call(value);
    }
}
```

```hocon
resilient.retry.kafka-listener {
  delay = 10ms
  attempts = 3
}
```

Retries happen **inside** the handler, before Kora's commit, so a successful retry commits normally
and a final failure falls through to the backoff path. Keep the total retry time well under
`max.poll.interval.ms` or the broker evicts the consumer. See
[kora-aop-resilient](../../kora-aop-resilient/SKILL.md); note that 2.0 takes a spec **class**, not a
config name string.

Do not write a `while` loop with `Thread.sleep` in the listener — it blocks the poll thread with no
visibility into `max.poll.interval.ms`.

---

## Backoff and restart

```hocon
kafka.consumer.orders {
  backoffTimeout = 15s      # first pause; doubles per consecutive failure up to 60s
  shutdownWait  = 30s
}
```

The backoff counter resets to `backoffTimeout` after any poll that completes without error. A
restarting consumer rejoins the group, which triggers a rebalance for the whole group — a listener
that fails constantly therefore destabilises its peers, which is another reason to skip or DLQ
poison records rather than let them throw.

Nothing is committed during shutdown. A handler interrupted at `shutdownWait` is redelivered.

---

## Pitfalls

| Symptom | Cause | Fix |
|---|---|---|
| Consumer restarts every `backoffTimeout` | a record throws on every attempt | skip it, DLQ it, or handle the exception |
| `KafkaSkipRecordException` does not skip | thrown from a **batch** listener | filter inside the loop; the batch handler has no skip branch |
| Deserialization error kills the listener | no exception parameter and no try/catch | add `@Nullable Exception`, or catch around `record.value()` |
| Exception parameter is always `null` | key failed but only a value parameter is declared | declare key + value, or use `RecordKeyDeserializationException` |
| `getRecord()` not found | called on the wrong exception | it exists on `RecordKeyDeserializationException` / `RecordValueDeserializationException` |
| Rebalance storm | a slow or retrying handler exceeds `max.poll.interval.ms` | shrink `max.poll.records`, cap retry time, raise the interval |
| Cannot see the error | `telemetry.logging.enabled` defaults to `false` | enable it on the listener |
| `@Retry("name")` does not compile | 1.x string form | `@Retryable(MySpec.class)` with `@RetrySpec("resilient.retry.<n>")` |

---

## Related references

- [Listener signatures](kafka-listener-reference.md)
- [Serialization](kafka-serialization-reference.md)
- [Offsets](kafka-offset-reference.md)
- [Telemetry](kafka-telemetry-reference.md)
- [Transactions](kafka-transactions-reference.md)

**Source:** framework tag `2.0.0.RC2` —
[exceptions](https://github.com/kora-projects/kora/tree/2.0.0.RC2/kafka/kafka/src/main/java/io/koraframework/kafka/common/exceptions) ·
[RecordHandler](https://github.com/kora-projects/kora/blob/2.0.0.RC2/kafka/kafka/src/main/java/io/koraframework/kafka/common/consumer/containers/handlers/impl/RecordHandler.java);
migrated examples on `migration/2.0` —
[kora-java-kafka](https://github.com/kora-projects/kora-examples/tree/migration/2.0/examples/java/kora-java-kafka)
