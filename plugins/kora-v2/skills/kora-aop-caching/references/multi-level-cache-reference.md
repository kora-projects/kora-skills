# Multi-Level Cache Reference

**Pattern:** Caffeine L1 + Redis L2  
**Modules:** `CaffeineCacheModule` + `RedisCacheModule`

---

## Contents

- [Overview](#overview)
- [When to Use](#when-to-use)
- [Setup](#setup)
- [Configuration](#configuration)
- [Multi-Level Service](#multi-level-service)
- [Invalidation Strategies](#invalidation-strategies)
- [Considerations](#considerations)
- [Metrics](#metrics)
- [Troubleshooting](#troubleshooting)

---

## Overview

Multi-level caching combines fast local cache (L1 Caffeine) with distributed cache (L2 Redis) for optimal performance:

```
┌─────────────┐
│   Request   │
└──────┬──────┘
       │
       ▼
┌─────────────┐
│ L1 Caffeine │ ──hit──▶ return
└──────┬──────┘
       │ miss
       ▼
┌─────────────┐
│ L2 Redis    │ ──hit──▶ populate L1 ▶ return
└──────┬──────┘
       │ miss
       ▼
┌─────────────┐
│  Repository │
└──────┬──────┘
       │
       ▼
┌─────────────┐
│ populate L1 │
│ populate L2 │
└─────────────┘
```

---

## When to Use

**Use multi-level cache when:**
- Multi-pod deployment with shared Redis
- Need lowest latency for hot data
- Want to reduce Redis load
- Can tolerate cache warm-up after restart

**Don't use when:**
- Single-instance deployment (Caffeine alone is enough)
- Memory is constrained (doubles memory usage)
- Cache invalidation complexity is a concern

---

## Setup

### 1. Add Dependencies

```groovy
implementation "ru.tinkoff.kora:cache-caffeine"
implementation "ru.tinkoff.kora:cache-redis"
```

### 2. Enable Both Modules

```java
@KoraApp
public interface Application 
    extends CaffeineCacheModule, RedisCacheModule {}
```

### 3. Declare Both Cache Types

```java
@KoraApp
public interface Application 
    extends CaffeineCacheModule, RedisCacheModule {
    
    @Cache("orders.caffeine.config")
    interface OrderCaffeineCache 
        extends CaffeineCache<UUID, OrderDto> {}
    
    @Cache("orders.redis.config")
    interface OrderRedisCache 
        extends RedisCache<UUID, @Json OrderDto> {}
}
```

---

## Configuration

### application.conf

```hocon
# L1 Caffeine - fast, small, local
orders.caffeine.config {
  maximumSize       = 5000
  expireAfterWrite  = "5m"
}

# L2 Redis - larger, shared, distributed
orders.redis.config {
  keyPrefix         = "orders"
  expireAfterWrite  = "1h"
}

# Lettuce driver
lettuce {
  uri              = "redis://localhost:6379"
  socketTimeout    = "15s"
  commandTimeout   = "15s"
}
```

### Config Guidelines

| Level | TTL | Size | Purpose |
|-------|-----|------|---------|
| L1 Caffeine | Short (1-10m) | Small (1K-10K) | Hot data, lowest latency |
| L2 Redis | Longer (30m-1h) | Large (100K+) | Full cache, shared state |

---

## Multi-Level Service

### With Annotations

Stack `@Cacheable` for L1 → L2 → method lookup:

```java
@Component
public class OrdersService {
    
    private final OrdersRepository repository;
    
    public OrdersService(OrdersRepository repository) {
        this.repository = repository;
    }
    
    // L1 → L2 → repository
    @Cacheable(OrderCaffeineCache.class)  // checked first
    @Cacheable(OrderRedisCache.class)     // checked on L1 miss
    public OrderDto get(UUID id) {
        return repository.find(id);
    }
    
    // Update both L1 and L2
    @CachePut(OrderCaffeineCache.class)
    @CachePut(OrderRedisCache.class)
    public OrderDto update(UUID id, OrderDto dto) {
        return repository.save(id, dto);
    }
    
    // Evict from both L1 and L2
    @CacheInvalidate(OrderCaffeineCache.class)
    @CacheInvalidate(OrderRedisCache.class)
    public void delete(UUID id) {
        repository.delete(id);
    }
}
```

**Annotation order matters:** L1 (Caffeine) first, then L2 (Redis).

### With Imperative API

```java
@Component
public class OrdersImperativeService {
    
    private final OrderCaffeineCache l1Cache;
    private final OrderRedisCache l2Cache;
    private final OrdersRepository repository;
    
    public OrdersImperativeService(
        OrderCaffeineCache l1Cache,
        OrderRedisCache l2Cache,
        OrdersRepository repository
    ) {
        this.l1Cache = l1Cache;
        this.l2Cache = l2Cache;
        this.repository = repository;
    }
    
    public OrderDto get(UUID id) {
        // Check L1
        var l1Hit = l1Cache.get(id);
        if (l1Hit != null) {
            return l1Hit;
        }
        
        // Check L2
        var l2Hit = l2Cache.get(id);
        if (l2Hit != null) {
            l1Cache.put(id, l2Hit);  // populate L1
            return l2Hit;
        }
        
        // Load from repository
        var loaded = repository.find(id);
        l1Cache.put(id, loaded);  // populate L1
        l2Cache.put(id, loaded);  // populate L2
        return loaded;
    }
}
```

---

## Invalidation Strategies

### Evict from Both Levels

Always evict from both L1 and L2 on updates/deletes:

```java
@CacheInvalidate(OrderCaffeineCache.class)
@CacheInvalidate(OrderRedisCache.class)
public void delete(UUID id) {
    repository.delete(id);
}
```

### Clear All (Use Sparingly)

```java
@CacheInvalidate(value = OrderCaffeineCache.class, invalidateAll = true)
@CacheInvalidate(value = OrderRedisCache.class, invalidateAll = true)
public void clearAll() {
    // administrative operation - causes cache stampede
}
```

**Warning:** `invalidateAll` clears entire cache—expensive operation.

---

## Considerations

### Cache Stampede

Clearing L2 (Redis) causes all pods to simultaneously hit the database. Mitigate with:

1. **Staggered TTLs** — Add jitter to expiration times
2. **Locking** — Use distributed lock for cache population
3. **Soft expiration** — Refresh in background before hard expiration

### Memory Usage

Multi-level caching doubles memory usage:
- L1: Heap memory in each pod
- L2: Redis memory (shared)

Size L1 appropriately to avoid OOM.

### Consistency

L1 cache can become stale if:
- Another pod updates/deletes the entry
- L2 is cleared but L1 still has entries

For strict consistency, use shorter L1 TTLs or evict on writes.

---

## Metrics

With the Micrometer metrics module enabled, monitor both levels:

- `cache.duration` — operation duration; the `cache` tag distinguishes L1 vs L2
- `cache.ratio` — hit/miss counter; the `type` tag separates hits from misses
- `cache.gets` / `cache.puts` / `cache.evictions` / `cache.size` — standard Caffeine (L1) metrics

See `.kora-agent/kora-docs/mkdocs/docs/en/documentation/metrics.md#cache` for the full table.

**Target ratios (rule of thumb):**
- L1 hit rate: 60-80% (hot data)
- L2 hit rate: 90-95% (warm data)
- Repository miss rate: <5%

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| **L1 not populated** | Check annotation order: L1 first, then L2 |
| **Stale L1 data** | Shorten L1 TTL, ensure eviction on writes |
| **High L1 miss rate** | Increase L1 size or extend TTL |
| **Memory pressure** | Reduce L1 `maximumSize` |

---

## See Also

- [cacheable-reference.md](cacheable-reference.md) — `@Cacheable`, `@CachePut`, `@CacheInvalidate`
- [cache-caffeine-reference.md](cache-caffeine-reference.md) — Caffeine configuration
- [cache-redis-reference.md](cache-redis-reference.md) — Redis/Lettuce configuration
