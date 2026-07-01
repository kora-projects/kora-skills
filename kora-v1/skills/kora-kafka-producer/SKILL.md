---
name: kora-kafka-producer
description: "Kafka message production in Kora via the @KafkaPublisher annotation on an interface. Covers @KafkaPublisher.Topic typed contracts, send signatures (void, RecordMetadata, Future/CompletionStage, ProducerRecord, Callback), @Json and @Tag serializer selection, KafkaPublishException handling, and transactional sends with TransactionalPublisher. Use when declaring a Kafka producer, publishing domain events, configuring kafka.producer.* driverProperties, or wiring a transactional Kafka publisher. Requires the ru.tinkoff.kora:kafka module, KafkaModule on @KoraApp, and the annotation-processors (Java) or symbol-processors (Kotlin)."
---

# Kora Kafka Producer

Kora generates a Kafka `Producer` implementation at compile time from an
interface annotated with `@KafkaPublisher`. You declare the contract; the
annotation processor wires the `KafkaProducer`, serializers, and telemetry.

Read this first when:
- declaring a typed publisher with `@KafkaPublisher`,
- choosing a send signature (sync, `RecordMetadata`, async, `ProducerRecord`),
- selecting serializers with `@Json` or `@Tag`,
- sending atomically with `TransactionalPublisher`.

For Kafka consumers (`@KafkaListener`), use the `kora-kafka-consumer` skill.

---

## Quick Start

### 1. Dependencies

```groovy
dependencies {
    koraBom platform("ru.tinkoff.kora:kora-parent:1.2.17")
    annotationProcessor "ru.tinkoff.kora:annotation-processors" // KSP for Kotlin: ksp "ru.tinkoff.kora:symbol-processors"

    implementation "ru.tinkoff.kora:kafka"
    implementation "ru.tinkoff.kora:json-module" // only if you publish @Json payloads
}
```

All `ru.tinkoff.kora:*` artifacts inherit their version from the `kora-parent`
BOM — never pin them individually.

### 2. Enable the module

```java
@KoraApp
public interface Application extends
        HoconConfigModule,
        LogbackModule,
        JsonModule,
        KafkaModule {

    static void main(String[] args) {
        KoraApplication.run(ApplicationGraph::graph);
    }
}
```

### 3. Declare a publisher

```java
import ru.tinkoff.kora.kafka.common.annotation.KafkaPublisher;
import ru.tinkoff.kora.kafka.common.annotation.KafkaPublisher.Topic;

@KafkaPublisher("kafka.producer.userEvents")
public interface UserEventPublisher {

    @Topic("kafka.producer.userEventsTopic")
    void send(@Json UserEvent event);
}
```

`@KafkaPublisher` points to the producer config section; `@Topic` (the nested
`@KafkaPublisher.Topic`) points to a topic config section.

### 4. Define the event

```java
@Json
public record UserEvent(String userId, String eventType, LocalDateTime timestamp) {}
```

### 5. Inject and publish

```java
@Component
public final class UserService {

    private final UserEventPublisher publisher;

    public UserService(UserEventPublisher publisher) {
        this.publisher = publisher;
    }

    public void createUser(String userId) {
        publisher.send(new UserEvent(userId, "CREATED", LocalDateTime.now()));
    }
}
```

Use constructor injection — Kora has no field injection.

### 6. Configure

```hocon
kafka {
  producer {
    userEvents {
      driverProperties {
        "bootstrap.servers": ${KAFKA_BOOTSTRAP}  # required
        "acks": "all"
      }
      telemetry.logging.enabled = true
    }
    userEventsTopic {
      topic = "user-events"  # required
      # partition = 0        # optional
    }
  }
}
```

The topic config section is a sibling of the producer section under
`kafka.producer`, named to match the `@Topic` path. Serializers for `@Json`
parameters are injected by Kora — do **not** set `key.serializer` /
`value.serializer` in `driverProperties` for those parameters.

---

## Send signatures

`K` is the key type, `V` the value type. With `@Topic`, value is required; key
and `Headers` are optional. Available return types:

| Signature | Behavior |
|-----------|----------|
| `void send(V value)` | Fire-and-forget; throws `KafkaPublishException` on failure |
| `void send(K key, V value)` | With key |
| `void send(K key, V value, Headers headers)` | With headers |
| `RecordMetadata send(V value)` | Blocking; returns broker metadata |
| `Future<RecordMetadata> send(V value)` | Async via `Future` |
| `CompletionStage<RecordMetadata> send(V value)` | Async via `CompletionStage` |
| `void send(ProducerRecord<K, V> record)` | Full control over the record |
| `void send(ProducerRecord<K, V> record, Callback callback)` | Record + Kafka `Callback` |

