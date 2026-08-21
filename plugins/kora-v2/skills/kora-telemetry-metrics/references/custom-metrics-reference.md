# Custom Business Metrics Reference

**Focus:** Patterns for implementing business metrics in Kora applications.

## Contents

- [Basic pattern](#basic-pattern)
- [Dynamic tags with caching](#pattern-dynamic-tags-with-caching)
- [High-throughput caching](#pattern-high-throughput-caching)
- [Complete payment example](#pattern-complete-example--payment-service)
- [Naming conventions](#naming-conventions)

---

## Basic Pattern

```java
@Component
public class BusinessMetrics {
    
    private final MeterRegistry meterRegistry;
    private final Timer operationTimer;
    private final Counter successCounter;
    
    public BusinessMetrics(MeterRegistry meterRegistry) {
        this.meterRegistry = meterRegistry;
        
        // Timer for operation duration
        this.operationTimer = Timer.builder("user.creation.duration")
            .description("Time taken to create users")
            .serviceLevelObjectives(
                Duration.ofMillis(50),
                Duration.ofMillis(100),
                Duration.ofMillis(250),
                Duration.ofMillis(500)
            )
            .register(meterRegistry);
        
        // Counter for total operations
        this.successCounter = Counter.builder("user.creation.total")
            .description("Total users created")
            .register(meterRegistry);
    }
    
    public User createUser(CreateUserRequest request) {
        return operationTimer.record(() -> {
            // Business logic
            User user = userRepository.save(request.toEntity());
            successCounter.increment();
            return user;
        });
    }
}
```

---

## Pattern: Dynamic Tags with Caching

**Problem:** You need tags that vary at runtime (e.g., email provider, payment method), but tag values must be bounded to avoid memory leaks.

**Solution:** Cache metric instances with `ConcurrentHashMap.computeIfAbsent()`.

```java
@Component
public class CachedMetricsService {

    private final MeterRegistry meterRegistry;
    private final Timer userCreationTimer;
    private final ConcurrentHashMap<String, Counter> userCreationCounters = new ConcurrentHashMap<>();

    public CachedMetricsService(MeterRegistry meterRegistry) {
        this.meterRegistry = meterRegistry;
        
        // Timer registered once (no dynamic tags)
        this.userCreationTimer = Timer.builder("user.creation.duration")
                .description("Time taken to create users")
                .serviceLevelObjectives(
                    Duration.ofMillis(50),
                    Duration.ofMillis(100),
                    Duration.ofMillis(250),
                    Duration.ofMillis(500)
                )
                .register(meterRegistry);
    }

    public <T> T recordUserCreation(String email, Callable<T> action) {
        try {
            var result = this.userCreationTimer.recordCallable(action);
            this.userCreationCounter(emailProvider(email)).increment();
            return result;
        } catch (RuntimeException e) {
            throw e;
        } catch (Exception e) {
            throw new IllegalStateException("Failed to record user creation metrics", e);
        }
    }

    private Counter userCreationCounter(String emailProvider) {
        return this.userCreationCounters.computeIfAbsent(emailProvider, provider ->
            Counter.builder("user.creation.total")
                .description("Total number of users created")
                .tag("email.provider", provider)
                .register(this.meterRegistry)
        );
    }

    private static String emailProvider(String email) {
        int at = email.indexOf('@');
        if (at < 0 || at == email.length() - 1) {
            return "unknown";
        }
        return email.substring(at + 1).toLowerCase(Locale.ROOT);
    }
}
```

**Key patterns:**
1. **Timer registered once** in constructor (no dynamic tags)
2. **Counter cache** with `computeIfAbsent` for dynamic tag values
3. **Tag extraction** from domain data (email → provider)
4. **Safe fallback** (`unknown`) for invalid data

---

## Pattern: High-Throughput Caching

**Problem:** Repeated `builder.register()` calls under high load cause contention on Micrometer's internal `ConcurrentHashMap`.

**Solution:** Cache metric instances in your own map with composite keys.

```java
public final class CachedMetrics {
    
    // Immutable record as Map key
    record MetricKey(String operation, String status) {}
    
    private final ConcurrentHashMap<MetricKey, Timer> timers = new ConcurrentHashMap<>();
    private final ConcurrentHashMap<MetricKey, Counter> counters = new ConcurrentHashMap<>();
    private final MeterRegistry registry;

    public CachedMetrics(MeterRegistry registry) {
        this.registry = registry;
    }

    public void recordOperation(String operation, long durationNanos, boolean success) {
        var key = new MetricKey(operation, success ? "success" : "failed");
        
        var timer = timers.computeIfAbsent(key, k -> 
            Timer.builder("custom.operation.duration")
                .tag("operation", k.operation())
                .tag("status", k.status())
                .register(registry)
        );
        
        timer.record(durationNanos, TimeUnit.NANOSECONDS);
    }

    public void incrementCounter(String operation, String type) {
        var key = new MetricKey(operation, type);
        
        var counter = counters.computeIfAbsent(key, k ->
            Counter.builder("custom.operation.count")
                .tag("operation", k.operation())
                .tag("type", k.type())
                .register(registry)
        );
        
        counter.increment();
    }
}
```

**When to cache:**
- High-throughput operations (>1000 calls/sec)
- Metrics with multiple tag combinations (bounded cardinality)

**When NOT to cache:**
- Simple counters without tags
- Metrics with unbounded tags (userId, sessionId, requestId) — causes memory leaks

---

## Pattern: Complete Example — Payment Service

```java
@Component
public final class PaymentMetricsService {
    
    private final Counter paymentsCounter;
    private final Counter failuresCounter;
    private final Timer paymentTimer;
    private final DistributionSummary paymentAmount;
    private final MeterRegistry registry;

    public PaymentMetricsService(MeterRegistry registry) {
        this.registry = registry;
        
        // Counters for event counting
        this.paymentsCounter = registry.counter("payment.processed.total", "status", "success");
        this.failuresCounter = registry.counter("payment.processed.total", "status", "failed");
        
        // Timer for latency with custom buckets
        this.paymentTimer = Timer.builder("payment.processing.duration")
            .description("Time taken to process payment")
            .serviceLevelObjectives(
                Duration.ofMillis(50),
                Duration.ofMillis(100),
                Duration.ofMillis(500),
                Duration.ofSeconds(1),
                Duration.ofSeconds(5)
            )
            .register(registry);
        
        // DistributionSummary for amount
        this.paymentAmount = DistributionSummary.builder("payment.amount")
            .description("Payment amount distribution")
            .tag("currency", "RUB")
            .baseUnit("rubles")
            .register(registry);
    }

    public PaymentResult process(Payment payment) {
        return paymentTimer.record(() -> {
            try {
                var result = executePayment(payment);
                
                paymentsCounter.increment();
                paymentAmount.record(payment.amount());
                
                return result;
            } catch (PaymentException e) {
                failuresCounter.increment();
                throw e;
            }
        });
    }
}
```

---

## Naming Conventions

Follow [OpenTelemetry semantic conventions](https://opentelemetry.io/docs/specs/semconv/):

| Pattern | Example | Type |
|---------|---------|------|
| `<noun>.<action>.duration` | `user.creation.duration` | Timer |
| `<noun>.<action>.total` | `user.creation.total` | Counter |
| `<noun>.<attribute>` | `payment.amount` | DistributionSummary |
| `<system>.<component>.<metric>` | `http.server.request.duration` | Timer |

**Best practices:**
- Use dots (`.`) as separators
- End duration metrics with `.duration`
- End counter metrics with `.total`
- Include unit in name or `baseUnit()` (e.g., `.bytes`, `.rubles`)

---

## References

- [Micrometer concepts](https://docs.micrometer.io/micrometer/reference/concepts.html)
- [OpenTelemetry semantic conventions](https://opentelemetry.io/docs/specs/semconv/)
- Local guide: `.kora-agent/kora-docs/mkdocs/docs/en/guides/observability-metrics.md`
