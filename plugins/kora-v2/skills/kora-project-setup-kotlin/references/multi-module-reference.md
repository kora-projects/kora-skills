# Multi-module Kora project setup (Kotlin)

How to split a Kotlin Kora 2.x service across several Gradle modules and let the
final application aggregate them with `@KoraApp` while feature modules expose a
precompiled graph fragment via `@KoraSubmodule`.

## Contents

- [When to split](#when-to-split)
- [Layout](#layout)
- [settings.gradle.kts](#settingsgradlekts)
- [Root build.gradle.kts (shared config for subprojects)](#root-buildgradlekts-shared-config-for-subprojects)
- [Feature module: @KoraSubmodule](#feature-module-korasubmodule)
- [App module: @KoraApp aggregator](#app-module-koraapp-aggregator)
- [Library modules that only declare config](#library-modules-that-only-declare-config)
- [Test graphs across modules](#test-graphs-across-modules)
- [Pitfalls](#pitfalls)

## When to split

- A single application module is fine for most services. Split only when you
  have genuine module boundaries (separate feature APIs, shared common code, an
  aggregating app).
- Use `@KoraSubmodule` so each feature module runs the symbol processors and
  generates its own partial graph at compile time; the `@KoraApp` module then
  links those fragments without reprocessing every component.

## Layout

```
my-app/
├── settings.gradle.kts          # includes every module
├── gradle.properties            # koraVersion, junitVersion
├── build.gradle.kts             # subprojects { ... } shared config
├── app/                         # @KoraApp aggregator + main()
├── pet-api/                     # @KoraSubmodule feature module
└── common/                      # @KoraSubmodule shared components
```

## settings.gradle.kts

```kotlin
plugins {
    id("org.gradle.toolchains.foojay-resolver-convention") version "1.0.0"
}

rootProject.name = "my-app"

include("common")
include("pet-api")
include("app")
```

## Root build.gradle.kts (shared config for subprojects)

Apply the Kotlin and KSP plugins to every subproject and give each the Kora BOM.

```kotlin
plugins {
    kotlin("jvm") version "2.4.20" apply false
    id("com.google.devtools.ksp") version "2.3.12" apply false
}

subprojects {
    apply(plugin = "org.jetbrains.kotlin.jvm")
    apply(plugin = "com.google.devtools.ksp")

    repositories { mavenCentral() }

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

        add("testImplementation", "io.koraframework:test-junit5")
    }
}
```

Two things about that `dependencies` block:

- **No `koraBom` configuration, no `extendsFrom`.** In a Kotlin module the BOM
  goes directly on `implementation`, and `ksp` carries an explicit version
  because it resolves against its own classpath. The `koraBom` + `extendsFrom`
  wiring belongs to Java modules only.
- `add("implementation", …)` rather than `implementation(…)`. Inside
  `subprojects { }` the typed configuration accessors are not generated, so the
  string-named `add(...)` form is what compiles.

If your mocking library runs in these modules, pin it for Java 25 class files:
MockK ≥ `1.14.9`, or — with `mockito-kotlin`, which drags an older
`mockito-core` along — pin `mockito-core` explicitly next to it.

## Feature module: @KoraSubmodule

A `@KoraSubmodule` interface lists the Kora `*Module` interfaces and the other
submodules the feature needs. KSP generates a partial graph for this module.

```kotlin
package com.example.pet

import io.koraframework.cache.caffeine.CaffeineCacheModule
import io.koraframework.common.annotation.KoraSubmodule
import io.koraframework.database.jdbc.JdbcDatabaseModule
import io.koraframework.resilient.ResilientModule
import com.example.common.CommonModule

@KoraSubmodule
interface PetModule : CommonModule, JdbcDatabaseModule, CaffeineCacheModule, ResilientModule
```

A `@KoraSubmodule` may be empty — it still exists to carry the module's own
`@Component` classes and any `@Tag` marker types into the aggregate graph:

```kotlin
package com.example.common

import io.koraframework.common.annotation.KoraSubmodule

@KoraSubmodule
interface CommonModule
```

Feature module `build.gradle.kts` is a plain library — no `application` plugin:

```kotlin
plugins {
    id("java-library")
}

dependencies {
    api(project(":common"))
    api("io.koraframework:database-jdbc")
    api("io.koraframework:cache-caffeine")
    api("io.koraframework:resilient-kora")
}
```

## App module: @KoraApp aggregator

The aggregator depends on the feature modules and extends their `@KoraSubmodule`
interfaces. The `application` plugin and `main()` live here.

```kotlin
plugins {
    id("application")
}

dependencies {
    implementation(project(":pet-api"))
    implementation("io.koraframework:http-server-undertow")
    implementation("io.koraframework:config-hocon")
    implementation("io.koraframework:json-common")
    implementation("io.koraframework:logging-logback")
}

application {
    mainClass.set("com.example.app.ApplicationKt")
}
```

```kotlin
package com.example.app

import io.koraframework.application.graph.KoraApplication
import io.koraframework.common.annotation.KoraApp
import io.koraframework.config.hocon.HoconConfigModule
import io.koraframework.http.server.undertow.UndertowPublicHttpServerModule
import io.koraframework.json.common.JsonModule
import io.koraframework.logging.logback.LogbackModule
import com.example.pet.PetModule

@KoraApp
interface Application :
    PetModule,
    HoconConfigModule,
    JsonModule,
    LogbackModule,
    UndertowPublicHttpServerModule

fun main() {
    KoraApplication.run { ApplicationGraph.graph() }
}
```

## Library modules that only declare config

A module that declares config interfaces with `@ConfigMapper` (the 2.x name for
1.x `@ConfigValueExtractor`) is processed by KSP too. Such a module **must apply
the KSP plugin and the processor itself**, even if it has no components:

```kotlin
plugins {
    id("org.jetbrains.kotlin.jvm")
    id("com.google.devtools.ksp")
    id("java-library")
}

dependencies {
    implementation(platform("io.koraframework:kora-bom:${property("koraVersion")}"))
    ksp("io.koraframework:symbol-processors:${property("koraVersion")}")
    implementation("io.koraframework:config-common")
}
```

In 1.x these modules often got away without a processor. After migration the
failure surfaces in the **consumer** as a missing generated `*Module`, which
sends you looking in the wrong project.

## Test graphs across modules

Add `kspTest("io.koraframework:symbol-processors:${property("koraVersion")}")`
to a module exactly when its `src/test` declares its own `@KoraApp`. A feature
module can have a test app built on its own submodule:

```kotlin
// pet-api/src/test/kotlin/com/example/pet/TestPetApplication.kt
@KoraApp
interface TestPetApplication : HoconConfigModule, PetModule {

    @Root
    fun root(petService: PetService): String = "root"
}
```

When a test `@KoraApp` instead **extends another `@KoraApp`** — the usual
`interface TestApplication : Application` in the app module — the *extended*
module has to be compiled with the submodule KSP argument:

```kotlin
ksp {
    arg("kora.app.submodule.enabled", "true")
}
```

That includes the cross-module case, where the test lives in one Gradle module
and the `@KoraApp` it extends is published by another: the argument goes on the
module that owns the extended `@KoraApp`. Without it KSP only warns —
`Expected @KoraApp as SubModule, but Submodule implementation not found for: …`
— and the parent's components are silently missing from the test graph.

## Pitfalls

- A module containing Kora annotations must run KSP itself
  (`ksp("io.koraframework:symbol-processors:${property("koraVersion")}")`) or no
  graph fragment is generated and the `@KoraApp` link fails.
- Use `api(...)` (not `implementation(...)`) for Kora module dependencies whose
  types a downstream `@KoraSubmodule` or `@KoraApp` extends, so those types stay
  on the compile classpath.
- Feature modules are libraries — do not apply the `application` plugin or define
  a `main()`; only the `@KoraApp` module does.
- Do not re-introduce a `koraBom` configuration with `extendsFrom` in a Kotlin
  build, and do not drop the explicit version from `ksp` / `kspTest`.
- After renaming packages, build once with `./gradlew clean` followed by
  `--no-build-cache`; generator output from the old package otherwise lingers in
  `build/generated` and produces unresolved references in files you never wrote.
