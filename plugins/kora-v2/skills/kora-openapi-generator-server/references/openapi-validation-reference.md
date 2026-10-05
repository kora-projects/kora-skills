# OpenAPI Validation Reference — Kora 2.x

`configOptions.enableServerValidation` turns OpenAPI schema constraints into Kora validation
annotations on the generated models and controller parameters. Kora validation is **not**
Jakarta Bean Validation — the annotations live in
`io.koraframework.validation.common.annotation` and are processed at compile time.

## Contents

- [1. Turning it on](#1-turning-it-on)
- [2. What gets generated](#2-what-gets-generated)
- [3. Constraint mapping](#3-constraint-mapping)
- [4. One annotation per property — the precedence chain](#4-one-annotation-per-property--the-precedence-chain)
- [5. The failure path and `enableServerValidationInterceptor`](#5-the-failure-path-and-enableservervalidationinterceptor)
- [6. Customising the error response](#6-customising-the-error-response)
- [7. `validation-module` and `http-server-common`](#7-validation-module-and-http-server-common)
- [8. Pitfalls](#8-pitfalls)

---

## 1. Turning it on

```groovy
configOptions = [
    mode                  : "java-server",
    enableServerValidation: "true",
]
```

```groovy
dependencies {
    implementation "io.koraframework:validation-module"
}
```

```java
@KoraApp
public interface Application extends
        HoconConfigModule, LogbackModule, JsonModule,
        ValidationModule,                       // io.koraframework.validation.module.ValidationModule
        UndertowPublicHttpServerModule { … }
```

`enableServerValidation` is read **only** in a server mode; on a client task it is a silent
no-op. Without `ValidationModule` in the graph the build fails on the missing
`ValidationHttpServerInterceptor` / `Validator<T>` components.

## 2. What gets generated

On the controller method:

```java
@InterceptWith(ValidationHttpServerInterceptor.class)   // see section 5
@Validate
public PetsApiResponses.ListPetsApiResponse listPets(
    @Query("filter") @Pattern(".*") String filter,
    @Query("limit") @Range(from = 1.0, to = 100.0, boundary = Range.Boundary.INCLUSIVE_INCLUSIVE)
    @Nullable Integer limit) throws Exception { … }

@InterceptWith(ValidationHttpServerInterceptor.class)
@Validate
public PetApiResponses.AddPetApiResponse addPet(@Json @Valid PetCreateTO petCreateTO) throws Exception { … }
```

On models: `@Valid` on the type, and one constraint annotation per constrained field. The
`*ApiDelegate` interface itself carries **no** validation annotations — validation runs in the
controller, before your delegate is called, so a delegate method only ever sees valid input.

## 3. Constraint mapping

| OpenAPI schema | Generated annotation |
|---|---|
| `minimum: 1` (integer/long, no `maximum`) | `@Min(1L)` |
| `minimum: 0` (integer/long, no `maximum`) | `@PositiveOrZero` |
| `minimum: 0, exclusiveMinimum: true` | `@Positive` |
| `maximum: 100` (integer/long, no `minimum`) | `@Max(100L)` |
| `maximum: 0` (integer/long) | `@NegativeOrZero` |
| `maximum: 0, exclusiveMaximum: true` | `@Negative` |
| `minimum` **and** `maximum`, or a non-integral numeric type | `@Range(from = …, to = …, boundary = Range.Boundary.INCLUSIVE_INCLUSIVE)` |
| `exclusiveMinimum` / `exclusiveMaximum` on a range | `boundary = Range.Boundary.EXCLUSIVE_INCLUSIVE` etc. |
| `minLength` / `maxLength` | `@Size(min = …, max = …)` (`max` defaults to `Integer.MAX_VALUE`) |
| `minItems` / `maxItems` | `@Size(min = …, max = …)` |
| `pattern: "^[a-z]+$"` | `@Pattern("^[a-z]+$")` |
| a `$ref` to another model | `@Valid` (cascades) |

A missing `minimum` in a `@Range` is filled with the type's floor (`Long.MIN_VALUE`,
`Integer.MIN_VALUE`) and likewise for `maximum`.

Up to 2.0.0.RC1 — fixed on master by kora-projects/kora PR #965 — the generator gets these schemas wrong:

| Schema | What happens | Without the fix |
|---|---|---|
| `type: number` (`BigDecimal`/`BigInteger`) with only `minimum` or only `maximum`, e.g. an amount with `minimum: 0` | generation fails: `IllegalArgumentException: Invalid OpenAPI numeric validation schema. Schema dataType: BigDecimal` | declare both bounds, or check the bound in the delegate |
| `format: double` / `float` with only `maximum` | the missing lower bound is `Double.MIN_VALUE` / `Float.MIN_VALUE` — the smallest **positive** value, so `0` and every negative value are rejected | declare `minimum` explicitly |
| Kotlin, fractional `minimum` and `maximum` | the upper bound is taken from `minimum`: `@Range(from = 0.5, to = 0.5)` | check the range in the delegate |
| `pattern` containing a backslash (`\S`, `\d`) | escaped twice: `.*\S.*` becomes `@Pattern(".*\\\\S.*")`, a literal backslash followed by `S` | check the pattern in the delegate |

With the fix a single bound on `BigDecimal`/`BigInteger` generates the same annotations as on
integers (`@PositiveOrZero`, `@Min`, …), and the pattern reaches `@Pattern` unchanged.

`required` is **not** a validation annotation — it is expressed as non-nullability in the
generated signature and enforced by the request parser, which answers `400` before validation
runs.

## 4. One annotation per property — the precedence chain

Fixed on master by kora-projects/kora PR #965: every constraint the schema declares is generated,
and an array of models also gets `@Valid`. Up to 2.0.0.RC1 the generator returns
**at most one** constraint annotation per property, from a first-match chain in this order:

1. `minimum` / `maximum`
2. `minLength` / `maxLength`
3. `minItems` / `maxItems`
4. `pattern`
5. `$ref` to a model → `@Valid`

So a string schema declaring **both** `maxLength` and `pattern` generates only `@Size` — the
`pattern` is silently not enforced — and an array of models with `minItems` gets `@Size` but no
`@Valid`, so its items are not validated at all. If you need both, validate the second constraint in the
delegate and return the contract's `400`, or split the schema. Do not add the annotation to
generated code.

## 5. The failure path and `enableServerValidationInterceptor`

`@Validate` makes the aspect throw
`io.koraframework.validation.common.ViolationException` when a constraint fails.
`ValidationHttpServerInterceptor` catches it and converts it to a response:

```java
try {
    return chain.process(request);
} catch (ViolationException e) {
    // custom mapper if one is in the graph, else:
    return HttpServerResponseException.of(400, e.getMessage());
}
```

`enableServerValidationInterceptor` defaults to **`true`**, which is why the interceptor
annotation appears on every validated method. Set it to `"false"` when you handle
`ViolationException` yourself — for instance in a global interceptor registered under
`@Tag(HttpServer.class)`, or when the contract requires an error body the default 400 cannot
produce. With it off, an unmapped `ViolationException` propagates as a 500.

## 6. Customising the error response

Supply a `ViolationExceptionHttpServerResponseMapper` and keep the interceptor. The framework
injects it as `@Nullable`, so it is genuinely optional; returning `null` from it falls back to the
plain 400.

```java
@KoraApp
public interface Application extends … {

    default ViolationExceptionHttpServerResponseMapper customViolationExceptionHttpServerResponseMapper() {
        return (request, exception) -> HttpServerResponseException.of(400, exception.getMessage());
    }
}
```

```kotlin
@KoraApp
interface Application : … {

    fun customViolationExceptionHttpServerResponseMapper(): ViolationExceptionHttpServerResponseMapper =
        ViolationExceptionHttpServerResponseMapper { _, exception ->
            HttpServerResponseException.of(400, exception.message)
        }
}
```

Both are `io.koraframework.validation.module.http.server.*`. A method on the `@KoraApp`
interface is a module factory method, so no `@Component` is needed — and adding one would create
a second candidate.

## 7. `validation-module` and `http-server-common`

`ValidationModule`'s only default method returns a `ValidationHttpServerInterceptor`, which
implements `io.koraframework.http.server.common.interceptor.HttpServerInterceptor`. But
`validation-module` declares `http-server-common` as **`compileOnly`**, so that dependency is
not transitive: the consuming project must put the HTTP server on the classpath itself.

For an OpenAPI server this is automatic — `io.koraframework:http-server-undertow` brings
`http-server-common` with it. It only bites a project that wants Kora validation *without* an
HTTP server; there `ValidationModule` fails to resolve `HttpServerInterceptor`. In that case use
`io.koraframework.validation.common.constraint.ValidatorModule` (which `ValidationModule`
extends) instead.

## 8. Pitfalls

| Symptom | Cause and fix |
|---|---|
| No validation annotations in the output | `enableServerValidation` not `"true"`, or it was set on a client-mode task. |
| Graph build fails on `ValidationHttpServerInterceptor` | `ValidationModule` missing from `@KoraApp`, or `io.koraframework:validation-module` missing from dependencies. |
| `pattern` never enforced | The property also declares `minLength`/`maxLength`; only one constraint is generated (section 4). |
| Constraint violation returns 500 | `enableServerValidationInterceptor: "false"` and nothing catches `ViolationException`. |
| Two `ViolationExceptionHttpServerResponseMapper`s | One as a `@KoraApp` default method and one as a `@Component` — keep exactly one. |
| Controller is `final` and aspects fail | Cannot happen through the generator: it emits the controller non-`final` (Java) / `open` (Kotlin) exactly when validation or extension annotations are on. If you see it, generated output is stale — `clean` and regenerate. |
| Jakarta annotations do nothing | Kora validation is its own annotation set; `jakarta.validation.*` is ignored. |

## Related

- [Controllers Reference](openapi-controllers-reference.md) — where the annotations land
- [Models Reference](openapi-models-reference.md) — field-level constraints
- `kora-aop-validation` skill — `@Valid`, `@Validate`, custom constraints
