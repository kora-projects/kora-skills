---
name: kora-kafka-consumer
description: "Kafka consumers in Kora 2.0 — @KafkaListener (io.koraframework.kafka.common.annotation) on a @Component method, wired by KafkaModule from io.koraframework:kafka. Covers the accepted handler signatures, subscribe vs assign containers, who commits the offset, @Json / @Tag deserializers, KafkaSkipRecordException and RecordKey/ValueDeserializationException, ConsumerAwareRebalanceListener, kafka.consumer.* config, and consumer telemetry. Use when consuming Kafka messages, porting a 1.x @KafkaListener, or debugging \"Kafka listener method has unsupported parameter\"."
license: Apache-2.0
metadata:
  kora-version: "2.x"
---

# Kora Kafka Consumer

> **Kora sub-skill — obey the [kora-v2 meta rules](../../SKILL.md) on every task:** **R0** ground the workspace on Kora 2.0 refs before starting (framework source at tag `2.0.0.RC2` + `kora-examples` at `migration/2.0` + Kora 2.0 docs at koraframework.io/v2, which trail the source; 1.x `kora-docs` pages are never an authority) · **R1** read this sub-skill before writing code · **R2** Kora 2.0 APIs only — no Spring/Micronaut/Quarkus, no Kora 1.x APIs, no invented annotations or config keys · **R3** journal any incorrect Kora usage. Add comments/Javadoc only if asked.

| | |
|---|---|
| **Artifact** | `io.koraframework:kafka` (BOM `io.koraframework:kora-bom`, version `2.0.0.RC2`) |
| **Module** | `KafkaModule` — `io.koraframework.kafka.common` (extends `KafkaListenerModule` + `KafkaPublisherModule`, which bring `KafkaDeserializersModule` / `KafkaSerializersModule`) |
| **Annotation** | `io.koraframework.kafka.common.annotation.KafkaListener` — `String value()` (config path, required), `Class<?> tag()` |
| **Config type** | `io.koraframework.kafka.common.consumer.KafkaListenerConfig` |
| **Exceptions** | `io.koraframework.kafka.common.exceptions.{KafkaSkipRecordException, SkippableRecordException, RecordKeyDeserializationException, RecordValueDeserializationException}` |
| **Rebalance** | `io.koraframework.kafka.common.consumer.ConsumerAwareRebalanceListener` |
| **Kafka clients** | `4.3.1` (from the 2.0 catalog) |

`@KafkaListener` turns a method on a `@Component` into a Kafka consumer. The annotation processor
(Java) or KSP (Kotlin) generates a `<ListenerClass>Module` next to your class containing the config
binding, the record handler and a `@Root` container — the graph starts and stops it for you.

**Listener contracts are synchronous.** Listener methods return `void`/`Unit` and run on a
dedicated poll thread. There is no Kora `Context` — that type no longer exists anywhere in the
framework.

An async return type on a **listener** is not rejected, it is **silently discarded**: neither
consumer generator inspects the return type at all (no `getReturnType` / `isFuture` /
`isCompletionStage` anywhere in `KafkaConsumerHandlerGenerator.java` or `KafkaHandlerGenerator.kt`),
and the call is emitted as the bare statement `controller.process(...)`. So a listener returning
`CompletionStage`/`Mono`/`Future` compiles, and `RecordHandler` commits `offset + 1` **as soon as
the method returns** — before the async work finishes. The record is marked done while it is still
in flight, and a failure inside the future never reaches telemetry or the backoff path. Return
`void`/`Unit` and do the work inline.

> This is the opposite of the **publisher** side, where an async return type is a first-class,
> generated contract — `Future`/`CompletionStage` (and, in Kotlin, `suspend`/`Deferred`) are the
> delivery acknowledgement of a send. Do not carry either rule across. See
> [kora-kafka-producer](../kora-kafka-producer/SKILL.md).

