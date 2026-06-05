# OpenAPI Kotlin Reference

**Source:** [.kora-agent/kora-docs/mkdocs/docs/en/documentation/openapi-codegen.md](.kora-agent/kora-docs/mkdocs/docs/en/documentation/openapi-codegen.md)  
**Examples:** `.kora-agent/kora-examples/kora-java-openapi-generator-http-server/`

## 1. Overview

Kora OpenAPI Generator supports Kotlin with specific patterns for client and server generation.

## 2. Client Modes

### Synchronous Client

```groovy
configOptions = [
    mode: "kotlin-client"
]
```

Generated interface:
```kotlin
interface PetApi {
    fun getPetById(petId: Long): Pet
}
```

### Suspend Client

```groovy
configOptions = [
    mode: "kotlin-suspend-client"
]
```

Generated interface:
```kotlin
interface PetApi {
    suspend fun getPetById(petId: Long): Pet
}
```

## 3. Server Modes

### Synchronous Server

```groovy
configOptions = [
    mode: "kotlin-server"
]
```

Generated delegate:
```kotlin
interface PetApiDelegate {
    fun getPetById(petId: Long): PetApiResponses.GetPetByIdApiResponse
}
```

### Suspend Server

```groovy
configOptions = [
    mode: "kotlin-suspend-server"
]
```

Generated delegate:
```kotlin
interface PetApiDelegate {
    suspend fun getPetById(petId: Long): PetApiResponses.GetPetByIdApiResponse
}
```

**Note:** Kotlin delegates return `ApiResponses` wrapper classes, not `ResponseEntity<T>`.

## 4. Gradle Configuration (Kotlin DSL)

### Buildscript Dependencies

```kotlin
buildscript {
    dependencies {
        classpath("ru.tinkoff.kora:openapi-generator:$koraVersion")
    }
}

plugins {
    kotlin("jvm") version "1.9.25"
    id("com.google.devtools.ksp") version "1.9.25-1.0.20"
    id("org.openapi.generator") version "7.14.0"
}
```

### Client Generation Task

```kotlin
val openApiGenerateHttpClient = tasks.register<GenerateTask>("openApiGenerateHttpClient") {
    generatorName = "kora"
    group = "openapi tools"
    inputSpec = "$projectDir/src/main/resources/openapi/my-api.yaml"
    outputDir = "$buildDir/generated/openapi"
    val corePackage = "com.example.myapi"
    apiPackage = "${corePackage}.api"
    modelPackage = "${corePackage}.model"
    invokerPackage = "${corePackage}.invoker"
    configOptions = mapOf(
        "mode" to "kotlin-client",
        "clientConfigPrefix" to "httpClient.myApi"
    )
}
kotlin.sourceSets.main { kotlin.srcDir(openApiGenerateHttpClient.get().outputDir) }
tasks.withType<KspTask> { dependsOn(openApiGenerateHttpClient) }
```

### Server Generation Task

```kotlin
val openApiGenerateHttpServer = tasks.register<GenerateTask>("openApiGenerateHttpServer") {
    generatorName = "kora"
    group = "openapi tools"
    inputSpec = "$projectDir/src/main/resources/openapi/my-api.yaml"
    outputDir = "$buildDir/generated/openapi"
    val corePackage = "com.example.myapi"
    apiPackage = "${corePackage}.api"
    modelPackage = "${corePackage}.model"
    invokerPackage = "${corePackage}.invoker"
    configOptions = mapOf(
        "mode" to "kotlin-server",
        "enableServerValidation" to "true"
    )
}
kotlin.sourceSets.main { kotlin.srcDir(openApiGenerateHttpServer.get().outputDir) }
tasks.withType<KspTask> { dependsOn(openApiGenerateHttpServer) }
```

## 5. Kotlin DTOs

Generated data classes:
```kotlin
data class Pet(
    val id: Long,
    val name: String,
    val status: String? = null,
    val tags: List<Tag> = emptyList()
)
```

### Nullable Handling

```kotlin
data class Pet(
    val id: Long,                    // required, not nullable
    val name: String?,               // optional, nullable
    val status: String = "available" // optional with default
)
```

## 6. Kotlin Delegate Implementation

