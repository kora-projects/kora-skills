# Runtime Graph API Reference

**Kora 2.0** · `io.koraframework.application.graph`

Public types in the package: `All`, `ApplicationGraphDraw`, `Graph`, `GraphCondition`,
`GraphInterceptor`, `InitializedGraph`, `KoraApplication`, `Lifecycle`, `LifecycleWrapper`, `Node`,
`NodeWithMapper`, `PromiseOf`, `RefreshListener`, `RefreshableGraph`, `TypeRef`, `ValueOf`,
`Wrapped`, `WrappedRefreshListener`, plus `exception/`.

Most applications touch only `KoraApplication`, `Lifecycle`, `All`, `ValueOf` and `@Root`. The rest
of this file is for the cases that do need the graph itself.

---

## 1. Entry point

```java
public final class KoraApplication {
    public static void run(Supplier<ApplicationGraphDraw> supplier);
}
```

```java
@KoraApp
public interface Application extends HoconConfigModule, LogbackModule {

    static void main(String[] args) {
        KoraApplication.run(ApplicationGraph::graph);
    }
}
```

```kotlin
@KoraApp
interface Application : HoconConfigModule, LogbackModule

fun main() {
    KoraApplication.run(ApplicationGraph::graph)
}
```

`ApplicationGraph` is generated next to the `@KoraApp` interface; its static `graph()` returns the
`ApplicationGraphDraw`. `run` then:

1. builds and initialises the graph, logging
   `Application initialized in {}ms (JVM running for {}s)` — wall-clock milliseconds;
2. on failure logs `Application initializing failed with error` and calls `System.exit(-1)`;
3. registers a JVM shutdown hook named `kora-shutdown` which releases the graph
   (`Application shutdown...` → `Application released in {}ms`) and only then unblocks the main
   thread;
4. blocks the calling thread until that hook has finished.

There is nothing to await, close or join around `run` — it returns when the application is done.

`run(supplier, keepAlive)` is the explicit form; the one-argument `run` is `run(supplier, true)`.
With `keepAlive = false` steps 1–3 are identical but step 4 is skipped: `run` returns right after
initialisation, and the graph is still released by the `kora-shutdown` hook when the JVM exits.
Use it only when the calling thread has other work to do after startup.

---

## 2. `Graph`, `RefreshableGraph`, `InitializedGraph`

```java
public interface Graph {
    ApplicationGraphDraw draw();
    <T> T get(Node<? extends T> node);
    <T> ValueOf<T> valueOf(Node<? extends T> node);
    <T> PromiseOf<T> promiseOf(Node<? extends T> node);
    default GraphCondition condition(Node<? extends GraphCondition> node);

    interface Factory<T> { T get(RefreshableGraph graph) throws Exception; }
}

public interface RefreshableGraph extends Graph {
    void refresh(Node<?> fromNode);
}

public interface InitializedGraph extends RefreshableGraph {
    void init() throws Exception;
    void release() throws Exception;
}
```

`Graph` and `RefreshableGraph` are injectable: a constructor or module-method parameter of either
type is recognised as a `GRAPH` claim and receives the live graph. `Graph.Factory<T>` is what
generated code implements per node — you do not write it by hand.

`ApplicationGraphDraw` is the *plan*: `addNode(...)`, `getNodes()`, `findNodeByType`,
`findNodesByType`, `replaceNode`, `replaceNodeKeepDependencies`, `subgraph`, `copy`, and `init()`
which materialises an `InitializedGraph`. Node replacement is the mechanism behind test graph
modification — use the testing skills' API rather than calling it directly.

---

## 3. `Node<T>` and `TypeRef<T>`

```java
public sealed interface Node<T> {
    Type type();
    @Nullable Class<?> tag();
    @Nullable Function<Graph, GraphCondition.ConditionResult> condition();
}
```

A `Node<T>` parameter (claim type `NODE_OF`) gives a **handle** to another component's node rather
than its value — enough to call `graph.get(node)`, `graph.valueOf(node)` or `graph.refresh(node)`.
In Kotlin, `Node<T>` may not be parameterised with a nullable `T`; the processor rejects it with
*"Node&lt;T&gt; cannot use a nullable T"*.

`TypeRef<T>` is a `ParameterizedType` carrier (`TypeRef.of(rawType, args…)`). A `TypeRef<T>`
parameter is filled in by generated code with the reified type — used by mappers and factories that
must inspect the type they are producing.

---

## 4. Refresh

`refresh(Node<?> fromNode)` always re-runs the factory of `fromNode`, then walks the nodes after it
and rebuilds only those whose inputs actually changed:

- a node is recreated only when one of its direct dependencies or interceptors now holds a
  **different instance** than before (reference comparison); a node whose dependencies all kept
  their instances keeps its own instance too, `init()` is not called again and it is not released;
- recreated nodes run `Lifecycle.init()` on the new instance; the old instances are released
  afterwards;
