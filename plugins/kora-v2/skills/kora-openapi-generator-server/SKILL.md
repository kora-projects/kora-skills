---
name: kora-openapi-generator-server
description: "Generate a Kora 2.x HTTP server from an OpenAPI 3.x contract with the `kora` generator (io.koraframework:openapi-generator, modes java-server / kotlin-server). Emits *ApiController (@Component + @HttpController), a *ApiDelegate interface you implement, sealed *ApiResponses with one record per status code, *ApiServerResponseMappers, model records/data classes and an ApiSecurity @Module for securitySchemes (401 unauthenticated, 403 missing OAuth scope). Use for contract-first servers, enableServerValidation, HttpServerPrincipalExtractor wiring, 4XX/5XX range responses, enum fromValue parsing, or \"delegate not found\" / phantom-package build errors."
license: Apache-2.0
metadata:
  kora-version: "2.x"
---

# Kora OpenAPI Generator — HTTP Server

> **Kora sub-skill — obey the [kora-v2 meta rules](../../SKILL.md) on every task:** **R0** ground the workspace on Kora 2.0 refs before starting (framework source at tag `2.0.0.RC2` + `kora-examples` at `migration/2.0` + Kora 2.0 docs at koraframework.io/v2, which trail the source; 1.x `kora-docs` pages are never an authority) · **R1** read this sub-skill before writing code · **R2** Kora 2.0 APIs only — no Spring/Micronaut/Quarkus, no Kora 1.x APIs, no invented annotations or config keys · **R3** journal any incorrect Kora usage. Add comments/Javadoc only if asked.

**Version:** Kora 2.0 (`io.koraframework`, `2.0.0.RC2`) | **Java:** 25 | **Kotlin:** 2.4.20 + KSP 2.3.12 | **Gradle:** 9.8.0

The `kora` generator turns an OpenAPI 3.x contract into the whole transport layer of a Kora
HTTP server. You implement exactly one thing: the generated `*ApiDelegate` interface, as a
`@Component`. Everything else — routing, parameter binding, JSON, response mapping, security
interceptors — is generated and must never be edited or hand-written alongside.

Kora 2.0 contracts are **synchronous**. Delegate methods return a value directly; there is no
`Mono`, `Flux`, `CompletionStage` or `suspend` variant of a delegate, and `Context` no longer
exists anywhere in the framework.

## Only four generator modes exist

`configOptions.mode` accepts exactly `java-client`, `java-server`, `kotlin-client`,
`kotlin-server` (`CodegenMode` in the generator). Anything else fails generation with
*"Invalid OpenAPI generator `mode`"* and a list of the supported values.

| Kora 1.x mode | Use instead |
|---|---|
| `java-async-server`, `java-reactive-server` | `java-server` |
| `kotlin-suspend-server` | `kotlin-server` |
| `java-async-client`, `java-reactive-client` | `java-client` |
| `kotlin-suspend-client` | `kotlin-client` |

Any other reactive/async/suspend variant is equally invalid — the mode string must be one of the
four above.

## Migrating from Kora 1.x

| Kora 1.x | Kora 2.x |
|---|---|
| BOM `ru.tinkoff.kora:kora-parent` | **`io.koraframework:kora-bom`** |
| `classpath("ru.tinkoff.kora:openapi-generator:…")` | **`classpath("io.koraframework:openapi-generator:$koraVersion")`** |
| `ru.tinkoff.kora:json-module` | **`io.koraframework:json-common`** |
| `UndertowHttpServerModule` | **`UndertowPublicHttpServerModule`** |
| `ru.tinkoff.kora.common.Component` | **`io.koraframework.common.annotation.Component`** |
| reactive / async / suspend server modes | **removed** — see the table above |
| `@Tag(ApiSecurity.SecurityRequirementTag1.class)` | **`@Tag(ApiSecurity.<SchemeName>.class)`**, e.g. `ApiSecurity.BearerAuth` |
| `Enum.valueOf(raw)` / hand-written `statusOf` | **`MyEnum.fromValue(raw)`** |
| `javax`/`jakarta` nullability on generated params | **JSpecify** `org.jspecify.annotations.@Nullable` |
| `configOptions.interceptors` | **`configOptions.extensions`** (`interceptorType` / `interceptorTag`) |
| `configOptions.additionalContractAnnotations` | **`extensions.*.additionalMethodAnnotations`** |
| `delegateMethodBodyMode: "throw-exception"` | **`"throwException"`** |

