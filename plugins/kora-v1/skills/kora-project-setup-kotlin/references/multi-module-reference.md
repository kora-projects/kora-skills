# Multi-module Kora project setup (Kotlin)

How to split a Kotlin Kora service across several Gradle modules and let the
final application aggregate them with `@KoraApp` while feature modules expose a
precompiled graph fragment via `@KoraSubmodule`.

## Contents

- [When to split](#when-to-split)
- [Layout](#layout)
- [settings.gradle.kts](#settingsgradlekts)
- [Root build.gradle.kts (shared config for subprojects)](#root-buildgradlekts-shared-config-for-subprojects)
- [Feature module: @KoraSubmodule](#feature-module-korasubmodule)
- [App module: @KoraApp aggregator](#app-module-koraapp-aggregator)
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
├── gradle.properties
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

Apply the Kotlin and KSP plugins to every subproject and feed the Kora BOM into
each. Adapted from `.kora-agent/kora-examples/examples/kotlin/kora-kotlin-crud-submodule/build.gradle.kts`.

```kotlin
plugins {
    kotlin("jvm") version "1.9.25" apply false
    id("com.google.devtools.ksp") version "1.9.25-1.0.20" apply false
}

subprojects {
    apply(plugin = "org.jetbrains.kotlin.jvm")
    apply(plugin = "com.google.devtools.ksp")

    repositories { mavenCentral() }

    pluginManager.withPlugin("org.jetbrains.kotlin.jvm") {
        configure<org.jetbrains.kotlin.gradle.dsl.KotlinProjectExtension> {
            jvmToolchain {
                languageVersion.set(JavaLanguageVersion.of(21))
                vendor.set(JvmVendorSpec.ADOPTIUM)
            }
            sourceSets.named("main") { kotlin.srcDir("build/generated/ksp/main/kotlin") }
            sourceSets.named("test") { kotlin.srcDir("build/generated/ksp/test/kotlin") }
        }
    }

    val koraBom: Configuration by configurations.creating
    configurations {
        listOf("ksp", "kspTest", "compileOnly", "api", "implementation", "testImplementation")
            .forEach { name -> named(name) { extendsFrom(koraBom) } }
    }

    dependencies {
        koraBom(platform("ru.tinkoff.kora:kora-parent:1.2.17"))
        add("ksp", "ru.tinkoff.kora:symbol-processors")
        add("testImplementation", "ru.tinkoff.kora:test-junit5")
    }
}
```

## Feature module: @KoraSubmodule

A `@KoraSubmodule` interface lists the Kora `*Module` interfaces and your own
components the feature needs. KSP generates a partial graph for this module.
Adapted from `.kora-agent/kora-examples/examples/kotlin/kora-kotlin-crud-submodule/kora-kotlin-crud-submodule-pet-api/src/main/kotlin/.../PetModule.kt`.

```kotlin
package com.example.pet

import ru.tinkoff.kora.cache.caffeine.CaffeineCacheModule
import ru.tinkoff.kora.common.KoraSubmodule
import ru.tinkoff.kora.database.jdbc.JdbcDatabaseModule

@KoraSubmodule
interface PetModule : JdbcDatabaseModule, CaffeineCacheModule
```

Feature module `build.gradle.kts` is a plain library — no `application` plugin:

```kotlin
plugins {
    id("java-library")
}

dependencies {
    api(project(":common"))
    api("ru.tinkoff.kora:database-jdbc")
    api("ru.tinkoff.kora:cache-caffeine")
}
```

## App module: @KoraApp aggregator

The aggregator depends on the feature modules and extends their generated
submodule interfaces (the processor exposes `PetModule` as a graph fragment).
The `application` plugin and `main()` live here.

```kotlin
plugins {
    id("application")
}

dependencies {
    implementation(project(":pet-api"))
    implementation("ru.tinkoff.kora:http-server-undertow")
    implementation("ru.tinkoff.kora:config-hocon")
    implementation("ru.tinkoff.kora:logging-logback")
}

application {
    mainClass.set("com.example.app.ApplicationKt")
}
```

```kotlin
package com.example.app

import ru.tinkoff.kora.application.graph.KoraApplication
import ru.tinkoff.kora.common.KoraApp
import ru.tinkoff.kora.config.hocon.HoconConfigModule
import ru.tinkoff.kora.http.server.undertow.UndertowHttpServerModule
import ru.tinkoff.kora.logging.logback.LogbackModule
import com.example.pet.PetModule

@KoraApp
interface Application :
    HoconConfigModule,
    LogbackModule,
    UndertowHttpServerModule,
    PetModule

fun main() {
    KoraApplication.run { ApplicationGraph.graph() }
}
```

## Pitfalls

- A feature module must run KSP itself (`ksp("ru.tinkoff.kora:symbol-processors")`)
  or no submodule graph is generated and the `@KoraApp` link fails.
- Use `api(...)` (not `implementation(...)`) for Kora module dependencies you
  expect downstream modules to extend, so their types stay on the compile classpath.
- Feature modules are libraries — do not apply the `application` plugin or define
  a `main()`; only the `@KoraApp` module does.
