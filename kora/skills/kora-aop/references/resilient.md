# Kora resilient — distilled reference

**Source:** [.kora-agent/kora-docs/mkdocs/docs/en/documentation/resilient.md](.kora-agent/kora-docs/mkdocs/docs/en/documentation/resilient.md)  
**Examples:** `.kora-agent/kora-examples/kora-java-resilient/`

Focused condensation of `kora-docs/.../documentation/resilient.md`.

## Setup

```groovy
implementation "ru.tinkoff.kora:resilient-kora"
```

```java
@KoraApp
public interface Application extends ResilientModule, /* ... */ { }
```

Four annotations, all under `ru.tinkoff.kora.resilient.*.annotation`:

| Annotation | Module | Annotation FQN |
|-----------|--------|-----------------|
| `@CircuitBreaker("name")` | circuitbreaker | `ru.tinkoff.kora.resilient.circuitbreaker.annotation.CircuitBreaker` |
| `@Retry("name")` | retry | `ru.tinkoff.kora.resilient.retry.annotation.Retry` |
| `@Timeout("name")` | timeout | `ru.tinkoff.kora.resilient.timeout.annotation.Timeout` |
| `@Fallback(value="name", method="fallbackMethod()")` | fallback | `ru.tinkoff.kora.resilient.fallback.annotation.Fallback` |

The `name` is the config key under `resilient.{circuitbreaker|retry|timeout|fallback}.<name>`.

## CircuitBreaker

```java
@Component
public class InventoryClient {
    @CircuitBreaker("inventory")
    public Stock get(String sku) { /* may throw */ }
}
```

```hocon
resilient.circuitbreaker {
  default {                                       # base settings
    slidingWindowSize             = 100
    minimumRequiredCalls          = 10
    failureRateThreshold          = 50            # percent (1-100)
    waitDurationInOpenState       = "25s"
    permittedCallsInHalfOpenState = 15
    enabled                       = true
  }
  inventory {                                     # named override
    waitDurationInOpenState = "10s"
  }
}
```

### State machine

| State | Behavior | Transition |
|-------|----------|-----------|
| `CLOSED` | Requests pass through. Failures counted in sliding window. | `OPEN` when `minimumRequiredCalls` reached and `failureRateThreshold` exceeded. |
| `OPEN` | Requests fail immediately. | `HALF_OPEN` after `waitDurationInOpenState`. |
| `HALF_OPEN` | `permittedCallsInHalfOpenState` requests allowed through. | `CLOSED` if all succeed. `OPEN` if any fail. |

### Custom failure predicate

By default every exception counts. Customize:

```java
@Component
public final class IgnoreNotFoundPredicate implements CircuitBreakerPredicate {
    public String name() { return "ignoreNotFound"; }
    public boolean test(Throwable e) { return !(e instanceof NotFoundException); }
}
```

```hocon
resilient.circuitbreaker.inventory.failurePredicateName = "ignoreNotFound"
```

### Imperative

```java
@Component
public final class OrdersService {
    private final CircuitBreakerManager manager;
    public OrdersService(CircuitBreakerManager manager) { this.manager = manager; }

    public Stock check(String sku) {
        return manager.get("inventory").accept(() -> client.get(sku));
    }
}
```

## Retry

```java
@Retry("inventory.check")
public Stock check(String sku) { /* may throw */ }
```

```hocon
resilient.retry {
  default {
    delay     = "100ms"               # initial delay before first retry
    attempts  = 2                     # additional attempts after the original call
    delayStep = "100ms"               # added to delay each subsequent retry
    enabled   = true
  }
  inventory.check { attempts = 3 }
}
```

Wait time on attempt `n` is `delay + (n-1) * delayStep`. With `delay=100ms, delayStep=100ms, attempts=3`, waits are 100ms, 200ms, 300ms.

Custom predicate via `RetryPredicate` interface, `failurePredicateName` in config — same pattern as CircuitBreaker.

Imperative: `RetryManager.get(name).retry(supplier)`.

## Timeout

```java
@Timeout("slow-call")
public String slowCall() { /* may hang */ }
```

```hocon
resilient.timeout {
  default        { duration = "1s",  enabled = true }
  slow-call      { duration = "10s" }
}
```

Throws `TimeoutExhaustedException` on expiry. The underlying thread is **interrupted** — your code should respond to `Thread.interrupted()`.

Imperative: `TimeoutManager.get(name).execute(supplier)`.

## Fallback

```java
@Component
public class InventoryClient {
    @Fallback(value = "inventory.check", method = "checkFallback(sku)")
    public Stock check(String sku) { return upstream.lookup(sku); }

    protected Stock checkFallback(String sku) { return Stock.UNKNOWN; }
}
```

`method` is the fallback method **with its arg list**: `"checkFallback(sku)"` says "call `checkFallback` passing `sku`". Signature must be compatible (return type assignable to the primary method's return).

```hocon
resilient.fallback {
  default { enabled = true }
  inventory.check { failurePredicateName = "ignoreClientErrors" }  # optional
}
```

Custom predicate via `FallbackPredicate` — same shape as the others.

## Stacking aspects — order matters

Outer annotation runs first. Recommended pattern from outside in:

```java
@Timeout("call")
@CircuitBreaker("call")
@Retry("call")
@Fallback(value = "call", method = "callFallback()")
public String call() { ... }
```

Semantics:
1. `@Timeout` caps the **entire** chain (including retries and fallback).
2. `@CircuitBreaker` short-circuits when open — `@Retry` doesn't even run.
3. `@Retry` retries the underlying call until success or attempts exhausted.
4. `@Fallback` provides a value if all retries fail.

To get **per-attempt timeout**, flip Retry above Timeout:

```java
@Retry("call")
@Timeout("call")           // applies to each retry attempt
public String call() { ... }
```

## Signatures

| Java | Kotlin |
|------|--------|
| `T method()` | `fun method(): T` |
| `CompletionStage<T>` | `suspend fun method(): T` |
| `Mono<T>` | — |

Java: class non-final. Kotlin: class `open`.

## See also

- Parent `../SKILL.md` — overview and pitfalls.
- `../../kora-client/SKILL.md` — pairing resilient with outbound HTTP calls.