Two of these fail only at runtime, never at compile time:

- **`fromValue`, not `valueOf`.** The wire value in the contract (`available`) need not match
  the generated constant (`AVAILABLE`). `Enum.valueOf("available")` throws for perfectly valid
  input. `fromValue` throws `IllegalArgumentException` only for values outside the contract, and
  the delegate turns that into the contract's `400`.
- **Security tags are named after the security scheme.** `components.securitySchemes.BearerAuth`
  becomes the nested marker `ApiSecurity.BearerAuth`. Ordinal `SecurityRequirementTagN` names do
  not exist in 2.0, so an extractor tagged that way is simply never found.

## The Gradle process itself must run on JDK 25+

`io.koraframework:openapi-generator` goes on the **buildscript classpath**, which is resolved by
the JVM running Gradle — not by the project toolchain. A Java 25 `toolchain { }` block is not
enough. On an older Gradle JVM configuration fails with:

```
Dependency requires at least JVM runtime version 25. This build uses a Java 21 JVM.
```

Fix it where the Gradle JVM is chosen (`JAVA_HOME`, `org.gradle.java.home`, or the IDE's Gradle
JVM setting), not in the toolchain block. This is the single most common setup failure here.

## Quick Start

### 1. `gradle.properties`

`2.0.0.RC2` is the Kora 2.0 release and resolves from plain `mavenCentral()`.
`2.0.0-SNAPSHOT` is the development line; it needs
`https://central.sonatype.com/repository/maven-snapshots` and does not belong in a new project.

```properties
koraVersion=2.0.0.RC2
```

### 2. Build wiring

Two independent versions are in play here — do not conflate them:

| What | Where it is set | Value |
|---|---|---|
| **OpenAPI Generator Gradle plugin** (`org.openapi.generator`) | `plugins { }` block | `7.25.0` (the migrated examples still pin `7.23.0` in the Java build files, `7.24.0` in the Kotlin ones) |
| **Kora `kora` generator** (`io.koraframework:openapi-generator`) | `buildscript { dependencies { classpath … } }` | `$koraVersion` = `2.0.0.RC2` |

The Kora generator is built against `org.openapitools:openapi-generator` **7.25.0** (framework
version catalog), so `7.25.0` is the aligned plugin choice.

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
        toolchain {
            languageVersion = JavaLanguageVersion.of(25)
        }
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
        implementation "io.koraframework:validation-module"   // required by enableServerValidation
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

### 3. Generation task

===! ":fontawesome-brands-java: `Java`"

    ```groovy title="build.gradle"
    def openApiGenerateHttpServer = tasks.register("openApiGenerateHttpServer", GenerateTask) {
        generatorName = "kora"
        group = "openapi tools"
        inputSpec = layout.projectDirectory.file("src/main/resources/openapi/pet-api.yaml")
        outputDir = layout.buildDirectory.dir("generated/pet-api-server")   // unique per spec
        def corePackage = "com.example.petapi"
        apiPackage = "${corePackage}.api"
        modelPackage = "${corePackage}.model"
        invokerPackage = "${corePackage}.invoker"
        configOptions = [
            mode                  : "java-server",
            enableServerValidation: "true",
        ]
    }
    sourceSets.main { java.srcDirs += openApiGenerateHttpServer.get().outputDir }
    compileJava.dependsOn openApiGenerateHttpServer
    ```

