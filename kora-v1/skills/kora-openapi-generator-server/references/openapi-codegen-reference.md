# OpenAPI Codegen Reference (Server)

**Source:** [openapi-codegen.md](../../../.kora-agent/kora-docs/mkdocs/docs/en/documentation/openapi-codegen.md)  
**Example:** `.kora-agent/kora-examples/examples/java/kora-java-openapi-generator-http-server/`

## Contents

- [1. Overview](#1-overview)
- [2. Dependency](#2-dependency)
- [3. Configuration](#3-configuration)
- [4. Server Configuration](#4-server-configuration)
- [5. Server Modes](#5-server-modes)
- [6. Server Config Options](#6-server-config-options)
- [7. OpenAPI Normalizer](#7-openapi-normalizer)
- [8. Discriminators (oneOf + allOf)](#8-discriminators-oneof--allof)

## 1. Overview

The Kora OpenAPI Codegen module creates declarative HTTP server handlers from
OpenAPI contracts using the `kora` generator of the
[OpenAPI Generator Gradle plugin](https://openapi-generator.tech/docs/plugins#gradle).
This reference covers the **server** side; the same plugin can also generate HTTP
clients with a `*-client` mode (see the `kora-openapi-generator-client` skill).

## 2. Dependency

===! ":fontawesome-brands-java: `Java`"

    **Buildscript dependency:**
    ```groovy
    buildscript {
        dependencies {
            classpath("ru.tinkoff.kora:openapi-generator:$koraVersion")
        }
    }
    ```

    **Plugin dependency:**
    ```groovy
    plugins {
        id "org.openapi.generator" version "7.14.0"
    }
    ```

    Use of other versions of the plugin is not guaranteed as it may not be compatible at the code level.

=== ":simple-kotlin: `Kotlin`"

    **Buildscript dependency:**
    ```kotlin
    buildscript {
        dependencies {
            classpath("ru.tinkoff.kora:openapi-generator:$koraVersion")
        }
    }
    ```

    **Plugin dependency:**
    ```kotlin
    plugins {
        id("org.openapi.generator") version("7.14.0")
    }
    ```

**Requires:** the HTTP server module ([http-server.md](../../../.kora-agent/kora-docs/mkdocs/docs/en/documentation/http-server.md)) or the HTTP client module ([http-client.md](../../../.kora-agent/kora-docs/mkdocs/docs/en/documentation/http-client.md)).

**Important:** Each generator task must use a unique `outputDir` (e.g., `$buildDir/generated/user-api-server`, `$buildDir/generated/data-api-client`). This is critical for Gradle incremental builds and caching to work correctly.

## 3. Configuration

Configuration is required for [OpenAPI Generator plugin](https://openapi-generator.tech/docs/plugins#gradle) parameters:

- Configuring Gradle plugin parameters in the [OpenAPI Generator Gradle plugin docs](https://openapi-generator.tech/docs/plugins#gradle).
- Configuring `configOptions` plugin parameter in [documentation](https://openapi-generator.tech/docs/generators/java/#config-options).
- Configuring `openapiNormalizer` plugin parameter in [documentation](https://openapi-generator.tech/docs/customization/#openapi-normalizer).


## 4. Server Configuration

A minimal example of configuring a plugin to create HTTP server handlers:

===! ":fontawesome-brands-java: `Java`"

    ```groovy
    def openApiGenerateHttpServer = tasks.register("openApiGenerateHttpServer", GenerateTask) {
        generatorName = "kora"
        group = "openapi tools"
        inputSpec = "$projectDir/src/main/resources/openapi/openapi.yaml" //(1)!
        outputDir = "$buildDir/generated/openapi" //(2)!  
        def corePackage = "ru.tinkoff.kora.example.openapi"
        apiPackage = "${corePackage}.api" //(3)!
        modelPackage = "${corePackage}.model" //(4)!
        invokerPackage = "${corePackage}.invoker" //(5)!
        openapiNormalizer = [
            DISABLE_ALL: "true"
        ]
        configOptions = [
            mode: "java-server" //(6)!
        ]
    }
    sourceSets.main { java.srcDirs += openApiGenerateHttpServer.get().outputDir } //(7)!
    compileJava.dependsOn openApiGenerateHttpServer //(8)!
    ```

    1. Path to OpenAPI file from which classes will be created
    2. Directory where the files will be created
    3. Package from classes of delegates, controllers, converters, etc.
    4. Package from classes of models, DTOs, etc.
    5. Package from calling classes
    6. Mode of plugin operation (creating Java client / Kotlin / Java server, etc.)
    7. Register the generated classes as the source code of the project
    8. Make code compilation dependent on HTTP client class generation (first generate, then compile)

=== ":simple-kotlin: `Kotlin`"

    ```kotlin
    val openApiGenerateHttpServer = tasks.register<GenerateTask>("openApiGenerateHttpServer") {
        generatorName = "kora"
        group = "openapi tools"
        inputSpec = "$projectDir/src/main/resources/openapi/openapi.yaml" //(1)!
        outputDir = "$buildDir/generated/openapi" //(2)!
        val corePackage = "ru.tinkoff.kora.example.openapi"
        apiPackage = "${corePackage}.api" //(3)!
        modelPackage = "${corePackage}.model" //(4)!
        invokerPackage = "${corePackage}.invoker" //(5)!
        openapiNormalizer = mapOf(
            "DISABLE_ALL" to "true"
        )
        configOptions = mapOf(
            "mode" to "kotlin-server" //(6)!
        )
    }
    kotlin.sourceSets.main { kotlin.srcDir(openApiGenerateHttpServer.get().outputDir) } //(7)!
    tasks.withType<KspTask> { dependsOn(openApiGenerateHttpServer) } //(8)!
    ```

    1. Path to OpenAPI file from which classes will be created
    2. Directory where the files will be created
    3. Package from classes of delegates, controllers, converters, etc.
    4. Package from classes of models, DTOs, etc.
    5. Package from calling classes
    6. Mode of plugin operation (creating Java client / Kotlin / Java server, etc.)
    7. Register the generated classes as the source code of the project
    8. Make code compilation dependent on HTTP client class generation (first generate, then compile)

**Once created, the handlers will be automatically registered.**

## 5. Server Modes

Set via `configOptions.mode`. The delegate method return type follows the mode.

| Mode | Description | Delegate return type |
|------|-------------|----------------------|
| `java-server` | Synchronous server (recommended start) | `*ApiResponses.*ApiResponse` |
| `java-async-server` | `CompletionStage` server | `CompletionStage<*ApiResponse>` |
| `java-reactive-server` | Reactive server (add `io.projectreactor:reactor-core`) | `Mono<*ApiResponse>` |
| `kotlin-server` | Synchronous Kotlin server | `*ApiResponses.*ApiResponse` |
| `kotlin-suspend-server` | Coroutine Kotlin server | `suspend fun ...: *ApiResponse` |

**Note:**
- Generated delegates return the sealed `*ApiResponses` records (e.g.,
  `PetApiResponses.GetPetByIdApiResponse`) — Kora has no `ResponseEntity`.
- Use the **Undertow** server module (`http-server-undertow` +
  `UndertowHttpServerModule`).

## 6. Server Config Options

| Option | Type | Description |
|--------|------|-------------|
| `mode` | String | **Required.** `java-server`, `java-async-server`, `java-reactive-server`, `kotlin-server`, `kotlin-suspend-server` |
| `enableServerValidation` | Boolean | Generate Kora validation annotations and enable validation on handlers |
| `enableServerValidationInterceptor` | Boolean | Add a validator interceptor that maps validation failures to a separate HTTP response |
| `requestInDelegateParams` | Boolean | Pass `HttpServerRequest` as a delegate method argument |
| `interceptors` | JSON | Interceptors for the generated `@HttpController`s |
| `additionalContractAnnotations` | String | Additional annotations on controller methods |
| `prefixPath` | String | Path prefix for all generated controllers |
| `delegateMethodBodyMode` | String | `none` (no body) or `throw-exception` (throw + generate a default delegate module if none is provided) |
| `enableJsonNullable` | Boolean | Treat `nullable=true` + `required=false` fields as `JsonNullable` |
| `forceIncludeOptional` | Boolean | Force `@JsonInclude(Always)` for `nullable=true` + `required=false` |
| `forceIncludeNonRequired` | Boolean | Force `@JsonInclude(Always)` for `required=false` |
| `filterWithModels` | Boolean | Also exclude unused models when `FILTER` is set in `openapiNormalizer` |

## 7. OpenAPI Normalizer

The `openapiNormalizer` parameter allows customizing OpenAPI spec processing:

```groovy
openapiNormalizer = [
    DISABLE_ALL: "true"  // Disable all normalizers
]
```

**Important:** Starting with plugin version `7.0.0`, the `SIMPLIFY_ONEOF_ANYOF` rule is enabled by default and may lead to unexpected generator results.

See [OpenAPI Normalizer documentation](https://openapi-generator.tech/docs/customization/#openapi-normalizer) for available rules.

## 8. Discriminators (oneOf + allOf)

**Discriminators** are an OpenAPI mechanism for polymorphic schemas — when a request can be one of several types with a common base.

### When to Use

- **Different request types** with shared fields (draft/published, tentative/final)
- **Payment options** (card/invoice/crypto) with common metadata
- **Notification types** (email/sms/push) with different delivery parameters

### Pattern: oneOf + allOf + discriminator

```yaml
MyPolymorphicRequest:
  type: object
  oneOf:
    - $ref: '#/components/schemas/TypeARequest'
    - $ref: '#/components/schemas/TypeBRequest'
  allOf:
    - $ref: '#/components/schemas/CommonBase'
  discriminator:
    propertyName: requestType  # Key field for type selection
    mapping:
      TYPE_A: '#/components/schemas/TypeARequest'
      TYPE_B: '#/components/schemas/TypeBRequest'
```

### What Gets Generated

- **Base class** with common fields (`CommonBase`)
- **Subclasses** for each type with specific fields
- **Discriminator field** (`requestType`) for type selection
- **Factory methods** to create correct type by discriminator

### Example from Template

See `assets/openapi-spec.yaml.template` for a complete example with migrations:

```yaml
Task:
  oneOf:
    - $ref: '#/components/schemas/TaskUnconfirmed'
    - $ref: '#/components/schemas/TaskConfirmed'
  allOf:
    - $ref: '#/components/schemas/TaskCommon'
  discriminator:
    propertyName: migrationType
    mapping:
      UNCONFIRMED: '#/components/schemas/TaskUnconfirmed'
      CONFIRMED: '#/components/schemas/TaskConfirmed'
```

### Delegate Implementation

```java
@Override
public MigrationApiResponses.CreateMigrationApiResponse createMigration(
    Task request
) {
    if (request.getMigrationType() == MigrationType.UNCONFIRMED) {
        // Requires script field
        if (request.getScript() == null) {
            return new CreateMigration400ApiResponse("Script required");
        }
        Task task = migrationService.createUnconfirmed(request);
        return new CreateMigration201ApiResponse(task);
    } 
    else if (request.getMigrationType() == MigrationType.CONFIRMED) {
        // Requires scriptKey field
        if (request.getScriptKey() == null) {
            return new CreateMigration400ApiResponse("ScriptKey required");
        }
        Task task = migrationService.createConfirmed(request);
        return new CreateMigration201ApiResponse(task);
    }
    return new CreateMigration400ApiResponse("Unknown type");
}
```

### Best Practices

1. **Always provide `example`** — helps with generation and testing
2. **Keep common base minimal** — only truly shared fields
3. **Use enum for discriminator** — type safety and validation
4. **Document each type** — when to use which
5. **Check discriminator explicitly in delegate** — clear logic over magic

### Troubleshooting

| Problem | Solution |
|---------|----------|
| Generator ignores discriminator | Ensure `propertyName` exists in all variants |
| Wrong type generated | Check `mapping` — keys must match enum values |
| Common fields not inherited | Check order: `oneOf` before `allOf` in spec |
| Example fails | Example must have all required fields from common + selected type |

