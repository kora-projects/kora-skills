# Sealed Hierarchies for Polymorphic JSON (Kora 2.x)

Verified against the Kora 2.0 sources — [`json/json-common`](https://github.com/kora-projects/kora/tree/2.0.0.RC2/json/json-common),
`SealedInterfaceReaderGenerator` / `SealedInterfaceWriterGenerator`, and the `SealedTest`
suites of `json-annotation-processor` and `json-symbol-processor`.

## Contents

1. [Overview](#1-overview)
2. [Basic pattern](#2-basic-pattern)
3. [Discriminator rules](#3-discriminator-rules)
4. [How it works](#4-how-it-works)
5. [Controller usage](#5-controller-usage)
6. [Advanced patterns](#6-advanced-patterns)
7. [Kotlin](#7-kotlin)
8. [Common pitfalls](#8-common-pitfalls)
9. [Quick reference](#9-quick-reference)

---

## 1. Overview

`@JsonDiscriminatorField` on a **sealed** interface or **sealed abstract class** enables
type-safe polymorphic JSON:

- **Type-safe** — the compiler knows the closed set of subtypes
- **Discriminator-based** — an explicit type field in the JSON document
- **Exhaustive** — `switch`/`when` over the hierarchy needs no default branch
- **Zero reflection** — the dispatching mapper is generated at compile time

The generated sealed mapper is *composed* from the per-subtype mappers, so **each subtype
needs its own `@Json`** (or `@JsonReader`/`@JsonWriter`).

---

## 2. Basic Pattern

Nested subtypes (the form used by the migrated examples):

```java
import io.koraframework.json.common.annotation.Json;
import io.koraframework.json.common.annotation.JsonDiscriminatorField;
import io.koraframework.json.common.annotation.JsonDiscriminatorValue;

@Json
@JsonDiscriminatorField("type")
public sealed interface Event {

    @Json
    @JsonDiscriminatorValue("created")
    record Created(String id) implements Event {}

    @Json
    @JsonDiscriminatorValue({"deleted", "removed"})
    record Deleted(String id, boolean permanent) implements Event {}
}
```

```json
{ "type": "created", "id": "42" }
{ "type": "deleted", "id": "42", "permanent": true }
```

Top-level subtypes with an explicit `permits` clause work the same way:

```java
@Json
@JsonDiscriminatorField("type")
public sealed interface PaymentResult permits PaymentSuccess, PaymentError {}

@Json
@JsonDiscriminatorValue("SUCCESS")
public record PaymentSuccess(String transactionId, BigDecimal amount) implements PaymentResult {}

@Json
@JsonDiscriminatorValue("ERROR")
public record PaymentError(String errorCode, String message) implements PaymentResult {}
```

`@JsonReader` or `@JsonWriter` may replace `@Json` on the supertype to generate only one
direction; the subtypes still need their own mappers.

---

## 3. Discriminator Rules

### The discriminator value is optional

`@JsonDiscriminatorValue` accepts `String[]`. **Without the annotation the discriminator
value is the subtype's simple name:**

```java
@Json
@JsonDiscriminatorField("@type")
public sealed interface TestInterface {
    @Json record Impl1(String value) implements TestInterface {}
    @Json record Impl2(int value) implements TestInterface {}
}
```
```json
{ "@type": "Impl1", "value": "test" }
{ "@type": "Impl2", "value": 42 }
```

An **empty** array is a build error:

```
Json discriminator value can't be empty:
  com.example.Impl1

Problem:
  @JsonDiscriminatorValue declares an empty value array.
```

### The discriminator does not have to be a field of the subtype

The generated writer emits the discriminator itself, so a subtype carrying **no** matching
component is the normal case (see the example above — `Impl1` has only `value`).

If you *do* want the discriminator visible on the model, declare a component whose JSON name
matches the discriminator field. The writer then takes the value from that component, which
is what makes several discriminator values on one subtype round-trip:

```java
@Json
@JsonDiscriminatorValue({"Impl1.1", "Impl1.2"})
record Impl1(@JsonField("@type") String type, String value) implements TestInterface {}
```

With multiple values and **no** such component the writer emits the **first** value in the
array, while the reader accepts any of them.

### A missing discriminator can have a default

`@JsonDiscriminatorField` has a second attribute, `defaultValue`, used when the field is
absent from the incoming document:

```java
@Json
@JsonDiscriminatorField(value = "@type", defaultValue = "Impl1")
public sealed interface TestInterface { … }
```
```json
{ "value": "test" }              → Impl1
{ "@type": "Impl2", "value": 42 } → Impl2
```

Without `defaultValue`, a document with no discriminator fails to read with
`Failed to read json <Type>: missing required discriminator field "<field>", expected one of [<values>] (at <pointer>)`.
`defaultValue` covers only an **absent** field — an unknown value still fails (below).

---

## 4. How It Works

**Deserialization**
1. The generated reader buffers the object (`BufferingJsonParser`) so the discriminator may
   appear **anywhere** in it, not just first.
2. It resolves the discriminator value (or `defaultValue`) to a subtype.
3. It replays the buffered tokens into that subtype's `JsonReader`.
4. Input `null` reads as `null`.

**Serialization**
1. The generated writer switches on the runtime subtype.
2. It writes the discriminator field — from the matching component if there is one,
   otherwise the subtype's first (or only) discriminator value.
3. It delegates the remaining fields to that subtype's `JsonWriter`.

**Inheritance** — the discriminator is looked up through the supertype chain, so
intermediate sealed sub-interfaces work without repeating the annotation:

```java
@Json
@JsonDiscriminatorField("@type")
public sealed interface TestInterface {
    sealed interface Subinterface extends TestInterface {}
    @Json record Impl1(String value) implements Subinterface {}
    @Json record Impl2(int value) implements Subinterface {}
}
```

**Sealed abstract classes** are supported too, with the same rules (the subtypes need
accessors for the writer, as any non-record class does).

---

## 5. Controller Usage

### Returning a sealed type

```java
@Component
@HttpController
public final class PaymentController {

    private final PaymentService paymentService;

    public PaymentController(PaymentService paymentService) {
        this.paymentService = paymentService;
    }

    @HttpRoute(method = HttpMethod.POST, path = "/payments/{id}")
    @Json
    public PaymentResult processPayment(@Path String id) {
        try {
            var transaction = paymentService.process(id);
            return new PaymentSuccess(transaction.id(), transaction.amount());
        } catch (PaymentException e) {
            return new PaymentError(e.errorCode(), e.getMessage());
        }
    }
}
```

### Pattern matching over the result

```java
String describe(PaymentResult result) {
    return switch (result) {                       // exhaustive — no default branch
        case PaymentSuccess success -> "completed " + success.transactionId();
        case PaymentError error -> "failed " + error.errorCode();
    };
}
```

### Accepting a sealed type as a request body

```java
@HttpRoute(method = HttpMethod.POST, path = "/notifications")
public void handleNotification(@Json PaymentResult result) {
    switch (result) {
        case PaymentSuccess success -> log.info("Payment completed: {}", success.transactionId());
        case PaymentError error -> log.warn("Payment failed: {} - {}", error.errorCode(), error.message());
    }
}
```

---

## 6. Advanced Patterns

### Multiple discriminator values

`@JsonDiscriminatorValue` takes a `String[]` — pass an array, do not repeat the annotation:

```java
@Json
@JsonDiscriminatorValue({"CARD_SUCCESS", "BANK_SUCCESS"})
public record PaymentSuccess(String transactionId, BigDecimal amount) implements PaymentResult {}
```

Both values read into `PaymentSuccess`; writing produces `"CARD_SUCCESS"` (the first entry)
unless the subtype exposes the discriminator as a component.

### Generic sealed hierarchies

Type parameters are propagated to the subtype mappers:

```java
@Json
@JsonDiscriminatorField("@type")
public sealed interface Response<T> {

    @Json
    @JsonDiscriminatorValue("ok")
    record Ok<T>(T data) implements Response<T> {}

    @Json
    @JsonDiscriminatorValue("fail")
    record Fail<T>(String error) implements Response<T> {}
}
```

A concrete `JsonReader<Response<UserResponse>>` still needs `JsonReader<UserResponse>` in the
graph — i.e. `UserResponse` must itself be `@Json`.

### A discriminator that is also a typed field

When the model must expose the discriminator (for example as an enum on every subtype), give
each subtype a component named like the discriminator field:

```java
@Json
@JsonDiscriminatorField("status")
public sealed interface UserResult permits UserResult.UserSuccess, UserResult.UserError {

    @Json
    enum Status { OK, ERROR }

    Status status();

    @Json
    @JsonDiscriminatorValue("OK")
    record UserSuccess(Status status, UserResponse user) implements UserResult {}

    @Json
    @JsonDiscriminatorValue("ERROR")
    record UserError(Status status, String message) implements UserResult {}
}
```

The nested `Status` enum needs its own `@Json` so a `JsonReader`/`JsonWriter` exists for it.

---

## 7. Kotlin

```kotlin
import io.koraframework.json.common.annotation.Json
import io.koraframework.json.common.annotation.JsonDiscriminatorField
import io.koraframework.json.common.annotation.JsonDiscriminatorValue

@Json
@JsonDiscriminatorField("type")
sealed interface Event {

    @Json
    @JsonDiscriminatorValue("created")
    data class Created(val id: String) : Event

    @Json
    @JsonDiscriminatorValue("deleted", "removed")   // vararg form of the String[] attribute
    data class Deleted(val id: String, val permanent: Boolean) : Event
}
```

```kotlin
@Component
@HttpController
class PaymentController(private val paymentService: PaymentService) {

    @HttpRoute(method = HttpMethod.POST, path = "/payments/{id}")
    @Json
    fun processPayment(@Path id: String): PaymentResult = try {
        val transaction = paymentService.process(id)
        PaymentSuccess(transaction.id, transaction.amount)
    } catch (e: PaymentException) {
        PaymentError(e.errorCode, e.message.orEmpty())
    }

    @HttpRoute(method = HttpMethod.POST, path = "/notifications")
    fun handleNotification(@Json result: PaymentResult) {
        when (result) {                            // exhaustive
            is PaymentSuccess -> log.info("Payment completed: ${result.transactionId}")
            is PaymentError -> log.warn("Payment failed: ${result.errorCode}")
        }
    }
}
```

Reading a sealed value outside the HTTP layer returns a nullable:

```kotlin
val event: Event = requireNotNull(eventReader.read(body))
```

---

## 8. Common Pitfalls

### Missing `@Json` on a subtype

```java
// WRONG — no mapper is generated for PaymentSuccess, so the sealed mapper cannot be wired
@JsonDiscriminatorValue("SUCCESS")
public record PaymentSuccess(String transactionId) implements PaymentResult {}

// CORRECT
@Json
@JsonDiscriminatorValue("SUCCESS")
public record PaymentSuccess(String transactionId) implements PaymentResult {}
```

### Missing `@Json` on the supertype

```java
// WRONG — @JsonDiscriminatorField alone generates nothing
@JsonDiscriminatorField("type")
public sealed interface PaymentResult permits PaymentSuccess, PaymentError {}

// CORRECT
@Json
@JsonDiscriminatorField("type")
public sealed interface PaymentResult permits PaymentSuccess, PaymentError {}
```

### Adding a `String type` component "because the discriminator needs one"

Not required — and if you add one, its JSON name must match the discriminator field
(`@JsonField("type")` when the names differ) or you get **two** keys in the output: the
discriminator written by the sealed writer plus your own field.

### Discriminator value mismatch

The value in the JSON must match a `@JsonDiscriminatorValue` entry exactly (case included),
or the subtype's simple name when the annotation is absent. There is no fuzzy matching. A
mismatch fails with a `StreamReadException` that lists what would have been accepted:

```
Failed to read json Payment: unknown discriminator value "wire" for field "type", expected one of [CARD, CASH] (at …)
```

A discriminator that is not a string (a number, an object) fails with
`Failed to read json: expected a string discriminator value for field "type", but got … (at …)`,
and a sealed value that is not a JSON object with
`Failed to read json: expected an object to read discriminator field "type", but got … (at …)`.

### Non-sealed supertype

`@JsonDiscriminatorField` is only honoured on a type carrying the `sealed` modifier; on an
ordinary interface it is silently ignored and the reader generation fails with
`JsonReader can't be generated for type` instead.

---

## 9. Quick Reference

```java
@Json
@JsonDiscriminatorField("type")                  // optional: defaultValue = "…"
public sealed interface ResultType permits SuccessCase, ErrorCase {}

@Json                                            // required on every subtype
@JsonDiscriminatorValue("SUCCESS")               // optional: defaults to the simple name
public record SuccessCase(/* success-specific fields */) implements ResultType {}

@Json
@JsonDiscriminatorValue("ERROR")
public record ErrorCase(/* error-specific fields */) implements ResultType {}
```

| Question | Answer |
|---|---|
| Must the supertype be `sealed`? | Yes — sealed interface or sealed abstract class |
| Must every subtype carry `@Json`? | Yes (or `@JsonReader`/`@JsonWriter`) |
| Must `@JsonDiscriminatorValue` be present? | No — defaults to the subtype simple name |
| Must the discriminator be a component of the subtype? | No — the writer emits it |
| Several values per subtype? | Yes — `@JsonDiscriminatorValue({"a", "b"})` |
| Discriminator missing in the document? | Only readable via `@JsonDiscriminatorField(defaultValue = "…")` |
| Discriminator anywhere in the object? | Yes — the reader buffers the object |
| Generics? | Yes — subtype mappers receive the type arguments |
