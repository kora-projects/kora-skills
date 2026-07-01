# Kafka Serialization Reference

**Source:** [../../../.kora-agent/kora-docs/mkdocs/docs/en/documentation/kafka.md](../../../.kora-agent/kora-docs/mkdocs/docs/en/documentation/kafka.md)

How Kora selects a `Serializer<T>` for each key and value of a `@KafkaPublisher`
method. (Consumer-side deserialization uses the mirror-image `@Json`/`@Tag`
rules — see the `kora-kafka-consumer` skill.)

## Contents

- [How serializer selection works](#how-serializer-selection-works)
- [JSON serialization with @Json](#json-serialization-with-json)
- [Custom serializers with @Tag](#custom-serializers-with-tag)
- [Standard Kafka serializers](#standard-kafka-serializers)
- [Best practices](#best-practices)
- [Common issues](#common-issues)

## How serializer selection works

For every key and value parameter, the annotation processor resolves a
`Serializer<T>` component from the application graph:

1. `@Json` on the parameter → Kora's JSON serializer for that type (requires
   `json-module` and `@Json` on the DTO).
2. `@Tag(SomeTag.class)` on the parameter → the `Serializer<T>` component bound
   under that tag.
3. Neither → the untagged `Serializer<T>` component for that type. Kora supplies
   the standard String / byte[] / numeric serializers via `KafkaModule`.

You normally do **not** set `key.serializer` / `value.serializer` in
`driverProperties`; Kora injects the resolved serializers into the generated
producer.

## JSON serialization with @Json

Annotate the DTO with `@Json` and the value parameter with `@Json`:

```java
import ru.tinkoff.kora.json.common.annotation.Json;
import ru.tinkoff.kora.kafka.common.annotation.KafkaPublisher;
import ru.tinkoff.kora.kafka.common.annotation.KafkaPublisher.Topic;

@KafkaPublisher("kafka.producer.myPublisher")
public interface MyKafkaProducer {

    @Json
    record JsonEvent(String name, Integer code) {}

    @Topic("kafka.producer.myTopic")
    void send(String key, @Json JsonEvent value);
}
```

`@Json` also works inside a `ProducerRecord` type parameter:

```java
void send(ProducerRecord<String, @Json JsonEvent> record);
```

## Custom serializers with @Tag

Bind a custom `Serializer<T>` as a `@Component` under a tag, then reference that
tag on the parameter. This example reuses Kora's generated `JsonWriter<T>` to
build a byte payload (adapted from `kora-java-kafka`):

```java
import java.io.IOException;
import org.apache.kafka.common.serialization.Serializer;
import ru.tinkoff.kora.common.Component;
import ru.tinkoff.kora.common.Tag;
import ru.tinkoff.kora.json.common.JsonWriter;
import ru.tinkoff.kora.json.common.annotation.Json;
import ru.tinkoff.kora.kafka.common.annotation.KafkaPublisher;
import ru.tinkoff.kora.kafka.common.annotation.KafkaPublisher.Topic;

@KafkaPublisher("kafka.producer.myPublisher")
public interface MyKafkaProducer {

    @Json
    record MyEvent(String username, int code) {}

    @Tag(MyEvent.class)
    @Component
    class MySerializer implements Serializer<MyEvent> {

        private final JsonWriter<MyEvent> writer;

        public MySerializer(JsonWriter<MyEvent> writer) {
            this.writer = writer;
        }

        @Override
        public byte[] serialize(String topic, MyEvent data) {
            try {
                return writer.toByteArray(data);
            } catch (IOException e) {
                throw new IllegalArgumentException(e);
            }
        }
    }

    @Topic("kafka.producer.myTopic")
    void send(@Tag(MyEvent.class) MyEvent value);
}
```

The `@Tag` on the parameter must match the tag on the `Serializer<T>` component.

## Standard Kafka serializers

Kora binds the common Apache Kafka serializers, so plain types work without any
annotation:

| Type | Serializer |
|------|------------|
| `String` | `StringSerializer` (UTF-8) |
| `Integer` | `IntegerSerializer` |
| `Long` | `LongSerializer` |
| `Double` | `DoubleSerializer` |
| `Float` | `FloatSerializer` |
| `byte[]` | `ByteArraySerializer` |

## Best practices

1. **Use `@Json` for DTOs** — the simplest path for structured payloads.
2. **Use `@Tag` for custom logic** — schema-registry clients, compression,
   protobuf, etc.
3. **Keep DTOs immutable** — `record` types are the natural fit.
4. **Version your events** — add a `version` field for schema evolution.

## Common issues

| Problem | Fix |
|---------|-----|
| No `Serializer<T>` found at compile time | Add `@Json` (with `json-module`) or bind a `@Tag` `Serializer<T>` component |
| `SerializationException` at send time | Check the `@Json` DTO / custom serializer logic |
| Wrong bytes on the consumer | Ensure the consumer uses a matching deserializer (`@Json` or matching `@Tag`) |
