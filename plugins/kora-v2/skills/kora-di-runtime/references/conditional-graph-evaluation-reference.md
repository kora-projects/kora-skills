# Conditional components at runtime — how `GraphCondition` is evaluated

**Kora 2.0** · `io.koraframework.application.graph.{GraphCondition, Node}` ·
`io.koraframework.application.graph.exception.*`

> **Scope.** This file covers only what the container does with a condition **while the graph is
> built**. Declaring conditional components — the `@Conditional(tag = …)` syntax, publishing a
> `GraphCondition` under a tag, composing conditions, choosing between implementations, and the
> compile-time rules the processor enforces — is
> [`kora-di-compile/references/conditional-components-reference.md`](../../kora-di-compile/references/conditional-components-reference.md).
> Read that first; this file assumes the wiring already compiles.

---

## 1. The runtime contract

```java
package io.koraframework.application.graph;

public interface GraphCondition {

    ConditionResult eval();

    static GraphCondition or(GraphCondition... conditions);
    static GraphCondition and(GraphCondition... conditions);

    sealed interface ConditionResult {
        static ConditionResult matched(String reason);
        static ConditionResult failed(String reason);

        record Matched(String reason) implements ConditionResult {}
        record Failed(String reason) implements ConditionResult {}
    }
}
```

Each conditional node carries the compiled decision on `Node.condition()`, typed
`Function<Graph, GraphCondition.ConditionResult>` — it receives the graph, so a condition can read
other components (config being the usual one) before deciding.

The `reason` string is not decoration: it is the only diagnostic the container prints when a
conditional resolution fails, and it is reproduced verbatim in the exceptions below.

---

## 2. When the condition runs

In `GraphImpl.TmpGraph.createNode`, the condition is evaluated **before the node's factory is
called** — after the node's dependencies are ready, before anything is constructed:

```
dependencies ready → evaluate condition → Matched? → factory.get(graph) → Lifecycle.init() → interceptors
                                        → Failed?  → stop here
```

Results are memoised per initialisation pass in `conditionResultsCache`, which
`GraphImpl.initializeSubgraph` clears at the start of every init **and every refresh**. So one
`GraphCondition` guarding twenty components is evaluated once per cycle, and re-evaluated after a
refresh — a config reload can flip a condition, a plain config change cannot.

---

## 3. What a failed condition leaves behind

The factory is never invoked. The node's slot holds an internal marker recording the reason, and
reading it throws:

```
IllegalStateException: Graph node value was not initialized because condition failed: <reason>
```

Because no instance is ever constructed, nothing downstream of construction happens either:

| | Conditional component whose condition failed |
|---|---|
| constructor | never called |
| `Lifecycle.init()` | never called |
| `GraphInterceptor.afterInit` | never called |
| `Lifecycle.release()` / `AutoCloseable.close()` | never called — there is nothing to release |
| membership in `All<T>` | skipped (§5) |

This matters most for a conditional `@Root`: a startup task guarded by a condition that fails simply
does not exist, which is the intended way to make a side-effecting task optional.

---

## 4. Two different reasons a component can be missing

A pruned component and a condition-failed component look identical from the outside — the work
silently did not happen — but they are different mechanisms and have different fixes.

| | Pruned | Condition failed |
|---|---|---|
| Decided at | compile time, by graph traversal | runtime, at graph init |
| Cause | nothing depends on it and it has no `@Root` | its `GraphCondition` returned `Failed` |
| Node in the graph | does not exist at all | exists, holds a failure marker |
| Reading it | compile error, "no component found" | `IllegalStateException: … condition failed: <reason>` |
| Fix | add `@Root`, or a dependent | fix the condition, its config, or the dependency on it |

If a component that *does* carry `@Root` never runs, check its condition before re-reading
[`root-component-reference.md`](root-component-reference.md) — the two are independent, and a
conditional root needs both to pass.

---

## 5. Choosing among conditional candidates

