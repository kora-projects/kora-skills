# JSON Logging Reference

**Source:** `.kora-agent/kora-docs/mkdocs/docs/en/documentation/logging-slf4j.md`

JSON output is produced by the third-party `net.logstash.logback:logstash-logback-encoder`
plugged into a standard Logback appender, wrapped by Kora's `KoraAsyncAppender`. Kora's own
`logging-logback` module ships a text encoder (`ConsoleTextRecordEncoder`); JSON requires the
Logstash encoder dependency.

## Contents

- [Logstash encoder setup](#logstash-encoder-setup)
- [Full production configuration](#full-production-configuration)
- [JSON output format](#json-output-format)
- [Encoder options](#encoder-options)
- [SIEM integration](#siem-integration)
- [Performance considerations](#performance-considerations)
- [Troubleshooting](#troubleshooting)

## Logstash Encoder Setup

### Dependency

```groovy
// Logstash encoder for JSON output
implementation "net.logstash.logback:logstash-logback-encoder:7.4"
```

### Basic JSON Configuration

```xml
<appender name="JSON_CONSOLE" class="ch.qos.logback.core.ConsoleAppender">
    <encoder class="net.logstash.logback.encoder.LogstashEncoder">
        <!-- Custom fields for all logs -->
        <customFields>{"service":"my-service","environment":"${SERVICE_ENV:-dev}"}</customFields>
        
        <!-- Timestamp format -->
        <timestampPattern>yyyy-MM-dd'T'HH:mm:ss.SSS'Z'</timestampPattern>
    </encoder>
</appender>
```

## Full Production Configuration

```xml
<?xml version="1.0" encoding="UTF-8"?>
<configuration>
    <!-- JSON Console Appender -->
    <appender name="JSON_CONSOLE" class="ch.qos.logback.core.ConsoleAppender">
        <encoder class="net.logstash.logback.encoder.LogstashEncoder">
            <!-- Custom fields for all logs -->
            <customFields>{"service":"${SERVICE_NAME:-my-service}","environment":"${SERVICE_ENV:-dev}"}</customFields>
            
            <!-- Include MDC fields in JSON -->
            <includeMdcKeyName>traceId</includeMdcKeyName>
            <includeMdcKeyName>requestId</includeMdcKeyName>
            <includeMdcKeyName>userId</includeMdcKeyName>
            <includeMdcKeyName>spanId</includeMdcKeyName>
            
            <!-- Timestamp format -->
            <timestampPattern>yyyy-MM-dd'T'HH:mm:ss.SSS'Z'</timestampPattern>
            
            <!-- Stack trace handling -->
            <stackTraceEnabled>true</stackTraceEnabled>
            <throwableConverter class="net.logstash.logback.stacktrace.ShortenedThrowableConverter">
                <maxDepthPerThrowable>30</maxDepthPerThrowable>
                <maxLength>2048</maxLength>
                <shortenedClassNameLength>20</shortenedClassNameLength>
                <rootCauseFirst>true</rootCauseFirst>
            </throwableConverter>
        </encoder>
    </appender>

    <!-- Async Wrapper (AsyncAppenderBase settings: queueSize / discardingThreshold) -->
    <appender name="ASYNC_JSON" class="ru.tinkoff.kora.logging.logback.KoraAsyncAppender">
        <appender-ref ref="JSON_CONSOLE"/>
        <queueSize>8192</queueSize>
        <discardingThreshold>0</discardingThreshold>
    </appender>

    <!-- Kora Framework Logging -->
    <logger name="ru.tinkoff.kora" level="INFO"/>
    <logger name="ru.tinkoff.kora.http.server.common.telemetry" level="INFO"/>
    <logger name="ru.tinkoff.kora.http.client.common.telemetry" level="INFO"/>
    <logger name="ru.tinkoff.kora.grpc" level="INFO"/>
    <logger name="ru.tinkoff.kora.database" level="INFO"/>
    <logger name="ru.tinkoff.kora.kafka" level="INFO"/>

    <!-- Application Logging -->
    <logger name="com.example" level="DEBUG"/>

    <!-- Root Logger -->
    <root level="INFO">
        <appender-ref ref="ASYNC_JSON"/>
    </root>
</configuration>
```

## JSON Output Format

### Standard Log Entry

```json
{
  "@timestamp": "2024-01-15T10:30:00.123Z",
  "level": "INFO",
  "thread": "main",
  "logger": "com.example.UserService",
  "message": "User created",
  "service": "user-service",
  "environment": "prod",
  "traceId": "abc-123-def",
  "requestId": "req-456",
  "userId": "user-789"
}
```

### Log with Structured Argument

```json
{
  "@timestamp": "2024-01-15T10:30:00.123Z",
  "level": "INFO",
  "logger": "com.example.OrderService",
  "message": "Order created",
  "service": "order-service",
  "traceId": "xyz-789",
  "order": {
    "id": "ord-123",
    "userId": "usr-456",
    "items": [
      {"productId": "prod-1", "quantity": 2},
      {"productId": "prod-2", "quantity": 1}
    ],
    "total": 99.99
  }
}
```

### Error Log with Stack Trace

```json
{
  "@timestamp": "2024-01-15T10:30:00.123Z",
  "level": "ERROR",
  "logger": "com.example.PaymentService",
  "message": "Payment failed",
  "service": "payment-service",
  "traceId": "err-trace-123",
  "paymentId": "pay-456",
  "stack_trace": "java.lang.RuntimeException: Payment declined\n\tat com.example.PaymentService.process(PaymentService.java:42)\n\t..."
}
```

## Encoder Options

### Common Options

| Option | Default | Description |
|--------|---------|-------------|
| `customFields` | - | Static JSON fields added to all logs |
| `includeMdcKeyName` | All MDC | Specific MDC keys to include |
| `timestampPattern` | ISO-8601 | Date/time format |
| `stackTraceEnabled` | true | Include stack traces |
| `includeCallerData` | false | Include class/method/line (performance impact) |

### Include Caller Data

For detailed debugging (performance impact):

```xml
<encoder class="net.logstash.logback.encoder.LogstashEncoder">
    <includeCallerData>true</includeCallerData>
</encoder>
```

### Custom Field Provider

Dynamic custom fields:

```xml
<encoder class="net.logstash.logback.encoder.LogstashEncoder">
    <customFields>{"service":"${SERVICE_NAME}"}</customFields>
    <fieldNames>
        <timestamp>@timestamp</timestamp>
        <level>level</level>
        <message>message</message>
    </fieldNames>
</encoder>
```

## Environment Variables

Use environment variables in configuration:

```xml
<customFields>{"service":"${SERVICE_NAME:-default-service}","env":"${SERVICE_ENV:-dev}"}</customFields>
```

## SIEM Integration

### ELK Stack (Elasticsearch, Logstash, Kibana)

```xml
<encoder class="net.logstash.logback.encoder.LogstashEncoder">
    <includeCallerData>false</includeCallerData>
    <stackTraceEnabled>true</stackTraceEnabled>
    <fieldNames>
        <level>log_level</level>
        <message>log_message</message>
    </fieldNames>
</encoder>
```

### Splunk

```xml
<encoder class="net.logstash.logback.encoder.LogstashEncoder">
    <customFields>{"app":"${APP_NAME}","host":"${HOSTNAME}"}</customFields>
    <includeMdcKeyName>traceId</includeMdcKeyName>
    <includeMdcKeyName>spanId</includeMdcKeyName>
</encoder>
```

### Datadog

```xml
<encoder class="net.logstash.logback.encoder.LogstashEncoder">
    <customFields>{"dd.source":"java","dd.service":"${SERVICE_NAME}"}</customFields>
    <includeMdcKeyName>dd.trace_id</includeMdcKeyName>
    <includeMdcKeyName>dd.span_id</includeMdcKeyName>
</encoder>
```

## Performance Considerations

1. **Use async appender** - Non-blocking log I/O
2. **Avoid `includeCallerData`** - Significant performance impact
3. **Limit MDC keys** - Only include necessary context
4. **Buffer size** - Tune for throughput vs. memory

## Troubleshooting

### JSON not appearing

1. Verify `logstash-logback-encoder` dependency
2. Check encoder class in logback.xml
3. Ensure no conflicting logback dependencies

### Missing fields in JSON

1. Check `includeMdcKeyName` for MDC fields
2. Verify `customFields` syntax is valid JSON
3. Check environment variable substitution
