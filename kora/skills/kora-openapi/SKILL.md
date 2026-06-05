---
name: kora-openapi
description: OpenAPI integration in Kora: generate HTTP clients/servers from OpenAPI specs (openapi-codegen), publish OpenAPI specifications (openapi-management), Swagger UI, Rapidoc documentation. Use for contract-first API development with automatic code generation, type-safe clients, and API documentation. Triggers: OpenAPI spec, openapi-codegen, @OpenApiCodegen, Swagger UI, Rapidoc, API documentation, contract-first, java-client/java-server generators.
---

# Kora OpenAPI — Contract-First HTTP API Development

Comprehensive guide to working with OpenAPI in Kora:
1. **OpenAPI Codegen** — generating type-safe HTTP clients and servers from OpenAPI specifications
2. **OpenAPI Management** — publishing OpenAPI specifications, Swagger UI, Rapidoc for API documentation

**When to use:**
- An HTTP client is needed for an external API that has an OpenAPI specification
- A REST API server with automatic documentation is needed
- Contract-first development (OpenAPI first, then code)
- Avoiding manual boilerplate code for DTOs and controllers
- Swagger UI or Rapidoc is needed for API documentation

**Recommendations:**
- **Contract-first approach:** Always use the OpenAPI contract as the primary source of truth — generate code from the specification, not the other way around. **Exception:** complex contracts with binary data, specific formats, or other elements that are hard to express in OpenAPI or that generate incorrectly — such controllers (typically 1 per entire API) are implemented manually without the OpenAPI generator
- **HTTP Client:** **`http-client-ok` (OkHttp) is recommended** — the most mature and performant HTTP client implementation in Kora. `http-client-jdk` (JDK HttpClient) is available as an alternative
- **HTTP Server:** Use `http-server-undertow` — the most mature HTTP server implementation in Kora
- **Synchronous contracts:** `java-client`/`java-server` is recommended for simplicity and performance
- **Separate generation:** Each API/module must generate into a separate directory (see Gradle Configuration)

Read this first when:
- generating type-safe HTTP clients from OpenAPI specs (`java-client`, `kotlin-client`),
- generating REST server delegates from OpenAPI specs (`java-server`, `kotlin-server`),
- publishing OpenAPI specifications with Swagger UI or Rapidoc documentation,
- working with polymorphic schemas using `oneOf` + `allOf` + discriminator,
- configuring separate output directories for multiple OpenAPI generators.

## Quick Start

### 1. Add Plugin Dependency

```groovy
buildscript {
    dependencies {
        classpath("ru.tinkoff.kora:openapi-generator:$koraVersion")
    }
}
```

### 2. Connect the Plugin

```groovy
plugins {
    id "org.openapi.generator" version "7.14.0"  // Recommended version
}
```

**Note:** Version 7.14.0 is the recommended version for use with the Kora OpenAPI Generator.

### 3. Configure Generation (client)

```groovy
def openApiGenerateHttpClient = tasks.register("openApiGenerateHttpClient", GenerateTask) {
    generatorName = "kora"
    group = "openapi tools"
    inputSpec = "$projectDir/src/main/resources/openapi/my-api.yaml"
    outputDir = "$buildDir/generated/my-api-client"  // Unique directory per API
    def corePackage = "com.example.myapi"
    apiPackage = "${corePackage}.api"
    modelPackage = "${corePackage}.model"
    invokerPackage = "${corePackage}.invoker"
    configOptions = [
        mode: "java-client",
        clientConfigPrefix: "httpClient.myApi"
    ]
}
sourceSets.main { java.srcDirs += openApiGenerateHttpClient.get().outputDir }
compileJava.dependsOn openApiGenerateHttpClient
```

**Important:** Each generator must use a unique `outputDir` (e.g., `$buildDir/generated/my-api-client`, `$buildDir/generated/user-api-server`). This is critical for Gradle cache and incremental build to work correctly.

### 4. Add Dependencies (client)

