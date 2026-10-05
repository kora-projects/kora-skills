---
name: kora-aop-validation
description: "Kora 2.0 declarative validation — @Valid generates a Validator<T> for records/classes/sealed types, @Validate weaves argument and result validation via AOP, with Kora's own 22 constraint annotations from io.koraframework.validation.common.annotation (@NotBlank, @NotEmpty, @Size, @Range, @Pattern, @Min, @Max, @Positive, @Digits, @Past, @Future, @Url, @Uri, @UUID, @OneOf, @AssertTrue, ...). Covers ValidatorModule (validation-common) vs ValidationModule (validation-module), custom constraints via @ValidatedBy + a parameterised ValidatorFactory, ViolationException, and mapping it to HTTP 400 through ValidationHttpServerInterceptor + ViolationExceptionHttpServerResponseMapper. Use when validating request DTOs, enforcing argument/return rules, validating @ConfigSource config, or building custom constraints. Kora validation is NOT Jakarta/JSR-380."
license: Apache-2.0
metadata:
  kora-version: "2.x"
---

# Kora AOP Validation

> **Kora sub-skill — obey the [kora-v2 meta rules](../../SKILL.md) on every task:** **R0** ground the workspace on Kora 2.0 refs before starting (framework source at tag `2.0.0.RC2` + `kora-examples` at `migration/2.0` + Kora 2.0 docs at koraframework.io/v2, which trail the source; 1.x `kora-docs` pages are never an authority) · **R1** read this sub-skill before writing code · **R2** Kora 2.0 APIs only — no Spring/Micronaut/Quarkus, no Kora 1.x APIs, no invented annotations or config keys · **R3** journal any incorrect Kora usage. Add comments/Javadoc only if asked.

| | |
|---|---|
| **Artifacts** | `io.koraframework:validation-common` (constraints + `Validator<T>`) · `io.koraframework:validation-module` (adds HTTP-server error mapping) |
| **Modules** | `io.koraframework.validation.common.constraint.ValidatorModule` · `io.koraframework.validation.module.ValidationModule extends ValidatorModule` |
| **Annotations** | `io.koraframework.validation.common.annotation.*` |
| **Processor** | Java `annotationProcessor "io.koraframework:annotation-processors"` · Kotlin `ksp "io.koraframework:symbol-processors"` |
| **Version** | `2.0.0.RC2` from `mavenCentral()` via `io.koraframework:kora-bom` · Java 25 · Kotlin 2.4 + KSP |

Validation is generated at compile time, with no reflection: `@Valid` on a type emits a
`$Name_Validator` class implementing `Validator<T>` and registers it in the DI graph; `@Validate` on
a method emits an AOP proxy that validates arguments before the body and the result after it.

## Key fact — this is not Jakarta / JSR-380

Kora ships **its own** constraint annotations in `io.koraframework.validation.common.annotation`.
`jakarta.validation.*` and `javax.validation.*` annotations are not recognised, produce no code and
no diagnostic — the DTO simply goes unvalidated.

There is **no `@NotNull`**: every field and argument is implicitly required and the generated code
emits its own null check. Opt out with `@Nullable` (JSpecify in Java, a `T?` type in Kotlin).

The constraint set has **22** annotations, not the five of the Kora 1.x skill:

`@NotBlank` `@NotEmpty` `@Size` `@Pattern` `@Range` `@Min` `@Max` `@Positive` `@PositiveOrZero`
`@Negative` `@NegativeOrZero` `@Digits` `@AssertTrue` `@AssertFalse` `@Past` `@PastOrPresent`
`@Future` `@FutureOrPresent` `@Url` `@Uri` `@UUID` `@OneOf`

plus the structural `@Valid`, `@Validate` and `@ValidatedBy`. Supported target types and attributes
per constraint: [references/validation-annotations-reference.md](references/validation-annotations-reference.md).

