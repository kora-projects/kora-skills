# Kora cache — distilled reference

**Source:** [.kora-agent/kora-docs/mkdocs/docs/en/documentation/cache.md](.kora-agent/kora-docs/mkdocs/docs/en/documentation/cache.md)  
**Examples:** `.kora-agent/kora-examples/kora-java-cache-caffeine/`, `.kora-agent/kora-examples/kora-java-cache-redis/`

Focused condensation of `kora-docs/.../documentation/cache.md`.

## Two implementations

| Implementation | Artifact | Module | Cache interface |
|----------------|----------|--------|-----------------|
| Caffeine (in-process) | `cache-caffeine` | `CaffeineCacheModule` | `CaffeineCache<K, V>` |
| Redis (distributed) | `cache-redis` | `RedisCacheModule` | `RedisCache<K, V>` |

Use Caffeine by default. Switch to Redis when you need cache state shared across pod replicas, larger-than-heap capacity, or persistence-on-restart guarantees.

Both can be plugged in simultaneously — see "Composite cache" below.

## Caffeine setup

```groovy
implementation "ru.tinkoff.kora:cache-caffeine"
```

```java
@KoraApp
public interface Application extends CaffeineCacheModule, /* ... */ { }
```

### Caffeine config (`<configPath>.config.*`)

```hocon
orders.cache.config {
  expireAfterWrite  = "10m"                    # delete N after put (optional)
  expireAfterAccess = "5m"                     # delete N after last read (optional)
  initialSize       = 100                      # pre-allocated capacity (optional)
  maximumSize       = 10000                    # eviction starts at or before this size (default 100000)
}
```

## Redis setup

```groovy
implementation "ru.tinkoff.kora:cache-redis"
```

```java
@KoraApp
public interface Application extends RedisCacheModule, /* ... */ { }
```

### Lettuce driver config

```hocon
lettuce {
  uri              = ${REDIS_URL}              # required, supports rediss:// for TLS
  user             = ${?REDIS_USER}            # optional
  password         = ${?REDIS_PASSWORD}        # optional
  database         = 0                          # optional
  protocol         = "RESP3"                    # RESP2 or RESP3
  socketTimeout    = "15s"
  commandTimeout   = "15s"
  forceClusterClient = false                    # force cluster mode for single-URI
  ssl {
    ciphers           = ["TLS_CHACHA20_POLY1305_SHA256"]
    handshakeTimeout  = "10s"
  }
}
```

A single Lettuce connection is shared across all `RedisCache` instances.

### Per-cache Redis config

```hocon
orders.cache.config {
  expireAfterWrite  = "1h"                     # optional
  expireAfterAccess = "30m"                    # optional
  keyPrefix         = "orders"                 # REQUIRED — avoids cross-cache collisions
}
```

**`keyPrefix` is required** for Redis caches — graph build fails at startup without it (`RedisCacheConfig.keyPrefix()` is non-`@Nullable`). The empty string `""` is technically allowed, but only if you understand that every other cache writing to the same Redis DB without a prefix will collide on overlapping keys. In multi-cache deployments, always give each cache a non-empty distinct prefix.

## Declaring a typed cache

```java
@Cache("orders.cache")                         // matches the config path
public interface OrderCache extends CaffeineCache<UUID, OrderDto> {}
```

Kora generates the implementation and registers it as a component. Inject directly:

```java
@Component
public final class OrdersService {
    private final OrderCache cache;
    public OrdersService(OrderCache cache) { this.cache = cache; }
}
```

`@Cache` annotation lives at `ru.tinkoff.kora.cache.annotation.Cache`. The cache interface (`Cache`, `CaffeineCache`, `RedisCache`) is at `ru.tinkoff.kora.cache.*` / `ru.tinkoff.kora.cache.caffeine.*` / `ru.tinkoff.kora.cache.redis.*`.

## Cache annotations

| Annotation | Effect | Method semantics |
|-----------|--------|------------------|
| `@Cacheable(MyCache.class)` | Read-through | Lookup; on miss call method, cache result |
| `@CachePut(MyCache.class)` | Write-through | Call method, put result in cache |
| `@CacheInvalidate(MyCache.class)` | Evict by key | Call method, then evict key built from args |
| `@CacheInvalidate(value = MyCache.class, invalidateAll = true)` | Evict all | Call method, then clear the cache |

All in `ru.tinkoff.kora.cache.annotation.*`.

```java
@Component
public class OrdersService {

    @Cacheable(OrderCache.class)
    public OrderDto get(UUID id) { return repo.find(id); }

    @CachePut(OrderCache.class)
    public OrderDto save(UUID id, OrderDto dto) { return repo.save(dto); }

    @CacheInvalidate(OrderCache.class)
    public void delete(UUID id) { repo.delete(id); }

    @CacheInvalidate(value = OrderCache.class, invalidateAll = true)
    public void clearAll() { /* nothing here */ }
}
```

