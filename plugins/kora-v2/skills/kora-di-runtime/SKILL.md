---
name: kora-di-runtime
description: "Runtime DI behaviour of the Kora 2.0 container (io.koraframework.application.graph) — @Root pruning, the synchronous Lifecycle init()/release() contract, LifecycleWrapper/Wrapped<T>, @Tag disambiguation incl. Tag.Any and Tag.Factory, All<T> collections, ValueOf<T>/PromiseOf<T>, @Nullable optional dependencies, GraphInterceptor afterInit/beforeRelease, GraphCondition + @Conditional, RefreshableGraph.refresh and RefreshListener. Use when a component must start although nothing depends on it, when writing init/release logic, when disambiguating or collecting components, when breaking a refresh chain or a dependency cycle, or when a component must be wrapped during graph build. For compile-time @KoraApp/@Module/@Component wiring see kora-di-compile."
license: Apache-2.0
metadata:
  version: "0.1.0"
  kora-version: "2.x"
---

# Kora DI Runtime — Container Behaviour

> **Kora sub-skill — obey the [kora-v2 meta rules](../../SKILL.md) on every task:** **R0** ground the workspace on Kora 2.0 refs before starting (framework source at tag `2.0.0.RC2` + `kora-examples` at `migration/2.0` + Kora 2.0 docs at koraframework.io/v2, which trail the source; 1.x `kora-docs` pages are never an authority) · **R1** read this sub-skill before writing code · **R2** Kora 2.0 APIs only — no Spring/Micronaut/Quarkus, no Kora 1.x APIs, no invented annotations or config keys · **R3** journal any incorrect Kora usage. Add comments/Javadoc only if asked.

| | |
|---|---|
| **Framework** | Kora 2.0 (`io.koraframework`) |
| **Runtime package** | `io.koraframework.application.graph` |
| **DI annotations** | `io.koraframework.common.annotation` |
| **Execution model** | Synchronous. Graph nodes are created and released on **virtual threads**; there are no reactive, `CompletionStage` or `suspend` container contracts. |
| **Boundary** | This skill covers what the container *does at runtime*. Declaring the graph (`@KoraApp`, `@Module`, `@Component`, `@KoraSubmodule`) is [`kora-di-compile`](../kora-di-compile/SKILL.md). |

**Read this skill when:**

- a component must be instantiated although nothing depends on it → `@Root`
- a component needs startup/shutdown work → `Lifecycle`, `LifecycleWrapper`
- two components of one type collide, or you need only some of them → `@Tag`
- you need *every* implementation of a type → `All<T>`
- a consumer must not be rebuilt when its dependency refreshes, or a cycle must be broken → `ValueOf<T>` / `PromiseOf<T>`
- a dependency may legitimately be absent → `@Nullable`
- a component must be wrapped or decorated while the graph is built → `GraphInterceptor<T>`
- a component must exist only under some runtime condition → `GraphCondition` + `@Conditional`

---

## 1. `@Root` — components nothing depends on

`io.koraframework.common.annotation.Root`, `@Target({TYPE, METHOD})`, `@Retention(RUNTIME)`.

The container is **not** a component scanner. Graph construction starts from the *root set* and walks
dependencies; anything the walk never reaches is not in the graph and is never created. `@Root` puts
a declaration into that root set. It goes on a `@Component` class, or on a `@KoraApp` / `@Module`
factory method.

```java
import io.koraframework.application.graph.Lifecycle;
import io.koraframework.common.annotation.Component;
import io.koraframework.common.annotation.Root;

@Root
@Component
public final class BucketInitializer implements Lifecycle {

    private final S3Client s3Client;
    private final UploadsConfig config;   // a @ConfigSource interface — see kora-config-hocon

    public BucketInitializer(S3Client s3Client, UploadsConfig config) {
        this.s3Client = s3Client;
        this.config = config;
    }

    @Override
    public void init() {
        // create the bucket if it is missing
    }

    @Override
    public void release() {}
}
```