```groovy
dependencies {
    koraBom platform("ru.tinkoff.kora:kora-parent:$koraVersion")
    annotationProcessor "ru.tinkoff.kora:annotation-processors"
    
    // HTTP Client (OkHttp - recommended)
    implementation "ru.tinkoff.kora:http-client-ok"
    implementation "ru.tinkoff.kora:json-module"
    implementation "ru.tinkoff.kora:logging-logback"
    implementation "ru.tinkoff.kora:config-hocon"
}
```

### 5. Configure Generation (server)

```groovy
def openApiGenerateHttpServer = tasks.register("openApiGenerateHttpServer", GenerateTask) {
    generatorName = "kora"
    group = "openapi tools"
    inputSpec = "$projectDir/src/main/resources/openapi/my-api.yaml"
    outputDir = "$buildDir/generated/my-api-server"  // Unique directory per API
    def corePackage = "com.example.myapi"
    apiPackage = "${corePackage}.api"
    modelPackage = "${corePackage}.model"
    invokerPackage = "${corePackage}.invoker"
    configOptions = [
        mode: "java-server",
        enableServerValidation: "true"
    ]
}
sourceSets.main { java.srcDirs += openApiGenerateHttpServer.get().outputDir }
compileJava.dependsOn openApiGenerateHttpServer
```

### 6. Add Dependencies (server)

**Client:**
```java
@Root
@Component
public final class MyService {
    private final MyApi api;
    public MyService(MyApi api) { this.api = api; }  // Auto-inject
}
```

**Server (Delegate):**
```java
@Component
public final class MyApiDelegate implements MyApiDelegate {
    @Override
    public MyApiResponses.GetPetByIdApiResponse getPetById(Long petId) {
        // Return ApiResponse, not ResponseEntity
        if (petId < 0) {
            return new MyApiResponses.GetPetByIdApiResponse.GetPetById400ApiResponse();
        }
        Pet pet = petService.findById(petId);
        if (pet == null) {
            return new MyApiResponses.GetPetByIdApiResponse.GetPetById404ApiResponse();
        }
        return new MyApiResponses.GetPetByIdApiResponse.GetPetById200ApiResponse(pet);
    }
}
```

**Note:** The delegate returns concrete ApiResponse subclasses for each HTTP status (200, 400, 404, etc.).

---

## 🔍 Examples and Source Code

**Reference examples:**
- `.kora-agent/kora-examples/kora-java-openapi-generator-http-server/` — example HTTP server with delegates
- `.kora-agent/kora-examples/kora-java-openapi-generator-http-client/` — example HTTP client

**Useful files to study:**
- `PetV2Delegate.java` — example delegate implementation with ApiResponse return values
- `RootService.java` — example usage of the generated client
- `build.gradle` — correct generation setup with multiple APIs

**If something is not working:**
1. Check the examples in `.kora-agent/kora-examples/` — they contain working configurations
2. Study the generated code in `$buildDir/generated/` — understand what is being generated
3. Read the Kora OpenAPI Generator source code in `$buildDir/generated/sources/annotationProcessor/`

**💡 Tip: Study the generated delegate code**
Before implementing a delegate, open the generated code in `$buildDir/generated/` and examine:
- The structure of `*Delegate` interfaces
- Which methods need to be implemented
- Which types are returned (`ApiResponses` and their subclasses)
- How different HTTP statuses are handled

This helps understand the expected structure and avoid implementation errors.

---

## Gradle Configuration

### Buildscript Dependencies

```groovy
buildscript {
    dependencies {
        classpath("ru.tinkoff.kora:openapi-generator:$koraVersion")  // Same version as Kora
    }
}

plugins {
    id "org.openapi.generator" version "7.14.0"  // Recommended plugin version
}
```

### Kotlin (build.gradle.kts)

```kotlin
buildscript {
    dependencies {
        classpath("ru.tinkoff.kora:openapi-generator:$koraVersion")
    }
}

plugins {
    id("org.openapi.generator") version("7.14.0")
}
```

---

## Generation Modes

### Clients (Client Modes)

| Mode | Description | Return Type |
|------|-------------|-------------|
| `java-client` | Synchronous client | `T` |
| `java-async-client` | Asynchronous client | `CompletionStage<T>` |
| `java-reactive-client` | Reactive client | `Mono<T>` / `Flux<T>` |
| `kotlin-client` | Kotlin synchronous | `T` |
| `kotlin-suspend-client` | Kotlin suspend | `suspend` function |

