# @RateLimited Reference

**Annotation:** `@RateLimited(X.class)` — `io.koraframework.resilient.ratelimiter.annotation.RateLimited`
**Spec:** `@RateLimiterSpec("<config path>")` on `interface X extends io.koraframework.resilient.ratelimiter.RateLimiter`
**Artifact:** `io.koraframework:resilient-kora`

> **New in Kora 2.0.** There is no 1.x equivalent to port.

## Contents

- [Basic Usage](#basic-usage)
- [Configuration](#configuration)
- [Algorithms](#algorithms)
- [Semantics](#semantics)
- [Supported Return Types](#supported-return-types)
- [Imperative Use](#imperative-use)
- [Telemetry](#telemetry)
- [Common Pitfalls](#common-pitfalls)

---

## Basic Usage

```java
@RateLimiterSpec("resilient.ratelimiter.notifications")
public interface NotificationRateLimiter extends RateLimiter {}
```

```java
@Component
public class NotificationSender {                // NOT final

    private final SmsGateway gateway;

    public NotificationSender(SmsGateway gateway) {
        this.gateway = gateway;
    }

    @RateLimited(NotificationRateLimiter.class)
    public void send(Notification notification) {
        gateway.send(notification);
    }
}
```

```kotlin
@RateLimiterSpec("resilient.ratelimiter.notifications")
interface NotificationRateLimiter : RateLimiter
```

```kotlin
@Component
open class NotificationSender(private val gateway: SmsGateway) {

    @RateLimited(NotificationRateLimiter::class)
    open fun send(notification: Notification) = gateway.send(notification)
}
```

One spec per limit. Every method annotated with the same spec class draws from the **same** permit
pool — which is how you enforce one shared quota across several call sites. Two spec interfaces
pointing at the same config path are two independent pools, each with the full allowance.

---

## Configuration

```hocon
resilient.ratelimiter.notifications {
  limitForPeriod = 100            # required — permits per period
  limitRefreshPeriod = "1s"       # required — the period
  type = TOKEN_BUCKET             # optional, default TOKEN_BUCKET; or FIXED_WINDOW
  enabled = true                  # optional, default true
}
```

Both `limitForPeriod` and `limitRefreshPeriod` are required and have no defaults; a missing one
fails at startup with
`ConfigValueException: Config expected value, but got null at path: 'ROOT.resilient.ratelimiter.notifications.limitForPeriod'`.

With `enabled = false` every `tryAcquire()` returns `true` and no permits are tracked.

---

## Algorithms

`RateLimiterConfig.type` (enum `RateLimiterConfig.RateLimiterType`) picks the algorithm;
`KoraRateLimiter` delegates to it. Both are lock-free, one CAS per call, in-memory.

| `type` | Behaviour | Pick it when |
|---|---|---|
| `TOKEN_BUCKET` (**default**) | GCRA token bucket. Refills continuously at `limitForPeriod / limitRefreshPeriod`; after an idle period up to `limitForPeriod` calls may pass at once (the burst), then calls are admitted one per `limitRefreshPeriod / limitForPeriod`. The bucket starts full. | the general case — smooth rate, bounded burst |
| `FIXED_WINDOW` | A counter per window. Windows are consecutive `limitRefreshPeriod` slices counted from the limiter's creation; the first `limitForPeriod` calls in a window pass, the rest are rejected until the next window. Unused permits do not carry over. | you want a literal "N per period" quota and accept that a burst straddling a window boundary can pass up to `2 * limitForPeriod` calls |

`FIXED_WINDOW` packs the counter into 24 bits, so `limitForPeriod` must stay below 2^24 (16 777 216).

---

## Semantics

- When no permit is available `acquire()` throws
  `RateLimitExceededException("RateLimiter 'X' rate limit exceeded")`, where `X` is the spec
  interface's **simple name**.
- **Callers never wait.** `acquire()` fails fast under both algorithms; there is no blocking or
  queueing variant. If you need to smooth traffic rather than reject it, pair `@RateLimited` with
  `@Retryable` (outermost) so a rejected call is retried after a delay.
- The limiter is **per process** — each JVM has its own bucket. For one quota across all instances
  use `@RateLimiterDistributedSpec`; see [distributed-reference.md](distributed-reference.md).
- `toString()` of the injected spec reports the algorithm and live state, e.g.
  `TokenBucketKoraRateLimiter{name='NotificationRateLimiter', enabled=true, limitForPeriod=100, availablePermits=37}`
  (`FixedWindowKoraRateLimiter{…, availablePermissions=…}` for the fixed window). Log it when
  debugging; do not parse it.

The aspect wraps the body as `acquire()` → body, so a rejected call never reaches the method.

---

## Supported Return Types

`@RateLimited` is the most restrictive of the five aspects:

| Return type | Java | Kotlin |
|---|---|---|
| `T`, `T?`, `void` / `Unit` | yes | yes |
| `Flow<T>` | n/a | yes — the permit is taken when collection starts |
| `suspend fun` | n/a | yes — the synchronous body is emitted into a `suspend` helper; `acquire()` never blocks, so there is no coroutine-specific path |
| `CompletionStage<T>` / `CompletableFuture<T>` | **no** | **no** |
| `Future<T>`, `Mono<T>`, `Flux<T>` | no | no |

`CompletionStage` is the one shape the other four Java aspects accept and `@RateLimited` does not.

Unsupported shapes fail the build with
`@RateLimited cannot be applied to '<Class>#<method>()' because return type '…' is not supported by this aspect.`

---

## Imperative Use

Inject the spec interface — it is a graph component:

```java
@Component
public final class BulkSender {

    private final NotificationRateLimiter rateLimiter;

    public BulkSender(NotificationRateLimiter rateLimiter) {
        this.rateLimiter = rateLimiter;
    }

    public void sendAll(List<Notification> batch) {
        for (var notification : batch) {
            if (!rateLimiter.tryAcquire()) {   // no exception, just a boolean
                deferred.add(notification);
                continue;
            }
            gateway.send(notification);
        }
    }
}
```

`RateLimiter` offers `tryAcquire()` (boolean), `acquire()` (throws), and
`execute(ThrowableRunnable)` / `execute(ThrowableCallable)`.

---

## Telemetry

Off by default. One counter, tagged `resilient.name` = the config path given to `@RateLimiterSpec` and
`resilient.status` = `acquired` / `rejected`:

| Metric | Meaning |
|---|---|
| `resilient.ratelimiter.acquire` | one increment per acquire attempt, recording whether a permit was granted |

```hocon
resilient.telemetry.rateLimiter {
  logging.enabled = true
  metrics.enabled = true
}
```

---

## Common Pitfalls

| Problem | Cause / fix |
|---|---|
| `must extend io.koraframework.resilient.ratelimiter.RateLimiter` | Spec interface missing its base type. |
| Aspect rejects a `CompletionStage` method | `@RateLimited` is the only aspect that refuses it in Java; use a synchronous signature. |
| Two call sites each get the full quota | Duplicate spec interfaces on one config path — share a single spec. |
| Callers block instead of failing | They do not; `acquire()` fails fast. Add `@Retryable` outside `@RateLimited` if you want waiting. |
| Twice the expected rate at a window edge | `type = FIXED_WINDOW` allows that by design; use the default `TOKEN_BUCKET` for a smooth rate. |
| `limitForPeriod` calls pass instantly, then one per interval | That is the `TOKEN_BUCKET` burst; lower `limitForPeriod` and `limitRefreshPeriod` together to shrink the burst while keeping the rate. |
| Limit not applied across instances | `@RateLimiterSpec` is per process. Use `@RateLimiterDistributedSpec` — [distributed-reference.md](distributed-reference.md). |

---

## See Also

- [retry-reference.md](retry-reference.md) — retrying a rejected call
- [distributed-reference.md](distributed-reference.md) — Redis-backed limiter shared across instances
- [resilience-config-reference.md](resilience-config-reference.md) — full `resilient.*` key set
