---
name: kora-bootstrap
description: Bootstrap new Kora projects with Gradle setup, DI container wiring, @KoraApp definition, component registration via @Component/@Module, typed configuration with @ConfigSource (HOCON/YAML), and lifecycle management. Use when scaffolding a new Kora service, adding DI components, configuring application bootstrap, or debugging graph build failures. Triggers: @KoraApp, KoraApplication.run, ApplicationGraph, @Component, @Module, @Root, @Tag, @ConfigSource, kora-parent BOM, annotation-processors, symbol-processors, HoconConfigModule, YamlConfigModule, LifecycleWrapper, ValueOf.
---

# Kora Bootstrap — Basic Setup for Kora Applications

## Framework Version & Compatibility

| Component | Version | Note |
|-----------|---------|------|
| **Kora** | 1.2.15+ | Latest stable |
| **Java** | 21+ (recommended: 25) | LTS 25 for new projects |
| **Kotlin** | 1.9+ (JVM 17) | Stable version with full support |
| **Gradle** | 9.5.1+ | Required for incremental build |
| **Annotation Processors** | Included in BOM | `annotation-processors` for Java |
| **KSP (Kotlin)** | 1.9.x-1.0.x | `kora-ksp` for Kotlin projects |

**BOM Dependency:**
```groovy
dependencies {
    koraBom platform("ru.tinkoff.kora:kora-parent:1.2.15")
}
```

Read this first when:
- bootstrapping a new Kora project (Java or Kotlin),
- adding or refactoring `@KoraApp`, modules, or factory methods,
- introducing a new typed configuration section with `@ConfigSource`,
- debugging graph build failures ("dependency not found", "no factory", multi-instance ambiguity),
- planning a multi-Gradle-module application with `@KoraSubmodule`.

**Java version recommendation:**
- **Java:** Always start new projects with **Java 25** (`JavaVersion.VERSION_25`) — this gives access to the latest platform features.
- **Kotlin:** Use **JVM 17** (`jvmToolchain(17)`) — the stable version with full Kotlin support.

