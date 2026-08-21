# @Retry Reference

**Annotation:** `@Retry("name")`  
**Module:** `resilient-kora`  
**Package:** `ru.tinkoff.kora.resilient.retry.annotation`

## Contents

- [Basic Usage](#basic-usage)
- [Configuration](#configuration)
- [Exponential Backoff](#exponential-backoff)
- [Custom Retry Predicate](#custom-retry-predicate)
- [When to Use](#when-to-use)
- [Imperative API](#imperative-api)
- [Common Pitfalls](#common-pitfalls)

---

## Basic Usage

```java
@Component
public class UserService {
    
    @Retry("user.read")
    public Optional<User> findById(String id) {
        return userRepository.findById(id);
    }
}
```

```kotlin
@Component
open class UserService(
    private val userRepository: UserRepository
) {
    
    @Retry("user.read")
    open fun findById(id: String): Optional<User> {
        return userRepository.findById(id)
    }
}
```

---

## Configuration

```hocon
resilient.retry {
  default {
    delay = "100ms"       # Initial delay before first retry
    attempts = 3          # Number of retry attempts (after original call)
    delayStep = "100ms"   # Increment per attempt (linear backoff)
    enabled = true
  }
  "user.read" {
    attempts = 5
    delayStep = "200ms"
  }
}
```

### Wait Time Calculation

Formula: `delay + (n-1) * delayStep`

| Attempt | Delay (default) |
|---------|-----------------|
| 1st retry | 100ms |
| 2nd retry | 200ms |
| 3rd retry | 300ms |

**Total worst-case latency:** `attempts × (delay + delayStep)`

---

## Exponential Backoff

For exponential backoff, configure increasing `delayStep`:

```hocon
resilient.retry."external.api" {
  delay = "100ms"
  attempts = 4
  delayStep = "200ms"  # 100ms → 300ms → 500ms → 700ms
}
```

---

## Custom Retry Predicate

By default, Kora retries on all exceptions. Create custom predicates to control which exceptions trigger retries:

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

---

## When to Use

**Use retry when:**
- Failures are short-lived (network glitches, temporary unavailability)
- Operation is idempotent or safe to repeat
- Extra latency from retries is acceptable

**Use carefully when:**
- Operation changes state (non-idempotent)
- Downstream is overloaded (retries amplify pressure)
- Timeout budget is tight

---

## Imperative API

```java
@Component
public final class DataSyncService {
    
    private final RetryManager manager;
    
    public DataSyncService(RetryManager manager) {
        this.manager = manager;
    }
    
    public Data fetchWithCustomRetry() {
        return manager.get("data-sync").retry(() -> dataSource.fetch());
    }
}
```

---

## Common Pitfalls

| Problem | Solution |
|---------|----------|
| Retry makes latency worse | Estimate worst-case: `attempts × (delay + delayStep)`. Reduce for latency-sensitive paths |
| Non-idempotent operation retried | Use retry only on idempotent operations, or implement idempotency keys |
| Retry + Timeout confusion | Put `@Timeout` inside `@Retry` for per-attempt timeout |

---

## See Also

- [resilience-config-reference.md](resilience-config-reference.md) — General resilience configuration
- [timeout-reference.md](timeout-reference.md) — Combining with @Timeout