`suspend` is the one exception worth knowing, and it is a trap rather than a feature: unlike the
HTTP-server and repository processors, **KSP does not reject a `suspend` listener** — for the
key/value and batch shapes it wraps your call in `kotlinx.coroutines.runBlocking(Dispatchers.Unconfined)`
(`KafkaHandlerGenerator.kt`, with framework tests `testProcessValueSuspend` and
`testProcessRecordsSuspend`). But `kotlinx-coroutines` appears in **no** Kora 2.0 build file, so your
project must supply it; the coroutine is run to completion on the poll thread, so it buys no
concurrency; and the single-`ConsumerRecord` shape has no such handling at all, so a `suspend`
listener taking a `ConsumerRecord` generates Kotlin that does not compile. **Write plain `fun`.**

---

## Renamed in 2.0 — check this before touching ported 1.x code

| Kora 1.x | Kora 2.0 |
|---|---|
| `ru.tinkoff.kora:kafka` | **`io.koraframework:kafka`** |
| `ru.tinkoff.kora:json-module` | **`io.koraframework:json-common`** |
| `ru.tinkoff.kora.kafka.common.annotation.KafkaListener` | **`io.koraframework.kafka.common.annotation.KafkaListener`** |
| `ru.tinkoff.kora.kafka.common.consumer.*` | **`io.koraframework.kafka.common.consumer.*`** |
| `ru.tinkoff.kora.kafka.common.exceptions.*` | **`io.koraframework.kafka.common.exceptions.*`** |
| `ru.tinkoff.kora.common.Component` | **`io.koraframework.common.annotation.Component`** |
| `ru.tinkoff.kora.common.Tag` | **`io.koraframework.common.annotation.Tag`** |
| `jakarta.annotation.Nullable` on listener params | **`org.jspecify.annotations.Nullable`** (type-use) |
| `KafkaConsumerTelemetry.KafkaConsumerRecordsTelemetryContext<K,V>` listener parameter | **removed** — 2.0's `KafkaUtils` has no telemetry check at all, so the parameter is no longer recognised. In a `ConsumerRecord`/`ConsumerRecords` listener it is a processor error; in a bare key/value listener it is silently taken as a **payload** and fails later as a missing `Deserializer` |
| a custom `KafkaConsumerLoggerFactory` implementation | **subclass `DefaultKafkaConsumerLoggerFactory`** and register it as a `@Component` — see [Telemetry](references/kafka-telemetry-reference.md) |
| `JsonReader.read(bytes)` returning non-null | **`@Nullable`** — Kotlin needs `requireNotNull(...)` |
| `org.testcontainers:kafka`, `org.testcontainers.containers.KafkaContainer` | **`org.testcontainers:testcontainers-kafka`**, `org.testcontainers.kafka.KafkaContainer` (Testcontainers 2.0.5) |

**References:** [Consumer config](references/kafka-consumer-reference.md) · [Listener signatures](references/kafka-listener-reference.md) · [Strategies](references/kafka-strategies-reference.md) · [Serialization](references/kafka-serialization-reference.md) · [Errors](references/kafka-error-handling-reference.md) · [Offsets](references/kafka-offset-reference.md) · [Batch](references/kafka-batch-reference.md) · [Rebalance](references/kafka-rebalance-reference.md) · [Telemetry](references/kafka-telemetry-reference.md) · [Transactions](references/kafka-transactions-reference.md) · [Testing](references/kafka-testing-reference.md)

---

## Quick start

**1. Dependencies** — every Kora artifact takes its version from the BOM; never pin one individually.

```groovy
configurations {
    koraBom
    annotationProcessor.extendsFrom(koraBom); implementation.extendsFrom(koraBom)
    testImplementation.extendsFrom(koraBom); testAnnotationProcessor.extendsFrom(koraBom)
}

dependencies {
    koraBom platform("io.koraframework:kora-bom:$koraVersion")   // koraVersion=2.0.0.RC2
    annotationProcessor "io.koraframework:annotation-processors"

    implementation "io.koraframework:kafka"
    implementation "io.koraframework:json-common"
    implementation "io.koraframework:config-hocon"
    implementation "io.koraframework:logging-logback"

    testImplementation "io.koraframework:test-junit5"
}
```

