---
name: kora-telemetry-logging
description: "Structured logging for Kora services via SLF4J + Logback (LogbackModule), the KoraAsyncAppender for non-blocking output, structured arguments/markers (StructuredArgument), Kora MDC (ru.tinkoff.kora.logging.common.MDC), and the @Log/@Mdc logging aspects (logging-common / LoggingModule). Use when adding logging-logback, wiring logback.xml with KoraAsyncAppender or ConsoleTextRecordEncoder, configuring per-package log levels via logging.levels in HOCON/YAML, enabling module telemetry logging (telemetry.logging.enabled), emitting JSON logs for ELK/Datadog/Splunk, or correlating logs with trace context."
---

# Kora Telemetry Logging

Kora uses `slf4j-api` as the logging facade for the whole framework; the recommended
implementation is Logback via `LogbackModule`. On top of SLF4J, Kora adds structured
arguments, a structured `MDC`, config-driven log levels, and the `KoraAsyncAppender`
for non-blocking output that correctly propagates structured MDC.

## When to use

- Add Logback to a Kora service and pick text vs JSON output.
- Set per-package log levels from config (`logging.levels`) instead of only `logback.xml`.
- Enable per-module telemetry logging (`*.telemetry.logging.enabled`).
- Attach structured key/values to log records (`StructuredArgument`, Kora `MDC`).
- Log method arguments/results declaratively with `@Log`, or enrich MDC with `@Mdc`.

## Source of truth

| Topic | Path |
|-------|------|
| SLF4J / Logback / structured logs / MDC | `.kora-agent/kora-docs/mkdocs/docs/en/documentation/logging-slf4j.md` |
| `@Log` / `@Mdc` aspects | `.kora-agent/kora-docs/mkdocs/docs/en/documentation/logging-aspect.md` |
| End-to-end observability guide | `.kora-agent/kora-docs/mkdocs/docs/en/guides/observability.md` |
| Example apps | `.kora-agent/kora-examples/examples/java/kora-java-telemetry`, `.kora-agent/kora-examples/guides/java/kora-java-guide-observability-app` |

---

## Quick Start

### 1. Dependencies

The `kora-parent` BOM manages all Kora versions; never pin a version on an individual
`ru.tinkoff.kora:*` artifact. The annotation processor is mandatory.

```groovy
dependencies {
    koraBom platform("ru.tinkoff.kora:kora-parent:1.2.17")
    annotationProcessor "ru.tinkoff.kora:annotation-processors"   // Java; Kotlin: ksp "ru.tinkoff.kora:symbol-processors"

    implementation "ru.tinkoff.kora:logging-logback"   // SLF4J + Logback implementation, pulls in logging-common
    implementation "ru.tinkoff.kora:config-hocon"      // log levels live in the Kora config
}
```

`logging-logback` transitively provides `logging-common`, which carries the `@Log`/`@Mdc`
aspects and the `StructuredArgument`/`MDC` API. JSON output uses the third-party
`net.logstash.logback:logstash-logback-encoder` (see [JSON Logging](references/json-logging-reference.md)).

### 2. Application graph

```java
import ru.tinkoff.kora.common.KoraApp;
import ru.tinkoff.kora.application.graph.KoraApplication;
import ru.tinkoff.kora.config.hocon.HoconConfigModule;
import ru.tinkoff.kora.logging.logback.LogbackModule;

@KoraApp
public interface Application extends LogbackModule, HoconConfigModule {
    static void main(String[] args) {
        KoraApplication.run(ApplicationGraph::graph);
    }
}
```

### 3. logback.xml (text output, async)

This mirrors the example apps: Kora's own `ConsoleTextRecordEncoder` wrapped by
`KoraAsyncAppender`. Levels are set in the Kora config, not here.

```xml
<configuration debug="false">
    <statusListener class="ch.qos.logback.core.status.NopStatusListener"/>

    <appender name="STDOUT" class="ch.qos.logback.core.ConsoleAppender">
        <encoder class="ru.tinkoff.kora.logging.logback.ConsoleTextRecordEncoder"/>
    </appender>

    <appender name="ASYNC" class="ru.tinkoff.kora.logging.logback.KoraAsyncAppender">
        <appender-ref ref="STDOUT"/>
    </appender>

    <root level="WARN">
        <appender-ref ref="ASYNC"/>
    </root>
</configuration>
```

