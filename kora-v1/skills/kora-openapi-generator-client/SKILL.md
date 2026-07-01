---
name: kora-openapi-generator-client
description: "Generates declarative Kora HTTP clients from an OpenAPI 3.x contract using the org.openapi.generator Gradle plugin with generatorName \"kora\". Produces typed *Api interfaces whose methods return sealed *ApiResponses wrappers, plus model records. Use when scaffolding a Gradle GenerateTask for an OpenAPI client, choosing a client mode (java-client, java-async-client, java-reactive-client, kotlin-client, kotlin-suspend-client), wiring the generated *Api into a @Component, setting clientConfigPrefix, attaching @InterceptWith auth interceptors (ApiKeyHttpClientInterceptor, BasicAuthHttpClientInterceptor, BearerAuthHttpClientInterceptor) or generator securityConfigPrefix/primaryAuth, or testing the client with @KoraAppTest and MockServer."
---

# Kora OpenAPI Generator — HTTP Client

Generate a typed, declarative Kora HTTP client from an OpenAPI 3.x contract. The
`org.openapi.generator` Gradle plugin with `generatorName = "kora"` emits a
`@HttpClient`-backed `*Api` interface plus model records at build time. Inject the
`*Api` into a `@Component` and call its methods.

This skill covers **clients only**. For OpenAPI server handlers (`*-server` modes,
delegates, `HttpServerPrincipalExtractor`), use the `kora-openapi-generator-server`
skill.

## Quick Start

### 1. Plugin and buildscript dependency

```groovy
buildscript {
    dependencies {
        classpath "ru.tinkoff.kora:openapi-generator:$koraVersion"
    }
}

plugins {
    id "java"
    id "application"
    id "org.openapi.generator" version "7.14.0" // pin exactly; other versions are not guaranteed compatible
}
```

### 2. Runtime modules

A generated client needs an HTTP client transport plus the JSON module. Pick one transport:

```groovy
dependencies {
    koraBom platform("ru.tinkoff.kora:kora-parent:1.2.17")
    annotationProcessor "ru.tinkoff.kora:annotation-processors"   // MANDATORY — nothing generates without it

    implementation "ru.tinkoff.kora:http-client-jdk"   // JdkHttpClientModule (or http-client-ok / http-client-async)
    implementation "ru.tinkoff.kora:json-module"
    implementation "ru.tinkoff.kora:config-hocon"
    implementation "ru.tinkoff.kora:logging-logback"
}
```

`@KoraApp` plugs the transport module in:

```java
@KoraApp
public interface Application extends
        HoconConfigModule,
        LogbackModule,
        JsonModule,
        JdkHttpClientModule {   // ru.tinkoff.kora.http.client.jdk.JdkHttpClientModule

    static void main(String[] args) {
        KoraApplication.run(ApplicationGraph::graph); // ru.tinkoff.kora.application.graph.KoraApplication
    }
}
```

### 3. Generation task (one per spec, unique `outputDir`)

```groovy
import org.openapitools.generator.gradle.plugin.tasks.GenerateTask

def openApiGenerateHttpClient = tasks.register("openApiGenerateHttpClient", GenerateTask) {
    generatorName = "kora"
    group = "openapi tools"
    inputSpec = "$projectDir/src/main/resources/openapi/pet.yaml"
    outputDir = "$buildDir/generated/pet-client"     // unique per task — required for incremental builds
    def corePackage = "com.example.pet"
    apiPackage = "${corePackage}.api"
    modelPackage = "${corePackage}.model"
    invokerPackage = "${corePackage}.invoker"
    configOptions = [
        mode              : "java-client",
        clientConfigPrefix: "httpClient.pet",        // config root; the Api name is appended (httpClient.pet.PetApi)
    ]
}
sourceSets.main { java.srcDirs += openApiGenerateHttpClient.get().outputDir }
compileJava.dependsOn openApiGenerateHttpClient
```

### 4. Inject and call the generated `*Api`

Generated methods return a **sealed `*ApiResponses` wrapper**, not the bare model.
Pattern match the response.

