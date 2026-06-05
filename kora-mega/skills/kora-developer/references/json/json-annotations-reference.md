# Kora JSON Annotations Reference

**Source:** [.kora-agent/kora-docs/mkdocs/docs/en/documentation/json.md](.kora-agent/kora-docs/mkdocs/docs/en/documentation/json.md)  
**Examples:** `.kora-agent/kora-examples/kora-java-json-module/`

---
## 1. Overview

Kora JSON module provides **compile-time** JSON serialization/deserialization without reflection:

- **Code generation** — JSON readers/writers generated at compile time
- **Zero reflection** — no runtime performance penalty
- **Type-safe** — full type checking during compilation
- **Null-safe** — explicit handling of nullable fields

---
## 2. Core Annotations
### 2.1 @Json — Reader + Writer

Main annotation for DTO classes:

```java
@Json
public record UserDto(
    String id, 
    String name,
    String email
) {}
```

**What it does:**
- Generates `JsonReader<UserDto>` for deserialization
- Generates `JsonWriter<UserDto>` for serialization
- Both components available via DI

**Kotlin equivalent:**

```kotlin
@Json
data class UserDto(
    val id: String,
    val name: String,
    val email: String
)
```
### 2.2 @JsonReader — Deserialization Only

```java
@JsonReader
public record ImportRequest(
    String source, 
    LocalDateTime timestamp
) {}
```

**Use case:** DTO for incoming data only (request body).
### 2.3 @JsonWriter — Serialization Only

```java
@JsonWriter
public record ExportResponse(
    String report,
    int totalRecords
) {}
```

**Use case:** DTO for outgoing data only (response body).

---
## 3. Field Configuration
### 3.1 Required vs Optional Fields

**Required (default):**

```java
@Json
public record UserRequest(
    String name,    // required field 
    String email    // required field
) {}
```

If JSON is missing a required field, deserialization fails with error.

**Optional with @Nullable:**

```java
@Json
public record UserUpdateRequest(
    String id,              // required
    @Nullable String name,  // optional field
    @Nullable String email  // optional field
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
### 3.2 @JsonField — Rename Fields

```java
@Json
public record ApiRequest(
    @JsonField("user_id") String userId,
    @JsonField("first_name") String firstName,
    @JsonField("last_name") String lastName
) {}
```

**Expected JSON:**

```json
{
    "user_id": "123", 
    "first_name": "John",
    "last_name": "Doe"
}
```

**Use cases:**
- snake_case JSON API compatibility
- Different naming conventions
- Backward compatibility for renamed fields
### 3.3 @JsonSkip — Ignore Fields

```java
@Json
public record InternalDto(
    String publicField,
    @JsonSkip String internalField,  // ignored during (de)serialization
    @JsonSkip transient String cacheField
) {}
```

**Use cases:**
- Internal/computed fields
- Fields with custom serialization
- Security-sensitive fields (passwords, tokens)
### 3.4 @JsonInclude — Control Serialization

```java
@Json
@JsonInclude(IncludeType.NON_NULL)
public record Response {
    String id; 
    
    @JsonInclude(IncludeType.ALWAYS) 
    @Nullable String optionalField;
}
```

**IncludeType values:**

| Type | Behavior |
|------|----------|
| `ALWAYS` | Always include field (default for required) |
| `NON_NULL` | Don't include null fields (default for optional) |
| `NON_EMPTY` | Don't include null and empty collections |

**Example with NON_EMPTY:**

```java
@Json
@JsonInclude(IncludeType.NON_EMPTY)
public record SearchResponse {
    List<Result> results;  // won't be serialized if empty
    int total;
}
```

---
## 4. JsonNullable — Missing vs Null
### 4.1 The Problem

Standard `@Nullable` doesn't distinguish between:
- Field not present in JSON (missing)
- Field explicitly set to `null`
### 4.2 Solution: JsonNullable Wrapper

```java
import ru.tinkoff.kora.json.common.JsonNullable;

@Json
public record UserUpdateRequest(
    String id, 
    JsonNullable<String> name,
    JsonNullable<String> email
) {}
```

**Usage:**

```java
@HttpRoute(method = HttpMethod.PUT, path = "/users/{id}")
@Json
public UserResponse updateUser(
    @Path String id,
    @Json UserUpdateRequest request
) {
    // Check if field was provided
    if (request.name().isPresent()) {
        user.setName(request.name().get());
    }

    // Check if field was explicitly null
    if (request.name().isNull()) {
        user.setName(null);
    }

    return userService.update(user);
}
```

**JsonNullable states:**

| State | Method | Meaning |
|-------|--------|---------|
| Present | `isPresent()` = true | Field in JSON with value |
| Null | `isNull()` = true | Field explicitly `null` in JSON |
| Absent | `isAbsent()` = true | Field not in JSON |

---
## 5. Default Values
### 5.1 Java Records

```java
@Json
public record Config(
    String host, 
    int port = 8080,  // Default value
    boolean ssl = false
) {}
```

**Note:** Java doesn't support default parameter values in records. Use builder pattern or separate constructors.
### 5.2 Kotlin Data Classes

```kotlin
@Json
data class Config(
    val host: String,
    val port: Int = 8080,      // Default value
    val ssl: Boolean = false
)
```

**JSON behavior:**

```json
// Missing field uses default
{"host": "localhost"}
// port = 8080, ssl = false

