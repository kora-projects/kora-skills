---
name: kora-telemetry-logging
description: "SLF4J + Logback logging for Kora 2.0 — LogbackModule from io.koraframework:logging-logback, KoraAsyncAppender, the text/pretty/json encoders (JsonRecordEncoder from logging-logback-json) chosen by KoraLogbackConfigurator and kora.logging.encoder, config-driven logging.levels, StructuredArgument, the ScopedValue-based Kora MDC, and @Mask masking. Use when wiring logback.xml or JSON log output, setting per-logger levels from application.conf/yaml, turning on per-component telemetry.logging.enabled, or porting a Kora 1.x logging setup."
license: Apache-2.0
metadata:
  kora-version: "2.x"
---

# Kora Telemetry Logging

> **Kora sub-skill — obey the [kora-v2 meta rules](../../SKILL.md) on every task:** **R0** ground the workspace on Kora 2.0 refs before starting (framework source at tag `2.0.0.RC2` + `kora-examples` at `migration/2.0` + Kora 2.0 docs at koraframework.io/v2, which trail the source; 1.x `kora-docs` pages are never an authority) · **R1** read this sub-skill before writing code · **R2** Kora 2.0 APIs only — no Spring/Micronaut/Quarkus, no Kora 1.x APIs, no invented annotations or config keys · **R3** journal any incorrect Kora usage. Add comments/Javadoc only if asked.

| | |
|---|---|
| **Artifacts** | `io.koraframework:logging-logback` (pulls `logging-common`, `json-common`, `core:common`); `io.koraframework:logging-logback-json` for JSON output (pulls `logging-logback`); BOM `io.koraframework:kora-bom` |
| **Modules** | `LogbackModule` — `io.koraframework.logging.logback`; it extends `LoggingModule` — `io.koraframework.logging.common` |
| **Logback classes** | `io.koraframework.logging.logback` — `KoraLogbackConfigurator`, `LogbackEncoderFactory`, `KoraAsyncAppender`, `KoraLoggingEvent`, `KoraMdcConverter`, `KoraLoggingMarkerConverter`; `…logback.text.ConsoleTextRecordEncoder`; `…logback.json.JsonRecordEncoder` |
| **Structured API** | `io.koraframework.logging.common.MDC`, `…logging.common.arg.{StructuredArgument, StructuredArgumentWriter, StructuredArgumentMapper}`, `…logging.common.masking.{MaskingRules, MaskingStrategy}`, `@…logging.common.annotation.Mask` |
| **Config** | `logging.levels` (`LoggingConfig.levels()` → `Map<String,String>`); per component `<path>.telemetry.logging.enabled` |
| **Third party** | Logback `1.6.5`, SLF4J `2.0.20`, Jackson `3.2.3` under `tools.jackson.core` |

`@Log` and `@Mdc` are **not** in this skill — they are the declarative aspects, covered by
[`kora-aop-logging`](../kora-aop-logging/SKILL.md). This skill owns the logging *backend*: module
wiring, `logback.xml`, log levels, structured records, MDC values, and component telemetry logging.

---

## The one thing that trips everyone: there are two independent switches

A Kora component writes a telemetry log record only when **both** are satisfied. They are
unrelated keys with different defaults, and each fails silently on its own.

| # | Switch | Where | Default | What it controls |
|---|---|---|---|---|
| 1 | `<path>.telemetry.logging.enabled` | component config section | **`false`** (`TelemetryConfig.LoggingConfig.enabled()`) | Whether the component builds a real logger at all. When `false` it gets a Noop logger and emits nothing at any level. |
| 2 | `logging.levels."<logger name>"` | `logging` config section | root `INFO`, everything else inherits | The SLF4J level of the logger the component writes to. Every component logger guards itself with `isDebugEnabled()` / `isInfoEnabled()` / `isTraceEnabled()`. |

```hocon
jdbc {
  poolName = "kora"
  telemetry.logging.enabled = true                     # switch 1 — without it: nothing, ever
}

logging.levels {
  "io.koraframework.database.kora.query" = "DEBUG"     # switch 2 — DB query records are DEBUG-only
}
```

The database logger name is built as `"io.koraframework.database." + poolName + ".query"`, so the
`kora` segment above is this pool's `poolName`, not a fixed string.