Kotlin uses `ksp("io.koraframework:symbol-processors")` instead of `annotationProcessor` — see
[kora-project-setup-kotlin](../kora-project-setup-kotlin/SKILL.md).

**2. Application graph** — a `@KoraApp` interface `extends` each module (an interface never
`implements`). The generated `<ListenerClass>Module` is discovered automatically inside the same
compilation; do **not** add it to the `extends` clause.

```java
@KoraApp
public interface Application extends HoconConfigModule, LogbackModule, JsonModule, KafkaModule {

    static void main(String[] args) {
        KoraApplication.run(ApplicationGraph::graph);
    }
}
```

**3. Listener**

```java
@Component
public final class UserEventListener {

    private static final Logger log = LoggerFactory.getLogger(UserEventListener.class);

    @KafkaListener("kafka.consumer.user-events")
    void process(String value) {
        log.info("Received: {}", value);
    }
}
```

**4. Configuration** — the `@KafkaListener` value is the full config path, nothing is prefixed for
you. `kafka.consumer.<name>` is a convention used by the Kora examples, not a framework rule.

```hocon
kafka {
  consumer {
    user-events {
      topics = ["user-events"]
      driverProperties {
        "bootstrap.servers" = "localhost:9092"
        "bootstrap.servers" = ${?KAFKA_BOOTSTRAP}
        "group.id" = "user-service"
        "auto.offset.reset" = "earliest"
      }
    }
  }
}
```

HOCON has no `${VAR:default}` placeholder. Write the literal first, then override it with `${?VAR}`.

---

## Accepted handler signatures

The processor classifies each parameter **by type**, then picks one of three handler shapes. Anything
it cannot classify becomes a payload parameter — and a third payload parameter is a compile error
(`Kafka listener method has too many payload parameters`). Inject services through the **class
constructor**, never as a listener parameter.

| Parameter type | Meaning |
|---|---|
| `ConsumerRecords<K, V>` | whole poll batch — selects the batch handler |
| `ConsumerRecord<K, V>` | single record, deserialized lazily — selects the record handler |
| `Consumer<K, V>` | the Kafka consumer — **turns off Kora's automatic commit** |
| `Headers` | `record.headers()` (key/value shape only) |
| `RecordKeyDeserializationException` / `RecordValueDeserializationException` | the specific failure, else `null` |
| `Exception` / `Throwable` | either failure, key first, else `null` |
| anything else | payload: first unclassified = value; two unclassified = key then value |

Batch listeners accept **only** `ConsumerRecords` and `Consumer` — a `Headers` or exception parameter
there fails with `Kafka records listener method has unsupported parameter`.

```java
void process(String value)                                             // value only
void process(String key, String value)                                 // key, value
void process(String key, String value, Headers headers)                // + headers
void process(ConsumerRecord<String, String> record)                    // full metadata
void process(ConsumerRecords<String, String> records)                  // whole poll batch
void process(ConsumerRecord<String, String> r, Consumer<String, String> c)  // manual commit
void process(@Nullable @Json Event e, @Nullable Exception exception)   // deserialization errors
```

The complete list, with the processor test that proves each one, is in the
[listener reference](references/kafka-listener-reference.md).

---

## Who commits the offset

Kora decides this at compile time from the signature, and at runtime from `enable.auto.commit`.

| Signature | `enable.auto.commit` | Who commits |
|---|---|---|
| no `Consumer` parameter | unset or `false` | **Kora** — `commitSync(offset + 1)` after each record, or `commitSync()` after the whole poll for a batch listener |
| no `Consumer` parameter | `true` | the Kafka driver's periodic auto-commit; Kora does not commit |
| has a `Consumer` parameter | any | **you** — call `consumer.commitSync()` yourself |
| assign strategy (no `group.id`) | any | **nobody** — commits are disabled in the assign container |

If `enable.auto.commit` is absent the subscribe container forces it to `false` and takes over
committing. Details and patterns: [offsets](references/kafka-offset-reference.md).

---

## Subscribe vs assign

