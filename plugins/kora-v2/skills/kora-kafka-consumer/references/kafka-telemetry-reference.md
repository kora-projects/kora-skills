# Kafka Consumer Telemetry Reference (Kora 2.0)

Logging, metrics and tracing for `@KafkaListener`, and how to replace any of them.

## Contents

- [Defaults changed in 2.0](#defaults-changed-in-20)
- [Configuration](#configuration)
- [Logging](#logging)
- [Masking](#masking)
- [Metrics](#metrics)
- [Tracing](#tracing)
- [Replacing a telemetry component](#replacing-a-telemetry-component)
- [Pitfalls](#pitfalls)

---

## Defaults changed in 2.0

`KafkaConsumerTelemetryConfig` extends the framework-wide `TelemetryConfig`, whose defaults are:

| | Default |
|---|---|
| `logging.enabled` | **`false`** |
| `metrics.enabled` | **`false`** |
| `metrics.driverMetrics` | `false` |
| `tracing.enabled` | `true` |

Logging and metrics must be switched on **per listener**. Any example that claims to show consumer
logs or `messaging.*` meters and does not enable them is showing nothing.

`logging.enabled` also gates the container's own lifecycle log lines: with it `false` the container
installs `NOPLogger`, so "KafkaListener started / stopped / backing off" never appears — which makes
a misconfigured consumer look completely silent.

If tracing, metrics **and** logging are all off, the factory short-circuits to
`NoopKafkaConsumerTelemetry.INSTANCE` and no telemetry object is built at all.

---

## Configuration

```hocon
kafka.consumer.orders {
  topics = ["orders"]
  driverProperties {
    "bootstrap.servers" = ${?KAFKA_BOOTSTRAP}
    "group.id" = "order-service"
  }

  telemetry {
    logging {
      enabled = true
      maskHeaders = ["authorization", "cookie", "set-cookie", "x-api-key"]
    }

    metrics {
      enabled = true
      driverMetrics = false
      slo = [1, 10, 50, 100, 200, 500, 1000, 2000, 5000, 10000]
      tags {
        "consumer-type" = "orders"
        "environment" = "production"
      }
    }

    tracing {
      enabled = true
      attributes { "service.name" = "order-service" }
    }
  }
}
```

`tags` are added to every consumer meter and `attributes` to every poll span.

**`slo` changed type, and the bare-number form changed meaning.** In 2.0 it is `Duration[]`, and
`DurationConfigValueMapper` maps a bare number with `Duration.ofMillis(number.longValue())` — so
`slo = [1, 10, 50]` still means milliseconds and still works. The hazard is a 1.x config written
against `OpentelemetrySpec.V123`, where `slo` was a `double[]` of **seconds**
(`DEFAULT_SLO_V123 = {0.001, 0.010, 0.050, …}`). Carried over unchanged, every one of those values
truncates to `Duration.ofMillis(0)` — the histogram silently collapses to zero-width buckets, with
no error. `OpentelemetrySpec` itself no longer exists in 2.0. Convert such values to milliseconds,
or write them as duration strings (`"1ms"`, `"10ms"`), which the same mapper also accepts.

Metrics need `io.koraframework:micrometer-module` (and an exporter) for a `MeterRegistry` to exist;
tracing needs `io.koraframework:opentelemetry-tracing` plus an exporter for a `Tracer`. Both are
injected as `@Nullable` — without them `enabled = true` silently produces nothing. See
[kora-telemetry-metrics](../../kora-telemetry-metrics/SKILL.md) and
[kora-telemetry-tracing](../../kora-telemetry-tracing/SKILL.md).

---

## Logging

`DefaultKafkaConsumerLoggerFactory.DefaultKafkaConsumerLogger` logs under the **listener's canonical
class name**, so levels are controlled per listener:

```hocon
logging.levels {
  "com.example.OrderListener" = "DEBUG"
  "io.koraframework.kafka" = "INFO"
}
```

The section is `logging.levels`, not `logging.level`.

| Event | Level | Structured fields |
|---|---|---|
| poll starting | TRACE | `listenerConfig` |
| records polled | TRACE (with topic/partition map) / DEBUG (count only) | `listenerConfig`, `topics`, `recordsCount` |
| records handled | INFO | `listenerConfig`, `recordsCount` |
| records handling failed | WARN | + `exceptionType`, `exceptionMessage` |
| record starting | DEBUG, or TRACE with payload | `listenerConfig`, `topic`, `partition`, `offset`; at TRACE also `headers`, `key`, `value` |
| record finished / failed | DEBUG / WARN | same, plus exception fields on failure |

---

## Masking

Record payloads are logged **only by the consumer and only at TRACE**: when the listener's logger is
at TRACE (and `telemetry.logging.enabled = true`), the "KafkaListener starting handling record..."
line is emitted at TRACE with three extra fields. At DEBUG the same line has no payload.

| Field | Rendered by | Masking |
|---|---|---|
| `headers` | `KafkaHeaderUtils.toMaskedString` — `name: value` pairs, one per line | a header whose name is in `telemetry.logging.maskHeaders` (case-insensitive, default `authorization`, `cookie`, `set-cookie`) is replaced by the `@Tag(KafkaConsumerTelemetry.class) MaskingStrategy`, which receives the raw `byte[]` value; the default strategy writes `***` |
| `key` / `value` | `DefaultKafkaConsumerBodyConverter.convertKey` / `convertValue` over the raw record bytes | if the key/value deserializer is a `JsonKafkaDeserializer` (an `@Json` parameter), the `@Tag(KafkaConsumerTelemetry.class) DataMasker` whose `format()` is `json` masks it; otherwise the bytes are written as UTF-8 text, unmasked |

**No `DataMasker` is registered for Kafka by default** — `KafkaListenerModule` collects
`@Tag(KafkaConsumerTelemetry.class) All<DataMasker>` and the collection is empty until you add one.
Without it a TRACE log prints JSON values verbatim. Register a format masker under the Kafka tag:

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

    @Tag(KafkaConsumerTelemetry.class)
    default MaskingStrategy kafkaHeaderMaskingStrategy() {
        return new MaskingFull("<hidden>");
    }
}
```

```kotlin
@Module
interface KafkaMaskingModule {

    @Tag(KafkaConsumerTelemetry::class)
    fun kafkaJsonDataMasker(): DataMasker = JsonDataMasker(
        MaskingPathRules.builder()
            .mask("password", MaskingFull())
            .mask("card.number", MaskingKeepLast())
            .build()
    )
}
```

A tagged `MaskingStrategy` component replaces the `@DefaultComponent` `***` strategy for Kafka
consumer headers only. Types: `io.koraframework.logging.common.masking.{MaskingStrategy,
MaskingPathRules, MaskingFull, MaskingKeepFirst, MaskingKeepLast}` and
`io.koraframework.logging.common.masking.raw.{DataMasker, JsonDataMasker}`;
`io.koraframework.kafka.common.consumer.telemetry.KafkaConsumerTelemetry` is the tag. The masking
model itself — path rules, fail-closed soft parsing, truncation — is documented once in
[kora-aop-logging masking](../../kora-aop-logging/references/logging-masking.md).

**Override points.** `DefaultKafkaConsumerBodyConverter` is a `@DefaultComponent`; subclass it and
register the subclass as a `@Component` to change how a body is chosen or rendered. Its
`protected` hooks are `selectKeyDataMasker(ConsumerRecord)`, `selectValueDataMasker(ConsumerRecord)`
and `convertBody(byte[], DataMasker)` — e.g. select an `xml` masker for a topic that carries XML:

```java
@Component
public final class XmlAwareBodyConverter extends DefaultKafkaConsumerBodyConverter {

    private final DataMasker xml;

    public XmlAwareBodyConverter(@Tag(KafkaConsumerTelemetry.class) All<DataMasker> maskers) {
        super(StreamSupport.stream(maskers.spliterator(), false).toList());
        this.xml = StreamSupport.stream(maskers.spliterator(), false)
            .filter(m -> XmlDataMasker.FORMAT.equals(m.format()))
            .findFirst().orElseThrow();
    }

    @Override
    protected @Nullable DataMasker selectValueDataMasker(ConsumerRecord<?, ?> record) {
        return record.topic().endsWith("-xml") ? xml : super.selectValueDataMasker(record);
    }
}
```

---

## Metrics

Three meters, registered on the injected `MeterRegistry`:

| Meter | Type | Scope |
|---|---|---|
| `messaging.process.duration` | Timer | one record |
| `messaging.process.batch.duration` | Timer | one poll |
| `messaging.kafka.consumer.lag` | Gauge | per partition — **assign mode only** |

Common tags on all three:

`messaging.system` (`kafka`), `messaging.client.id`, `messaging.consumer.group.name`,
`messaging.operation.name` (`process`; on the two timers),
`system.config` (the `@KafkaListener` path), `system.name.simple`, `system.name.canonical`, plus
everything in `telemetry.metrics.tags`.

Additional tags:

| Meter | Extra tags |
|---|---|
| `messaging.process.duration` | `error.type` (empty string on success), `messaging.destination.name`, `messaging.destination.partition.id` |
| `messaging.process.batch.duration` | `error.type` |
| `messaging.kafka.consumer.lag` | `messaging.destination.name`, `messaging.destination.partition.id` |

The lag gauge is emitted **only by the assign container** — `reportLag` is never called from the
subscribe container. For consumer-group lag, scrape it from the broker (`kafka_consumergroup_lag`
from a Kafka exporter) or from the driver metrics below.

`driverMetrics = true` binds Micrometer's `KafkaClientMetrics` to the underlying client, publishing
the whole `kafka.consumer.*` family (fetch rates, records-lag-max, coordinator stats). It is a lot of
series — enable it deliberately.

Meter names reach Prometheus through Micrometer's naming convention: dots become underscores and the
registry appends a unit suffix for timers. Confirm the exact exported names against your own
`/metrics` output rather than guessing, since the suffix depends on the registry configuration.

---

## Tracing

Two span kinds, both `SpanKind.CONSUMER`:

| Span | When | Parent |
|---|---|---|
| `poll` | one per poll | none (`setNoParent`), so each poll is a trace root |
| `process <topic>` | one per record | the W3C context extracted from the record's headers, plus a link to the poll span |

Span names follow the OpenTelemetry messaging convention `<operation> <destination>` since
2.0.0.RC2 (#972); RC1 named them `kafka.poll` and `<topic> process record`. The poll span ends with a
`messaging.poll.result` event.

`poll` attributes: `messaging.system`, `messaging.operation.name` = `poll`,
`messaging.operation.type` = `receive`, `messaging.client.id`,
`messaging.consumer.group.name`, `system.config`, `system.name.simple`, `system.name.canonical`,
plus `telemetry.tracing.attributes`.

Record span attributes: the same identity attributes with `messaging.operation.name` = `process` and
`messaging.operation.type` = `process`, plus `messaging.destination.name`,
`messaging.destination.partition.id`, `messaging.kafka.offset` and, when the key can be stringified,
`messaging.kafka.message.key`.

Context propagation is W3C `traceparent` read from the record headers, so a trace started by a Kora
publisher continues in the consumer with no code on your side.

The batch handler establishes the poll observation and the OpenTelemetry context around your method;
the single-record handler scopes a per-record observation and a forked MDC around each call. Nothing
is exposed to your method as a parameter — a telemetry-context parameter is a compile error.

---

## Replacing a telemetry component

`KafkaListenerModule` (pulled in by `KafkaModule`) declares the factory as a `@DefaultComponent`
with optional collaborators:

```java
@DefaultComponent
default KafkaConsumerTelemetryFactory defaultKafkaConsumerTelemetryFactory(
        @Nullable Tracer tracer,
        @Nullable MeterRegistry meterRegistry,
        @Nullable DefaultKafkaConsumerLoggerFactory loggerFactory,
        @Nullable DefaultKafkaConsumerMetricsFactory metricsFactory) {
    return new DefaultKafkaConsumerTelemetryFactory(tracer, meterRegistry, loggerFactory, metricsFactory);
}
```

There is **no `KafkaConsumerLoggerFactory` interface in 2.0** — the extension points are the concrete
`Default*Factory` classes and the `KafkaConsumerTelemetryFactory` interface. Three levels, from
narrow to broad:

**1. Custom logger** — subclass `DefaultKafkaConsumerLoggerFactory` and register it as a
`@Component`; the module picks it up through the `@Nullable` parameter. The factory and the logger
take the header `MaskingStrategy` and the `DefaultKafkaConsumerBodyConverter` in their constructors,
so inject and pass them on:

```java
@Component
public final class OrderConsumerLoggerFactory extends DefaultKafkaConsumerLoggerFactory {

    private final MaskingStrategy maskingStrategy;
    private final DefaultKafkaConsumerBodyConverter bodyConverter;
    private final AuditService audit;

    public OrderConsumerLoggerFactory(@Tag(KafkaConsumerTelemetry.class) MaskingStrategy maskingStrategy,
                                      DefaultKafkaConsumerBodyConverter bodyConverter,
                                      AuditService audit) {
        super(maskingStrategy, bodyConverter);
        this.maskingStrategy = maskingStrategy;
        this.bodyConverter = bodyConverter;
        this.audit = audit;
    }

    @Override
    public DefaultKafkaConsumerLogger create(DefaultKafkaConsumerTelemetry.TelemetryContext context) {
        var logger = LoggerFactory.getLogger("kafka.consumer.audit");
        return new DefaultKafkaConsumerLogger(logger, maskingStrategy, bodyConverter, context) {
            @Override
            public void logRecordEnd(ConsumerRecord<?, ?> record, @Nullable Throwable error) {
                super.logRecordEnd(record, error);
                audit.record(record.topic(), record.offset(), error);
            }
        };
    }
}
```

It is consulted **only when `telemetry.logging.enabled = true`**; otherwise the factory substitutes
`NoopKafkaConsumerLoggerFactory`. The same pattern works for
`DefaultKafkaConsumerMetricsFactory` (`create` returns a `DefaultKafkaConsumerMetrics` whose
`createMetricRecordDuration` / `createMetricRecordsDuration` / `createMetricLag` builders are
`protected` and overridable).

**2. Custom telemetry object** — subclass `DefaultKafkaConsumerTelemetryFactory` and override the
`protected build(...)` hook, registering it as a plain `@Component` so it wins over the
`@DefaultComponent`.

**3. Full replacement** — implement `KafkaConsumerTelemetryFactory` yourself:

```java
KafkaConsumerTelemetry get(String listenerConfig, String listenerCanonicalName,
                           Properties driverProperties, KafkaConsumerTelemetryConfig config);
```

`KafkaConsumerTelemetry` exposes `meterRegistry()`, `observePoll()` and
`reportLag(TopicPartition, long)`; `KafkaConsumerPollObservation` yields per-record
`KafkaConsumerRecordObservation`s. A `@Component` of this type replaces the default for **every**
listener in the application — there is no per-listener tag on this parameter.

Migrating from a 1.x custom telemetry listener: port the logging bits into a
`DefaultKafkaConsumerLoggerFactory` subclass, the metric bits into a
`DefaultKafkaConsumerMetricsFactory` subclass, and prefer configuration (`tags`, `attributes`, `slo`,
`driverMetrics`) wherever it covers the requirement.

---

## Pitfalls

| Symptom | Cause | Fix |
|---|---|---|
| No consumer logs at all, not even lifecycle | `telemetry.logging.enabled` is `false` by default | enable it on the listener |
| No `messaging.*` meters | `telemetry.metrics.enabled` is `false` by default | enable it |
| Enabled but still nothing | no `MeterRegistry` / `Tracer` in the graph | add `micrometer-module` / `opentelemetry-tracing` and an exporter |
| Lag gauge missing | subscribe mode never reports lag | use broker-side lag, or `driverMetrics = true` |
| Custom logger never used | not a `@Component`, or logging disabled | register it and enable logging |
| `KafkaConsumerLoggerFactory` does not resolve | 1.x interface, removed in 2.0 | subclass `DefaultKafkaConsumerLoggerFactory` |
| `DefaultKafkaConsumerLogger(logger, context)` does not compile | the constructor also takes `MaskingStrategy` and `DefaultKafkaConsumerBodyConverter` | inject both and pass them on |
| No `key` / `value` in record logs | logger at DEBUG, not TRACE | set the listener's logger to TRACE |
| JSON values logged unmasked at TRACE | no `@Tag(KafkaConsumerTelemetry.class) DataMasker` with format `json` | register one (`JsonDataMasker`) |
| A custom header still shows in clear | not in `telemetry.logging.maskHeaders` | add it; the list replaces the default, so keep `authorization` etc. |
| Telemetry parameter on a listener does not compile | no such parameter kind in 2.0 | drop it; observations are not injectable |
| Metric cardinality explosion | `driverMetrics = true`, or per-record tags | disable driver metrics; keep `tags` low-cardinality |
| Every poll is its own trace | the `poll` span is created with `setNoParent()` | expected; per-record spans still continue the producer's trace |

---

## Related references

- [Consumer configuration](kafka-consumer-reference.md)
- [Error handling](kafka-error-handling-reference.md)
- [Strategies](kafka-strategies-reference.md) — why lag is assign-only
- [kora-telemetry-metrics](../../kora-telemetry-metrics/SKILL.md) · [kora-telemetry-tracing](../../kora-telemetry-tracing/SKILL.md) · [kora-telemetry-logging](../../kora-telemetry-logging/SKILL.md)

**Source:** framework tag `2.0.0.RC2` —
[consumer telemetry](https://github.com/kora-projects/kora/tree/2.0.0.RC2/kafka/kafka/src/main/java/io/koraframework/kafka/common/consumer/telemetry) ·
[KafkaListenerModule](https://github.com/kora-projects/kora/blob/2.0.0.RC2/kafka/kafka/src/main/java/io/koraframework/kafka/common/consumer/KafkaListenerModule.java) ·
[TelemetryConfig](https://github.com/kora-projects/kora/blob/2.0.0.RC2/telemetry/telemetry-common/src/main/java/io/koraframework/telemetry/common/TelemetryConfig.java)
