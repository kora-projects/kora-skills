# `All<T>` Reference — collection injection in Kora 2.0

**Kora 2.0** · `io.koraframework.application.graph.All`

---

## 1. The type

```java
package io.koraframework.application.graph;

public sealed interface All<T> extends Iterable<T>
    permits All.StaticAll, AllPromisesImpl, AllSimpleImpl, AllValuesImpl {

    static <T> All<T> of(T... values);      // for tests and manual graphs
    // the remaining static factories are used by generated code
}
```

**`All<T>` extends `Iterable<T>`, not `List<T>`.** It has no `size()`, `get(int)`, `isEmpty()`,
`stream()` or `forEach(BiConsumer)` — only `iterator()` and `Iterable.forEach`. It is also `sealed`,
so you cannot implement it yourself; use `All.of(...)` to build one in a test.

`List<T>` is **not** a collection claim. A constructor parameter of type `List<Notifier>` asks the
container for a single component of type `List<Notifier>` and fails with "no component found" unless
some module actually provides one.

---

## 2. Supported claims

The processor recognises exactly these collection shapes:

| Parameter type | Claim | Meaning |
|---|---|---|
| `All<T>` | `ALL_OF_ONE` | every matching component, eagerly |
| `All<ValueOf<T>>` | `ALL_OF_VALUE` | every matching component as a `ValueOf` — refresh-isolated |
| `All<PromiseOf<T>>` | `ALL_OF_PROMISE` | every matching component as a `PromiseOf` — resolved lazily |

Anything else parameterised over `All` is not special-cased.

---

## 3. Tag semantics

Which components land in the collection is decided by the tag on the **parameter**:

| Parameter | Collects |
|---|---|
| `All<Notifier>` | untagged `Notifier` components only |
| `@Tag(Tag.Any.class) All<Notifier>` | every `Notifier`, tagged or not |
| `@Tag(SmsTag.class) All<Notifier>` | only `Notifier`s tagged `SmsTag` |

The first row is the usual cause of "my collection is missing implementations": tagging an
implementation removes it from every untagged consumer, including untagged `All<T>`.

---

## 4. Java

```java
package com.example.notify;

import io.koraframework.application.graph.All;
import io.koraframework.common.annotation.Component;
import io.koraframework.common.annotation.Tag;

@Component
public final class NotificationService {

    private final All<Notifier> notifiers;

    public NotificationService(@Tag(Tag.Any.class) All<Notifier> notifiers) {
        this.notifiers = notifiers;
    }

    public void broadcast(String user, String message) {
        for (var notifier : notifiers) {
            notifier.notify(user, message);
        }
    }
}
```

Keeping the `All<T>` and iterating it is the simplest correct shape. If you genuinely need a `List`
— to sort it, index it, or hand it to an API — materialise it explicitly; `List.copyOf` does **not**
accept an `Iterable`:

```java
private final List<Notifier> notifiers;

public NotificationService(@Tag(Tag.Any.class) All<Notifier> notifiers) {
    var list = new ArrayList<Notifier>();
    notifiers.forEach(list::add);
    this.notifiers = List.copyOf(list);
}
```

## 5. Kotlin

```kotlin
package com.example.notify

import io.koraframework.application.graph.All
import io.koraframework.common.annotation.Component
import io.koraframework.common.annotation.Tag

@Component
class NotificationService(
    @Tag(Tag.Any::class) private val notifiers: All<Notifier>
) {

    fun broadcast(user: String, message: String) {
        for (notifier in notifiers) {
            notifier.notify(user, message)
        }
    }
}
```

Kotlin's `Iterable` extensions apply, so `notifiers.toList()`, `.map { }`, `.filter { }` all work
without materialising by hand.

---

## 6. `All<ValueOf<T>>` and `All<PromiseOf<T>>`

`All<ValueOf<T>>` gives a collection whose elements always resolve to the *current* instance, and —
like a plain `ValueOf` dependency — keeps the consumer from being rebuilt when a member refreshes:

```java
@Component
public final class HealthAggregator {

    private final All<ValueOf<HealthCheck>> checks;

    public HealthAggregator(@Tag(Tag.Any.class) All<ValueOf<HealthCheck>> checks) {
        this.checks = checks;
    }

    public boolean healthy() {
        for (var check : checks) {
            if (!check.get().isHealthy()) {
                return false;
            }
        }
        return true;
    }
}
```

`All<PromiseOf<T>>` yields `PromiseOf<T>` elements whose `get()` returns `Optional<T>`; use it when
members may legitimately not be resolvable at the point of use.

---

## 7. Ordering and conditional members

Order follows the order in which the processor resolved the components — it is deterministic for a
given source set but **not** something to encode behaviour against. Where order matters (a filter or
validation chain), give the element interface an explicit `order()`/`priority()` and sort.

Members declared `@Conditional` whose condition failed are **skipped**, not returned as null:

- `All<T>` filters at construction time — the collection is fixed once built;
- `All<ValueOf<T>>` / `All<PromiseOf<T>>` re-evaluate the filter on **every `iterator()` call**.

---

## 8. Pitfalls

| Symptom | Cause |
|---|---|
| `cannot find symbol: method size()` / `get(int)` / `stream()` | `All` is `Iterable`, not `List` |
| `List.copyOf(all)` does not compile | `List.copyOf` needs a `Collection`; drain the iterable first |
| "no component found for `List<Foo>`" | `List<T>` is not a collection claim — use `All<T>` |
| collection is empty | no untagged components of that type; try `@Tag(Tag.Any.class)` |
| collection misses the tagged implementations | untagged `All<T>` excludes them by design |
| `class is not allowed to extend sealed class: All` | `All` is sealed; use `All.of(...)` in tests |
| a member is unexpectedly absent at runtime | its `@Conditional` condition evaluated to `Failed` |
| `Circular dependency found:` naming an `All<T>` consumer | a member of the collection depends back on the consumer — directly, or because the member is `@Conditional` on a `GraphCondition` that itself injects the `All<T>`. The processor breaks ordinary cycles with a generated promised proxy, but a proxy stands in for one component and never for a collection (`All<T>`, `TypeRef<T>`, `Graph`), so this cycle is always a compile error. Remove the back-edge: move the shared piece into a separate component. The `Fix:` line `Use All<ValueOf<T>> or All<PromiseOf<T>> instead of All<T>` does not help — those are collection claims as well and the same cycle is reported |

---

## See also

- [`tag-injection-reference.md`](tag-injection-reference.md) — tag matching rules
- [`optional-dependency-reference.md`](optional-dependency-reference.md) — `ValueOf` / `PromiseOf` semantics
- [`conditional-graph-evaluation-reference.md`](conditional-graph-evaluation-reference.md) — why a member can be missing
