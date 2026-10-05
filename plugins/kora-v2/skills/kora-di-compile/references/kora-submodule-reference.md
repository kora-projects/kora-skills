# @KoraSubmodule Reference

**Applies to:** Kora 2.x (`io.koraframework`)

## Contents

- [Overview](#overview)
- [What the Processor Generates](#what-the-processor-generates)
- [Project Structure](#project-structure)
- [Root Build Configuration](#root-build-configuration)
- [Subproject Builds](#subproject-builds)
- [The Sources](#the-sources)
- [Kotlin Variant](#kotlin-variant)
- [Test @KoraApp and kora.app.submodule.enabled](#test-koraapp-and-koraappsubmoduleenabled)
- [Key Rules](#key-rules)
- [Common Mistakes](#common-mistakes)
- [Related References](#related-references)

## Overview

`@KoraSubmodule` (`io.koraframework.common.annotation.KoraSubmodule`) is how a Gradle subproject
exports its Kora components across a compilation boundary. Placed on an interface, it makes the
processor emit a companion interface containing a provider for **every `@Component` class and every
`@Module` provider method compiled in that subproject**. The `@KoraApp` in the assembly project then
extends the annotated interface, and the generated companion is wired in automatically.

Without it, `@Module`/`@Component` in another subproject are invisible — the `@KoraApp` processor
never compiled them.

## What the Processor Generates

| Property | Value |
|---|---|
| Generated interface | `<InterfaceSimpleName>SubmoduleImpl`, same package |
| Contents | `_component0()`, `_component1()`, … one per exported provider |
| Carried over | `@Tag`, `@Root`, `@DefaultComponent` from the original declaration |
| Skipped | abstract `@Component` classes and classes carrying AOP annotations (the aspect processor owns those) |
| Trigger | the annotation processor / symbol processor running **in that subproject** |

The `@KoraApp` processor looks the companion up by name. If the subproject did not run a processor:

```
Kora submodule was not generated yet:
  expected type: com.example.pet.PetModuleSubmoduleImpl

Fix:
  - Ensure the submodule processor is enabled.
  - Compile again after generated sources are available.
```

## Project Structure

```
my-app/
├── settings.gradle
├── gradle.properties            # koraVersion=2.0.0.RC2
├── build.gradle                 # shared subprojects { } configuration
├── common/
│   └── src/main/java/com/example/common/CommonModule.java   // @KoraSubmodule
├── pet-api/
│   └── src/main/java/com/example/pet/PetModule.java         // @KoraSubmodule
├── vet-api/
│   └── src/main/java/com/example/vet/VetModule.java         // @KoraSubmodule
└── app/
    └── src/main/java/com/example/app/Application.java       // @KoraApp
```

Split when domains have genuinely separate ownership or dependency sets — not by class count.
The assembly project should hold the `@KoraApp`, the entry point and little else.

## Root Build Configuration

### settings.gradle

```groovy
rootProject.name = "my-app"

include ":common"
include ":pet-api"
include ":vet-api"
include ":app"
```

### gradle.properties

```properties
koraVersion=2.0.0.RC2

org.gradle.parallel=true
org.gradle.caching=true
```

### build.gradle (root)

```groovy
subprojects {
    repositories {
        mavenCentral()   // io.koraframework:kora-bom:2.0.0.RC2 is on Maven Central
    }

    configurations {
        koraBom
        annotationProcessor.extendsFrom(koraBom)
        compileOnly.extendsFrom(koraBom)
        implementation.extendsFrom(koraBom)
        api.extendsFrom(koraBom)
        testImplementation.extendsFrom(koraBom)
        testAnnotationProcessor.extendsFrom(koraBom)
    }

    dependencies {
        koraBom platform("io.koraframework:kora-bom:$koraVersion")
        annotationProcessor "io.koraframework:annotation-processors"
    }

    plugins.withId("java") {
        java {
            toolchain {
                languageVersion = JavaLanguageVersion.of(25)
                vendor = JvmVendorSpec.ADOPTIUM
            }
        }
    }

    tasks.withType(JavaCompile).configureEach { options.encoding = "UTF-8" }
}
```

Declaring `annotationProcessor` once in `subprojects` is what guarantees every module generates its
`…SubmoduleImpl`. If you configure builds per-project instead, add it to every one of them.

## Subproject Builds

### common/build.gradle

```groovy
plugins { id "java-library" }

dependencies {
    api "io.koraframework:common"   // just the annotations
}
```

### pet-api/build.gradle

```groovy
plugins { id "java-library" }

dependencies {
    api project(":common")

    api "io.koraframework:database-jdbc"
    api "io.koraframework:cache-caffeine"
    api "io.koraframework:resilient-kora"

    testAnnotationProcessor "io.koraframework:annotation-processors"
    testImplementation "io.koraframework:config-hocon"
}
```

Use `api` (not `implementation`) for the Kora modules a submodule's interface `extends` — the
assembly project's `@KoraApp` has to see those types to extend `PetModule` at all.

### app/build.gradle

```groovy
plugins { id "java"; id "application" }

dependencies {
    implementation project(":pet-api")
    implementation project(":vet-api")

    implementation "io.koraframework:config-hocon"
    implementation "io.koraframework:logging-logback"
    implementation "io.koraframework:json-common"

    testAnnotationProcessor "io.koraframework:annotation-processors"
}

application {
    applicationName = "application"
    mainClass = "com.example.app.Application"
    applicationDefaultJvmArgs = ["-Dfile.encoding=UTF-8"]
}
```

## The Sources

```java
// common/src/main/java/com/example/common/CommonModule.java
package com.example.common;

import io.koraframework.common.annotation.KoraSubmodule;

@KoraSubmodule
public interface CommonModule { }
```

An empty `@KoraSubmodule` interface is normal and useful: the interface is only the *handle*; the
generated companion carries everything the subproject declared.

```java
// pet-api/src/main/java/com/example/pet/PetModule.java
package com.example.pet;

import io.koraframework.cache.caffeine.CaffeineCacheModule;
import io.koraframework.common.annotation.KoraSubmodule;
import io.koraframework.database.jdbc.JdbcDatabaseModule;
import io.koraframework.resilient.ResilientModule;
import com.example.common.CommonModule;

@KoraSubmodule
public interface PetModule extends
        CommonModule,
        JdbcDatabaseModule,
        CaffeineCacheModule,
        ResilientModule { }
```

```java
// app/src/main/java/com/example/app/Application.java
package com.example.app;

import io.koraframework.application.graph.KoraApplication;
import io.koraframework.common.annotation.KoraApp;
import io.koraframework.config.hocon.HoconConfigModule;
import io.koraframework.json.common.JsonModule;
import io.koraframework.logging.logback.LogbackModule;
import com.example.pet.PetModule;
import com.example.vet.VetModule;

@KoraApp
public interface Application extends
        PetModule,
        VetModule,
        HoconConfigModule,
        LogbackModule,
        JsonModule {

    static void main(String[] args) {
        KoraApplication.run(ApplicationGraph::graph);
    }
}
```

A `@KoraSubmodule` may itself extend Kora modules; the assembly project inherits them and must not
repeat them.

## Kotlin Variant

```kotlin
// root build.gradle.kts
plugins {
    kotlin("jvm") version "2.4.20" apply false
    id("com.google.devtools.ksp") version "2.3.12" apply false
}

subprojects {
    apply(plugin = "org.jetbrains.kotlin.jvm")
    apply(plugin = "com.google.devtools.ksp")

    repositories {
        mavenCentral()
    }

    pluginManager.withPlugin("org.jetbrains.kotlin.jvm") {
        configure<org.jetbrains.kotlin.gradle.dsl.KotlinProjectExtension> {
            jvmToolchain {
                languageVersion.set(JavaLanguageVersion.of(25))
                vendor.set(JvmVendorSpec.ADOPTIUM)
            }
            sourceSets.named("main") { kotlin.srcDir("build/generated/ksp/main/kotlin") }
            sourceSets.named("test") { kotlin.srcDir("build/generated/ksp/test/kotlin") }
        }
    }

    dependencies {
        add("implementation", platform("io.koraframework:kora-bom:${property("koraVersion")}"))
        add("ksp", "io.koraframework:symbol-processors:${property("koraVersion")}")
    }
}
```

```kotlin
@KoraSubmodule
interface PetModule : CommonModule, JdbcDatabaseModule, CaffeineCacheModule, ResilientModule
```

```kotlin
@KoraApp
interface Application : PetModule, VetModule, HoconConfigModule, LogbackModule, JsonModule

fun main() {
    KoraApplication.run(ApplicationGraph::graph)
}
```

`ksp` is not covered by the BOM platform, so `symbol-processors` carries an explicit version. Add
`kspTest(...)` in any subproject with Kora annotations in its test sources.

## Test @KoraApp and `kora.app.submodule.enabled`

A common integration-test pattern is a test-source `@KoraApp` that extends the production one and
adds test-only components:

```java
// app/src/test/java/com/example/app/TestApplication.java
@KoraApp
public interface TestApplication extends Application {

    @Root
    @Component
    @Repository
    interface TestPetRepository extends JdbcRepository {
        @Query("DELETE FROM pets")
        void deleteAll();
    }
}
```

For this to see the production app's `@Component` classes, the **main** compilation must also emit a
submodule companion for the `@KoraApp` interface. That is exactly what the flag does:

```groovy
// app/build.gradle — Java
compileJava {
    options.compilerArgs += ["-Akora.app.submodule.enabled=true"]
}
```

```kotlin
// app/build.gradle.kts — Kotlin
ksp {
    arg("kora.app.submodule.enabled", "true")
}
```

Set it on the **main** compilation, not the test one — it changes what `compileJava`/`compileKotlin`
generates for `Application`, which the test compilation then consumes.

**This is a silent failure.** Without the flag the build still succeeds; you only get a warning:

```
Expected @KoraApp as SubModule, but Submodule implementation not found for: com.example.app.Application
Check that @KoraApp was generated with compile annotation processor option: -Akora.app.submodule.enabled=true
```

(KSP wording: `Check that @KoraApp was generated with KSP argument: kora.app.submodule.enabled=true`.)

The test graph then quietly loses every `@Component` declared in the production module, and the
failure surfaces much later as a missing dependency or a test asserting against a half-built graph.

The flag is only needed for this pattern. A plain single-project application does not want it.

## Key Rules

| Rule | Detail |
|---|---|
| Processor everywhere | every subproject with Kora annotations needs `annotationProcessor` / `ksp` |
| `@KoraSubmodule` only on interfaces | same constraint as `@Module` and `@KoraApp` |
| Assembly must `extends` | cross-subproject modules are never auto-discovered |
| Use `api`, not `implementation` | for the Kora modules a `@KoraSubmodule` extends |
| One `@KoraApp` per runnable artifact | a test `@KoraApp` in `src/test` is separate and fine |
| No cross-domain project dependencies | `pet-api` and `vet-api` both depend on `common`, never on each other |

## Common Mistakes

### Missing processor in a subproject

```groovy
// BAD — no processor, so PetModuleSubmoduleImpl is never generated
// pet-api/build.gradle
dependencies { api project(":common") }

// GOOD — inherit it from subprojects { }, or declare it here
dependencies {
    annotationProcessor "io.koraframework:annotation-processors"
    api project(":common")
}
```

Symptom: `Kora submodule was not generated yet: expected type: …SubmoduleImpl`.

### `@Module` instead of `@KoraSubmodule` across a boundary

```java
// BAD — @Module does not cross a compilation boundary
@Module
public interface PetModule { }

// GOOD
@KoraSubmodule
public interface PetModule { }
```

### `implementation` where `api` is required

```groovy
// BAD — the app cannot see JdbcDatabaseModule, so `PetModule extends JdbcDatabaseModule` breaks
implementation "io.koraframework:database-jdbc"

// GOOD
api "io.koraframework:database-jdbc"
```

### Test `@KoraApp` without the submodule flag

Covered above — add `-Akora.app.submodule.enabled=true` (or the KSP `arg`) to the **main**
compilation, and assert in a test that a production component is actually present.

### Business logic in the assembly project

Keep `@Component` classes in the domain subprojects. Anything declared in `app/` is only visible to
`app/`, which defeats the split.

## Related References

- [@KoraApp Reference](kora-app-component-reference.md) — bootstrap and the generated graph
- [Module Auto-Discovery Reference](module-auto-discovery-reference.md) — when `extends` is required
- [Component Registration Reference](component-registration-reference.md) — how types enter the graph
- [Graph Roots & Lifecycle Reference](lifecycle-reference.md) — `@Root` propagation through a submodule
