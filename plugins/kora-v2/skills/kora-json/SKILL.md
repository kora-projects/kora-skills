---
name: kora-json
description: "Compile-time JSON in Kora 2.x — @Json generates io.koraframework.json.common.JsonReader/JsonWriter for records and data classes at build time. Covers artifact json-common, the JsonModule graph module, sealed-type discriminators (@JsonDiscriminatorField/@JsonDiscriminatorValue), @JsonField/@JsonSkip/@JsonInclude, JsonNullable, RawJson, @NamingStrategy, custom JsonReader/JsonWriter factories and @Mapping, and swapping HTTP bodies onto Jackson 3 via JacksonModule (tools.jackson). Use for HTTP DTOs, Kafka payloads, polymorphic JSON, or \"JsonReader not found\" graph errors."
license: Apache-2.0
metadata:
  kora-version: "2.x"
---

# Kora JSON — compile-time JSON processing

> **Kora sub-skill — obey the [kora-v2 meta rules](../../SKILL.md) on every task:** **R0** ground the workspace on Kora 2.0 refs before starting (framework source at tag `2.0.0.RC2` + `kora-examples` at `migration/2.0` + Kora 2.0 docs at koraframework.io/v2, which trail the source; 1.x `kora-docs` pages are never an authority) · **R1** read this sub-skill before writing code · **R2** Kora 2.0 APIs only — no Spring/Micronaut/Quarkus, no Kora 1.x APIs, no invented annotations or config keys · **R3** journal any incorrect Kora usage. Add comments/Javadoc only if asked.

**Version:** Kora 2.0 (`io.koraframework`, `2.0.0.RC2` on Maven Central) | **Java:** 25 | **Kotlin:** 2.4.20 + KSP 2.3.12 | **Gradle:** 9.8.0

Kora generates `JsonReader<T>` / `JsonWriter<T>` at compile time from `@Json`-annotated
records (Java) or data classes (Kotlin). No reflection, no runtime mapper discovery: an
unsupported shape fails the build instead of throwing at runtime. Put `@Json` on the DTO
type itself, not only on the controller parameter — that lets the mapper be generated
during normal annotation processing and reused across HTTP bodies, cache values and Kafka
payloads.

The runtime is built on **Jackson 3 streaming** (`tools.jackson.core`), which `json-common`
exposes as an `api` dependency. Kora 2.0 JSON contracts are **synchronous** — there are no
`Mono`/`Flux`/`CompletionStage`/`suspend` reader or writer variants.

## Migrating from Kora 1.x

| Kora 1.x | Kora 2.x |
|---|---|
| artifact `ru.tinkoff.kora:json-module` | **`io.koraframework:json-common`** |
| BOM `ru.tinkoff.kora:kora-parent` | **`io.koraframework:kora-bom`** |
| `ru.tinkoff.kora.json.module.JsonModule` | **`io.koraframework.json.common.JsonModule`** |
| `JsonCommonModule` | **`JsonModule`** (only one module interface exists) |
| `ru.tinkoff.kora.json.common.*` | `io.koraframework.json.common.*` |
| `writer.toStringUnchecked(v)` | **`writer.toString(v)`** |
| `writer.toByteArrayUnchecked(v)` | **`writer.toByteArray(v)`** |
| `reader.readUnchecked(v)` | **`reader.read(v)`** |
| `com.fasterxml.jackson.core.*` | **`tools.jackson.core.*`** (Jackson 3) |

Two consequences that a package rename alone will not fix:

- **`toByteArray` / `toString` declare no checked exception.** They declare only
  `throws tools.jackson.core.JacksonException`, which is unchecked. Java code that wrapped them
  in `try { … } catch (IOException e)` now fails to compile with
  `error: exception IOException is never thrown in body of corresponding try statement`.
  Delete the `catch` block and the `import java.io.IOException;`.
