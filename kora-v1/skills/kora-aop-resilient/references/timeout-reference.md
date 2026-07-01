# @Timeout Reference

**Annotation:** `@Timeout("name")`  
**Module:** `resilient-kora`  
**Package:** `ru.tinkoff.kora.resilient.timeout.annotation`

## Contents

- [Basic Usage](#basic-usage)
- [Configuration](#configuration)
- [When to Use](#when-to-use)
- [Timeout Hierarchy](#timeout-hierarchy)
- [Combining with Retry](#combining-with-retry)
- [Imperative API](#imperative-api)
- [Common Pitfalls](#common-pitfalls)

---

## Basic Usage

```java
@Component
public class ReportService {
    
    @Timeout("report.generate")
    public Report generateReport(ReportRequest request) {
        return reportEngine.generate(request);
    }
}
```

```kotlin
@Component
open class ReportService(
    private val reportEngine: ReportEngine
) {
    
    @Timeout("report.generate")
    open fun generateReport(request: ReportRequest): Report {
        return reportEngine.generate(request)
    }
}
```

---

## Configuration

```hocon
resilient.timeout {
  default {
    duration = "1s"
    enabled = true
  }
  "report.generate" {
    duration = "30s"  // Long-running operation
  }
  "http.call" {
    duration = "5s"
  }
}
```

### Exception

`TimeoutExhaustedException` is thrown when timeout expires.

### Thread Interruption

**Important:** The underlying thread is **interrupted** on timeout. Ensure your code handles `Thread.interrupted()`:

```java
@Timeout("long.operation")
public Result longOperation() {
    try {
        for (int i = 0; i < 1000; i++) {
            if (Thread.interrupted()) {
                // Clean up and return early
                return Result.cancelled();
            }
            processStep(i);
        }
        return Result.success();
    } catch (InterruptedException e) {
        Thread.currentThread().interrupt();
        return Result.cancelled();
    }
}
```

---

## When to Use

**Use timeout when:**
- Operations may hang (network calls, slow queries)
- Need predictable latency bounds
- Slow failures are worse than fast failures

**Use carefully when:**
- Timeout is shorter than normal latency
- Operation has side effects (may continue after timeout)
- Stacking with retries (total latency = timeout × attempts)

---

## Timeout Hierarchy

Different timeouts for different operation types:

```hocon
resilient.timeout {
  fast { duration = "100ms" }    # Health checks, cache lookups
  standard { duration = "1s" }   # Most business operations
  slow { duration = "10s" }      # Report generation, batch ops
  very_slow { duration = "60s" } # Data imports, migrations
}
```

---

## Combining with Retry

### Per-Attempt Timeout (Recommended)

Timeout applies to each retry attempt:

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

**Total worst-case latency:** `3 attempts × 2s = 6s`

### Overall Timeout

Timeout applies to the entire retry chain:

```java
@Component
public class PaymentService {
    
    @Timeout("payment.overall")  // 10s total
    @Retry("payment.retry")      // 3 attempts
    public PaymentResult charge(PaymentRequest request) {
        return paymentGateway.charge(request);
    }
}
```

```hocon
resilient {
  timeout."payment.overall" {
    duration = "10s"  // Total budget
  }
  retry."payment.retry" {
    attempts = 3
    delay = "100ms"
  }
}
```

---

## Imperative API

```java
@Component
public final class ReportService {
    
    private final TimeoutManager manager;
    
    public ReportService(TimeoutManager manager) {
        this.manager = manager;
    }
    
    public Report generate(ReportRequest request) {
        Timeout timeout = manager.get("report.generate");
        return timeout.execute(() -> reportEngine.generate(request));
    }
}
```

---

## Common Pitfalls

| Problem | Solution |
|---------|----------|
| Timeout never fires | Ensure operation actually exceeds duration |
| Thread not interrupted | Check code for `Thread.interrupted()` handling |
| Confusion with retry total time | Put `@Timeout` inside `@Retry` for per-attempt timeout |
| Side effects after timeout | Use cancellation tokens or idempotent operations |

---

## See Also

- [resilience-config-reference.md](resilience-config-reference.md) — General resilience configuration
- [retry-reference.md](retry-reference.md) — Combining with @Retry
