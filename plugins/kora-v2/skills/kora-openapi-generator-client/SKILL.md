---
name: kora-openapi-generator-client
description: "Generate a Kora 2.x HTTP client from an OpenAPI 3.x contract with the `kora` generator (io.koraframework:openapi-generator, modes java-client / kotlin-client). Emits a @HttpClient-annotated *Api interface with synchronous methods, sealed *ApiResponses per status code, *ApiClientRequestMappers / *ApiClientResponseMappers, model records or data classes and an ApiSecurity @Module for securitySchemes. Use for contract-first outbound clients, clientConfig / clientConfigPrefix wiring, the lower-camel httpClient.<client>.<api> config key, clientResponseMode SUCCESSFUL with typed HttpClientResponseException errors, 4XX/5XX range responses, enum fromValue parsing, HttpClientTokenProvider auth tags, or a client that starts green but hangs on every request."
license: Apache-2.0
metadata:
  kora-version: "2.x"
---

# Kora OpenAPI Generator — HTTP Client

> **Kora sub-skill — obey the [kora-v2 meta rules](../../SKILL.md) on every task:** **R0** ground the workspace on Kora 2.0 refs before starting (framework source at tag `2.0.0.RC2` + `kora-examples` at `migration/2.0` + Kora 2.0 docs at koraframework.io/v2, which trail the source; 1.x `kora-docs` pages are never an authority) · **R1** read this sub-skill before writing code · **R2** Kora 2.0 APIs only — no Spring/Micronaut/Quarkus, no Kora 1.x APIs, no invented annotations or config keys · **R3** journal any incorrect Kora usage. Add comments/Javadoc only if asked.

**Version:** Kora 2.0 (`io.koraframework`, `2.0.0.RC2`) | **Java:** 25 | **Kotlin:** 2.4.20 + KSP 2.3.12 | **Gradle:** 9.7.1

Generate a typed, declarative outbound HTTP client from an OpenAPI 3.x contract. The
`org.openapi.generator` Gradle plugin with `generatorName = "kora"` emits a `@HttpClient`
interface plus models at build time; inject the `*Api` into a `@Component` and call it.

This skill covers **clients only**. For generated server controllers and delegates use
`kora-openapi-generator-server`; for a hand-written `@HttpClient` use `kora-http-client`.

---

## Read this first: the client config key lower-cases the API name

This is the one change that costs the most time, because nothing fails loudly.

`clientConfigPrefix` is joined to the **generated API class name with its first letter
lower-cased**. `PetApi` becomes `petApi`, so a build with `clientConfigPrefix = "httpClient.petV2"`
produces `@HttpClient("httpClient.petV2.petApi")`:

```java
// io/koraframework/openapi/generator/KoraCodegen.java — clientConfigPath(String)
return params.clientConfigPrefix + "." + StringUtils.uncapitalize(clientName);
```

```hocon
# Kora 1.x — silently ignored in 2.0
httpClient.petV2.PetApi { url = ${PET_API_URL} }

# Kora 2.0
httpClient.petV2.petApi { url = ${PET_API_URL} }
```

**Why it hurts:** HOCON does not reject an unknown section. The stale block is simply never read,
the client comes up with no `url`, and requests do not fail fast — they **hang until
`requestTimeout` expires**. Tests time out instead of reporting a config error.

**Never guess the key.** Read it off the generated annotation, which is the only authority:

```bash
grep -rn '@HttpClient' build/generated/**/api/*Api.java   # or *Api.kt
```

The generator also prints the full mapping at the end of every client generation:

```
Generated Kora OpenAPI HTTP clients and config paths:
  - PetApi -> httpClient.petV2.petApi (configPath)
```

### `clientConfig` vs `clientConfigPrefix`

Client modes require exactly one of them; with neither, generation fails with
*"Missing OpenAPI generator `clientConfig`"*.