- **`JsonReader<T>.read(...)` is annotated `@Nullable`.** Kotlin cannot assign the result to
  a non-null type: use `requireNotNull(reader.read(data))` (or `!!`).

## Quick Start

`gradle.properties` — pin the released **`2.0.0.RC2`** from Maven Central. `2.0.0-SNAPSHOT` is
the development line and needs the snapshot repository; do not put it in a new project.

```properties
koraVersion=2.0.0.RC2
```

`build.gradle` — plain `mavenCentral()`; all Kora artifacts inherit their version from the
`kora-bom` platform, so never pin an individual `io.koraframework:*` version:

```groovy
repositories {
    mavenCentral()
}

configurations {
    koraBom
    annotationProcessor.extendsFrom(koraBom)
    implementation.extendsFrom(koraBom)
}

dependencies {
    koraBom platform("io.koraframework:kora-bom:$koraVersion")

    annotationProcessor "io.koraframework:annotation-processors" // mandatory: generates readers/writers
    implementation "io.koraframework:json-common"
}
```

Kotlin uses KSP instead: `ksp("io.koraframework:symbol-processors:${property("koraVersion")}")`.

Declare `json-common` explicitly in every Gradle module that uses `@Json`, as the migrated
guides do. It does reach the compile classpath transitively when the HTTP server is present
(`http-server-undertow` → `api logging-common` → `api json-common`), but relying on that
edge means a direct dependency is invisible in your build file.

Wire the module into the application graph:

```java
@KoraApp
public interface Application extends JsonModule {   // io.koraframework.json.common.JsonModule
    static void main(String[] args) {
        KoraApplication.run(ApplicationGraph::graph);
    }
}
```

Define DTOs and a controller (adapted from `kora-java-guide-json-app`):

```java
import io.koraframework.json.common.annotation.Json;

@Json
public record UserRequest(String name, String email) {}

@Json
public record UserResponse(String id, String name, String email, LocalDateTime createdAt) {}

@Component
@HttpController
public final class UserController {

    private final UserService userService;

    public UserController(UserService userService) {
        this.userService = userService;
    }

    @HttpRoute(method = HttpMethod.POST, path = "/users")
    @Json
    public UserResponse createUser(@Json UserRequest request) {
        return userService.createUser(request);
    }
}
```

`@Json` on the method marks the response body as JSON; `@Json` on the parameter marks the
request body. `@Json` is meta-annotated `@Tag(Json.class)`, so those bodies resolve to the
`@Json`-tagged `HttpServerRequestMapper`/`HttpServerResponseMapper` supplied by the HTTP
module, which in turn needs the generated `JsonReader`/`JsonWriter` in the graph.

---

Use this skill when:
- creating DTO records/data classes for HTTP request/response bodies with `@Json`,
- implementing polymorphic JSON with sealed types and `@JsonDiscriminatorField`,
- registering a custom `JsonReader`/`JsonWriter` factory, or a per-field one with `@Mapping`,
- handling optional fields with `@Nullable`, or distinguishing missing vs null with `JsonNullable`,
- routing HTTP JSON bodies through a Jackson 3 `ObjectMapper` via `JacksonModule`.

---

## Assets (Templates)

| Template | Purpose |
|----------|---------|
| `dto.java.template` | DTO record with `@Json`, JSpecify `@Nullable`, `@JsonField`/`@JsonSkip` |
| `dto.kt.template` | Kotlin data class with `@Json` and nullable types |
| `enum.java.template` | Enum with `@Json`, custom value via `toString()` or a `@Json` accessor |
| `enum.kt.template` | Kotlin enum equivalent |
| `sealed-dto.java.template` | Sealed interface with `@JsonDiscriminatorField` |
| `sealed-dto.kt.template` | Kotlin sealed interface |
| `sealed-dto-impl.java.template` | Sealed subtype with `@Json` + `@JsonDiscriminatorValue` |
| `sealed-dto-impl.kt.template` | Kotlin sealed subtype |
| `custom-mapper.java.template` | `@Module` with custom `JsonReader`/`JsonWriter` factories |
| `custom-mapper.kt.template` | Kotlin custom mapper module |