The container is chosen by the presence of `group.id` in `driverProperties`:

| | Subscribe (`group.id` set) | Assign (no `group.id`) |
|---|---|---|
| Delivery | partitions split across group members | every instance reads every partition |
| `topics` | required unless `topicsPattern` is set | **required**, one or more topics |
| `topicsPattern` | supported | **rejected** at startup |
| Offsets | committed (see above) | never committed; `offset` config seeks instead |
| Rebalance listener | honoured | not used |
| Consumer lag gauge | not reported | reported |

The assign container reads every partition of **every** listed topic (`topics = ["prices", "rates"]`
is fine) and fails fast in its constructor, so the graph does not start:

- `topicsPattern` set → `@KafkaListener with assign strategy (when group.id is null) does not support topicsPattern, please specify topics instead`
- `topics` missing or empty → `@KafkaListener with assign strategy (when group.id is null) requires at least one topic to subscribe, but received: ...`

A pattern subscription needs the group rebalance protocol, so it needs a `group.id`.

[Strategies reference](references/kafka-strategies-reference.md).

---

## Deserialization

`KafkaDeserializersModule` supplies `Deserializer` beans for `String`, `UUID`, `byte[]`, `Bytes`,
`ByteBuffer`, `Double`, `Float`, `Integer`, `Long`, `Short` and `Void`. `@Json` on the payload type
selects the generated `JsonKafkaDeserializer<T>`; `@Tag(X.class)` selects your own `Deserializer<T>`
`@Component` carrying that tag.

```java
@Json public record OrderEvent(String orderId, BigDecimal amount) {}

@KafkaListener("kafka.consumer.orders")
void process(@Nullable @Json OrderEvent event, @Nullable Exception exception) {
    if (exception != null) { log.warn("bad record", exception); return; }
    orderService.process(event);
}
```

Kotlin writes the nullability into the type, not into an annotation, and `JsonReader.read` is
`@Nullable`:

```kotlin
@KafkaListener("kafka.consumer.orders")
fun process(@Json event: OrderEvent?, exception: Exception?) { ... }

override fun deserialize(topic: String, data: ByteArray): OrderEvent =
    requireNotNull(reader.read(data)) { "Empty payload in topic $topic" }
```

[Serialization reference](references/kafka-serialization-reference.md).

---

## Errors

| Thrown from the listener | Container behaviour |
|---|---|
| `KafkaSkipRecordException` | reported to telemetry, record skipped, offset still committed |
| any exception implementing `SkippableRecordException` | same as above |
| anything else, single-record listener | poll loop aborts, waits `backoffTimeout` (doubling up to 60s), reconnects and **re-reads from the last committed offset** |
| anything else, batch listener | same — there is no per-record skip in the batch handler |

Deserialization is lazy: `ConsumerRecord.key()`/`value()` throw
`RecordKeyDeserializationException` / `RecordValueDeserializationException`, and both carry
`getRecord()` returning the raw `ConsumerRecord<byte[], byte[]>` for a DLQ.
[Error handling reference](references/kafka-error-handling-reference.md).

---

## Configuration keys

`kafka.consumer.<name>` is the conventional path. Everything below is `KafkaListenerConfig`.

| Key | Default | Meaning |
|---|---|---|
| `driverProperties` | — | **required**, raw Kafka consumer properties |
| `topics` | `null` | list of topics; `topics` or `topicsPattern` must be set |
| `topicsPattern` | `null` | regex subscription; subscribe mode only |
| `partitions` | `null` | used only for consumer naming when nothing else identifies it |
| `offset` | `latest` | `earliest`, `latest` or a `Duration` to rewind; **assign mode only** |
| `pollTimeout` | `5s` | `poll()` wait |
| `backoffTimeout` | `15s` | initial pause after an unhandled error, doubles up to 60s |
| `threads` | `1` | consumers started; **`0` disables the listener** |
| `partitionRefreshInterval` | `1m` | assign-mode partition rediscovery |
| `shutdownWait` | `30s` | graceful shutdown budget |
| `allowEmptyRecords` | `false` | call a batch listener with an empty `ConsumerRecords` |
| `initializationFailTimeout` | `null` | fail startup if the first poll does not happen in time |
| `telemetry.logging.enabled` | **`false`** | |
| `telemetry.logging.maskHeaders` | `["authorization", "cookie", "set-cookie"]` | header names (case-insensitive) masked in TRACE record logs |
| `telemetry.metrics.enabled` | **`false`** | |
| `telemetry.metrics.driverMetrics` | `false` | bind the Kafka client's own Micrometer metrics |
| `telemetry.tracing.enabled` | `true` | |

