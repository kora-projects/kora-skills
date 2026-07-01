# OpenAPI Client Codegen Reference

**Source:** `.kora-agent/kora-docs/mkdocs/docs/en/documentation/openapi-codegen.md`
**Example:** `.kora-agent/kora-examples/examples/java/kora-java-openapi-generator-http-client`,
`.kora-agent/kora-examples/guides/java/kora-java-guide-openapi-http-client-app`

## Contents

- [Overview](#overview)
- [Dependency](#dependency)
- [Client configuration](#client-config)
- [Client modes](#client-modes)
- [Config options](#config-options)
- [Interceptors](#interceptors)
- [Tags](#tags)
- [OpenAPI normalizer](#normalizer)
- [Discriminators (oneOf + allOf)](#discriminators)

---

## Overview { #overview }

The Kora OpenAPI codegen module creates declarative HTTP clients (see
`.kora-agent/kora-docs/mkdocs/docs/en/documentation/http-client.md`) from OpenAPI
contracts using the `org.openapi.generator` Gradle plugin with
`generatorName = "kora"`. This reference covers the **client** side only; for
server handlers use the `kora-openapi-generator-server` skill.

The generated artifacts are:

- `*Api` — a `@HttpClient`-backed interface with one method per operation.
- `*ApiResponses` — sealed response wrappers per operation (e.g.
  `PetApiResponses.GetPetByIdApiResponse` with nested `GetPetById200ApiResponse`,
  `GetPetById404ApiResponse`).
- model records / enums under `modelPackage`.

## Dependency { #dependency }

**Buildscript dependency** (provides the `kora` generator to the plugin):

```groovy
buildscript {
    dependencies {
        classpath("ru.tinkoff.kora:openapi-generator:$koraVersion")
    }
}
```

**Plugin dependency** — pin the exact version; other versions are not guaranteed
compatible at the code level:

```groovy
plugins {
    id "org.openapi.generator" version "7.14.0"
}
```

**Requires** an HTTP client transport module plus `json-module`. Each generator
task must use a **unique `outputDir`** (e.g. `$buildDir/generated/pet-client`,
`$buildDir/generated/order-client`) for Gradle incremental builds and caching.

## Client configuration { #client-config }

Java (Groovy DSL):

```groovy
import org.openapitools.generator.gradle.plugin.tasks.GenerateTask

def openApiGenerateHttpClient = tasks.register("openApiGenerateHttpClient", GenerateTask) {
    generatorName = "kora"
    group = "openapi tools"
    inputSpec = "$projectDir/src/main/resources/openapi/openapi.yaml" // (1) source contract
    outputDir = "$buildDir/generated/openapi"                          // (2) unique output dir
    def corePackage = "ru.tinkoff.kora.example.openapi"
    apiPackage = "${corePackage}.api"                                  // (3) generated *Api package
    modelPackage = "${corePackage}.model"                             // (4) model/DTO package
    invokerPackage = "${corePackage}.invoker"                         // (5) invoker package
    openapiNormalizer = [
        DISABLE_ALL: "true"
    ]
    configOptions = [
        mode              : "java-client",                            // (6) generation mode
        clientConfigPrefix: "httpClient.myclient",                    // (7) config root (Api name appended)
    ]
}
sourceSets.main { java.srcDirs += openApiGenerateHttpClient.get().outputDir } // (8) register generated sources
compileJava.dependsOn openApiGenerateHttpClient                              // (9) generate before compile
```

Kotlin (Kotlin DSL):

```kotlin
val openApiGenerateHttpClient = tasks.register<GenerateTask>("openApiGenerateHttpClient") {
    generatorName = "kora"
    group = "openapi tools"
    inputSpec = "$projectDir/src/main/resources/openapi/openapi.yaml"
    outputDir = "$buildDir/generated/openapi"
    val corePackage = "ru.tinkoff.kora.example.openapi"
    apiPackage = "${corePackage}.api"
    modelPackage = "${corePackage}.model"
    invokerPackage = "${corePackage}.invoker"
    openapiNormalizer = mapOf("DISABLE_ALL" to "true")
    configOptions = mapOf(
        "mode" to "kotlin-client",
        "clientConfigPrefix" to "httpClient.myclient",
    )
}
kotlin.sourceSets.main { kotlin.srcDir(openApiGenerateHttpClient.get().outputDir) }
tasks.withType<KspTask> { dependsOn(openApiGenerateHttpClient) } // Kotlin uses KSP; depend on generation
```

Once generated, the `*Api` interface is available in the Graph as a dependency —
inject it into any `@Component`.

## Client modes { #client-modes }

| Mode | Description | Method shape |
|------|-------------|--------------|
| `java-client` | Synchronous client (recommended) | `T` |
| `java-async-client` | `CompletionStage` client | `CompletionStage<T>` |
| `java-reactive-client` | Reactive client — add `io.projectreactor:reactor-core` yourself | `Mono<T>` / `Flux<T>` |
| `kotlin-client` | Kotlin synchronous client | `T` |
| `kotlin-suspend-client` | Kotlin coroutine client | `suspend fun` |

`T` is always a sealed `*ApiResponses.*ApiResponse`. The generator is
transport-agnostic — plug `JdkHttpClientModule` (`http-client-jdk`),
`OkHttpClientModule` (`http-client-ok`), or `AsyncHttpClientModule`
(`http-client-async`) into `@KoraApp`.

## Config options { #config-options }

| Option | Type | Description |
|--------|------|-------------|
| `mode` | String | **Required.** One of the client modes above |
| `clientConfigPrefix` | String | Config root for generated clients; the `*Api` class name is appended |
| `interceptors` | JSON | Per-tag interceptor wiring (see [Interceptors](#interceptors)) |
| `tags` | JSON | Per-tag `httpClientTag` / `telemetryTag` (see [Tags](#tags)) |
| `primaryAuth` | String | Primary `securitySchemes` entry when several are defined |
| `securityConfigPrefix` | String | Config prefix for Basic/ApiKey credentials |
| `authAsMethodArgument` | Boolean | Pass auth as a method argument instead of via interceptor |
| `authAllowMultiple` | Boolean | Generate interceptors for multi-authentication |
| `additionalContractAnnotations` | String | Extra annotations on generated client methods |
| `enableJsonNullable` | Boolean | Use `JsonNullable` for `nullable=true, required=false` fields |
| `forceIncludeOptional` | Boolean | Force `@JsonInclude(Always)` for `nullable=true, required=false` |
| `forceIncludeNonRequired` | Boolean | Force `@JsonInclude(Always)` for `required=false` fields |
| `filterWithModels` | Boolean | Filter models when `FILTER` is set in `openapiNormalizer` |

## Interceptors { #interceptors }

Attach interceptors to generated clients via `configOptions.interceptors`, keyed
by the OpenAPI tag (`*` applies to all tags). Each entry has `type` (interceptor
class) and/or `tag` (interceptor tag, possibly an array):

```groovy
configOptions = [
    mode: "java-client",
    interceptors: """
            {
              "*":    [ { "tag":  "ru.tinkoff.example.MyTag" } ],
              "pet":  [ { "type": "ru.tinkoff.example.MyInterceptor" } ],
              "shop": [ { "type": "ru.tinkoff.example.MyInterceptor", "tag": "ru.tinkoff.example.MyTag" } ]
            }
            """
]
```

## Tags { #tags }

Set `httpClientTag` and `telemetryTag` per OpenAPI tag via `configOptions.tags`.
`*` applies to all tags except those explicitly listed:

```groovy
configOptions = [
    mode: "java-client",
    tags: """
          {
            "*":          { "httpClientTag": "some.tag.Common",     "telemetryTag": "some.tag.Common" },
            "instrument": { "httpClientTag": "some.tag.Instrument", "telemetryTag": "some.tag.Instrument" }
          }
          """
]
```

## OpenAPI normalizer { #normalizer }

`openapiNormalizer` customizes spec processing before generation:

```groovy
openapiNormalizer = [ DISABLE_ALL: "true" ] // disable all normalizers
```

**Important:** plugin ≥ `7.0.0` enables `SIMPLIFY_ONEOF_ANYOF` by default, which
can change generator output for polymorphic schemas. Disabling all normalizers
keeps the output predictable.

## Discriminators (oneOf + allOf) { #discriminators }

Discriminators model polymorphic request/response bodies — one of several types
sharing a common base. The pattern is `oneOf` (variants) + `allOf` (common base)
+ `discriminator` (the selecting field):

```yaml
Task:
  oneOf:
    - $ref: '#/components/schemas/TaskUnconfirmed'
    - $ref: '#/components/schemas/TaskConfirmed'
  allOf:
    - $ref: '#/components/schemas/TaskCommon'
  discriminator:
    propertyName: taskType
    mapping:
      UNCONFIRMED: '#/components/schemas/TaskUnconfirmed'
      CONFIRMED: '#/components/schemas/TaskConfirmed'
```

The generator emits a base type with the common fields, a subtype per variant,
and a discriminator field. On the **client** side, branch on the discriminator
before sending or after receiving:

```java
Task request = new TaskUnconfirmed(...); // a concrete variant subtype
var response = taskApi.createTask(request);
if (response instanceof TaskApiResponses.CreateTaskApiResponse.CreateTask201ApiResponse ok) {
    Task created = ok.content();
    switch (created.getTaskType()) {
        case UNCONFIRMED -> handleUnconfirmed(created);
        case CONFIRMED   -> handleConfirmed(created);
    }
}
```

### Best practices

1. Provide an `example` on the polymorphic schema — improves generation and testing.
2. Keep the common base minimal — only truly shared fields.
3. Use an enum for the discriminator value — type safety.
4. With plugin ≥ 7.0.0, set `openapiNormalizer = [DISABLE_ALL: "true"]` to avoid
   `SIMPLIFY_ONEOF_ANYOF` altering the result.

### Troubleshooting

| Problem | Solution |
|---------|----------|
| Generator ignores discriminator | Ensure `propertyName` exists in all variants |
| Wrong type generated | Check `mapping` keys match the discriminator enum values |
| Common fields not inherited | Keep `oneOf` before `allOf` in the schema |
| Unexpected output for `oneOf`/`anyOf` | Disable `SIMPLIFY_ONEOF_ANYOF` via the normalizer |
