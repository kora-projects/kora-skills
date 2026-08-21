# Imperative Cache Usage

**Kora Version:** 1.2.x

This reference covers programmatic (imperative) cache usage in Kora — injecting cache components and calling methods directly, without `@Cacheable` AOP annotations.

---

## Overview

Kora cache can be used **programmatically** for:

- Stateful caching (OAuth flow state, rate-limit counters)
- Manual cache management (explicit invalidation, conditional updates)
- Non-memoization use cases (caching computed values, external data)

This is separate from the declarative `@Cacheable`/`@CachePut`/`@CacheInvalidate` AOP pattern.

---

## Declaring an Imperative Cache

Define a typed cache interface and inject it as a regular component:

```java
import ru.tinkoff.kora.cache.annotation.Cache;
import ru.tinkoff.kora.cache.caffeine.CaffeineCache;

// Typed cache interface
@Cache("oauth.state.cache")
public interface OAuthStateCache extends CaffeineCache<String, OAuthState> {}
```

**Config path:** `oauth.state.cache` — corresponds to HOCON/YAML config section.

---

## Cache Methods

`CaffeineCache<K, V>` and `RedisCache<K, V>` provide:

| Method | Purpose | Returns |
|--------|---------|---------|
| `V get(K key)` | Get value | `null` if absent |
| `void put(K key, V value)` | Put value | `void` (throws if value is `null`) |
| `V computeIfAbsent(K key, Function<K,V> loader)` | Atomic get-or-load | Existing or loaded value |
| `void invalidate(K key)` | Evict single key | `void` |
| `void invalidateAll()` | Clear entire cache | `void` |
| `boolean contains(K key)` | Check if key exists | `true`/`false` |

**NOT available:** `containsValue()`, `asMap()` — cache is key-based only. For reverse lookup (by value), maintain a separate index cache.

---

## Example: OAuth State Cache

```java
import ru.tinkoff.kora.common.Component;
import com.example.cache.OAuthStateCache;
import com.example.auth.OAuthState;
import java.util.UUID;

@Component
public final class OAuthService {
    private final OAuthStateCache stateCache;
    
    public OAuthService(OAuthStateCache stateCache) {
        this.stateCache = stateCache;
    }
    
    /**
     * Generate and cache OAuth state for CSRF protection.
     */
    public String generateState() {
        String state = UUID.randomUUID().toString();
        OAuthState oauthState = new OAuthState(state, Instant.now().plusSeconds(300));
        
        // Direct put — TTL from config
        stateCache.put(state, oauthState);
        
        return state;
    }
    
    /**
     * Validate and consume OAuth state (one-time use).
     */
    public OAuthState validateState(String state) {
        // Direct get — returns null if missing/expired
        OAuthState oauthState = stateCache.get(state);
        
        if (oauthState == null) {
            throw new IllegalStateException("Invalid or expired OAuth state");
        }
        
        // Check expiration
        if (Instant.now().isAfter(oauthState.expiresAt())) {
            stateCache.invalidate(state);
            throw new IllegalStateException("OAuth state expired");
        }
        
        // Consume (one-time token)
        stateCache.invalidate(state);
        
        return oauthState;
    }
    
    /**
     * Compute-if-absent pattern for rate limiting.
     */
    public int getRateLimitCounter(String userId) {
        return stateCache.computeIfAbsent(userId, key -> {
            // This lambda is NOT called if key exists
            return new OAuthState(key, Instant.now().plusSeconds(60));
        }).counter();
    }
}
```

---

## TTL Configuration

Cache config path comes from `@Cache("path.to.section")`:

```hocon
oauth.state.cache {
  maximumSize = 10000
  expireAfterWrite = "5m"        # TTL — entries auto-expire after 5 minutes
  expireAfterAccess = "1m"       # Optional: expire after 1m of inactivity
}
```

**Common options:**
- `maximumSize` — max entries (evict LRU when exceeded)
- `expireAfterWrite` — TTL from creation time
- `expireAfterAccess` — TTL from last read/write
- `refreshAfterWrite` — async refresh after duration (Caffeine only)

See [Cache Config Reference](references/cache-config-reference.md) for all options.

---

## Module Requirements

| Cache Type | Module | Dependency |
|------------|--------|------------|
| Caffeine (in-process) | `CaffeineCacheModule` | `ru.tinkoff.kora:cache-caffeine` |
| Redis (distributed) | `RedisCacheModule` | `ru.tinkoff.kora:cache-redis` |

```java
@KoraApp
public interface Application extends CaffeineCacheModule {}
// Or for Redis: extends RedisCacheModule
// Or for both (multi-level): extends CaffeineCacheModule, RedisCacheModule
```

---

## Multi-Level Cache Pattern

For L1 (Caffeine) + L2 (Redis) caching:

```java
@Cache("users.cache")
public interface UsersL1Cache extends CaffeineCache<String, User> {}

@Cache("users.cache")  // Same config path
public interface UsersL2Cache extends RedisCache<String, User> {}

@Component
public final class UserService {
    private final UsersL1Cache l1Cache;
    private final UsersL2Cache l2Cache;
    
    public User getUser(String id) {
        // Try L1 first
        User user = l1Cache.get(id);
        if (user != null) {
            return user;
        }
        
        // Try L2
        user = l2Cache.get(id);
        if (user != null) {
            // Populate L1
            l1Cache.put(id, user);
            return user;
        }
        
        // Load from database
        user = loadFromDatabase(id);
        
        // Populate both caches
        l1Cache.put(id, user);
        l2Cache.put(id, user);
        
        return user;
    }
}
```

---

## Comparison: Imperative vs Declarative

| Aspect | Imperative | Declarative (`@Cacheable`) |
|--------|------------|---------------------------|
| **Control** | Full manual control | Automatic memoization |
| **Use case** | Stateful caching, manual invalidation | Method result memoization |
| **Code location** | Service/business logic | Method annotations |
| **Null handling** | Explicit (`get()` returns `null`) | `@Cacheable` skips `null` by default |
| **Complexity** | Higher (manual management) | Lower (annotation-only) |

---

## Common Patterns

### Rate Limiting

```java
@Component
public final class RateLimiter {
    private final RateLimitCache cache;
    
    public RateLimiter(RateLimitCache cache) {
        this.cache = cache;
    }
    
    public boolean allowRequest(String userId) {
        Counter counter = cache.computeIfAbsent(userId, k -> new Counter());
        return counter.incrementAndGet() <= 100;  // 100 requests per TTL window
    }
    
    @Cache("rate.limit.cache")
    public interface RateLimitCache extends CaffeineCache<String, Counter> {}
    
    public static class Counter {
        private final AtomicLong count = new AtomicLong(0);
        public long incrementAndGet() { return count.incrementAndGet(); }
    }
}
```

### Manual Invalidation

```java
@Component
public final class ProductService {
    private final ProductCache cache;
    
    public void updateProduct(String id, ProductUpdate update) {
        // Update database
        repository.update(id, update);
        
        // Invalidate cache
        cache.invalidate(id);
    }
    
    @Cache("products.cache")
    public interface ProductCache extends CaffeineCache<String, Product> {}
}
```

---

## See Also

- [AOP Caching Skill](../SKILL.md) — `@Cacheable`, `@CachePut`, `@CacheInvalidate`
- [Cache Config Reference](references/cache-config-reference.md) — TTL, sizing, eviction
- [Multi-Level Cache Guide](../../.kora-agent/kora-docs/mkdocs/docs/en/guides/cache-multi-level.md) — L1 + L2 patterns
