# Kora Container — Dependency Injection Reference

**Source:** [.kora-agent/kora-docs/mkdocs/docs/en/documentation/container.md](.kora-agent/kora-docs/mkdocs/docs/en/documentation/container.md)  
**Examples:** `.kora-agent/kora-examples/kora-java-helloworld/`

## Overview

Kora Container — compile-time DI container: **Compile-time code generation** (dependency graph built at compile time) | **Null safety** (all dependencies checked at compile time) | **Fast startup** (no runtime reflection) | **Type-safe** (full type checking at compile time).

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
    HoconConfigModule,  // External Module Factory — modules from libraries
    LogbackModule, JsonModule,
    PetModule, VetModule {  // Submodule Factory — for multi-module projects
    static void main(String[] args) { KoraApplication.run(ApplicationGraph::graph); }
}
```

**What NOT to connect:** `@Module` interfaces in the same src/main/java — auto-discovered.

## @Component — Singleton Components

**Basic Component:**
```java
@Component
public final class UserService {
    private final UserRepository repository;
    public UserService(UserRepository repository) { this.repository = repository; }  // Constructor injection (preferred)
    public User findById(String id) { return repository.findById(id); }
}
```

**Requirements for @Component Classes:**

| Requirement | Description |
|-------------|-------------|
| **Not abstract** | Class must not be abstract |
| **Single constructor** | Single constructor (automatic injection) |
| **Final** | Must be final if no aspects applied |

**Constructor Injection (Preferred):**
```java
// Constructor injection (the only injection method in Kora)
@Component
public final class UserService {
    private final UserRepository repository; 
    public UserService(UserRepository repository) { this.repository = repository; }
}

// Field injection is not supported in Kora — constructor injection only
```

---

## @Module — Factory Methods

### Module Factory (Auto-Discovery)

**Important:** `@Module` interfaces in the same src/main/java as `@KoraApp` are **auto-discovered** and do **NOT** require `extends`.

```java
@Module  // Auto-discovery — NO extends required
public interface DatabaseModule {
    default DataSource dataSource(Config config) {
        return new DriverManagerDataSource(config.getString("database.url"), config.getString("database.username"), config.getString("database.password"));
    }
    default JdbcDatabaseExecutor jdbcExecutor(DataSource dataSource) { return new JdbcDatabaseExecutor(dataSource); }
}

@KoraApp
public interface Application extends HoconConfigModule, LogbackModule {  // modules NOT connected via extends
    static void main(String[] args) { KoraApplication.run(ApplicationGraph::graph); }
}
```

### External Module Factory (Requires extends)

```java
@KoraApp
public interface Application extends
    HoconConfigModule,  // From kora-config-hocon
    LogbackModule,  // From kora-logging-logback
    JsonModule {  // From kora-json-module
    static void main(String[] args) { KoraApplication.run(ApplicationGraph::graph); }
}
```

### When to Use extends

| Situation | Use extends |
|-----------|-------------|
| @Module in the same src/main/java | No (auto-discovery) |
| Module from an external library | Yes |
| Module from another Gradle module | Yes (via @KoraSubmodule) |
| Want explicit connection | Yes (optional) |

---

## @KoraSubmodule — Multi-Module Projects

**Purpose:** `@KoraSubmodule` is used for **physical separation** into separate Gradle modules (each with its own `build.gradle`).

**Multi-Module Structure:**
```
my-app/
├── common/ → CommonModule.java
├── pet-api/ → PetModule.java
├── vet-api/ → VetModule.java
└── app/ → Application.java
```

**Connection Example:**
```java
@KoraSubmodule
public interface CommonModule extends LogbackModule, HoconConfigModule { /* Common components */ }

@KoraSubmodule
public interface PetModule extends CommonModule, JdbcDatabaseModule { /* Pet domain */ }

@KoraSubmodule
public interface VetModule extends CommonModule, JdbcDatabaseModule { /* Vet domain */ }

@KoraApp
public interface Application extends PetModule, VetModule {
    static void main(String[] args) { KoraApplication.run(ApplicationGraph::graph); }
}
```

**Important:** One `@KoraSubmodule` per separate Gradle module | Each submodule corresponds to its own `build.gradle` | Submodules require `extends`.

---

## @Root — Startup Initialization

**Purpose:** Components marked with `@Root` are always initialized at application startup.

**Use Cases:**

| Use Case | Example |
|----------|---------|
| Cache warm-up | Pre-loading data into cache |
| Connection check | Database health check at startup |
| Background tasks | Scheduler for periodic tasks |
| Event listeners | Event subscription at startup |

### Examples

```java
// Example 1: Cache warm-up
@Root @Component
public final class CacheWarmer {
    public CacheWarmer(CacheService cache) { cache.warm(); }  // Called at startup
}

