# Logback Configuration Reference

**Source:** `.kora-agent/kora-docs/mkdocs/docs/en/documentation/logging-slf4j.md`

## Contents

- [Module setup](#module-setup)
- [logback.xml configuration](#logbackxml-configuration)
- [Async appender parameters](#async-appender-parameters)
- [Pattern formats](#pattern-formats)
- [Log levels configuration](#log-levels-configuration)
- [Troubleshooting](#troubleshooting)

## Module Setup

### Dependency

The `kora-parent` BOM manages the version; do not pin it on the artifact.

```groovy
implementation "ru.tinkoff.kora:logging-logback"
```

### Application Module

===! "Java"

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

=== "Kotlin"

    ```kotlin
    import ru.tinkoff.kora.common.KoraApp
    import ru.tinkoff.kora.application.graph.KoraApplication
    import ru.tinkoff.kora.config.hocon.HoconConfigModule
    import ru.tinkoff.kora.logging.logback.LogbackModule

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

## logback.xml Configuration

### Basic Console Appender

```xml
<?xml version="1.0" encoding="UTF-8"?>
<configuration debug="false">
    <statusListener class="ch.qos.logback.core.status.NopStatusListener" />
    
    <appender name="STDOUT" class="ch.qos.logback.core.ConsoleAppender">
        <encoder>
            <charset>UTF-8</charset>
            <pattern>%d{HH:mm:ss.SSS} %-5level [%thread] %logger{36} - %msg%n</pattern>
        </encoder>
    </appender>

    <appender name="ASYNC" class="ru.tinkoff.kora.logging.logback.KoraAsyncAppender">
        <appender-ref ref="STDOUT"/>
    </appender>

    <root level="WARN">
        <appender-ref ref="ASYNC"/>
    </root>
</configuration>
```

### Production Configuration with Async

```xml
<?xml version="1.0" encoding="UTF-8"?>
<configuration>
    <!-- JSON Console Appender -->
    <appender name="JSON_CONSOLE" class="ch.qos.logback.core.ConsoleAppender">
        <encoder class="net.logstash.logback.encoder.LogstashEncoder">
            <customFields>{"service":"${SERVICE_NAME:-my-service}"}</customFields>
            <timestampPattern>yyyy-MM-dd'T'HH:mm:ss.SSS'Z'</timestampPattern>
        </encoder>
    </appender>

    <!-- Async Wrapper for Non-Blocking I/O.
         KoraAsyncAppender extends Logback AsyncAppenderBase: use queueSize /
         discardingThreshold, NOT bufferSize / flushThreshold. -->
    <appender name="ASYNC_JSON" class="ru.tinkoff.kora.logging.logback.KoraAsyncAppender">
        <appender-ref ref="JSON_CONSOLE"/>
        <queueSize>8192</queueSize>
        <discardingThreshold>0</discardingThreshold>
    </appender>

    <!-- Per-package levels are configured in the Kora config (logging.levels);
         set only the root level here. -->
    <root level="INFO">
        <appender-ref ref="ASYNC_JSON"/>
    </root>
</configuration>
```

### Async Appender Parameters

`KoraAsyncAppender` extends Logback's `AsyncAppenderBase`, so it uses the standard async settings
(not `bufferSize`/`flushThreshold`). See
[async-logging-reference.md](async-logging-reference.md) for the full table.

| Parameter | Default | Description |
|-----------|---------|-------------|
| `queueSize` | 256 | Capacity of the blocking event queue |
| `discardingThreshold` | 20% of `queueSize` | Below this remaining capacity, TRACE/DEBUG/INFO drop; `0` = never drop |
| `maxFlushTime` | 1000 | Max time (ms) to flush on shutdown |
| `neverBlock` | false | Drop instead of block when the queue is full |

### Pattern Formats

**Standard:**
```
%d{HH:mm:ss.SSS} %-5level [%thread] %logger{36} - %msg%n
```

**With MDC:**
```
%d{HH:mm:ss.SSS} %-5level [%thread] %logger{36} [traceId=%X{traceId}, userId=%X{userId}] - %msg%n
```

## Log Levels Configuration

### Via application.conf (Hocon)

```hocon
logging {
    levels {
        "ru.tinkoff.kora" = "INFO"
        "ru.tinkoff.kora.http.server.common.telemetry" = "DEBUG"
        "ru.tinkoff.kora.http.client.common.telemetry" = "DEBUG"
        "com.example" = "DEBUG"
        "com.example.sensitive" = "WARN"  # Reduce noise
    }
}
```

### Via application.yml (YAML)

```yaml
logging:
  levels:
    ru.tinkoff.kora: "INFO"
    ru.tinkoff.kora.http.server.common.telemetry: "DEBUG"
    ru.tinkoff.kora.http.client.common.telemetry: "DEBUG"
    com.example: "DEBUG"
    com.example.sensitive: "WARN"
```

### Level Guide

| Level | When to Use | Production |
|-------|-------------|------------|
| `TRACE` | Verbose tracing, full request dumps | Disabled |
| `DEBUG` | Detailed diagnostic info | Debug only |
| `INFO` | Business events, lifecycle | Enabled |
| `WARN` | Recoverable issues | Enabled |
| `ERROR` | Unrecoverable errors | Enabled |

## Troubleshooting

### Logging does not work

1. Check `logging-logback` dependency
2. Verify `logback.xml` in classpath (`src/main/resources/`)
3. Enable debug: `<configuration debug="true">`

### Async appender drops logs

1. Set `discardingThreshold` to `0` (never drop)
2. Increase `queueSize`
3. Increase `maxFlushTime` and ensure graceful shutdown via `KoraApplication.run(...)`

### High memory usage

1. Reduce `queueSize` (e.g., 4096)
2. Reduce average event size (fewer/smaller structured fields)
