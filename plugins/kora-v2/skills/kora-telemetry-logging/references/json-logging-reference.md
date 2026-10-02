# JSON Logging Reference

Everything here is verified against `logging/logging-logback` and `logging/logging-logback-json`
in the Kora 2.0 framework source.

## Contents

- [Which artifact ships what](#which-artifact-ships-what)
- [Zero-config: pick an encoder without a logback.xml](#zero-config-pick-an-encoder-without-a-logbackxml)
- [Declaring JsonRecordEncoder in logback.xml](#declaring-jsonrecordencoder-in-logbackxml)
- [What a JSON record looks like](#what-a-json-record-looks-like)
- [Masking fields in the JSON record](#masking-fields-in-the-json-record)
- [Custom writers](#custom-writers)
- [Third-party JSON encoders](#third-party-json-encoders)
- [Pitfalls](#pitfalls)

## Which artifact ships what

| Artifact | Package | Contents |
|---|---|---|
| `io.koraframework:logging-logback` | `io.koraframework.logging.logback` | `KoraLogbackConfigurator` (the Logback `Configurator` SPI), `LogbackEncoderFactory` (the encoder SPI), `KoraLogbackProperties`, `KoraAsyncAppender`, `KoraLoggingEvent`, `KoraMdcConverter`, `KoraLoggingMarkerConverter`, `LogbackModule` |
| | `…logging.logback.text` | `ConsoleTextRecordEncoder`, `ConsoleTextEncoderFactory` (name `text`), `ColorConsoleTextEncoderFactory` (name `pretty`) |
| | `…logging.logback.text.writer` | `LoggingEventTextWriter` and its `Default*TextWriter` parts |
| `io.koraframework:logging-logback-json` | `io.koraframework.logging.logback.json` | `JsonRecordEncoder`, `JsonEncoderFactory` (name `json`), `LoggingEventJsonMasker`, `FieldLoggingEventJsonMasker`, `JsonFieldConstants` |
| | `…logging.logback.json.writer` | `LoggingEventJsonWriter` and its `Default*JsonWriter*` parts |

`logging-logback-json` declares `api project(':logging:logging-logback')`, so it replaces
`logging-logback` in the build rather than sitting next to it. Both are managed by
`io.koraframework:kora-bom` — no version on the artifact:

```groovy
implementation "io.koraframework:logging-logback-json"   // brings logging-logback, logging-common, json-common
```

```kotlin
implementation("io.koraframework:logging-logback-json")
```

The `@KoraApp` still extends `LogbackModule`; the JSON module contributes no graph component, only
the encoder and its `ServiceLoader` registration.

## Zero-config: pick an encoder without a `logback.xml`

`logging-logback` registers `KoraLogbackConfigurator` in
`META-INF/services/ch.qos.logback.classic.spi.Configurator`. When Logback starts it does this, in
order:

1. Runs Logback's own `DefaultJoranConfigurator`. **If a configuration file is found**
   (`logback-test.xml`, `logback.xml`, or `-Dlogback.configurationFile`), that file is applied as
   usual and Kora's encoder selection is skipped entirely.
2. Otherwise reads `kora.logging.encoder`. The value `none` hands configuration back to Logback's
   own defaults.
3. Otherwise loads every `LogbackEncoderFactory` through `ServiceLoader` and picks one:
   the one whose `name()` equals the property (case-insensitive), or — when the property is not
   set — the one with the highest `priority()`.
4. Attaches that encoder to a `ConsoleAppender` named `KORA_CONSOLE`, wraps it in a
   `KoraAsyncAppender` named `KORA_ASYNC`, and puts it on the root logger with the level from
   `kora.logging.levels.root` (default `INFO`).

The factories on the classpath:

| `name()` | Factory | Encoder | `priority()` |
|---|---|---|---|
| `text` | `ConsoleTextEncoderFactory` (`logging-logback`) | `ConsoleTextRecordEncoder` | `0` |
| `pretty` | `ColorConsoleTextEncoderFactory` (`logging-logback`) | `ConsoleTextRecordEncoder(true)` — ANSI-coloured timestamp and level | `1000` inside a Gradle test worker (`org.gradle.test.worker` system property set), `Integer.MIN_VALUE` everywhere else |
| `json` | `JsonEncoderFactory` (`logging-logback-json`) | `JsonRecordEncoder` | `100` |

So, with no `logback.xml` and no property:

| Classpath | Production run | Gradle test run |
|---|---|---|
| `logging-logback` only | `text` | `pretty` |
| `logging-logback-json` | `json` | `pretty` |

### How `kora.logging.encoder` is read

Logback configures itself before the Kora graph and its `application.conf` exist, so this is **not
a config-file key**. `KoraLogbackProperties.get(...)` reads a **JVM system property first**, then an
**environment variable** whose name is the property upper-cased with `.` and `-` turned into `_`:

| System property | Environment variable | Default | Effect |
|---|---|---|---|
| `kora.logging.encoder` | `KORA_LOGGING_ENCODER` | highest `priority()` | `text`, `pretty`, `json`, or `none` |
| `kora.logging.levels.root` | `KORA_LOGGING_LEVELS_ROOT` | `INFO` | Root level until the graph starts |
| `kora.logging.config.jul-bridge` | `KORA_LOGGING_CONFIG_JUL_BRIDGE` | `true` | Route `java.util.logging` into Logback |
| `kora.logging.config.timestamp-epoch-millis` | `KORA_LOGGING_CONFIG_TIMESTAMP_EPOCH_MILLIS` | `false` | Timestamp as epoch milliseconds instead of a formatted date |

```shell
KORA_LOGGING_ENCODER=json java -jar app.jar        # container env
java -Dkora.logging.encoder=text -jar app.jar      # force text even with logging-logback-json present
```

```groovy
test {
    systemProperty "kora.logging.encoder", "json"  // a test that asserts on JSON output
}
```

An unknown name (`kora.logging.encoder=jsonn`) is reported as a Logback error status listing the
available names, and Kora installs nothing — Logback's own default configuration applies.

`kora.logging.levels.root` only covers the window before the graph starts: `LoggingLevelRefresher`
still resets the root to `INFO` at graph init and then applies `logging.levels` (see
[logback-config-reference.md](logback-config-reference.md)).

## Declaring `JsonRecordEncoder` in `logback.xml`

A configuration file always wins over the zero-config path, so a project that keeps a
`logback.xml` must name the encoder itself. Keep the `KoraAsyncAppender` wrapper — it is what makes
`traceId`/`spanId` and the Kora MDC available to the encoder.

```xml
<configuration debug="false">
    <statusListener class="ch.qos.logback.core.status.NopStatusListener"/>

    <appender name="STDOUT" class="ch.qos.logback.core.ConsoleAppender">
        <encoder class="io.koraframework.logging.logback.json.JsonRecordEncoder">
            <maskField>password</maskField>
            <maskField>token</maskField>
        </encoder>
    </appender>

    <appender name="ASYNC" class="io.koraframework.logging.logback.KoraAsyncAppender">
        <appender-ref ref="STDOUT"/>
    </appender>

    <root level="INFO">
        <appender-ref ref="ASYNC"/>
    </root>
</configuration>
```

`JsonRecordEncoder` accepts three nested elements:

| Element | Setter | Effect |
|---|---|---|
| `<writer class="…"/>` | `addWriter(LoggingEventJsonWriter)` | The first one **replaces** the default writers; list every part you want, in order |
| `<maskField>name</maskField>` | `addMaskField(String)` | Masks every JSON field with that name, see below |
| `<masker class="…"/>` | `setMasker(LoggingEventJsonMasker)` | A custom masker; when both are set, `<maskField>` is ignored with a warning |

## What a JSON record looks like

One JSON object per line, UTF-8, `\n`-terminated. The default writers, in order:

| Writer | Fields |
|---|---|
| `DefaultLoggingEventJsonWriter` | `@timestamp`, `level`, `thread`, `logger`, `message` |
| `DefaultTraceJsonWriterLogging` | `traceId`, `spanId` — only on a `KoraLoggingEvent` with a valid span context |
| `DefaultMdcJsonWriterLogging` | `mdc` — Kora MDC values (JSON-typed) merged with the SLF4J MDC (strings); the Kora value wins on a key conflict; omitted when both are empty |
| `DefaultStructuredJsonWriterLogging` | `data` — every `StructuredArgument` named `data` (the `@Log` aspect's marker); several are merged into one object. `args` — every other `StructuredArgument` marker/argument plus every SLF4J key/value pair |
| `DefaultExceptionJsonWriterLogging` | `exception` — `class`, `message`, `stacktrace`, plus `data` when a structured argument named `exception` or `throwable` is present |

```json
{"@timestamp":"2026-09-30T09:14:02.311Z","level":"INFO","thread":"kora-undertow-1","logger":"io.koraframework.http.server.common.HttpServer.response","message":"HttpServer responded","traceId":"4f0e…","spanId":"9a1c…","mdc":{"orderId":"ORD-1"},"args":{"httpResponse":{"serverName":"kora-undertow","statusCode":200,"processingTime":12}}}
```

- `@timestamp` is ISO-8601 in **UTC**. With `kora.logging.config.timestamp-epoch-millis=true` it is a
  JSON number of epoch milliseconds instead; the same property switches the text encoder to raw
  epoch millis.
- SLF4J key/value values keep their JSON type (`String`, numbers, `Boolean`, `null`,
  `StructuredArgumentWriter`); anything else is written with `toString()`.
- If a writer throws, the record is still written: a fallback object with `@timestamp`, `level`,
  `logger`, `message` and the failure as `exception`.

## Masking fields in the JSON record

`<maskField>` builds a `FieldLoggingEventJsonMasker`: a field whose **name** matches
(case-insensitive) is replaced by `"***"` wherever it appears in the record — inside `mdc`, `args`,
`data` or `exception.data`. If the matched value is an object or array, the whole value is replaced.

It is a last line of defence, not the primary masking tool:

- It only sees JSON **field names** the writers emit. A secret inside a string value — the
  `message` text, an HTTP `headers` or `body` string in component telemetry — is not reached.
- It exists only in `JsonRecordEncoder`; the text encoders have no equivalent.

For a custom rule, implement `io.koraframework.logging.logback.json.LoggingEventJsonMasker`
(`boolean shouldMask(String path, String fieldName)`, optional `writeMasked(...)`, default
`"***"`). `path` is the dotted field path from the record root, e.g. `args.user.password`.

Masking that should happen *before* a value becomes a log string — `@Mask` on logged types, and the
`DataMasker` body maskers used by HTTP and Kafka telemetry — is documented in the canonical
[logging-masking.md](../../kora-aop-logging/references/logging-masking.md).

## Custom writers

`LoggingEventJsonWriter` is `void write(JsonGenerator gen, ILoggingEvent event) throws IOException`
on the Jackson 3 `tools.jackson.core.JsonGenerator`, called inside the record object. Check for
`KoraLoggingEvent` to read `koraMdc()` or `span()`.

```java
package com.example.logging;

import ch.qos.logback.classic.spi.ILoggingEvent;
import io.koraframework.logging.logback.json.writer.LoggingEventJsonWriter;
import tools.jackson.core.JsonGenerator;

public final class ServiceNameJsonWriter implements LoggingEventJsonWriter {
    @Override
    public void write(JsonGenerator gen, ILoggingEvent event) {
        gen.writeStringProperty("service", "orders");
    }
}
```

```xml
<encoder class="io.koraframework.logging.logback.json.JsonRecordEncoder">
    <writer class="io.koraframework.logging.logback.json.writer.DefaultLoggingEventJsonWriter"/>
    <writer class="io.koraframework.logging.logback.json.writer.DefaultTraceJsonWriterLogging"/>
    <writer class="io.koraframework.logging.logback.json.writer.DefaultMdcJsonWriterLogging"/>
    <writer class="io.koraframework.logging.logback.json.writer.DefaultStructuredJsonWriterLogging"/>
    <writer class="io.koraframework.logging.logback.json.writer.DefaultExceptionJsonWriterLogging"/>
    <writer class="com.example.logging.ServiceNameJsonWriter"/>
</encoder>
```

`ConsoleTextRecordEncoder` is composed the same way from `LoggingEventTextWriter`
(`void write(StringBuilder out, ILoggingEvent event)`) parts via `<writer class="…"/>`.

Logback instantiates writers reflectively: in a GraalVM native image, register your writer classes
in the application's `reflect-config.json`.

## Third-party JSON encoders

Kora ships a JSON encoder; prefer it. A third-party `Encoder<ILoggingEvent>` still plugs into a
`ConsoleAppender` wrapped by `KoraAsyncAppender`, but:

- none appears in the Kora 2.0 source or tests; Kora pins Logback `1.6.5` and SLF4J `2.0.20`, so
  check the encoder against those versions on a real run;
- an encoder that does not know `KoraLoggingEvent` emits neither `koraMdc()` nor `span()` — Kora
  MDC values and `traceId`/`spanId` go missing.

## Pitfalls

| Symptom | Cause / fix |
|---|---|
| `logging-logback-json` added, output is still text | A `logback.xml` / `logback-test.xml` is on the classpath and wins. Declare `JsonRecordEncoder` in it, or delete it to use the zero-config path |
| JSON in production, coloured text in tests | Expected: `pretty` has priority `1000` inside a Gradle test worker. Set `kora.logging.encoder=json` on the test task to assert on JSON |
| `kora.logging.encoder` in `application.conf` does nothing | It is read before the config exists — system property or `KORA_LOGGING_ENCODER` only |
| No logs and a Logback error listing encoder names | Misspelled `kora.logging.encoder` value |
| `traceId` / `mdc` missing from JSON | The encoder is not behind `KoraAsyncAppender` (hand-written `logback.xml`) |
| A secret in an HTTP body or header string is not masked by `<maskField>` | `<maskField>` matches JSON field names only; mask at the source — see [logging-masking.md](../../kora-aop-logging/references/logging-masking.md) |
| No console output; with `debug="true"` Logback reports `ClassNotFoundException` for `io.koraframework.logging.logback.ConsoleTextRecordEncoder` | The text encoder lives in the `text` sub-package: `io.koraframework.logging.logback.text.ConsoleTextRecordEncoder` |
