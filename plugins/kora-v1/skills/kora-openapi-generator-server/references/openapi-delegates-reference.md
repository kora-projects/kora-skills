# OpenAPI Delegates Reference

**Generated into:** `$buildDir/generated/<api-name>-server/<apiPackage>/`

## Contents

- [1. Overview](#1-overview)
- [2. Generated Interface Structure](#2-generated-interface-structure)
- [3. Implementation Pattern](#3-implementation-pattern) (sync / async / reactive / suspend)
- [4. Method Signature Mapping](#4-method-signature-mapping)
- [5. Configuration Options](#5-configuration-options) (`requestInDelegateParams`, `delegateMethodBodyMode`)
- [6. Generated Files Summary](#6-generated-files-summary)
- [7. Common Issues](#7-common-issues)
- [8. Related](#8-related)

---

## 1. Overview

Generated `*ApiDelegate` interfaces are the **only implementation point** for OpenAPI server code. Delegates separate business logic from HTTP transport concerns.

**Key characteristics:**
- One interface per OpenAPI tag (e.g., `UsersApiDelegate`, `OrdersApiDelegate`)
- Methods return sealed `*ApiResponses` interfaces (NOT `ResponseEntity<T>`)
- Generated — **never edit**
- Implement with `@Component` for DI discovery

---

## 2. Generated Interface Structure

### Example OpenAPI Spec

```yaml
tags:
  - name: users
    description: User management operations

paths:
  /users/{userId}:
    get:
      tags: [users]
      operationId: getUser
      parameters:
        - name: userId
          in: path
          required: true
          schema:
            type: string
            format: uuid
      responses:
        "200":
          description: User found
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/UserResponseTO'
        "404":
          description: User not found
  
  /users:
    post:
      tags: [users]
      operationId: createUser
      requestBody:
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/UserRequestTO'
      responses:
        "201":
          description: Created
        "400":
          description: Invalid input
```

### Generated Delegate Interface

```java
// build/generated/user-api-server/com/example/userapi/api/UserApiDelegate.java
package com.example.userapi.api;

import com.example.userapi.model.UserRequestTO;
import java.util.concurrent.CompletionStage;

public interface UserApiDelegate {

    /**
     * GET /users/{userId}
     * 
     * @param userId User UUID (path parameter)
     * @return Sealed response interface with 200, 404, 500 variants
     */
    UserApiResponses.GetUserApiResponse getUser(String userId);

    /**
     * POST /users
     * 
     * @param request User creation request body
     * @return Sealed response interface with 201, 400, 500 variants
     */
    UserApiResponses.CreateUserApiResponse createUser(UserRequestTO request);
}
```

---

## 3. Implementation Pattern

### Synchronous Delegate (Recommended)

```java
package com.example.userapi.api;

import com.example.userapi.model.UserResponseTO;
import com.example.userapi.model.ErrorResponseTO;
import ru.tinkoff.kora.common.Component;

@Component
public final class UserApiDelegateImpl implements UserApiDelegate {
    
    private final UserService userService;
    private final UserMapper mapper;

    public UserApiDelegateImpl(UserService userService, UserMapper mapper) {
        this.userService = userService;
        this.mapper = mapper;
    }

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

    @Override
    public UserApiResponses.CreateUserApiResponse createUser(UserRequestTO request) {
        try {
            var user = userService.create(mapper.toEntity(request));
            return new UserApiResponses.CreateUserApiResponse.CreateUser201ApiResponse(
                mapper.toResponse(user)
            );
        } catch (EmailAlreadyExistsException e) {
            return new UserApiResponses.CreateUserApiResponse.CreateUser400ApiResponse(
                new ErrorResponseTO(e.getMessage())
            );
        }
    }
}
```

### Async Delegate (CompletionStage)

```java
@Component
public final class UserApiDelegateImpl implements UserApiDelegate {
    
    private final UserService userService;

    @Override
    public CompletionStage<UserApiResponses.GetUserApiResponse> getUser(String userId) {
        return userService.findByIdAsync(userId)
            .thenApply(user -> 
                user.<UserApiResponses.GetUserApiResponse>map(u -> 
                    new UserApiResponses.GetUserApiResponse.GetUser200ApiResponse(
                        mapper.toResponse(u)
                    )
                )
                .orElseGet(() -> 
                    new UserApiResponses.GetUserApiResponse.GetUser404ApiResponse(
                        new ErrorResponseTO("Not found")
                    )
                )
            );
    }
}
```

### Reactive Delegate (Mono)

```java
@Component
public final class UserApiDelegateImpl implements UserApiDelegate {
    
    private final UserService userService;

    @Override
    public Mono<UserApiResponses.GetUserApiResponse> getUser(String userId) {
        return userService.findByIdReactive(userId)
            .map(user -> 
                new UserApiResponses.GetUserApiResponse.GetUser200ApiResponse(
                    mapper.toResponse(user)
                )
            )
            .defaultIfEmpty(
                new UserApiResponses.GetUserApiResponse.GetUser404ApiResponse(
                    new ErrorResponseTO("Not found")
                )
            );
    }
}
```

### Kotlin Suspend Delegate

```kotlin
@Component
class UserApiDelegateImpl(
    private val userService: UserService
) : UserApiDelegate {

    override suspend fun getUser(userId: String): UserApiResponses.GetUserApiResponse {
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
}
```

---

## 4. Method Signature Mapping

| OpenAPI | Delegate Method |
|---------|-----------------|
| `operationId` | Method name |
| `tags` | Interface name (`*ApiDelegate`) |
| `parameters` (path/query) | Method arguments |
| `requestBody` | Method argument (DTO) |
| `responses` | Return type (`*ApiResponses.*ApiResponse`) |

### Parameter Mapping Examples

```yaml
# Path + Query parameters
/users/{userId}/orders/{orderId}?includeItems=true
```

```java
UserApiResponses.GetOrderApiResponse getOrder(
    String userId,      // path
    String orderId,     // path
    Boolean includeItems // query
);
```

### Request Body Mapping

```yaml
requestBody:
  required: true
  content:
    application/json:
      schema:
        $ref: '#/components/schemas/CreateUserRequest'
```

```java
UserApiResponses.CreateUserApiResponse createUser(
    @Valid CreateUserRequest request  // @Valid if validation enabled
);
```

---

## 5. Configuration Options

### requestInDelegateParams

Include `HttpServerRequest` as delegate method argument:

```groovy
configOptions = [
    mode: "java-server",
    requestInDelegateParams: "true"
]
```

```java
UserApiResponses.GetUserApiResponse getUser(
    String userId,
    HttpServerRequest request  // ← Added
);
```

**Use cases:**
- Access raw headers not in OpenAPI spec
- Read query parameters dynamically
- Access request context/attributes

### delegateMethodBodyMode

Generate default method body (for prototyping):

```groovy
configOptions = [
    mode: "java-server",
    delegateMethodBodyMode: "throw-exception"
]
```

```java
default UserApiResponses.GetUserApiResponse getUser(String userId) {
    throw new UnsupportedOperationException("Not implemented");
}
```

**Values:**
- `none` (default) — empty method body (abstract)
- `throw-exception` — throws `UnsupportedOperationException`

---

## 6. Generated Files Summary

| File | Purpose | Edit? |
|------|---------|-------|
| `*ApiDelegate.java` | Interface to implement | **Implement** |
| `*ApiController.java` | HTTP controller | **Never** |
| `*ApiResponses.java` | Sealed response types | **Never** |

---

## 7. Common Issues

### Not Discovered by DI

```java
// Missing @Component
public final class UserApiDelegateImpl implements UserApiDelegate { ... }

// Fix: Add @Component
@Component
public final class UserApiDelegateImpl implements UserApiDelegate { ... }
```

### Wrong Return Type

```java
// Wrong: returning a raw DTO instead of the generated sealed response
@Override
public UserResponseTO getUser(String userId) { ... }

// Correct: return the generated sealed response (Kora has no ResponseEntity)
@Override
public UserApiResponses.GetUserApiResponse getUser(String userId) { ... }
```

### Type Mismatch

```java
// OpenAPI has format: uuid
// Delegate expects UUID, not String
@Override
public UserApiResponses.GetUserApiResponse getUser(UUID userId) { ... }
```

---

## 8. Related

- [OpenAPI Controllers Reference](openapi-controllers-reference.md) — Generated controllers
- [OpenAPI Response Reference](openapi-response-reference.md) — Response wrappers
- [OpenAPI Validation Reference](openapi-validation-reference.md) — Kora validation annotations
- [OpenAPI Codegen Reference](openapi-codegen-reference.md) — Full configuration
