# OpenAPI Codegen Reference

**Source:** [.kora-agent/kora-docs/mkdocs/docs/en/documentation/openapi-codegen.md](.kora-agent/kora-docs/mkdocs/docs/en/documentation/openapi-codegen.md)  
**Examples:** `.kora-agent/kora-examples/kora-java-openapi-generator-http-server/`, `.kora-agent/kora-examples/kora-java-openapi-generator-http-client/`

## 1. Overview

Kora OpenAPI Codegen is a module for creating declarative HTTP handlers ([HTTP server](http-server.md)) or HTTP clients ([HTTP client](http-client.md)) from OpenAPI contracts using the [OpenAPI Generator plugin](https://openapi-generator.tech/docs/plugins#gradle).

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

**Requires:** [HTTP server](http-server.md) or [HTTP client](http-client.md) module.

**Important:** Each generator task must use a unique `outputDir` (e.g., `$buildDir/generated/user-api-server`, `$buildDir/generated/data-api-client`). This is critical for Gradle incremental builds and caching to work correctly.

## 3. Configuration

Configuration is required for [OpenAPI Generator plugin](https://openapi-generator.tech/docs/plugins#gradle) parameters:

- Configuring Gradle plugin parameters in [documentation](https://github.com/OpenAPITools/openapi-generator/blob/v7.14.0/modules/openapi-generator-gradle-plugin/README.adoc).
- Configuring `configOptions` plugin parameter in [documentation](https://openapi-generator.tech/docs/generators/java/#config-options).
- Configuring `openapiNormalizer` plugin parameter in [documentation](https://openapi-generator.tech/docs/customization/#openapi-normalizer).

## 4. Client Configuration

A minimal example of configuring a plugin to create a declarative HTTP client:

===! ":fontawesome-brands-java: `Java`"

    ```groovy
    def openApiGenerateHttpClient = tasks.register("openApiGenerateHttpClient", GenerateTask) {
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
            mode: "java-client", //(6)!
            clientConfigPrefix: "httpClient.myclient" //(7)!
        ]
    }
    sourceSets.main { java.srcDirs += openApiGenerateHttpClient.get().outputDir } //(8)!
    compileJava.dependsOn openApiGenerateHttpClient //(9)!
    ```

    1. Path to OpenAPI file from which classes will be created
    2. Directory where the files will be created
    3. Package from classes of delegates, controllers, converters, etc.
    4. Package from classes of models, DTOs, etc.
    5. Package from calling classes
    6. Mode of plugin operation (creating Java client / Kotlin / Java server, etc.)
    7. Prefix path to client configuration file
    8. Register the generated classes as the source code of the project
    9. Make code compilation dependent on HTTP client class generation (first generate, then compile)

=== ":simple-kotlin: `Kotlin`"

    ```kotlin
    val openApiGenerateHttpClient = tasks.register<GenerateTask>("openApiGenerateHttpClient") {
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
            "mode" to "kotlin-client", //(6)!
            "clientConfigPrefix" to "httpClient.myclient" //(7)!
        )
    }
    kotlin.sourceSets.main { kotlin.srcDir(openApiGenerateHttpClient.get().outputDir) } //(8)!
    tasks.withType<KspTask> { dependsOn(openApiGenerateHttpClient) } //(9)!
    ```

    1. Path to OpenAPI file from which classes will be created
    2. Directory where the files will be created
    3. Package from classes of delegates, controllers, converters, etc.
    4. Package from classes of models, DTOs, etc.
    5. Package from calling classes
    6. Mode of plugin operation (creating Java client / Kotlin / Java server, etc.)
    7. Prefix path to client configuration file
    8. Register the generated classes as the source code of the project
    9. Make code compilation dependent on HTTP client class generation (first generate, then compile)

**Once created, the HTTP client will be available for deployment as a dependency on the created interface.**

## 5. Server Configuration

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

## 6. Available Modes

### Client Modes

| Mode | Description | Return Type |
|------|-------------|-------------|
| `java-client` | Create synchronous client (recommended) | `T` |
| `java-async-client` | Create CompletionStage client | `CompletionStage<T>` |
| `java-reactive-client` | Create reactive client | `Mono<T>` / `Flux<T>` |
| `kotlin-client` | Create Kotlin synchronous client | `T` |
| `kotlin-suspend-client` | Create Kotlin suspend client | `suspend` function |

**Note:** Generated clients use **OkHttp** (`http-client-ok` + `OkHttpClientModule`) — the most mature HTTP client implementation in Kora.

### Server Modes

| Mode | Description | Return Type |
|------|-------------|-------------|
| `java-server` | Create synchronous server (recommended) | `ApiResponses` subclass |
| `java-async-server` | Create CompletionStage server | `CompletionStage<ApiResponses>` |
| `java-reactive-server` | Create reactive server | `Mono<ApiResponses>` |
| `kotlin-server` | Create Kotlin synchronous server | `ApiResponses` subclass |
| `kotlin-suspend-server` | Create Kotlin suspend server | `suspend` function |

**Note:** 
- Generated delegates return `ApiResponses` wrapper classes (e.g., `PetApiResponses.GetPetByIdApiResponse`), not `ResponseEntity<T>`.
- For server projects, use **Undertow** (`http-server-undertow` + `UndertowHttpServerModule`) — the recommended HTTP server in Kora.

## 7. Config Options Reference

### Client Options

| Option | Type | Description |
|--------|------|-------------|
| `mode` | String | **Required.** Client mode: `java-client`, `java-async-client`, `java-reactive-client`, `kotlin-client`, `kotlin-suspend-client` |
| `clientConfigPrefix` | String | Configuration prefix for generated HTTP clients |
| `interceptors` | JSON | Interceptors configuration (see Interceptors section) |
| `tags` | JSON | HTTP client tags configuration (see Tags section) |
| `primaryAuth` | String | Primary authentication mechanism if multiple securitySchemes defined |
| `securityConfigPrefix` | String | Configuration prefix for Basic/ApiKey authentication |
| `authAsMethodArgument` | Boolean | Pass auth as method argument instead of interceptor |
| `authAllowMultiple` | Boolean | Generate interceptors for multi-authentication |
| `additionalContractAnnotations` | String | Additional annotations on HTTP client methods |
| `enableJsonNullable` | Boolean | Use JsonNullable for nullable=true, required=false fields |
| `forceIncludeOptional` | Boolean | Force @JsonInclude(Always) for nullable=true, required=false |
| `forceIncludeNonRequired` | Boolean | Force @JsonInclude(Always) for required=false fields |
| `filterWithModels` | Boolean | Filter models when FILTER option in openapiNormalizer is specified |

### Server Options

| Option | Type | Description |
|--------|------|-------------|
| `mode` | String | **Required.** Server mode: `java-server`, `java-async-server`, `java-reactive-server`, `kotlin-server`, `kotlin-suspend-server` |
| `enableServerValidation` | Boolean | Generate validation annotations per OpenAPI spec |
| `requestInDelegateParams` | Boolean | Include HttpServerRequest as delegate method argument |
| `interceptors` | JSON | Interceptors configuration for controllers |
| `prefixPath` | String | Path prefix for HTTP server controllers |
| `delegateMethodBodyMode` | String | `none` (no body) or `throw-exception` (throw exception) |
| `additionalContractAnnotations` | String | Additional annotations on controller methods |
| `enableJsonNullable` | Boolean | Use JsonNullable for nullable=true, required=false fields |
| `forceIncludeOptional` | Boolean | Force @JsonInclude(Always) for nullable=true, required=false |
| `forceIncludeNonRequired` | Boolean | Force @JsonInclude(Always) for required=false fields |
| `filterWithModels` | Boolean | Filter models when FILTER option in openapiNormalizer is specified |

## 8. OpenAPI Normalizer

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

