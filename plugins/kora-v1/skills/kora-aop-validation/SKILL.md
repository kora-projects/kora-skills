---
name: kora-aop-validation
description: "Kora declarative validation via its own constraint annotations (@NotBlank, @NotEmpty, @Pattern, @Range, @Size), class/record validation with @Valid (generates Validator<T>), method argument and result validation with @Validate (AOP), custom constraints via @ValidatedBy + ValidatorFactory, and ViolationException handling mapped to HTTP 400 with ValidationHttpServerInterceptor. Use when validating request DTOs, enforcing argument/return rules on services or controllers, building custom constraints, or turning validation failures into structured 400 responses. Kora validation is NOT Jakarta/JSR-380 — annotations live in ru.tinkoff.kora.validation.common.annotation."
---

# Kora AOP Validation

Kora validates classes/records and method arguments/results at compile time using its **own** constraint annotations and generated `Validator<T>` components. There is no reflection: `@Valid` generates a `Validator<T>`, `@Validate` weaves an aspect into a method.

**Key fact:** Kora validation annotations come from `ru.tinkoff.kora.validation.common.annotation`, NOT from `jakarta.validation` / JSR-380. The full constraint set is only these five: `@NotBlank`, `@NotEmpty`, `@Pattern`, `@Range`, `@Size`. There is **no** `@NotNull` constraint — every field/argument is implicitly required (null fails) unless marked `@Nullable`.

---

## Quick Start

### 1. Dependency + module

Two setups exist — pick by whether you need HTTP integration. All Kora artifacts inherit their version from the `kora-parent` BOM; never pin individual `ru.tinkoff.kora:*` versions.

**Plain validation (no HTTP)** — artifact `validation-common`, module `ValidatorModule`:

```groovy
dependencies {
    annotationProcessor "ru.tinkoff.kora:annotation-processors" // mandatory: generates validators + aspects
    implementation "ru.tinkoff.kora:validation-common"
}
```

```java
import ru.tinkoff.kora.validation.common.constraint.ValidatorModule;

@KoraApp
public interface Application extends ValidatorModule { }
```

**With HTTP-server integration** (maps `ViolationException` → 400) — artifact `validation-module`, module `ValidationModule`:

```groovy
dependencies {
    annotationProcessor "ru.tinkoff.kora:annotation-processors"
    implementation "ru.tinkoff.kora:validation-module"
}
```

```java
import ru.tinkoff.kora.validation.module.ValidationModule;

@KoraApp
public interface Application extends ValidationModule, UndertowHttpServerModule, JsonModule { }
```

Kotlin: replace `annotationProcessor`/`testAnnotationProcessor` with `ksp "ru.tinkoff.kora:symbol-processors"`.

### 2. Validated record — generates `Validator<CreateUserRequest>`

```java
import jakarta.annotation.Nullable;
import ru.tinkoff.kora.validation.common.annotation.*;

@Valid
public record CreateUserRequest(
    @NotBlank @Size(min = 2, max = 100) String name,
    @NotBlank @Pattern("^[^@\\s]+@[^@\\s]+\\.[^@\\s]+$") String email,
    @Range(from = 18, to = 120) Integer age,
    @Nullable String note                                // opt out of the implicit null check
) {}
```

### 3. Validate a method with `@Validate`

```java
@Component
public class UserController {

    @HttpRoute(method = HttpMethod.POST, path = "/users")
    @Json
    @Validate
    public UserResponse createUser(@Valid @Json CreateUserRequest request) {
        return userService.create(request); // ViolationException thrown before the body runs if invalid
    }
}
```

### 4. Inject the generated validator directly (manual validation)

```java
@Component
public final class Example {

    private final Validator<CreateUserRequest> validator;

    public Example(Validator<CreateUserRequest> validator) {
        this.validator = validator;
    }

    public void check(CreateUserRequest req) {
        validator.validateAndThrow(req); // collects all violations, then throws ViolationException
    }
}
```

---

## How it works

| Annotation | Where | Effect |
|------------|-------|--------|
| `@Valid` on a type/record | type | Generates a `Validator<T>` component in the graph |
| `@Valid` on a field/parameter | field/param | Recurses into a nested validated type's `Validator` |
| `@Validate` on a method | method | Weaves an aspect: validates `@`-annotated args (and the result if the method itself is annotated) before/after the body |
| `@NotBlank/@NotEmpty/@Pattern/@Range/@Size` | field/param/method | The actual constraint checks |
| `@Nullable` (any flavor) | field/param | Suppresses the implicit null check |

A `Validator<T>` returns `List<Violation>`. Use `validate(value)` to inspect, or `validateAndThrow(value)` to throw `ViolationException` on the first non-empty result. The `@Validate` aspect throws `ViolationException` automatically.

---

## Class / record validation

Every field is implicitly required. Mark optional fields with any `@Nullable` annotation (`jakarta.annotation.Nullable`, `javax.annotation.Nullable`, `org.jetbrains.annotations.Nullable`).

```java
@Valid
public record OrderRequest(
    @NotBlank String id,
    @Valid Customer customer,            // nested → uses generated Validator<Customer>
    @Valid List<OrderItem> items,        // elements validated via Validator<OrderItem>
    @Nullable String comment
) {}
```

For a regular (non-record) class, getters must be at least package-private (`getId()`); records use the component accessor (`id()`).

### Kotlin

