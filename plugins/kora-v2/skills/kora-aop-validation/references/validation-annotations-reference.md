# Validation Annotations Reference

**Package:** `ru.tinkoff.kora.validation.common.annotation`

These five constraint annotations are the **complete** Kora constraint set, plus the structural `@Valid` / `@Validate`. There is no `@NotNull` — null checks are implicit (see [Implicit nullability](#implicit-nullability-and-nullable)).

## Contents

- [@NotBlank](#notblank)
- [@NotEmpty](#notempty)
- [@Size](#size)
- [@Range](#range)
- [@Pattern](#pattern)
- [@Valid](#valid)
- [@Validate](#validate)
- [@NotBlank vs @NotEmpty](#notblank-vs-notempty)
- [Implicit nullability and @Nullable](#implicit-nullability-and-nullable)

---

## @NotBlank

**Target:** `String`, `CharSequence`
**Check:** not null and contains at least one non-whitespace character.

```java
@Valid
public record UserRequest(
    @NotBlank String name  // "  " -> INVALID, "John" -> VALID
) {}
```

## @NotEmpty

**Target:** `String`, `CharSequence`, `Iterable`, `Collection`, `List`, `Set`, `Map`
**Check:** not null and size/length > 0 (whitespace-only strings pass).

```java
@Valid
public record OrderRequest(
    @NotEmpty String notes,       // "" -> INVALID, "  " -> VALID
    @NotEmpty List<String> items  // [] -> INVALID, ["item"] -> VALID
) {}
```

## @Size

**Target:** `String`, `CharSequence`, `Collection`, `List`, `Set`, `Map`
**Check:** size/length within `[min, max]` (both inclusive).

```java
@Valid
public record UserRequest(
    @Size(min = 2, max = 100) String name,     // "A" -> INVALID (too short)
    @Size(min = 1, max = 10) List<String> tags // 15 items -> INVALID (too many)
) {}
```

**Parameters:**
- `min` — minimum size, inclusive (default `0`).
- `max` — maximum size, inclusive (required, no default).

## @Range

**Target:** `Integer`, `Long`, `Short`, `Float`, `Double`, `BigInteger`, `BigDecimal`
**Check:** numeric value within range according to `boundary`.

```java
import ru.tinkoff.kora.validation.common.annotation.Range;

@Valid
public record ProductRequest(
    @Range(from = 1, to = 1000) int quantity,
    @Range(from = 0.0, to = 100.0) Double discount,
    @Range(from = 18, to = 120, boundary = Range.Boundary.INCLUSIVE_INCLUSIVE) Integer age
) {}
```

**Parameters:**
- `from` — minimum value (`double`).
- `to` — maximum value (`double`).
- `boundary` — boundary inclusion rule, default `Range.Boundary.INCLUSIVE_INCLUSIVE`.

`Boundary` is a nested enum on the annotation: reference it as `Range.Boundary.*`.

| `Range.Boundary` | from | to | Example (from=0, to=100) |
|------------------|------|----|--------------------------|
| `INCLUSIVE_INCLUSIVE` | yes | yes | 0 <= x <= 100 |
| `EXCLUSIVE_EXCLUSIVE` | no  | no  | 0 < x < 100 |
| `INCLUSIVE_EXCLUSIVE` | yes | no  | 0 <= x < 100 |
| `EXCLUSIVE_INCLUSIVE` | no  | yes | 0 < x <= 100 |

## @Pattern

**Target:** `String`, `CharSequence`
**Check:** value matches the supplied regular expression.

```java
import java.util.regex.Pattern;
import ru.tinkoff.kora.validation.common.annotation.Pattern;

@Valid
public record UserRequest(
    @Pattern("^[^@\\s]+@[^@\\s]+\\.[^@\\s]+$") String email,
    // flags is a plain int built from java.util.regex.Pattern constants
    @Pattern(value = "^[a-z]{2}$", flags = Pattern.CASE_INSENSITIVE) String country
) {}
```

**Parameters:**
- `value` — the regex (the default/unnamed attribute, so `@Pattern("...")` works).
- `flags` — an `int`, default `0`. Combine `java.util.regex.Pattern` constants
  (`CASE_INSENSITIVE`, `MULTILINE`, `DOTALL`, `UNICODE_CASE`, `CANON_EQ`,
  `UNIX_LINES`, `LITERAL`, `UNICODE_CHARACTER_CLASS`, `COMMENTS`) with `|`.

There is no `Pattern.Flag` enum — use the standard `java.util.regex.Pattern` int constants.

## @Valid

**Target:** type, field, parameter, method.
**Purpose:** trigger validator generation and nested/result validation.

```java
// On a type -> generates Validator<Address> in the graph
@Valid
public record Address(@NotBlank String city, @NotBlank String street) {}

// On a field -> recurses into the nested type's Validator
@Valid
public record OrderRequest(@Valid Address shippingAddress) {}

// On a parameter -> validates the argument (with @Validate on the method)
public User create(@Valid CreateUserRequest request) { ... }
```

## @Validate

**Target:** method.
**Purpose:** weave the validation aspect for arguments and (optionally) the result.

```java
@Component
public class UserService {

    @Validate
    public User create(@Valid CreateUserRequest request) {
        // arguments validated before the body runs
        return repository.save(request);
    }

    @Validate(failFast = true)
    public User getByEmail(@NotBlank @Pattern("^[^@\\s]+@[^@\\s]+$") String email) {
        return repository.findByEmail(email);
    }
}
```

**Parameter:** `failFast` (default `false`) — stop on the first violation versus collect all.

---

## @NotBlank vs @NotEmpty

| Annotation | String/CharSequence | Collection / Map | Whitespace-only string |
|------------|---------------------|------------------|------------------------|
| `@NotBlank` | yes | no | rejected (`"   "` is INVALID) |
| `@NotEmpty` | yes | yes | accepted (`"   "` is VALID) |

Rule of thumb: `@NotBlank` for human-typed strings (names, emails); `@NotEmpty` for collections, or strings where whitespace-only is acceptable.

---

## Implicit nullability and @Nullable

All fields and arguments are **implicitly required**: the generated validator emits a null check for each one. There is no `@NotNull` annotation. To opt a field/argument out of the null check, mark it with any `@Nullable`:

```java
@Valid
public record UserRequest(
    @NotBlank String name,           // required
    @Nullable String middleName,     // optional, no null check
    @Nullable List<@NotBlank String> tags // list optional; elements validated if present
) {}
```

**Accepted `@Nullable` annotations:** `jakarta.annotation.Nullable`, `javax.annotation.Nullable`, `org.jetbrains.annotations.Nullable`. Pick one and use it consistently. In Kotlin, use a nullable type (`String?`) instead.

---

## See Also

- [custom-validators-reference.md](custom-validators-reference.md) — custom `Validator<T>` implementations
- [violation-exception-reference.md](violation-exception-reference.md) — `ViolationException` handling and HTTP mapping
