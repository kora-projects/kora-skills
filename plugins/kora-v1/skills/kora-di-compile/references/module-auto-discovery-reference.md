# Module Auto-Discovery Reference

**Source:** `.kora-agent/kora-docs/mkdocs/docs/en/documentation/container.md`

## Contents

- [Overview](#overview)
- [Auto-Discovery Rules](#auto-discovery-rules)
- [When to Use extends](#when-to-use-extends)
- [Project Structure Examples](#project-structure-examples)
- [Auto-Discovery Mechanism](#auto-discovery-mechanism)
- [Common Mistakes](#common-mistakes)
- [Migration Patterns](#migration-patterns)

## Overview

Kora automatically discovers `@Module` interfaces in the same source directory as `@KoraApp`. Understanding when `extends` is required vs optional prevents common DI errors.

## Auto-Discovery Rules

### Same Source Set = Auto-Discovered

Modules in the same `src/main/java` (or `src/main/kotlin`) as `@KoraApp` are **automatically discovered**:

```java
// Same package or subpackage as @KoraApp
@Module
public interface DatabaseModule {
    default DataSource dataSource() { /* ... */ }
}

@KoraApp
public interface Application extends HoconConfigModule, LogbackModule {
    // DatabaseModule automatically included - NO extends needed
    static void main(String[] args) {
        KoraApplication.run(ApplicationGraph::graph);
    }
}
```

### External Libraries = Requires extends

Modules from external dependencies must be explicitly connected:

```java
@KoraApp
public interface Application extends
    HoconConfigModule,      // From kora-config-hocon
    LogbackModule,          // From kora-logging-logback
    JsonModule,             // From kora-json-module
    MetricsModule {         // From kora-metrics-micrometer
    
    static void main(String[] args) {
        KoraApplication.run(ApplicationGraph::graph);
    }
}
```

## When to Use extends

| Situation | Use extends | Example |
|-----------|-------------|---------|
| `@Module` in same src/main/java | **No** (auto-discovered) | Local DatabaseModule |
| Module from external library | **Yes** | HoconConfigModule |
| Module from another Gradle module | **Yes** (via @KoraSubmodule) | PetModule from pet-api |
| Want explicit documentation | Optional | LocalModule for clarity |

## Project Structure Examples

### Single Module Project

```
my-app/
├── build.gradle
└── src/main/java/com/example/
    ├── Application.java        // @KoraApp
    ├── DatabaseModule.java     // @Module (auto-discovered)
    └── ServiceModule.java      // @Module (auto-discovered)
```

```java
// Application.java
@KoraApp
public interface Application extends HoconConfigModule, LogbackModule {
    static void main(String[] args) {
        KoraApplication.run(ApplicationGraph::graph);
    }
}

// DatabaseModule.java - auto-discovered
@Module
public interface DatabaseModule {
    default DataSource dataSource() { /* ... */ }
}

// ServiceModule.java - auto-discovered
@Module
public interface ServiceModule {
    default UserService userService(DataSource dataSource) { /* ... */ }
}
```

### Multi-Module Gradle Project

```
my-app/
├── common/
│   └── src/main/java/com/example/common/
│       └── CommonModule.java   // @KoraSubmodule
├── pet-api/
│   └── src/main/java/com/example/pet/
│       └── PetModule.java      // @KoraSubmodule
└── app/
    └── src/main/java/com/example/
        └── Application.java    // @KoraApp
```

```java
// Application.java
@KoraApp
public interface Application extends
    CommonModule,             // From common module
    PetModule,                // From pet-api module
    HoconConfigModule,
    LogbackModule {
    
    static void main(String[] args) {
        KoraApplication.run(ApplicationGraph::graph);
    }
}
```

## Auto-Discovery Mechanism

Kora annotation processor scans:

1. **Same package** as `@KoraApp` interface
2. **All subpackages** recursively
3. **All `@Module` interfaces** found

Discovered modules are automatically added to the generated `ApplicationGraph`.

## Common Mistakes

### Mistake 1: Unnecessary extends for Local Module

```java
// BAD - Redundant
@Module
public interface LocalModule { }

@KoraApp
public interface Application extends LocalModule, HoconConfigModule { }

// GOOD - Auto-discovered
@KoraApp
public interface Application extends HoconConfigModule { }
```

### Mistake 2: Missing extends for External Module

```java
// BAD - External module not connected
@KoraApp
public interface Application {
    // HoconConfigModule NOT connected - config won't work!
}

// GOOD
@KoraApp
public interface Application extends HoconConfigModule { }
```

### Mistake 3: Module in Wrong Location

```
// BAD - Module outside source path
my-app/
├── src/main/java/com/example/
│   └── Application.java
└── modules/DatabaseModule.java  // Not discovered!

// GOOD - Module in same source tree
my-app/
└── src/main/java/com/example/
    ├── Application.java
    └── DatabaseModule.java
```

## Migration Patterns

### From Auto-Discovery to Explicit

When moving a module to separate Gradle module:

```java
// Before: Auto-discovered in same module
@Module
public interface DatabaseModule { }

@KoraApp
public interface Application extends HoconConfigModule { }

// After: Moved to database-api Gradle module
// database-api/src/main/java/com/example/database/DatabaseModule.java
@KoraSubmodule
public interface DatabaseModule { }

// app/src/main/java/com/example/Application.java
@KoraApp
public interface Application extends DatabaseModule, HoconConfigModule { }
```

### From Explicit to Auto-Discovery

When consolidating modules:

```java
// Before: Separate Gradle module
// database-api/build.gradle
@KoraSubmodule
public interface DatabaseModule { }

// After: Consolidated into main module
// src/main/java/com/example/DatabaseModule.java
@Module  // Auto-discovered, no @KoraSubmodule needed
public interface DatabaseModule { }

@KoraApp
public interface Application extends HoconConfigModule {
    // DatabaseModule automatically included
}
```

## When to Read This Reference

- **"Module not found" errors** — Verify module location and extends
- **Restructuring project** — Moving modules between Gradle subprojects
- **Understanding auto-discovery** — When extends is optional vs required
- **Debugging DI issues** — Module not being picked up by container

## Related References

- [@KoraApp Reference](kora-app-component-reference.md) — Application bootstrap
- [Component Registration Reference](component-registration-reference.md) — 5 registration methods
- [@KoraSubmodule Reference](kora-submodule-reference.md) — @KoraSubmodule patterns
