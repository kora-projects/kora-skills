# OpenAPI Models Reference — Kora 2.x

`modelPackage` receives one type per schema plus the compile-time JSON readers and writers Kora
needs. Models are generated; you construct and read them, never edit them.

## Contents

- [1. Java: records](#1-java-records)
- [2. Kotlin: data classes and the named-argument rule](#2-kotlin-data-classes-and-the-named-argument-rule)
- [3. Required, optional and nullable](#3-required-optional-and-nullable)
- [4. `JsonNullable`](#4-jsonnullable)
- [5. Enums — always `fromValue`](#5-enums--always-fromvalue)
- [6. Discriminated hierarchies](#6-discriminated-hierarchies)
- [7. Type mapping](#7-type-mapping)
- [8. JSPecify positions in generated Java](#8-jspecify-positions-in-generated-java)
- [9. Generated JSON support](#9-generated-json-support)
- [10. Extra type annotations](#10-extra-type-annotations)

---

## 1. Java: records

```java
@Generated("io.koraframework.openapi.generator.javagen.ModelGenerator")
@JsonWriter
public record Pet(long id, @Nullable Long nonRequiredId, String name, @Nullable String tag) {

  @JsonReader
  public Pet { }

  /** required-only convenience constructor, generated when any field is optional */
  public Pet(long id, String name) {
    this(id, null, name, null);
  }

  public Pet withId(long id) { … }
  public Pet withName(String name) { … }
  public Pet withTag(@Nullable String tag) { … }
}
```

Three things to use:

- **The canonical constructor** takes every field in spec order.
- **A required-only constructor** is generated whenever at least one field is optional; it passes
  `null` for all of them. This is the safe way to build a model in Java.
- **`withX(…)` copy methods**, one per field, returning `this` unchanged when the value is equal.
  Use them instead of re-listing every component:

```java
var updated = pet.withName(newName).withStatus(Pet.StatusEnum.fromValue(rawStatus));
```

`@JsonWriter` on the type and `@JsonReader` on the compact constructor are what make Kora
generate `$Pet_JsonWriter` / `$Pet_JsonReader` next to the model.

## 2. Kotlin: data classes and the named-argument rule

```kotlin
@Json
public data class Pet(
  public val id: Long,
  public val nonRequiredId: Long? = null,
  public val name: String,
  public val tag: String? = null,
)
```

Properties keep **spec order**, and optional ones carry defaults *in place* — an optional
property can sit between two required ones, as `nonRequiredId` does above. Consequences:

- **Always construct with named arguments.**

  ```kotlin
  val pet = Pet(id = 1L, name = "Fido")          // correct
  // val pet = Pet(1L, "Fido")                   // does not compile: arg 2 is Long?
  ```

  A positional call happens to work only while the required fields lead. Reordering properties in
  the contract, or making one optional, silently changes which argument lands where for any
  positional call whose types still line up. Named arguments make that a compile error instead.

- **Copy with `copy(named = …)`**, the Kotlin equivalent of Java's `withX`:

  ```kotlin
  val updated = pet.copy(name = newName, status = Pet.StatusEnum.fromValue(raw))
  ```

- There is no required-only secondary constructor in Kotlin — the defaults do that job.

## 3. Required, optional and nullable

The generator combines the schema's `required` list and its `nullable` flag:

| `required` | `nullable` | Java field | Kotlin property |
|---|---|---|---|
| yes | no | plain type, primitives unboxed (`long id`) | `val id: Long` |
| yes | yes | boxed + `@Nullable`, parameter carries `@JsonInclude(ALWAYS)` | `val x: T? = null`, `@JsonInclude(ALWAYS)` |
| no | no | boxed + `@Nullable` | `val x: T? = null` |
| no | yes | **`JsonNullable<T>`** | **`JsonNullable<T> = JsonNullable.nullValue()`** |

A field that is `required` **and** `nullable` gets a second, JSON-only constructor annotated
`@JsonReader` that takes `JsonNullable<T>` and throws
`IllegalArgumentException("Field 'x' was not found in parsed json")` when the key is absent — so
"present but null" and "absent" stay distinguishable on the wire while your code sees a plain
nullable field.

## 4. `JsonNullable`

`io.koraframework.json.common.JsonNullable<T>` (artifact `json-common`) models the third state
of a JSON field: absent, present-and-null, present-with-value. It appears automatically for
`nullable: true` + not `required`; there is no `enableJsonNullable` option in 2.0 (that 1.x key
is ignored).

```java
if (patch.nickname().isDefined()) {
    entity.setNickname(patch.nickname().value());   // may itself be null
}
```

```kotlin
if (patch.nickname.isDefined) {
    entity.nickname = patch.nickname.value()
}
```

To build one: `JsonNullable.of(value)`, `JsonNullable.nullValue()` for present-and-null, and
`JsonNullable.undefined()` for absent. This is the correct shape for `PATCH` bodies — see the
`kora-json` skill for the full contract.

## 5. Enums — always `fromValue`

Every generated enum, top-level or nested in a model, has this shape:

```java
public enum StatusEnum {
  AVAILABLE(Constants.AVAILABLE),
  PENDING(Constants.PENDING),
  SOLD(Constants.SOLD);

  private static final StatusEnum[] VALUES = values();
  private final String value;

  public String getValue() { return this.value; }

  @Override public String toString() { return String.valueOf(value); }

  public static StatusEnum fromValue(String value) {
    for (var candidate : VALUES) {
      if (candidate.value.equals(value)) {
        return candidate;
      }
    }
    throw new IllegalArgumentException("Unexpected value '" + value + "'");
  }

  public static final class Constants {
    public static final String AVAILABLE = "available";
  }
}
```

**The constant name and the wire value are different strings.** `AVAILABLE` is the Java
identifier; `"available"` is what the contract says. Therefore:

| Wrong | Why |
|---|---|
| `StatusEnum.valueOf(raw)` | Compares against the constant name — throws for the valid wire value `"available"`. |
| `Arrays.stream(values()).filter(v -> v.name().equals(raw))` | Same bug, written out. |
| a hand-written `statusOf(String)` helper | Duplicates `fromValue` and drifts from the contract. |
| `StatusEnum.valueOf(raw.toUpperCase())` | Works only while every wire value happens to be the lower-cased constant name. |

**Right:**

```java
final Pet.StatusEnum status;
try {
    status = Pet.StatusEnum.fromValue(raw);
} catch (IllegalArgumentException e) {
    return new PetApiResponses.FindPetsByStatusApiResponse.FindPetsByStatus400ApiResponse();
}
```

```kotlin
val status = try {
    raw?.let(Pet.StatusEnum::fromValue)
} catch (_: IllegalArgumentException) {
    null
} ?: return PetApiResponses.FindPetsByStatusApiResponse.FindPetsByStatus400ApiResponse()
```

This is a runtime-only failure: `valueOf` compiles perfectly and passes any test whose fixture
uses the constant name. It breaks on the first real payload.

Serialising: use `getValue()`, not `name()` or `toString()` if you need the exact wire form (they
happen to agree because `toString` returns `value`).

Alongside the enum the generator emits a `@Module` of `@DefaultComponent` bindings —
`<Enum>MapperModule` for a top-level enum, `<Model>__NestedEnumMapperModule` for nested ones —
providing `JsonWriter`, `JsonReader` and `HttpServerParameterReader` for it, so enums work as
query/path parameters and as JSON values without any wiring from you.

## 6. Discriminated hierarchies

A schema with a `discriminator` becomes a `sealed interface`, each mapped variant a record /
data class:

```java
@Json
@JsonDiscriminatorField("pet_type")
public sealed interface Pet permits PetCommon, PetCat, PetDog {
  String petType();
}

@JsonWriter
@JsonDiscriminatorValue({"PetCat"})
public record PetCat(@JsonField("pet_type") String petType, @Nullable Boolean hunts)
    implements Pet { }
```

- Several `mapping` keys may resolve to one schema: `@JsonDiscriminatorValue({"Mapping3", "Mapping2"})`.
- Discriminator properties whose JSON name is not a valid identifier are renamed and carry
  `@JsonField("…")` — `@kind` becomes `atKind`, `pet_type` becomes `petType`.
- Two different discriminator fields converging on one model is a generation error.
- Use `switch` / `when` over the sealed type; exhaustiveness is checked at compile time.

## 7. Type mapping

| OpenAPI | Java | Kotlin |
|---|---|---|
| `string` | `String` | `String` |
| `string, format: uuid` | `java.util.UUID` | `java.util.UUID` |
| `string, format: uri` | `java.net.URI` | `java.net.URI` |
| `string, format: date` | `java.time.LocalDate` | `java.time.LocalDate` |
| `string, format: date-time` | `java.time.OffsetDateTime` (see `typeMappings` below) | same |
| `string, format: binary`/`byte` | `byte[]` | `ByteArray` |
| `integer, format: int32` | `int` / `Integer` | `Int` |
| `integer, format: int64` | `long` / `Long` | `Long` |
| `number` / `format: decimal` | `java.math.BigDecimal` | `java.math.BigDecimal` |
| `number, format: double` / `float` | `double` / `float` | `Double` / `Float` |
| `boolean` | `boolean` / `Boolean` | `Boolean` |
| `array` | `List<T>` | `List<T>` |
| `array` of an inline `enum` | `List<Model.XxxEnum>` | `List<Model.XxxEnum>` |
| `object` + `additionalProperties: {schema}` | `Map<String, T>` | `Map<String, T>` |
| `object` + `additionalProperties: true` (free-form) | `Map<String, Object>` | `Map<String, Any>` |
| bare `object` (no schema) | per `rawBodyMode`: `byte[]` / `HttpBodyInput` / `Object` | same |

Unboxed primitives appear only for `required: true` fields; anything nullable or optional is
boxed.

`date-time` follows the plugin's `typeMappings` (a `GenerateTask` property, not a `configOptions`
key). Map `DateTime` (or `date-time`) to `Instant`, `ZonedDateTime` or `LocalDateTime`, by simple
or fully qualified name; any other target falls back to `OffsetDateTime`:

```groovy
typeMappings = ["DateTime": "java.time.Instant"]                  // build.gradle
```

```kotlin
typeMappings.set(mapOf("DateTime" to "java.time.Instant"))        // build.gradle.kts
```

Descriptions, summaries and string defaults from the contract are copied as text, so `%` and `$`
in them (`%2B`, `${…}`) are safe; Kotlin string defaults get `$` escaped.

## 8. JSPecify positions in generated Java

Java modes emit `package-info.java` marking both packages
`@org.jspecify.annotations.NullMarked`, and `@Nullable` is JSpecify's **type-use** annotation. It
therefore binds to the type it precedes, which for a nested type looks unusual but is correct:

```java
public record Pet(long id,
                  Pet. @Nullable StatusEnum status,        // nested type
                  @Nullable String tag,                    // top-level type
                  List<@Nullable String> notes) { }
```

Writing `@Nullable Pet.StatusEnum` instead annotates `Pet`, not `StatusEnum`, and javac rejects
it with *"type annotation @org.jspecify.annotations.Nullable is not expected here"*. Copy the
position from the generated signature.

Kotlin does not use these annotations at all — nullability is the type (`T?`). Do not carry
`@field:Nullable` into Kotlin; it is not a valid target under Kotlin 2.4.

## 9. Generated JSON support

Next to every model Kora's JSON processor emits `$Model_JsonReader` and `$Model_JsonWriter`.
They require `io.koraframework:json-common` on the compile classpath and `JsonModule` in the
`@KoraApp` graph. Kora 2.0 runs on **Jackson 3 streaming** (`tools.jackson.core`); the artifact
`json-module` and the package `com.fasterxml.jackson.*` belong to 1.x.

If you read or write these models yourself, note the 2.0 signature changes: `JsonWriter.toString`
/ `toByteArray` no longer declare a checked exception (a `catch (IOException)` around them is a
compile error), and `JsonReader.read` is `@Nullable`.

## 10. Extra type annotations

Model annotations can be injected without touching generated code, through
`configOptions.extensions`:

```groovy
configOptions = [
    mode      : "java-server",
    extensions: """
        {
          "*": {
            "additionalModelTypeAnnotations": [
              "@io.koraframework.json.common.annotation.JsonInclude(io.koraframework.json.common.annotation.JsonInclude.IncludeType.ALWAYS)"
            ],
            "additionalEnumTypeAnnotations": []
          }
        }
        """,
]
```

`additionalTypeAnnotations` applies to models and enums; `additionalModelTypeAnnotations` and
`additionalEnumTypeAnnotations` narrow it. Only the `"*"` (global) section is read for type
annotations — the `tags` and `operations` sections apply to methods and interceptors.

Note that a **type-level** `@JsonInclude` is not generated by default; the snippet above is how
you get one.

## Related

- [Delegates Reference](openapi-delegates-reference.md) — where models appear as parameters
- [Response Reference](openapi-response-reference.md) — where models appear as `content`
- [Validation Reference](openapi-validation-reference.md) — constraints on model fields
- `kora-json` skill — `@Json`, `JsonNullable`, custom readers/writers
