# Kora Compatibility Matrix

Java / Kotlin / KSP / Gradle versions that the Kora example apps build and run on.

## Contents

- [Recommended versions](#recommended-versions)
- [Java](#java)
- [Kotlin and KSP](#kotlin-and-ksp)
- [Gradle](#gradle)
- [Build plugins](#build-plugins)
- [Testing dependencies](#testing-dependencies)

---

## Recommended versions

These mirror the Kora example projects.

| Component | Version | Note |
|-----------|---------|------|
| Kora BOM (`kora-parent`) | 1.2.17 | Pin once; all Kora artifacts inherit it |
| Java | 21 | Toolchain used by the example apps |
| Kotlin | 1.9.25 | JVM target |
| KSP | 1.9.25-1.0.20 | Must match the Kotlin version |
| Gradle | 9+ | |

---

## Java

The example apps compile with a JDK 21 Adoptium toolchain. Kora targets modern Java and uses virtual threads for the HTTP server and JDBC, so JDK 21 or newer is the practical baseline. Set the version through the Gradle toolchain rather than `sourceCompatibility` so Gradle can download the JDK if needed:

```groovy
java {
    toolchain {
        languageVersion = JavaLanguageVersion.of(21)
        vendor = JvmVendorSpec.ADOPTIUM
    }
}
```

The `org.gradle.toolchains.foojay-resolver-convention` settings plugin lets Gradle resolve or download the requested JDK automatically.

---

## Kotlin and KSP

KSP is published per Kotlin version. The plugin version is `<kotlin>-<ksp>`, and it must match the Kotlin compiler version.

| Kotlin | KSP |
|--------|-----|
| 1.9.25 | 1.9.25-1.0.20 |
| 1.9.24 | 1.9.24-1.0.20 |
| 1.9.23 | 1.9.23-1.0.20 |

```kotlin
plugins {
    kotlin("jvm") version "1.9.25"
    id("com.google.devtools.ksp") version "1.9.25-1.0.20"
}
```

If the Kotlin compiler cannot target a newer JDK exactly, set `kotlin.jvm.target.validation.mode=warning` in `gradle.properties` so the fallback is a warning, not a build failure.

---

## Gradle

Use Gradle 9 or newer. Pin it through the wrapper:

```properties
# gradle/wrapper/gradle-wrapper.properties
distributionUrl=https\://services.gradle.org/distributions/gradle-9.0-bin.zip
```

---

## Build plugins

### Java

```groovy
plugins {
    id "java"
    id "application"
}
```

### Kotlin

```kotlin
plugins {
    application
    kotlin("jvm") version "1.9.25"
    id("com.google.devtools.ksp") version "1.9.25-1.0.20"
}
```

### Multi-module plugin management

```kotlin
// settings.gradle.kts
pluginManagement {
    repositories {
        gradlePluginPortal()
        mavenCentral()
    }
    plugins {
        kotlin("jvm") version "1.9.25"
        id("com.google.devtools.ksp") version "1.9.25-1.0.20"
    }
}

plugins {
    id("org.gradle.toolchains.foojay-resolver-convention") version "1.0.0"
}
```

---

## Testing dependencies

Kora's JUnit 5 extension is a Kora artifact (BOM-managed). JUnit and Testcontainers are external — version them yourself.

```groovy
dependencies {
    testImplementation "ru.tinkoff.kora:test-junit5"
    testImplementation "org.testcontainers:junit-jupiter:1.21.4"
    testImplementation "io.goodforgod:testcontainers-extensions-postgres:0.13.1"
}
```

---

## See Also

- [SKILL.md](../SKILL.md) — Quick start
- [bom-usage-reference.md](bom-usage-reference.md) — BOM setup
- [annotation-processors-reference.md](annotation-processors-reference.md) — Processors / KSP setup