```java
@Component
public final class PetService {

    private final PetApi petApi;

    public PetService(PetApi petApi) {
        this.petApi = petApi;
    }

    public Pet getPet(long id) {
        var response = petApi.getPetById(id);
        if (response instanceof PetApiResponses.GetPetByIdApiResponse.GetPetById200ApiResponse ok) {
            return ok.content();
        }
        throw new IllegalStateException("Unexpected response: " + response);
    }
}
```

### 5. Configure the client (HOCON)

```hocon
httpClient.pet.PetApi {
  url = ${PET_API_URL}
  requestTimeout = 10s
  telemetry.logging.enabled = true
}
```

---

## What's in this skill

| File | Purpose |
|------|---------|
| [references/openapi-codegen-reference.md](references/openapi-codegen-reference.md) | Full `configOptions`, modes, interceptors, tags, normalizer, discriminators |
| [references/authorization-reference.md](references/authorization-reference.md) | Client-side auth: interceptors and generator `securityConfigPrefix`/`primaryAuth` |
| [assets/build.gradle.client.template](assets/build.gradle.client.template) | Ready-to-edit client `build.gradle` |
| [assets/Application.client.java.template](assets/Application.client.java.template) / [.kt](assets/Application.client.kt.template) | `@KoraApp` module wiring |
| [assets/PetService.client.java.template](assets/PetService.client.java.template) / [.kt](assets/PetService.client.kt.template) | `*Api` injection + response pattern matching |
| [assets/openapi-spec.yaml.template](assets/openapi-spec.yaml.template) | Example OpenAPI 3.x spec (includes a discriminator) |
| [scripts/validate_openapi.py](scripts/validate_openapi.py) | Pre-generation spec linter |

---

## Generation modes

| Mode | Description | Method shape |
|------|-------------|--------------|
| `java-client` | Synchronous (recommended) | `T method(...)` |
| `java-async-client` | `CompletionStage` | `CompletionStage<T> method(...)` |
| `java-reactive-client` | Project Reactor — add `io.projectreactor:reactor-core` yourself | `Mono<T>` / `Flux<T>` |
| `kotlin-client` | Kotlin synchronous | `fun method(...): T` |
| `kotlin-suspend-client` | Kotlin coroutines | `suspend fun method(...): T` |

The return type `T` is always a sealed `*ApiResponses.*ApiResponse`, wrapped in
the async/reactive container for the corresponding mode.

## Transport choice

A generated client depends on an HTTP client transport module — choose one and
plug its module into `@KoraApp`:

| Artifact | Module | Package |
|----------|--------|---------|
| `ru.tinkoff.kora:http-client-jdk` | `JdkHttpClientModule` | `ru.tinkoff.kora.http.client.jdk` |
| `ru.tinkoff.kora:http-client-ok` | `OkHttpClientModule` | `ru.tinkoff.kora.http.client.ok` |
| `ru.tinkoff.kora:http-client-async` | `AsyncHttpClientModule` | `ru.tinkoff.kora.http.client.async` |

The generator is transport-agnostic; the same generated `*Api` works with any of them.

---

## When to use vs NOT

Use this skill when:
- you have an OpenAPI 3.x contract and want a typed outbound client,
- you want request/response models and a `@HttpClient`-backed `*Api` generated at build time,
- you are wiring `clientConfigPrefix`, interceptors, tags, or generator-driven auth.

Do NOT use this skill when:
- you are generating **server** handlers/delegates → `kora-openapi-generator-server`,
- you are hand-writing a `@HttpClient` interface without a spec → `kora-http-client`,
- you only need client-side auth interceptors on a hand-written client → `kora-http-client-auth`.

---

## Core patterns

### Multiple specs in one module

Each spec gets its own `GenerateTask` with a **unique `outputDir`** and its own
`corePackage`. Repeat the `sourceSets`/`dependsOn` lines per task. Sharing an
`outputDir` breaks Gradle incremental builds and caching.

### Response wrappers

For `GET /pet/{id}` returning `200` and `404`, the generator emits a sealed
interface `PetApiResponses.GetPetByIdApiResponse` with nested record variants
`GetPetById200ApiResponse` (carrying `.content()`) and `GetPetById404ApiResponse`.
Use `instanceof` pattern matching (Java) or `is`/`when` (Kotlin) to branch.

