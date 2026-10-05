# Micrometer Types Reference

Choosing and building the right meter. Micrometer is pinned to **`1.17.1`** by the Kora 2.0 BOM and
arrives transitively with `io.koraframework:micrometer-module` — never add
`io.micrometer:micrometer-core` or `micrometer-registry-prometheus` yourself.

All types below are `io.micrometer.core.instrument.*`. They are Micrometer APIs, not Kora APIs:
Kora only supplies the `MeterRegistry` you register them on.

## Contents

- [Overview](#overview)
- [Counter](#counter)
- [Gauge](#gauge)
- [Timer](#timer)
- [DistributionSummary](#distributionsummary)
- [Type selection guide](#selection)
- [Kotlin notes](#kotlin)
- [Common pitfalls](#pitfalls)

---

## Overview { #overview }

| Type | Use for | Typical call | Prometheus shape |
|---|---|---|---|
| **Counter** | monotonically increasing event counts | `counter.increment()` | `<name>_total` counter |
| **Gauge** | a current, up-and-down value | `Gauge.builder(name, obj, fn).register(registry)` | `<name>` gauge |
| **Timer** | latency / duration | `timer.record(() -> …)` | histogram: `_count`, `_sum`, `_bucket`, `_max` |
| **DistributionSummary** | distribution of a non-time value | `summary.record(size)` | histogram: `_count`, `_sum`, `_bucket`, `_max` |

Kora's own instrumentation uses only `Timer`, `Counter` and `Gauge` — see
[metrics-reference.md](metrics-reference.md).

---

## Counter { #counter }

Events that can only go up: requests handled, errors, cache hits, messages published.

```java
// no tags
Counter counter = registry.counter("http.requests.total");
counter.increment();

// with tags, via the builder
Counter counter = Counter.builder("http.requests.total")
        .description("Total requests handled")
        .tag("method", "GET")
        .tag("status", "200")
        .register(registry);
counter.increment();
```

`increment(double)` adds an arbitrary positive amount. A counter must never decrease — if the value
can go down, you want a `Gauge`.

For a value derived from something you already track, `FunctionCounter` avoids double-counting:

```java
registry.more().counter("queue.processed.total", Tags.empty(), queue, Queue::processedCount);
```

---

## Gauge { #gauge }

A value sampled at scrape time: queue depth, active connections, cache size, a warm-up flag.

```java
AtomicInteger queueSize = new AtomicInteger(0);
Gauge.builder("queue.size", queueSize, AtomicInteger::get)
        .tag("queue", "orders")
        .register(registry);

Gauge.builder("cache.size", cache, Cache::estimatedSize)
        .register(registry);
```

**Micrometer holds a weak reference to the gauged object.** If nothing else keeps `queueSize` or
`cache` alive, the gauge starts reporting `NaN` after a GC. Store the object in a field of a
`@Component` — a Kora graph component lives for the application's lifetime, which is exactly the
right scope.

`Gauge.builder(...).register(...)` returns the `Gauge`, but you usually discard it: the value comes
from the function on every scrape. Kora does this in `DefaultHttpServerMetricsFactory`, keeping the
`AtomicLong` and letting the `Gauge` register itself:

```java
var value = new AtomicLong(0);
Gauge.builder("http.server.active_requests", value, AtomicLong::get)
        .tags(staticTags)
        .register(this.context.meterRegistry());
return value;
```

---

## Timer { #timer }

Latency and duration.

```java
Timer timer = Timer.builder("api.request.duration")
        .description("Request processing duration")
        .serviceLevelObjectives(
                Duration.ofMillis(50),
                Duration.ofMillis(100),
                Duration.ofMillis(250),
                Duration.ofMillis(500),
                Duration.ofSeconds(1))
        .register(registry);
```

Four ways to record, each with different exception behaviour:

| Call | Returns | Exceptions |
|---|---|---|
| `timer.record(Runnable)` | `void` | unchecked only |
| `timer.record(Supplier<T>)` | `T` | unchecked only |
| `timer.recordCallable(Callable<T>)` | `T` | declares `throws Exception` |
| `timer.record(long, TimeUnit)` | `void` | n/a — you supply the duration |

`Timer.start(registry)` / `sample.stop(timer)` covers regions that are not a single call:

```java
var sample = Timer.start(registry);
try {
    doWork();
} finally {
    sample.stop(timer);
}
```

### `serviceLevelObjectives` vs `publishPercentiles`

- `serviceLevelObjectives(...)` emits cumulative `_bucket{le="…"}` series. Prometheus computes
  quantiles from them with `histogram_quantile`, and buckets are aggregatable across instances.
  This is what Kora's own timers use — the boundaries come from `telemetry.metrics.slo`.
- `publishPercentiles(0.95, 0.99)` computes percentiles **inside the process** and exports them as
  `quantile` labels. They cost CPU and memory, and they are **not aggregatable**: averaging two
  pods' p99 gives a number that means nothing.

With Prometheus, prefer SLO buckets. Reach for `publishPercentiles` only when a single instance's
own percentile is the thing you need.

---

## DistributionSummary { #distributionsummary }

Distributions of values that are not durations: payload bytes, batch sizes, monetary amounts.

```java
DistributionSummary summary = DistributionSummary.builder("payload.size")
        .description("Size of request payloads")
        .baseUnit("bytes")
        .register(registry);

summary.record(payloadSize);
```

With buckets:

```java
DistributionSummary.builder("response.size")
        .baseUnit("bytes")
        .serviceLevelObjectives(100, 1_000, 10_000, 100_000)
        .register(registry);
```

`record` takes a `double`, and there is no implicit unit — always set `baseUnit(...)` so the
exported series carries it. Negative values are ignored by Micrometer, so a summary cannot represent
a signed quantity; record the magnitude and a sign tag, or use two summaries.

---

## Type selection guide { #selection }

| What you are measuring | Type | Example name |
|---|---|---|
| Total requests | Counter | `http.requests.total` |
| Error count | Counter | `errors.total` |
| Cache hits | Counter | `cache.hits.total` |
| Active connections | Gauge | `db.connections.active` |
| Queue depth | Gauge | `queue.size` |
| Warm-up / feature flag state | Gauge | `reference.data.loaded` |
| Request latency | Timer | `http.request.duration` |
| Operation duration | Timer | `user.creation.duration` |
| Response size | DistributionSummary | `http.response.size` (`baseUnit("bytes")`) |
| Message size | DistributionSummary | `kafka.message.size` (`baseUnit("bytes")`) |

Rule of thumb: **if the unit is time, it is a `Timer`; if it only goes up, it is a `Counter`;
if it is sampled, it is a `Gauge`; otherwise it is a `DistributionSummary`.**

---

## Kotlin notes { #kotlin }

- `DistributionSummary.record` takes a `double`, so an `Int`/`Long` needs `.toDouble()`.
- `Timer.record { … }` is ambiguous between the `Runnable` and `Supplier<T>` overloads when the
  lambda's last expression has a value. If the compiler complains, name the overload:
  `timer.record(Supplier { … })` or use `recordCallable { … }`.
- `recordCallable` returns a platform type; assign it to an explicit type if you want Kotlin to
  enforce nullability.
- Build meters in property initialisers or `init`, not lazily per call — see
  [custom-metrics-reference.md](custom-metrics-reference.md).

---

## Common pitfalls { #pitfalls }

| Problem | Fix |
|---|---|
| Gauge reports `NaN` after a while | The gauged object was garbage collected — hold it in a component field |
| Using a Gauge for a count | Counters are monotonic and rate-able; gauges are not |
| Using a Timer for sizes | `DistributionSummary` — a Timer forces a time base unit |
| No buckets, then asking for p99 | Add `serviceLevelObjectives(...)`; without them there is nothing for `histogram_quantile` |
| `publishPercentiles` everywhere | Per-instance percentiles do not aggregate; prefer SLO buckets |
| Registering the same meter per request | Register once in the constructor, or cache with `computeIfAbsent` |
| Dynamic tags passed to a cached builder | The cache key must contain every varying tag, or meters collide |
| Missing base unit | Set `baseUnit(...)` on every `DistributionSummary` |
| Added `micrometer-core` explicitly | Remove it — the BOM pins `1.17.1` through `micrometer-module` |

---

## References

- [Micrometer counters](https://docs.micrometer.io/micrometer/reference/concepts/counters.html)
- [Micrometer gauges](https://docs.micrometer.io/micrometer/reference/concepts/gauges.html)
- [Micrometer timers](https://docs.micrometer.io/micrometer/reference/concepts/timers.html)
- [Micrometer distribution summaries](https://docs.micrometer.io/micrometer/reference/concepts/distribution-summaries.html)
- [Prometheus histograms and quantiles](https://prometheus.io/docs/practices/histograms/)
