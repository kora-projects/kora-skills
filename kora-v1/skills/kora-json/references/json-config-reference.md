# JSON Module Configuration Reference

Source of truth: `.kora-agent/kora-docs/mkdocs/docs/en/documentation/json.md`.

## Contents

1. [Overview](#1-overview)
2. [Dependency](#2-dependency)
3. [Module wiring](#3-module-wiring)
4. [Jackson integration](#4-jackson-integration)
5. [Supported types](#5-supported-types)
6. [Choosing JsonModule vs JacksonModule](#6-choosing-jsonmodule-vs-jacksonmodule)
7. [Quick reference](#7-quick-reference)

---

## 1. Overview

Kora JSON module setup:

- **Dependency** — `ru.tinkoff.kora:json-module` plus the mandatory annotation processor
- **Module** — the `JsonModule` interface, plugged into `@KoraApp`
- **Jackson alternative** — `JacksonModule` backed by an `ObjectMapper` factory
- **Supported types** — extensive built-in list (see below)

---

## 2. Dependency

The annotation processor is mandatory — it generates the `JsonReader`/`JsonWriter`
classes. All Kora artifacts inherit their version from the `kora-parent` BOM.

### Java (Gradle)

```groovy
dependencies {
    koraBom platform("ru.tinkoff.kora:kora-parent:1.2.17")

    annotationProcessor "ru.tinkoff.kora:annotation-processors"
    implementation "ru.tinkoff.kora:json-module"
}
```

### Kotlin (Gradle, KSP)

```kotlin
dependencies {
    ksp("ru.tinkoff.kora:symbol-processors")
    implementation("ru.tinkoff.kora:json-module")
}
```

---

## 3. Module wiring

### Basic Setup

```java
@KoraApp
public interface Application extends JsonModule {
    static void main(String[] args) {
        KoraApplication.run(ApplicationGraph::graph);
    }
}
```

### Kotlin

```kotlin
@KoraApp
interface Application : JsonModule {
    companion object {
        @JvmStatic
        fun main(args: Array<String>) {
            KoraApplication.run(ApplicationGraph::graph)
        }
    }
}
```

---

## 4. Jackson integration

To use Jackson instead of (or alongside) the generated mappers, add the
`jackson-module` together with the JSON annotation processor, register a factory that
provides an `ObjectMapper`, and Kora supplies the corresponding mappers required by the
other Kora modules (HTTP server/client, cache, Kafka, etc.).

### Dependency

Java:

```groovy
dependencies {
    annotationProcessor "ru.tinkoff.kora:json-annotation-processor"
    implementation "ru.tinkoff.kora:jackson-module"
}
```

Kotlin (KSP):

```kotlin
dependencies {
    ksp("ru.tinkoff.kora:json-annotation-processor")
    implementation("ru.tinkoff.kora:jackson-module")
}
```

### Module

```java
@KoraApp
public interface Application extends JacksonModule {
    static void main(String[] args) {
        KoraApplication.run(ApplicationGraph::graph);
    }
}
```

### Providing a custom ObjectMapper

Register a factory for the `ObjectMapper` in the application graph. A factory without
`@DefaultComponent` overrides the framework-supplied default, so this is how you tune
Jackson behavior:

```java
@KoraApp
public interface Application extends JacksonModule {

    default ObjectMapper objectMapper() {
        return JsonMapper.builder()
            .addModule(new JavaTimeModule())
            .disable(SerializationFeature.WRITE_DATES_AS_TIMESTAMPS)
            .disable(DeserializationFeature.FAIL_ON_UNKNOWN_PROPERTIES)
            .build();
    }

    static void main(String[] args) {
        KoraApplication.run(ApplicationGraph::graph);
    }
}
```

When `JacksonModule` is wired, Kora's HTTP server/client `@Json` bodies and other JSON
boundaries are served through the `ObjectMapper`-backed mappers it contributes.

---

## 5. Supported types

Out-of-the-box support for:

| Type Category | Types |
|---------------|-------|
| **Primitives** | `boolean`, `int`, `long`, `double`, `float`, `short`, `byte` |
| **Boxed** | `Boolean`, `Integer`, `Long`, `Double`, `Float`, `Short`, `Byte` |
| **Strings** | `String`, `UUID` |
| **Numbers** | `BigInteger`, `BigDecimal` |
| **Arrays** | `byte[]` |
| **Collections** | `List<T>`, `Set<T>`, `Map<K,V>` |
| **Date/Time** | `LocalDate`, `LocalTime`, `LocalDateTime`, `OffsetTime`, `OffsetDateTime`, `ZonedDateTime`, `Year`, `YearMonth`, `MonthDay`, `Month`, `DayOfWeek`, `ZoneId`, `Duration` |
| **Enums** | Any enum type |

---

## 6. Choosing JsonModule vs JacksonModule

### Migrating Jackson DTOs to Kora annotations

#### Before (fasterxml Jackson)

```java
import com.fasterxml.jackson.annotation.*;

@JsonInclude(JsonInclude.Include.NON_NULL)
public class UserDto {

    @JsonProperty("user_id")
    private String userId;

    @JsonProperty("email_address")
    private String email;

    @JsonIgnore
    private String internalField;

    // Constructors, getters, setters
}
```

#### After (Kora JSON)

```java
import ru.tinkoff.kora.json.common.annotation.Json;
import ru.tinkoff.kora.json.common.annotation.JsonField;
import ru.tinkoff.kora.json.common.annotation.JsonSkip;

@Json
@JsonInclude(IncludeType.NON_NULL)
public record UserDto(
    @JsonField("user_id") String userId, 
    @JsonField("email_address") String email,
    @JsonSkip String internalField
) {}
```

#### Migration checklist

- [ ] Replace `@JsonProperty` with `@JsonField`
- [ ] Replace `@JsonIgnore` with `@JsonSkip`
- [ ] Replace fasterxml `@JsonInclude` with Kora's `@JsonInclude(IncludeType...)`
- [ ] Convert classes to records (Java 17+) or Kotlin data classes
- [ ] Update polymorphic types to sealed types with discriminator annotations
- [ ] Test serialization/deserialization round-trips

### When to keep Jackson (`JacksonModule`)

- An existing fasterxml-Jackson codebase you are not ready to convert
- You need advanced Jackson features: mix-ins, annotation-driven custom serializers,
  XML/YAML/CBOR/Smile formats, or a third-party library that requires an `ObjectMapper`

### When to use the generated mappers (`JsonModule`, default)

- New code, simple DTOs, and performance-critical paths
- Compile-time safety: unsupported shapes fail the build, not at runtime

---

## 7. Quick Reference

### Dependency

```groovy
// Kora JSON (default) — annotation processor is mandatory
annotationProcessor "ru.tinkoff.kora:annotation-processors"
implementation "ru.tinkoff.kora:json-module"

// Jackson integration (optional, alternative backend)
annotationProcessor "ru.tinkoff.kora:json-annotation-processor"
implementation "ru.tinkoff.kora:jackson-module"
```

### Module

```java
// Kora JSON
@KoraApp
public interface Application extends JsonModule {}

// Jackson
@KoraApp
public interface Application extends JacksonModule {}

// Both
@KoraApp
public interface Application extends JsonModule, JacksonModule {}
```

### Annotation Mapping

| Jackson | Kora Equivalent |
|---------|-----------------|
| `@JsonProperty("name")` | `@JsonField("name")` |
| `@JsonIgnore` | `@JsonSkip` |
| `@JsonInclude(NON_NULL)` | `@JsonInclude(IncludeType.NON_NULL)` |
| `@JsonFormat(pattern = "...")` | Custom mapper |
| `@JsonTypeInfo` | `@JsonDiscriminatorField` |
| `@JsonSubTypes` | `@JsonDiscriminatorValue` |
