---
name: kora-project-setup-java
description: "Scaffold a new Java Kora 2.0 service (Gradle) — io.koraframework:kora-bom, annotationProcessor io.koraframework:annotation-processors, the koraBom configuration, @KoraApp root and KoraApplication.run(ApplicationGraph::graph). Use when starting a Java Kora project, writing build.gradle/settings.gradle/gradle.properties, or fixing \"annotation processor did not run\", \"cannot find symbol ApplicationGraph\", or \"Dependency requires at least JVM runtime version 25\". For Kotlin see kora-project-setup-kotlin."
license: Apache-2.0
metadata:
  version: "0.1.0"
  kora-version: "2.x"
---

# Kora Project Setup — Java

> **Kora sub-skill — obey the [kora-v2 meta rules](../../SKILL.md) on every task:** **R0** ground the workspace on Kora 2.0 refs before starting (framework source at tag `2.0.0.RC2` + `kora-examples` at `migration/2.0` + Kora 2.0 docs at koraframework.io/v2, which trail the source; 1.x `kora-docs` pages are never an authority) · **R1** read this sub-skill before writing code · **R2** Kora 2.0 APIs only — no Spring/Micronaut/Quarkus, no Kora 1.x APIs, no invented annotations or config keys · **R3** journal any incorrect Kora usage. Add comments/Javadoc only if asked.

Scaffold a minimal, compilable Kora 2.0 service in Java. Kora is a compile-time
framework: its annotation processor generates `ApplicationGraph`, controllers,
JSON readers/writers and aspects during `compileJava`. If the processor is not
wired into the Gradle build, **nothing is generated and nothing works**. This
skill gets that wiring right the first time.

| | |
|---|---|
| **Group** | `io.koraframework` (everything under `experimental/` publishes as `io.koraframework.experimental`) |
| **BOM** | `io.koraframework:kora-bom:2.0.0.RC2` — on Maven Central; plain `mavenCentral()` resolves it |
| **Processor** | `io.koraframework:annotation-processors` (also as `testAnnotationProcessor`) |
| **JDK** | **25 or newer** — Kora 2.0 artifacts are compiled for JVM 25; the reference apps pin toolchain `25` |
| **Gradle** | wrapper `9.8.0` — the version the framework itself builds with |

---

## Quick Start

Smallest build that compiles and runs an HTTP endpoint.

`gradle.properties`:

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

`build.gradle`:

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

repositories {
    mavenCentral()
}

configurations {
    koraBom
    annotationProcessor.extendsFrom(koraBom)
    compileOnly.extendsFrom(koraBom)
    implementation.extendsFrom(koraBom)
    testImplementation.extendsFrom(koraBom)
    testAnnotationProcessor.extendsFrom(koraBom)
}

