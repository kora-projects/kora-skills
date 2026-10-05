---
name: kora-aop-caching
description: "Kora 2.0 declarative caching via compile-time AOP — @Cacheable / @CachePut / @CacheInvalidate / @CacheInvalidateAll from io.koraframework.cache.annotation, with the args key attribute and CacheMode.SYNC|ASYNC. Covers the typed @Cache interface over CaffeineCache (io.koraframework:cache-caffeine) or RedisCache (io.koraframework:cache-redis-lettuce + LettuceRedisCacheModule), CacheKeyMapper + @Mapping, @Json Redis value types, LoadableCache, and stacked L1/L2 multi-level caching. Use when adding caching to a Kora service, choosing Caffeine vs Redis, porting Kora 1.x parameters= / invalidateAll=true, or debugging \"Config expected value, but got null at path: 'ROOT.<cache>.keyPrefix'\"."
license: Apache-2.0
metadata:
  version: "0.1.0"
  kora-version: "2.x"
---

# Kora AOP Caching

> **Kora sub-skill — obey the [kora-v2 meta rules](../../SKILL.md) on every task:** **R0** ground the workspace on Kora 2.0 refs before starting (framework source at tag `2.0.0.RC2` + `kora-examples` at `migration/2.0` + Kora 2.0 docs at koraframework.io/v2, which trail the source; 1.x `kora-docs` pages are never an authority) · **R1** read this sub-skill before writing code · **R2** Kora 2.0 APIs only — no Spring/Micronaut/Quarkus, no Kora 1.x APIs, no invented annotations or config keys · **R3** journal any incorrect Kora usage. Add comments/Javadoc only if asked.

| | |
|---|---|
| **Annotations** | `io.koraframework.cache.annotation.*` — `@Cache`, `@Cacheable`, `@CachePut`, `@CacheInvalidate`, `@CacheInvalidateAll`, `CacheMode` |
| **Contracts** | `io.koraframework.cache.{Cache, CacheKeyMapper, LoadableCache}` |
| **Caffeine** | artifact `io.koraframework:cache-caffeine`, module `CaffeineCacheModule`, contract `io.koraframework.cache.caffeine.CaffeineCache<K, V>` |
| **Redis** | artifact `io.koraframework:cache-redis-lettuce`, module **`LettuceRedisCacheModule`**, contract `io.koraframework.cache.redis.RedisCache<K, V>` |
| **Processor** | Java `annotationProcessor "io.koraframework:annotation-processors"` · Kotlin `ksp "io.koraframework:symbol-processors"` |
| **Execution** | Synchronous only. No `Mono`/`Flux`, no `CompletionStage`, no Kotlin `suspend`. |

Read this skill when you are:

- adding `@Cacheable` / `@CachePut` / `@CacheInvalidate` / `@CacheInvalidateAll` to a service method
- declaring a typed `@Cache` interface and its config section
- choosing Caffeine (in-process) vs Redis (shared) or stacking both as L1/L2
- deriving a cache key with `CacheKeyMapper` and `@Mapping`
- porting Kora 1.x cache code (`parameters =`, `invalidateAll = true`, `cache-redis`)

---

## 1. What changed from Kora 1.x

| Kora 1.x | Kora 2.0 |
|---|---|
| `ru.tinkoff.kora.cache.*` | `io.koraframework.cache.*` |
| `@Cacheable(value = X.class, parameters = "id")` | `@Cacheable(value = X.class, args = "id")` |
| `@CacheInvalidate(value = X.class, invalidateAll = true)` | **`@CacheInvalidateAll(X.class)`** — the `invalidateAll` attribute no longer exists |
| artifact `cache-redis` | **`cache-redis-lettuce`** (`cache-redis` is not in the 2.0 BOM) |
| `RedisCacheModule` supplied the client | `RedisCacheModule` is transport-neutral and supplies **no** `RedisCacheClient`; use **`LettuceRedisCacheModule`** |
| `LettuceConfigurator` | removed — use `@Tag(Tag.Factory.class)` `Configurer<...>` components |
| `ru.tinkoff.kora.common.Mapping` | `io.koraframework.common.annotation.Mapping` |
| reactive/`suspend` cached methods | removed; cache AOP is synchronous |
| — | **new:** `CacheMode.SYNC` / `CacheMode.ASYNC` on every operation annotation |
| — | **new:** repeatable containers `@Cacheables`, `@CachePuts`, `@CacheInvalidates`, `@CacheInvalidateAlls` |