**Usage:** copy the template, replace placeholders (`${package}`, `${entity_name}`, …).

---

## Quick Reference

### Core annotations — `io.koraframework.json.common.annotation`

```java
@Json                       // Reader + Writer; also marks HTTP bodies (meta @Tag(Json.class))
@JsonReader                 // Deserialization only (TYPE, CONSTRUCTOR, METHOD)
@JsonWriter                 // Serialization only (TYPE, METHOD)
@JsonField("user_id")       // Rename a field in JSON
@JsonSkip                   // Ignore field on read and write
@JsonInclude(IncludeType.X) // ALWAYS / NON_NULL (default) / NON_EMPTY
@JsonDiscriminatorField("type")            // on the sealed supertype; optional defaultValue
@JsonDiscriminatorValue({"A", "B"})        // on a subtype; defaults to the subtype simple name
```

Runtime types live in `io.koraframework.json.common`: `JsonReader`, `JsonWriter`,
`JsonNullable`, `RawJson`, `JsonModule`.
Nullability is JSpecify `org.jspecify.annotations.Nullable` in Java (type-use — position
matters: `java.util.@Nullable List<String>`) and a nullable type `T?` in Kotlin.
Field naming can be driven wholesale by `@NamingStrategy(SnakeCaseNameConverter.class)`
from `io.koraframework.common.annotation` / `io.koraframework.common.naming`.

### Runtime contracts (verbatim signatures)

```java
public interface JsonWriter<T> extends Mapping.MappingFunction {
    void write(JsonGenerator generator, @Nullable T object) throws JacksonException;
    default byte[] toByteArray(@Nullable T value) throws JacksonException;
    default String toString(@Nullable T value) throws JacksonException;
    default String toPrettyString(@Nullable T value) throws JacksonException;
}

public interface JsonReader<T> extends Mapping.MappingFunction {
    @Nullable T read(JsonParser parser) throws JacksonException;
    @Nullable default T read(byte[] bytes) throws JacksonException;
    @Nullable default T read(byte[] bytes, int offset, int length) throws JacksonException;
    @Nullable default T read(String str) throws JacksonException;
    @Nullable default T read(InputStream is) throws JacksonException;
}
```

`tools.jackson.core.JacksonException` is **unchecked**, so callers need no `try/catch` and an
implementation may omit the clause (Kora's own `RawJsonWriter.write` and `ListJsonReader.read`
do). No method declares `IOException`.

### Parse errors

Every generated reader and built-in `JsonModule` reader fails with a
`tools.jackson.core.exc.StreamReadException` whose message starts `Failed to read json` and ends
with the JSON Pointer of the failing value (`(at /items/0/price)`, `<root>` for the top level):

| Situation | Message shape |
|---|---|
| wrong token for a field | `Failed to read json Order.quantity: expected an integer number, but got a string "abc" (at /quantity)` |
| required field absent | `Failed to read json Order: missing required field(s): id, quantity (at …)` |
| non-nullable field is JSON `null` | `Failed to read json Order.id: required field must not be null (at /id)` |
| wrong scalar in a built-in reader | `Failed to read json: expected an integer number, but got a boolean true (at /count)` |
| unknown enum value | `Failed to read json enum: expected one of [NEW, PAID], but got "SENT" (at /status)` |
| sealed type, discriminator missing | `Failed to read json Payment: missing required discriminator field "type", expected one of [CARD, CASH] (at …)` |
| sealed type, unknown discriminator | `Failed to read json Payment: unknown discriminator value "WIRE" for field "type", expected one of [CARD, CASH] (at …)` |

String values over 128 characters are truncated in the message. Map `StreamReadException` to a
`400` in an HTTP error handler; do not parse the message text, it is diagnostic.

### Single-value types — `@JsonReader` factory / `@JsonWriter` method

