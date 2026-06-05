---
name: kora-json
description: JSON serialization/deserialization in Kora applications using @Json annotations, DTO records/data classes, sealed interfaces for polymorphic JSON with @JsonDiscriminatorField, custom JsonReader/JsonWriter, and Jackson integration. Use when creating HTTP APIs with JSON request/response bodies, integrating external JSON APIs, or building type-safe DTOs. Triggers: @Json, @JsonReader, @JsonWriter, @JsonField, @JsonSkip, @JsonInclude, @JsonDiscriminatorField, @JsonDiscriminatorValue, JsonNullable, sealed interface, enum serialization, JacksonModule.
---

# Kora JSON — JSON Processing in Kora Applications

### 1. Add dependency

```groovy
// build.gradle
dependencies {
    implementation "ru.tinkoff.kora:json-module"
}
```

### 2. Wire the module

```java
@KoraApp
public interface Application extends JsonModule {
    static void main(String[] args) {
        KoraApplication.run(ApplicationGraph::graph);
    }
}
```

### 3. Create a DTO

```java
@Json
public record UserRequest(
    String name,
    String email
) {}
```

### 4. JSON Controller

```java
@HttpController
public final class UserController {
    
    @HttpRoute(method = HttpMethod.POST, path = "/users")
    @Json
    public UserResponse createUser(@Json UserRequest request) {
        // request is automatically deserialized from JSON
        return userService.create(request);
    }
}
```

Read this first when:
- creating DTO classes for HTTP request/response bodies with `@Json`,
- implementing polymorphic JSON serialization with sealed interfaces and `@JsonDiscriminatorField`,
- writing custom `JsonReader`/`JsonWriter` for non-standard JSON formats,
- handling nullable fields with `JsonNullable` or `@JsonInclude`,
- integrating Jackson serializer alongside Kora's built-in JSON module.

---

## Assets (Templates)

The skill includes ready-to-use templates in `assets/` to speed up development:

| Template | Purpose |
|----------|---------|
| `dto.java.template` | Basic DTO record with `@Json` annotation |
| `enum.java.template` | Enum with custom JSON serialization via `toString()` |
| `sealed-dto.java.template` | Sealed interface for polymorphic JSON with discriminator |
| `sealed-dto-impl.java.template` | Sealed interface implementation with `@JsonDiscriminatorValue` |
| `custom-mapper.java.template` | Module with custom `JsonReader`/`JsonWriter` |

**Usage:** Copy the template into your project and replace the placeholders (`${package}`, `${entity_name}`, etc.).

---

## JSON Annotations

### @Json — Reader + Writer

The primary annotation for generating compile-time JSON mappers:

```java
@Json
public record UserDto(String id, String name, String email) {}
```

**What it does:**
- Generates `JsonReader<UserDto>` for deserialization
- Generates `JsonWriter<UserDto>` for serialization
- Both components are available via DI

### @JsonReader — Deserialization only

```java
@JsonReader
public record ImportData(String source, LocalDateTime timestamp) {}
```

**Use case:** DTO for incoming data only (request body).

### @JsonWriter — Serialization only

```java
@JsonWriter
public record ExportData(String report, int totalRecords) {}
```

**Use case:** DTO for outgoing data only (response body).

---

## Field Configuration

### Required vs Optional fields

**Required (by default):**

```java
@Json
public record UserRequest(
    String name,    // required
    String email    // required
) {}
```

**Optional with @Nullable:**

```java
@Json
public record UserUpdateRequest(
    @Nullable String name,      // optional
    @Nullable String email,     // optional
    String id                   // required
) {}
```

**Kotlin nullability:**

```kotlin
@Json
data class UserUpdateRequest(
    val name: String?,      // optional
    val email: String?,     // optional
    val id: String          // required
)
```

### @JsonField — Renaming fields

```java
@Json
public record ApiRequest(
    @JsonField("user_id") String userId,
    @JsonField("first_name") String firstName
) {}
```

**JSON:**
```json
{ "user_id": "123", "first_name": "John" }
```

### @JsonSkip — Ignoring fields

```java
@Json
public record InternalDto(
    String publicField,
    @JsonSkip String internalField  // ignored during (de)serialization
) {}
```

### @JsonInclude — Controlling serialization

```java
@Json
@JsonInclude(IncludeType.NON_NULL)  // do not serialize null fields
public record Response(
    String id,
    @JsonInclude(IncludeType.ALWAYS)  // always serialize
    @Nullable String optionalField
) {}
```

