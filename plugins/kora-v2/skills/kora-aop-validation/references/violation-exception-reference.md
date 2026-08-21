# ViolationException Reference

Handling validation failures via `ViolationException` and mapping them to HTTP responses.

**Packages:**
- `ViolationException`, `Violation`, `ValidationContext` — `ru.tinkoff.kora.validation.common`
- `ValidationHttpServerInterceptor`, `ViolationExceptionHttpServerResponseMapper` — `ru.tinkoff.kora.validation.module.http.server` (artifact `validation-module`)

## Contents

- [The types](#the-types)
- [When ViolationException is thrown](#when-violationexception-is-thrown)
- [HTTP error handling](#http-error-handling)
- [Violation path examples](#violation-path-examples)
- [Inspecting violations](#inspecting-violations)
- [Fail-fast vs collect-all](#fail-fast-vs-collect-all)
- [Testing](#testing)
- [Common pitfalls](#common-pitfalls)

---

## The types

`ViolationException` is an unchecked exception carrying every collected violation:

```java
public final class ViolationException extends RuntimeException {
    public ViolationException(Violation violation);
    public ViolationException(List<Violation> violations);
    public List<Violation> getViolations();
    // getMessage() renders all violations as "Path '<path>' violation: <message>"
}
```

`Violation` is an **interface**:

```java
public interface Violation {
    String message();                 // human-readable failure message
    ValidationContext.Path path();    // location of the failure
}
```

`ValidationContext.Path` describes where in the object graph the failure occurred:

```java
public interface ValidationContext.Path {
    String value();   // this segment (field name, or index as text)
    Path root();      // parent path, or null at the root
    Path add(String field);
    Path add(int index);
    String full();    // dotted full path, e.g. "customer.address.city"
}
```

There is no `ViolationPath` class and no `fieldName()` / `parent()` / `elements()` methods — use `path().full()` and `path().value()`.

---

## When ViolationException is thrown

### From a `@Validate` method

```java
@Component
public class UserService {
    @Validate
    public User create(@Valid CreateUserRequest request) {
        // throws ViolationException BEFORE the body runs if the request is invalid
        return repository.save(request);
    }
}
```

### From manual validation

```java
@Component
public class OrderService {
    private final Validator<OrderRequest> validator;

    public OrderService(Validator<OrderRequest> validator) {
        this.validator = validator;
    }

    public Order create(OrderRequest request) {
        validator.validateAndThrow(request);            // default context, collects all

        var ctx = ValidationContext.builder().failFast(true).build();
        validator.validateAndThrow(request, ctx);       // or fail-fast

        return repository.save(request);
    }
}
```

---

## HTTP error handling

With the `validation-module` artifact, register an HTTP-server interceptor and a response mapper on the `@KoraApp`. Adapted from `.kora-agent/kora-examples/guides/java/kora-java-guide-validation-app`:

```java
import java.util.List;
import java.util.stream.Collectors;
import ru.tinkoff.kora.common.Tag;
import ru.tinkoff.kora.http.common.body.HttpBody;
import ru.tinkoff.kora.http.server.common.HttpServerModule;
import ru.tinkoff.kora.http.server.common.HttpServerResponse;
import ru.tinkoff.kora.json.common.JsonWriter;
import ru.tinkoff.kora.validation.common.Violation;
import ru.tinkoff.kora.validation.module.ValidationModule;
import ru.tinkoff.kora.validation.module.http.server.ValidationHttpServerInterceptor;
import ru.tinkoff.kora.validation.module.http.server.ViolationExceptionHttpServerResponseMapper;

@KoraApp
public interface Application extends ValidationModule, UndertowHttpServerModule, JsonModule {

    default ViolationExceptionHttpServerResponseMapper violationExceptionMapper(
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
            .map(v -> new ValidationErrorDetails(lastSegment(v), v.message()))
            .collect(Collectors.toList());
    }

    private static String lastSegment(Violation violation) {
        String full = violation.path().full();
        int dot = full.lastIndexOf('.');
        return dot >= 0 ? full.substring(dot + 1) : full;
    }
}
```

### Error response DTOs

```java
@Json
public record ValidationErrorDetails(String field, String message) {}

@Json
public record ValidationErrorResponse(String code, String message, List<ValidationErrorDetails> errors) {
    public static ValidationErrorResponse of(List<ValidationErrorDetails> errors) {
        return new ValidationErrorResponse("VALIDATION_ERROR", "Validation failed", errors);
    }
}
```

### Resulting response

```http
HTTP/1.1 400 Bad Request
Content-Type: application/json

{
  "code": "VALIDATION_ERROR",
  "message": "Validation failed",
  "errors": [
    { "field": "email", "message": "..." },
    { "field": "name",  "message": "..." }
  ]
}
```

---

## Violation path examples

```java
@Valid public record UserRequest(@NotBlank String name) {}
// path().full() -> "name"

@Valid public record OrderRequest(@Valid Customer customer) {}
@Valid public record Customer(@Valid Address address) {}
@Valid public record Address(@NotBlank String city) {}
// path().full() -> "customer.address.city"

@Valid public record Order(@Valid List<OrderItem> items) {}
@Valid public record OrderItem(@NotBlank String productId) {}
// path().full() for the first item -> "items.[0].productId" (index segments render as [n])
```

---

## Inspecting violations

```java
try {
    validator.validateAndThrow(request);
} catch (ViolationException ex) {
    List<Violation> violations = ex.getViolations();

    boolean hasNameError = violations.stream()
        .anyMatch(v -> v.path().full().contains("name"));

    Map<String, String> errorMap = violations.stream()
        .collect(Collectors.toMap(v -> v.path().full(), Violation::message));
}
```

---

## Fail-fast vs collect-all

| Mode | How | Behavior |
|------|-----|----------|
| Collect-all (default) | `@Validate` / `validate(value)` / `ValidationContext.full()` | Gathers every violation, then throws once |
| Fail-fast | `@Validate(failFast = true)` / `ValidationContext.builder().failFast(true).build()` / `ValidationContext.failFast()` | Throws on the first violation |

```java
var failFast = ValidationContext.builder().failFast(true).build();
List<Violation> violations = validator.validate(request, failFast);
```

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

    @Test
    void collectsAllViolations() {
        var request = new CreateUserRequest("   ", "invalid", 5, null);

        ViolationException ex = assertThrows(ViolationException.class,
            () -> validator.validateAndThrow(request));

        assertTrue(ex.getViolations().size() >= 3); // name, email, age
    }
}
```

---

## Common pitfalls

| Problem | Cause | Fix |
|---------|-------|-----|
| HTTP 500 instead of 400 | No mapper/interceptor registered, or using `validation-common` | Use `validation-module`; register `ValidationHttpServerInterceptor` + `ViolationExceptionHttpServerResponseMapper` |
| Wrong exception type | Catching a `jakarta.validation` exception | Catch `ru.tinkoff.kora.validation.common.ViolationException` |
| `path().fieldName()` won't compile | No such method | Use `path().full()` or `path().value()` |
| Empty violations list | Exception not from Kora validation | Confirm the validator/`@Validate` actually ran |

---

## See Also

- [validation-annotations-reference.md](validation-annotations-reference.md) — built-in constraint annotations
- [custom-validators-reference.md](custom-validators-reference.md) — custom `Validator<T>` implementations
