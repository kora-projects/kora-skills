# OpenAPI Models Reference

**Generated into:** `$buildDir/generated/<api-name>-server/<modelPackage>/`

## Contents

- [1. Overview](#1-overview)
- [2. Generated Model Types](#2-generated-model-types) (records, enums)
- [3. JsonNullable Wrapper](#3-jsonnullable-wrapper)
- [4. Discriminator Polymorphism](#4-discriminator-polymorphism)
- [5. Date/Time Types](#5-datetime-types)
- [6. Array and Map Types](#6-array-and-map-types)
- [7. Additional Properties](#7-additional-properties)
- [8. JsonInclude Configuration](#8-jsoninclude-configuration)
- [9. Model Inheritance](#9-model-inheritance)
- [10. Common Issues](#10-common-issues)
- [11. Related](#11-related)

---

## 1. Overview

Generated model classes (DTOs) represent OpenAPI schemas. They are used for:
- Request bodies (input)
- Response bodies (output)
- Path/query parameters (simple types)
- Polymorphic requests (discriminators)

**Naming conventions:**
- `*TO` — Transfer Object (default suffix)
- `*DTO` — Data Transfer Object (configurable)
- `*Request` / `*Response` — Custom suffixes

---

## 2. Generated Model Types

### Record Classes (Java 17+)

```yaml
UserResponseTO:
  type: object
  required: [id, name, email]
  properties:
    id:
      type: string
      format: uuid
    name:
      type: string
      minLength: 1
      maxLength: 100
    email:
      type: string
      format: email
```

Generated (with `enableServerValidation: "true"`):

```java
package com.example.userapi.model;

import ru.tinkoff.kora.validation.common.annotation.*;
import java.util.UUID;

public record UserResponseTO(
    
    @NotNull
    UUID id,
    
    @NotBlank
    @Size(min = 1, max = 100)
    String name,
    
    @NotBlank
    @Email
    String email
) {}
```

### Enum Classes

```yaml
UserStatus:
  type: string
  enum: [ACTIVE, INACTIVE, PENDING, SUSPENDED]
```

Generated:

```java
package com.example.userapi.model;

import com.fasterxml.jackson.annotation.*;

public enum UserStatus {
    
    @JsonProperty("ACTIVE")
    ACTIVE("ACTIVE"),
    
    @JsonProperty("INACTIVE")
    INACTIVE("INACTIVE"),
    
    @JsonProperty("PENDING")
    PENDING("PENDING"),
    
    @JsonProperty("SUSPENDED")
    SUSPENDED("SUSPENDED");
    
    private final String value;
    
    UserStatus(String value) {
        this.value = value;
    }
    
    @JsonValue
    public String getValue() {
        return value;
    }
    
    @JsonCreator
    public static UserStatus fromValue(String value) {
        for (UserStatus status : UserStatus.values()) {
            if (status.value.equals(value)) {
                return status;
            }
        }
        throw new IllegalArgumentException("Unknown UserStatus: " + value);
    }
}
```

---

## 3. JsonNullable Wrapper

For `nullable=true, required=false` fields, use `JsonNullable<T>`:

```groovy
configOptions = [
    mode: "java-server",
    enableJsonNullable: "true"
]
```

```yaml
UserUpdateRequest:
  type: object
  properties:
    name:
      type: string
      nullable: true  # Can explicitly set null
    email:
      type: string
      required: false  # Optional (may be absent)
```

Generated:

```java
import org.openapitools.jackson.nullable.JsonNullable;

public record UserUpdateRequest(
    
    JsonNullable<String> name,  // null = explicit null, absent = field not provided
    
    @JsonInclude(JsonInclude.Include.ALWAYS)
    String email  // Optional, no wrapper
) {}
```

**Usage:**

```java
@Override
public UserApiResponses.UpdateUserApiResponse updateUser(
    String userId,
    UserUpdateRequest request
) {
    User user = userService.findById(userId)
        .orElseThrow();
    
    // Check if name was explicitly set to null
    if (request.name().isPresent()) {
        user.setName(request.name().get());  // May be null
    }
    
    // Check if email was provided
    if (request.email() != null) {
        user.setEmail(request.email());
    }
    
    userService.update(user);
    return new UpdateUser200ApiResponse(mapper.toResponse(user));
}
```

---

## 4. Discriminator Polymorphism

### OpenAPI Spec

```yaml
Task:
  type: object
  description: Migration task
  oneOf:
    - $ref: '#/components/schemas/TaskUnconfirmed'
    - $ref: '#/components/schemas/TaskConfirmed'
  allOf:
    - $ref: '#/components/schemas/TaskCommon'
  discriminator:
    propertyName: migrationType
    mapping:
      UNCONFIRMED: '#/components/schemas/TaskUnconfirmed'
      CONFIRMED: '#/components/schemas/TaskConfirmed'

TaskCommon:
  type: object
  required: [migrationType, targetRepos]
  properties:
    migrationType:
      $ref: '#/components/schemas/MigrationType'
    targetRepos:
      type: array
      items:
        $ref: '#/components/schemas/TargetRepository'

TaskUnconfirmed:
  allOf:
    - $ref: '#/components/schemas/TaskCommon'
    - type: object
      required: [script]
      properties:
        script:
          $ref: '#/components/schemas/MigrationScript'

TaskConfirmed:
  allOf:
    - $ref: '#/components/schemas/TaskCommon'
    - type: object
      required: [scriptKey]
      properties:
        scriptKey:
          type: string
```

### Generated Classes

```java
// Base class
public class Task {
    
    @NotNull
    protected MigrationType migrationType;
    
    @NotNull
    protected List<TargetRepository> targetRepos;
    
    // Getters/setters
}

// Unconfirmed variant
public class TaskUnconfirmed extends Task {
    
    @NotNull
    private MigrationScript script;
    
    // Constructor sets migrationType = MigrationType.UNCONFIRMED
}

// Confirmed variant
public class TaskConfirmed extends Task {
    
    @NotNull
    private String scriptKey;
    
    // Constructor sets migrationType = MigrationType.CONFIRMED
}
```

### Delegate Implementation

```java
@Override
public MigrationApiResponses.CreateMigrationApiResponse createMigration(
    Task request  // Polymorphic base type
) {
    if (request.getMigrationType() == MigrationType.UNCONFIRMED) {
        // Cast to specific type for discriminator-specific fields
        TaskUnconfirmed unconfirmed = (TaskUnconfirmed) request;
        
        if (unconfirmed.getScript() == null) {
            return new CreateMigration400ApiResponse("Script required for UNCONFIRMED");
        }
        
        Migration migration = migrationService.createUnconfirmed(unconfirmed);
        return new CreateMigration201ApiResponse(mapper.toResponse(migration));
    } 
    else if (request.getMigrationType() == MigrationType.CONFIRMED) {
        TaskConfirmed confirmed = (TaskConfirmed) request;
        
        if (confirmed.getScriptKey() == null) {
            return new CreateMigration400ApiResponse("ScriptKey required for CONFIRMED");
        }
        
        Migration migration = migrationService.createConfirmed(confirmed);
        return new CreateMigration201ApiResponse(mapper.toResponse(migration));
    }
    
    return new CreateMigration400ApiResponse("Unknown migrationType");
}
```

---

## 5. Date/Time Types

### OpenAPI Formats

```yaml
properties:
  createdAt:
    type: string
    format: date-time
  birthDate:
    type: string
    format: date
  localTime:
    type: string
    format: time
```

### Generated Types

```java
public record UserRecord(
    
    @NotNull
    Instant createdAt,  // date-time → Instant
    
    @NotNull
    LocalDate birthDate,  // date → LocalDate
    
    @NotNull
    LocalTime localTime  // time → LocalTime
) {}
```

---

## 6. Array and Map Types

### Arrays

```yaml
properties:
  tags:
    type: array
    items:
      type: string
  scores:
    type: array
    items:
      type: integer
      format: int32
```

Generated:

```java
public record UserMetadata(
    
    @NotNull
    List<String> tags,
    
    @NotNull
    List<Integer> scores
) {}
```

### Maps

```yaml
properties:
  attributes:
    type: object
    additionalProperties:
      type: string
```

Generated:

```java
public record UserAttributes(
    
    @NotNull
    Map<String, String> attributes
) {}
```

---

## 7. Additional Properties

### Allow Arbitrary Fields

```yaml
DynamicConfig:
  type: object
  properties:
    name:
      type: string
  additionalProperties: true
```

Generated:

```java
public record DynamicConfig(
    
    String name,
    
    @JsonAnyGetter
    @JsonAnySetter
    Map<String, Object> additionalProperties
) {}
```

### Restrict Additional Properties

```yaml
StrictConfig:
  type: object
  additionalProperties: false  # No extra fields
```

Generated without `additionalProperties` field.

---

## 8. JsonInclude Configuration

Force inclusion of optional fields:

```groovy
configOptions = [
    mode: "java-server",
    forceIncludeOptional: "true"  // nullable=true, required=false
]
```

Generated:

```java
public record UserUpdateRequest(
    
    @JsonInclude(JsonInclude.Include.ALWAYS)
    String name,  // Always serialize, even if null
    
    String email  // Default behavior
) {}
```

---

## 9. Model Inheritance

```yaml
BaseUser:
  type: object
  required: [id, name]
  properties:
    id:
      type: string
    name:
      type: string

AdminUser:
  allOf:
    - $ref: '#/components/schemas/BaseUser'
    - type: object
      properties:
        permissions:
          type: array
          items:
            type: string
```

Generated:

```java
// Base class
public class BaseUser {
    
    @NotNull
    protected String id;
    
    @NotNull
    protected String name;
}

// Derived class
public class AdminUser extends BaseUser {
    
    @NotNull
    private List<String> permissions;
}
```

---

## 10. Common Issues

### Discriminator Not Working

```groovy
// Wrong: SIMPLIFY_ONEOF_ANYOF breaks discriminators
openapiNormalizer = [:]

// Correct: Disable normalizers
openapiNormalizer = [
    DISABLE_ALL: "true"
]
```

### Missing Validation Annotations

```groovy
// Wrong: Validation not enabled
configOptions = [
    mode: "java-server"
]

// Correct
configOptions = [
    mode: "java-server",
    enableServerValidation: "true"
]
```

### Wrong Date Type

```yaml
# Wrong: Custom format without typeMapping
createdAt:
  type: string
  format: custom-date

# Correct
createdAt:
  type: string
  format: date-time  # Standard format
```

---

## 11. Related

- [OpenAPI Validation Reference](openapi-validation-reference.md) — Kora validation annotations
- [OpenAPI Delegates Reference](openapi-delegates-reference.md) — Using models in delegates
- [Kora JSON Module](../../../.kora-agent/kora-docs/mkdocs/docs/en/documentation/json.md)
