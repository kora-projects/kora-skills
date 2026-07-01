---
name: kora-aop-caching
description: "Declarative and imperative caching for Kora via compile-time AOP. Covers @Cacheable (read-through), @CachePut (write-through), @CacheInvalidate (evict / invalidateAll), the typed @Cache contract over CaffeineCache (artifact cache-caffeine, in-process) and RedisCache (artifact cache-redis, Lettuce-backed, distributed), CacheKeyMapper + @Mapping for composite/derived keys, the parameters key attribute, @Json on Redis value types, LoadableCache, and stacked annotations for multi-level L1/L2 caching. Use when adding caching to a Kora service, choosing Caffeine vs Redis, configuring a cache via @ConfigSource paths (maximumSize, expireAfterWrite, keyPrefix), fixing \"required keyPrefix\" graph build failures, or when aspects do not fire because a class is final/not open."
---

# Kora AOP Caching Skill

**Focus:** Declarative caching via compile-time AOP annotations for Caffeine (in-process) and Redis (distributed) caches.

Read this first when:
- Adding cache to methods with `@Cacheable`, `@CachePut`, `@CacheInvalidate`
- Configuring Caffeine or Redis cache backends
- Creating custom cache key mappers with `CacheKeyMapper`
- Setting up multi-level caching (L1 Caffeine + L2 Redis)

---

## Quick Start

### 1. Add Dependencies

All Kora artifacts inherit their version from the `kora-parent` BOM, so never pin a
version on a `ru.tinkoff.kora:*` dependency. The annotation processor is mandatory -
without it the `@Cache`/`@Cacheable` aspects and the typed cache implementation are
never generated.

```groovy
dependencies {
    koraBom platform("ru.tinkoff.kora:kora-parent:$koraVersion")  // e.g. 1.2.17
    annotationProcessor "ru.tinkoff.kora:annotation-processors"   // Kotlin: ksp "ru.tinkoff.kora:symbol-processors"

    // Local cache (Caffeine) - recommended for most cases
    implementation "ru.tinkoff.kora:cache-caffeine"

    // Or distributed cache (Redis/Lettuce) - for multi-pod shared state
    // implementation "ru.tinkoff.kora:cache-redis"
}
```

### 2. Enable in Application

```java
@KoraApp
public interface Application extends CaffeineCacheModule {}
// Or for Redis: extends RedisCacheModule
// Or for multi-level: extends CaffeineCacheModule, RedisCacheModule
```

### 3. Declare Typed Cache

```java
@Cache("orders.cache.config")
public interface OrderCache extends CaffeineCache<UUID, OrderDto> {}
```

### 4. Use Cache Annotations

```java
@Component
public class OrdersService {

    @Cacheable(OrderCache.class)
    public OrderDto get(UUID id) {
        return repository.find(id);
    }

    @CachePut(value = OrderCache.class, parameters = { "id" })
    public OrderDto update(UUID id, OrderDto dto) {
        return repository.save(id, dto);
    }

    @CacheInvalidate(OrderCache.class)
    public void delete(UUID id) {
        repository.delete(id);
    }
}
```

### 5. Add Configuration

```hocon
# Caffeine
orders.cache.config {
  maximumSize = 10000
  expireAfterWrite = "10m"
}

# Redis (requires keyPrefix)
orders.cache.config {
  keyPrefix = "orders"
  expireAfterWrite = "1h"
}
```

---

## Imperative Cache Usage

For programmatic cache usage (stateful caching, manual invalidation, rate limiting) without `@Cacheable` AOP, see [Imperative Cache Reference](references/imperative-cache-reference.md).

---

## Cache Annotations

| Annotation | Purpose | Method Runs | Cache Behavior |
|------------|---------|-------------|----------------|
| `@Cacheable(MyCache.class)` | Read-through cache | On cache miss only | Lookup first; on miss call method, cache result |
| `@CachePut(MyCache.class)` | Write-through cache | Always | Call method, then put result in cache |
| `@CacheInvalidate(MyCache.class)` | Evict by key | Always | Call method, then evict key built from args |
| `@CacheInvalidate(value = MyCache.class, invalidateAll = true)` | Clear entire cache | Always | Call method, then clear all entries |

**Important:** Annotations are repeatable. Stack multiple `@Cacheable` for multi-level caching.

---

## Key Strategies

### Single-Argument Key
```java
@Cacheable(OrderCache.class)
public OrderDto get(UUID id) { /* key = id */ }
```

### Composite Key
```java
@Cache("orders.cache")
public interface OrderCache extends CaffeineCache<OrderCache.Key, OrderDto> {
    record Key(UUID tenantId, UUID orderId) {}
}
@Cacheable(OrderCache.class)
public OrderDto get(UUID tenantId, UUID orderId) { /* key = new Key(tenantId, orderId) */ }
```

### Custom Key Mapper
```java
public static final class OrderContextMapper implements CacheKeyMapper<OrderCache.Key, OrderContext> {
    public OrderCache.Key map(OrderContext ctx) { return new OrderCache.Key(ctx.tenantId(), ctx.orderId()); }
}
@Cacheable(OrderCache.class)
@Mapping(OrderContextMapper.class)
public OrderDto getByContext(OrderContext ctx) { /* key = mapper.map(ctx) */ }
```

