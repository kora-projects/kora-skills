# JSON DTO Reference

Source of truth: `.kora-agent/kora-docs/mkdocs/docs/en/documentation/json.md`,
`.kora-agent/kora-examples/guides/java/kora-java-guide-json-app`.

## Contents

1. [Overview](#1-overview)
2. [Core annotations](#2-core-annotations)
3. [Field configuration](#3-field-configuration)
4. [JsonNullable — missing vs null](#4-jsonnullable--missing-vs-null)
5. [Enum serialization](#5-enum-serialization)
6. [Collection types](#6-collection-types)
7. [Date/time types](#7-datetime-types)
8. [Nested objects](#8-nested-objects)
9. [Quick reference](#9-quick-reference)

---

## 1. Overview

Kora JSON module provides **compile-time** JSON (de)serialization without reflection:

- **Code generation** — readers/writers generated at compile time
- **Zero reflection** — no runtime performance penalty
- **Type-safe** — full type checking during compilation
- **Null-safe** — explicit handling of nullable fields

---

## 2. Core Annotations

### @Json — Reader + Writer

Primary annotation for DTO classes:

```java
@Json
public record UserDto(String id, String name, String email) {}
```

**What it does:**
- Generates `JsonReader<UserDto>` for deserialization
- Generates `JsonWriter<UserDto>` for serialization
- Both components available via DI

**Kotlin:**
```kotlin
@Json
data class UserDto(val id: String, val name: String, val email: String)
```

### @JsonReader — Deserialization Only

```java
@JsonReader
public record ImportRequest(String source, LocalDateTime timestamp) {}
```

**Use case:** DTO for incoming data only (request body).

### @JsonWriter — Serialization Only

```java
@JsonWriter
public record ExportResponse(String report, int totalRecords) {}
```

**Use case:** DTO for outgoing data only (response body).

---

## 3. Field Configuration

### Required vs Optional Fields

**Required (default):**
```java
@Json
public record UserRequest(String name, String email) {}
```

**Optional with @Nullable:**
```java
@Json
public record UserUpdateRequest(
    String id,              // required
    @Nullable String name,  // optional
    @Nullable String email  // optional
) {}
```

**Kotlin nullability:**
```kotlin
@Json
data class UserUpdateRequest(
    val id: String,         // required
    val name: String?,      // optional
    val email: String?      // optional
)
```

### @JsonField — Rename Fields

```java
@Json
public record ApiRequest(
    @JsonField("user_id") String userId,
    @JsonField("first_name") String firstName,
    @JsonField("last_name") String lastName
) {}
```

**JSON:**
```json
{ "user_id": "123", "first_name": "John", "last_name": "Doe" }
```

### @JsonSkip — Ignore Fields

```java
@Json
public record InternalDto(
    String publicField,
    @JsonSkip String internalField  // ignored during (de)serialization
) {}
```

**Use cases:** internal/computed fields, security-sensitive data.

### @JsonInclude — Control Serialization

```java
@Json
@JsonInclude(IncludeType.NON_NULL)
public record Response(
    String id,
    @JsonInclude(IncludeType.ALWAYS)  // always serialize
    @Nullable String optionalField
) {}
```

**IncludeType values:**

| Type | Behavior |
|------|----------|
| `ALWAYS` | Always include |
| `NON_NULL` | Skip if null (default) |
| `NON_EMPTY` | Skip if null or empty |

---

## 4. JsonNullable — Missing vs Null

`JsonNullable<T>` distinguishes between a field that was absent in the JSON and a field
explicitly set to `null`. Use it for PATCH endpoints where "do not touch" and "clear the
value" are different intents.

```java
@Json
public record PatchRequest(
    String id,
    JsonNullable<String> name,
    JsonNullable<String> email
) {}
```

**API** (`ru.tinkoff.kora.json.common.JsonNullable`):

| Method | Meaning |
|--------|---------|
| `isDefined()` | The field was present in the JSON (its value may still be `null`) |
| `isNull()` | The field was present and its value is explicitly `null` |
| `value()` | The contained value (`null` when `isNull()`; throws if undefined) |

Factories: `JsonNullable.of(v)`, `JsonNullable.ofNullable(v)`, `JsonNullable.nullValue()`,
`JsonNullable.undefined()`.

**Three states** for a `JsonNullable<String>` field:

| JSON | `isDefined()` | `isNull()` | `value()` |
|------|---------------|------------|-----------|
| `"name": "John"` | `true` | `false` | `"John"` |
| `"name": null`   | `true` | `true`  | `null` |
| field omitted    | `false`| `false` | throws `NullPointerException` |

**Usage in PATCH:**
```java
@HttpRoute(method = HttpMethod.PATCH, path = "/users/{id}")
@Json
public UserResponse updateUser(@Path String id, @Json PatchRequest request) {
    User user = userService.findById(id);
    if (request.name().isDefined()) {     // present in JSON
        user.setName(request.name().value()); // value() is null when isNull() is true
    }
    // field omitted → isDefined() == false → leave property untouched
    return userService.update(user);
}
```

---

## 5. Enum Serialization

Enums use `toString()` for serialization by default:

```java
@Json
public enum OrderStatus { PENDING, PROCESSING, SHIPPED }
```

**JSON:** `"PENDING"`, `"PROCESSING"`, `"SHIPPED"`

**Custom values via toString():**
```java
@Json
public enum OrderStatus {
    PENDING("pending"), PROCESSING("processing"), SHIPPED("shipped");
    private final String value;
    OrderStatus(String v) { this.value = v; }
    @Override public String toString() { return value; }
    public static OrderStatus fromString(String v) {
        return Arrays.stream(values())
            .filter(s -> s.value.equals(v))
            .findFirst()
            .orElseThrow(() -> new IllegalArgumentException("Unknown: " + v));
    }
}
```

**JSON:** `"pending"`, `"processing"`, `"shipped"`

---

## 6. Collection Types

### Lists
```java
@Json
public record TeamResponse(String teamId, List<Member> members) {}
```

### Maps
```java
@Json
public record ConfigResponse(Map<String, String> settings) {}
```

### Empty Collections
```java
@Json
@JsonInclude(IncludeType.NON_EMPTY)
public record SearchResponse(List<Result> results, int total) {}
```

---

## 7. Date/Time Types

Built-in support for standard Java types (ISO-8601 format):

```java
@Json
public record EventDto(
    LocalDateTime timestamp,
    LocalDate date,
    Instant instant,
    ZonedDateTime zonedDateTime
) {}
```

---

## 8. Nested Objects

```java
@Json
public record OrderResponse(
    String orderId,
    Customer customer,
    List<OrderItem> items,
    Payment payment
) {}

@Json
public record Customer(String id, String name, String email) {}
```

---

## 9. Quick Reference

### Annotation Summary

| Annotation | Purpose |
|------------|---------|
| `@Json` | Reader + Writer |
| `@JsonReader` | Deserialization only |
| `@JsonWriter` | Serialization only |
| `@JsonField("name")` | Rename JSON field |
| `@JsonSkip` | Ignore field |
| `@JsonInclude(IncludeType.X)` | Control serialization |
| `@Nullable` | Optional field |
| `JsonNullable<T>` | Distinguish missing vs null |

### Common Patterns

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
