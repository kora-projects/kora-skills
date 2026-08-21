# Micrometer Types Reference

**Focus:** Choosing the right metric type for your use case.

## Contents

- [Overview](#metric-types-overview)
- [Counter](#counter)
- [Gauge](#gauge)
- [Timer](#timer)
- [DistributionSummary](#distributionsummary)
- [Type selection guide](#type-selection-guide)
- [Common pitfalls](#common-pitfalls)

---

## Metric Types Overview

| Type | Use Case | API | Prometheus Type |
|------|----------|-----|-----------------|
| **Counter** | Count events (requests, errors, successes) | `counter.increment()` | `counter` |
| **Gauge** | Current value (queue size, connections) | `Gauge.builder(...).register()` | `gauge` |
| **Timer** | Duration/latency (request time, operation duration) | `timer.record(() -> {...})` | `histogram` |
| **DistributionSummary** | Size distribution (payload bytes, response sizes) | `summary.record(size)` | `histogram` |

---

## Counter

**Use for:** Events that can only increase — requests, errors, successes, cache hits.

```java
// Simple counter
Counter counter = registry.counter("http.requests.total");
counter.increment();

// Counter with tags
Counter counter = Counter.builder("http.requests.total")
    .tag("method", "GET")
    .tag("status", "200")
    .register(registry);
counter.increment();
```

**Important:** Counters can only go up. For gauges (values that can go up/down), use `Gauge`.

---

## Gauge

**Use for:** Current values that can go up and down — queue depth, active connections, cache size.

```java
// Gauge from atomic value
AtomicInteger queueSize = new AtomicInteger(0);
Gauge.builder("queue.size", queueSize, AtomicInteger::get)
    .tag("queue", "orders")
    .register(registry);

// Gauge from object method
Gauge.builder("cache.size", cache, Cache::size)
    .register(registry);
```

**Important:** Gauges report current value. Ensure the object reference remains valid for the lifetime of the application.

---

## Timer

**Use for:** Latency and duration measurements — request time, operation duration, query time.

```java
// Basic timer
Timer timer = registry.timer("operation.duration");
timer.record(() -> {
    // Business logic
});

// Timer with SLO buckets
Timer timer = Timer.builder("api.request.duration")
    .description("Request processing duration")
    .serviceLevelObjectives(
        Duration.ofMillis(50),   // p50 target
        Duration.ofMillis(100),  // p90 target
        Duration.ofMillis(250),  // p95 target
        Duration.ofMillis(500),  // p99 target
        Duration.ofSeconds(1)    // degradation threshold
    )
    .register(registry);

// Timer with percentiles (adds overhead)
Timer percentileTimer = Timer.builder("api.request.duration.percentile")
    .publishPercentiles(0.5, 0.9, 0.95, 0.99)
    .register(registry);
```

**Timer features:**
- `serviceLevelObjectives()` — configure histogram buckets for percentile calculations
- `publishPercentiles()` — enable server-side percentile calculation (adds CPU overhead)
- `record(Callable<T>)` — record execution time and return result
- `record(Runnable)` — record execution time

---

## DistributionSummary

**Use for:** Arbitrary value distributions — response sizes, message sizes, payload bytes.

```java
// Basic distribution summary
DistributionSummary summary = DistributionSummary.builder("payload.size.bytes")
    .description("Size of request payloads")
    .baseUnit("bytes")
    .register(registry);

summary.record(payloadSize);

// With SLO buckets
DistributionSummary summary = DistributionSummary.builder("response.size.bytes")
    .serviceLevelObjectives(100, 1000, 10000, 100000) // bytes
    .register(registry);
```

**Important:** Unlike Timer, DistributionSummary doesn't have built-in time units — you must track what unit you're using (bytes, items, etc.).

---

## Type Selection Guide

| What you're measuring | Type | Example |
|----------------------|------|---------|
| Total requests | Counter | `http.requests.total` |
| Error count | Counter | `errors.total` |
| Cache hits | Counter | `cache.hits.total` |
| Active connections | Gauge | `db.connections.active` |
| Queue depth | Gauge | `queue.size` |
| Request latency | Timer | `http.request.duration` |
| Operation duration | Timer | `user.creation.duration` |
| Response size | DistributionSummary | `http.response.size.bytes` |
| Message size | DistributionSummary | `kafka.message.size.bytes` |

---

## Common Pitfalls

| Problem | Solution |
|---------|----------|
| Using Gauge for counts | Use Counter for monotonically increasing values |
| Using Timer for sizes | Use DistributionSummary for non-time values |
| Not configuring buckets | Use `serviceLevelObjectives()` for meaningful percentiles |
| Enabling percentiles everywhere | Percentiles add CPU overhead — use SLO buckets instead |
| Wrong base unit | Always set `baseUnit()` for DistributionSummary (bytes, items, etc.) |

---

## References

- [Micrometer Counters](https://docs.micrometer.io/micrometer/reference/concepts/counters.html)
- [Micrometer Gauges](https://docs.micrometer.io/micrometer/reference/concepts/gauges.html)
- [Micrometer Timers](https://docs.micrometer.io/micrometer/reference/concepts/timers.html)
- [Micrometer DistributionSummaries](https://docs.micrometer.io/micrometer/reference/concepts/distribution-summaries.html)
