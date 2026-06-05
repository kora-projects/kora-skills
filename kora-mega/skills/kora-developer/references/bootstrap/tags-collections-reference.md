# Kora Tags and Collections Reference

**Source:** [.kora-agent/kora-docs/mkdocs/docs/en/guides/dependency-injection-guide.md](.kora-agent/kora-docs/mkdocs/docs/en/guides/dependency-injection-guide.md)  
**Examples:** `.kora-agent/kora-examples/kora-java-helloworld/`

When you have multiple implementations of the same interface, use `@Tag` annotation to distinguish which one to inject.

---

## @Tag Annotation

### Simple Tag Class (Preferred)

Use a simple class as a tag without creating custom annotations:

```java
// Simple tag classes
public final class RedisTag {}
public final class CaffeineTag {}

// Tagged implementations
@Tag(RedisTag.class)
@Component
public final class RedisCache implements Cache {
    // Redis implementation
}

@Tag(CaffeineTag.class)
@Component
public final class CaffeineCache implements Cache {
    // In-memory implementation
}

// Injection with tag
@Component
public final class UserService {
    public UserService(@Tag(RedisTag.class) Cache cache) {
        // Injects RedisCache specifically
    }
}
```
### Why Simple Approach is Better

```java
// BAD — redundant custom annotation
@Target({ElementType.TYPE, ElementType.PARAMETER, ElementType.FIELD})
@Retention(RetentionPolicy.RUNTIME)
@Tag(RedisTag.class)
public @interface RedisCache {}

// GOOD — simple tag class
public final class RedisTag {}
```

**Benefits of simple tag classes:** Less boilerplate code, no annotation processing overhead, clearer intent, easier to maintain.

---

## All<T> — Collection Injection

### Basic Usage

Inject all implementations of a type:

```java
@Component
public final class NotificationService {
    private final List<Notifier> notifiers;
    
    public NotificationService(All<Notifier> notifiers) {
        this.notifiers = List.copyOf(notifiers);
    }
    
    public void notify(String message) {
        notifiers.forEach(n -> n.send(message));
    }
}
```
### Example: Multiple Notifiers

```java
// Multiple implementations
@Component
public final class EmailNotifier implements Notifier {
    public void send(String message) {
        // Send email
    }
}

@Component
public final class SmsNotifier implements Notifier {
    public void send(String message) {
        // Send SMS
    }
}

@Component
public final class PushNotifier implements Notifier {
    public void send(String message) {
        // Send push notification
    }
}

// Inject all notifiers
@Component
public final class NotificationService {
    private final List<Notifier> notifiers;

    public NotificationService(All<Notifier> notifiers) {
        this.notifiers = List.copyOf(notifiers);
    }
}
```

---

## Tag.Any — All Components Regardless of Tag

### Purpose

`Tag.Any` injects ALL components including those with tags (which are normally excluded from untagged injection).
### Example

```java
// Tagged implementations
@Tag(RedisTag.class)
@Component
public final class RedisCache implements Cache {}

@Tag(CaffeineTag.class)
@Component
public final class CaffeineCache implements Cache {}

// Untagged implementation
@Component
public final class DefaultCache implements Cache {}

// Inject ALL caches (including tagged)
@Component
public final class CacheManager {
    private final List<Cache> allCaches;
    
    public CacheManager(@Tag(Tag.Any.class) List<Cache> allCaches) {
        this.allCaches = allCaches;
    }
}
```
### Without Tag.Any

```java
// Without @Tag(Tag.Any.class) — only untagged caches injected
public CacheManager(List<Cache> caches) {
    // Gets only DefaultCache
}

// With @Tag(Tag.Any.class) — ALL caches injected
public CacheManager(@Tag(Tag.Any.class) List<Cache> allCaches) {
    // Gets RedisCache, CaffeineCache, AND DefaultCache
}
```

---

## Tag.All — Collection with Specific Tag

### Purpose

`Tag.All` combined with a specific tag injects ALL components with that specific tag.
### Example

```java
// Multiple Redis caches with same tag
@Tag(RedisTag.class)
@Component
public final class UserRedisCache implements Cache {}

@Tag(RedisTag.class)
@Component
public final class OrderRedisCache implements Cache {}

@Tag(CaffeineTag.class)
@Component
public final class LocalCache implements Cache {}

// Inject only Redis caches
@Component
public final class RedisCacheManager {
    private final List<Cache> redisCaches;
    
    public RedisCacheManager(
        @Tag(RedisTag.class) 
        @Tag(Tag.All.class) 
        List<Cache> redisCaches
    ) {
        this.redisCaches = redisCaches;
    }
}
```
### Tag.All vs Tag.Any

