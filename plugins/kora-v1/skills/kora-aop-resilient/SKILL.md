---
name: kora-aop-resilient
description: "Kora resilience aspects — @CircuitBreaker, @Retry, @Timeout, @Fallback from the resilient-kora module (ResilientModule). Covers circuit breaker states (CLOSED/OPEN/HALF_OPEN), retry backoff, execution timeouts, fallback methods, custom CircuitBreakerPredicate/RetryPredicate/FallbackPredicate, the imperative *Manager API, and stacking aspects on one method. Use when adding fault tolerance to outbound HTTP/gRPC calls, database or external-service operations, debugging \"circuit never opens\", TimeoutExhaustedException, or fallback not firing, or wiring resilient.* config keys (failureRateThreshold, minimumRequiredCalls, attempts, delayStep, waitDurationInOpenState)."
---

# Kora AOP Resilient

Compile-time AOP annotations for fault tolerance: `@Retry`, `@CircuitBreaker`, `@Timeout`, `@Fallback`. They are generated into `$<Class>__AopProxy` classes at build time — no reflection. Provided by the `resilient-kora` module via `ResilientModule`.

**Quick Navigation:**
- [Quick Start](#quick-start) — get running in four steps
- [Combined Pattern](#combined-resilience-pattern) — stack all annotations on one method
- [References](#references) — per-aspect deep dives

---

## Quick Start

### 1. Add the dependency and annotation processor

```groovy
dependencies {
    // All Kora artifacts inherit their version from the kora-parent BOM — never pin them individually.
    annotationProcessor "ru.tinkoff.kora:annotation-processors" // mandatory: generates the AOP proxies

    implementation "ru.tinkoff.kora:resilient-kora"
}
```

> Kotlin uses `ksp "ru.tinkoff.kora:symbol-processors"` instead of `annotationProcessor`.

### 2. Enable ResilientModule

```java
@KoraApp
public interface Application extends
        HoconConfigModule,
        LogbackModule,
        ResilientModule { } // enables the resilience aspects
```

### 3. Apply Resilience Annotations

Each annotation lives in its own package:

| Annotation | Import |
|------------|--------|
| `@CircuitBreaker` | `ru.tinkoff.kora.resilient.circuitbreaker.annotation.CircuitBreaker` |
| `@Retry` | `ru.tinkoff.kora.resilient.retry.annotation.Retry` |
| `@Timeout` | `ru.tinkoff.kora.resilient.timeout.annotation.Timeout` |
| `@Fallback` | `ru.tinkoff.kora.resilient.fallback.annotation.Fallback` |

```java
@Component
public class PaymentService { // MUST be non-final (Java) / open (Kotlin) for aspects to apply

    @Fallback(value = "payment.process", method = "processFallback(request)")
    @CircuitBreaker("payment.process")
    @Retry("payment.process")
    @Timeout("payment.process")
    public PaymentResult process(PaymentRequest request) {
        return paymentGateway.charge(request);
    }

    protected PaymentResult processFallback(PaymentRequest request) {
        return PaymentResult.pendingManualReview();
    }
}
```

The annotation value is a **config key**, not a shared identifier — `@Retry("payment.process")` reads `resilient.retry."payment.process"`. Different aspects on the same method may use independent keys.

### 4. Configure Resilience

```hocon
resilient {
  timeout {
    default { duration = "1s" }
    "payment.process" { duration = "5s" }
  }
  retry {
    default {
      delay = "100ms"
      attempts = 3
      delayStep = "100ms"
    }
  }
  circuitbreaker {
    default {
      slidingWindowSize = 100
      minimumRequiredCalls = 10
      failureRateThreshold = 50
      waitDurationInOpenState = "30s"
      permittedCallsInHalfOpenState = 5
    }
  }
  fallback {
    default { enabled = true }
  }
}
```

> **Important:** Use `minimumRequiredCalls` (NOT `minimumNumberOfCalls`) — Kora-specific key.

---

## Combined Resilience Pattern

Recommended order (outer → inner):

```java
@Component
public class PaymentClient {
    
    // Order (outer → inner):
    // 1. @Fallback — degraded response if everything fails
    // 2. @CircuitBreaker — fail fast if repeatedly failing
    // 3. @Retry — retry transient failures
    // 4. @Timeout — bound each attempt
    
    @Fallback(value = "payment.charge", method = "chargeFallback(request)")
    @CircuitBreaker("payment.charge")
    @Retry("payment.charge")
    @Timeout("payment.charge")
    public PaymentResult charge(PaymentRequest request) {
        return httpClient.post("/payments", request);
    }
    
    protected PaymentResult chargeFallback(PaymentRequest request) {
        return PaymentResult.pendingManualReview();
    }
}
```

**Execution flow:**
1. `@Timeout` bounds the actual HTTP call
2. `@Retry` repeats on transient failures (up to N attempts)
3. `@CircuitBreaker` opens if failures exceed threshold
4. `@Fallback` returns degraded response if circuit is open or all retries fail

---

## References

Detailed guides with configuration options, patterns, and examples:

| Reference | Description |
|-----------|-------------|
| [retry-reference.md](references/retry-reference.md) | `@Retry`, predicates, backoff patterns, wait time calculation |
| [circuit-breaker-reference.md](references/circuit-breaker-reference.md) | `@CircuitBreaker`, state machine (CLOSED/OPEN/HALF_OPEN), custom predicates |
| [timeout-reference.md](references/timeout-reference.md) | `@Timeout` patterns, per-attempt vs overall timeout, thread interruption |
| [fallback-reference.md](references/fallback-reference.md) | `@Fallback` methods, signature rules, fallback patterns |
| [resilience-config-reference.md](references/resilience-config-reference.md) | Full configuration reference, custom predicates, high-throughput tuning |

---

## Supported Signatures

### Java

Class must be **non-final** for AOP to work.

| Return Type | Example |
|-------------|---------|
| `T` (or `Void`) | `User getUser(String id)` |
| `Optional<T>` | `Optional<User> getUser(String id)` |
| `Mono<T>` / `Flux<T>` | Project Reactor types (require `io.projectreactor:reactor-core`) |

### Kotlin

Class and methods must be **open** for AOP to work.

| Return Type | Example |
|-------------|---------|
| `T` / `T?` / `Unit` | `fun getUser(id: String): User?` |
| `suspend fun ... : T` | `suspend fun getUserAsync(id: String): User` (requires `kotlinx-coroutines-core`) |
| `Flow<T>` | `fun getAllUsers(): Flow<User>` (requires `kotlinx-coroutines-core`) |

---

## Common Pitfalls

| Problem | Solution |
|---------|----------|
| **Annotations don't trigger** | Java: class must be non-`final`. Kotlin: class and methods must be `open` |
| **Circuit breaker never opens** | Check `minimumRequiredCalls` — need enough calls to evaluate |
| **Circuit breaker reacts to 404** | Implement `CircuitBreakerPredicate` to exclude business errors |
| **Fallback not called** | Check method signature: return type compatible, parameters match subset |
| **Retry makes latency worse** | Estimate worst-case: `attempts × (delay + delayStep)`. Reduce for latency-sensitive paths |
| **Config not applied** | Config key must match annotation value: `@Retry("custom")` → `resilient.retry."custom"` |

---

## Troubleshooting

### Verify AOP is working

```bash
# Check generated proxy classes
find build -name "*__AopProxy.java" | head -5
```

If no proxies are generated:
- Check the class is non-final (Java) / `open` (Kotlin), and the method is `open` in Kotlin.
- Verify the annotation processor is wired: Java `annotationProcessor "ru.tinkoff.kora:annotation-processors"`, Kotlin `ksp "ru.tinkoff.kora:symbol-processors"`.
- Clean rebuild: `./gradlew clean build --no-daemon`

### Enable debug logging

```hocon
logging.levels {
  "ru.tinkoff.kora.resilient": "DEBUG"
}
```

---

## Assets

Templates in `assets/`:

| Template | Description |
|----------|-------------|
| `ResilientService.java.template` | Full resilience stack (Java) |
| `ResilientService.kt.template` | Full resilience stack (Kotlin) |
| `RetryService.*.template` | @Retry pattern |
| `CircuitBreakerService.*.template` | @CircuitBreaker pattern |
| `TimeoutService.*.template` | @Timeout pattern |
| `FallbackService.*.template` | @Fallback pattern |

See [assets/README.md](assets/README.md) for usage.

---

## See Also

- [kora-http-client](../kora-http-client/SKILL.md) — Pair resilient with outbound HTTP clients
- [kora-telemetry-metrics](../kora-telemetry-metrics/SKILL.md) — Monitor retry attempts, circuit breaker state
- [kora-aop-logging](../kora-aop-logging/SKILL.md) — Add logging to resilient services
