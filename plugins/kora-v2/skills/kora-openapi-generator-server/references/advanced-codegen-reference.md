# Advanced OpenAPI Codegen Options

**Kora Version:** 1.2.x  
**OpenAPI Generator:** 7.14.0

This reference covers advanced `kora` generator options for HTTP server codegen, including `requestInDelegateParams` and handling `oneOf`/`allOf` schemas.

---

## requestInDelegateParams

### Purpose

By default, generated delegate methods have parameters corresponding only to the OpenAPI spec (path/query/header params, request body). To access the raw `HttpServerRequest` (e.g., for computing fingerprints from multiple headers, reading untyped query params, or accessing low-level request metadata), enable `requestInDelegateParams`.

### Configuration

```groovy
def openApiGenerateHttpServer = tasks.register("openApiGenerateHttpServer", GenerateTask) {
    generatorName = "kora"
    inputSpec = "$projectDir/src/main/resources/openapi/api.yaml"
    outputDir = "$buildDir/generated/api-server"
    
    configOptions = [
        mode: "java-server",
        requestInDelegateParams: "true",  // Adds HttpServerRequest as FIRST parameter
    ]
}
```

### Generated Signature

**Without `requestInDelegateParams`:**
```java
public GetUserApiResponse getUser(String userId, @Nullable String fields)
```

**With `requestInDelegateParams`:**
```java
public GetUserApiResponse getUser(
    HttpServerRequest _serverRequest,  // FIRST parameter
    String userId,
    @Nullable String fields
)
```

### Use Cases

**1. Compute fingerprint from multiple headers:**
```java
@Override
public GetUserApiResponse getUser(HttpServerRequest _serverRequest, String userId) {
    String userAgent = _serverRequest.header("User-Agent");
    String accept = _serverRequest.header("Accept");
    String fingerprint = computeFingerprint(userAgent, accept);
    return userService.findById(userId, fingerprint)
        .map(GetUserApiResponse::new)
        .orElseGet(() -> new GetUser404ApiResponse());
}
```

**2. Read untyped query params:**
```java
@Override
public SearchApiResponse search(HttpServerRequest _serverRequest) {
    // Access query params not defined in spec
    String extraParam = _serverRequest.queryParam("extra");
    // ...
}
```

**3. Access raw request metadata:**
```java
@Override
public CreateApiResponse create(HttpServerRequest _serverRequest, CreateRequest request) {
    Instant receivedAt = Instant.now();
    String remoteAddr = _serverRequest.remoteAddress();
    // Audit logging
    auditLog.log(remoteAddr, receivedAt, request);
    // ...
}
```

### Verification

After enabling the option, inspect generated delegates:

```bash
cat build/generated/openapi/api/src/main/java/com/example/api/*Delegate.java
```

Look for `HttpServerRequest _serverRequest` as the first parameter.

---

## oneOf / allOf Without Discriminator

### Problem

Kora generator 7.14.0 **collapses `oneOf` without discriminator into an empty record** — this breaks wire compatibility.

**Example spec (broken):**
```yaml
components:
  schemas:
    PaymentResult:
      oneOf:
        - $ref: '#/components/schemas/PendingResult'
        - $ref: '#/components/schemas/CompletedResult'
```

**Generated (broken):**
```java
// Empty record!
public record PaymentResult() {}
```

### Workaround: Flatten to Single Schema

Convert `oneOf` to a single object schema with all fields `nullable` (boxed types, not primitives):

```yaml
components:
  schemas:
    PaymentResult:
      type: object
      properties:
        status:
          type: string
          enum: [pending, completed]
        # Pending-specific fields
        estimatedCompletionTime:
          type: string
          format: date-time
          nullable: true
        # Completed-specific fields
        transactionId:
          type: string
          nullable: true
        completedAt:
          type: string
          format: date-time
          nullable: true
```

**Generated:**
```java
public record PaymentResult(
    String status,
    @Nullable Instant estimatedCompletionTime,
    @Nullable String transactionId,
    @Nullable Instant completedAt
) {}
```

**Why this works:** Kora's `JsonWriter` uses `IncludeType.NON_NULL` by default — `null` fields are omitted during serialization. Each branch sends only its fields, producing byte-identical JSON to the `oneOf` version.

### Proper Solution: Add Discriminator

For true polymorphism, add a `discriminator` with `propertyName`:

```yaml
components:
  schemas:
    PaymentResult:
      oneOf:
        - $ref: '#/components/schemas/PendingResult'
        - $ref: '#/components/schemas/CompletedResult'
      discriminator:
        propertyName: resultType
        mapping:
          pending: '#/components/schemas/PendingResult'
          completed: '#/components/schemas/CompletedResult'

    PendingResult:
      type: object
      required: [resultType, estimatedCompletionTime]
      properties:
        resultType:
          type: string
          enum: [pending]
        estimatedCompletionTime:
          type: string
          format: date-time

    CompletedResult:
      type: object
      required: [resultType, transactionId, completedAt]
      properties:
        resultType:
          type: string
          enum: [completed]
        transactionId:
          type: string
        completedAt:
          type: string
          format: date-time
```

**Generated:**
```java
// Sealed interface with discriminator-based deserialization
public sealed interface PaymentResult permits PendingResult, CompletedResult {}

public record PendingResult(String resultType, Instant estimatedCompletionTime) implements PaymentResult {}
public record CompletedResult(String resultType, String transactionId, Instant completedAt) implements PaymentResult {}
```

### openapiNormalizer Setting

Since OpenAPI Generator plugin 7.0.0, the `SIMPLIFY_ONEOF_ANYOF` rule is **ON by default** and rewrites polymorphic schemas.

**Disable it:**
```groovy
openapiNormalizer = [DISABLE_ALL: "true"]
```

This preserves `oneOf`/`allOf` structures for the Kora generator to handle.

---

## enableServerValidation

### Purpose

Generates `@Valid` annotations on delegate method parameters and model fields based on OpenAPI constraints (`minLength`, `pattern`, `nullable: false`, etc.).

### Configuration

```groovy
configOptions = [
    mode: "java-server",
    enableServerValidation: "true",
]
```

### Required Dependency

Add `validation-module` or generated models won't compile:

```groovy
dependencies {
    implementation "ru.tinkoff.kora:validation-module"
}
```

```java
@KoraApp
public interface Application extends
    ValidationModule,  // Required for @Valid annotations
    UndertowHttpServerModule,
    OpenApiManagementModule {
}
```

### Generated Annotations

**Spec:**
```yaml
CreateUserRequest:
  type: object
  required: [email, name]
  properties:
    email:
      type: string
      format: email
      minLength: 5
      maxLength: 255
    name:
      type: string
      minLength: 1
      maxLength: 100
```

**Generated:**
```java
@Generated(value = "org.openapitools.codegen.DefaultCodegen", date = "...")
public record CreateUserRequest(
    @NotNull @Email @Size(min = 5, max = 255) String email,
    @NotNull @Size(min = 1, max = 100) String name
) {}
```

### Validation Interceptor

Kora automatically validates `@Valid`-annotated parameters via the validation interceptor. Invalid requests return 400 with constraint violation details.

See [Validation Reference](references/openapi-validation-reference.md) for constraint mappings.

---

## See Also

- [Codegen Reference](references/openapi-codegen-reference.md) — Full `configOptions` table
- [Delegates Reference](references/openapi-delegates-reference.md) — Delegate method signatures
- [Models Reference](references/openapi-models-reference.md) — Generated records, enums, discriminators
- [Validation Reference](references/openapi-validation-reference.md) — `@Valid` annotations and constraints
