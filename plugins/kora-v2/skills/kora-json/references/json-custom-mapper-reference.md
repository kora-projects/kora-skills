# Custom JSON Mappers Reference (Kora 2.x)

Verified against the Kora 2.0 sources — [`json/json-common`](https://github.com/kora-projects/kora/tree/2.0.0.RC2/json/json-common)
(`JsonReader`, `JsonWriter`, `JsonModule`, `reader/`, `writer/`) and the generated-code paths
in `JsonReaderGenerator` / `JsonWriterGenerator`.

## Contents

1. [Overview](#1-overview)
2. [The two contracts](#2-the-two-contracts)
3. [Jackson 3 streaming API](#3-jackson-3-streaming-api)
4. [Registering a mapper as a component](#4-registering-a-mapper-as-a-component)
5. [Per-field mappers with @Mapping](#5-per-field-mappers-with-mapping)
6. [Common use cases](#6-common-use-cases)
7. [Config-driven readers/writers](#7-config-driven-readerswriters)
8. [Kotlin specifics](#8-kotlin-specifics)
9. [Testing custom mappers](#9-testing-custom-mappers)
10. [Best practices](#10-best-practices)
11. [Quick reference](#11-quick-reference)

---

## 1. Overview

When a type is not in the built-in supported list, supply a `JsonReader<T>` and/or
`JsonWriter<T>`. Use cases:

- custom value types (`UserId`, `Money`)
- a non-standard wire format for a built-in type (a custom date pattern)
- compatibility with a legacy JSON layout
- overriding one of Kora's own `@DefaultComponent` mappers

Two registration routes, with different scope:

| Route | Scope | When |
|---|---|---|
| A component of type `JsonReader<T>` / `JsonWriter<T>` in the graph | every `@Json` DTO containing `T` | the format is a property of the type |
| `@Mapping(X.class)` on one field/parameter | that field only | the same type is encoded differently in different DTOs |

---

## 2. The Two Contracts

```java
package io.koraframework.json.common;

public interface JsonReader<T> extends Mapping.MappingFunction {
    @Nullable T read(JsonParser parser) throws JacksonException;
    // plus default read(byte[]) / read(byte[], int, int) / read(String) / read(InputStream)
}

public interface JsonWriter<T> extends Mapping.MappingFunction {
    void write(JsonGenerator generator, @Nullable T object) throws JacksonException;
    // plus default toByteArray(T) / toString(T) / toPrettyString(T)
}
```

Three things follow:

- **Only `read(JsonParser)` and `write(JsonGenerator, T)` have to be implemented.** The
  byte-array / String / stream helpers are `default` methods on the interface.
- **No checked exception.** Every method declares `throws tools.jackson.core.JacksonException`,
  which is unchecked (Kora's own `RawJsonWriter.write` and `ListJsonReader.read` override with no
  `throws` clause). An implementation therefore never has to declare anything, and a caller
  must never write `catch (IOException …)` around these methods — in Java that is a compile
  error (`exception IOException is never thrown in body of corresponding try statement`).
- **Both extend `Mapping.MappingFunction`**, which is what makes them usable from `@Mapping`.

The module is `@NullMarked`, so `write` receives a `@Nullable` value and `read` may return
`null` — implementations must handle both ends.

---

## 3. Jackson 3 Streaming API

Kora 2.0 is built on **Jackson 3** (`tools.jackson.core`). Several method names differ from
Jackson 2; these are the ones Kora's own generated code uses:

| Purpose | Jackson 3 (`tools.jackson.core`) | Jackson 2 name (wrong here) |
|---|---|---|
| current / next token | `parser.currentToken()`, `parser.nextToken()` | same |
| current property name | `parser.currentName()` | `getCurrentName()` |
| read a string | `parser.getString()`, `parser.getValueAsString()` | `getText()` |
| read numbers | `getIntValue()`, `getLongValue()`, `getShortValue()`, `getFloatValue()`, `getDoubleValue()`, `getDecimalValue()`, `getBigIntegerValue()` | same |
| read base64 | `parser.getBinaryValue()` | same |
| skip a subtree | `parser.nextToken(); parser.skipChildren();` | same |
| JSON pointer of the cursor | `parser.streamReadContext().pathAsPointer()` | `getParsingContext()` |
| write a property name | `gen.writeName("field")` | `writeFieldName(...)` |
| write a value | `gen.writeString(…)`, `writeNumber(…)`, `writeBoolean(…)`, `writeNull()`, `writeBinary(…)` | same |
| write structure | `gen.writeStartObject()`, `writeEndObject()`, `writeStartArray()`, `writeEndArray()` | same |
| pass through raw JSON | `gen.writeRawValue(rawJson)` | same |
| read failure | `throw new StreamReadException(parser, "message")` (`tools.jackson.core.exc`) | `JsonParseException` |

Name + value are written as two calls (`writeName` then `writeString`), which is exactly what
the generated writers do — do not reach for Jackson 2's `writeStringField`-style helpers.

A `JsonFactory` is rarely needed: `JsonModule.JSON_FACTORY` is the pre-configured
`tools.jackson.core.json.JsonFactory` the default methods use.

---

## 4. Registering a Mapper as a Component

### As a class

```java
package com.example.json;

import io.koraframework.json.common.JsonReader;
import io.koraframework.json.common.JsonWriter;
import org.jspecify.annotations.Nullable;
import tools.jackson.core.JsonGenerator;
import tools.jackson.core.JsonParser;
import tools.jackson.core.JsonToken;
import tools.jackson.core.exc.StreamReadException;

public final class UserIdJsonCodec implements JsonReader<UserId>, JsonWriter<UserId> {

    @Override
    public @Nullable UserId read(JsonParser parser) {
        return switch (parser.currentToken()) {
            case VALUE_NULL -> null;
            case VALUE_STRING -> UserId.from(parser.getString());
            default -> throw new StreamReadException(parser, "Expected a user id string");
        };
    }

    @Override
    public void write(JsonGenerator generator, @Nullable UserId value) {
        if (value == null) {
            generator.writeNull();
        } else {
            generator.writeString(value.value());
        }
    }
}
```

### Wiring it into the graph

```java
import io.koraframework.common.annotation.Module;

@Module
public interface CustomJsonModule {

    default UserIdJsonCodec userIdJsonCodec() {   // satisfies both JsonReader<UserId> and JsonWriter<UserId>
        return new UserIdJsonCodec();
    }
}

@KoraApp
public interface Application extends JsonModule, CustomJsonModule {
    static void main(String[] args) {
        KoraApplication.run(ApplicationGraph::graph);
    }
}
```

`@Module` and `@DefaultComponent` live in **`io.koraframework.common.annotation`**.

**Plain vs `@DefaultComponent`:**

- A plain `default` factory method is an ordinary component. It **wins** over the
  `@DefaultComponent` factories in `JsonModule`, which is how you replace a built-in mapper
  (e.g. a different `LocalDate` format).
- `@DefaultComponent` marks *your* factory as the fallback, so downstream code can override
  it in turn. Do not use it to override a Kora built-in — two `@DefaultComponent` factories
  for the same type leave the graph ambiguous.

Declaring the factory as a `default` method on the `@KoraApp` interface itself works
identically and is fine for a one-off.

---

## 5. Per-Field Mappers with `@Mapping`

`io.koraframework.common.annotation.Mapping` is `@Repeatable` and targets `FIELD`, `METHOD`,
`PARAMETER`, `RECORD_COMPONENT`. Point it at a class implementing `JsonReader<T>` and/or
`JsonWriter<T>` to change the encoding of **one** field:

```java
import io.koraframework.common.annotation.Mapping;

@Json
public record JsonShowcase(
    UUID id,
    @Mapping(HexReader.class) @Mapping(HexWriter.class) Integer code
) {
    public static final class HexWriter implements JsonWriter<Integer> {
        @Override
        public void write(JsonGenerator generator, Integer value) {
            generator.writeString(Integer.toHexString(value));
        }
    }

    public static final class HexReader implements JsonReader<Integer> {
        @Override
        public Integer read(JsonParser parser) {
            if (parser.currentToken() != JsonToken.VALUE_STRING) {
                throw new StreamReadException(parser, "Expected hexadecimal string");
            }
            return Integer.parseInt(parser.getValueAsString(), 16);
        }
    }
}
```
```json
{ "id": "…", "code": "ff" }
```

**Whether the mapper has to be a DI component depends on its shape:**

- **`final` class with a no-arg constructor** → the generated mapper instantiates it inline
  (`private static final HexReader … = new HexReader();`). No `@Component` needed. Kotlin
  classes are `final` by default, so this is the usual case.
- **anything else** (non-final, or a constructor with parameters) → it becomes a constructor
  parameter of the generated mapper and must be resolvable from the graph, i.e. a
  `@Component` or a module factory. Otherwise the build fails with
  `No component found for dependency`.

Kotlin accepts `@Mapping(HexReader::class)` on the constructor parameter, or
`@field:Mapping(HexReader::class)` on the backing field — both are used in the sources.

---

## 6. Common Use Cases

### Date/time with a custom format

Overrides the built-in `LocalDate` mappers everywhere — note the plain (non-default) factory
methods:

```java
@Module
public interface DateTimeModule {

    DateTimeFormatter DDMMYYYY = DateTimeFormatter.ofPattern("dd.MM.yyyy");

    default JsonReader<LocalDate> localDateReader() {
        return parser -> switch (parser.currentToken()) {
            case VALUE_NULL -> null;
            case VALUE_STRING -> LocalDate.parse(parser.getString(), DDMMYYYY);
            default -> throw new StreamReadException(parser, "Expected a dd.MM.yyyy date string");
        };
    }

    default JsonWriter<LocalDate> localDateWriter() {
        return (generator, value) -> {
            if (value == null) {
                generator.writeNull();
            } else {
                generator.writeString(value.format(DDMMYYYY));
            }
        };
    }
}
```
```json
{ "birthDate": "15.01.1990" }
```

### An enum whose codes are not its constant names

Prefer the built-in mechanism — a `@Json`-annotated accessor — over a hand-written mapper:

```java
@Json
public enum Status {
    ACTIVE("A"), INACTIVE("I"), PENDING("P");

    private final String code;

    Status(String code) { this.code = code; }

    @Json
    public String code() { return code; }
}
```
```json
{ "status": "A" }
```

### A composite value object

```java
public final class MoneyJsonCodec implements JsonReader<Money>, JsonWriter<Money> {

    @Override
    public @Nullable Money read(JsonParser parser) {
        if (parser.currentToken() == JsonToken.VALUE_NULL) {
            return null;
        }
        if (parser.currentToken() != JsonToken.START_OBJECT) {
            throw new StreamReadException(parser, "Expected an object for Money");
        }
        BigDecimal amount = null;
        String currency = null;
        while (parser.nextToken() != JsonToken.END_OBJECT) {
            var field = parser.currentName();
            parser.nextToken();
            switch (field) {
                case "amount" -> amount = parser.getDecimalValue();
                case "currency" -> currency = parser.getString();
                default -> parser.skipChildren();
            }
        }
        if (amount == null || currency == null) {
            throw new StreamReadException(parser, "Money requires amount and currency");
        }
        return new Money(amount, Currency.getInstance(currency));
    }

    @Override
    public void write(JsonGenerator generator, @Nullable Money value) {
        if (value == null) {
            generator.writeNull();
            return;
        }
        generator.writeStartObject();
        generator.writeName("amount");
        generator.writeNumber(value.amount());
        generator.writeName("currency");
        generator.writeString(value.currency().getCurrencyCode());
        generator.writeEndObject();
    }
}
```
```json
{ "price": { "amount": 99.99, "currency": "USD" } }
```

### Base64 vs the built-in `byte[]`

`byte[]` is already written as base64 by the generated code (`writeBinary`) and read with
`getBinaryValue()`. A custom mapper is only needed for a different binary encoding (hex,
URL-safe base64, …).

---

## 7. Config-driven Readers/Writers

Drive the format from a typed `@ConfigSource` and inject it into the factory:

```java
@ConfigSource("json.date")
public interface DateFormatConfig {
    default String pattern() { return "yyyy-MM-dd"; }   // overridable via HOCON
}

@Module
public interface ConfigurableDateModule {

    default JsonReader<LocalDate> localDateReader(DateFormatConfig config) {
        var formatter = DateTimeFormatter.ofPattern(config.pattern());   // built once, per graph
        return parser -> switch (parser.currentToken()) {
            case VALUE_NULL -> null;
            case VALUE_STRING -> LocalDate.parse(parser.getString(), formatter);
            default -> throw new StreamReadException(parser, "Expected a date string");
        };
    }

    default JsonWriter<LocalDate> localDateWriter(DateFormatConfig config) {
        var formatter = DateTimeFormatter.ofPattern(config.pattern());
        return (generator, value) -> {
            if (value == null) {
                generator.writeNull();
            } else {
                generator.writeString(value.format(formatter));
            }
        };
    }
}
```

```hocon
json {
  date {
    pattern = "dd.MM.yyyy"
  }
}
```

Build the `DateTimeFormatter` **outside** the lambda — the factory runs once, the lambda runs
per value. See the `kora-config-hocon` skill for `@ConfigSource` details.

---

## 8. Kotlin Specifics

The contracts are `@NullMarked`, so the overrides must match the declared nullability
exactly:

```kotlin
import io.koraframework.json.common.JsonReader
import io.koraframework.json.common.JsonWriter
import tools.jackson.core.JsonGenerator
import tools.jackson.core.JsonParser
import tools.jackson.core.JsonToken
import tools.jackson.core.exc.StreamReadException

class HexWriter : JsonWriter<Int> {
    override fun write(generator: JsonGenerator, value: Int?) {   // value MUST be nullable
        if (value == null) generator.writeNull() else generator.writeString(value.toString(16))
    }
}

class HexReader : JsonReader<Int> {
    override fun read(parser: JsonParser): Int {                  // narrowing the return to non-null is allowed
        if (parser.currentToken() != JsonToken.VALUE_STRING) {
            throw StreamReadException(parser, "Expected hexadecimal string")
        }
        return parser.valueAsString.toInt(16)
    }
}
```

Declaring `value: Int` instead of `Int?` produces `'write' overrides nothing` — a message
that says nothing about nullability. In a module:

```kotlin
@Module
interface CustomJsonModule {
    fun hexWriter(): JsonWriter<Int> = HexWriter()
    fun hexReader(): JsonReader<Int> = HexReader()
}
```

---

## 9. Testing Custom Mappers

Use the interface's own `default` methods instead of building a `JsonFactory` by hand:

```java
class UserIdJsonCodecTest {

    private final UserIdJsonCodec codec = new UserIdJsonCodec();

    @Test
    void readsValidId() {
        assertThat(codec.read("\"usr_123456\"")).isEqualTo(UserId.from("usr_123456"));
    }

    @Test
    void rejectsNonString() {
        assertThatThrownBy(() -> codec.read("42"))
            .isInstanceOf(StreamReadException.class);
    }

    @Test
    void writesString() {
        assertThat(codec.toString(UserId.from("usr_123456"))).isEqualTo("\"usr_123456\"");
    }

    @Test
    void writesNull() {
        assertThat(codec.toString(null)).isEqualTo("null");
    }
}
```

To test a mapper as it is actually wired, pull `JsonReader<T>`/`JsonWriter<T>` out of the
graph with `@KoraAppTest` + `@TestComponent` — see
[json-best-practices.md](json-best-practices.md#82-round-trip-test).

---

## 10. Best Practices

### Handle `null` at both ends

```java
// GOOD
@Override
public void write(JsonGenerator generator, @Nullable UserId value) {
    if (value == null) {
        generator.writeNull();
    } else {
        generator.writeString(value.value());
    }
}

// BAD — the contract passes null; this NPEs on a null field
@Override
public void write(JsonGenerator generator, @Nullable UserId value) {
    generator.writeString(value.value());
}
```

Readers should return `null` for `JsonToken.VALUE_NULL` rather than throwing — that is what
every built-in reader in `JsonModule` does.

### Fail with a locatable message

`StreamReadException(parser, message)` carries the parser location. Match the built-in
readers, which say what was expected, what arrived and where — the JSON Pointer from
`parser.streamReadContext().pathAsPointer()`, `<root>` when it is empty:

```java
var path = parser.streamReadContext().pathAsPointer().toString();
throw new StreamReadException(parser, "Failed to read json Money: expected a string, but got "
    + parser.currentToken() + " (at " + (path.isEmpty() ? "<root>" : path) + ")");
```

The built-in and generated readers all use the `Failed to read json …: expected …, but got …
(at /pointer)` shape, so a custom reader written this way reads the same in logs.

### Do not re-position the parser

`read(JsonParser)` is called with the parser already on the value's first token, and must
leave it on that value's **last** token — `skipChildren()` after `nextToken()` is the safe
way to discard an unknown subtree.

### Keep formatters and lookups out of the hot path

Build `DateTimeFormatter`s, tables and regexes once, in the factory method or as a `static
final` field, never inside `read`/`write`.

---

## 11. Quick Reference

### Reader template

```java
public final class CustomReader implements JsonReader<CustomType> {
    @Override
    public @Nullable CustomType read(JsonParser parser) {
        return switch (parser.currentToken()) {
            case VALUE_NULL -> null;
            case VALUE_STRING -> CustomType.from(parser.getString());
            default -> throw new StreamReadException(parser, "Expected a CustomType string");
        };
    }
}
```

### Writer template

```java
public final class CustomWriter implements JsonWriter<CustomType> {
    @Override
    public void write(JsonGenerator generator, @Nullable CustomType value) {
        if (value == null) {
            generator.writeNull();
        } else {
            generator.writeString(value.toString());
        }
    }
}
```

### Module registration

```java
@Module
public interface CustomJsonModule {
    default JsonReader<CustomType> customTypeReader() { return new CustomReader(); }
    default JsonWriter<CustomType> customTypeWriter() { return new CustomWriter(); }
}
```

### Per-field

```java
@Json
public record Dto(@Mapping(CustomReader.class) @Mapping(CustomWriter.class) CustomType value) {}
```
