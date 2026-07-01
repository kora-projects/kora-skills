# Custom Validators Reference

How to create a custom constraint annotation in Kora when the five built-in constraints are not enough.

## Contents

- [The five steps](#the-five-steps)
- [Worked example: a string constraint](#worked-example-a-string-constraint)
- [Validating a value type](#validating-a-value-type)
- [Validator and ValidatorFactory interfaces](#validator-and-validatorfactory-interfaces)
- [Building violations](#building-violations)
- [Using the annotation](#using-the-annotation)
- [Testing](#testing)

---

## The five steps

1. Implement `Validator<T>` for the type the annotation will sit on.
2. Declare a `ValidatorFactory<T>` sub-interface (it has a single no-arg `create()`).
3. Register that factory as a component (a `@KoraApp` `default` method).
4. Declare the annotation and mark it `@ValidatedBy(YourFactory.class)`.
5. Put the annotation on a field / argument / result inside a `@Valid` or `@Validate` context.

Packages:
- `Validator`, `ValidatorFactory`, `ValidationContext`, `Violation` — `ru.tinkoff.kora.validation.common`
- `ValidatedBy` — `ru.tinkoff.kora.validation.common.annotation`

---

## Worked example: a string constraint

### 1. Validator

The `T` is the type the annotation is applied to. For a constraint on a `String` field, implement `Validator<String>`.

```java
import jakarta.annotation.Nonnull;
import java.util.Collections;
import java.util.List;
import ru.tinkoff.kora.validation.common.ValidationContext;
import ru.tinkoff.kora.validation.common.Validator;
import ru.tinkoff.kora.validation.common.Violation;

final class MyValidStringValidator implements Validator<String> {

    @Nonnull
    @Override
    public List<Violation> validate(String value, @Nonnull ValidationContext context) {
        if (value == null) {
            return List.of(context.violates("Should be not empty, but was null"));
        } else if (value.isEmpty()) {
            return List.of(context.violates("Should be not empty, but was empty"));
        }
        return Collections.emptyList();
    }
}
```

### 2. ValidatorFactory

`ValidatorFactory<T>` is a `@FunctionalInterface` with exactly one method, `Validator<T> create()`. Declare a named sub-interface so it can be a distinct graph component.

```java
import ru.tinkoff.kora.validation.common.ValidatorFactory;

public interface MyValidValidatorFactory extends ValidatorFactory<String> { }
```

### 3. Register the factory in the application

```java
@KoraApp
public interface Application extends ValidatorModule {

    default MyValidValidatorFactory myValidStringConstraintFactory() {
        return MyValidStringValidator::new; // satisfies create()
    }
}
```

### 4. Annotation

```java
import java.lang.annotation.*;
import ru.tinkoff.kora.validation.common.annotation.ValidatedBy;

@Retention(RetentionPolicy.CLASS)
@Target({ElementType.METHOD, ElementType.FIELD, ElementType.PARAMETER})
@ValidatedBy(MyValidValidatorFactory.class)
public @interface MyValid { }
```

Requirements: `@Retention(RetentionPolicy.CLASS)` (compile-time processing), an appropriate `@Target`, and `@ValidatedBy` pointing at the factory.

### 5. Use it

```java
@Valid
public record Foo(@MyValid String number) { }
```

The `@Valid` on `Foo` makes Kora generate `Validator<Foo>`, which calls the validator produced by `MyValidValidatorFactory` for the `number` field.

---

## Validating a value type

For a wrapper value type, the validator targets that type and the factory/annotation follow the same shape.

```java
public record Iban(String value) {}

final class IbanValidator implements Validator<Iban> {
    @Override
    public List<Violation> validate(Iban value, ValidationContext context) {
        if (value == null) {
            return List.of(context.violates("IBAN must not be null"));
        }
        if (!isValidIban(value.value())) {
            return List.of(context.violates("Invalid IBAN format"));
        }
        return Collections.emptyList();
    }

    private boolean isValidIban(String iban) {
        // mod-97 checksum; omitted for brevity
        return true;
    }
}

public interface IbanValidatorFactory extends ValidatorFactory<Iban> { }

@KoraApp
public interface Application extends ValidatorModule {
    default IbanValidatorFactory ibanValidatorFactory() {
        return IbanValidator::new;
    }
}

@Retention(RetentionPolicy.CLASS)
@Target({ElementType.FIELD, ElementType.PARAMETER, ElementType.METHOD})
@ValidatedBy(IbanValidatorFactory.class)
public @interface ValidIban {}
```

---

## Validator and ValidatorFactory interfaces

```java
public interface Validator<T> {
    List<Violation> validate(@Nullable T value, ValidationContext context);

    default List<Violation> validate(@Nullable T value);                       // uses a default context
    default void validateAndThrow(@Nullable T value, ValidationContext context); // throws ViolationException
    default void validateAndThrow(@Nullable T value);                          // throws ViolationException
}

@FunctionalInterface
public interface ValidatorFactory<T> {
    Validator<T> create();
}
```

`ValidatorFactory` has **no** parameterized `create(...)` overload — it is a plain `create()`. There is no built-in mechanism to pass annotation attributes into a custom validator; if a constraint needs configuration, encode it in the validator implementation (or in distinct annotations/factories).

---

## Building violations

Use the `ValidationContext` passed into `validate`:

```java
// simple violation on the current path
context.violates("Field is invalid");

// nested path (matches how generated validators describe nested fields)
context.addPath("nested").addPath("field").violates("Invalid value");

// indexed path (collection element)
context.addPath(0).violates("Invalid element");
```

Return an empty list (`Collections.emptyList()`) when the value is valid.

---

## Using the annotation

On DTO fields:

```java
@Valid
public record PaymentRequest(
    @ValidIban Iban iban,
    @NotBlank String accountId
) {}
```

On method parameters (with `@Validate`):

```java
@Validate
public Payment processPayment(@ValidIban Iban beneficiaryIban) { ... }
```

On a method result:

```java
@ValidIban
@Validate
public Iban generateIban(String accountId) {
    return new Iban("XX" + accountId);
}
```

---

## Testing

```java
@KoraAppTest(Application.class)
class IbanValidatorTest {

    @TestComponent
    private Validator<Iban> validator;

    @Test
    void rejectsNull() {
        ViolationException ex = assertThrows(ViolationException.class,
            () -> validator.validateAndThrow(null));
        assertTrue(ex.getViolations().stream()
            .anyMatch(v -> v.message().contains("must not be null")));
    }

    @Test
    void acceptsValid() {
        var iban = new Iban("US1234567890");
        List<Violation> violations = validator.validate(iban, ValidationContext.full());
        assertTrue(violations.isEmpty());
    }
}
```

---

## See Also

- [validation-annotations-reference.md](validation-annotations-reference.md) — built-in constraint annotations
- [violation-exception-reference.md](violation-exception-reference.md) — `ViolationException` handling
