# JSON DTO Reference (Kora 2.x)

Verified against the Kora 2.0 sources — [`json/json-common`](https://github.com/kora-projects/kora/tree/2.0.0.RC2/json/json-common)
and the `json-annotation-processor` / `json-symbol-processor` test suites.

## Contents

1. [Overview](#1-overview)
2. [Core annotations](#2-core-annotations)
3. [Supported shapes](#3-supported-shapes)
4. [Field configuration](#4-field-configuration)
5. [Naming strategy](#5-naming-strategy)
6. [JsonNullable — missing vs null](#6-jsonnullable--missing-vs-null)
7. [Enum serialization](#7-enum-serialization)
8. [Built-in supported types](#8-built-in-supported-types)
9. [RawJson](#9-rawjson)
10. [Using the generated mappers directly](#10-using-the-generated-mappers-directly)
11. [Quick reference](#11-quick-reference)

---

## 1. Overview

Kora JSON is **compile-time** (de)serialization without reflection:

- **Code generation** — `<Type>JsonReader` / `<Type>JsonWriter` classes are generated next
  to the annotated type at build time (nested types flatten to `Outer_Inner_JsonReader`).
- **Zero reflection** — nothing is discovered at runtime; the generated classes are ordinary
  components in the DI graph.
- **Type-safe** — an unsupported shape fails the build, not a production request.
- **Synchronous** — Kora 2.0 has no reactive/`suspend` JSON contracts.

Package map:

| Purpose | Package |
|---|---|
| Annotations | `io.koraframework.json.common.annotation` |
| Runtime contracts (`JsonReader`, `JsonWriter`, `JsonNullable`, `RawJson`, `JsonModule`) | `io.koraframework.json.common` |
| Jackson 3 streaming types (`JsonParser`, `JsonGenerator`, `JsonToken`, `StreamReadException`) | `tools.jackson.core` |
| Nullability | `org.jspecify.annotations.Nullable` |

---

## 2. Core Annotations

### `@Json` — reader + writer

```java
import io.koraframework.json.common.annotation.Json;

@Json
public record UserDto(String id, String name, String email) {}
```

**What it does:**
- Generates `JsonReader<UserDto>` for deserialization
- Generates `JsonWriter<UserDto>` for serialization
- Both become components in the DI graph
- On a controller method/parameter it marks the HTTP body as JSON — `@Json` is
  meta-annotated `@Tag(Json.class)`, so it also carries that tag to the dependency

**Kotlin:**
```kotlin
@Json
data class UserDto(val id: String, val name: String, val email: String)
```

### `@JsonReader` — deserialization only

Targets `TYPE`, `CONSTRUCTOR`, `METHOD`.

```java
@JsonReader
public record ImportRequest(String source, LocalDateTime timestamp) {}
```

On a **constructor** it selects which constructor the generated reader uses:

```kotlin
@Json
data class KotlinDto(val field1: String, val field2: String?) {
    @JsonReader
    constructor(field1: String) : this(field1, null)
}
```

### `@JsonWriter` — serialization only

Targets `TYPE`, `METHOD`.

```java
@JsonWriter
public record ExportResponse(String report, int totalRecords) {}
```

### Single-value types

`@JsonReader` on a **`public static` factory method** `(V) -> T` plus `@JsonWriter` on a method
returning `V` — an instance method `() -> V` or a static `(T) -> V` — makes a non-enum type read and
write as a single JSON value (Jackson's `@JsonCreator(mode = DELEGATING)` + `@JsonValue`). The
generated reader/writer delegate to `JsonReader<V>` / `JsonWriter<V>` from the graph. Proven by
`DelegatingValueTest` in both processors.

```java
public record UserId(long id) {
    @JsonReader public static UserId of(long v) { return new UserId(v); }
    @JsonWriter public long id() { return id; }                      // UserId(42) <-> 42
}

public record Sku(String code) {
    @JsonReader public static Sku parse(String v) { return new Sku(v); }
    @JsonWriter public static String toJson(Sku sku) { return sku.code(); }   // static form
}
```

```kotlin
class UserId(val id: Long) {
    @JsonWriter fun toJson(): Long = id
    companion object { @JsonReader fun of(v: Long): UserId = UserId(v) }
}
```

- Kotlin: the factory is declared in the `companion object`.
- A factory that is not `public static` fails with `@JsonReader factory method must be public static`;
  an annotated method outside a class fails with
  `@JsonReader on a method is supported only for a static factory method of a class or enum`.
- A `null` value is written as JSON `null`.
- Enums keep their own mechanism — a `@Json` accessor (see [Enum Serialization](#7-enum-serialization)).

> **Import collision:** `io.koraframework.json.common.annotation.JsonReader` (annotation) and
> `io.koraframework.json.common.JsonReader` (runtime contract) share a simple name. In a file
> that needs both, fully-qualify one of them — the migrated Kotlin example does exactly this.

---

## 3. Supported Shapes

| Shape | Reader | Writer |
|---|---|---|
| Java `record` | yes | yes |
| Kotlin `data class` | yes | yes |
| Concrete Java/Kotlin class with a single public constructor | yes | yes (needs accessors) |
| Java bean (fields + getters, no-arg + full constructor) | yes | yes |
| `enum` | yes | yes |
| `sealed interface` / `sealed abstract class` | yes (via discriminator) | yes |
| `interface`, `abstract class`, annotation, array | **no** — supply a custom component |

Reader constructor rules (`ReaderTypeMetaParser`):

- exactly one public constructor → used automatically;
- several public constructors → mark exactly one with `@JsonReader` or `@Json`, otherwise:

```
JsonReader can't choose a constructor for type:
  com.example.Dto

Problem:
  There are multiple possible public constructors and none is selected explicitly.
```

Writer accessor rules (`WriterTypeMetaParser`): every non-skipped field needs a
zero-argument `field()` or `getField()` returning the field's type, otherwise:

```
JsonWriter can't find an accessor for field:
  com.example.Dto.field1
```

---

## 4. Field Configuration

### Required vs optional

**Required (default):**
```java
@Json
public record UserRequest(String name, String email) {}
```

**Optional with JSpecify `@Nullable`:**
```java
import org.jspecify.annotations.Nullable;

@Json
public record UserUpdateRequest(
    String id,                       // required
    @Nullable String name,           // optional
    java.util.@Nullable List<String> tags   // type-use: annotation sits before the simple name
) {}
```

JSpecify annotations are **type-use**. On a qualified or nested type they must sit
immediately before the simple name (`java.util.@Nullable List<…>`, `Outer.@Nullable Inner`),
otherwise javac rejects them with
`type annotation @org.jspecify.annotations.Nullable is not expected here`.

**Kotlin — the type carries nullability; do not port Java annotations:**
```kotlin
@Json
data class UserUpdateRequest(
    val id: String,          // required
    val name: String?,       // optional
    val email: String?       // optional
)
```

### `@JsonField` — rename fields

```java
@Json
public record ApiRequest(
    @JsonField("user_id") String userId,
    @JsonField("first_name") String firstName
) {}
```
```json
{ "user_id": "123", "first_name": "John" }
```

Kotlin accepts the annotation with or without a use-site target — `@JsonField`,
`@field:JsonField`, `@property:JsonField` and `@param:JsonField` all resolve (all four are
covered by `JsonFieldTest`):

```kotlin
@Json
data class ApiRequest(@JsonField("user_id") val userId: String)
```

### `@JsonSkip` — ignore fields

Targets `FIELD` only (which still allows it on a Java record component and on a Kotlin
constructor `val`).

```java
@Json
public record InternalDto(
    String publicField,
    @JsonSkip String internalField   // never written, never read
) {}
```

```kotlin
@Json
data class InternalDto(val publicField: String, @field:JsonSkip val internalField: String)
```

### `@JsonInclude` — control what is written

Targets `TYPE` and `FIELD`; `value()` defaults to `NON_NULL`.

```java
@Json
@JsonInclude(IncludeType.NON_NULL)                 // type-level default
public record Response(
    String id,
    @JsonInclude(IncludeType.ALWAYS) @Nullable String optionalField   // per-field override
) {}
```

| `IncludeType` | Behaviour |
|------|-----------|
| `ALWAYS` | always written, `null` included (does not affect `JsonNullable`) |
| `NON_NULL` | skipped when `null` (default; does not affect `JsonNullable`) |
| `NON_EMPTY` | skipped when `null` **or** empty; applies to `JsonNullable` too |

`NON_EMPTY` only works where the processor can see a `Collection` or `Map` type at compile
time — on a generic type parameter the emptiness check cannot be applied.

---

## 5. Naming Strategy

To rename every field at once, use `@NamingStrategy` from
`io.koraframework.common.annotation` with a converter from `io.koraframework.common.naming`:

```java
import io.koraframework.common.annotation.NamingStrategy;
import io.koraframework.common.naming.SnakeCaseNameConverter;

@Json
@NamingStrategy(SnakeCaseNameConverter.class)
public record DtoWithSnakeCaseNaming(String stringField, Integer integerField) {}
```
```json
{ "string_field": "…", "integer_field": 1 }
```

Available converters: `CamelCaseNameConverter`, `PascalCaseNameConverter`,
`SnakeCaseNameConverter`, `SnakeCaseUpperNameConverter`, `NoopNameConverter`.
An explicit `@JsonField("…")` on a field wins over the strategy. A bare `@JsonField`
(no value) does **not** fall back to the strategy — it pins the plain field name.

---

## 6. JsonNullable — Missing vs Null

`io.koraframework.json.common.JsonNullable<T>` distinguishes a field absent from the JSON
from a field explicitly set to `null`. Use it for PATCH endpoints where "do not touch" and
"clear the value" are different intents.

```java
@Json
public record PatchRequest(
    String id,
    JsonNullable<String> name,
    JsonNullable<String> email
) {}
```

**API:**

| Member | Meaning |
|--------|---------|
| `isDefined()` | the field was present in the JSON (its value may still be `null`) |
| `isNull()` | the field was present and its value is explicitly `null` |
| `value()` | the contained value (`null` when `isNull()`; throws when undefined) |

Factories: `JsonNullable.of(v)` (rejects `null`), `JsonNullable.ofNullable(v)`,
`JsonNullable.nullValue()`, `JsonNullable.undefined()`.
`JsonNullable` is a `sealed interface` with the records `Defined<T>` and `Undefined<T>`.

**Three states** for a `JsonNullable<String>` field:

| JSON | `isDefined()` | `isNull()` | `value()` |
|------|---------------|------------|-----------|
| `"name": "John"` | `true` | `false` | `"John"` |
| `"name": null`   | `true` | `true`  | `null` |
| field omitted    | `false`| `false` | throws `NullPointerException` |

**Writing:** `JsonNullable.undefined()` is omitted from the output entirely, regardless of
`@JsonInclude(ALWAYS)`; `JsonNullable.nullValue()` is written as `null`.

```java
jsonWriter.toString(new Example(
    JsonNullable.of("Interstellar"),
    JsonNullable.nullValue(),
    JsonNullable.undefined()));
// → { "definedNonNull": "Interstellar", "definedNull": null }
```

**Usage in PATCH:**
```java
@HttpRoute(method = HttpMethod.PATCH, path = "/users/{id}")
@Json
public UserResponse updateUser(@Path String id, @Json PatchRequest request) {
    var user = userService.findById(id);
    if (request.name().isDefined()) {          // present in JSON
        user.setName(request.name().value());  // value() is null when isNull() is true
    }
    // field omitted → isDefined() == false → leave the property untouched
    return userService.update(user);
}
```

---

## 7. Enum Serialization

The generated enum mapper picks a **value accessor**:

1. the first **public, non-static, zero-argument method annotated `@Json`**, whose return
   type becomes the JSON value type; otherwise
2. `toString()` — i.e. `name()` unless overridden.

Reading matches the parsed value against `values()` through the same accessor.

**Default — the constant name:**
```java
@Json
public enum OrderStatus { PENDING, PROCESSING, SHIPPED }
```
```json
"PENDING"
```

**Custom string via `toString()`:**
```java
@Json
public enum OrderStatus {
    PENDING("pending"), PROCESSING("processing"), SHIPPED("shipped");

    private final String value;

    OrderStatus(String value) { this.value = value; }

    @Override
    public String toString() { return value; }
}
```
```json
"pending"
```

**Non-string value via a `@Json` accessor:**
```java
@Json
public enum Status {
    CREATED(1), DELETED(2);

    private final int code;

    Status(int code) { this.code = code; }

    @Json
    public int code() { return this.code; }
}
```
```json
1
```

```kotlin
@Json
enum class Status(private val code: Int) {
    CREATED(1), DELETED(2);

    @Json
    fun code(): Int = code
}
```

No `fromString`/`valueOf` helper is needed or used — the generated reader does the lookup.

---

## 8. Built-in Supported Types

Written inline by the generated code (`KnownType`): `String`, `boolean`/`Boolean`,
`short`/`Short`, `int`/`Integer`, `long`/`Long`, `float`/`Float`, `double`/`Double`,
`BigInteger`, `byte[]` (base64 via `writeBinary`), `UUID`.

Supplied as `@DefaultComponent` mappers by `JsonModule` (override any of them by declaring
your own non-default component of the same type):

| Category | Types |
|---|---|
| Scalars | `Short`, `Integer`, `Long`, `Float`, `Double`, `String`, `Boolean`, `BigDecimal`, `BigInteger`, `UUID` |
| Collections | `List<T>`, `Set<T>`, `SortedSet<T>` (reader), `Map<String, T>` |
| Free-form | `Object` (reads/writes arbitrary JSON), `RawJson` (writer) |
| Date/time | `LocalDate`, `LocalTime`, `LocalDateTime`, `OffsetTime`, `OffsetDateTime`, `ZonedDateTime`, `Instant`, `Year`, `YearMonth`, `MonthDay`, `Month`, `DayOfWeek`, `ZoneId`, `Duration` |
| Enums | any `@Json` enum |

Date/time formats are ISO-8601 with flexible fractional-second precision on read.
`Month` and `DayOfWeek` accept either the name (case-insensitive) or the ordinal number.

Anything else — `Period`, `Currency`, `Optional`, `char`/`Character`, `byte`/`Byte`, your own
value types — needs a custom `JsonReader`/`JsonWriter`; see
[json-custom-mapper-reference.md](json-custom-mapper-reference.md).

---

## 9. RawJson

`io.koraframework.json.common.RawJson` carries already-encoded JSON and is written through
untouched (writer only — `JsonModule` supplies `JsonWriter<RawJson>`, no reader):

```java
@JsonWriter
public record RawPayload(String id, RawJson payload) {}

writer.toString(new RawPayload("1", new RawJson("{\"trusted\":true}")));
// → {"id":"1","payload":{"trusted":true}}
```

`RawJson` supports only unquoted write operations; asking it to quote throws
`UnsupportedOperationException`. Never build one from untrusted input — its content is
emitted verbatim into the output document.

---

## 10. Using the Generated Mappers Directly

Inject `JsonReader<T>` / `JsonWriter<T>` like any other component:

```java
@Component
public final class EventCodec {
    private final JsonWriter<Event> writer;
    private final JsonReader<Event> reader;

    public EventCodec(JsonWriter<Event> writer, JsonReader<Event> reader) {
        this.writer = writer;
        this.reader = reader;
    }

    public byte[] encode(Event event) {
        return writer.toByteArray(event);   // no checked exception — do not wrap in try/catch (IOException)
    }

    public Event decode(byte[] body) {
        var event = reader.read(body);      // @Nullable — "null" input decodes to null
        if (event == null) {
            throw new IllegalArgumentException("empty event body");
        }
        return event;
    }
}
```

```kotlin
@Component
class EventCodec(private val writer: JsonWriter<Event>, private val reader: JsonReader<Event>) {
    fun encode(event: Event): ByteArray = writer.toByteArray(event)
    fun decode(body: ByteArray): Event = requireNotNull(reader.read(body))
}
```

`toPrettyString(value)` is available when a human-readable dump is wanted.

---

## 11. Quick Reference

### Annotation summary

| Annotation | Purpose |
|------------|---------|
| `@Json` | reader + writer; marks an HTTP body; selects an enum value accessor |
| `@JsonReader` | deserialization only; also selects a constructor |
| `@JsonWriter` | serialization only |
| `@JsonField("name")` | rename a JSON field |
| `@JsonSkip` | ignore a field on read and write |
| `@JsonInclude(IncludeType.X)` | `ALWAYS` / `NON_NULL` / `NON_EMPTY` |
| `@NamingStrategy(X.class)` | rename all fields by convention |
| `@Mapping(X.class)` | per-field custom reader/writer |
| `@Nullable` (JSpecify) | optional field |
| `JsonNullable<T>` | distinguish missing vs explicit null |

### Common patterns

```java
// Basic DTO
@Json public record UserDto(String id, String name) {}

// Optional fields
@Json public record UpdateRequest(String id, @Nullable String name) {}

// Renamed fields
@Json public record ApiRequest(@JsonField("user_id") String userId) {}

// PATCH DTO
@Json public record PatchRequest(String id, JsonNullable<String> name) {}

// Enum
@Json public enum Status { PENDING, SHIPPED }
```