### Servers (Server Modes)

| Mode | Description | Return Type |
|------|-------------|-------------|
| `java-server` | Synchronous server | `ApiResponses` subclass |
| `java-async-server` | Asynchronous server | `CompletionStage<ApiResponses>` |
| `java-reactive-server` | Reactive server | `Mono<ApiResponses>` |
| `kotlin-server` | Kotlin synchronous | `ApiResponses` subclass |
| `kotlin-suspend-server` | Kotlin suspend | `suspend` function |

---

## 💚 Kotlin Specifics

### Generating Kotlin Clients

**Recommendation:** Use `kotlin-client` for synchronous clients or `kotlin-suspend-client` for suspend functions.

**Generation example:**
```groovy
def openApiGenerateHttpClient = tasks.register("openApiGenerateHttpClient", GenerateTask) {
    generatorName = "kora"
    inputSpec = "$projectDir/src/main/resources/openapi/my-api.yaml"
    outputDir = "$buildDir/generated/my-api-client"
    def corePackage = "com.example.myapi"
    apiPackage = "${corePackage}.api"
    modelPackage = "${corePackage}.model"
    invokerPackage = "${corePackage}.invoker"
    configOptions = [
        mode: "kotlin-client",  // or "kotlin-suspend-client"
        clientConfigPrefix: "httpClient.myApi"
    ]
}
```

**Usage example (see `PetService.client.kt.template`):**
```kotlin
@Root
@Component
class PetService(
    private val petApi: PetApi
) {
    fun getPet(petId: Long): Pet {
        return petApi.getPetById(petId)
    }
}
```

### Generating Kotlin Servers

**Recommendation:** Use `kotlin-server` for synchronous servers or `kotlin-suspend-server` for suspend functions.

**Generation example:**
```groovy
def openApiGenerateHttpServer = tasks.register("openApiGenerateHttpServer", GenerateTask) {
    generatorName = "kora"
    inputSpec = "$projectDir/src/main/resources/openapi/my-api.yaml"
    outputDir = "$buildDir/generated/my-api-server"
    def corePackage = "com.example.myapi"
    apiPackage = "${corePackage}.api"
    modelPackage = "${corePackage}.model"
    invokerPackage = "${corePackage}.invoker"
    configOptions = [
        mode: "kotlin-server",  // or "kotlin-suspend-server"
        enableServerValidation: "true"
    ]
}
```

**Delegate implementation example (see `PetApiDelegate.server.kt.template`):**
```kotlin
@Component
class PetApiDelegate : ru.tinkoff.kora.example.api.PetApiDelegate {

    override fun getPetById(petId: Long): GetPetByIdApiResponse {
        if (petId < 0) {
            return GetPetByIdApiResponse.GetPetById400ApiResponse()
        }
        val pet = petService.findById(petId) ?: return GetPetByIdApiResponse.GetPetById404ApiResponse()
        return GetPetByIdApiResponse.GetPetById200ApiResponse(pet)
    }
}
```

**Important:** 
- The delegate returns concrete `ApiResponses` subclasses for each HTTP status
- Kotlin versions use `override fun` instead of `@Override`
- Data models are generated as Kotlin data classes

### Application Graph (Kotlin)

**Client (see `Application.client.kt.template`):**
```kotlin
@KoraApp
interface Application :
    HoconConfigModule,
    LogbackModule,
    JsonModule,
    ValidationModule,
    OkHttpClientModule {
    companion object {
        @JvmStatic
        fun main(args: Array<String>) {
            KoraApplication.run(ApplicationGraph::graph)
        }
    }
}
```

**Server (see `Application.server.kt.template`):**
```kotlin
@KoraApp
interface Application :
    HoconConfigModule,
    LogbackModule,
    JsonModule,
    ValidationModule,
    UndertowHttpServerModule {
    companion object {
        @JvmStatic
        fun main(args: Array<String>) {
            KoraApplication.run(ApplicationGraph::graph)
        }
    }

    fun violationExceptionHttpServerResponseMapper(): ViolationExceptionHttpServerResponseMapper {
        return ViolationExceptionHttpServerResponseMapper { request, exception ->
            ru.tinkoff.kora.http.server.common.HttpServerResponseException.of(
                400,
                exception.message
            )
        }
    }
}
```

