# Advanced runtime DI patterns

**Kora 2.0** · `io.koraframework.application.graph` · `io.koraframework.common.annotation`

The material here is what you reach for after `@Root`, `Lifecycle`, `@Tag` and `All<T>` are not
enough: generic component templates, the "meta" dependency claims (`Graph`, `Node`, `TypeRef`), and
the type rules the resolver enforces.

---

## 1. The complete claim vocabulary

A constructor or module-method parameter is turned into exactly one *dependency claim*. These are all
of them:

| Parameter type | Claim | Notes |
|---|---|---|
| `T` | `ONE_REQUIRED` | the default |
| `@Nullable T` / `T?` | `ONE_NULLABLE` | absent → `null` |
| `ValueOf<T>` | `VALUE_OF` | current value, refresh-isolated |
| `@Nullable ValueOf<T>` / `ValueOf<T>?` | `NULLABLE_VALUE_OF` | |
| `PromiseOf<T>` | `PROMISE_OF` | `get()` returns `Optional<T>` |
| `@Nullable PromiseOf<T>` / `PromiseOf<T>?` | `NULLABLE_PROMISE_OF` | |
| `All<T>` | `ALL_OF_ONE` | |
| `All<ValueOf<T>>` | `ALL_OF_VALUE` | |
| `All<PromiseOf<T>>` | `ALL_OF_PROMISE` | |
| `TypeRef<T>` | `TYPE_REF` | reified type token, filled in by generated code |
| `Node<T>` | `NODE_OF` | handle to another node |
| `Graph` / `RefreshableGraph` | `GRAPH` | the live graph |

`java.util.Optional<T>` is a special case of `T`: the claim is for a component of type `Optional<T>`,
and when none exists the processor synthesises one, `Optional.ofNullable(...)` over a nullable claim of
`T` with the same tag (Java and KSP `GraphBuilder`). Anything else — `List<T>`, `Provider<T>`,
`Supplier<T>` used as a laziness wrapper — is just a request for a component of that exact type.

Every claim also carries a tag, so `@Tag(X.class) All<ValueOf<T>>` is a normal, supported shape.

---

## 2. Component templates — generic module methods

A generic method in a module is a **component template**: the processor instantiates it per required
type argument.

```java
@Module
public interface StorageModule {

    default Function<Integer, byte[]> intMapper() {
        return i -> new byte[] { i.byteValue() };
    }

    default Function<String, byte[]> stringMapper() {
        return s -> s.getBytes(StandardCharsets.UTF_8);
    }

    default <T> Storage<T> typedStorage(Function<T, byte[]> mapper) {
        return new TempFileStorage<>(mapper);
    }
}
```

```kotlin
@Module
interface StorageModule {

    fun intMapper(): Function<Int, ByteArray> = Function { i -> byteArrayOf(i.toByte()) }

    fun stringMapper(): Function<String, ByteArray> = Function { s -> s.toByteArray(StandardCharsets.UTF_8) }

    fun <T> typedStorage(mapper: Function<T, ByteArray>): Storage<T> = TempFileStorage(mapper)
}
```

A consumer asking for `Storage<String>` gets one built from `stringMapper()`; a consumer asking for
`Storage<Integer>` gets one built from `intMapper()`. The template contributes nothing on its own —
only actual requests instantiate it.

Matching (`ComponentTemplateHelper`) binds type variables by unifying the declared return type with
the required type, honouring the variables' bounds and unwrapping `Wrapped<T>` on both sides.

**Every non-`private`, non-`static` method of a module interface is a declaration.** A helper method
you did not mean to publish becomes a component — or, if generic, an over-broad template that starts
answering requests you never intended. Mark helpers `private` (interface private methods) or
`static`; both are skipped by `KoraAppUtils.parseComponents`.

```java
@Module
public interface ReportModule {

    default ReportRenderer renderer(TemplateEngine engine) {
        return new ReportRenderer(engine, defaults());
    }

    private static RenderOptions defaults() {   // private → not a component
        return RenderOptions.compact();
    }
}
```

Keep templates narrowly bounded (`<T extends Event>` rather than `<T>`) so a stray request cannot
match them.

---

## 3. `Wrapped<T>` unwrapping in resolution

Resolution tries a direct assignment first and then an *unwrapped* one
(`ServiceTypesHelper.isAssignableToUnwrapped`): a component declared as `Wrapped<T>` satisfies a
claim for `T`. This applies to plain claims, to `All<T>` members and to template matching.

