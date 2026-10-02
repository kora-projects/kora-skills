# Kora 2.x DI Compile — Quick Reference

## Annotations — all in `io.koraframework.common.annotation`

| Annotation | Target | Purpose |
|---|---|---|
| `@KoraApp` | interface | the container configuration; generates `<Name>Graph` |
| `@KoraSubmodule` | interface | exports a Gradle subproject; generates `<Name>SubmoduleImpl` |
| `@Module` | interface | group of provider methods, auto-discovered in the same compilation |
| `@Component` | class | register the class, built by its single public constructor |
| `@DefaultComponent` | method, type | fallback beaten by any non-default provider of the same type+tag |
| `@FactoryModule` | method | the returned object is itself a module (new in 2.0) |
| `@Conditional(tag = X.class)` | type, method | gate on a `GraphCondition` tagged `X` (new in 2.0) |
| `@Root` | type, method | force into the graph even when nothing depends on it |
| `@Tag(X.class)` | method, param, field, type, type-use | disambiguate |
| `@Mapping`, `@NamingStrategy`, `@Generated` | various | converter / naming / generated-source markers |

**Do not import these from `io.koraframework.common`** — that package holds `Configurer`, `Either`,
`Principal`, `PromisedProxy`. A blind `ru.tinkoff.kora` → `io.koraframework` rewrite lands them there.

## Graph types — `io.koraframework.application.graph`

`All`, `ApplicationGraphDraw`, `Graph`, `GraphCondition`, `GraphInterceptor`, `InitializedGraph`,
`KoraApplication`, `Lifecycle`, `LifecycleWrapper`, `Node`, `NodeWithMapper`, `PromiseOf`,
`RefreshListener`, `RefreshableGraph`, `TypeRef`, `ValueOf`, `Wrapped`, `WrappedRefreshListener`

## Dependency shapes

| Parameter | Behaviour |
|---|---|
| `T` | required; unresolved → compile error |
| `@Nullable T` (JSpecify) / `T?` (Kotlin) | `null` when nothing matches |
| `Optional<T>` | the processor builds the `Optional` |
| `All<T>` | every match; **`Iterable<T>`, not `List<T>`**; may be empty |
| `@Tag(Tag.Any.class) All<T>` | every match *including tagged* |
| `ValueOf<T>` | indirect; `get()`, `map()`, `optional()` — **no `refresh()`** |
| `PromiseOf<T>` | indirect; `get()` returns `Optional<T>` |
| `Wrapped<T>` (provider return) | consumers receive the unwrapped `T` |

## Tag matching

| Required | Provided | Match |
|---|---|---|
| none | none | yes |
| none | `X` | **no** |
| `X` | `X` | yes |
| `Tag.Any` | anything | yes |

## Patterns

### Component
```java
@Component
public final class UserService {
    private final UserRepository repo;
    public UserService(UserRepository repo) { this.repo = repo; }
}
```

### Module provider
```java
@Module
public interface StorageModule {
    default Storage storage(StorageConfig config) { return new TempFileStorage(config); }
}
```

### Bootstrap
```java
@KoraApp
public interface Application extends HoconConfigModule, LogbackModule {
    static void main(String[] args) { KoraApplication.run(ApplicationGraph::graph); }
}
```

```kotlin
@KoraApp
interface Application : HoconConfigModule, LogbackModule

fun main() { KoraApplication.run(ApplicationGraph::graph) }
```

`run(supplier)` = `run(supplier, true)`: blocks until the shutdown hook released the graph.
`run(supplier, false)` returns after init.

### Tagged
```java
public final class RedisTag { private RedisTag() {} }

@Tag(RedisTag.class) @Component
public final class RedisCache implements Cache { }

public UserService(@Tag(RedisTag.class) Cache cache) { }
```

### Root + lifecycle
```java
@Root @Component
public final class CacheWarmer implements Lifecycle {
    public void init() { /* startup */ }
    public void release() { /* shutdown */ }
}
```

### Lifecycle for a type you do not own
```java
@Module
public interface PoolModule {
    default Wrapped<ConnectionPool> pool(PoolConfig c) {
        return new LifecycleWrapper<>(new HikariConnectionPool(c),
                                      ConnectionPool::initialize,
                                      ConnectionPool::close);
    }
}
```

### Conditional
```java
@Component @Conditional(tag = RedisEnabled.class)
public final class RedisCache implements Cache { }

@Module
public interface ConditionModule {
    @Tag(RedisEnabled.class)
    default GraphCondition redisEnabled(CacheConfig c) {
        return () -> c.redisEnabled()
                ? GraphCondition.ConditionResult.matched("cache.redisEnabled = true")
                : GraphCondition.ConditionResult.failed("cache.redisEnabled = false");
    }
}
```

## Build

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
}

java { toolchain { languageVersion = JavaLanguageVersion.of(25) } }
```

### Kotlin
```kotlin
plugins {
    kotlin("jvm") version "2.4.20"
    id("com.google.devtools.ksp") version "2.3.12"
}

dependencies {
    implementation(platform("io.koraframework:kora-bom:$koraVersion"))
    ksp("io.koraframework:symbol-processors:$koraVersion")       // not covered by the BOM
}

kotlin {
    jvmToolchain(25)
    sourceSets.main { kotlin.srcDir("build/generated/ksp/main/kotlin") }
}
```

## Errors

| First line | Fix |
|---|---|
| `No component found for dependency:` | add `@Component` / a provider / `extends` the module — read the `Note:` block for tag mismatches |
| `Multiple components match dependency:` | distinct `@Tag`, or `@DefaultComponent` on the fallback |
| `Circular dependency found:` | no proxy possible (final class, `All<T>`…, see `Note:`): depend on an interface, or `ValueOf<T>`/`PromiseOf<T>` on one side; through `All<T>` — split out the shared piece |
| `@Component class must have exactly one public constructor:` | keep one public constructor (the error lists the ones found) |
| `@KoraApp can only be applied to interfaces.` | make it an interface (same for `@Module`) |
| `Kora submodule was not generated yet:` | add the processor to that Gradle subproject |
| `@Tag.Factory can only be used inside factory modules:` | use an explicit `@Tag(...)` |
| `Dependency uses a raw type:` | supply type arguments |
| `Expected @KoraApp as SubModule, but Submodule implementation not found` (warning) | add `-Akora.app.submodule.enabled=true` to the **main** compilation |
| `cannot find symbol: ApplicationGraph` | the processor is not on the classpath |

## Generated code

```
build/generated/sources/annotationProcessor/java/main/<package>/ApplicationGraph.java   # Java
build/generated/ksp/main/kotlin/<package>/ApplicationGraph.kt                           # Kotlin
build/kora/log/                                                                         # processor log (Java only; both log to the console, -AkoraLogLevel / ksp arg koraLogLevel)
```

Never hand-edit generated sources. After a package rename or a 1.x migration:

```bash
./gradlew clean classes --no-build-cache
```

## Removed in 2.0

- **`Context` does not exist** anywhere in the framework
- component contracts are synchronous — no `CompletionStage`, `Mono`, `Flux`, `suspend`
- `ru.tinkoff.kora:kora-parent` → `io.koraframework:kora-bom`
- `json-module` → `json-common`

## Commands

```bash
./gradlew classes                 # run the processor
./gradlew clean build

python3 scripts/generate_project.py --name my-app --package com.example --dry-run
python3 scripts/validate_gradle.py --file build.gradle
```