---

## Configuration

### Config Options (Client)

```groovy
configOptions = [
    mode: "java-client",                    // Generation mode (synchronous recommended)
    clientConfigPrefix: "httpClient.myApi", // Configuration prefix
    interceptors: """...""",                // Interceptors (JSON)
    tags: """...""",                        // Tags (JSON)
    primaryAuth: "bearerAuth",              // Primary auth mechanism
    securityConfigPrefix: "auth",           // Auth config prefix
    authAsMethodArgument: "false",          // Pass auth as method argument
    authAllowMultiple: "false",             // Multi-auth interceptors
    enableJsonNullable: "true",             // JsonNullable for nullable fields
    forceIncludeOptional: "false",          // Force @JsonInclude(Always)
    forceIncludeNonRequired: "false",       // Force for required=false
    filterWithModels: "true"                // Filter models with FILTER
]
```

**Recommendation:** Use `java-client` (synchronous) for most cases — it is simpler and more performant.

### Config Options (Server)

```groovy
configOptions = [
    mode: "java-server",                    // Generation mode (synchronous recommended)
    enableServerValidation: "true",         // Validation per OpenAPI spec
    requestInDelegateParams: "false",       // HttpServerRequest in delegate params
    interceptors: """...""",                // Interceptors (JSON)
    prefixPath: "/api/v1",                  // Path prefix
    delegateMethodBodyMode: "throw-exception", // Delegate method body mode
    enableJsonNullable: "true",
    forceIncludeOptional: "false",
    forceIncludeNonRequired: "false",
    filterWithModels: "true"
]
```

**Recommendation:** Use `java-server` (synchronous) for most cases — it is simpler and more performant.

### OpenAPI Normalizer

```groovy
openapiNormalizer = [
    DISABLE_ALL: "true"  // Disable all normalizers
]
```

**Important:** Starting with plugin version `7.0.0`, the `SIMPLIFY_ONEOF_ANYOF` rule is enabled by default and may lead to unexpected generator results.

---

## 🔌 Interceptors and Tags

### Interceptors (Client and Server)

```groovy
configOptions = [
    mode: "java-client",
    interceptors: """
        {
          "*": [
            {
              "tag": "com.example.MyTag"
            }
          ],
          "pet": [
            {
              "type": "com.example.MyInterceptor"
            }
          ],
          "shop": [
            {
              "type": "com.example.MyInterceptor",
              "tag": "com.example.MyTag"
            }
          ]
        }
        """
]
```

### Tags (Client)

```groovy
configOptions = [
    mode: "java-client",
    tags: """
        {
          "*": {
            "httpClientTag": "some.tag.Common",
            "telemetryTag": "some.tag.Common"
          },
          "instrument": {
            "httpClientTag": "some.tag.Instrument",
            "telemetryTag": "some.tag.Instrument"
          }
        }
        """
]
```

---

## Authorization (Server)

### Bearer Auth Extractor

```java
@Module
public interface AuthModule {
    @Tag(ApiSecurity.BearerAuth.class)
    default HttpServerPrincipalExtractor<MyPrincipal> bearerHttpServerPrincipalExtractor() {
        return (request, value) -> CompletableFuture.completedFuture(
            new MyPrincipal(request.headers().getFirst("Authorization"))
        );
    }
}
```

### API Key Auth Extractor

```java
@Module
public interface AuthModule {
    @Tag(ApiSecurity.ApiKeyAuth.class)
    default HttpServerPrincipalExtractor<MyPrincipal> apiKeyHttpServerPrincipalExtractor() {
        return (request, value) -> CompletableFuture.completedFuture(
            new MyPrincipal(value)
        );
    }
}
```

### Basic Auth Extractor

