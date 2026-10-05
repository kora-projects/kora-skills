# Logback Configuration Reference

Everything in this file is verified against the Kora 2.0 framework source (`logging/logging-logback`,
`logging/logging-common`, `logging/logging-logback-json`). Logback is `1.6.5`, SLF4J `2.0.20`.

## Contents

- [What `logging-logback` contains](#what-logging-logback-contains)
- [Module setup](#module-setup)
- [No logback.xml: KoraLogbackConfigurator](#no-logbackxml-koralogbackconfigurator)
- [logback.xml](#logbackxml)
- [Log levels are owned by the config, not by logback.xml](#log-levels-are-owned-by-the-config-not-by-logbackxml)
- [Pattern layouts and the Kora converters](#pattern-layouts-and-the-kora-converters)
- [Native image metadata](#native-image-metadata)
- [Troubleshooting](#troubleshooting)

## What `logging-logback` contains

The public surface of `io.koraframework:logging-logback` — do not assume a class exists because a
1.x setup had one.

| Type | Package | Purpose |
|---|---|---|
| `LogbackModule` | `io.koraframework.logging.logback` | `interface … extends LoggingModule`; supplies the `@DefaultComponent` `LoggingLevelApplier` that drives the Logback `LoggerContext` |
| `KoraLogbackConfigurator` | `io.koraframework.logging.logback` | Logback `Configurator` registered through `ServiceLoader`; installs a default pipeline when no configuration file exists |
| `LogbackEncoderFactory` | `io.koraframework.logging.logback` | SPI the configurator picks an encoder from (`name()`, `priority()`, `create(LoggerContext)`) |
| `KoraLogbackProperties` | `io.koraframework.logging.logback` | Reads `kora.logging.*` bootstrap settings from system properties, then environment variables |
| `KoraAsyncAppender` | `io.koraframework.logging.logback` | `final class extends AsyncAppenderBase<ILoggingEvent>`; captures the Kora `MDC` and the current `SpanContext` into the queued event |
| `KoraLoggingEvent` | `io.koraframework.logging.logback` | `record … implements ILoggingEvent`; adds `koraMdc()` and `span()` |
| `KoraMdcConverter` | `io.koraframework.logging.logback` | `ClassicConverter` rendering the Kora MDC as `key: <json>` pairs for a `PatternLayout` |
| `KoraLoggingMarkerConverter` | `io.koraframework.logging.logback` | `ClassicConverter` rendering the first `StructuredArgument` marker as `field=<json>` |
| `ConsoleTextRecordEncoder` | `io.koraframework.logging.logback.text` | Kora's text encoder, built from `LoggingEventTextWriter` parts |
| `ConsoleTextEncoderFactory`, `ColorConsoleTextEncoderFactory` | `io.koraframework.logging.logback.text` | Encoder factories named `text` and `pretty` |

`io.koraframework:logging-logback-json` adds `JsonRecordEncoder` and the `json` factory in
`io.koraframework.logging.logback.json` — see [json-logging-reference.md](json-logging-reference.md).

`logging-common` adds `LoggingModule`, `LoggingConfig`, `LoggingLevelApplier`,
`LoggingLevelRefresher`, `MDC`, the `arg` package, the `masking` package and the `@Log` / `@Mdc` /
`@Mask` annotations. The declarative `@Log` / `@Mdc` aspects belong to
[`kora-aop-logging`](../../kora-aop-logging/SKILL.md).

## Module setup

```groovy
dependencies {
    koraBom platform("io.koraframework:kora-bom:$koraVersion")   // koraVersion=2.0.0.RC2
    annotationProcessor "io.koraframework:annotation-processors" // Kotlin: ksp "io.koraframework:symbol-processors"

    implementation "io.koraframework:logging-logback"            // or logging-logback-json for JSON output
    implementation "io.koraframework:config-hocon"               // or config-yaml
}
```

`logging-logback/build.gradle` declares `api project(':core:common')`,
`api project(':logging:logging-common')` and `api(libs.logback.classic)` with the `slf4j-api`
transitive excluded (SLF4J comes from `logging-common` instead). `logging-common/build.gradle`
declares `api project(':core:common')`, `api project(':json:json-common')`,
`api project(':config:config-common')`, `api libs.slf4j.api` and `api libs.slf4j.jul`
(`org.slf4j:jul-to-slf4j`, which `KoraLogbackConfigurator` uses to route `java.util.logging` into
Logback). So a single `logging-logback` dependency brings SLF4J, Logback,
`json-common` (needed for every structured value) and the OpenTelemetry API that
`KoraAsyncAppender` reads `Span.current()` from.

**A config module is mandatory.** `LoggingModule` declares

```java
default LoggingConfig loggingConfig(Config config, ConfigValueMapper<LoggingConfig> mapper) {
    return mapper.mapOrThrow(config.get("logging"));
}
```

so without `HoconConfigModule` / `YamlConfigModule` in the `@KoraApp` there is no `Config` component
and the graph does not build.

===! "Java"

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

=== "Kotlin"

    ```kotlin
    import io.koraframework.application.graph.KoraApplication
    import io.koraframework.common.annotation.KoraApp
    import io.koraframework.config.hocon.HoconConfigModule
    import io.koraframework.logging.logback.LogbackModule

    @KoraApp
    interface Application : LogbackModule, HoconConfigModule {
        companion object {
            @JvmStatic
            fun main(args: Array<String>) {
                KoraApplication.run(ApplicationGraph::graph)
            }
        }
    }
    ```

## No logback.xml: `KoraLogbackConfigurator`

A `logback.xml` is optional. `KoraLogbackConfigurator` first lets Logback look for a configuration
file (`logback-test.xml`, `logback.xml`, `-Dlogback.configurationFile`); **a file, when found,
always wins**. Without one it selects a `LogbackEncoderFactory` — `text`, `pretty` (coloured,
picked automatically inside a Gradle test worker) or `json` (when `logging-logback-json` is on the
classpath) — by the `kora.logging.encoder` system property / `KORA_LOGGING_ENCODER` environment
variable or by priority, and installs `ConsoleAppender` → `KoraAsyncAppender` on the root logger.
Selection rules, priorities and every `kora.logging.*` property:
[json-logging-reference.md](json-logging-reference.md#zero-config-pick-an-encoder-without-a-logbackxml).

In both paths the configurator also installs the `java.util.logging` bridge (`SLF4JBridgeHandler`
plus a `LevelChangePropagator`, skipped when already present); turn it off with
`kora.logging.config.jul-bridge=false` / `KORA_LOGGING_CONFIG_JUL_BRIDGE=false`.

## logback.xml

### Production text output

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

The encoder is `io.koraframework.logging.logback.text.ConsoleTextRecordEncoder` — the `text`
sub-package matters. A `logback.xml` still naming `io.koraframework.logging.logback.ConsoleTextRecordEncoder`
fails to create the encoder, and with a `NopStatusListener` the only symptom is an empty console.
For JSON, put `io.koraframework.logging.logback.json.JsonRecordEncoder` in the same place
([json-logging-reference.md](json-logging-reference.md#declaring-jsonrecordencoder-in-logbackxml)).

With no nested element, `ConsoleTextRecordEncoder` uses its default writers
(`DefaultLoggingEventTextWriter`, `DefaultTraceTextWriter`, `DefaultMdcTextWriter`,
`DefaultMessageTextWriter`, `DefaultStructuredTextWriter`, `DefaultExceptionTextWriter` from
`io.koraframework.logging.logback.text.writer`); the first `<writer class="…"/>` element replaces
them all. The default output, in order:

```
yyyy-MM-dd HH:mm:ss.SSS LEVEL [thread] abbreviated.logger.Name - traceId=… spanId=… <koraMdc k=json …> <slf4jMdc k=v …> message
        \tfieldName=<json>          # one line per StructuredArgument marker
        \tfieldName=<json>          # one line per StructuredArgument argument
        \tkey=<json>                # one line per SLF4J key/value whose value is a StructuredArgumentWriter
stack trace, if any
```

`traceId` / `spanId` appear only when the event is a `KoraLoggingEvent` (i.e. it went through
`KoraAsyncAppender`) and the span context is valid. Timestamps are formatted in **UTC**. The logger
name is abbreviated to a target length of 100 characters.

### Test — pattern encoder

The example apps deliberately use a different `logback-test.xml` in `src/test/resources`: a plain
pattern encoder, still wrapped by `KoraAsyncAppender`, plus explicit `<logger>` elements. A
`logback-test.xml` is optional: without any configuration file, tests running in a Gradle test
worker get the coloured `pretty` encoder from `KoraLogbackConfigurator` with no XML at all.

Those `<logger>` elements are **not** exempt from the reset below. `LoggingLevelRefresher` is a
`@Root` component and its `init()` calls `reset()` unconditionally — an absent `logging` section
maps to an empty object (`@ConfigMapper(mapNullAsEmptyObject = true)`), it does not skip the
refresher. What they actually govern is the window the graph does not cover: output emitted
**before** graph init — Testcontainers pulling and starting containers, which is why the examples
set `org.testcontainers` levels here — and tests that never build a graph. Levels that must hold
inside a `@KoraAppTest` belong in the test config's `logging.levels`.

```xml
<configuration debug="false">
    <statusListener class="ch.qos.logback.core.status.NopStatusListener" />

    <appender name="STDOUT" class="ch.qos.logback.core.ConsoleAppender">
        <encoder>
            <charset>UTF-8</charset>
            <pattern>%cyan(%d{HH:mm:ss.SSS}) %highlight(%-5level) [%thread] %logger{36} - %msg%n</pattern>
        </encoder>
    </appender>

    <appender name="ASYNC" class="io.koraframework.logging.logback.KoraAsyncAppender">
        <appender-ref ref="STDOUT"/>
    </appender>

    <root level="INFO">
        <appender-ref ref="ASYNC"/>
    </root>

    <logger level="INFO" name="io.koraframework"/>
    <logger level="DEBUG" name="com.example"/>
</configuration>
```

## Log levels are owned by the config, not by `logback.xml`

`LoggingModule` registers a `@Root LoggingLevelRefresher`, whose `init()` runs during graph
initialization:

```java
public void init() {
    this.loggingLevelApplier.reset();
    for (var entry : config.levels().entrySet()) {
        this.loggingLevelApplier.apply(entry.getKey(), entry.getValue());
    }
}
```

`LogbackModule`'s applier implements `reset()` as: set the **root logger to `INFO`**, and set every
other logger's level to `null` (inherit). Consequences:

- `<logger name="com.example" level="DEBUG"/>` in `logback.xml` is discarded at graph start.
- `<root level="WARN">` is discarded too — the root falls back to `INFO` unless
  `logging.levels."ROOT"` says otherwise. The migrated examples set the root level in *both*
  places for exactly this reason.
- Kora does not validate the level string. `apply(name, level)` hands it straight to Logback's
  `Level.toLevel(String)`, whose single-argument overload resolves to a fallback level instead of
  throwing — so a typo like `"INFOO"` does not fail startup and does not warn; the logger simply
  ends up at a level you did not ask for.

```hocon
logging.levels {
  "ROOT" = "WARN"
  "io.koraframework" = "INFO"
  "io.koraframework.http.server.common.HttpServer.request" = "DEBUG"
  "com.example" = "DEBUG"
}
```

```yaml
logging:
  levels:
    ROOT: ${LOGGING_LEVEL_ROOT:WARN}
    io.koraframework: ${LOGGING_LEVEL_KORA:INFO}
    com.example: ${LOGGING_LEVEL_APP:DEBUG}
```

The key is **`levels`**, plural. `logging.level` is not a recognised key; HOCON and YAML both accept
it without complaint and the block simply never reaches `LoggingConfig`, leaving every logger at
its default.

Both `"ROOT"` and `"root"` appear across the migrated examples (`kora-java-crud`,
`kora-java-telemetry` and `kora-java-graalvm-kafka` use lower case; the observability guides use
upper case). Prefer `"ROOT"`, the canonical Logback name.

### Level guide

| Level | When to use | Production |
|-------|-------------|------------|
| `TRACE` | Request/response bodies, full SQL text | Disabled |
| `DEBUG` | Headers, query params, DB query records | Debug only |
| `INFO` | Business events, HTTP request/response lines | Enabled |
| `WARN` | Recoverable issues, failed HTTP responses | Enabled |
| `ERROR` | Unrecoverable errors | Enabled |

## Pattern layouts and the Kora converters

If you keep a `PatternLayout` instead of `ConsoleTextRecordEncoder`, two `ClassicConverter`s in
`logging-logback` can put the Kora-specific data back into the line:

- `KoraMdcConverter` — renders the Kora MDC as `key: <json>` pairs. On a `KoraLoggingEvent` it reads
  `koraMdc()`; on any other event it reads the bound `MDC`, and renders **nothing** when no MDC
  scope is bound (startup, library pools, threads you start yourself) — it never fails the line.
  Behind a synchronous appender it therefore only shows MDC values for records logged inside a
  request/message/job scope; behind `KoraAsyncAppender` it uses the snapshot taken at log time.
- `KoraLoggingMarkerConverter` — renders the first `StructuredArgument` marker as
  `fieldName=<json>`, and an empty string for an event with no markers or no structured one (RC1
  threw a `NullPointerException` on marker-less events, #934).

Neither is auto-registered: `logging-logback` ships no `ServiceLoader` entry and no default
configuration for them, so a Logback conversion rule must declare them before a pattern can use
them. Consult the Logback manual for the exact `<conversionRule>` element accepted by your Logback
version — <https://logback.qos.ch/manual/layouts.html> — the element changed shape across the 1.5
line and Kora does not pin it. `%X{key}` in a pattern reads the **SLF4J** MDC only; it never sees
Kora MDC values.

## Native image metadata

Only relevant when the service is built with GraalVM `native-image`. On the JVM none of this is
read, so "it works on the JVM" proves nothing about it.

Kora's own logback metadata ships inside the artifact at
`META-INF/native-image/io.koraframework.logging.logback/` (`reflect-config.json` registering
`KoraAsyncAppender`, `text.ConsoleTextRecordEncoder`, `KoraMdcConverter`,
`KoraLoggingMarkerConverter`, `KoraLogbackConfigurator`, `text.ConsoleTextEncoderFactory`,
`text.ColorConsoleTextEncoderFactory` (RC1 listed a non-existent `PrettyTextEncoderFactory`, #920)
and the Logback classes it needs; `resource-config.json` including `logback.xml`, `logback-test.xml` and the
two `META-INF/services` files the configurator is discovered through). `logging-logback-json`
ships its own pair under `META-INF/native-image/io.koraframework.logging.logback.json/`.

Application-owned metadata lives in the application's own resources and **is not migrated by
OpenRewrite or any rename script — resource directories are never touched**. Two things change
when moving from 1.x:

1. **The directory**, which carries the group name:
   `src/main/resources/META-INF/native-image/ru.tinkoff.kora.examples/logback/`
   → `src/main/resources/META-INF/native-image/io.koraframework.examples/logback/`
2. **The Kora class names inside** `reflect-config.json`:
   `ru.tinkoff.kora.logging.logback.ConsoleTextRecordEncoder`
   → `io.koraframework.logging.logback.text.ConsoleTextRecordEncoder` (note the `text` package);
   `ru.tinkoff.kora.logging.logback.KoraAsyncAppender` → `io.koraframework.logging.logback.KoraAsyncAppender`.
   Third-party entries such as `ch.qos.logback.core.status.NopStatusListener` do **not** change.

**File names are load-bearing.** Only `reflect-config.json`, `resource-config.json`,
`proxy-config.json`, `serialization-config.json`, `jni-config.json`, `native-image.properties` and
`reachability-metadata.json` are read. A file named `reflection-config.json` is silently ignored —
the build succeeds and none of the registrations apply.

```shell
find . -name "reflection-config.json"      # every hit is a dead file
```

An application-owned pair for a text `logback.xml`:

```json
[
  { "name": "io.koraframework.logging.logback.text.ConsoleTextRecordEncoder",
    "allDeclaredConstructors": true, "allPublicMethods": true },
  { "name": "io.koraframework.logging.logback.KoraAsyncAppender",
    "allDeclaredConstructors": true, "allPublicMethods": true },
  { "name": "ch.qos.logback.core.status.NopStatusListener",
    "allDeclaredConstructors": true }
]
```

```json
{
  "resources": {
    "includes": [
      { "pattern": "\\Qlogback.xml\\E" },
      { "pattern": "\\Qapplication.conf\\E" }
    ]
  }
}
```

Symptom of lost logback metadata in a native image: the binary starts, but logs are empty or ignore
`logback.xml` entirely.

## Troubleshooting

| Symptom | Cause / fix |
|---|---|
| No logs at all | The encoder class in `logback.xml` does not exist (`…logback.ConsoleTextRecordEncoder` instead of `…logback.text.ConsoleTextRecordEncoder`), or `kora.logging.encoder` names an unknown encoder; set `<configuration debug="true">` and drop the `NopStatusListener` to see Logback's own diagnostics |
| Output format is not the one `kora.logging.encoder` asks for | A `logback.xml` / `logback-test.xml` is on the classpath — a configuration file always wins over encoder selection |
| Coloured text in tests, plain text or JSON in production | Expected without a `logback-test.xml`: the `pretty` encoder wins inside a Gradle test worker |
| Levels from `logback.xml` ignored | Expected — `LoggingLevelRefresher.init()` resets them. Move them into `logging.levels` |
| A `logging.levels` entry has no effect | Wrong key (`logging.level`), or a logger name that does not match — component logger names are listed in [component-telemetry-reference.md](component-telemetry-reference.md) |
| A level string typo does not fail the build | `Level.toLevel(String)` resolves to a fallback instead of throwing; check the spelling against `TRACE/DEBUG/INFO/WARN/ERROR/OFF` |
| `traceId` / MDC / structured fields missing | Plain `<pattern>` encoder — use `ConsoleTextRecordEncoder` or `JsonRecordEncoder` behind `KoraAsyncAppender` |
| Graph build fails on `Config` or `ConfigValueMapper<LoggingConfig>` | Add `HoconConfigModule` or `YamlConfigModule` to the `@KoraApp` |
| Native binary logs are empty | Metadata directory still on the old group, or a `reflection-config.json` file name |
