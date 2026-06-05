# Kora Logging Reference

**Source:** [.kora-agent/kora-docs/mkdocs/docs/en/documentation/logging.md](.kora-agent/kora-docs/mkdocs/docs/en/documentation/logging.md)  
**Examples:** `.kora-agent/kora-examples/kora-java-logging-logback/`

Full reference for logging in Kora applications.

## Modules

### LogbackModule

**Dependency:** `ru.tinkoff.kora:logging-logback`

**Module:** `ru.tinkoff.kora.logging.logback.LogbackModule`

## Usage

### Obtaining a Logger

**Java:**
```java
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

Logger logger = LoggerFactory.getLogger(MyClass.class);
```

**Kotlin:**
```kotlin
import org.slf4j.LoggerFactory

private val logger = LoggerFactory.getLogger(MyClass::class.java)
```

### Log Levels

```java
logger.trace("Trace message");
logger.debug("Debug message");
logger.info("Info message");
logger.warn("Warn message");
logger.error("Error message");
```

## Structured Logging

### StructuredArgument

**Java:**
```java
import ru.tinkoff.kora.logging.common.arg.StructuredArgument;

// Marker
var marker = StructuredArgument.marker("userId", gen -> gen.writeString(userId));
logger.info(marker, "User action performed");

// Parameter
var param = StructuredArgument.arg("requestId", gen -> gen.writeString(requestId));
logger.info("Request {} processed", param);

// Multiple arguments
var userArg = StructuredArgument.arg("user", gen -> {
    gen.writeStartObject();
    gen.writeString("id", user.getId());
    gen.writeString("name", user.getName());
    gen.writeEndObject();
});
logger.info("User {} logged in", userArg);
```

**Kotlin:**
```kotlin
import ru.tinkoff.kora.logging.common.arg.StructuredArgument

// Marker
val marker = StructuredArgument.marker("userId") { it.writeString(userId) }
logger.info(marker, "User action performed")

// Parameter
val param = StructuredArgument.arg("requestId") { it.writeString(requestId) }
logger.info("Request {} processed", param)

// Multiple arguments
val userArg = StructuredArgument.arg("user") { gen ->
    gen.writeStartObject()
    gen.writeString("id", user.id)
    gen.writeString("name", user.name)
    gen.writeEndObject()
}
logger.info("User {} logged in", userArg)
```

### MDC (Mapped Diagnostic Context)

**Java:**
```java
import org.slf4j.MDC;

MDC.put("traceId", traceId);
MDC.put("userId", userId);
try {
    // Logging with MDC context
    logger.info("Processing request");
} finally {
    MDC.clear();
}
```

**Kotlin:**
```kotlin
import org.slf4j.MDC

MDC.put("traceId", traceId)
MDC.put("userId", userId)
try {
    // Logging with MDC context
    logger.info("Processing request")
} finally {
    MDC.clear()
}
```

## Logback Configuration

### logback.xml

```xml
<?xml version="1.0" encoding="UTF-8"?>
<configuration>
    <!-- Console appender -->
    <appender name="STDOUT" class="ch.qos.logback.core.ConsoleAppender">
        <encoder class="ch.qos.logback.classic.encoder.PatternLayoutEncoder">
            <pattern>%d{HH:mm:ss.SSS} %-5level [%thread] %logger{36} - %msg%n</pattern>
        </encoder>
    </appender>

    <!-- Async appender -->
    <appender name="ASYNC" class="ru.tinkoff.kora.logging.logback.KoraAsyncAppender">
        <appender-ref ref="STDOUT"/>
        <bufferSize>8192</bufferSize>
        <flushThreshold>7000</flushThreshold>
    </appender>

    <!-- Kora logging -->
    <logger name="ru.tinkoff.kora" level="INFO"/>
    <logger name="ru.tinkoff.kora.http.server.common.telemetry" level="INFO"/>
    <logger name="ru.tinkoff.kora.http.client.common.telemetry" level="INFO"/>
    <logger name="ru.tinkoff.kora.grpc" level="INFO"/>
    <logger name="ru.tinkoff.kora.database" level="INFO"/>
    <logger name="ru.tinkoff.kora.kafka" level="INFO"/>

    <!-- Application logging -->
    <logger name="com.example" level="DEBUG"/>

    <!-- Root logger -->
    <root level="INFO">
        <appender-ref ref="ASYNC"/>
    </root>
</configuration>
```

### Patterns

**Standard:**
```
%d{HH:mm:ss.SSS} %-5level [%thread] %logger{36} - %msg%n
```

**With MDC:**
```
%d{HH:mm:ss.SSS} %-5level [%thread] %logger{36} [traceId=%X{traceId}, userId=%X{userId}] - %msg%n
```

**JSON (Logstash):**
```json
{
  "@timestamp": "2024-01-15T10:30:00.000Z",
  "level": "INFO",
  "thread": "main",
  "logger": "com.example.MyService",
  "message": "Request processed",
  "traceId": "abc123",
  "userId": "user456"
}
```

## Log Levels

### Configuration via application.conf

```hocon
logging {
    levels {
        "ru.tinkoff.kora" = "INFO"
        "ru.tinkoff.kora.http.server.common.telemetry" = "DEBUG"
        "ru.tinkoff.kora.http.client.common.telemetry" = "DEBUG"
        "com.example" = "DEBUG"
        "com.example.sensitive" = "WARN"
    }
}
```

### Levels

| Level | When to use |
|-------|-------------|
| TRACE | Detailed debug information |
| DEBUG | Debug information for development |
| INFO | Important events (start/stop, business events) |
| WARN | Warnings (non-critical errors) |
| ERROR | Errors (critical, require attention) |

## Telemetry Logging

### HTTP Server

```hocon
httpServer {
    telemetry {
        logging {
            enabled = true
        }
    }
}
```

### HTTP Client

```hocon
httpClient {
    MyClient {
        telemetry {
            logging {
                enabled = true
            }
        }
    }
}
```

### gRPC Server

```hocon
grpcServer {
    telemetry {
        logging {
            enabled = true
        }
    }
}
```

### gRPC Client

```hocon
grpcClient {
    MyService {
        telemetry {
            logging {
                enabled = true
            }
        }
    }
}
```

### Database

```hocon
db {
    telemetry {
        logging {
            enabled = true
            includeQueryParameters = true  # Include query parameters
        }
    }
}
```

### Kafka

```hocon
kafka {
    consumer {
        telemetry {
            logging {
                enabled = true
            }
        }
    }
    producer {
        telemetry {
            logging {
                enabled = true
            }
        }
    }
}
```

## Best Practices

1. **Use async appender** for performance
2. **Avoid logging PII** (passwords, tokens, personal data)
3. **Use structured logging** for machine-readable logs
4. **Configure MDC** for traceId, userId, requestId
5. **Use log levels** according to severity
6. **Do not log inside loops** unnecessarily
7. **Use parameterized logging** instead of concatenation:
   ```java
   // Correct
   logger.info("User {} logged in", userId);
   
   // Incorrect
   logger.info("User " + userId + " logged in");
   ```

## Troubleshooting

### Logging does not work

1. Check the `logging-logback` dependency
2. Verify that `logback.xml` is present in the classpath
3. Enable debug logging for logback:
   ```xml
   <configuration debug="true">
   ```

### Async appender drops logs

1. Increase `bufferSize`
2. Increase `flushThreshold`
3. Check the shutdown hook

### JSON logging does not work

1. Add the `logstash-logback-encoder` dependency
2. Check the encoder in logback.xml
3. Enable `includeCallerData` for stack traces
