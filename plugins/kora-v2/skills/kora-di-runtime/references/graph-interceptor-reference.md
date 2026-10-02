# `GraphInterceptor` Reference — wrapping components during graph build

**Kora 2.0** · `io.koraframework.application.graph.GraphInterceptor`

---

## 1. The contract

```java
package io.koraframework.application.graph;

public interface GraphInterceptor<T> {

    T afterInit(T value);

    T beforeRelease(T value);
}
```

The method names are **`afterInit`** and **`beforeRelease`**. They are not `init` / `release` — the
1.x names — and neither declares `throws Exception`, so an override cannot add one.

Both return the instance the container should carry on with. Returning `value` unchanged is a
no-op observer; returning a different object replaces the node's value for everything downstream.

---

## 2. When each method runs

From `GraphImpl.TmpGraph.createNode` and `GraphImpl.release`:

**`afterInit`**

1. the node's factory produces the instance;
2. if it implements `Lifecycle`, its own `init()` runs;
3. **then** each interceptor's `afterInit` runs, in declaration order, each receiving the previous
   one's return value;
4. the final value is stored on the node and handed to dependents.

The framework's own test (`interceptorCalledAfterInitAndBeforeDependentObjectCreated`) asserts both
halves: the intercepted object is initialised after the interceptor exists, and dependents are
created after interception completed.

**`beforeRelease`**

1. everything depending on the node has already been released;
2. interceptors run in **reverse** order;
3. **then** the node's own `Lifecycle.release()` runs;
4. then `AutoCloseable.close()` if applicable.

**Errors.** A `RuntimeException` or `Error` from `afterInit` propagates and fails graph
initialisation. A checked exception is wrapped as
`IllegalStateException: Graph interceptor failed with checked exception for node <type> and interceptor <type>`.
Failures in `beforeRelease` are collected and rethrown after the rest of the release completed.

---

## 3. Matching — exact type and tag

`ComponentInterceptors.interceptorsFor` selects interceptors for a resolved component with two
filters:

```java
.filter(interceptor -> this.ctx.types.isSameType(interceptor.interceptType(), type))
.filter(interceptor -> TagUtils.tagsMatch(interceptor.component().tag(), component.tag()))
```

- **`isSameType`, not `isAssignable`.** `GraphInterceptor<Cache>` intercepts components whose
  *declared* type is exactly `Cache`. It does not intercept a `@Component RedisCache implements Cache`
  registered under its own class. Interceptors of an interface catch module methods declared to
  return that interface; interceptors of a class catch that class. The Kotlin symbol processor uses the
  same exact-type match (it no longer also matches a generated `__AopProxy` subclass of the
  intercepted class) — an aspect-annotated `@Component` is still intercepted, because its node is
  declared with the original type.
- **Tag matching, with the interceptor as the "required" side.** An untagged interceptor intercepts
  only untagged components; `@Tag(X.class)` on the interceptor limits it to components tagged `X`;
  `@Tag(Tag.Any.class)` on the interceptor intercepts every tag. The Kotlin symbol processor
  applies the identical rule (`ComponentInterceptors.interceptorsFor` → `tagMatches`), so a
  `@Tag(Tag.Any::class)` interceptor declared in Kotlin intercepts tagged and untagged components
  alike.

A generic `GraphInterceptor<T>` component therefore matches nothing — the intercepted type resolves
to a type variable, which is never `isSameType` with a concrete component type. Declare interceptors
for a concrete type.

An interceptor does **not** need `@Root` and does not need a dependent: `GraphBuilder.findInterceptors`
adds it to the resolution stack as soon as the component it intercepts is resolved.

---

## 4. Java

```java
package com.example.telemetry;

import io.koraframework.application.graph.GraphInterceptor;
import io.koraframework.common.annotation.Component;

@Component
public final class PaymentGatewayMetrics implements GraphInterceptor<PaymentGateway> {

    private final MeterRegistry registry;

    public PaymentGatewayMetrics(MeterRegistry registry) {
        this.registry = registry;
    }

    @Override
    public PaymentGateway afterInit(PaymentGateway gateway) {
        return new MeteredPaymentGateway(gateway, registry);
    }

    @Override
    public PaymentGateway beforeRelease(PaymentGateway gateway) {
        return gateway;
    }
}
```

Everything that injects `PaymentGateway` now receives `MeteredPaymentGateway`. Note what
`beforeRelease` gets: the value currently on the node — the wrapper, not the original.

## 5. Kotlin

```kotlin
package com.example.telemetry

import io.koraframework.application.graph.GraphInterceptor
import io.koraframework.common.annotation.Component

@Component
class PaymentGatewayMetrics(
    private val registry: MeterRegistry
) : GraphInterceptor<PaymentGateway> {

    override fun afterInit(value: PaymentGateway): PaymentGateway =
        MeteredPaymentGateway(value, registry)

    override fun beforeRelease(value: PaymentGateway): PaymentGateway = value
}
```

Kora contracts are `@NullMarked`, so the Kotlin parameter and return types are non-nullable `T`.
Writing `value: T?` produces `'afterInit' overrides nothing`, a message that does not mention
nullability at all.

---

## 6. Observing without replacing

```java
@Component
public final class ReportingSchemaCheck implements GraphInterceptor<ReportingClient> {

    @Override
    public ReportingClient afterInit(ReportingClient client) {
        client.verifySchema();     // fail fast on a schema mismatch
        return client;
    }

    @Override
    public ReportingClient beforeRelease(ReportingClient client) {
        client.flushPending();
        return client;
    }
}
```

Use this shape for a check or a one-off action that must happen after the component's own `init()`
and before anything uses it — `Lifecycle` on the component itself cannot see that boundary from the
outside.

---

## 7. `Lifecycle` vs `GraphInterceptor` vs AOP

| Need | Use |
|---|---|
| a component manages its own startup/shutdown | `Lifecycle` on the component |
| a third-party type needs startup/shutdown | `Wrapped<T>` + `LifecycleWrapper` in a module |
| something *outside* the component must decorate or replace it | `GraphInterceptor<T>` |
| per-method cross-cutting behaviour (log, retry, cache, timeout) | the AOP modules — `@Log`, `@Retryable`, `@Cacheable`, `@Timeout` … |

`GraphInterceptor` is graph-build machinery, not a request-path concern. Whatever it returns is
constructed once, so keep the interception cheap and put per-call work in the wrapper you return.

---

## 8. Pitfalls

| Symptom | Cause |
|---|---|
| `method does not override or implement a method from a supertype` (Java) / `'init' overrides nothing` (Kotlin) | 1.x method names; use `afterInit` / `beforeRelease` |
| `afterInit(T) … cannot implement afterInit(T) in GraphInterceptor` | the override added `throws Exception`; the 2.0 methods declare none |
| interceptor never fires | intercepted type is not the component's *exact* declared type |
| interceptor never fires, types look right | tag mismatch — an untagged interceptor skips tagged components |
| generic `GraphInterceptor<T>` does nothing | matches no concrete type; declare it for a concrete one |
| `ClassCastException` downstream | the wrapper returned by `afterInit` does not implement the declared type |
| `'afterInit' overrides nothing` (Kotlin) | `T?` instead of `T`; Kora contracts are `@NullMarked` |

---

## See also

- [`lifecycle-reference.md`](lifecycle-reference.md) — the callbacks `afterInit`/`beforeRelease` bracket
- [`tag-injection-reference.md`](tag-injection-reference.md) — tag matching rules
- [`runtime-graph-api-reference.md`](runtime-graph-api-reference.md) — refresh and interceptors
