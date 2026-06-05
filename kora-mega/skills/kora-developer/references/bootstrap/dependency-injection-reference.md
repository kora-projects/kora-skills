# Kora Dependency Injection Reference

**Source:** [.kora-agent/kora-docs/mkdocs/docs/en/documentation/container.md](.kora-agent/kora-docs/mkdocs/docs/en/documentation/container.md)  
**Examples:** `.kora-agent/kora-examples/kora-java-helloworld/`

## Overview

Kora DI — **compile-time** DI container: **Code generation** (dependency graph built at compile time) | **Null safety** | **Fast startup** (no reflection) | **Type-safe**.

## @KoraApp — Main Container

**Basic Usage:**
```java
@KoraApp
public interface Application {
    static void main(String[] args) { KoraApplication.run(ApplicationGraph::graph); }
}
```
**Important:** `ApplicationGraph` is generated automatically by the annotation processor in the same package.

**What to Connect via extends:**
```java
@KoraApp
public interface Application extends
    HoconConfigModule, LogbackModule, JsonModule,  // External Module Factory
    PetModule, VetModule {  // Submodule Factory — for multi-module
    static void main(String[] args) { KoraApplication.run(ApplicationGraph::graph); }
}
```

**Module Auto-Discovery:** `@Module` in the same src/main/java — **auto-discovered**, do **NOT** require `extends`.

```java
@Module  // Auto-discovered — NO extends needed
public interface DatabaseModule {
    default DataSource dataSource(Config config) {
        return new DriverManagerDataSource(
            config.getString("database.url"),
            config.getString("database.username"), 
            config.getString("database.password")
        ); 
    }
}

@KoraApp
public interface Application extends HoconConfigModule, LogbackModule {  // External — requires extends
    static void main(String[] args) { KoraApplication.run(ApplicationGraph::graph); }
}
```

**When to Use extends:**

| Situation | Use extends |
|-----------|-------------|
| @Module in the same src/main/java | No (auto-discovery) |
| Module from an external library | Yes |
| Module from another Gradle module | Yes (via @KoraSubmodule) |
| Want explicit connection | Yes (optional) |

---

## @Component — Singleton Components

### Basic Component

```java
@Component
public final class UserService {
    private final UserRepository repository; 
    
    public UserService(UserRepository repository) { 
        this.repository = repository;
    } 
    
    public User findById(String id) { 
        return repository.findById(id);
    }
}
```

### Requirements for @Component Classes

| Requirement | Description |
|-------------|-------------|
| **Not abstract** | Class must not be abstract |
| **Single constructor** | Single constructor (automatic injection) |
| **Final** | Must be final if no aspects applied |

### Constructor Injection (Preferred)

```java
// Constructor injection (the only injection method in Kora)
@Component
public final class UserService {
    private final UserRepository repository; 
    public UserService(UserRepository repository) { this.repository = repository; }
}

// Field injection is not supported in Kora — constructor injection only
```

### Auto-Creation

Components are auto-created when:
- Class is annotated with `@Component`
- Has a single constructor (automatic injection)
- All constructor parameters can be resolved
- Class is not abstract

---

## @Module — Factory Methods

### Module Factory (Auto-Discovery)

Modules in the same source directory are auto-discovered:

```java
@Module
public interface DatabaseModule {
     
    default DataSource dataSource(Config config) {
        return new DriverManagerDataSource( 
            config.getString("database.url"),
            config.getString("database.username"), 
            config.getString("database.password")
        ); 
    }
     
    default JdbcDatabaseExecutor jdbcExecutor(DataSource dataSource) {
        return new JdbcDatabaseExecutor(dataSource); 
    }
}
```

### External Module Factory (Requires extends)

Modules from libraries/dependencies require explicit connection:

```java
// Module from Kora library
@KoraApp
public interface Application extends
    HoconConfigModule,      // From kora-config-hocon 
    LogbackModule,          // From kora-logging-logback
    JsonModule {            // From kora-json-module 
    
    static void main(String[] args) { 
        KoraApplication.run(ApplicationGraph::graph);
    }
}
```

### @DefaultComponent

Mark factory methods with `@DefaultComponent` for override priority:

```java
@Module
public interface DatabaseModule {
     
    @DefaultComponent
    default DataSource dataSource(Config config) { 
        return new DriverManagerDataSource(
            config.getString("database.url"), 
            config.getString("database.username"),
            config.getString("database.password") 
        );
    }
}
```

---

## @KoraSubmodule — Multi-Module Projects

### Purpose

`@KoraSubmodule` is used for **physical separation** into separate Gradle modules (each with its own `build.gradle`).

**Important:** One `@KoraSubmodule` per separate Gradle module.

### Multi-Module Project Structure

```
my-app/
├── common/
│   ├── build.gradle
│   └── src/main/java/com/example/common/
│       └── CommonModule.java
├── pet-api/
│   ├── build.gradle
│   └── src/main/java/com/example/pet/
│       └── PetModule.java
├── vet-api/
│   ├── build.gradle
│   └── src/main/java/com/example/vet/
│       └── VetModule.java
└── app/
    ├── build.gradle 
    └── src/main/java/com/example/app/
        └── Application.java
```

### Connection Example

```java
// common/ — base components
@KoraSubmodule
public interface CommonModule extends LogbackModule, HoconConfigModule {
    // Common components for all modules
}

// pet-api/ — Pet domain
@KoraSubmodule
public interface PetModule extends CommonModule, JdbcDatabaseModule {
    // Pet-specific components
}

// vet-api/ — Vet domain
@KoraSubmodule
public interface VetModule extends CommonModule, JdbcDatabaseModule {
    // Vet-specific components
}

// app/ — main application
@KoraApp
public interface Application extends PetModule, VetModule {
    static void main(String[] args) { 
        KoraApplication.run(ApplicationGraph::graph);
    }
}
```

---

## @Root — Startup Initialization

### Purpose

Components marked with `@Root` are always initialized at application startup.

### Use Cases

| Use Case | Example |
|----------|---------|
| Cache warm-up | Pre-loading data into cache |
| Connection check | Database health check at startup |
| Background tasks | Scheduler for periodic tasks |
| Event listeners | Event subscription at startup |

### Examples

```java
// Example 1: Cache warm-up
@Root
@Component
public final class CacheWarmer {
    public CacheWarmer(CacheService cache) { 
        cache.warm();  // Called at startup
    }
}

// Example 2: Database connection check
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

// Example 3: Scheduler for background tasks
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

---

## @Tag — Distinguishing Implementations

### Simple Approach (Preferred)

Use simple tag classes without creating custom annotations:

```java
// Simple tag classes
public final class RedisTag {}
public final class CaffeineTag {}

// Tagged implementations
@Tag(RedisTag.class)
@Component
public final class RedisCache implements Cache {
    // ...
}

@Tag(CaffeineTag.class)
@Component
public final class CaffeineCache implements Cache {
    // ...
}

// Injection by tag
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

---

## All<T> — Collection Injection

### Basic Usage

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

### Tag.Any — All Components Regardless of Tag

```java
// Tagged components
@Tag(RedisTag.class)
@Component
public final class RedisCache implements Cache {}

@Tag(CaffeineTag.class)
@Component
public final class CaffeineCache implements Cache {}

// Inject ALL caches (including tagged)
@Component
public final class CacheManager {
    private final List<Cache> allCaches; 
    
    public CacheManager(@Tag(Tag.Any.class) List<Cache> allCaches) { 
        this.allCaches = allCaches;
    }
}
```

### Tag.All — Collection with Specific Tag

```java
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

---

## ValueOf<T> — Indirect Dependencies

### Purpose

`ValueOf<T>` prevents cascading updates of components when configuration changes.

### Usage Example

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
| Circular dependency | Yes (alternative) |

---

## Optional Dependencies

### @Nullable for Optional

```java
@Component
public final class SmsService {
    private final Optional<SmsProvider> provider; 
    
    public SmsService(@Nullable SmsProvider provider) { 
        this.provider = Optional.ofNullable(provider);
    } 
    
    public void send(String message) { 
        provider.ifPresent(p -> p.send(message));
    }
}
```

### Default Methods in Interfaces

```java
@DefaultComponent
@Component
public final class DefaultEmailService implements EmailService {
    // Default implementation
}

