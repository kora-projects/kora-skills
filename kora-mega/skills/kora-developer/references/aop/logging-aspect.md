# Kora method logging — distilled reference

**Source:** [.kora-agent/kora-docs/mkdocs/docs/en/documentation/logging-aspect.md](.kora-agent/kora-docs/mkdocs/docs/en/documentation/logging-aspect.md)  
**Examples:** `.kora-agent/kora-examples/kora-java-helloworld/`

Focused condensation of `kora-docs/.../documentation/logging-aspect.md`.

## Setup

`logging-common` is usually transitively pulled by other modules (`logging-logback`, `logging-slf4j`). If not:

```groovy
implementation "ru.tinkoff.kora:logging-common"
```

```java
@KoraApp
public interface Application extends LoggingModule, /* ... */ { }
```

Pair with a logging backend — `logging-logback` (default) or `logging-slf4j`.

## `@Log` family

| Annotation | Effect |
|-----------|--------|
| `@Log.in` | Log on method entry; includes args at TRACE/DEBUG |
| `@Log.out` | Log on method exit; includes return value at TRACE/DEBUG |
| `@Log.result` | Log only the return value (not the boundary marker on entry/exit) |
| `@Log` | Both — equivalent to `@Log.in` + `@Log.out` |
| `@Log.off` on parameter | Suppress this specific value in the log line |
| `@Log.off` on method | Suppress everything (when combined with `@Log.out` you still get the boundary marker) |

All in package `ru.tinkoff.kora.logging.common.annotation`.

## Output by level

For `@Log` on `methodWithArgs(String strParam, int numParam)` returning `"testResult"`:

| Log level | Output |
|-----------|--------|
| TRACE / DEBUG | `> {data: {strParam: "s", numParam: "4"}}` then `< {data: {out: "testResult"}}` |
| INFO | `>` then `<` (boundary markers only, no data) |
| WARN+ | nothing |

So `@Log` is safe to leave on hot-path methods in production at INFO level — you get traces but not PII or large payloads. Drop to DEBUG to see argument/result data.

## Selective field logging

```java
@Log                                                   // log args + result
public Order create(
    CreateOrderDto body,
    @Log.off String idempotencyKey                     // never logged
) {
    return ...;
}
```

Use `@Log.off` for credentials, tokens, large blobs, anything PII-tagged.

## MDC — Mapped Diagnostic Context

`@Mdc` attaches key/value pairs to **Kora's** MDC for the duration of the method call (or globally on the thread). Multiple `@Mdc` annotations on one method/parameter are supported.

> **Always use Kora's MDC, never SLF4J's.**
>
> - Annotation: `import ru.tinkoff.kora.logging.common.annotation.Mdc;` — there is no SLF4J equivalent.
> - Imperative: `import ru.tinkoff.kora.logging.common.MDC;` — **never** `import org.slf4j.MDC;`.
>
> SLF4J's stock `MDC` writes into a separate thread-local that `KoraAsyncAppender` does not propagate and `ConsoleTextRecordEncoder` does not render — values silently vanish from log output. IDE auto-import picks SLF4J by default; verify the import every time. Full callout in `../../kora-telemetry/references/logging-slf4j.md`.

| `@Mdc` parameter | Default | Meaning |
|------------------|---------|---------|
| `key` | parameter / method name | MDC key |
| `value` | parameter / argument value | MDC value (supports `${expr}` interpolation) |
| `global` | `false` | If `true`, stays on the thread after the method returns |

### Parameter annotation

```java
public Order create(@Mdc CreateOrderDto body) { ... }
// → MDC: "body" -> body.toString() for the duration of create()
```

```java
public Order create(@Mdc(key = "orderId") UUID orderId) { ... }
// → MDC: "orderId" -> orderId.toString()
```

### Method annotation

```java
@Mdc(key = "tenant", value = "${tenantId}")            // ${...} interpolates the param
@Mdc(key = "operation", value = "create-order")
public Order create(String tenantId, CreateOrderDto body) { ... }
```

`${expression}` references method parameters by name. You can call methods too:

```java
@Mdc(key = "requestId", value = "${java.util.UUID.randomUUID().toString()}")
public void process() { ... }
```

### Global MDC

```java
@Mdc(key = "tenant", value = "${tenantId}", global = true)
public void enterTenantContext(String tenantId) { ... }
```

After `enterTenantContext` returns, `tenant` remains in the MDC for the rest of the thread's lifetime (until cleared). Use sparingly — it's easy to leak context into unrelated work.

## Combined example

```java
@Log
@Mdc(key = "tenant", value = "${tenantId}")
@Mdc(key = "operation", value = "create")
public Order create(@Mdc String tenantId, @Log.off CreateOrderDto body) {
    // MDC: tenant, operation, tenantId
    // Log: arguments (tenantId only — body suppressed) on entry, return on exit
    return ...;
}
```

## Signatures

| Java | Kotlin |
|------|--------|
| `T method()` | `fun method(): T` |
| `Optional<T> method()` | — |
| `CompletionStage<T>` | `suspend fun method(): T` |
| `Mono<T>` / `Flux<T>` (with reactor-core) | `Flow<T>` (with coroutines) |

Java: class non-`final`. Kotlin: class `open`.

## Configuring backend (Logback)

The `@Log` aspect writes through SLF4J — your `logback.xml` controls format. Kora ships `ru.tinkoff.kora.logging.logback.ConsoleTextRecordEncoder` for structured text output (logfmt-style, includes MDC + structured args). It does **not** ship a built-in JSON encoder.

For JSON output ingestible by Loki / ELK / Datadog, pair Kora's `KoraAsyncAppender` with `logstash-logback-encoder`:

```groovy
implementation "net.logstash.logback:logstash-logback-encoder:7.4"
```

```xml
<appender name="STDOUT" class="ch.qos.logback.core.ConsoleAppender">
    <encoder class="net.logstash.logback.encoder.LogstashEncoder"/>
</appender>
<appender name="ASYNC" class="ru.tinkoff.kora.logging.logback.KoraAsyncAppender">
    <appender-ref ref="STDOUT"/>
</appender>
```

`KoraAsyncAppender` is mandatory wrapping for async logging — Kora's MDC and structured args don't propagate correctly through Logback's stock `AsyncAppender`.

## See also

- Parent `../SKILL.md`.
- `../../kora-telemetry/references/logging-slf4j.md` — backend choice and JSON encoder.
