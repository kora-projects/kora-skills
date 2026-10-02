# Optional and lazy dependencies — `@Nullable`, `ValueOf<T>`, `PromiseOf<T>`

**Kora 2.0** · `io.koraframework.application.graph.{ValueOf, PromiseOf}` ·
`org.jspecify.annotations.Nullable`

---

## 1. `@Nullable` — the dependency may be absent

Marking an injection point nullable tells the processor that a missing component is acceptable: the
graph builds, and the parameter receives `null`.

### Java — JSpecify, and it is type-use

Kora 2.0 uses **JSpecify** (`org.jspecify.annotations.Nullable`, version `1.0.1`, transitive with
`io.koraframework:common`). The processor accepts any annotation whose type name ends in `.Nullable`,
so it is the compiler — not Kora — that is strict about *where* the annotation may appear.

`@Nullable` is a **type-use** annotation. On a plain parameter the declaration position is fine:

```java
import org.jspecify.annotations.Nullable;

@Module
public interface SmsModule {

    final class SmsTag {
        private SmsTag() {}
    }

    @Tag(SmsTag.class)
    default Notifier smsNotifier(@Nullable SmsCellularProvider provider) {
        return (user, message) -> {
            if (provider == null) {
                System.out.println("[SMS] " + user + "@" + message);
            } else {
                System.out.println("+" + provider.getCode() + " [SMS] " + user + "@" + message);
            }
        };
    }
}
```

Position starts to matter as soon as the type is nested, generic or an array:

| Intent | Correct | Wrong |
|---|---|---|
| nullable nested type | `Config.@Nullable Inner inner` | `@Nullable Config.Inner inner` |
| nullable array | `String @Nullable [] names` | `@Nullable String[] names` (nullable *elements*) |
| nullable element | `List<@Nullable String> names` | `@Nullable List<String> names` (nullable *list*) |
| nullable wrapper | `@Nullable ValueOf<Tracer> tracer` | — |

A wrong position is a `javac` error:
`type annotation @org.jspecify.annotations.Nullable is not expected here`.

**Do not add a null check the compiler already gives you, and do not swallow the absence silently.**
The point of an optional dependency is a real fallback path.

### Kotlin — nullability is the type

```kotlin
@Module
interface SmsModule {

    class SmsTag private constructor()

    @Tag(SmsTag::class)
    fun smsNotifier(provider: SmsCellularProvider?): Notifier = Notifier { user, message ->
        if (provider == null) {
            println("[SMS] $user@$message")
        } else {
            println("+${provider.getCode()} [SMS] $user@$message")
        }
    }
}
```

KSP treats `isMarkedNullable` as the optional marker. Do not carry JSpecify annotations into Kotlin
sources; `@field:Nullable` in particular is an invalid target under Kotlin 2.4.

### Java — `java.util.Optional<T>` works too

An `Optional<T>` parameter is also an optional dependency. When the graph has no component of the
exact type `Optional<T>`, both processors synthesise one: they resolve `T` as a **nullable** claim
with the parameter's tag and generate `Optional.ofNullable(...)` around it, so an absent `T` arrives
as `Optional.empty()` (`GraphBuilder` / `GraphFileGenerator` in the Java and KSP processors). It
nests with the lazy handles — `ValueOf<Optional<T>>`, `Optional<ValueOf<T>>`,
`PromiseOf<Optional<T>>`, `Optional<PromiseOf<T>>` all compile and initialise
(`DependencyTest.testOptionalDependencies`).

```java
public NotificationService(Optional<SmsCellularProvider> provider) { ... }
```