Where a claim has several candidates and the processor deferred the choice, `Graph.getOneOf`
evaluates each candidate's condition and requires **exactly one** match:

| Matched | Outcome |
|---|---|
| 1 | that component is injected |
| 0 | `NoneOfConditionalNodeMatches` |
| ≥ 2 | `MoreThanOneConditionalNodeMatches` |

Both extend `IllegalStateException`, live in `io.koraframework.application.graph.exception`, and
list every candidate with its reason:

```
None of conditional candidates was created:
- node [#1] class java.lang.String (1 dependencies):
    condition failed
- node [#2] class java.lang.String (1 dependencies):
    condition failed
```

```
More than one conditional candidates was created:
- node [#2] class java.lang.String (1 dependencies):
    condition matched
- node [#3] class java.lang.String (1 dependencies):
    condition matched
```

This is why an uninformative `reason` is a real defect: these two blocks are the entire startup
diagnostic.

### Inside `All<T>`

Conditional members whose condition failed are **skipped**, never returned as `null`. The filtering
moment differs by collection shape:

- `All<T>` filters once, when the collection is constructed — the membership is then fixed;
- `All<ValueOf<T>>` and `All<PromiseOf<T>>` re-evaluate the filter on **every `iterator()` call**.

So an `All<ValueOf<T>>` can change size across a refresh while an `All<T>` captured before it cannot.
See [`collection-injection-reference.md`](collection-injection-reference.md).

---

## 6. Refresh

`RefreshableGraph.refresh(node)` clears the condition cache, so conditions are re-evaluated for every
node the refresh rebuilds. A condition that now fails means the component is not recreated; a
condition that now matches means it is constructed and initialised for the first time. Components
depending on it through `ValueOf<T>` survive the refresh either way and will see the change — or an
`IllegalStateException` on `get()` if the node went away.

---

## 7. Runtime pitfalls

| Symptom | Cause |
|---|---|
| `Graph node value was not initialized because condition failed` | something depends unconditionally on a conditional component |
| the same message although the dependency is `@Nullable` / `T?` | a nullable single dependency is generated as `g.get(node)` in both processors (`ComponentDependency`), so it throws instead of receiving `null`; Java `Optional<T>` is built on the same claim. Fixed in `2.0.0.RC2` (kora-projects/kora PR #960) — only `2.0.0.RC1` is affected, which generates `Graph.getNullable(node)`. On RC1, inject `All<T>` — it skips condition-failed members (§5) — or put the consumer under the same `@Conditional` |
| `@KoraAppTest` fails with `Graph node belongs to another application graph` | `ApplicationGraphDraw.copy()`/`subgraph()` keep the original node condition, which then reads the original condition node on the derived graph. Fixed in `2.0.0.RC2` (kora-projects/kora PR #963) — only `2.0.0.RC1` is affected; see `kora-testing-junit-java` / `kora-testing-junit-kotlin` |
| `NoneOfConditionalNodeMatches` | every candidate's condition failed — read the listed reasons |
| `MoreThanOneConditionalNodeMatches` | the conditions are not mutually exclusive |
| a conditional `@Root` never runs | expected when its condition fails; check the reason, not the `@Root` |
| the failure message says nothing useful | the `ConditionResult` reason strings are uninformative |
| flipping config at runtime does not enable a component | conditions are re-evaluated only on graph init or refresh |
| an `All<T>` member appears/disappears unexpectedly | `All<ValueOf<T>>`/`All<PromiseOf<T>>` re-filter per `iterator()` |

---

## See also

- [`kora-di-compile/references/conditional-components-reference.md`](../../kora-di-compile/references/conditional-components-reference.md) — declaring conditions, composing them, compile-time rules
- [`root-component-reference.md`](root-component-reference.md) — pruning, the other reason a component is missing
- [`collection-injection-reference.md`](collection-injection-reference.md) — conditional members of `All<T>`
- [`runtime-graph-api-reference.md`](runtime-graph-api-reference.md) — nodes, refresh, diagnostics