`jdbc.telemetry.logging.enabled = true` alone produces **no output**: `DefaultDatabaseLogger`
returns early unless the logger is at `DEBUG`. Raising the level alone produces no output either,
because the component holds a `NOPLogger`. Say which switch you mean whenever you answer a
"my logs are missing" question — see
[component-telemetry-reference.md](references/component-telemetry-reference.md) for the full
logger-name table and each component's config path.

`telemetry.tracing.enabled` defaults to `true`, `telemetry.metrics.enabled` to `false` — do not
generalise from one to the others.

---

## Renamed / changed from Kora 1.x

| Kora 1.x | Kora 2.0 |
|---|---|
| `ru.tinkoff.kora:logging-logback` / `logging-common` | `io.koraframework:logging-logback` / `logging-common` |
| `ru.tinkoff.kora.logging.logback.*` | `io.koraframework.logging.logback.*` (`LogbackModule`, `KoraAsyncAppender`); the text encoder is `io.koraframework.logging.logback.text.ConsoleTextRecordEncoder` |
| `ru.tinkoff.kora.logging.common.MDC` backed by Kora `Context` | `io.koraframework.logging.common.MDC` backed by `ScopedValue<MDC>` — **`Context` no longer exists anywhere in the framework** |
| Jackson 2 generator (`writeStringField`, `writeNumberField`) | Jackson 3 `tools.jackson.core.JsonGenerator` — **`writeStringProperty`, `writeNumberProperty`, `writeName`** |
| `ru.tinkoff.kora:kora-parent` BOM | `io.koraframework:kora-bom` |
| `db.telemetry.logging.enabled` | `jdbc.telemetry.logging.enabled` (the JDBC config section was renamed `db` → `jdbc`) |
| `META-INF/native-image/ru.tinkoff.kora.<x>/logback/` | `META-INF/native-image/io.koraframework.<x>/logback/` — rename the directory **and** the `io.koraframework.logging.logback.*` entries inside |

`logging.levels` kept its name and shape across the rename — `LoggingConfig` in 2.0 still exposes
`Map<String,String> levels()`, and `LoggingModule` still reads the `logging` section. The key is
**`levels`, plural — never `logging.level`**. A singular key is not a recognised HOCON/YAML key,
is ignored without a warning, and leaves every logger at its default level.

---

## Quick start

### 1. Dependencies

Put `koraVersion=2.0.0.RC2` in `gradle.properties`.

```groovy
repositories { mavenCentral() }

configurations {
    koraBom
    annotationProcessor.extendsFrom(koraBom)
    implementation.extendsFrom(koraBom)
}

dependencies {
    koraBom platform("io.koraframework:kora-bom:$koraVersion")

    annotationProcessor "io.koraframework:annotation-processors"   // Kotlin: ksp "io.koraframework:symbol-processors"

    implementation "io.koraframework:logging-logback"   // Logback backend; pulls logging-common
    // JSON lines instead of text: implementation "io.koraframework:logging-logback-json"
    implementation "io.koraframework:config-hocon"      // MANDATORY — LoggingModule reads the `logging` config section
}
```

`logging-logback` declares `api project(':logging:logging-common')`, and `logging-common` declares
`api project(':json:json-common')` and `api project(':core:common')`. So `JsonWriter`, the
structured-argument API and the OpenTelemetry API that `KoraAsyncAppender` needs all arrive
transitively — no extra dependency. Never pin a version on an individual `io.koraframework:*`
artifact; the BOM does it.

### 2. Application graph

`LogbackModule extends LoggingModule`, and `LoggingModule.loggingConfig(Config, ConfigValueMapper<LoggingConfig>)`
reads `config.get("logging")` — so a config module (`HoconConfigModule` or `YamlConfigModule`) must
be in the graph too, or the graph will not build.

```java
import io.koraframework.application.graph.KoraApplication;
import io.koraframework.common.annotation.KoraApp;
import io.koraframework.config.hocon.HoconConfigModule;
import io.koraframework.logging.logback.LogbackModule;

@KoraApp
public interface Application extends LogbackModule, HoconConfigModule {
    static void main(String[] args) {
        KoraApplication.run(ApplicationGraph::graph);
    }
}
```

`LogbackModule` contributes one thing of its own: a `LoggingLevelApplier` that drives the Logback
`LoggerContext`. `LoggingModule` contributes `LoggingConfig`, an `ILoggerFactory`, the three
built-in `MaskingStrategy` components, the structured-argument mappers, and a `@Root`
`LoggingLevelRefresher` that applies `logging.levels` during graph initialization.

