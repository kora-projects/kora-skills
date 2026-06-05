# JSON Best Practices and Patterns

**Source:** [.kora-agent/kora-docs/mkdocs/docs/en/documentation/json.md](.kora-agent/kora-docs/mkdocs/docs/en/documentation/json.md)  
**Examples:** `.kora-agent/kora-examples/kora-java-json/`

**Based on:** Kora documentation and production experience

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

// BAD — using entity as DTO
@Entity
@Table("users")
public class User {  // Don't expose entity directly!
    @Id 
    private String id;
    private String name; 
    // ...
}
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
### 3.2 Global Error Handler

```java
@HttpController
@Component
public final class GlobalExceptionHandler {

    @ExceptionHandler
    @Json
    public ErrorResponse handleValidationException(ValidationException e) {
        return new ErrorResponse(
            "ERROR",
            "VALIDATION_ERROR",
            e.getMessage(),
            e.getFieldErrors().stream() 
                .map(err -> new ErrorResponse.FieldError(err.getField(), err.getMessage()))
                .toList()
        );
    }

    @ExceptionHandler
    @Json
    public ErrorResponse handleNotFoundException(NotFoundException e) {
        return new ErrorResponse(
            "ERROR",
            "NOT_FOUND",
            e.getMessage(),
            null
        );
    }
}
```

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
    
    // Only update fields that were provided 
    if (request.name().isPresent()) {
        user.setName(request.name().get()); 
    }
    if (request.email().isPresent()) { 
        user.setEmail(request.email().get());
    } 
    if (request.avatar().isPresent()) {
        user.setAvatar(request.avatar().get()); 
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
        user.setName(value.isNull() ? null : (String) value.get()); 
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

// Internal entity with sensitive data
@Entity
public class User {
    @Id 
    private String id;
    private String name; 
    private String email;
     
    @JsonSkip  // Explicitly skip
    private String passwordHash; 
    
    @JsonSkip 
    private String apiToken;
}
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

```java
@Test
void testUserDtoRoundTrip() throws IOException {
    UserResponse original = new UserResponse(
        "usr_123",
        "John Doe",
        "john@example.com",
        LocalDateTime.now()
    );

    // Serialize
    String json = objectMapper.writeValueAsString(original);

    // Deserialize 
    UserResponse deserialized = objectMapper.readValue(json, UserResponse.class);

    // Verify
    assertThat(deserialized).isEqualTo(original);
}
```

---
## 9. Documentation Patterns
### 9.1 DTO Documentation

```java
/**
 * User creation request.
 * 
 * @param name User's full name (required, 2-100 chars)
 * @param email User's email address (required, valid email format)
 * @param password User's password (required, min 8 chars)
 */
@Json
public record CreateUserRequest(
    @NotBlank @Size(min = 2, max = 100) String name, 
    @NotBlank @Email String email,
    @NotBlank @Size(min = 8) String password
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
