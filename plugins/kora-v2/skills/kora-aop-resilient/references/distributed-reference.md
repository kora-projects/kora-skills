# Distributed Rate Limiter and Retry Budget Reference

**Spec:** `@RateLimiterDistributedSpec("<config path>")` on `interface X extends io.koraframework.resilient.ratelimiter.RateLimiter`
— `io.koraframework.resilient.distributed.ratelimiter.annotation.RateLimiterDistributedSpec`
**Artifacts:** `io.koraframework:resilient-kora-distributed` (API) · `io.koraframework:resilient-kora-distributed-redis-lettuce` (Redis backend)
**Module:** `io.koraframework.resilient.distributed.LettuceDistributedResilientModule`

`@RateLimiterSpec` and the default retry budget keep their state in the JVM, so N instances of a
service get N quotas. The distributed variants keep the state in Redis and enforce **one** quota /
budget across every instance that shares the Redis keys.

## Contents

- [Setup](#setup)
- [Distributed Rate Limiter](#distributed-rate-limiter)
- [Configuration](#configuration)
- [Semantics](#semantics)
- [Distributed Retry Budget](#distributed-retry-budget)
- [Other Backends and Other Redis Instances](#other-backends-and-other-redis-instances)
- [Telemetry](#telemetry)
- [Testing](#testing)
- [Common Pitfalls](#common-pitfalls)

---

## Setup

```groovy
dependencies {
    koraBom platform("io.koraframework:kora-bom:$koraVersion")   // koraVersion=2.0.0.RC2
    annotationProcessor "io.koraframework:annotation-processors" // Kotlin: ksp "io.koraframework:symbol-processors"

    implementation "io.koraframework:resilient-kora"
    implementation "io.koraframework:resilient-kora-distributed-redis-lettuce"
}
```

`resilient-kora-distributed-redis-lettuce` brings `resilient-kora-distributed` and `redis-lettuce`
transitively. Depend on `resilient-kora-distributed` alone only when you supply your own backend
clients (see [Other Backends](#other-backends-and-other-redis-instances)).

```java
@KoraApp
public interface Application extends
        HoconConfigModule,
        LogbackModule,
        ResilientModule,
        LettuceDistributedResilientModule { }
```

```kotlin
@KoraApp
interface Application : HoconConfigModule, LogbackModule, ResilientModule, LettuceDistributedResilientModule
```

`ResilientModule` is still required — the distributed spec reuses its telemetry factory and
`ResilientConfig`. `LettuceDistributedResilientModule` extends `LettuceModule`, so the Redis
connection is the standard `lettuce` config section (`lettuce.uri` is required). One URI gives a
standalone `RedisClient`; a comma-separated URI list or `forceClusterClient = true` gives a
`RedisClusterClient`; both are supported. The driver keys are documented in
[kora-aop-caching → cache-redis-reference.md](../../kora-aop-caching/references/cache-redis-reference.md#the-lettuce-driver-section).
Combining it with `LettuceRedisCacheModule` is fine — both share the one `LettuceModule` client.

---

## Distributed Rate Limiter

Swap the spec annotation; everything else stays the same. The generated implementation extends
`KoraDistributedRateLimiter` and implements your interface, so it is a drop-in `RateLimiter`:
`@RateLimited(X.class)`, `tryAcquire()`, `acquire()` and `execute(…)` work unchanged, in Java and in
Kotlin (KSP).

```java
@RateLimiterDistributedSpec("resilient.ratelimiter.partner-api")
public interface PartnerApiRateLimiter extends RateLimiter {}

@Component
public class PartnerClient {                     // NOT final

    @RateLimited(PartnerApiRateLimiter.class)
    public Quote quote(String sku) { … }
}
```

```kotlin
@RateLimiterDistributedSpec("resilient.ratelimiter.partner-api")
interface PartnerApiRateLimiter : RateLimiter

@Component
open class PartnerClient {

    @RateLimited(PartnerApiRateLimiter::class)
    open fun quote(sku: String): Quote = …
}
```

Supported return types are those of `@RateLimited` — see
[rate-limiter-reference.md](rate-limiter-reference.md#supported-return-types).

**One spec = one Redis key.** There is no per-key (per-tenant, per-user) limiter in the framework:
the key is fixed at `<keyPrefix>:<SpecSimpleName>`, and every instance using that spec with the same
`keyPrefix` shares the quota.

---

## Configuration

`DistributedRateLimiterConfig` — note the algorithm key is **`algorithm`**, not `type` as on the
local limiter:

```hocon
resilient.ratelimiter.partner-api {
  limitForPeriod = 50          # required
  limitRefreshPeriod = "1s"    # required
  keyPrefix = "orders-service" # required — namespaces the Redis keys
  algorithm = TOKEN_BUCKET     # optional, default TOKEN_BUCKET; or FIXED_WINDOW
  enabled = true               # optional, default true
}
```

| Key | Type | Default | Notes |
|---|---|---|---|
| `enabled` | boolean | `true` | `false` grants every call without touching Redis |
| `limitForPeriod` | int | **required** | permits per period |
| `limitRefreshPeriod` | Duration | **required** | the period; millisecond resolution |
| `keyPrefix` | String | **required** | first segment of every Redis key |
| `algorithm` | enum | `TOKEN_BUCKET` | `TOKEN_BUCKET`, `FIXED_WINDOW` |
| `telemetry.*` | object | inherits `resilient.telemetry.rateLimiter` | same shape as the local limiter |

---

## Semantics

No Lua scripts: both algorithms use plain `INCR` / `INCRBY` / `PEXPIRE` / `SET … PX` over a
synchronous connection, so every `acquire()` is a Redis round trip.

| `algorithm` | Redis state | Behaviour |
|---|---|---|
| `TOKEN_BUCKET` | one key `<keyPrefix>:<Spec>` holding the GCRA theoretical arrival time in epoch ms, TTL ≈ `limitRefreshPeriod`, refreshed on every write | continuous refill with a burst of `limitForPeriod`; a rejected call refunds its slot. `now` is each caller's wall clock, so accuracy depends on clock sync between instances |
| `FIXED_WINDOW` | one key per window, `<keyPrefix>:<Spec>:<epochMillis / windowMillis>`, TTL = window | windows are aligned to the epoch; quota per window, up to `2 * limitForPeriod` across a boundary |

- An exceeded limit throws `RateLimitExceededException` exactly like the local limiter — callers never
  wait.
- A Redis error is **not** turned into a permit: the Lettuce exception propagates out of
  `tryAcquire()` / the aspect, so the protected call fails while Redis is unreachable. Put
  `@Fallback` above `@RateLimited` if the call must degrade instead.
- `toString()` reports the algorithm, key and limits (`TokenBucketRateLimiter{name=…, keyBase=…, limitForPeriod=…, windowMillis=…}`);
  it does not query Redis.

---

## Distributed Retry Budget

`DistributedRetryBudgetFactory` (`io.koraframework.resilient.distributed.retry`) is a
`RetryBudgetFactory` whose budgets live in Redis. It is **not** registered by any module — build it
from the `DistributedRetryBudgetClient` that `LettuceDistributedResilientModule` supplies, and
register it with the retry spec's tag (see
[retry-reference.md](retry-reference.md#where-the-budget-comes-from) for the lookup order):

```java
@Module
public interface DistributedRetryBudgetModule {

    @Tag(PartnerRetry.class)
    default RetryBudgetFactory partnerRetryBudget(DistributedRetryBudgetClient client) {
        return new DistributedRetryBudgetFactory(client, "orders-service:retrybudget", Duration.ofMinutes(10));
    }
}
```

```kotlin
@Module
interface DistributedRetryBudgetModule {

    @Tag(PartnerRetry::class)
    fun partnerRetryBudget(client: DistributedRetryBudgetClient): RetryBudgetFactory =
        DistributedRetryBudgetFactory(client, "orders-service:retrybudget", Duration.ofMinutes(10))
}
```

Declare the method with return type `RetryBudgetFactory`. Leave out `@Tag` to replace the default
factory for **every** retry. The one-argument constructor uses key prefix `kora:retrybudget` and a
10-minute key TTL.

- The factory still reads the spec's `retryBudget` block and returns no budget when it is absent or
  `enabled = false` — keep the block.
- Key: `<keyPrefix>:<RetrySpecSimpleName>`, a floating-point token balance seeded with
  `tokensInitial`. A retry withdraws one token (refunded and denied if the balance goes negative);
  a success deposits `ratio`, clamped back to `tokensMax` on a best-effort basis.
- `minTokensPerSecond` is **ignored** — the distributed balance is driven only by successes and
  retries.
- Every write refreshes the TTL; a budget idle for longer than the TTL expires and restarts at
  `tokensInitial`.
- `availableTokens()` and a denied retry behave as for the local budget: the original exception
  propagates and `resilient.retry.exhausted` is tagged `resilient.reason=EXHAUSTED_BUDGET`.

---

## Other Backends and Other Redis Instances

`LettuceDistributedResilientModule` registers everything as `@DefaultComponent`, so your own
component of the same type wins:

| Override | Effect |
|---|---|
| `DistributedRateLimiterClient` component | a different store for the rate limiter (`incrementAndExpire`, `addAndExpire`, `set`) |
| `DistributedRetryBudgetClient` component | a different store for the retry budget (`addAndGet`, `get`) |
| `AbstractRedisClient` tagged `@Tag(LettuceDistributedResilientModule.class)` | point the distributed clients at a Redis other than the `lettuce` section's |

The Lettuce clients open their connection in `init()` and accept only `RedisClient` or
`RedisClusterClient`; any other `AbstractRedisClient` fails graph start with
`UnsupportedOperationException`.

---

## Telemetry

Same as the local limiter: counter `resilient.ratelimiter.acquire`, tag `resilient.name` = the config path of
the spec, enabled under `resilient.telemetry.rateLimiter` or `<specPath>.telemetry`. Off by default.
The distributed retry budget reports through the retry's own metrics.

---

## Testing

The graph needs a `DistributedRateLimiterClient` for every `@RateLimiterDistributedSpec`. Either run
Redis (Testcontainers) and set `lettuce.uri`, or register an in-memory fake `@Component` that
implements `DistributedRateLimiterClient` — the framework's own processor tests do the latter with a
`ConcurrentHashMap` and `merge`.

---

## Common Pitfalls

| Problem | Cause / fix |
|---|---|
| `Config expected value, but got null at path: '….keyPrefix'` | `keyPrefix` is required for a distributed spec. |
| `type = FIXED_WINDOW` has no effect | Distributed specs read `algorithm`, not `type`. |
| No component found for `DistributedRateLimiterClient` | `LettuceDistributedResilientModule` not on the `@KoraApp`, or the lettuce artifact missing. |
| Two services throttle each other | Same `keyPrefix` and same spec simple name → same Redis key. Give each service its own prefix. |
| Need a limit per user / tenant | Not provided — one key per spec. Keep per-key limiting in your own code. |
| `cannot find symbol: DistributedRateLimiterFactory` | There is no such class and no per-key API; the distributed limiter is only the spec-based one. |
| Calls fail when Redis is down | Redis errors propagate; add `@Fallback` or accept fail-closed. |
| Distributed retry budget never denies | No `retryBudget` block on the retry section — the factory returns no budget without it. |
| Retry budget still per JVM | The `DistributedRetryBudgetFactory` method is missing `@Tag(<RetrySpec>.class)` for that retry (or is not declared as `RetryBudgetFactory`). |
| Budget refills over time locally but not in Redis | `minTokensPerSecond` is not supported by the distributed budget. |

---

## See Also

- [rate-limiter-reference.md](rate-limiter-reference.md) — local limiter, algorithms, return types
- [retry-reference.md](retry-reference.md) — `RetryBudget`, `RetryBudgetFactory`, lookup order
- [resilience-config-reference.md](resilience-config-reference.md) — full `resilient.*` key set
