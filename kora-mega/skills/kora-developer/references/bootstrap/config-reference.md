# Kora Config — Configuration Reference

**Source:** [.kora-agent/kora-docs/mkdocs/docs/en/documentation/config.md](.kora-agent/kora-docs/mkdocs/docs/en/documentation/config.md)  
**Examples:** `.kora-agent/kora-examples/kora-java-config-hocon/`, `.kora-agent/kora-examples/kora-java-config-yaml/`

## Overview

Kora Config module provides configuration mapping from files (HOCON/YAML) to typed interfaces with environment variable substitution and hot reload support.

**Key Features:**
- Type-safe configuration interfaces
- Environment variable substitution
- Hot reload via config watcher
- Support for HOCON and YAML formats
- Custom configuration extractors

---

## HOCON Configuration

### Format

HOCON (Human-Optimized Configurable Object Notation) is a JSON-based format with more flexible syntax:

```hocon
services {
    foo {
        bar = "SomeValue"                    # String value
        baz = 10                             # Numeric value
        propRequired = ${REQUIRED_ENV}       # Required env variable
        propOptional = ${?OPTIONAL_ENV}      # Optional env variable
        propDefault = ${?NON_DEFAULT:-10}    # With default value
        propReference = ${services.foo.bar}  # Reference to other config
        propArray = ["v1", "v2"]             # Array
        propArrayAsString = "v1, v2"         # Comma-separated string
        propMap = {                          # Map/dictionary
            "k1" = "v1"
            "k2" = "v2"
        }
        propObject = {                       # Nested object
            p1 = "v1"
            p2 = "v2"
        }
        propObjects = [                      # List of objects
            { p1 = "v1", p2 = "v2" },
            { p1 = "v3", p2 = "v4" }
        ]
    }
}
```

### @ConfigSource Interface

```java
@ConfigSource("services.foo")
public interface FooConfig {
    String bar();
    Integer baz();
    String propRequired();

    @Nullable
    String propOptional();

    Integer propDefault();
    String propReference();

    List<String> propArray();
    List<String> propArrayAsString();
    Map<String, String> propMap();

    @ConfigValueExtractor
    interface ObjectConfig {
        String p1();
        String p2();
    }

    ObjectConfig propObject();
    List<ObjectConfig> propObjects();
}
```

### HOCON Module

```java
// build.gradle
implementation "ru.tinkoff.kora:config-hocon"

// Application
@KoraApp
public interface Application extends HoconConfigModule {
    static void main(String[] args) {
        KoraApplication.run(ApplicationGraph::graph);
    }
}
```

---

## YAML Configuration

### Format

```yaml
services:
    foo:
        bar: "SomeValue"                    # String value
        baz: 10                             # Numeric value
        propRequired: ${REQUIRED_ENV}       # Required env variable
        propOptional: ${?OPTIONAL_ENV}      # Optional env variable
        propDefault: ${?NON_DEFAULT:-10}    # With default value
        propReference: ${services.foo.bar}  # Reference to other config
        propArray: ["v1", "v2"]             # Array
        propArrayAsString: "v1, v2"         # Comma-separated string
        propMap:                            # Map/dictionary
            k1: "v1"
            k2: "v2"
        propObject:                         # Nested object
            p1: "v1"
            p2: "v2"
        propObjects:                        # List of objects
            - p1: "v1"
              p2: "v2"
            - p1: "v3"
              p2: "v4"
```

### YAML Module

```java
// build.gradle
implementation "ru.tinkoff.kora:config-yaml"

// Application
@KoraApp
public interface Application extends YamlConfigModule {
    static void main(String[] args) {
        KoraApplication.run(ApplicationGraph::graph);
    }
}
```

---

## Configuration Files

### File Loading Order

Kora loads configuration files in this order:

1. **reference.conf / reference.yaml** — Library defaults (merged from all JARs)
2. **application.conf / application.yaml** — Application-specific overrides

### File Resolution Priority