| Option | Emits | Use when |
|---|---|---|
| `clientConfigPrefix: "httpClient.petV2"` | `@HttpClient("httpClient.petV2.petApi")` — one section **per API class** | the spec has several tags, or you want one section per client |
| `clientConfig: "httpClient.petV2"` | `@HttpClient("httpClient.petV2")` — the **same** section for every API in the spec, nothing appended | a single-tag spec you want to configure once |

The API class name comes from the OpenAPI **tag**: `pets` → `PetsApi`, `pet` → `PetApi`, no tag at
all → `DefaultApi`. Rename a tag and the config key moves with it.

---

## Only four generator modes exist

`configOptions.mode` accepts exactly `java-client`, `java-server`, `kotlin-client`,
`kotlin-server` (`CodegenMode` in the generator). Anything else aborts generation with
*"Invalid OpenAPI generator `mode`"* plus the list of supported values.

| Removed in 2.0 | Use instead |
|---|---|
| `java-reactive-client`, `java-async-client` | `java-client` |
| `kotlin-suspend-client`, `kotlin-reactive-client` | `kotlin-client` |

Generated client methods are **synchronous** and run on virtual threads. There is no
`CompletionStage`, `Mono`/`Flux` or `suspend` variant, and `http-client-async` no longer exists as
an artifact. Changing the mode string is necessary but not sufficient — every call site that
awaited a client method has to become a direct call.

---

## Migrating from Kora 1.x

| Kora 1.x | Kora 2.x |
|---|---|
| BOM `ru.tinkoff.kora:kora-parent` | **`io.koraframework:kora-bom`** |
| `classpath("ru.tinkoff.kora:openapi-generator:…")` | **`classpath("io.koraframework:openapi-generator:$koraVersion")`** |
| `ru.tinkoff.kora:json-module` | **`io.koraframework:json-common`** |
| `ru.tinkoff.kora:http-client-async` | **removed** — use `http-client-ok`, `http-client-jdk` or `http-client-apache` |
| `httpClient.petV2.PetApi { … }` | **`httpClient.petV2.petApi { … }`** — first letter lower-cased |
| `<operationId>Config { … }` | **`<methodName> { … }`**, e.g. `getPetById { requestTimeout = 20s }` |
| `@HttpClient(configPath = "x")` | **`@HttpClient("x")`** — 2.0 declares `value()`, `telemetryTag()`, `httpClientTag()`; there is no `configPath` |
| reactive / async / suspend client modes | **removed** — see the table above |
| `Enum.valueOf(raw)` / `enumValueOf(raw)` | **`MyEnum.fromValue(raw)`** |
| `@Tag(ApiSecurity.SecurityRequirementTag1.class)` | **`@Tag(ApiSecurity.<SchemeName>.class)`**, e.g. `ApiSecurity.BearerAuth` |
| `configOptions.interceptors` | **`configOptions.extensions`** (`interceptorType` / `interceptorTag`) |
| `configOptions.additionalContractAnnotations` | **`extensions.*.additionalMethodAnnotations`** |
| `configOptions.authAllowMultiple`, `enableJsonNullable`, `forceIncludeNonRequired` | **removed** — no replacement option |
| `ru.tinkoff.kora.common.Component` | **`io.koraframework.common.annotation.Component`** |

Three of these fail only at runtime, never at compile time — the config key above, plus:

- **`fromValue`, not `valueOf`.** The wire value in the contract need not match the generated
  constant: `available` → `AVAILABLE`, `Dingo-Don` → `DINGO_DON`, `5` → `NUMBER_5`. The raw values
  live in a nested `Constants` holder, and `fromValue(raw)` is the only lookup that consults them.
  `Enum.valueOf("available")` throws `IllegalArgumentException` for perfectly valid input, and only
  once real data arrives.