### Subset/Reordering with `parameters`
```java
@Cacheable(value = OrderCache.class, parameters = { "orderId", "tenantId" })
public OrderDto get(UUID tenantId, String extra, UUID orderId) { /* key = new Key(orderId, tenantId) */ }
```

See [cache-key-mapper-reference.md](references/cache-key-mapper-reference.md) for details.

---

## Multi-Level Cache (Caffeine + Redis)

```java
@KoraApp
public interface Application extends CaffeineCacheModule, RedisCacheModule {
    @Cache("orders.caffeine.config")
    interface OrderCaffeineCache extends CaffeineCache<UUID, OrderDto> {}

    @Cache("orders.redis.config")
    interface OrderRedisCache extends RedisCache<UUID, @Json OrderDto> {}
}

@Cacheable(OrderCaffeineCache.class)  // L1 first
@Cacheable(OrderRedisCache.class)     // L2 on miss
public OrderDto get(UUID id) { /* Caffeine → Redis → repository */ }
```

See [multi-level-cache-reference.md](references/multi-level-cache-reference.md) for details.

---

## Common Pitfalls

| Problem | Solution |
|---------|----------|
| **Wrong artifact name** | Use `cache-caffeine` not `caffeine-cache`, `cache-redis` not `lettuce-cache` |
| **Class is final (Java) / not open (Kotlin)** | AOP requires subclassing: non-final in Java, `open` in Kotlin |
| **Redis keyPrefix missing** | `keyPrefix` is **required** for Redis - graph build fails without it |
| **Wrong argument order** | Argument order must match record component order, or use `parameters` |
| **Self-invocation bypass** | Call from another bean if cache not triggering on internal calls |
| **Multi-level wrong order** | Stack annotations L1 first (Caffeine), then L2 (Redis) |
| **Redis serialization** | Use `@Json` on value type: `RedisCache<K, @Json V>` |

---

## Imperative API

```java
@Component
public class OrdersService {
    private final OrderCache cache;
    public OrdersService(OrderCache cache) { this.cache = cache; }

    public OrderDto getOrCreate(UUID id) {
        var cached = cache.get(id);
        if (cached != null) return cached;
        var loaded = repository.find(id);
        cache.put(id, loaded);
        return loaded;
    }
}
```

See [cache-caffeine-reference.md](references/cache-caffeine-reference.md) for full API.

---

## Testing

Use `@KoraAppTest(Application.class)` and inject both the service and the cache with
`@TestComponent` (field injection by the Kora JUnit 5 extension - not `@Inject`). Reset
the cache between tests via the imperative API.

```java
@KoraAppTest(Application.class)
class OrdersServiceTest {

    @TestComponent
    private OrdersService service;
    @TestComponent
    private OrderCache cache;

    @BeforeEach
    void cleanup() {
        cache.invalidateAll();
    }

    @Test
    void cachesResultBetweenCalls() {
        var id = UUID.randomUUID();
        var first = service.get(id);
        var second = service.get(id);   // served from cache
        assertEquals(first, second);
    }
}
```

Add `testImplementation "ru.tinkoff.kora:test-junit5"`. See `kora-testing-junit-java`
for the full testing approach.

---

## Reference Documents

| Document | Description |
|----------|-------------|
| [cacheable-reference.md](references/cacheable-reference.md) | `@Cacheable`, `@CachePut`, `@CacheInvalidate` details |
| [cache-key-mapper-reference.md](references/cache-key-mapper-reference.md) | `CacheKeyMapper`, composite keys |
| [cache-caffeine-reference.md](references/cache-caffeine-reference.md) | Caffeine configuration |
| [cache-redis-reference.md](references/cache-redis-reference.md) | Redis/Lettuce configuration |
| [multi-level-cache-reference.md](references/multi-level-cache-reference.md) | L1+L2 patterns |

---

## Common Pitfalls

| Symptom | Fix |
|---------|-----|
| Cache aspect doesn't fire | Class is `final` (Java) or not `open` (Kotlin) — AOP needs inheritance |
| "Required keyPrefix" graph build failure (Redis) | Add `keyPrefix` to cache config section |
| Null value throws on `put()` | Cache values must be `@Nonnull` |
| Need reverse lookup (by value) | Maintain separate index cache |
| Want stateful cache (not memoization) | Use imperative pattern (see [Imperative Cache](references/imperative-cache-reference.md)) |

---

## Assets

Templates: `OrderCache.java.template`, `OrderCache.kt.template`, `CacheConfig.java.template`, `CacheConfig.kt.template`

See [assets/README.md](assets/README.md).

---

## Sources

- Cache module documentation: `.kora-agent/kora-docs/mkdocs/docs/en/documentation/cache.md`
- Cache guide: `.kora-agent/kora-docs/mkdocs/docs/en/guides/cache.md`
- Multi-level cache guide: `.kora-agent/kora-docs/mkdocs/docs/en/guides/cache-multi-level.md`
- Caffeine example: `.kora-agent/kora-examples/examples/java/kora-java-cache-caffeine/`
- Redis example: `.kora-agent/kora-examples/examples/java/kora-java-cache-redis/`
- Guide apps: `.kora-agent/kora-examples/guides/java/kora-java-guide-cache-app/`, `.../kora-java-guide-cache-multi-level-app/`
