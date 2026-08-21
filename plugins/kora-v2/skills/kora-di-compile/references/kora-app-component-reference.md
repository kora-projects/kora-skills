# @KoraApp and ApplicationGraph Reference

**Source:** `.kora-agent/kora-docs/mkdocs/docs/en/documentation/container.md`
**Examples:** `.kora-agent/kora-examples/examples/java/kora-java-helloworld/`

## Contents

- [Overview](#overview)
- [Basic Usage](#basic-usage)
- [Key Rules](#key-rules)
- [What to Connect via extends](#what-to-connect-via-extends)
- [Application Entry Point](#application-entry-point)
- [Common Mistakes](#common-mistakes)

## Overview

`@KoraApp` marks the main dependency injection container interface. Kora generates `ApplicationGraph` class at compile time that contains the complete dependency graph implementation.

## Basic Usage

### Java

```java
package com.example;

import ru.tinkoff.kora.application.graph.KoraApplication;
import ru.tinkoff.kora.application.graph.ApplicationGraph;
import ru.tinkoff.kora.common.KoraApp;
import ru.tinkoff.kora.config.hocon.HoconConfigModule;
import ru.tinkoff.kora.logging.logback.LogbackModule;

@KoraApp
public interface Application extends HoconConfigModule, LogbackModule {
    static void main(String[] args) {
        KoraApplication.run(ApplicationGraph::graph);
    }
}
```

### Kotlin

```kotlin
package com.example

import ru.tinkoff.kora.application.graph.KoraApplication
import ru.tinkoff.kora.application.graph.ApplicationGraph
import ru.tinkoff.kora.common.KoraApp
import ru.tinkoff.kora.config.hocon.HoconConfigModule
import ru.tinkoff.kora.logging.logback.LogbackModule

@KoraApp
interface Application : HoconConfigModule, LogbackModule {
    companion object {
        @JvmStatic
        fun main(args: Array<String>) {
            KoraApplication.run(ApplicationGraph::graph)
        }
    }
}
```

## Key Rules

| Rule | Description |
|------|-------------|
| **Single @KoraApp** | Only ONE interface per application can have `@KoraApp` |
| **ApplicationGraph location** | Generated in the same package as `@KoraApp` interface |
| **Generation trigger** | Run `./gradlew classes` to invoke annotation processor |
| **Generated code path** | `build/generated/sources/annotationProcessor/` |

## What to Connect via `extends`

### External Modules (Required)

Modules from external libraries must be explicitly connected:

```java
@KoraApp
public interface Application extends
    HoconConfigModule,      // kora-config-hocon
    LogbackModule,          // kora-logging-logback
    JsonModule,             // kora-json-module
    MetricsModule,          // kora-metrics-micrometer
    TracingModule {         // kora-tracing-opentelemetry
    
    static void main(String[] args) {
        KoraApplication.run(ApplicationGraph::graph);
    }
}
```

### Local Modules (Optional - Auto-Discovered)

Modules in the same `src/main/java` are auto-discovered:

```java
// Auto-discovered - extends NOT required
@Module
public interface DatabaseModule {
    default DataSource dataSource() { /* ... */ }
}

@KoraApp
public interface Application extends HoconConfigModule, LogbackModule {
    // DatabaseModule automatically included
}
```

## Application Entry Point

The entry point calls `KoraApplication.run()` with a supplier for the generated graph:

```java
// Standard pattern
KoraApplication.run(ApplicationGraph::graph);

// With config override
KoraApplication.run(config -> ApplicationGraph.graph(config));
```

## Common Mistakes

### Mistake 1: Multiple @KoraApp Interfaces

```java
// BAD - Only one @KoraApp allowed
@KoraApp
public interface Application { }

@KoraApp  
public interface SecondApp { }  // Error!
```

### Mistake 2: Wrong main() Signature

```java
// BAD - Missing ApplicationGraph
@KoraApp
public interface Application {
    static void main(String[] args) {
        new Application().run();  // Error!
    }
}

// GOOD
@KoraApp
public interface Application {
    static void main(String[] args) {
        KoraApplication.run(ApplicationGraph::graph);
    }
}
```

### Mistake 3: Connecting Local Modules

```java
// BAD - Redundant extends for local module
@Module
public interface LocalModule { }

@KoraApp
public interface Application extends LocalModule { }  // Unnecessary

// GOOD - Auto-discovered
@KoraApp
public interface Application { }
```

## When to Read This Reference

- **Bootstrap new project** — Setting up `@KoraApp` for the first time
- **Debug "ApplicationGraph not found"** — Verify annotation processor ran
- **Multi-module setup** — Connecting external modules and submodules
- **Multiple @KoraApp errors** — Ensure single entry point

## Related References

- [Component Registration Reference](component-registration-reference.md) — `@Component`, `@Module` patterns
- [Module Auto-Discovery Reference](module-auto-discovery-reference.md) — When extends is needed
- [@KoraSubmodule Reference](kora-submodule-reference.md) — `@KoraSubmodule` for Gradle modules
