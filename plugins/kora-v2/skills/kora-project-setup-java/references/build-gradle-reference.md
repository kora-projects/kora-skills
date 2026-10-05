# build.gradle Reference (Java Kora 2.0)

Annotated walkthrough of every block in a Java Kora `build.gradle`, why it is
there, and how to tune it. Mirrors the reference apps in the upstream
[kora-examples](https://github.com/kora-projects/kora-examples) repository on the
**`migration/2.0`** branch — `guides/java/kora-java-guide-getting-started-app`
(minimal), `examples/java/kora-java-helloworld`, and `examples/java/kora-java-crud`
(full-stack reference module). The default branch of that repository is still 1.x;
so is the whole kora-docs site, which has no 2.0 content — read it as conceptual
background only, never as a 2.0 API authority.

## Contents

- [Plugins](#plugins)
- [Java toolchain and the Gradle JVM](#java-toolchain-and-the-gradle-jvm)
- [Repositories](#repositories)
- [The koraBom configuration](#the-korabom-configuration)
- [Dependencies](#dependencies)
- [application block](#application-block)
- [Compile and test tuning](#compile-and-test-tuning)
- [gradle.properties](#gradleproperties)
- [settings.gradle](#settingsgradle)
- [Gradle wrapper](#gradle-wrapper)
- [Docker packaging](#docker-packaging)
- [Fat jar with Shadow](#fat-jar-with-shadow)
- [Multi-module and library projects](#multi-module-and-library-projects)

## Plugins

```groovy
plugins {
    id "java"
    id "application"
}
```

`java` adds `compileJava`, `classes`, `test`, and the standard dependency
configurations. `application` adds the `run` task and distribution packaging
(`distTar`, `installDist`) for an executable service.

## Java toolchain and the Gradle JVM

```groovy
java {
    toolchain {
        languageVersion = JavaLanguageVersion.of(25)
        vendor = JvmVendorSpec.ADOPTIUM
    }
}
```

Two distinct requirements, often conflated:

**The bytecode floor is JVM 25.** Every Kora 2.0 artifact is compiled for Java 25,
and the published `kora-bom` pom declares `java.version` = `25`. A toolchain below
25 cannot read them. The reference apps pin `JavaLanguageVersion.of(25)`.

**The Gradle process needs its own JDK 25+ when a Kora artifact is on the
buildscript classpath.** The toolchain block governs `compileJava` and `test`; it
does not govern the JVM that runs Gradle. Contract-first OpenAPI projects put the
generator there:

```groovy
buildscript {
    repositories { mavenCentral() }
    dependencies {
        classpath("io.koraframework:openapi-generator:$koraVersion")
    }
}
```

That classpath is resolved by the Gradle JVM, so an older JDK fails during
configuration, before any compilation:

```
Dependency requires at least JVM runtime version 25. This build uses a Java 21 JVM.
> Run this build using a Java 25 or newer JVM.
```

Run Gradle on JDK 25 or newer — in practice, the latest GA feature release
available on the day you set the project up; derive that value then rather than
copying a frozen number out of any document. Set it with `JAVA_HOME`
(`JAVA_HOME=<jdk> ./gradlew projects` is the cheapest check). Do **not** commit
`org.gradle.java.home` in `gradle.properties` — that path is machine-specific.

**`--enable-preview` is not required by Kora.** It appears in Kora's own test task
and in the `kora-bom` Maven surefire `argLine`, not in any consumer build. Add it
only when your own code uses a preview API (for example `StructuredTaskScope`),
and then add it consistently to `javac`, `test`, `JavaExec` and the launcher.

## Repositories

```groovy
repositories {
    mavenCentral()
}
```

`io.koraframework:kora-bom:2.0.0.RC2` and the 100 modules it constrains are on
Maven Central; `mavenCentral()` alone resolves the whole build. Put `2.0.0.RC2`
in a new project.

`2.0.0-SNAPSHOT` is the framework's `master` development line, not a version to
put in a project. It resolves only from the snapshot repository, or after
building the framework locally with `publishToMavenLocal`:

```groovy
repositories {
    mavenCentral()
    maven { url = "https://central.sonatype.com/repository/maven-snapshots" }
}
```

The Kora example repository builds against the snapshot because it is developed
alongside the framework — that is a property of that repository, not advice for
consumers.

## The koraBom configuration

```groovy
configurations {
    koraBom
    annotationProcessor.extendsFrom(koraBom)
    compileOnly.extendsFrom(koraBom)
    implementation.extendsFrom(koraBom)
    testImplementation.extendsFrom(koraBom)
    testAnnotationProcessor.extendsFrom(koraBom)
}
```

A custom `koraBom` configuration carries the BOM platform. Every configuration
that needs aligned Kora versions extends it. The annotation-processor classpath
is **separate** from the application classpath, so `annotationProcessor` (and
`testAnnotationProcessor`) must extend `koraBom` explicitly — otherwise the
processor dependency resolves without a version and the build fails.

If the module also applies `java-library` and exposes Kora types in its public
API, add `api.extendsFrom(koraBom)` — that is what the multi-module reference
examples do.

## Dependencies

```groovy
dependencies {
    koraBom platform("io.koraframework:kora-bom:$koraVersion")

    annotationProcessor "io.koraframework:annotation-processors"

    implementation "io.koraframework:http-server-undertow"
    implementation "io.koraframework:config-hocon"
    implementation "io.koraframework:json-common"
    implementation "io.koraframework:logging-logback"

    testAnnotationProcessor "io.koraframework:annotation-processors"

    testImplementation platform("org.junit:junit-bom:$junitVersion")
    testImplementation "org.junit.jupiter:junit-jupiter"
    testImplementation "io.koraframework:test-junit5"
}
```

- `koraBom platform(...)` — the BOM. Declared once; pins every
  `io.koraframework:*` artifact. Never put a version on the individual modules.
- `annotation-processors` — the single aggregate processor. It transitively
  contains the graph, AOP, config, JSON, HTTP server/client, SOAP, database,
  Kafka, scheduling, resilient, cache, validation, logging, gRPC-client, S3 and
  Zeebe processors, so one entry covers every Kora annotation you may add later.
- The four runtime modules each back one `extends` in the `@KoraApp` interface.
  `json-common` also arrives transitively through `logging-logback`
  (`LoggingModule` builds JSON structured-argument mappers from `JsonWriter`);
  declare it explicitly anyway, because `JsonModule` is in the `extends` list and
  the build should not depend on someone else's transitive edge.
- `test-junit5` + `testAnnotationProcessor` enable `@KoraAppTest`. JUnit is
  aligned through `org.junit:junit-bom` at `6.1.3` in the reference apps.

Add further modules (database, kafka, grpc, s3, metrics, tracing) the same way:
one `implementation "io.koraframework:<artifact>"` plus the matching `*Module`
in the `@KoraApp extends` list. See `kora-project-dependencies` for the catalog.

### Third-party versions that must stay aligned

Kora 2.0 raised transitive library versions, and a pinned older version usually
fails at **runtime**, not at compile time:

| Library | Aligned with Kora 2.0 | Symptom when pinned lower |
|---|---|---|
| gRPC | `1.84.0` | `AbstractMethodError` while building the server |
| Flyway | `13.x`; `database-flyway` ships `flyway-core` only — add your dialect artifact yourself (e.g. `org.flywaydb:flyway-database-postgresql`) | `FlywayException: Unsupported Database` at startup |
| Mockito / Byte Buddy | Byte Buddy must understand class file version 69 (Java 25) | `IllegalArgumentException: Java 25 (69) is not supported by the current version of Byte Buddy` |
| Testcontainers | `2.x` renamed its modules to `testcontainers-postgresql`, `testcontainers-kafka`, `testcontainers-cassandra` | unresolved dependency |

Let the BOM pick the version whenever the artifact is a Kora one; for the rest,
prefer the version Kora already brings in over an older pin of your own.

## application block

```groovy
application {
    applicationName = "application"
    mainClass = "com.example.Application"
    applicationDefaultJvmArgs = ["-Dfile.encoding=UTF-8"]
}
```

`mainClass` points at the `@KoraApp` interface — its `static void main` calls
`KoraApplication.run(ApplicationGraph::graph)`. `./gradlew run` uses this entry.

Optional distribution packaging used by the reference apps:

```groovy
distTar {
    archiveFileName = "application.tar"
}
```

## Compile and test tuning

```groovy
tasks.withType(JavaCompile).configureEach {
    options.encoding = "UTF-8"
    options.incremental = true
    options.fork = false
}

test {
    jvmArgs += [
            "-XX:+TieredCompilation",
            "-XX:TieredStopAtLevel=1",
    ]
    useJUnitPlatform()
    testLogging {
        showStandardStreams = true
        events("passed", "skipped", "failed")
        exceptionFormat = "full"
    }
}
```

Kora supports incremental, multi-round annotation processing, so keep
`options.incremental = true`. `useJUnitPlatform()` is required for the JUnit 5
extension behind `@KoraAppTest`. The tiered-compilation flags speed up test JVM
startup.

**When a processor reports something impossible, force a clean round.** Under
incremental compilation a processor can read an interface from a class file whose
parameter names are synthetic, producing errors like
`SQL query placeholder has no matching method parameter: :id / Available parameters: - :arg0`
against perfectly correct source. `./gradlew <module>:clean` or `--rerun-tasks`
clears it; the message never points at the cause.

## gradle.properties

```properties
koraVersion=2.0.0.RC2
junitVersion=6.1.3

org.gradle.java.installations.auto-detect=true
org.gradle.java.installations.auto-download=true

org.gradle.daemon=true
org.gradle.parallel=true
org.gradle.caching=true

org.gradle.jvmargs=-Dfile.encoding=UTF-8 -Xmx2g
```

`koraVersion` is the single place the Kora version lives; `build.gradle`
references it as `$koraVersion`. `auto-detect` / `auto-download` let the
toolchain locate or fetch the requested JDK. `parallel` and `caching` speed up
multi-module builds.

The upstream example and template builds additionally carry
`--add-exports jdk.compiler/com.sun.tools.javac.*=ALL-UNNAMED` in
`org.gradle.jvmargs`. Those builds all apply the Spotless Eclipse formatter,
which needs them; no published Kora 2.0 artifact touches `com.sun.tools.javac`,
so a scaffold without Spotless does not need the flags. Add them if and when you
add Spotless.

## settings.gradle

```groovy
plugins {
    id "org.gradle.toolchains.foojay-resolver-convention" version "1.0.0"
}

rootProject.name = "kora-example"
```

The foojay resolver convention lets the Java toolchain download a JDK that is
not already installed, making the build reproducible across machines.

## Gradle wrapper

`gradle/wrapper/gradle-wrapper.properties`:

```properties
distributionUrl=https\://services.gradle.org/distributions/gradle-9.8.0-bin.zip
```

Gradle `9.8.0` is the wrapper the Kora framework itself builds with. Gradle 9 is also what the
GraalVM `native-build-tools` `1.1.7` plugin expects if you later add native-image
builds.

## Docker packaging

The reference apps run the `distTar` output on a JRE 25 base image:

```dockerfile
ARG RUN_IMAGE=eclipse-temurin:25-jre-jammy
FROM ${RUN_IMAGE}

ARG TARGET_DIR=/opt/app
ARG SOURCE_DIR=build/distributions

COPY $SOURCE_DIR/*.tar application.tar
RUN mkdir $TARGET_DIR && tar -xf application.tar -C $TARGET_DIR && rm application.tar

ARG DOCKER_USER=app
RUN groupadd -r $DOCKER_USER && useradd -rg $DOCKER_USER $DOCKER_USER
USER $DOCKER_USER

EXPOSE 8080/tcp
EXPOSE 8085/tcp
CMD [ "/opt/app/application/bin/application" ]
```

`8080` is the public API (`httpServer.port`), `8085` the system API
(`httpServer.system.port`, serving `/system/readiness`, `/system/liveness`,
`/metrics`).

## Fat jar with Shadow

The reference apps ship the `distTar` layout above, not a fat jar. If you build one with the
`com.gradleup.shadow` 9.x plugin, `mergeServiceFiles()` on its own is not enough:

```groovy
shadowJar {
    mergeServiceFiles()
    duplicatesStrategy = DuplicatesStrategy.INCLUDE   // let every META-INF/services copy reach the merge
}
```

Without `INCLUDE` the jar keeps only the first copy of each `META-INF/services/*` file — the
default duplicates strategy drops the others before the service-file transformer sees them. Flyway
registers its plugins through `ServiceLoader` files in both `flyway-core` and
`flyway-database-postgresql`, so the fat jar then fails at startup with a `NullPointerException`
in `DryRunConfigurationExtensionStub.getOrResolveOutputStream`. This was observed on a real
service build, not derived from Kora source — Kora itself does not touch the packaging.

## Multi-module and library projects

Repeat the `koraBom` block in every module that compiles Kora annotations —
configuration inheritance does not cross project boundaries. A module that only
contributes components to a parent graph uses `@KoraSubmodule` instead of
`@KoraApp`; the processor emits `<Type>SubmoduleImpl` for it unconditionally, and
the aggregating `@KoraApp` picks it up by `extends`.

Reusing a full `@KoraApp` as a submodule — the usual reason being an integration
test whose own `@KoraApp` extends the production application — is off by default.
Compile the module that declares the production `@KoraApp` with:

```groovy
compileJava {
    options.compilerArgs += ["-Akora.app.submodule.enabled=true"]
}
```

Without it the aggregate emits
`Expected @KoraApp as SubModule, but Submodule implementation not found for: …
Check that @KoraApp was generated with compile annotation processor option:
-Akora.app.submodule.enabled=true`. Submodule design itself → `kora-di-compile`.
