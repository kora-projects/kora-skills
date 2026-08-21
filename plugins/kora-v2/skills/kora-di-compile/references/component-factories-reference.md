# Component Factories Reference

**Source:** `.kora-agent/kora-docs/mkdocs/docs/en/documentation/container.md`
**Examples:** `.kora-agent/kora-examples/guides/java/kora-java-guide-dependency-injection/`

## Contents

- [Factory Types](#factory-types)
- [1. Auto Factory (@Component)](#1-auto-factory-component)
- [2. Basic Factory](#2-basic-factory)
- [3. Module Factory](#3-module-factory)
- [4. Generic Factory](#4-generic-factory)
- [5. Extension Factory](#5-extension-factory)
- [Factory Method Patterns](#factory-method-patterns)
- [Factory Selection Guide](#factory-selection-guide)
- [Common Mistakes](#common-mistakes)

## Overview

Component factories are methods or classes that create component instances. Kora supports multiple factory patterns for different use cases.

## Factory Types

| Type | Location | Use Case |
|------|----------|----------|
| **Auto Factory** | `@Component` class | Standard application services |
| **Basic Factory** | `@KoraApp` interface | Simple inline creation |
| **Module Factory** | `@Module` interface | Organized component groups |
| **Generic Factory** | `@Module` with `<T>` | Parameterized components |
| **Extension Factory** | Annotation processor | Framework-level creation |

## 1. Auto Factory (@Component)

Automatic component creation from class with single constructor.

```java
import ru.tinkoff.kora.common.Component;

@Component
public final class UserService {
    private final UserRepository repository;
    
    public UserService(UserRepository repository) {
        this.repository = repository;
    }
}
```

### Requirements

- Not abstract
- Single public constructor
- Final (unless aspects applied)
- All dependencies resolvable

## 2. Basic Factory

Inline factory methods in `@KoraApp` interface.

```java
@KoraApp
public interface Application {
    
    default SomeService someService() {
        return new SomeService();
    }
    
    default OtherService otherService(SomeService someService) {
        return new OtherService(someService);
    }
    
    static void main(String[] args) {
        KoraApplication.run(ApplicationGraph::graph);
    }
}
```

**Note:** Factory method **must not return null**.

## 3. Module Factory

Organized factory methods in `@Module` interface.

```java
import ru.tinkoff.kora.common.Module;
import javax.sql.DataSource;
import com.zaxxer.hikari.HikariConfig;
import com.zaxxer.hikari.HikariDataSource;

@Module
public interface DatabaseModule {
    
    default DataSource dataSource() {
        HikariConfig config = new HikariConfig();
        config.setJdbcUrl("jdbc:postgresql://localhost:5432/mydb");
        config.setUsername("postgres");
        config.setPassword("postgres");
        return new HikariDataSource(config);
    }
    
    default UserRepository userRepository(DataSource dataSource) {
        return new JdbcUserRepository(dataSource);
    }
    
    default OrderRepository orderRepository(DataSource dataSource) {
        return new JdbcOrderRepository(dataSource);
    }
}
```

### When to Use Module Factory

- Grouping related components
- External library integration
- Complex creation logic
- Multiple components from same source

## 4. Generic Factory

Parameterized factory for type-safe generic components.

```java
@Module
public interface RepositoryModule {
    
    // Generic factory method
    default <T> Repository<T> repository(
        Class<T> entityType, 
        DataSource dataSource
    ) {
        return new JdbcRepository<>(entityType, dataSource);
    }
    
    // Concrete usages
    default Repository<User> userRepository(DataSource dataSource) {
        return repository(User.class, dataSource);
    }
    
    default Repository<Order> orderRepository(DataSource dataSource) {
        return repository(Order.class, dataSource);
    }
    
    default Repository<Product> productRepository(DataSource dataSource) {
        return repository(Product.class, dataSource);
    }
}
```

### When to Use Generic Factory

- Creating parameterized repositories
- Same logic for multiple types
- Type-safe generic components
- Avoid code duplication

## 5. Extension Factory

Compile-time code generation for framework components.

```java
// Kora extension for JDBC repositories
@Repository
public interface UserRepository {
    
    @Query("SELECT * FROM users WHERE id = :id")
    User findById(String id);
    
    @Query("INSERT INTO users (name, email) VALUES (:name, :email)")
    void save(String name, String email);
}
```

### Built-in Extensions

| Extension | Module | Generated |
|-----------|--------|-----------|
| **JDBC Repository** | kora-database-jdbc | `*RepositoryImpl` |
| **Cassandra Repository** | kora-database-cassandra | `*RepositoryImpl` |
| **JSON Reader/Writer** | kora-json | `*JsonReader`, `*JsonWriter` |
| **HTTP Controller** | kora-http-server | `*HttpRouter` |
| **AOP Aspects** | kora-aop | `*Aspect` |

## Factory Method Patterns

### Pattern 1: Config-Based Creation

```java
@Module
public interface CacheModule {
    
    default Cache cache(Config config) {
        String type = config.getString("cache.type");
        return switch (type) {
            case "redis" -> new RedisCache(config);
            case "caffeine" -> new CaffeineCache(config);
            default -> throw new IllegalArgumentException("Unknown cache type: " + type);
        };
    }
}
```

### Pattern 2: Lifecycle Wrapper

A factory that needs lifecycle hooks returns `Wrapped<T>` and constructs a
`LifecycleWrapper<>` with init and release callbacks:

```java
import ru.tinkoff.kora.application.graph.LifecycleWrapper;
import ru.tinkoff.kora.application.graph.Wrapped;

@Module
public interface PoolModule {

    default Wrapped<ConnectionPool> connectionPool(Config config) {
        return new LifecycleWrapper<>(
            new HikariConnectionPool(config),
            pool -> pool.initialize(),    // init
            pool -> pool.close()          // release
        );
    }
}
```

### Pattern 3: Decorator Pattern

```java
@Module
public interface LoggingModule {
    
    default HttpClient httpClient() {
        HttpClient delegate = new RealHttpClient();
        return new LoggingHttpClient(delegate);
    }
}
```

### Pattern 4: Conditional Creation

```java
@Module
public interface FeatureModule {
    
    default FeatureService featureService(Config config) {
        if (config.getBoolean("feature.new.enabled")) {
            return new NewFeatureService();
        } else {
            return new LegacyFeatureService();
        }
    }
}
```

## Factory Selection Guide

| Need | Use |
|------|-----|
| Simple service | `@Component` class |
| External dependency | `@Module` factory |
| Multiple implementations | Module with `@Tag` |
| Generic type | Generic factory |
| SQL/Code generation | Extension factory |
| Lifecycle management | `LifecycleWrapper` in factory |
| Optional component | `@Nullable` return or factory |

## Common Mistakes

### Mistake 1: Null Return

```java
// BAD - Factory returns null
@Module
public interface BadModule {
    default Service service() {
        if (someCondition) {
            return null;  // Error!
        }
        return new Service();
    }
}

// GOOD - Use Optional or @Nullable
@Module
public interface GoodModule {
    @Nullable
    default Service service() {
        return someCondition ? new Service() : null;
    }
}
```

### Mistake 2: Circular Dependency

```java
// BAD - Circular dependency
@Module
public interface CircularModule {
    default ServiceA serviceA(ServiceB b) { return new ServiceA(b); }
    default ServiceB serviceB(ServiceA a) { return new ServiceB(a); }  // Circular!
}

// GOOD - Break cycle with ValueOf
@Module
public interface FixedModule {
    default ServiceA serviceA(ServiceB b) { return new ServiceA(b); }
    default ServiceB serviceB(ValueOf<ServiceA> a) { return new ServiceB(a); }
}
```

### Mistake 3: Missing Dependencies

```java
// BAD - Unresolvable dependency
@Module
public interface BadModule {
    default Service service(ExternalDep dep) {  // ExternalDep not in graph!
        return new Service(dep);
    }
}

// GOOD - Provide dependency or use @Nullable
@Module
public interface GoodModule {
    default ExternalDep externalDep() { return new ExternalDep(); }
    default Service service(ExternalDep dep) { return new Service(dep); }
}
```

## When to Read This Reference

- **Creating components** — Choose appropriate factory type
- **Generic types** — Generic factory pattern
- **Code generation** — Extension mechanism
- **Complex creation** — Lifecycle wrapper, decorators

## Related References

- [Component Registration Reference](component-registration-reference.md) — 5 registration methods
- [@DefaultComponent Reference](default-component-reference.md) — Overridable defaults
- [Lifecycle Reference](lifecycle-reference.md) — Init/release patterns
