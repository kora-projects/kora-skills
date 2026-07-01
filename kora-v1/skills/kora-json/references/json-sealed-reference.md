# Sealed Interfaces for Polymorphic JSON

Source of truth: `.kora-agent/kora-docs/mkdocs/docs/en/documentation/json.md`
(section "Sealed classes and interfaces"),
`.kora-agent/kora-examples/guides/java/kora-java-guide-json-app` (`UserResult`).

## Contents

1. [Overview](#1-overview)
2. [Basic pattern](#2-basic-pattern)
3. [JSON examples](#3-json-examples)
4. [How it works](#4-how-it-works)
5. [Controller usage](#5-controller-usage)
6. [Advanced patterns](#6-advanced-patterns)
7. [Kotlin support](#7-kotlin-support)
8. [Common pitfalls](#8-common-pitfalls)
9. [Quick reference](#9-quick-reference)

---

## 1. Overview

Sealed interfaces with `@JsonDiscriminatorField` enable type-safe polymorphic JSON:

- **Type-safe** — compile-time type checking
- **Discriminator-based** — explicit type field in JSON
- **Exhaustive** — compiler verifies all cases
- **Zero reflection** — generated mappers at compile time

---

## 2. Basic Pattern

### Define Sealed Interface

```java
@Json
@JsonDiscriminatorField("type")
public sealed interface PaymentResult 
    permits PaymentSuccess, PaymentError {}
```

**Annotations:**
- `@Json` — enables JSON serialization
- `@JsonDiscriminatorField("type")` — field name for type discriminator
- `permits` — lists allowed implementations (Java 17+)

### Define Implementations

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

---

## 3. JSON Examples

### Success Response
```json
{
    "type": "SUCCESS", 
    "transactionId": "txn_12345",
    "amount": 99.99
}
```
**Deserialized as:** `PaymentSuccess`

### Error Response
```json
{
    "type": "ERROR",
    "errorCode": "CARD_DECLINED",
    "message": "The card was declined"
}
```
**Deserialized as:** `PaymentError`

---

## 4. How It Works

### Deserialization
1. Kora reads the discriminator field value (`type`)
2. Finds the class with matching `@JsonDiscriminatorValue`
3. Deserializes JSON into the concrete record

### Serialization
1. Kora determines runtime type of the object
2. Adds discriminator field to JSON
3. Serializes remaining fields

---

## 5. Controller Usage

### Returning Sealed Interface

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

### Pattern Matching (Java 21+)

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

### Handling in Client Code

```java
@HttpRoute(method = HttpMethod.POST, path = "/notifications")
public void handleNotification(@Json PaymentResult result) { 
    switch (result) {
        case PaymentSuccess success -> { 
            log.info("Payment completed: {}", success.transactionId());
        }
        case PaymentError error -> { 
            log.warn("Payment failed: {} - {}", error.errorCode(), error.message());
        }
    } 
}
```

---

## 6. Advanced Patterns

### Multiple Discriminator Values

`@JsonDiscriminatorValue` accepts `String[]`, so pass several values as an array (do not
repeat the annotation):

```java
@JsonDiscriminatorValue({"CARD_SUCCESS", "BANK_SUCCESS"})
public record PaymentSuccess(
    String type,
    String transactionId,
    BigDecimal amount
) implements PaymentResult {}
```

**Both discriminator values deserialize to the same class.**

### Nested Sealed Interfaces

```java
@Json
@JsonDiscriminatorField("category")
public sealed interface Notification 
    permits EmailNotification, SmsNotification, PushNotification {}

@JsonDiscriminatorValue("EMAIL")
public record EmailNotification(
    String category, 
    String to, String subject, String body
) implements Notification {}

@JsonDiscriminatorValue("SMS")
public record SmsNotification(
    String category, 
    String phone, String message
) implements Notification {}
```

### Generic Sealed Interface

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

---

## 7. Kotlin Support

### Sealed Interfaces in Kotlin

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

### When Expression

```kotlin
@HttpController
class PaymentController(private val paymentService: PaymentService) {
     
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
            is PaymentSuccess -> log.info("Payment completed: ${result.transactionId}")
            is PaymentError -> log.warn("Payment failed: ${result.errorCode}")
        }
    }
}
```

---

## 8. Common Pitfalls

### Missing Discriminator Field

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

### Wrong Discriminator Value

```java
// WRONG — value doesn't match
@JsonDiscriminatorValue("OK")  // But interface expects "SUCCESS"
public record PaymentSuccess(String type) implements PaymentResult {}

// CORRECT
@JsonDiscriminatorValue("SUCCESS")
public record PaymentSuccess(String type) implements PaymentResult {}
```

### Missing @Json on Interface

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
            return new SuccessCase("SUCCESS", /* data */);
        } catch (Exception e) {
            return new ErrorCase("ERROR", "ERROR_CODE", e.getMessage());
        }
    }
}
```