Consequences:

- a module method returning `Wrapped<T>` and another returning `T` are **the same component type**
  for the resolver — declaring both is an ambiguity, not an overload;
- `Wrapped.unwrap(ValueOf<Wrapped<T>>)` returns `ValueOf<T>` when you hold the wrapper yourself;
- the wrapper object is what the container keeps for lifecycle purposes, which is exactly why
  `LifecycleWrapper` works — see [`lifecycle-reference.md`](lifecycle-reference.md).

---

## 4. Injecting `Graph`, `Node<T>` and `TypeRef<T>`

These exist for components that must manipulate the container rather than merely live in it — config
watchers, admin endpoints that trigger a refresh, factories that must reify a type argument.

```java
import io.koraframework.application.graph.Node;
import io.koraframework.application.graph.RefreshableGraph;

@Component
public final class RoutingTableAdmin {

    private final RefreshableGraph graph;
    private final Node<RoutingTable> tableNode;

    public RoutingTableAdmin(RefreshableGraph graph, Node<RoutingTable> tableNode) {
        this.graph = graph;
        this.tableNode = tableNode;
    }

    /** Rebuilds the routing table and everything downstream of it. */
    public void reload() {
        graph.refresh(tableNode);
    }
}
```

Use these sparingly. A component that reaches into the graph is harder to test and to reason about
than one that declares what it needs; Kora's own `ConfigWatcher` is the model for when it is
warranted — see [`runtime-graph-api-reference.md`](runtime-graph-api-reference.md).

`TypeRef<T>` is the reified-type carrier for generic factories:

```java
@Module
public interface CodecModule {

    default <T> Codec<T> codec(TypeRef<T> type, ObjectMapper mapper) {
        return new JacksonCodec<>(type, mapper);
    }
}
```

---

## 5. Type rules the resolver enforces

**Raw types are rejected**, both on providers and on claims:

```
Component provider returns a raw type:
  type: java.util.function.Function

Raw component types are forbidden because they make dependency resolution ambiguous.
```

```
Dependency uses a raw type:
  type: io.koraframework.application.graph.All
```

**Unresolved generics in a claim are rejected**:

```
Dependency uses an unresolved generic type:
  type: T

Kora dependency keys must be concrete types.
```

**Primitives are rejected** — components are classes or interfaces, so an `int` or `long` parameter
cannot be a dependency. Configuration values reach components through a `@ConfigSource` interface,
not as loose scalars.

**A `@Component` class must have exactly one public constructor.** Extra constructors must be
non-public, or the construction logic belongs in a module method.

---

## 6. Fallbacks and overrides

| Goal | Mechanism |
|---|---|
| provide a component only if nobody else does | `@DefaultComponent` on the provider |
| replace a module's component in the application | override the module method in the `@KoraApp` interface — repeat its `@Tag` |
| provide a component only under a runtime condition | `@Conditional` + `GraphCondition` |
| several independently-configured families of one type | `@FactoryModule` + `@Tag.Factory` |

When several candidates match a claim, the resolver first drops the `@DefaultComponent` ones; if
exactly one non-default remains it wins. If several remain and they are **all** `@Conditional`, the
choice is deferred to runtime (see
[`conditional-graph-evaluation-reference.md`](conditional-graph-evaluation-reference.md)). Otherwise the build
fails with a duplicate-dependency error.

---

## 7. Pitfalls

| Symptom | Cause |
|---|---|
| a helper in a module became a component | non-`private`, non-`static` module methods are all declarations |
| a generic template answers unrelated requests | unbounded type variable — add a bound |
| "raw component types are forbidden" | a provider or claim lost its type arguments |
| `Wrapped<T>` and `T` providers collide | both register the same component type |
| a component reads `Graph` and is untestable | declare the dependency instead |
| `@Component class must have exactly one public constructor` | extra public constructors |

---

## See also

- [`lifecycle-reference.md`](lifecycle-reference.md) — `Wrapped<T>`, `LifecycleWrapper`
- [`conditional-graph-evaluation-reference.md`](conditional-graph-evaluation-reference.md) — `@Conditional`, `GraphCondition`
- [`tag-injection-reference.md`](tag-injection-reference.md) — `@Tag.Factory` and factory modules
- [`kora-di-compile`](../../kora-di-compile/SKILL.md) — module and component declaration rules
