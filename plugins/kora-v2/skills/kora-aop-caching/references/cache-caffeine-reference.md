# Caffeine cache reference

**Artifact:** `io.koraframework:cache-caffeine`
**Module:** `io.koraframework.cache.caffeine.CaffeineCacheModule`
**Contract:** `io.koraframework.cache.caffeine.CaffeineCache<K, V> extends Cache<K, V>`
**Config type:** `io.koraframework.cache.caffeine.CaffeineCacheConfig`

---

## Contents

- [When to use it](#when-to-use-it)
- [Setup](#setup)
- [Configuration keys](#configuration-keys)
- [Telemetry](#telemetry)
- [The CaffeineCache contract](#the-caffeinecache-contract)
- [LoadableCache](#loadablecache)
- [Customising the factory](#customising-the-factory)
- [Testing](#testing)
- [Troubleshooting](#troubleshooting)

---

## When to use it

Use Caffeine when the cache is per-process: small hot data, single instance, or an L1 in front of a
shared L2. Do not use it alone when several pods must agree on the cached value, or when the cache
must survive a restart — that is Redis' job.

The library version is pinned by the BOM (Caffeine `3.3.0` in the 2.0 line); do not add
`com.github.ben-manes.caffeine:caffeine` yourself.

---

## Setup

```groovy
dependencies {
    koraBom platform("io.koraframework:kora-bom:$koraVersion")
    annotationProcessor "io.koraframework:annotation-processors"
    implementation "io.koraframework:cache-caffeine"
    implementation "io.koraframework:config-hocon"
}
```

```java
@KoraApp
public interface Application extends HoconConfigModule, LogbackModule, CaffeineCacheModule {

    static void main(String[] args) {
        KoraApplication.run(ApplicationGraph::graph);
    }
}
```

```java
@Cache("orders.cache")
public interface OrderCache extends CaffeineCache<UUID, OrderDto> {}
```

```kotlin
@Cache("orders.cache")
interface OrderCache : CaffeineCache<UUID, OrderDto>
```

`CaffeineCacheModule` supplies a `@DefaultComponent CaffeineCacheFactory` and a
`@DefaultComponent CaffeineCacheTelemetryFactory`, and it inherits `CacheCommonModule` (which
publishes the `@Tag(CacheMode.class) Executor` used by `CacheMode.ASYNC`). The per-cache
`$OrderCache_Impl` and `$OrderCache_Module` are generated from the `@Cache` interface and picked up
automatically.

---

## Configuration keys

The path comes from `@Cache("…")`. Dotted (`cache.caffeine.users`) and hyphenated (`pet-cache`)
paths both work; the migrated examples use both.

```hocon
orders.cache {
  maximumSize       = 10000     # default 100000
  initialSize       = 100       # optional, Caffeine initialCapacity
  expireAfterWrite  = "10m"     # optional
  expireAfterAccess = "5m"      # optional
  enabled           = true      # default true

  telemetry {
    logging.enabled = false     # default false
    metrics.enabled = false     # default false
    tracing.enabled = true      # default true
  }
}
```

| Key | Type | Default | Notes |
|---|---|---|---|
| `enabled` | boolean | `true` | `false` turns the cache into a pass-through: `get` returns null, `computeIfAbsent` calls the loader every time, writes and evictions are no-ops |
| `maximumSize` | long | `100000` | always applied — there is no "unbounded" setting |
| `initialSize` | int | *unset* | Caffeine `initialCapacity` |
| `expireAfterWrite` | Duration | *unset* | |
| `expireAfterAccess` | Duration | *unset* | |
| `telemetry.logging.enabled` | boolean | `false` | |
| `telemetry.metrics.enabled` | boolean | `false` | |
| `telemetry.metrics.tags` | map | `{}` | extra tags, also applied to the Caffeine binder |
| `telemetry.metrics.slo` | Duration[] | Kora default SLO buckets | |
| `telemetry.tracing.enabled` | boolean | `true` | |

There is **no** `refreshAfterWrite`, `weakKeys`, `softValues`, `recordStats` or `evictionListener`
key — `CaffeineCacheConfig` exposes exactly the fields above.

Durations use the HOCON duration syntax (`"10m"`, `10s`, `"1h"`, `"250ms"`).

`enabled = false` is the clean way to switch a cache off in one environment. `maximumSize = 0` is
the trick the `kora-java-crud` integration test uses to make a Caffeine cache never retain anything.

---

## Telemetry

Defaults are **logging off, metrics off, tracing on** — the same defaults as every other Kora 2.0
component. A dashboard that shows nothing is almost always this.

```hocon
orders.cache.telemetry {
  logging.enabled = true
  metrics.enabled = true
}
```

Caffeine metrics come from Micrometer's Caffeine instrumentation, not from Kora's own timers:
`CaffeineFactory` builds the cache with `recordStats()` and binds it with Micrometer's
`CaffeineCacheMetrics` under the cache's config path, with `telemetry.metrics.tags` added — and only
when `telemetry.metrics.enabled = true` **and** a `MeterRegistry` is in the graph. The published
meters are Micrometer's standard cache set: `cache.gets` (`result` = `hit`/`miss`), `cache.puts`,
`cache.evictions`, `cache.eviction.weight` and `cache.size`, each tagged `cache` = that name. Kora's
`cache.operation.duration` / `cache.requests` series are not emitted for Caffeine
(`DefaultCaffeineCacheTelemetry` never calls its metrics factory); they exist for Redis. See
`kora-telemetry-metrics` for the metrics module itself.

A Caffeine cache opens no spans (`DefaultCaffeineCacheObservation` only logs). Its logs carry
`system.config` (the config path), `system.name.simple` and `system.name.canonical` (the generated
cache implementation), plus the `operation` key
(`GET`, `GET_MANY`, `GET_ALL`, `PUT`, `PUT_MANY`, `COMPUTE_IF_ABSENT`, `COMPUTE_IF_ABSENT_MANY`,
`INVALIDATE`, `INVALIDATE_MANY`, `INVALIDATE_ALL`).

---

## The `CaffeineCache` contract

`CaffeineCache<K, V>` adds one method to `Cache<K, V>`:

```java
Map<K, V> getAll();     // every live entry, unmodifiable view
```

Everything else — `get`, `get(Collection)`, `put`, `put(Map)`, `computeIfAbsent`, `invalidate`,
`invalidate(Collection)`, `invalidateAll`, `asLoadable*` — comes from `Cache<K, V>`; see
[imperative-cache-reference.md](imperative-cache-reference.md).

Behaviour worth knowing:

- `get(key)` returns `null` on a miss and on a `null` key.
- `put(key, value)` **silently skips** null keys and null values; nothing is thrown.
- `computeIfAbsent` delegates to Caffeine's `Cache#get(key, mappingFunction)`, so the loader runs
  once per key under Caffeine's own lock; returning `null` from the loader stores nothing.
- Exceptions from Caffeine propagate to the caller (unlike the Redis cache, which swallows them).

---

## `LoadableCache`

`LoadableCache<K, V>` is a read-only get-or-load view over a `Cache`:

```java
@Nullable V get(K key);
Map<K, V> get(Collection<K> keys);
```

Build it from any cache — note the two factory methods have different loader shapes:

```java
Cache<K, V>.asLoadableSimple(Function<K, V> loader)                  // one key at a time
Cache<K, V>.asLoadable(Function<Collection<K>, Map<K, V>> loader)    // bulk loader
```

`asLoadable` is the bulk form; passing a single-key method reference to it does not compile. Expose
it as a module component:

```java
@KoraApp
public interface Application extends HoconConfigModule, CaffeineCacheModule {

    default LoadableCache<UUID, OrderDto> orderLoadableCache(OrderCache cache, OrderRepository repository) {
        return cache.asLoadableSimple(repository::find);
    }
}
```

```java
@Component
public class OrderService {

    private final LoadableCache<UUID, OrderDto> cache;

    public OrderService(LoadableCache<UUID, OrderDto> cache) { this.cache = cache; }

    public OrderDto get(UUID id) {
        return cache.get(id);           // loads through repository::find on a miss
    }
}
```

No `@Root` is needed when something injects it; `@Root` is only for components nothing depends on.

---

## Customising the factory

`CaffeineCacheFactory` is a `@DefaultComponent`, so your own `@Component` replaces it for every
Caffeine cache in the graph:

```java
public interface CaffeineCacheFactory {
    <K, V> com.github.benmanes.caffeine.cache.Cache<K, V> build(String name, CaffeineCacheConfig config);
}
```

This is the hook for Caffeine features Kora's config does not expose (weak keys, removal listeners,
a custom `Ticker`). Read the config fields you still want to honour — `expireAfterWrite`,
`expireAfterAccess`, `initialSize`, `maximumSize` — because the default implementation is bypassed
entirely.

---

## Testing

```java
@KoraAppTest(Application.class)
class OrderServiceTests {

    @TestComponent
    private OrderService service;
    @TestComponent
    private OrderCache cache;

    @BeforeEach
    void cleanup() {
        cache.invalidateAll();
    }

    @Test
    void servesSecondCallFromCache() {
        var id = UUID.randomUUID();
        var first = service.get(id);
        assertEquals(first, service.get(id));
    }

    @Test
    void reloadsAfterInvalidate() {
        var id = UUID.randomUUID();
        var first = service.get(id);
        service.delete(id);
        assertNotEquals(first, service.get(id));
    }
}
```

Add `testImplementation "io.koraframework:test-junit5"`. `@KoraAppTest` and `@TestComponent` live in
`io.koraframework.test.extension.junit5`; the extension performs field injection, so no `@Inject`.
To disable a cache for one test class, override its config with `KoraAppTestConfigModifier` and
either `enabled = false` or `maximumSize = 0`.

---

## Troubleshooting

| Symptom | Cause |
|---|---|
| `No component found for dependency: OrderCache (no tags)` | the annotation processor / KSP is not on the build, or the `@Cache` interface is not compiled |
| `@Cache interface '…' does not implement a supported cache contract.` | extend `CaffeineCache<K, V>` (or `RedisCache<K, V>`), not `Cache<K, V>` |
| `AOP aspect cannot be applied to class '…' because the class is final.` | Java target class is `final` |
| `AOP aspect cannot be applied to class '…' because the class is not open.` | Kotlin class (and its annotated functions) must be `open` |
| aspect generated, cache never consulted | self-invocation — the call must arrive through the injected proxy |
| everything is a miss | `enabled = false`, or `maximumSize = 0`, in that cache's config section |
| no metrics | `telemetry.metrics.enabled` defaults to `false` |
| `ConfigValueException: … at path: 'ROOT.orders.cache…'` | the `@Cache` path and the config section disagree |

---

## See also

- [cacheable-reference.md](cacheable-reference.md) — the operation annotations
- [cache-redis-reference.md](cache-redis-reference.md) — the distributed backend
- [multi-level-cache-reference.md](multi-level-cache-reference.md) — Caffeine as L1 in front of Redis
- [imperative-cache-reference.md](imperative-cache-reference.md) — the `Cache<K, V>` API