=== ":simple-kotlin: `Kotlin`"

    ```kotlin title="build.gradle.kts"
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

Kotlin needs **both** hooks: KSP reads the generated sources, and `compileKotlin` compiles them.
Wiring only one of them produces "unresolved reference" errors on a clean build.

### 4. Plug the modules into `@KoraApp`

```java
@KoraApp
public interface Application extends
        HoconConfigModule,
        LogbackModule,
        JsonModule,
        ValidationModule,                  // only with enableServerValidation = true
        UndertowPublicHttpServerModule {

    static void main(String[] args) {
        KoraApplication.run(ApplicationGraph::graph);
    }
}
```

`KoraApplication` is `io.koraframework.application.graph.KoraApplication`.

**Do not `extends` the generated `ApiSecurity` / `*ApiModule` interfaces.** They carry `@Module`,
and the `@KoraApp` processor discovers every `@Module`-annotated interface in the compilation
round automatically (`KoraAppProcessor#processModules`). The migrated examples list only the
framework modules.

```hocon title="application.conf"
httpServer {
  port = 8080
  system.port = 8085
  telemetry.logging.enabled = true   # logging and metrics default to false in 2.0
}
```

### 5. Implement the generated delegate

For a tag `pet` the generator emits `PetApiDelegate` (one method per `operationId`) and
`PetApiResponses` (one sealed interface per operation, one record per declared status).

===! ":fontawesome-brands-java: `Java`"

    ```java
    package com.example.petapi.delegate;

    import io.koraframework.common.annotation.Component;
    import org.jspecify.annotations.Nullable;
    import com.example.petapi.api.PetApiDelegate;
    import com.example.petapi.api.PetApiResponses;
    import com.example.petapi.model.Pet;

    @Component
    public final class PetDelegate implements PetApiDelegate {

        private final PetService petService;

        public PetDelegate(PetService petService) {
            this.petService = petService;
        }

        @Override
        public PetApiResponses.GetPetByIdApiResponse getPetById(long petId) {
            var pet = petService.find(petId);
            return pet == null
                ? new PetApiResponses.GetPetByIdApiResponse.GetPetById404ApiResponse()
                : new PetApiResponses.GetPetByIdApiResponse.GetPetById200ApiResponse(pet);
        }

        @Override
        public PetApiResponses.FindPetsByStatusApiResponse findPetsByStatus(@Nullable String status) {
            final Pet.StatusEnum parsed;
            try {
                parsed = Pet.StatusEnum.fromValue(status);       // never Enum.valueOf
            } catch (IllegalArgumentException e) {
                return new PetApiResponses.FindPetsByStatusApiResponse.FindPetsByStatus400ApiResponse();
            }
            return new PetApiResponses.FindPetsByStatusApiResponse
                .FindPetsByStatus200ApiResponse(petService.byStatus(parsed));
        }
    }
    ```

=== ":simple-kotlin: `Kotlin`"

    ```kotlin
    package com.example.petapi.delegate

    import io.koraframework.common.annotation.Component
    import com.example.petapi.api.PetApiDelegate
    import com.example.petapi.api.PetApiResponses
    import com.example.petapi.model.Pet

    @Component
    class PetDelegate(private val petService: PetService) : PetApiDelegate {

        override fun getPetById(petId: Long): PetApiResponses.GetPetByIdApiResponse {
            val pet = petService.find(petId)
                ?: return PetApiResponses.GetPetByIdApiResponse.GetPetById404ApiResponse()
            return PetApiResponses.GetPetByIdApiResponse.GetPetById200ApiResponse(pet)
        }

        override fun findPetsByStatus(status: String?): PetApiResponses.FindPetsByStatusApiResponse {
            val parsed = try {
                status?.let(Pet.StatusEnum::fromValue)
            } catch (_: IllegalArgumentException) {
                null
            } ?: return PetApiResponses.FindPetsByStatusApiResponse.FindPetsByStatus400ApiResponse()

            return PetApiResponses.FindPetsByStatusApiResponse
                .FindPetsByStatus200ApiResponse(petService.byStatus(parsed))
        }
    }
    ```

### 6. Build and run

```bash
./gradlew clean classes   # generate, then compile
./gradlew run
```

Use `clean` (and `--no-build-cache`) on the first build after changing `apiPackage`,
`modelPackage` or the spec's package layout — see the pitfalls table.

## What gets generated

For `apiPackage = com.example.petapi.api` and a spec tag `pet`:

| Generated type | Kind | Your job |
|---|---|---|
| `PetApiController` | `@Component @HttpController` class, `final` unless aspects are enabled | never touch |
| `PetApiDelegate` | `public interface`, one method per `operationId` | **implement as `@Component`** |
| `PetApiResponses` | interface holding one sealed `<Op>ApiResponse` per operation | construct, never edit |
| `PetApiServerResponseMappers` | `@Component @DefaultComponent` `HttpServerResponseMapper`s | never touch |
| `PetApiServerRequestMappers` | form/multipart request mappers | never touch |
| `ApiSecurity` | `@Module` interface: scheme marker classes + generated interceptors | supply `HttpServerPrincipalExtractor`s |
| `PetApiModule` | `@Module` with a default delegate — only with `delegateMethodBodyMode` ≠ `none` | leave alone |
| `package-info.java` | `@org.jspecify.annotations.NullMarked` (Java modes only) | never touch |
| model records / data classes | `@Json` DTOs, nested enums with `fromValue` | construct, never edit |

Routing is registered by the **Kora HTTP-server annotation processor**, which generates
`PetApiControllerModule` from the `@HttpController`. That is a separate step from OpenAPI
generation, and it is why the annotation processor / KSP dependency is mandatory.

## Core rules

1. **Implement `*ApiDelegate`, nothing else.** Never hand-write an `@HttpController` or
   `@HttpRoute` for an operation that the generator already covers — you would register the
   route twice.
2. **Return the generated response record**, never a raw DTO. There is no `ResponseEntity`.
3. **A response record exists only for a status declared in the contract.** Need a `500`?
   Declare `"500"` under that operation's `responses` and regenerate.
4. **`@Component` on the delegate implementation** — it is what the compile-time graph resolves
   into the generated controller's constructor.
5. **Parse generated enums with `fromValue`**, and map `IllegalArgumentException` to the
   contract's error response.
6. **Tag principal extractors with the scheme-named marker**, e.g.
   `@Tag(ApiSecurity.BearerAuth.class)`.
7. **Never edit anything under `build/generated`.** A stale-package error is fixed by `clean`,
   not by editing output.
8. **Kotlin models: use named arguments.** Optional properties carry defaults but stay in spec
   order, so a positional call breaks (or silently shifts) as soon as the contract changes.

## Common pitfalls

| Symptom | Cause and fix |
|---|---|
| `Dependency requires at least JVM runtime version 25. This build uses a Java 21 JVM.` | The Gradle JVM, not the toolchain, resolves the buildscript classpath. Run Gradle on JDK 25+. |
| `Invalid OpenAPI generator 'mode'` | Only `java-client`, `java-server`, `kotlin-client`, `kotlin-server` exist. |
| `package com.example… does not exist`, pointing at `build/generated` | Old output from a previous `apiPackage`/`modelPackage` still on the source set — the generator does not delete stale files and the build-cache key ignores those settings. Run `./gradlew clean build --no-build-cache`. Never "fix" it by editing generated code. |
| Delegate not discovered — `No component found for dependency … ApiDelegate` | Missing `@Component`, or the class implements a delegate from a different `apiPackage`. |
| `method does not override or implement a method from a supertype` | The implementation signature drifted from the regenerated delegate — usually a leftover `Mono`/`CompletionStage`/`suspend` return type, or a nullability mismatch. Copy the signature from the generated interface. |
| `'…' overrides nothing` (Kotlin) | Kora contracts are `@NullMarked`; an optional parameter is `T?` in the generated interface and must be `T?` in the override. |
| Enum lookup fails on valid data | `Enum.valueOf` / `values()` scan instead of `fromValue`. |
| Principal extractor never called, every request 401 | The extractor's `@Tag` does not match a generated `ApiSecurity` marker. |
| OAuth2 route answers 403 for a valid token | The extractor returned a principal, but its `scopes()` lack a scope the operation requires. 401 means no principal at all. |
| `4XX` / `5XX` response record needs a status argument | A range response becomes `<Op>4XXApiResponse(int statusCode, …)` (like `default`); pass the concrete status you send. |
| `Multiple components match` for the delegate | `delegateMethodBodyMode` generated a default delegate **and** you wrote a `@Component` one. Pick one. |
| Validation annotations absent | `enableServerValidation: "true"` plus `io.koraframework:validation-module` and `ValidationModule` in `@KoraApp`. |
| `Invalid OpenAPI numeric validation schema. Schema dataType: BigDecimal`; a `pattern` or item `@Valid` silently missing; `0` rejected by a `double` with only `maximum` | Generator defects up to 2.0.0.RC1, fixed on master by kora-projects/kora PR #965 — workarounds in the [Validation Reference](references/openapi-validation-reference.md#3-constraint-mapping). |
| Two generator tasks overwrite each other | Give every task its own `outputDir`. |
| Kotlin `unresolved reference` to generated types | KSP **and** `compileKotlin` must both `dependsOn` the generate task. |

