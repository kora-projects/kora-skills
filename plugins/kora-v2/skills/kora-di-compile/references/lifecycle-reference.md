# Kora Lifecycle and GraphInterceptor Reference

**Source:** `.kora-agent/kora-docs/mkdocs/docs/en/documentation/container.md`
**Examples:** `.kora-agent/kora-examples/guides/java/kora-java-guide-dependency-injection/`

## Contents

- [Lifecycle Interface](#lifecycle-interface)
- [LifecycleWrapper for Factory Methods](#lifecyclewrapper-for-factory-methods)
- [@Root — Startup Initialization](#root--startup-initialization)
- [GraphInterceptor](#graphinterceptor)
- [ValueOf<T> — Indirect Dependencies](#valueoft--indirect-dependencies)
- [Common Mistakes](#common-mistakes)
- [Quick Reference](#quick-reference)

Kora provides lifecycle management for components with initialization and cleanup logic: the `Lifecycle` interface for resource management, `LifecycleWrapper`/`Wrapped<T>` for factory methods, `GraphInterceptor<T>` for component modification during graph construction, and `@Root` for startup initialization.

---

## Lifecycle Interface

### Basic Usage

Components implement `Lifecycle` for resource management:

```java
@Component
public final class DatabasePool implements Lifecycle {
    private final DataSource dataSource;
    
    public DatabasePool(DataSource dataSource) {
        this.dataSource = dataSource;
    }
    
    @Override
    public void init() throws Exception {
        // Called after component creation
        // Pool initialization, cache warm-up, connection test
        System.out.println("Database pool initialized");
    }
    
    @Override
    public void release() throws Exception {
        // Called during shutdown
        // Close connections, cleanup resources
        if (dataSource instanceof AutoCloseable) {
            ((AutoCloseable) dataSource).close();
        }
    }
}
```
### Lifecycle Methods

| Method | When Called | Purpose |
|--------|-------------|---------|
| `init()` | After component creation | Initialize resources, warm caches, test connections |
| `release()` | During shutdown (SIGTERM) | Cleanup resources, close connections |

Kora calls `release()` methods in **reverse order** of component creation.

---

## LifecycleWrapper for Factory Methods

### Purpose

Use `LifecycleWrapper` when you need lifecycle hooks for a component created via a
factory method in a `@Module`. The factory returns `Wrapped<T>` and constructs a
`LifecycleWrapper<>` with the instance, an init callback, and a release callback.
The container unwraps `Wrapped<T>` and injects the underlying `T` into dependents.

```java
public final class LifecycleWrapper<T> implements Wrapped<T>, Lifecycle {
    // new LifecycleWrapper<>(value, initConsumer, releaseConsumer)
}
```

### Basic Example

```java
import ru.tinkoff.kora.application.graph.LifecycleWrapper;
import ru.tinkoff.kora.application.graph.Wrapped;

@Module
public interface CacheModule {

    default Wrapped<Cache> cache(Config config) {
        var cacheConfig = config.get("cache");

        return new LifecycleWrapper<>(
            new CaffeineCache(cacheConfig),  // Component instance
            cache -> cache.warmup(),         // init logic
            cache -> cache.invalidateAll()   // release logic
        );
    }
}
```

### With Exception Handling

```java
@Module
public interface DatabaseModule {

    default Wrapped<DataSource> dataSource(Config config) {
        return new LifecycleWrapper<>(
            new DriverManagerDataSource(
                config.get("database").get("url").asString(),
                config.get("database").get("username").asString(),
                config.get("database").get("password").asString()
            ),
            ds -> {
                // init: test connection
                try (Connection conn = ds.getConnection()) {
                    System.out.println("Database connection OK");
                }
            },
            ds -> {
                // release: close connections
                if (ds instanceof AutoCloseable c) {
                    c.close();
                }
            }
        );
    }
}
```

### Scheduler Lifecycle

```java
@Module
public interface SchedulerModule {

    default Wrapped<ScheduledExecutorService> scheduler() {
        return new LifecycleWrapper<>(
            Executors.newSingleThreadScheduledExecutor(),
            scheduler -> scheduler.scheduleAtFixedRate(
                this::cleanupTask, 0, 1, TimeUnit.HOURS
            ),
            scheduler -> {
                // release: graceful shutdown
                scheduler.shutdown();
                if (!scheduler.awaitTermination(30, TimeUnit.SECONDS)) {
                    scheduler.shutdownNow();
                }
            }
        );
    }

    private void cleanupTask() {
        // Periodic cleanup logic
    }
}
```

---

## @Root — Startup Initialization

### Purpose

Components marked with `@Root` are **always initialized** at application startup, even if not directly referenced.
### Use Cases

| Use Case | Example |
|----------|---------|
| Cache warm-up | Pre-loading data into cache |
| Connection check | Database health check at startup |
| Background tasks | Scheduler for periodic tasks |
| Event listeners | Event subscription at startup |
| Health checks | Registering health check endpoints |

### Examples

**Cache Warmer:**

```java
@Root
@Component
public final class CacheWarmer {
    public CacheWarmer(CacheService cache) {
        cache.warm();  // Called at startup
    }
}
```

**Database Health Checker:**

```java
@Root
@Component
public final class DatabaseHealthChecker {
    public DatabaseHealthChecker(DataSource dataSource) {
        try {
            dataSource.getConnection().close();
            System.out.println("Database connection OK");
        } catch (SQLException e) {
            throw new RuntimeException("Database connection failed", e);
        }
    }
}
```

**Background Scheduler:**

```java
@Root
@Component
public final class BackgroundScheduler {
    private final ScheduledExecutorService scheduler;
    
    public BackgroundScheduler(TaskProcessor processor) {
        this.scheduler = Executors.newSingleThreadScheduledExecutor();
        scheduler.scheduleAtFixedRate(
            processor::process, 
            0, 1, TimeUnit.MINUTES
        );
    }
}
```

**Event Listener:**

```java
@Root
@Component
public final class EventListener {
    public EventListener(EventBus eventBus) {
        eventBus.subscribe(MyEvent.class, this::handleEvent);
    }

    private void handleEvent(MyEvent event) {
        // Handle event
    }
}
```

---

## GraphInterceptor

### Purpose

`GraphInterceptor<T>` lets you inspect, initialize, or replace a specific component
of type `T` after it is created but before any other component starts using it.
Place a component implementing `GraphInterceptor<T>` into the container. Its contract
mirrors `Lifecycle` except that `init`/`release` receive and return the value, so the
returned instance is what other components depend on.

```java
public interface GraphInterceptor<T> {

    T init(T value);

    T release(T value);
}
```

### Basic Example

This interceptor warms a cache built on top of `JdbcDatabase` before the rest of the
graph can use it:

```java
import ru.tinkoff.kora.application.graph.GraphInterceptor;

@Component
public final class CacheWarmupInterceptor implements GraphInterceptor<JdbcDatabase> {

    @Override
    public JdbcDatabase init(JdbcDatabase value) {
        // warm up cache from the database, then expose the same instance
        return value;
    }

    @Override
    public JdbcDatabase release(JdbcDatabase value) {
        return value;
    }
}
```

### Returning a Different Instance

`init` may return a modified or wrapped instance of `T`, which then becomes the
dependency seen by other components:

```java
@Component
public final class LoggingDataSourceInterceptor implements GraphInterceptor<DataSource> {

    @Override
    public DataSource init(DataSource value) {
        return new LoggingDataSource(value);  // dependents receive the wrapper
    }

    @Override
    public DataSource release(DataSource value) {
        return value;
    }
}
```

### Use Cases

| Use Case | Example |
|----------|---------|
| Cache warm-up | Pre-load data into a cache built on a `JdbcDatabase` |
| Logging proxy | Wrap a component to log calls |
| Validation | Wrap a component with parameter validation |
| Tracing | Wrap a component with tracing instrumentation |

---

## Combining Lifecycle and @Root

### Full Example

```java
@Root
@Component
public final class CacheManager implements Lifecycle {
    private final Cache cache;
    private final ScheduledExecutorService scheduler;

    public CacheManager(CacheConfig config) {
        this.cache = new CaffeineCache(config);
        this.scheduler = Executors.newSingleThreadScheduledExecutor();
    }

    @Override
    public void init() {
        // Warm cache at startup
        cache.warmup();

        // Schedule periodic cleanup
        scheduler.scheduleAtFixedRate(
            cache::evictExpired,
            5, 5, TimeUnit.MINUTES
        );

        System.out.println("Cache manager initialized");
    }

    @Override
    public void release() {
        // Stop scheduler
        scheduler.shutdown();

        // Clear cache
        cache.invalidateAll();

        System.out.println("Cache manager released");
    }
}
```
### Multiple Lifecycle Components

```java
// Components are released in reverse order of creation:
// 1. DatabasePool created → 2. CacheManager created → 3. Scheduler created
// Shutdown order:
// 1. Scheduler released → 2. CacheManager released → 3. DatabasePool released
```

---

## ValueOf<T> — Indirect Dependencies

### Purpose

`ValueOf<T>` provides indirect access to a dependency via `get()`. Kora treats it as an
indirect link: when the wrapped component is refreshed, the holder is **not** refreshed,
which decouples lifecycles and breaks direct dependency cycles. `ValueOf<T>` also exposes
`refresh()` to trigger a component refresh (for example, on config file change).

```java
public interface ValueOf<T> {
    T get();
    void refresh();
}
```

### Basic Example

```java
@Component
public final class ActivityRecorder {
    private final ValueOf<ActivityLog> log;

    public ActivityRecorder(ValueOf<ActivityLog> log) {
        this.log = log;
    }

    public void record(String activity) {
        log.get().log(activity);  // Lazy access
    }
}
```
### When to Use

| Situation | Use ValueOf |
|-----------|-------------|
| Configuration may change | Yes |
| Preventing cascading refresh | Yes |
| Lazy initialization | Yes |
| Circular dependency | Alternative |

### Circular Dependency Resolution

```java
// Without ValueOf — circular dependency error
@Component
public final class ServiceA {
    public ServiceA(ServiceB b) {}  // Circular!
}

@Component
public final class ServiceB {
    public ServiceB(ServiceA a) {}  // Circular!
}

// With ValueOf — resolves circular dependency
@Component
public final class ServiceA {
    private final ValueOf<ServiceB> b;
    
    public ServiceA(ValueOf<ServiceB> b) {
        this.b = b;  // Lazy reference
    }
    
    public void doSomething() {
        b.get().doOther();  // Access when needed
    }
}
```

---

## Common Mistakes

### Not Implementing Lifecycle for Resources

```java
// BAD — connections never closed
@Component
public final class DatabasePool {
    private final DataSource dataSource;

    public DatabasePool(DataSource dataSource) {
        this.dataSource = dataSource;
    }
}

// GOOD
@Component
public final class DatabasePool implements Lifecycle {
    private final DataSource dataSource;

    public DatabasePool(DataSource dataSource) {
        this.dataSource = dataSource;
    }

    @Override
    public void release() throws Exception {
        if (dataSource instanceof AutoCloseable) {
            ((AutoCloseable) dataSource).close();
        }
    }
}
```
### Missing @Root for Startup Tasks

```java
// BAD — never initialized
@Component
public final class CacheWarmer {
    public CacheWarmer(CacheService cache) {
        cache.warm();  // Never called!
    }
}

// GOOD
@Root
@Component
public final class CacheWarmer {
    public CacheWarmer(CacheService cache) {
        cache.warm();  // Called at startup
    }
}
```
### Wrong LifecycleWrapper Usage

```java
// BAD — lifecycle not wrapped
@Module
public interface CacheModule {
    default Cache cache(Config config) {
        return new CaffeineCache(config);  // No lifecycle!
    }
}

// GOOD
@Module
public interface CacheModule {
    default Wrapped<Cache> cache(Config config) {
        return new LifecycleWrapper<>(
            new CaffeineCache(config),
            cache -> cache.warmup(),
            cache -> cache.invalidateAll()
        );
    }
}
```

---

## Quick Reference

### Lifecycle Component
```java
@Component
public final class MyComponent implements Lifecycle {
    @Override
    public void init() { /* init logic */ }
    
    @Override
    public void release() { /* cleanup logic */ }
}
```
### LifecycleWrapper
```java
default Wrapped<MyComponent> component(Config config) {
    return new LifecycleWrapper<>(
        new MyComponent(config),
        c -> c.init(),
        c -> c.cleanup()
    );
}
```
### @Root Component
```java
@Root
@Component
public final class StartupTask {
    public StartupTask(Service service) {
        service.initialize();  // Called at startup
    }
}
```
### GraphInterceptor
```java
@Component
public final class MyInterceptor implements GraphInterceptor<DataSource> {
    @Override
    public DataSource init(DataSource value) {
        // Inspect, initialize, or wrap the instance
        return value;
    }

    @Override
    public DataSource release(DataSource value) {
        return value;
    }
}
```
### ValueOf
```java
@Component
public final class MyService {
    public MyService(ValueOf<OtherService> other) {
        // Lazy access via other.get()
    }
}
```