- **Security tags are named after the security scheme.** `components.securitySchemes.bearerAuth`
  becomes the nested marker `ApiSecurity.BearerAuth`. Ordinal `SecurityRequirementTagN` names do
  not exist in 2.0, so a token provider tagged that way is never found and the graph fails to
  build. See [references/authorization-reference.md](references/authorization-reference.md).

---

## The Gradle process itself must run on JDK 25+

`io.koraframework:openapi-generator` goes on the **buildscript classpath**, which is resolved by
the JVM running Gradle — not by the project toolchain. A Java 25 `toolchain { }` block is not
enough. On an older Gradle JVM configuration fails with:

```
Dependency requires at least JVM runtime version 25. This build uses a Java 21 JVM.
```

Fix it where the Gradle JVM is chosen (`JAVA_HOME`, `org.gradle.java.home`, or the IDE's Gradle
JVM setting), not in the toolchain block.

---

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
| **OpenAPI Generator Gradle plugin** (`org.openapi.generator`) | `plugins { }` block | `7.25.0` |
| **Kora `kora` generator** (`io.koraframework:openapi-generator`) | `buildscript { dependencies { classpath … } }` | `$koraVersion` = `2.0.0.RC2` |

The Kora generator is compiled against `org.openapitools:openapi-generator` **7.25.0** (framework
version catalog), so `7.25.0` is the aligned plugin choice. The migrated examples still pin
`7.23.0` / `7.24.0`; bump them when you copy a build file.

```groovy title="build.gradle (Java)"
import org.openapitools.generator.gradle.plugin.tasks.GenerateTask

buildscript {
    repositories { mavenCentral() }
    dependencies {
        classpath "io.koraframework:openapi-generator:$koraVersion"
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
        vendor = JvmVendorSpec.ADOPTIUM
    }
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
    annotationProcessor "io.koraframework:annotation-processors"   // MANDATORY

    implementation "io.koraframework:http-client-ok"               // transport — pick exactly one
    implementation "io.koraframework:json-common"
    implementation "io.koraframework:config-hocon"
    implementation "io.koraframework:logging-logback"
}
```

```kotlin title="build.gradle.kts (Kotlin)"
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
    jvmToolchain {
        languageVersion.set(JavaLanguageVersion.of(25))
        vendor.set(JvmVendorSpec.ADOPTIUM)
    }
}

dependencies {
    implementation(platform("io.koraframework:kora-bom:${property("koraVersion")}"))
    ksp("io.koraframework:symbol-processors:${property("koraVersion")}")   // MANDATORY

    implementation("io.koraframework:http-client-ok")
    implementation("io.koraframework:json-common")
    implementation("io.koraframework:config-hocon")
    implementation("io.koraframework:logging-logback")
}
```

Transports and their `@KoraApp` modules:

| Artifact | Module | Package |
|---|---|---|
| `io.koraframework:http-client-ok` | `OkHttpClientModule` | `io.koraframework.http.client.ok` |
| `io.koraframework:http-client-jdk` | `JdkHttpClientModule` | `io.koraframework.http.client.jdk` |
| `io.koraframework:http-client-apache` | `ApacheHttpClientModule` | `io.koraframework.http.client.apache` |

The generator is transport-agnostic — the same generated `*Api` works with any of them.

### 3. Generation task — one per spec, unique `outputDir`

```groovy title="build.gradle (Java)"
def openApiGeneratePetV2 = tasks.register("openApiGeneratePetV2", GenerateTask) {
    generatorName = "kora"
    group = "openapi tools"
    inputSpec = layout.projectDirectory.file("src/main/resources/openapi/petstoreV2.yaml")
    outputDir = layout.buildDirectory.dir("generated/openapi/petV2")
    def corePackage = "com.example.openapi.petV2"
    apiPackage = "${corePackage}.api"
    modelPackage = "${corePackage}.model"
    invokerPackage = "${corePackage}.invoker"
    configOptions = [
            mode              : "java-client",
            clientConfigPrefix: "httpClient.petV2",   // -> @HttpClient("httpClient.petV2.petApi")
    ]
}
sourceSets.main { java.srcDirs += openApiGeneratePetV2.get().outputDir }
compileJava.dependsOn openApiGeneratePetV2
```