A non-enum type can serialize as **one JSON value** instead of an object (Jackson's
`@JsonCreator(mode = DELEGATING)` + `@JsonValue`): annotate a `public static` factory
`(V) -> T` with `@JsonReader` and a method producing `V` with `@JsonWriter` — an instance
method `() -> V` or a static one `(T) -> V`. The generated reader/writer delegate to the
`JsonReader<V>` / `JsonWriter<V>` for the value type.

```java
public record UserId(long id) {
    @JsonReader public static UserId of(long v) { return new UserId(v); }
    @JsonWriter public long id() { return id; }
}
// UserId(42) <-> 42
```

```kotlin
class Sku(val code: String) {
    @JsonWriter fun toJson(): String = code
    companion object { @JsonReader fun parse(v: String): Sku = Sku(v) }
}
// Sku("ABC") <-> "ABC"
```

In Kotlin the factory lives in the `companion object`. A non-`public static` factory fails with
`@JsonReader factory method must be public static`. For enums use the `@Json` accessor instead
([Enum serialization](#enum-serialization)).

### Sealed interfaces

```java
@Json
@JsonDiscriminatorField("type")
public sealed interface Result permits Success, Error {}

@Json
@JsonDiscriminatorValue("SUCCESS")
public record Success(String data) implements Result {}

@Json
@JsonDiscriminatorValue("ERROR")
public record Error(String code) implements Result {}
```

```json
{ "type": "SUCCESS", "data": "..." }
{ "type": "ERROR", "code": "NOT_FOUND" }
```

Every subtype needs its own `@Json` (or `@JsonReader`/`@JsonWriter`) — the generated sealed
mapper is wired from the per-subtype mappers. `@JsonDiscriminatorValue` is optional; without
it the discriminator value is the subtype's **simple name**. The discriminator does **not**
have to be a record component: the generated writer emits it, and the generated reader
tolerates it appearing anywhere in the object.

### Enum serialization

```java
@Json
public enum Status { PENDING, PROCESSING, SHIPPED }   // → "PENDING", "PROCESSING", "SHIPPED"
```

The value accessor defaults to `toString()` (i.e. `name()`). A **public, non-static,
zero-argument method annotated `@Json`** overrides it and its return type becomes the JSON
value type:

```java
@Json
public enum Status {
    CREATED(1), DELETED(2);
    private final int code;
    Status(int code) { this.code = code; }
    @Json public int code() { return this.code; }     // → 1, 2
}
```

### Controller pattern

```java
@Component
@HttpController
public final class ApiController {
    @HttpRoute(method = HttpMethod.POST, path = "/items")
    @Json
    public ItemResponse create(@Json ItemRequest request) { ... }

    @HttpRoute(method = HttpMethod.GET, path = "/items")
    @Json
    public List<ItemResponse> getAll() { ... }
}
```

---

## JsonNullable — missing vs null (PATCH)

`JsonNullable<T>` distinguishes a field absent from the JSON from a field explicitly `null`.
Its API is `isDefined()`, `isNull()`, `value()` plus the factories `JsonNullable.of(v)`,
`JsonNullable.ofNullable(v)`, `JsonNullable.nullValue()`, `JsonNullable.undefined()`:

```java
@Json
public record PatchUserRequest(JsonNullable<String> name, JsonNullable<String> email) {}

if (request.name().isDefined()) {          // field present in JSON (value may be null)
    user.setName(request.name().value());  // value() returns null when isNull() is true
}
// undefined field → isDefined() == false → leave the property untouched
```

`JsonNullable.undefined()` is omitted from the output entirely, and `@JsonInclude(ALWAYS)`
and `NON_NULL` do not change that. See
[json-dto-reference.md](references/json-dto-reference.md) for the full state table.

---

## Troubleshooting

| Problem | Cause / fix |
|---|---|
| `No component found for dependency io.koraframework.json.common.JsonReader<X>` | Add `@Json` (or `@JsonReader`) to `X`, and make sure the `@KoraApp` extends `JsonModule` |
| `exception IOException is never thrown in body of corresponding try statement` | 1.x leftover: remove the `try/catch (IOException)` around `toByteArray`/`toString` and the `IOException` import |
| Kotlin: `Type mismatch: inferred type is X? but X was expected` on `reader.read(...)` | `read` returns `@Nullable T` — wrap in `requireNotNull(...)` |
| `JsonReader can't be generated for type / for abstract type` | `@Json` is on an interface, enum-like abstract class or annotation. Move it to a concrete class/record, or supply a custom `JsonReader<T>` component |
| `JsonReader can't choose a constructor for type` | Keep a single public constructor, or mark exactly one with `@JsonReader`/`@Json` |
| `JsonWriter can't find an accessor for field` | Java bean field has no `field()`/`getField()` accessor — add one, or exclude the field with `@JsonSkip` |
| `Json discriminator value can't be empty` | `@JsonDiscriminatorValue({})` — supply at least one value or drop the annotation |
| `Failed to read json X: missing required field(s): …` | Fields are required by default — mark them `@Nullable` (Kotlin: `T?`), or send the field |
| `Failed to read json X: unknown discriminator value "…" for field "…"` | The payload's discriminator matches no `@JsonDiscriminatorValue` (or subtype simple name); the message lists the accepted values. Add the value, or set `@JsonDiscriminatorField(defaultValue = …)` only for a missing field |
| `Failed to read json …: expected …, but got … (at /path)` | The value at that JSON Pointer has the wrong JSON type for the field |
| Phantom `ru.tinkoff.kora` errors after the rename | Stale generated sources: `./gradlew clean` + `--no-build-cache`; never edit `build/generated` |
| Jackson types do not resolve | Kora 2.0 uses **Jackson 3** under group `tools.jackson.core`, not `com.fasterxml.jackson.core` |

---

## Reference Files

| File | Description |
|------|-------------|
| [json-dto-reference.md](references/json-dto-reference.md) | DTOs, records/data classes, field config, JsonNullable, enums, supported types |
| [json-sealed-reference.md](references/json-sealed-reference.md) | Sealed hierarchies, discriminators, generics, pitfalls |
| [json-custom-mapper-reference.md](references/json-custom-mapper-reference.md) | Custom `JsonReader`/`JsonWriter`, `@Mapping`, Jackson 3 streaming API |
| [json-config-reference.md](references/json-config-reference.md) | Artifacts, `JsonModule` wiring, `JacksonModule` / Jackson 3 swap |
| [json-best-practices.md](references/json-best-practices.md) | DTO patterns, PATCH, errors, security, round-trip tests |

## Common Pitfalls

- **Artifact `json-module` does not exist in 2.0** → use `io.koraframework:json-common`.
- **`io.koraframework.json.module.JsonModule` does not exist** → the module interface is `io.koraframework.json.common.JsonModule`; there is no `JsonCommonModule`.
- **`*Unchecked` methods are gone** → `toString`, `toByteArray`, `read`; and no `IOException` to catch.
- **`read(...)` is nullable** → Kotlin needs `requireNotNull(...)`; Java should null-check.
- **Missing `@Json` on a sealed subtype** → the sealed mapper cannot be wired.
- **All fields required by default** → use JSpecify `@Nullable` (Kotlin: `T?`).
- **`@JsonSkip` vs `@JsonInclude`** — `@JsonSkip` removes the field from read *and* write; `@JsonInclude` only controls when a present field is written.
- **Wrong `JsonNullable` API** — `isDefined()`/`isNull()`/`value()`, not `Optional`-style `isPresent()`/`get()`.
- **Jackson 2 group with `jackson-module`** — `jackson-module` binds `tools.jackson.core:jackson-databind`; adding `com.fasterxml.jackson.core:jackson-databind` gives you a second, unused Jackson.