Implementing `Lifecycle` does **not** make a component reachable. A `Lifecycle`-only side-effect
component with no dependents and no `@Root` is silently pruned: the build stays green, the graph
initialises, and `init()` never runs. This is exactly the shape of the S3 bucket initialiser above,
and the reason it carries `@Root`.

With an empty root set the annotation processor fails the build outright:

```
@KoraApp has no root components.

Fix:
  - Check that modules with @Root components are plugged-in.
  - Annotate at least one component or module method with @Root.
  - Check that root component is visible from this @KoraApp module set.
```

**Interceptors are the exception:** a `GraphInterceptor<T>` is pulled in automatically as soon as the
component it intercepts is resolved. It needs neither `@Root` nor a dependent.

> [`references/root-component-reference.md`](references/root-component-reference.md)

---

## 2. `Lifecycle` — init and release

```java
package io.koraframework.application.graph;

public interface Lifecycle {
    void init() throws Exception;
    void release() throws Exception;
}
```

Both methods are **`void` and synchronous**. There is no reactive return type, no `CompletionStage`,
no `suspend`. Kotlin implements them as plain `fun init()` / `fun release()`.

Ordering guarantees, as implemented in `GraphImpl`:

- each node is created on its own virtual thread and waits for its dependencies, so init is as
  parallel as the graph allows while still respecting dependency order;
- `init()` runs immediately after the factory produced the instance, before any dependent is created;
- release runs in **reverse** order — a component is released only after everything that depends on
  it has been released;
- a component that implements `AutoCloseable` also gets `close()` called on release, after
  `release()`;
- `KoraApplication.run` installs a JVM shutdown hook (`kora-shutdown`) that performs the release;
  `run(supplier)` then blocks `main` until that release has finished, while
  `run(supplier, false)` returns right after init and leaves the release to the hook.

A checked exception out of `init()` is rethrown as
`IllegalStateException: Lifecycle init failed with checked exception for node …`; a failed init
releases everything already created and aborts startup.

For third-party types you cannot make implement `Lifecycle`, return `Wrapped<T>` from a factory
method and use `LifecycleWrapper`:

```java
@Module
public interface ActivityModule {

    default Wrapped<ActivityRecorder> activityRecorder() {
        var recorder = new ActivityRecorderImpl();
        return new LifecycleWrapper<>(recorder, ActivityRecorder::connect, ActivityRecorder::disconnect);
    }
}
```

Consumers keep injecting `ActivityRecorder`; the container unwraps `Wrapped<T>` for them.

> [`references/lifecycle-reference.md`](references/lifecycle-reference.md)

---

## 3. `@Tag` — disambiguation

`io.koraframework.common.annotation.Tag`. The tag is a **class**, not a string.

```java
@Tag(RedisTag.class)  @Component public final class RedisCache implements Cache {}
@Tag(LocalTag.class)  @Component public final class LocalCache implements Cache {}

@Component
public final class UserService {
    public UserService(@Tag(RedisTag.class) Cache remote,
                       @Tag(LocalTag.class) Cache local) { … }
}
```

Matching rule (`TagUtils.tagsMatch`): an untagged injection point accepts only untagged components;
a tagged one accepts only the same tag; `@Tag(Tag.Any.class)` accepts everything.

Two nested marker types exist:

| Marker | Meaning |
|---|---|
| `Tag.Any` | at an injection point, matches components with any tag and untagged ones |
| `Tag.Factory` | inside a `@FactoryModule`-provided module, resolves to the tag of the factory-module method itself |

`Tag.Factory` is what lets one factory module be instantiated several times under different tags and
produce several independently-configured clients of one type. Used outside a factory module it is a
compile error.

> [`references/tag-injection-reference.md`](references/tag-injection-reference.md)

---

## 4. `All<T>` — collections

```java
public sealed interface All<T> extends Iterable<T> { … }
```

