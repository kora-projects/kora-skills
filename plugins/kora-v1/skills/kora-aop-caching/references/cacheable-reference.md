# Cache Annotations Reference

**Annotations:** `@Cacheable`, `@CachePut`, `@CacheInvalidate`  
**Package:** `ru.tinkoff.kora.cache.annotation.*`

---

## Contents

- [Annotation Overview](#annotation-overview)
- [@Cacheable](#cacheable)
- [@CachePut](#cacheput)
- [@CacheInvalidate](#cacheinvalidate)
- [Common Pitfalls](#common-pitfalls)

---

## Annotation Overview

| Annotation | Purpose | Method Runs | Cache Behavior |
|------------|---------|-------------|----------------|
| `@Cacheable(MyCache.class)` | Read-through cache | On cache miss only | Lookup first; on miss call method, cache result |
| `@CachePut(MyCache.class)` | Write-through cache | Always | Call method, then put result in cache |
| `@CacheInvalidate(MyCache.class)` | Evict by key | Always | Call method, then evict key built from args |
| `@CacheInvalidate(value = MyCache.class, invalidateAll = true)` | Clear entire cache | Always | Call method, then clear all entries |

**Important:** Annotations are repeatable. Stack multiple `@Cacheable` for multi-level caching (L1 → L2 → method).

---

## @Cacheable

Read-through caching: check cache first, call method only on miss.

### Basic Usage

```java
@Cacheable(OrderCache.class)
public OrderDto get(UUID id) {
    return repository.find(id);
}
```

**Flow:**
1. Check cache for key = `id`
2. If hit → return cached value (method NOT called)
3. If miss → call method, cache result, return

### Composite Key

```java
@Cache("orders.cache")
public interface OrderCache extends CaffeineCache<OrderCache.Key, OrderDto> {
    record Key(UUID tenantId, UUID orderId) {}
}

@Cacheable(OrderCache.class)
public OrderDto get(UUID tenantId, UUID orderId) {
    // key = new Key(tenantId, orderId)
    return repository.find(tenantId, orderId);
}
```

**Important:** Argument order maps to record component order.

### Custom Key Mapper

When the argument is a domain object, not the key itself:

```java
public record OrderContext(UUID tenantId, UUID orderId, String requestId) {}

public static final class OrderContextMapper 
    implements CacheKeyMapper<OrderCache.Key, OrderContext> {
    
    @Nonnull
    @Override
    public OrderCache.Key map(OrderContext ctx) {
        return new OrderCache.Key(ctx.tenantId(), ctx.orderId());
    }
}

@Cacheable(OrderCache.class)
@Mapping(OrderContextMapper.class)
public OrderDto getByContext(OrderContext ctx) {
    // key = mapper.map(ctx)
    return repository.find(ctx.tenantId(), ctx.orderId());
}
```

### Subset/Reordering with `parameters`

```java
@Cacheable(value = OrderCache.class, parameters = { "orderId", "tenantId" })
public OrderDto get(UUID tenantId, String unrelated, UUID orderId) {
    // key = new Key(orderId, tenantId) — order from `parameters`
    return repository.find(tenantId, orderId);
}
```

Use `parameters` when:
- Method has more arguments than the key needs
- Argument order doesn't match record constructor
- You need to skip certain arguments

### Multi-Level Cache

Stack annotations for L1 → L2 → method lookup:

```java
@Cacheable(OrderCaffeineCache.class)  // L1: checked first
@Cacheable(OrderRedisCache.class)     // L2: checked on L1 miss
public OrderDto get(UUID id) {
    // Order: Caffeine → Redis → repository
    return repository.find(id);
}
```

**Aspects apply top-to-bottom:**
1. Check Caffeine (L1)
2. On miss, check Redis (L2)
3. On miss, call method
4. Populate both caches on the way back

### Supported Return Types

`T` is the return value type. The two language sets are independent — do not read
the rows as Java↔Kotlin equivalents.

**Java:**
- `T method()`
- `@Nullable T method()`
- `Optional<T> method()`
- `Mono<T> method()` (requires `io.projectreactor:reactor-core`)

**Kotlin:**
- `fun method(): T`
- `fun method(): T?`
- `fun method(): Unit` (for `@CachePut` / `@CacheInvalidate`)
- `suspend fun method(): T` (requires `org.jetbrains.kotlinx:kotlinx-coroutines-core`)

---

## @CachePut

Write-through caching: always call method, then update cache.

### Basic Usage

```java
@CachePut(value = OrderCache.class, parameters = { "id" })
public OrderDto update(UUID id, OrderDto dto) {
    return repository.save(id, dto);
}
```

**Flow:**
1. Call method
2. Extract key from arguments (`id`)
3. Put result in cache: `cache.put(id, result)`

### With Composite Key

```java
@CachePut(value = OrderCache.class, parameters = { "tenantId", "orderId" })
public OrderDto update(UUID tenantId, UUID orderId, OrderDto dto) {
    // key = new Key(tenantId, orderId)
    return repository.save(tenantId, orderId, dto);
}
```

### With Custom Mapper

```java
@CachePut(OrderCache.class)
@Mapping(OrderContextMapper.class)
public OrderDto updateByContext(OrderContext ctx, OrderDto dto) {
    // key = mapper.map(ctx)
    return repository.save(ctx.tenantId(), ctx.orderId(), dto);
}
```

---

## @CacheInvalidate

Evict from cache: call method, then remove key from cache.

### Evict by Key

```java
@CacheInvalidate(OrderCache.class)
public void delete(UUID id) {
    repository.delete(id);
    // After: cache.invalidate(id) is called
}
```

**Flow:**
1. Call method
2. Extract key from arguments
3. Evict key: `cache.invalidate(id)`

### Clear Entire Cache

```java
@CacheInvalidate(value = OrderCache.class, invalidateAll = true)
public void clearAll() {
    // administrative operation
    // After: cache.invalidateAll() is called
}
```

**Warning:** `invalidateAll = true` clears the entire cache. Use sparingly—causes cache stampede.

### With Composite Key

```java
@CacheInvalidate(OrderCache.class)
public void delete(UUID tenantId, UUID orderId) {
    // key = new Key(tenantId, orderId)
    repository.delete(tenantId, orderId);
}
```

---

## Common Pitfalls

| Problem | Solution |
|---------|----------|
| **Class is final (Java) / not open (Kotlin)** | AOP requires subclassing: non-final in Java, `open` in Kotlin |
| **Wrong argument order** | Argument order must match record component order, or use `parameters` |
| **Self-invocation bypass** | Call from another component; the AOP proxy is only applied to external calls |
| **Multi-level wrong order** | Stack annotations L1 first (Caffeine), then L2 (Redis) |
| **No conditional caching attribute** | `@Cacheable`/`@CachePut`/`@CacheInvalidate` expose only `value`, `parameters`, and (for invalidate) `invalidateAll` — there is no `unless`/`condition`; gate caching with the imperative API instead |

---

## See Also

- [cache-key-mapper-reference.md](cache-key-mapper-reference.md) — `CacheKeyMapper`, composite keys
- [cache-caffeine-reference.md](cache-caffeine-reference.md) — Caffeine configuration
- [cache-redis-reference.md](cache-redis-reference.md) — Redis/Lettuce configuration
- [multi-level-cache-reference.md](multi-level-cache-reference.md) — L1+L2 patterns
