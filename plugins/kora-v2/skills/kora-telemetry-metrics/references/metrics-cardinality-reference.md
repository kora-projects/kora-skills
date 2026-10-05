# Metrics Cardinality Reference

Keeping the number of time series bounded. Nothing here is Kora-version-specific except the tag
names, which are the real Kora 2.0 ones — see [metrics-reference.md](metrics-reference.md).

## Contents

- [What cardinality is](#what)
- [Good vs bad tags](#good-vs-bad)
- [The leak pattern](#leak)
- [Safe dynamic-tag pattern](#safe-pattern)
- [Kora's own bounded tags](#koras-tags)
- [The bucket multiplier](#buckets)
- [Practical limits](#limits)
- [Checklist](#checklist)
- [Troubleshooting](#troubleshooting)

---

## What cardinality is { #what }

**Cardinality** = the number of distinct tag-value combinations for a metric. Each combination is a
separate time series held in the registry for the process's lifetime, and stored forever by the
scraper.

```java
// bounded: 4 methods x ~10 routes x 2 error states ≈ 80 series
Counter.builder("http.requests")
    .tag("http.request.method", "GET")
    .tag("http.route", "/api/users/{id}")
    .tag("error.type", "")
    .register(registry);

// UNBOUNDED — do not do this
Counter.builder("http.requests")
    .tag("userId", "user-12345")
    .tag("requestId", UUID.randomUUID().toString())
    .register(registry);
```

The second form allocates a new `Counter` per unique pair and keeps it. That is an in-process
memory leak *and* an unbounded write load on the scraper.

---

## Good vs bad tags { #good-vs-bad }

### Bounded and stable

| Tag | Example values | Why it is safe |
|---|---|---|
| `http.request.method` | `GET`, `POST`, `PUT`, `DELETE` | fixed set |
| `http.response.status_code` | `200`, `404`, `500` | the codes your routes actually return |
| `http.route` | `/api/users/{id}` — the **template** | one per declared route; Kora uses `UNKNOWN_ROUTE` when nothing matched |
| `error.type` | `""`, `java.io.IOException` | the exception classes your code can actually throw |
| `db.operation.name` | `SELECT`, `INSERT`, `UPDATE` | fixed set |
| `db.query.text` | the repository **query id** | one per declared `@Query` |
| `status` / `result` | `success`, `failed`, `timeout` | your own enum |
| `provider` | `stripe`, `paypal`, `sbp` | enumerable business dimension |
| `origin` | `caffeine`, `redis` | fixed by the framework |

### Unbounded

| Tag | Why it is unsafe |
|---|---|
| `userId` | one series per user, forever |
| `email` | strictly one per user |
| `requestId` / `traceId` | one per request — the fastest possible leak |
| `sessionId`, `orderId` | one per session / order |
| raw URL or path | query parameters make it infinite |
| client `ip` | high cardinality plus a privacy problem |
| a raw exception **message** | often embeds ids or values; use the exception **type** |

The last one is the subtle one. `error.type` in Kora is
`throwable.getClass().getCanonicalName()` — deliberately the class, never `getMessage()`.

---

## The leak pattern { #leak }

```java
// WRONG
public void recordRequest(String userId) {
    Counter.builder("requests.total")
        .tag("userId", userId)
        .register(registry)          // new meter per userId, retained forever
        .increment();
}
```

After a million users this is a million meters, each holding its tag list, in a
`ConcurrentHashMap` that is never pruned. The symptom is a slow heap climb that survives GC,
followed by scrape timeouts as `/metrics` grows to megabytes.

```java
// CORRECT — aggregate to a bounded dimension
public void recordRequest(String userId) {
    registry.counter("requests.total").increment();                  // no tag at all
    registry.counter("requests.total", "tier", tierOf(userId)).increment();  // or a bounded tier
}
```

If you need per-user attribution, that is a job for logs or traces (where each record is discarded
after retention), not for metrics (where each label combination is retained forever). See
[kora-telemetry-logging](../../kora-telemetry-logging/SKILL.md) and
[kora-telemetry-tracing](../../kora-telemetry-tracing/SKILL.md).

---

## Safe dynamic-tag pattern { #safe-pattern }

For a runtime tag whose values are genuinely bounded, map to a known set and cache the meter:

```java
package com.example;

import io.koraframework.common.annotation.Component;
import io.micrometer.core.instrument.Counter;
import io.micrometer.core.instrument.MeterRegistry;

import java.util.Locale;
import java.util.concurrent.ConcurrentHashMap;

@Component
public final class EmailMetrics {

    private final MeterRegistry registry;
    private final ConcurrentHashMap<String, Counter> providerCounters = new ConcurrentHashMap<>();

    public EmailMetrics(MeterRegistry registry) {
        this.registry = registry;
    }

    public void recordEmailSent(String email) {
        counter(provider(email)).increment();
    }

    private Counter counter(String provider) {
        return this.providerCounters.computeIfAbsent(provider, p ->
                Counter.builder("email.sent.total")
                        .tag("email.provider", p)
                        .register(this.registry));
    }

    private static String provider(String email) {
        int at = email.indexOf('@');
        if (at < 0 || at == email.length() - 1) {
            return "unknown";
        }
        return switch (email.substring(at + 1).toLowerCase(Locale.ROOT)) {
            case "gmail.com", "googlemail.com" -> "gmail";
            case "outlook.com", "hotmail.com", "live.com" -> "outlook";
            default -> "other";
        };
    }
}
```

The `switch` is what makes this safe. Returning the raw domain instead would put an attacker — or
just a typo-prone signup form — in charge of your series count. **Bounding happens in the mapping
function, not in the cache.** A `ConcurrentHashMap` around an unbounded key set is still a leak.

---

## Kora's own bounded tags { #koras-tags }

Worth copying, because the framework had the same problem and solved it:

- **route templates, never raw paths.** `DefaultHttpServerMetricsFactory` uses
  `request.pathTemplate()` and substitutes the literal `UNKNOWN_ROUTE` when there is none, so 404
  traffic to random URLs collapses into one series instead of one per URL.
- **query ids, never SQL text.** `db.query.text` carries `query.queryId()`.
- **exception classes, never messages**, with `CompletionException` unwrapped to its cause first so
  a wrapper type does not double the series.
- **cached meters keyed by a record** holding every varying tag —
  `requestDurationCache`, `activeRequestsCache`, `operationDurationCache`, and so on.
- the guard comment on every builder method:
  `DO NOT ADD DYNAMIC TAGS IN BUILDER, use metric key instead of metric collision will happen`.

---

## The bucket multiplier { #buckets }

Cardinality is not only about tags. Every Kora timer is a histogram with `telemetry.metrics.slo`
boundaries, and the default `MetricsConfig.DEFAULT_SLO` has **14** of them. Each distinct tag
combination therefore produces roughly 14 `_bucket` series plus `_count`, `_sum` and `_max`.

50 route/method combinations × 17 series ≈ 850 series from one metric — multiplied again by the
number of distinct `http.response.status_code` values each route returns, before common tags.

Trim the buckets where you do not need the resolution:

```hocon
httpServer.telemetry.metrics {
  enabled = true                              # slo does nothing without this
  slo = [ 25, 100, 500, 1000, 5000 ]
}
```

And remember that global common tags (`metrics.tags`, `MetricsTagsProvider`, or a
`PrometheusMeterRegistryInitializer`) and per-component
`telemetry.metrics.tags` multiply onto **every** series — a constant-valued common tag adds no
cardinality, but a tag that differs per pod (like an instance id) multiplies everything by the
number of pods.

---

## Practical limits { #limits }

| Scope | Comfortable | Investigate above |
|---|---|---|
| Unique tag combinations per metric | under ~100 | 10 000 |
| Total series per scraped instance | under ~10 000 | 100 000 |

These are operational rules of thumb, not framework limits — Kora enforces nothing. The real limit
is your scraper's memory and query latency.

---

## Checklist { #checklist }

Before adding a tag:

- [ ] Can I enumerate every possible value, today, on paper?
- [ ] Is the value set fixed by code (an enum, a route table) rather than by user input?
- [ ] Does traffic growth leave the value count unchanged?
- [ ] Is there a bounded fallback for unexpected input?
- [ ] Do I need this for an alert or a dashboard, or would a log/trace serve better?
- [ ] Have I accounted for the bucket multiplier if this is a timer?

A "no" to any of the first four means the tag does not belong on a metric.

---

## Troubleshooting { #troubleshooting }

| Symptom | Likely cause | Fix |
|---|---|---|
| Heap grows steadily, survives GC | unbounded tag values | remove or aggregate the tag |
| `/metrics` response is megabytes | too many series | reduce tags and/or `slo` buckets |
| Scrape times out | same | same, plus raise `scrape_timeout` while you fix it |
| Prometheus rejects samples | per-target series limit | reduce cardinality |
| Dashboard query is slow | too many combinations | aggregate with `sum by (…)` and drop unused tags |
| Series appeared after a deploy | a new tag or a new bounded value set | verify it is genuinely bounded |

To find the offender, sort the exposition by name:

```bash
curl -s http://localhost:8085/metrics | grep -v '^#' | cut -d'{' -f1 | sort | uniq -c | sort -rn | head -20
```

---

## References

- [metrics-reference.md](metrics-reference.md) — the real Kora 2.0 tag sets
- [custom-metrics-reference.md](custom-metrics-reference.md) — the meter-caching patterns
- [Prometheus naming and labels](https://prometheus.io/docs/practices/naming/#labels)
- [Micrometer concepts](https://docs.micrometer.io/micrometer/reference/concepts.html)
