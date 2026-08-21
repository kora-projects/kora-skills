# @DefaultComponent Reference

**Source:** `.kora-agent/kora-docs/mkdocs/docs/en/documentation/container.md`

## Contents

- [Overview](#overview)
- [Override Priority](#override-priority)
- [Basic Usage](#basic-usage)
- [Use Cases](#use-cases)
- [Common Patterns](#common-patterns)
- [When to Use @DefaultComponent](#when-to-use-defaultcomponent)
- [Common Mistakes](#common-mistakes)

## Overview

`@DefaultComponent` marks factory methods that provide **default implementations** which can be overridden by the application. This is essential for library authors providing sensible defaults while allowing customization.

## Override Priority

Kora uses this priority order when multiple components of the same type exist:

| Priority | Source | Example |
|----------|--------|---------|
| **1 (Highest)** | Explicit factory in application | `default ObjectMapper objectMapper()` |
| **2** | `@DefaultComponent` factory | `@DefaultComponent default ObjectMapper objectMapper()` |
| **3 (Lowest)** | Auto-created `@Component` | `@Component class ObjectMapper { }` |

## Basic Usage

### Library Module with Default

```java
package ru.tinkoff.kora.json.module;

import ru.tinkoff.kora.common.Module;
import ru.tinkoff.kora.common.DefaultComponent;
import com.fasterxml.jackson.databind.ObjectMapper;

@Module
public interface JsonModule {
    
    @DefaultComponent
    default ObjectMapper objectMapper() {
        ObjectMapper mapper = new ObjectMapper();
        // Default configuration
        mapper.enable(com.fasterxml.jackson.databind.SerializationFeature.INDENT_OUTPUT);
        return mapper;
    }
}
```

### Application Override

```java
package com.example;

import ru.tinkoff.kora.common.Module;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.datatype.jsr310.JavaTimeModule;

@Module
public interface CustomJsonModule {
    
    // Overrides @DefaultComponent from JsonModule
    default ObjectMapper objectMapper() {
        ObjectMapper mapper = new ObjectMapper();
        // Custom configuration
        mapper.registerModule(new JavaTimeModule());
        mapper.disable(com.fasterxml.jackson.databind.SerializationFeature.INDENT_OUTPUT);
        return mapper;
    }
}

@KoraApp
public interface Application extends JsonModule, CustomJsonModule {
    static void main(String[] args) {
        KoraApplication.run(ApplicationGraph::graph);
    }
}
```

## Use Cases

### 1. Library Default Components

Libraries provide sensible defaults:

```java
@Module
public interface DatabaseModule {
    
    @DefaultComponent
    default DataSource dataSource(Config config) {
        HikariConfig hikariConfig = new HikariConfig();
        hikariConfig.setJdbcUrl(config.getString("database.url"));
        hikariConfig.setUsername(config.getString("database.username"));
        hikariConfig.setPassword(config.getString("database.password"));
        hikariConfig.setMaximumPoolSize(10);  // Default pool size
        return new HikariDataSource(hikariConfig);
    }
}
```

Application can override for specific needs:

```java
@Module
public interface ProductionDatabaseModule {
    
    // Override with production settings
    default DataSource dataSource(Config config) {
        HikariConfig hikariConfig = new HikariConfig();
        hikariConfig.setJdbcUrl(config.getString("database.url"));
        hikariConfig.setUsername(config.getString("database.username"));
        hikariConfig.setPassword(config.getString("database.password"));
        hikariConfig.setMaximumPoolSize(50);  // Production pool size
        hikariConfig.setMinimumIdle(10);
        return new HikariDataSource(hikariConfig);
    }
}
```

### 2. Test Overrides

Override defaults for testing:

```java
// Main module
@Module
public interface HttpClientModule {
    
    @DefaultComponent
    default HttpClient httpClient() {
        return new RealHttpClient();
    }
}

// Test module
@Module
public interface TestHttpClientModule {
    
    // Override for tests
    default HttpClient httpClient() {
        return new MockHttpClient();
    }
}

// Test application
@KoraApp
public interface TestApplication extends TestHttpClientModule {
    static void main(String[] args) {
        KoraApplication.run(ApplicationGraph::graph);
    }
}
```

### 3. Environment-Specific Configuration

Different implementations per environment:

```java
// Base module
@Module
public interface CacheModule {
    
    @DefaultComponent
    default Cache cache() {
        return new CaffeineCache();  // Default: local cache
    }
}

// Production module
@Module
public interface ProductionCacheModule {
    
    // Override for production
    default Cache cache() {
        return new RedisCache();  // Production: distributed cache
    }
}
```

## Common Patterns

### Pattern 1: Conditional Default

```java
@Module
public interface ConfigModule {
    
    @DefaultComponent
    default ConfigSource configSource(Config config) {
        String env = config.getString("environment");
        return switch (env) {
            case "production" -> new ProductionConfigSource();
            case "staging" -> new StagingConfigSource();
            default -> new DefaultConfigSource();
        };
    }
}
```

### Pattern 2: Decorator Pattern

```java
@Module
public interface LoggingModule {
    
    @DefaultComponent
    default Logger logger() {
        return new LoggingDecorator(new BaseLogger());
    }
}
```

### Pattern 3: Composite Pattern

```java
@Module
public interface NotificationModule {
    
    @DefaultComponent
    default NotificationService notificationService(
        All<NotificationProvider> providers
    ) {
        return new CompositeNotificationService(providers);
    }
}
```

## When to Use @DefaultComponent

| Scenario | Use @DefaultComponent |
|----------|----------------------|
| **Library defaults** | Yes — allow app customization |
| **Test overrides** | Yes — mock implementations |
| **Environment-specific** | Yes — different per env |
| **Application-specific** | No — use regular factory |
| **Unique component** | No — no override needed |

## Common Mistakes

### Mistake 1: @DefaultComponent Without Module

```java
// BAD - @DefaultComponent on class
@DefaultComponent  // Error!
@Component
public final class DefaultLogger implements Logger { }

// GOOD - @DefaultComponent on factory method
@Module
public interface LoggerModule {
    
    @DefaultComponent
    default Logger logger() {
        return new DefaultLogger();
    }
}
```

### Mistake 2: Multiple @DefaultComponent for Same Type

```java
// BAD - Two @DefaultComponent for same type
@Module
public interface ModuleA {
    @DefaultComponent
    default Logger logger() { return new LoggerA(); }
}

@Module
public interface ModuleB {
    @DefaultComponent
    default Logger logger() { return new LoggerB(); }  // Ambiguous!
}

// GOOD - Only one @DefaultComponent
@Module
public interface ModuleA {
    @DefaultComponent
    default Logger logger() { return new LoggerA(); }
}

@Module
public interface ModuleB {
    // No @DefaultComponent - explicit override
    default Logger logger() { return new LoggerB(); }
}
```

### Mistake 3: Forgetting extends in Application

```java
// BAD - Override module not connected
@Module
public interface CustomLoggerModule {
    default Logger logger() { return new CustomLogger(); }
}

@KoraApp
public interface Application {
    // CustomLoggerModule NOT connected - override won't work!
}

// GOOD
@KoraApp
public interface Application extends CustomLoggerModule { }
```

## Comparison Table

| Annotation | Location | Override Priority | Use Case |
|------------|----------|-------------------|----------|
| **@DefaultComponent** | Factory method | Medium | Library defaults |
| *(none)* | Factory method | High | Application override |
| **@Component** | Class | Low | Auto-created components |

## When to Read This Reference

- **Creating reusable modules** — Provide overridable defaults
- **Test configuration** — Mock components for tests
- **Environment-specific components** — Different implementations per env
- **Library development** — Allow app customization

## Related References

- [Component Registration Reference](component-registration-reference.md) — 5 registration methods
- [Module Auto-Discovery Reference](module-auto-discovery-reference.md) — When extends needed
- [Component Factories Reference](component-factories-reference.md) — Advanced factory patterns