- if a factory returns a value `equals` to the previous one, the new value is released immediately
  and the old node value is kept — so the change stops propagating there, and a refresh in which
  nothing changed leaves every existing instance in place;
- an `equals` that throws does not fail the refresh: it is logged at `WARN`
  (`Can't compare refreshed object of <class>, treating it as changed`) and the new value wins;
- consumers that depend through `ValueOf<T>` are **not** rebuilt; they simply observe the new value;
- when the refresh fails, the partially created objects are released and the previous graph is left
  intact.

Refresh runs under the graph's init lock, so refreshes and the initial init do not overlap.

### The canonical caller: `ConfigWatcher`

Kora's own config module ships the one production refresh source, and it is a compact tour of this
whole API:

```java
@Root
@DefaultComponent
default ConfigWatcher applicationConfigWatcher(RefreshableGraph graph,
                                               @Nullable @ApplicationConfig Node<? extends ConfigOrigin> applicationConfigNode,
                                               @Nullable @ApplicationConfig ValueOf<ConfigOrigin> applicationConfig) {
    return new ConfigWatcher(graph, applicationConfigNode, applicationConfig, Duration.ofSeconds(1));
}
```

`ConfigWatcher implements Lifecycle`: `init()` starts a virtual thread named `config-reload` that
polls, once a second, the modification time and symlink target of the config file and of every file
it includes, and calls `graph.refresh(applicationConfigNode)` only when one of them changed or an
included file was added or removed; `release()` interrupts it. The watcher itself survives the
refreshes it triggers — `Node<T>` and `ValueOf<T>` parameters are not refresh dependencies. It does nothing when there is no application config node, and
watches nothing when the config has no file origin. It is on by default and can be turned off with
the `KORA_CONFIG_WATCHER_ENABLED` environment variable or the `kora.config.watcher.enabled` system
property.

Note the shape worth copying: `@Root` (nothing depends on a watcher), `RefreshableGraph` +
`Node<T>` + `ValueOf<T>` injected side by side, everything `@Nullable` so the component degrades to a
no-op instead of failing the graph.

---

## 5. `RefreshListener` and `WrappedRefreshListener`

```java
public interface RefreshListener {
    void graphRefreshed() throws Exception;
}

public interface WrappedRefreshListener<T> extends Wrapped<T>, RefreshListener {
}
```

Any component that implements `RefreshListener` is registered when it is created, and
`graphRefreshed()` is called on every registered listener after a refresh completes. Exceptions are
logged (`Exception caught when calling listener.graphRefreshed(), object={}`) and **do not** fail the
refresh — do not put anything load-bearing behind them.

`WrappedRefreshListener<T>` is the combination used by wrappers that must both expose an unwrapped
value and react to refreshes; the generated `PromisedProxy` for a dependency cycle is exactly this
shape.

---

## 6. Diagnostics

| Message | Meaning |
|---|---|
| `Graph node value was not initialized: <node>` | the node was read before it was created |
| `Graph node value was not initialized because condition failed: <reason>` | a `@Conditional` node was skipped and something still asked for it |
| `Application graph failed to initialize with N errors; see suppressed exceptions` | several nodes failed during init |
| `Lifecycle init failed with checked exception for node <type> at index <n>` | `init()` threw a checked exception |
| `Graph interceptor failed with checked exception for node <t> and interceptor <i>` | `afterInit`/`beforeRelease` threw a checked exception |
| `Graph dependency belongs to another application graph` | a `Node` from a different `ApplicationGraphDraw` was passed in |
| `Graph node belongs to another application graph: node index <n>, type <t>` | a graph was asked for a node of another draw. On a draw built by `copy()`/`subgraph()` — every `@KoraAppTest` — this is a node **condition**: both methods rebind factory node references but keep the original condition, which reads the original condition node. Fixed in `2.0.0.RC2` (kora-projects/kora PR #963) — only `2.0.0.RC1` is affected |

Turn on `DEBUG`/`TRACE` for the `@KoraApp` root class to get per-node creation logging.
`kora.graph.slowNodeInitThresholdMillis` (default `100`) controls the threshold above which a node's
initialisation is reported at `DEBUG`.

---

## 7. What is not here

- **`Context` does not exist in Kora 2.0.** It is gone from the whole framework, not just from the
  HTTP APIs. Any parameter, field or thread-local threading a Kora `Context` is dead code.
- No reactive graph API: `init`, `release` and `refresh` are synchronous calls, executed internally
  on virtual threads.

---

## See also

- [`lifecycle-reference.md`](lifecycle-reference.md) — `Lifecycle`, `LifecycleWrapper`, release order
- [`optional-dependency-reference.md`](optional-dependency-reference.md) — `ValueOf`, `PromiseOf`
- [`conditional-graph-evaluation-reference.md`](conditional-graph-evaluation-reference.md) — `GraphCondition` and node conditions
- [`kora-config-hocon`](../../kora-config-hocon/SKILL.md) — the config components refreshed above
