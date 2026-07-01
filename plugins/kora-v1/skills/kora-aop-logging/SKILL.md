---
name: kora-aop-logging
description: "Declarative method logging in Kora via the logging-common module — @Log (args + result), @Log.in / @Log.out / @Log.result, @Log.off to suppress a parameter or method, and @Mdc for Mapped Diagnostic Context (key/value, ${expr} interpolation, global thread scope). Covers the imperative ru.tinkoff.kora.logging.common.MDC API and the SLF4J-MDC import pitfall. Use when adding entry/exit logging to a service method, enriching logs with contextual keys, hiding sensitive arguments from log output, or wiring LoggingModule into a @KoraApp."
---

# Kora AOP Logging — `@Log` and `@Mdc`

Declarative, compile-time method logging. The annotation processor generates a `*Aspect` class around your method; there is no reflection or runtime proxy. The aspect writes through SLF4J, so your Logback configuration controls the final format.

Use this skill when you need to:
- log method entry/exit with arguments and return value (`@Log`),
- enrich every log line of a call with contextual keys (`@Mdc`),
- suppress credentials or large payloads from log output (`@Log.off`),
- wire `LoggingModule` into a `@KoraApp`.

## Quick Start

### 1. Dependencies

`logging-common` is usually pulled transitively by a logging backend (`logging-logback`). Add it explicitly only if it is missing. All Kora artifacts inherit their version from the `kora-parent` BOM — never pin an individual `ru.tinkoff.kora:*` version.

```groovy
dependencies {
    koraBom platform("ru.tinkoff.kora:kora-parent:1.2.17")

    // Mandatory: without the annotation processor no aspect is generated
    annotationProcessor "ru.tinkoff.kora:annotation-processors"

    implementation "ru.tinkoff.kora:logging-logback" // pulls logging-common transitively
}
```

Kotlin replaces the processor with KSP:

```groovy
ksp "ru.tinkoff.kora:symbol-processors"
implementation "ru.tinkoff.kora:logging-logback"
```

### 2. Enable in the application graph

```java
@KoraApp
public interface Application extends LoggingModule { }
```

### 3. Log a method

The enclosing class must be non-`final` (Java) / `open` (Kotlin) so the aspect can subclass it.

```java
@Component
public class UserService {          // NOT final

    @Log
    public User getUser(String id) {
        return userRepository.findById(id);
    }
}
```

### 4. Enrich with MDC

```java
@Log
public User getUser(@Mdc(key = "userId") String id) {
    return userRepository.findById(id); // every log line in this call carries userId=<id>
}
```

---

## `@Log` family

All annotations live in `ru.tinkoff.kora.logging.common.annotation`.

| Annotation | Effect |
|-----------|--------|
| `@Log` | Log on entry and exit |
| `@Log.in` | Log on method entry only |
| `@Log.out` | Log on method exit only |
| `@Log.result` | Log the return value only |
| `@Log.off` on a **parameter** | Suppress that one value in the log line |
| `@Log.off` on a **method** | Suppress all logging for the method |

### Choosing the level

`@Log`, `@Log.in`, and `@Log.out` accept the level as the **annotation value** — the attribute is `value`, not `level`, and the type is `org.slf4j.event.Level`.

```java
import org.slf4j.event.Level;

@Log(Level.DEBUG)            // value attribute, not level =
public User getUser(String id) { ... }
```

Default level is `INFO` for `@Log`/`@Log.in`/`@Log.out` and `DEBUG` for `@Log.result`.

There is **no `Level.OFF`** — `org.slf4j.event.Level` only has `TRACE`, `DEBUG`, `INFO`, `WARN`, `ERROR`. To disable logging for a method, use `@Log.off` (not a level).

### Output by configured logger level

For `@Log` on `methodWithArgs(String strParam, int numParam)` returning `"testResult"`, the actual output depends on the **logger level** configured in `logback.xml` for that class:

| Logger level | Output |
|--------------|--------|
| `TRACE` / `DEBUG` | `> {data: {strParam: "s", numParam: "4"}}` then `< {data: {out: "testResult"}}` |
| `INFO` | `>` then `<` (boundary markers only, no argument or result data) |
| `WARN`+ | nothing |

So `@Log` is safe on hot-path methods in production at `INFO` — you get execution traces with no PII or large payloads. Drop the logger to `DEBUG` to see argument/result data.

---

## `@Mdc` — Mapped Diagnostic Context

`@Mdc` attaches key/value pairs to Kora's MDC for the duration of the method call (or, with `global = true`, for the rest of the thread's life). The annotation is `@Repeatable`, so multiple `@Mdc` on one method/parameter are allowed.

