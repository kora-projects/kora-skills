# Kora MDC reference — `@Mdc` and the imperative API

**Source:** `.kora-agent/kora-docs/mkdocs/docs/en/documentation/logging-aspect.md`
**Annotation source of truth:** `ru.tinkoff.kora.logging.common.annotation.Mdc`, `ru.tinkoff.kora.logging.common.MDC`

## Contents

- [Import warning](#import-warning)
- [`@Mdc` attributes](#mdc-attributes)
- [Parameter-level `@Mdc`](#parameter-level-mdc)
- [Method-level `@Mdc` and interpolation](#method-level-mdc-and-interpolation)
- [Global MDC](#global-mdc)
- [Imperative `MDC` API](#imperative-mdc-api)
- [Combined `@Log` + `@Mdc`](#combined-log--mdc)
- [Pitfalls](#pitfalls)

## Import warning

Always use Kora's MDC, never SLF4J's:

```java
import ru.tinkoff.kora.logging.common.annotation.Mdc; // annotation — CORRECT
import ru.tinkoff.kora.logging.common.MDC;            // imperative API — CORRECT
// import org.slf4j.MDC;                               // WRONG — values are lost
```

SLF4J's `org.slf4j.MDC` writes into a different thread-local that `KoraAsyncAppender` does not propagate and Kora's `ConsoleTextRecordEncoder` does not render — values silently disappear from output. IDE auto-import picks the SLF4J one by default; verify the import every time you reference `MDC`.

## `@Mdc` attributes

`@Mdc` is `@Repeatable` (multiple annotations allowed on a method or parameter).

| Attribute | Default | Meaning |
|-----------|---------|---------|
| `key` | annotated parameter / method name | MDC key |
| `value` | annotated parameter's runtime value | MDC value; supports `${expr}` interpolation |
| `global` | `false` | If `true`, the value stays on the thread after the method returns |

## Parameter-level `@Mdc`

### Default key (parameter name)

```java
@Log
public Order create(@Mdc String orderId) {
    // MDC: "orderId" -> orderId
    return repository.save(orderId);
}
```

### Custom key

```java
@Log
public Order create(@Mdc(key = "order_id") String orderId) {
    // MDC: "order_id" -> orderId
}
```

### Multiple parameters

```java
@Log
public Order create(
    @Mdc(key = "orderId") String orderId,
    @Mdc(key = "userId") String userId,
    @Mdc(key = "amount") BigDecimal amount
) {
    // MDC: orderId, userId, amount
}
```

### Whole object

```java
@Log
public void process(@Mdc User user) {
    // MDC: "user" -> user.toString()
}
```

## Method-level `@Mdc` and interpolation

### Static value

```java
@Mdc(key = "operation", value = "create-order")
@Log
public Order create(CreateOrderDto request) { ... }
```

### Parameter interpolation

`${expression}` references method parameters by name.

```java
@Mdc(key = "tenant", value = "${tenantId}")
@Log
public Order create(String tenantId, CreateOrderDto request) {
    // MDC: tenant=<value of tenantId>
}
```

### Generated values

The expression may call methods, including static factories:

```java
@Mdc(key = "requestId", value = "${java.util.UUID.randomUUID().toString()}")
@Log
public Response process(Request request) {
    // MDC: requestId=<random UUID>
}
```

### Multiple method annotations

```java
@Mdc(key = "tenant", value = "${tenantId}")
@Mdc(key = "operation", value = "create-order")
@Mdc(key = "service", value = "order-service")
@Log
public Order create(String tenantId, CreateOrderDto request) {
    // MDC: tenant, operation, service
}
```

Example log line combining `@Log` and `@Mdc` (DEBUG logger level):

```
INFO [main] r.t.e.e.Example.test: > {data: {s: "testValue"}} key=some-uuid-value key1=value2 123=testValue
```

## Global MDC

```java
@Mdc(key = "tenant", value = "${tenantId}", global = true)
@Log
public void enterTenantContext(String tenantId) {
    // tenant persists on the thread after this method returns
}
```

`global = true` keeps the key on the thread beyond the method call. On pooled threads (HTTP, Kafka), an uncleared global key leaks into the next unrelated unit of work. Prefer method-scoped `@Mdc` (auto-removed when the method returns). When you do need a global key, remove it imperatively at the end of the unit of work:

```java
MDC.remove("tenant");
```

## Imperative `MDC` API

`ru.tinkoff.kora.logging.common.MDC` exposes static helpers:

```java
import ru.tinkoff.kora.logging.common.MDC;

MDC.put("userId", "42");      // overloads: String, Integer, Long, Boolean, StructuredArgumentWriter
MDC.remove("userId");         // static remove
MDC mdc = MDC.get();          // current MDC instance (for reading values())
```

There is **no `MDC.wrap(...)`, `MDC.clear()`, or `MDC.getContext()`** in Kora's API — do not write them. To propagate MDC into a manually-spawned thread, capture the values you need before the hop and re-`put` them inside, or rely on Kora's own context propagation in the supported async signatures (`CompletionStage`, `Mono`/`Flux`, `suspend`/`Flow`).

## Combined `@Log` + `@Mdc`

```java
@Log
@Mdc(key = "tenant", value = "${tenantId}")
@Mdc(key = "operation", value = "create")
public Order create(
    @Mdc String tenantId,
    @Mdc(key = "request_id") String requestId,
    @Log.off CreateOrderDto request   // suppressed from log output
) {
    // MDC: tenant, operation, request_id, tenantId
    // Log: tenantId + requestId on entry, return on exit; request body not logged
    return repository.save(request.toEntity());
}
```

## Pitfalls

| Symptom | Cause | Fix |
|---------|-------|-----|
| MDC keys never appear | `org.slf4j.MDC` imported | Use `ru.tinkoff.kora.logging.common.MDC` |
| MDC value from a previous request | Global key not removed | Avoid `global = true`, or static `MDC.remove(key)` when done |
| `MDC.wrap` / `MDC.clear` does not resolve | Those methods do not exist in Kora | Use `put` / `remove` / `get` |
| Null MDC value | Parameter was null | Kora skips null MDC values |
| Sensitive data in MDC | `@Mdc` on a secret parameter | Do not annotate secrets; use `@Log.off` for the log line |

## See also

- [logging-aspect.md](logging-aspect.md) — `@Log` reference
- [logging-performance.md](logging-performance.md) — production tuning
- Parent [SKILL.md](../SKILL.md)