### 3. Output format: no `logback.xml`, or your own

A `logback.xml` is **optional**. `KoraLogbackConfigurator` (a Logback `Configurator` registered by
`logging-logback`) applies a configuration file when one exists; otherwise it installs
`ConsoleAppender` → `KoraAsyncAppender` on the root logger with one encoder picked from the
`LogbackEncoderFactory` implementations on the classpath:

| Name | Encoder | Picked automatically when |
|---|---|---|
| `text` | `ConsoleTextRecordEncoder` | only `logging-logback` is present |
| `json` | `JsonRecordEncoder` | `logging-logback-json` is present (priority 100 > 0) |
| `pretty` | coloured `ConsoleTextRecordEncoder` | running in a Gradle test worker (priority 1000 there, never elsewhere) |

Force one with the **JVM system property `kora.logging.encoder`** or the **environment variable
`KORA_LOGGING_ENCODER`** (system property is read first); `none` leaves Logback's defaults. It is
not an `application.conf` key — Logback starts before the config exists. Details:
[json-logging-reference.md](references/json-logging-reference.md).

When you keep a `logback.xml`, it wins, so name the encoder yourself — Kora's text encoder inside a
`ConsoleAppender`, wrapped by `KoraAsyncAppender`:

```xml
<configuration debug="false">
    <statusListener class="ch.qos.logback.core.status.NopStatusListener"/>

    <appender name="STDOUT" class="ch.qos.logback.core.ConsoleAppender">
        <encoder class="io.koraframework.logging.logback.text.ConsoleTextRecordEncoder"/>
    </appender>

    <appender name="ASYNC" class="io.koraframework.logging.logback.KoraAsyncAppender">
        <appender-ref ref="STDOUT"/>
    </appender>

    <root level="INFO">
        <appender-ref ref="ASYNC"/>
    </root>
    <!-- Logger levels are configured in application.conf -->
</configuration>
```

`ConsoleTextRecordEncoder` (package `io.koraframework.logging.logback.text`) and
`JsonRecordEncoder` (`io.koraframework.logging.logback.json`) are what render `traceId`/`spanId`,
Kora MDC entries and structured arguments; a plain `<pattern>` encoder drops all of them. For JSON,
swap the encoder for `io.koraframework.logging.logback.json.JsonRecordEncoder`
(`assets/logback.json.xml.template`).

### 4. Levels come from the config, not from `logback.xml`

`LoggingLevelRefresher.init()` runs during graph initialization and calls
`LoggingLevelApplier.reset()` **first**: the Logback root logger is forced to `INFO` and every
other logger's level is set to `null` (inherit). Only then are the `logging.levels` entries
applied. Any `<logger name="…" level="…"/>` element and the `<root level="…">` value in
`logback.xml` are therefore discarded the moment the graph starts.

```hocon
logging.levels {
  "ROOT" = "WARN"
  "io.koraframework" = "INFO"
  "com.example" = "DEBUG"
}
```

```yaml
logging:
  levels:
    ROOT: "WARN"
    io.koraframework: "INFO"
    com.example: "DEBUG"
```

### 5. Log

```java
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

private static final Logger log = LoggerFactory.getLogger(UserService.class);

log.info("Created user with id={}", generatedId);   // parameterized, never concatenated
```

---

## What's in `references/` and `assets/`

| Reference | Purpose |
|-----------|---------|
| [logback-config-reference.md](references/logback-config-reference.md) | Module wiring, `logback.xml` patterns, the level-reset rule, native-image logback metadata, troubleshooting |
| [component-telemetry-reference.md](references/component-telemetry-reference.md) | `telemetry.logging.enabled` per component, the logger-name table, level→detail ladder, masking of headers/queries/bodies |
| [structured-logging-reference.md](references/structured-logging-reference.md) | `StructuredArgument` arg/marker/value, the Jackson 3 generator API, `StructuredArgumentMapper`, `@Mask` / `MaskingRules` |
| [mdc-context-reference.md](references/mdc-context-reference.md) | Kora `MDC` over `ScopedValue`, where a scope is bound, SLF4J `MDC`, seeding MDC from an HTTP interceptor |
| [json-logging-reference.md](references/json-logging-reference.md) | `logging-logback-json`, `JsonRecordEncoder`, encoder selection by `KoraLogbackConfigurator` / `kora.logging.encoder`, the JSON record shape, `<maskField>`, custom writers |
| [async-logging-reference.md](references/async-logging-reference.md) | `KoraAsyncAppender` internals, its defaults (`queueSize` 512, `neverBlock` true) and `kora.logging.config.*` properties, shutdown, troubleshooting |

