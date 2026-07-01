---
name: kora-openapi-generator-server
description: "Generates Kora HTTP server code from OpenAPI 3.x contracts with the kora generator of the org.openapi.generator Gradle plugin. Produces a generated *ApiController, an *ApiDelegate interface implemented with @Component, sealed *ApiResponses wrappers (one record per status code), and model records. Use when scaffolding a contract-first Kora HTTP server, choosing the server mode (java-server, java-async-server, java-reactive-server, kotlin-server, kotlin-suspend-server), enabling enableServerValidation, wiring HttpServerPrincipalExtractor for securitySchemes, handling oneOf/allOf discriminators with openapiNormalizer DISABLE_ALL, or exposing /openapi and /swagger-ui via OpenApiManagementModule. Requires the http-server-undertow module plus the Kora annotation processor (annotation-processors) or KSP (symbol-processors)."
---

# Kora OpenAPI Generator — HTTP Server

Generate a type-safe Kora HTTP server from an OpenAPI 3.x contract. The `kora`
generator emits the transport layer (controller, response wrappers, models); you
implement one generated `*ApiDelegate` interface with `@Component` and return the
generated sealed `*ApiResponses` records. The generated controller registers
routes automatically — never write `@HttpController`/`@HttpRoute` by hand for a
generated API, and never edit files under `build/generated/`.

All Kora artifacts inherit their version from the `kora-parent` BOM
(`ru.tinkoff.kora:kora-parent`, e.g. `1.2.17` in the example apps) — never pin a
version on an individual `ru.tinkoff.kora:*` dependency. The OpenAPI plugin
`org.openapi.generator` is pinned to `7.14.0`; other versions are not guaranteed
to be code-compatible.

## Quick Start

### 1. Dependencies

===! ":fontawesome-brands-java: `Java`"

    ```groovy title="build.gradle"
    import org.openapitools.generator.gradle.plugin.tasks.GenerateTask

    buildscript {
        dependencies {
            classpath("ru.tinkoff.kora:openapi-generator:$koraVersion")
        }
    }

    plugins {
        id "java"
        id "application"
        id "org.openapi.generator" version "7.14.0"
    }

    configurations {
        koraBom
        annotationProcessor.extendsFrom(koraBom)
        implementation.extendsFrom(koraBom)
    }

    dependencies {
        koraBom platform("ru.tinkoff.kora:kora-parent:$koraVersion")
        annotationProcessor "ru.tinkoff.kora:annotation-processors"

        implementation "ru.tinkoff.kora:http-server-undertow"
        implementation "ru.tinkoff.kora:json-module"
        implementation "ru.tinkoff.kora:config-hocon"
        implementation "ru.tinkoff.kora:logging-logback"
        implementation "ru.tinkoff.kora:openapi-management"   // serves /openapi + /swagger-ui
        implementation "ru.tinkoff.kora:validation-module"    // needed for enableServerValidation
    }
    ```

=== ":simple-kotlin: `Kotlin`"

    ```kotlin title="build.gradle.kts"
    import org.openapitools.generator.gradle.plugin.tasks.GenerateTask

    buildscript {
        dependencies {
            classpath("ru.tinkoff.kora:openapi-generator:$koraVersion")
        }
    }

    plugins {
        kotlin("jvm") version "1.9.24"
        id("application")
        id("org.openapi.generator") version "7.14.0"
        id("com.google.devtools.ksp") version "1.9.24-1.0.20"
    }

    configurations {
        koraBom
        ksp.extendsFrom(koraBom)
        implementation.extendsFrom(koraBom)
    }

    dependencies {
        koraBom(platform("ru.tinkoff.kora:kora-parent:$koraVersion"))
        ksp("ru.tinkoff.kora:symbol-processors")

        implementation("ru.tinkoff.kora:http-server-undertow")
        implementation("ru.tinkoff.kora:json-module")
        implementation("ru.tinkoff.kora:config-yaml")
        implementation("ru.tinkoff.kora:logging-logback")
        implementation("ru.tinkoff.kora:openapi-management")
        implementation("ru.tinkoff.kora:validation-module")
    }
    ```

### 2. Generation task