| `@Mdc` attribute | Default | Meaning |
|------------------|---------|---------|
| `key` | annotated parameter / method name | MDC key |
| `value` | annotated parameter's runtime value | MDC value; supports `${expr}` interpolation |
| `global` | `false` | If `true`, the value stays on the thread after the method returns |

### On a parameter

```java
public Order create(@Mdc UUID orderId) { ... }            // key = "orderId", value = orderId.toString()
public Order create(@Mdc(key = "order_id") UUID id) { ... } // explicit key
```

### On a method (with interpolation)

`${expression}` references method parameters by name and can call methods.

```java
@Mdc(key = "tenant", value = "${tenantId}")
@Mdc(key = "requestId", value = "${java.util.UUID.randomUUID().toString()}")
public Order create(String tenantId, CreateOrderDto body) { ... }
```

### Global MDC

```java
@Mdc(key = "tenant", value = "${tenantId}", global = true)
public void enterTenantContext(String tenantId) { ... }
```

After the method returns, `tenant` remains in the MDC for the rest of the thread's life. Use sparingly — global keys leak into unrelated work on a pooled thread. Remove them imperatively with the static `MDC.remove("tenant")` when the unit of work ends.

### Imperative API

Kora's imperative MDC is `ru.tinkoff.kora.logging.common.MDC` (static methods):

```java
import ru.tinkoff.kora.logging.common.MDC;

MDC.put("userId", "42");   // also overloads for Integer, Long, Boolean, StructuredArgumentWriter
MDC.remove("userId");
MDC.get();                 // current MDC instance
```

> **Never import `org.slf4j.MDC`.** SLF4J's stock MDC writes into a different thread-local that `KoraAsyncAppender` does not propagate and Kora's encoder does not render — values silently vanish. IDE auto-import picks the SLF4J one by default; verify the import on every `MDC` usage. There is no `MDC.wrap(...)` / `MDC.clear()` in Kora's API.

---

## Combined example

```java
@Component
public class OrderService {                       // NOT final

    @Log                                          // entry + exit
    @Mdc(key = "tenant", value = "${tenantId}")
    @Mdc(key = "operation", value = "create-order")
    public Order create(
        @Mdc String tenantId,                     // value lands in MDC as tenantId
        @Log.off CreateOrderDto body              // body never appears in log output
    ) {
        return repository.save(body.toEntity());
    }
}
```

MDC keys present during the call: `tenant`, `operation`, `tenantId`. The log line shows `tenantId` (and the boundary markers); `body` is suppressed.

---

## Supported signatures

| Java | Kotlin |
|------|--------|
| `T myMethod()` | `fun myMethod(): T` (or `T?`, `Unit`) |
| `Optional<T> myMethod()` | — |
| `CompletionStage<T> myMethod()` | `suspend fun myMethod(): T` |
| `Mono<T>` / `Flux<T>` (needs `io.projectreactor:reactor-core`) | `Flow<T>` (needs `kotlinx-coroutines-core`) |

Java class must be non-`final`; Kotlin class must be `open`.

---

## Common pitfalls

| Symptom | Fix |
|---------|-----|
| `@Log` compiles but nothing is logged | The class is `final` (Java) / not `open` (Kotlin), or the annotation processor / KSP is missing |
| MDC values never appear in output | `org.slf4j.MDC` imported instead of `ru.tinkoff.kora.logging.common.MDC` |
| `@Log(level = ...)` does not compile | The attribute is `value`, not `level`: write `@Log(Level.DEBUG)` |
| Looking for `Level.OFF` | It does not exist; use `@Log.off` to disable a method |
| Want full args but see only `>` / `<` | The logger level for that class is `INFO`; set it to `DEBUG` in `logback.xml` |
| Sensitive argument leaks into logs | Add `@Log.off` to that parameter |
| Global MDC bleeds across requests | Avoid `global = true`, or remove the key with the static `MDC.remove(key)` at the end of the unit of work |

---

## References

- [logging-aspect.md](references/logging-aspect.md) — full `@Log` / `@Mdc` / level reference distilled from the docs
- [logging-mdc.md](references/logging-mdc) — MDC patterns, interpolation, global scope, imperative API
- [logging-performance.md](references/logging-performance.md) — production tuning, `KoraAsyncAppender`, suppressing large payloads

## Assets

- `assets/LoggedService.java.template`, `assets/LoggedService.kt.template` — runnable `@Log` + `@Mdc` service templates. See [assets/README.md](assets/README.md).