> `io.koraframework.validation.common.annotation.Size` is the constraint. It is a different type
> from `io.koraframework.common.util.Size`, the byte-size value type used by config. Import carefully.

---

## Quick start

### 1. Dependency and module

Pick by whether the application serves HTTP.

**No HTTP** — artifact `validation-common`, module `ValidatorModule`:

```groovy
dependencies {
    koraBom platform("io.koraframework:kora-bom:$koraVersion")   // koraVersion=2.0.0.RC2
    annotationProcessor "io.koraframework:annotation-processors" // mandatory: generates validators + aspects
    implementation "io.koraframework:validation-common"
}
```

```java
import io.koraframework.validation.common.constraint.ValidatorModule;

@KoraApp
public interface Application extends ValidatorModule { }
```

**With HTTP-server error mapping** — artifact `validation-module`, module `ValidationModule`:

```groovy
dependencies {
    koraBom platform("io.koraframework:kora-bom:$koraVersion")
    annotationProcessor "io.koraframework:annotation-processors"
    implementation "io.koraframework:validation-module"
    implementation "io.koraframework:http-server-undertow"
}
```

```java
import io.koraframework.validation.module.ValidationModule;
import io.koraframework.http.server.undertow.UndertowPublicHttpServerModule;

@KoraApp
public interface Application extends ValidationModule, UndertowPublicHttpServerModule, JsonModule { }
```

`ValidationModule` extends `ValidatorModule`, so it also supplies every built-in constraint factory.

Kotlin (`build.gradle.kts`):

```kotlin
dependencies {
    implementation(platform("io.koraframework:kora-bom:${property("koraVersion")}"))
    ksp("io.koraframework:symbol-processors:${property("koraVersion")}")
    implementation("io.koraframework:validation-module")   // or validation-common
}
```

The `koraBom` configuration wiring for Groovy builds lives in
[`kora-project-setup-java`](../kora-project-setup-java/SKILL.md) / [`kora-project-setup-kotlin`](../kora-project-setup-kotlin/SKILL.md).

> **`validation-module` does not drag an HTTP server in.** Its dependency on `http-server-common` is
> `compileOnly` (`requires static` in `module-info`), and the published `2.0.0.RC2` POM and Gradle
> module metadata list only `validation-common` and `jspecify`. You must add an HTTP server module
> yourself. Conversely, extending `ValidationModule` in a non-HTTP application compiles fine — the
> interceptor is simply an unused component and gets pruned — but prefer `ValidatorModule` there so
> the intent is explicit.

### 2. Validated record — generates `Validator<CreateUserRequest>`

```java
import org.jspecify.annotations.Nullable;
import io.koraframework.validation.common.annotation.*;

@Valid
public record CreateUserRequest(
    @NotBlank @Size(min = 2, max = 100) String name,
    @NotBlank @Pattern("^[^@\\s]+@[^@\\s]+\\.[^@\\s]+$") String email,
    @Range(from = 18, to = 120) Integer age,
    @Nullable String note                                // opt out of the implicit null check
) {}
```

The generated class is `$CreateUserRequest_Validator`; for a nested type it carries the outer names
(`$Outer_Inner_Validator`). Never reference the generated name in hand-written code — inject
`Validator<CreateUserRequest>` instead.

### 3. Validate a method with `@Validate`

```java
@Component
@HttpController
public class UserController {                             // NOT final

    @HttpRoute(method = HttpMethod.POST, path = "/users")
    @Json
    @Validate
    public UserResponse createUser(@Valid @Json CreateUserRequest request) {
        return userService.create(request);   // ViolationException is thrown before the body runs
    }
}
```

### 4. Inject the generated validator (imperative validation)

```java
@Component
public final class Example {                                   // final is fine — no @Validate here

    private final Validator<CreateUserRequest> validator;

    public Example(Validator<CreateUserRequest> validator) {   // supplied by the DI extension
        this.validator = validator;
    }

    public void check(CreateUserRequest req) {
        validator.validateAndThrow(req);                       // collects all, then throws
    }
}
```