```kotlin title="build.gradle.kts (Kotlin)"
val openApiGeneratePetV2 = tasks.register<GenerateTask>("openApiGeneratePetV2") {
    generatorName.set("kora")
    group = "openapi tools"
    inputSpec.set("$projectDir/src/main/resources/openapi/petstoreV2.yaml")
    outputDir.set(layout.buildDirectory.dir("generated/openapi/petV2").get().asFile.absolutePath)
    val corePackage = "com.example.openapi.petV2"
    apiPackage.set("$corePackage.api")
    modelPackage.set("$corePackage.model")
    invokerPackage.set("$corePackage.invoker")
    configOptions.set(
        mapOf(
            "mode" to "kotlin-client",
            "clientConfigPrefix" to "httpClient.petV2",
        )
    )
}

kotlin.sourceSets.main { kotlin.srcDir(openApiGeneratePetV2.get().outputDir) }
// KSP must see the generated sources, so every ksp* task depends on generation
tasks.matching { it.name.startsWith("ksp") }.configureEach { dependsOn(openApiGeneratePetV2) }
tasks.compileKotlin { dependsOn(openApiGeneratePetV2) }
```

Every spec gets its **own `outputDir`**. Sharing one breaks incremental builds and leaves stale
classes behind.

### 4. Plug the modules into `@KoraApp`

```java title="Application.java"
@KoraApp
public interface Application extends
        HoconConfigModule,      // io.koraframework.config.hocon
        LogbackModule,          // io.koraframework.logging.logback
        JsonModule,             // io.koraframework.json.common
        OkHttpClientModule {    // io.koraframework.http.client.ok

    static void main(String[] args) {
        KoraApplication.run(ApplicationGraph::graph);
    }
}
```

A client-only application does **not** need an HTTP server module. Note that
`io.koraframework.validation.module.ValidationModule` pulls `http-server-common` onto the
classpath through `ViolationExceptionHttpServerResponseMapper`; if you only need the constraint
validators, extend `io.koraframework.validation.common.constraint.ValidatorModule` instead.

### 5. Inject and call the generated `*Api`

Generated methods return a **sealed `*ApiResponses` wrapper**, one variant per declared status
code — never the bare model.

```java title="PetService.java"
@Component
public final class PetService {

    private final PetApi petApi;

    public PetService(PetApi petApi) {
        this.petApi = petApi;
    }

    public Pet getPet(long petId) {
        return switch (petApi.getPetById(petId)) {
            case PetApiResponses.GetPetByIdApiResponse.GetPetById200ApiResponse ok -> ok.content();
            case PetApiResponses.GetPetByIdApiResponse.GetPetById404ApiResponse ignored ->
                    throw new NoSuchElementException("pet " + petId);
        };
    }
}
```

```kotlin title="PetService.kt"
@Component
class PetService(private val petApi: PetApi) {

    fun getPet(petId: Long): Pet = when (val response = petApi.getPetById(petId)) {
        // Kotlin variants are data classes: `content` is a property, not a method
        is PetApiResponses.GetPetByIdApiResponse.GetPetById200ApiResponse -> response.content
        is PetApiResponses.GetPetByIdApiResponse.GetPetById404ApiResponse ->
            throw NoSuchElementException("pet $petId")
    }
}
```

In Java the variants are `record`s, so the payload is `ok.content()`. In Kotlin they are
`data class`es, so it is `response.content`. A variant with no body is an empty `record` / a plain
`class`, with no `content` at all.

### 6. Configure the client (HOCON)

