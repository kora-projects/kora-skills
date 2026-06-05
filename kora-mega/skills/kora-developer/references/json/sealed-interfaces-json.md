# Sealed Interfaces for Polymorphic JSON

**Source:** [.kora-agent/kora-docs/mkdocs/docs/en/documentation/json.md](.kora-agent/kora-docs/mkdocs/docs/en/documentation/json.md)  
**Examples:** `.kora-agent/kora-examples/kora-java-json-module/`

---
## 1. Overview

Sealed interfaces (Java 17+) with `@JsonDiscriminatorField` enable type-safe polymorphic JSON serialization:

- **Type-safe** — compile-time type checking
- **Discriminator-based** — explicit type field in JSON
- **Exhaustive** — compiler verifies all cases
- **Zero reflection** — generated mappers at compile time

---
## 2. Basic Pattern
### 2.1 Define Sealed Interface

```java
@Json
@JsonDiscriminatorField("type")
public sealed interface PaymentResult 
    permits PaymentSuccess, PaymentError {}
```

**Key annotations:**
- `@Json` — enables JSON serialization
- `@JsonDiscriminatorField("type")` — field name for type discriminator
- `permits` — lists allowed implementations (Java 17+)
### 2.2 Define Implementations

```java
@JsonDiscriminatorValue("SUCCESS")
public record PaymentSuccess(
    String type,  // Must match discriminator value
    String transactionId,
    BigDecimal amount
) implements PaymentResult {}

@JsonDiscriminatorValue("ERROR")
public record PaymentError(
    String type,  // Must match discriminator value
    String errorCode,
    String message
) implements PaymentResult {}
```

**Key annotations:**
- `@JsonDiscriminatorValue("X")` — discriminator value for this implementation
- `String type` — field must exist and match discriminator value

---
## 3. JSON Examples
### 3.1 Success Response

```json
{
    "type": "SUCCESS", 
    "transactionId": "txn_12345",
    "amount": 99.99
}
```

**Deserialized as:** `PaymentSuccess`
### 3.2 Error Response

```json
{
    "type": "ERROR",
    "errorCode": "CARD_DECLINED",
    "message": "The card was declined"
}
```

**Deserialized as:** `PaymentError`

---
## 4. Controller Usage
### 4.1 Returning Sealed Interface

```java
@HttpController
public final class PaymentController {
     
    private final PaymentService paymentService;
     
    public PaymentController(PaymentService paymentService) {
        this.paymentService = paymentService; 
    }
     
    @HttpRoute(method = HttpMethod.POST, path = "/payments/{id}")
    @Json 
    public PaymentResult processPayment(@Path String id) {
        try { 
            var transaction = paymentService.process(id);
            return new PaymentSuccess( 
                "SUCCESS",
                transaction.getId(), 
                transaction.getAmount()
            ); 
        } catch (PaymentException e) {
            return new PaymentError( 
                "ERROR",
                e.getErrorCode(), 
                e.getMessage()
            ); 
        }
    }
}
```
### 4.2 Pattern Matching (Java 21+)

```java
@HttpRoute(method = HttpMethod.GET, path = "/payments/{id}/status")
@Json
public Object getPaymentStatus(@Path String id) {
    PaymentResult result = paymentService.getResult(id);

    return switch (result) {
        case PaymentSuccess success -> Map.of(
            "status", "completed",
            "transactionId", success.transactionId()
        );
        case PaymentError error -> Map.of(
            "status", "failed",
            "errorCode", error.errorCode()
        );
    };
}
```
### 4.3 Handling in Client Code

```java
@HttpController
public final class NotificationController {
     
    @HttpRoute(method = HttpMethod.POST, path = "/notifications")
    public void handleNotification(@Json PaymentResult result) { 
        switch (result) {
            case PaymentSuccess success -> { 
                log.info("Payment completed: {}", success.transactionId());
                // Send success notification 
            }
            case PaymentError error -> { 
                log.warn("Payment failed: {} - {}", error.errorCode(), error.message());
                // Send failure notification 
            }
        } 
    }
}
```

