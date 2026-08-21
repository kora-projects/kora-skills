# JSON Best Practices and Patterns

Source of truth: `.kora-agent/kora-docs/mkdocs/docs/en/documentation/json.md`,
`.kora-agent/kora-examples/guides/java/kora-java-guide-json-app`.

## Contents

1. [DTO design patterns](#1-dto-design-patterns)
2. [API versioning patterns](#2-api-versioning-patterns)
3. [Error response patterns](#3-error-response-patterns)
4. [PATCH endpoint patterns](#4-patch-endpoint-patterns)
5. [Collection handling](#5-collection-handling)
6. [Security considerations](#6-security-considerations)
7. [Performance](#7-performance-optimization)
8. [Testing patterns](#8-testing-patterns)
9. [Documentation patterns](#9-documentation-patterns)
10. [Quick reference](#10-quick-reference)

---
## 1. DTO Design Patterns
### 1.1 Separate Request/Response DTOs

```java
// GOOD — separate DTOs
@Json
public record CreateUserRequest(
    String name, 
    String email,
    String password
) {}

@Json
public record UserResponse(
    String id, 
    String name,
    String email, 
    LocalDateTime createdAt
) {}

// BAD — exposing the persistence row record directly as the HTTP body.
// Map the @Table/@Column DAO record (database layer) to a dedicated @Json DTO instead.
@Table("users")
public record UserRow(@Column("id") String id, @Column("name") String name) {}
```

**Why:**
- API evolution independence
- Hide internal fields
- Different validation rules
### 1.2 Request DTOs with @JsonReader

```java
@JsonReader
public record LoginRequest(
    String email,
    String password
) {}

// Only deserialization needed
@HttpRoute(method = HttpMethod.POST, path = "/login")
public LoginResponse login(@Json LoginRequest request) {
    // ...
}
```
### 1.3 Response DTOs with @JsonWriter

```java
@JsonWriter
public record HealthResponse(
    String status, 
    long uptime,
    Map<String, String> checks
) {}

// Only serialization needed
@HttpRoute(method = HttpMethod.GET, path = "/health")
@Json
public HealthResponse health() {
    // ...
}
```

---
## 2. API Versioning Patterns
### 2.1 DTO Versioning

```java
// V1 DTO
@Json
public record UserResponseV1(
    String id,
    String name
) {}

// V2 DTO with additional fields
@Json
public record UserResponseV2(
    String id,
    String name,
    String avatar,
    String bio
) {}
```
### 2.2 Controller Versioning

```java
@HttpController
public final class UserController {
     
    @HttpRoute(method = HttpMethod.GET, path = "/v1/users/{id}")
    @Json 
    public UserResponseV1 getUserV1(@Path String id) {
        User user = userService.findById(id); 
        return new UserResponseV1(user.getId(), user.getName());
    } 
    
    @HttpRoute(method = HttpMethod.GET, path = "/v2/users/{id}") 
    @Json
    public UserResponseV2 getUserV2(@Path String id) { 
        User user = userService.findById(id);
        return new UserResponseV2( 
            user.getId(),
            user.getName(), 
            user.getAvatar(),
            user.getBio() 
        );
    }
}
```

---
## 3. Error Response Patterns
### 3.1 Sealed Interface for API Responses

```java
@Json
@JsonDiscriminatorField("status")
public sealed interface ApiResponse<T> 
    permits SuccessResponse, ErrorResponse {}

@JsonDiscriminatorValue("SUCCESS")
public record SuccessResponse<T>(
    String status,
    T data,
    @Nullable String message
) implements ApiResponse<T> {}

@JsonDiscriminatorValue("ERROR")
public record ErrorResponse(
    String status,
    String code,
    String message,
    @Nullable List<FieldError> errors
) implements ApiResponse<Object> {

    public record FieldError(String field, String message) {}
}
```

**JSON examples:**

```json
// Success
{
    "status": "SUCCESS", 
    "data": {
        "id": "123", 
        "name": "John"
    }, 
    "message": null
}

// Error
{
    "status": "ERROR", 
    "code": "VALIDATION_ERROR",
    "message": "Invalid input data", 
    "errors": [
        {"field": "email", "message": "Invalid email format"}, 
        {"field": "password", "message": "Too short"}
    ]
}
```
### 3.2 Returning a typed JSON error from a route

Kora's HTTP server has no global `@ExceptionHandler`. To emit a typed JSON error body,
either return a JSON-mapped error type from the route, or throw
`HttpServerResponseException` and centralize error mapping in an
`HttpServerInterceptor` registered with `@InterceptWith`. The route-level form keeps the
error in the JSON contract:

```java
@HttpRoute(method = HttpMethod.POST, path = "/users")
@Json
public ApiResponse<UserResponse> createUser(@Json CreateUserRequest request) {
    var errors = validate(request);
    if (!errors.isEmpty()) {
        return new ErrorResponse("ERROR", "VALIDATION_ERROR", "Invalid input data", errors);
    }
    return new SuccessResponse<>("SUCCESS", userService.create(request), null);
}
```

For a non-200 status, throw `HttpServerResponseException.of(status, message)` and let an
interceptor serialize the error body; see the `kora-http-server` skill for interceptors.

---
## 4. PATCH Endpoint Patterns
### 4.1 JsonNullable for Partial Updates

```java
@Json
public record UpdateUserRequest(
    String id, 
    JsonNullable<String> name,
    JsonNullable<String> email, 
    JsonNullable<String> avatar
) {}

@HttpRoute(method = HttpMethod.PATCH, path = "/users/{id}")
@Json
public UserResponse updateUser(
    @Path String id, 
    @Json UpdateUserRequest request
) {
    User user = userService.findById(id);

    // Only update fields that were present in the JSON (value() may be null when isNull())
    if (request.name().isDefined()) {
        user.setName(request.name().value());
    }
    if (request.email().isDefined()) {
        user.setEmail(request.email().value());
    }
    if (request.avatar().isDefined()) {
        user.setAvatar(request.avatar().value());
    }

    return userService.update(user);
}
```

**JSON examples:**

```json
// Update only name
{
    "id": "123",
    "name": "New Name"
}

// Update only email
{
    "id": "123",
    "email": "new@example.com"
}

// Explicitly set field to null
{
    "id": "123",
    "avatar": null
}
```
### 4.2 Map-based Approach

```java
@Json
public record PatchRequest(
    Map<String, JsonNullable<Object>> fields
) {}

@HttpRoute(method = HttpMethod.PATCH, path = "/users/{id}")
public UserResponse patchUser(
    @Path String id, 
    @Json PatchRequest request
) {
    User user = userService.findById(id); 
    
    if (request.fields().containsKey("name")) {
        var value = request.fields().get("name");
        user.setName(value.isNull() ? null : (String) value.value());
    }
    // ... handle other fields 
    
    return userService.update(user);
}
```

---
## 5. Collection Handling
### 5.1 Empty Collections vs Null

```java
@Json
@JsonInclude(IncludeType.NON_EMPTY)
public record SearchResponse(
    List<Result> results,  // Won't serialize if empty
    int total,
    @Nullable String nextCursor  // Won't serialize if null
) {}
```

**JSON:**

```json
// With results
{
    "results": [...], 
    "total": 100
}

// Empty results (results field omitted)
{
    "total": 0
}
```
### 5.2 Paginated Response

```java
@Json
public record PaginatedResponse<T>(
    List<T> items,
    int page,
    int pageSize,
    long totalItems,
    int totalPages,
    @Nullable String nextCursor,
    @Nullable String prevCursor
) {
    public static <T> PaginatedResponse<T> of(
        List<T> items,
        int page,
        int pageSize,
        long totalItems
    ) {
        int totalPages = (int) Math.ceil((double) totalItems / pageSize); 
        String nextCursor = page < totalPages ? String.valueOf(page + 1) : null;
        String prevCursor = page > 1 ? String.valueOf(page - 1) : null;

        return new PaginatedResponse<>(
            items, page, pageSize, totalItems, totalPages,
            nextCursor, prevCursor
        );
    }
}
```

---
## 6. Security Considerations
### 6.1 Sensitive Field Exclusion

```java
@Json
public record UserResponse(
    String id, 
    String name,
    String email 
    // No password, token, or security fields!
) {}

// If a type carrying sensitive data must itself be @Json, skip those fields explicitly.
@Json
public record UserView(
    String id,
    String name,
    String email,
    @JsonSkip String passwordHash, // never serialized or read
    @JsonSkip String apiToken
) {}
```
### 6.2 Different DTOs for Different Contexts

```java
// Public response (minimal info)
@Json
public record PublicUserResponse(
    String id,
    String displayName
) {}

// Internal response (full info)
@Json
public record InternalUserResponse(
    String id,
    String name,
    String email,
    String role,
    LocalDateTime createdAt,
    LocalDateTime lastLogin
) {}

// Admin response (includes sensitive info)
@Json
public record AdminUserResponse(
    String id,
    String name,
    String email,
    String role,
    boolean active,
    int loginAttempts,
    LocalDateTime lastLogin,
    String passwordHash  // Only for admin
) {}
```

---
## 7. Performance Optimization
### 7.1 Avoid Nested Serialization

```java
// BAD — deep nesting
@Json
public record OrderResponse(
    String id, 
    CustomerResponse customer,  // Full customer object
    List<OrderItemResponse> items, 
    PaymentResponse payment,    // Full payment object
    ShippingResponse shipping   // Full shipping object
) {}

// GOOD — references only
@Json
public record OrderSummaryResponse(
    String id, 
    String customerId,
    int itemCount, 
    BigDecimal total,
    String status
) {}

// Fetch details separately if needed
@HttpRoute(method = HttpMethod.GET, path = "/orders/{id}/full")
@Json
public OrderResponse getOrderFull(@Path String id) {
    // Fetch complete order with all relations
}
```
### 7.2 Lazy Loading for Large Responses

```java
@Json
public record ReportResponse(
    String reportId,
    String name,
    LocalDateTime generatedAt,
    // Don't include large data inline
    String downloadUrl  // Pre-signed URL instead
) {}

// BAD — large inline data
@Json
public record BadReportResponse(
    String reportId,
    byte[] data,  // Large binary in JSON!
    String name
) {}
```

---
## 8. Testing Patterns
### 8.1 JSON Assertion Helpers

```java
class JsonAssertions {
     
    static void assertUserResponse(String json, User expected) {
        assertThatJson(json) 
            .inPath("id").isEqualTo(expected.getId())
            .inPath("name").isEqualTo(expected.getName()) 
            .inPath("email").isEqualTo(expected.getEmail())
            .inPath("createdAt").isNotNull() 
            .inPath("password").doesNotExist();  // Verify not exposed
    } 
    
    static void assertErrorResponse(String json, String code, String message) { 
        assertThatJson(json)
            .inPath("status").isEqualTo("ERROR") 
            .inPath("code").isEqualTo(code)
            .inPath("message").isEqualTo(message); 
    }
}
```
### 8.2 Round-trip Test

Inject the generated `JsonWriter<T>` / `JsonReader<T>` (available as components once the
DTO is `@Json` and `JsonModule` is wired) and round-trip through them. In a `@KoraAppTest`
they are pulled in with `@TestComponent`:

```java
@KoraAppTest(Application.class)
class UserResponseJsonTest {

    @TestComponent
    private JsonWriter<UserResponse> writer;
    @TestComponent
    private JsonReader<UserResponse> reader;

    @Test
    void roundTrip() {
        var original = new UserResponse("usr_123", "John Doe", "john@example.com", null);

        byte[] json = writer.toByteArray(original); // JsonWriter#toByteArray
        UserResponse decoded = reader.read(json);   // JsonReader#read(byte[])

        assertThat(decoded).isEqualTo(original);
    }
}
```

---
## 9. Documentation Patterns
### 9.1 DTO Documentation

```java
/**
 * User creation request. (Field-level constraints belong to the validation skill,
 * via @Validate / Kora validation annotations — kept out of the JSON contract here.)
 *
 * @param name User's full name (required)
 * @param email User's email address (required)
 * @param password User's password (required)
 */
@Json
public record CreateUserRequest(
    String name,
    String email,
    String password
) {}

/**
 * User response.
 * 
 * @param id Unique user identifier
 * @param name User's full name
 * @param email User's email address
 * @param createdAt Account creation timestamp (ISO-8601)
 */
@Json
public record UserResponse(
    String id, 
    String name,
    String email, 
    LocalDateTime createdAt
) {}
```
### 9.2 API Response Examples

```java
/**
 * Create a new user.
 * 
 * @param request User creation data
 * @return Created user with generated ID
 * 
 * **Request example:**
 * ```json
 * {
 *     "name": "John Doe",
 *     "email": "john@example.com",
 *     "password": "securepassword123"
 * }
 * ```
 * 
 * **Response example:**
 * ```json
 * {
 *     "id": "usr_abc123",
 *     "name": "John Doe",
 *     "email": "john@example.com",
 *     "createdAt": "2024-01-15T10:30:00Z"
 * }
 * ```
 */
@HttpRoute(method = HttpMethod.POST, path = "/users")
@Json
public UserResponse createUser(@Json CreateUserRequest request) {
    // ...
}
```

---
## 10. Quick Reference
### DTO Patterns

```java
// Request DTO
@JsonReader
public record CreateRequest(String name, String email) {}

// Response DTO
@JsonWriter
public record ResponseDto(String id, String name) {}

// Full DTO
@Json
public record UserDto(String id, String name, String email) {}

// Patch DTO
@Json
public record UpdateRequest(
    String id, 
    JsonNullable<String> name,
    JsonNullable<String> email
) {}
```
### Response Patterns

```java
// Success/Error with sealed interface
@Json
@JsonDiscriminatorField("status")
public sealed interface ApiResponse<T> 
    permits SuccessResponse, ErrorResponse {}

// Paginated response
@Json
public record PaginatedResponse<T>(
    List<T> items,
    long total,
    @Nullable String nextCursor
) {}
```
### Best Practices Checklist

- [ ] Separate request/response DTOs
- [ ] Use records instead of classes
- [ ] Document all fields
- [ ] Validate input fields
- [ ] Exclude sensitive data
- [ ] Use JsonNullable for PATCH
- [ ] Document API with examples
- [ ] Test round-trip serialization
