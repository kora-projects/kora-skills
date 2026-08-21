# OpenAPI Response Reference

**Generated into:** `$buildDir/generated/<api-name>-server/<apiPackage>/`

## Contents

- [1. Overview](#1-overview)
- [2. Generated Structure](#2-generated-structure)
- [3. Response Selection Guide](#3-response-selection-guide)
- [4. Delegate Usage](#4-delegate-usage)
- [5. Responses with Headers](#5-responses-with-headers)
- [6. Multiple Response Codes per Operation](#6-multiple-response-codes-per-operation)
- [7. Controller Response Mapping](#7-controller-response-mapping)
- [8. Kotlin Pattern Matching](#8-kotlin-pattern-matching)
- [9. Response with No Content](#9-response-with-no-content)
- [10. Common Pitfalls](#10-common-pitfalls)
- [11. Testing Responses](#11-testing-responses)
- [12. Related](#12-related)

---

## 1. Overview

Generated `*ApiResponses` classes are **sealed interfaces** (Java 17+) that represent all possible HTTP responses for each operation. They provide type-safe response handling — Kora has no `ResponseEntity`.

**Key characteristics:**
- One sealed interface per operation (e.g., `GetUserApiResponse`)
- Each HTTP status is a separate record implementing the interface
- The delegate returns the sealed interface, never a raw DTO
- The generated controller maps the returned record to an HTTP response

---

## 2. Generated Structure

### OpenAPI Spec

```yaml
paths:
  /users/{userId}:
    get:
      operationId: getUser
      responses:
        "200":
          description: User found
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/UserResponseTO'
        "404":
          description: User not found
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/ErrorResponseTO'
        "500":
          description: Internal error
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/ErrorResponseTO'
```

### Generated Sealed Interface

```java
// build/generated/user-api-server/com/example/userapi/api/UserApiResponses.java
package com.example.userapi.api;

import com.example.userapi.model.UserResponseTO;
import com.example.userapi.model.ErrorResponseTO;

/**
 * Sealed interface for getUser operation responses.
 * Generated — DO NOT EDIT.
 */
public interface UserApiResponses {
    
    sealed interface GetUserApiResponse {
        
        record GetUser200ApiResponse(
            UserResponseTO content
        ) implements GetUserApiResponse {}
        
        record GetUser404ApiResponse(
            ErrorResponseTO content
        ) implements GetUserApiResponse {}
        
        record GetUser500ApiResponse(
            ErrorResponseTO content
        ) implements GetUserApiResponse {}
    }
}
```

---

## 3. Response Selection Guide

| HTTP Status | When to Use | Generated Class |
|-------------|-------------|-----------------|
| `200 OK` | Successful GET, PUT, PATCH | `*200ApiResponse(content)` |
| `201 Created` | Successful POST | `*201ApiResponse(content)` |
| `204 No Content` | Successful DELETE | `*204ApiResponse()` |
| `400 Bad Request` | Invalid input, business rules | `*400ApiResponse(error)` |
| `404 Not Found` | Resource not found | `*404ApiResponse(error)` |
| `409 Conflict` | Duplicate, version conflict | `*409ApiResponse(error)` |
| `422 Unprocessable Entity` | Semantic validation error | `*422ApiResponse(error)` |
| `500 Internal Error` | Unexpected failures | `*500ApiResponse(error)` |

---

## 4. Delegate Usage

### Simple Response (200 OK)

```java
@Component
public final class UserApiDelegateImpl implements UserApiDelegate {
    
    @Override
    public UserApiResponses.GetUserApiResponse getUser(String userId) {
        User user = userService.findById(userId)
            .orElseThrow(() -> new UserNotFoundException(userId));
        
        return new UserApiResponses.GetUserApiResponse.GetUser200ApiResponse(
            mapper.toResponse(user)
        );
    }
}
```

### Multiple Responses (200/404)

```java
@Override
public UserApiResponses.GetUserApiResponse getUser(String userId) {
    return userService.findById(userId)
        .<UserApiResponses.GetUserApiResponse>map(user -> 
            new UserApiResponses.GetUserApiResponse.GetUser200ApiResponse(
                mapper.toResponse(user)
            )
        )
        .orElseGet(() -> 
            new UserApiResponses.GetUserApiResponse.GetUser404ApiResponse(
                new ErrorResponseTO("User not found: " + userId)
            )
        );
}
```

### Business Logic Errors (400)

```java
@Override
public UserApiResponses.CreateUserApiResponse createUser(UserRequestTO request) {
    if (emailExists(request.email())) {
        return new UserApiResponses.CreateUserApiResponse.CreateUser400ApiResponse(
            new ErrorResponseTO("Email already exists: " + request.email())
        );
    }
    
    User user = userService.create(mapper.toEntity(request));
    return new UserApiResponses.CreateUserApiResponse.CreateUser201ApiResponse(
        mapper.toResponse(user)
    );
}
```

### No Content Response (204)

```java
@Override
public UserApiResponses.DeleteUserApiResponse deleteUser(String userId) {
    if (!userService.exists(userId)) {
        return new UserApiResponses.DeleteUserApiResponse.DeleteUser404ApiResponse(
            new ErrorResponseTO("User not found")
        );
    }
    
    userService.delete(userId);
    return new UserApiResponses.DeleteUserApiResponse.DeleteUser204ApiResponse();
}
```

---

## 5. Responses with Headers

### OpenAPI Spec with Custom Headers

```yaml
put:
  operationId: updateUser
  responses:
    "200":
      description: User updated
      headers:
        X-Updated-At:
          required: true
          description: Last update timestamp
          schema:
            type: string
            format: date-time
      content:
        application/json:
          schema:
            $ref: '#/components/schemas/UserResponseTO'
```

### Generated Response with Header

```java
sealed interface UpdateUserApiResponse {
    
    record UpdateUser200ApiResponse(
        UserResponseTO content,
        String xUpdatedAtHeader  // ← Header value
    ) implements UpdateUserApiResponse {}
    
    record UpdateUser400ApiResponse(
        ErrorResponseTO content
    ) implements UpdateUserApiResponse {}
}
```

### Delegate with Header

```java
@Override
public UserApiResponses.UpdateUserApiResponse updateUser(
    String userId,
    UserRequestTO request
) {
    Instant now = Instant.now();
    User user = userService.update(userId, mapper.toEntity(request));
    
    return new UserApiResponses.UpdateUserApiResponse.UpdateUser200ApiResponse(
        mapper.toResponse(user),
        now.toString()  // Header value
    );
}
```

---

## 6. Multiple Response Codes per Operation

Complex operation with many responses:

```yaml
post:
  operationId: processPayment
  responses:
    "200":
      description: Payment processed
    "400":
      description: Invalid request
    "402":
      description: Payment required (insufficient funds)
    "409":
      description: Duplicate transaction
    "500":
      description: Processing error
```

Generated sealed interface:

```java
sealed interface ProcessPaymentApiResponse {
    record ProcessPayment200ApiResponse(PaymentResultTO content) 
        implements ProcessPaymentApiResponse {}
    
    record ProcessPayment400ApiResponse(ErrorResponseTO content) 
        implements ProcessPaymentApiResponse {}
    
    record ProcessPayment402ApiResponse(ErrorResponseTO content) 
        implements ProcessPaymentApiResponse {}
    
    record ProcessPayment409ApiResponse(ErrorResponseTO content) 
        implements ProcessPaymentApiResponse {}
    
    record ProcessPayment500ApiResponse(ErrorResponseTO content) 
        implements ProcessPaymentApiResponse {}
}
```

---

## 7. Controller Response Mapping

The generated `*ApiController` inspects which sealed record the delegate returned,
serializes its body via the Kora JSON module, and writes the matching HTTP status
and any declared headers. This mapping lives entirely in generated code under
`build/generated/<api-name>-server/` — you do not write or override it. Your only
job is to return the correct record from the delegate; the contract's `responses`
section determines which records exist and which status each maps to.

---

## 8. Kotlin Pattern Matching

Kotlin's `when` expression provides elegant handling:

```kotlin
@Component
class UserApiDelegateImpl(
    private val userService: UserService
) : UserApiDelegate {

    override fun getUser(userId: String): UserApiResponses.GetUserApiResponse {
        val user = userService.findById(userId)
        
        return if (user != null) {
            UserApiResponses.GetUserApiResponse.GetUser200ApiResponse(
                mapper.toResponse(user)
            )
        } else {
            UserApiResponses.GetUserApiResponse.GetUser404ApiResponse(
                ErrorResponseTO("User not found: $userId")
            )
        }
    }

    override fun deleteUser(userId: String): UserApiResponses.DeleteUserApiResponse {
        return when {
            !userService.exists(userId) -> 
                UserApiResponses.DeleteUserApiResponse.DeleteUser404ApiResponse(
                    ErrorResponseTO("User not found")
                )
            else -> {
                userService.delete(userId)
                UserApiResponses.DeleteUserApiResponse.DeleteUser204ApiResponse()
            }
        }
    }
}
```

---

## 9. Response with No Content

### OpenAPI 204 Response

```yaml
delete:
  operationId: deleteUser
  responses:
    "204":
      description: User deleted (no content)
```

### Generated Response (No Fields)

```java
sealed interface DeleteUserApiResponse {
    
    record DeleteUser204ApiResponse()  // Empty record
        implements DeleteUserApiResponse {}
    
    record DeleteUser404ApiResponse(
        ErrorResponseTO content
    ) implements DeleteUserApiResponse {}
}
```

### Delegate Usage

```java
@Override
public UserApiResponses.DeleteUserApiResponse deleteUser(String userId) {
    if (!userService.exists(userId)) {
        return new DeleteUser404ApiResponse(
            new ErrorResponseTO("Not found")
        );
    }
    userService.delete(userId);
    return new DeleteUser204ApiResponse();  // No arguments
}
```

---

## 10. Common Pitfalls

### Wrong: Returning a Raw DTO

```java
// Wrong: a raw DTO is not a generated response record
@Override
public UserResponseTO getUser(String userId) {
    return mapper.toResponse(userService.findById(userId));
}

// Correct: return the generated sealed response record
@Override
public UserApiResponses.GetUserApiResponse getUser(String userId) {
    return new UserApiResponses.GetUserApiResponse.GetUser200ApiResponse(mapper.toResponse(user));
}
```

### Wrong: Ignoring Response Variants

```java
// Wrong: Only handles 200, ignores 404/500
@Override
public UserApiResponses.GetUserApiResponse getUser(String userId) {
    User user = userService.findById(userId).get();  // Throws if empty
    return new GetUser200ApiResponse(mapper.toResponse(user));
}

// Correct: Handle all variants
@Override
public UserApiResponses.GetUserApiResponse getUser(String userId) {
    return userService.findById(userId)
        .<UserApiResponses.GetUserApiResponse>map(u -> 
            new GetUser200ApiResponse(mapper.toResponse(u))
        )
        .orElseGet(() -> 
            new GetUser404ApiResponse(new ErrorResponseTO("Not found"))
        );
}
```

---

## 11. Testing Responses

### Unit Test with Sealed Interface

```java
@Test
void getUser_found_returns200() {
    User user = new User("123", "John", "john@example.com");
    when(userService.findById("123")).thenReturn(Optional.of(user));
    
    UserApiResponses.GetUserApiResponse response = 
        delegate.getUser("123");
    
    assertThat(response)
        .isInstanceOf(UserApiResponses.GetUserApiResponse.GetUser200ApiResponse.class);
    
    var successResponse = (UserApiResponses.GetUserApiResponse.GetUser200ApiResponse) response;
    assertThat(successResponse.content().name()).isEqualTo("John");
}

@Test
void getUser_notFound_returns404() {
    when(userService.findById("123")).thenReturn(Optional.empty());
    
    UserApiResponses.GetUserApiResponse response = 
        delegate.getUser("123");
    
    assertThat(response)
        .isInstanceOf(UserApiResponses.GetUserApiResponse.GetUser404ApiResponse.class);
}
```

---

## 12. Related

- [OpenAPI Delegates Reference](openapi-delegates-reference.md) — Delegate interfaces
- [OpenAPI Controllers Reference](openapi-controllers-reference.md) — Response mapping
- [OpenAPI Models Reference](openapi-models-reference.md) — DTO structures
