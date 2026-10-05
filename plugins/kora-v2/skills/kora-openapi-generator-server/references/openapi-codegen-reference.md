# OpenAPI Codegen Reference (Server) — Kora 2.x

Everything here is taken from the `io.koraframework:openapi-generator` sources and tests for
`2.0.0.RC2` and from the migrated `kora-examples` server examples and guides.

## Contents

- [1. What the `kora` generator is](#1-what-the-kora-generator-is)
- [2. Two versions, two places](#2-two-versions-two-places)
- [3. Build wiring](#3-build-wiring)
- [4. The generation task](#4-the-generation-task)
- [5. Generator modes](#5-generator-modes)
- [6. `configOptions` — complete verified list](#6-configoptions--complete-verified-list)
- [7. `openapiNormalizer`](#7-openapinormalizer)
- [8. Discriminators, `oneOf` and `allOf`](#8-discriminators-oneof-and-allof)
- [9. Generated output inventory](#9-generated-output-inventory)
- [10. Incremental builds and stale output](#10-incremental-builds-and-stale-output)
- [11. Multiple specs in one project](#11-multiple-specs-in-one-project)

---

## 1. What the `kora` generator is

`io.koraframework:openapi-generator` registers a `CodegenConfig` named **`kora`** with the
OpenAPI Generator toolchain (`META-INF/services/org.openapitools.codegen.CodegenConfig`). You
select it with `generatorName = "kora"` on the plugin's `GenerateTask`.

Internally Kora 2.0 no longer renders Mustache templates: each `*.mustache` under
`openapi/templates/kora/` is a one-line lambda that hands off to a JavaPoet
(`…generator.javagen.*`) or KotlinPoet (`…generator.kotlingen.*`) generator class. The practical
consequence is that **custom Mustache template overrides no longer change generated code** —
`templateDir` has nothing meaningful to override. Shape your output with `configOptions`
(section 6) instead.

## 2. Two versions, two places

| What | Where the consumer sets it | Value |
|---|---|---|
| `org.openapi.generator` **Gradle plugin** | `plugins { id "org.openapi.generator" version "…" }` | use `7.25.0`; the migrated examples still pin `7.23.0` (Java) / `7.24.0` (Kotlin) |
| `io.koraframework:openapi-generator` — the **Kora generator** | `buildscript { dependencies { classpath("io.koraframework:openapi-generator:$koraVersion") } }` | `$koraVersion` = `2.0.0.RC2` |
| `org.openapitools:openapi-generator` — the upstream **library** the Kora generator compiles against | not set by the consumer; transitive | `7.25.0` (framework version catalog) |

They are three different things. Bumping the plugin does not bump the Kora generator, and the
Kora generator's own upstream dependency is fixed by `$koraVersion`. `7.25.0` is the plugin
version aligned with what the generator was built against.

Related third-party pins from the same catalog: `swagger-core 2.2.55`, `swagger-parser 2.1.48`.

## 3. Build wiring

===! ":fontawesome-brands-java: `Java`"

    ```groovy title="build.gradle"
    import org.openapitools.generator.gradle.plugin.tasks.GenerateTask

    buildscript {
        repositories { mavenCentral() }
        dependencies {
            classpath("io.koraframework:openapi-generator:$koraVersion")
        }
    }

    plugins {
        id "java"
        id "application"
        id "org.openapi.generator" version "7.25.0"
    }

    java {
        toolchain { languageVersion = JavaLanguageVersion.of(25) }
    }

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

        implementation "io.koraframework:http-server-undertow"
        implementation "io.koraframework:json-common"
        implementation "io.koraframework:config-hocon"
        implementation "io.koraframework:logging-logback"
        implementation "io.koraframework:validation-module"
    }
    ```

=== ":simple-kotlin: `Kotlin`"

    ```kotlin title="build.gradle.kts"
    import org.openapitools.generator.gradle.plugin.tasks.GenerateTask

    buildscript {
        repositories { mavenCentral() }
        dependencies {
            classpath("io.koraframework:openapi-generator:${property("koraVersion")}")
        }
    }

    plugins {
        id("application")
        kotlin("jvm") version "2.4.20"
        id("com.google.devtools.ksp") version "2.3.12"
        id("org.openapi.generator") version "7.25.0"
    }

    kotlin {
        jvmToolchain { languageVersion.set(JavaLanguageVersion.of(25)) }
    }

    dependencies {
        implementation(platform("io.koraframework:kora-bom:${property("koraVersion")}"))
        ksp("io.koraframework:symbol-processors:${property("koraVersion")}")

        implementation("io.koraframework:http-server-undertow")
        implementation("io.koraframework:json-common")
        implementation("io.koraframework:config-hocon")
        implementation("io.koraframework:logging-logback")
        implementation("io.koraframework:validation-module")
    }
    ```

### The Gradle JVM must be 25+

The `classpath("io.koraframework:openapi-generator:…")` dependency is resolved by the JVM that
runs Gradle, not by the project toolchain. Kora 2.0 artifacts are class-file 69 (Java 25), so an
older Gradle JVM fails at **configuration time**:

```
Dependency requires at least JVM runtime version 25. This build uses a Java 21 JVM.
```

Set `JAVA_HOME`, `org.gradle.java.home` in `gradle.properties`, or the IDE's Gradle JVM. Adding
`toolchain { languageVersion = JavaLanguageVersion.of(25) }` does **not** fix it.

## 4. The generation task

===! ":fontawesome-brands-java: `Java`"

    ```groovy
    def openApiGenerateHttpServer = tasks.register("openApiGenerateHttpServer", GenerateTask) {
        generatorName = "kora"                                                       // (1)
        group = "openapi tools"
        inputSpec = layout.projectDirectory.file("src/main/resources/openapi/pet-api.yaml")
        outputDir = layout.buildDirectory.dir("generated/pet-api-server")             // (2)
        def corePackage = "com.example.petapi"
        apiPackage   = "${corePackage}.api"                                           // (3)
        modelPackage = "${corePackage}.model"                                         // (4)
        invokerPackage = "${corePackage}.invoker"
        configOptions = [
            mode                  : "java-server",                                    // (5)
            enableServerValidation: "true",
        ]
    }
    sourceSets.main { java.srcDirs += openApiGenerateHttpServer.get().outputDir }      // (6)
    compileJava.dependsOn openApiGenerateHttpServer                                    // (7)
    ```

    1. Selects the Kora generator provided by the buildscript classpath dependency.
    2. One directory per spec — see section 11.
    3. Controllers, delegates, responses, mappers and `ApiSecurity` land here.
    4. Models and their generated JSON readers/writers land here.
    5. See section 5.
    6. Register the output as project source.
    7. Generate before compiling.

=== ":simple-kotlin: `Kotlin`"

    ```kotlin
    val openApiGenerateHttpServer = tasks.register<GenerateTask>("openApiGenerateHttpServer") {
        generatorName.set("kora")
        group = "openapi tools"
        inputSpec.set("$projectDir/src/main/resources/openapi/pet-api.yaml")
        outputDir.set(layout.buildDirectory.dir("generated/pet-api-server").get().asFile.absolutePath)
        val corePackage = "com.example.petapi"
        apiPackage.set("$corePackage.api")
        modelPackage.set("$corePackage.model")
        invokerPackage.set("$corePackage.invoker")
        configOptions.set(
            mapOf(
                "mode" to "kotlin-server",
                "enableServerValidation" to "true",
            )
        )
    }

    kotlin.sourceSets.main { kotlin.srcDir(openApiGenerateHttpServer.get().outputDir) }
    tasks.matching { it.name.startsWith("ksp") }.configureEach { dependsOn(openApiGenerateHttpServer) }
    tasks.compileKotlin { dependsOn(openApiGenerateHttpServer) }
    ```

    KSP and `compileKotlin` are separate tasks and both consume the generated sources. Wiring
    only one of them leaves the other racing the generator on a clean build.

Once generated and compiled, routes register themselves: the Kora HTTP-server annotation
processor sees the generated `@HttpController` and emits a `*ApiControllerModule` that binds
every `HttpServerRequestHandler`.

## 5. Generator modes

`CodegenMode` accepts exactly four values. Any other value aborts generation with
*"Invalid OpenAPI generator `mode`"* and prints the supported list.

| `mode` | Emits |
|---|---|
| `java-server` | Java controller + delegate + responses + mappers + models |
| `kotlin-server` | Kotlin equivalents |
| `java-client` | Java `@HttpClient` interface + models (see the `kora-openapi-generator-client` skill) |
| `kotlin-client` | Kotlin equivalents |

The Kora 1.x modes `java-async-server`, `java-reactive-server`, `java-async-client`,
`java-reactive-client`, `kotlin-suspend-server` and `kotlin-suspend-client` **do not exist in
2.0**, and neither does any other reactive/async/suspend variant. Kora 2.0 contracts are
synchronous and run on virtual threads.

## 6. `configOptions` — complete verified list

Every key below is read by `CodegenParams.parse`. Keys not in this table are ignored silently by
the Kora generator — including `interceptors`, `additionalContractAnnotations`,
`enableJsonNullable`, `forceIncludeNonRequired` and `discriminatorCaseSensitive`, all of which
were 1.x-era names. Values are passed as strings by the Gradle plugin.

### Server options

| Option | Type | Default | Effect |
|---|---|---|---|
| `mode` | String | `java-client` | **Set it.** One of the four values in section 5. |
| `enableServerValidation` | Boolean | `false` | Emits Kora validation annotations on models and controller parameters and `@Validate` on controller methods. Requires `io.koraframework:validation-module` + `ValidationModule`. |
| `enableServerValidationInterceptor` | Boolean | `true` | Adds `@InterceptWith(ValidationHttpServerInterceptor.class)` next to `@Validate`. Set `false` when you map `ViolationException` yourself. Only has an effect when `enableServerValidation` is on. |
| `requestInDelegateParams` | Boolean | `false` | Adds `HttpServerRequest _serverRequest` as the **first** parameter of every controller and delegate method. |
| `delegateMethodBodyMode` | String | `none` | `none` → abstract delegate methods. `throwException` → `default` methods that `throw new UnsupportedOperationException("Not yet implemented")` (Kotlin: `TODO()`), plus a generated `*ApiModule` supplying an anonymous delegate. The 1.x spelling `throw-exception` is rejected. |
| `prefixPath` | String | `""` | Value of the generated `@HttpController`. See the caveat below. |
| `serverConfigPrefix` | String | `httpServer.controller.%{ControllerTypeNameInCamelCase}` | Substituted for `%{configPath}` inside `extensions.*.additionalMethodAnnotations`. |

Options read **only** when `mode` is a server mode: `enableServerValidation`,
`enableServerValidationInterceptor`, `requestInDelegateParams`. Setting them on a client task is
a silent no-op.

**`prefixPath` caveat.** The Kotlin generator emits it as a quoted string
(`addMember("%S", prefixPath)`), while the Java generator passes it straight into a JavaPoet
format slot (`addMember("value", params.prefixPath)`), so it is written into the annotation
verbatim rather than quoted. In `java-server` mode, pass the value already quoted —
`prefixPath: '"/api/v1"'` — or leave it unset and put the prefix in the spec's `paths`. The
default `""` produces a bare `@HttpController()`.

### Options that apply to both server and client

| Option | Type | Default | Effect |
|---|---|---|---|
| `extensions` | JSON | `{}` | Extra annotations and interceptors, per-global / per-tag / per-operation. See [Advanced Codegen](advanced-codegen-reference.md). |
| `implicitHeaders` | Boolean | `false` | Every header parameter is removed from the generated signature and documented with `@io.swagger.v3.oas.annotations.Parameter` instead. |
| `implicitHeadersRegex` | String (regex) | none | Same, but only for header names matching the regex. |
| `filterWithModels` | Boolean | `false` | With `openapiNormalizer` `FILTER`, also prunes models no surviving operation references. |
| `rawBodyMode` | String | `BYTES` | Type used for a bare-object (`type: object` with no schema) body: `BYTES` → `byte[]`; `BODY` → `HttpBodyInput`/`HttpBodyOutput`; `OBJECT` → `Object` routed through JSON. |
| `useSecurityDeclarationOrder` | Boolean | `false` | Keeps the OpenAPI declaration order of security requirements when deriving `ApiSecurity` tag names, instead of normalising them. |
| `forceIncludeOptional` | Boolean | `false` | Parsed, but no generator consumes it — it has no effect. JSON inclusion is decided by the model rules in [Models Reference](openapi-models-reference.md). |

### Client-only options

`authAsMethodArgument`, `primaryAuth`, `clientConfig`, `clientConfigPrefix`,
`securityConfigPrefix`, `tags`, `clientResponseMode`. They are parsed in every mode but only
consumed by the client generators — see the `kora-openapi-generator-client` skill.

## 7. `openapiNormalizer`

`openapiNormalizer` is a plugin-level (not Kora) knob that rewrites the parsed spec before
generation. The Kora generator reads one entry directly:

- **`FILTER`** — pairs with `configOptions.filterWithModels` to prune both operations and the
  models only they used.

```groovy
openapiNormalizer = [FILTER: "operationId:getPetById|addPet"]
configOptions = [mode: "java-server", filterWithModels: "true"]
```

Nothing in the Kora 2.0 corpus sets `DISABLE_ALL`, and the generator's own discriminator tests
produce correct sealed hierarchies without it. Treat `DISABLE_ALL: "true"` as an escape hatch
for a spec the normalizer visibly mangles, not as a default. Full rule list:
<https://openapi-generator.tech/docs/customization/#openapi-normalizer>.

## 8. Discriminators, `oneOf` and `allOf`

A schema with `discriminator.propertyName` and `discriminator.mapping` becomes a **Kora sealed
JSON hierarchy**, verified against generated output:

```yaml
components:
  schemas:
    Pet:
      type: object
      discriminator:
        propertyName: pet_type
        mapping:
          PetCat: '#/components/schemas/PetCat'
          PetDog: '#/components/schemas/PetDog'
      properties:
        pet_type: { type: string }
      required: [pet_type]

    PetCat:
      allOf:
        - $ref: '#/components/schemas/Pet'
        - type: object
          properties:
            hunts: { type: boolean }
```

generates

```java
@Json
@JsonDiscriminatorField("pet_type")
public sealed interface Pet permits PetCommon, PetCat, PetDog { }

@JsonDiscriminatorValue({"PetCat"})
public record PetCat(@JsonField("pet_type") String petType, @Nullable Boolean hunts)
        implements Pet { }
```

Rules that follow from the generated shape:

1. The discriminator property must exist on the base schema and be listed in `required`; it
   surfaces as a normal field on every variant.
2. Several mapping keys may point at one schema — the variant then carries
   `@JsonDiscriminatorValue({"Mapping3", "Mapping2"})`.
3. A base with **only** `oneOf` and no properties generates an empty sealed interface, which is
   correct: the variants hold the data.
4. Kora's own JSON reader/writer are generated per variant, so nothing about this needs Jackson.
5. Two different discriminator fields resolving onto one model is rejected at generation time.

Handle the hierarchy in the delegate with a `switch` pattern match (Java) or `when` (Kotlin) —
the interface is `sealed`, so the compiler checks exhaustiveness for you.

## 9. Generated output inventory

For `apiPackage = com.example.petapi.api`, `modelPackage = com.example.petapi.model` and spec
tag `pet`, `.openapi-generator/FILES` lists:

```
com/example/petapi/api/PetApiController.java          @Component @HttpController
com/example/petapi/api/PetApiDelegate.java            public interface — implement this
com/example/petapi/api/PetApiResponses.java           sealed response hierarchy
com/example/petapi/api/PetApiServerRequestMappers.java
com/example/petapi/api/PetApiServerResponseMappers.java
com/example/petapi/api/ApiSecurity.java               only when components.securitySchemes exists
com/example/petapi/api/PetApiModule.java              only when delegateMethodBodyMode != none
com/example/petapi/api/package-info.java              @NullMarked  (Java modes only)
com/example/petapi/model/*.java                       models
com/example/petapi/model/package-info.java            @NullMarked  (Java modes only)
```

`kotlin-server` produces the same set as `.kt` files, without the two `package-info` files.

`PetApiControllerModule` also appears in the build output but is **not** produced by the OpenAPI
generator — it carries
`@Generated("io.koraframework.http.server.annotation.processor.ControllerModuleGenerator")` and
comes from the Kora HTTP-server annotation processor / KSP reading the generated
`@HttpController`.

`package-info.java` marks both packages `@org.jspecify.annotations.NullMarked`. Generated Java
signatures therefore use type-use `@Nullable` in positions like `Pet. @Nullable StatusEnum` — do
not "simplify" that to `@Nullable Pet.StatusEnum` in your own code, it is a different position.

## 10. Incremental builds and stale output

The generator **writes** its output but never deletes files from a previous run, and the Gradle
build-cache key does not include `apiPackage` / `modelPackage`. After renaming either one — or
after moving the spec's packages — the old and new package trees coexist in the same source set
and javac/kotlinc reports phantom errors such as `package ru.tinkoff.kora… does not exist` or
`package com.example.old.api does not exist`, always pointing into `build/generated`.

```bash
./gradlew clean build --no-build-cache
```

Never respond to those errors by editing files under `build/generated` — the next generation run
overwrites them, and the error returns.

## 11. Multiple specs in one project

Give every `GenerateTask` its own `outputDir` **and** its own `apiPackage`/`modelPackage`.
Sharing an output directory makes the two tasks fight over `.openapi-generator/FILES` and
produces non-deterministic builds.

```groovy
def genPets  = tasks.register("openApiGeneratePets",  GenerateTask) { /* outputDir …/generated/pets  */ }
def genUsers = tasks.register("openApiGenerateUsers", GenerateTask) { /* outputDir …/generated/users */ }

sourceSets.main {
    java.srcDirs += genPets.get().outputDir
    java.srcDirs += genUsers.get().outputDir
}
compileJava.dependsOn genPets, genUsers
```

Serving the specs over `/openapi` and `/swagger-ui` is the `openapi-management` module's job:
`openapi.management.files` is a **list** in 2.0 (the 1.x singular `file` key is gone) and the
Scalar UI replaced RapiDoc. See the `kora-openapi-management` skill.

## Related

- [Delegates Reference](openapi-delegates-reference.md)
- [Response Reference](openapi-response-reference.md)
- [Controllers Reference](openapi-controllers-reference.md)
- [Models Reference](openapi-models-reference.md)
- [Validation Reference](openapi-validation-reference.md)
- [Authorization Reference](authorization-reference.md)
- [Advanced Codegen](advanced-codegen-reference.md)
