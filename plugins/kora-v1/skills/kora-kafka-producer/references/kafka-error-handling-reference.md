# Kafka Producer Error Handling Reference

**Source:** [../../../.kora-agent/kora-docs/mkdocs/docs/en/documentation/kafka.md](../../../.kora-agent/kora-docs/mkdocs/docs/en/documentation/kafka.md)

Error handling for `@KafkaPublisher` send methods. For consumer-side error
handling (`KafkaSkipRecordException`, deserialization errors, the `Exception`
parameter pattern), use the `kora-kafka-consumer` skill.

## Contents

- [KafkaPublishException](#kafkapublishexception)
- [Serialization errors](#serialization-errors)
- [Handling synchronous send errors](#handling-synchronous-send-errors)
- [Handling async send errors](#handling-async-send-errors)
- [Dead-letter pattern](#dead-letter-pattern)
- [Transaction rollback](#transaction-rollback)
- [Reliability configuration](#reliability-configuration)
- [Best practices](#best-practices)

## Quick Navigation

- [Producer Reference](kafka-producer-reference.md) — `@KafkaPublisher` API
- [Serialization Reference](kafka-serialization-reference.md) — `@Json`, `@Tag`
- [Transactions Reference](kafka-transactions-reference.md) — transaction rollback

## KafkaPublishException

For a `@Topic` method that does NOT return `Future<RecordMetadata>` /
`CompletionStage<RecordMetadata>`, a send failure throws
`ru.tinkoff.kora.kafka.common.exceptions.KafkaPublishException`. The real
`KafkaProducer` error is in `getCause()`.

```java
@KafkaPublisher("kafka.producer.myPublisher")
public interface MyPublisher {

    @Topic("kafka.producer.myTopic")
    void send(String value);  // throws KafkaPublishException on failure
}
```

## Serialization errors

A key/value serialization failure throws
`org.apache.kafka.common.errors.SerializationException`, the same as a direct
`Producer#send`.

```java
@Topic("kafka.producer.myTopic")
void send(@Json MyEvent event);  // throws SerializationException on JSON error
```

## Handling synchronous send errors

```java
import org.apache.kafka.common.errors.SerializationException;
import ru.tinkoff.kora.kafka.common.exceptions.KafkaPublishException;

@Component
public final class MessageSender {

    private static final Logger log = LoggerFactory.getLogger(MessageSender.class);
    private final MyPublisher publisher;

    public MessageSender(MyPublisher publisher) {
        this.publisher = publisher;
    }

    public void sendMessage(String event) {
        try {
            publisher.send(event);
        } catch (SerializationException e) {
            log.error("Failed to serialize message", e);
            throw e;
        } catch (KafkaPublishException e) {
            log.error("Failed to publish message", e.getCause());
            throw e;
        }
    }
}
```

## Handling async send errors

`Future<RecordMetadata>` and `CompletionStage<RecordMetadata>` methods report
the failure through the returned handle instead of throwing
`KafkaPublishException` directly:

```java
@KafkaPublisher("kafka.producer.myPublisher")
public interface MyPublisher {

    @Topic("kafka.producer.myTopic")
    CompletionStage<RecordMetadata> sendStage(String value);
}

@Component
public final class AsyncSender {

    private static final Logger log = LoggerFactory.getLogger(AsyncSender.class);
    private final MyPublisher publisher;

    public AsyncSender(MyPublisher publisher) {
        this.publisher = publisher;
    }

    public void sendMessage(String event) {
        publisher.sendStage(event)
            .thenAccept(metadata -> log.info("Sent to {}@{}", metadata.topic(), metadata.offset()))
            .exceptionally(ex -> {
                log.error("Failed to send", ex);
                return null;
            });
    }
}
```

## Dead-letter pattern

Application code can route failed payloads to a separate topic with another
publisher:

```java
@KafkaPublisher("kafka.producer.dlPublisher")
public interface DeadLetterPublisher {

    @Topic("kafka.producer.dlTopic")
    void send(String originalMessage, String errorMessage);
}
```

## Transaction rollback

With a `TransactionalPublisher`, any exception thrown inside `inTx` aborts the
transaction so none of the records are committed:

```java
transactionalPublisher.inTx(producer -> {
    producer.send("k1", "v1");
    producer.send("k2", "v2");
    // throwing here aborts the whole transaction
});
```

Note: this atomicity covers the Kafka sends only, not a separate database write.
See [Transactions Reference](kafka-transactions-reference.md).

## Reliability configuration

Tune delivery guarantees through `driverProperties`:

```hocon
kafka {
  producer {
    myPublisher {
      driverProperties {
        "bootstrap.servers": ${KAFKA_BOOTSTRAP}
        "acks": "all"                 # wait for in-sync replicas
        "retries": 2147483647         # retry transient failures
        "enable.idempotence": true    # no duplicate appends on retry
        "delivery.timeout.ms": 120000
      }
    }
  }
}
```

## Best practices

1. Catch `SerializationException` and `KafkaPublishException` separately for
   sync sends; inspect `KafkaPublishException.getCause()`.
2. Use async signatures with `.exceptionally(...)` when you must not block.
3. Set `acks=all` and `enable.idempotence=true` for reliable delivery.
4. Use a `TransactionalPublisher` when several records must commit together.
5. Route poison payloads to a dead-letter topic instead of losing them.
