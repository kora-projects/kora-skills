# build.gradle Reference (Java Kora)

Annotated walkthrough of every block in a Java Kora `build.gradle`, why it is
there, and how to tune it. Adapted from
`.kora-agent/kora-examples/guides/java/kora-java-guide-getting-started-app/build.gradle`
and `.kora-agent/kora-examples/examples/java/kora-java-helloworld/build.gradle`.

## Contents

- [Plugins](#plugins)
- [Java toolchain](#java-toolchain)
- [Repositories](#repositories)
- [The koraBom configuration](#the-korabom-configuration)
- [Dependencies](#dependencies)
- [application block](#application-block)
- [Compile and test tuning](#compile-and-test-tuning)
- [gradle.properties](#gradleproperties)
- [settings.gradle](#settingsgradle)

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

## Java toolchain

```groovy
import org.gradle.jvm.toolchain.JavaLanguageVersion
import org.gradle.jvm.toolchain.JvmVendorSpec

java {
    toolchain {
        languageVersion = JavaLanguageVersion.of(21)
        vendor = JvmVendorSpec.ADOPTIUM
    }
}
```

The toolchain decides which JDK compiles the code, independently of `JAVA_HOME`.
JDK 17 is the minimum Kora supports; 21 is recommended and matches the example
apps. Pair this with the foojay resolver in `settings.gradle` so Gradle can
download the requested JDK when it is not installed locally.

## Repositories

```groovy
repositories {
    mavenCentral()
}
```

Kora artifacts, Undertow, Logback, and their transitive dependencies are on
Maven Central.

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

## Dependencies

```groovy
dependencies {
    koraBom platform("ru.tinkoff.kora:kora-parent:1.2.17")

    annotationProcessor "ru.tinkoff.kora:annotation-processors"

    implementation "ru.tinkoff.kora:http-server-undertow"
    implementation "ru.tinkoff.kora:config-hocon"
    implementation "ru.tinkoff.kora:json-module"
    implementation "ru.tinkoff.kora:logging-logback"

    testAnnotationProcessor "ru.tinkoff.kora:annotation-processors"
    testImplementation "ru.tinkoff.kora:test-junit5"
}
```

- `koraBom platform(...)` — the BOM. Declared once; pins every
  `ru.tinkoff.kora:*` artifact. Never put a version on the individual modules.
- `annotation-processors` — the single mandatory processor; generates the
  graph, controllers, JSON readers/writers, and aspects.
- The four runtime modules each back one `extends` in the `@KoraApp` interface.
- `test-junit5` + `testAnnotationProcessor` enable `@KoraAppTest`.

Add further modules (database, kafka, grpc, s3, metrics, tracing) the same way:
one `implementation "ru.tinkoff.kora:<artifact>"` plus the matching `*Module`
in the `@KoraApp extends` list. See `kora-project-dependencies` for the catalog.

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

Optional distribution packaging used by the example apps:

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

## gradle.properties

```properties
org.gradle.java.installations.auto-detect=true
org.gradle.java.installations.auto-download=true

org.gradle.daemon=true
org.gradle.parallel=true
org.gradle.caching=true

org.gradle.jvmargs=-Dfile.encoding=UTF-8 -Xmx2g
```

`auto-detect` / `auto-download` let the toolchain locate or fetch the requested
JDK. `parallel` and `caching` speed up multi-module builds.

## settings.gradle

```groovy
plugins {
    id "org.gradle.toolchains.foojay-resolver-convention" version "1.0.0"
}

rootProject.name = "kora-example"
```

The foojay resolver convention lets the Java toolchain download a JDK that is
not already installed, making the build reproducible across machines.