In Kotlin a `suspend fun send(value: V): RecordMetadata` and
`Deferred<RecordMetadata>` are also supported.

A method WITHOUT `@Topic` must take a `ProducerRecord` (the topic comes from the
record). A method WITH `@Topic` takes unpacked `value`/`key`/`headers`.

See [Producer Reference](references/kafka-producer-reference.md) for full detail.

---

## Serialization

Kora chooses a `Serializer<T>` for each key/value from the application graph:

- `@Json` on a parameter (and on its DTO) serializes that value as JSON via the
  `json-module`.
- `@Tag(SomeTag.class)` on a parameter selects a custom `Serializer<T>`
  component bound under that tag.
- Otherwise the matching `Serializer<T>` component is used (Kora provides the
  standard String/byte/numeric serializers).

```java
@KafkaPublisher("kafka.producer.myPublisher")
public interface MyPublisher {

    @Topic("kafka.producer.myTopic")
    void send(String key, @Json MyEvent value);

    // custom serializer selected by tag
    void send(ProducerRecord<String, @Tag(MyEvent.class) MyEvent> record);
}
```

See [Serialization Reference](references/kafka-serialization-reference.md).

---

## Transactional publishing

To send several records atomically (all or nothing), declare a regular
publisher, then a second `@KafkaPublisher` interface that extends
`TransactionalPublisher<P>`:

```java
import ru.tinkoff.kora.kafka.common.producer.TransactionalPublisher;

@KafkaPublisher("kafka.producer.myPublisher")
public interface MyPublisher {
    @Topic("kafka.producer.myTopic")
    void send(String key, String value);
}

@KafkaPublisher("kafka.producer.myTransactional")
public interface MyTransactionalPublisher extends TransactionalPublisher<MyPublisher> {
}
```

Send inside `inTx` — on success the transaction commits, on any thrown
exception it aborts:

```java
transactionalPublisher.inTx(producer -> {
    producer.send("key1", "value1");
    producer.send("key2", "value2");
});
```

Transaction config lives under the transactional publisher section:

```hocon
kafka {
  producer {
    myTransactional {
      idPrefix = "order-service-"  # transactional.id prefix
      maxPoolSize = 10             # transaction connection pool size
      maxWaitTime = "10s"          # max transaction wait time
    }
  }
}
```

Kafka transactions cover Kafka only. They do NOT make a database write and a
Kafka send atomic together — for that use the transactional outbox pattern.
See [Transactions Reference](references/kafka-transactions-reference.md).

---

## References

| Document | Description |
|----------|-------------|
| [Producer Reference](references/kafka-producer-reference.md) | Full `@KafkaPublisher` API, signatures, config keys |
| [Serialization Reference](references/kafka-serialization-reference.md) | `@Json`, `@Tag`, custom `Serializer<T>` components |
| [Transactions Reference](references/kafka-transactions-reference.md) | `TransactionalPublisher`, `inTx`, manual `begin()` |
| [Error Handling Reference](references/kafka-error-handling-reference.md) | `KafkaPublishException`, `SerializationException`, async errors |

---

## Common pitfalls

| Symptom | Fix |
|---------|-----|
| `Required dependency not found` for the publisher | Add `KafkaModule` to `@KoraApp`, and `annotation-processors` (KSP for Kotlin) |
| No `Serializer` found for a parameter | Add `@Json` (and `json-module`) or bind a `@Tag` `Serializer<T>` component |
| Method without `@Topic` fails to generate | A non-`@Topic` method must take a `ProducerRecord` |
| `KafkaPublishException` on every send | Check `bootstrap.servers` and broker reachability; inspect `getCause()` |
| Topic config not picked up | The `@Topic` path must match a config section under `kafka.producer` |
| Transaction never aborts | Let the exception propagate out of the `inTx` lambda; do not swallow it |

---

## Assets

Templates and config live in `assets/`. See
[assets/README.md](assets/README.md) for the full list and usage.

| Template | Description |
|----------|-------------|
| `MessagePublisher.java.template` | Publisher with every send signature |
| `JsonMessagePublisher.java.template` | `@Json` publisher with DTO |
| `TransactionalPublisher.java.template` | Base + transactional publisher |
| `application.conf.template` | HOCON producer config |
| `build.gradle.template` / `build.gradle.kts.template` | Gradle dependencies |
