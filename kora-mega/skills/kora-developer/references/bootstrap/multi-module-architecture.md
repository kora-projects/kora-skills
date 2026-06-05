# Kora Multi-Module Architecture Guide

**Source:** [.kora-agent/kora-docs/mkdocs/docs/en/guides/dependency-injection-guide.md](.kora-agent/kora-docs/mkdocs/docs/en/guides/dependency-injection-guide.md)  
**Examples:** `.kora-agent/kora-examples/kora-java-helloworld/`

## When to Split

Split into multiple Gradle modules when: 500+ classes, clear domain boundaries, multiple teams working on different domains, different deployment units needed, or compilation time exceeds 2 minutes.

## Project Structure

### Recommended Structure

```
my-app/
├── build.gradle              # Root build configuration
├── settings.gradle           # Module includes
├── gradle.properties         # Version properties
├── common/                   # Shared types and utilities
│   ├── build.gradle
│   └── src/main/java/...
├── pet-api/                  # Pet domain module
│   ├── build.gradle
│   └── src/main/java/...
├── vet-api/                  # Vet domain module
│   ├── build.gradle
│   └── src/main/java/...
└── app/                      # Application assembly
    ├── build.gradle
    └── src/main/java/...
```

### Module Responsibilities

| Module | Purpose | Dependencies |
|--------|---------|--------------|
| `common` | Shared types, utilities, base interfaces | kora:common |
| `pet-api` | Pet domain entities, services, controllers | common, database, cache |
| `vet-api` | Vet domain entities, services, controllers | common, database, cache |
| `app` | Application assembly, main class | all domain modules |

## Root Build Configuration


```groovy
// Root build.gradle for multi-module Kora project
// See: https://github.com/kora-projects/kora-docs

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
        koraBom platform("ru.tinkoff.kora:kora-parent:1.2.15")
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

## settings.gradle

```groovy
rootProject.name = 'my-app'

// Include submodules
include ':common'
include ':pet-api'
include ':vet-api'
include ':app'

// Add more domain modules as needed:
// include ':order-api'
// include ':customer-api'
```

## gradle.properties

```properties
koraVersion=1.2.15
org.gradle.caching=true
org.gradle.configuration-cache=true
org.gradle.parallel=true
```

## Module build.gradle Examples

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

@KoraSubmodule
public interface CommonModule {
    // Base submodule interface
    // Extend to add shared dependencies
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

import ru.tinkoff.kora.cache.caffeine.CaffeineCacheModule;
import ru.tinkoff.kora.common.KoraSubmodule;
import ru.tinkoff.kora.database.jdbc.JdbcDatabaseModule;
import com.example.common.CommonModule;
import ru.tinkoff.kora.resilient.ResilientModule;

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
import ru.tinkoff.kora.common.KoraApp;
import ru.tinkoff.kora.config.hocon.HoconConfigModule;
import ru.tinkoff.kora.json.module.JsonModule;
import ru.tinkoff.kora.logging.logback.LogbackModule;
import com.example.pet.PetModule;
import com.example.vet.VetModule;

@KoraApp
public interface Application extends
    PetModule,              // Pet domain submodule
    VetModule,              // Vet domain submodule
    HoconConfigModule,
    LogbackModule,
    JsonModule {

    static void main(String[] args) {
        KoraApplication.run(ApplicationGraph::graph);
    }
}
```

**Reference:** [Dependency Injection Guide](.kora-agent/kora-docs/mkdocs/docs/en/guides/dependency-injection-guide.md)

## Benefits

1. Faster compilation — only changed modules recompile
2. Clear boundaries — domain separation enforced
3. Team autonomy — teams work independently
4. Better testing — module-level isolation
5. Code reuse — common module shared across domains
6. Deployment flexibility — deploy domains separately if needed

## Module Naming Conventions

- `common` — Shared types and utilities
- `{domain}-api` — Domain module with API and implementation
- `{domain}-service` — Alternative for service-only modules
- `app` — Main application assembly

## Tips

1. Start simple — begin with single module, split when needed
2. Common should be small — only truly shared code
3. Domain modules independent — no cross-dependencies between domain modules
4. App is thin — only assembly and main class
5. Use KoraSubmodule — for clean module boundaries