```hocon title="application.conf"
httpClient.petV2.petApi {          # <clientConfigPrefix>.<apiName with first letter lower-cased>
  url = ${PET_API_URL}
  requestTimeout = 10s

  getPetById {                     # per-operation override: the generated METHOD name, no suffix
    requestTimeout = 20s
  }

  telemetry.logging.enabled = true # logging and metrics default to false in 2.0
}
```

Per-operation sections are named after the generated method (`getPetById`, `listPets`), because
the HTTP client processor derives the generated `$PetApi_Config` accessors straight from the
interface methods. The 1.x `<operationId>Config` spelling is not read.

---

## Response mode: `SEALED` (default) or `SUCCESSFUL`

`configOptions.clientResponseMode` decides what a generated method returns when the operation
declares error responses (any non-2xx code, or `default`):

| `clientResponseMode` | Return type | Declared error responses |
|---|---|---|
| `SEALED` (default) | the sealed `<Op>ApiResponse` — you `switch` / `when` over every variant | returned as variants |
| `SUCCESSFUL` | the success variant itself, e.g. `GetPetById200ApiResponse` | **thrown** as typed `HttpClientResponseException` subclasses |

```groovy
configOptions = [
        mode              : "java-client",
        clientConfigPrefix: "httpClient.pet",
        clientResponseMode: "SUCCESSFUL",
]
```

```java
public Pet getPet(long petId) {
    return petApi.getPetById(petId).content();          // 404 arrives as an exception
}

public Optional<Pet> findPet(long petId) {
    try {
        return Optional.of(petApi.getPetById(petId).content());
    } catch (PetApi.PetApiModelErrorHttpClientResponseException e) {
        if (e.getCode() == 404) {
            return Optional.empty();
        }
        throw e;
    }
}
```

```kotlin
fun findPet(petId: Long): Pet? = try {
    petApi.getPetById(petId).content
} catch (e: PetApi.PetApiModelErrorHttpClientResponseException) {
    if (e.code == 404) null else throw e
}
```

How `SUCCESSFUL` shapes the output (the mapper exists for operations that declare an error response
or whose return type is narrowed — e.g. `200` + `206` sharing one body; an operation with neither keeps
its per-code `@ResponseCodeMapper`s):

- **Return type.** One 2xx response → that variant (`<Op>200ApiResponse`). Several 2xx responses
  with the same body type → the shared sealed `<Op><Type>ApiResponse` with `content()` and
  `statusCode()`. Several 2xx responses with different bodies (or one without a body) → the full
  sealed `<Op>ApiResponse` type, but error responses are still thrown rather than returned.
- **Error types.** One exception class per distinct error **body type**, shared by every operation
  of the API and nested in the `*Api` interface: `<Api><Type>HttpClientResponseException` with
  `getContent()` (Kotlin: `content`). An error response without a body throws
  `<Api>NoContentHttpClientResponseException`. A schema named `Error` is generated as `ModelError`,
  so its exception is `PetApiModelErrorHttpClientResponseException`. Status code, headers and the
  raw body come from the base class: `getCode()`, `getHeaders()`, `getBytes()`.
- **Mapper.** The method carries `@Mapping(<Api>ClientResponseMappers.<Op>SuccessfulResponseMapper.class)`
  instead of one `@ResponseCodeMapper` per code. It is a `@Component` (and `@DefaultComponent`), so
  it resolves from the graph like the per-code mappers.
- **Fallbacks.** An error body that fails to parse becomes a plain `HttpClientResponseException`
  carrying the raw body, with the parse failure attached as a suppressed exception. A status the
  contract does not declare, on an operation without `default`, also throws a plain
  `HttpClientResponseException`. Catch the typed subclass first, then the base class.
- **Status-code ranges.** A `2XX` range is a success (returned, e.g. `<Op>2XXApiResponse`); `4XX` /
  `5XX` are errors thrown as the typed exception. An exact code wins over the range containing it.

Full service examples: [assets/PetService.successful.client.java.template](assets/PetService.successful.client.java.template)
· [assets/PetService.successful.client.kt.template](assets/PetService.successful.client.kt.template).