| Asset | Purpose |
|-------|---------|
| `Application.logging.java.template`, `Application.logging.kt.template` | `@KoraApp` with `LogbackModule` + `HoconConfigModule` |
| `build.gradle.logging.template` | BOM, processor, `logging-logback` + `config-hocon` |
| `logback.xml.template` | Production text output: `ConsoleTextRecordEncoder` + `KoraAsyncAppender` |
| `logback.json.xml.template` | Production JSON output: `JsonRecordEncoder` with `<maskField>` + `KoraAsyncAppender` |
| `logback.dev.xml.template` | Local development, colourised pattern encoder |
| `logback-test.xml.template` | `src/test/resources` variant used by the example apps |
| `application.logging.conf.template` | `logging.levels` + per-component `telemetry.logging.enabled` |
| `LoggingInterceptor.java.template` | `HttpServerInterceptor` that seeds Kora MDC from request headers |
| `LoggingService.java.template` | `StructuredArgument` / `MDC` / `@Mask` usage in a `@Component` |

---

## Core patterns

### Structured arguments

`io.koraframework.logging.common.arg.StructuredArgument` attaches machine-readable JSON to a
record, as a **parameter**, a **marker** (metadata only), or a bare **value** for SLF4J key/value
pairs. In all three forms the JSON is appended on its own indented line as `name={…}`; the
parameter form additionally consumes a `{}` slot, where SLF4J prints the argument's `toString()`
(a bare record dump, not the JSON) — so keep the message a constant and prefer the marker or
`addKeyValue` form. Typed overloads exist for `String`, `Integer`, `Long`, `Boolean` and
`Map<String,String>`; anything else takes a writer lambda over the Jackson 3
`tools.jackson.core.JsonGenerator`.

```java
import io.koraframework.logging.common.arg.StructuredArgument;

log.info("Request {} processed", StructuredArgument.arg("requestId", requestId));

log.info(StructuredArgument.marker("userId", userId), "User action performed");

log.atInfo()
   .addKeyValue("user", StructuredArgument.value(gen -> {
       gen.writeStartObject();
       gen.writeStringProperty("id", user.id());       // Jackson 3 name — NOT writeStringField
       gen.writeStringProperty("email", user.email());
       gen.writeEndObject();
   }))
   .log("User created");
```

See [structured-logging-reference.md](references/structured-logging-reference.md).

### Kora MDC

`io.koraframework.logging.common.MDC` holds structured (JSON-typed) values and is published
through `public static final ScopedValue<MDC> VALUE`. Kora binds a fresh `MDC` at the entry of
every request, message or job — the Undertow request handler, the gRPC transport filter, each
Kafka consumer batch/record, each scheduled job, each JMS message. Inside such a scope
`MDC.put(...)` works; **outside one — graph init, a shutdown hook, a plain unit test —
`MDC.get()` throws** because the `ScopedValue` is unbound.

```java
import io.koraframework.logging.common.MDC;

MDC.put("orderId", orderId);        // String / Integer / Long / Boolean / StructuredArgumentWriter
MDC.put("attempt", attempt);
log.info("Processing order");       // both keys attached to the record
```

`KoraAsyncAppender` snapshots the bound MDC into the queued event, so values survive the hop to
the appender thread; Logback's stock `AsyncAppender` does not. The string-only `org.slf4j.MDC`
also works (Kora speaks SLF4J) and is what a `%X{}` pattern reads. `KoraMdcConverter`, the pattern
converter for Kora MDC, renders nothing when no MDC scope is bound instead of failing the line. See
[mdc-context-reference.md](references/mdc-context-reference.md).

### Masking

`@io.koraframework.logging.common.annotation.Mask` on a record/class field, and on the type
itself, drives a `MaskingRules<T>` component (KSP generates `$<Type>_MaskingRulesModule`; in Java
declare the rules component yourself). `MaskedStructuredArgumentMapper` then replaces matched values through
a `MaskingStrategy` — `MaskingFull` (default, `***`), `MaskingKeepFirst`, `MaskingKeepLast`, or
your own `@Component`. Rules match a bare field name globally (`password`), a dotted path from the
logged root (`user.password`), or a path with a `*` wildcard segment (`users.*.password`).