```kotlin
@Component
class PetApiDelegate(
    private val petService: PetService
) : PetApiDelegate {
    
    override fun getPetById(petId: Long): PetApiResponses.GetPetByIdApiResponse {
        val pet = petService.findById(petId)
        return PetApiResponses.GetPetByIdApiResponse.GetPetById200ApiResponse(pet)
    }
    
    override fun addPet(pet: Pet): PetApiResponses.AddPetApiResponse {
        val created = petService.create(pet)
        return PetApiResponses.AddPetApiResponse.AddPet200ApiResponse(created)
    }
}
```

### Suspend Implementation

```kotlin
@Component
class PetApiDelegate(
    private val petService: PetService
) : PetApiDelegate {
    
    override suspend fun getPetById(petId: Long): PetApiResponses.GetPetByIdApiResponse {
        val pet = petService.findById(petId)
        return PetApiResponses.GetPetByIdApiResponse.GetPetById200ApiResponse(pet)
    }
    
    override suspend fun addPet(pet: Pet): PetApiResponses.AddPetApiResponse {
        val created = petService.create(pet)
        return PetApiResponses.AddPetApiResponse.AddPet200ApiResponse(created)
    }
}
```

## 7. Kotlin Interceptors

```kotlin
@Component
@Tag(LoggingTag::class)
class LoggingInterceptor : HttpClientInterceptor {
    private val log = LoggerFactory.getLogger(LoggingInterceptor::class.java)
    
    override fun <T> handle(
        request: HttpClientRequest,
        body: HttpClientRequest.BodyProvider,
        responseHandler: HttpClientResponseHandler<T>,
        chain: HttpClientInterceptor.Chain
    ): T {
        log.info("Request: {} {}", request.method(), request.uri())
        return chain.proceed(request, body, responseHandler)
    }
}
```

## 8. Kotlin Configuration

```kotlin
@ConfigSource("app.api")
interface ApiConfig {
    val baseUrl: String
    val timeout: Duration
    val retries: Int
}
```

Usage in delegate:
```kotlin
@Component
class PetApiDelegate(
    private val petService: PetService,
    private val config: ApiConfig
) : PetApiDelegate {
    // config.baseUrl, config.timeout available
}
```

## 9. Kotlin Coroutines Support

### Reactive to Coroutines Bridge

```kotlin
@Component
class PetApiDelegate(
    private val petService: PetService,
    private val scope: CoroutineScope
) : PetApiDelegate {
    
    override suspend fun getPetById(petId: Long): PetApiResponses.GetPetByIdApiResponse =
        scope.async {
            val pet = petService.findById(petId)
            PetApiResponses.GetPetByIdApiResponse.GetPetById200ApiResponse(pet)
        }.await()
}
```

### Flow Support

```kotlin
override fun listPets(): Flow<Pet> =
    petService.findAll()  // Returns Flow<Pet>
```

## 10. Kotlin-Specific Config Options

```kotlin
configOptions = mapOf(
    "mode" to "kotlin-suspend-client",
    "enableJsonNullable" to "true",
    "forceIncludeOptional" to "false",
    "forceIncludeNonRequired" to "false",
    "filterWithModels" to "true"
)
```

## 11. Kotlin Testing

```kotlin
@KoraTest
class PetApiDelegateTest {
    
    @Inject
    lateinit var petApi: PetApi
    
    @Test
    fun `getPetById returns pet`() = runTest {
        val pet = petApi.getPetById(1L)
        
        assertNotNull(pet)
        assertEquals(1L, pet.id)
    }
}
```

## 12. Troubleshooting

| Problem | Solution |
|---------|----------|
| KSP not running | Ensure `dependsOn(openApiGenerate*)` |
| Suspend functions not working | Use `kotlin-suspend-client` or `kotlin-suspend-server` |
| Nullable types incorrect | Check `enableJsonNullable` setting |
| Coroutines not available | Add `kotlinx-coroutines-core` dependency |

---

## Related References

- [openapi-codegen-reference.md](openapi-codegen-reference.md) — OpenAPI Generator configuration
- [interceptors-reference.md](interceptors-reference.md) — Interceptors for clients and servers
- [validation-reference.md](validation-reference.md) — Server-side validation
