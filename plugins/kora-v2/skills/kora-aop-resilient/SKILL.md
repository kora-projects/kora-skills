---
name: kora-aop-resilient
description: "Kora 2.x resilience aspects (io.koraframework:resilient-kora) — @CircuitBreakable, @Retryable, @Timeout, @RateLimited, @Fallback. In 2.0 every aspect takes a typed spec interface (@CircuitBreakerSpec/@RetrySpec/@TimeoutSpec/@RateLimiterSpec on an interface extending CircuitBreaker/Retry/Timeouter/RateLimiter) instead of a string name. Use when adding fault tolerance to outbound HTTP/gRPC/DB calls, wiring resilient.* config (countBased.windowSize, failureRateThreshold, attempts, delay, duration, limitForPeriod, TOKEN_BUCKET/FIXED_WINDOW), binding a CircuitBreakerPredicate/RetryPredicate/RetryBudgetFactory by @Tag, excluding exceptions via NonRetryableException/NonCircuitableException, Redis-shared limits (@RateLimiterDistributedSpec, DistributedRetryBudgetFactory), or porting Kora 1.x @CircuitBreaker(\"name\")/@Retry(\"name\") string annotations."
license: Apache-2.0
metadata:
  kora-version: "2.x"
---

# Kora AOP Resilient

> **Kora sub-skill — obey the [kora-v2 meta rules](../../SKILL.md) on every task:** **R0** ground the workspace on Kora 2.0 refs before starting (framework source at tag `2.0.0.RC2` + `kora-examples` at `migration/2.0` + Kora 2.0 docs at koraframework.io/v2, which trail the source; 1.x `kora-docs` pages are never an authority) · **R1** read this sub-skill before writing code · **R2** Kora 2.0 APIs only — no Spring/Micronaut/Quarkus, no Kora 1.x APIs, no invented annotations or config keys · **R3** journal any incorrect Kora usage. Add comments/Javadoc only if asked.

| | |
|---|---|
| **Artifact** | `io.koraframework:resilient-kora` (BOM `io.koraframework:kora-bom`, `koraVersion=2.0.0.RC2`) |
| **Processor** | Java `annotationProcessor "io.koraframework:annotation-processors"` · Kotlin `ksp "io.koraframework:symbol-processors"` |
| **Graph module** | `io.koraframework.resilient.ResilientModule` |
| **Generated** | `$<Class>__AopProxy` (the aspect) · `$<Spec>_Impl` + `$<Spec>_Module` (the spec) |

## The one thing that changed in 2.0

**A resilience annotation no longer takes a string name. It takes the `Class` of a spec interface,
and the spec interface carries the config path.**

```java
// Kora 1.x — does not compile in 2.0
@CircuitBreaker("payment")
@Retry("payment")
@Timeout("payment")
public PaymentResult charge(PaymentRequest request) { … }
```

```java
// Kora 2.0
@CircuitBreakable(PaymentCircuitBreaker.class)
@Retryable(PaymentRetry.class)
@Timeout(PaymentTimeouter.class)
public PaymentResult charge(PaymentRequest request) { … }
```

```java
@CircuitBreakerSpec("resilient.circuitbreaker.payment")
public interface PaymentCircuitBreaker extends CircuitBreaker {}

@RetrySpec("resilient.retry.payment")
public interface PaymentRetry extends Retry {}

@TimeoutSpec("resilient.timeout.payment")
public interface PaymentTimeouter extends Timeouter {}
```

**One spec interface per logical configuration name, shared across every class that uses it —
never one per method.** Two spec interfaces pointing at the same config path are two independent
runtime instances with independent state; two circuit breakers that never see each other's failures.

Leaving the string form in place is a hard failure, not a warning:

- Java — `error: incompatible types: String cannot be converted to Class<? extends Timeouter>`
- Kotlin — the KSP processor crashes with
  `java.lang.ClassCastException: class java.lang.String cannot be cast to class com.google.devtools.ksp.symbol.KSType`,
  with no line number pointing at your code.

---

## Quick Start

### 1. Dependencies