**IncludeType options:**
- `ALWAYS` — always include the field
- `NON_NULL` — exclude null fields (default)
- `NON_EMPTY` — exclude null fields and empty collections

---

### Enum — Serialization via toString()

**Important:** Enums must be annotated with `@Json` for mapper generation:

```java
@Json  // required for mapper generation
public enum OrderStatus { PENDING, PROCESSING, SHIPPED }
```

Kora uses `toString()` for serialization. By default an enum is serialized via `name()`:

```java
@Json
public record OrderRequest(String orderId, OrderStatus status) {}
```

**Customization via toString():**

```java
@Json
public enum OrderStatus {
    PENDING("pending"), PROCESSING("processing"), SHIPPED("shipped");
    private final String value;
    OrderStatus(String v) { this.value = v; }
    @Override public String toString() { return value; }
    public static OrderStatus fromString(String v) {
        return Arrays.stream(values()).filter(s -> s.value.equals(v))
            .findFirst().orElseThrow(() -> new IllegalArgumentException("Unknown: " + v));
    }
}
```

**Build warning:** If you see the warning "mapper generated in a new round" — verify that `@Json` is present on all DTOs and enums.

**@Json as a tag:** The `@Json` annotation also acts as a marker tag. When placed on a controller method, a Kafka parameter, or a database parameter, Kora requires an existing mapper but does not generate a new one:

```java
@HttpController
public final class OrderController {
    
    // @Json requires JsonWriter<OrderResponse> but does not generate it
    // (the mapper must already be provided)
    @HttpRoute(method = HttpMethod.GET, path = "/orders/{id}")
    @Json
    public OrderResponse getById(@Path String id) { ... }
    
    // @Json requires JsonReader<CreateOrderRequest>
    @HttpRoute(method = HttpMethod.POST, path = "/orders")
    @Json
    public OrderResponse create(@Json CreateOrderRequest request) { ... }
}
```

---

## Sealed Interfaces for Polymorphic JSON

### Basic pattern

```java
@Json
@JsonDiscriminatorField("type")
public sealed interface PaymentResult permits PaymentSuccess, PaymentError {}

@JsonDiscriminatorValue("SUCCESS")
public record PaymentSuccess(
    String type,
    String transactionId,
    BigDecimal amount
) implements PaymentResult {}

@JsonDiscriminatorValue("ERROR")
public record PaymentError(
    String type,
    String errorCode,
    String message
) implements PaymentResult {}
```

**JSON examples:**

```json
// Success
{ "type": "SUCCESS", "transactionId": "txn_123", "amount": 99.99 }

// Error
{ "type": "ERROR", "errorCode": "CARD_DECLINED", "message": "Card was declined" }
```

### How it works

**Deserialization:**
1. Kora reads the discriminator field value (`type`)
2. Finds the class with the matching `@JsonDiscriminatorValue`
3. Deserializes the JSON into the concrete record

**Serialization:**
1. Kora determines the runtime type of the object
2. Adds the discriminator field to the JSON
3. Serializes the remaining fields

### Controller with sealed response

```java
@HttpController
public final class PaymentController {
    
    @HttpRoute(method = HttpMethod.POST, path = "/payments/{id}")
    @Json
    public PaymentResult processPayment(@Path String id) {
        try {
            var txn = paymentService.process(id);
            return new PaymentSuccess("SUCCESS", txn.id(), txn.amount());
        } catch (PaymentException e) {
            return new PaymentError("ERROR", e.getCode(), e.getMessage());
        }
    }
}
```

---

## 🔌 HTTP Controller Integration

### JSON Request + Response

```java
@HttpController
public final class UserController {
    
    private final UserService userService;
    
    public UserController(UserService userService) {
        this.userService = userService;
    }
    
    @HttpRoute(method = HttpMethod.POST, path = "/users")
    @Json
    public UserResponse createUser(@Json UserRequest request) {
        return userService.create(request);
    }
    
    @HttpRoute(method = HttpMethod.GET, path = "/users/{id}")
    @Json
    public UserResponse getUser(@Path String id) {
        return userService.getById(id);
    }
}
```

### How JSON processing works

**Request body (@Json on parameter):**
1. Kora looks for `HttpRequestMapper<UserRequest>` tagged with `@Json`
2. If not found — generates one via `JsonReader<UserRequest>`
3. The reader is injected into the controller via DI
4. On each request the reader parses the JSON body into `UserRequest`, Content-Type = `application/json`

**Response body (@Json on method):**
1. Kora looks for `HttpResultMapper<UserResponse>` tagged with `@Json`
2. If not found — generates one via `JsonWriter<UserResponse>`
3. The mapper is injected into the controller via DI
4. The return value is serialized to JSON, Content-Type = `application/json`