```java
var response = petApi.getPetById(id);
return switch (response) {
    case PetApiResponses.GetPetByIdApiResponse.GetPetById200ApiResponse ok -> ok.content();
    case PetApiResponses.GetPetByIdApiResponse.GetPetById404ApiResponse nf -> throw new NotFoundException(id);
    default -> throw new IllegalStateException("Unexpected: " + response);
};
```

### Per-client configuration

`clientConfigPrefix` is the config root; the generated `*Api` class name is
appended. With `clientConfigPrefix = "httpClient.pet"` and a `PetApi`, the config
section is `httpClient.pet.PetApi`. Per-operation overrides nest under
`<operationId>Config`:

```hocon
httpClient.pet.PetApi {
  url = ${PET_API_URL}
  requestTimeout = 10s
  getPetByIdConfig { requestTimeout = 20s }
  telemetry { logging.enabled = true, metrics.enabled = true }
}
```

### Authorization (two routes)

1. **Generator-driven** — when the spec declares `securitySchemes`, set
   `primaryAuth` and `securityConfigPrefix` in `configOptions`. Credentials come
   from config under `<securityConfigPrefix>.<schemeName>`.
2. **Manual interceptor** — provide an auth interceptor (`ApiKeyHttpClientInterceptor`,
   `BasicAuthHttpClientInterceptor`, `BearerAuthHttpClientInterceptor`) as a
   `@Module` component and attach it with `@InterceptWith`.

Full detail in [references/authorization-reference.md](references/authorization-reference.md).

### Testing the client

Stub the remote API with a MockServer container and inject the `*Api` via
`@TestComponent`; point the client at the stub with `KoraAppTestConfigModifier`.

```java
@TestcontainersMockServer(mode = ContainerMode.PER_RUN)
@KoraAppTest(Application.class)
class PetApiTest implements KoraAppTestConfigModifier {

    @ConnectionMockServer
    private MockServerConnection mockserver;

    @TestComponent
    private PetApi petApi;

    @Override
    public KoraConfigModification config() {
        return KoraConfigModification.ofSystemProperty("PET_API_URL", mockserver.params().uri().toString());
    }

    @Test
    void getPetById() {
        mockserver.client()
            .when(request().withMethod("GET").withPath("/v2/pet/1"))
            .respond(response().withBody("{\"id\":1,\"name\":\"Rex\",\"status\":\"available\"}"));

        var response = petApi.getPetById(1L);
        assertTrue(response instanceof PetApiResponses.GetPetByIdApiResponse.GetPetById200ApiResponse);
    }
}
```

Test dependency: `ru.tinkoff.kora:test-junit5` plus
`io.goodforgod:testcontainers-extensions-mockserver`.

---

## Common pitfalls

| Symptom | Cause / fix |
|---------|-------------|
| Generated method "returns the model" assumption fails to compile | Methods return sealed `*ApiResponses.*ApiResponse`; pattern match and call `.content()` |
| "Required dependency PetApi not found" | Missing transport module on `@KoraApp` (`JdkHttpClientModule` / `OkHttpClientModule` / `AsyncHttpClientModule`) or `json-module` absent |
| Config not picked up | Prefix must include the Api class name: `httpClient.pet.PetApi`, not `httpClient.pet` |
| Stale or duplicated generated classes | Two `GenerateTask`s share an `outputDir`; give each a unique directory and clean `build/generated/` |
| Unexpected `oneOf`/`anyOf` output | Plugin ≥ 7.0.0 enables `SIMPLIFY_ONEOF_ANYOF`; set `openapiNormalizer = [DISABLE_ALL: "true"]` |
| Plugin task type unresolved | Add `import org.openapitools.generator.gradle.plugin.tasks.GenerateTask` |
| Reactive mode fails to compile | `java-reactive-client` needs `io.projectreactor:reactor-core` added manually |

---

## Source of truth

- Doc: `.kora-agent/kora-docs/mkdocs/docs/en/documentation/openapi-codegen.md`
- HTTP client doc: `.kora-agent/kora-docs/mkdocs/docs/en/documentation/http-client.md`
- Guide: `.kora-agent/kora-docs/mkdocs/docs/en/guides/openapi-http-client.md`
- Examples: `.kora-agent/kora-examples/examples/java/kora-java-openapi-generator-http-client`,
  `.kora-agent/kora-examples/guides/java/kora-java-guide-openapi-http-client-app`