A blind `parameters` → `args` search-and-replace is unsafe: HOCON and YAML files legitimately contain `parameters =` keys. Change only the cache annotations.

---

## 2. Quick start

### 2.1 Dependencies

`koraVersion=2.0.0.RC2` from plain `mavenCentral()`; the BOM is `io.koraframework:kora-bom`.
Never pin a version on an individual `io.koraframework:*` artifact.

```groovy
dependencies {
    koraBom platform("io.koraframework:kora-bom:$koraVersion")
    annotationProcessor "io.koraframework:annotation-processors"   // mandatory

    implementation "io.koraframework:cache-caffeine"               // in-process
    // implementation "io.koraframework:cache-redis-lettuce"       // distributed
    // implementation "io.koraframework:json-common"               // only for @Json Redis values
}
```

Kotlin (`build.gradle.kts`):

```kotlin
dependencies {
    implementation(platform("io.koraframework:kora-bom:${property("koraVersion")}"))
    ksp("io.koraframework:symbol-processors:${property("koraVersion")}")
    implementation("io.koraframework:cache-caffeine")
}
```

Without the processor no `$XxxCache_Impl`, no `$XxxCache_Module` and no aspect is generated, and the
graph fails with `No component found for dependency: XxxCache (no tags)`.

### 2.2 Connect the module

```java
@KoraApp
public interface Application extends HoconConfigModule, LogbackModule, CaffeineCacheModule {

    static void main(String[] args) {
        KoraApplication.run(ApplicationGraph::graph);
    }
}
```

Only the backend module goes on `@KoraApp`. The per-cache module `$OrderCache_Module` generated from
your `@Cache` interface is discovered automatically — do **not** extend it.

### 2.3 Declare the typed cache

```java
@Cache("orders.cache")
public interface OrderCache extends CaffeineCache<UUID, OrderDto> {}
```

`@Cache` targets an **interface** that extends exactly one of `CaffeineCache<K, V>` or
`RedisCache<K, V>`; its `value` is the config path.

### 2.4 Annotate the methods

```java
@Component
public class OrderService {                      // must not be final

    @Cacheable(OrderCache.class)
    public OrderDto get(UUID id) {
        return repository.find(id);
    }

    @CachePut(value = OrderCache.class, args = "id")
    public OrderDto update(UUID id, OrderRequest request) {
        return repository.save(id, request);
    }

    @CacheInvalidate(OrderCache.class)
    public void delete(UUID id) {
        repository.delete(id);
    }

    @CacheInvalidateAll(OrderCache.class)
    public void deleteAll() {
        repository.deleteAll();
    }
}
```

Kotlin: the class **and** every annotated function must be `open`.

```kotlin
@Component
open class OrderService(private val repository: OrderRepository) {

    @Cacheable(OrderCache::class)
    open fun get(id: UUID): OrderDto = repository.find(id)

    @CachePut(value = OrderCache::class, args = ["id"])
    open fun update(id: UUID, request: OrderRequest): OrderDto = repository.save(id, request)

    @CacheInvalidateAll(OrderCache::class)
    open fun deleteAll() = repository.deleteAll()
}
```

### 2.5 Configure

```hocon
orders.cache {
  maximumSize = 10000
  expireAfterWrite = "10m"
}
```

---

## 3. The four operation annotations

All four take `Class<? extends Cache<?, ?>> value()`, and all are repeatable.

| Annotation | Extra attributes | Method runs | Effect |
|---|---|---|---|
| `@Cacheable` | `args`, `mode` | only on a miss | look up, on miss call the method and store the result |
| `@CachePut` | `args`, `mode` | always | call the method, then store the returned value |
| `@CacheInvalidate` | `args`, `mode` | always | call the method, then `invalidate(key)` |
| `@CacheInvalidateAll` | `mode` | always | call the method, then `invalidateAll()` |

- `args` is `String[]` — the **method parameter names** that make up the key. Empty (the default)
  means *all* parameters, in declaration order. A single name may be written unbraced:
  `args = "id"`.
- `mode` is `CacheMode.SYNC` (default) or `CacheMode.ASYNC`. See §6.
- `@Cacheable` and `@CachePut` reject `void`/`Unit` returns; all four reject `Publisher` and
  `Future` returns.
- One method carries **one** operation kind. Mixing kinds is a compile error.