```java
@Module
public interface AuthModule {
    @Tag(ApiSecurity.BasicAuth.class)
    default HttpServerPrincipalExtractor<MyPrincipal> basicHttpServerPrincipalExtractor() {
        return (request, value) -> {
            // Parse Basic auth header: "Basic base64(username:password)"
            String authHeader = request.headers().getFirst("Authorization");
            String credentials = authHeader.substring("Basic ".length());
            String decoded = new String(Base64.getDecoder().decode(credentials), StandardCharsets.UTF_8);
            String[] parts = decoded.split(":");
            String username = parts[0];
            String password = parts[1];
            // Validate credentials and return Principal
            return CompletableFuture.completedFuture(new MyPrincipal(username, password));
        };
    }
}
```

---

## Validation (Server)

### Enable Validation

```groovy
configOptions = [
    mode: "java-server",
    enableServerValidation: "true"
]
```

**What gets generated:**
- Validation annotations on DTOs (`@NotNull`, `@Size`, `@Pattern`, etc.)
- Input parameter validation in controllers
- Automatic 400 responses on constraint violations

---

## Project Structure

```
my-app/
├── build.gradle
├── src/main/
│   ├── java/com/example/
│   │   ├── Application.java
│   │   └── api/
│   │       └── MyApiDelegate.java  # Delegate implementation
│   └── resources/openapi/
│       └── my-api.yaml             # OpenAPI specification
└── build/generated/openapi/        # Generated code
    ├── api/                        # Controllers/Delegates
    └── model/                      # DTOs
```

---

## Troubleshooting

| Problem | Solution |
|---------|---------|
| Classes are not generated | Check the `inputSpec` path |
| Compilation error | Ensure `compileJava.dependsOn openApiGenerate*` |
| Wrong types | Check `mode` in configOptions |
| No validation | Add `enableServerValidation: "true"` |
| Name conflicts | Use `filterWithModels` + `openapiNormalizer.FILTER` |

---

## Working with Discriminators (oneOf + allOf)

**Discriminators** are an OpenAPI mechanism for polymorphic schemas — when a request can be one of several types with a common base.

### When to Use

- **Different request types** with a common base (e.g., draft/published, draft/final)
- **Payment options** (card/invoice/crypto) with common fields
- **Notification types** (email/sms/push) with different delivery parameters

### Pattern: oneOf + allOf + discriminator

```yaml
MyPolymorphicRequest:
  type: object
  description: Request with type selection via discriminator
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
  example:
    requestType: TYPE_A
    # ... common fields from CommonBase
    # ... specific fields from TypeARequest
```

### Example from templates/openapi-spec.yaml

The specification template includes an example with migrations:

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

**What gets generated:**
- **CommonBase class** with shared fields (`TaskCommon`)
- **Subclasses** for each type with unique fields
- **Discriminator field** (`migrationType`) for type selection
- **Factory method** to create the correct type by discriminator

### Delegate for Working with a Discriminator

```java
@Override
public MigrationApiResponses.CreateMigrationApiResponse createMigration(
    Task request
) {
    // Check type via discriminator
    if (request.getMigrationType() == MigrationType.UNCONFIRMED) {
        // script field is required
        if (request.getScript() == null) {
            return new MigrationApiResponses.CreateMigrationApiResponse
                .CreateMigration400ApiResponse("Script required for UNCONFIRMED");
        }
        // Run test migration
        Task task = migrationService.createUnconfirmed(request);
        return new MigrationApiResponses.CreateMigrationApiResponse
            .CreateMigration201ApiResponse(task);
    } 
    else if (request.getMigrationType() == MigrationType.CONFIRMED) {
        // scriptKey field is required
        if (request.getScriptKey() == null) {
            return new MigrationApiResponses.CreateMigrationApiResponse
                .CreateMigration400ApiResponse("ScriptKey required for CONFIRMED");
        }
        // Run final migration
        Task task = migrationService.createConfirmed(request);
        return new MigrationApiResponses.CreateMigrationApiResponse
            .CreateMigration201ApiResponse(task);
    }
    else {
        return new MigrationApiResponses.CreateMigrationApiResponse
            .CreateMigration400ApiResponse("Unknown migration type");
    }
}
```

### Best Practices

