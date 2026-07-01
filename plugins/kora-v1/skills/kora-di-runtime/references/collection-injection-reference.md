# Kora Collection Injection Reference

**Source:** [Kora Container Documentation](../../../.kora-agent/kora-docs/mkdocs/docs/en/documentation/container.md)

Complete reference for injecting collections of components using `All<T>` and `@Tag`.

---

## Table of Contents

1. [All<T> Basics](#allt-basics)
2. [All<T> with Tags](#allt-with-tags)
3. [Tag.Any — Collect All Components](#tagany--collect-all-components)
4. [Common Patterns](#common-patterns)
5. [Troubleshooting](#troubleshooting)

---

## All<T> Basics

`All<T>` injects all untagged implementations of a type.

```java
// Multiple implementations
@Component
public final class EmailNotifier implements Notifier {
    public void send(String message) { /* Send email */ }
}

@Component
public final class SmsNotifier implements Notifier {
    public void send(String message) { /* Send SMS */ }
}

@Component
public final class PushNotifier implements Notifier {
    public void send(String message) { /* Send push */ }
}

// Collect all notifiers
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

### All<T> Contract

```java
public interface All<T> extends List<T> {}
```

**Key points:**
- `All<T>` extends `List<T>` — can be passed to any method expecting `List`
- Injects only **untagged** components
- Order is deterministic (based on component creation order)

---

## All<T> with Tags

Combine `@Tag` with `All<T>` for filtered collections.

```java
// Tagged handlers
@Tag(AsyncTag.class)
@Component
public final class AsyncHandler implements EventHandler {}

@Tag(AsyncTag.class)
@Component
public final class BatchHandler implements EventHandler {}

@Tag(SyncTag.class)
@Component
public final class SyncHandler implements EventHandler {}

// Only async handlers
@Component
public final class EventBus {
    private final List<EventHandler> asyncHandlers;

    public EventBus(
        @Tag(AsyncTag.class)
        All<EventHandler> asyncHandlers
    ) {
        this.asyncHandlers = asyncHandlers;
    }
}
```

### Syntax Rules

When you use `@Tag(SpecificTag.class)` with `All<T>` or `List<T>`, Kora automatically collects ALL components with that specific tag.

```java
// Inject all components with a specific tag
public EventBus(
    @Tag(AsyncTag.class)
    All<EventHandler> asyncHandlers
) {}

// Same with List
public EventBus(
    @Tag(AsyncTag.class)
    List<EventHandler> asyncHandlers
) {}

// To get ALL components (tagged + untagged), use @Tag(Tag.Any.class):
public ComponentCollector(
    @Tag(Tag.Any.class)
    All<Component> allComponents
) {}
```

---

## Tag.Any — Collect ALL Components

`@Tag(Tag.Any.class)` injects ALL components regardless of tags.

```java
// Tagged implementations
@Tag(RedisTag.class)
@Component
public final class RedisCache implements Cache {}

@Tag(CaffeineTag.class)
@Component
public final class CaffeineCache implements Cache {}

@Component
public final class DefaultCache implements Cache {}

// ALL caches injected
@Component
public final class CacheManager {
    private final List<Cache> allCaches;

    public CacheManager(@Tag(Tag.Any.class) List<Cache> allCaches) {
        this.allCaches = allCaches;
        // Gets: RedisCache, CaffeineCache, DefaultCache
    }

    public void invalidateAll() {
        allCaches.forEach(Cache::invalidate);
    }
}
```

### Tag with Specific Tag Type — Collect Components with Specific Tag

`@Tag(SpecificTag.class)` with `All<T>` or `List<T>` injects all components with that specific tag.

```java
// Multiple Redis caches
@Tag(RedisTag.class)
@Component
public final class UserRedisCache implements Cache {}

@Tag(RedisTag.class)
@Component
public final class OrderRedisCache implements Cache {}

@Tag(RedisTag.class)
@Component
public final class SessionRedisCache implements Cache {}

// Only Redis caches
@Component
public final class RedisCacheManager {
    private final List<Cache> redisCaches;

    public RedisCacheManager(
        @Tag(RedisTag.class)
        All<Cache> redisCaches
    ) {
        this.redisCaches = redisCaches;
    }
}
```

### Quick Reference Table

| Injection Pattern | What You Get |
|-------------------|--------------|
| `List<Cache>` | Only untagged caches |
| `@Tag(Tag.Any.class) List<Cache>` | ALL caches (tagged + untagged) |
| `@Tag(RedisTag.class) List<Cache>` | Single `RedisCache` (error if multiple) |
| `@Tag(RedisTag.class) All<Cache>` | All caches with `RedisTag` |
| `All<Cache>` | Same as `List<Cache>` (untagged only) |
| `@Tag(Tag.Any.class) All<Cache>` | ALL caches (tagged + untagged) |

---

## Common Patterns

### Pattern 1: Event Bus with Multiple Handlers

```java
// Event handler marker
public final class OrderCreatedTag {}

// Multiple handlers for same event
@Tag(OrderCreatedTag.class)
@Component
public final class EmailNotificationHandler implements EventHandler<OrderCreated> {
    public void handle(OrderCreated event) {
        // Send confirmation email
    }
}

@Tag(OrderCreatedTag.class)
@Component
public final class InventoryHandler implements EventHandler<OrderCreated> {
    public void handle(OrderCreated event) {
        // Reserve inventory
    }
}

@Tag(OrderCreatedTag.class)
@Component
public final class AnalyticsHandler implements EventHandler<OrderCreated> {
    public void handle(OrderCreated event) {
        // Track analytics
    }
}

// Event bus
@Component
public final class EventBus {
    private final List<EventHandler<OrderCreated>> handlers;

    public EventBus(
        @Tag(OrderCreatedTag.class)
        All<EventHandler<OrderCreated>> handlers
    ) {
        this.handlers = handlers;
    }

    public void publish(OrderCreated event) {
        handlers.forEach(h -> h.handle(event));
    }
}
```

### Pattern 2: Validation Chain

```java
// All validators
@Component
public final class ValidationService {
    private final List<Validator> validators;

    public ValidationService(All<Validator> validators) {
        this.validators = validators;
    }

    public ValidationResult validate(Request request) {
        for (Validator validator : validators) {
            var result = validator.validate(request);
            if (!result.isValid()) {
                return result;  // Fail fast
            }
        }
        return ValidationResult.ok();
    }
}

// Validator implementations
@Component
public final class AuthValidator implements Validator {
    public ValidationResult validate(Request request) { /* ... */ }
}

@Component
public final class RateLimitValidator implements Validator {
    public ValidationResult validate(Request request) { /* ... */ }
}

@Component
public final class SchemaValidator implements Validator {
    public ValidationResult validate(Request request) { /* ... */ }
}
```

### Pattern 3: Plugin Architecture

```java
// All plugins collected
@Component
public final class PluginManager {
    private final List<Plugin> plugins;

    public PluginManager(@Tag(Tag.Any.class) All<Plugin> plugins) {
        this.plugins = plugins;
    }

    public void init() {
        plugins.forEach(Plugin::initialize);
    }

    public void shutdown() {
        plugins.forEach(Plugin::shutdown);
    }

    public List<Plugin> getPlugins() {
        return List.copyOf(plugins);
    }
}

// Plugin implementations
@Component
public final class MetricsPlugin implements Plugin {
    public void initialize() { /* Setup metrics */ }
    public void shutdown() { /* Cleanup */ }
}

@Component
public final class TracingPlugin implements Plugin {
    public void initialize() { /* Setup tracing */ }
    public void shutdown() { /* Cleanup */ }
}

@Component
public final class HealthPlugin implements Plugin {
    public void initialize() { /* Setup health checks */ }
    public void shutdown() { /* Cleanup */ }
}
```

### Pattern 4: Health Checks

```java
@Component
public final class HealthChecker {
    private final All<HealthCheck> healthChecks;

    public HealthChecker(All<HealthCheck> healthChecks) {
        this.healthChecks = healthChecks;
    }

    public Map<String, Boolean> checkAll() {
        Map<String, Boolean> results = new HashMap<>();
        for (HealthCheck check : healthChecks) {
            try {
                check.run();
                results.put(check.name(), true);
            } catch (Exception e) {
                results.put(check.name(), false);
            }
        }
        return results;
    }
}

// Health check implementations
@Component
public final class DatabaseHealthCheck implements HealthCheck {
    public String name() { return "database"; }
    public void run() { /* Check DB connection */ }
}

@Component
public final class CacheHealthCheck implements HealthCheck {
    public String name() { return "cache"; }
    public void run() { /* Check cache connectivity */ }
}

@Component
public final class KafkaHealthCheck implements HealthCheck {
    public String name() { return "kafka"; }
    public void run() { /* Check Kafka consumer */ }
}
```

### Pattern 5: Strategy Pattern with Tags

```java
// Tag classes
public final class JsonTag {}
public final class XmlTag {}
public final class CsvTag {}

// Strategy implementations
@Tag(JsonTag.class)
@Component
public final class JsonExporter implements DataExporter {
    public void export(Data data) { /* JSON format */ }
}

@Tag(XmlTag.class)
@Component
public final class XmlExporter implements DataExporter {
    public void export(Data data) { /* XML format */ }
}

@Tag(CsvTag.class)
@Component
public final class CsvExporter implements DataExporter {
    public void export(Data data) { /* CSV format */ }
}

// All exporters for batch export
@Component
public final class ExportService {
    private final Map<String, DataExporter> exporters;

    public ExportService(
        @Tag(Tag.Any.class) All<DataExporter> allExporters,
        @Tag(JsonTag.class) DataExporter json,
        @Tag(XmlTag.class) DataExporter xml,
        @Tag(CsvTag.class) DataExporter csv
    ) {
        // Map for dynamic lookup
        this.exporters = allExporters.stream()
            .collect(Collectors.toMap(
                e -> getFormat(e),
                e -> e
            ));
    }

    public void export(Data data, String format) {
        exporters.get(format).export(data);
    }
}
```

---

## Troubleshooting

### Empty Collection

**Problem:** `All<Notifier>` is empty

**Check:**
1. Are components marked with `@Component`?
2. Are they in scanned packages?
3. Do they have all dependencies satisfied?

### Ambiguous Dependency Error

**Error:** `Found multiple components of type Cache`

**Solution:** Use `@Tag` to disambiguate or use collection injection:

```java
// WRONG: Ambiguous
public UserService(Cache cache) {}

// CORRECT: Tagged
public UserService(@Tag(RedisTag.class) Cache cache) {}

// OR: Collection
public UserService(@Tag(Tag.Any.class) List<Cache> caches) {}
```

### Tag.Any Not Working

**Problem:** `@Tag(Tag.Any.class)` only gets untagged components

**Check:**
1. Make sure you're using `List<T>` or `All<T>` (not single injection)
2. Verify `Tag.Any` is imported from correct package

### Wrong Order

**Problem:** Components not in expected order

**Solution:** Don't rely on injection order for logic. Use explicit ordering:

```java
@Component
public final class FirstValidator implements Validator {
    public int priority() { return 1; }  // Custom ordering method
}

@Component
public final class SecondValidator implements Validator {
    public int priority() { return 2; }
}

// Or sort manually with custom comparator
public ValidationService(All<Validator> validators) {
    this.validators = validators.stream()
        .sorted(Comparator.comparingInt(v -> v.priority()))
        .toList();
}
```

### Duplicate Components

**Problem:** Same implementation appears twice in collection

**Check:**
1. Is component defined in multiple modules?
2. Are there duplicate `@Component` annotations?

---

## See Also

- [SKILL.md](../SKILL.md) — Runtime DI overview
- [Tag Injection Reference](tag-injection-reference.md) — @Tag disambiguation patterns
- [Container Documentation](../../../.kora-agent/kora-docs/mkdocs/docs/en/documentation/container.md) — Official docs
