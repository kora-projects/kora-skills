# OpenAPI Validation Reference

**Source:** [.kora-agent/kora-docs/mkdocs/docs/en/documentation/openapi-codegen.md](.kora-agent/kora-docs/mkdocs/docs/en/documentation/openapi-codegen.md)  
**Examples:** `.kora-agent/kora-examples/kora-java-openapi-generator-http-server/`

## 1. Overview

Kora OpenAPI Generator can generate validation annotations on server-side DTOs and controller methods based on OpenAPI specification constraints.

## 2. Enable Server Validation

```groovy
configOptions = [
    mode: "java-server",
    enableServerValidation: "true"
]
```

## 3. Generated Validation Annotations

### Required Fields

OpenAPI:
```yaml
components:
  schemas:
    Pet:
      type: object
      required:
        - id
        - name
      properties:
        id:
          type: integer
        name:
          type: string
```

Generated DTO:
```java
public record Pet(
    @NotNull Long id,
    @NotNull String name
) {}
```

### String Constraints

OpenAPI:
```yaml
properties:
  name:
    type: string
    minLength: 1
    maxLength: 100
    pattern: "^[a-zA-Z]+$"
```

Generated DTO:
```java
public record Pet(
    @NotNull
    @Size(min = 1, max = 100)
    @Pattern(regexp = "^[a-zA-Z]+$")
    String name
) {}
```

### Numeric Constraints

OpenAPI:
```yaml
properties:
  age:
    type: integer
    minimum: 0
    maximum: 150
  price:
    type: number
    exclusiveMinimum: 0
```

Generated DTO:
```java
public record Pet(
    @Min(0)
    @Max(150)
    Integer age,
    
    @DecimalMin(value = "0", inclusive = false)
    BigDecimal price
) {}
```

### Collection Constraints

OpenAPI:
```yaml
properties:
  tags:
    type: array
    minItems: 1
    maxItems: 10
    uniqueItems: true
```

Generated DTO:
```java
public record Pet(
    @NotNull
    @Size(min = 1, max = 10)
    Set<String> tags
) {}
```

### Nested Validation

OpenAPI:
```yaml
properties:
  address:
    $ref: '#/components/schemas/Address'
```

Generated DTO:
```java
public record Pet(
    @NotNull
    @Valid
    Address address
) {}
```

## 4. Controller Method Validation

Generated controller interface:
```java
@HttpController
public interface PetApi {
    @HttpRoute(path = "/pets", method = "POST")
    PetApiResponses.AddPetApiResponse addPet(
        @NotNull @Valid @Body Pet body
    );
}
```

Delegate implementation:
```java
@Component
public final class PetApiDelegate implements PetApiDelegate {
    @Override
    public PetApiResponses.AddPetApiResponse addPet(@NotNull @Valid Pet body) {
        // Validation happens automatically before this method is called
        return new PetApiResponses.AddPetApiResponse.AddPet200ApiResponse(petService.create(body));
    }
}
```

## 5. Validation Error Responses

When validation fails, Kora automatically returns:

```http
HTTP/1.1 400 Bad Request
Content-Type: application/json

{
  "type": "validation_error",
  "errors": [
    {
      "field": "name",
      "message": "must not be null"
    },
    {
      "field": "age",
      "message": "must be greater than or equal to 0"
    }
  ]
}
```

## 6. Custom Validation

### Custom Constraint Annotation

```java
@Target({ElementType.FIELD})
@Retention(RetentionPolicy.RUNTIME)
@Constraint(validatedBy = ValidPetStatusValidator.class)
public @interface ValidPetStatus {
    String message() default "Invalid pet status";
    Class<?>[] groups() default {};
    Class<? extends Payload>[] payload() default {};
}
```

### Validator Implementation

```java
public final class ValidPetStatusValidator implements ConstraintValidator<ValidPetStatus, String> {
    private static final Set<String> VALID_STATUSES = Set.of("available", "pending", "sold");
    
    @Override
    public boolean isValid(String value, ConstraintValidatorContext context) {
        if (value == null) {
            return true;  // Let @NotNull handle nulls
        }
        return VALID_STATUSES.contains(value.toLowerCase());
    }
}
```

### Usage in DTO

```java
public record Pet(
    @NotNull
    @ValidPetStatus
    String status
) {}
```

## 7. Manual Validation in Delegate

For business logic validation:

```java
@Component
public final class PetApiDelegate implements PetApiDelegate {
    @Override
    public PetApiResponses.AddPetApiResponse addPet(@Valid Pet body) {
        // Business logic validation
        if (!petService.isNameUnique(body.name())) {
            throw new ConflictException("Pet with name " + body.name() + " already exists");
        }
        
        if (body.age() < 0 || body.age() > 150) {
            throw new BadRequestException("Age must be between 0 and 150");
        }
        
        return new PetApiResponses.AddPetApiResponse.AddPet200ApiResponse(petService.create(body));
    }
}
```

## 8. Validation Groups

For different validation scenarios:

```java
public record Pet(
    @NotNull(groups = UpdateGroup.class)
    Long id,
    
    @NotNull(groups = CreateGroup.class)
    @Size(min = 1, max = 100)
    String name
) {}

public interface CreateGroup {}
public interface UpdateGroup {}
```

Controller with groups:
```java
@HttpRoute(path = "/pets", method = "POST")
PetApiResponses.AddPetApiResponse addPet(
    @Validated(CreateGroup.class) @Body Pet body
);
```

## 9. Nullable vs Required

### OpenAPI 3.0

```yaml
properties:
  name:
    type: string
    nullable: true
required:
  - id
```

Generated with `enableJsonNullable: "true"`:
```java
public record Pet(
    @NotNull Long id,
    JsonNullable<String> name  // Nullable but not required
) {}
```

### Force Include Optional

```groovy
configOptions = [
    enableJsonNullable: "true",
    forceIncludeOptional: "true"
]
```

```java
public record Pet(
    @NotNull Long id,
    @JsonInclude(JsonInclude.Include.ALWAYS)
    JsonNullable<String> name
) {}
```

## 10. Validation Dependencies

Add validation dependency to `build.gradle`:

```groovy
dependencies {
    implementation "ru.tinkoff.kora:validation-module"
}
```

**Note:** Kora's `validation-module` provides all necessary validation functionality. Do NOT add `hibernate-validator` — it's not needed and may cause conflicts.

## 11. Troubleshooting

| Problem | Solution |
|---------|----------|
| Validation annotations not generated | Set `enableServerValidation: "true"` |
| Validation not triggered | Add `validation-module` dependency |
| 400 response not returned | Check exception handler is configured |
| Nested validation not working | Add `@Valid` annotation |
| Custom validator not found | Ensure validator is in classpath |

---

## Related References

- [openapi-codegen-reference.md](openapi-codegen-reference.md) — OpenAPI Generator configuration
- [authorization-reference.md](authorization-reference.md) — Authorization mechanisms
- [interceptors-reference.md](interceptors-reference.md) — Interceptors for clients and servers