1. **Always provide `example`** — helps with generation and testing
2. **Keep the common base minimal** — only truly shared fields
3. **Use enum for the discriminator** — type safety and validation
4. **Document each type** — what it selects, when to use it
5. **Check the discriminator explicitly in the delegate** — clear logic over magic

### Discriminator Troubleshooting

| Problem | Solution |
|---------|---------|
| Generator does not see discriminator | Ensure `propertyName` exists in all variants |
| Wrong type generated | Check `mapping` — keys must match enum values |
| Common fields not inherited | Check order: `oneOf` before `allOf` in spec |
| Example fails | Example must contain all required fields from common + selected type |

**Example in assets:** See `assets/openapi-spec.yaml.template` — the `/migrations` section with a complete example.

---

## Quick Reference

### Plugin Configuration Template

```groovy
def openApiGenerate = tasks.register("openApiGenerate", GenerateTask) {
    generatorName = "kora"
    group = "openapi tools"
    inputSpec = "$projectDir/src/main/resources/openapi/api.yaml"
    outputDir = "$buildDir/generated/openapi"
    def corePackage = "com.example.api"
    apiPackage = "${corePackage}.api"
    modelPackage = "${corePackage}.model"
    invokerPackage = "${corePackage}.invoker"
    openapiNormalizer = [DISABLE_ALL: "true"]
    configOptions = [
        mode: "java-client",  // or "java-server"
        clientConfigPrefix: "httpClient.myApi"
    ]
}
sourceSets.main { java.srcDirs += openApiGenerate.get().outputDir }
compileJava.dependsOn openApiGenerate
```

### Mode Selection

| Task | Mode |
|------|------|
| Synchronous HTTP client (OkHttp) | `java-client` |
| Asynchronous HTTP client | `java-async-client` |
| Reactive HTTP client | `java-reactive-client` |
| Synchronous REST server (Undertow) | `java-server` |
| Asynchronous REST server | `java-async-server` |
| Reactive REST server | `java-reactive-server` |
| Asynchronous REST server | `java-async-server` |
| Reactive REST server | `java-reactive-server` |
| Kotlin client | `kotlin-client` |
| Kotlin server | `kotlin-server` |

### Config Options Quick List

**Client:** `mode`, `clientConfigPrefix`, `interceptors`, `tags`, `primaryAuth`, `securityConfigPrefix`, `authAsMethodArgument`, `authAllowMultiple`, `enableJsonNullable`, `forceIncludeOptional`, `forceIncludeNonRequired`, `filterWithModels`

**Server:** `mode`, `enableServerValidation`, `requestInDelegateParams`, `interceptors`, `prefixPath`, `delegateMethodBodyMode`, `enableJsonNullable`, `forceIncludeOptional`, `forceIncludeNonRequired`, `filterWithModels`

---

## Reference Files

### OpenAPI Codegen

| File | Description |
|------|-------------|
| [references/openapi-codegen-reference.md](references/openapi-codegen-reference.md) | Full OpenAPI Generator reference |
| [references/authorization-reference.md](references/authorization-reference.md) | Authorization (Bearer/ApiKey/Basic/OAuth) |
| [references/interceptors-reference.md](references/interceptors-reference.md) | Interceptors for clients and servers |
| [references/validation-reference.md](references/validation-reference.md) | Server-side validation |
| [references/kotlin-reference.md](references/kotlin-reference.md) | Kotlin specifics |

### OpenAPI Management

| File | Description |
|------|-------------|
| [references/openapi-management-reference.md](references/openapi-management-reference.md) | Publishing OpenAPI, Swagger UI, Rapidoc |

---

## Assets

### Java Templates

| File | Description |
|------|-------------|
| `build.gradle.client.template` | Gradle build with OpenAPI generation (client) |
| `build.gradle.server.template` | Gradle build with OpenAPI generation (server) |
| `Application.client.java.template` | Application graph with OkHttpClientModule (client) |
| `Application.server.java.template` | Application graph with UndertowHttpServerModule (server) |
| `PetApiDelegate.server.java.template` | Example delegate implementation (server) |
| `PetService.client.java.template` | Example client usage |

### Kotlin Templates