---
## 5. Advanced Patterns
### 5.1 Multiple Discriminator Values

```java
@JsonDiscriminatorValue("CARD_SUCCESS")
@JsonDiscriminatorValue("BANK_SUCCESS")
public record PaymentSuccess(
    String type,
    String transactionId,
    BigDecimal amount
) implements PaymentResult {}
```

**Both discriminator values deserialize to same class.**
### 5.2 Nested Sealed Interfaces

```java
@Json
@JsonDiscriminatorField("category")
public sealed interface Notification 
    permits EmailNotification, SmsNotification, PushNotification {}

@JsonDiscriminatorValue("EMAIL")
public record EmailNotification(
    String category, 
    String to,
    String subject, 
    String body
) implements Notification {}

@JsonDiscriminatorValue("SMS")
public record SmsNotification(
    String category, 
    String phone,
    String message
) implements Notification {}

@JsonDiscriminatorValue("PUSH")
public record PushNotification(
    String category, 
    String deviceId,
    String title, 
    String body
) implements Notification {}
```
### 5.3 Common Fields in Base Interface

```java
@Json
@JsonDiscriminatorField("type")
public sealed interface ApiResponse<T> 
    permits SuccessResponse, ErrorResponse {}

@JsonDiscriminatorValue("SUCCESS")
public record SuccessResponse<T>(
    String type,
    T data,
    @Nullable String message
) implements ApiResponse<T> {}

@JsonDiscriminatorValue("ERROR")
public record ErrorResponse(
    String type,
    String errorCode,
    String message,
    @Nullable Map<String, String> details
) implements ApiResponse<Object> {}
```

**Usage:**

```java
@HttpRoute(method = HttpMethod.GET, path = "/users/{id}")
@Json
public ApiResponse<UserDto> getUser(@Path String id) {
    try { 
        UserDto user = userService.findById(id);
        return new SuccessResponse<>("SUCCESS", user, null); 
    } catch (UserNotFoundException e) {
        return new ErrorResponse("NOT_FOUND", "User not found", null); 
    }
}
```

---
## 6. Kotlin Support
### 6.1 Sealed Interfaces in Kotlin

```kotlin
@Json
@JsonDiscriminatorField("type")
sealed interface PaymentResult

@JsonDiscriminatorValue("SUCCESS")
data class PaymentSuccess(
    val type: String,
    val transactionId: String,
    val amount: BigDecimal
) : PaymentResult

@JsonDiscriminatorValue("ERROR")
data class PaymentError(
    val type: String,
    val errorCode: String,
    val message: String
) : PaymentResult
```
### 6.2 When Expression

```kotlin
@HttpController
class PaymentController(
    private val paymentService: PaymentService
) {
     
    @HttpRoute(method = HttpMethod.POST, path = "/payments/{id}")
    @Json 
    fun processPayment(@Path id: String): PaymentResult {
        return try { 
            val transaction = paymentService.process(id)
            PaymentSuccess("SUCCESS", transaction.id, transaction.amount) 
        } catch (e: PaymentException) {
            PaymentError("ERROR", e.errorCode, e.message) 
        }
    } 
    
    @HttpRoute(method = HttpMethod.POST, path = "/notifications") 
    fun handleNotification(@Json result: PaymentResult) {
        when (result) { 
            is PaymentSuccess -> {
                log.info("Payment completed: ${result.transactionId}") 
            }
            is PaymentError -> { 
                log.warn("Payment failed: ${result.errorCode} - ${result.message}")
            } 
        }
    }
}
```

---
## 7. Best Practices
### 7.1 Naming Conventions

**Discriminator field names:**
- `type` — most common, recommended
- `kind` — alternative
- `discriminator` — explicit
- `@class` — Jackson compatibility (avoid in Kora)