## References

| Document | Covers |
|---|---|
| [Codegen Reference](references/openapi-codegen-reference.md) | Build wiring, the complete verified `configOptions` table, normalizer, output inventory |
| [Delegates Reference](references/openapi-delegates-reference.md) | `*ApiDelegate` shape, signature mapping, `requestInDelegateParams`, `delegateMethodBodyMode` |
| [Response Reference](references/openapi-response-reference.md) | Sealed `*ApiResponses`, headers, `default` responses, generated response mappers |
| [Controllers Reference](references/openapi-controllers-reference.md) | Generated controller, route registration, `prefixPath`, interceptors |
| [Models Reference](references/openapi-models-reference.md) | Records / data classes, `withX`, enums, `JsonNullable`, discriminators, JSpecify positions |
| [Validation Reference](references/openapi-validation-reference.md) | `enableServerValidation`, constraint mapping, `ViolationExceptionHttpServerResponseMapper` |
| [Authorization Reference](references/authorization-reference.md) | `ApiSecurity` module, scheme-named tags, `HttpServerPrincipalExtractor`, scopes |
| [Advanced Codegen](references/advanced-codegen-reference.md) | `extensions`, implicit headers, `rawBodyMode`, `filterWithModels`, multi-spec projects |

Related skills: [`kora-http-server`](../kora-http-server/SKILL.md),
[`kora-http-server-auth`](../kora-http-server-auth/SKILL.md),
[`kora-openapi-generator-client`](../kora-openapi-generator-client/SKILL.md),
[`kora-openapi-management`](../kora-openapi-management/SKILL.md),
[`kora-json`](../kora-json/SKILL.md),
[`kora-aop-validation`](../kora-aop-validation/SKILL.md).

Upstream: [kora @ `2.0.0.RC2`](https://github.com/kora-projects/kora/tree/2.0.0.RC2),
[kora-examples @ `migration/2.0`](https://github.com/kora-projects/kora-examples/tree/migration/2.0),
[OpenAPI Generator Gradle plugin](https://openapi-generator.tech/docs/plugins#gradle).
Kora 2.0 docs: [koraframework.io/v2/en](https://koraframework.io/v2/en/) — they trail the source; verify keys and defaults there.

## Assets

| Asset | Purpose |
|---|---|
| `assets/build.gradle.server.template` / `assets/build.gradle.kts.server.template` | Annotated build wiring for server generation |
| `assets/Application.server.java.template` / `.kt.template` | `@KoraApp` with validation and principal extractors |
| `assets/PetApiDelegate.server.java.template` / `.kt.template` | Delegate implementation, both languages |
| `assets/delegate-impl-templates.java.template` | Delegate patterns: enums, form params, raw request, errors |
| `assets/response-handling-templates.java.template` | Response construction, headers, `default` status, Kotlin equivalents |
| `assets/openapi-spec.yaml.template` | Full OpenAPI 3.x contract: CRUD, security, discriminator |
| `assets/openapi-spec-snippets.yaml.template` | Copy-paste spec fragments mapped to generated code |
| `scripts/validate_openapi.py` | Read-only pre-generation spec check (Kora 2.0 rules) |