// Example 2: Database connection check
@Root @Component
public final class DatabaseHealthChecker {
    public DatabaseHealthChecker(DataSource dataSource) {
        try { dataSource.getConnection().close(); System.out.println("Database connection OK"); }
        catch (SQLException e) { throw new RuntimeException("Database connection failed", e); }
    }
}

// Example 3: Scheduler for background tasks
@Root @Component
public final class BackgroundScheduler {
    private final ScheduledExecutorService scheduler;
    public BackgroundScheduler(TaskProcessor processor) {
        this.scheduler = Executors.newSingleThreadScheduledExecutor();
        scheduler.scheduleAtFixedRate(processor::process, 0, 1, TimeUnit.MINUTES);
    }
}
```

---

## @Tag — Distinguishing Implementations

**Simple Approach (Preferred):**
```java
public final class RedisTag {}  // Simple tag class
public final class CaffeineTag {}

@Tag(RedisTag.class) @Component
public final class RedisCache implements Cache {}

@Tag(CaffeineTag.class) @Component
public final class CaffeineCache implements Cache {}

@Component
public final class UserService {
    public UserService(@Tag(RedisTag.class) Cache cache) {}  // Injects RedisCache specifically
}
```

**Why Simple Approach is Better:**
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

**Basic Usage:**
```java
@Component
public final class NotificationService {
    private final List<Notifier> notifiers;
    public NotificationService(All<Notifier> notifiers) { this.notifiers = List.copyOf(notifiers); }
    public void notify(String message) { notifiers.forEach(n -> n.send(message)); }
}
```

**Tag.Any — All Components Regardless of Tag:**
```java
@Tag(RedisTag.class) @Component public final class RedisCache implements Cache {}
@Tag(CaffeineTag.class) @Component public final class CaffeineCache implements Cache {}