> **Important: Gradle (recommended)**
> 
> Kora **recommends Gradle 9.5.1+** — it provides optimal annotation processor support and incremental build. Maven is technically possible but significantly slower.
>
> **Why Gradle is preferred:**
> - Kora relies on annotation processors (Java) and KSP (Kotlin) for compile-time code generation.
> - Gradle provides optimal incremental build support with annotation processors.
> - Gradle supports multi-round annotation processing — critical for Kora code generation.
> - Significantly faster builds due to incrementality.
> - Better integration with the Kora BOM and dependencies.
>
> Maven is technically possible but will be **significantly slower** due to worse annotation processing support and no incremental build.
>
> Minimum required Gradle version is **7+**.
>
> **Documentation:** [Kora Build System](.kora-agent/kora-docs/mkdocs/docs/en/documentation/general.md#build-system)

## Quick start: scaffold a new service

A minimum-viable Kora service has:

1. **`build.gradle`** with the Kora BOM and the annotation processor (Java) or KSP (Kotlin).
2. **`Application.java` / `Application.kt`** — an interface annotated with `@KoraApp` extending the modules you need.
3. **`application.conf` / `application.yaml`** — typed configuration.
4. **A logging backend** — `logging-logback` is the canonical choice. Add `logback.xml`.
5. **Entry point** — `KoraApplication.run(ApplicationGraph::graph)`.

Templates for every file above are in `assets/`. Copy them, change the package name, and you have a runnable service that prints nothing and exits cleanly. Add modules (HTTP server, JSON, DB, ...) only as you need them by `extends ...Module` on the `@KoraApp` interface and `implementation "ru.tinkoff.kora:<module>"` in `build.gradle`.

### 0. Prepare the Gradle Wrapper (if Gradle is not installed)

**If Gradle is not installed on the machine** — use the Gradle Wrapper to initialize the project:

```bash
mkdir -p gradle/wrapper
cat > gradle/wrapper/gradle-wrapper.properties << 'EOF'
distributionBase=GRADLE_USER_HOME
distributionPath=wrapper/dists
distributionUrl=https\://services.gradle.org/distributions/gradle-9.5.1-bin.zip
networkTimeout=10000
validateDistributionUrl=true
zipStoreBase=GRADLE_USER_HOME
zipStorePath=wrapper/dists
EOF
curl -L https://raw.githubusercontent.com/gradle/gradle/v9.5.1/gradle/wrapper/gradle-wrapper.jar -o gradle/wrapper/gradle-wrapper.jar
java -cp gradle/wrapper/gradle-wrapper.jar org.gradle.wrapper.GradleWrapperMain init
ls -la build.gradle
```

### 1. Generate the project

```bash
# Single-module Java
python kora-bootstrap/scripts/generate_project.py --name my-app --package com.example
# Kotlin
python kora-bootstrap/scripts/generate_project.py --name my-app --package com.example --lang kotlin
# Multi-module (>500 classes)
python kora-bootstrap/scripts/generate_project.py --name my-app --package com.example --multi-module
```

### 2. Validate and run

```bash
python kora-bootstrap/scripts/validate_gradle.py --project my-app
cd my-app && ./gradlew clean build && ./gradlew run
```

---

## Core concepts (one-paragraph each)

### `@KoraApp` is the container

`@KoraApp` is the single root of the dependency graph. It must be put on **one interface** in the application. That interface lists external modules via `extends` and may itself declare factory methods (`default` interface methods). At compile time Kora generates a class `<Application>Graph` in the same package — that class implements the graph and is what `KoraApplication.run` consumes. There is no separate "main class": `main` is a `static` method on the `@KoraApp` interface that calls `KoraApplication.run(ApplicationGraph::graph)`.

**Important:** `ApplicationGraph` is generated automatically by the annotation processor.

**Tip: When in doubt, read the generated code.**
Kora is a compile-time framework: all code is generated at compile time. If it is unclear how DI, AOP, or any other mechanism works:
1. Open `$buildDir/generated/sources/annotationProcessor/`
2. Find the generated class (e.g., `*ComponentImpl`, `*Graph`, `*Aspect`)
3. Study how the code is wired together

This helps understand how Kora processes your annotations and how components interact — no magic involved.

### Components are singletons, wired at compile time

A component is anything the container holds. By default every component is a **singleton** initialized eagerly (in parallel where possible) at startup. There are five ways to register a component, in priority order:

1. **`@Component` on a final class** with a single public constructor — the container creates the instance and injects constructor dependencies.
2. **A `default` factory method on a `@Module` interface** — Kora discovers `@Module` interfaces in the same source set and runs every factory method. Module must live in the same compilation as `@KoraApp`.
3. **A `default` factory method directly on the `@KoraApp` interface** — useful for app-specific overrides.
4. **`@KoraSubmodule`** — generates an inheritor interface with all `@Module`/`@Component` factories from a separate Gradle module, which the `@KoraApp` interface then `extends`. Use this when you split the build into multi-module Gradle.
5. **Auto-creation** — if no factory exists and the requested class is final with a single public constructor, Kora generates the factory on the fly.

Reflection is never used. Mismatches (missing factory, ambiguous component, cycle) are compile errors, not runtime crashes.

### `@Root` for "no consumers but must start"

Only components that are dependencies of other components, or marked `@Root`, are actually instantiated. Servers, message consumers, schedulers, and warmers must be `@Root` — otherwise nothing depends on them and the graph silently drops them. **Forget `@Root` and your HTTP server won't start.**

### Modules from third-party Kora artifacts

External Kora modules (Json, Hocon config, Undertow HTTP server, etc.) ship `*Module` interfaces. You plug them in by inheritance on the `@KoraApp` interface:

```java
@KoraApp
public interface Application extends
        HoconConfigModule,
        JsonModule,
        LogbackModule,
        UndertowHttpServerModule { ... }
```

Kora does **not** auto-discover modules from the classpath (unlike Spring Boot). Explicit `extends` keeps startup deterministic and makes it obvious which capabilities the service has.

### Module Auto-Discovery

| Module type | extends |
|------------|---------|
| `@Module` in the same `src/main/java` | No (auto-discovery) |
| Module from an external library | Yes |
| `@KoraSubmodule` from another Gradle module | Yes (one per Gradle module) |

### `@DefaultComponent` and overrides

When a library wants to provide an opt-out default (e.g., a default `ObjectMapper`), it marks the factory `@DefaultComponent`. The app can override by declaring a plain factory without that annotation; the non-default factory wins. To override a module factory, declare a method with the same return type on the `@KoraApp` interface.

### Tags differentiate same-type components

If two components share a type, use `@Tag(MyTag.class)` both on the factory and on the injection point. `@Tag` uses a **class literal**, not a string, so refactoring is safe. To collect all components of a type into a list, inject `All<T>` (a token interface that extends `List<T>`); to filter by tag, combine `@Tag(MyTag.class) All<Handler>`. `@Tag(Tag.Any.class)` collects all instances regardless of tag.

```java
public final class RedisTag {}  // Simple tag class
@Tag(RedisTag.class) @Component
public final class RedisCache implements Cache {}  // Tagged component
public Service(@Tag(RedisTag.class) Cache cache) {}  // Tagged injection
public Service(@Tag(Tag.Any.class) List<Cache> allCaches) {}  // All including tagged
```

### Optional dependencies

Mark a constructor parameter `@Nullable` (any `@Nullable` annotation works — Jakarta, JetBrains, javax) to opt out of the "missing factory is an error" rule. In Kotlin, declare the type nullable: `val foo: Foo?`.

### Lifecycle and graceful shutdown

A component with non-trivial init/release implements `Lifecycle`:

```java
public interface Lifecycle {
    void init() throws Exception;
    void release() throws Exception;
}
```

For factory methods that don't return a `Lifecycle` directly, wrap the component:

```java
default Wrapped<SomeService> someService() {
    return new LifecycleWrapper<>(new SomeService(),
            (c) -> { /* init */ },
            (c) -> { /* release */ });
}
```

On SIGTERM the container releases components in reverse init order. HTTP server, Kafka consumers, schedulers all support graceful shutdown via lifecycle out of the box.

### `ValueOf<T>` — indirect dependency

`ValueOf<T>` decouples lifecycle: if `B` depends on `ValueOf<A>` and `A` updates (e.g., its config changes), `B` is **not** restarted. Use this when the consumer can swap its target at runtime — HTTP request handlers, for example, are injected as `ValueOf` into the server so config-driven route reloads don't restart Undertow.

### `GraphInterceptor<T>` — modify or warm up

Implement `GraphInterceptor<T>` to wrap a component's lifecycle:

```java
@Component
public final class CacheWarmupInterceptor implements GraphInterceptor<JdbcDatabase> {
    public JdbcDatabase init(JdbcDatabase value) { /* warm */ return value; }
    public JdbcDatabase release(JdbcDatabase value) { return value; }
}
```

`init` may return a different instance and that one becomes the dependency seen by downstream components.

---

## Configuration

Kora supports HOCON (`config-hocon` + `HoconConfigModule`) and YAML (`config-yaml` + `YamlConfigModule`). Pick one — using both is supported but unusual. Templates for both are in `assets/`.

**File precedence (per format):** `config.resource` system property → `config.file` system property → `application.conf` / `application.yaml` on the classpath → empty config.

**Defining a typed section:**

```java
@ConfigSource("app.database")
public interface DatabaseConfig {
    String url();          // required
    @Nullable String username(); // optional, null if absent
    String password();    // required
    default int poolSize() { return 20; } // default value
}
```

`@ConfigSource` on an interface registers a component of that type. Inject `DatabaseConfig` into any other component normally. For library-defined configs (without an absolute path), use `@ConfigValueExtractor` instead and provide a factory that reads `config.get("path.to.section")`.

**Environment / system properties:**

```hocon
app.database {
    url = ${DATABASE_URL}                  # required env var, fail-fast if absent
    username = ${?DATABASE_USERNAME}       # optional env var, omitted if absent
    password = ${?DATABASE_PASSWORD:-secret} # optional with default value
    pool-size = 20
}
```

YAML: `${?DB_USER:default}` for inline default.

**Don't inject the raw `Config`** as a dependency in business components — when the file changes, every component that depends on `Config` is restarted. Always declare an `@ConfigSource` interface and inject that. The container will only restart consumers when *that specific section* changes.

**Disable the config watcher** with env var `KORA_CONFIG_WATCHER_ENABLED=false` or system property `kora.config.watcher.enabled=false`. The watcher is on by default and refreshes the graph when the file changes on disk.

---

## Gradle Setup

```groovy
plugins { id "java"; id "application" }
configurations { koraBom; annotationProcessor.extendsFrom(koraBom); implementation.extendsFrom(koraBom) }
dependencies {
    koraBom platform("ru.tinkoff.kora:kora-parent:1.2.15")
    annotationProcessor "ru.tinkoff.kora:annotation-processors"
}
java { sourceCompatibility = JavaVersion.VERSION_25 }
application { mainClass = "com.example.Application" }
```

**Important:** Use double quotes (`"`) for strings, not single quotes (`'`).

**See also:** [references/gradle-setup-reference.md](references/gradle-setup-reference.md)

---

## Code Style

**Oracle Java Code Style** — use [Oracle Java Code Conventions](https://www.oracle.com/java/technologies/javase/codeconventions-introduction.html) as the base standard:

- **Naming**: `CamelCase` for classes, `camelCase` for methods/variables, `UPPER_SNAKE_CASE` for constants
- **Braces**: K&R style (opening brace on the same line)
- **Indentation**: 4 spaces (no tabs)
- **Line length**: 180 characters maximum
- **Imports**: Grouped by package, no wildcards (`import java.util.*` is forbidden)

**Note:** For Kotlin, use [Kotlin Coding Conventions](https://kotlinlang.org/docs/coding-conventions.html).

---

## Project Structure

**Threshold:** 500+ classes is the signal to split into modules.

**Single-Module:**
```
my-app/
├── build.gradle
├── settings.gradle
└── src/main/java/com/example/
    ├── Application.java
    ├── DatabaseModule.java
    └── service/
        └── UserService.java
```

**Multi-Module:**
```
my-app/
├── common/    # Shared types
├── pet-api/   # Pet domain
├── vet-api/   # Vet domain
└── app/       # Application assembly
```

**See also:** [references/multi-module-architecture.md](references/multi-module-architecture.md)

---

## Development Workflow

**Iterative Development:** Write code in small increments → Compile: `./gradlew clean classes` → Tests: `./gradlew test` → Validate against examples.

| Command | When to use |
|---------|-------------|
| `./gradlew clean classes` | Quick compilation check |
| `./gradlew clean build` | Full build before commit |
| `./gradlew distTar` | Build the final artifact (tar.gz) |
| `./gradlew --stop` | Stop the Gradle daemon when it causes problems |

**Important:** Use `distTar` to build the final artifact. For intermediate compilation checks, use `./gradlew clean classes`.

---

## Common pitfalls

- **`@Root` missing on long-running components** → HTTP server / Kafka consumer never starts, app exits 0. Always `@Root` for "self-driving" components.
- **`@KoraApp` extends a module whose dependency is missing in `build.gradle`** → compile-time error pointing to the missing factory. Add the `implementation "ru.tinkoff.kora:<artifact>"` line.
- **Two `@Component` of the same type without `@Tag`** → graph build fails with "ambiguous dependency". Fix by either tagging or by removing one.
- **Injecting `Config` directly** → every config edit reboots the whole graph. Always go through `@ConfigSource`.
- **Forgetting `@Nullable` on optional config** → app fails to start because Kora treats every method as required.
- **Final class with non-public constructor + `@Component`** → factory generation fails. Constructor must be public and singular.
- **Mixing `@Module` interface placement across Gradle modules without `@KoraSubmodule`** → factories from other Gradle modules aren't picked up. Use `@KoraSubmodule` per Gradle module.
- **Writing `mainClass = "...ApplicationGraph"`** → wrong. `mainClass` is the `@KoraApp` interface itself (it has the `static void main`), e.g., `ru.tinkoff.kora.example.helloworld.Application`.

---

## Quick Reference

### DI Patterns

```java
public Service(Dependency dep) {}  // Constructor injection
public Service(@Tag(MyTag.class) Dependency dep) {}  // Tagged injection
public Service(All<Listener> listeners) {}  // Collection injection
public Service(@Nullable Dependency dep) {}  // Optional injection
public Service(ValueOf<Config> config) {}  // Lazy injection
```

### Config Patterns

```hocon
value = ${ENV_VAR}  # Required
value = ${?ENV_VAR}  # Optional
value = ${?ENV_VAR:-default}  # Default
```

### Tag Patterns

```java
public final class MyTag {}  // Simple tag class
@Tag(MyTag.class) @Component
public final class MyComponent implements Interface {}  // Tagged component
public Service(@Tag(MyTag.class) Interface impl) {}  // Tagged injection
public Service(@Tag(Tag.Any.class) List<Interface> allImpls) {}  // All including tagged
```

### Lifecycle Patterns

```java
@Component
public final class MyComponent implements Lifecycle {
    @Override public void init() { /* init logic */ }
    @Override public void release() { /* cleanup logic */ }
}

// Factory method with LifecycleWrapper
default MyComponent myComponent() {
    return LifecycleWrapper.wrap(new MyComponent(), c -> c.warmup(), c -> c.cleanup());
}
```

---

## Assets

| File | Description |
|------|-------------|
| `build.gradle.template` / `build.gradle.kts.template` | Gradle build for Java / Kotlin |
| `settings.gradle.template` | Settings file with module includes |
| `gradle.properties.template` | Kora version properties |
| `gradle-wrapper.properties.template` | Gradle Wrapper (Gradle 9.5.1) |
| `Application.java.template` / `Application.kt.template` | Main application interface |
| `application.conf.template` / `application.yaml.template` | HOCON / YAML configuration |

**Script:** `scripts/generate_project.py` — generates the project using templates.

---

## Reference Files

| File | Description |
|------|-------------|
| [references/core-container-reference.md](references/core-container-reference.md) | Full DI container reference |
| [references/dependency-injection-reference.md](references/dependency-injection-reference.md) | DI annotations and patterns |
| [references/config-reference.md](references/config-reference.md) | HOCON/YAML configuration |
| [references/lifecycle-reference.md](references/lifecycle-reference.md) | Lifecycle and GraphInterceptor |
| [references/tags-collections-reference.md](references/tags-collections-reference.md) | @Tag, All<T>, Tag.Any, Tag.All |
| [references/gradle-setup-reference.md](references/gradle-setup-reference.md) | Gradle build setup |
| [references/multi-module-architecture.md](references/multi-module-architecture.md) | Multi-module structure |

---

## Scripts

```bash
# Single-module Java / Kotlin / Multi-module
python kora-bootstrap/scripts/generate_project.py --name my-app --package com.example [--lang kotlin] [--multi-module]

# Validate project / file
python kora-bootstrap/scripts/validate_gradle.py --project my-app
python kora-bootstrap/scripts/validate_gradle.py --file build.gradle
```