---

## How the annotations compose

| Annotation | Target | Effect |
|---|---|---|
| `@Valid` on a type | `TYPE` | Generates `$Name_Validator implements Validator<T>` and registers it in the graph |
| `@Valid` on a field / parameter | `FIELD`, `PARAMETER` | Recurses into the nested type's `Validator<T>` |
| `@Valid` on a method | `METHOD` | With `@Validate`, validates the returned object graph |
| `@Validate` on a method | `METHOD` only | Weaves the AOP proxy; attribute `failFast` (default `false`) |
| any constraint | `METHOD`, `FIELD`, `PARAMETER` | The actual check |
| `@Nullable` | field / parameter / return | Suppresses the implicit null check for that element |

`Validator<T>` (package `io.koraframework.validation.common`):

```java
List<Violation> validate(@Nullable T value, ValidationContext context);
default List<Violation> validate(@Nullable T value);
default void validateAndThrow(@Nullable T value, ValidationContext context) throws ViolationException;
default void validateAndThrow(@Nullable T value) throws ViolationException;
```

`ValidationContext` here is validation-scoped path/fail-fast state. It is unrelated to the Kora 1.x
`Context` propagation type, which no longer exists anywhere in Kora 2.0.

---

## What `@Valid` accepts

| Shape | Where constraints go | Accessor used by the generated validator |
|---|---|---|
| `record` | record components (propagated to the backing field) | `name()` |
| plain class | **the fields** | `getName()` — a JavaBean getter is required |
| `sealed interface` | on each permitted subtype (each needs its own `@Valid`) | dispatches with `instanceof` to the subtype validator |
| `@ConfigSource` / `@ConfigMapper` interface | the accessor methods | `name()` |
| `enum` | — | compile error: `Validation can't be generated for enum` |
| non-sealed, non-config `interface` | — | compile error: `Validation can't be generated for non sealed interface` |

**Plain classes: constraints belong on fields, not getters.** A constraint on a getter of a
non-record class is silently ignored and the generated validator contains only the root null check.

**Collections.** `ValidatorModule` supplies `Validator<List<T>>`, `Validator<Set<T>>` and
`Validator<Collection<T>>` derived from `Validator<T>`, so `@Valid List<OrderItem> items` validates
every element once `OrderItem` itself is `@Valid`. Element violation paths render as `items.[0].sku`.

**Config.** `@Valid` on a `@ConfigSource` / `@ConfigMapper` interface makes the generated config
mapper call `validateAndThrow` on the parsed value, so invalid configuration fails during graph
build with a `ViolationException` instead of at first use. See
[`kora-config-hocon`](../kora-config-hocon/SKILL.md) for the config side.

### Kotlin

```kotlin
@Valid
data class CreateUserRequest(
    @field:NotBlank @field:Size(min = 2, max = 100) val name: String,
    @field:NotBlank val email: String,
    @field:Range(from = 18.0, to = 120.0) val age: Int,
    val note: String?                    // nullable type opts out of the null check
)
```

- Use the **`@field:`** use-site target. The constraint annotations declare no `PROPERTY` target, so
  without the prefix Kotlin puts them on the constructor parameter and the data class goes unvalidated.
- `@Range` takes `double` attributes — write `from = 18.0, to = 120.0`, not `18`/`120`.
- A `data class` is fine for **class** validation. `open` is only needed on a class that hosts a
  `@Validate` **method**.

---

## Method validation with `@Validate`

```java
@Component
public class UserService {                                  // NOT final

    @Validate
    public User create(@Valid CreateUserRequest request) { ... }

    @Validate(failFast = true)                              // stop at the first violation
    public User getByEmail(@NotBlank @Pattern("^[^@\\s]+@[^@\\s]+$") String email) { ... }

    @Size(min = 1, max = 500)                               // constrains the returned list
    @Valid                                                  // validates each element
    @Validate                                               // enables the aspect
    public List<User> getAllUsers() { ... }
}
```

