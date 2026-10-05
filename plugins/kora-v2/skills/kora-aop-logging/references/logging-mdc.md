# `@Mdc` and the Kora MDC — Kora 2.0

Annotation: **`io.koraframework.logging.common.annotation.Mdc`**
Runtime store: **`io.koraframework.logging.common.MDC`**
Artifact: `io.koraframework:logging-common` (transitive through `logging-logback`).

## Contents

- [Annotation shape](#annotation-shape)
- [Method-level `@Mdc`](#method-level-mdc)
- [Parameter-level `@Mdc`](#parameter-level-mdc)
- [How values are typed](#how-values-are-typed)
- [Scoping and `global`](#scoping-and-global)
- [The runtime model: `ScopedValue`, not `Context`, not a thread-local](#the-runtime-model-scopedvalue-not-context-not-a-thread-local)
- [Where the MDC scope is bound](#where-the-mdc-scope-is-bound)
- [Imperative API](#imperative-api)
- [Kora MDC vs `org.slf4j.MDC`](#kora-mdc-vs-orgslf4jmdc)
- [Return types `@Mdc` rejects](#return-types-mdc-rejects)
- [Pitfalls](#pitfalls)

## Annotation shape

```java
@AopAnnotation
@Repeatable(Mdc.MdcContainer.class)
@Target({METHOD, PARAMETER})
@Retention(RUNTIME)
public @interface Mdc {
    String key() default "";
    String value() default "";
    boolean global() default false;
}
```

`@Mdc` is an `@AopAnnotation`: on its own it weaves the aspect, so a method with only `@Mdc` and no
`@Log` still gets a proxy that maintains the MDC around the call.

## Method-level `@Mdc`

On a method **both `key` and `value` are mandatory**. A blank one is a compile error:

```
@Mdc annotation must have 'key' attribute
@Mdc annotation must have 'value' attribute
```

`value` is either a literal or `${…}`. The text between `${` and `}` is **inlined verbatim into the
generated code** — it is not a config placeholder and not restricted to parameter names. Any
expression legal at that point in the method compiles:

```java
@Mdc(key = "operation", value = "create-order")                              // literal
@Mdc(key = "tenant",    value = "${tenantId}")                               // a parameter
@Mdc(key = "requestId", value = "${java.util.UUID.randomUUID().toString()}") // any expression
public Order create(String tenantId, CreateOrderDto body) { ... }
```

In Kotlin the `$` must be escaped so Kotlin's own string templates do not consume it:

```kotlin
@Mdc(key = "tenant", value = "\${tenantId}")
open fun create(tenantId: String, body: CreateOrderDto): Order { ... }
```

Repeat the annotation for several keys — it is `@Repeatable`.

## Parameter-level `@Mdc`

On a parameter the **argument** is the value; the attributes only name the key, resolved in order:

1. `key` if non-blank,
2. otherwise `value` if non-blank,
3. otherwise the parameter name.

```java
public Order create(
    @Mdc UUID orderId,                 // key "orderId"
    @Mdc("order_id") UUID id,          // key "order_id"  (value used as the key)
    @Mdc(key = "user_id") String user  // key "user_id"
) { ... }
```

## How values are typed

The MDC stores `StructuredArgumentWriter`s, so values keep their JSON type instead of becoming
strings.

| Parameter type | Written as |
|---|---|
| `String`, `Integer`, `Long`, `Boolean` (and `int`, `long`, `boolean`) | dedicated `MDC.put` overload — JSON string / number / boolean |
| `StructuredArgumentWriter` | written by the writer itself |
| any other primitive (e.g. `double`) | `String.valueOf(v)` → JSON string |
| any other reference type | `v.toString()` → JSON string, guarded by a null check |
| `null` reference | **nothing is put** — the key is absent, not `null` |

`MDC.put(key, (String) null)` called by hand writes a JSON `null`; the aspect's null guard means an
absent argument simply produces no key.

## Scoping and `global`

For every non-`global` key the aspect captures the previous value **before** the call and restores it
in a `finally` block — putting the old value back, or removing the key if there was none. So a method
with `@Mdc` cannot leak a key to its caller, and nesting two methods that use the same key works.

`global = true` skips both the capture and the restore: the key stays in the MDC after the method
returns, for the remainder of the surrounding scope (the request, the Kafka record, the scheduled
run). It does **not** persist beyond that scope — a `ScopedValue` binding ends with its scope — but it
is visible to everything the caller does afterwards inside the same request.

```java
@Mdc(key = "tenant", value = "${tenantId}", global = true)
public void enterTenant(String tenantId) { ... }
```

Remove it yourself when done — there is no `clear()`:

```java
MDC.remove("tenant");
```

Kotlin restriction: `global = true` on a `suspend` function is rejected by KSP —
`@Mdc annotation with 'global' attribute is not supported for this function`. Kora 2.0 contracts are
synchronous anyway.

## The runtime model: `ScopedValue`, not `Context`, not a thread-local

```java
public class MDC {
    public static final ScopedValue<MDC> VALUE = ScopedValue.newInstance();
    public static MDC get() { return VALUE.get(); }
    // put(String, String|Integer|Long|Boolean|StructuredArgumentWriter), remove(String)
    public MDC fork();
    public Map<String, StructuredArgumentWriter> values();
}
```

**Kora's 1.x `Context` type no longer exists anywhere in the framework.** Any 1.x pattern that read
or wrote MDC through `Context`, or copied a `Context` to another thread, has no 2.0 equivalent —
delete it rather than translate it. The 2.0 store is a JDK `ScopedValue<MDC>`, which means:

- The binding is **immutable and scope-bounded**: it is visible for the dynamic extent of the
  `ScopedValue.where(...).run/call(...)` that established it, then gone.
- It is **not inherited** by a thread you start yourself, nor by tasks you submit to an
  `ExecutorService`. Values are visible to a `StructuredTaskScope` fork of the current scope, and
  Kora re-binds explicitly where it hands work to another thread (Kafka calls `mdc.fork()` per
  record).
- Reading it **outside a binding throws `NoSuchElementException`**. `LoggingModule`'s Logback
  appender guards this with `MDC.VALUE.isBound()`; the `@Mdc` aspect does not — its first generated
  statement is `MDC.get().values()`.

To use `@Mdc` (or `MDC.put`) outside a Kora entry point — `main`, a plain unit test, a worker thread
you started — bind the scope yourself:

```java
ScopedValue.where(MDC.VALUE, new MDC()).run(() -> service.create(tenantId, body));
```

```kotlin
ScopedValue.where(MDC.VALUE, MDC()).call<Unit, RuntimeException> { service.create(tenantId, body) }
```

## Where the MDC scope is bound

Kora binds `MDC.VALUE` at every entry point that starts a unit of work, so ordinary application code
never has to:

| Entry point | Binder |
|---|---|
| HTTP server (Undertow) | `KoraRequestProcessingHttpHandler.handleRequest` |
| Kafka consumers | `RecordHandler` / `RecordsHandler` (one `MDC` per poll, `mdc.fork()` per record) |
| gRPC server | `VirtualThreadExecutorTransportFilter` |
| JMS | `JmsMessageListenerContainer` |
| JDK scheduler | `KoraJdkJob` (`io.koraframework.scheduling.jdk.job`) |
| Quartz scheduler | `KoraQuartzJob` |
| DB scheduler (db-scheduler) | `KoraDbJob` (`io.koraframework.scheduling.db.scheduler.job`) |

## Imperative API

```java
import io.koraframework.logging.common.MDC;

MDC.put("userId", "42");        // String | Integer | Long | Boolean | StructuredArgumentWriter
MDC.remove("userId");
Map<String, StructuredArgumentWriter> current = MDC.get().values();
```

There is **no `MDC.clear()`, no `MDC.wrap(...)`, no `MDC.getContext()`** — do not write them.
`MDC.get()` returns the bound `MDC` instance; `fork()` produces an independent copy for a nested
scope.

## Kora MDC vs `org.slf4j.MDC`

They are two different stores, and `@Mdc` writes only to Kora's.

- Read a `@Mdc` key back with `io.koraframework.logging.common.MDC` — `org.slf4j.MDC.get(...)` will
  not see it.
- `KoraRequestProcessingHttpHandler` calls `org.slf4j.MDC.clear()` at the start of every request, so
  anything put into the SLF4J MDC before routing does not reach the handler.
- Kora's `ConsoleTextRecordEncoder` prints both maps, so an SLF4J MDC value is not invisible — it
  simply is not what `@Mdc` manages, gets no restore-on-exit, and carries no JSON type.
- IDE auto-import offers `org.slf4j.MDC` first. Check the import on every `MDC` reference.

Rendering MDC into log output is the backend's job: `KoraAsyncAppender` snapshots
`MDC.get().values()` into the event, and `ConsoleTextRecordEncoder` (or the `KoraMdcConverter`
conversion rule in a pattern layout) writes it. See
[kora-telemetry-logging](../../kora-telemetry-logging/SKILL.md) — without that Logback wiring the
Kora MDC is maintained correctly and printed nowhere.

## Return types `@Mdc` rejects

The aspect fails the build when the annotated method returns a Reactive Streams `Publisher`
(Reactor `Mono` / `Flux`), a `Future`, or a `CompletionStage`:

```
@Mdc can't be applied for type java.util.concurrent.CompletionStage
```

This is deliberate: the MDC binding is scope-bounded, and a value returned for completion elsewhere
would leave the scope. Kora 2.0 contracts are synchronous — annotate synchronous methods.

## Pitfalls

| Symptom | Cause | Fix |
|---|---|---|
| `NoSuchElementException` at `MDC.get()` | No `ScopedValue` binding — called from `main`, a plain test, or a thread you started | Call through a Kora entry point, or wrap in `ScopedValue.where(MDC.VALUE, new MDC())` |
| `@Mdc annotation must have 'key'/'value' attribute` | Method-level `@Mdc` missing an attribute | Method form needs both; only the parameter form may omit them |
| Kotlin `${tenantId}` resolves at compile time to the parameter's value or fails | Kotlin string template consumed the `$` | Escape it: `"\${tenantId}"` |
| Key missing for a nullable argument | The aspect skips null non-native values | Expected; pass a default or use a method-level `@Mdc` |
| Key from the previous request appears | `global = true` and never removed | Drop `global`, or `MDC.remove(key)` at the end of the unit of work |
| `MDC.clear()` does not resolve | Not part of Kora's API | Remove keys individually |
| Values never printed | Logback not wired with `KoraAsyncAppender` + a Kora encoder | See [kora-telemetry-logging](../../kora-telemetry-logging/SKILL.md) |
| Migrating 1.x code that put values on `Context` | `Context` is removed from the whole framework | Rewrite against `MDC` / `ScopedValue`; there is no drop-in replacement |

## See also

- [logging-aspect.md](logging-aspect.md) — `@Log` reference
- [logging-masking.md](logging-masking.md) — redacting fields inside logged objects
- [logging-performance.md](logging-performance.md) — cost model and volume control
- Parent [SKILL.md](../SKILL.md)
