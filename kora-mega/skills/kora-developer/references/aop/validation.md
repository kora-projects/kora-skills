# Kora validation — distilled reference

**Source:** [.kora-agent/kora-docs/mkdocs/docs/en/documentation/validation.md](.kora-agent/kora-docs/mkdocs/docs/en/documentation/validation.md)  
**Examples:** `.kora-agent/kora-examples/kora-java-validation/`

Focused condensation of `kora-docs/.../documentation/validation.md`.

## Setup

```groovy
implementation "ru.tinkoff.kora:validation-module"
```

```java
@KoraApp
public interface Application extends ValidationModule, /* ... */ { }
```

## Built-in validators

| Annotation | Scope | Parameter | Effect |
|-----------|-------|-----------|--------|
| `@NotEmpty` | `String`, collections | — | non-null and not empty |
| `@NotBlank` | `String` | — | non-null and not whitespace-only |
| `@Pattern` | `String` | `regexp`, `flags` | matches regex |
| `@Range` | numeric | `from`, `to`, optional `boundary` | numeric range |
| `@Size` | `String`, collections, maps | `min`, `max` | length / size range |

All in package `ru.tinkoff.kora.validation.common.annotation`.

`@NotEmpty` vs `@NotBlank`: `@NotEmpty` checks that a value is non-null and has size > 0 — use for collections, maps, and strings where empty `""` is acceptable as "value present"; `@NotBlank` is **string-only** and also rejects whitespace-only values. Prefer `@NotBlank` for human-typed strings (names, IDs), `@NotEmpty` for collections.

All fields are implicitly **required (`@NotNull`)**. Use `@Nullable` to opt out — any of `jakarta.annotation.Nullable`, `javax.annotation.Nullable`, or `org.jetbrains.annotations.Nullable` work (Kora doesn't care which). Pick one and stick with it project-wide.

## `@Valid` on records / classes

```java
@Valid
public record CreateOrder(
    @NotBlank @Size(max = 64) String sku,
    @Range(from = 1, to = 1000) int quantity,
    @Nullable String note,
    @Valid Address billing    // nested validation
) {}

@Valid
public record Address(@NotBlank String line1, @Pattern(regexp = "[A-Z]{2}") String country) {}
```

For each `@Valid`-annotated class, the annotation processor generates a `Validator<T>` component. Inject and use:

```java
@Component
public class OrdersService {
    private final Validator<CreateOrder> validator;

    public OrdersService(Validator<CreateOrder> validator) { this.validator = validator; }

    public Order create(CreateOrder body) {
        validator.validateAndThrow(body);                  // throws ViolationException on failure
        // ...
    }
}
```

### Manual mode

```java
List<Violation> violations = validator.validate(body);
if (!violations.isEmpty()) {
    // build custom error response
}
```

### Fail-fast

```java
ValidationContext ctx = ValidationContext.builder().failFast(true).build();
validator.validate(body, ctx);
```

Default is **full** mode (collect all violations, then throw). Fail-fast throws on the first.

## `@Validate` on methods

Marks the method for aspect-based validation of arguments and return value:

```java
@Component
public class OrdersService {                              // not final
    @Validate
    public Order create(@Valid CreateOrder body, @NotBlank String tenantId) {
        return new Order(/* ... */);
    }
}
```

Java: class must be **not final**. Kotlin: class must be **open**.

The aspect:
1. Validates each parameter annotated with a validation annotation or `@Valid`.
2. Calls the method.
3. Validates the return value if it carries `@Valid` or any validator annotation.

`ViolationException` is thrown — catch in your global error interceptor.

## Custom validator

For domain-specific checks (e.g., "is a valid IBAN"):

```java
public record Iban(String value) {}

@Component
public final class IbanValidator implements Validator<Iban> {
    public List<Violation> validate(Iban value, ValidationContext context) {
        if (!isValidIban(value.value())) {
            return List.of(Violation.of("invalid IBAN", context.currentPath()));
        }
        return List.of();
    }
}
```

The `@Component` registration makes it available wherever `Validator<Iban>` is injected, including transitively in `@Valid` parents.

## Generated validator signatures

For Java records, validators use the canonical accessors (`record.field()`). For non-record classes, getters following `getXxx` convention with at least package-private visibility are required.

Kotlin: properties from data class constructors are accessed via their generated getters. Field-targeting annotations on properties need `@field:` prefix:

```kotlin
@Valid
data class CreateOrder(
    @field:NotBlank val sku: String,
    @field:Range(from = 1, to = 1000) val quantity: Int,
    val note: String?,
)
```

## `Violation`, `ViolationException`

```java
public final class Violation {
    public String message();
    public String path();              // e.g., "billing.country" for nested @Valid
}

public final class ViolationException extends RuntimeException {
    public List<Violation> violations();
}
```

In a global `ErrorInterceptor` (see `kora-server/references/error-handling.md`):

```java
if (e instanceof ViolationException ve) {
    var msg = ve.violations().stream()
        .map(v -> v.path() + ": " + v.message())
        .collect(Collectors.joining("; "));
    return HttpServerResponse.of(400, HttpBody.plaintext(msg));
}
```

## Mode signatures

| Java | Kotlin |
|------|--------|
| `T method()` | `fun method(): T` |
| `CompletionStage<T> method()` | `suspend fun method(): T` |
| `Mono<T> method()` (with reactor-core) | `fun method(): Flow<T>` (with coroutines) |
| `Optional<T> method()` | — |

## See also

- Parent `../SKILL.md` — overview, aspect mechanism, pitfalls.
- `../../kora-server/references/error-handling.md` — turning `ViolationException` into 400.