Logging and metrics are **off by default in 2.0**. An example that claims to demonstrate them must
turn them on explicitly. [Consumer config reference](references/kafka-consumer-reference.md) ·
[Telemetry reference](references/kafka-telemetry-reference.md).

### Payload logging and masking

With `telemetry.logging.enabled = true` and the listener's logger at **TRACE**, the
"KafkaListener starting handling record..." line also carries `headers`, `key` and `value`. At DEBUG
it carries only topic/partition/offset. Headers named in `maskHeaders` go through the
`@Tag(KafkaConsumerTelemetry.class) MaskingStrategy` (default: `***`). Key and value are rendered by
`DefaultKafkaConsumerBodyConverter`: when the deserializer is a `JsonKafkaDeserializer` (an `@Json`
parameter) it uses the `@Tag(KafkaConsumerTelemetry.class) DataMasker` with format `json`, otherwise
the raw bytes are written as UTF-8. **No such `DataMasker` is registered by default**, so JSON values
are logged unmasked until you provide one:

```java
@Module
public interface KafkaMaskingModule {

    @Tag(KafkaConsumerTelemetry.class)
    default DataMasker kafkaJsonDataMasker() {
        return new JsonDataMasker(MaskingPathRules.builder()
            .mask("password", new MaskingFull())
            .mask("card.number", new MaskingKeepLast())
            .build());
    }
}
```

