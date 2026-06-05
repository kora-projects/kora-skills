# Logging Reference (SLF4J / Logback)

**Source:** [.kora-agent/kora-docs/mkdocs/docs/en/documentation/logging.md](.kora-agent/kora-docs/mkdocs/docs/en/documentation/logging.md)  
**Examples:** `.kora-agent/kora-examples/kora-java-logging-logback/`

Kora uses [SLF4J](https://www.slf4j.org/) as logging API and [Logback](https://logback.qos.ch/) as default implementation.

## Dependency

```groovy
// build.gradle
dependencies {
    implementation "ru.tinkoff.kora:logging-logback"
}
```

## Module

```java
@KoraApp
public interface Application extends LogbackModule { }
```

## Logger Usage

```java
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

Logger logger = LoggerFactory.getLogger(SomeService.class);
logger.info("Message");
```

```kotlin
import org.slf4j.Logger
import org.slf4j.LoggerFactory

val logger = LoggerFactory.getLogger(SomeService::class.java)
logger.info("Message")
```

## Logback Configuration (logback.xml)

```xml
<configuration debug="false">
    <!-- Disable status listener -->
    <statusListener class="ch.qos.logback.core.status.NopStatusListener" />
    
    <!-- Console appender -->
    <appender name="STDOUT" class="ch.qos.logback.core.ConsoleAppender">
        <encoder>
            <charset>UTF-8</charset>
            <pattern>%d{HH:mm:ss.SSS} %-5level [%thread] %logger{36} - %msg%n</pattern>
        </encoder>
    </appender>
    
    <!-- Async appender (recommended for production) -->
    <appender name="ASYNC" class="ru.tinkoff.kora.logging.logback.KoraAsyncAppender">
        <appender-ref ref="STDOUT"/>
    </appender>
    
    <!-- Root logger -->
    <root level="WARN">
        <appender-ref ref="ASYNC"/>
    </root>
</configuration>
```

## Logging Levels Configuration

Module logging is configured in `application.conf` / `application.yaml`:

```hocon
logging {
    levels {
        # Logging for specific classes/packages
        "ru.tinkoff.kora.http.server.common.telemetry": "INFO"
        "ru.tinkoff.kora.http.client.common.telemetry": "DEBUG"
    }
}
```

## Module Telemetry Logging

Module logging is **disabled by default**. Enable only needed modules:

```hocon
# Database
db.telemetry.logging.enabled = true              # JDBC / R2DBC / Vertx
cassandra.telemetry.logging.enabled = true       # Cassandra

# gRPC
grpcServer.telemetry.logging.enabled = true      # gRPC server
grpcClient.MyGrpcService.telemetry.logging.enabled = true  # gRPC client (per service)

# HTTP
httpServer.telemetry.logging.enabled = true      # HTTP server
MyHttpClient.telemetry.logging.enabled = true    # HTTP client (per client)

# SOAP
soapClient.MySoapService.telemetry.logging.enabled = true  # SOAP client

# Scheduler
scheduling.telemetry.logging.enabled = true      # Scheduler

# Kafka
MyConsumer.telemetry.logging.enabled = true      # Kafka consumer (per consumer)
MyProducer.telemetry.logging.enabled = true      # Kafka producer (per producer)
```

## Structured Logging

```java
// Via marker
var marker = StructuredArgument.marker("key", gen -> gen.writeString("value"));
logger.info(marker, "message");

// Via parameter
var parameter = StructuredArgument.arg("key", gen -> gen.writeString("value"));
logger.info("message", parameter);
```

```kotlin
// Via marker
val marker = StructuredArgument.marker("key") { it.writeString("value") }
logger.info(marker, "message")

// Via parameter
val parameter = StructuredArgument.arg("key") { it.writeString("value") }
logger.info("message", parameter)
```

## MDC (Mapped Diagnostic Context)

```java
// Add structured data to all logs in context
MDC.put("requestId", gen -> gen.writeString(uuid));

// In Kotlin
MDC.put("userId") { it.writeString(userId) }
```

**Important:** When using `AsyncAppender`, use `KoraAsyncAppender` for correct MDC propagation.