`All<T>` is an **`Iterable`, not a `List`** — no `size()`, no `get(i)`, no `stream()`. Copy it if you
need a list.

```java
import io.koraframework.application.graph.All;

@Component
public final class NotificationService {

    private final All<Notifier> notifiers;

    public NotificationService(@Tag(Tag.Any.class) All<Notifier> notifiers) {
        this.notifiers = notifiers;
    }

    public void broadcast(String message) {
        for (var notifier : notifiers) {
            notifier.send(message);
        }
    }
}
```

Plain `All<T>` collects only **untagged** components — the usual reason "some implementations are
missing". `@Tag(Tag.Any.class) All<T>` collects every one; `@Tag(X.class) All<T>` collects only those
tagged `X`. `All<ValueOf<T>>` and `All<PromiseOf<T>>` are also supported claims.

> [`references/collection-injection-reference.md`](references/collection-injection-reference.md)

---

## 5. `ValueOf<T>` — lazy access and refresh isolation

```java
public interface ValueOf<T> {
    T get();
    default <Q> ValueOf<Q> map(Function<T, Q> mapper);
    default ValueOf<Optional<T>> optional();
}
```

There is **no `refresh()` on `ValueOf`** — refreshing is `RefreshableGraph.refresh(Node)`.
`ValueOf<T>.get()` always returns the current instance, and depending on `ValueOf<B>` tells the
container this component must **not** be recreated when `B` is refreshed. `PromiseOf<T>` is the
weaker form whose `get()` returns `Optional<T>`; it is how the processor breaks dependency cycles.

> [`references/optional-dependency-reference.md`](references/optional-dependency-reference.md) ·
> [`references/runtime-graph-api-reference.md`](references/runtime-graph-api-reference.md)

---

## 6. `@Nullable` — optional dependencies

- **Java:** JSpecify `org.jspecify.annotations.Nullable`. It is a **type-use** annotation, so
  position matters: `@Nullable Tracer tracer` on a parameter is fine, but a nested type must be
  written `Outer.@Nullable Inner`, and `@Nullable String[]` and `String @Nullable []` mean different
  things. A wrong position is a `javac` error, not a warning.
- **Kotlin:** nullability is the type — `tracer: Tracer?`. Do not carry JSpecify annotations into
  Kotlin sources.

`ValueOf<T>` and `PromiseOf<T>` have their own nullable claim types, so `@Nullable ValueOf<T>` /
`ValueOf<T>?` are valid and mean "the wrapped component may be absent".

---

## 7. `GraphInterceptor<T>` — wrapping during graph build

```java
public interface GraphInterceptor<T> {
    T afterInit(T value);
    T beforeRelease(T value);
}
```

The methods are `afterInit` / `beforeRelease` — **not** `init` / `release` — and neither declares
`throws Exception`. `afterInit` runs after the intercepted component's own `Lifecycle.init()` and
before any dependent is created; whatever it returns is what the rest of the graph receives.
`beforeRelease` runs before that component's `release()`, in reverse interceptor order.

An interceptor is matched by **exact declared type**, not by assignability, and by tag: an untagged
interceptor sees only untagged components, `@Tag(X.class)` only components tagged `X`, and
`@Tag(Tag.Any.class)` components of every tag — the same rule under javac and KSP. Declare it for a
concrete type — a generic `GraphInterceptor<T>` component matches nothing.

> [`references/graph-interceptor-reference.md`](references/graph-interceptor-reference.md)

---

## 8. `GraphCondition` + `@Conditional` (new in 2.0)

`@Conditional(tag = MyCondition.class)` on a component or module method binds it to the single
`GraphCondition` component tagged `@Tag(MyCondition.class)`. At graph init the condition is evaluated
once; a `Failed` result means the component's factory is never invoked. Where several candidates of
one type are all `@Conditional`, **exactly one** must match.

