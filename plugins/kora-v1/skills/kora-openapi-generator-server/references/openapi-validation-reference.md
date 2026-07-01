# OpenAPI Validation Reference

**Kora Validation:** `ru.tinkoff.kora.validation.common.annotation.*` — Kora's own validation annotations, NOT Jakarta/JSR-380.

---

## 1. Overview

Kora OpenAPI Generator can produce Kora Validation annotations from OpenAPI schema constraints when `enableServerValidation: "true"` is set.

**Enable with:**
```groovy
configOptions = [
    mode: "java-server",
    enableServerValidation: "true",
    enableServerValidationInterceptor: "true"  // Auto 400 mapping
]
```

**Important:** Kora uses its own validation library (`ru.tinkoff.kora:validation-module`), NOT Jakarta Bean Validation or Hibernate Validator.

---

## 2. Generated Validation Annotations

### OpenAPI Constraints → Kora Validation Annotations

| OpenAPI Constraint | Generated Annotation |
|-------------------|---------------------|
| `required: true` | `@NotNull` |
| `minLength: N` | `@Size(min = N)` |
| `maxLength: N` | `@Size(max = N)` |
| `minimum: N` | `@Range(from = N)` |
| `maximum: N` | `@Range(to = N)` |
| `pattern: "..."` | `@Pattern("...")` |
| `format: email` | `@Pattern(regexp = "^[^@\\\\s]+@[^@\\\\s]+$")` |
| `format: uuid` | `@Pattern(regexp = "^[0-9a-fA-F]{8}-...$")` |
| `format: date-time` | `@PastOrPresent` / `@FutureOrPresent` |
| `nullable: true` | No annotation (allows null) |

### Example: OpenAPI Schema

```yaml
components:
  schemas:
    UserRequestTO:
      type: object
      required: [name, email]
      properties:
        name:
          type: string
          minLength: 1
          maxLength: 100
        email:
          type: string
          format: email
        age:
          type: integer
          minimum: 18
          maximum: 120
        status:
          type: string
          enum: [ACTIVE, INACTIVE, PENDING]
        tags:
          type: array
          items:
            type: string
          minItems: 1
          maxItems: 10
```

### Generated DTO

```java
package com.example.userapi.model;

import ru.tinkoff.kora.validation.common.annotation.*;
import java.util.List;

@Valid
public record UserRequestTO(
    
    @NotNull
    @Size(min = 1, max = 100)
    String name,
    
    @NotNull
    @Pattern(regexp = "^[^@\\\\s]+@[^@\\\\s]+$")
    String email,
    
    @Range(from = 18, to = 120)
    Integer age,
    
    @Pattern(regexp = "^(ACTIVE|INACTIVE|PENDING)$")
    String status,
    
    @Size(min = 1, max = 10)
    List<String> tags
) {}
```

---

## 3. ViolationException Handling

When validation fails on a handler, Kora throws a `ViolationException`
(`ru.tinkoff.kora.validation.common.ViolationException`).

Provide a `ViolationExceptionHttpServerResponseMapper`
(`ru.tinkoff.kora.validation.module.http.server.ViolationExceptionHttpServerResponseMapper`)
in the application graph to control the HTTP response. This matches the example app:

```java
import ru.tinkoff.kora.http.server.common.HttpServerResponseException;
import ru.tinkoff.kora.validation.module.http.server.ViolationExceptionHttpServerResponseMapper;

default ViolationExceptionHttpServerResponseMapper customViolationExceptionHttpServerResponseMapper() {
    return (request, exception) -> HttpServerResponseException.of(400, exception.getMessage());
}
```

Setting `enableServerValidationInterceptor: "true"` adds a generated interceptor
that routes validation failures through this mapper. See
[kora-aop-validation](../../kora-aop-validation/SKILL.md) for the full validation
annotation set and `@Validate` patterns.

---

## 4. Related

- [kora-aop-validation](../../kora-aop-validation/SKILL.md) — Kora Validation annotations, @Validate, ViolationException
- [OpenAPI Delegates Reference](openapi-delegates-reference.md) — Using DTOs in delegates
- [OpenAPI Controllers Reference](openapi-controllers-reference.md) — Controllers, interceptors
