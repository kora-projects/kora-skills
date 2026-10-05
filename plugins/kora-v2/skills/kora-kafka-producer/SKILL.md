---
name: kora-kafka-producer
description: "Kora 2.0 Kafka publishers — @KafkaPublisher interfaces and the nested @KafkaPublisher.Topic, generated $X_Impl / $X_PublisherModule / $X_TopicConfig, KafkaModule from io.koraframework:kafka, Serializer<T> selection with @Json and @Tag, TransactionalPublisher with inTx/withTx/begin, KafkaPublishException, and the kafka.producer.* config tree (driverProperties, topic, idPrefix). Use when publishing to Kafka from a Kora service, choosing a send signature, wiring producer telemetry, or porting a ru.tinkoff.kora publisher to io.koraframework."
license: Apache-2.0
metadata:
  kora-version: "2.x"
---

# Kora Kafka Producer

> **Kora sub-skill — obey the [kora-v2 meta rules](../../SKILL.md) on every task:** **R0** ground the workspace on Kora 2.0 refs before starting (framework source at tag `2.0.0.RC2` + `kora-examples` at `migration/2.0` + Kora 2.0 docs at koraframework.io/v2, which trail the source; 1.x `kora-docs` pages are never an authority) · **R1** read this sub-skill before writing code · **R2** Kora 2.0 APIs only — no Spring/Micronaut/Quarkus, no Kora 1.x APIs, no invented annotations or config keys · **R3** journal any incorrect Kora usage. Add comments/Javadoc only if asked.

| | |
|---|---|
| **Artifact** | `io.koraframework:kafka` (BOM `io.koraframework:kora-bom`, version `2.0.0.RC2`) |
| **Module** | `KafkaModule` — `io.koraframework.kafka.common` (extends `KafkaPublisherModule` + `KafkaListenerModule`, which bring `KafkaSerializersModule` / `KafkaDeserializersModule`) |
| **Annotations** | `io.koraframework.kafka.common.annotation` — `@KafkaPublisher`, nested `@KafkaPublisher.Topic` |
| **Runtime types** | `io.koraframework.kafka.common.producer` — `TransactionalPublisher<P>`, `TransactionalPublisher.Transaction<P>`, `KafkaPublisherConfig`, `GeneratedPublisher`, `AbstractPublisher` |
| **Exceptions** | `io.koraframework.kafka.common.exceptions.KafkaPublishException` (extends `org.apache.kafka.common.KafkaException`) |
| **Kafka clients** | `org.apache.kafka:kafka-clients` **4.3.1**, pulled transitively by `io.koraframework:kafka` |

Kora generates the Kafka `Producer` implementation at compile time from an interface annotated with
`@KafkaPublisher`. You declare the contract; the annotation processor (Java) or KSP (Kotlin) emits
`$Name_Impl`, `$Name_PublisherModule` and `$Name_TopicConfig`, and wires the `KafkaProducer`,
the `Serializer<T>`s and the telemetry.

Read this first when:
- declaring a typed publisher with `@KafkaPublisher`,
- choosing a send signature (blocking, `RecordMetadata`, `Future`, `ProducerRecord`, Kotlin `suspend`),
- selecting serializers with `@Json` or `@Tag`,
- sending atomically with `TransactionalPublisher`.

For Kafka consumers (`@KafkaListener`), use the `kora-kafka-consumer` skill.

---

## Renamed in 2.0 — check this before touching ported 1.x code

