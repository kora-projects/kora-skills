# Structured Logging Reference

Machine-readable values on a log record, from `io.koraframework.logging.common.arg` and
`…logging.common.masking` (artifact `io.koraframework:logging-common`, transitively present with
`logging-logback`).

## Contents

- [The Jackson 3 generator](#the-jackson-3-generator)
- [StructuredArgument — arg / marker / value](#structuredargument--arg--marker--value)
- [Typed overloads](#typed-overloads)
- [Writer lambdas](#writer-lambdas)
- [StructuredArgumentMapper and @Json types](#structuredargumentmapper-and-json-types)
- [Masking with @Mask](#masking-with-mask)
- [How a structured value reaches the output](#how-a-structured-value-reaches-the-output)
- [Best practices](#best-practices)

## The Jackson 3 generator

Every structured value is written through **Jackson 3**: `tools.jackson.core.JsonGenerator`, not
`com.fasterxml.jackson.core.JsonGenerator`. Jackson 3 renamed the field-writing methods, and this
is the single most common porting error in logging code:

| Jackson 2 (Kora 1.x) | Jackson 3 (Kora 2.0) |
|---|---|
| `writeStringField(name, value)` | **`writeStringProperty(name, value)`** |
| `writeNumberField(name, value)` | **`writeNumberProperty(name, value)`** |
| `writeFieldName(name)` | **`writeName(name)`** |

`writeStartObject()`, `writeStartObject(pojo)`, `writeEndObject()`, `writeStartArray(pojo)`,
`writeString`, `writeNumber`, `writeBoolean` and `writeNull` keep their names. Jackson 3 throws the
unchecked `tools.jackson.core.JacksonException`, so none of these need a `try/catch`.

## `StructuredArgument` — arg / marker / value

`io.koraframework.logging.common.arg.StructuredArgument` has three static entry points; all of them
produce something that carries a `fieldName` plus a JSON body.

| Factory | Returns | How you pass it | Rendered by `ConsoleTextRecordEncoder` |
|---|---|---|---|
| `StructuredArgument.arg(name, …)` | `StructuredArgument` | as a message parameter: `log.info("… {}", arg)` | appended as `\tname=<json>`; the `{}` position gets the argument's `toString()` — see the note below |
| `StructuredArgument.marker(name, …)` | `org.slf4j.Marker` | as the marker: `log.info(marker, "…")` | appended as `\tname=<json>` only |
| `StructuredArgument.value(writer)` | `StructuredArgumentWriter` | as an SLF4J key/value: `log.atInfo().addKeyValue("name", value)` | appended as `\tname=<json>` only |

`value(...)` is what Kora's own component telemetry uses (`addKeyValue("httpRequest", …)`,
`addKeyValue("sqlQuery", …)`), and it is the cleanest form for new code: the key lives in
`addKeyValue`, and the message stays a constant string.

**The `{}` position does not get JSON.** SLF4J interpolates a message parameter with its
`toString()`, and `ArgumentWithValueAndWriter` / `ArgumentWithWriter` are package-private records
with no `toString()` override — so `log.info("Created user {}", arg("user", map))` renders
`Created user ArgumentWithValueAndWriter[fieldName=user, value=..., writer=...]` on the message
line, with the real JSON on the appended `\tuser={…}` line. That is another reason to prefer
`marker(...)` or `addKeyValue` + `value(...)` and keep the message a constant.

## Typed overloads

`arg` and `marker` both accept `String`, `Integer`, `Long`, `Boolean` and `Map<String,String>`
directly, plus `(String fieldName, StructuredArgumentWriter writer)` and
`(String fieldName, T value, JsonWriter<T> writer)`.

===! "Java"

    ```java
    import io.koraframework.logging.common.arg.StructuredArgument;

    log.info("Request {} processed", StructuredArgument.arg("requestId", requestId));   // String
    log.info("Loaded {}", StructuredArgument.arg("count", items.size()));               // Integer
    log.info("User {} logged in", StructuredArgument.arg("user", Map.of(                // Map<String,String>
        "id", user.id(),
        "role", user.role())));

    log.info(StructuredArgument.marker("userId", userId), "User action performed");     // metadata only
    ```

=== "Kotlin"

    ```kotlin
    import io.koraframework.logging.common.arg.StructuredArgument

    log.info("Request {} processed", StructuredArgument.arg("requestId", requestId))
    log.info("User {} logged in", StructuredArgument.arg("user", mapOf(
        "id" to user.id,
        "role" to user.role)))

    log.info(StructuredArgument.marker("userId", userId), "User action performed")
    ```

A `null` value is written as JSON `null` (`ArgumentWithValueAndWriter.writeTo` checks it), so a
nullable field does not need a guard.

## Writer lambdas

For anything that is not one of the typed overloads, supply a `StructuredArgumentWriter` —
a functional interface, `void writeTo(JsonGenerator generator)`.

===! "Java"

    ```java
    log.atInfo()
       .addKeyValue("user", StructuredArgument.value(gen -> {
           gen.writeStartObject();
           gen.writeStringProperty("id", user.id());
           gen.writeStringProperty("email", user.email());
           gen.writeNumberProperty("age", user.age());
           gen.writeEndObject();
       }))
       .log("User created");
    ```

=== "Kotlin"

    ```kotlin
    log.atInfo()
        .addKeyValue("user", StructuredArgument.value { gen ->
            gen.writeStartObject()
            gen.writeStringProperty("id", user.id)
            gen.writeStringProperty("email", user.email)
            gen.writeNumberProperty("age", user.age)
            gen.writeEndObject()
        })
        .log("User created")
    ```

`StructuredArgumentWriter.writeToString()` renders the same JSON into a `String` using the shared
`JsonModule.JSON_FACTORY`, which is what the pattern converters use.

## `StructuredArgumentMapper` and `@Json` types

`StructuredArgumentMapper<T>` (`void write(JsonGenerator gen, T value)`, plus
`writeToString(T)`) bridges a whole domain type into a log record. `LoggingModule` supplies two
generic `@DefaultComponent` factories:

```java
@Json @DefaultComponent
default <T> StructuredArgumentMapper<T> jsonStructuredArgumentMapper(JsonWriter<T> writer) { … }

@DefaultComponent
default <T> MaskedStructuredArgumentMapper<T> maskedStructuredArgumentMapper(JsonWriter<T> writer, MaskingRules<T> rules) { … }

@Json @DefaultComponent
default <T> MaskedStructuredArgumentMapper<T> jsonMaskedStructuredArgumentMapper(JsonWriter<T> writer, MaskingRules<T> rules) { … }
```

They consume the compile-time `JsonWriter<T>` that `@Json` generates, so a type only needs `@Json`
(see [`kora-json`](../../kora-json/SKILL.md)) to be loggable as a nested JSON object. The
`@Json`-tagged variants write a real nested object; the untagged masked variant writes the JSON as
a single escaped **string** property (`MaskedStructuredArgumentMapper(writer, rules, structured)`
with `structured = false`).

## Masking with `@Mask`

`io.koraframework.logging.common.annotation.Mask` marks values that must never reach the log
verbatim.

```java
import io.koraframework.json.common.annotation.Json;
import io.koraframework.logging.common.annotation.Mask;
import io.koraframework.logging.common.masking.MaskingKeepLast;

@Json
@Mask
public record Payment(String id,
                      @Mask String cvv,                       // MaskingFull   -> "***"
                      @Mask(MaskingKeepLast.class) String pan, // MaskingKeepLast -> "***1234"
                      long amount) {}
```

- `@Mask` targets `TYPE`, `FIELD`, `RECORD_COMPONENT`, `PARAMETER`, `METHOD` and `TYPE_USE`; its
  single attribute is `Class<? extends MaskingStrategy> value() default MaskingFull.class`.
- `@Mask` **on the type** is what the rules generator reacts to: only a class or record (not an
  interface, not an abstract class) gets a `@Module` interface named `$<Type>_MaskingRulesModule`
  with a `@DefaultComponent` factory returning `MaskingRules<Type>`. Outer classes are prefixed: a
  nested `Outer.Payment` yields `$Outer_Payment_MaskingRulesModule`. Both KSP (Kotlin) and the Java
  annotation processor generate it (Java since `2.0.0.RC2`, #921) — see
  [logging-masking.md](../../kora-aop-logging/references/logging-masking.md#java-and-kotlin-both-generate-the-rules).
  An interface or abstract class annotated `@Mask` is rejected (`"Only classes and records can be
  annotated with @Mask"` / `"Abstract classes can't be annotated with @Mask"`).
- Built-in strategies, all `@DefaultComponent`s of `LoggingModule`:
  `MaskingFull` (replacement `***`), `MaskingKeepFirst` (first 4 chars + `***`),
  `MaskingKeepLast` (`***` + last 4 chars). A custom `MaskingStrategy`
  (`String mask(Object value)`) can be a regular Kora `@Component` with constructor parameters.
- Rules are matched by `MaskingRules.strategy(path, fieldName)`: a single segment (`password`)
  matches that JSON field name **anywhere**; a dotted path (`user.password`) matches only from the
  logged root; `*` matches exactly one dynamic segment (`users.*.password`).
- Build rules by hand where you need to:
  `MaskingRules.builder(Payment.class).mask("cvv", new MaskingFull()).build()`. Select a custom
  rules class for one logged parameter or result with `@Mapping(CustomRules.class)`.
- JSON `null` is never masked; map **keys** are never masked as values.

Masking of `@Log`-ged method arguments and results is driven by the same annotations but wired by
the aspect — see [`kora-aop-logging`](../../kora-aop-logging/SKILL.md). The same rule syntax
(`MaskingRules` extends `MaskingPathRules`) also drives the `DataMasker` body maskers of HTTP and
Kafka telemetry; how the masking layers relate is in the canonical
[logging-masking.md](../../kora-aop-logging/references/logging-masking.md).

## How a structured value reaches the output

```
log.atInfo().addKeyValue("k", StructuredArgument.value(w))
        │
        ▼
Logback event (KeyValuePair / Marker / argument array)
        │
        ▼  KoraAsyncAppender.append  →  KoraLoggingEvent(… koraMdc, spanContext)
        │
        ▼  ConsoleTextRecordEncoder  →  "\tk={…json…}"
           JsonRecordEncoder         →  "args":{"k":{…json…}}
```

An encoder that does not know about `StructuredArgument` — a plain `<pattern>` encoder — drops the
value entirely: `%msg` renders `arg(...)` through `toString()` and never sees a marker or a
key/value pair. This is why production output uses `ConsoleTextRecordEncoder` or
`JsonRecordEncoder` — see [json-logging-reference.md](json-logging-reference.md).

## Best practices

- Prefer `addKeyValue` + `StructuredArgument.value(...)` for new code; keep the message a constant.
- Use the typed overloads before reaching for a writer lambda.
- Write only the fields you need. Do not dump whole entities — combine `@Json` with `@Mask` when
  a type has to be logged whole.
- Always parameterize (`log.info("user {}", arg)`); never concatenate.
- Remember the generator is Jackson 3: `writeStringProperty`, not `writeStringField`.
