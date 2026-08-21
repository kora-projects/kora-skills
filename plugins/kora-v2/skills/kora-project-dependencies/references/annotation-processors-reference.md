# Annotation Processors & KSP Reference

Setting up compile-time code generation for Java (annotation processors) and Kotlin (KSP).

## Contents

- [Overview](#overview)
- [Java projects](#java-projects)
- [Kotlin projects](#kotlin-projects)
- [KSP version matrix](#ksp-version-matrix)
- [Multi-module projects](#multi-module-projects)
- [Troubleshooting](#troubleshooting)
- [Generated code locations](#generated-code-locations)

---

## Overview

Kora generates code at build time instead of using reflection or runtime proxies:

- DI container → `*ComponentImpl` / `ApplicationGraph`
- HTTP routes → `*Module`-generated routers
- JSON → `*JsonReader` / `*JsonWriter`
- Repositories → `*RepositoryImpl`
- AOP aspects → `*_AopProxy`

Without the processor, none of this is generated and the build fails with missing-dependency errors. The processor is mandatory: Java uses `annotation-processors`, Kotlin uses KSP with `symbol-processors`.

---

## Java projects

```groovy
plugins {
    id "java"
    id "application"
}

configurations {
    koraBom
    annotationProcessor.extendsFrom(koraBom)
    compileOnly.extendsFrom(koraBom)
    implementation.extendsFrom(koraBom)
}

dependencies {
    koraBom platform("ru.tinkoff.kora:kora-parent:$koraVersion")
    annotationProcessor "ru.tinkoff.kora:annotation-processors"

    implementation "ru.tinkoff.kora:json-module"
    implementation "ru.tinkoff.kora:http-server-undertow"
}
```

If component tests generate code (for example a `@KoraAppTest` test application), also wire the test processor:

```groovy
configurations {
    testAnnotationProcessor.extendsFrom(koraBom)
}

dependencies {
    testAnnotationProcessor "ru.tinkoff.kora:annotation-processors"
}
```

Recommended compile options:

```groovy
compileJava {
    options.encoding = "UTF-8"
    options.incremental = true
    options.fork = false
}
```

---

## Kotlin projects

KSP replaces the Java `annotationProcessor`. Apply the KSP Gradle plugin and add `symbol-processors`.

```kotlin
plugins {
    application
    kotlin("jvm") version "1.9.25"
    id("com.google.devtools.ksp") version "1.9.25-1.0.20"
}

val koraBom: Configuration by configurations.creating
configurations {
    ksp.get().extendsFrom(koraBom)
    compileOnly.get().extendsFrom(koraBom)
    implementation.get().extendsFrom(koraBom)
}

dependencies {
    koraBom(platform("ru.tinkoff.kora:kora-parent:$koraVersion"))
    ksp("ru.tinkoff.kora:symbol-processors")

    implementation("ru.tinkoff.kora:json-module")
    implementation("ru.tinkoff.kora:http-server-undertow")
}
```

Register the KSP output directory so the IDE and compiler see the generated Kotlin:

```kotlin
kotlin {
    jvmToolchain {
        languageVersion.set(JavaLanguageVersion.of(21))
        vendor.set(JvmVendorSpec.ADOPTIUM)
    }
    sourceSets.main { kotlin.srcDir("build/generated/ksp/main/kotlin") }
    sourceSets.test { kotlin.srcDir("build/generated/ksp/test/kotlin") }
}
```

---

## KSP version matrix

The KSP plugin version must match the Kotlin version exactly (the suffix `-1.0.x` is the KSP release).

| Kotlin | KSP | Status |
|--------|-----|--------|
| 1.9.25 | 1.9.25-1.0.20 | Recommended |
| 1.9.24 | 1.9.24-1.0.20 | Supported |
| 1.9.23 | 1.9.23-1.0.20 | Supported |

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
        koraBom platform("ru.tinkoff.kora:kora-parent:$koraVersion")
        annotationProcessor "ru.tinkoff.kora:annotation-processors"
    }
}
```

### A Kotlin submodule with KSP

```kotlin
// submodule/build.gradle.kts
plugins {
    kotlin("jvm")
    id("com.google.devtools.ksp") version "1.9.25-1.0.20"
}

val koraBom: Configuration by configurations.creating
configurations {
    ksp.get().extendsFrom(koraBom)
    implementation.get().extendsFrom(koraBom)
}

dependencies {
    koraBom(platform("ru.tinkoff.kora:kora-parent:$koraVersion"))
    ksp("ru.tinkoff.kora:symbol-processors")
    implementation(project(":common"))
}
```

When a submodule contributes components to a `@KoraApp` in another module, mark its boundary with `@KoraSubmodule` so its components are exported.

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
- `koraBom` is `extendsFrom` the `annotationProcessor`/`ksp` configuration.
- The `@KoraApp` interface `extends`/implements every required `*Module`.

### KSP does not run

```bash
./gradlew dependencies --configuration ksp
```

- The `com.google.devtools.ksp` plugin is applied.
- The KSP version matches the Kotlin version.

### Stale generated classes after a refactor

```bash
rm -rf build/generated/
./gradlew clean build
```

---

## Generated code locations

| Processor | Output directory |
|-----------|------------------|
| Java annotation processing | `build/generated/sources/annotationProcessor/` |
| Kotlin KSP | `build/generated/ksp/` |
| OpenAPI generator | `build/generated/openapi/` |
| gRPC / protobuf | `build/generated/proto/` |

---

## See Also

- [SKILL.md](../SKILL.md) — Quick start
- [compatibility-matrix.md](compatibility-matrix.md) — Version matrix
- [bom-usage-reference.md](bom-usage-reference.md) — BOM setup
- [`kora-project-setup-java/SKILL.md`](../../kora-project-setup-java/SKILL.md) — Java project setup
- [`kora-project-setup-kotlin/SKILL.md`](../../kora-project-setup-kotlin/SKILL.md) — Kotlin project setup
