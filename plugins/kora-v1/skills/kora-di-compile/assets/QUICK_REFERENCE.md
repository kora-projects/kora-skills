# Kora DI Compile Quick Reference Card

## Annotations Cheat Sheet

| Annotation | Purpose | Example |
|------------|---------|---------|
| `@KoraApp` | Main application entry point | `@KoraApp interface Application` |
| `@Component` | Auto-created singleton | `@Component class Service` |
| `@Module` | Factory methods interface | `@Module interface DbModule` |
| `@KoraSubmodule` | Multi-module support | `@KoraSubmodule interface Common` |
| `@Root` | Startup initialization | `@Root class CacheWarmer` |
| `@Tag(Class)` | Disambiguate implementations | `@Tag(RedisTag.class) Cache` |
| `@DefaultComponent` | Overridable default | `@DefaultComponent ObjectMapper` |
| `@Nullable` | Optional dependency | `@Nullable SmsProvider` |

## Dependency Wrappers

| Wrapper | Use Case | Access |
|---------|----------|--------|
| `ValueOf<T>` | Lazy, cascading prevention | `value.get()` |
| `All<T>` | All implementations | Iterable |
| `Optional<T>` | Optional dependency | `optional.isPresent()` |
| `@Tag(Tag.Any.class) All<T>` | All including tagged | Iterable |

## Common Patterns

### Component with Constructor Injection
```java
@Component
public final class UserService {
    private final UserRepository repo;
    public UserService(UserRepository repo) { this.repo = repo; }
}
```

### Module with Factory
```java
@Module
public interface DatabaseModule {
    @DefaultComponent
    default DataSource dataSource() { return new HikariDataSource(); }
}
```

### Tagged Implementations
```java
@Tag(RedisTag.class)
@Component
public final class RedisCache implements Cache {}

public UserService(@Tag(RedisTag.class) Cache cache) {}
```

### Lifecycle Component
```java
@Component
public final class Pool implements Lifecycle {
    public void init() { /* startup */ }
    public void release() { /* shutdown */ }
}
```

## Build Setup (Java)

```groovy
configurations {
    koraBom
    annotationProcessor.extendsFrom(koraBom)
    implementation.extendsFrom(koraBom)
}

dependencies {
    koraBom platform("ru.tinkoff.kora:kora-parent:1.2.17")
    annotationProcessor "ru.tinkoff.kora:annotation-processors"
}

java {
    sourceCompatibility = JavaVersion.VERSION_25
}
```

## Error Solutions

| Error | Solution |
|-------|----------|
| No factory found | Add `@Component` or factory method |
| Ambiguous dependency | Use `@Tag(ClassName.class)` |
| Multiple @KoraApp | Keep only one `@KoraApp` interface |
| Component not generated | Ensure class is `final` with single constructor |
| ApplicationGraph missing | Run `./gradlew classes` |

## Generated Code Location

```
build/generated/sources/annotationProcessor/
└── java/main/
    └── com/example/
        └── ApplicationGraph.java
```

## Commands

```bash
# Build project
./gradlew clean build

# Trigger annotation processing
./gradlew classes

# Validate build
python scripts/validate_gradle.py build.gradle

# Generate new project
python scripts/generate_project.py --name my-app --package com.example
```
