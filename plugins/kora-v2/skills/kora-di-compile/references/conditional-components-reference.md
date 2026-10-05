# Conditional Components Reference

**Applies to:** Kora 2.x (`io.koraframework`) — `@Conditional` and `GraphCondition` are **new in 2.0**

## Contents

- [Overview](#overview)
- [The Two Halves](#the-two-halves)
- [Minimal Example](#minimal-example)
- [Choosing Between Implementations](#choosing-between-implementations)
- [@Conditional on a @Root](#conditional-on-a-root)
- [Composing Conditions](#composing-conditions)
- [Failure Modes](#failure-modes)
- [@Conditional vs the Alternatives](#conditional-vs-the-alternatives)
- [Common Mistakes](#common-mistakes)
- [Related References](#related-references)

## Overview

`@Conditional` (`io.koraframework.common.annotation.Conditional`) attaches a runtime predicate to a
component declaration. Every conditional candidate is still **compiled into the graph** — the
processor keeps them all — but only the ones whose condition matches are actually instantiated when
the graph initialises.

That split is the whole design: the wiring is decided at compile time, the selection at startup.
There is no profile system and no configuration-keyed magic; the predicate is a component you write.

```java
@Target({ElementType.TYPE, ElementType.METHOD})
@Retention(RetentionPolicy.RUNTIME)
public @interface Conditional {
    Class<?> tag();
}
```

Note the attribute is named `tag`, and it is **required** — `@Conditional(tag = X.class)`, never
`@Conditional(X.class)`.

## The Two Halves

### 1. A `GraphCondition` component, published under a tag

```java
package io.koraframework.application.graph;

public interface GraphCondition {

    ConditionResult eval();

    sealed interface ConditionResult {
        static ConditionResult matched(String reason);
        static ConditionResult failed(String reason);

        record Matched(String reason) implements ConditionResult { }
        record Failed(String reason) implements ConditionResult { }
    }
}
```

The `reason` string is not decoration — it is what the failure message prints, so make it name the
setting that decided the outcome.

### 2. `@Conditional(tag = …)` on the component or provider

The `tag` value is the class the `GraphCondition` is published under. Using the condition
implementation class as its own tag keeps the two halves obviously paired.

## Minimal Example

```java
// the condition
public final class RedisEnabled implements GraphCondition {

    private final CacheConfig config;

    public RedisEnabled(CacheConfig config) {
        this.config = config;
    }

    @Override
    public ConditionResult eval() {
        return config.redisEnabled()
                ? ConditionResult.matched("cache.redisEnabled = true")
                : ConditionResult.failed("cache.redisEnabled = false");
    }
}
```

```java
// publish it under a tag
@Module
public interface CacheConditionModule {

    @Tag(RedisEnabled.class)
    default GraphCondition redisEnabled(CacheConfig config) {
        return new RedisEnabled(config);
    }
}
```

```java
// gate a component on it
@Component
@Conditional(tag = RedisEnabled.class)
public final class RedisCache implements Cache { }
```

```kotlin
@Component
@Conditional(tag = RedisEnabled::class)
class RedisCache : Cache
```

`@Conditional` also works on a provider method:

```java
@Module
public interface CacheModule {

    @Conditional(tag = RedisEnabled.class)
    default Cache redisCache(RedisClient client) {
        return new RedisCache(client);
    }
}
```

## Choosing Between Implementations

When several candidates satisfy one dependency claim, the processor normally fails with
`Multiple components match dependency`. It makes one exception: if **every** remaining non-default
candidate is `@Conditional`, it defers the choice to graph initialisation and requires exactly one
condition to match.

```java
@Component @Conditional(tag = RedisEnabled.class)
public final class RedisCache implements Cache { }

@Component @Conditional(tag = RedisDisabled.class)
public final class CaffeineCache implements Cache { }

@Component
public final class UserService {
    public UserService(Cache cache) { }   // resolves at startup to exactly one of the two
}
```

The conditions must be genuinely mutually exclusive. If both match you get
`More than one conditional candidates was created`; if neither does, `None of conditional candidates
was created`. Both are startup failures, not compile errors — cover the combination in a test.

Mixing one conditional candidate with one unconditional candidate does **not** work: the
unconditional one is not `@Conditional`, so the exception does not apply and you get the ordinary
`Multiple components match dependency` at compile time. Either gate both, or make the fallback a
`@DefaultComponent`.

## `@Conditional` on a `@Root`

A failed condition on a `@Root` prunes that root and everything reachable only through it:

```java
@KoraApp
public interface Application extends HoconConfigModule {

    static void main(String[] args) { KoraApplication.run(ApplicationGraph::graph); }

    @Root
    @Conditional(tag = MigrationsEnabled.class)
    default MigrationRunner migrations(DataSource dataSource) {
        return new MigrationRunner(dataSource);
    }
}
```

This is the cleanest way to make a startup task optional — better than a `@Root` component whose
`init()` begins with `if (!enabled) return;`.

## Composing Conditions

`GraphCondition` provides static combinators:

```java
GraphCondition.or(a, b)    // matched if any matches
GraphCondition.and(a, b)   // all must match
```

Build a composed condition inside the provider that publishes it:

```java
@Module
public interface ConditionModule {

    @Tag(RedisEnabled.class)
    default GraphCondition redisEnabled(CacheConfig cache, ClusterConfig cluster) {
        return GraphCondition.and(
                () -> cache.redisEnabled()
                        ? GraphCondition.ConditionResult.matched("cache.redisEnabled = true")
                        : GraphCondition.ConditionResult.failed("cache.redisEnabled = false"),
                () -> cluster.multiNode()
                        ? GraphCondition.ConditionResult.matched("cluster.multiNode = true")
                        : GraphCondition.ConditionResult.failed("cluster.multiNode = false"));
    }
}
```

Because a `GraphCondition` is an ordinary component, it can depend on typed config, on
`ValueOf<Config>`, or on anything else already in the graph.

## Failure Modes

All of these happen at **graph initialisation**, after a clean compile:

| Message | Cause |
|---|---|
| `Graph node value was not initialized because condition failed: <reason>` | something asked for a node whose condition failed |
| the same message from a consumer that declared the dependency `@Nullable` / `T?` (or Java `Optional<T>`) | a nullable single dependency is generated as `g.get(node)`, which throws for a condition-failed node. Fixed in `2.0.0.RC2` (kora-projects/kora PR #960) — only `2.0.0.RC1` is affected — the consumer then gets `null`. On RC1, inject `All<T>`, which skips condition-failed members, or make the consumer `@Conditional` on the same tag |
| `None of conditional candidates was created:` (`NoneOfConditionalNodeMatches`) | a claim had only conditional candidates and every condition failed; the message lists each node with its reason |
| `More than one conditional candidates was created:` (`MoreThanOneConditionalNodeMatches`) | two or more conditions matched for the same claim |

Both exception types live in `io.koraframework.application.graph.exception`.

Because conditions are evaluated at startup, a misconfigured condition set is a **deployment-time**
failure. Write a test that boots the graph for each configuration you actually ship.

## `@Conditional` vs the Alternatives

| Goal | Use |
|---|---|
| A library default the application may replace | `@DefaultComponent` |
| One of several implementations, chosen by config at startup | `@Conditional` |
| A branch *inside* one component | a plain `if`/`switch` in a provider |
| A component that may legitimately be absent | `@Nullable` / `Optional<T>` on the consumer — for a `@Conditional` component too since `2.0.0.RC2` (PR #960; on RC1 use `All<T>`, see Failure Modes) |
| Different wiring per Gradle build | separate `@KoraApp` interfaces or submodules |

`@Conditional` is not a profile system. If the choice is fixed at build time, expressing it in the
build is simpler and fails earlier.

## Common Mistakes

### Omitting the `tag =` name

```java
// BAD — Conditional has no value(); this does not compile
@Conditional(RedisEnabled.class)

// GOOD
@Conditional(tag = RedisEnabled.class)
```

### No `GraphCondition` published under that tag

```java
// BAD — nothing provides GraphCondition with @Tag(RedisEnabled.class)
@Component @Conditional(tag = RedisEnabled.class)
public final class RedisCache implements Cache { }

// GOOD — publish the condition too
@Module
public interface ConditionModule {
    @Tag(RedisEnabled.class)
    default GraphCondition redisEnabled(CacheConfig config) { return new RedisEnabled(config); }
}
```

Symptom: `No component found for dependency: GraphCondition with @Tag(…)`.

### Conditions that are not mutually exclusive

```java
// BAD — both match when redis is enabled → MoreThanOneConditionalNodeMatches at startup
@Conditional(tag = RedisEnabled.class)  … implements Cache
@Conditional(tag = CacheConfigured.class) … implements Cache

// GOOD — exactly one matches for any configuration
@Conditional(tag = RedisEnabled.class)  … implements Cache
@Conditional(tag = RedisDisabled.class) … implements Cache
```

### Mixing conditional and unconditional candidates

```java
// BAD — compile error "Multiple components match dependency"
@Component @Conditional(tag = RedisEnabled.class) public final class RedisCache    implements Cache { }
@Component                                        public final class CaffeineCache implements Cache { }

// GOOD — the fallback becomes the default
@Component @Conditional(tag = RedisEnabled.class) public final class RedisCache    implements Cache { }
@Component @DefaultComponent                      public final class CaffeineCache implements Cache { }
```

### An uninformative `reason`

```java
// BAD — the startup failure says only "no"
return ConditionResult.failed("no");

// GOOD — the message names the setting that decided it
return ConditionResult.failed("cache.redisEnabled = false");
```

## Related References

- [Component Registration Reference](component-registration-reference.md) — how conditional candidates fit the resolution order
- [@DefaultComponent Reference](default-component-reference.md) — the other way to resolve a tie
- [Component Factories Reference](component-factories-reference.md) — `@FactoryModule`, generic providers
- [Tags & Collections Reference](tags-collections-reference.md) — how the `tag` is matched
