# Kafka Transactions Reference

**Source:** [.kora-agent/kora-docs/mkdocs/docs/en/documentation/kafka.md](.kora-agent/kora-docs/mkdocs/docs/en/documentation/kafka.md)  
**Examples:** `.kora-agent/kora-examples/kora-java-kafka/`

Transactional message sending in Kora Kafka.

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

```java
@Component
public final class MyService {
    private final MyTransactionalPublisher transactionalPublisher;
    
    public void sendManual() {
        try (var transaction = transactionalPublisher.begin()) {
            transaction.producer().send("key", "value");
            
            if (somethingBad) {
                transaction.abort();  // Explicit rollback
            }
            // commit on try-with-resources close
        }
    }
}
```

### With result return

```java
public RecordMetadata sendInTransactionWithResult() {
    return transactionalPublisher.inTx(producer -> {
        producer.send("key1", "value1");
        return producer.sendWithMeta("key2", "value2");
    });
}
```

## Atomicity with DB

For atomic sending to Kafka and the database, use `@Transactional`:

```java
@Component
public final class OrderService {
    private final MyTransactionalPublisher kafkaPublisher;
    private final JdbcDatabase database;
    
    @Transactional
    public void createOrder(Order order) {
        // 1. Save to DB
        database.execute(conn -> {
            // INSERT INTO orders ...
        });
        
        // 2. Send event to Kafka
        kafkaPublisher.inTx(producer -> {
            producer.send(order.id().toString(), order.toJson());
        });
        
        // Both actions commit atomically or both roll back
    }
}
```

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
