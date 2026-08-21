# Metrics Cardinality Reference

**Focus:** Understanding and avoiding high-cardinality tag pitfalls.

## Contents

- [What is cardinality?](#what-is-cardinality)
- [Good vs bad tags](#good-vs-bad-tags)
- [Memory leak pattern](#memory-leak-pattern)
- [Safe dynamic-tag pattern](#dynamic-tags-pattern-safe)
- [Cardinality limits](#cardinality-limits)
- [Checklist](#cardinality-checklist)
- [Troubleshooting](#troubleshooting)

---

## What is Cardinality?

**Cardinality** = the number of unique tag value combinations for a metric.

**Example:**
```java
// Low cardinality (3 methods × 4 status codes × 10 routes = 120 combinations)
Counter.builder("http.requests")
    .tag("method", "GET")        // bounded: GET, POST, PUT, DELETE
    .tag("status", "200")        // bounded: 2xx, 3xx, 4xx, 5xx
    .tag("route", "/api/users")  // bounded: known routes
    .register(registry);

// HIGH CARDINALITY - DO NOT USE!
Counter.builder("http.requests")
    .tag("userId", "user-12345")    // UNBOUNDED: millions of users
    .tag("requestId", UUID.randomUUID().toString())  // UNBOUNDED: every request unique
    .register(registry);
```

---

## Good vs Bad Tags

### ✅ Good Tags (Bounded, Stable)

| Tag | Example Values                  | Why Good |
|-----|---------------------------------|----------|
| `method` | `GET`, `POST`, `PUT`, `DELETE`  | Fixed set of HTTP methods |
| `status` | `200`, `400`, `404`, `500`      | Bounded status codes |
| `route` | `/api/users`, `/api/orders`     | Known, finite routes |
| `provider` | `stripe`, `paypal`, `sbp`       | Bounded payment providers |
| `email.provider` | `gmail.com`, `yahoo.com`        | Bounded (popular providers) |
| `operation` | `create`, `update`, `delete`    | Bounded operations |
| `result` | `success`, `failed`, `timeout`  | Bounded outcomes |
| `cache` | `users`, `orders`, `sessions`   | Known cache names |
| `pool` | `main`, `readonly`, `analytics` | Known connection pools |

### ❌ Bad Tags (Unbounded, High Cardinality)

| Tag | Why Bad | Memory Impact |
|-----|---------|---------------|
| `userId` | Millions of unique users | **Memory leak** — new entry per user |
| `email` | Every email is unique | **Memory leak** |
| `requestId` | UUID per request | **Memory leak** — grows infinitely |
| `sessionId` | Session per user | **Memory leak** |
| `orderId` | Every order is unique | **Memory leak** |
| `url` (raw) | Query params create infinite combos | **Memory leak** |
| `ip` | Client IP addresses | High cardinality, privacy concerns |
| `traceId` | Trace per request | **Memory leak** |

---

## Memory Leak Pattern

**Problem:** Each unique tag combination creates a new metric instance in Micrometer's internal `ConcurrentHashMap`.

```java
// WRONG: causes memory leak
public void recordRequest(String userId) {
    Counter.builder("requests.total")
        .tag("userId", userId)  // Each userId creates new metric!
        .register(registry);
}

// After 1M users: 1M metric instances in memory
// Application runs out of memory and crashes
```

**Solution:** Use bounded tags or aggregate:

```java
// CORRECT: aggregate by tier or use no tags
public void recordRequest(String userId) {
    // Option 1: No tags, just count
    registry.counter("requests.total").increment();
    
    // Option 2: Bounded tag (user tier)
    String tier = getUserTier(userId);  // "free", "premium", "enterprise"
    registry.counter("requests.total", "tier", tier).increment();
}
```

---

## Dynamic Tags Pattern (Safe)

For tags that vary at runtime but have **bounded values**:

```java
@Component
public class EmailMetrics {
    
    private final MeterRegistry registry;
    private final ConcurrentHashMap<String, Counter> providerCounters = new ConcurrentHashMap<>();
    
    public EmailMetrics(MeterRegistry registry) {
        this.registry = registry;
    }
    
    public void recordEmailSent(String email) {
        String provider = extractProvider(email);
        getOrCreateCounter(provider).increment();
    }
    
    private Counter getOrCreateCounter(String provider) {
        return providerCounters.computeIfAbsent(provider, p ->
            Counter.builder("email.sent.total")
                .tag("email.provider", p)
                .register(registry)
        );
    }
    
    private String extractProvider(String email) {
        int at = email.indexOf('@');
        if (at < 0 || at == email.length() - 1) {
            return "unknown";
        }
        String domain = email.substring(at + 1).toLowerCase();
        
        // Map to bounded set of providers
        return switch (domain) {
            case "gmail.com", "googlemail.com" -> "gmail";
            case "outlook.com", "hotmail.com", "live.com" -> "outlook";
            default -> "other";  // Bounded fallback
        };
    }
}
```

**Key principles:**
1. **Bounded values:** Map infinite domains to bounded set (gmail, outlook, other)
2. **Cache instances:** Use `computeIfAbsent` to create each metric once
3. **Fallback:** Handle unknown values with safe default

---

## Cardinality Limits

Kora serves metrics for Prometheus scraping. As a practical guideline:

| Scope | Recommended | Caution above |
|-------|-------------|---------------|
| Per metric (unique tag combinations) | under ~100 | 10K |
| Per Prometheus instance (total series) | — | 100K |

**Rule of thumb:** Keep cardinality under 100 unique tag combinations per metric.

---

## Cardinality Checklist

Before adding a tag, ask:

- [ ] **Is the value set bounded?** (e.g., HTTP methods: GET, POST, PUT, DELETE)
- [ ] **Can I enumerate all possible values?** (e.g., routes: /api/users, /api/orders, ...)
- [ ] **Will this tag explode with traffic?** (e.g., userId → millions)
- [ ] **Can I aggregate to a higher level?** (e.g., user tier instead of userId)
- [ ] **Is this tag necessary for alerting?** (If not, consider omitting)

---

## Troubleshooting

| Symptom | Likely Cause | Solution |
|---------|-------------|----------|
| Memory grows continuously | Unbounded tags (userId, requestId) | Remove or aggregate tags |
| Prometheus scrape fails | Too many time series | Reduce cardinality |
| Metric query times out | Too many unique combinations | Add aggregation or filters |

---

## References

- [Prometheus naming and labels](https://prometheus.io/docs/practices/naming/#labels)
- [Micrometer concepts](https://docs.micrometer.io/micrometer/reference/concepts.html)
- Local guide: `.kora-agent/kora-docs/mkdocs/docs/en/guides/observability-metrics.md`
