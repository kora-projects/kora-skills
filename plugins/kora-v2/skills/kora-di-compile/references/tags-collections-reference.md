# Tags and Collections Reference

**Applies to:** Kora 2.x (`io.koraframework`)

This reference covers what the **processor** does with `@Tag` and with collection/indirect
parameter shapes. For what those wrappers do once the graph is running — refresh propagation,
`init`/`release` ordering, `GraphInterceptor` — see **kora-di-runtime**.

## Contents

- [@Tag](#tag)
- [Tag Matching — The Exact Rule](#tag-matching--the-exact-rule)
- [Meta-Annotation Tags](#meta-annotation-tags)
- [Tag.Any](#tagany)
- [Tag.Factory](#tagfactory)
- [All&lt;T&gt;](#allt)
- [Indirect and Optional Parameter Shapes](#indirect-and-optional-parameter-shapes)
- [Combining Tags and Collections](#combining-tags-and-collections)
- [Common Mistakes](#common-mistakes)
- [Quick Reference](#quick-reference)
- [Related References](#related-references)

## @Tag

`io.koraframework.common.annotation.Tag` carries a single `Class<?> value()`. The class is a marker
— it is never instantiated — so a private-constructor final class is the idiomatic form:

```java
public final class RedisTag { private RedisTag() {} }
public final class CaffeineTag { private CaffeineTag() {} }
```

```kotlin
class RedisTag private constructor()
```

Nesting the tag inside the module that owns it keeps the namespace tidy and is what Kora's own
guides do:

```java
@Module
public interface SmsModule {

    final class SmsTag { private SmsTag() {} }

    @Tag(SmsTag.class)
    default Notifier smsNotifier() { … }
}
```

`@Tag` applies to `METHOD`, `PARAMETER`, `FIELD`, `TYPE` and `TYPE_USE`:

```java
@Tag(RedisTag.class) @Component
public final class RedisCache implements Cache { }

@Component
public final class UserService {
    public UserService(@Tag(RedisTag.class) Cache cache) { }
}
```

```kotlin
@Tag(RedisTag::class) @Component
class RedisCache : Cache

@Component
class UserService(@Tag(RedisTag::class) private val cache: Cache)
```

## Tag Matching — The Exact Rule

The processor compares the **required** tag on the injection point with the **provided** tag on the
declaration:

| Required (injection point) | Provided (declaration) | Match |
|---|---|---|
| none | none | **yes** |
| none | `X` | **no** |
| `X` | `X` | **yes** |
| `X` | `Y` | no |
| `X` | none | no |
| `Tag.Any` | anything, including none | **yes** |

The second row is the one that surprises people: **a tagged component is invisible to an untagged
claim.** Tagging every implementation of an interface and then injecting it untagged produces
`No component found for dependency`, not an ambiguity error.

When that happens the error itself points at the cause:

```
No component found for dependency:
  com.example.Cache (no tags)
…
Note:
  Found component(s) with the same type but different tag. Maybe the tag was forgotten or mixed up:
  - com.example.Cache with @Tag(com.example.RedisTag.class) from component  com.example.RedisCache
```

Read the `Note:` section before anything else.

## Meta-Annotation Tags

An annotation that is itself annotated with `@Tag(X.class)` acts as the tag `X`. Kora uses this for
`@SystemApi`:

```java
@Tag(SystemApi.class)
@Target({ElementType.METHOD, ElementType.TYPE, ElementType.PARAMETER})
public @interface SystemApi { }
```

`@SystemApi` on a provider is then equivalent to `@Tag(SystemApi.class)`. It is a reasonable pattern
for a tag used widely across a codebase, but for a tag used in two places a plain marker class is
less machinery.

## `Tag.Any`

`@Tag(Tag.Any.class)` matches every declaration regardless of its tag — including untagged ones. Its
main use is collecting *everything* of a type:

```java
@Component
public final class NotificationService {
    public NotificationService(@Tag(Tag.Any.class) All<Notifier> notifiers) { }
}
```

Without `Tag.Any`, `All<Notifier>` collects only the **untagged** `Notifier` components, following
the same matching rule as a single claim.

## `Tag.Factory`

`@Tag(Tag.Factory.class)` is only legal inside a `@FactoryModule` and means "the tag of the
enclosing factory-module method". It is how one factory-module class yields two independently tagged
sets of components. See
[Component Factories Reference](component-factories-reference.md#5-factorymodule--parameterised-modules).

Used anywhere else it is a compile error:

```
@Tag.Factory can only be used inside factory modules:
  module: com.example.StorageModule
```

## `All<T>`

`io.koraframework.application.graph.All<T>` **extends `Iterable<T>`, not `List<T>`.** It is a sealed
interface; you iterate it, or copy it if you need list semantics.

```java
import io.koraframework.application.graph.All;

@Component
public final class NotificationService {
    private final List<Notifier> notifiers;

    public NotificationService(@Tag(Tag.Any.class) All<Notifier> notifiers) {
        this.notifiers = new ArrayList<>();
        notifiers.forEach(this.notifiers::add);
    }
}
```

```kotlin
@Component
class NotificationService(
    @Tag(Tag.Any::class) private val notifiers: All<Notifier>
) {
    fun broadcast(message: String) = notifiers.forEach { it.notifyUser(message) }
}
```

Facts that matter when writing against it:

- An `All<T>` claim with no matching components is **not** an error — it is simply empty.
- A `@DefaultComponent` is skipped when other candidates exist, and collected when it is the only one.
- A provider returning `Wrapped<T>` contributes its unwrapped `T`.
- `All<ValueOf<T>>` and `All<PromiseOf<T>>` collect the same set held indirectly.

## Indirect and Optional Parameter Shapes

The processor recognises these parameter shapes and resolves each differently:

| Parameter | Claim | Behaviour |
|---|---|---|
| `T` | required | must resolve, or compile error |
| `@Nullable T` | nullable | `null` injected when nothing matches |
| `Optional<T>` | optional | the processor resolves `T` as nullable and builds the `Optional` |
| `ValueOf<T>` | indirect | `get()` on demand; breaks cycles, decouples refresh |
| `@Nullable ValueOf<T>` | nullable indirect | `null` when nothing matches |
| `PromiseOf<T>` | indirect, deferred | `get()` returns `Optional<T>` |
| `All<T>` | collection | every match, possibly empty |
| `All<ValueOf<T>>`, `All<PromiseOf<T>>` | collection, indirect | as above |
| `Graph` / `RefreshableGraph` | the graph itself | rarely needed in application code |
| `Node<T>` | the graph node | rarely needed in application code |
| `TypeRef<T>` | the reified type | used by generic framework components |

`ValueOf<T>` in 2.0 declares `get()`, plus the defaults `map(Function)` and `optional()`. It has
**no `refresh()`** — refresh is driven by the graph, not by the holder.

```java
import io.koraframework.application.graph.ValueOf;

@Component
public final class ActivityService {
    private final ValueOf<ActivityRecorder> recorder;

    public ActivityService(ValueOf<ActivityRecorder> recorder) {
        this.recorder = recorder;   // ActivityRecorder is not touched yet
    }

    public void record(String user) {
        recorder.get().recordUser(user);
    }
}
```

Java nullability is JSpecify `org.jspecify.annotations.Nullable` — a **type-use** annotation, so
position matters (`List<@Nullable String>`, `String @Nullable []`). Kotlin expresses it as `T?`;
never carry JSpecify annotations into Kotlin sources.

## Combining Tags and Collections

```java
public final class PrimaryTag { private PrimaryTag() {} }
public final class SecondaryTag { private SecondaryTag() {} }

@Tag(PrimaryTag.class)   @Component public final class PrimaryDatabase   implements Database { }
@Tag(SecondaryTag.class) @Component public final class SecondaryDatabase implements Database { }
@Component                          public final class DefaultDatabase   implements Database { }

@Component
public final class DataService {
    public DataService(
            @Tag(PrimaryTag.class)   Database primary,        // PrimaryDatabase
            @Tag(SecondaryTag.class) Database secondary,      // SecondaryDatabase
            @Tag(Tag.Any.class) All<Database> all,            // all three
            @Tag(PrimaryTag.class) All<Database> primaries,   // only PrimaryTag-tagged
            All<Database> untagged) {                         // only DefaultDatabase
    }
}
```

## Common Mistakes

### Treating `All<T>` as a `List<T>`

```java
// BAD — All<T> extends Iterable<T>; this does not compile
public NotificationService(All<Notifier> notifiers) {
    this.notifiers = notifiers;      // field is List<Notifier>
}

// GOOD
public NotificationService(All<Notifier> notifiers) {
    var copy = new ArrayList<Notifier>();
    notifiers.forEach(copy::add);
    this.notifiers = List.copyOf(copy);
}
```

Keeping the field as `All<Notifier>` and iterating it directly is usually simpler still.

### Tagging every implementation, injecting untagged

```java
// BAD — "No component found for dependency: Cache (no tags)"
@Tag(RedisTag.class)    @Component public final class RedisCache    implements Cache { }
@Tag(CaffeineTag.class) @Component public final class CaffeineCache implements Cache { }

@Component
public final class UserService {
    public UserService(Cache cache) { }
}

// GOOD — ask for the tag you want
@Component
public final class UserService {
    public UserService(@Tag(RedisTag.class) Cache cache) { }
}
```

### Expecting `All<T>` to include tagged components

```java
// BAD — collects only untagged Notifier components
public NotificationService(All<Notifier> notifiers) { }

// GOOD
public NotificationService(@Tag(Tag.Any.class) All<Notifier> notifiers) { }
```

### Calling `refresh()` on `ValueOf`

```java
// BAD — ValueOf<T> has no refresh() in Kora 2.0
valueOf.refresh();

// GOOD — read the current value
var current = valueOf.get();
```

### Untagged implementations left ambiguous

```java
// BAD — "Multiple components match dependency"
@Component public final class RedisCache    implements Cache { }
@Component public final class CaffeineCache implements Cache { }

// GOOD — tag both, or mark one @DefaultComponent
@Tag(RedisTag.class)    @Component public final class RedisCache    implements Cache { }
@Tag(CaffeineTag.class) @Component public final class CaffeineCache implements Cache { }
```

### Building a custom annotation for a one-off tag

```java
// Unnecessary machinery for a tag used once
@Tag(RedisTag.class)
@Target({ElementType.TYPE, ElementType.PARAMETER})
public @interface Redis { }

// Enough
public final class RedisTag { private RedisTag() {} }
```

The meta-annotation form earns its keep only when the tag is applied widely.

## Quick Reference

```java
public final class RedisTag { private RedisTag() {} }                  // tag class

@Tag(RedisTag.class) @Component
public final class RedisCache implements Cache { }                     // tagged component

public UserService(@Tag(RedisTag.class) Cache cache) { }               // tagged injection

public Service(All<Notifier> notifiers) { }                            // untagged only
public Service(@Tag(Tag.Any.class) All<Notifier> notifiers) { }        // everything
public Service(@Tag(RedisTag.class) All<Cache> redis) { }              // one tag only

public Service(ValueOf<Other> other) { }                               // indirect, breaks cycles
public Service(@Nullable Other other) { }                              // optional
public Service(Optional<Other> other) { }                              // optional, wrapped
```

## Related References

- [Component Registration Reference](component-registration-reference.md) — the full resolution order
- [Component Factories Reference](component-factories-reference.md) — `@FactoryModule` and `Tag.Factory`
- [@DefaultComponent Reference](default-component-reference.md) — precedence between candidates
- [Graph Roots & Lifecycle Reference](lifecycle-reference.md) — `Wrapped<T>`, `@Root`
- **kora-di-runtime** — runtime behaviour of `All<T>`, `ValueOf<T>`, `Lifecycle`, `GraphInterceptor`
