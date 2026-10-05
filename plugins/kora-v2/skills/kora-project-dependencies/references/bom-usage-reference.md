# Kora BOM Usage Reference

How to import `io.koraframework:kora-bom` so every Kora module and every third-party library Kora
pins resolves to one consistent set of versions.

## Contents

- [What the BOM is](#what-the-bom-is)
- [Java setup: the koraBom configuration](#java-setup-the-korabom-configuration)
- [Kotlin setup: BOM on implementation](#kotlin-setup-bom-on-implementation)
- [Why the two languages differ](#why-the-two-languages-differ)
- [What the BOM manages](#what-the-bom-manages)
- [Common mistakes](#common-mistakes)
- [Multi-module projects](#multi-module-projects)
- [Externally versioned dependencies](#externally-versioned-dependencies)
- [Verifying versions](#verifying-versions)
- [Upgrading Kora](#upgrading-kora)

---

## What the BOM is

A `java-platform` POM that constrains the version of every Kora module. Import it once and list Kora
artifacts without versions.

```
io.koraframework:kora-bom:<koraVersion>
```

`ru.tinkoff.kora:kora-parent` does not exist in 2.0.

Pin the version in `gradle.properties`:

```properties
koraVersion=2.0.0.RC2
```

**`2.0.0.RC2` is published on Maven Central**, so a release build needs nothing but
`mavenCentral()`:

```groovy
repositories {
    mavenCentral()
}
```

`2.0.0-SNAPSHOT` is the `master` development line, not a version to pin in a new project. If you
deliberately track it, it also needs the snapshot repository (or a local `publishToMavenLocal`):

```groovy
repositories {
    mavenCentral()
    maven { url = "https://central.sonatype.com/repository/maven-snapshots" }
}
```

Check <https://github.com/kora-projects/kora/releases> before moving to a newer release.

---

## Java setup: the koraBom configuration

Java declares a dedicated `koraBom` configuration and makes every configuration that resolves Kora
artifacts extend it — **including `annotationProcessor` and `testAnnotationProcessor`**. Without that
the processor classpath is unconstrained and `annotation-processors` fails to resolve.

```groovy
plugins {
    id "java"
    id "application"
}

java {
    toolchain {
        languageVersion = JavaLanguageVersion.of(25)
        vendor = JvmVendorSpec.ADOPTIUM
    }
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

    // Kora modules — no versions
    implementation "io.koraframework:http-server-undertow"
    implementation "io.koraframework:database-jdbc"
    implementation "io.koraframework:json-common"
    implementation "io.koraframework:config-hocon"
    implementation "io.koraframework:logging-logback"

    testAnnotationProcessor "io.koraframework:annotation-processors"
    testImplementation "io.koraframework:test-junit5"
}
```

`testAnnotationProcessor` is needed only when test sources themselves generate Kora code — a test
`@KoraApp`, a test-only `@Component`, a `@ConfigSource` declared in `src/test`.

---

## Kotlin setup: BOM on implementation

Kotlin does **not** create a `koraBom` configuration and does **not** use `extendsFrom`. The BOM goes
straight on `implementation`, and the KSP processor carries an explicit version.

```kotlin
plugins {
    id("application")
    kotlin("jvm") version "2.4.20"
    id("com.google.devtools.ksp") version "2.3.12"
}

dependencies {
    implementation(platform("io.koraframework:kora-bom:${property("koraVersion")}"))
    ksp("io.koraframework:symbol-processors:${property("koraVersion")}")

    implementation("io.koraframework:http-server-undertow")
    implementation("io.koraframework:database-jdbc")
    implementation("io.koraframework:json-common")
    implementation("io.koraframework:config-hocon")
    implementation("io.koraframework:logging-logback")

    testImplementation("io.koraframework:test-junit5")
}

kotlin {
    jvmToolchain {
        languageVersion.set(JavaLanguageVersion.of(25))
        vendor.set(JvmVendorSpec.ADOPTIUM)
    }
}
```

`kspTest("io.koraframework:symbol-processors:${property("koraVersion")}")` is added only when test
sources need graph generation of their own.

---

## Why the two languages differ

The two shapes are deliberate, not an inconsistency to "fix":

- A `platform` dependency on `implementation` does not reach Java's `annotationProcessor`
  configuration, which is why Java needs the separate `koraBom` configuration wired with
  `extendsFrom`.
- The `ksp` configuration is not a child of `implementation` either — but rather than wiring it,
  Kotlin gives the processor an explicit version. Fewer moving parts, and it survives KSP plugin
  changes.

Do not port the Java `koraBom` + `extendsFrom` block into a Kotlin build script, and do not drop the
explicit `ksp(...)` version in favour of the BOM: the BOM is not applied to `ksp`, so a versionless
`ksp("io.koraframework:symbol-processors")` fails to resolve.

---

## What the BOM manages

**Kora module versions.** Every `io.koraframework:*` and `io.koraframework.experimental:*` module
resolves to `koraVersion`.

**Third-party libraries Kora ships.** These arrive transitively at the version Kora built against —
do not pin them yourself:

| Library | Arrives with |
|---|---|
| Jackson (`tools.jackson.core`) | `json-common`, `jackson-module` |
| OkHttp | `http-client-ok` |
| Apache HttpClient 5 | `http-client-apache` |
| Undertow, JBoss Threads/Logging | `http-server-undertow` |
| Micrometer + Prometheus registry, OpenTelemetry API | `micrometer-module` |
| Logback | `logging-logback` |
| HikariCP | `database-jdbc` |
| `org.apache.cassandra:java-driver-core` | `database-cassandra` |
| `org.flywaydb:flyway-core` | `database-flyway` |
| `org.liquibase:liquibase-core` | `database-liquibase` |
| Kafka clients | `kafka` |
| gRPC (`grpc-stub`, `grpc-okhttp`) | `grpc-server`, `grpc-client` |
| Caffeine | `cache-caffeine` |
| Lettuce, Netty | `redis-lettuce`, `cache-redis-lettuce` |
| Quartz | `scheduling-quartz` |
| AWS SDK S3 | `s3-client-aws` |
| JUnit 5 | `test-junit5` |

Resilience is Kora's own implementation — `resilient-kora` brings no Resilience4j.

---

## Common mistakes

### Versioning a Kora module explicitly

```groovy
// WRONG
implementation "io.koraframework:http-server-undertow:2.0.0.RC2"

// RIGHT
koraBom platform("io.koraframework:kora-bom:$koraVersion")
implementation "io.koraframework:http-server-undertow"
```

The one deliberate exception is the Kotlin `ksp(...)` line, which needs its version.

### Overriding a transitive version

```groovy
// WRONG — can break Kora at runtime
implementation "tools.jackson.core:jackson-databind:3.0.0"
implementation "com.squareup.okhttp3:okhttp:5.0.0"

// RIGHT — let the BOM decide
implementation "io.koraframework:json-common"
implementation "io.koraframework:http-client-ok"
```

### Forgetting extendsFrom in a Java build

```groovy
// WRONG — BOM never applies to the annotation processor classpath
configurations { koraBom }
dependencies {
    koraBom platform("io.koraframework:kora-bom:$koraVersion")
    annotationProcessor "io.koraframework:annotation-processors" // unconstrained -> fails to resolve
}
```

### Carrying the 1.x coordinates over

`kora-parent`, `json-module`, `cache-redis`, `http-client-async`, `database-r2dbc`,
`database-vertx`, `s3-client-minio` and `mapstruct-extension` are all gone. See
[artifact-catalog.md](artifact-catalog.md#renamed-and-removed-since-1x).

### Trusting the Maven Central directory listing

Browsing `repo1.maven.org/maven2/io/koraframework/` is **not** a way to check what 2.0 publishes.
The listing is cumulative, so 1.x and alpha leftovers are still visible there — `kora-parent`,
`cache-redis`, `declarative-logging-annotation-processor`, `declarative-logging-symbol-processor`,
`scheduling-ksp`, `experimental/s3-client`. None of them is constrained by the `2.0.0.RC2` BOM.

**And a resolved dependency is not proof either.** `io.koraframework:kora-parent` and
`io.koraframework:cache-redis` are published at `2.0.0.alpha5` and `2.0.0.alpha6`. A blind group-only
rename that keeps the old artifact id therefore does not fail loudly — at an alpha version it
resolves and quietly pins a **pre-release BOM** from before the 2.0 renames. `kora-parent` has no
`2.0.0.RC*` version, so whether you get a 404 or a silently wrong BOM depends only on the version string
that happened to survive the rename. Rename the **artifact**, not just the group.

The authoritative list is what `kora-bom` constrains — see
[artifact-catalog.md](artifact-catalog.md). To check a single coordinate:

```bash
curl -s https://repo1.maven.org/maven2/io/koraframework/<artifact>/maven-metadata.xml
```

and look for a `2.0.x` entry, not merely for the directory.

### Wrong group for the S3 artifacts

```groovy
implementation "io.koraframework:s3-client-aws"                  // correct — NOT experimental
implementation "io.koraframework.experimental:s3-client-kora"    // correct — IS experimental
```

---

## Multi-module projects

Apply the BOM in a `subprojects` block so every leaf module shares one version.

### Root build.gradle (Java leaves)

```groovy
subprojects {
    apply plugin: "java"

    configurations {
        koraBom
        annotationProcessor.extendsFrom(koraBom)
        compileOnly.extendsFrom(koraBom)
        implementation.extendsFrom(koraBom)
        testImplementation.extendsFrom(koraBom)
    }

    dependencies {
        koraBom platform("io.koraframework:kora-bom:$koraVersion")
        annotationProcessor "io.koraframework:annotation-processors"
    }
}
```

### settings.gradle

```groovy
rootProject.name = "my-app"
include ":common"
include ":app"
```

A module that contributes components to a `@KoraApp` living in another module marks its boundary
with `@KoraSubmodule`. A library module that only declares `@ConfigSource`/`@ConfigMapper`
interfaces still needs the processor: without it the consumer sees a missing generated `*Module`,
and the error points at the consumer rather than the library.

---

## Externally versioned dependencies

Not Kora artifacts, not in the BOM — the app pins them. Versions and the failure each mismatch
produces are in [compatibility-matrix.md](compatibility-matrix.md#externally-versioned-dependencies).

```groovy
dependencies {
    // JDBC driver — database-jdbc ships Hikari, never a driver (database-jdbc-postgres brings one)
    implementation "org.postgresql:postgresql:42.7.13"

    // Flyway dialect — database-flyway ships flyway-core only
    implementation "org.flywaydb:flyway-database-postgresql:13.9.0"

    // Mocking — test-junit5 declares Mockito/MockK compileOnly
    testImplementation "org.mockito:mockito-core:5.24.0"   // Java
    testImplementation "io.mockk:mockk:1.14.11"            // Kotlin

    testImplementation "io.koraframework:test-junit5"
    testImplementation "org.testcontainers:testcontainers-postgresql:2.0.5"
}
```

Force a transitive version only against a concrete, reproduced conflict:

```groovy
configurations.configureEach {
    resolutionStrategy {
        force "io.grpc:grpc-netty:1.84.0"
    }
}
```

---

## Verifying versions

```bash
# Where a dependency came from and why it resolved to that version
./gradlew dependencyInsight --dependency jackson-core

# Every Kora dependency on the compile classpath
./gradlew dependencies --configuration compileClasspath | grep koraframework

# Confirm the processor classpath actually got the BOM
./gradlew dependencies --configuration annotationProcessor   # Java
./gradlew dependencies --configuration ksp                    # Kotlin
```

---

## Upgrading Kora

Change one property; every module follows.

```properties
koraVersion=2.0.0.RC2
```

```bash
./gradlew clean build --refresh-dependencies
```

After a group rename (`ru.tinkoff.kora` → `io.koraframework`) the first build also needs the build
cache out of the way — generator tasks (OpenAPI, protobuf, `wsdl2java`) do not delete their previous
output, so one source set ends up holding both the old and the new package:

```bash
./gradlew clean --continue
./gradlew classes testClasses --continue --no-build-cache
```

Symptom without it: hundreds of `package ru.tinkoff.kora... does not exist` errors in files that are
not in your sources — every path leads into `build/generated/`. Never edit generated code to fix it.

---

## See Also

- [SKILL.md](../SKILL.md) — quick start, module picking
- [artifact-catalog.md](artifact-catalog.md) — every published artifact
- [annotation-processors-reference.md](annotation-processors-reference.md) — processors / KSP setup
- [compatibility-matrix.md](compatibility-matrix.md) — JDK, Kotlin/KSP, Gradle, third-party versions
- [core-modules-reference.md](core-modules-reference.md) — core modules
