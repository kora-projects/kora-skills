# @CircuitBreakable Reference

**Annotation:** `@CircuitBreakable(X.class)` — `io.koraframework.resilient.circuitbreaker.annotation.CircuitBreakable`
**Spec:** `@CircuitBreakerSpec("<config path>")` on `interface X extends io.koraframework.resilient.circuitbreaker.CircuitBreaker`
**Artifact:** `io.koraframework:resilient-kora`

> Renamed in 2.0. The 1.x annotation was `@CircuitBreaker("name")`; that name now belongs to the
> runtime contract `CircuitBreaker`, which spec interfaces extend.

## Contents

- [Basic Usage](#basic-usage)
- [State Machine](#state-machine)
- [Window Implementations](#window-implementations)
- [Configuration](#configuration)
- [Failure Predicate](#failure-predicate)
- [Imperative Use](#imperative-use)
- [Telemetry](#telemetry)
- [Common Pitfalls](#common-pitfalls)

---

## Basic Usage

```java
// OrderCircuitBreaker.java — one spec per config path, shared by every caller
@CircuitBreakerSpec("resilient.circuitbreaker.order")
public interface OrderCircuitBreaker extends CircuitBreaker {}
```

```java
@Component
public class OrderClient {                       // NOT final

    private final OrderHttpClient httpClient;

    public OrderClient(OrderHttpClient httpClient) {
        this.httpClient = httpClient;
    }

    @CircuitBreakable(OrderCircuitBreaker.class)
    public Order getOrder(String orderId) {
        return httpClient.get(orderId);
    }
}
```

```kotlin
@CircuitBreakerSpec("resilient.circuitbreaker.order")
interface OrderCircuitBreaker : CircuitBreaker
```

```kotlin
@Component
open class OrderClient(private val httpClient: OrderHttpClient) {

    @CircuitBreakable(OrderCircuitBreaker::class)
    open fun getOrder(orderId: String): Order = httpClient.get(orderId)
}
```

The annotation processor turns each spec into two generated files: `$OrderCircuitBreaker_Impl`
(extends `KoraCircuitBreaker`, implements your interface) and `$OrderCircuitBreaker_Module`
(a `@Module` supplying the config and the instance). `@KoraApp` picks the module up
automatically — do not extend it.

### Sharing, not copying

The spec interface *is* the identity of the circuit breaker. Two interfaces with the same
`@CircuitBreakerSpec` path are **two independent breakers** with independent windows and states.
If `OrderClient` and `OrderAdminClient` must trip together, both annotate with the *same*
`OrderCircuitBreaker.class`.

---

## State Machine

`CircuitBreaker.State` is `CLOSED`, `OPEN`, `HALF_OPEN`.

| State | Behaviour | Transition |
|---|---|---|
| **CLOSED** | Calls pass through; outcomes recorded in the window | → OPEN once at least `minimumRequiredCalls` are recorded and the failure rate reaches `failureRateThreshold` |
| **OPEN** | Every call throws `CallNotPermittedException` immediately | → HALF_OPEN after `waitDurationInOpenState` |
| **HALF_OPEN** | Up to `permittedCallsInHalfOpenState` probes allowed; further calls throw | → CLOSED if probes pass, → OPEN if the failure rate is still at/above the threshold |

`CallNotPermittedException` carries `state()` and a message naming the breaker, e.g.
`Call Is Not Permitted due to CircuitBreaker 'OrderCircuitBreaker' been in OPEN state`.
**The name in the message is the spec interface's simple name**, not the config path.

The aspect wraps the call as `acquire()` → body → `releaseOnSuccess()` / `releaseOnError(e)`.
A `CallNotPermittedException` raised by `acquire()` is rethrown untouched and is **not** recorded
as a failure of the breaker itself.

---

## Window Implementations

`CircuitBreakerConfig.CircuitBreakerType` — set with `type` in the config section:

| `type` | Window | When to use |
|---|---|---|
| `STRIPED_APPROX` (**default**) | count-based, sharded across `countBased.stripedApprox.stripes` (default 16, max 64) | hot paths at high concurrency; CLOSED statistics are approximate and can drift under uneven load |
| `FIXED_WINDOW` | count-based, single packed counter | cheapest; what the migrated examples use |
| `RING_BUFFER` | count-based, exact last-N history via a global sequencer | the closest match to the 1.x counting window; `windowSize` capped at 2^22 |
| `TIME_BASED` | time-based buckets over `timeBased.windowDuration` | rate over a period rather than over a call count |

`STRIPED_APPROX`, `FIXED_WINDOW` and `RING_BUFFER` require a `countBased` block.
`TIME_BASED` requires a `timeBased` block instead and ignores `countBased`.

**Porting a 1.x `slidingWindowSize`:** `RING_BUFFER` preserves the semantics (exact last N calls);
`FIXED_WINDOW` is cheaper and usually good enough. Choosing nothing gives you `STRIPED_APPROX`,
whose statistics are deliberately approximate — decide rather than default into it.

---

## Configuration

```hocon
resilient.circuitbreaker.order {
  type = FIXED_WINDOW                # default STRIPED_APPROX
  countBased.windowSize = 50         # required unless type = TIME_BASED
  minimumRequiredCalls = 25          # required
  failureRateThreshold = 50          # required, percent, 1..100
  waitDurationInOpenState = "25s"    # required
  permittedCallsInHalfOpenState = 10 # required
  enabled = true                     # optional, default true
}
```

`failureRateThreshold`, `minimumRequiredCalls`, `permittedCallsInHalfOpenState` and
`waitDurationInOpenState` have **no defaults** — every section must set all four. See
[resilience-config-reference.md](resilience-config-reference.md) for the full key set including
`countBased.stripedApprox.stripes` and the `timeBased` block.

### Validation happens during graph initialisation

`KoraCircuitBreaker`'s constructor calls `CircuitBreakerConfig.validate(name, config)` before it
picks an implementation, so bad values fail the application startup with an
`IllegalArgumentException` naming the exact property:

| Message | Cause |
|---|---|
| `CircuitBreaker 'X' property 'countBased' is not configured` | window block missing (any non-`TIME_BASED` type) |
| `CircuitBreaker 'X' property 'timeBased' is not configured` | `type = TIME_BASED` without a `timeBased` block |
| `CircuitBreaker 'X' property 'minimumRequiredCalls' can't be negative or zero value` | `minimumRequiredCalls < 1` |
| `CircuitBreaker 'X' property 'minimumRequiredCalls' has value N, it can't be greater than property 'countBased.windowSize'` | more required calls than the window can hold |
| `CircuitBreaker 'X' failureRateThreshold is percentage and must be in range from 1 to 100` | threshold outside 1..100 |
| `CircuitBreaker 'X' property 'countBased.windowSize' can't be greater than 4194304 for 'RING_BUFFER' type` | `RING_BUFFER` window over 2^22 |
| `CircuitBreaker 'X' property 'countBased.stripedApprox.stripes' can't be greater than 64` | too many stripes |

A *missing* section is a different failure and comes from the config layer first:
`ConfigValueException: Config expected value, but got null at path: 'ROOT.resilient.circuitbreaker.order.failureRateThreshold'`.

---

## Failure Predicate

By default every exception counts as a failure **except** one that implements the marker interface
`io.koraframework.resilient.circuitbreaker.NonCircuitableException` — `CircuitBreaker.isFailure` is
`!(throwable instanceof NonCircuitableException)`:

```java
public final class OrderNotFoundException extends RuntimeException implements NonCircuitableException {
    public OrderNotFoundException(String id) { super("Order not found: " + id); }
}
```

```kotlin
class OrderNotFoundException(id: String) : RuntimeException("Order not found: $id"), NonCircuitableException
```

An exception the breaker does not count still propagates to the caller unchanged. It is recorded as
neither a failure nor a success (`CallResult.IGNORED_FAILURE` in telemetry): in `CLOSED` it does not
enter the window, in `HALF_OPEN` it just frees the probe slot. `NonCircuitableException` is an
**interface** — add it to `implements` of your own exception.

The marker is honoured only by the default `isFailure`. There are two ways to replace that default,
and the second wins over the first; either one takes over completely, so check the marker yourself
if you still want it respected.

### 1. Override `isFailure` on the spec interface

Cheapest when the rule has no dependencies:

```java
@CircuitBreakerSpec("resilient.circuitbreaker.order")
public interface OrderCircuitBreaker extends CircuitBreaker {

    @Override
    default boolean isFailure(Throwable throwable) {
        return !(throwable instanceof OrderNotFoundException);
    }
}
```

### 2. A `@Tag`-bound `CircuitBreakerPredicate` component

Use this when the rule needs injected collaborators. `CircuitBreakerPredicate` is a
`@FunctionalInterface` with a single method — **the 1.x `name()` + `test(Throwable)` pair is gone,
and so is the `failurePredicateName` config key.** Binding is by tag:

```java
@Tag(OrderCircuitBreaker.class)
@Component
public final class OrderFailurePredicate implements CircuitBreakerPredicate {

    @Override
    public boolean isCircuitBreakerFailure(Throwable throwable) {
        if (throwable instanceof HttpClientResponseException e) {
            return e.getCode() >= 500;   // 4xx are business errors, not outages
        }
        return true;
    }
}
```

```kotlin
@Tag(OrderCircuitBreaker::class)
@Component
class OrderFailurePredicate : CircuitBreakerPredicate {
    override fun isCircuitBreakerFailure(throwable: Throwable): Boolean =
        throwable !is HttpClientResponseException || throwable.code >= 500
}
```

The generated module injects the predicate as `@Nullable @Tag(OrderCircuitBreaker.class)`, so it is
optional. **An untagged `CircuitBreakerPredicate` component is silently ignored** — the tag is the
only wiring. When a tagged predicate exists it replaces `isFailure` entirely; the interface default
is not consulted.

---

## Imperative Use

There is no `CircuitBreakerManager` in 2.0. The spec interface itself is a graph component —
inject it and call the contract directly:

```java
@Component
public final class OrderReconciliation {

    private final OrderCircuitBreaker circuitBreaker;

    public OrderReconciliation(OrderCircuitBreaker circuitBreaker) {
        this.circuitBreaker = circuitBreaker;
    }

    public Order load(String id) {
        return circuitBreaker.accept(() -> httpClient.get(id));
    }
}
```

`CircuitBreaker` offers `accept(ThrowableRunnable)`, `accept(ThrowableCallable)`,
`accept(callable, fallback)`, plus the manual `tryAcquire()` / `acquire()` /
`releaseOnSuccess()` / `releaseOnError(t)` pair. `acquire()` + `release*` must be paired by hand.

`toString()` of the injected spec reports the implementation and live state, e.g.
`FixedWindowKoraCircuitBreaker{name='OrderCircuitBreaker', state=CLOSED, errors=3, total=41, windowSize=50}`
(`HALF_OPEN` shows probe counters, `OPEN` shows how long it has been open). Log it while debugging;
do not parse it.

---

## Telemetry

Off by default — logging, metrics **and** tracing (the resilient tracing configs override the
framework default of `true` back to `false`). Metric families, all tagged `resilient.name` = **the
config path** given to `@CircuitBreakerSpec`:

| Metric | Type | Extra tags |
|---|---|---|
| `resilient.circuitbreaker.state` | gauge, `0` CLOSED / `1` HALF_OPEN / `2` OPEN | — |
| `resilient.circuitbreaker.transition` | counter | `resilient.state` |
| `resilient.circuitbreaker.call.acquire` | counter | `resilient.state`, `resilient.status` (acquire status) |
| `resilient.circuitbreaker.call.result` | counter | `resilient.state`, `resilient.status` (call result) |

Enable globally under `resilient.telemetry.circuitBreaker`, or per breaker under
`<specPath>.telemetry`; the per-breaker value wins when set. See
[resilience-config-reference.md](resilience-config-reference.md#telemetry).

---

## Common Pitfalls

| Problem | Cause / fix |
|---|---|
| `String cannot be converted to Class<? extends CircuitBreaker>` | Un-migrated `@CircuitBreaker("name")`. |
| `must extend io.koraframework.resilient.circuitbreaker.CircuitBreaker` | Spec interface missing its base type. |
| `@CircuitBreakerSpec can only be applied to an interface` | Spec declared as a class/record. |
| `property 'countBased' is not configured` at startup | Window block missing; `STRIPED_APPROX` needs it too. |
| Breaker never opens | `minimumRequiredCalls` not reached, or the failure predicate excludes the exception. |
| Two callers never trip each other | Duplicate spec interfaces on one config path — share a single spec. |
| 404s open the breaker | Make the not-found exception implement `NonCircuitableException`, add a tagged `CircuitBreakerPredicate`, or override `isFailure`. |
| `NonCircuitableException` still trips the breaker | A tagged predicate or an overridden `isFailure` replaced the default check. |
| Predicate ignored | Missing `@Tag(<Spec>.class)`; `failurePredicateName` does nothing in 2.0. |
| Overloaded on recovery | Lower `permittedCallsInHalfOpenState`. |

---

## See Also

- [resilience-config-reference.md](resilience-config-reference.md) — full `resilient.*` key set
- [retry-reference.md](retry-reference.md) — retry inside the breaker
- [fallback-reference.md](fallback-reference.md) — degraded result when the breaker is open