---

## What gets generated

For `apiPackage = com.example.openapi.petV2.api`, tag `pet`:

| File | Contents |
|---|---|
| `PetApi` | `@HttpClient("…")` interface, one synchronous method per operation, `@HttpRoute` / `@Path` / `@Query` / `@Header` / `@Json`, `@ResponseCodeMapper` per exact status code; in `SUCCESSFUL` mode a `@Mapping(…SuccessfulResponseMapper.class)` instead, plus the nested `PetApi<Type>HttpClientResponseException` classes |
| `PetApiResponses` | nested `sealed interface <Op>ApiResponse` with a record/data class per status code; the OpenAPI `default` response becomes `<Op>DefaultApiResponse(int statusCode, T content)` and a range becomes `<Op>4XXApiResponse(int statusCode, T content)`; responses sharing a body type also implement a sealed `<Op><Type>ApiResponse` with `content()` and `statusCode()` |
| `PetApiClientResponseMappers` | one `HttpClientResponseMapper` per response variant; `<Op>DefaultCodeApiResponseMapper` when the operation declares `4XX`/`5XX` ranges; `<Op>SuccessfulResponseMapper` in `SUCCESSFUL` mode |
| `PetApiClientRequestMappers` | request body / form mappers where needed |
| `PetApi<Op>OptArgs` | an optional-argument holder plus overloads, when an operation has optional parameters |
| `ApiSecurity` | a `@Module` with a marker class per security scheme, a `SecurityConfig` record and `HttpClientTokenProvider` components — only when the spec declares `securitySchemes` |
| model package | records (Java, `@JsonWriter` + `@JsonReader`) / data classes (Kotlin, `@Json`); polymorphic schemas become a `sealed interface` with `@JsonDiscriminatorField` |

`$PetApi_ClientImpl`, `$PetApi_Config` and `$PetApi_Module` are produced afterwards by the Kora
annotation processor / KSP from the generated interface — they are not OpenAPI generator output.

---

## Core rules

1. **Never hand-edit generated code.** After renaming `apiPackage` / `modelPackage` or moving
   `outputDir`, run `./gradlew clean build --no-build-cache` once: the generator does not delete
   its previous output and the build-cache key ignores the package change, so the old and new
   packages coexist in one source set and you get phantom errors from classes nobody imports.
2. **Parse enums with `fromValue`.** Never `Enum.valueOf` / `enumValueOf` on a wire value.
3. **Kotlin: construct models with named arguments.** The constructor parameter order mirrors the
   spec's property declaration order, and optional properties carry `= null` /
   `= JsonNullable.nullValue()` defaults. Reorder two same-typed properties in the contract and a
   positional call still compiles while silently swapping the values.
4. **Do not mark a generated client method `suspend`.** `kotlin-client` emits plain functions and
   the interface is generated, so there is nothing to annotate. If the caller must stay
   coroutine-based, put the bridge in your own service — and decide deliberately whether it is
   needed at all: the call already runs on a virtual thread, so `withContext(Dispatchers.IO)` buys
   nothing.
5. **One `GenerateTask` per spec, one `outputDir` per task.**
6. **Read the config key off the generated `@HttpClient`**, never from memory.

---

## Common pitfalls

