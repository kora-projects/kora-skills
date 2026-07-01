# Caffeine Cache Reference

**Module:** `CaffeineCacheModule`  
**Artifact:** `ru.tinkoff.kora:cache-caffeine`  
**Interface:** `CaffeineCache<K, V>`

---

## Contents

- [When to Use Caffeine](#when-to-use-caffeine)
- [Setup](#setup)
- [Configuration](#configuration)
- [Complete Example](#complete-example)
- [Imperative API](#imperative-api)
- [LoadableCache Pattern](#loadablecache-pattern)
- [Metrics](#metrics)
- [Testing](#testing)
- [Troubleshooting](#troubleshooting)

---

## When to Use Caffeine

**Use Caffeine when:**
- Single-instance application (no shared state needed)
- Cache warm-up is acceptable after restart
- Lowest latency is critical (in-process access)
- Data fits in heap memory

**Don't use Caffeine when:**
- Multi-pod/stateless deployment (use Redis)
- Cache must survive restarts
- Cache size exceeds heap capacity

---

## Setup

### 1. Add Dependency

```groovy
implementation "ru.tinkoff.kora:cache-caffeine"
```

### 2. Enable Module

```java
@KoraApp
public interface Application extends CaffeineCacheModule {}
```

### 3. Declare Typed Cache

```java
@Cache("orders.cache.config")
public interface OrderCache extends CaffeineCache<UUID, OrderDto> {}
```

Kora generates the implementation and registers it as a component.

---

## Configuration

### HOCON Config

```hocon
orders.cache.config {
  expireAfterWrite  = "10m"     # delete entry 10m after write (optional)
  expireAfterAccess = "5m"      # delete entry 5m after last read (optional)
  initialSize       = 100       # pre-allocate capacity (optional)
  maximumSize       = 10000     # eviction threshold (default: 100000)
}
```

### Parameters

| Parameter | Description | Default | Required |
|-----------|-------------|---------|----------|
| `expireAfterWrite` | Delete entry after time since write | — | No |
| `expireAfterAccess` | Delete entry after time since last access | — | No |
| `initialSize` | Pre-allocate capacity | — | No |
| `maximumSize` | Max entries before LRU eviction | 100000 | No |

**Duration format:** `"10m"`, `"1h"`, `"30s"`, `"1d"`

---

## Complete Example

```java
package com.example.app.cache;

import com.example.app.dto.OrderDto;
import ru.tinkoff.kora.cache.annotation.Cache;
import ru.tinkoff.kora.cache.annotation.Cacheable;
import ru.tinkoff.kora.cache.caffeine.CaffeineCache;
import ru.tinkoff.kora.common.Component;
import java.util.UUID;

// 1. Typed cache interface
@Cache("orders.cache.config")
public interface OrderCache extends CaffeineCache<UUID, OrderDto> {}

// 2. Service with caching
@Component
public class OrdersService {
    
    private final OrderCache cache;
    private final OrdersRepository repository;
    
    public OrdersService(OrderCache cache, OrdersRepository repository) {
        this.cache = cache;
        this.repository = repository;
    }
    
    @Cacheable(OrderCache.class)
    public OrderDto get(UUID id) {
        return repository.find(id);
    }
}
```

### application.conf

```hocon
orders.cache.config {
  maximumSize = 10000
  expireAfterWrite = "10m"
}
```

---

## Imperative API

Inject the typed cache for manual control:

```java
@Component
public class OrdersService {
    private final OrderCache cache;
    
    public OrdersService(OrderCache cache) {
        this.cache = cache;
    }
    
    public OrderDto getOrCreate(UUID id) {
        var cached = cache.get(id);
        if (cached != null) {
            return cached;
        }
        var loaded = repository.find(id);
        cache.put(id, loaded);
        return loaded;
    }
}
```

**Operations:**
- `get(key)` — retrieve value (returns `null` on miss)
- `put(key, value)` — store value
- `invalidate(key)` — evict key
- `invalidateAll()` — clear cache
- `asLoadable(loader)` — wrap as `LoadableCache`

---

## LoadableCache Pattern

Get-or-load without aspects:

```java
@KoraApp
public interface Application extends CaffeineCacheModule {
    
    @Cache("orders.cache.config")
    interface OrderCache extends CaffeineCache<UUID, OrderDto> {}
    
    @Root
    default LoadableCache<UUID, OrderDto> orderLoadableCache(
        OrderCache cache,
        OrdersRepository repository
    ) {
        return cache.asLoadable(repository::find);
    }
}

@Component
public class OrdersService {
    private final LoadableCache<UUID, OrderDto> cache;
    
    public OrdersService(LoadableCache<UUID, OrderDto> cache) {
        this.cache = cache;
    }
    
    public OrderDto get(UUID id) {
        return cache.get(id);  // loads via repository::find on miss
    }
}
```

---

## Metrics

With the Micrometer metrics module enabled, the cache module emits:

- `cache.duration` — operation duration (tags: `cache`, `operation`, `origin`, `status`)
- `cache.ratio` — hit/miss counter (tags: `cache`, `origin`, `type`)

Caffeine additionally registers the standard Micrometer cache metrics:

- `cache.gets` — number of cache requests
- `cache.puts` — number of cache writes
- `cache.evictions` — number of cache evictions
- `cache.size` — current cache size

See `.kora-agent/kora-docs/mkdocs/docs/en/documentation/metrics.md#cache` for the full table.

---

## Testing

### Component Test with In-Memory Cache

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
    void shouldCacheResult() {
        var id = UUID.randomUUID();
        var first = service.get(id);
        var second = service.get(id);  // served from cache
        assertEquals(first, second);
    }
}
```

`@KoraAppTest` and `@TestComponent` come from `ru.tinkoff.kora:test-junit5`.

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| **Class is final** | AOP requires non-final class in Java |
| **Cache not triggering** | Check: method called from outside the bean (self-invocation bypass) |
| **Wrong config path** | `@Cache("path")` must match HOCON config path exactly |
| **Null pointer on get()** | `cache.get(key)` returns `null` on miss—handle explicitly |

---

## See Also

- [cacheable-reference.md](cacheable-reference.md) — `@Cacheable`, `@CachePut`, `@CacheInvalidate`
- [cache-key-mapper-reference.md](cache-key-mapper-reference.md) — `CacheKeyMapper`, composite keys
- [cache-redis-reference.md](cache-redis-reference.md) — Redis/Lettuce configuration
- [multi-level-cache-reference.md](multi-level-cache-reference.md) — L1+L2 patterns
