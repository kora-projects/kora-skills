# Kora Lifecycle and GraphInterceptor Reference

**Source:** [.kora-agent/kora-docs/mkdocs/docs/en/documentation/container.md](.kora-agent/kora-docs/mkdocs/docs/en/documentation/container.md)  
**Examples:** `.kora-agent/kora-examples/kora-java-helloworld/`

Kora provides lifecycle management for components with initialization and cleanup logic: Lifecycle interface for resource management, LifecycleWrapper for factory methods, GraphInterceptor for component modification during graph construction, and @Root for startup initialization.

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

Use `LifecycleWrapper` when you need lifecycle for components created via factory methods in `@Module`.
### Basic Example

```java
@Module
public interface CacheModule {

    default Cache cache(Config config) throws Exception {
        var cacheConfig = config.getConfig("cache");

        return LifecycleWrapper.wrap(
            new CaffeineCache(cacheConfig),  // Component instance
            cache -> {
                // init logic
                cache.warmup();
            },
            cache -> {
                // release logic
                cache.invalidateAll();
            }
        );
    }
}
```
### With Exception Handling

```java
@Module
public interface DatabaseModule {
    
    default DataSource dataSource(Config config) {
        return LifecycleWrapper.wrap(
            new DriverManagerDataSource(
                config.getString("database.url"),
                config.getString("database.username"),
                config.getString("database.password")
            ),
            ds -> {
                // init: test connection
                try (Connection conn = ds.getConnection()) {
                    System.out.println("Database connection OK");
                }
            },
            ds -> {
                // release: close connections
                if (ds instanceof AutoCloseable) {
                    ((AutoCloseable) ds).close();
                }
            }
        );
    }
}
```
### Async Lifecycle

```java
@Module
public interface SchedulerModule {

    default ScheduledExecutorService scheduler() {
        return LifecycleWrapper.wrap(
            Executors.newSingleThreadScheduledExecutor(),
            scheduler -> {
                // init: schedule periodic task
                scheduler.scheduleAtFixedRate(
                    this::cleanupTask,
                    0, 1, TimeUnit.HOURS
                );
            },
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

`GraphInterceptor` allows inspecting and modifying components during graph construction.
### Basic Example

```java
@Component
public final class MyGraphInterceptor implements GraphInterceptor {
    
    @Override
    public <T> T intercept(Graph graph, Class<T> type, T instance) {
        // Inspect or modify component
        if (instance instanceof DataSource) {
            // Wrap DataSource in proxy for logging
            return (T) new LoggingDataSource((DataSource) instance);
        }
        return instance;
    }
}
```
### Use Cases

| Use Case | Example |
|----------|---------|
| Logging proxy | Wrap services for call logging |
| Metrics collection | Add timing/metrics wrappers |
| Validation | Add parameter validation proxies |
| Circuit breaker | Add fault tolerance wrappers |
| Tracing | Add distributed tracing wrappers |

### Metrics Interceptor

```java
@Component
public final class MetricsInterceptor implements GraphInterceptor {
    private final MeterRegistry meterRegistry;

    public MetricsInterceptor(MeterRegistry meterRegistry) {
        this.meterRegistry = meterRegistry;
    }

    @Override
    public <T> T intercept(Graph graph, Class<T> type, T instance) {
        if (instance instanceof HttpClient) {
            return (T) new MetricsHttpClient(
                (HttpClient) instance,
                meterRegistry
            );
        }
        return instance;
    }
}
```
### Circuit Breaker Interceptor

```java
@Component
public final class CircuitBreakerInterceptor implements GraphInterceptor {
    private final ResilienceRegistry registry;
    
    public CircuitBreakerInterceptor(ResilienceRegistry registry) {
        this.registry = registry;
    }
    
    @Override
    public <T> T intercept(Graph graph, Class<T> type, T instance) {
        if (instance instanceof ExternalService) {
            return (T) registry.circuitBreaker(
                (ExternalService) instance,
                "external-service"
            );
        }
        return instance;
    }
}
```

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

## ValueOf<T> — Lazy Dependencies

### Purpose

`ValueOf<T>` provides lazy access to dependencies and prevents cascading refreshes when configuration changes.
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
    default Cache cache(Config config) {
        return LifecycleWrapper.wrap(
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
default MyComponent component(Config config) {
    return LifecycleWrapper.wrap(
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
public final class MyInterceptor implements GraphInterceptor {
    @Override
    public <T> T intercept(Graph graph, Class<T> type, T instance) {
        // Modify or wrap instance
        return instance;
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
