# @Timeout Reference

**Annotation:** `@Timeout(X.class)` — `io.koraframework.resilient.timeout.annotation.Timeout`
**Spec:** `@TimeoutSpec("<config path>")` on `interface X extends io.koraframework.resilient.timeout.Timeouter`
**Artifact:** `io.koraframework:resilient-kora`

> The annotation kept its 1.x name but **changed its attribute type**: `String value()` became
> `Class<? extends Timeouter> value()`. The runtime contract is spelled `Timeouter`, not `Timeout`.

## Contents

- [Basic Usage](#basic-usage)
- [Configuration](#configuration)
- [Execution Model](#execution-model)
- [Combining with Retry](#combining-with-retry)
- [Imperative Use](#imperative-use)
- [Telemetry](#telemetry)
- [Common Pitfalls](#common-pitfalls)

---

## Basic Usage

```java
@TimeoutSpec("resilient.timeout.report")
public interface ReportTimeouter extends Timeouter {}
```

```java
@Component
public class ReportService {                     // NOT final

    private final ReportEngine engine;

    public ReportService(ReportEngine engine) {
        this.engine = engine;
    }

    @Timeout(ReportTimeouter.class)
    public Report generate(ReportRequest request) {
        return engine.generate(request);
    }
}
```

```kotlin
@TimeoutSpec("resilient.timeout.report")
interface ReportTimeouter : Timeouter
```

```kotlin
@Component
open class ReportService(private val engine: ReportEngine) {

    @Timeout(ReportTimeouter::class)
    open fun generate(request: ReportRequest): Report = engine.generate(request)
}
```

Because the identity is the spec type, a "timeout tier" shared by many services is one interface
reused everywhere rather than a string repeated in annotations:

```java
@TimeoutSpec("resilient.timeout.fast")     public interface FastTimeouter extends Timeouter {}
@TimeoutSpec("resilient.timeout.standard") public interface StandardTimeouter extends Timeouter {}
@TimeoutSpec("resilient.timeout.slow")     public interface SlowTimeouter extends Timeouter {}
```

---

## Configuration

```hocon
resilient.timeout.report {
  duration = "30s"   # required
  enabled = true     # optional, default true
}
```

`duration` is the only required key and has no default; a missing one fails startup with
`ConfigValueException: Config expected value, but got null at path: 'ROOT.resilient.timeout.report.duration'`.
With `enabled = false` the aspect calls straight through and never starts a timer.

**Named sections do not inherit `resilient.timeout.default`.**

---

## Execution Model

`KoraTimeouter` does **not** time the calling thread. It submits the method body to a
per-timeouter virtual-thread executor (`Thread.ofVirtual().name("timeout-<SpecSimpleName>-", 1)`)
and waits `duration` on the resulting future. Consequences worth knowing:

- On expiry the future is cancelled with `mayInterruptIfRunning = true`, so the worker thread is
  **interrupted**, and `TimeoutExhaustedException` is thrown to the caller with the message
  `Timeout exceeded <duration>` and `name()` = the spec interface's simple name.
- Interruption only stops work that observes it. A tight CPU loop or a blocking call that ignores
  interrupts keeps running after the caller has already received the exception — side effects can
  still land. Check `Thread.currentThread().isInterrupted()` in long loops, and let
  `InterruptedException` propagate rather than swallowing it.
- The body runs on a *different* thread from the caller. Anything thread-affine in the method body
  (a thread-local, a thread-bound transaction) does not carry over.
- An exception thrown by the body before the deadline is rethrown unchanged, including checked
  exceptions — a `throws IOException` method still throws `IOException`, not a wrapper.

```java
@Timeout(SlowTimeouter.class)
public Result longOperation() {
    for (int i = 0; i < 1_000_000; i++) {
        if (Thread.currentThread().isInterrupted()) {
            return Result.cancelled();
        }
        processStep(i);
    }
    return Result.success();
}
```

### Kotlin `suspend` and `Flow`

For a `suspend` function the aspect uses `kotlinx.coroutines.withTimeout(duration)` instead of the
executor, converting `TimeoutCancellationException` into `TimeoutExhaustedException` — proper
cooperative cancellation, no separate thread. For a `Flow` the deadline is checked between
emissions, so the timeout bounds the whole stream rather than a single item.

`@Timeout` rejects `CompletionStage`/`CompletableFuture` in **Kotlin**; in Java it wraps them with
`orTimeout(...)`.

---

## Combining with Retry

Declaration order decides nesting: **first-listed is outermost, last-listed is innermost.**

### Per-attempt bound (usual choice)

```java
@Retryable(SearchRetry.class)     // outer
@Timeout(SearchTimeouter.class)   // inner — bounds ONE attempt
public List<SearchResult> search(String query) {
    return searchEngine.search(query);
}
```

```hocon
resilient {
  retry.search   { attempts = 3, delay = "50ms" }
  timeout.search { duration = "2s" }
}
```

Worst case ≈ `(attempts + 1) * duration` plus the retry delays: 4 × 2s + 150ms.

### Overall budget

```java
@Timeout(PaymentTimeouter.class)  // outer — bounds the whole chain
@Retryable(PaymentRetry.class)    // inner
public PaymentResult charge(PaymentRequest request) { … }
```

```hocon
resilient {
  timeout.payment { duration = "10s" }
  retry.payment   { attempts = 3, delay = "100ms" }
}
```

Make the budget larger than the retry schedule can consume, or the later attempts never run.

---

## Imperative Use

`TimeoutManager` does not exist in 2.0. Inject the spec interface:

```java
@Component
public final class ReportJob {

    private final ReportTimeouter timeouter;

    public ReportJob(ReportTimeouter timeouter) {
        this.timeouter = timeouter;
    }

    public Report generate(ReportRequest request) {
        return timeouter.execute(() -> engine.generate(request));
    }
}
```

`Timeouter` offers `execute(ThrowableRunnable)`, `execute(ThrowableCallable)` and
`timeout()` returning the configured `Duration`.

---

## Telemetry

Off by default. One counter, tagged `resilient.name` = the config path given to `@TimeoutSpec`:

| Metric | Meaning |
|---|---|
| `resilient.timeout.exhausted` | the deadline expired |

Enable under `resilient.telemetry.timeout`, or per spec under `<specPath>.telemetry`.

---

## Common Pitfalls

| Problem | Cause / fix |
|---|---|
| `String cannot be converted to Class<? extends Timeouter>` | Un-migrated `@Timeout("name")` — the classic symptom of a half-finished migration. |
| `must extend io.koraframework.resilient.timeout.Timeouter` | Spec extends `Timeout` (the annotation) instead of `Timeouter`. |
| Timeout never fires | `enabled = false`, or the work finishes inside `duration`. |
| Work continues after the exception | The body ignores interruption; check `Thread.currentThread().isInterrupted()`. |
| Thread-local / transaction missing inside the method | The body runs on a separate virtual thread. |
| Retries never all run | `@Timeout` placed outside `@Retryable` with too small a budget. |
| Aspect rejects the method in Kotlin | `CompletionStage`/`CompletableFuture` are unsupported in Kotlin; use `suspend` or a sync signature. |

---

## See Also

- [retry-reference.md](retry-reference.md) — attempt counting and delay schedules
- [circuit-breaker-reference.md](circuit-breaker-reference.md) — stop calling a timing-out dependency
- [resilience-config-reference.md](resilience-config-reference.md) — full `resilient.*` key set