===! ":fontawesome-brands-java: `Java`"

    ```groovy title="build.gradle"
    def openApiGenerateHttpServer = tasks.register("openApiGenerateHttpServer", GenerateTask) {
        generatorName = "kora"
        group = "openapi tools"
        inputSpec = "$projectDir/src/main/resources/openapi/user-api.yaml"
        outputDir = "$buildDir/generated/user-api-server"   // unique per API
        def corePackage = "com.example.userapi"
        apiPackage = "${corePackage}.api"
        modelPackage = "${corePackage}.model"
        invokerPackage = "${corePackage}.invoker"
        openapiNormalizer = [DISABLE_ALL: "true"]           // keeps oneOf/allOf intact
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
        generatorName = "kora"
        group = "openapi tools"
        inputSpec = "$projectDir/src/main/resources/openapi/user-api.yaml"
        outputDir = "$buildDir/generated/user-api-server"   // unique per API
        val corePackage = "com.example.userapi"
        apiPackage = "$corePackage.api"
        modelPackage = "$corePackage.model"
        invokerPackage = "$corePackage.invoker"
        openapiNormalizer = mapOf("DISABLE_ALL" to "true")
        configOptions = mapOf(
            "mode" to "kotlin-server",
            "enableServerValidation" to "true",
        )
    }
    kotlin.sourceSets.main { kotlin.srcDir(openApiGenerateHttpServer.get().outputDir) }
    tasks.withType<org.jetbrains.kotlin.gradle.tasks.KspTask> {
        dependsOn(openApiGenerateHttpServer)
    }
    ```

### 3. Plug the modules into `@KoraApp`

```java
@KoraApp
public interface Application extends
        HoconConfigModule,
        LogbackModule,
        JsonModule,
        ValidationModule,             // only if enableServerValidation = true
        UndertowHttpServerModule,
        OpenApiManagementModule {     // exposes /openapi + /swagger-ui

    static void main(String[] args) {
        KoraApplication.run(ApplicationGraph::graph);
    }
}
```

`KoraApplication` is `ru.tinkoff.kora.application.graph.KoraApplication`.

### 4. Implement the generated delegate

The generator emits `UsersApiDelegate` (one method per `operationId`) and
`UsersApiResponses` (one sealed interface per operation, one record per declared
status). Implement the delegate, returning the matching response record.

For advanced codegen options (`requestInDelegateParams`, `oneOf` handling, `enableServerValidation`),
see [Advanced Codegen Options](references/advanced-codegen-reference.md).

===! ":fontawesome-brands-java: `Java`"

    ```java
    package com.example.userapi.controller;

    import ru.tinkoff.kora.common.Component;
    import com.example.userapi.api.UsersApiDelegate;
    import com.example.userapi.api.UsersApiResponses;
    import com.example.userapi.model.ErrorResponseTO;

    @Component
    public final class UserApiDelegateImpl implements UsersApiDelegate {

        private final UserService userService;

        public UserApiDelegateImpl(UserService userService) {
            this.userService = userService;
        }

        @Override
        public UsersApiResponses.GetUserApiResponse getUser(String userId) {
            return userService.findById(userId)
                .<UsersApiResponses.GetUserApiResponse>map(user ->
                    new UsersApiResponses.GetUserApiResponse.GetUser200ApiResponse(toTO(user)))
                .orElseGet(() ->
                    new UsersApiResponses.GetUserApiResponse.GetUser404ApiResponse(
                        new ErrorResponseTO("User not found: " + userId)));
        }
    }
    ```

=== ":simple-kotlin: `Kotlin`"

    ```kotlin
    package com.example.userapi.controller

    import ru.tinkoff.kora.common.Component
    import com.example.userapi.api.UsersApiDelegate
    import com.example.userapi.api.UsersApiResponses
    import com.example.userapi.model.ErrorResponseTO

    @Component
    class UserApiDelegateImpl(
        private val userService: UserService
    ) : UsersApiDelegate {

        override fun getUser(userId: String): UsersApiResponses.GetUserApiResponse =
            userService.findById(userId)
                ?.let { UsersApiResponses.GetUserApiResponse.GetUser200ApiResponse(it.toTO()) }
                ?: UsersApiResponses.GetUserApiResponse.GetUser404ApiResponse(
                    ErrorResponseTO("User not found: $userId"))
    }
    ```

### 5. Build and run

```bash
./gradlew clean classes   # runs the generator, then compiles
./gradlew run
```

---

## Server modes

Set via `configOptions.mode`. The delegate method's return type follows the mode.

| Mode | Delegate return type | Notes |
|------|----------------------|-------|
| `java-server` | `*ApiResponses.*ApiResponse` | Synchronous (recommended start) |
| `java-async-server` | `CompletionStage<*ApiResponse>` | Non-blocking |
| `java-reactive-server` | `Mono<*ApiResponse>` | Add `io.projectreactor:reactor-core` yourself |
| `kotlin-server` | `*ApiResponses.*ApiResponse` | Synchronous Kotlin |
| `kotlin-suspend-server` | `suspend fun ... : *ApiResponse` | Coroutine-based |