**Discriminator values:**
- `UPPER_CASE` — for enums/states (SUCCESS, ERROR)
- `snake_case` — for event types (payment.created, user.updated)
- Avoid camelCase — less readable in JSON
### 7.2 Exhaustive Handling

Always handle all cases:

```java
// GOOD — exhaustive switch
public void handle(PaymentResult result) {
    switch (result) {
        case PaymentSuccess s -> processSuccess(s);
        case PaymentError e -> processError(e);
    }
}

// BAD — non-exhaustive
public void handle(PaymentResult result) {
    if (result instanceof PaymentSuccess s) {
        processSuccess(s);
    }
    // PaymentError not handled!
}
```
### 7.3 Documentation

Document each discriminator value:

```java
/**
 * Payment processing result.
 * 
 * @param type Discriminator: "SUCCESS" or "ERROR"
 */
@Json
@JsonDiscriminatorField("type")
public sealed interface PaymentResult permits PaymentSuccess, PaymentError {}

/**
 * Successful payment result.
 * 
 * @param type Always "SUCCESS"
 * @param transactionId Unique transaction identifier
 * @param amount Payment amount
 */
@JsonDiscriminatorValue("SUCCESS")
public record PaymentSuccess(
    String type, 
    String transactionId,
    BigDecimal amount
) implements PaymentResult {}
```

---
## 8. Common Pitfalls
### 8.1 Missing Discriminator Field

```java
// WRONG — missing 'type' field
@JsonDiscriminatorValue("SUCCESS")
public record PaymentSuccess(
    String transactionId,  // Missing 'type' field!
    BigDecimal amount
) implements PaymentResult {}

// CORRECT
@JsonDiscriminatorValue("SUCCESS")
public record PaymentSuccess(
    String type,  // Required!
    String transactionId,
    BigDecimal amount
) implements PaymentResult {}
```
### 8.2 Wrong Discriminator Value

```java
// WRONG — value doesn't match
@JsonDiscriminatorValue("OK")  // But interface expects "SUCCESS"
public record PaymentSuccess(
    String type, 
    String transactionId
) implements PaymentResult {}

// CORRECT
@JsonDiscriminatorValue("SUCCESS")  // Matches expected value
public record PaymentSuccess(
    String type, 
    String transactionId
) implements PaymentResult {}
```
### 8.3 Missing @Json on Interface

```java
// WRONG — missing @Json
@JsonDiscriminatorField("type")
public sealed interface PaymentResult permits PaymentSuccess, PaymentError {}

// CORRECT
@Json
@JsonDiscriminatorField("type")
public sealed interface PaymentResult permits PaymentSuccess, PaymentError {}
```

---
## 9. Quick Reference
### Pattern Template

```java
@Json
@JsonDiscriminatorField("type")
public sealed interface ResultType 
    permits SuccessCase, ErrorCase {}

@JsonDiscriminatorValue("SUCCESS")
public record SuccessCase(
    String type, 
    // ... success-specific fields
) implements ResultType {}

@JsonDiscriminatorValue("ERROR")
public record ErrorCase(
    String type, 
    // ... error-specific fields
) implements ResultType {}
```
### Controller Pattern

```java
@HttpController
public final class ApiController {

    @HttpRoute(method = HttpMethod.POST, path = "/endpoint")
    @Json
    public ResultType handleRequest(@Json RequestDto request) {
        try {
            // Business logic
            return new SuccessCase("SUCCESS", /* data */);
        } catch (Exception e) {
            return new ErrorCase("ERROR", "ERROR_CODE", e.getMessage());
        }
    }
}
```
### JSON Examples

```json
// Success case
{
    "type": "SUCCESS", 
    "data": { ... }
}

// Error case
{
    "type": "ERROR", 
    "errorCode": "CODE",
    "message": "Description"
}
```