| Annotation | What it injects |
|------------|----------------|
| `List<Cache>` | Only untagged caches |
| `@Tag(Tag.Any.class) List<Cache>` | ALL caches (tagged + untagged) |
| `@Tag(RedisTag.class) @Tag(Tag.All.class) List<Cache>` | Only caches tagged with `RedisTag` |

---

## Combining Tags and Collections

### Full Example

```java
// Tag classes
public final class PrimaryTag {}
public final class SecondaryTag {}

// Implementations
@Tag(PrimaryTag.class)
@Component
public final class PrimaryDatabase implements Database {}

@Tag(SecondaryTag.class)
@Component
public final class SecondaryDatabase implements Database {}

@Component
public final class DefaultDatabase implements Database {}

// Injection scenarios
@Component
public final class DataService {
    private final Database primary;
    private final Database secondary;
    private final List<Database> allDatabases;
    private final List<Database> primaryDatabases;

    public DataService(
        @Tag(PrimaryTag.class) Database primary,           // PrimaryDatabase only
        @Tag(SecondaryTag.class) Database secondary,       // SecondaryDatabase only
        @Tag(Tag.Any.class) List<Database> allDatabases,   // All 3 databases
        @Tag(PrimaryTag.class) @Tag(Tag.All.class) 
        List<Database> primaryDatabases                     // PrimaryDatabase only (as list)
    ) {
        this.primary = primary;
        this.secondary = secondary;
        this.allDatabases = allDatabases;
        this.primaryDatabases = primaryDatabases;
    }
}
```

---

## Tagged Factory Methods

### Module with Tagged Factories

```java
@Module
public interface CacheModule {
    
    @Tag(RedisTag.class)
    default Cache redisCache(RedisConfig config) {
        return new RedisCache(config);
    }
    
    @Tag(CaffeineTag.class)
    default Cache caffeineCache(CacheConfig config) {
        return new CaffeineCache(config);
    }
}
```
### Injecting Tagged Factory Results

```java
@Component
public final class UserService {
    public UserService(@Tag(RedisTag.class) Cache cache) {
        // Gets redisCache from CacheModule
    }
}
```

---

## Common Mistakes

### Missing @Tag on Injection Point

```java
// BAD — ambiguous dependency error
@Component
public final class UserService {
    public UserService(Cache cache) {
        // Error: Found several components of type Cache
    }
}

// GOOD — specify which implementation
@Component
public final class UserService {
    public UserService(@Tag(RedisTag.class) Cache cache) {
        // Gets RedisCache specifically
    }
}
```
### Tag on Only One Implementation

```java
// BAD — still ambiguous for untagged injection
@Tag(RedisTag.class)
@Component
public final class RedisCache implements Cache {}

@Component
public final class CaffeineCache implements Cache {}

// Error when injecting Cache without @Tag
// GOOD — tag ALL implementations or use @DefaultComponent
```
### Creating Redundant Annotations

```java
// BAD — unnecessary complexity
@Target({ElementType.TYPE, ElementType.PARAMETER})
@Retention(RetentionPolicy.RUNTIME)
@Tag(RedisTag.class)
public @interface Redis {}

// GOOD — use simple tag class directly
public final class RedisTag {}
```

---

## Quick Reference

### Tag Classes
```java
public final class RedisTag {}
public final class CaffeineTag {}
```
### Tagged Component
```java
@Tag(RedisTag.class)
@Component
public final class RedisCache implements Cache {}
```
### Tagged Injection
```java
public UserService(@Tag(RedisTag.class) Cache cache) {}
```
### All Implementations
```java
public Service(All<Notifier> notifiers) {}
```
### All Including Tagged
```java
public Service(@Tag(Tag.Any.class) List<Cache> caches) {}
```
### All with Specific Tag
```java
public Service(
    @Tag(RedisTag.class) 
    @Tag(Tag.All.class) 
    List<Cache> redisCaches
) {}
```

---

## Use Cases

| Use Case | Solution |
|----------|----------|
| Multiple implementations | Use `@Tag` to distinguish |
| Strategy pattern | Tag each strategy, inject specific one |
| Plugin architecture | `All<Plugin>` for all plugins |
| Primary/secondary DB | `@Tag(PrimaryTag.class)` for primary |
| Multi-tenant caching | `@Tag(TenantATag.class)`, `@Tag(TenantBTag.class)` |
| Environment-specific | `@Tag(ProdTag.class)`, `@Tag(DevTag.class)` |