| Kora 1.x | Kora 2.0 |
|---|---|
| `ru.tinkoff.kora.kafka.common.annotation.KafkaPublisher` | **`io.koraframework.kafka.common.annotation.KafkaPublisher`** |
| `ru.tinkoff.kora.kafka.common.producer.TransactionalPublisher` | **`io.koraframework.kafka.common.producer.TransactionalPublisher`** |
| `ru.tinkoff.kora.kafka.common.exceptions.KafkaPublishException` | **`io.koraframework.kafka.common.exceptions.KafkaPublishException`** |
| `ru.tinkoff.kora:kafka` | **`io.koraframework:kafka`** |
| `ru.tinkoff.kora:json-module` | **`io.koraframework:json-common`** (artifact renamed) |
| `ru.tinkoff.kora:kora-parent` (BOM) | **`io.koraframework:kora-bom`** |
| `ru.tinkoff.kora.json.module.JsonModule` | **`io.koraframework.json.common.JsonModule`** |
| `JsonWriter.toByteArray` declared `throws IOException` | **no checked exception** — a `try/catch (IOException)` is now a *compile error* |
| custom `KafkaProducerLogger*` / telemetry-listener factories registered as components | **gone** — see [Telemetry](#telemetry) for the 2.0 hooks |
| Kafka clients 3.x | **4.3.1** |
| Testcontainers `org.testcontainers:kafka` | **`org.testcontainers:testcontainers-kafka`** (2.0.5 renamed every module) |

**Not renamed, and still supported** — do not "fix" these:

- `@KafkaPublisher.Topic` still exists and is still nested inside `@KafkaPublisher`.
- `Future<RecordMetadata>`, `CompletionStage<RecordMetadata>` and `CompletableFuture<RecordMetadata>`
  are still accepted publisher return types, and Kotlin `suspend fun` / `Deferred<RecordMetadata>`
  still work. The publisher is the one place Kora 2.0 did **not** drop asynchronous signatures —
  see [Send signatures](#send-signatures) for the proof and the one extra dependency Kotlin needs.
- `TransactionalPublisher<P>` keeps its shape, `inTx`, `begin()` and the `idPrefix` / `maxPoolSize` /
  `maxWaitTime` config keys.

---

## Quick Start

### 1. Dependencies

```groovy
configurations {
    koraBom
    annotationProcessor.extendsFrom(koraBom); implementation.extendsFrom(koraBom)
}

dependencies {
    koraBom platform("io.koraframework:kora-bom:$koraVersion")   // koraVersion=2.0.0.RC2
    annotationProcessor "io.koraframework:annotation-processors" // Kotlin: ksp "io.koraframework:symbol-processors:$koraVersion"

    implementation "io.koraframework:kafka"
    implementation "io.koraframework:json-common"   // only if you publish @Json payloads
}
```

Artifacts pulled through the `koraBom` platform inherit their version — never pin them individually.
The Kotlin `ksp` configuration is **not** covered by the platform, so the processor there carries an
explicit version.

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

`JsonModule` is `io.koraframework.json.common.JsonModule`; `KafkaModule` is
`io.koraframework.kafka.common.KafkaModule`.

### 3. Declare a publisher

```java
import io.koraframework.json.common.annotation.Json;
import io.koraframework.kafka.common.annotation.KafkaPublisher;
import io.koraframework.kafka.common.annotation.KafkaPublisher.Topic;

@KafkaPublisher("kafka.producer.userEvents")
public interface UserEventPublisher {

    @Json
    record UserEvent(String userId, String eventType, Instant timestamp) {}

    @Topic(".topic")
    void send(@Json UserEvent event);
}
```

`@KafkaPublisher` takes the producer config path. `@Topic` takes a topic config path; a value
starting with `.` is resolved **relative to the publisher path**, so `.topic` above means
`kafka.producer.userEvents.topic`.

### 4. Inject and publish

```java
@Component
public final class UserService {

    private final UserEventPublisher publisher;

    public UserService(UserEventPublisher publisher) {
        this.publisher = publisher;
    }

    public void createUser(String userId) {
        publisher.send(new UserEvent(userId, "CREATED", Instant.now()));
    }
}
```

Constructor injection only — Kora has no field injection.

### 5. Configure

```hocon
kafka {
  producer {
    userEvents {
      driverProperties {
        "bootstrap.servers": ${KAFKA_BOOTSTRAP}   # required
        "acks": "all"
      }
      topic {                                     # matches @Topic(".topic")
        topic = "user-events"                     # required
        # partition = 0                           # optional
      }
      telemetry.logging.enabled = true            # defaults to false
    }
  }
}
```

`driverProperties` is required and takes plain Kafka producer properties. Serializers for `@Json`
and `@Tag` parameters come from the DI graph — do **not** set `key.serializer` / `value.serializer`
in `driverProperties`.

---

## Send signatures

`K` is the key type, `V` the value type. Parameters are classified by type: a
`org.apache.kafka.common.header.Headers` parameter is headers, a
`org.apache.kafka.clients.producer.Callback` parameter is a callback, a
`org.apache.kafka.clients.producer.ProducerRecord` parameter is the whole record, and everything
else is payload — one payload parameter is the value, two are key then value.

| Return type | Behaviour |
|---|---|
| `void` | **Blocks** until the broker acks (the generated code calls `.get()`), throws `KafkaPublishException` on failure |
| `RecordMetadata` | Blocks and returns the broker metadata |
| `Future<RecordMetadata>` | Returns immediately with a `CompletableFuture` completed by the producer callback |
| `CompletionStage<RecordMetadata>` | Same, typed as a stage |
| `CompletableFuture<RecordMetadata>` | Same, concrete type |
| Kotlin `suspend fun … : RecordMetadata` | Suspends until the callback fires — **needs `org.jetbrains.kotlinx:kotlinx-coroutines-jdk8`** |
| Kotlin `Deferred<RecordMetadata>` | Same dependency requirement |

> `void` is **not** fire-and-forget. Verified in the generated `$X_Impl`: every non-future signature
> ends in `this.delegate.send(_record, _observation).get()` wrapped in a try/catch that rethrows as
> `KafkaPublishException`. If you want fire-and-forget, take a `Future` and ignore it.

Parameter shapes, all valid with `@Topic`:

```java
@Topic(".topic") void send(V value);
@Topic(".topic") void send(K key, V value);
@Topic(".topic") void send(K key, V value, Headers headers);
@Topic(".topic") void send(V value, Callback callback);
```

Without `@Topic` the method must take a single `ProducerRecord<K, V>` (the topic comes from the
record), optionally followed by a `Callback`:

```java
void send(ProducerRecord<K, V> record);
void send(ProducerRecord<K, V> record, Callback callback);
```

### One shape per interface

**Do not mix `@Topic` methods and `ProducerRecord` methods in the same `@KafkaPublisher`
interface.** Split them into two interfaces (they may share the same config path).

The generated `$X_TopicConfig` record and the `$X_PublisherModule` factory that fills it disagree on
arity as soon as an interface mixes the two shapes. In Java this always fails:

```
error: constructor $MixedPublisher_TopicConfig in record $MixedPublisher_TopicConfig
       cannot be applied to given types;
  required: TopicConfig,TopicConfig
  found:    TopicConfig
```

In Kotlin it fails only when a non-`@Topic` method is declared *before* a `@Topic` one, which makes
it look like a random ordering bug:

```
$KMixed2_PublisherModule.kt:37:5 Syntax error: Expecting an argument.
```

Kotlin `suspend` / `Deferred` publishers additionally need:

```kotlin
implementation("org.jetbrains.kotlinx:kotlinx-coroutines-jdk8:1.10.2")
```

Without it KSP generates fine and `compileKotlin` fails on the *generated* file with
`Unresolved reference 'kotlinx'` / `Unresolved reference 'await'`.

See [Producer Reference](references/kafka-producer-reference.md) for the full API and config tree.

---

## Serialization

For every key and value the processor resolves a `org.apache.kafka.common.serialization.Serializer<T>`
from the graph:

1. `@Json` on the parameter → Kora's compile-time JSON serializer (needs `io.koraframework:json-common`
   and `@Json` on the DTO).
2. `@Tag(SomeTag.class)` on the parameter → the `Serializer<T>` `@Component` bound under that tag.
3. Neither → the untagged `Serializer<T>` for that type. `KafkaSerializersModule` supplies
   `String`, `byte[]`, `ByteBuffer`, `Bytes`, `Double`, `Float`, `Integer`, `Long`, `Short`,
   `UUID` and `Void`.

Both annotations also work on a `ProducerRecord` type argument:

```java
@KafkaPublisher("kafka.producer.myPublisher")
public interface MyPublisher {

    @Json
    record MyEvent(String username, int code) {}

    @Topic(".topic")
    void send(String key, @Json MyEvent value);
}

@KafkaPublisher("kafka.producer.myPublisher")
public interface MyRecordPublisher {
    void send(ProducerRecord<String, @Json MyEvent> record);
}
```

A hand-written serializer over Kora's generated `JsonWriter<T>` must **not** wrap `toByteArray` in a
`try/catch (IOException)` — in 2.0 the method declares no checked exception and the catch is a
compile error (`exception IOException is never thrown in body of corresponding try statement`).

See [Serialization Reference](references/kafka-serialization-reference.md).

---

## Transactional publishing

Declare the payload publisher, then a second `@KafkaPublisher` interface extending
`TransactionalPublisher<P>` where `P` is that publisher. The migrated examples nest `P` inside the
transactional interface so both fit in one file:

```java
import io.koraframework.kafka.common.annotation.KafkaPublisher;
import io.koraframework.kafka.common.annotation.KafkaPublisher.Topic;
import io.koraframework.kafka.common.producer.TransactionalPublisher;

@KafkaPublisher("kafka.producer.myTransactional")
public interface MyTransactionalPublisher extends TransactionalPublisher<MyTransactionalPublisher.TopicPublisher> {

    @KafkaPublisher("kafka.producer.myPublisher")
    interface TopicPublisher {
        @Topic("kafka.producer.myTopic")
        void send(String value);
    }
}
```

`inTx` commits when the lambda returns and aborts when it throws:

```java
transactionalPublisher.inTx(producer -> {
    producer.send("value1");
    producer.send("value2");
});
```

```hocon
kafka {
  producer {
    myTransactional {          # only these three keys are read here
      idPrefix = "order-service"   # transactional.id = "<idPrefix>-<random UUID>"
      maxPoolSize = 10
      maxWaitTime = "10s"
    }
    myPublisher {              # the wrapped publisher supplies the driver properties
      driverProperties { "bootstrap.servers": ${KAFKA_BOOTSTRAP} }
      myTopic { topic = "my-topic" }
    }
  }
}
```

**The transactional section carries no `driverProperties`.** Its config path is mapped to
`KafkaPublisherConfig.TransactionConfig`, which declares only `idPrefix`, `maxPoolSize` and
`maxWaitTime`; the transactional producers are built from the *wrapped* publisher's config plus a
generated `transactional.id`. A `driverProperties` block under the transactional section is dead
config that is silently ignored.

In Kotlin `inTx` is overloaded (consumer and function forms), so the SAM type must be named:

```kotlin
publisher.inTx(TransactionalConsumer<MyTransactionalPublisher.TopicPublisher, RuntimeException> { producer ->
    producer.send("""{"username":"Foo"}""")
})
```

A Kafka transaction covers Kafka only. It does **not** make a database write and a Kafka send atomic
together — use the transactional outbox pattern.
See [Transactions Reference](references/kafka-transactions-reference.md).

---

## Telemetry

`TelemetryConfig` defaults in 2.0 are **`logging.enabled = false`**, **`metrics.enabled = false`**,
`tracing.enabled = true`. A publisher emits no logs and no metrics until you turn them on per
publisher section:

```hocon
kafka.producer.myPublisher.telemetry {
  logging.enabled = true
  logging.maskHeaders = ["authorization", "cookie", "set-cookie", "x-api-key"]
  metrics.enabled = true
  metrics.driverMetrics = true   # binds Micrometer KafkaClientMetrics to the raw producer
}
```

**The publisher never logs record keys or values.** At TRACE the "KafkaPublisher starting record
sending..." line adds only the record `headers`; a header named in `logging.maskHeaders`
(case-insensitive, default `authorization`, `cookie`, `set-cookie`) is replaced by the
`@Tag(KafkaPublisherTelemetry.class) MaskingStrategy` (default `***`, it receives the raw `byte[]`).
Register your own tagged `MaskingStrategy` component to change the replacement. Payload logging with
format-aware `DataMasker`s exists only on the consumer side — see
[kora-kafka-consumer](../kora-kafka-consumer/references/kafka-telemetry-reference.md#masking); the
shared masking model is in [kora-aop-logging](../kora-aop-logging/references/logging-masking.md).

`KafkaPublisherModule` (pulled in by `KafkaModule`) supplies `KafkaPublisherTelemetryFactory` as a
`@DefaultComponent`, so telemetry is customised by *replacing components*, not by registering
listener factories the way 1.x did:

| Goal | 2.0 hook |
|---|---|
| Change log lines | `@Component` extending `DefaultKafkaPublisherLoggerFactory` (injected `@Nullable` into the default factory); its constructor takes the `@Tag(KafkaPublisherTelemetry.class) MaskingStrategy` |
| Change metric tags / meters | `@Component` extending `DefaultKafkaPublisherMetricsFactory` |
| Replace telemetry wholesale | `@Component` implementing `KafkaPublisherTelemetryFactory` — it overrides the `@DefaultComponent` |

All three live in `io.koraframework.kafka.common.producer.telemetry` (`…telemetry.impl` for the
`Default*` classes). There is no `KafkaProducerLogger`-style interface to implement any more.

---

## References

| Document | Description |
|---|---|
| [Producer Reference](references/kafka-producer-reference.md) | `@KafkaPublisher` API, generated types, every `kafka.producer.*` key, telemetry |
| [Serialization Reference](references/kafka-serialization-reference.md) | `@Json`, `@Tag`, custom `Serializer<T>` components |
| [Transactions Reference](references/kafka-transactions-reference.md) | `TransactionalPublisher`, `inTx` / `withTx` / `begin`, pooling |
| [Error Handling Reference](references/kafka-error-handling-reference.md) | `KafkaPublishException`, `SerializationException`, async failures |

---

## Common pitfalls

| Symptom | Fix |
|---|---|
| `constructor $X_TopicConfig … cannot be applied to given types` | The interface mixes `@Topic` and `ProducerRecord` methods — split it in two |
| KSP: `$X_PublisherModule.kt: Syntax error: Expecting an argument` | Same mixing problem, Kotlin flavour: a `ProducerRecord` method precedes a `@Topic` method |
| `Unresolved reference 'kotlinx'` in a generated `$X_Impl.kt` | A `suspend` / `Deferred` publisher method without `org.jetbrains.kotlinx:kotlinx-coroutines-jdk8` |
| `exception IOException is never thrown in body of corresponding try statement` | Drop the `try/catch (IOException)` around `JsonWriter.toByteArray` |
| `Required dependency not found` for the publisher | Add `KafkaModule` to `@KoraApp`, and `annotation-processors` (Java) / `symbol-processors` (KSP) |
| No `Serializer` found for a parameter | Add `@Json` (with `io.koraframework:json-common`) or bind a `@Tag` `Serializer<T>` `@Component` |
| `Key/value/headers signature has no @Topic annotation` | Add `@Topic`, or switch the method to a `ProducerRecord` parameter |
| `ConfigValueException` at `kafka.producer.<name>` | The publisher path has no section, or `driverProperties` / `topic` is missing |
| No producer logs or metrics | `telemetry.logging.enabled` / `telemetry.metrics.enabled` default to `false` — set them |
| No key/value in producer logs, even at TRACE | By design: the publisher logs only masked headers; payloads are logged by the consumer at TRACE |
| Transaction never aborts | Let the exception propagate out of the `inTx` lambda; do not swallow it |
| Publisher never starts | Nothing injects it — Kora prunes every node no `@Root` depends on; inject it from a rooted chain |
| `@KoraAppTest`: `Cannot inject Kora component … No matching component was found in the application graph` | The publisher was pruned. Add a `@Root @Component` holder in **main** sources (this is what `RootPublisher` does in the `kora-java-kafka` example) — `@KoraAppTest(components = …)` does **not** bring a pruned node back |

---

## Assets

Templates and config live in `assets/`.

| Template | Description |
|---|---|
| `MessagePublisher.java.template` / `.kt.template` | Publisher with every accepted send signature |
| `AdvancedMessagePublisher.java.template` | Headers, `Callback`, and the separate `ProducerRecord` interface |
| `AsyncMessagePublisher.java.template` | `Future` / `CompletionStage` publisher |
| `JsonMessagePublisher.java.template` / `.kt.template` | `@Json` publisher with DTO |
| `OrderEventPublisher.java.template` | Domain publisher plus its transactional wrapper |
| `TransactionalPublisher.java.template` / `.kt.template` | Transactional publisher and usage |
| `KotlinTransactionalPublisher.kt.template` | Kotlin `suspend` publisher inside a transaction |
| `MessageSender.java.template` | Error handling around sends |
| `Application.java.template` / `.kt.template` | `@KoraApp` with `KafkaModule` |
| `MessagePublisherTests.java.template` / `.kt.template` | `@KoraAppTest` + Testcontainers 2.0.5 |
| `application.conf.template` | HOCON producer config |
| `build.gradle.template` (Java) / `build.gradle.kts.template` (Kotlin) | Gradle dependencies |

`scripts/generate_producer.py` scaffolds a publisher, its HOCON section and an optional test;
`scripts/validate_config.py` checks a `kafka { … }` section; `scripts/run_evals.py` prints the
eval rubric.