dependencies {
    koraBom platform("io.koraframework:kora-bom:$koraVersion")

    // Mandatory: without this nothing is generated.
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

application {
    mainClass = "com.example.Application"
}
```

`settings.gradle`:

```groovy
plugins {
    id "org.gradle.toolchains.foojay-resolver-convention" version "1.0.0"
}

rootProject.name = "kora-example"
```

`src/main/java/com/example/Application.java`:

```java
package com.example;

import io.koraframework.application.graph.KoraApplication;
import io.koraframework.common.annotation.KoraApp;
import io.koraframework.config.hocon.HoconConfigModule;
import io.koraframework.http.server.undertow.UndertowPublicHttpServerModule;
import io.koraframework.json.common.JsonModule;
import io.koraframework.logging.logback.LogbackModule;

@KoraApp
public interface Application extends
        HoconConfigModule,
        JsonModule,
        LogbackModule,
        UndertowPublicHttpServerModule {

    static void main(String[] args) {
        KoraApplication.run(ApplicationGraph::graph);
    }
}
```

The processor generates `<InterfaceName>Graph` in the same package — so
`Application` yields `ApplicationGraph`, with a static `graph()` returning the
`ApplicationGraphDraw` that `KoraApplication.run(Supplier<ApplicationGraphDraw>)`
takes. It appears under `build/generated/sources/annotationProcessor/` after the
first compile.

`src/main/java/com/example/HelloController.java`:

```java
package com.example;

import io.koraframework.common.annotation.Component;
import io.koraframework.http.common.HttpMethod;
import io.koraframework.http.common.annotation.HttpRoute;
import io.koraframework.http.common.body.HttpBody;
import io.koraframework.http.server.common.annotation.HttpController;
import io.koraframework.http.server.common.response.HttpServerResponse;

@Component
@HttpController
public final class HelloController {

    @HttpRoute(method = HttpMethod.GET, path = "/hello")
    public HttpServerResponse hello() {
        return HttpServerResponse.of(200, HttpBody.plaintext("Hello, Kora!"));
    }
}
```

`src/main/resources/application.conf`:

```hocon
httpServer {
  port = 8080
  system.port = 8085
}

logging.levels {
  "root": "WARN"
  "io.koraframework": "INFO"
  "com.example": "INFO"
}

httpServer.telemetry.logging.enabled = true
```

`UndertowPublicHttpServerModule` extends `UndertowSystemHttpServerModule`, so one
`extends` gives both servers: the public API on `httpServer.port` (default 8080)
and the system API on `httpServer.system.port` (default 8085), which serves
`/system/readiness`, `/system/liveness` and `/metrics`. Component telemetry —
logging and metrics — is **off by default**; enable it per component as shown.

Build and run:

```bash
./gradlew clean build   # runs the annotation processor, builds the graph
./gradlew run           # GET http://localhost:8080/hello -> "Hello, Kora!"
```

---

## Project structure

```
my-app/
├── build.gradle
├── settings.gradle
├── gradle.properties
├── gradle/wrapper/gradle-wrapper.properties
├── src/main/java/com/example/Application.java
├── src/main/resources/application.conf
├── src/main/resources/logback.xml
└── src/test/java/com/example/
```

---

## JDK: two separate requirements

**1. Bytecode floor — JVM 25.** Kora 2.0 artifacts are compiled for Java 25
(the published `kora-bom` pom declares `java.version` = `25`). Your toolchain
must be 25 or newer; the reference apps pin `JavaLanguageVersion.of(25)`.

**2. The JDK that runs the Gradle process itself.** The `java { toolchain { … } }`
block does **not** affect the JVM Gradle runs on. The moment you put
`io.koraframework:openapi-generator` on the `buildscript` classpath (contract-first
OpenAPI codegen), that classpath is resolved by the Gradle JVM and an older JDK
fails at configuration time:

```
Dependency requires at least JVM runtime version 25. This build uses a Java 21 JVM.
> Run this build using a Java 25 or newer JVM.
```

Rule: run Gradle on JDK 25+ — in practice the latest GA feature release available
on the day you set the project up (derive it then; do not copy a frozen number).
Set it through `JAVA_HOME`, not through `org.gradle.java.home` in a committed
`gradle.properties` — that path is machine-specific.

**`--enable-preview` is not a blanket requirement.** Kora's own test task and the
BOM's Maven surefire `argLine` use it; a consumer needs it only when its own code
uses a preview API (`StructuredTaskScope`, for example). Do not add it by default.

---

## What's in `references/` and `assets/`

| File | Purpose |
|------|---------|
| [`references/build-gradle-reference.md`](references/build-gradle-reference.md) | Fully annotated `build.gradle`, the `koraBom` configuration explained, test/run tuning, distribution packaging, Docker base image |
| [`references/troubleshooting-reference.md`](references/troubleshooting-reference.md) | Build-error symptom → cause → fix table, plus the checklist for moving an existing older build onto 2.0 |
| [`assets/build.gradle.template`](assets/build.gradle.template) | Drop-in `build.gradle` |
| [`assets/settings.gradle.template`](assets/settings.gradle.template) | `settings.gradle` with the foojay toolchain resolver |
| [`assets/gradle.properties`](assets/gradle.properties) | `koraVersion`, JVM args and Gradle flags |
| [`assets/Application.java.template`](assets/Application.java.template) | `@KoraApp` graph root |
| [`assets/application.conf.template`](assets/application.conf.template) | HOCON with the 2.0 server/logging keys |
| [`assets/logback.xml.template`](assets/logback.xml.template) | Logback appender wiring for `LogbackModule` |
| [`assets/gradle-wrapper.properties`](assets/gradle-wrapper.properties) | Gradle wrapper distribution |

---

## When to use vs NOT

**Use this skill when:**
- Creating a Java Kora service from scratch (build files + `@KoraApp` root).
- A build fails with "annotation processor did not run", a missing
  `ApplicationGraph`, or "Required dependency was not found".
- Choosing the JDK toolchain, the `kora-bom` version, or the Gradle wrapper.
- **Migration symptom:** after moving a project onto 2.0, the build reports
  `package ru.tinkoff.kora.… does not exist` from files under `build/generated/`
  that no longer exist in your sources.

**Do NOT use this skill for:**
- Kotlin projects → `kora-project-setup-kotlin` (uses `ksp` +
  `symbol-processors`, not `annotationProcessor`).
- Adding HTTP / Database / Kafka / gRPC modules to an existing build →
  `kora-project-dependencies`.
- Writing `@ConfigSource` typed config → `kora-config-hocon`.
- DI patterns (`@Component`, `@Module`, factories) → `kora-di-compile`.

---

## The five things that must be right

1. **`koraBom` configuration wiring.** A custom `koraBom` configuration holds
   `platform("io.koraframework:kora-bom:$koraVersion")` and is extended by
   `annotationProcessor`, `implementation`, `compileOnly`, and the `test*`
   configurations. The annotation-processor classpath is separate from the
   application classpath, so it needs the BOM explicitly — otherwise the
   processor resolves without a version and fails.

2. **`annotationProcessor "io.koraframework:annotation-processors"`.** This is
   the single aggregate processor: it pulls in the graph, AOP, config, JSON,
   HTTP server/client, SOAP, database, Kafka, scheduling, resilient, cache,
   validation, logging, gRPC-client, S3 and Zeebe processors. Add
   `testAnnotationProcessor` too so `@KoraAppTest` works.

3. **`@KoraApp` graph root.** An `interface` annotated with `@KoraApp` that
   `extends` the framework `*Module` interfaces it needs. `main` calls
   `KoraApplication.run(ApplicationGraph::graph)`.

4. **Correct imports.** In 2.0 the DI annotations sit one package deeper:
   `@KoraApp` and `@Component` are in `io.koraframework.common.annotation`;
   `KoraApplication` is `io.koraframework.application.graph.KoraApplication`.

5. **JDK 25+ for both the toolchain and the Gradle process.** See the section
   above.

---

## Core patterns

### Modules are interfaces the `@KoraApp` extends

Framework capabilities ship as `*Module` interfaces. The graph root pulls them
in via `extends`; each module contributes component factories to the graph.

```java
@KoraApp
public interface Application extends
        HoconConfigModule,                // config-hocon
        JsonModule,                       // json-common
        LogbackModule,                    // logging-logback
        UndertowPublicHttpServerModule    // http-server-undertow
{ ... }
```

Each `extends` must be backed by an `implementation "io.koraframework:<artifact>"`
in `build.gradle`. If a module is on the build path but not extended, its
factories are not added to the graph.

### Your code joins the graph via `@Component`

A class annotated with `@Component` becomes a managed node. Dependencies are
declared as **constructor parameters** — Kora resolves them at compile time.

```java
@Component
@HttpController
public final class HelloController {
    private final GreetingService service;        // resolved from the graph

    public HelloController(GreetingService service) {
        this.service = service;
    }
}
```

Do not use field injection. Kora wires components only through constructors.

### Nullability is JSpecify, and it is type-use

`org.jspecify.annotations.Nullable` / `@NonNull` / `@NullMarked` arrive
transitively with the core; `jakarta.annotation.Nullable` is not what Kora 2.0
uses. JSpecify annotations are **type-use**, so they bind to the type, not the
declaration: `Outer.@Nullable Inner`, not `@Nullable Outer.Inner`. Wrong position
gives `error: type annotation @org.jspecify.annotations.Nullable is not expected here`
— positions and the array/generic cases are in
[`references/troubleshooting-reference.md`](references/troubleshooting-reference.md#type-annotation-is-not-expected-here).

### A minimal `@KoraAppTest`

`test-junit5` provides `@KoraAppTest`, which builds the real graph and injects
components into the test via `@TestComponent`.

```java
import static org.junit.jupiter.api.Assertions.assertNotNull;

import io.koraframework.test.extension.junit5.KoraAppTest;
import io.koraframework.test.extension.junit5.TestComponent;
import org.junit.jupiter.api.Test;

@KoraAppTest(Application.class)
class ApplicationTest {

    @TestComponent
    private HelloController controller;

    @Test
    void controllerIsWired() {
        assertNotNull(controller);
    }
}
```

Requires `testAnnotationProcessor "io.koraframework:annotation-processors"` so
the test graph is generated. Deeper testing → `kora-testing-junit-java`.

---

## Common pitfalls

| Symptom | Cause | Fix |
|---------|-------|-----|
| No generated classes; `ApplicationGraph` unresolved | `annotationProcessor "io.koraframework:annotation-processors"` missing | Add it to `dependencies` |
| "Could not resolve io.koraframework:annotation-processors" (no version) | `annotationProcessor` does not extend `koraBom` | `annotationProcessor.extendsFrom(koraBom)` |
| `Dependency requires at least JVM runtime version 25` at configuration time | Gradle itself runs on an older JDK; `openapi-generator` is on the buildscript classpath | Run Gradle on JDK 25+ via `JAVA_HOME` |
| *(migration only)* `package ru.tinkoff.kora.… does not exist` in files you never wrote | Stale generator output under `build/generated/` survived the package rename | `./gradlew clean`, then build once with `--no-build-cache` |
| Module factories absent from the graph | Module on classpath but not in `@KoraApp extends` | Add the `*Module` to `extends` |
| `cannot find symbol KoraApp` / `Component` | Imported from `io.koraframework.common` instead of `io.koraframework.common.annotation` | Use the `.annotation` sub-package |
| Custom ports ignored; app answers on 8080/8085 | Old port keys are unknown to 2.0 config and silently ignored | Use `httpServer.port` and `httpServer.system.port` |
| `@KoraAppTest` finds no components | `testAnnotationProcessor` missing | Add `testAnnotationProcessor "io.koraframework:annotation-processors"` |
| IDE shows red but `./gradlew classes` passes | IDE has not indexed `build/generated/` | Re-run `classes`, refresh/invalidate IDE caches |
| Shadow fat jar: Flyway fails at startup with `NullPointerException` in `DryRunConfigurationExtensionStub.getOrResolveOutputStream` | `com.gradleup.shadow` 9.x keeps only the first `META-INF/services/*` copy unless duplicates are included, so `mergeServiceFiles()` merges nothing (observed empirically) | `shadowJar { mergeServiceFiles(); duplicatesStrategy = DuplicatesStrategy.INCLUDE }` — see [build reference](references/build-gradle-reference.md#fat-jar-with-shadow) |

Full diagnosis table: [`references/troubleshooting-reference.md`](references/troubleshooting-reference.md).

---

## Next steps

- [`kora-project-dependencies`](../kora-project-dependencies/SKILL.md) — add HTTP, Database, Kafka, gRPC, S3 modules.
- [`kora-config-hocon`](../kora-config-hocon/SKILL.md) — typed `@ConfigSource` configuration.
- [`kora-di-compile`](../kora-di-compile/SKILL.md) — compile-time DI patterns.
- [`kora-testing-junit-java`](../kora-testing-junit-java/SKILL.md) — `@KoraAppTest` testing.
