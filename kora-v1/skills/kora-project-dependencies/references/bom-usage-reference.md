# Kora BOM Usage Reference

How to use the Kora Bill of Materials (BOM) to align module and transitive versions.

## Contents

- [What the BOM is](#what-the-bom-is)
- [Setup](#setup)
- [What the BOM manages](#what-the-bom-manages)
- [Common mistakes](#common-mistakes)
- [Multi-module projects](#multi-module-projects)
- [Externally versioned dependencies](#externally-versioned-dependencies)
- [Verifying versions](#verifying-versions)
- [Upgrading Kora](#upgrading-kora)

---

## What the BOM is

The BOM is a platform POM that pins the version of every Kora module and of the third-party libraries Kora depends on. Import it once and reference Kora artifacts without versions.

Coordinates:

```
ru.tinkoff.kora:kora-parent:<koraVersion>
```

Pin `koraVersion` in `gradle.properties` so a single line controls the whole build:

```properties
koraVersion=1.2.17
```

---

## Setup

The `koraBom` configuration must be made a parent (`extendsFrom`) of every configuration that resolves Kora artifacts — including `annotationProcessor`/`ksp` — or the BOM will not constrain those classpaths.

### Java (build.gradle)

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
    api.extendsFrom(koraBom)
}

dependencies {
    koraBom platform("ru.tinkoff.kora:kora-parent:$koraVersion")
    annotationProcessor "ru.tinkoff.kora:annotation-processors"

    // Kora modules — no versions
    implementation "ru.tinkoff.kora:http-server-undertow"
    implementation "ru.tinkoff.kora:database-jdbc"
}
```

### Kotlin (build.gradle.kts)

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
    api.get().extendsFrom(koraBom)
    implementation.get().extendsFrom(koraBom)
}

val koraVersion: String by project
dependencies {
    koraBom(platform("ru.tinkoff.kora:kora-parent:$koraVersion"))
    ksp("ru.tinkoff.kora:symbol-processors")

    // Kora modules — no versions
    implementation("ru.tinkoff.kora:http-server-undertow")
    implementation("ru.tinkoff.kora:database-jdbc")
}
```

---

## What the BOM manages

### Kora module versions

Every `ru.tinkoff.kora:*` module resolves to `koraVersion`: `http-server-undertow`, `database-jdbc`, `kafka`, `micrometer-module`, and so on.

### Transitive libraries

The BOM also pins the versions of the third-party libraries Kora relies on:

| Library | Used by |
|---------|---------|
| Jackson | `json-module` |
| OkHttp | `http-client-ok` |
| Undertow | `http-server-undertow` |
| Micrometer | `micrometer-module` |
| OpenTelemetry | `opentelemetry-tracing-exporter-*` |
| Logback | `logging-logback` |
| HikariCP | `database-jdbc` |
| Kafka client | `kafka` |
| gRPC | `grpc-server`, `grpc-client` |
| Caffeine | `cache-caffeine` |
| Resilience4j | `resilient-kora` |

Do not override these versions by hand.

---

## Common mistakes

### Versioning a Kora module explicitly

```groovy
// WRONG
implementation "ru.tinkoff.kora:http-server-undertow:1.2.17"

// RIGHT
koraBom platform("ru.tinkoff.kora:kora-parent:$koraVersion")
implementation "ru.tinkoff.kora:http-server-undertow"
```

### Overriding a transitive version

```groovy
// WRONG — can break Kora at runtime
implementation "com.fasterxml.jackson.core:jackson-databind:2.17.0"
implementation "com.squareup.okhttp3:okhttp:5.0.0"

// RIGHT — let the BOM decide
koraBom platform("ru.tinkoff.kora:kora-parent:$koraVersion")
implementation "ru.tinkoff.kora:json-module"
implementation "ru.tinkoff.kora:http-client-ok"
```

### Forgetting extendsFrom for koraBom

```groovy
// WRONG — BOM never applies to the annotation processor classpath
configurations { koraBom }
dependencies {
    koraBom platform("ru.tinkoff.kora:kora-parent:$koraVersion")
    annotationProcessor "ru.tinkoff.kora:annotation-processors" // unconstrained -> fails to resolve
}

// RIGHT
configurations {
    koraBom
    annotationProcessor.extendsFrom(koraBom)
    implementation.extendsFrom(koraBom)
}
dependencies {
    koraBom platform("ru.tinkoff.kora:kora-parent:$koraVersion")
    annotationProcessor "ru.tinkoff.kora:annotation-processors"
}
```

---

## Multi-module projects

Apply the BOM in a `subprojects` block so every leaf module shares one version.

### Root build.gradle

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

### settings.gradle

```groovy
rootProject.name = "my-app"
include ":common"
include ":app"
```

---

## Externally versioned dependencies

These are not Kora artifacts and are not in the BOM — pin them yourself:

```groovy
dependencies {
    // JDBC drivers
    implementation "org.postgresql:postgresql:42.7.7"
    runtimeOnly    "com.mysql:mysql-connector-j:8.3.0"

    // Testing
    testImplementation "ru.tinkoff.kora:test-junit5"
    testImplementation "org.testcontainers:junit-jupiter:1.21.4"
    testImplementation "io.goodforgod:testcontainers-extensions-postgres:0.13.1"
    testImplementation "org.mockito:mockito-core:5.14.2"
    testImplementation "io.mockk:mockk:1.13.13"
}
```

Force a specific transitive version only when you have a concrete conflict:

```groovy
configurations.all {
    resolutionStrategy {
        force "com.fasterxml.jackson.core:jackson-databind:2.17.1"
    }
}
```

---

## Verifying versions

```bash
# Where a dependency came from
./gradlew dependencyInsight --dependency jackson-databind

# All Kora dependencies on the implementation classpath
./gradlew dependencies --configuration implementation | grep kora

# Full dependency tree
./gradlew dependencies --configuration implementation
```

---

## Upgrading Kora

Change one property — every module follows:

```properties
# gradle.properties
koraVersion=1.2.17
```

Refresh and rebuild after the bump:

```bash
./gradlew clean build --refresh-dependencies
```

---

## See Also

- [SKILL.md](../SKILL.md) — Quick start, module catalog
- [compatibility-matrix.md](compatibility-matrix.md) — Java / Kotlin / Gradle versions
- [core-modules-reference.md](core-modules-reference.md) — Core modules
- [annotation-processors-reference.md](annotation-processors-reference.md) — Processors / KSP setup
