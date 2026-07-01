---
name: kora-di-compile
description: "Compile-time dependency injection in Kora Framework. Use when creating @KoraApp applications, @Component classes, @Module interfaces, @KoraSubmodule multi-module projects, @Root startup components, @Tag disambiguation, All<T> collections, ValueOf lazy dependencies, Lifecycle management, or debugging DI container errors - no factory found, ambiguous dependency, circular dependencies. Triggers - dependency injection, DI, compile-time, container, graph, component, factory, submodule, auto-wiring, constructor injection."
---

# Kora DI Compile — Compile-Time Dependency Injection

**Version:** Kora 1.x | **Java:** 25+ | **Kotlin:** 1.9+ | **Gradle:** 9+

> **Kora uses compile-time code generation** — all dependency wiring happens at compile time via annotation processors. No reflection, no runtime proxies. Errors are caught at compile time, not runtime.

Read this skill when: bootstrapping `@KoraApp`, creating `@Component`/`@Module`, multi-module projects with `@KoraSubmodule`, debugging DI errors ("no factory found", "ambiguous dependency", circular dependencies).

---

## Quick Start

```
Task Progress:
- [ ] 1. Add Kora BOM and annotation processor to build.gradle
- [ ] 2. Create @KoraApp interface with main() entry point
- [ ] 3. Extend required modules (HoconConfigModule, LogbackModule)
- [ ] 4. Create @Component classes with constructor injection
- [ ] 5. Run ./gradlew classes to generate ApplicationGraph
```

---

## 1. Build Setup

```groovy
plugins { id "java"; id "application" }

configurations {
    koraBom
    annotationProcessor.extendsFrom(koraBom)
    implementation.extendsFrom(koraBom)
}

dependencies {
    koraBom platform("ru.tinkoff.kora:kora-parent:1.2.17")
    annotationProcessor "ru.tinkoff.kora:annotation-processors"
    implementation "ru.tinkoff.kora:config-hocon"
    implementation "ru.tinkoff.kora:logging-logback"
}

java { sourceCompatibility = JavaVersion.VERSION_25 }
application { mainClass = "com.example.Application" }
```

---

## 2. Application Bootstrap

```java
@KoraApp
public interface Application extends HoconConfigModule, LogbackModule {
    static void main(String[] args) {
        KoraApplication.run(ApplicationGraph::graph);
    }
}
```

**Key Rules:** ONE `@KoraApp` per app | `ApplicationGraph` auto-generated | External modules need `extends` | Local modules auto-discovered

**→ [@KoraApp Reference](references/kora-app-component-reference.md)** — Full bootstrap guide

---

## 3. Component Registration

### @Component (Constructor Injection)
```java
@Component
public final class UserService {
    private final UserRepository repository;
    public UserService(UserRepository repository) { this.repository = repository; }
}
```

### @Module (Factory Methods)
```java
@Module
public interface DatabaseModule {
    @DefaultComponent
    default DataSource dataSource() {
        HikariConfig config = new HikariConfig();
        config.setJdbcUrl("jdbc:postgresql://localhost:5432/mydb");
        return new HikariDataSource(config);
    }
}
```

**5 Methods:** `@Component` | `@Module` factory | `@DefaultComponent` | Auto-creation | Generic factory

**→ [Component Registration Reference](references/component-registration-reference.md)** — All methods compared

---

## 4. Module Auto-Discovery

| Situation | extends |
|-----------|---------|
| Local `@Module` (same src/main/java) | No |
| External library module | Yes |
| Gradle submodule (`@KoraSubmodule`) | Yes |

```java
@Module  // Auto-discovered, NO extends needed
public interface DatabaseModule { }

@KoraApp
public interface Application extends HoconConfigModule { }  // External only
```

**→ [Module Auto-Discovery Reference](references/module-auto-discovery-reference.md)**

---

## 5. Multi-Module Projects

```java
// common/src/main/java/com/example/common/CommonModule.java
@KoraSubmodule
public interface CommonModule extends HoconConfigModule, LogbackModule { }

// app/src/main/java/com/example/app/Application.java  
@KoraApp
public interface Application extends CommonModule, PetModule {
    static void main(String[] args) { KoraApplication.run(ApplicationGraph::graph); }
}
```

**→ [@KoraSubmodule Reference](references/kora-submodule-reference.md)** — Full multi-module guide

---

## 6. Disambiguation with @Tag

```java
// Tags
public final class RedisTag {}
public final class CaffeineTag {}

// Implementations
@Tag(RedisTag.class) @Component public final class RedisCache implements Cache {}
@Tag(CaffeineTag.class) @Component public final class CaffeineCache implements Cache {}

// Inject specific
@Component
public final class UserService {
    public UserService(@Tag(RedisTag.class) Cache cache) { }  // RedisCache
}
```

**→ [Tags & Collections Reference](references/tags-collections-reference.md)**

---

## 7. Collection & Optional Dependencies

```java
// All<T> - all implementations
@Component
public final class NotificationService {
    public NotificationService(All<Notifier> notifiers) { }
}

// @Nullable - optional
@Component
public final class SmsService {
    public SmsService(@Nullable SmsProvider provider) { }
}

// ValueOf<T> - lazy/circular
@Component
public final class ActivityRecorder {
    public ActivityRecorder(ValueOf<ActivityLog> log) { }
}
```

---

## 8. Lifecycle Management

```java
// @Root - startup
@Root @Component
public final class CacheWarmer {
    public CacheWarmer(CacheService cache) { cache.warm(); }
}

// Lifecycle - init/release
@Component
public final class DatabasePool implements Lifecycle {
    public void init() { }
    public void release() { }
}
```

**→ [Lifecycle Reference](references/lifecycle-reference.md)**

---

## 9. Common Pitfalls

| Problem | Solution |
|---------|----------|
| "No factory found" | Add `@Component` or factory |
| "Ambiguous dependency" | Use `@Tag(ClassName.class)` |
| "Multiple @KoraApp" | ONE `@KoraApp` per app |
| "Component not generated" | Class final, single constructor |
| "Circular dependency" | Use `ValueOf<T>` |
| ApplicationGraph missing | Run `./gradlew classes` |

---

## 10. Debugging

```bash
ls build/generated/sources/annotationProcessor/
./gradlew clean classes
```

---

## References

| Reference | When |
|-----------|------|
| [@KoraApp](references/kora-app-component-reference.md) | Bootstrap |
| [Component Registration](references/component-registration-reference.md) | Services |
| [Module Auto-Discovery](references/module-auto-discovery-reference.md) | extends rules |
| [@KoraSubmodule](references/kora-submodule-reference.md) | Multi-module |
| [@DefaultComponent](references/default-component-reference.md) | Overrides |
| [Component Factories](references/component-factories-reference.md) | Advanced |
| [Tags & Collections](references/tags-collections-reference.md) | @Tag, All<T> |
| [Lifecycle](references/lifecycle-reference.md) | @Root |

---

## Assets

Templates: `Application.java.template`, `Module.java.template`, `Component.java.template`, `KoraSubmodule.java.template`, `build.gradle.template`

```bash
python scripts/generate_project.py --name my-app --package com.example
```

**Why Compile-Time DI?** No reflection | Compile-time validation | Fast startup | IDE-friendly