### 4. Log levels in config

Kora overrides logger levels from `logging.levels`. `ROOT` is the root logger.

```hocon
logging {
  levels {
    "ROOT" = "WARN"
    "ru.tinkoff.kora" = "INFO"
    "com.example" = "DEBUG"
  }
}
```

### 5. Log

```java
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

private static final Logger log = LoggerFactory.getLogger(UserService.class);

// Parameterized — never concatenate
log.info("Created user with id={}", generatedId);
```

---

## Enabling module telemetry logging

Telemetry logging is **disabled by default** for every module. Enable per module
(`telemetry.logging.enabled = true`); names match each module's config path.

```hocon
db.telemetry.logging.enabled = true                  # JDBC / R2DBC / Vert.x
cassandra.telemetry.logging.enabled = true
httpServer.telemetry.logging.enabled = true
grpcServer.telemetry.logging.enabled = true
scheduling.telemetry.logging.enabled = true
grpcClient.SomeService.telemetry.logging.enabled = true       # per client
SomePathToConfigHttpClient.telemetry.logging.enabled = true   # per client
SomePathToConfigKafkaConsumer.telemetry.logging.enabled = true
SomePathToConfigKafkaProducer.telemetry.logging.enabled = true
```

`httpServer.telemetry.logging.enabled = true` lets HTTP telemetry enrich log records
with trace context (when a tracing module is present).

---

## What's in `references/` and `assets/`

| Reference | Purpose |
|-----------|---------|
| [logback-config-reference.md](references/logback-config-reference.md) | Full `logback.xml` patterns, encoders, log levels, troubleshooting |
| [structured-logging-reference.md](references/structured-logging-reference.md) | `StructuredArgument` arg/marker API, supported types |
| [mdc-context-reference.md](references/mdc-context-reference.md) | Kora `MDC`, `@Mdc` aspect, HTTP interceptor for trace context |
| [logging-aspect-reference.md](references/logging-aspect-reference.md) | `@Log`, `@Log.in/out/off`, `@Mdc` declarative logging |
| [json-logging-reference.md](references/json-logging-reference.md) | LogstashEncoder JSON output, SIEM integration |
| [async-logging-reference.md](references/async-logging-reference.md) | `KoraAsyncAppender` tuning and troubleshooting |

| Asset | Purpose |
|-------|---------|
| `Application.logging.java.template` / `.kt.template` | `@KoraApp` with `LogbackModule` |
| `build.gradle.logging.template` | BOM + processor + `logging-logback` deps |
| `logback.xml.template` | Text console + `KoraAsyncAppender` (matches examples) |
| `logback.dev.xml.template` | Local text output with MDC pattern |
| `logback.json-only.xml.template` | JSON output via LogstashEncoder |
| `application.logging.conf.template` | `logging.levels` + module telemetry toggles |
| `LoggingInterceptor.java.template` | HTTP interceptor that seeds trace context into MDC |
| `LoggingService.java.template` | Structured logging / MDC usage patterns |

See [assets/README.md](assets/README.md) for copy-paste usage.

---

## Core patterns

### Structured arguments

Pass machine-readable key/values to a record either as a **parameter** (interpolated into
the message) or a **marker** (metadata only). Typed overloads exist for `String`, `Integer`,
`Long`, `Boolean`, and `Map<String, String>`; for anything else supply a writer lambda over
the Jackson `JsonGenerator`.

```java
import ru.tinkoff.kora.logging.common.arg.StructuredArgument;

// Parameter — appears in the rendered message position
var requestArg = StructuredArgument.arg("requestId", requestId);   // String overload
log.info("Request {} processed", requestArg);

// Marker — structured metadata, not interpolated
var marker = StructuredArgument.marker("userId", userId);
log.info(marker, "User action performed");

// Map overload for a small object
var attrs = StructuredArgument.arg("attrs", Map.of("id", user.id(), "role", user.role()));
log.info("User created {}", attrs);
```

See [structured-logging-reference.md](references/structured-logging-reference.md) for the
writer-lambda form and supported types.

### Kora MDC (structured, async-safe)

Kora's `ru.tinkoff.kora.logging.common.MDC` attaches structured values to every record in the
current context and is the form that `KoraAsyncAppender` propagates correctly. It is a static
put/remove API (no `clear`, no auto-close).

