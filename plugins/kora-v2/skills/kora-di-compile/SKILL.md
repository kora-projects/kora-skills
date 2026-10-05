---
name: kora-di-compile
description: "Compile-time DI in Kora 2.0 — @KoraApp, @Component, @Module, @KoraSubmodule, @FactoryModule, @Conditional, @DefaultComponent, @Root, @Tag from io.koraframework.common.annotation. Generates <App>Graph; entry point KoraApplication.run(ApplicationGraph::graph). Use when wiring the application graph, splitting a build into Gradle submodules, or fixing \"No component found for dependency\" / \"Multiple components match dependency\" / \"Circular dependency found\". For graph runtime behaviour see kora-di-runtime."
license: Apache-2.0
metadata:
  kora-version: "2.x"
---

# Kora DI Compile — Compile-Time Dependency Injection

> **Kora sub-skill — obey the [kora-v2 meta rules](../../SKILL.md) on every task:** **R0** ground the workspace on Kora 2.0 refs before starting (framework source at tag `2.0.0.RC2` + `kora-examples` at `migration/2.0` + Kora 2.0 docs at koraframework.io/v2, which trail the source; 1.x `kora-docs` pages are never an authority) · **R1** read this sub-skill before writing code · **R2** Kora 2.0 APIs only — no Spring/Micronaut/Quarkus, no Kora 1.x APIs, no invented annotations or config keys · **R3** journal any incorrect Kora usage. Add comments/Javadoc only if asked.

| | |
|---|---|
| **Framework** | Kora **2.x** — group `io.koraframework`, BOM `io.koraframework:kora-bom` |
| **Java** | **25+** (the published artifacts are class-file 69) |
| **Kotlin** | **2.4.x** with KSP **2.3.x** |
| **Gradle** | **9.x** |

Kora wires the whole container **at compile time**. The annotation processor (Java) or symbol
processor (Kotlin) reads your `@KoraApp` interface, resolves every dependency, and emits a plain
Java/Kotlin class that constructs the graph. There is no reflection, no classpath scanning and no
runtime proxying: an unresolvable dependency is a **compile error**, not a startup failure.

Read this skill when: bootstrapping `@KoraApp`, registering components with `@Component` /
`@Module` / `@FactoryModule`, splitting a build with `@KoraSubmodule`, disambiguating with `@Tag`,
gating components with `@Conditional`, or decoding a graph build failure.

**Scope boundary.** This skill covers everything the *processor* decides: declaration, discovery,
resolution and the compile errors it emits. What the graph does once it is *running* —
`init()`/`release()` ordering, refresh, `GraphInterceptor` — belongs to **kora-di-runtime**.

---

## Quick Start

```
Task Progress:
- [ ] 1. Add the kora-bom platform + annotation-processors (Java) / symbol-processors (KSP)
- [ ] 2. Create the @KoraApp interface and its main() entry point
- [ ] 3. extends the external modules you need (HoconConfigModule, LogbackModule, …)
- [ ] 4. Register your own types with @Component / @Module factory methods
- [ ] 5. ./gradlew classes and read the generated <App>Graph
```

---

## 1. Build Setup

### Java

```groovy
configurations {
    koraBom
    annotationProcessor.extendsFrom(koraBom)
    implementation.extendsFrom(koraBom)
    testAnnotationProcessor.extendsFrom(koraBom)
}

dependencies {
    koraBom platform("io.koraframework:kora-bom:$koraVersion")   // koraVersion=2.0.0.RC2
    annotationProcessor "io.koraframework:annotation-processors"
    testAnnotationProcessor "io.koraframework:annotation-processors"
}

java { toolchain { languageVersion = JavaLanguageVersion.of(25) } }
application { mainClass = "com.example.Application" }
```

### Kotlin

```kotlin
plugins {
    kotlin("jvm") version "2.4.20"
    id("com.google.devtools.ksp") version "2.3.12"
}

dependencies {
    implementation(platform("io.koraframework:kora-bom:$koraVersion"))
    ksp("io.koraframework:symbol-processors:$koraVersion")        // explicit version required
    kspTest("io.koraframework:symbol-processors:$koraVersion")
}

kotlin {
    jvmToolchain(25)
    sourceSets.main { kotlin.srcDir("build/generated/ksp/main/kotlin") }
    sourceSets.test { kotlin.srcDir("build/generated/ksp/test/kotlin") }
}

application { mainClass.set("com.example.ApplicationKt") }   // not "…Application"
```