Details, generated shapes and the exact diagnostics: [cacheable-reference.md](references/cacheable-reference.md).

---

## 4. Cache keys

| Situation | What the processor emits |
|---|---|
| one key parameter | the parameter itself |
| several parameters, key type has a matching public constructor (record / data class) | `new Key(a, b)` |
| several parameters, no matching constructor | injects a `CacheKeyMapper.CacheKeyMapperN<Key, A, B, …>` component |
| `@Mapping(SomeMapper.class)` on the method | injects `SomeMapper` and calls `map(...)` |

```java
@Cache("orders.cache")
public interface OrderCache extends CaffeineCache<OrderCache.Key, OrderDto> {
    record Key(UUID tenantId, UUID orderId) {}
}

@Cacheable(OrderCache.class)
public OrderDto get(UUID tenantId, UUID orderId) { … }          // key = new Key(tenantId, orderId)

@Cacheable(value = OrderCache.class, args = { "orderId", "tenantId" })
public OrderDto find(UUID tenantId, String trace, UUID orderId) { … }  // key = new Key(orderId, tenantId)
```

**Every class named in `@Mapping` must be a `@Component`** — nested classes included. The cache
processor always *injects* the mapper; unlike HTTP mappers it never constructs a dependency-free one
itself, so a mapper without `@Component` fails with `No component found for dependency`.

See [cache-key-mapper-reference.md](references/cache-key-mapper-reference.md).

---

## 5. Caffeine vs Redis

|  | Caffeine | Redis |
|---|---|---|
| Artifact | `io.koraframework:cache-caffeine` | `io.koraframework:cache-redis-lettuce` |
| Module | `CaffeineCacheModule` | `LettuceRedisCacheModule` |
| Contract | `CaffeineCache<K, V>` (adds `getAll()`) | `RedisCache<K, V>` (adds `putExpireAfterWrite(...)`) |
| Scope | one JVM, lost on restart | shared across pods, survives restart |
| Required config | none — `maximumSize` defaults to `100000` | **`keyPrefix`** plus a `lettuce { uri = … }` section |
| Errors | propagate | Redis failures swallowed (a failed read is a miss); loader exceptions propagate |
| `CacheMode.ASYNC` | ignored (compile warning) | honoured |

```java
@Cache("orders.redis")
public interface OrderRedisCache extends RedisCache<UUID, @Json OrderDto> {}
```

The `@Json` on the **value type argument** is what selects the JSON `RedisCacheValueMapper`; the DTO
itself also needs `@Json` so a `JsonReader`/`JsonWriter` is generated.

[cache-caffeine-reference.md](references/cache-caffeine-reference.md) ·
[cache-redis-reference.md](references/cache-redis-reference.md)

---

## 6. `CacheMode`

```java
public enum CacheMode { SYNC, ASYNC }
```

`SYNC` (the default) performs the cache write or eviction on the calling thread. `ASYNC` hands the
`put` / `invalidate` / `invalidateAll` to an `Executor` published by `CacheCommonModule` under
`@Tag(CacheMode.class)`; the default implementation starts one virtual thread named `kora-cache-N`
per operation and logs failures as
`Cache asynchronous operation failed on thread {}`.

- The cache **read** is never asynchronous; only the write side moves off-thread.
- `ASYNC` on a `CaffeineCache` is ignored, with the compile warning
  `Cache async mode is ignored for CaffeineCache <fqn>`.
- Use it for a Redis L2 whose write latency you do not want on the request path; accept that a
  failed write is only logged.
- Override the executor with your own `@Component @Tag(CacheMode.class) Executor`.

---

## 7. Multi-level (L1 Caffeine + L2 Redis)

Stack the annotations — first listed is checked first, and a deeper hit back-fills every shallower
level.

```java
@Cacheable(UserCaffeineCache.class)   // L1
@Cacheable(UserRedisCache.class)      // L2
public Optional<UserResponse> getUser(String id) {
    return userRepository.findById(id);
}
```

Repeated annotations on one method must use the **same** `args` list. See
[multi-level-cache-reference.md](references/multi-level-cache-reference.md).

---

## 8. Imperative use

`Cache<K, V>` is injectable on its own — `get`, `get(Collection)`, `put`, `put(Map)`,
`computeIfAbsent`, `invalidate`, `invalidate(Collection)`, `invalidateAll`, plus
`asLoadableSimple(loader)` / `asLoadable(bulkLoader)` for a `LoadableCache`.