Result validation runs after the body. `@Validate` alone validates only arguments; the constraints
for the result go on the **method**.

**The target must be proxyable.** The generated proxy is `$Name__AopProxy extends Name`, so the class
must not be `final` (Java) / must be `open` (Kotlin), the method must not be `final` or `private`
(Java) / must be `open` (Kotlin), and a non-private constructor must exist.

> **Both languages fail loudly on `final` / non-`open`.** A `final` class, a `final` method or a
> `private` method carrying `@Validate` is a **compile error**, not a silent skip — the Java
> processor reports `AOP aspect cannot be applied to class '…' because the class is final.`
> (respectively `… method '…#…()' because the method is final.` / `… because the method is private.`),
> and KSP reports `AOP aspect cannot be applied to class '…' because the class is not open.`
>
> The genuinely silent case is Java-only: an **abstract class or an interface** carrying an aspect
> annotation is skipped without a proxy, a warning or an error. Kotlin rejects an abstract class with
> `AOP aspect cannot be applied to abstract class '…'.`

**Return types.** Kora 2.0 contracts are synchronous and that is the shape to write.

- Java: `Publisher` (`Mono`/`Flux`) and bare `Future` are rejected outright with a processing error.
  `CompletionStage` / `CompletableFuture` are still accepted by `@Validate`.
- Kotlin: plain values, `suspend` functions and `Flow<T>` are supported. `Future`, `CompletionStage`,
  `Mono` and `Flux` are rejected — but only when the method also validates its **result**;
  argument-only validation on such a method is not checked.

Kora's own contracts — repositories, controllers, HTTP clients — are synchronous. Do not reintroduce
async signatures just to reach these paths.

---

## Mapping `ViolationException` to HTTP 400

`ValidationModule` declares the interceptor as a `@DefaultComponent` **without a tag**, so nothing
picks it up on its own — the HTTP router collects only `@Tag(HttpServer.class) All<HttpServerInterceptor>`.
Wiring it is an explicit step: override the module method with the tag, and supply the response
mapper that builds the body.

```java
@KoraApp
public interface Application extends
        ValidationModule, UndertowPublicHttpServerModule, JsonModule, HoconConfigModule, LogbackModule {

    default ViolationExceptionHttpServerResponseMapper violationExceptionHttpServerResponseMapper(
            JsonWriter<ValidationErrorResponse> writer) {
        return (request, exception) -> HttpServerResponse.of(
            400,
            HttpBody.json(writer.toByteArray(
                ValidationErrorResponse.of(toErrors(exception.getViolations())))));
    }

    @Tag(HttpServer.class)                                  // io.koraframework.http.server.common.HttpServer
    default ValidationHttpServerInterceptor validationHttpServerInterceptor(
            ViolationExceptionHttpServerResponseMapper mapper) {
        return new ValidationHttpServerInterceptor(mapper);
    }

    private static List<ValidationErrorDetails> toErrors(List<Violation> violations) {
        return violations.stream()
            .map(v -> new ValidationErrorDetails(v.path().full(), v.message()))
            .toList();
    }
}
```

- `ValidationHttpServerInterceptor` (an `HttpServerInterceptor`) is what turns the exception into a
  response; `ViolationExceptionHttpServerResponseMapper` is an optional collaborator that shapes the
  body. Without a mapper the interceptor still answers `400` with `HttpServerResponseException.of(400, message)`.
- `@Tag(HttpServerModule.class)` is the Kora 1.x tag. It still compiles in 2.0 and the interceptor
  silently never runs.
- OpenAPI-generated servers do this differently: with `enableServerValidation=true` the generator
  puts `@InterceptWith(ValidationHttpServerInterceptor.class)` on each controller. Turn that off with
  `enableServerValidationInterceptor=false` when mapping errors by hand — see
  [`kora-openapi-generator-server`](../kora-openapi-generator-server/SKILL.md).

