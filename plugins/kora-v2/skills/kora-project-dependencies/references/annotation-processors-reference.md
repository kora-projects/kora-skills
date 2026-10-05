# Annotation Processors & KSP Reference

Compile-time code generation for Kora 2.0: Java annotation processors and Kotlin KSP.

## Contents

- [Overview](#overview)
- [Java projects](#java-projects)
- [Kotlin projects](#kotlin-projects)
- [What the aggregate processors contain](#what-the-aggregate-processors-contain)
- [Per-domain processors](#per-domain-processors)
- [Multi-module projects](#multi-module-projects)
- [KSP 2 differences](#ksp-2-differences)
- [Troubleshooting](#troubleshooting)
- [Generated code locations](#generated-code-locations)

---

## Overview

Kora generates code at build time instead of using reflection or runtime proxies:

- DI container → `ApplicationGraph`
- HTTP routes → generated controller modules
- JSON → `*JsonReader` / `*JsonWriter`
- Repositories → `*RepositoryImpl`
- AOP aspects → `*_AopProxy`
- Config → `*_ConfigValueMapper` / generated `*Module`

Without the processor none of this exists and the build fails with missing-dependency errors. The
processor is mandatory: Java uses `io.koraframework:annotation-processors`, Kotlin uses KSP with
`io.koraframework:symbol-processors`.

---

## Java projects

```groovy
plugins {
    id "java"
    id "application"
}

repositories {
    mavenCentral()
}

configurations {
    koraBom
    annotationProcessor.extendsFrom(koraBom)
    compileOnly.extendsFrom(koraBom)
    implementation.extendsFrom(koraBom)
}

dependencies {
    koraBom platform("io.koraframework:kora-bom:$koraVersion")
    annotationProcessor "io.koraframework:annotation-processors"

    implementation "io.koraframework:json-common"
    implementation "io.koraframework:http-server-undertow"
}
```

Test sources that generate Kora code of their own — a test `@KoraApp`, a `@ConfigSource` declared in
`src/test`, a test-only `@Component` — need the processor on the test classpath too:

```groovy
configurations {
    testAnnotationProcessor.extendsFrom(koraBom)
}

dependencies {
    testAnnotationProcessor "io.koraframework:annotation-processors"
}
```

Compile options used by the reference examples:

```groovy
compileJava {
    options.encoding = "UTF-8"
    options.incremental = true
    options.fork = false
}
```

To let integration tests reach the generated graph as a submodule, the reference `crud` example adds
the processor option `-Akora.app.submodule.enabled=true`:

```groovy
compileJava {
    options.compilerArgs += ["-Akora.app.submodule.enabled=true"]
}
```

---

## Kotlin projects

KSP replaces `annotationProcessor`. Note the shape: **no `koraBom` configuration, no `extendsFrom`,
and an explicit version on the `ksp` dependency** — the BOM does not constrain the `ksp` configuration.

```kotlin
plugins {
    id("application")
    kotlin("jvm") version "2.4.20"
    id("com.google.devtools.ksp") version "2.3.12"
}

repositories {
    mavenCentral()
}

dependencies {
    implementation(platform("io.koraframework:kora-bom:${property("koraVersion")}"))
    ksp("io.koraframework:symbol-processors:${property("koraVersion")}")

    implementation("io.koraframework:json-common")
    implementation("io.koraframework:http-server-undertow")
}

kotlin {
    jvmToolchain {
        languageVersion.set(JavaLanguageVersion.of(25))
        vendor.set(JvmVendorSpec.ADOPTIUM)
    }
}
```

`kspTest(...)` goes in only when test sources really generate a graph. The KSP Gradle plugin already
registers its output directories as source roots — an explicit `kotlin.srcDir("build/generated/ksp/...")`
is not needed.

Processor options go through the `ksp` extension:

```kotlin
ksp {
    arg("kora.app.submodule.enabled", "true")
}
```

---

## What the aggregate processors contain

`annotation-processors` (Java) aggregates: `kora-app-`, `aop-`, `config-`, `json-`, `http-server-`,
`http-client-`, `soap-client-`, `database-`, `kafka-`, `scheduling-`, `resilient-`, `cache-`,
`validation-`, `logging-`, `grpc-client-`, `s3-client-` and `camunda-zeebe-worker-`
`-annotation-processor`, **plus `mapstruct-java-extension`**.

`symbol-processors` (Kotlin) aggregates the same domains in `-symbol-processor` form, **plus
`konvert-ksp-extension`**.

Consequences worth knowing:

- Mapper discovery is already on the processor classpath. Do not add `mapstruct-java-extension` or
  `konvert-ksp-extension` by hand.
- You still add the third-party half yourself, by language: Java → `org.mapstruct:mapstruct` plus
  `annotationProcessor "org.mapstruct:mapstruct-processor"`; Kotlin → `io.mcarle:konvert-api` plus
  `ksp("io.mcarle:konvert")`. Never MapStruct in a Kotlin module.

---

## Per-domain processors

Every domain also publishes its processor separately (`config-annotation-processor`,
`json-symbol-processor`, `database-annotation-processor`, …). A service does not need them — the
aggregate covers everything.

Use a single per-domain processor when a library module generates code for exactly one domain and you
want a minimal processor classpath. The most common real case is a library module that only declares
config interfaces: `@ConfigSource` / `@ConfigMapper` are processed at compile time, so the **library**
must apply the processor. If it does not, the failure surfaces in the **consumer** as a missing
generated `*Module`, which points at the wrong module entirely.

---

## Multi-module projects

### Root build.gradle (Java leaves)

```groovy
subprojects {
    apply plugin: "java"

    configurations {
        koraBom
        annotationProcessor.extendsFrom(koraBom)
        implementation.extendsFrom(koraBom)
    }

    dependencies {
        koraBom platform("io.koraframework:kora-bom:$koraVersion")
        annotationProcessor "io.koraframework:annotation-processors"
    }
}
```

### A Kotlin submodule with KSP

```kotlin
// submodule/build.gradle.kts
plugins {
    kotlin("jvm")
    id("com.google.devtools.ksp") version "2.3.12"
}

dependencies {
    implementation(platform("io.koraframework:kora-bom:${property("koraVersion")}"))
    ksp("io.koraframework:symbol-processors:${property("koraVersion")}")
    implementation(project(":common"))
}
```

A submodule that contributes components to a `@KoraApp` in another module marks its boundary with
`@KoraSubmodule` so its components are exported.

---

## KSP 2 differences

Kotlin 2.4.20 / KSP 2.3.12 replace the 1.9.x pair, and KSP 2 **no longer exports the `KspTask`
Gradle type**. Build logic that used it stops compiling:

```kotlin
// Broken under KSP 2 — the type is gone
import com.google.devtools.ksp.gradle.KspTask
tasks.withType<KspTask>().configureEach { /* ... */ }
```

Match tasks by name instead:

```kotlin
tasks.matching { it.name.startsWith("ksp") }.configureEach {
    dependsOn(openApiGenerateHttpServer)
}
// or, for one known task:
tasks.named("kspKotlin") { /* ... */ }
```

This matters most when a code generator (OpenAPI, protobuf) must run before KSP.

Kora 2.0 has no `kapt` step: Kotlin maps with Konvert, whose processor is a KSP processor, so KSP
alone is enough. MapStruct is Java-only — see [`kora-mapstruct`](../../kora-mapstruct/SKILL.md).

---

## Troubleshooting

### DI container / repository impl not generated

```bash
./gradlew clean classes
ls -la build/generated/sources/annotationProcessor/   # Java
ls -la build/generated/ksp/                            # Kotlin
```

Checklist:

- `annotation-processors` (Java) or `symbol-processors` (Kotlin) is on the processor classpath.
- Java only: `koraBom` is `extendsFrom` the `annotationProcessor` configuration.
- Kotlin only: the `ksp(...)` dependency carries an explicit version.
- The `@KoraApp` interface extends every required `*Module`.

### KSP does not run

```bash
./gradlew dependencies --configuration ksp
```

- The `com.google.devtools.ksp` plugin is applied.
- The KSP plugin version matches the Kotlin version (2.4.20 → 2.3.12).

### `SQL query placeholder has no matching method parameter: :id`

Available parameters are reported as `:arg0`, `:arg1`. The source is fine — an incremental build let
the database processor read the repository interface from a class file with synthetic parameter
names. Rerun the module clean:

```bash
./gradlew :module:compileJava --rerun-tasks
```

Any strange processor failure is worth retrying from a clean build before you start editing code.

### Phantom `package ru.tinkoff.kora... does not exist`

The failing files are under `build/generated/`, not in your sources. Generator tasks (OpenAPI,
protobuf, `wsdl2java`) do not delete previous output and the build-cache key does not account for a
changed `apiPackage`, so old 1.x-package files sit next to new ones.

```bash
./gradlew clean --continue
./gradlew classes testClasses --continue --no-build-cache
```

Never fix this by editing generated code.

### Stale generated classes after a refactor

```bash
rm -rf build/generated/
./gradlew clean build
```

---

## Generated code locations

| Processor | Output directory |
|---|---|
| Java annotation processing | `build/generated/sources/annotationProcessor/` |
| Kotlin KSP | `build/generated/ksp/` |
| OpenAPI generator | `build/generated/openapi/` |
| gRPC / protobuf | `build/generated/source/proto/` |

---

## See Also

- [SKILL.md](../SKILL.md) — quick start
- [artifact-catalog.md](artifact-catalog.md) — every published artifact, including per-domain processors
- [bom-usage-reference.md](bom-usage-reference.md) — BOM wiring for both languages
- [compatibility-matrix.md](compatibility-matrix.md) — JDK / Kotlin / KSP / Gradle versions
- [`kora-project-setup-java/SKILL.md`](../../kora-project-setup-java/SKILL.md) — Java project setup
- [`kora-project-setup-kotlin/SKILL.md`](../../kora-project-setup-kotlin/SKILL.md) — Kotlin project setup