```kotlin
@Valid
data class CreateUserRequest(
    @field:NotBlank @field:Size(min = 2, max = 100) val name: String,
    @field:NotBlank val email: String,
    val note: String?                    // Kotlin nullability marks it optional
)
```

Use the `@field:` prefix on constraints. A `data class` is fine for **class** validation. A class only needs `open` when it hosts a `@Validate` **method** (aspects require subclassing).

---

## Method validation with `@Validate`

`@Validate` on a method validates its annotated arguments before the body and, if the method itself carries constraint annotations, its result afterward. The enclosing class must be non-`final` (Java) / `open` (Kotlin) so the aspect can subclass it.

```java
@Component
public class UserService {

    @Validate
    public User create(@Valid CreateUserRequest request) { ... }

    // single-argument constraint, stop on the first error
    @Validate(failFast = true)
    public User getByEmail(@NotBlank @Pattern("^[^@\\s]+@[^@\\s]+$") String email) { ... }

    // result validation: @Validate enables it, @Valid validates the returned objects,
    // @Size constrains the list itself
    @Size(min = 1)
    @Valid
    @Validate
    public List<User> getAllUsers() { ... }
}
```

`failFast = true` throws on the first violation; the default collects all violations into one `ViolationException`.

Supported method signatures: `T`, `Optional<T>`, `Mono<T>`/`Flux<T>` (with `reactor-core`) in Java; `T`, `suspend fun`, `Flow<T>` in Kotlin.

---

## Mapping `ViolationException` to HTTP 400

Requires the `validation-module` artifact (`ValidationModule`). Register an interceptor tagged for the HTTP server plus a response mapper. Adapted from `.kora-agent/kora-examples/guides/java/kora-java-guide-validation-app`:

```java
@KoraApp
public interface Application extends
        ValidationModule, UndertowHttpServerModule, JsonModule, LogbackModule {

    default ViolationExceptionHttpServerResponseMapper violationMapper(
            JsonWriter<ValidationErrorResponse> writer) {
        return (request, exception) -> HttpServerResponse.of(
            400,
            HttpBody.json(writer.toByteArrayUnchecked(
                ValidationErrorResponse.of(toErrors(exception.getViolations())))));
    }

    @Tag(HttpServerModule.class)
    default ValidationHttpServerInterceptor validationInterceptor(
            ViolationExceptionHttpServerResponseMapper mapper) {
        return new ValidationHttpServerInterceptor(mapper);
    }

    private static List<ValidationErrorDetails> toErrors(List<Violation> violations) {
        return violations.stream()
            .map(v -> new ValidationErrorDetails(v.path().full(), v.message()))
            .collect(java.util.stream.Collectors.toList());
    }
}
```

`Violation` is an interface: `message()` and `path()` (a `ValidationContext.Path` whose `full()` returns the dotted path, e.g. `customer.address.city`). See [violation-exception-reference.md](references/violation-exception-reference.md).

---

## References & assets

| File | Purpose |
|------|---------|
| [references/validation-annotations-reference.md](references/validation-annotations-reference.md) | The five constraints, `@Range` boundary enum, `@Pattern` int flags, `@Nullable` opt-out |
| [references/custom-validators-reference.md](references/custom-validators-reference.md) | Custom constraints via `Validator<T>` + `ValidatorFactory<T>` + `@ValidatedBy` |
| [references/violation-exception-reference.md](references/violation-exception-reference.md) | `ViolationException`, `Violation`, `ValidationContext`, HTTP 400 mapping, testing |
| [assets/README.md](assets/README.md) | DTO / service / custom-validator / error-response templates (Java + Kotlin) |

Working example apps: `.kora-agent/kora-examples/examples/java/kora-java-validation` (plain validation) and `.kora-agent/kora-examples/guides/java/kora-java-guide-validation-app` (HTTP 400 mapping).

---

## Common pitfalls

| Symptom | Fix |
|---------|-----|
| Validation never runs on a method | Add `@Validate` to the method; ensure the class is non-`final` (Java) / `open` (Kotlin) |
| Nested object not validated | Add `@Valid` to the field/parameter holding it |
| Field unexpectedly required | All fields are implicit-not-null; add `@Nullable` to make optional |
| Looking for `@NotNull` | It does not exist in Kora — nullability is the default; opt out with `@Nullable` |
| Reached for `jakarta.validation.*` | Use `ru.tinkoff.kora.validation.common.annotation.*` instead |
| Caught the wrong exception | Catch `ru.tinkoff.kora.validation.common.ViolationException` |
| HTTP 500 instead of 400 on bad input | Use `validation-module`; register `ValidationHttpServerInterceptor` + `ViolationExceptionHttpServerResponseMapper` |
| Kotlin constraints ignored | Use the `@field:` prefix |
| `@Pattern(regexp = ...)` won't compile | The attribute is the unnamed `value`: `@Pattern("...")` |

---

## Testing

```java
@KoraAppTest(Application.class)
class CreateUserValidationTest {

    @TestComponent
    private Validator<CreateUserRequest> validator;

    @Test
    void failsForBlankName() {
        var request = new CreateUserRequest("   ", "test@example.com", 25, null);

        ViolationException ex = assertThrows(ViolationException.class,
            () -> validator.validateAndThrow(request));

        assertTrue(ex.getViolations().stream()
            .anyMatch(v -> v.path().full().contains("name")));
    }
}
```

See `.kora-agent/kora-examples/examples/java/kora-java-validation/src/test/java/...` for the `@KoraAppTest` + `@TestComponent` pattern over `ArgumentValidator` / `ResultValidator`.