Full walkthrough, DTOs and Kotlin variant: [references/violation-exception-reference.md](references/violation-exception-reference.md).

---

## References and assets

| File | Purpose |
|---|---|
| [references/validation-annotations-reference.md](references/validation-annotations-reference.md) | All 22 constraints — attributes, supported types, violation messages, `@Valid`/`@Validate` |
| [references/custom-validators-reference.md](references/custom-validators-reference.md) | Custom constraints: `Validator<T>`, parameterised `ValidatorFactory<T>`, `@ValidatedBy` |
| [references/violation-exception-reference.md](references/violation-exception-reference.md) | `ViolationException`, `Violation`, `ValidationContext`, HTTP 400 wiring, testing |
| `assets/` | DTO, service and error-response templates (Java + Kotlin); custom-constraint templates (annotation / validator / factory) are Java — for the Kotlin specifics see the custom-validators reference |

---

## Common pitfalls

| Symptom | Cause | Fix |
|---|---|---|
| DTO is never validated, no error | `jakarta.validation.*` / `javax.validation.*` annotations | Use `io.koraframework.validation.common.annotation.*` |
| `AOP aspect cannot be applied … because the class is final` | Java `final` class, `final` method or `private` method | Make the class and method non-`final` and at least package-private |
| `@Validate` method runs unvalidated, `javac` exits 0 | Java **abstract** class or interface — the only silent AOP case | Move `@Validate` onto the concrete implementation |
| Kotlin `AOP aspect cannot be applied … not open` | class or function is not `open` | `open class` + `open fun` |
| Kotlin data class silently unvalidated | constraint written without `@field:` | `@field:NotBlank`, `@field:Size(...)` |
| Plain class validator is empty | constraints on getters instead of fields | Move constraints onto the fields |
| `Validation can't be generated for non sealed interface` | `@Valid` on a plain interface | Make it `sealed`, or use `@ConfigSource`/`@ConfigMapper` for config |
| Field unexpectedly required | every element is implicitly non-null | Add `@Nullable` (JSpecify) / use `T?` in Kotlin |
| Looking for `@NotNull` | it does not exist in Kora | Nullability is the default; opt out with `@Nullable` |
| 500 instead of 400 on bad input | interceptor not tagged, or tagged `@Tag(HttpServerModule.class)` | Override the module method with `@Tag(HttpServer.class)` |
| `Expected X#create() method with N parameters` | custom constraint has attributes, factory has no matching `create(...)` | Add `create(...)` with one parameter per annotation attribute, in declaration order |
| `toByteArrayUnchecked` does not compile | Kora 1.x JSON API | `JsonWriter.toByteArray(...)` — the `*Unchecked` methods are gone in 2.0 |
| Kotlin `'validationHttpServerInterceptor' overrides nothing` | the module parameter is `@Nullable` | Declare it as `ViolationExceptionHttpServerResponseMapper?` |
| `@Range(from = 1, to = 5)` does not compile in Kotlin | attributes are `double` | `from = 1.0, to = 5.0` |

---

## Testing

```java
@KoraAppTest(Application.class)
class UserServiceValidationTest {

    @TestComponent
    private UserService service;          // the AOP proxy, so @Validate is active

    @Test
    void rejectsBlankName() {
        var request = new CreateUserRequest("   ", "test@example.com", 25, null);

        var ex = assertThrows(ViolationException.class, () -> service.create(request));

        assertTrue(ex.getViolations().stream().anyMatch(v -> v.path().full().contains("name")));
    }
}
```

`@KoraAppTest` / `@TestComponent` come from `io.koraframework.test.extension.junit5`
(artifact `io.koraframework:test-junit5`). `@TestComponent` resolves nodes from the already-built
graph, so `@TestComponent Validator<CreateUserRequest>` only injects when something in the
application already depends on that validator. Testing through the `@Validate` component, as above,
always works.