`ksp` is **not** covered by the BOM platform, so `symbol-processors` needs its own version. Every
Gradle module declaring `@KoraApp`, `@KoraSubmodule`, `@Module` or `@Component` needs the processor
on its own compile classpath — otherwise nothing is generated and the only symptom is
`cannot find symbol: ApplicationGraph`.

Full templates: [`build.gradle.template`](assets/build.gradle.template),
[`build.gradle.kts.template`](assets/build.gradle.kts.template).

---

## 2. Application Bootstrap

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

```kotlin
// same imports; a top-level main() compiles into com.example.ApplicationKt
@KoraApp
interface Application : HoconConfigModule, LogbackModule

fun main() {
    KoraApplication.run(ApplicationGraph::graph)
}
```

`ApplicationGraph` is **generated into your own package** — never import it from
`io.koraframework.*`. The class name is always `<KoraAppSimpleName>Graph`.

`run(supplier)` blocks `main` until the JVM shutdown hook has released the graph; it is
`run(supplier, true)`. `run(supplier, false)` returns right after startup — only for a caller that
keeps working on that thread.

**Key rules:** `@KoraApp` only on an **interface** · one graph per runnable application ·
external modules need `extends` · local `@Module` interfaces are discovered automatically.

**→ [@KoraApp Reference](references/kora-app-component-reference.md)**

---

## 3. Component Registration

### `@Component` — constructor injection

```java
@Component
public final class UserService {
    private final UserRepository repository;

    public UserService(UserRepository repository) {   // exactly one public constructor
        this.repository = repository;
    }
}
```

### `@Module` — factory methods

```java
@Module
public interface StorageModule {

    default Storage storage(StorageConfig config) {
        return new TempFileStorage(config);
    }
}
```

`@Module` and `@KoraApp` accept **interfaces only**; providers are `default` methods (Kotlin: bodied
interface functions). A provider must return a reference type and must not return `null` unless the
consumer's parameter is `@Nullable`.

**→ [Component Registration Reference](references/component-registration-reference.md)** ·
**[Component Factories Reference](references/component-factories-reference.md)**

---

## 4. Module Discovery — when `extends` is required

The processor auto-collects every `@Module` interface **it compiles in this Gradle module**.
Anything already on the classpath as bytecode was never seen by the processor and must be pulled in
explicitly.

| Where the module lives | `extends` on `@KoraApp`? |
|---|---|
| `@Module` interface in the same compilation (`src/main/java`, `src/main/kotlin`) | **No** — auto-discovered |
| Module shipped by a Kora artifact (`HoconConfigModule`, `JdbcDatabaseModule`, …) | **Yes** |
| `@KoraSubmodule` in another Gradle subproject | **Yes** |

**→ [Module Auto-Discovery Reference](references/module-auto-discovery-reference.md)**

---

## 5. Multi-Module Projects

```java
// pet-api/  — the domain subproject
@KoraSubmodule
public interface PetModule extends CommonModule, JdbcDatabaseModule { }

// app/      — the assembly subproject
@KoraApp
public interface Application extends PetModule, HoconConfigModule, LogbackModule {
    static void main(String[] args) { KoraApplication.run(ApplicationGraph::graph); }
}
```

`@KoraSubmodule` makes the processor emit `<Name>SubmoduleImpl` next to the interface, carrying
every `@Component` and `@Module` provider compiled in that subproject. The processor must run in the
subproject too, or the `@KoraApp` build fails with *"Kora submodule was not generated yet"*.

**→ [@KoraSubmodule Reference](references/kora-submodule-reference.md)**

---

## 6. Disambiguation with `@Tag`

A tag is any class used as a marker. Matching is exact, with one wildcard:

| Injection point | Provider tag | Result |
|---|---|---|
| no tag | no tag | match |
| no tag | `@Tag(X.class)` | **no match** — tagged components are invisible to untagged claims |
| `@Tag(X.class)` | `@Tag(X.class)` | match |
| `@Tag(Tag.Any.class)` | any / none | match |