```groovy
dependencies {
    koraBom platform("io.koraframework:kora-bom:$koraVersion")   // koraVersion=2.0.0.RC2
    annotationProcessor "io.koraframework:annotation-processors" // mandatory: generates the AOP proxies + spec modules

    implementation "io.koraframework:resilient-kora"
}
```

Kotlin uses `ksp "io.koraframework:symbol-processors"` instead of `annotationProcessor`.
Never pin a version on an individual Kora artifact — the BOM supplies it.

### 2. Extend `ResilientModule`

```java
@KoraApp
public interface Application extends
        HoconConfigModule,
        LogbackModule,
        ResilientModule { }
```

`ResilientModule` is required. It supplies the telemetry factories and the `ResilientConfig`
that every generated spec module injects. **You never extend the generated `$<Spec>_Module`
yourself** — `@KoraApp` collects `@Module`-annotated interfaces produced in the same compilation.

### 3. Declare the spec interfaces

One interface per config path. They are plain interfaces; the processor generates the
implementation and registers it in the graph.

```java
@CircuitBreakerSpec("resilient.circuitbreaker.payment")
public interface PaymentCircuitBreaker extends CircuitBreaker {}
```

### 4. Annotate the methods

The class must be **non-final** (Java) / **`open`** (Kotlin), and in Kotlin the method must be
`open` too. Otherwise compilation fails — see [Troubleshooting](#troubleshooting).

```java
@Component
public class PaymentService {

    @Fallback(method = "chargeFallback(request)")
    @CircuitBreakable(PaymentCircuitBreaker.class)
    @Retryable(PaymentRetry.class)
    @Timeout(PaymentTimeouter.class)
    public PaymentResult charge(PaymentRequest request) {
        return paymentGateway.charge(request);
    }

    protected PaymentResult chargeFallback(PaymentRequest request) {
        return PaymentResult.pendingManualReview();
    }
}
```

### 5. Configure

```hocon
resilient {
  circuitbreaker.payment {
    type = FIXED_WINDOW              # window implementation
    countBased.windowSize = 50       # was slidingWindowSize in 1.x
    minimumRequiredCalls = 25
    failureRateThreshold = 50
    waitDurationInOpenState = "25s"
    permittedCallsInHalfOpenState = 10
  }
  retry.payment   { delay = "100ms", attempts = 3, delayStep = "100ms" }
  timeout.payment { duration = "5s" }
  ratelimiter.notifications { limitForPeriod = 100, limitRefreshPeriod = "1s" }   # type = TOKEN_BUCKET by default
}
```

Circuit-breaker sections have **no defaults** for `failureRateThreshold`,
`minimumRequiredCalls`, `permittedCallsInHalfOpenState` and `waitDurationInOpenState`, and the
window block is mandatory. See
[resilience-config-reference.md](references/resilience-config-reference.md).

---

## The five aspects

| Annotation | Package | Spec annotation | Spec base type | Throws on failure |
|---|---|---|---|---|
| `@CircuitBreakable(X.class)` | `io.koraframework.resilient.circuitbreaker.annotation` | `@CircuitBreakerSpec(path)` | `…circuitbreaker.CircuitBreaker` | `CallNotPermittedException` |
| `@Retryable(X.class)` | `io.koraframework.resilient.retry.annotation` | `@RetrySpec(path)` | `…retry.Retry` | `RetryExhaustedException` |
| `@Timeout(X.class)` | `io.koraframework.resilient.timeout.annotation` | `@TimeoutSpec(path)` | `…timeout.Timeouter` | `TimeoutExhaustedException` |
| `@RateLimited(X.class)` | `io.koraframework.resilient.ratelimiter.annotation` | `@RateLimiterSpec(path)` | `…ratelimiter.RateLimiter` | `RateLimitExceededException` |
| `@Fallback(method = "…")` | `io.koraframework.resilient.fallback.annotation` | — (no spec, no config) | — | — |

All five target **methods only**. All exceptions extend
`io.koraframework.resilient.exception.ResilientException`, which carries `name()`.

`@Timeout` kept its 1.x name but changed its attribute type from `String` to
`Class<? extends Timeouter>`. `@Fallback` **lost its `value` attribute** — `method` is the only one
left. `@RateLimited` is new in 2.0.

`@RateLimited` also accepts a spec annotated `@RateLimiterDistributedSpec` (artifact
`resilient-kora-distributed-redis-lettuce`): same `RateLimiter` contract, state in Redis, one quota
across all instances — see [distributed-reference.md](references/distributed-reference.md).

### Rate limiter algorithm

The local limiter defaults to `type = TOKEN_BUCKET` (GCRA: continuous refill at
`limitForPeriod / limitRefreshPeriod`, burst of up to `limitForPeriod`). `type = FIXED_WINDOW` is a
quota per window and lets up to `2 * limitForPeriod` through across a window boundary. Both reject
immediately with `RateLimitExceededException`; neither blocks.

### Exceptions that do not count

Implement a marker interface on your own exception instead of writing a predicate:

| Marker interface | Effect under the default predicate |
|---|---|
| `io.koraframework.resilient.retry.NonRetryableException` | never retried — propagates on the first throw, no `RetryExhaustedException` |
| `io.koraframework.resilient.circuitbreaker.NonCircuitableException` | propagates, but is counted as neither failure nor success by the breaker |

```java
public final class ValidationException extends RuntimeException
        implements NonRetryableException, NonCircuitableException { … }
```

A tagged `RetryPredicate` / `CircuitBreakerPredicate` or an overridden `isFailure` on the spec
replaces the default and with it the marker check.

### Retry budget

A `retryBudget` block on a retry section caps retries to a share of successful calls. The budget
comes from a `RetryBudgetFactory`: one tagged `@Tag(<RetrySpec>.class)` wins for that retry, else the
untagged one (`DefaultRetryBudgetFactory`, or your own replacing it globally).
`DistributedRetryBudgetFactory` shares the budget across instances through Redis. See
[retry-reference.md](references/retry-reference.md#retry-budget).

---

## Combined stack

Aspect nesting is decided by annotation declaration order: **the first-listed annotation is the
outermost wrapper, the last-listed is innermost** and calls the real method body.

```java
@Fallback(method = "chargeFallback(request)")   // 4. outermost — degraded result
@CircuitBreakable(PaymentCircuitBreaker.class)  // 3. short-circuits before any retry runs
@Retryable(PaymentRetry.class)                  // 2. repeats the timed call
@Timeout(PaymentTimeouter.class)                // 1. innermost — bounds ONE attempt
public PaymentResult charge(PaymentRequest request) { … }
```

Move `@Timeout` above `@Retryable` and it becomes a budget for the whole retry chain instead of a
per-attempt bound. Both are valid; pick deliberately.

---

## Supported return types

`@CircuitBreakable`, `@Retryable`, `@Timeout` and `@Fallback` reject reactive types with
`… cannot be applied to '<Class>#<method>()' because return type '…' is not supported by this aspect.`
Reactor `Mono`/`Flux` were removed as Kora contracts in 2.0 and no aspect accepts them.

| Return type | Java | Kotlin |
|---|---|---|
| `T`, `T?`/`Optional<T>`, `void`/`Unit` | yes | yes |
| `CompletionStage<T>` / `CompletableFuture<T>` | yes — except `@RateLimited` | **no** — rejected by every aspect |
| `suspend fun` | n/a | yes, all five |
| `Flow<T>` | n/a | yes, all five |
| `Future<T>` (non-`CompletionStage`) | no | no |
| `Mono<T>` / `Flux<T>` | no | no |

---

## Migrating from Kora 1.x

| Kora 1.x | Kora 2.0 |
|---|---|
| `@CircuitBreaker("n")` | `@CircuitBreakable(X.class)` + `@CircuitBreakerSpec("resilient.circuitbreaker.n")` |
| `@Retry("n")` | `@Retryable(X.class)` + `@RetrySpec("resilient.retry.n")` |
| `@Timeout("n")` | `@Timeout(X.class)` + `@TimeoutSpec("resilient.timeout.n")` |
| `@Fallback(value = "n", method = "m()")` | `@Fallback(method = "m()")` — `value` removed |
| unnamed annotation falling back to the `default` section | explicit spec pointing at `…default`; **you declare that interface yourself** |
| `slidingWindowSize = 50` | `type = FIXED_WINDOW` + `countBased.windowSize = 50` |
| `failurePredicateName = "X"` config key | key removed — bind the predicate with `@Tag(<Spec>.class)` on a `@Component` |
| `CircuitBreakerPredicate.name()` + `test(t)` | `isCircuitBreakerFailure(t)` (single method) |
| `RetryPredicate.name()` + `test(t)` | `isRetryFailure(t)` (single method) |
| `FallbackPredicate` | **removed** — use a `@Fallback.Reason` parameter to filter by exception type |
| `CircuitBreakerManager` / `RetryManager` / `TimeoutManager` / `FallbackManager` | **removed** — inject the spec interface directly; it is a graph component |
| `ru.tinkoff.kora.resilient.*` | `io.koraframework.resilient.*` |

There is **no `DefaultCircuitBreaker` / `DefaultRetry` / `DefaultTimeouter` type in the
framework.** Those names appear in `kora-examples` as *application-declared* interfaces pointing at
`resilient.<aspect>.default`. If your 1.x code relied on the implicit `default` section, declare
your own equivalent — the framework will not supply one.

**Named sections no longer inherit `default`.** In 1.x `resilient.circuitbreaker.my_cb` supplemented
`resilient.circuitbreaker.default`. In 2.0 a spec resolves exactly one path and nothing else; unset
keys fall back to the *type's* defaults, and a `default` section no spec points at is dead config.
A partially filled named section that used to work will now either take type defaults or fail
outright on a required key.

---

## References

| Reference | Description |
|---|---|
| [circuit-breaker-reference.md](references/circuit-breaker-reference.md) | `@CircuitBreakable`, the four window implementations, state machine, `CircuitBreakerPredicate` via `@Tag`, `NonCircuitableException` |
| [retry-reference.md](references/retry-reference.md) | `@Retryable`, linear vs exponential backoff, jitter, `RetryBudget` / `RetryBudgetFactory`, `RetryPredicate`, `NonRetryableException` |
| [timeout-reference.md](references/timeout-reference.md) | `@Timeout`, virtual-thread execution and interruption, per-attempt vs overall |
| [rate-limiter-reference.md](references/rate-limiter-reference.md) | `@RateLimited` — new in 2.0; `TOKEN_BUCKET` (default) vs `FIXED_WINDOW` |
| [distributed-reference.md](references/distributed-reference.md) | `@RateLimiterDistributedSpec`, `DistributedRetryBudgetFactory`, `LettuceDistributedResilientModule`, Redis keys and failure modes |
| [fallback-reference.md](references/fallback-reference.md) | `@Fallback`, method-reference syntax, `@Fallback.Reason` |
| [resilience-config-reference.md](references/resilience-config-reference.md) | Complete `resilient.*` key set, telemetry, imperative use, testing |

## Assets

| Template | Description |
|---|---|
| `ResilientSpecs.{java,kt}.template` | The spec interfaces — **start here**, everything else references them |
| `ResilientService.{java,kt}.template` | Full stack: `@Fallback` + `@CircuitBreakable` + `@Retryable` + `@Timeout` |
| `CircuitBreakerService.{java,kt}.template` | `@CircuitBreakable` + a tagged `CircuitBreakerPredicate` |
| `RetryService.{java,kt}.template` | `@Retryable` + a tagged `RetryPredicate` |
| `TimeoutService.{java,kt}.template` | `@Timeout`, per-attempt and overall |
| `RateLimiterService.{java,kt}.template` | `@RateLimited`, `TOKEN_BUCKET` / `FIXED_WINDOW` config |
| `RetryBudgetService.{java,kt}.template` | `retryBudget` block, a tagged `RetryBudgetFactory`, a `NonRetryableException` |
| `DistributedResilience.{java,kt}.template` | `@RateLimiterDistributedSpec` + `LettuceDistributedResilientModule` + tagged `DistributedRetryBudgetFactory` |
| `FallbackService.{java,kt}.template` | `@Fallback` with and without `@Fallback.Reason` |

---

## Common Pitfalls

| Problem | Cause / fix |
|---|---|
| `String cannot be converted to Class<? extends Timeouter>` | Un-migrated 1.x string annotation. Declare a spec interface and pass its class. |
| KSP `ClassCastException: String cannot be cast to KSType` | Same cause, Kotlin side. The stack trace names the Kora aspect, not your file — grep for `@Retryable("`, `@CircuitBreakable("`, `@Timeout("`. |
| `CircuitBreaker 'X' property 'countBased' is not configured` at startup | The window block is missing. Add `countBased.windowSize` (or `timeBased` for `type = TIME_BASED`). |
| `Config expected value, but got null at path: 'ROOT.resilient.circuitbreaker.x.failureRateThreshold'` | Circuit-breaker keys are required and named sections do not inherit `default`. Fill the section. |
| `@CircuitBreakerSpec annotated interface 'X' must extend io.koraframework.resilient.circuitbreaker.CircuitBreaker` | The spec interface is missing its base type. |
| `@CircuitBreakerSpec can only be applied to an interface` | A spec must be an interface, not a class or record. |
| `AOP aspect cannot be applied to class 'X' because the class is final` / `… is not open` | Drop `final` (Java) or add `open` to the class **and** the method (Kotlin). |
| Two circuit breakers never open | Two spec interfaces on the same config path = two independent instances. Share one spec. |
| Predicate never runs | The `@Component` needs `@Tag(<Spec>.class)`; an untagged `CircuitBreakerPredicate` is not picked up. `failurePredicateName` no longer exists. |
| No `resilient.*` metrics or logs | Resilient telemetry is **off by default** (logging, metrics *and* tracing). Enable it explicitly. |
| Limiter lets `2 * limitForPeriod` through at a boundary | `type = FIXED_WINDOW`; the default `TOKEN_BUCKET` does not. |
| Rate limit or retry budget is per instance | Local specs are per JVM. Use `@RateLimiterDistributedSpec` / `DistributedRetryBudgetFactory`. |
| Business error retried or trips the breaker | Implement `NonRetryableException` / `NonCircuitableException` on it. |

---

## Troubleshooting

### Verify the proxies and spec implementations were generated

```bash
# Java lands in build/generated/sources/annotationProcessor, Kotlin in build/generated/ksp
find build/generated \( -name '*__AopProxy.*' -o -name '*_Impl.*' -o -name '*_Module.*' \)
```

Expect `$PaymentService__AopProxy`, plus `$PaymentCircuitBreaker_Impl` and
`$PaymentCircuitBreaker_Module` for each spec. If the spec files are missing, the spec annotation
or the processor dependency is missing. If the proxy is missing, the class is `final`/not `open`
(that is a compile error in 2.0 — read the build output rather than guessing).

After renaming packages during a migration, stale generated sources produce phantom
`ru.tinkoff.kora` errors. Fix with `./gradlew clean build --no-build-cache`; never edit
`build/generated`.

### Enable resilience logging

Logging is disabled by default at every level, so the logger level alone is not enough:

```hocon
resilient.telemetry {
  circuitBreaker.logging.enabled = true
  retry.logging.enabled = true
  timeout.logging.enabled = true
  fallback.logging.enabled = true
  rateLimiter.logging.enabled = true
}

logging.levels."io.koraframework.resilient" = "DEBUG"
```

### Inspect live state

Circuit breakers, retries, retry states, retry budgets and rate limiters implement `toString()` with
their current state (breaker state and counters, available permits, available budget tokens). Inject
the spec interface and log it; the format is for humans, not for parsing.

---

## See Also

- [kora-http-client](../kora-http-client/SKILL.md) — the usual thing being made resilient
- [kora-telemetry-metrics](../kora-telemetry-metrics/SKILL.md) — `resilient.*` metric families
- [kora-di-compile](../kora-di-compile/SKILL.md) — `@Tag`, `@Component`, `@Module` semantics
- [kora-config-hocon](../kora-config-hocon/SKILL.md) — how `resilient.*` sections are mapped
