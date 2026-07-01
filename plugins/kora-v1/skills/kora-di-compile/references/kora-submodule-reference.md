# @KoraSubmodule Reference

**Source:** `.kora-agent/kora-docs/mkdocs/docs/en/documentation/container.md`
**Examples:** `.kora-agent/kora-examples/guides/java/kora-java-guide-dependency-injection/`

## Contents

- [Overview](#overview)
- [When to Split](#when-to-split)
- [Project Structure](#project-structure)
- [Root Build Configuration](#root-build-configuration)
- [Module Configuration Examples](#module-configuration-examples)
- [Module Inheritance Chain](#module-inheritance-chain)
- [Key Rules](#key-rules)
- [Common Mistakes](#common-mistakes)

## Overview

`@KoraSubmodule` marks an interface for which Kora builds a module from all `@Module` and `@Component` types in that Gradle compilation module. It is used for **physical separation** of code into separate Gradle subprojects, where the `@KoraApp` assembly lives in its own module apart from the business logic. Each submodule has its own `build.gradle` and can be developed and tested independently.

## When to Split

Split into multiple Gradle modules when:

| Criteria | Threshold |
|----------|-----------|
| **Code size** | 500+ classes |
| **Domain boundaries** | Clear separation (pet-api, vet-api) |
| **Team structure** | Multiple teams working on different domains |
| **Compilation time** | Exceeds 2 minutes |
| **Deployment** | Different deployment units needed |

## Project Structure

### Recommended Layout

```
my-app/
├── build.gradle              # Root build configuration
├── settings.gradle           # Module includes
├── gradle.properties         # Version properties
├── common/                   # Shared types and utilities
│   ├── build.gradle
│   └── src/main/java/com/example/common/
│       └── CommonModule.java
├── pet-api/                  # Pet domain module
│   ├── build.gradle
│   └── src/main/java/com/example/pet/
│       └── PetModule.java
├── vet-api/                  # Vet domain module
│   ├── build.gradle
│   └── src/main/java/com/example/vet/
│       └── VetModule.java
└── app/                      # Application assembly
    ├── build.gradle
    └── src/main/java/com/example/app/
        └── Application.java
```

### Module Responsibilities

| Module | Purpose | Dependencies |
|--------|---------|--------------|
| `common` | Shared types, utilities, base interfaces | kora:common |
| `pet-api` | Pet domain entities, services, controllers | common, database, cache |
| `vet-api` | Vet domain entities, services, controllers | common, database, cache |
| `app` | Application assembly, main class | all domain modules |

## Root Build Configuration

### build.gradle (Root)

```groovy
// Root build.gradle for multi-module Kora project

subprojects {
    apply plugin: "java"
    
    configurations {
        koraBom
        annotationProcessor.extendsFrom(koraBom)
        compileOnly.extendsFrom(koraBom)
        implementation.extendsFrom(koraBom)
        api.extendsFrom(koraBom)
    }
    
    dependencies {
        koraBom platform("ru.tinkoff.kora:kora-parent:1.2.17")
        annotationProcessor "ru.tinkoff.kora:annotation-processors"
    }
    
    java {
        sourceCompatibility = JavaVersion.VERSION_25
        targetCompatibility = JavaVersion.VERSION_25
    }
    
    compileJava {
        options.encoding("UTF-8")
        options.incremental(true)
        options.fork = false
    }
}
```

### settings.gradle

```groovy
rootProject.name = 'my-app'

// Include submodules
include ':common'
include ':pet-api'
include ':vet-api'
include ':app'
```

### gradle.properties

```properties
koraVersion=1.2.17
org.gradle.caching=true
org.gradle.configuration-cache=true
org.gradle.parallel=true
```

## Module Configuration Examples

### common/build.gradle

```groovy
plugins {
    id "java-library"
}

dependencies {
    koraBom platform("ru.tinkoff.kora:kora-parent:$koraVersion")
    annotationProcessor "ru.tinkoff.kora:annotation-processors"
    
    implementation "ru.tinkoff.kora:common"
}
```

### CommonModule.java

```java
package com.example.common;

import ru.tinkoff.kora.common.KoraSubmodule;
import ru.tinkoff.kora.config.hocon.HoconConfigModule;
import ru.tinkoff.kora.logging.logback.LogbackModule;

@KoraSubmodule
public interface CommonModule extends HoconConfigModule, LogbackModule {
    // Base submodule interface
    // Shared dependencies for all domain modules
}
```

### pet-api/build.gradle

```groovy
plugins {
    id "java"
}

dependencies {
    implementation project(":common")
    
    koraBom platform("ru.tinkoff.kora:kora-parent:$koraVersion")
    annotationProcessor "ru.tinkoff.kora:annotation-processors"
    
    implementation "ru.tinkoff.kora:database-jdbc"
    implementation "ru.tinkoff.kora:cache-caffeine"
    implementation "ru.tinkoff.kora:resilient-kora"
}
```

### PetModule.java

```java
package com.example.pet;

import ru.tinkoff.kora.common.KoraSubmodule;
import com.example.common.CommonModule;
// External modules: JdbcDatabaseModule (ru.tinkoff.kora:database-jdbc),
// CaffeineCacheModule (ru.tinkoff.kora:cache-caffeine),
// ResilientModule (ru.tinkoff.kora:resilient-kora)

@KoraSubmodule
public interface PetModule extends
    CommonModule,
    JdbcDatabaseModule,
    CaffeineCacheModule,
    ResilientModule {
    // Pet domain specific dependencies
}
```

### app/build.gradle

```groovy
plugins {
    id "java"
    id "application"
}

dependencies {
    implementation project(":common")
    implementation project(":pet-api")
    implementation project(":vet-api")
    
    koraBom platform("ru.tinkoff.kora:kora-parent:$koraVersion")
    annotationProcessor "ru.tinkoff.kora:annotation-processors"
    
    implementation "ru.tinkoff.kora:config-hocon"
    implementation "ru.tinkoff.kora:logging-logback"
    implementation "ru.tinkoff.kora:json-module"
}

application {
    applicationName = "application"
    mainClass = "com.example.app.Application"
    applicationDefaultJvmArgs = ["-Dfile.encoding=UTF-8"]
}
```

### Application.java

```java
package com.example.app;

import ru.tinkoff.kora.application.graph.KoraApplication;
import ru.tinkoff.kora.application.graph.ApplicationGraph;
import ru.tinkoff.kora.common.KoraApp;
import ru.tinkoff.kora.json.module.JsonModule;
import com.example.common.CommonModule;
import com.example.pet.PetModule;
import com.example.vet.VetModule;

@KoraApp
public interface Application extends
    CommonModule,             // Common submodule
    PetModule,                // Pet domain submodule
    VetModule,                // Vet domain submodule
    JsonModule {              // External library module

    static void main(String[] args) {
        KoraApplication.run(ApplicationGraph::graph);
    }
}
```

## Module Inheritance Chain

```
Application (@KoraApp)
    ├── PetModule (@KoraSubmodule)
    │   ├── CommonModule (@KoraSubmodule)
    │   │   ├── HoconConfigModule (external)
    │   │   └── LogbackModule (external)
    │   ├── JdbcDatabaseModule (external)
    │   ├── CaffeineCacheModule (external)
    │   └── ResilientModule (external)
    ├── VetModule (@KoraSubmodule)
    │   └── CommonModule (shared)
    └── JsonModule (external)
```

## Key Rules

| Rule | Description |
|------|-------------|
| **One submodule per Gradle module** | Each `@KoraSubmodule` = one `build.gradle` |
| **Submodules require extends** | Parent `@KoraApp` must extend submodules |
| **Common should be small** | Only truly shared code in common module |
| **No cross-dependencies** | Domain modules (pet-api, vet-api) should not depend on each other |
| **App is thin** | Application module only for assembly |

## Benefits

| Benefit | Description |
|---------|-------------|
| **Faster compilation** | Only changed modules recompile |
| **Clear boundaries** | Domain separation enforced by build |
| **Team autonomy** | Teams work independently on modules |
| **Better testing** | Module-level isolation |
| **Code reuse** | Common module shared across domains |
| **Deployment flexibility** | Deploy domains separately if needed |

## Module Naming Conventions

| Pattern | Purpose |
|---------|---------|
| `common` | Shared types and utilities |
| `{domain}-api` | Domain module with API and implementation |
| `{domain}-service` | Alternative for service-only modules |
| `app` | Main application assembly |
| `{domain}-client` | External client integrations |
| `{domain}-repository` | Data access layer |

## Common Mistakes

### Mistake 1: Circular Dependencies

```groovy
// BAD - pet-api depends on vet-api
// pet-api/build.gradle
dependencies {
    implementation project(":vet-api")  // Error!
}

// vet-api/build.gradle  
dependencies {
    implementation project(":pet-api")  // Circular!
}

// GOOD - Both depend only on common
// pet-api/build.gradle
dependencies {
    implementation project(":common")
}

// vet-api/build.gradle
dependencies {
    implementation project(":common")
}
```

### Mistake 2: Missing @KoraSubmodule

```java
// BAD - Module interface without annotation
// pet-api/src/main/java/com/example/pet/PetModule.java
public interface PetModule { }  // Won't be discovered!

// GOOD
@KoraSubmodule
public interface PetModule { }
```

### Mistake 3: App Module with Business Logic

```java
// BAD - Business logic in app module
@KoraApp
public interface Application extends PetModule {
    
    @Component
    class PetController {  // Wrong location!
        // Business logic here
    }
}

// GOOD - Business logic in domain module
// pet-api/src/main/java/com/example/pet/PetController.java
@Component
public final class PetController {
    // Business logic here
}
```

## When to Read This Reference

- **Project growing large** — Consider splitting into modules
- **Team scaling** — Multiple teams need clear boundaries
- **Build times slow** — Incremental compilation needed
- **Code reuse needed** — Common module for shared types

## Related References

- [@KoraApp Reference](kora-app-component-reference.md) — Application bootstrap
- [Module Auto-Discovery Reference](module-auto-discovery-reference.md) — When extends needed
- [Component Registration Reference](component-registration-reference.md) — 5 registration methods
