# Kafka Listener Reference (Kora 2.0)

Every accepted `@KafkaListener` method signature, derived from the annotation processor and KSP
sources at tag `2.0.0.RC2` and from the processor tests that assert each shape.

## Contents

- [The annotation](#the-annotation)
- [How parameters are classified](#how-parameters-are-classified)
- [Accepted signatures](#accepted-signatures)
- [Rejected signatures and their errors](#rejected-signatures-and-their-errors)
- [Kotlin differences](#kotlin-differences)
- [What the processor generates](#what-the-processor-generates)
- [Custom tag on a listener](#custom-tag-on-a-listener)

---

## The annotation

```java
package io.koraframework.kafka.common.annotation;

@Target(ElementType.METHOD)
@Retention(RetentionPolicy.RUNTIME)
public @interface KafkaListener {
    String value();                          // config path — required, no default
    Class<?> tag() default Tag.class;        // override the generated tag
}
```

`value()` is the **full** config path. Kora prefixes nothing: `@KafkaListener("kafka.consumer.orders")`
reads `kafka.consumer.orders`, `@KafkaListener("orders")` reads a top-level `orders` section.

The enclosing class must be resolvable from the graph — mark it `@Component` (or supply it from a
`@Module` factory). Listener methods return `void` / `Unit`.

**A non-`void` return type is silently ignored, not rejected.** Neither generator inspects it:
`getReturnType`, `isFuture` and `isCompletionStage` appear nowhere in
`KafkaConsumerHandlerGenerator.java` or `KafkaHandlerGenerator.kt`, and the invocation is emitted as
the bare statement `controller.<method>(…)` in all three shapes. A listener returning
`CompletionStage`, `Mono` or `Future` therefore compiles and runs, but the container never awaits
it — `RecordHandler` commits `offset + 1` the moment the method returns, so the offset advances past
a record whose work is still in flight, and an exception inside the future reaches neither
`observeError` nor the backoff/redelivery path. There is no error message for this; it is only
visible as lost records after a crash.

Do not generalise this to publishers: on a `@KafkaPublisher` an async return type **is** a
generated contract (`Future`/`CompletionStage`, plus `suspend`/`Deferred` in Kotlin), because there
it means the delivery acknowledgement of a send.

---

## How parameters are classified

`ConsumerParameter.parseParameters` walks the parameter list and tags each one **by its type**:

| Type | Classified as |
|---|---|
| `org.apache.kafka.clients.consumer.ConsumerRecord<K, V>` | `Record` |
| `org.apache.kafka.clients.consumer.ConsumerRecords<K, V>` | `Records` |
| `org.apache.kafka.clients.consumer.Consumer<K, V>` | `Consumer` |
| `org.apache.kafka.common.header.Headers` | `Headers` (Java: a dedicated branch; Kotlin: detected inside the key/value generator) |
| `io.koraframework.kafka.common.exceptions.RecordKeyDeserializationException` | `KeyDeserializationException` |
| `io.koraframework.kafka.common.exceptions.RecordValueDeserializationException` | `ValueDeserializationException` |
| `java.lang.Exception` or `java.lang.Throwable` **exactly** | `Exception` |
| anything else | `Unknown` — a payload parameter |

Then one of three handler shapes is generated:

1. any `ConsumerRecords` parameter → **batch handler** (`KafkaRecordsHandler<K, V>`)
2. else any `ConsumerRecord` parameter → **record handler** (`KafkaRecordHandler<K, V>`)
3. else → **key/value handler** (also `KafkaRecordHandler<K, V>`)

In shape 3 the *first* unclassified parameter is the **value**; if a *second* appears, the first
becomes the **key** and the second the value. Order matters, names do not.

Type-use annotations do not confuse the check — the processor compares the type element, not the
printed type, so `@Nullable Exception` (which renders as `java.lang.@Nullable Exception`) is still
recognised as the exception parameter. Asserted by
`KafkaListenerRecordTest#testProcessRecordAndParseExceptionWithTypeUseAnnotation`.

---

## Accepted signatures

Each row names the processor test that compiles and exercises it.

### Key/value shape

| Signature | Key type seen by Kora | Proving test |
|---|---|---|
| `void process(String value)` | `byte[]` | `KafkaListenerKeyAndValueTest#testProcessValue` |
| `void process(String key, String value)` | `String` | `#testProcessKeyAndValue` |
| `void process(String value, Headers headers)` | `byte[]` | `#testProcessValueAndHeaders` |
| `void process(String key, String value, Headers headers)` | `String` | `#testProcessKeyAndValueAndHeaders` |
| `void process(String value, RecordValueDeserializationException e)` | `byte[]` | `#testProcessValueAndValueException` |
| `void process(String value, Exception e)` | `byte[]` | `#testProcessValueAndException` |
| `void process(String key, String value, Exception e)` | `String` | `#testProcessKeyValueAndException` |
| `void process(String key, String value, Headers h, Exception e)` | `String` | `#testProcessKeyValueHeaderAndException` |
| `void process(Consumer<?, ?> c, String value, Exception e)` | `byte[]` | `#testProcessValueAndConsumer` |
| `void process(Consumer<?, ?> c, String key, String value, Headers h, Exception e)` | `String` | `#testProcessKeyValueHeadersAndConsumer` |

When no key parameter is declared (or the key parameter is `Object`), the key deserializer is
requested as `Deserializer<byte[]>` — the key bytes are never decoded.

**Failure semantics of the exception parameter.** Values are resolved inside a `try`; on failure
the corresponding payload parameter is `null` and the exception parameter is non-null:

- with only a value parameter, a **key** deserialization failure is not caught — the value is still
  delivered and the exception parameter stays `null` (`#testProcessValueAndException`);
- with a key **and** a value parameter, either failure nulls **both** payload parameters
  (`#testProcessKeyValueAndException`);
- `Exception`/`Throwable` receives the key failure in preference to the value failure;
- **without** an exception parameter a deserialization failure propagates out of the handler —
  `handler.handle(errorValue(), RecordValueDeserializationException.class)` in
  `#testProcessValue`.

`Headers` is read from the raw record and is always present, even when deserialization failed
(`assertHeadersIsEmpty` still passes on the error paths).

### Record shape

| Signature | Proving test |
|---|---|
| `void process(ConsumerRecord<String, String> record)` | `KafkaListenerRecordTest#testProcessRecord` |
| `void process(ConsumerRecord<?, String> record)` — key delivered as `byte[]` | `#testProcessRecordAnyKeyType` |
| `void process(Consumer<String, String> c, ConsumerRecord<String, String> r)` | `#testProcessRecordAndConsumer` |
| `void process(ConsumerRecord<String, String> r, RecordKeyDeserializationException e)` | `#testProcessRecordAndKeyParseException` |
| `void process(ConsumerRecord<String, String> r, RecordValueDeserializationException e)` | `#testProcessRecordAndValueParseException` |
| `void process(ConsumerRecord<String, String> r, Exception e)` | `#testProcessRecordAndParseException` |
| `void process(ConsumerRecord<String, String> r, Throwable e)` | `#testProcessRecordAndParseThrowable` |
| `void process(ConsumerRecord<@Tag(A.class) String, @Tag(B.class) String> r)` | `#testProcessRecordWithTag` |

The record is a `ConsumerRecordWrapper` that deserializes **lazily**: `key()` and `value()` decode on
first call and throw `RecordKeyDeserializationException` / `RecordValueDeserializationException`.
A `Headers` parameter is **not** accepted here — use `record.headers()`.

### Batch shape

| Signature | Proving test |
|---|---|
| `void process(ConsumerRecords<byte[], String> records)` | `KafkaListenerRecordsTest#testProcessRecords` |
| `void process(ConsumerRecords<?, String> records)` — key delivered as `byte[]` | `#testProcessRecordsAnyKeyType` |
| `void process(Consumer<?, ?> c, ConsumerRecords<String, String> records)` | `#testProcessRecordsAndConsumer` |

Batch listeners accept **only** `ConsumerRecords` and `Consumer`. Records inside the batch are still
lazily deserialized, so `record.value()` inside the loop can throw.

---

## Rejected signatures and their errors

| What you wrote | Error |
|---|---|
| a service/repository as a parameter | `Kafka record listener method has unsupported parameter` — inject it through the constructor |
| a telemetry context parameter, in a `ConsumerRecord`/`ConsumerRecords` listener | same error. 2.0's `KafkaUtils` has no telemetry check, so `ConsumerParameter.RecordsTelemetry` is declared but never produced; the 1.x `KafkaConsumerTelemetry.KafkaConsumerRecordsTelemetryContext<K, V>` type is gone. In a bare **key/value** listener there is no processor error — the parameter is taken as a payload and fails later as a missing `Deserializer` |
| `Headers` on a batch listener | `Kafka records listener method has unsupported parameter` |
| an exception parameter on a batch listener | same |
| three unclassified parameters | `Kafka listener method has too many payload parameters` |
| only `Consumer` / `Headers` / exception parameters | `Kafka listener method has no payload parameter` |
| `ConsumerRecord<String, ? extends Foo>` | `Kafka listener method has invalid value type` — a wildcard value has no deserializer |
| a payload type that is not a class, array or primitive | `Kafka listener method has invalid key/value type` |

`ConsumerRecord<?, V>` and `ConsumerRecords<?, V>` are the one wildcard that *is* accepted: an
unbounded key wildcard means "give me the raw key bytes".

---

## Kotlin differences

- Nullability lives in the type. Write `exception: Exception?`, not `@Nullable exception: Exception`.
- The exception parameter must be nullable, and any payload parameter that shares a `try` with it
  must be nullable too, because the generated code assigns `null` on failure:
  ```kotlin
  @KafkaListener("kafka.consumer.orders")
  fun process(@Json value: OrderEvent?, exception: Exception?) { ... }
  ```
- `ConsumerRecords<*, String>` / `ConsumerRecord<*, String>` map the star projection to `ByteArray`.
- **`suspend` is accepted but useless — and broken in one shape.** Unlike the HTTP-server and
  repository processors, KSP does **not** reject a `suspend` listener: `KafkaHandlerGenerator.kt`
  checks `Modifier.SUSPEND` at lines 133 (batch) and 236 (key/value) and wraps the call in
  `kotlinx.coroutines.runBlocking(Dispatchers.Unconfined)`. The framework has tests that compile it and assert success —
  `KafkaListenerKeyAndValueTest#testProcessValueSuspend` and
  `KafkaListenerRecordsTest#testProcessRecordsSuspend`. Three reasons to write a plain `fun` anyway:
  1. `kotlinx-coroutines` appears in **no** `.gradle` or `.toml` file in the Kora 2.0 repository, so
     the generated `runBlocking` compiles only if your own project puts `kotlinx-coroutines-core` on
     the compile classpath;
  2. `runBlocking` runs the coroutine to completion on the poll thread, so nothing is gained —
     the listener still blocks its consumer for the whole handler;
  3. `generateRecord` (the single-`ConsumerRecord` shape) has **no** `Modifier.SUSPEND` branch, so
     `suspend fun process(record: ConsumerRecord<K, V>)` emits `controller.process(record)` outside
     any coroutine builder and the generated Kotlin does not compile.

  Every migrated Kotlin example listener is a plain `fun`.
- `Headers` combined with a deserialization-exception parameter works in Kotlin as in Java —
  `fun process(key: String?, value: String?, headers: Headers, exception: Exception?)` is covered by
  the KSP tests `testProcessKeyValueHeaderAndException` and `testProcessKeyValueHeadersAndConsumer`.

---

## What the processor generates

For `class OrderListener { @KafkaListener("kafka.consumer.orders") void process(...) }` the
processor emits an `@Module` interface `OrderListenerModule` next to the class containing:

| Generated member | Purpose |
|---|---|
| `class OrderListenerProcessTag` | the tag that binds config, handler, container and rebalance listener together |
| `KafkaListenerConfig orderListenerProcessConfig(Config, ConfigValueMapper<KafkaListenerConfig>)` | `mapper.mapOrThrow(config.get("kafka.consumer.orders"))` |
| `KafkaRecordHandler<K,V> orderListenerProcessHandler(OrderListener controller)` | adapts the record to your method |
| `@Root GeneratedListener orderListenerProcessContainer(...)` | builds the subscribe or assign container |

`GeneratedListener extends Lifecycle`, and `@Root` keeps it in the graph even though nothing depends
on it — that is what starts the consumer.

The tag name is `capitalize(<class>) + capitalize(<method>) + "Tag"`, nested in `<class>Module`. Use
it to inject the container into a test:

```java
@Tag(OrderListenerModule.OrderListenerProcessTag.class)
@TestComponent
private Lifecycle consumerLifecycle;
```

Do **not** add `OrderListenerModule` to the `@KoraApp` `extends` clause — `@Module` interfaces
generated in the same compilation are discovered automatically.

---

## Custom tag on a listener

`tag()` replaces the generated tag with your own class, which is the readable way to bind a
rebalance listener:

```java
public final class OrdersTag {}

@Component
public final class OrderListener {
    @KafkaListener(value = "kafka.consumer.orders", tag = OrdersTag.class)
    void process(String value) { }
}

@Tag(OrdersTag.class)
@Component
public final class OrdersRebalanceListener implements ConsumerAwareRebalanceListener { ... }
```

When `tag()` is set, no `<Class><Method>Tag` class is generated — asserted by
`KafkaListenerKeyAndValueTest#testProcessValueWithTaggedListener`.

Tags on the **payload types** are a different thing: they select the deserializer, not the listener.
See the [serialization reference](kafka-serialization-reference.md).

---

## Related references

- [Consumer configuration](kafka-consumer-reference.md)
- [Serialization](kafka-serialization-reference.md)
- [Error handling](kafka-error-handling-reference.md)
- [Offsets](kafka-offset-reference.md)
- [Batch processing](kafka-batch-reference.md)

**Source:** framework tag `2.0.0.RC2` —
[kafka-annotation-processor](https://github.com/kora-projects/kora/tree/2.0.0.RC2/kafka/kafka-annotation-processor) ·
[kafka-symbol-processor](https://github.com/kora-projects/kora/tree/2.0.0.RC2/kafka/kafka-symbol-processor);
migrated examples on `migration/2.0` —
[kora-java-kafka](https://github.com/kora-projects/kora-examples/tree/migration/2.0/examples/java/kora-java-kafka) ·
[kora-kotlin-kafka](https://github.com/kora-projects/kora-examples/tree/migration/2.0/examples/kotlin/kora-kotlin-kafka)