| Symptom | Cause / fix |
|---|---|
| Client starts fine, every request hangs until `requestTimeout` | Config section not read — the key must be `httpClient.pet.petApi`, not `httpClient.pet.PetApi`. Verify against the generated `@HttpClient` |
| Generation fails: *"Missing OpenAPI generator `clientConfig`"* | A client mode needs `clientConfig` **or** `clientConfigPrefix` in `configOptions` |
| Generation fails: *"Invalid OpenAPI generator `mode`"* | Only `java-client`, `java-server`, `kotlin-client`, `kotlin-server` exist |
| `IllegalArgumentException: No enum constant …` at runtime, on valid data | `Enum.valueOf(raw)` instead of `MyEnum.fromValue(raw)` |
| Per-operation timeout ignored | Section must be the generated method name (`getPetById`), not `getPetByIdConfig` |
| `No component found for dependency: HttpClientTokenProvider` | The spec declares a `bearer`, `oauth2` or `openIdConnect` scheme; the generator emits the tag but no provider. Supply `@Tag(ApiSecurity.BearerAuth.class) HttpClientTokenProvider` yourself |
| Request carries the wrong credential | The generated group interceptor takes the **first** provider returning a non-null token; a scheme you do not use must return `null` |
| `Required dependency PetApi not found` | No transport module on `@KoraApp`, or the Kora annotation processor / KSP is missing |
| Phantom `ru.tinkoff.kora` or old-package errors from `build/generated` | Stale generator output — `clean` + `--no-build-cache`, never edit generated files |
| An HTTP **server** artifact appears in a client-only app | `ValidationModule` drags in `http-server-common`; use `ValidatorModule` from `validation-common` |
| Unexpected `oneOf`/`anyOf` output | Plugin ≥ 7.0.0 enables `SIMPLIFY_ONEOF_ANYOF`; set `openapiNormalizer = [DISABLE_ALL: "true"]` |
| `SUCCESSFUL` client: a 4xx/5xx response surfaces as plain `HttpClientResponseException`, not the typed one | The error body did not parse (the cause is attached as a suppressed exception), or the status is not declared and the operation has no `default` |
| Server receives `Authorization: Bearer Bearer …` | The generated interceptor already prefixes `Bearer ` (bearer, oauth2, openIdConnect) and `Basic ` (basic). A `HttpClientTokenProvider` returns the bare token |
| `date-time` fields stay `OffsetDateTime` | Map it in the generate task: `typeMappings = ["DateTime": "java.time.Instant"]` (also `date-time` as key). Only `Instant`, `ZonedDateTime`, `LocalDateTime` are recognised; anything else falls back to `OffsetDateTime` |
| `Dependency requires at least JVM runtime version 25` | The **Gradle JVM** is too old; a toolchain block does not fix a buildscript dependency |

---

## References

| File | Purpose |
|---|---|
| [references/openapi-codegen-reference.md](references/openapi-codegen-reference.md) | Every `configOptions` key, config-path derivation, response shapes, `clientResponseMode`, `4XX`/`5XX` ranges, type mapping (`typeMappings`), `extensions`, `tags`, normalizer, discriminators |
| [references/authorization-reference.md](references/authorization-reference.md) | `securitySchemes` → `ApiSecurity`, `HttpClientTokenProvider` tags, the `Bearer `/`Basic ` prefix the interceptor adds, credential config paths, `authAsMethodArgument` |

## Assets

| File | Purpose |
|---|---|
| [assets/build.gradle.client.template](assets/build.gradle.client.template) | Ready-to-edit Java client `build.gradle` |
| [assets/Application.client.java.template](assets/Application.client.java.template) · [assets/Application.client.kt.template](assets/Application.client.kt.template) | `@KoraApp` module wiring for a client-only app |
| [assets/PetService.client.java.template](assets/PetService.client.java.template) · [assets/PetService.client.kt.template](assets/PetService.client.kt.template) | `*Api` injection and sealed-response handling |
| [assets/PetService.successful.client.java.template](assets/PetService.successful.client.java.template) · [assets/PetService.successful.client.kt.template](assets/PetService.successful.client.kt.template) | `clientResponseMode = SUCCESSFUL`: success record returned, typed error exceptions caught |
| [assets/openapi-spec.yaml.template](assets/openapi-spec.yaml.template) | Example OpenAPI 3.x contract (enums, discriminator, apiKey scheme) |
| [scripts/validate_openapi.py](scripts/validate_openapi.py) | Pre-generation linter; also prints the derived client config keys |