Shared masking model (`MaskingStrategy`, `DataMasker`, `JsonDataMasker`, `MaskingPathRules`):
[kora-aop-logging masking](../kora-aop-logging/references/logging-masking.md). Kafka specifics:
[Telemetry reference](references/kafka-telemetry-reference.md#masking).

---

## Common pitfalls

| Symptom | Cause | Fix |
|---|---|---|
| `Kafka listener method has unsupported parameter` | a service, a telemetry context or a `Headers` on a batch listener | inject services via the constructor; drop the telemetry parameter — it does not exist in 2.0 |
| `Kafka listener method has too many payload parameters` | three unclassified parameters | at most key + value; move the rest to the constructor |
| `Kafka listener method has no payload parameter` | only `Consumer`/`Headers`/exception parameters | add a value, `ConsumerRecord` or `ConsumerRecords` |
| Nothing is consumed, no error | `threads = 0` | `threads >= 1` |
| Records reprocessed after a crash | `Consumer` parameter present but `commitSync()` never called | commit yourself, or drop the `Consumer` parameter |
| Records lost on crash | `"enable.auto.commit" = true` commits ahead of processing | remove the key so Kora commits after the handler returns |
| `offset = "5m"` ignored | `group.id` is set → subscribe mode | `offset` only seeks in assign mode; use `auto.offset.reset` with a group |
| `Group id is required for subscribe container` | subscribe container built without `group.id` | set `group.id` in `driverProperties` |
| `assign strategy (when group.id is null) does not support topicsPattern` | `topicsPattern` without `group.id` | list the topics, or add `group.id` to use subscribe mode |
| `assign strategy (when group.id is null) requires at least one topic` | no `group.id` and no `topics` | list the topics, or add `group.id` |
| JSON record values in TRACE logs are not masked | no `@Tag(KafkaConsumerTelemetry.class) DataMasker` in the graph | register a `json` `DataMasker` with that tag |
| Consumer restarts in a loop | handler throws on every record | throw `KafkaSkipRecordException`, or handle and return |
| Rebalance listener never fires | tag mismatch, or assign mode | tag both sides with the same class; assign mode has no rebalance |
| No metrics / no logs | `telemetry.metrics.enabled` and `telemetry.logging.enabled` default to `false` | enable them per listener |
| Kotlin: `'deserialize' overrides nothing` | `data: ByteArray` vs the `@NullMarked` contract | match the contract exactly; `read()` is `@Nullable`, wrap in `requireNotNull` |
| `ru.tinkoff.kora` symbols after a rename | stale `build/generated` | `./gradlew clean` and rebuild with `--no-build-cache`; never edit generated code |

---

## Templates and scripts

`assets/` — `Application.{java,kt}.template`, `ConsumerListener.{java,kt}.template`,
`JsonMessageListener.{java,kt}.template`, `ConsumerListenerTests.{java,kt}.template`,
`MessagePublisher.{java,kt}.template`, `JsonMessagePublisher.{java,kt}.template`,
`TransactionalPublisher.{java,kt}.template`, `MessagePublisherTests.{java,kt}.template`,
`application.conf.template`, `build.gradle.template`, `build.gradle.kts.template`.

`scripts/` — `generate_consumer.py`, `generate_producer.py` (both support `--dry-run`) and
`validate_config.py` (read-only). Run `--help` for the full CLI.

```bash
python3 scripts/generate_consumer.py --name UserEvent --topics user-events \
    --package com.example --signature record --dry-run
python3 scripts/validate_config.py --config src/main/resources/application.conf
```

---

## Related skills

- [kora-kafka-producer](../kora-kafka-producer/SKILL.md) — `@KafkaPublisher`, `@Topic`, transactions
- [kora-json](../kora-json/SKILL.md) — `@Json`, `JsonReader`/`JsonWriter`
- [kora-di-compile](../kora-di-compile/SKILL.md) — `@KoraApp`, `@Component`, `@Tag`
- [kora-config-hocon](../kora-config-hocon/SKILL.md) — HOCON substitution rules
- [kora-testing-junit-java](../kora-testing-junit-java/SKILL.md) · [kora-testing-junit-kotlin](../kora-testing-junit-kotlin/SKILL.md) — `@KoraAppTest`
- [kora-telemetry-metrics](../kora-telemetry-metrics/SKILL.md) — the meters this skill configures
- [kora-aop-resilient](../kora-aop-resilient/SKILL.md) — `@Retryable` on a listener method

## Source of truth

Evidence order: framework source and tests > migrated examples > the Kora 2.0 docs
([koraframework.io/v2/en/documentation/kafka](https://koraframework.io/v2/en/documentation/kafka/)).
1.x pages (`ru.tinkoff.kora`) are background only. Resolve 2.0 questions from:

- Framework source, tag `2.0.0.RC2`:
  [kafka](https://github.com/kora-projects/kora/tree/2.0.0.RC2/kafka/kafka) ·
  [kafka-annotation-processor](https://github.com/kora-projects/kora/tree/2.0.0.RC2/kafka/kafka-annotation-processor) ·
  [kafka-symbol-processor](https://github.com/kora-projects/kora/tree/2.0.0.RC2/kafka/kafka-symbol-processor)
- Migrated examples, branch `migration/2.0`:
  [kora-java-kafka](https://github.com/kora-projects/kora-examples/tree/migration/2.0/examples/java/kora-java-kafka) ·
  [kora-kotlin-kafka](https://github.com/kora-projects/kora-examples/tree/migration/2.0/examples/kotlin/kora-kotlin-kafka)
- Migrated guide apps, branch `migration/2.0`:
  [kora-java-guide-messaging-kafka-app](https://github.com/kora-projects/kora-examples/tree/migration/2.0/guides/java/kora-java-guide-messaging-kafka-app) ·
  [kora-kotlin-guide-messaging-kafka-app](https://github.com/kora-projects/kora-examples/tree/migration/2.0/guides/kotlin/kora-kotlin-guide-messaging-kafka-app)
- [Apache Kafka consumer configs](https://kafka.apache.org/documentation/#consumerconfigs) for
  everything inside `driverProperties`
