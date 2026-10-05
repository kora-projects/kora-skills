# Kafka Producer Reference (Kora 2.0)

Everything `@KafkaPublisher` generates, every signature the processor accepts, and every
`kafka.producer.*` key that is actually read.

## Contents

- [Packages and artifacts](#packages-and-artifacts)
- [`@KafkaPublisher`](#kafkapublisher)
- [`@KafkaPublisher.Topic`](#kafkapublishertopic)
- [What the processor generates](#what-the-processor-generates)
- [Accepted method signatures](#accepted-method-signatures)
- [Return types](#return-types)
- [Kotlin `suspend` and `Deferred`](#kotlin-suspend-and-deferred)
- [One shape per interface](#one-shape-per-interface)
- [Configuration](#configuration)
- [Telemetry](#telemetry)
- [Driver property recommendations](#driver-property-recommendations)
- [Injecting a publisher](#injecting-a-publisher)

## Quick Navigation

- [Serialization](kafka-serialization-reference.md) — `@Json`, `@Tag`, custom `Serializer<T>`
- [Error Handling](kafka-error-handling-reference.md) — exceptions, retries, dead letters
- [Transactions](kafka-transactions-reference.md) — `TransactionalPublisher`, atomic sends

---

## Packages and artifacts

| What | Fully-qualified name |
|---|---|
| Artifact | `io.koraframework:kafka` |
| Module | `io.koraframework.kafka.common.KafkaModule` |
| Publisher annotation | `io.koraframework.kafka.common.annotation.KafkaPublisher` |
| Topic annotation | `io.koraframework.kafka.common.annotation.KafkaPublisher.Topic` |
| Config | `io.koraframework.kafka.common.producer.KafkaPublisherConfig` (+ nested `TopicConfig`, `TransactionConfig`) |
| Transactional contract | `io.koraframework.kafka.common.producer.TransactionalPublisher` |
| Generated-publisher contract | `io.koraframework.kafka.common.producer.GeneratedPublisher` (extends `Lifecycle`) |
| Publish failure | `io.koraframework.kafka.common.exceptions.KafkaPublishException` |
| Telemetry | `io.koraframework.kafka.common.producer.telemetry.*` (+ `.impl.*`) |
| Serializer contract | `org.apache.kafka.common.serialization.Serializer` (Kafka clients **4.3.1**) |

`KafkaModule` extends `KafkaPublisherModule` (`io.koraframework.kafka.common.producer`, itself extending
`KafkaSerializersModule` from `io.koraframework.kafka.common.producer.serializer`) and
`KafkaListenerModule`, so adding it to `@KoraApp` brings the standard serializers and the default
publisher telemetry along.

---

## `@KafkaPublisher`

```java
@Target(ElementType.TYPE)
@Retention(RetentionPolicy.RUNTIME)
public @interface KafkaPublisher {
    String value();   // config path, mandatory, no default
}
```

- Allowed only on an **interface**. On anything else:
  `@KafkaPublisher can be placed only on interfaces.`
- The interface must extend **nothing**, or exactly one `TransactionalPublisher<P>`. Anything else:
  `@KafkaPublisher interface can either extend no interfaces or extend exactly one TransactionalPublisher<T>.`
- `value()` is the full config path of the producer section, e.g. `kafka.producer.myPublisher`.
  There is no default and no `configPath` attribute.
- `default` methods on the interface are ignored by the processor — use them for convenience
  overloads that delegate to a generated method.

## `@KafkaPublisher.Topic`

```java
@Target(ElementType.METHOD)
@Retention(RetentionPolicy.CLASS)
@interface Topic {
    String value();   // config path of the topic section
}
```

A value starting with `.` is **relative to the enclosing `@KafkaPublisher` path**:
`@KafkaPublisher("kafka.producer.userEvents")` + `@Topic(".topic")` reads
`kafka.producer.userEvents.topic`. Absolute paths (`@Topic("kafka.producer.myTopic")`) work too and
are what the migrated examples use.

Several methods may point at the same topic path; each gets its own entry in the generated topic
config record.

---

## What the processor generates

For `@KafkaPublisher("…") interface MyPublisher` in package `p`:

| Generated type | Role |
|---|---|
| `p.$MyPublisher_Impl` | `final class … extends AbstractPublisher implements MyPublisher` — the real producer |
| `p.$MyPublisher_TopicConfig` | `record` with one `KafkaPublisherConfig.TopicConfig` component per `@Topic` method, named `topic0`, `topic1`, … |
| `p.$MyPublisher_PublisherModule` | `@Module` interface supplying the config, the topic config, a `Function<Properties, $MyPublisher_Impl>` factory and the publisher itself |

For a transactional interface the processor emits `$MyTx_Impl` (a `Lifecycle` wrapping
`TransactionalPublisherImpl`) and `$MyTx_Module`.

You never reference these types by hand; they exist so that stack traces, `Multiple components
match` errors and `cannot be applied to given types` errors are readable.

---

## Accepted method signatures

Parameters are classified **by type**, not by position:

| Parameter type | Meaning |
|---|---|
| `org.apache.kafka.common.header.Headers` | record headers (at most one) |
| `org.apache.kafka.clients.producer.Callback` | Kafka send callback (at most one) |
| `org.apache.kafka.clients.producer.ProducerRecord<K, V>` | the whole record (at most one, excludes key/value/headers and `@Topic`) |
| anything else | payload — the first is the value; if a second appears the first becomes the key |

With `@Topic`:

```java
@Topic(".topic") void send(V value);
@Topic(".topic") void send(K key, V value);
@Topic(".topic") void send(K key, V value, Headers headers);
@Topic(".topic") void send(V value, Callback callback);
@Topic(".topic") void send(K key, V value, Headers headers, Callback callback);
```

Without `@Topic` — the topic comes from the record:

```java
void send(ProducerRecord<K, V> record);
void send(ProducerRecord<K, V> record, Callback callback);
```

Processor diagnostics you can hit:

| Message | Cause |
|---|---|
| `Key/value/headers signature has no @Topic annotation.` | key/value method missing `@Topic` |
| `ProducerRecord parameter is combined with @Topic annotation.` | `@Topic` on a `ProducerRecord` method |
| `ProducerRecord parameter is combined with key, value, or headers parameters.` | mixed shapes in one method |
| `Too many payload parameters were found.` | three or more non-special parameters |
| `More than one Headers parameter was found.` / `More than one Callback parameter was found.` | duplicates |

When both a `Callback` parameter and telemetry are present, the generated code invokes the
telemetry observation first and your callback second.

---

## Return types

Each of these shapes has a dedicated passing test in the framework's own
`KafkaPublisherTest` (`kafka-annotation-processor`, and its KSP twin in
`kafka-symbol-processor`) at tag `2.0.0.RC2` — `testReturnVoid`, `testReturnRecordMetadata`,
`testReturnFuture`, `testReturnStageFuture`, `testReturnCompletableFuture`,
`testReturnRecordMetadataFuture`, `testReturnRecordMetadataStageFuture`,
`testReturnRecordMetadataCompletableFuture`:

| Return type | Generated body |
|---|---|
| `void` | `this.delegate.send(record, observation).get()` — **blocks**, result discarded |
| `RecordMetadata` | same `.get()`, result returned |
| `Future<RecordMetadata>` | a `CompletableFuture` completed from the producer callback, returned immediately |
| `CompletionStage<RecordMetadata>` | same |
| `CompletableFuture<RecordMetadata>` | same |
| `Future<?>` / `CompletionStage<?>` | same (the wildcard forms are accepted too) |

> **`void` blocks.** It is not fire-and-forget. Every non-future signature ends in `.get()` inside a
> try/catch that rethrows as `KafkaPublishException`. For genuine fire-and-forget, declare
> `Future<RecordMetadata>` and drop the result, or pass a `Callback`.

Serialization runs *before* the try/catch, so a `SerializationException` propagates unwrapped; a
broker/transport failure surfaces as `KafkaPublishException` with the real cause in `getCause()`.
Future-returning methods never throw `KafkaPublishException` — the failure lands on the future.

## Kotlin `suspend` and `Deferred`

The KSP processor supports both, and generates
`kotlinx.coroutines.future.await` / `asDeferred` over the same `CompletableFuture`:

```kotlin
@KafkaPublisher("kafka.producer.myPublisher")
interface MyPublisher {
    @Topic(".topic")
    suspend fun send(value: String): RecordMetadata

    @Topic(".topic")
    fun sendDeferred(value: String): Deferred<RecordMetadata>
}
```

Both require an explicit dependency — `io.koraframework:kafka` does not bring coroutines:

```kotlin
implementation("org.jetbrains.kotlinx:kotlinx-coroutines-jdk8:1.10.2")
```

Without it KSP succeeds and `compileKotlin` fails on the *generated* file:

```
$MyPublisher_Impl.kt:17:8 Unresolved reference 'kotlinx'.
$MyPublisher_Impl.kt:199:6 Unresolved reference 'await'.
```

## One shape per interface

**A single `@KafkaPublisher` interface must use either `@Topic` methods or `ProducerRecord`
methods — never both.** Two interfaces may share the same config path, so splitting costs nothing.

The generated topic-config record and the module method that constructs it derive their arity
differently, so a mixed interface produces generated code that does not compile.

Java — always fails, whatever the order:

```
$MixedPublisher_PublisherModule.java:44: error: constructor $MixedPublisher_TopicConfig
    in record $MixedPublisher_TopicConfig cannot be applied to given types;
  required: TopicConfig,TopicConfig
  found:    TopicConfig
```

Kotlin — fails only when a `ProducerRecord` method is declared before a `@Topic` method, which
makes it look like an unrelated ordering bug:

```
$KMixed2_PublisherModule.kt:37:5 Syntax error: Expecting an argument.
$KMixed2_PublisherModule.kt:38:5 Too many arguments for
    'constructor(topic1: KafkaPublisherConfig.TopicConfig): $KMixed2_TopicConfig'.
```

---

## Configuration

`@KafkaPublisher("<path>")` maps `<path>` to `KafkaPublisherConfig`:

| Key | Type | Required | Meaning |
|---|---|---|---|
| `driverProperties` | `java.util.Properties` | **yes** | plain Apache Kafka producer properties |
| `telemetry` | `KafkaPublisherTelemetryConfig` | no | see [Telemetry](#telemetry) |

`@Topic("<path>")` maps `<path>` to `KafkaPublisherConfig.TopicConfig`:

| Key | Type | Required | Meaning |
|---|---|---|---|
| `topic` | `String` | **yes** | destination topic |
| `partition` | `Integer` | no (`@Nullable`) | fixed partition; standard Kafka partitioning when absent |

A transactional interface maps its path to `KafkaPublisherConfig.TransactionConfig`:

| Key | Type | Default | Meaning |
|---|---|---|---|
| `idPrefix` | `String` | `"kora-app-"` | `transactional.id` becomes `<idPrefix>-<random UUID>` |
| `maxPoolSize` | `int` | `10` | maximum pooled transactional producers |
| `maxWaitTime` | `Duration` | `10s` | how long `begin()` waits for a free producer |

Unknown keys inside a mapped section are ignored, so nesting the topic section inside the publisher
section works and keeps related config together:

```hocon
kafka {
  producer {
    myPublisher {
      driverProperties {
        "bootstrap.servers": ${KAFKA_BOOTSTRAP}
        "acks": "all"
        "enable.idempotence": true
      }
      topic {                        # matches @Topic(".topic")
        topic = "my-topic"
        # partition = 0
      }
      telemetry.logging.enabled = true
    }
  }
}
```

The migrated examples instead keep them as siblings — both layouts are valid, pick one and be
consistent:

```hocon
kafka.producer {
  my-publisher { driverProperties { "bootstrap.servers": ${KAFKA_BOOTSTRAP} } }
  my-topic     { topic = "my-topic-producer" }
}
```

Never set `key.serializer` / `value.serializer` in `driverProperties` — `AbstractPublisher` always
constructs the `KafkaProducer` with `ByteArraySerializer` on both sides and applies the
graph-resolved `Serializer<T>` itself.

---

## Telemetry

`kafka.producer.<name>.telemetry` maps to `KafkaPublisherTelemetryConfig extends TelemetryConfig`:

| Key | Default | Notes |
|---|---|---|
| `logging.enabled` | **`false`** | producer start/stop and per-record logs |
| `logging.maskHeaders` | `["authorization", "cookie", "set-cookie"]` | header names (case-insensitive) masked in the TRACE record log; the list replaces the default |
| `metrics.enabled` | **`false`** | the meters below |
| `metrics.driverMetrics` | `false` | binds Micrometer `KafkaClientMetrics` to the raw producer |
| `metrics.slo` | 1ms…90s histogram buckets | service-level objectives for the duration timer |
| `metrics.tags` | `{}` | extra tags on every meter |
| `tracing.enabled` | `true` | |
| `tracing.attributes` | `{}` | extra span attributes |

Meters emitted when `metrics.enabled = true`:

| Meter | Type | Key tags |
|---|---|---|
| `messaging.client.operation.duration` | timer | `messaging.system`, `messaging.client.id`, `messaging.operation.name` (`send`), `messaging.operation.type`, `messaging.destination.name`, `messaging.destination.partition.id`, `error.type` |
| `messaging.client.sent.messages` | counter | same |

Spans (when `tracing.enabled`): one `SpanKind.PRODUCER` span per record named `send <topic>`
(OpenTelemetry `<operation> <destination>`; RC1 used `<topic> send`), with `messaging.system`,
`messaging.operation.name` = `send`, `messaging.operation.type` = `send`, `messaging.destination.name`,
the three `system.*` attributes and `tracing.attributes`. A transactional publisher adds an INTERNAL
`producer transaction` span whose `messaging.operation.name` is set to `commit` or `rollback`.

Record logging. `logRecordStart` writes at DEBUG (`topic`, `publisherConfig`) or, when the logger is
at TRACE, adds `headers` — rendered as `name: value` lines, with every header in
`logging.maskHeaders` replaced by the `@Tag(KafkaPublisherTelemetry.class) MaskingStrategy`
(`KafkaPublisherModule` supplies `value -> "***"` as a `@DefaultComponent`). Keys and values are
**never** logged by the publisher. To change the replacement, register a tagged strategy:

```java
@Module
public interface KafkaPublisherMaskingModule {

    @Tag(KafkaPublisherTelemetry.class)
    default MaskingStrategy kafkaPublisherHeaderMasking() {
        return new MaskingKeepLast();
    }
}
```

`MaskingStrategy`, `MaskingFull`, `MaskingKeepFirst`, `MaskingKeepLast` live in
`io.koraframework.logging.common.masking`; the model is documented in
[kora-aop-logging masking](../../kora-aop-logging/references/logging-masking.md).

Customisation points (`KafkaPublisherModule` declares the factory as `@DefaultComponent`, and injects
the two `Default*Factory` classes as `@Nullable` dependencies):

```java
// swap the log format — the constructor takes the header masking strategy
@Component
public final class MyPublisherLoggerFactory extends DefaultKafkaPublisherLoggerFactory {
    public MyPublisherLoggerFactory(@Tag(KafkaPublisherTelemetry.class) MaskingStrategy maskingStrategy) {
        super(maskingStrategy);
    }
    …
}

// swap the meters
@Component
public final class MyPublisherMetricsFactory extends DefaultKafkaPublisherMetricsFactory { … }

// replace telemetry entirely — this overrides the @DefaultComponent
@Component
public final class MyPublisherTelemetryFactory implements KafkaPublisherTelemetryFactory {
    @Override
    public KafkaPublisherTelemetry get(String publisherConfig, String publisherCanonicalName,
                                       KafkaPublisherTelemetryConfig config, Properties properties) { … }
}
```

Kora 1.x registered telemetry *listeners* through dedicated factory interfaces; those are gone. If a
ported service has such a class, delete it and either turn the built-in telemetry on through config
or subclass one of the `Default*Factory` classes above.

---

## Driver property recommendations

These are plain Apache Kafka 4.x producer properties; Kora passes them through untouched.

Reliability:

```hocon
driverProperties {
  "acks" = "all"
  "enable.idempotence" = true
  "retries" = 2147483647
  "delivery.timeout.ms" = 120000
}
```

Throughput:

```hocon
driverProperties {
  "acks" = 1
  "linger.ms" = 20
  "batch.size" = 65536
  "compression.type" = "lz4"
}
```

Low latency:

```hocon
driverProperties {
  "acks" = 1
  "linger.ms" = 0
  "max.in.flight.requests.per.connection" = 5
}
```

`min.insync.replicas` is a **broker/topic** setting, not a producer property — putting it in
`driverProperties` does nothing.

---

## Injecting a publisher

```java
@Component
public final class MyService {

    private final MyPublisher publisher;

    public MyService(MyPublisher publisher) {
        this.publisher = publisher;
    }

    public void doSomething() {
        publisher.send("key", "value");
    }
}
```

The publisher is a `Lifecycle` node, but `Lifecycle` alone does **not** make it a graph root: Kora
prunes every node that no `@Root` transitively depends on, so a publisher nobody injects is never
instantiated.

This bites hardest in tests. `@TestComponent` can only inject what is in the graph, so a pruned
publisher fails with:

```
org.junit.jupiter.api.extension.ExtensionConfigurationException: Cannot inject Kora component:
  com.example.publisher.MessagePublisher
Problem:
  No matching component was found in the application graph.
```

`@KoraAppTest(components = MessagePublisher.class)` does **not** fix it — the node was pruned at
compile time and is not in the graph to include. Keep a root in **main** sources instead: either the
`@HttpController` / `@KafkaListener` / service that really uses the publisher, marked `@Root` if
nothing else reaches it, or a dedicated holder — which is exactly what `RootPublisher` does in the
`kora-java-kafka` and `kora-kotlin-kafka` examples:

```java
@Root
@Component
public final class PublisherRoot {
    public PublisherRoot(MessagePublisher publisher) {}
}
```