1. `config.resource` system property (file from resources)
2. `config.file` system property (file from filesystem)
3. `application.conf` / `application.yaml` from resources
4. Empty configuration if none found

### Example Structure

```
src/main/resources/
├── reference.conf          # Library defaults
└── application.conf        # Application config
```

```hocon
# reference.conf (library defaults)
database {
    url = "jdbc:postgresql://localhost:5432/db"
    username = "default"
    password = "default"
    pool-size = 10
}

# application.conf (application overrides)
database {
    username = ${DB_USERNAME}
    password = ${DB_PASSWORD}
    pool-size = 20
}
```

---

## Custom Configuration

### Application Config (@ConfigSource)

For application-specific configuration:

```java
@ConfigSource("app.database")
public interface DatabaseConfig {
    String url();
    String username();
    String password();
    int poolSize();
}
```

```hocon
# application.conf
app {
    database {
        url = "jdbc:postgresql://localhost:5432/mydb"
        username = ${DB_USERNAME}
        password = ${DB_PASSWORD}
        pool-size = 20
    }
}
```

**Usage in components:**

```java
@Component
public final class DatabasePool {
    private final DatabaseConfig config;
    
    public DatabasePool(DatabaseConfig config) {
        this.config = config;
    }
}
```

### Library Config (@ConfigValueExtractor)

For library-provided configuration:

```java
// Library config interface
@ConfigValueExtractor
public interface CacheConfig {
    int maxSize();
    Duration expireAfterWrite();
}

// Library module
public interface CacheModule {
    default CacheConfig config(Config config, ConfigValueExtractor<CacheConfig> extractor) {
        return extractor.extract(config.get("library.cache"));
    }

    default Cache cache(CacheConfig config) {
        return new CaffeineCache(config.maxSize(), config.expireAfterWrite());
    }
}
```

```hocon
# application.conf
library {
    cache {
        maxSize = 10000
        expireAfterWrite = 1h
    }
}
```

---

## Required vs Optional Values

### Required Values (Default)

All config methods are **required** by default:

```java
@ConfigSource("app.foo")
public interface FooConfig {
    String requiredValue();  // Must be present in config
}
```

### Optional Values

**Java:** Use `@Nullable` annotation

```java
@ConfigSource("app.foo")
public interface FooConfig {
    @Nullable
    String optionalValue();  // Can be null if not present
}
```

**Kotlin:** Use nullable return type

```kotlin
@ConfigSource("app.foo")
interface FooConfig {
    fun optionalValue(): String?  // Can be null if not present
}
```

### Default Values

**Java:** Use `default` methods

```java
@ConfigSource("app.foo")
public interface FooConfig {
    default int poolSize() {
        return 10;  // Default value
    }
}
```

**Kotlin:** Use default method implementation

```kotlin
@ConfigSource("app.foo")
interface FooConfig {
    fun poolSize(): Int = 10  // Default value
}
```

---

## Injecting Configuration

### Custom Config Interface (Recommended)

```java
@Component
public final class DatabasePool {
    private final DatabaseConfig config;
    
    public DatabasePool(DatabaseConfig config) {
        this.config = config;
    }
}
```

### Raw Config Injection

**Full configuration (file + env + system properties):**

```java
@Component
public final class ConfigReader {
    private final Config config;

    public ConfigReader(Config config) {
        this.config = config;
    }
}
```

**Environment variables only:**

```java
@Component
public final class EnvReader {
    private final Config config;
    
    public EnvReader(@Environment Config config) {
        this.config = config;
    }
}
```

**System properties only:**

```java
@Component
public final class SystemPropReader {
    private final Config config;

    public SystemPropReader(@SystemProperties Config config) {
        this.config = config;
    }
}
```

**Application config file only:**

```java
@Component
public final class FileConfigReader {
    private final Config config;
    
    public FileConfigReader(@ApplicationConfig Config config) {
        this.config = config;
    }
}
```

### Best Practice

> **Recommendation:** Always use custom `@ConfigSource` interfaces instead of injecting raw `Config`. This prevents cascading refreshes when configuration changes.

