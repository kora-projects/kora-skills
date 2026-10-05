# @KoraApp and the Generated Graph Reference

**Applies to:** Kora 2.x (`io.koraframework`)

## Contents

- [Overview](#overview)
- [Basic Usage](#basic-usage)
- [The Generated Graph Class](#the-generated-graph-class)
- [Entry Point](#entry-point)
- [What to Connect via extends](#what-to-connect-via-extends)
- [Providers Declared on @KoraApp Itself](#providers-declared-on-koraapp-itself)
- [Common Mistakes](#common-mistakes)
- [Related References](#related-references)

## Overview

`@KoraApp` (`io.koraframework.common.annotation.KoraApp`) marks the interface that *is* the
container configuration. The processor walks its whole interface hierarchy, adds every module and
component it compiled alongside it, resolves every dependency, and writes one class that builds the
graph.

`@KoraApp` may only be placed on an **interface**. On anything else the processor reports:

```
@KoraApp can only be applied to interfaces.

Fix:
  - Change this type to an interface.
  - Move @KoraApp to an interface that declares root components and modules.
```

## Basic Usage

### Java

```java
package com.example;

import io.koraframework.application.graph.KoraApplication;
import io.koraframework.common.annotation.KoraApp;
import io.koraframework.config.hocon.HoconConfigModule;
import io.koraframework.logging.logback.LogbackModule;

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

import io.koraframework.application.graph.KoraApplication
import io.koraframework.common.annotation.KoraApp
import io.koraframework.config.hocon.HoconConfigModule
import io.koraframework.logging.logback.LogbackModule

@KoraApp
interface Application : HoconConfigModule, LogbackModule

fun main() {
    KoraApplication.run(ApplicationGraph::graph)
}
```

A top-level `fun main()` compiles to `com.example.ApplicationKt`, which is what
`application { mainClass }` must point at. `KoraApplication.run { ApplicationGraph.graph() }` is an
equivalent spelling.

## The Generated Graph Class

| Property | Value |
|---|---|
| Class name | `<KoraAppSimpleName>Graph` — `interface Application` → `ApplicationGraph` |
| Package | **the same package as the `@KoraApp` interface** |
| Factory method | `static ApplicationGraphDraw graph()` (Kotlin: a companion function) |
| Java output path | `build/generated/sources/annotationProcessor/java/main/` |
| Kotlin output path | `build/generated/ksp/main/kotlin/` |

Because the graph class is generated into *your* package, it is referenced unqualified from the
`@KoraApp` interface and must never be imported from `io.koraframework.application.graph`.

The generated class splits components into `ComponentHolder` inner classes of 500 nodes each, so a
large application still compiles — do not be surprised by `ComponentHolder0`, `ComponentHolder1`, …

**Never edit generated sources.** After a package rename or a 1.x → 2.0 migration, stale files in
`build/generated` produce errors naming types that no longer exist. Regenerate instead:

```bash
./gradlew clean classes --no-build-cache
```

## Entry Point

`io.koraframework.application.graph.KoraApplication` exposes two methods:

```java
public static void run(Supplier<ApplicationGraphDraw> supplier)                     // = run(supplier, true)
public static void run(Supplier<ApplicationGraphDraw> supplier, boolean keepAlive)
```

It builds the draw, initialises it, logs `Application initialized in <n>ms (JVM running for <s>s)`,
and registers a `kora-shutdown` JVM shutdown hook that calls `release()` and logs
`Application released in <n>ms`. Both durations are wall-clock milliseconds. If initialisation
throws, it logs `Application initializing failed with error` and exits with `-1`.

`keepAlive` decides what the calling thread does next:

- `true` (the one-argument form) — `run` blocks until the shutdown hook has finished releasing the
  graph. This is what `main` wants.
- `false` — `run` returns as soon as the graph is initialised and the hook is registered. Use it
  when something else owns the calling thread (an embedding launcher, a CLI that does its work in
  `main` after startup); release still happens in the shutdown hook on JVM exit.

There is no overload taking a config or a `String[]` — `run(ApplicationGraph::graph)` is what an
application's `main` calls.

## What to Connect via `extends`

Modules that arrive as compiled bytecode were never seen by the processor, so they must be named:

```java
@KoraApp
public interface Application extends
        HoconConfigModule,                  // io.koraframework:config-hocon
        LogbackModule,                      // io.koraframework:logging-logback
        JsonModule,                         // io.koraframework:json-common
        MetricsModule,                      // io.koraframework:micrometer-module
        ValidationModule,                   // io.koraframework:validation-module
        UndertowPublicHttpServerModule {    // io.koraframework:http-server-undertow

    static void main(String[] args) {
        KoraApplication.run(ApplicationGraph::graph);
    }
}
```

A `@Module` interface compiled in the same Gradle module is picked up without `extends`. See
[Module Auto-Discovery Reference](module-auto-discovery-reference.md).

## Providers Declared on @KoraApp Itself

The `@KoraApp` interface is also a module: its own `default` methods are providers. This is the
idiomatic place to override a `@DefaultComponent` supplied by a module you extend, because an
`@Override` on the same signature replaces it outright.

```java
@KoraApp
public interface Application extends HoconConfigModule, LogbackModule, EmailModule {

    static void main(String[] args) {
        KoraApplication.run(ApplicationGraph::graph);
    }

    @Tag(EmailModule.EmailTag.class)
    @Override
    default Supplier<String> emailNotifierHeaderSupplier() {
        return () -> "[EMAIL OVERRIDDEN] ";
    }
}
```

```kotlin
@KoraApp
interface Application : HoconConfigModule, LogbackModule, EmailModule {

    @Tag(EmailModule.EmailTag::class)
    override fun emailNotifierHeaderSupplier(): Supplier<String> = Supplier { "[EMAIL OVERRIDDEN] " }
}
```

Two details decide whether this works:

1. **`@Override` (Java) / `override` (Kotlin) is load-bearing.** The processor looks the annotation
   up, finds the overridden method in the supertypes, and *removes that declaration from the graph*.
   Without it both methods stay registered and you get `Multiple components match dependency`.
2. **Re-declare the `@Tag`.** The tag is read from the method you actually compile, so an override
   that drops it silently publishes the component untagged.

An override needs no `@Override`/`override` when the method it replaces is a `@DefaultComponent` —
precedence already resolves that case. See [@DefaultComponent Reference](default-component-reference.md).

## Common Mistakes

### `@KoraApp` on a class

```java
// BAD — processor error: "@KoraApp can only be applied to interfaces."
@KoraApp
public class Application { }

// GOOD
@KoraApp
public interface Application { }
```

### Importing the generated graph

```java
// BAD — ApplicationGraph is not part of the framework
import io.koraframework.application.graph.ApplicationGraph;

// GOOD — it is generated into your own package; no import needed
package com.example;

@KoraApp
public interface Application {
    static void main(String[] args) { KoraApplication.run(ApplicationGraph::graph); }
}
```

### Inventing a `run` overload

```java
// BAD — KoraApplication.run only accepts Supplier<ApplicationGraphDraw>
KoraApplication.run(config -> ApplicationGraph.graph(config));

// GOOD
KoraApplication.run(ApplicationGraph::graph);
```

### Kotlin `mainClass` pointing at the interface

```kotlin
// BAD — a top-level fun main() lives in <File>Kt
mainClass.set("com.example.Application")

// GOOD
mainClass.set("com.example.ApplicationKt")
```

### Missing processor

If `annotation-processors` (Java) or `symbol-processors` (KSP) is absent, nothing is generated and
the only symptom is `cannot find symbol: ApplicationGraph`. Check the processor dependency before
suspecting the graph.

## Related References

- [Component Registration Reference](component-registration-reference.md) — getting types into the graph
- [Module Auto-Discovery Reference](module-auto-discovery-reference.md) — when `extends` is required
- [@KoraSubmodule Reference](kora-submodule-reference.md) — multi-module Gradle builds
- [@DefaultComponent Reference](default-component-reference.md) — overriding module defaults