| File | Description |
|------|-------------|
| `Application.client.kt.template` | Application graph with OkHttpClientModule (client, Kotlin) |
| `Application.server.kt.template` | Application graph with UndertowHttpServerModule + ValidationModule (server, Kotlin) |
| `PetApiDelegate.server.kt.template` | Example delegate implementation (server, Kotlin) — returns ApiResponses subclasses |
| `PetService.client.kt.template` | Example client usage (client, Kotlin) |

### Shared Assets

| File | Description |
|------|-------------|
| `openapi-spec.yaml.template` | OpenAPI specification template with discriminator example |

---

## 🌐 OpenAPI Management (Publishing Specifications)

**Purpose:** The `openapi-management` module provides access to OpenAPI specifications from the application, as well as Swagger UI and Rapidoc for API documentation visualization.

**Recommendation:** Use **Swagger UI** — the most mature and stable solution with full support for all OpenAPI features. Rapidoc is available as an alternative but may have limitations with complex specifications.

### Dependency

===! ":fontawesome-brands-java: `Java`"

    ```groovy
    dependencies {
        implementation "ru.tinkoff.kora:openapi-management"
    }
    ```

    Module:
    ```java
    @KoraApp
    public interface Application extends OpenApiManagementModule { }
    ```

=== ":simple-kotlin: `Kotlin`"

    ```kotlin
    dependencies {
        implementation("ru.tinkoff.kora:openapi-management")
    }
    ```

    Module:
    ```kotlin
    @KoraApp
    interface Application : OpenApiManagementModule
    ```

**Requires:** [HTTP server](http-server.md) module.

### Configuration

```hocon
openapi {
    management {
        file = ["my-openapi-1.yaml", "my-openapi-2.yaml"]  // (1)!
        enabled = true  // (2)!
        endpoint = "/openapi"  // (3)!
        swaggerui {
            enabled = true  // (4)! Recommended to use Swagger UI
            endpoint = "/swagger-ui"  // (5)!
        }
        rapidoc {
            enabled = false  // (6)! Not recommended, use only as an alternative
            endpoint = "/rapidoc"  // (7)!
        }
    }
}
```

**Parameters:**
1. `file` — relative path to OpenAPI files in the `resources` directory. One or multiple files can be specified
2. `enabled` — enable/disable the OpenAPI access controller (default `true`)
3. `endpoint` — path at which OpenAPI will be accessible
   - If a single file is specified — this is the path to the file
   - If multiple files — this is a path prefix; each file is accessible at `endpoint + "/" + filename`
4. `swaggerui.enabled` — enable Swagger UI (default `true`, **recommended**)
5. `swaggerui.endpoint` — path for Swagger UI (default `/swagger-ui`)
6. `rapidoc.enabled` — enable Rapidoc (default `false`, not recommended)
7. `rapidoc.endpoint` — path for Rapidoc (default `/rapidoc`)

### Usage Example

**build.gradle:**
```groovy
dependencies {
    implementation "ru.tinkoff.kora:openapi-management"
    implementation "ru.tinkoff.kora:http-server-undertow"
}
```

**Application.java:**
```java
@KoraApp
public interface Application extends
    OpenApiManagementModule,
    UndertowHttpServerModule { }
```

**application.conf:**
```hocon
openapi {
    management {
        file = ["openapi/petstore.yaml"]
        enabled = true
        endpoint = "/api/openapi"
        swaggerui {
            enabled = true  # Recommended
            endpoint = "/api/docs"
        }
        rapidoc {
            enabled = false  # Not recommended
        }
    }
}
```

**Result:**
- OpenAPI specification: `GET /api/openapi/petstore.yaml`
- Swagger UI: `GET /api/docs`

---

**Script:** `scripts/validate_openapi.py` — OpenAPI specification validation (TBD)

---

## Common Pitfalls

- **Duplicate endpoints** → don't mix generated delegate + manual controller for same paths.
- **Wrong outputDir** → each OpenAPI spec needs unique `outputDir` to avoid class conflicts.
- **Missing discriminator in oneOf** → define discriminators in OpenAPI spec for polymorphic types.
- **Server delegate without `@Component`** → generated delegates need `@Component` to be discovered.
- **Client without `@Tag`** → tag multiple clients from different specs.
