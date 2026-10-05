# JSON Best Practices and Patterns (Kora 2.x)

Verified against the Kora 2.0 sources and the migrated `kora-java-json`,
`kora-kotlin-json`, `kora-java-guide-json-app` and `kora-kotlin-guide-json-app`
examples.

## Contents

1. [DTO design patterns](#1-dto-design-patterns)
2. [Migrating a 1.x codebase](#2-migrating-a-1x-codebase)
3. [Error response patterns](#3-error-response-patterns)
4. [PATCH endpoint patterns](#4-patch-endpoint-patterns)
5. [Collection handling](#5-collection-handling)
6. [Security considerations](#6-security-considerations)
7. [Performance](#7-performance)
8. [Testing patterns](#8-testing-patterns)
9. [Documentation patterns](#9-documentation-patterns)
10. [Quick reference](#10-quick-reference)

---

## 1. DTO Design Patterns

### 1.1 Separate request/response DTOs

```java
// GOOD — separate DTOs
@Json
public record CreateUserRequest(String name, String email, String password) {}

@Json
public record UserResponse(String id, String name, String email, LocalDateTime createdAt) {}

// BAD — exposing the persistence row record directly as the HTTP body.
// Map the @EntityJdbc/@Table row (database layer) to a dedicated @Json DTO instead.
@Table("users")
public record UserRow(@Column("id") String id, @Column("name") String name) {}
```

**Why:** independent API evolution, hidden internal fields, different validation rules.

### 1.2 Request DTOs with `@JsonReader`

```java
@JsonReader
public record LoginRequest(String email, String password) {}

@HttpRoute(method = HttpMethod.POST, path = "/login")
@Json
public LoginResponse login(@Json LoginRequest request) { … }
```

Generating only the direction you need keeps the build output smaller and makes an
accidental "we serialized the login request into a log" impossible.

### 1.3 Response DTOs with `@JsonWriter`

```java
@JsonWriter
public record HealthResponse(String status, long uptime, Map<String, String> checks) {}

@HttpRoute(method = HttpMethod.GET, path = "/health")
@Json
public HealthResponse health() { … }
```

### 1.4 Annotate the type, not just the parameter

`@Json` on a controller parameter marks the body as JSON, but the `JsonReader<T>` still has
to exist. Put `@Json` (or `@JsonReader`/`@JsonWriter`) on the DTO type itself so the mapper
is generated during ordinary annotation processing and reused by HTTP, Kafka and cache code
alike.

### 1.5 Version DTOs, not mappers

```java
@Json public record UserResponseV1(String id, String name) {}
@Json public record UserResponseV2(String id, String name, String avatar, String bio) {}
```

```java
@HttpRoute(method = HttpMethod.GET, path = "/v1/users/{id}")
@Json
public UserResponseV1 getUserV1(@Path String id) { … }

@HttpRoute(method = HttpMethod.GET, path = "/v2/users/{id}")
@Json
public UserResponseV2 getUserV2(@Path String id) { … }
```

---

## 2. Migrating a 1.x Codebase

Work in this order — a blind package rename leaves the last three items broken:

1. **Coordinates.** `ru.tinkoff.kora:kora-parent` → `io.koraframework:kora-bom`;
   `ru.tinkoff.kora:json-module` → `io.koraframework:json-common`.
2. **Packages.** `ru.tinkoff.kora.json.*` → `io.koraframework.json.common.*`;
   the module interface is `io.koraframework.json.common.JsonModule` and `JsonCommonModule`
   no longer exists.
3. **Jackson.** `com.fasterxml.jackson.core.*` → `tools.jackson.core.*`;
   `JsonParseException` → `tools.jackson.core.exc.StreamReadException`;
   `parser.getText()` → `getString()` / `getValueAsString()`;
   `gen.writeFieldName(...)` → `gen.writeName(...)`.
4. **`*Unchecked` methods.** `toStringUnchecked` → `toString`,
   `toByteArrayUnchecked` → `toByteArray`, `readUnchecked` → `read`.
5. **`IOException` handling.** The surviving methods declare no checked exception — only the
   unchecked `tools.jackson.core.JacksonException`. In Java a leftover `try/catch (IOException)` is now a **compile
   error**:

   ```java
   // 1.x
   try {
       return HttpServerResponse.of(code, HttpBody.json(errorJsonWriter.toByteArray(error)));
   } catch (IOException ex) {
       return HttpServerResponse.of(500, HttpBody.plaintext(ex.getMessage()));
   }

   // 2.x — drop the try/catch and the `import java.io.IOException;`
   return HttpServerResponse.of(code, HttpBody.json(errorJsonWriter.toByteArray(error)));
   ```

   In Kotlin the `catch (e: IOException)` compiles but is dead code — remove it too.
6. **Nullable reads.** `JsonReader<T>.read(...)` is annotated `@Nullable`. Kotlin cannot
   assign the result to a non-null type:

   ```kotlin
   val event = requireNotNull(reader.read(data))
   ```

   This bites hardest in Kafka listeners that decode a payload by hand.
7. **Async contracts.** Kora 2.0 JSON is synchronous — there is no `Mono`/`Flux`/
   `CompletionStage`/`suspend` reader or writer to port. Convert the call sites first, then
   the DTOs.

If phantom `ru.tinkoff.kora` errors survive the rename, they come from stale generated
sources: `./gradlew clean` with `--no-build-cache`. Never edit anything under
`build/generated`.

---

## 3. Error Response Patterns

### 3.1 A sealed interface for API responses

```java
@Json
@JsonDiscriminatorField("status")
public sealed interface ApiResponse<T> permits ApiResponse.Success, ApiResponse.Failure {

    @Json
    @JsonDiscriminatorValue("SUCCESS")
    record Success<T>(T data, @Nullable String message) implements ApiResponse<T> {}

    @Json
    @JsonDiscriminatorValue("ERROR")
    record Failure<T>(String code, String message, @Nullable List<FieldError> errors)
        implements ApiResponse<T> {}

    @Json
    record FieldError(String field, String message) {}
}
```

```json
{ "status": "SUCCESS", "data": { "id": "123", "name": "John" } }

{
  "status": "ERROR",
  "code": "VALIDATION_ERROR",
  "message": "Invalid input data",
  "errors": [ { "field": "email", "message": "Invalid email format" } ]
}
```

The discriminator is written by the generated sealed writer — no `String status` component
is needed on the subtypes.

### 3.2 Returning a typed JSON error from a route

Kora's HTTP server has no global `@ExceptionHandler`. Either return a JSON-mapped error type
from the route, or throw `HttpServerResponseException` and centralise error mapping in an
`HttpServerInterceptor`. The route-level form keeps the error inside the JSON contract:

```java
@HttpRoute(method = HttpMethod.POST, path = "/users")
@Json
public ApiResponse<UserResponse> createUser(@Json CreateUserRequest request) {
    var errors = validate(request);
    if (!errors.isEmpty()) {
        return new ApiResponse.Failure<>("VALIDATION_ERROR", "Invalid input data", errors);
    }
    return new ApiResponse.Success<>(userService.create(request), null);
}
```

For a non-200 status, throw `HttpServerResponseException.of(status, message)` and let an
interceptor serialise the body. In 2.0 a **global** interceptor is registered with
`@Tag(HttpServer.class)` — the 1.x `@Tag(HttpServerModule.class)` still compiles but is never
looked up, so the interceptor silently stops running. See the `kora-http-server` skill.

An interceptor that serialises an error body needs a `JsonWriter<ErrorTO>` injected, and its
`toByteArray` call must **not** be wrapped in `try/catch (IOException)`.

---

## 4. PATCH Endpoint Patterns

### 4.1 `JsonNullable` for partial updates

```java
@Json
public record UpdateUserRequest(
    JsonNullable<String> name,
    JsonNullable<String> email,
    JsonNullable<String> avatar
) {}

@HttpRoute(method = HttpMethod.PATCH, path = "/users/{id}")
@Json
public UserResponse updateUser(@Path String id, @Json UpdateUserRequest request) {
    var user = userService.findById(id);

    // Only touch fields that were present in the JSON; value() may be null when isNull()
    if (request.name().isDefined())   { user.setName(request.name().value()); }
    if (request.email().isDefined())  { user.setEmail(request.email().value()); }
    if (request.avatar().isDefined()) { user.setAvatar(request.avatar().value()); }

    return userService.update(user);
}
```

```json
{ "name": "New Name" }            // update only name
{ "avatar": null }                // explicitly clear avatar
{ }                               // touch nothing
```

### 4.2 Kotlin

```kotlin
@Json
data class UpdateUserRequest(
    val name: JsonNullable<String>,
    val email: JsonNullable<String>
)

if (request.name.isDefined) {
    user.name = request.name.value()
}
```

### 4.3 What not to do

- Do not model "missing" as `@Nullable T` — that collapses omitted and `null` into one state.
- Do not use `Optional<T>` — Kora has no built-in mapper for it, and it cannot express the
  third state anyway.
- Do not call `Optional`-style `isPresent()`/`get()` on `JsonNullable`; the API is
  `isDefined()` / `isNull()` / `value()`.

---

## 5. Collection Handling

### 5.1 Empty collections vs null

```java
@Json
@JsonInclude(IncludeType.NON_EMPTY)
public record SearchResponse(
    List<Result> results,             // omitted when empty
    int total,
    @Nullable String nextCursor       // omitted when null
) {}
```

```json
{ "results": [ … ], "total": 100 }
{ "total": 0 }
```

`NON_EMPTY` needs a `Collection`/`Map` type visible at compile time — on a bare type
parameter the emptiness check cannot be applied and the field behaves as `NON_NULL`.

If a client parses the response with a strict schema, prefer emitting an empty array over
omitting the key: keep the default `NON_NULL` and return `List.of()`.

### 5.2 Paginated response

```java
@Json
public record PaginatedResponse<T>(
    List<T> items,
    int page,
    int pageSize,
    long totalItems,
    int totalPages,
    @Nullable String nextCursor
) {}
```

A generic DTO needs a `JsonReader`/`JsonWriter` for each concrete `T` used — i.e. every `T`
must itself be `@Json`.

---

## 6. Security Considerations

### 6.1 Never let a secret reach the writer

```java
// GOOD — the response type simply has no secret fields
@Json
public record UserResponse(String id, String name, String email) {}

// Acceptable — the type must carry them, so exclude them explicitly
@Json
public record UserView(
    String id,
    String name,
    @JsonSkip String passwordHash,   // never written and never read
    @JsonSkip String apiToken
) {}
```

`@JsonSkip` removes the field from **both** directions. If a field must be accepted on read
but never echoed back, use two DTOs rather than one.

### 6.2 Different DTOs for different audiences

```java
@Json public record PublicUserResponse(String id, String displayName) {}
@Json public record InternalUserResponse(String id, String name, String email, String role) {}
```

Choosing the DTO by audience is enforced by the compiler; filtering fields at runtime is not.

### 6.3 `RawJson` is a trust boundary

`RawJson` content is emitted into the output document **verbatim**, without escaping or
validation. Only ever construct one from JSON your own code produced.

### 6.4 Unknown input fields are skipped

The generated reader skips properties it does not know (`nextToken(); skipChildren();`).
That makes forward-compatible clients easy, but it also means a typo in a request field name
is not reported — required fields are still enforced, optional ones silently stay `null`.

---

## 7. Performance

Kora's JSON is already reflection-free and generated; most wins are about payload shape.

### 7.1 Do not serialise more than the endpoint promises

```java
// BAD — deep object graph on every call
@Json
public record OrderResponse(String id, CustomerResponse customer,
                            List<OrderItemResponse> items, PaymentResponse payment) {}

// GOOD — summary plus a follow-up endpoint for the detail
@Json
public record OrderSummaryResponse(String id, String customerId, int itemCount,
                                   BigDecimal total, String status) {}
```

### 7.2 Keep large binaries out of JSON

```java
// GOOD — a link
@Json public record ReportResponse(String reportId, String name, String downloadUrl) {}

// BAD — a megabyte of base64 in the body
@Json public record BadReportResponse(String reportId, byte[] data) {}
```

### 7.3 Prefer `toByteArray` over `toString` for wire output

`toByteArray` writes UTF-8 directly through a recycled `ByteArrayBuilder`; `toString` goes
through a `SegmentedStringWriter` and then has to be encoded again. Reserve
`toPrettyString` for diagnostics.

### 7.4 Reuse the injected mappers

`JsonReader<T>`/`JsonWriter<T>` are singletons in the graph and safe to hold in a field.
Never construct a generated `*JsonReader` by hand.

---

## 8. Testing Patterns

### 8.1 Assert on the wire format, not just the object

```java
var json = writer.toString(value);
assertTrue(json.contains("\"identifier\""));      // @JsonField rename applied
assertTrue(json.contains("\"explicitNull\":null")); // @JsonInclude(ALWAYS) honoured
assertFalse(json.contains("internalOnly"));       // @JsonSkip honoured
```

A round-trip test alone passes even when both directions are wrong in the same way.

### 8.2 Round-trip test

Pull the generated mappers out of the graph with `@KoraAppTest` + `@TestComponent`:

```java
@KoraAppTest(Application.class)
class UserResponseJsonTest {

    @TestComponent
    private JsonWriter<UserResponse> writer;
    @TestComponent
    private JsonReader<UserResponse> reader;

    @Test
    void roundTrip() {
        var original = new UserResponse("usr_123", "John Doe", "john@example.com",
            LocalDateTime.of(2026, 8, 14, 10, 30));

        byte[] json = writer.toByteArray(original);   // no checked exception
        UserResponse decoded = reader.read(json);     // @Nullable

        assertThat(decoded).isEqualTo(original);
    }
}
```

```kotlin
@KoraAppTest(Application::class)
class UserResponseJsonTest {

    @TestComponent lateinit var writer: JsonWriter<UserResponse>
    @TestComponent lateinit var reader: JsonReader<UserResponse>

    @Test
    fun roundTrip() {
        val original = UserResponse("usr_123", "John Doe", "john@example.com",
            LocalDateTime.of(2026, 8, 14, 10, 30))

        val decoded = requireNotNull(reader.read(writer.toByteArray(original)))

        assertEquals(original, decoded)
    }
}
```

A `@Root @Component` holder that constructor-injects every mapper under test is a compact
way to prove the whole set is wirable — that is what the migrated `kora-java-json` example
does with `JsonRoot`.

### 8.3 Cover the JSON-specific edge cases

| Case | Assertion |
|---|---|
| `null` document | `reader.read("null")` returns `null` |
| omitted optional field | decodes, field is `null` |
| omitted required field | read fails |
| unknown extra field | ignored |
| `JsonNullable` | all three states: defined non-null, defined null, undefined |
| sealed subtype | each discriminator value, including every alias |
| enum | every constant, plus an unknown value |

---

## 9. Documentation Patterns

```java
/**
 * User creation request. Field-level constraints belong to Kora validation
 * (@Valid / @Validate) rather than to the JSON contract.
 *
 * @param name     user's full name (required)
 * @param email    user's email address (required)
 * @param password user's password (required)
 */
@Json
public record CreateUserRequest(String name, String email, String password) {}
```

Where the JSON name differs from the Java name, say so — a reader of the record sees
`userId`, the client sees `user_id`:

```java
@Json
public record ApiRequest(
    /** JSON key: {@code user_id}. */
    @JsonField("user_id") String userId
) {}
```

---

## 10. Quick Reference

### DTO patterns

```java
@JsonReader public record CreateRequest(String name, String email) {}          // inbound only
@JsonWriter public record ResponseDto(String id, String name) {}               // outbound only
@Json       public record UserDto(String id, String name, String email) {}     // both
@Json       public record UpdateRequest(JsonNullable<String> name) {}          // PATCH
```

### Response patterns

```java
@Json
@JsonDiscriminatorField("status")
public sealed interface ApiResponse<T> permits ApiResponse.Success, ApiResponse.Failure { … }

@Json
public record PaginatedResponse<T>(List<T> items, long total, @Nullable String nextCursor) {}
```

### Checklist

- [ ] Separate request/response DTOs; never expose a persistence row
- [ ] Records / data classes, `@Json` on the **type**
- [ ] JSpecify `@Nullable` (Kotlin `T?`) on every optional field
- [ ] `JsonNullable<T>` wherever "omitted" and "null" differ
- [ ] Sealed hierarchies for polymorphism — `@Json` on every subtype
- [ ] No secrets in a writable DTO; `@JsonSkip` if the type must carry them
- [ ] No `try/catch (IOException)` around `toByteArray`/`toString`
- [ ] Kotlin: `requireNotNull(reader.read(...))`
- [ ] Round-trip **and** wire-format assertions