// Can be overridden in application
```

---

## Lifecycle — Resource Management

### Lifecycle Interface

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
        // Pool initialization, cache warm-up
    }
     
    @Override
    public void release() throws Exception { 
        // Called during application shutdown
        // Close connections, cleanup resources
    }
}
```

### Graceful Shutdown

Kora handles SIGTERM and calls `release()` methods in **reverse order** of component creation.

### LifecycleWrapper for Factory Methods

```java
@Module
public interface CacheModule {
     
    default Cache cache(Config config) throws Exception {
        var cacheConfig = config.getConfig("cache"); 
        
        return LifecycleWrapper.wrap( 
            new CaffeineCache(cacheConfig),
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

---

## GraphInterceptor — Inspection and Modification

### Purpose

`GraphInterceptor` allows inspecting and modifying components during graph construction.

### Usage Example

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
| Logging proxy | Call logging |
| Metrics | Metrics collection |
| Validation | Parameter validation |
| Circuit breaker | Fault protection |

---

## Component Override

### Override Priority

1. Explicit factory methods in application
2. @DefaultComponent factory methods
3. Auto-created components

### Override Example

```java
// Base module
@Module
public interface DatabaseModule {
     
    @DefaultComponent
    default DataSource dataSource(Config config) { 
        return new DriverManagerDataSource(
            config.getString("db.url"), 
            config.getString("db.username"),
            config.getString("db.password") 
        );
    }
}

// Override for tests
@Module
public interface TestDatabaseModule {
     
    // Overrides dataSource from DatabaseModule
    default DataSource dataSource(Config config) { 
        return new TestDataSource();
    }
}

// Test application
@KoraApp
public interface TestApplication extends TestDatabaseModule, LogbackModule {
    static void main(String[] args) { 
        KoraApplication.run(ApplicationGraph::graph);
    }
}
```

---

## Troubleshooting

### Component Not Created

**Problem:** Component is not created in the container.

**Causes:**
1. Class is not annotated with `@Component`
2. Missing dependency in graph (component is not used)
3. Class is abstract or interface
4. Not marked as `@Root` for startup initialization

**Solution:**
```java
@Root
@Component
public final class CacheWarmer {
    public CacheWarmer(CacheService cache) { 
        cache.warm();
    }
}
```

### Ambiguous Dependency

**Problem:** Multiple implementations without tags.

```
error: Found several components of type com.example.Cache:
  - com.example.RedisCache
  - com.example.CaffeineCache
```

**Solution:** Use `@Tag`:
```java
@Tag(RedisTag.class)
@Component
public final class RedisCache implements Cache {}

@Tag(CaffeineTag.class)
@Component
public final class CaffeineCache implements Cache {}
```

### Circular Dependency

**Problem:** Circular dependency detected.

```
error: Circular dependency detected:
  ServiceA -> ServiceB -> ServiceC -> ServiceA
```

**Solution 1:** Use `ValueOf<T>`:
```java
@Component
public final class ServiceA {
    private final ValueOf<ServiceB> serviceB; 
    
    public ServiceA(ValueOf<ServiceB> serviceB) { 
        this.serviceB = serviceB;
    }
}
```

**Solution 2:** Refactor — extract common logic into separate service.

---

## Quick Reference

### Annotations Summary

| Annotation | Purpose | Target |
|------------|---------|--------|
| `@KoraApp` | Main application container | Interface |
| `@Component` | Singleton component | Class |
| `@Module` | Factory methods | Interface |
| `@KoraSubmodule` | Multi-module project | Interface |
| `@Root` | Startup initialization | Class |
| `@Tag` | Distinguish implementations | Class, Parameter, Field |
| `@DefaultComponent` | Override priority | Method |
| `@ConfigSource` | Configuration interface | Interface |
| *(none)* | Constructor injection (automatic) | Constructor |

### Dependency Injection Patterns

```java
// Constructor injection (preferred)
@Component
public final class Service {
    public Service(Dependency dep) {}
}

// Tagged injection
public Service(@Tag(MyTag.class) Dependency dep) {}

// Collection injection
public Service(All<Listener> listeners) {}

// Optional injection
public Service(@Nullable Dependency dep) {}

// Lazy injection
public Service(ValueOf<Config> config) {}
```