@Component
public final class CacheManager {
    private final List<Cache> allCaches;
    public CacheManager(@Tag(Tag.Any.class) List<Cache> allCaches) { this.allCaches = allCaches; }
}
```

**Tag.All — Collection with Specific Tag:**
```java
@Component
public final class RedisCacheManager {
    private final List<Cache> redisCaches;
    public RedisCacheManager(@Tag(RedisTag.class) @Tag(Tag.All.class) List<Cache> redisCaches) {
        this.redisCaches = redisCaches;
    }
}
```

---

## ValueOf<T> — Indirect Dependencies

**Purpose:** `ValueOf<T>` prevents cascading updates when configuration changes.

**Usage Example:**
```java
@Component
public final class ActivityRecorder {
    private final ValueOf<ActivityLog> log;
    public ActivityRecorder(ValueOf<ActivityLog> log) { this.log = log; }
    public void record(String activity) { log.get().log(activity); }  // Lazy access
}
```

**When to Use:**

| Situation | Use ValueOf |
|-----------|-------------|
| Configuration may change | Yes |
| Preventing cascading refresh | Yes |
| Lazy initialization | Yes |
| Circular dependency | Yes (alternative) |

---

## Optional Dependencies

**@Nullable for Optional:**
```java
@Component
public final class SmsService {
    private final Optional<SmsProvider> provider;
    public SmsService(@Nullable SmsProvider provider) { this.provider = Optional.ofNullable(provider); }
    public void send(String message) { provider.ifPresent(p -> p.send(message)); }
}
```

**Default Methods in Interfaces:**
```java
@DefaultComponent @Component
public final class DefaultEmailService implements EmailService { /* Default implementation */ }
// Can be overridden in application
```

---

## Lifecycle — Resource Management

**Lifecycle Interface:**
```java
@Component
public final class DatabasePool implements Lifecycle {
    private final DataSource dataSource;
    public DatabasePool(DataSource dataSource) { this.dataSource = dataSource; }
    @Override public void init() throws Exception { /* Pool initialization, cache warm-up */ }
    @Override public void release() throws Exception { /* Close connections, cleanup resources */ }
}
```

**Graceful Shutdown:** Kora handles SIGTERM and calls `release()` in **reverse order** of component creation.

**LifecycleWrapper for factory methods:**
```java
@Module
public interface CacheModule {
    default Cache cache(Config config) throws Exception {
        return LifecycleWrapper.wrap(new CaffeineCache(config.getConfig("cache")),
            cache -> cache.warmup(),  // init logic
            cache -> cache.invalidateAll());  // release logic
    }
}
```

---

## GraphInterceptor — Inspection and Modification

**Purpose:** `GraphInterceptor` allows inspecting and modifying components during graph construction.

**Usage Example:**
```java
@Component
public final class MyGraphInterceptor implements GraphInterceptor {
    @Override
    public <T> T intercept(Graph graph, Class<T> type, T instance) {
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

## Generic Factory — Parameterized Creation

```java
@Module
public interface RepositoryModule {
    // Generic factory for creating Repository<T>
    default <T> Repository<T> repository(Class<T> entityType, DataSource dataSource) {
        return new JdbcRepository<>(entityType, dataSource);
    }
    // Concrete implementations
    default Repository<User> userRepository(DataSource dataSource) { return repository(User.class, dataSource); }
    default Repository<Order> orderRepository(DataSource dataSource) { return repository(Order.class, dataSource); }
}
```

---

## Component Override

**Override Priority:** 1. Explicit factory methods in application → 2. @DefaultComponent factory methods → 3. Auto-created components.

**Override Example:**
```java
// Base module
@Module
public interface DatabaseModule {
    @DefaultComponent
    default DataSource dataSource(Config config) {
        return new DriverManagerDataSource(config.getString("db.url"), config.getString("db.username"), config.getString("db.password"));
    }
}

// Override for tests
@Module
public interface TestDatabaseModule {
    // Overrides dataSource from DatabaseModule
    default DataSource dataSource(Config config) { return new TestDataSource(); }
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

**Component Not Created:** Causes: no `@Component` | Missing dependency in graph | Class is abstract | Not marked as `@Root`.

**Solution:**
```java
@Root @Component
public final class CacheWarmer {
    public CacheWarmer(CacheService cache) { cache.warm(); }
}
```

**Ambiguous Dependency:** Multiple implementations without tags.

**Solution:** Use `@Tag`:
```java
@Tag(RedisTag.class) @Component public final class RedisCache implements Cache {}
@Tag(CaffeineTag.class) @Component public final class CaffeineCache implements Cache {}
```

**Circular Dependency:**

**Solution 1:** Use `ValueOf<T>`:
```java
@Component
public final class ServiceA {
    private final ValueOf<ServiceB> serviceB;
    public ServiceA(ValueOf<ServiceB> serviceB) { this.serviceB = serviceB; }
}
```

**Solution 2:** Refactor — extract common logic into separate service.

**Missing Configuration:**
```
com.typesafe.config.ConfigException$Missing: No configuration setting found for key 'database.url'
```

**Solution:** Check `application.conf` in `src/main/resources` | Use optional: `${?DATABASE_URL:"jdbc:postgresql://localhost:5432/mydb"}`.

**Annotation Processor Not Running:** `*Graph` classes not generated.

**Solution:**
```groovy
configurations { koraBom; annotationProcessor.extendsFrom(koraBom); implementation.extendsFrom(koraBom) }
dependencies {
    koraBom platform("ru.tinkoff.kora:kora-parent:1.2.15")
    annotationProcessor "ru.tinkoff.kora:annotation-processors"
}
```

---

## Common Mistakes

**Mistake 1: Non-Final Class**
```java
// BAD — class must be final
@Component
public class UserService {}

// GOOD
@Component
public final class UserService { public UserService(UserRepository repository) { this.repository = repository; } }
```

**Mistake 2: Missing @Tag**
```java
// BAD — ambiguous dependency
@Component
public final class RedisCache implements Cache {}

@Component
public final class CaffeineCache implements Cache {}

// GOOD
@Tag(RedisTag.class) @Component public final class RedisCache implements Cache {}
@Tag(CaffeineTag.class) @Component public final class CaffeineCache implements Cache {}
```

**Mistake 3: Direct Config Usage**
```java
// BAD
default DataSource dataSource(Config config) {
    return new DriverManagerDataSource(config.getString("database.url"), config.getString("database.username"));
}

// GOOD
@ConfigSource("database")
public interface DatabaseConfig { String url(); String username(); }

default DataSource dataSource(DatabaseConfig config) {
    return new DriverManagerDataSource(config.url(), config.username());
}
```

**Mistake 4: Ignoring Lifecycle**
```java
// BAD — resources not released
@Component
public final class DatabasePool {
    private final DataSource dataSource;
    public DatabasePool(DataSource dataSource) { this.dataSource = dataSource; }
}

// GOOD
@Component
public final class DatabasePool implements Lifecycle {
    private final DataSource dataSource;
    public DatabasePool(DataSource dataSource) { this.dataSource = dataSource; }
    @Override public void release() throws Exception {
        if (dataSource instanceof AutoCloseable) ((AutoCloseable) dataSource).close();
    }
}
```