`@Nullable T` stays the convention; in Kotlin write `T?`. Because `Optional<T>` goes through the same
nullable claim, it shares the `@Conditional` pitfall below (PR #960).

### When it is the wrong tool

`@Nullable` is for a dependency that may genuinely not be in the container — an optional telemetry
exporter, an optional provider from a module the application may not plug in. It is not a way to
silence an "ambiguous dependency" error, and it is not a substitute for `@DefaultComponent` when what
you actually want is a fallback implementation.

---

## 2. `ValueOf<T>` — current value, no refresh cascade

```java
package io.koraframework.application.graph;

public interface ValueOf<T> {

    T get();

    default <Q> ValueOf<Q> map(Function<T, Q> mapper);
    default ValueOf<Optional<T>> optional();

    static <T> ValueOf<Optional<T>> emptyOptional();
}
```

**There is no `refresh()` method.** Refreshing the graph is `RefreshableGraph.refresh(Node<?>)` — see
[`runtime-graph-api-reference.md`](runtime-graph-api-reference.md). `ValueOf` is purely a handle.

Two properties, both verified by the framework's own `GraphTest`:

- `get()` always returns the **current** instance of that node (`valueOfAlwaysPointsOnTheCurrentObject`);
- a component that depends on `ValueOf<B>` is **not** recreated when `B` is refreshed
  (`refreshDoesntAffectDependentObjectWithValueOf`), whereas a direct dependency on `B` is.

```java
package com.example.api;

import io.koraframework.application.graph.ValueOf;
import io.koraframework.common.annotation.Component;

@Component
public final class ApiClient {

    private final HttpClient http;
    private final ValueOf<AuthConfig> auth;

    public ApiClient(HttpClient http, ValueOf<AuthConfig> auth) {
        this.http = http;
        this.auth = auth;
    }

    public Response fetch(String path) {
        var token = auth.get().token();   // always the current config
        return http.get(path, token);
    }
}
```

```kotlin
@Component
class ApiClient(
    private val http: HttpClient,
    private val auth: ValueOf<AuthConfig>
) {
    fun fetch(path: String): Response = http.get(path, auth.get().token())
}
```

Reach for `ValueOf<T>` when:

- rebuilding this component on every refresh of that dependency is expensive or disruptive (an open
  server socket, a warm cache, a connection pool);
- you need the latest value per call rather than a snapshot taken at construction.

Do **not** use it as a general-purpose laziness knob. A direct dependency is cheaper to read and
gives the container a real ordering edge.

### `@Nullable ValueOf<T>`

`ValueOf` and `PromiseOf` have dedicated nullable claim types, so both spellings are meaningful:

```java
public MetricsReporter(@Nullable ValueOf<MeterRegistry> registry) { … }
```

```kotlin
class MetricsReporter(private val registry: ValueOf<MeterRegistry>?)
```

Here it is the *component* that may be absent — `registry` itself is `null`, not `registry.get()`.

---

## 3. `PromiseOf<T>` — the weaker handle

```java
public interface PromiseOf<T> {

    Optional<T> get();

    default <Q> PromiseOf<Q> map(Function<T, Q> mapper);
    default PromiseOf<Optional<T>> optional();

    static <T> PromiseOf<T> of(T value);
    static <T> PromiseOf<T> promiseOfNull();
    static <T> PromiseOf<Optional<T>> emptyOptional();
}
```

`get()` returns `Optional<T>`, so a promise can be unresolved. This is what the processor uses to
break dependency cycles: when it must, it generates a `PromisedProxy` implementation of the cycle's
interface (`io.koraframework.common.PromisedProxy`, plus `RefreshListener`) that delegates through a
`PromiseOf`.

Declare `PromiseOf<T>` yourself when a dependency is legitimately resolvable only after graph
construction. For an ordinary cycle between two of your own components, prefer either extracting the
shared piece into a third component or `ValueOf<T>` on one side — both are easier to read than a
promise.

---

## 4. Choosing

| Need | Use |
|---|---|
| component may be missing from the container | `@Nullable T` / `T?` |
| always read the latest instance; survive its refresh | `ValueOf<T>` |
| break a refresh cascade | `ValueOf<T>` |
| break a construction cycle | restructure, else `ValueOf<T>` / `PromiseOf<T>` |
| optional *and* refresh-isolated | `@Nullable ValueOf<T>` / `ValueOf<T>?` |
| every implementation, refresh-isolated | `All<ValueOf<T>>` |

---

## 5. Pitfalls

| Symptom | Cause |
|---|---|
| `type annotation @Nullable is not expected here` | JSpecify `@Nullable` in a non-type-use position |
| `cannot find symbol: method refresh()` on `ValueOf` | 1.x memory — refresh lives on `RefreshableGraph` |
| NPE on an optional dependency | `@Nullable` added, fallback path not written |
| `Graph node value was not initialized because condition failed` on a `@Nullable` dependency | the target is `@Conditional` and its condition failed; the nullable claim is generated as `g.get(node)`, which throws instead of yielding `null`. Fixed in `2.0.0.RC2` (kora-projects/kora PR #960) — only `2.0.0.RC1` is affected; on RC1 inject `All<T>` — see [`conditional-graph-evaluation-reference.md`](conditional-graph-evaluation-reference.md#7-runtime-pitfalls) |
| consumer still rebuilt on refresh | dependency declared directly, not as `ValueOf<T>` |
| `@field:Nullable` rejected by Kotlin | invalid target; use `T?` |
| `Optional<T>` parameter is always `Optional.empty()` | no component of type `T` (with that tag) in the graph — the processor wraps a nullable claim of `T`, so check the tag and that `T` is registered |

---

## See also

- [`collection-injection-reference.md`](collection-injection-reference.md) — `All<ValueOf<T>>`, `All<PromiseOf<T>>`
- [`runtime-graph-api-reference.md`](runtime-graph-api-reference.md) — `RefreshableGraph.refresh`, `RefreshListener`
- [`lifecycle-reference.md`](lifecycle-reference.md) — what a refresh does to `Lifecycle` components
