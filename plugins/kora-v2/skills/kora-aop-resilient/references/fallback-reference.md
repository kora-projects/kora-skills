# @Fallback Reference

**Annotation:** `@Fallback(method = "fallbackMethod()")` — `io.koraframework.resilient.fallback.annotation.Fallback`
**Artifact:** `io.koraframework:resilient-kora`

> **The `value` attribute was removed in 2.0.** `method` is the only attribute. There is no
> `@FallbackSpec`, no `resilient.fallback.<name>` configuration section and no `FallbackPredicate` —
> a fallback is not a configurable component, it is a code path. The only fallback configuration in
> 2.0 is telemetry, under `resilient.telemetry.fallback`.

## Contents

- [Basic Usage](#basic-usage)
- [Method Reference Syntax](#method-reference-syntax)
- [Signature Rules](#signature-rules)
- [@Fallback.Reason](#fallbackreason)
- [Position in a Stack](#position-in-a-stack)
- [Patterns](#patterns)
- [Telemetry](#telemetry)
- [Common Pitfalls](#common-pitfalls)

---

## Basic Usage

```java
@Component
public class ProductService {                    // NOT final

    private final ProductRepository repository;
    private final ProductCache cache;

    public ProductService(ProductRepository repository, ProductCache cache) {
        this.repository = repository;
        this.cache = cache;
    }

    @Fallback(method = "getFromCache(id)")
    public Product getProduct(String id) {
        return repository.findById(id)
            .orElseThrow(() -> new ProductNotFoundException(id));
    }

    protected Product getFromCache(String id) {
        return cache.get(id);
    }
}
```

```kotlin
@Component
open class ProductService(
    private val repository: ProductRepository,
    private val cache: ProductCache
) {

    @Fallback(method = "getFromCache(id)")
    open fun getProduct(id: String): Product =
        repository.findById(id) ?: throw ProductNotFoundException(id)

    protected open fun getFromCache(id: String): Product = cache.get(id)
}
```

The generated proxy wraps the body in `try { … } catch (Throwable _e) { … fallback … }`. **Every**
`Throwable` triggers the fallback unless a `@Fallback.Reason` parameter narrows it.

---

## Method Reference Syntax

`method` is a textual reference resolved at compile time: `name()` or `name(arg1, arg2)`.
Argument names must be **parameter names of the annotated method**, and they are passed straight
through — this is not an expression language.

| Annotated method | Valid `method` values |
|---|---|
| `Product getProduct(String id)` | `"getFromCache()"`, `"getFromCache(id)"` |
| `User getUser(String id, boolean details)` | `"fb()"`, `"fb(id)"`, `"fb(details)"`, `"fb(id, details)"` |

Missing parentheses fail the build:

```
@Fallback method reference 'getFromCache' has invalid syntax.

Fix: use method reference syntax 'methodName()' or 'methodName(arg1, arg2)'.
Example: @Fallback(method = "fallback(value)")
```

An unknown argument name fails with
`@Fallback method reference 'fb(missing)' uses unknown source arguments: [missing].`

---

## Signature Rules

1. The fallback method lives in the **same class** as the annotated method — a missing one is
   `@Fallback method 'x' was not found in '<Class>'.`
2. Its parameter list must be exactly the referenced arguments, **plus at most one**
   `@Fallback.Reason` parameter. Any other shape fails with
   `@Fallback method 'x' does not match requested signature 'x(id)'.`
3. Its return type must be assignable to the annotated method's return type. For a `void`/`Unit`
   method the fallback is `void`/`Unit` too.
4. It must be reachable from the generated subclass — `protected` or `public` (Java), non-`private`
   (Kotlin). `private` breaks the generated call.
5. It does **not** itself need to be `open` in Kotlin; only the annotated method does. The examples
   mark it `protected open` anyway, which is fine.
6. An exception thrown *by the fallback* is recorded and rethrown — there is no second fallback.

```java
// correct — subset of arguments, same return type, protected
@Fallback(method = "getUserFallback(id)")
public User getUser(String id, boolean includeDetails) { … }
protected User getUserFallback(String id) { … }

// wrong — extra parameter the reference does not supply
@Fallback(method = "getUserFallback(id)")
public User getUser(String id, boolean includeDetails) { … }
protected User getUserFallback(String id, boolean includeDetails) { … }

// wrong — private is unreachable from the proxy
@Fallback(method = "getUserFallback(id)")
public User getUser(String id) { … }
private User getUserFallback(String id) { … }
```

Argument *order* follows the reference string, so `"fb(b, a)"` really does pass `b` first; the
fallback's parameter types must line up with that order.

---

## @Fallback.Reason

New in 2.0, and the replacement for the removed `FallbackPredicate`. One fallback parameter may be
annotated `@Fallback.Reason` to receive the exception that triggered the fallback:

```java
@Fallback(method = "chargeFallback(request)")
public PaymentResult charge(PaymentRequest request) { … }

protected PaymentResult chargeFallback(PaymentRequest request,
                                       @Fallback.Reason RuntimeException reason) {
    log.warn("charge failed, queueing for review", reason);
    return PaymentResult.pendingManualReview();
}
```

**The reason parameter is never named in the `method` string.** The reference lists only the
annotated method's own parameters — `"chargeFallback(request)"` above, not
`"chargeFallback(request, reason)"` — and the processor appends the exception itself. Naming it
fails the build, because `reason` is not a parameter of `charge`.

**The parameter type is also a filter.** The generated code emits
`if (!(_e instanceof <ReasonType>)) { throw _e; }` before invoking the fallback, so anything outside
that type propagates untouched. Declaring `@Fallback.Reason IllegalStateException` in Kotlin means
only `IllegalStateException` degrades; everything else fails the call.

In **Java** the permitted reason type is fixed by the annotated method's `throws` clause:

| Annotated method declares | Required `@Fallback.Reason` type |
|---|---|
| no `throws` | `RuntimeException` |
| `throws SomeCheckedException` | `Exception` |
| `throws Throwable` | `Throwable` |

A mismatch fails the build with
`@Fallback.Reason parameter on fallback method 'x' has incompatible type '…'. Expected: ….`
In **Kotlin** there is no checked-exception clause and no such restriction — whatever type you
declare becomes the filter.

More than one `@Fallback.Reason` parameter is an error:
`@Fallback method 'x' declares more than one @Fallback.Reason parameter.`

---

## Position in a Stack

Declaration order decides nesting: first-listed is outermost. `@Fallback` belongs at the top, so it
catches everything the inner aspects raise — `CallNotPermittedException` from an open circuit
breaker, `RetryExhaustedException`, `TimeoutExhaustedException`, `RateLimitExceededException`, and
the original business exception alike.

```java
@Fallback(method = "chargeFallback(request)")   // outermost
@CircuitBreakable(PaymentCircuitBreaker.class)
@Retryable(PaymentRetry.class)
@Timeout(PaymentTimeouter.class)                // innermost
public PaymentResult charge(PaymentRequest request) { … }
```

Putting `@Fallback` last instead makes it innermost: it swallows the business exception before the
circuit breaker ever sees a failure, so the breaker records only successes and never opens.

---

## Patterns

### Cached / stale read

```java
@Fallback(method = "fromCache(id)")
public Product getProduct(String id) {
    return remoteCatalog.fetch(id);
}

protected Product fromCache(String id) {
    return cache.get(id);
}
```

### Deferred write

```java
@Fallback(method = "enqueue(request)")
public PaymentResult charge(PaymentRequest request) {
    return paymentGateway.charge(request);
}

protected PaymentResult enqueue(PaymentRequest request) {
    manualReviewQueue.enqueue(request);
    return PaymentResult.pendingManualReview();
}
```

### Degrade only on infrastructure failure

```java
@Fallback(method = "unknownStock(sku)")
public Stock checkStock(String sku) {
    return inventoryClient.lookup(sku);
}

// HttpClientResponseException only — a domain exception propagates to the caller
protected Stock unknownStock(String sku, @Fallback.Reason RuntimeException reason) {
    if (!(reason instanceof HttpClientResponseException)) {
        throw reason;
    }
    return Stock.UNKNOWN;
}
```

When the discriminator is a type, prefer narrowing the `@Fallback.Reason` parameter type itself and
let the generated guard do the work.

---

## Telemetry

Off by default, and the only fallback configuration there is:

```hocon
resilient.telemetry.fallback {
  logging.enabled = true
  metrics.enabled = true
}
```

One counter, `resilient.fallback.attempts`, tagged `resilient.name` = `<fully.qualified.Class>.<method>` of
the annotated method — fallbacks are identified by call site, not by a config path.

---

## Common Pitfalls

| Problem | Cause / fix |
|---|---|
| `@Fallback(value = "…")` does not compile | `value` was removed in 2.0; keep only `method`. |
| `@Fallback method 'x' was not found` | Fallback declared in another class or misspelled. |
| `does not match requested signature` | Parameter list is not exactly the referenced args (+ one optional `@Fallback.Reason`). |
| `has invalid syntax` | Missing `()` in the method reference. |
| Fallback never runs | It is nested inside another aspect that already handled the failure — move `@Fallback` to the top. |
| Circuit breaker never opens | `@Fallback` placed innermost swallows the failure before the breaker records it. |
| `@Fallback.Reason parameter … has incompatible type` | Java: match the type to the method's `throws` clause. |
| Fallback hides a real outage | Emit a log/metric in the fallback body; `resilient.fallback.attempts` only counts. |

---

## See Also

- [circuit-breaker-reference.md](circuit-breaker-reference.md) — what `CallNotPermittedException` means
- [retry-reference.md](retry-reference.md) — `RetryExhaustedException` and its cause
- [resilience-config-reference.md](resilience-config-reference.md) — telemetry and the full key set