// Explicit value overrides default
{"host": "localhost", "port": 9000}
// port = 9000, ssl = false
```

---
## 6. Collection Types
### 6.1 Lists

```java
@Json
public record TeamResponse(
    String teamId,
    List<Member> members
) {}

@Json
public record Member(
    String id,
    String name
) {}
```

**JSON:**

```json
{
    "teamId": "team-1", 
    "members": [
        {"id": "1", "name": "Alice"}, 
        {"id": "2", "name": "Bob"}
    ]
}
```
### 6.2 Maps

```java
@Json
public record ConfigResponse(
    Map<String, String> settings
) {}
```

**JSON:**

```json
{
    "settings": { 
        "theme": "dark",
        "language": "en" 
    }
}
```
### 6.3 Optional Collections

```java
@Json
public record SearchResponse {
    @Nullable List<Result> results;  // Can be null or missing
}
```

---
## 7. Date/Time Types
### 7.1 Built-in Support

Kora JSON module supports standard Java/Kotlin date types:

```java
@Json
public record EventDto(
    LocalDateTime timestamp, 
    LocalDate date,
    Instant instant, 
    ZonedDateTime zonedDateTime
) {}
```

**Default format:** ISO-8601

```json
{
    "timestamp": "2024-01-15T10:30:00",
    "date": "2024-01-15",
    "instant": "2024-01-15T10:30:00Z",
    "zonedDateTime": "2024-01-15T10:30:00+03:00[Europe/Moscow]"
}
```
### 7.2 Custom Format

```java
@Json
public record EventDto(
    @JsonFormat(pattern = "dd.MM.yyyy HH:mm") LocalDateTime timestamp
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
public record Customer(
    String id,
    String name,
    String email
) {}

@Json
public record OrderItem(
    String productId,
    int quantity,
    BigDecimal price
) {}

@Json
public record Payment(
    String method,
    BigDecimal amount,
    String status
) {}
```

**JSON:**

```json
{
    "orderId": "order-123", 
    "customer": {
        "id": "cust-456", 
        "name": "John Doe",
        "email": "john@example.com" 
    },
    "items": [ 
        {
            "productId": "prod-789", 
            "quantity": 2,
            "price": 29.99 
        }
    ], 
    "payment": {
        "method": "CARD", 
        "amount": 59.98,
        "status": "COMPLETED" 
    }
}
```

---
## 9. Inheritance
### 9.1 Simple Inheritance (Not Recommended)

```java
// Don't do this - use sealed interfaces instead
@Json
public class BaseDto {
    public String id;
}

@Json
public class ExtendedDto extends BaseDto {
    public String extraField;
}
```

**Problem:** No discriminator field, ambiguous deserialization.
### 9.2 Sealed Interfaces (Recommended)

See [sealed-interfaces-json.md](sealed-interfaces-json.md) for complete guide.

---
## 10. Quick Reference
### Annotation Summary

| Annotation | Target | Purpose |
|------------|--------|---------|
| `@Json` | Class | Reader + Writer |
| `@JsonReader` | Class | Deserialization only |
| `@JsonWriter` | Class | Serialization only |
| `@JsonField("name")` | Field | Rename JSON field |
| `@JsonSkip` | Field | Ignore during (de)serialization |
| `@JsonInclude(IncludeType.X)` | Class/Field | Control serialization |
| `@Nullable` | Field | Optional field |
### IncludeType Values

| Type | Behavior |
|------|----------|
| `ALWAYS` | Always include |
| `NON_NULL` | Skip if null |
| `NON_EMPTY` | Skip if null or empty |
### Common Patterns

```java
// Basic DTO
@Json
public record UserDto(String id, String name) {}

// Optional fields
@Json
public record UpdateRequest(
    String id, 
    @Nullable String name,
    @Nullable String email
) {}

// Renamed fields
@Json
public record ApiRequest(
    @JsonField("user_id") String userId
) {}

// JsonNullable for PATCH
@Json
public record PatchRequest(
    String id, 
    JsonNullable<String> name
) {}
```
