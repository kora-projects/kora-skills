# @Fallback Reference

**Annotation:** `@Fallback(value = "name", method = "fallbackMethod()")`  
**Module:** `resilient-kora`  
**Package:** `ru.tinkoff.kora.resilient.fallback.annotation`

## Contents

- [Basic Usage](#basic-usage)
- [Fallback Method Signature Rules](#fallback-method-signature-rules)
- [Configuration](#configuration)
- [When to Use](#when-to-use)
- [Fallback Patterns](#fallback-patterns)
- [Imperative API](#imperative-api)
- [Common Pitfalls](#common-pitfalls)

---

## Basic Usage

```java
@Component
public class ProductService {
    
    @Fallback(value = "product.read", method = "getFromCacheFallback(id)")
    public Product getProduct(String id) {
        return productRepository.findById(id)
            .orElseThrow(() -> new NotFoundException(id));
    }
    
    protected Product getFromCacheFallback(String id) {
        return cache.get(id, Product::unknown);
    }
}
```

```kotlin
@Component
open class ProductService(
    private val productRepository: ProductRepository,
    private val cache: ProductCache
) {
    
    @Fallback(value = "product.read", method = "getFromCacheFallback(id)")
    open fun getProduct(id: String): Product {
        return productRepository.findById(id)
            .orElseThrow { NotFoundException(id) }
    }
    
    protected open fun getFromCacheFallback(id: String): Product {
        return cache.get(id) { Product.unknown() }
    }
}
```

---

## Fallback Method Signature Rules

| Primary Method | Valid Fallback | Invalid Fallback |
|----------------|----------------|------------------|
| `T method(A a)` | `T fallback(A a)` | `void fallback(A a)` |
| `T method(A a, B b)` | `T fallback(A a)` | `T fallback(B b, A a)` |
| `Optional<T> method(A a)` | `Optional<T> fallback(A a)` | `T fallback(A a)` |

### Key Rules

1. **Return type** must be assignable to primary method's return type
2. **Parameters** must be a subset of primary method's parameters (in same order)
3. **Fallback method** must be in the same class
4. **Visibility:** `protected` or `public` (not `private`)

### Examples

```java
// ✅ Correct - same return type, subset of params
@Fallback(method = "getUserFallback(id)")
public User getUser(String id, boolean includeDetails) { ... }
protected User getUserFallback(String id) { ... }

// ✅ Correct - same return type, all params
@Fallback(method = "getUserFallback(id, includeDetails)")
public User getUser(String id, boolean includeDetails) { ... }
protected User getUserFallback(String id, boolean includeDetails) { ... }

// ❌ Wrong - different return type
@Fallback(method = "getUserFallback(id)")
public Optional<User> getUser(String id) { ... }
protected User getUserFallback(String id) { ... }  // Missing Optional

// ❌ Wrong - private visibility
@Fallback(method = "getUserFallback(id)")
public User getUser(String id) { ... }
private User getUserFallback(String id) { ... }  // Must be protected

// ❌ Wrong - wrong param order
@Fallback(method = "processFallback(b, a)")
public Result process(String a, Integer b) { ... }
protected Result processFallback(Integer b, String a) { ... }  // Wrong order
```

---

## Configuration

```hocon
resilient.fallback {
  default {
    enabled = true
  }
  "product.read" {
    failurePredicateName = "CacheableErrors"  // Optional: when to trigger fallback
  }
}
```

---

## When to Use

**Use fallback when:**
- Safe substitute response exists
- Better to degrade than fail completely
- Cached/stale data is acceptable
- Manual review queue is available

**Use carefully when:**
- Fallback hides serious incidents
- Fallback may create inconsistent state
- Using fallback as substitute for proper persistence

---

## Fallback Patterns

### Cache Fallback

```java
@Component
public class UserService {
    
    @Fallback(value = "user.read", method = "getFromCacheFallback(id)")
    public Optional<User> getUser(String id) {
        return userRepository.findById(id);
    }
    
    protected Optional<User> getFromCacheFallback(String id) {
        log.warn("User {} not found in DB, trying cache", id);
        return cache.get(id);
    }
}
```

### Default Value Fallback

```java
@Component
public class ConfigService {
    
    @Fallback(value = "config.read", method = "getDefaultConfig(key)")
    public ConfigValue getConfig(String key) {
        return configRepository.findByKey(key)
            .orElseThrow(() -> new ConfigNotFoundException(key));
    }
    
    protected ConfigValue getDefaultConfig(String key) {
        return ConfigValue.defaultFor(key);
    }
}
```

### Manual Review Fallback

```java
@Component
public class PaymentService {
    
    @Fallback(value = "payment.process", method = "processManualFallback(request)")
    public PaymentResult process(PaymentRequest request) {
        return paymentGateway.charge(request);
    }
    
    protected PaymentResult processManualFallback(PaymentRequest request) {
        log.warn("Payment {} queued for manual review", request.getId());
        manualReviewQueue.enqueue(request);
        return PaymentResult.pendingManualReview();
    }
}
```

### Empty/Unknown Fallback

```java
@Component
public class InventoryService {
    
    @Fallback(value = "inventory.check", method = "checkUnknownFallback(sku)")
    public Stock checkStock(String sku) {
        return inventoryRepository.findBySku(sku)
            .orElseThrow(NotFoundException::new);
    }
    
    protected Stock checkUnknownFallback(String sku) {
        return Stock.unknown();
    }
}
```

---

## Imperative API

```java
@Component
public final class ProductService {
    
    private final FallbackManager manager;
    
    public ProductService(FallbackManager manager) {
        this.manager = manager;
    }
    
    public Product getProduct(String id) {
        var fallback = manager.get("product.read");
        return fallback.fallback(
            () -> productRepository.findById(id),
            () -> Product.unknown()
        );
    }
}
```

---

## Common Pitfalls

| Problem | Solution |
|---------|----------|
| Fallback not called | Check method signature: return type compatible, parameters match |
| Compile error: method not found | Ensure fallback method exists with exact signature |
| Wrong return type | Fallback return must be assignable to primary return |
| Private method | Change visibility to `protected` or `public` |

---

## See Also

- [circuit-breaker-reference.md](circuit-breaker-reference.md) — Fallback when circuit is open
- [retry-reference.md](retry-reference.md) — Retry before fallback
- [resilience-config-reference.md](resilience-config-reference.md) — General resilience configuration
