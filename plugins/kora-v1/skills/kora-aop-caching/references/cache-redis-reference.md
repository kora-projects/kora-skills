# Redis Cache Reference

**Module:** `RedisCacheModule`  
**Artifact:** `ru.tinkoff.kora:cache-redis`  
**Interface:** `RedisCache<K, V>`  
**Driver:** Lettuce

---

## Contents

- [When to Use Redis](#when-to-use-redis)
- [Setup](#setup)
- [Lettuce Driver Configuration](#lettuce-driver-configuration)
- [Per-Cache Configuration](#per-cache-configuration)
- [Complete Example](#complete-example)
- [Imperative API](#imperative-api)
- [LettuceConfigurator](#lettuceconfigurator)
- [Testing with Testcontainers](#testing-with-testcontainers)
- [Troubleshooting](#troubleshooting)

---

## When to Use Redis

**Use Redis when:**
- Multi-pod/stateless deployment (shared cache)
- Cache state must survive restarts
- Cache size exceeds heap capacity
- Cross-service cache sharing needed

**Don't use Redis when:**
- Single-instance app with fast local access (use Caffeine)
- Lowest latency is critical (network round-trip adds latency)
- No Redis infrastructure available

---

## Setup

### 1. Add Dependency

```groovy
implementation "ru.tinkoff.kora:cache-redis"
```

### 2. Enable Module

```java
@KoraApp
public interface Application extends RedisCacheModule {}
```

### 3. Declare Typed Cache

```java
@Cache("orders.cache.config")
public interface OrderCache extends RedisCache<UUID, @Json OrderDto> {}
```

**Important:** Use `@Json` annotation on value type for JSON serialization.

---

## Lettuce Driver Configuration

### Global Lettuce Config

Single connection shared across all `RedisCache` instances:

```hocon
lettuce {
  uri              = "redis://localhost:6379"  # required, rediss:// for TLS
  user             = ${?REDIS_USER}            # optional
  password         = ${?REDIS_PASSWORD}        # optional
  database         = 0                         # optional DB number
  protocol         = "RESP3"                   # RESP2 or RESP3
  socketTimeout    = "15s"                     # connection timeout
  commandTimeout   = "15s"                     # command execution timeout
  forceClusterClient = false                   # force cluster mode
  
  # SSL configuration (optional)
  ssl {
    ciphers          = ["TLS_CHACHA20_POLY1305_SHA256"]
    handshakeTimeout = "10s"
  }
}
```

### URI Formats

| Format | Description |
|--------|-------------|
| `redis://localhost:6379` | Single server |
| `redis://host1:6379,host2:6379` | Multiple servers |
| `rediss://localhost:6380` | SSL connection |
| `redis+tls://localhost:6380` | TLS connection |

---

## Per-Cache Configuration

```hocon
orders.cache.config {
  expireAfterWrite  = "1h"                     # optional TTL on write
  expireAfterAccess = "30m"                    # optional TTL on access
  keyPrefix         = "orders"                 # REQUIRED — avoids collisions
}
```

### Parameters

| Parameter | Description | Default | Required |
|-----------|-------------|---------|----------|
| `keyPrefix` | Prefix for all Redis keys | — | **Yes** |
| `expireAfterWrite` | Delete entry after time since write | — | No |
| `expireAfterAccess` | Delete entry after time since last access | — | No |

**CRITICAL:** `keyPrefix` is **required** for Redis caches. Graph build fails without it because `RedisCacheConfig.keyPrefix()` is non-`@Nullable`.

### Key Prefix Rules

- Use distinct prefixes per cache to avoid collisions
- Empty string `""` is technically allowed but dangerous in multi-cache deployments
- Recommended format: `"<domain>-<entity>"` (e.g., `"orders-cache"`, `"users-cache"`)

---

## Complete Example

```java
package com.example.app.cache;

import com.example.app.dto.OrderDto;
import ru.tinkoff.kora.cache.annotation.Cache;
import ru.tinkoff.kora.cache.annotation.Cacheable;
import ru.tinkoff.kora.cache.redis.RedisCache;
import ru.tinkoff.kora.common.Component;
import ru.tinkoff.kora.json.common.annotation.Json;
import java.util.UUID;

// 1. Typed cache interface with JSON serialization
@Cache("orders.cache.config")
public interface OrderCache extends RedisCache<UUID, @Json OrderDto> {}

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
  keyPrefix = "orders"
  expireAfterWrite = "1h"
}

lettuce {
  uri = "redis://localhost:6379"
  password = ${?REDIS_PASSWORD}
}
```

---

## Imperative API

`RedisCache<K, V>` extends the common `Cache<K, V>` contract, so you can inject the typed
cache and call its operations directly alongside the declarative annotations:

```java
@Component
public class OrdersService {

    private final OrderCache cache;
    private final OrdersRepository repository;

    public OrdersService(OrderCache cache, OrdersRepository repository) {
        this.cache = cache;
        this.repository = repository;
    }

    public OrderDto getOrLoad(UUID id) {
        var cached = cache.get(id);            // null on miss
        if (cached != null) {
            return cached;
        }
        var loaded = repository.find(id);
        cache.put(id, loaded);
        return loaded;
    }
}
```

**`Cache<K, V>` operations:**
- `get(key)` / `get(Collection<K> keys)` — retrieve one value or a batch
- `put(key, value)` / `put(Map<K, V>)` — store one value or a batch
- `computeIfAbsent(key, loader)` — get-or-load atomically
- `invalidate(key)` / `invalidate(Collection<K>)` — evict by key(s)
- `invalidateAll()` — clear the cache
- `asLoadable(loader)` — wrap as `LoadableCache`

The Kora cache module documentation also notes that the Redis cache supports
asynchronous usage with `CompletionStage` signatures; the synchronous `Cache`
contract above is the portable surface shared with Caffeine.

---

## LettuceConfigurator

Customize Lettuce client before creation:

```java
@Component
public class MyLettuceConfigurator implements LettuceConfigurator {
    
    @Override
    public DefaultClientResources.Builder configure(
        DefaultClientResources.Builder resourceBuilder
    ) {
        // Customize client resources (thread pools, event loops)
        return resourceBuilder;
    }

    @Override
    public ClusterClientOptions.Builder configure(
        ClusterClientOptions.Builder clusterBuilder
    ) {
        // Customize cluster options (topology refresh)
        return clusterBuilder;
    }

    @Override
    public io.lettuce.core.ClientOptions.Builder configure(
        io.lettuce.core.ClientOptions.Builder clientBuilder
    ) {
        // Customize client options (timeouts, retries)
        return clientBuilder;
    }
}
```

---

## Testing with Testcontainers

Spin up a real Redis with Testcontainers and point the Lettuce `uri` at it (via env
substitution or a test config). Inject the typed cache with `@TestComponent`.

```java
@KoraAppTest(Application.class)
class RedisCacheTest {

    @TestComponent
    private SimpleCache cache;   // @Cache(...) extends RedisCache<String, Long>

    @BeforeEach
    void cleanup() {
        cache.invalidateAll();
    }

    @Test
    void shouldCacheInRedis() {
        cache.put("key", 42L);
        assertEquals(42L, cache.get("key"));
    }
}
```

The Redis example wires Testcontainers via `io.goodforgod:testcontainers-extensions-redis`
and sets `REDIS_URL` so the Lettuce driver connects to the container; see
`.kora-agent/kora-examples/examples/java/kora-java-cache-redis/`.

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| **Graph build fails: keyPrefix not found** | Add `keyPrefix` to cache config—it's required |
| **Class is final** | AOP requires non-final class in Java |
| **Wrong artifact name** | Use `cache-redis` not `lettuce-cache` |
| **Serialization error** | Add `@Json` annotation on value type |
| **Connection refused** | Check Lettuce `uri` config and Redis availability |

---

## See Also

- [cacheable-reference.md](cacheable-reference.md) — `@Cacheable`, `@CachePut`, `@CacheInvalidate`
- [cache-caffeine-reference.md](cache-caffeine-reference.md) — Caffeine configuration
- [multi-level-cache-reference.md](multi-level-cache-reference.md) — L1+L2 patterns
