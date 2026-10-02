# Graph Roots and Lifecycle Reference

**Applies to:** Kora 2.x (`io.koraframework`)

This reference covers how you **declare** roots and lifecycle at compile time, and what the
processor does with those declarations. Runtime semantics — the exact `init`/`release` ordering, the
refresh protocol, `GraphInterceptor` — belong to **kora-di-runtime**.

## Contents

- [@Root — What Gets Built at All](#root--what-gets-built-at-all)
- [Where to Put @Root](#where-to-put-root)
- [Lifecycle on a Class You Own](#lifecycle-on-a-class-you-own)
- [Wrapped&lt;T&gt; and LifecycleWrapper for Types You Do Not Own](#wrappedt-and-lifecyclewrapper-for-types-you-do-not-own)
- [Breaking Cycles with ValueOf and PromiseOf](#breaking-cycles-with-valueof-and-promiseof)
- [GraphInterceptor](#graphinterceptor)
- [@Root Across a @KoraSubmodule](#root-across-a-korasubmodule)
- [Common Mistakes](#common-mistakes)
- [Related References](#related-references)

## `@Root` — What Gets Built at All

Graph resolution starts from the `@Root` declarations and nothing else. The processor seeds its
stack with every declaration annotated `@Root` — on the class, or on the provider method — and
resolves outward from there. **A component that is not a `@Root` and not a transitive dependency of
one is never in the graph.**

That is not laziness at runtime: the component is simply absent from the generated code.

```java
import io.koraframework.common.annotation.Component;
import io.koraframework.common.annotation.Root;

@Root
@Component
public final class NotifyRunner implements Lifecycle {

    private final All<Notifier> notifiers;

    public NotifyRunner(@Tag(Tag.Any.class) All<Notifier> notifiers) {
        this.notifiers = notifiers;
    }

    @Override
    public void init() {
        notifiers.forEach(n -> n.notifyUser("started"));
    }

    @Override
    public void release() { }
}
```

`@Root` lives in `io.koraframework.common.annotation` — the same package as everything else in 2.0.
Under 1.x it was already in `…common.annotation` while its neighbours were in `…common`, so it is
the one annotation whose *sub*package did not change.

Most applications never write `@Root` explicitly: framework modules provide their own roots. The
Undertow server, for example, is declared `@Root` inside `UndertowHttpServerFactoryModule`, which is
why extending `UndertowPublicHttpServerModule` is enough to make a service listen. You need `@Root`
for **your own** components whose only purpose is a side effect.

## Where to Put `@Root`

`@Root` targets `TYPE` and `METHOD`, so both forms work:

```java
// on a @Component class
@Root @Component
public final class CacheWarmer { }

// on a provider method
@KoraApp
public interface Application extends HoconConfigModule {

    static void main(String[] args) { KoraApplication.run(ApplicationGraph::graph); }

    @Root
    default MigrationRunner migrations(DataSource dataSource) {
        return new MigrationRunner(dataSource);
    }
}
```

```kotlin
@Root
@Component
class CacheWarmer(private val cache: CacheService) : Lifecycle {
    override fun init() = cache.warm()
    override fun release() { }
}
```

A `@Root` can also be `@Conditional`, which is the clean way to make a startup task optional — see
[Conditional Components Reference](conditional-components-reference.md).

## Lifecycle on a Class You Own

`io.koraframework.application.graph.Lifecycle` is two methods, both allowed to throw:

```java
public interface Lifecycle {
    void init() throws Exception;
    void release() throws Exception;
}
```

Implement it directly on a `@Component` when the class is yours:

```java
@Component
public final class ConnectionPool implements Lifecycle {

    private final PoolConfig config;
    private HikariDataSource dataSource;

    public ConnectionPool(PoolConfig config) {
        this.config = config;
    }

    @Override
    public void init() {
        this.dataSource = new HikariDataSource(config.toHikari());
    }

    @Override
    public void release() {
        if (this.dataSource != null) {
            this.dataSource.close();
        }
    }
}
```

Prefer `init()` over constructor side effects. The constructor runs while the graph is still being
assembled; `init()` runs when the graph starts, in dependency order, and its failure is reported as
an initialisation failure rather than a construction failure.

Implementing `Lifecycle` does **not** make a component a root. A `Lifecycle` component that nothing
depends on still needs `@Root`.

## `Wrapped<T>` and `LifecycleWrapper` for Types You Do Not Own

When the instance is a third-party type you cannot make implement `Lifecycle`, return a `Wrapped<T>`
from the provider. The processor unwraps it: consumers keep asking for plain `T`.

```java
public interface Wrapped<T> {
    T value();
}

public class LifecycleWrapper<T> implements Lifecycle, Wrapped<T> {

    public interface ThrowingConsumer<T> {
        void accept(T t) throws Exception;
    }

    public LifecycleWrapper(T value, ThrowingConsumer<T> init, ThrowingConsumer<T> release) { … }
}
```

```java
import io.koraframework.application.graph.LifecycleWrapper;
import io.koraframework.application.graph.Wrapped;
import io.koraframework.common.annotation.Module;

@Module
public interface ActivityModule {

    default Wrapped<ActivityRecorder> activityRecorder() {
        var recorder = new RemoteActivityRecorder();
        return new LifecycleWrapper<>(recorder, r -> { }, ActivityRecorder::disconnect);
    }
}
```

```kotlin
@Module
interface ActivityModule {

    fun activityRecorder(): Wrapped<ActivityRecorder> {
        val recorder = RemoteActivityRecorder()
        return LifecycleWrapper(recorder, {}, ActivityRecorder::disconnect)
    }
}
```

Consumers inject `ActivityRecorder`, not `Wrapped<ActivityRecorder>`:

```java
@Component
public final class ActivityService {
    public ActivityService(ValueOf<ActivityRecorder> recorder) { }
}
```

Both callbacks are required — pass a no-op lambda (`r -> { }` / `{}`) for the half you do not need.
Unwrapping applies to `All<T>` too: a provider returning `Wrapped<T>` contributes its `T`.

## Breaking Cycles with `ValueOf` and `PromiseOf`

The processor first tries to break a cycle on its own: when the dependency that closes it is an
interface or a non-final class, it generates a *promised proxy* that stands in for the component and
the graph compiles. A cycle is a compile error only when that is impossible — the dependency is a
`final` class (every Kotlin class is final by default), not a class or interface at all, or an
`All<T>` / `TypeRef<T>` / `Graph` claim. With two `final` classes:

```
Circular dependency found:
  com.example.ServiceA (no tags)

Dependency cycle:
  @--- component  com.example.ServiceA
  ^--- component  com.example.ServiceB
  ^--- component  com.example.ServiceA [CYCLE]

Required at:
  com.example.ServiceB(
    com.example.ServiceA)
  parameter: com.example.ServiceA a

Note:
  Kora can break a cycle with a proxy only for interface or non-final class dependency, but com.example.ServiceA is final.

Fix:
  - Depend on an interface implemented by com.example.ServiceA instead of the class itself, or make the class non-final, so Kora can break the cycle with a proxy.
  - Break the cycle with ValueOf<T> or PromiseOf<T> where lazy access is valid.
  - Move shared state into a separate component.
  - Do not create dependency cycles in Lifecycle.
```

The error is reported on the parameter that closes the cycle (`Required at:`), and `Note:` says why
no proxy could be used. Prefer the interface fix: the proxy for a *class* is a generated subclass,
and for a class whose only constructor takes arguments the generated code does not compile
(`constructor ServiceA … cannot be applied to given types`) — so "make it non-final" is only safe
for a class with a usable no-arg constructor.

Take an indirect reference on one side:

```java
@Component
public final class ServiceA {
    public ServiceA(ServiceB b) { }
}

@Component
public final class ServiceB {
    private final ValueOf<ServiceA> a;

    public ServiceB(ValueOf<ServiceA> a) {
        this.a = a;               // not resolved yet
    }

    public void work() {
        a.get().doSomething();    // resolved on demand
    }
}
```

`ValueOf<T>` in 2.0 declares `get()`, plus the default methods `map(Function)` and `optional()`.
There is **no `refresh()`** — refresh is driven by the graph. `PromiseOf<T>` is the same idea with
`Optional<T> get()`, for a value that may not exist yet at the moment you look.

Do not reach for `ValueOf` first. A cycle usually means shared state wants its own component; the
error's `Fix:` list says so for a reason.

## GraphInterceptor

`io.koraframework.application.graph.GraphInterceptor<T>` wraps or inspects a component as the graph
starts and stops. **The 2.0 method names are `afterInit` and `beforeRelease`** — not `init`/`release`:

```java
public interface GraphInterceptor<T> {
    T afterInit(T value);
    T beforeRelease(T value);
}
```

Declare an implementation as a component and the processor wires it into the resolution of every
matching node. Its runtime contract — when it runs, what returning a different instance means for
dependents — is covered by **kora-di-runtime**.

## `@Root` Across a `@KoraSubmodule`

The submodule processor copies `@Root` (along with `@Tag` and `@DefaultComponent`) onto the provider
it generates in `…SubmoduleImpl`. A `@Root` component in a domain subproject stays a root once the
assembly project's `@KoraApp` extends that submodule — nothing extra to declare.

## Common Mistakes

### A startup task without `@Root`

```java
// BAD — nothing depends on CacheWarmer, so it is not in the graph at all
@Component
public final class CacheWarmer implements Lifecycle {
    public void init() { cache.warm(); }
    public void release() { }
}

// GOOD
@Root
@Component
public final class CacheWarmer implements Lifecycle {
    public void init() { cache.warm(); }
    public void release() { }
}
```

There is no error to read here — the component silently does not exist. If a startup side effect is
not happening, check `@Root` first.

### Expecting `Lifecycle` to imply `@Root`

It does not. The two are independent: `@Root` decides whether the component exists, `Lifecycle`
decides what happens to it once it does.

### Work in the constructor instead of `init()`

```java
// BAD — runs during graph assembly, before dependencies are initialised
@Root @Component
public final class CacheWarmer {
    public CacheWarmer(CacheService cache) { cache.warm(); }
}

// GOOD
@Root @Component
public final class CacheWarmer implements Lifecycle {
    private final CacheService cache;
    public CacheWarmer(CacheService cache) { this.cache = cache; }
    public void init() { cache.warm(); }
    public void release() { }
}
```

### Injecting `Wrapped<T>` instead of `T`

```java
// BAD — the graph unwraps it; nothing provides Wrapped<ActivityRecorder> to consumers
public ActivityService(Wrapped<ActivityRecorder> recorder) { }

// GOOD
public ActivityService(ActivityRecorder recorder) { }
```

### `GraphInterceptor` with 1.x method names

```java
// BAD — does not override anything in Kora 2.0
public DataSource init(DataSource value) { return value; }
public DataSource release(DataSource value) { return value; }

// GOOD
@Override public DataSource afterInit(DataSource value) { return value; }
@Override public DataSource beforeRelease(DataSource value) { return value; }
```

### `@PostConstruct` / `@PreDestroy`

Kora does not read JSR-250 annotations. Implement `Lifecycle`, or wrap with `LifecycleWrapper`.

### Asynchronous lifecycle

`init()` and `release()` are synchronous and may throw `Exception`. There is no `Mono<Void>` or
`suspend` form in Kora 2.0.

## Related References

- [Component Registration Reference](component-registration-reference.md) — how types enter the graph
- [Component Factories Reference](component-factories-reference.md) — providers that return `Wrapped<T>`
- [Conditional Components Reference](conditional-components-reference.md) — making a `@Root` optional
- [Tags & Collections Reference](tags-collections-reference.md) — `ValueOf<T>`, `PromiseOf<T>`, `All<T>`
- [@KoraSubmodule Reference](kora-submodule-reference.md) — `@Root` across subprojects
- **kora-di-runtime** — `init`/`release` ordering, refresh, `GraphInterceptor` semantics
