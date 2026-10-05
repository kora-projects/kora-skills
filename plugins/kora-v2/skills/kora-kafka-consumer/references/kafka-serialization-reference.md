# Kafka Deserialization Reference (Kora 2.0)

How a listener parameter type becomes a `org.apache.kafka.common.serialization.Deserializer`.

## Contents

- [How a deserializer is chosen](#how-a-deserializer-is-chosen)
- [Built-in deserializers](#built-in-deserializers)
- [@Json payloads](#json-payloads)
- [Custom deserializers with @Tag](#custom-deserializers-with-tag)
- [Keys](#keys)
- [Lazy deserialization](#lazy-deserialization)
- [Kotlin nullability](#kotlin-nullability)
- [Pitfalls](#pitfalls)

---

## How a deserializer is chosen

The generated container method takes two deserializers as graph dependencies:

```java
@Root
@Tag(OrderListenerModule.OrderListenerProcessTag.class)
default GeneratedListener orderListenerProcessContainer(
        @Tag(...) KafkaListenerConfig config,
        @Tag(...) ValueOf<KafkaRecordHandler<String, OrderEvent>> handler,
        Deserializer<String> keyDeserializer,
        @Json Deserializer<OrderEvent> valueDeserializer,   // annotations copied from your parameter
        KafkaConsumerTelemetryFactory telemetryFactory,
        @Tag(...) @Nullable ConsumerAwareRebalanceListener rebalanceListener) { ... }
```

The key and value **types** come from your method signature, and any `@Json` / `@Tag` annotation on
the payload type or parameter is copied onto the deserializer parameter. Resolution is then ordinary
Kora DI.

The Kafka client itself is always created with `ByteArrayDeserializer` for both key and value and
wrapped in a `ConsumerWrapper`. Setting `key.deserializer` / `value.deserializer` in
`driverProperties` therefore changes nothing about what your listener receives.

---

## Built-in deserializers

`KafkaDeserializersModule` (pulled in by `KafkaModule`) supplies a `@DefaultComponent` for:

`String`, `UUID`, `byte[]`, `org.apache.kafka.common.utils.Bytes`, `ByteBuffer`, `Double`, `Float`,
`Integer`, `Long`, `Short`, `Void`.

```java
@KafkaListener("kafka.consumer.events")
void process(String value) { }

@KafkaListener("kafka.consumer.events")
void process(byte[] value) { }
```

Because these are `@DefaultComponent`, declaring your own untagged `Deserializer<String>`
`@Component` replaces the built-in one for every listener using `String`. Prefer a `@Tag`.

---

## `@Json` payloads

`@Json` on the payload type selects `JsonKafkaDeserializer<T>`, which wraps the generated
`JsonReader<T>`:

```java
@Component
public final class OrderListener {

    @Json
    public record OrderEvent(String orderId, BigDecimal amount) {}

    @KafkaListener("kafka.consumer.orders")
    void process(@Json OrderEvent event) {
        orderService.handle(event);
    }
}
```

The annotation goes wherever the payload type appears:

```java
void process(String key, @Json OrderEvent value)                    // value parameter
void process(ConsumerRecord<String, @Json OrderEvent> record)       // type argument
void process(ConsumerRecords<String, @Json OrderEvent> records)     // batch
```

Requires `io.koraframework:json-common` on the classpath and `JsonModule` on the `@KoraApp`
interface. `JsonKafkaDeserializer` catches everything the reader throws and rethrows
`org.apache.kafka.common.errors.SerializationException`, which the record wrapper then turns into
`RecordValueDeserializationException`.

A `null` payload (a tombstone) deserializes to `null` without an error.

---

## Custom deserializers with `@Tag`

Implement `Deserializer<T>`, register it as a `@Component` with a `@Tag`, and put the same tag on the
payload:

```java
@Component
public final class OrderListener {

    @Json
    public record OrderEvent(String orderId, BigDecimal amount) {}

    @Tag(OrderEvent.class)
    @Component
    public static class OrderEventDeserializer implements Deserializer<OrderEvent> {

        private final JsonReader<OrderEvent> reader;

        public OrderEventDeserializer(JsonReader<OrderEvent> reader) {
            this.reader = reader;
        }

        @Override
        public OrderEvent deserialize(String topic, byte[] data) {
            return reader.read(data);
        }
    }

    @KafkaListener("kafka.consumer.orders")
    void process(@Tag(OrderEvent.class) OrderEvent value) { }
}
```

The tag class is arbitrary — using the payload type itself is the convention in the Kora examples.

On a `ConsumerRecord` the tag is a **type-use** annotation on the type argument:

```java
void process(ConsumerRecord<@Tag(KeyTag.class) String, @Tag(OrderEvent.class) OrderEvent> record)
```

Asserted by `KafkaListenerRecordTest#testProcessRecordWithTag` and
`KafkaListenerKeyAndValueTest#testProcessKeyAndValueWithTag`.

`JsonReader.read(byte[])` returns `@Nullable` and declares only the unchecked
`tools.jackson.core.JacksonException` — a `try { ... } catch (IOException e)` around it is a compile error
(`exception IOException is never thrown in body of corresponding try statement`).

---

## Keys

The key type is whatever the key position says:

| Signature | Key deserializer requested |
|---|---|
| `void process(String value)` | `Deserializer<byte[]>` — the key is never decoded |
| `void process(String key, String value)` | `Deserializer<String>` |
| `void process(Object key, String value)` | `Deserializer<byte[]>` |
| `void process(ConsumerRecord<String, V> r)` | `Deserializer<String>` |
| `void process(ConsumerRecord<?, V> r)` | `Deserializer<byte[]>` |

Use `ConsumerRecord<?, V>` (or omit the key parameter) when the key is opaque — it avoids demanding a
deserializer for a type you never read.

---

## Lazy deserialization

`ConsumerRecordWrapper.key()` / `.value()` decode on first call and cache the result. Consequences:

- A `ConsumerRecord` listener that never calls `value()` never deserializes — a corrupt payload
  passes through silently.
- `key()` and `value()` throw `RecordKeyDeserializationException` /
  `RecordValueDeserializationException`, both carrying `getRecord()` with the raw
  `ConsumerRecord<byte[], byte[]>`.
- In the key/value shape the processor performs the calls for you inside a `try`, which is why the
  exception parameter works there.

---

## Kotlin nullability

Kora contracts are `@NullMarked`, so a Kotlin override must match the contract exactly:

```kotlin
@Tag(OrderEvent::class)
@Component
class OrderEventDeserializer(private val reader: JsonReader<OrderEvent>) : Deserializer<OrderEvent> {
    override fun deserialize(topic: String, data: ByteArray): OrderEvent =
        requireNotNull(reader.read(data)) { "Empty payload in topic $topic" }
}
```

`reader.read(data)` is `@Nullable`, so assigning it to a non-null return type does not compile.
`requireNotNull` is what the migrated Kotlin examples use. A mismatched parameter nullability
produces `'deserialize' overrides nothing`, which never mentions nullability.

Do not carry JSpecify annotations into Kotlin; `@field:Nullable` is not a valid target under
Kotlin 2.4.

---

## Pitfalls

| Symptom | Cause | Fix |
|---|---|---|
| `No component found for dependency Deserializer<Foo>` | payload type has neither `@Json` nor a tagged `Deserializer` | add `@Json`, or register a tagged `Deserializer<Foo>` `@Component` |
| `Multiple components match Deserializer<String>` | an untagged custom `Deserializer<String>` competes with the built-in | add a `@Tag` and reference it on the parameter |
| Custom deserializer ignored | tag on the parameter differs from the tag on the `@Component` | use the same class in both `@Tag`s |
| `value.deserializer` in `driverProperties` has no effect | the client always uses `ByteArrayDeserializer` | choose via the method signature |
| Corrupt payload never reported | `ConsumerRecord` listener that never calls `value()` | call `value()`, or use the key/value shape with an exception parameter |
| Java: `exception IOException is never thrown` | 1.x `try/catch` around `read` | remove the catch |
| Kotlin: `'deserialize' overrides nothing` | signature does not match the `@NullMarked` contract | `deserialize(topic: String, data: ByteArray)` |
| `JsonReader<Foo> not found` | `Foo` is not annotated `@Json`, or `json-common` / `JsonModule` missing | annotate it and wire the module |

---

## Related references

- [Listener signatures](kafka-listener-reference.md)
- [Error handling](kafka-error-handling-reference.md)
- [kora-json skill](../../kora-json/SKILL.md)
- [Producer serialization](../../kora-kafka-producer/references/kafka-serialization-reference.md)

**Source:** framework tag `2.0.0.RC2` —
[KafkaDeserializersModule](https://github.com/kora-projects/kora/blob/2.0.0.RC2/kafka/kafka/src/main/java/io/koraframework/kafka/common/consumer/deserializer/KafkaDeserializersModule.java) ·
[JsonKafkaDeserializer](https://github.com/kora-projects/kora/blob/2.0.0.RC2/kafka/kafka/src/main/java/io/koraframework/kafka/common/consumer/deserializer/JsonKafkaDeserializer.java) ·
[ConsumerRecordWrapper](https://github.com/kora-projects/kora/blob/2.0.0.RC2/kafka/kafka/src/main/java/io/koraframework/kafka/common/consumer/containers/ConsumerRecordWrapper.java)