Other masking layers — `DataMasker` for raw HTTP/Kafka payloads, tagged `MaskingStrategy` for
header/query/metadata values, and `JsonRecordEncoder`'s `<maskField>` on the finished JSON line —
and how they relate are documented once, in
[logging-masking.md](../kora-aop-logging/references/logging-masking.md).

---

## Common pitfalls

| Problem | Cause / fix |
|---|---|
| Component telemetry logs missing | Two switches — set `<path>.telemetry.logging.enabled = true` **and** the logger's level in `logging.levels` |
| `logging.level` has no effect | The key is **`logging.levels`** (plural). The singular form is an unknown key, silently ignored |
| DB query logs missing with `jdbc.telemetry.logging.enabled = true` | Query records are `DEBUG`; add `"io.koraframework.database.<poolName>.query" = "DEBUG"` to `logging.levels` |
| `<logger>` / `<root>` levels in `logback.xml` are ignored | `LoggingLevelRefresher.init()` resets every logger at graph start. Configure levels in `logging.levels` |
| `traceId`, MDC or structured fields missing from the line | The appender uses a plain `<pattern>` encoder — switch to `ConsoleTextRecordEncoder` or `JsonRecordEncoder` behind `KoraAsyncAppender` |
| Empty console after pointing `logback.xml` at `io.koraframework.logging.logback.ConsoleTextRecordEncoder` | The class is `io.koraframework.logging.logback.text.ConsoleTextRecordEncoder`; Logback cannot build the encoder and a `NopStatusListener` hides the error |
| Added `logging-logback-json`, output still text | A `logback.xml` / `logback-test.xml` wins over encoder selection — declare `JsonRecordEncoder` in it or remove it |
| `kora.logging.encoder` in `application.conf` ignored | Read before the config exists: `-Dkora.logging.encoder=json` or `KORA_LOGGING_ENCODER=json` |
| Coloured text in tests even with `logging-logback-json` | `pretty` wins inside a Gradle test worker; set the `kora.logging.encoder` system property on the test task to override |
| Log records lost under a burst | `KoraAsyncAppender` drops `TRACE`/`DEBUG`/`INFO` once free slots fall below `discardingThreshold` (default `queueSize / 5`) and drops everything when full (`neverBlock = true`, 512-event queue) — raise `queueSize`, set `discardingThreshold` to `0`, or `neverBlock` to `false` |
| Structured MDC empty behind an async appender | Use `io.koraframework.logging.logback.KoraAsyncAppender`, not Logback `AsyncAppender` |
| `MDC.get()` throws `NoSuchElementException` | Called outside a bound request/message/job scope. Guard with `MDC.VALUE.isBound()` |
| `writeStringField` / `writeNumberField` does not compile | Jackson 3: `writeStringProperty` / `writeNumberProperty`; the generator is `tools.jackson.core.JsonGenerator` |
| Ported 1.x MDC helper built on Kora `Context` does not compile | `Context` was removed from the whole framework. Use `MDC` directly inside the framework-bound scope |
| Graph fails with a missing `Config` / `ConfigValueMapper<LoggingConfig>` | `LoggingModule` needs a config module — add `HoconConfigModule` or `YamlConfigModule` |
| Native image logs are empty or ignore `logback.xml` | Metadata directory still on the old group, or a file named `reflection-config.json` (never read) — see [logback-config-reference.md](references/logback-config-reference.md) |

---

## Anti-patterns

- Do not concatenate: `log.info("user " + id)` — use `log.info("user {}", id)`.
- Do not put per-package levels in `logback.xml`; they are wiped at graph start.
- Do not log secrets or PII. Use `@Mask` for structured values, `maskHeaders` / `maskQueries` plus
  the transport's tagged `MaskingStrategy` and `DataMasker` for component telemetry
  ([logging-masking.md](../kora-aop-logging/references/logging-masking.md)).
- Do not write your own JSON encoder: `io.koraframework:logging-logback-json` ships `JsonRecordEncoder`.
- Do not pin versions on `io.koraframework:*` artifacts — `io.koraframework:kora-bom` does it.
- Do not carry a Kora 1.x `Context`-based MDC helper into 2.0; there is nothing to port it onto.