Declaring conditions — the `@Conditional` syntax, publishing a `GraphCondition` under a tag,
composing conditions, and the compile-time rules — is
[`kora-di-compile`](../kora-di-compile/references/conditional-components-reference.md). What the
container does with a condition while it builds the graph is documented here.

> [`references/conditional-graph-evaluation-reference.md`](references/conditional-graph-evaluation-reference.md)

---

## 9. Pitfalls

| Symptom | Cause | Fix |
|---|---|---|
| `Lifecycle.init()` never runs, build is green | component pruned — nothing depends on it | add `@Root` |
| `@KoraApp has no root components` | no `@Root` anywhere in the module set | annotate at least one component/method |
| `init()`/`release()` written as reactive or `suspend` | 1.x habit | `void init() throws Exception` |
| `cannot find symbol: method size()` on `All<T>` | `All` is `Iterable`, not `List` | copy into a `List` |
| collection misses some implementations | untagged `All<T>` skips tagged components | `@Tag(Tag.Any.class) All<T>` |
| interceptor never fires | wrong method names, or the interceptor's type is not the component's *exact* declared type / tag | `afterInit`/`beforeRelease`, concrete type, matching tag |
| consumer rebuilt on every config refresh | direct dependency | inject `ValueOf<T>` and call `get()` |
| `type annotation @Nullable is not expected here` | JSpecify `@Nullable` in a non-type-use position | move it onto the type |
| `Graph node value was not initialized because condition failed` | a `@Conditional` component was skipped and something still asks for it | fix the condition or the dependency |
| same message at startup although the consumer declares the dependency `@Nullable` / `T?` | the processors generate a nullable single dependency as `g.get(node)`, which throws for a condition-failed node instead of passing `null` (Java `Optional<T>` goes through the same claim) | fixed in `2.0.0.RC2` (kora-projects/kora PR #960) — only `2.0.0.RC1` is affected — the dependency then receives `null` via the new default `Graph.getNullable`. On RC1, inject `All<T>` (condition-failed members are skipped) or make the consumer `@Conditional` on the same tag |
| any Kora `Context` parameter | `Context` no longer exists anywhere in Kora 2.0 | delete it |

---

## 10. Checklist

```
- [ ] Every component that must run without dependents carries @Root
- [ ] Lifecycle methods are void init()/release(), synchronous, no reactive/suspend
- [ ] Factory-provided third-party resources return Wrapped<T> via LifecycleWrapper
- [ ] Tags are marker classes; Tag.Any used deliberately, Tag.Factory only inside @FactoryModule
- [ ] All<T> treated as Iterable; tag semantics chosen consciously
- [ ] ValueOf<T> used where refresh isolation or a cycle break is needed — no ValueOf.refresh() calls
- [ ] Optional deps: JSpecify @Nullable in type-use position (Java) or T? (Kotlin)
- [ ] Interceptors implement afterInit/beforeRelease for a concrete type
- [ ] No io.koraframework Context anywhere
```

---

## 11. Assets

Templates under [`assets/`](assets/) — `RootComponent`, `LifecycleComponent`, `LifecycleFactory`,
`TagClass`, `TaggedComponent`, `CollectionComponent`, `ValueOfComponent`, `GraphInterceptor`,
`GraphCondition`, `Application`, plus Gradle and config scaffolding, in Java and Kotlin variants.

## 12. Related skills

- [`kora-di-compile`](../kora-di-compile/SKILL.md) — `@KoraApp`, `@Module`, `@Component`, `@KoraSubmodule`, graph build errors
- [`kora-config-hocon`](../kora-config-hocon/SKILL.md) / [`kora-config-yaml`](../kora-config-yaml/SKILL.md) — the `@ConfigSource` components injected above
- [`kora-testing-junit-java`](../kora-testing-junit-java/SKILL.md) / [`kora-testing-junit-kotlin`](../kora-testing-junit-kotlin/SKILL.md) — replacing graph nodes in tests