### List responses

```java
@HttpRoute(method = HttpMethod.GET, path = "/users")
@Json
public List<UserResponse> getAllUsers() {
    return userService.getAll();
}
```

**JSON output:**
```json
[
    {"id": "1", "name": "John", "email": "john@example.com"},
    {"id": "2", "name": "Jane", "email": "jane@example.com"}
]
```

---

## Custom JsonReader/JsonWriter

See [custom-json-mappers.md](references/custom-json-mappers.md) for the full guide.

```java
@Module
public interface CustomJsonModule {
    
    @DefaultComponent
    default JsonReader<LocalDate> localDateReader() {
        return parser -> LocalDate.parse(parser.nextString());
    }
    
    @DefaultComponent
    default JsonWriter<ZoneOffset> zoneOffsetWriter() {
        return (generator, value) -> generator.writeString(value.getId());
    }
}
```

---

## Jackson Integration

```groovy
dependencies {
    annotationProcessor "ru.tinkoff.kora:json-annotation-processor"
    implementation "ru.tinkoff.kora:jackson-module"
}

@KoraApp
public interface Application extends JacksonModule {}
```

See [jackson-integration.md](references/jackson-integration.md) for the full guide.

---

## Troubleshooting

| Problem | Solution |
|---------|---------|
| JsonReader not found | Add `@Json` to the DTO/enum, verify `JsonModule` is wired |
| Missing field error | Fields are required by default — add `@Nullable` |
| Discriminator not found | Check `@JsonDiscriminatorField` on the sealed interface |
| Warning "mapper generated in a new round" | Verify `@Json` on all DTOs and enums |
| Jackson mapper not working | Add `jackson-module`, extend `JacksonModule` |

---

## Quick Reference

```java
// Annotations
@Json              // Reader + Writer (DTO, enum, sealed interface)
@JsonReader        // Deserialization only
@JsonWriter        // Serialization only
@JsonField("name") // Rename field
@JsonSkip          // Ignore field
@JsonDiscriminatorField("type")  // Sealed interface
@JsonDiscriminatorValue("OK")    // Discriminator value

// Field patterns
String name;                      // Required (default)
@Nullable String name;            // Optional
@JsonField("user_name") String userName;  // Rename
@JsonSkip String internal;        // Ignore
JsonNullable<String> optional;    // PATCH / missing vs null

// Enum — @Json is required, serialization via toString()
@Json  // otherwise warning "mapper generated in a new round"
public enum Status { PENDING, SHIPPED }  // JSON: "PENDING"

// Sealed interface
@Json
@JsonDiscriminatorField("status")
public sealed interface Result permits Success, Error {}

// Controller — @Json as a tag (requires HttpResultMapper/HttpRequestMapper with @Json)
@HttpController
public final class ApiController {
    @HttpRoute(method = HttpMethod.POST, path = "/items")
    @Json  // looks for HttpResultMapper with @Json, otherwise generates JsonWriter
    public ItemResponse create(@Json ItemRequest request) {}  // HttpRequestMapper with @Json
}
// Same pattern for Kafka, DB: @Json requires a mapper with this tag
```

---

## Reference Files

| File | Description |
|------|-------------|
| [references/json-annotations-reference.md](references/json-annotations-reference.md) | Full reference for @Json annotations |
| [references/sealed-interfaces-json.md](references/sealed-interfaces-json.md) | Sealed interfaces for polymorphic JSON |
| [references/custom-json-mappers.md](references/custom-json-mappers.md) | Custom JsonReader/JsonWriter |
| [references/jackson-integration.md](references/jackson-integration.md) | Jackson module integration |
| [references/json-best-practices.md](references/json-best-practices.md) | Best practices and patterns |

---

## Common Pitfalls

- **Missing `@Json` on DTO/enum** → compile-time mapper not generated. Always annotate DTOs and enums with `@Json`.
- **All fields required by default** → deserialization fails on missing fields. Use `@Nullable` for optional fields.
- **Discriminator value mismatch** → `@JsonDiscriminatorValue` must match JSON exactly (case-sensitive).
- **Discriminator field missing in JSON** → polymorphic deserialization requires the discriminator field (default: `type`).
- **`@JsonSkip` vs `@JsonInclude`** — `@JsonSkip` excludes from both read/write; `@JsonInclude` only affects serialization.
- **PATCH API: can't distinguish missing vs null** → use `JsonNullable<T>` for optional fields in PATCH requests.