## Key strategies

### Single-arg key

```java
@Cache("orders.cache")
public interface OrderCache extends CaffeineCache<UUID, OrderDto> {}

@Cacheable(OrderCache.class)
public OrderDto get(UUID id) { ... }                          // key = id
```

### Composite key (multiple args)

Define an inner record:

```java
@Cache("orders.cache")
public interface OrderCache extends CaffeineCache<OrderCache.Key, OrderDto> {
    record Key(UUID tenantId, UUID orderId) {}
}

@Cacheable(OrderCache.class)
public OrderDto get(UUID tenantId, UUID orderId) { ... }      // key = new Key(tenantId, orderId)
```

Argument order maps to record component order.

### Custom key projection

Argument can't be a key directly (e.g., domain object). Provide a mapper:

```java
public record UserContext(UUID userId, String traceId) {}

public static final class UserKeyMapper implements CacheKeyMapper<UUID, UserContext> {
    public UUID map(UserContext ctx) { return ctx.userId(); }
}

@Cacheable(OrderCache.class)
@Mapping(UserKeyMapper.class)
public OrderDto get(UserContext ctx) { ... }                  // key = ctx.userId()
```

### Subset / reordering — `parameters`

```java
@Cacheable(value = OrderCache.class, parameters = {"orderId", "tenantId"})
public OrderDto get(UUID tenantId, String unrelated, UUID orderId) { ... }
// key = new Key(orderId, tenantId)  — order matches `parameters`, skipping `unrelated`
```

Use when the method takes more args than the key, or when arg order doesn't match the record constructor.

## Composite cache (multi-layer)

Caffeine in front of Redis is a common pattern — fast local read, fall back to Redis if missing:

```java
@KoraApp
public interface Application extends CaffeineCacheModule, RedisCacheModule {

    @Cache("orders.caffeine.config")
    interface OrderCaffeineCache extends CaffeineCache<UUID, OrderDto> {}

    @Cache("orders.redis.config")
    interface OrderRedisCache extends RedisCache<UUID, OrderDto> {}
}

@Cacheable(OrderCaffeineCache.class)
@Cacheable(OrderRedisCache.class)
public OrderDto get(UUID id) { ... }
```

Aspects apply in declaration order, top to bottom. With the order above:
- read: first try Caffeine; on miss try Redis; on miss call the method; populate both caches on the way back.
- The method body sees the call only on full miss.

## Async caching (`AsyncCache`)

`RedisCache` implements both `Cache<K, V>` (sync) and `AsyncCache<K, V>` (async, `CompletionStage`-based). Useful for non-blocking handler chains.

Caffeine `CaffeineCache` is sync-only.

## `LoadableCache<K, V>` — get-or-load without aspects

```java
@KoraApp
public interface Application extends CaffeineCacheModule {

    @Cache("orders.cache")
    interface OrderCache extends CaffeineCache<UUID, OrderDto> {}

    @Root
    default LoadableCache<UUID, OrderDto> orderLoadableCache(OrderCache cache, OrdersRepository repo) {
        return cache.asLoadable(repo::find);
    }
}
```

```java
@Component
public class OrdersService {
    private final LoadableCache<UUID, OrderDto> cache;
    public OrdersService(LoadableCache<UUID, OrderDto> cache) { this.cache = cache; }

    public OrderDto get(UUID id) {
        return cache.get(id);                                  // load on miss via repo::find
    }
}
```

Useful in tests, library code, or anywhere `@Cacheable` would be awkward (lambdas, multiple lookups in one method).

## Imperative API

```java
@Component
public class OrdersService {
    private final OrderCache cache;
    public OrdersService(OrderCache cache) { this.cache = cache; }

    public OrderDto get(UUID id) {
        var hit = cache.get(id);
        if (hit != null) return hit;
        var loaded = repo.find(id);
        cache.put(id, loaded);
        return loaded;
    }
}
```

`Cache<K, V>` provides `get`, `put`, `invalidate`, `invalidateAll`, batch variants. `AsyncCache<K, V>` mirrors with `CompletionStage` returns.

## Signatures supported

| Java | Kotlin |
|------|--------|
| `T method()` | `fun method(): T` |
| `@Nullable T method()` | `fun method(): T?` |
| `Optional<T> method()` | — |
| `Mono<T>` (with reactor-core) | `suspend fun method(): T` (with coroutines) |

Java: class non-final. Kotlin: class `open`.