```java
@Component
public class OrderService {

    private final OrderCache cache;

    public OrderService(OrderCache cache) { this.cache = cache; }

    public OrderDto getOrLoad(UUID id) {
        return cache.computeIfAbsent(id, repository::find);
    }
}
```

See [imperative-cache-reference.md](references/imperative-cache-reference.md).

---

## 9. Testing

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
        assertEquals(service.get(id), service.get(id));
    }
}
```

`@KoraAppTest` / `@TestComponent` come from `io.koraframework:test-junit5`
(`io.koraframework.test.extension.junit5`). Field injection is done by the extension — do not add
`@Inject`. Setting `<cache-path>.maximumSize = 0` in a test config is the cheap way to disable a
Caffeine cache for a test. See `kora-testing-junit-java` / `kora-testing-junit-kotlin`.

---

## 10. Pitfalls

| Symptom | Cause and fix |
|---|---|
| `AOP aspect cannot be applied to class '…' because the class is final.` | Java target class is `final` — remove the modifier. |
| `AOP aspect cannot be applied to class '…' because the class is not open.` | Kotlin class is not `open`. The function must be `open` too, otherwise: `AOP aspect cannot be applied to function '…' because the function is not open.` |
| `AOP aspect cannot be applied to method '…' because the method is private.` | Cache AOP overrides the method; make it public/protected/package-private. |
| Aspect compiled but never runs | Self-invocation. Only calls that go through the injected `$Service__AopProxy` are intercepted. |
| `ConfigValueException: Config expected value, but got null at path: 'ROOT.orders.redis.keyPrefix' for origin '…'` | `RedisCacheConfig.keyPrefix()` has no default and is not `@Nullable`. Add it. Fails at **graph init**, not at compile time. |
| `invalidateAll()` wiped the whole Redis database | `keyPrefix = ""` makes `invalidateAll()` fall back to `FLUSHALL`. There is a warning (`Redis Cache key prefix is empty! …`) but it goes to the cache's own logger, which is a no-op logger unless that section sets `telemetry.logging.enabled = true` — by default you get **no** warning. Always set a non-blank prefix. |
| `No component found for dependency: <Mapper> (no tags)` | The `@Mapping` key mapper is not a `@Component`. |
| `No component found for dependency: RedisCacheClient (no tags)` | `RedisCacheModule` was connected instead of `LettuceRedisCacheModule`, or `cache-redis-lettuce` is missing. |
| `Cache annotations on '…' use different key argument lists.` | Repeated annotations on one method disagree on `args`. |
| `@Cacheable cannot be applied to '…' because the method returns void.` | `@Cacheable` / `@CachePut` need a value to cache. |
| No cache metrics in Prometheus | Cache telemetry defaults are `logging.enabled = false`, `metrics.enabled = false` (`tracing.enabled = true`). Enable per cache section. |
| `cache.put(key, null)` appears to do nothing | Both backends silently skip null keys and null values; nothing is stored and nothing is thrown. |

---

## 11. Reference documents

| Document | Content |
|---|---|
| [cacheable-reference.md](references/cacheable-reference.md) | the four operation annotations, `args`, `CacheMode`, return types, diagnostics |
| [cache-key-mapper-reference.md](references/cache-key-mapper-reference.md) | `CacheKeyMapper`, `@Mapping`, composite keys, Redis record keys |
| [cache-caffeine-reference.md](references/cache-caffeine-reference.md) | `CaffeineCacheModule`, config keys, metrics, testing |
| [cache-redis-reference.md](references/cache-redis-reference.md) | `LettuceRedisCacheModule`, `lettuce` config, `keyPrefix`, value mappers |
| [multi-level-cache-reference.md](references/multi-level-cache-reference.md) | stacked annotations, back-fill order, invalidation |
| [imperative-cache-reference.md](references/imperative-cache-reference.md) | `Cache<K, V>` API, `LoadableCache`, facade cache |

---

## 12. Assets

| Template | Content |
|---|---|
| `assets/OrderCache.java.template` | typed caches, key mapper, service with all four annotations (Java) |
| `assets/OrderCache.kt.template` | the same in Kotlin, with the `open` requirements |
| `assets/CacheConfig.java.template` | `@KoraApp` wiring, HOCON for Caffeine/Redis/Lettuce, `Configurer` (Java) |
| `assets/CacheConfig.kt.template` | the same in Kotlin |