```java
// BAD — causes cascading refreshes
@Component
public final class BadService {
    public BadService(Config config) {
        // Direct config usage
    }
}

// GOOD — isolated refresh
@ConfigSource("app.foo")
public interface FooConfig {
    String value();
}

@Component
public final class GoodService {
    public GoodService(FooConfig config) {
        // Only this component refreshes on config change
    }
}
```

---

## Config Watcher (Hot Reload)

Kora includes a configuration file watcher that detects changes and refreshes affected components:

**Disable watcher:**

1. Environment variable: `KORA_CONFIG_WATCHER_ENABLED=false`
2. System property: `kora.config.watcher.enabled=false`

---

## Supported Types

Config extractors support these types:

| Type | Example |
|------|---------|
| **Primitives** | `boolean`, `int`, `long`, `double`, `float` |
| **Wrapper types** | `Boolean`, `Integer`, `Long`, `Double`, `Float` |
| **Numeric** | `BigInteger`, `BigDecimal` |
| **Time** | `Duration`, `Period`, `LocalDate`, `LocalTime`, `LocalDateTime` |
| **String** | `String`, `Pattern`, `UUID` |
| **Collections** | `List<T>`, `Set<T>`, `Map<K, V>` |
| **Special** | `Size` (e.g., `1Mb`, `1024b`), `Properties`, `Either<A, B>` |
| **Enums** | Any enum type |

### Size Type

Special human-readable byte size format:

```hocon
cache {
    maxSize = 1Mb      # 1,000,000 bytes (decimal)
    maxSize = 1Mib     # 1,048,576 bytes (binary)
    maxSize = 1024b    # 1024 bytes
    maxSize = 1024     # 1024 bytes (no suffix = bytes)
}
```

---

## Environment Variable Substitution

### Syntax

| Syntax | Meaning |
|--------|---------|
| `${ENV_VAR}` | Required environment variable |
| `${?ENV_VAR}` | Optional environment variable (omitted if not set) |
| `${?ENV_VAR:-default}` | Optional with default value |

### Example

```hocon
app {
    # Required — fails if not set
    apiKey = ${API_KEY}

    # Optional — omitted if not set
    debug = ${?DEBUG_MODE}

    # Optional with default
    port = ${?PORT:-8080}

    # Nested reference
    connectionString = "jdbc:postgresql://${DB_HOST}:${DB_PORT}/${DB_NAME}"
}
```

---

## Common Mistakes

### Direct Config Usage

```java
// BAD
default DataSource dataSource(Config config) {
    return new DriverManagerDataSource(
        config.getString("database.url"),
        config.getString("database.username")
    );
}

// GOOD
@ConfigSource("database")
public interface DatabaseConfig {
    String url();
    String username();
}

default DataSource dataSource(DatabaseConfig config) {
    return new DriverManagerDataSource(
        config.url(),
        config.username()
    );
}
```

### Missing Environment Variables

```hocon
# BAD — fails if DB_PASSWORD not set
database {
    password = ${DB_PASSWORD}
}

# GOOD — optional with default
database {
    password = ${?DB_PASSWORD:-default_password}
}
```

### Wrong Config Path

```java
// BAD — mismatch between path and interface
@ConfigSource("app.foo")
public interface BarConfig { ... }

// GOOD — path matches interface name
@ConfigSource("app.bar")
public interface BarConfig { ... }
```

---

## Quick Reference

### HOCON Module
```java
implementation "ru.tinkoff.kora:config-hocon"
@KoraApp
public interface Application extends HoconConfigModule {}
```

### YAML Module
```java
implementation "ru.tinkoff.kora:config-yaml"
@KoraApp
public interface Application extends YamlConfigModule {}
```

### Config Interface
```java
@ConfigSource("app.name")
public interface AppConfig {
    String value();
    @Nullable
    String optional();
    default int defaultVal() { return 42; }
}
```

### Environment Variables
```hocon
required = ${ENV_VAR}
optional = ${?ENV_VAR}
default = ${?ENV_VAR:-default}
```