```java
public final class RedisTag { private RedisTag() {} }

@Tag(RedisTag.class) @Component
public final class RedisCache implements Cache { }

public UserService(@Tag(RedisTag.class) Cache cache) { }
```

**→ [Tags & Collections Reference](references/tags-collections-reference.md)**

---

## 7. Collection, Lazy and Optional Dependencies

| Parameter shape | Meaning |
|---|---|
| `All<T>` | every matching component; **`All<T> extends Iterable<T>`, not `List<T>`** |
| `All<ValueOf<T>>` / `All<PromiseOf<T>>` | the same set, held indirectly |
| `ValueOf<T>` | indirect link — breaks cycles, decouples refresh |
| `PromiseOf<T>` | indirect link resolved to `Optional<T>` after init |
| `@Nullable T` | optional; the processor injects `null` when nothing matches |
| `Optional<T>` | optional; the processor builds the `Optional` for you |
| `Wrapped<T>` (provider side) | provider returns a wrapper, consumers receive the unwrapped `T` |

```java
@Component
public final class NotificationService {
    public NotificationService(@Tag(Tag.Any.class) All<Notifier> notifiers,
                               ValueOf<AuditLog> audit,
                               @Nullable SmsProvider sms) { }
}
```

Java nullability is **JSpecify** (`org.jspecify.annotations.Nullable`, type-use). Kotlin expresses it
as `T?` — never carry JSpecify annotations into Kotlin.

---

## 8. Graph Roots

Nothing is instantiated unless it is a `@Root` or a transitive dependency of one. A component whose
only job is a side effect at startup will be **pruned** without `@Root`.

```java
import io.koraframework.common.annotation.Root;

@Root @Component
public final class CacheWarmer implements Lifecycle {
    public void init() { /* runs at startup */ }
    public void release() { }
}
```

`@Root` also applies to a `@Module` provider method. `@Root` lives in
`io.koraframework.common.annotation` — the same package as everything else in 2.0.

**→ [Graph Roots & Lifecycle Reference](references/lifecycle-reference.md)** ·
runtime `init`/`release` semantics: **kora-di-runtime**

---

## 9. Conditional Components (new in 2.0)

`@Conditional(tag = X.class)` gates a component on a `GraphCondition` published under `@Tag(X.class)`.
Candidates are all compiled; exactly one must match when the graph initialises.

```java
@Component
@Conditional(tag = RedisEnabled.class)
public final class RedisCache implements Cache { }
```

**→ [Conditional Components Reference](references/conditional-components-reference.md)**

---

## 10. Graph Build Failures

The 2.0 processor prints a diagnosis, the `Required at:` signature with the offending parameter, a
resolution path (`@---` root … `^---` … `[MISSING]` / `[CYCLE]`), optional `Note:` and `Hint:`
sections and a `Fix:` list. Tags print as written in code (`@Tag(X.class)`, `@Pg`). Match on the
**first line**:

| First line | Cause | Fix |
|---|---|---|
| `No component found for dependency:` | nothing provides that type+tag | add `@Component`, add a module provider, or `extends` the module that has one |
| `Multiple components match dependency:` | two providers, same type+tag | differentiate with `@Tag`, mark the fallback `@DefaultComponent`, or delete one |
| `Circular dependency found:` | a cycle the processor could not break with a generated proxy — the closing dependency is a `final` class (Kotlin: not `open`), not a class/interface, or an `All<T>`/`TypeRef<T>`/`Graph` claim; `Note:` says which | depend on an interface so a proxy can be used; or take `ValueOf<T>` / `PromiseOf<T>` on one side; a cycle through an `All<T>` injection point — remove the back-edge, move the shared piece into a separate component (the printed `Use All<ValueOf<T>> or All<PromiseOf<T>>` fix does **not** break it — still the same error) |
| `@Component class must have exactly one public constructor:` (submodule: `@Component type has more than one public constructor:` / `… has no public constructors:`) | 0 or 2+ public constructors; the error lists the ones found | keep one; move complex construction to a module provider |
| `@KoraApp can only be applied to interfaces.` / `@Module can only be applied to interfaces.` | annotation on a class | make it an interface |
| `Kora submodule was not generated yet:` | processor missing in the submodule's build | add `annotationProcessor` / `ksp` there |
| `@Tag.Factory can only be used inside factory modules:` | `Tag.Factory` outside a `@FactoryModule` | use an explicit `@Tag(...)` |
| `Component provider returns a generated AOP proxy type:` | a module method returns `$Foo__AopProxy` | return (and inject) the original type `Foo` |
| `Dependency uses a raw type:` / `Component uses a raw type:` | raw `List`, `Map`, `Repository` … as a parameter / as a provided type | supply type arguments |
| `Expected @KoraApp as SubModule, but Submodule implementation not found` (**warning**) | a test `@KoraApp` extends the main one without `-Akora.app.submodule.enabled=true` | see [@KoraSubmodule Reference](references/kora-submodule-reference.md) |

