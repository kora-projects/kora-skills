# @CircuitBreaker Reference

**Annotation:** `@CircuitBreaker("name")`  
**Module:** `resilient-kora`  
**Package:** `ru.tinkoff.kora.resilient.circuitbreaker.annotation`

## Contents

- [Basic Usage](#basic-usage)
- [State Machine](#state-machine)
- [Configuration](#configuration)
- [Custom Failure Predicate](#custom-failure-predicate)
- [When to Use](#when-to-use)
- [Imperative API](#imperative-api)
- [Common Pitfalls](#common-pitfalls)

---

## Basic Usage

```java
@Component
public class OrderClient {
    
    @CircuitBreaker("order.service")
    public Order getOrder(String orderId) {
        return httpClient.get("/orders/" + orderId);
    }
}
```

```kotlin
@Component
open class OrderClient(
    private val httpClient: HttpClient
) {
    
    @CircuitBreaker("order.service")
    open fun getOrder(orderId: String): Order {
        return httpClient.get("/orders/$orderId")
    }
}
```

---

## State Machine

| State | Behavior | Transitions |
|-------|----------|-------------|
| **CLOSED** | Normal operation, failures tracked | → OPEN when failure threshold exceeded |
| **OPEN** | Requests fail immediately | → HALF_OPEN after `waitDurationInOpenState` |
| **HALF_OPEN** | Limited probe calls allowed | → CLOSED if successful, → OPEN if fails |

```
CLOSED ──(failures > threshold)──> OPEN ──(wait duration)──> HALF_OPEN
   ^                                  |
   |          (success)               | (failure)
   └──────────────────────────────────┘
```

---

## Configuration

```hocon
resilient.circuitbreaker {
  default {
    slidingWindowSize = 100           # Window for failure rate calculation
    minimumRequiredCalls = 10         # Minimum calls before evaluating failures
    failureRateThreshold = 50         # % failures to open (1-100)
    waitDurationInOpenState = "30s"   # Time before half-open
    permittedCallsInHalfOpenState = 5 # Probes allowed in half-open
    enabled = true
  }
  "order.service" {
    slidingWindowSize = 50
    failureRateThreshold = 30  # More sensitive for critical service
    waitDurationInOpenState = "60s"
  }
}
```

### Configuration Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `slidingWindowSize` | 100 | Number of calls in sliding window |
| `minimumRequiredCalls` | 10 | Minimum calls before evaluating failure rate |
| `failureRateThreshold` | 50 | Percentage of failures to trip circuit (1-100) |
| `waitDurationInOpenState` | 30s | Time to wait before transitioning to HALF_OPEN |
| `permittedCallsInHalfOpenState` | 5 | Number of test calls allowed in HALF_OPEN |

---

## Custom Failure Predicate

Prevent business errors (like 404 Not Found) from affecting circuit breaker state:

```java
@Component
public final class IgnoreBusinessErrors implements CircuitBreakerPredicate {
    
    @Override
    public String name() {
        return "IgnoreBusinessErrors";
    }
    
    @Override
    public boolean test(Throwable throwable) {
        // Only count infrastructure errors
        if (throwable instanceof HttpClientResponseException httpEx) {
            return httpEx.code() >= 500;  // Server errors only
        }
        return true;  // All other exceptions count
    }
}
```

```hocon
resilient.circuitbreaker."order.service" {
  failurePredicateName = "IgnoreBusinessErrors"
}
```

---

## When to Use

**Use circuit breaker when:**
- Downstream dependency is unstable
- Fast failure is better than repeated timeouts
- System needs recovery time before retrying
- Preventing cascading failures

**Configuration tips:**
- Lower `failureRateThreshold` for critical dependencies
- Higher `waitDurationInOpenState` for slow-recovering services
- Lower `permittedCallsInHalfOpenState` for high-load systems

---

## Imperative API

```java
@Component
public final class OrderService {
    
    private final CircuitBreakerManager manager;
    
    public OrderService(CircuitBreakerManager manager) {
        this.manager = manager;
    }
    
    public Order getOrder(String id) {
        CircuitBreaker cb = manager.get("order.service");
        return cb.accept(() -> httpClient.get("/orders/" + id));
    }
}
```

`CircuitBreakerManager.get(name)` returns the `CircuitBreaker` configured under `resilient.circuitbreaker."<name>"`, and `accept(...)` runs the supplied work through it. State is observed through the resilience metrics (see [kora-telemetry-metrics](../kora-telemetry-metrics/SKILL.md)), not by reading it imperatively.

---

## Common Pitfalls

| Problem | Solution |
|---------|----------|
| Circuit breaker never opens | Check `minimumRequiredCalls` — need enough calls to evaluate |
| Circuit opens too easily | Increase `minimumRequiredCalls`, raise `failureRateThreshold` |
| Reacts to 404 errors | Implement `CircuitBreakerPredicate` to exclude business errors |
| Overloaded in HALF_OPEN | Reduce `permittedCallsInHalfOpenState` |

---

## See Also

- [resilience-config-reference.md](resilience-config-reference.md) — General resilience configuration
- [retry-reference.md](retry-reference.md) — Combining with @Retry
- [fallback-reference.md](fallback-reference.md) — Graceful degradation
