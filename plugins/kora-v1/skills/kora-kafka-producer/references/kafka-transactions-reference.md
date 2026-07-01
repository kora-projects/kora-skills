# Kafka Transactions Reference

**Source:** [../../../.kora-agent/kora-docs/mkdocs/docs/en/documentation/kafka.md](../../../.kora-agent/kora-docs/mkdocs/docs/en/documentation/kafka.md)

Transactional message sending in Kora Kafka.

## Contents

- [TransactionalPublisher](#transactionalpublisher)
- [Usage](#usage)
- [Atomicity with a database](#atomicity-with-a-database)
- [Kafka requirements](#kafka-requirements)
- [Limitations](#limitations)
- [Best Practices](#best-practices)

## See Also

- [Producer Reference](kafka-producer-reference.md) — Basic producer patterns
- [Error Handling](kafka-error-handling-reference.md) — Transaction rollback patterns

## TransactionalPublisher

To send messages within a transaction, use `TransactionalPublisher<T>`.

### Definition

```java
// Base publisher
@KafkaPublisher("kafka.producer.myPublisher")
public interface MyPublisher {
    @Topic("kafka.producer.myTopic")
    void send(String key, String value);
}

// Transactional publisher
@KafkaPublisher("kafka.producer.myTransactionalPublisher")
public interface MyTransactionalPublisher extends TransactionalPublisher<MyPublisher> {
}
```

### Configuration

```hocon
kafka {
  producer {
    myTransactionalPublisher {
      idPrefix = "my-app-"       # Prefix for transactional.id
      maxPoolSize = 10           # Transaction pool size
      maxWaitTime = "10s"        # Maximum transaction wait time
      driverProperties {
        "bootstrap.servers" = "localhost:9093"
        # transactional.id will be generated as {idPrefix}{uuid}
      }
    }
  }
}
```

## Usage

### Lambda style (recommended)

```java
@Component
public final class MyService {
    private final MyTransactionalPublisher transactionalPublisher;
    
    public MyService(MyTransactionalPublisher transactionalPublisher) {
        this.transactionalPublisher = transactionalPublisher;
    }
    
    public void sendInTransaction() {
        transactionalPublisher.inTx(producer -> {
            producer.send("key1", "value1");
            producer.send("key2", "value2");
            // All messages will be committed atomically
            // On error - rollback
        });
    }
}
```

### Manual management

`begin()` returns a `Transaction<P>` (an `AutoCloseable`). It exposes
`publisher()` (your typed publisher, already in transaction mode) and the raw
`producer()` (`Producer<byte[], byte[]>`). On `close()` the transaction commits;
call `abort()` to roll back instead.

```java
@Component
public final class MyService {
    private final MyTransactionalPublisher transactionalPublisher;

    public MyService(MyTransactionalPublisher transactionalPublisher) {
        this.transactionalPublisher = transactionalPublisher;
    }

    public void sendManual(boolean somethingBad) {
        try (var transaction = transactionalPublisher.begin()) {
            // use the typed publisher API
            transaction.publisher().send("key", "value");

            if (somethingBad) {
                transaction.abort();  // explicit rollback; close() will not commit
            }
            // otherwise: commit on try-with-resources close
        }
    }
}
```

### Returning a result

`inTx` is overloaded with a function variant that returns a value:

```java
public RecordMetadata sendInTransactionWithResult() {
    return transactionalPublisher.inTx(producer -> {
        producer.send("key1", "value1");
        return producer.sendWithMeta("key2", "value2");
    });
}
```

(Here `sendWithMeta` is a method on the base publisher that returns
`RecordMetadata`.)

## Atomicity with a database

A Kafka transaction is atomic only across the Kafka sends inside it. It does
**not** make a database write and a Kafka send atomic together — they are two
independent systems with separate transaction managers.

To keep a DB change and an event consistent, use the **transactional outbox**
pattern: write the event into an outbox table in the same DB transaction, then a
separate relay reads the outbox and publishes to Kafka (the relay may use a
`TransactionalPublisher` for atomic batch sends). Do not nest a Kafka
transaction inside a DB transaction expecting two-phase commit.

## Kafka requirements

Transactions require:
- Kafka brokers with transaction support (0.11+)
- `transactional.id` must be unique for each producer instance
- `acks=all` for reliable delivery

## Limitations

- Transactions work only within a single producer instance
- Transaction duration is limited by `transaction.timeout.ms`
- Maximum number of active transactions is limited by `maxPoolSize`

## Best Practices

1. **Short transactions** — minimize time spent inside `inTx()`
2. **Avoid external calls** — do not make HTTP requests inside a transaction
3. **Proper idPrefix** — use unique prefixes for each service
4. **Monitoring** — watch the number of active transactions