A `No component found` error also lists **same-type-different-tag** candidates under `Note:`, and
its `Fix:` then starts with the tag move to make (request the candidate's tag, drop the
dependency's tag, or retag the component) — read that section first; a forgotten or mismatched
`@Tag` is the usual cause. For a type a Kora module provides, `Hint:` gives numbered steps: the
Gradle artifact to add and the module interface to `extends` on `@KoraApp`.

---

## 11. Debugging

```bash
# Java — generated graph
ls build/generated/sources/annotationProcessor/java/main/

# Kotlin — generated graph
ls build/generated/ksp/main/kotlin/
```

Both processors log to the build console (level `INFO` by default) and take the same `koraLogLevel`
option. The Java annotation processor also writes a full log under `build/kora/log/`; KSP writes no
log file:

```groovy
// Java
compileJava { options.compilerArgs += ["-AkoraLogLevel=DEBUG"] }
```

```kotlin
// Kotlin (build.gradle.kts)
ksp { arg("koraLogLevel", "DEBUG") }
```

After renaming a package or migrating from 1.x, stale generated sources produce phantom errors that
point at classes you have already deleted. Rebuild the generated tree — never hand-edit it:

```bash
./gradlew clean classes --no-build-cache
```

---

## 12. Removed in Kora 2.0

- **`Context` does not exist anywhere in the framework.** A component or provider that takes a Kora
  `Context` parameter will not compile.
- Component contracts are **synchronous**, executed on virtual threads. `CompletionStage`,
  Reactor `Mono`/`Flux` and Kotlin `suspend` are no longer Kora contracts.
- `ru.tinkoff.kora.*` is gone; DI annotations moved from `ru.tinkoff.kora.common` to
  **`io.koraframework.common.annotation`**. `@Root` was already in `…common.annotation` under 1.x —
  it only changed group.
- `ru.tinkoff.kora:kora-parent` is replaced by `io.koraframework:kora-bom`.

---

## References

| Reference | When |
|---|---|
| [@KoraApp](references/kora-app-component-reference.md) | Bootstrap, generated graph, entry point |
| [Component Registration](references/component-registration-reference.md) | Getting a type into the graph |
| [Module Auto-Discovery](references/module-auto-discovery-reference.md) | `extends` rules |
| [@KoraSubmodule](references/kora-submodule-reference.md) | Multi-module Gradle builds |
| [@DefaultComponent](references/default-component-reference.md) | Overridable defaults |
| [Component Factories](references/component-factories-reference.md) | Providers, generics, `@FactoryModule` |
| [Tags & Collections](references/tags-collections-reference.md) | `@Tag`, `All<T>`, `ValueOf<T>` |
| [Conditional Components](references/conditional-components-reference.md) | `@Conditional`, `GraphCondition` |
| [Graph Roots & Lifecycle](references/lifecycle-reference.md) | `@Root`, `Lifecycle`, `Wrapped<T>` |

---

## Assets

Templates in `assets/`: `Application.java.template`, `Application.kt.template`,
`Component.java.template`, `Module.java.template`, `KoraSubmodule.java.template`,
`build.gradle.template`, `build.gradle.kts.template`, `settings.gradle.template`,
`gradle.properties.template`, `gradle-wrapper.properties.template`, `application.conf.template`,
`application.yaml.template`, plus [QUICK_REFERENCE.md](assets/QUICK_REFERENCE.md).

```bash
python3 scripts/generate_project.py --name my-app --package com.example --dry-run
python3 scripts/generate_project.py --name my-app --package com.example --lang kotlin
python3 scripts/validate_gradle.py --file build.gradle
```
