# Resilience Configuration Reference

**Artifact:** `io.koraframework:resilient-kora` · **Module:** `io.koraframework.resilient.ResilientModule`

## Contents

- [Module Setup](#module-setup)
- [How a Config Path Is Chosen](#how-a-config-path-is-chosen)
- [Full Example](#full-example)
- [YAML](#yaml)
- [Complete Key Reference](#complete-key-reference)
- [Telemetry](#telemetry)
- [Predicates](#predicates)
- [Combining Aspects](#combining-aspects)
- [Testing](#testing)
- [Migrating 1.x Configuration](#migrating-1x-configuration)

---

## Module Setup

```groovy
dependencies {
    koraBom platform("io.koraframework:kora-bom:$koraVersion")   // koraVersion=2.0.0.RC2
    annotationProcessor "io.koraframework:annotation-processors" // Kotlin: ksp "io.koraframework:symbol-processors"

    implementation "io.koraframework:resilient-kora"
    implementation "io.koraframework:config-hocon"               // or config-yaml
}
```

```java
@KoraApp
public interface Application extends
        HoconConfigModule,
        LogbackModule,
        ResilientModule { }
```

```kotlin
@KoraApp
interface Application : HoconConfigModule, LogbackModule, ResilientModule
```

`ResilientModule` aggregates `CircuitBreakerModule`, `RetryModule`, `TimeoutModule`,
`FallbackModule` and `RateLimiterModule`, and supplies the `ResilientConfig` read from
`resilient.telemetry`. Every generated spec module injects `ResilientConfig`, so **omitting
`ResilientModule` from the `@KoraApp` interface makes the graph fail to build.**

You never extend the generated `$<Spec>_Module` yourself; `@KoraApp` collects `@Module`-annotated
interfaces produced in the same compilation.

---

## How a Config Path Is Chosen

The path is whatever string you put in the spec annotation. **Nothing in the framework enforces a
`resilient.` prefix** — `@CircuitBreakerSpec("payment")` reading a top-level `payment { … }` block
is valid. The only path the framework owns is `resilient.telemetry`.

The convention used across `kora-examples` is
`resilient.<aspect>.<name>`, with `circuitbreaker` spelled as one lowercase word:

```
resilient.circuitbreaker.<name>
resilient.retry.<name>
resilient.timeout.<name>
resilient.ratelimiter.<name>
```

Follow it unless you have a reason not to; it keeps `resilient { … }` as the single place a reader
looks. Two rules hold regardless of the path you pick:

1. **One spec interface per path**, shared by every class that needs it. Two interfaces on the same
   path are two independent runtime instances with independent state.
2. **Sections do not inherit from each other.** `resilient.retry.payment` never merges with
   `resilient.retry.default`; unset keys take the *type's* defaults, and a `default` section no spec
   points at is dead config.

---

## Full Example

```hocon
resilient {

  circuitbreaker {
    payment {
      type = FIXED_WINDOW
      countBased.windowSize = 50
      minimumRequiredCalls = 25
      failureRateThreshold = 50
      waitDurationInOpenState = "25s"
      permittedCallsInHalfOpenState = 10
    }
    catalog {
      type = RING_BUFFER              # exact last-N window, closest to a 1.x sliding window
      countBased.windowSize = 100
      minimumRequiredCalls = 20
      failureRateThreshold = 40
      waitDurationInOpenState = "10s"
      permittedCallsInHalfOpenState = 5
      telemetry.metrics.enabled = true
    }
    hotpath {
      type = STRIPED_APPROX           # the default; approximate CLOSED statistics
      countBased {
        windowSize = 1000
        stripedApprox.stripes = 32
      }
      minimumRequiredCalls = 100
      failureRateThreshold = 60
      waitDurationInOpenState = "10s"
      permittedCallsInHalfOpenState = 10
    }
    slowdown {
      type = TIME_BASED               # needs timeBased, NOT countBased
      timeBased {
        windowDuration = "30s"
        sampleCount = 30
      }
      minimumRequiredCalls = 20
      failureRateThreshold = 50
      waitDurationInOpenState = "15s"
      permittedCallsInHalfOpenState = 5
    }
  }

  retry {
    payment {
      delay = "100ms"
      attempts = 3
      delayStep = "100ms"             # linear: 100ms, 200ms, 300ms
    }
    external {
      delay = "100ms"
      attempts = 5
      backoff { multiplier = 2.0, delayMax = "5s" }   # replaces delayStep
      jitter  { type = FULL, ratio = 0.5 }
      retryBudget { ratio = 0.1, tokensMax = 100 }
    }
  }

  timeout {
    fast     { duration = "100ms" }
    payment  { duration = "5s" }
    report   { duration = "30s" }
  }

  ratelimiter {
    notifications { limitForPeriod = 100, limitRefreshPeriod = "1s" }                   # TOKEN_BUCKET (default)
    exports       { limitForPeriod = 10, limitRefreshPeriod = "1m", type = FIXED_WINDOW }
  }

  telemetry {
    circuitBreaker.metrics.enabled = true
    retry.metrics.enabled = true
    timeout.metrics.enabled = true
    fallback.metrics.enabled = true
    rateLimiter.metrics.enabled = true
  }
}
```

Note the casing split: **aspect sections are lowercase** (`circuitbreaker`, `ratelimiter`) because
you chose those paths, while **`resilient.telemetry` sub-keys are camelCase**
(`circuitBreaker`, `rateLimiter`) because they are accessor names on the framework's
`ResilientConfig`. This is not a typo.

---

## YAML

```yaml
resilient:
  circuitbreaker:
    payment:
      type: FIXED_WINDOW
      countBased:
        windowSize: 50
      minimumRequiredCalls: 25
      failureRateThreshold: 50
      waitDurationInOpenState: "25s"
      permittedCallsInHalfOpenState: 10
  retry:
    payment:
      delay: "100ms"
      attempts: 3
      delayStep: "100ms"
  timeout:
    payment:
      duration: "5s"
  ratelimiter:
    notifications:
      limitForPeriod: 100
      limitRefreshPeriod: "1s"
      type: TOKEN_BUCKET
  telemetry:
    circuitBreaker:
      metrics:
        enabled: true
```

Requires `io.koraframework:config-yaml` and `YamlConfigModule` instead of the HOCON pair.

---

## Complete Key Reference

Derived from the config interfaces in `resilient-kora`. "required" means the accessor has no
default — the section must set it or the graph fails to build.

### `resilient.circuitbreaker.<name>` — `CircuitBreakerConfig`

| Key | Type | Default | Notes |
|---|---|---|---|
| `enabled` | boolean | `true` | `false` bypasses the breaker entirely |
| `type` | enum | `STRIPED_APPROX` | `FIXED_WINDOW`, `STRIPED_APPROX`, `RING_BUFFER`, `TIME_BASED` |
| `failureRateThreshold` | int | **required** | percent, 1..100 |
| `minimumRequiredCalls` | int | **required** | ≥ 1, and ≤ `countBased.windowSize` for count-based types |
| `waitDurationInOpenState` | Duration | **required** | must be non-negative |
| `permittedCallsInHalfOpenState` | int | **required** | 1..65535 |
| `countBased.windowSize` | int | **required** for count-based types | ≥ 1; ≤ 2^22 for `RING_BUFFER`; ≤ `stripes * 65535` for `STRIPED_APPROX` |
| `countBased.stripedApprox.stripes` | int | `16` | 1..64, `STRIPED_APPROX` only |
| `timeBased.windowDuration` | Duration | **required** for `TIME_BASED` | > 0 |
| `timeBased.sampleCount` | int | `16` | 1..1024 |
| `timeBased.counterStripes` | int | `16` | 1..64 |
| `timeBased.counterType` | enum | `ATOMIC` | `ATOMIC`, `LONG_ADDER` |
| `telemetry.*` | object | inherits `resilient.telemetry.circuitBreaker` | see [Telemetry](#telemetry) |

Exactly one of `countBased` / `timeBased` is required, selected by `type`. Omitting the one your
`type` needs is **not** a config error — it fails later, during graph initialisation, with
`IllegalArgumentException: CircuitBreaker '<SpecSimpleName>' property 'countBased' is not configured`,
because `KoraCircuitBreaker`'s constructor validates the config before choosing an implementation.

### `resilient.retry.<name>` — `RetryConfig`

| Key | Type | Default | Notes |
|---|---|---|---|
| `enabled` | boolean | `true` | `false` calls straight through |
| `delay` | Duration | **required** | base delay |
| `attempts` | int | **required** | number of **retries**, not total invocations |
| `delayStep` | Duration | `0` | linear increment; **ignored when `backoff` is set** |
| `backoff.type` | enum | `EXPONENTIAL` | only value |
| `backoff.multiplier` | double | `2.0` | |
| `backoff.delayMax` | Duration | none | optional cap |
| `jitter.type` | enum | `NONE` | `NONE`, `FULL` |
| `jitter.ratio` | double | `1.0` | fraction of the delay that may be shaved off |
| `retryBudget.enabled` | boolean | `true` | the block itself is optional; absent = no budget (with the default `RetryBudgetFactory`) |
| `retryBudget.ratio` | double | `0.1` | tokens deposited per success; one retry costs one token |
| `retryBudget.tokensMax` | int | `100` | |
| `retryBudget.tokensInitial` | int | `10` | ≤ `tokensMax` |
| `retryBudget.minTokensPerSecond` | double | `0.0` | time-based refill; ignored by the distributed budget |
| `telemetry.*` | object | inherits `resilient.telemetry.retry` | |

### `resilient.timeout.<name>` — `TimeoutConfig`

| Key | Type | Default | Notes |
|---|---|---|---|
| `enabled` | boolean | `true` | |
| `duration` | Duration | **required** | |
| `telemetry.*` | object | inherits `resilient.telemetry.timeout` | |

### `resilient.ratelimiter.<name>` — `RateLimiterConfig`

| Key | Type | Default | Notes |
|---|---|---|---|
| `enabled` | boolean | `true` | |
| `type` | enum | `TOKEN_BUCKET` | `TOKEN_BUCKET` (GCRA, continuous refill with a burst of `limitForPeriod`), `FIXED_WINDOW` (quota per window, up to 2x at a boundary) |
| `limitForPeriod` | int | **required** | permits per period; bucket size for `TOKEN_BUCKET` |
| `limitRefreshPeriod` | Duration | **required** | the period — refill horizon for `TOKEN_BUCKET`, window length for `FIXED_WINDOW` |
| `telemetry.*` | object | inherits `resilient.telemetry.rateLimiter` | |

A spec annotated `@RateLimiterDistributedSpec` reads a different config type,
`DistributedRateLimiterConfig`, whose algorithm key is `algorithm` (not `type`) and which requires
`keyPrefix`. See [distributed-reference.md](distributed-reference.md#configuration).

### Fallback

**No per-fallback configuration exists.** `@Fallback` has no spec, no name and no config section.
Only `resilient.telemetry.fallback` applies.

### Keys that no longer exist

| Removed key | Replacement |
|---|---|
| `slidingWindowSize` | `countBased.windowSize` (+ pick a `type`) |
| `failurePredicateName` | a `@Component` predicate bound with `@Tag(<Spec>.class)` |
| `resilient.fallback.<name>` | nothing — fallbacks are not configurable |
| `minimumNumberOfCalls` | never existed in Kora; the key is `minimumRequiredCalls` |

---

## Telemetry

**All resilient telemetry is off by default** — logging and metrics inherit the framework default of
`false`, and the resilient tracing configs explicitly override the framework's `true` back to
`false`. An example that claims to show resilience metrics must enable them.

Two levels, with the per-spec value winning when it is set:

```hocon
resilient.telemetry {                 # global default per aspect
  circuitBreaker { logging.enabled = true, metrics.enabled = true, tracing.enabled = true }
  retry          { logging.enabled = true, metrics.enabled = true }
  timeout        { metrics.enabled = true }
  fallback       { metrics.enabled = true }
  rateLimiter    { metrics.enabled = true }
}

resilient.circuitbreaker.payment.telemetry {   # per-spec override
  logging.enabled = false
  metrics { slo = ["10ms", "100ms", "1s"], tags { team = "payments" } }
}
```

Per level: `logging.enabled`, `metrics.enabled`, `metrics.slo`, `metrics.tags`,
`tracing.enabled`, `tracing.attributes`. Anything left unset at the spec level falls through to the
global aspect level.

### Metric families

Every metric carries a `resilient.name` tag (all resilience tags are `resilient.`-prefixed since
2.0.0.RC2, #972; RC1 used bare `name` / `state` / `status` / `reason` / `type`). For the four spec-based aspects that tag is **the config path**
you gave the spec annotation; for `@Fallback` it is `<fully.qualified.Class>.<method>`.
Exception messages, by contrast, name the spec interface's **simple name** — the two identifiers
differ on purpose.

| Metric | Type | Extra tags |
|---|---|---|
| `resilient.circuitbreaker.state` | gauge — `0` CLOSED, `1` HALF_OPEN, `2` OPEN | — |
| `resilient.circuitbreaker.transition` | counter | `resilient.state` |
| `resilient.circuitbreaker.call.acquire` | counter | `resilient.state`, `resilient.status` (acquire status) |
| `resilient.circuitbreaker.call.result` | counter | `resilient.state`, `resilient.status` (call result) |
| `resilient.retry.attempts` | counter | — |
| `resilient.retry.exhausted` | counter | `resilient.reason` = `EXHAUSTED_ATTEMPTS` / `EXHAUSTED_BUDGET` |
| `resilient.timeout.exhausted` | counter | — |
| `resilient.ratelimiter.acquire` | counter | `resilient.status` = `acquired` / `rejected` |
| `resilient.fallback.attempts` | counter | `resilient.type` = `executed` |

Metrics need `io.koraframework:micrometer-module` in the graph; tracing needs the OpenTelemetry
modules. Without them the factories degrade to no-ops even with `enabled = true`.

---

## Predicates

Only the circuit breaker and retry have predicates in 2.0. `@Timeout`, `@RateLimited` and
`@Fallback` have none — `FallbackPredicate` was removed, and `@Fallback` filters by the
`@Fallback.Reason` parameter type instead.

| Contract | Method | Bound by |
|---|---|---|
| `io.koraframework.resilient.circuitbreaker.CircuitBreakerPredicate` | `boolean isCircuitBreakerFailure(Throwable)` | `@Tag(<CircuitBreakerSpec>.class)` on a `@Component` |
| `io.koraframework.resilient.retry.RetryPredicate` | `boolean isRetryFailure(Throwable)` | `@Tag(<RetrySpec>.class)` on a `@Component` |

Both are `@FunctionalInterface`s: the 1.x `name()` + `test(Throwable)` shape is gone, and so is the
`failurePredicateName` config key that used to select one.

```java
@Tag(PaymentCircuitBreaker.class)
@Component
public final class PaymentFailurePredicate implements CircuitBreakerPredicate {

    @Override
    public boolean isCircuitBreakerFailure(Throwable throwable) {
        return !(throwable instanceof HttpClientResponseException e) || e.getCode() >= 500;
    }
}
```

The generated spec module injects the predicate as `@Nullable`, so it is optional — and an
**untagged** predicate component is simply never found. When present, a tagged predicate replaces
the `isFailure` default the spec interface may define.

Without either, the defaults exclude marker interfaces: an exception implementing
`io.koraframework.resilient.retry.NonRetryableException` is never retried, and one implementing
`io.koraframework.resilient.circuitbreaker.NonCircuitableException` is not counted by the breaker.
A custom predicate or `isFailure` override drops that check unless it repeats it.

Retry has one more tagged extension point: a `RetryBudgetFactory` tagged `@Tag(<RetrySpec>.class)`
replaces the budget of that retry; an untagged one replaces the default for all retries. See
[retry-reference.md](retry-reference.md#where-the-budget-comes-from).

---

## Combining Aspects

Declaration order is application order: **first-listed is outermost, last-listed is innermost.**

```java
@Fallback(method = "chargeFallback(request)")   // 4. outermost
@CircuitBreakable(PaymentCircuitBreaker.class)  // 3.
@Retryable(PaymentRetry.class)                  // 2.
@Timeout(PaymentTimeouter.class)                // 1. innermost — one attempt
public PaymentResult charge(PaymentRequest request) { … }
```

| Goal | Order |
|---|---|
| Timeout each attempt | `@Retryable` above `@Timeout` |
| One budget for the whole retry chain | `@Timeout` above `@Retryable` |
| Circuit breaker counts one failure per logical call | `@CircuitBreakable` above `@Retryable` |
| Circuit breaker counts every attempt | `@Retryable` above `@CircuitBreakable` |
| Degrade instead of failing | `@Fallback` first, above everything |

Putting `@Fallback` last makes it innermost, so it swallows the exception before the circuit breaker
records anything and the breaker never opens.

---

## Testing

`@KoraAppTest` builds the real graph, which means the resilience config must be valid or the test
fails at graph init rather than in an assertion. HOCON embedded in a test source counts as
configuration and is missed by every scanner that only reads `.conf`/`.yaml` files — including the
window block:

```java
@KoraAppTest(Application.class)
class PaymentServiceTest implements KoraAppTestConfigModifier {

    @Override
    public KoraConfigModification config() {
        return KoraConfigModification.ofString("""
            resilient {
              circuitbreaker.payment {
                type = FIXED_WINDOW
                countBased.windowSize = 2
                minimumRequiredCalls = 2
                failureRateThreshold = 100
                waitDurationInOpenState = "200ms"
                permittedCallsInHalfOpenState = 1
              }
              retry.payment   { delay = "20ms", attempts = 2 }
              timeout.payment { duration = "100ms" }
            }
            """);
    }

    @TestComponent
    private PaymentService paymentService;

    @Test
    void breakerOpensAfterTwoFailures() { … }
}
```

Tune the numbers down hard — `windowSize = 1..2`, `minimumRequiredCalls = 1..2`,
`failureRateThreshold = 100`, sub-second `waitDurationInOpenState` — so a test trips the breaker in
two or three calls instead of a hundred. Assert on invocation counts against a fake collaborator
rather than on wall-clock timing.

---

## Migrating 1.x Configuration

1. Collect every string name from `@CircuitBreaker("…")`, `@Retry("…")`, `@Timeout("…")`,
   `@Fallback(value = "…")`. In 1.x the name was the last segment of the config path.
2. Note which names are used by **more than one class** — each gets exactly one shared spec
   interface, not one per class.
3. For each name, declare the spec interface and point it at the existing section path.
4. Circuit-breaker sections: replace `slidingWindowSize = N` with `type = …` plus
   `countBased.windowSize = N`. `RING_BUFFER` preserves 1.x semantics; `FIXED_WINDOW` is what the
   migrated examples use; the default `STRIPED_APPROX` is deliberately approximate.
5. Fill every named section completely — required circuit-breaker keys are no longer inherited from
   `default`. A section that used to set one key now needs all of them.
6. Delete `failurePredicateName` keys and rewrite each predicate as a `@Tag`-bound `@Component`.
7. Delete `resilient.fallback.*` sections; only `resilient.telemetry.fallback` survives.
8. Delete a `default` section once no spec points at it.
9. Re-check embedded HOCON in tests, not just resource files.

An unrecognised HOCON key is ignored silently, so a leftover `slidingWindowSize` produces no warning
at all — the breaker simply fails on the missing `countBased` block instead.

---

## See Also

- [circuit-breaker-reference.md](circuit-breaker-reference.md)
- [retry-reference.md](retry-reference.md)
- [timeout-reference.md](timeout-reference.md)
- [rate-limiter-reference.md](rate-limiter-reference.md)
- [fallback-reference.md](fallback-reference.md)
- [distributed-reference.md](distributed-reference.md)
