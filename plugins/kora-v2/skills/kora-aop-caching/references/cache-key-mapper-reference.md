# Cache Key Mapper Reference

**Interfaces:** `CacheKeyMapper<T, A1>` and the nested
`CacheKeyMapper.CacheKeyMapper2<T, A1, A2>` … `CacheKeyMapper9<...>`.  
**Package:** `ru.tinkoff.kora.cache.CacheKeyMapper`  
**Applied via:** `@Mapping` (`ru.tinkoff.kora.common.Mapping`)

---

## Contents

- [Overview](#overview)
- [CacheKeyMapper Interface](#cachekeymapper-interface)
- [Single Argument Mapper](#single-argument-mapper)
- [Composite Key Mapper](#composite-key-mapper)
- [Key Hashing/Transformation](#key-hashingtransformation)
- [Usage with @CachePut](#usage-with-cacheput)
- [Usage with @CacheInvalidate](#usage-with-cacheinvalidate)
- [Multi-Argument Mappers](#multi-argument-mappers)
- [Comparison: Direct vs Mapper](#comparison-direct-vs-mapper)
- [Best Practices](#best-practices)

---

## Overview

`CacheKeyMapper` extracts a cache key from method arguments when the argument type doesn't match the cache key type directly.

**Use cases:**
- Method argument is a domain object, not the key itself
- Need to extract/combine multiple fields into a composite key
- Need to transform the key (e.g., hash, normalize)

---

## CacheKeyMapper Interface

```java
@FunctionalInterface
public interface CacheKeyMapper<T, A1> extends Mapping.MappingFunction {
    T map(A1 arg);
}
```

- `T` — cache key type (must match the cache interface key type)
- `A1` — method argument type

For methods with multiple arguments, use the nested variants
`CacheKeyMapper.CacheKeyMapper2<T, A1, A2>` through `CacheKeyMapper.CacheKeyMapper9<...>`.
They are declared inside `CacheKeyMapper`, not as separate top-level interfaces.

---

## Single Argument Mapper

Extract a single field from a domain object:

```java
public record UserContext(UUID userId, String traceId) {}

public static final class UserIdMapper implements CacheKeyMapper<UUID, UserContext> {
    @Nonnull
    @Override
    public UUID map(UserContext ctx) {
        return ctx.userId();
    }
}

@Cacheable(OrderCache.class)
@Mapping(UserIdMapper.class)
public OrderDto getByUserContext(UserContext ctx) {
    // key = ctx.userId()
    return repository.findByUserId(ctx.userId());
}
```

---

## Composite Key Mapper

Extract multiple fields into a composite key:

```java
@Cache("orders.cache")
public interface OrderCache extends CaffeineCache<OrderCache.Key, OrderDto> {
    record Key(UUID tenantId, UUID orderId) {}
}

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
    // key = new Key(ctx.tenantId(), ctx.orderId())
    return repository.find(ctx.tenantId(), ctx.orderId());
}
```

---

## Key Hashing/Transformation

Transform the key (e.g., for uniform distribution):

```java
public static final class HashedKeyMapper 
    implements CacheKeyMapper<String, OrderContext> {
    
    @Nonnull
    @Override
    public String map(OrderContext ctx) {
        // Combine and hash for uniform distribution
        return String.format("%s:%s", ctx.tenantId(), ctx.orderId());
    }
}
```

---

## Usage with @CachePut

```java
@CachePut(OrderCache.class)
@Mapping(OrderContextMapper.class)
public OrderDto updateByContext(OrderContext ctx, OrderDto dto) {
    // key = mapper.map(ctx)
    return repository.save(ctx.tenantId(), ctx.orderId(), dto);
}
```

## Usage with @CacheInvalidate

```java
@CacheInvalidate(OrderCache.class)
@Mapping(OrderContextMapper.class)
public void deleteByContext(OrderContext ctx) {
    // evicts key = mapper.map(ctx)
    repository.delete(ctx.tenantId(), ctx.orderId());
}
```

---

## Multi-Argument Mappers

For methods with multiple arguments, implement the nested `CacheKeyMapper.CacheKeyMapper2`:

```java
import ru.tinkoff.kora.cache.CacheKeyMapper;

public static final class TenantOrderMapper
    implements CacheKeyMapper.CacheKeyMapper2<OrderCache.Key, UUID, UUID> {

    @Nonnull
    @Override
    public OrderCache.Key map(UUID tenantId, UUID orderId) {
        return new OrderCache.Key(tenantId, orderId);
    }
}

@Cacheable(OrderCache.class)
@Mapping(TenantOrderMapper.class)
public OrderDto get(UUID tenantId, UUID orderId) {
    return repository.find(tenantId, orderId);
}
```

---

## Comparison: Direct vs Mapper

| Approach | When to Use |
|----------|-------------|
| **Single argument = key** | `get(UUID id)` — argument is the key |
| **Composite key (record)** | `get(UUID tenantId, UUID orderId)` — arguments match record |
| **Custom mapper** | `get(OrderContext ctx)` — need extraction/transformation |
| **`parameters` attribute** | `get(UUID tenantId, String extra, UUID orderId)` — subset/reorder |

---

## Best Practices

1. **Make mappers static final classes** — avoids DI complexity
2. **Keep mapping logic simple** — no side effects, pure functions
3. **Use records for composite keys** — immutable, equals/hashCode auto-generated
4. **Name mappers descriptively** — `UserIdMapper`, `OrderContextMapper`

---

## See Also

- [cacheable-reference.md](cacheable-reference.md) — `@Cacheable`, `@CachePut`, `@CacheInvalidate`
- [cache-caffeine-reference.md](cache-caffeine-reference.md) — Caffeine configuration
- [multi-level-cache-reference.md](multi-level-cache-reference.md) — L1+L2 patterns
