# Component Registration Reference

**Source:** `.kora-agent/kora-docs/mkdocs/docs/en/documentation/container.md`

## Contents

- [Overview](#overview)
- [1. @Component with Constructor Injection](#1-component-with-constructor-injection)
- [2. @Module Factory Methods](#2-module-factory-methods)
- [3. @DefaultComponent for Overridable Defaults](#3-defaultcomponent-for-overridable-defaults)
- [4. Auto-Creation (No Annotation)](#4-auto-creation-no-annotation)
- [5. Generic Factory Methods](#5-generic-factory-methods)
- [Method Comparison](#method-comparison)
- [Common Mistakes](#common-mistakes)

## Overview

Kora supports 5 ways to register components in the dependency container. All components are singletons initialized at application startup.

## 1. @Component with Constructor Injection

Auto-created component with a single public constructor.

### Java

```java
package com.example.service;

import ru.tinkoff.kora.common.Component;

@Component
public final class UserService {
    private final UserRepository repository;
    
    // Single public constructor = automatic dependency injection
    public UserService(UserRepository repository) {
        this.repository = repository;
    }
    
    public User findById(String id) {
        return repository.findById(id);
    }
}
```

### Kotlin

```kotlin
package com.example.service

import ru.tinkoff.kora.common.Component

@Component
class UserService(
    private val repository: UserRepository
) {
    fun findById(id: String): User {
        return repository.findById(id)
    }
}
```

### Requirements

| Requirement | Description |
|-------------|-------------|
| **Not abstract** | Class must be concrete |
| **Single constructor** | Only one public constructor |
| **Final** | Must be `final` (unless aspects applied) |
| **Dependencies resolvable** | All constructor params must be available in graph |

## 2. @Module Factory Methods

Interface with default methods that return component instances.

```java
package com.example;

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
}
```

**Auto-discovery:** Modules in the same `src/main/java` as `@KoraApp` are auto-discovered — no `extends` needed.

## 3. @DefaultComponent for Overridable Defaults

Mark factory methods as overridable by application.

```java
@Module
public interface ObjectMapperModule {
    
    @DefaultComponent
    default ObjectMapper objectMapper() {
        return new ObjectMapper();
    }
}

// Application can override
@Module
public interface CustomObjectMapperModule {
    
    // Overrides @DefaultComponent method
    default ObjectMapper objectMapper() {
        ObjectMapper mapper = new ObjectMapper();
        mapper.registerModule(new JavaTimeModule());
        return mapper;
    }
}
```

**Override Priority:**
1. Explicit factory method in application (no `@DefaultComponent`)
2. `@DefaultComponent` factory method
3. Auto-created `@Component` class

## 4. Auto-Creation (No Annotation)

Classes with single public constructor are auto-created when needed.

```java
// No @Component annotation needed
public final class HelperService {
    private final Logger logger;
    
    public HelperService(Logger logger) {
        this.logger = logger;
    }
}

// Used in factory - will be auto-created
@Module
public interface ServiceModule {
    default MainService mainService(HelperService helper) {
        return new MainService(helper);
    }
}
```

### Requirements

| Requirement | Description |
|-------------|-------------|
| Not abstract | Class must be concrete |
| Single constructor | Only one public constructor |
| Final | Must be `final` (unless aspects applied) |

## 5. Generic Factory Methods

Generic methods for parameterized component creation.

```java
@Module
public interface RepositoryModule {
    
    // Generic factory
    default <T> Repository<T> repository(
        Class<T> entityType, 
        DataSource dataSource
    ) {
        return new JdbcRepository<>(entityType, dataSource);
    }
    
    // Concrete usage
    default Repository<User> userRepository(DataSource dataSource) {
        return repository(User.class, dataSource);
    }
    
    default Repository<Order> orderRepository(DataSource dataSource) {
        return repository(Order.class, dataSource);
    }
}
```

## Method Comparison

| Method | Use Case | Pros | Cons |
|--------|----------|------|------|
| **@Component** | Standard services | Clean, minimal boilerplate | Requires final class |
| **@Module factory** | External deps, complex creation | Full control over creation | More verbose |
| **@DefaultComponent** | Library defaults | Overridable by app | Only in modules |
| **Auto-creation** | Simple helpers | No annotation needed | Implicit behavior |
| **Generic factory** | Parameterized types | Type-safe generics | More complex |

## When to Use Each

### Use @Component When:
- Creating application services
- You have a single public constructor
- Class doesn't need to be extended

### Use @Module When:
- Integrating external libraries
- Complex creation logic needed
- Multiple components from same source

### Use @DefaultComponent When:
- Providing library defaults
- Allowing application customization
- Building reusable modules

### Use Auto-Creation When:
- Simple utility classes
- Constructor has all dependencies
- No special lifecycle needed

### Use Generic Factory When:
- Creating parameterized repositories
- Same logic for multiple types
- Type-safe generic components

## Common Mistakes

### Mistake 1: Multiple Constructors

```java
// BAD - Multiple constructors
@Component
public final class UserService {
    public UserService() { }
    public UserService(Logger logger) { }  // Error!
}

// GOOD - Single constructor
@Component
public final class UserService {
    public UserService(Logger logger) { }
}
```

### Mistake 2: Non-Final Class

```java
// BAD - Missing final
@Component
public class UserService { }  // Error!

// GOOD
@Component
public final class UserService { }
```

### Mistake 3: Abstract Class

```java
// BAD - Abstract class
@Component
public abstract class BaseService { }  // Error!

// GOOD - Concrete class
@Component
public final class UserService extends BaseService { }
```

## When to Read This Reference

- **Creating new services** — Choose between `@Component` and `@Module`
- **"No factory found" error** — Verify registration method
- **Overriding library components** — Use `@DefaultComponent`
- **Generic types** — Generic factory pattern

## Related References

- [@KoraApp Reference](kora-app-component-reference.md) — Application bootstrap
- [Module Auto-Discovery Reference](module-auto-discovery-reference.md) — When extends needed
- [Component Factories Reference](component-factories-reference.md) — Advanced factory patterns