---

## Core rules

1. **Implement `*ApiDelegate` only.** It is the single implementation point. The
   `*ApiController` and `*ApiResponses` are generated — do not touch them.
2. **Return the generated sealed `*ApiResponses` record**, never a raw DTO. There
   is no `ResponseEntity` in Kora.
3. **A response record exists only for a status declared in the contract.** If you
   need a `GetUser500ApiResponse`, declare `"500"` under that operation's
   `responses`.
4. **`@Component` makes the delegate discoverable** by the compile-time graph.
   Keep business logic in services; the delegate maps between generated transport
   models and your internal DTOs.
5. **`openapiNormalizer = [DISABLE_ALL: "true"]`** when using `oneOf`/`allOf` — since plugin 7.0.0 the `SIMPLIFY_ONEOF_ANYOF` rule rewrites polymorphic schemas.
6. **`oneOf` without discriminator** collapses to empty record in 7.14.0 — flatten to single schema with nullable fields, or add explicit `discriminator` (see [Advanced Codegen](references/advanced-codegen-reference.md)).

---

## Common pitfalls

| Symptom | Fix |
|---------|-----|
| Delegate not discovered ("required dependency not found") | Add `@Component`; confirm it implements the generated `*ApiDelegate` from your `apiPackage`. |
| Wrong return type / compile error | Return `*ApiResponses.<Op><Status>ApiResponse`, not a DTO or `ResponseEntity`. |
| Generated classes missing | Register `outputDir` in `sourceSets.main` and add `compileJava.dependsOn` (Java) / `KspTask` `dependsOn` (Kotlin). |
| Discriminator collapsed to a single type | Set `openapiNormalizer = [DISABLE_ALL: "true"]`. |
| Validation annotations absent | Set `enableServerValidation: "true"` and add `validation-module` + `ValidationModule`. |
| Two tasks overwrite each other | Give each generator task a unique `outputDir`. |
| `/swagger-ui` missing | Add `OpenApiManagementModule` and enable `openapi.management` in config. |
| `oneOf` without discriminator generates empty record | Kora generator 7.14.0 bug — flatten to single schema with nullable fields, or add `discriminator` (see [Advanced Codegen](references/advanced-codegen-reference.md)) |
| Need raw `HttpServerRequest` in delegate | Set `requestInDelegateParams: "true"` (see [Advanced Codegen](references/advanced-codegen-reference.md)) |

---

## References

| Document | Covers |
|----------|--------|
| [Codegen Reference](references/openapi-codegen-reference.md) | Full `configOptions` table, modes, normalizer |
| [Delegates Reference](references/openapi-delegates-reference.md) | `*ApiDelegate` shapes, sync/async/reactive/suspend, `requestInDelegateParams`, `delegateMethodBodyMode` |
| [Response Reference](references/openapi-response-reference.md) | Sealed `*ApiResponses` records, headers, 204, status selection |
| [Controllers Reference](references/openapi-controllers-reference.md) | Generated controller, `prefixPath`, interceptors, validation interceptor |
| [Models Reference](references/openapi-models-reference.md) | Generated records, enums, dates, `JsonNullable`, discriminators |
| [Validation Reference](references/openapi-validation-reference.md) | Kora validation annotations from schema constraints |
| [Authorization Reference](references/authorization-reference.md) | `securitySchemes` → `HttpServerPrincipalExtractor` + `ApiSecurity` tags |

Source of truth: [openapi-codegen.md](../../.kora-agent/kora-docs/mkdocs/docs/en/documentation/openapi-codegen.md),
guides [openapi-http-server.md](../../.kora-agent/kora-docs/mkdocs/docs/en/guides/openapi-http-server.md)
and [openapi-http-server-advanced.md](../../.kora-agent/kora-docs/mkdocs/docs/en/guides/openapi-http-server-advanced.md).

## Assets

| Asset | Purpose |
|-------|---------|
| `assets/build.gradle.server.template` / `assets/build.gradle.kts.server.template` | Annotated build config for server generation |
| `assets/Application.server.java.template` / `.kt.template` | `@KoraApp` with OpenAPI management + validation |
| `assets/PetApiDelegate.server.java.template` / `.kt.template` | Delegate implementation example |
| `assets/openapi-spec.yaml.template` | Full OpenAPI 3.x spec with CRUD + discriminators |
| `assets/templates/` | Reusable spec snippets, delegate and response patterns |
| `scripts/validate_openapi.py` | Pre-generation spec sanity check |
