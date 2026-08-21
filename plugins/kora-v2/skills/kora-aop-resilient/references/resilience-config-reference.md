# Resilience Configuration Reference

**Module:** `resilient-kora`  
**Package:** `ru.tinkoff.kora.resilient`

## Contents

- [Module Setup](#module-setup)
- [Full Configuration Example](#full-configuration-example)
- [YAML Configuration](#yaml-configuration)
- [Configuration Keys Reference](#configuration-keys-reference)
- [Custom Predicates](#custom-predicates)
- [Combining Resilience Patterns](#combining-resilience-patterns)
- [High-Throughput Configuration](#high-throughput-configuration)

---

## Module Setup

### Dependency

```groovy
dependencies {
    // Java — mandatory processor that generates the AOP proxies
    annotationProcessor "ru.tinkoff.kora:annotation-processors"
    // Kotlin instead uses: ksp "ru.tinkoff.kora:symbol-processors"

    implementation "ru.tinkoff.kora:resilient-kora"
}
```

### Enable ResilientModule

```java
@KoraApp
public interface Application extends
        HoconConfigModule,
        LogbackModule,
        ResilientModule { } // enables the resilience aspects
```

```kotlin
@KoraApp
interface Application :
    HoconConfigModule,
    LogbackModule,
    ResilientModule // enables the resilience aspects
```

---

## Full Configuration Example

```hocon
resilient {
  # ========== TIMEOUT ==========
  timeout {
    default {
      duration = "1s"
      enabled = true
    }
    "payment.process" {
      duration = "5s"
    }
    "report.generate" {
      duration = "30s"
    }
    "health.check" {
      duration = "100ms"
    }
  }
  
  # ========== RETRY ==========
  retry {
    default {
      delay = "100ms"       # Initial delay
      attempts = 3          # Retry attempts
      delayStep = "100ms"   # Increment per attempt
      enabled = true
    }
    "user.read" {
      attempts = 5
      delayStep = "200ms"
    }
    "external.api" {
      delay = "200ms"
      attempts = 4
      delayStep = "400ms"   # 200ms → 600ms → 1000ms → 1400ms
      failurePredicateName = "TransientErrorsOnly"
    }
  }
  
  # ========== CIRCUIT BREAKER ==========
  circuitbreaker {
    default {
      slidingWindowSize = 100
      minimumRequiredCalls = 10
      failureRateThreshold = 50
      waitDurationInOpenState = "30s"
      permittedCallsInHalfOpenState = 5
      enabled = true
    }
    "order.service" {
      slidingWindowSize = 50
      minimumRequiredCalls = 5
      failureRateThreshold = 30
      waitDurationInOpenState = "60s"
      failurePredicateName = "IgnoreBusinessErrors"
    }
  }
  
  # ========== FALLBACK ==========
  fallback {
    default {
      enabled = true
    }
    "product.read" {
      failurePredicateName = "CacheableErrors"
    }
  }
}
```

---

## YAML Configuration

```yaml
resilient:
  timeout:
    default:
      duration: "1s"
      enabled: true
    payment.process:
      duration: "5s"
    report.generate:
      duration: "30s"
  retry:
    default:
      delay: "100ms"
      attempts: 3
      delayStep: "100ms"
      enabled: true
  circuitbreaker:
    default:
      slidingWindowSize: 100
      minimumRequiredCalls: 10
      failureRateThreshold: 50
      waitDurationInOpenState: "30s"
      permittedCallsInHalfOpenState: 5
      enabled: true
  fallback:
    default:
      enabled: true
```

---

## Configuration Keys Reference

### Timeout

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `duration` | Duration | - | Timeout duration (required) |
| `enabled` | Boolean | `true` | Enable/disable |

### Retry

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `delay` | Duration | - | Initial delay before first retry |
| `attempts` | Integer | - | Number of retry attempts |
| `delayStep` | Duration | - | Increment per attempt |
| `enabled` | Boolean | `true` | Enable/disable |
| `failurePredicateName` | String | - | Custom predicate name |

### Circuit Breaker

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `slidingWindowSize` | Integer | 100 | Window size for failure calculation |
| `minimumRequiredCalls` | Integer | 10 | Minimum calls before evaluation |
| `failureRateThreshold` | Integer | 50 | Failure % to trip (1-100) |
| `waitDurationInOpenState` | Duration | 30s | Time before HALF_OPEN |
| `permittedCallsInHalfOpenState` | Integer | 5 | Test calls in HALF_OPEN |
| `enabled` | Boolean | `true` | Enable/disable |
| `failurePredicateName` | String | - | Custom predicate name |

### Fallback

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `enabled` | Boolean | `true` | Enable/disable |
| `failurePredicateName` | String | - | Custom predicate name |

---

## Custom Predicates

### Retry Predicate

```java
@Component
public final class RetryOnlyTransientErrors implements RetryPredicate {
    
    @Override
    public String name() {
        return "TransientErrorsOnly";
    }
    
    @Override
    public boolean test(Throwable throwable) {
        return throwable instanceof SocketTimeoutException
            || throwable instanceof ConnectException
            || throwable instanceof TransientSystemException;
    }
}
```

```hocon
resilient.retry."external.api" {
  failurePredicateName = "TransientErrorsOnly"
}
```

### Circuit Breaker Predicate

```java
@Component
public final class IgnoreBusinessErrors implements CircuitBreakerPredicate {
    
    @Override
    public String name() {
        return "IgnoreBusinessErrors";
    }
    
    @Override
    public boolean test(Throwable throwable) {
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

### Fallback Predicate

```java
@Component
public final class CacheableErrors implements FallbackPredicate {
    
    @Override
    public String name() {
        return "CacheableErrors";
    }
    
    @Override
    public boolean test(Throwable throwable) {
        // Trigger fallback on database errors
        return throwable instanceof SQLException
            || throwable instanceof DatabaseException;
    }
}
```

```hocon
resilient.fallback."product.read" {
  failurePredicateName = "CacheableErrors"
}
```

---

## Combining Resilience Patterns

### Recommended Order (Outer → Inner)

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

### Execution Flow

1. `@Timeout` bounds the actual HTTP call
2. `@Retry` repeats on transient failures (up to N attempts)
3. `@CircuitBreaker` opens if failures exceed threshold
4. `@Fallback` returns degraded response if circuit is open or all retries fail

### Per-Attempt Timeout

For timeout on each retry attempt (not the whole chain):

```java
@Component
public class SearchService {
    
    @Retry("search.query")
    @Timeout("search.query.perAttempt")
    public List<SearchResult> search(String query) {
        return searchEngine.search(query);
    }
}
```

```hocon
resilient {
  retry."search.query" {
    attempts = 3
    delay = "50ms"
  }
  timeout."search.query.perAttempt" {
    duration = "2s"  // Each retry gets 2s
  }
}
```

---

## High-Throughput Configuration

For services handling >1000 req/s:

```hocon
resilient {
  circuitbreaker {
    high_throughput {
      slidingWindowSize = 1000
      minimumRequiredCalls = 100
      failureRateThreshold = 60
      permittedCallsInHalfOpenState = 10
      waitDurationInOpenState = "10s"
    }
  }
  
  retry {
    high_throughput {
      attempts = 2
      delay = "50ms"
      delayStep = "50ms"
    }
  }
  
  timeout {
    high_throughput {
      duration = "200ms"
    }
  }
}
```

---

## See Also

- [retry-reference.md](retry-reference.md) — @Retry details
- [circuit-breaker-reference.md](circuit-breaker-reference.md) — @CircuitBreaker details
- [timeout-reference.md](timeout-reference.md) — @Timeout details
- [fallback-reference.md](fallback-reference.md) — @Fallback details
