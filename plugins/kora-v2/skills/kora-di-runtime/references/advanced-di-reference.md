# Advanced DI Runtime Patterns

**Kora Version:** 1.2.x

This reference covers advanced runtime DI patterns in Kora, including `LifecycleWrapper` exact signatures and generic factory warnings.

---

## LifecycleWrapper Exact Signature

### Purpose

When wrapping a third-party resource (MongoClient, external RPC client, etc.) in a `@Module` factory method, you cannot implement `Lifecycle` directly on the resource. Use `LifecycleWrapper` to add init/release behavior.

### Signature (Kora 1.2.x)

```java
public class LifecycleWrapper<T> implements Wrapped<T>, Lifecycle {
    public LifecycleWrapper(T value, Function<T, Void> initFn, Function<T, Void> releaseFn) {
        // ...
    }
}
```

**Key points:**
- Return type is `Wrapped<T>`, **NOT** `T`
- Use **constructor** — static `wrap()` method does **NOT** exist in Kora 1.2.14
- Capture external resource in the `releaseFn` lambda

### Example: MongoDB Wrapper

```java
import com.mongodb.client.MongoClient;
import com.mongodb.client.MongoClients;
import com.mongodb.client.MongoDatabase;
import ru.tinkoff.kora.common.Component;
import ru.tinkoff.kora.common.Module;
import ru.tinkoff.kora.common.Default;
import ru.tinkoff.kora.application.graph.Wrapped;
import ru.tinkoff.kora.application.graph.LifecycleWrapper;

@Module
public interface MongoModule {
    
    @Default
    @Component
    default Wrapped<MongoDatabase> mongoDatabase(MongoConfig config) {
        MongoClient client = MongoClients.create(config.connectionString());
        
        // Constructor: LifecycleWrapper(value, initFn, releaseFn)
        return new LifecycleWrapper<>(
            client.getDatabase(config.databaseName()),  // The wrapped value
            db -> {                                      // Init function (async-safe)
                // Optional: verify connection, create indexes, etc.
                try {
                    db.runCommand(new Document("ping", 1));
                    System.out.println("MongoDB connected");
                } catch (Exception e) {
                    throw new RuntimeException("MongoDB ping failed", e);
                }
                return null;  // Void return
            },
            db -> {                                      // Release function
                // Capture 'client' to close
                client.close();
                System.out.println("MongoDB connection closed");
                return null;  // Void return
            }
        );
    }
}
```

### Alternative: Implement Lifecycle Directly

For your own classes, implement `Lifecycle` directly instead of wrapping:

```java
@Component
public final class DatabasePool implements Lifecycle {
    private final DataSource dataSource;
    private final ScheduledExecutorService scheduler;
    
    public DatabasePool(DataSource dataSource) {
        this.dataSource = dataSource;
        this.scheduler = Executors.newSingleThreadScheduledExecutor();
    }
    
    @Override
    public void init() throws Exception {
        try (Connection conn = dataSource.getConnection()) {
            System.out.println("Database connection OK");
        }
        scheduler.scheduleAtFixedRate(this::cleanup, 5, 5, TimeUnit.MINUTES);
    }
    
    @Override
    public void release() throws Exception {
        scheduler.shutdown();
        if (!scheduler.awaitTermination(30, TimeUnit.SECONDS)) {
            scheduler.shutdownNow();
        }
        if (dataSource instanceof AutoCloseable) {
            ((AutoCloseable) dataSource).close();
        }
    }
}
```

---

## ⚠️ Generic Factories Warning

### Problem

Kora treats generic methods in a `@Module` interface as **"generic factories"** (container.md §Generic Factory) and may use them for **ANY** matching type in the graph. This leads to implicit, hard-to-debug behavior.

### Wrong: Generic Method Inside Module

```java
@Module
public interface JdbcMappersModule {
    
    // BAD: Generic method inside module becomes a generic factory
    // Kora may use this for ANY Enum type, not just intended ones
    private <E extends Enum<E>> JdbcResultColumnMapper<E> enumMapper(Class<E> enumClass) {
        return (rs, index, columnCount) -> {
            String value = rs.getString(index);
            return value != null ? Enum.valueOf(enumClass, value) : null;
        };
    }
    
    // This implicitly creates bindings for all Enum types
    // Hard to debug: which enum uses which mapper?
}
```

### Correct: Top-Level Helper Methods

Move generic helpers to top-level `private static` methods in the same file — they are **not** module members and do **not** enter the graph:

```java
@Module
public interface JdbcMappersModule {
    
    // GOOD: Monomorphic per-type factories
    @Default
    @Component
    default JdbcResultColumnMapper<Status> statusMapper() {
        return enumMapper(Status.class);
    }
    
    @Default
    @Component
    default JdbcResultColumnMapper<Role> roleMapper() {
        return enumMapper(Role.class);
    }
    
    @Default
    @Component
    default JdbcResultColumnMapper<PunishmentType> punishmentTypeMapper() {
        return enumMapper(PunishmentType.class);
    }
}

// Top-level helper — NOT a module member, does not enter the graph
private static <E extends Enum<E>> JdbcResultColumnMapper<E> enumMapper(Class<E> enumClass) {
    return (rs, index, columnCount) -> {
        String value = rs.getString(index);
        return value != null ? Enum.valueOf(enumClass, value) : null;
    };
}
```

### Verification

Inspect generated `$ApplicationImpl`:

```java
// Generated graph should contain:
object : JdbcMappersModule {}

// With monomorphic methods only:
this.statusMapper()
this.roleMapper()
this.punishmentTypeMapper()

// NOT generic factories:
// this.<E>enumMapper(...)  // Should NOT appear
```

### When Generic Factories Are Appropriate

Generic factories are useful when you **intentionally** want a single implementation to handle multiple types:

```java
@Module
public interface CacheModule {
    
    // GOOD: Intentional generic factory for all cache types
    @Default
    @Component
    default <K, V> Cache<K, V> caffeineCache(CacheConfig config) {
        return new CaffeineCache<>(config);
    }
}
```

Use generic factories deliberately, not accidentally.

---

## See Also

- [Root Component Reference](references/root-component-reference.md) — `@Root` for self-starting components
- [Lifecycle Reference](references/lifecycle-reference.md) — `Lifecycle`, init/release, graceful shutdown
- [Tag Injection Reference](references/tag-injection-reference.md) — `@Tag` for disambiguation
- [Collection Injection Reference](references/collection-injection-reference.md) — `All<T>`, `List<T>`
