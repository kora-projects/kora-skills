# Structured Logging Reference

**Source:** `.kora-agent/kora-docs/mkdocs/docs/en/documentation/logging-slf4j.md`

## Contents

- [StructuredArgument API](#structuredargument-api)
- [Typed overloads](#typed-overloads)
- [Writer lambda (custom shapes)](#writer-lambda-custom-shapes)
- [Marker vs parameter](#marker-vs-parameter)
- [Supported types](#supported-types)
- [JSON output example](#json-output-example)
- [Best practices](#best-practices)

## StructuredArgument API

Kora provides `ru.tinkoff.kora.logging.common.arg.StructuredArgument` for machine-readable
structured logging. Structured data can be passed two ways:

- **Parameter** (`StructuredArgument.arg(...)`) — interpolated into the `{}` position of the message.
- **Marker** (`StructuredArgument.marker(...)`) — attached as metadata, not interpolated.

```java
import ru.tinkoff.kora.logging.common.arg.StructuredArgument;
```

```kotlin
import ru.tinkoff.kora.logging.common.arg.StructuredArgument
```

## Typed overloads

The simplest and safest form uses the typed overloads. `arg`/`marker` accept `String`,
`Integer`, `Long`, `Boolean`, and `Map<String, String>` directly.

===! "Java"

    ```java
    var requestArg = StructuredArgument.arg("requestId", requestId);     // String
    log.info("Request {} processed", requestArg);

    var countArg = StructuredArgument.arg("count", items.size());        // Integer
    log.info("Loaded {}", countArg);

    var attrs = StructuredArgument.arg("user", Map.of(                   // Map<String,String>
        "id", user.id(),
        "role", user.role()));
    log.info("User {} logged in", attrs);
    ```

=== "Kotlin"

    ```kotlin
    val requestArg = StructuredArgument.arg("requestId", requestId)      // String
    logger.info("Request {} processed", requestArg)

    val attrs = StructuredArgument.arg("user", mapOf(                    // Map<String,String>
        "id" to user.id,
        "role" to user.role))
    logger.info("User {} logged in", attrs)
    ```

## Writer lambda (custom shapes)

For values that are not one of the typed overloads, pass a writer lambda. The lambda receives a
Jackson `JsonGenerator`, so use Jackson generator methods (`writeString`, `writeNumber`,
`writeStartObject`/`writeEndObject`, `writeStringField`, `writeNumberField`). There is no
two-argument `writeString(name, value)`.

===! "Java"

    ```java
    // Single value
    var idArg = StructuredArgument.arg("requestId", gen -> gen.writeString(requestId));
    log.info("Request {} processed", idArg);

    // Nested object: open an object, then write named fields
    var userArg = StructuredArgument.arg("user", gen -> {
        gen.writeStartObject();
        gen.writeStringField("id", user.getId());
        gen.writeStringField("email", user.getEmail());
        gen.writeEndObject();
    });
    log.info("User created {}", userArg);
    ```

=== "Kotlin"

    ```kotlin
    val idArg = StructuredArgument.arg("requestId") { it.writeString(requestId) }
    logger.info("Request {} processed", idArg)

    val userArg = StructuredArgument.arg("user") { gen ->
        gen.writeStartObject()
        gen.writeStringField("id", user.id)
        gen.writeStringField("email", user.email)
        gen.writeEndObject()
    }
    logger.info("User created {}", userArg)
    ```

## Marker vs parameter

| Form | Call | Appears in message text? | Use for |
|------|------|--------------------------|---------|
| Parameter | `log.info("... {}", arg)` | Yes (at the `{}` position) | Values you want rendered in the line |
| Marker | `log.info(marker, "...")` | No (metadata only) | Filtering / structured-only context |

===! "Java"

    ```java
    var marker = StructuredArgument.marker("userId", userId);
    log.info(marker, "User action performed");
    ```

=== "Kotlin"

    ```kotlin
    val marker = StructuredArgument.marker("userId", userId)
    logger.info(marker, "User action performed")
    ```

## Supported types

The typed `arg`/`marker` overloads accept:

| Type | Notes |
|------|-------|
| `String` | rendered as a JSON string |
| `Integer` | rendered as a JSON number |
| `Long` | rendered as a JSON number |
| `Boolean` | rendered as a JSON boolean |
| `Map<String, String>` | rendered as a nested JSON object |
| anything else | supply a writer lambda over the Jackson `JsonGenerator` |

## JSON output example

With `LogstashEncoder`, structured arguments produce:

```json
{
  "@timestamp": "2024-01-15T10:30:00.000Z",
  "level": "INFO",
  "logger": "com.example.UserService",
  "message": "User created {}",
  "user": {
    "id": "usr-123",
    "email": "user@example.com"
  }
}
```

## Best practices

- Use the typed overloads (`arg("k", value)`) where possible; reach for the writer lambda only
  for nested/custom shapes.
- Write only the fields you need — never dump whole entities containing secrets or PII.
- Always parameterize the message (`log.info("user {}", arg)`); never concatenate strings.