```java
import ru.tinkoff.kora.logging.common.MDC;

MDC.put("traceId", traceId);          // String / Integer / Long / Boolean / writer overloads
MDC.put("userId", userId);
try {
    log.info("Processing request");   // both keys attached to the record
} finally {
    MDC.remove("traceId");
    MDC.remove("userId");
}
```

The standard `org.slf4j.MDC` (string-only, with `putCloseable`/try-with-resources) also works
because Kora speaks SLF4J — use it for simple string context. Do not mix the two MDC classes in
one file. See [mdc-context-reference.md](references/mdc-context-reference.md).

### Declarative logging with `@Log` / `@Mdc`

`@Log` logs method arguments and/or results; `@Mdc` enriches MDC from parameters or generated
values. Both are AOP aspects from `logging-common` and require the annotation processor; the
target class must be non-`final` (Java) / `open` (Kotlin).

```java
import ru.tinkoff.kora.logging.common.annotation.Log;
import ru.tinkoff.kora.logging.common.annotation.Mdc;

@Component
public class OrderService {

    @Log                                                  // logs args (>) and result (<)
    @Mdc(key = "traceId", value = "${java.util.UUID.randomUUID().toString()}")
    public String process(@Mdc String orderId, @Log.off String secret) {
        return "ok";
    }
}
```

See [logging-aspect-reference.md](references/logging-aspect-reference.md).

### JSON output for log aggregation

Switch the inner appender's encoder to `LogstashEncoder` (third-party) and keep the
`KoraAsyncAppender` wrapper.

```xml
<appender name="JSON_CONSOLE" class="ch.qos.logback.core.ConsoleAppender">
    <encoder class="net.logstash.logback.encoder.LogstashEncoder">
        <customFields>{"service":"${SERVICE_NAME:-my-service}"}</customFields>
        <timestampPattern>yyyy-MM-dd'T'HH:mm:ss.SSS'Z'</timestampPattern>
    </encoder>
</appender>
<appender name="ASYNC_JSON" class="ru.tinkoff.kora.logging.logback.KoraAsyncAppender">
    <appender-ref ref="JSON_CONSOLE"/>
</appender>
```

See [json-logging-reference.md](references/json-logging-reference.md) and
[async-logging-reference.md](references/async-logging-reference.md).

---

## Log level guide

| Level | When to use | Production |
|-------|-------------|------------|
| `TRACE` | Verbose tracing, full request dumps | Disabled |
| `DEBUG` | Detailed diagnostics | Debug only |
| `INFO` | Business events, lifecycle | Enabled |
| `WARN` | Recoverable issues | Enabled |
| `ERROR` | Unrecoverable errors | Enabled |

---

## Common pitfalls

| Problem | Fix |
|---------|-----|
| Module logs missing | Module telemetry logging is off by default — set `<module>.telemetry.logging.enabled = true` |
| Levels in `logback.xml` ignored | Set levels in `logging.levels` (Kora config), not `<logger>` entries |
| Structured MDC empty with async appender | Use `ru.tinkoff.kora.logging.logback.KoraAsyncAppender` and Kora `MDC`, not plain `AsyncAppender` |
| `gen.writeString("name", value)` does not compile | The writer is a Jackson `JsonGenerator`; use the typed `arg(...)`/`Map` overloads, or `writeStringField`/`writeNumberField` inside `writeStartObject`/`writeEndObject` |
| Two `MDC` classes clash | Pick one per file: SLF4J `org.slf4j.MDC` (strings) or Kora `ru.tinkoff.kora.logging.common.MDC` (structured + async) |
| `@Log`/`@Mdc` do nothing | Annotation processor missing, or class is `final`/not `open` |
| Logs lost on shutdown | Run via `KoraApplication.run(...)` so the appender flushes on graceful shutdown |
| JSON not emitted | Add `logstash-logback-encoder` and reference `LogstashEncoder` in the encoder |

---

## Anti-patterns

- Do not concatenate: `log.info("user " + id)` — use `log.info("user {}", id)`.
- Do not log secrets/PII (passwords, tokens, full payloads).
- Do not pin versions on `ru.tinkoff.kora:*` artifacts — the `kora-parent` BOM does it.
