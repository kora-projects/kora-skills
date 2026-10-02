# OpenAPI Client Codegen Reference — Kora 2.x

Everything here is verified against the `io.koraframework:openapi-generator` source and tests
for `2.0.0.RC2` and against the migrated Java/Kotlin OpenAPI HTTP-client examples and guides.

## Contents

- [Overview](#overview)
- [Build wiring and versions](#dependency)
- [Generation task](#task)
- [Client modes](#client-modes)
- [Config path derivation](#config-path)
- [Runtime configuration keys](#runtime-config)
- [`configOptions` reference](#config-options)
- [Generated artifacts](#generated)
- [`clientResponseMode` — sealed or successful](#response-mode)
- [Status-code ranges (`4XX`, `5XX`)](#ranges)
- [Enums](#enums)
- [Models and constructor order](#models)
- [Type mapping notes](#type-mapping)
- [`extensions` — annotations and interceptors](#extensions)
- [`tags` — per-tag client and telemetry tags](#tags)
- [OpenAPI normalizer](#normalizer)
- [Discriminators (oneOf + allOf)](#discriminators)
- [Testing a generated client](#testing)

---

## Overview { #overview }

The Kora OpenAPI codegen module produces declarative HTTP clients from OpenAPI 3.x contracts using
the `org.openapi.generator` Gradle plugin with `generatorName = "kora"`. This reference covers the
**client** side only; for generated servers use the `kora-openapi-generator-server` skill.

Generated client methods are **synchronous**. Kora 2.0 contracts run on virtual threads; there is
no reactive, `CompletionStage` or `suspend` client.

## Build wiring and versions { #dependency }

Two versions that are easy to conflate:

| What | Where | Value |
|---|---|---|
| `org.openapi.generator` Gradle plugin | `plugins { }` | `7.25.0` |
| `io.koraframework:openapi-generator` (the `kora` generator) | `buildscript { dependencies { classpath … } }` | `$koraVersion` = `2.0.0.RC2` |

The Kora generator is compiled against `org.openapitools:openapi-generator` **7.25.0** (the
framework's version catalog), so `7.25.0` is the aligned plugin choice. The migrated examples still
pin `7.23.0` / `7.24.0`.

```groovy
buildscript {
    repositories { mavenCentral() }
    dependencies {
        classpath "io.koraframework:openapi-generator:$koraVersion"
    }
}

plugins {
    id "org.openapi.generator" version "7.25.0"
}
```

Because the generator lands on the **buildscript** classpath, the JVM running Gradle itself must be
JDK 25 or newer. A project `toolchain { }` block does not affect it; on an older Gradle JVM
configuration fails with `Dependency requires at least JVM runtime version 25.`

Runtime dependencies for a generated client: one transport (`http-client-ok`, `http-client-jdk` or
`http-client-apache`), `json-common`, a config module, and the Kora annotation processor
(`io.koraframework:annotation-processors`) or KSP (`io.koraframework:symbol-processors`).

## Generation task { #task }

```groovy title="Java"
import org.openapitools.generator.gradle.plugin.tasks.GenerateTask

def openApiGeneratePet = tasks.register("openApiGeneratePet", GenerateTask) {
    generatorName = "kora"                                                    // (1)
    group = "openapi tools"
    inputSpec = layout.projectDirectory.file("src/main/resources/openapi/pet.yaml")
    outputDir = layout.buildDirectory.dir("generated/openapi/pet")            // (2) unique per task
    def corePackage = "com.example.openapi.pet"
    apiPackage = "${corePackage}.api"
    modelPackage = "${corePackage}.model"
    invokerPackage = "${corePackage}.invoker"
    openapiNormalizer = [DISABLE_ALL: "true"]                                 // (3) optional
    configOptions = [
            mode              : "java-client",
            clientConfigPrefix: "httpClient.pet",
    ]
}
sourceSets.main { java.srcDirs += openApiGeneratePet.get().outputDir }
compileJava.dependsOn openApiGeneratePet
```

```kotlin title="Kotlin"
val openApiGeneratePet = tasks.register<GenerateTask>("openApiGeneratePet") {
    generatorName.set("kora")
    group = "openapi tools"
    inputSpec.set("$projectDir/src/main/resources/openapi/pet.yaml")
    outputDir.set(layout.buildDirectory.dir("generated/openapi/pet").get().asFile.absolutePath)
    val corePackage = "com.example.openapi.pet"
    apiPackage.set("$corePackage.api")
    modelPackage.set("$corePackage.model")
    invokerPackage.set("$corePackage.invoker")
    configOptions.set(
        mapOf(
            "mode" to "kotlin-client",
            "clientConfigPrefix" to "httpClient.pet",
        )
    )
}

kotlin.sourceSets.main { kotlin.srcDir(openApiGeneratePet.get().outputDir) }
// KSP consumes the generated interfaces, so every ksp* task must wait for generation
tasks.matching { it.name.startsWith("ksp") }.configureEach { dependsOn(openApiGeneratePet) }
tasks.compileKotlin { dependsOn(openApiGeneratePet) }
```

Each spec needs its own task **and its own `outputDir`**. Sharing an output directory breaks Gradle
incremental builds and leaves stale classes in the source set.

After changing `apiPackage`, `modelPackage` or `outputDir`, run
`./gradlew clean build --no-build-cache` once. The generator does not delete its previous output
and the build-cache key does not account for the package change, so both package trees end up in
the same source set and the compiler reports errors in classes nothing references. Never fix that
by editing generated code.

## Client modes { #client-modes }

`CodegenMode` accepts exactly four values, and `mode` is validated eagerly:

| Mode | Output |
|---|---|
| `java-client` | Java interface, synchronous methods |
| `kotlin-client` | Kotlin interface, synchronous functions |
| `java-server` | see `kora-openapi-generator-server` |
| `kotlin-server` | see `kora-openapi-generator-server` |

Anything else throws:

```
Invalid OpenAPI generator `mode`: `java-reactive-client`.

Supported modes: [java-client, java-server, kotlin-client, kotlin-server]
```

`java-async-client`, `java-reactive-client`, `kotlin-suspend-client` and `kotlin-reactive-client`
no longer exist. Their call sites become straight synchronous calls.

## Config path derivation { #config-path }

A client mode must be given `clientConfig` **or** `clientConfigPrefix`; with neither, generation
aborts with *"Missing OpenAPI generator `clientConfig`"*.

| Option | Generated annotation | Shape |
|---|---|---|
| `clientConfigPrefix = "httpClient.pet"` | `@HttpClient("httpClient.pet.petApi")` | prefix + `.` + API class name, **first letter lower-cased** |
| `clientConfig = "httpClient.pet"` | `@HttpClient("httpClient.pet")` | used verbatim; the same section for every API in the spec |

The lower-casing comes from `clientConfigPath(String)` in `KoraCodegen` (and the identical helper
in `AbstractJavaGenerator` / `AbstractKotlinGenerator`):

```java
if (params.clientConfigPrefix != null && !params.clientConfigPrefix.isBlank()) {
    return params.clientConfigPrefix + "." + StringUtils.uncapitalize(clientName);
}
return params.clientConfig;
```

`clientName` is the generated API class name, which the OpenAPI tooling derives from the OpenAPI
**tag**: tag `pets` → `PetsApi` → `petsApi`; tag `pet` → `PetApi` → `petApi`; an operation with no
tag lands in `DefaultApi` → `defaultApi`.

The generator's own tests pin this behaviour —
`HttpClientJavaOpenapiTest.clientConfigPrefixAppendsLowerCamelClientName` and its Kotlin twin
generate from a spec tagged `pets` with `clientConfigPrefix = "httpClient"` and assert
`value = "httpClient.petsApi"`.

**This is a silent failure.** A Kora 1.x config still spelled `httpClient.pet.PetApi` is an
unrecognised HOCON section: it is ignored without a warning, the client has no `url`, and calls
hang until `requestTimeout` fires. Nothing reports a configuration problem.

Two reliable ways to obtain the key rather than guess it:

```bash
grep -rn '@HttpClient' build/generated/**/api/*Api.java     # or *Api.kt
```

or read the summary the generator logs after every client generation:

```
Generated Kora OpenAPI HTTP clients and config paths:
  - PetApi -> httpClient.pet.petApi (configPath)
```

## Runtime configuration keys { #runtime-config }

The generated `@HttpClient` interface is handed to the Kora HTTP client processor, which produces a
`$PetApi_Config` extending `DeclarativeHttpClientConfig` with one `HttpClientOperationConfig`
accessor **named after each interface method**.

```hocon
httpClient.pet.petApi {
  url = ${PET_API_URL}      # required
  requestTimeout = 10s      # optional, whole-request budget

  getPetById {              # per-operation override — the generated METHOD name, no suffix
    requestTimeout = 20s
    telemetry.logging.enabled = true
  }

  telemetry {
    logging.enabled = true  # 2.0 default: false
    metrics.enabled = true  # 2.0 default: false
    tracing.enabled = true  # 2.0 default: true
  }
}
```

| Key | Type | Notes |
|---|---|---|
| `url` | String | mandatory; no default |
| `requestTimeout` | Duration | nullable; covers DNS, connect, write, server time and read |
| `telemetry.logging.*` | | `enabled`, `maskQueries`, `maskHeaders`, `mask`, `pathFull`, `maxRequestBodyLogSize`, `maxResponseBodyLogSize` |
| `telemetry.tracing.*` | | `enabled`, `attributes`, `pathFull` |
| `telemetry.metrics.*` | | `enabled`, `slo`, `tags` |
| `<methodName>` | object | per-operation `requestTimeout` and `telemetry` overrides |

Logging and metrics are **off by default** in Kora 2.0, so an example that claims to demonstrate
either must enable it explicitly.

The 1.x `<operationId>Config` spelling does not exist in 2.0 — the accessor name is the method
name verbatim, so a `getPetByIdConfig { … }` block is dead config.

## `configOptions` reference { #config-options }

Verified against `CodegenParams`. Options marked *server* are ignored in client modes (the parser
gates them on `codegenMode.isServer()`).

| Option | Type | Default | Meaning |
|---|---|---|---|
| `mode` | String | `java-client` | One of the four modes above |
| `clientConfig` | String | — | Fixed config path applied to every generated client in this spec |
| `clientConfigPrefix` | String | — | Config prefix; `.` + lower-camel API name is appended per client |
| `clientResponseMode` | String | `SEALED` | `SEALED` returns the sealed response; `SUCCESSFUL` returns the success variant and throws declared errors — see [below](#response-mode). Case-insensitive |
| `securityConfigPrefix` | String | derived | Config prefix for generated credential lookups — see [authorization-reference.md](authorization-reference.md) |
| `primaryAuth` | String | — | Security scheme to prefer when an operation allows several |
| `authAsMethodArgument` | Boolean | `false` | Pass the credential as a generated method parameter instead of via the interceptor |
| `useSecurityDeclarationOrder` | Boolean | `false` | Derive auth tags and interceptors in the spec's declaration order instead of a normalised order |
| `tags` | JSON | `{}` | Per-OpenAPI-tag `httpClientTag` / `telemetryTag` |
| `extensions` | JSON | `{}` | Additional annotations and interceptors, per `*` / tag / operation |
| `filterWithModels` | Boolean | `false` | When `openapiNormalizer` `FILTER` is set, also drop unused models |
| `implicitHeaders` | Boolean | `false` | Do not generate header parameters as method arguments |
| `implicitHeadersRegex` | String | — | Regex selecting which headers `implicitHeaders` applies to |
| `forceIncludeOptional` | Boolean | `false` | Parsed, but no generator consumes it — it has no effect |
| `rawBodyMode` | String | `BYTES` | Bare-object body handling: `BYTES`, `BODY` or `OBJECT` |
| `enableServerValidation` | Boolean | `false` | *server* |
| `enableServerValidationInterceptor` | Boolean | `true` | *server* |
| `requestInDelegateParams` | Boolean | `false` | *server* |
| `serverConfigPrefix` | String | `httpServer.controller.%{ControllerTypeNameInCamelCase}` | *server* |
| `prefixPath` | String | `""` | *server* |
| `delegateMethodBodyMode` | String | `NONE` | *server* |

Removed in 2.0 with no drop-in replacement: `interceptors` (folded into `extensions`),
`additionalContractAnnotations` (folded into `extensions.*.additionalMethodAnnotations`),
`authAllowMultiple`, `enableJsonNullable`, `forceIncludeNonRequired`. Passing them is silently
ignored, so a build that still sets them looks fine and produces different code.

## Generated artifacts { #generated }

For `apiPackage = com.example.openapi.pet.api`, `modelPackage = …pet.model`, tag `pet`:

| File | Contents |
|---|---|
| `PetApi` | the `@HttpClient` interface: one synchronous method per operation, `@HttpRoute(method = "GET", path = "/pets/{petId}")`, `@Path` / `@Query` / `@Header` / `@Json` parameters, one `@ResponseCodeMapper` per declared status code |
| `PetApiResponses` | `sealed interface <Op>ApiResponse` per operation with a record (Java) / data class (Kotlin) per status code |
| `PetApiClientResponseMappers` | a `HttpClientResponseMapper` per response variant |
| `PetApiClientRequestMappers` | request body and form mappers |
| `PetApi<Op>OptArgs` | optional-argument holder + convenience overloads when an operation has optional parameters |
| `ApiSecurity` | `@Module` with scheme marker classes, `SecurityConfig` and token providers — only when the spec declares `securitySchemes` |
| model package | records (Java: `@JsonWriter` on the type, `@JsonReader` on the canonical constructor, one `withX` per component) / data classes (Kotlin: `@Json`), nested enums, `sealed interface` for discriminated schemas |

The response wrapper for the OpenAPI `default` response is named after the operation, not a status
code, and carries the actual code:

```java
sealed interface ListPetsApiResponse {
    record ListPets200ApiResponse(List<Pet> content, String xNext, String xOptionalNext)
            implements ListPetsApiResponse {}
    record ListPetsDefaultApiResponse(int statusCode, ModelError content)
            implements ListPetsApiResponse {}
}
```

Response headers declared in the contract become extra components on the variant (`xNext` above).
A status code with no body produces an empty `record X()` in Java and a plain `class X()` in
Kotlin — there is no `content` member to read.

Java variants expose the payload as `ok.content()`; Kotlin variants are data classes, so it is
`ok.content`.

Three further files — `$PetApi_ClientImpl`, `$PetApi_Config`, `$PetApi_Module` — are produced by
the Kora annotation processor or KSP from the generated interface. They are not OpenAPI generator
output, and they only appear if the processor is on the build.

When two or more responses of one operation share a body type, they also implement a sealed
`<Op><Type>ApiResponse` interface exposing `content()` and `statusCode()`, so one branch can handle
them together:

```java
sealed interface GetErrorsApiResponse {
    sealed interface GetErrorsModelErrorApiResponse extends GetErrorsApiResponse {
        ModelError content();
        int statusCode();
    }
    record GetErrors400ApiResponse(ModelError content) implements GetErrorsModelErrorApiResponse { … }
    record GetErrors404ApiResponse(ModelError content) implements GetErrorsModelErrorApiResponse { … }
}
```

## `clientResponseMode` — sealed or successful { #response-mode }

`SEALED` (the default) is everything above: every declared status is a variant of the returned
sealed type. With `SUCCESSFUL`, operations that declare at least one error response — a non-2xx
code, a `4XX`/`5XX` range or `default` — or whose return type is narrowed (several 2xx sharing one
body, e.g. `200` + `206`) are generated like this:

| Aspect | `SUCCESSFUL` output |
|---|---|
| Return type | the single 2xx variant (`<Op>200ApiResponse`); for several 2xx with one body type the shared `<Op><Type>ApiResponse`; otherwise the full sealed `<Op>ApiResponse` |
| Method mapping | `@Mapping(<Api>ClientResponseMappers.<Op>SuccessfulResponseMapper.class)` replaces the `@ResponseCodeMapper` list |
| Mapper | `<Op>SuccessfulResponseMapper`, `@Component` + `@DefaultComponent`, built from the per-code mappers; switches on the status code |
| Error statuses | body buffered, parsed by the per-code mapper, thrown as `<Api><Type>HttpClientResponseException` |
| Error without a body | `<Api>NoContentHttpClientResponseException` |
| Undeclared status | the `default` response's exception if `default` is declared, else `HttpClientResponseException.fromResponse(response)` |
| Error body that fails to parse | plain `HttpClientResponseException(code, headers, body)` with the parse failure added as suppressed |

The exception classes are nested in the `*Api` interface and generated **once per distinct error
body type across the whole API**, not per operation — `PetApi.PetApiModelErrorHttpClientResponseException`
serves every operation of `PetApi` whose error body is `ModelError`:

```java
public interface PetApi {
    class PetApiModelErrorHttpClientResponseException extends HttpClientResponseException {
        public PetApiModelErrorHttpClientResponseException(int code, HttpHeaders headers,
                                                           ModelError content, byte[] body) { … }
        public ModelError getContent() { … }
    }
    class PetApiNoContentHttpClientResponseException extends HttpClientResponseException { … }
}
```

```kotlin
public class PetApiModelErrorHttpClientResponseException(
    code: Int, headers: HttpHeaders, public val content: ModelError, body: ByteArray,
) : HttpClientResponseException(code, headers, body)
```

The type part of the name is the generated model name: a schema called `Error` becomes `ModelError`.
`HttpClientResponseException` (`io.koraframework.http.client.common.exception`) is unchecked and
exposes `getCode()`, `getHeaders()` and `getBytes()` (Kotlin: `code`, `headers`, `bytes`).

Because several statuses can map to one exception, branch on `getCode()` when the distinction
matters. Catch the typed exception before the base class.

Status-code ranges work in `SUCCESSFUL` mode: the mapper switches on exact codes first, then tests
`200 <= code < 300`, `400 <= code < 500`, … in order, then falls back to `default`. A `2XX` range is
a success and is returned (`<Op>2XXApiResponse`); `4XX`/`5XX` ranges are thrown as the typed
exception of their body type.

## Status-code ranges (`4XX`, `5XX`) { #ranges }

A response keyed `1XX`…`5XX` covers the whole class. It cannot be an `int` annotation member, so
the generator lowers it:

- the variant carries the real status: `record ListPets4XXApiResponse(int statusCode, ModelError content)`;
- exact codes keep their own `@ResponseCodeMapper(code = 404, …)` — an exact code wins over a range;
- ranges and `default` share one `@ResponseCodeMapper(code = ResponseCodeMapper.DEFAULT, mapper = <Op>DefaultCodeApiResponseMapper.class)`,
  which dispatches `400 <= code < 500` to the `4XX` mapper, `500 <= code < 600` to the `5XX` mapper,
  and anything else to the `default` mapper — or throws `HttpClientResponseException` when the
  operation has no `default`.

Ranges are generated for Java and Kotlin clients in both modes (see the previous section for
`SUCCESSFUL`).

## Enums { #enums }

A generated enum keeps the contract's raw value in a nested `Constants` holder and exposes
`fromValue`:

```java
public enum StatusEnum {
    AVAILABLE(Constants.AVAILABLE),
    PENDING(Constants.PENDING);

    private final String value;
    public String getValue() { return this.value; }

    public static StatusEnum fromValue(String value) { /* … */ }

    public static final class Constants {
        public static final String AVAILABLE = "available";
        public static final String PENDING = "pending";
    }
}
```

```kotlin
public enum class StatusEnum private constructor(public val value: String) {
    AVAILABLE(Constants.AVAILABLE),
    ;
    public companion object {
        @JvmStatic
        public fun fromValue(value: String): StatusEnum = /* … */
    }
    public object Constants { public const val AVAILABLE: String = "available" }
}
```

The constant name is a normalised identifier, not the wire value. Observed in the generator's own
fixtures: `available` → `AVAILABLE`, `Dingo-Don` → `DINGO_DON`, `Лелик` → `LELIK`,
`Mega3000Retriever` → `MEGA_3000_RETRIEVER`, integer `5` → `NUMBER_5`.

Therefore:

```java
StatusEnum.valueOf(raw)     // wrong — throws on every value whose name differs
StatusEnum.fromValue(raw)   // correct
```

`fromValue` throws `IllegalArgumentException("Unexpected value '…'")` only for values outside the
contract. Numeric and boolean enums take the corresponding parameter type
(`fromValue(Integer)` / `fromValue(Double)`).

## Models and constructor order { #models }

Constructor parameters follow the **order the properties are declared in the contract**. Required
and optional properties are *not* separated — an optional property declared between two required
ones stays there:

```yaml
Pet:
  required: [id, name]
  properties:
    id:            { type: integer, format: int64 }
    nonRequiredId: { type: integer, format: int64 }
    name:          { type: string }
    tag:           { type: string }
```

```kotlin
public data class Pet(
  public val id: Long,
  public val nonRequiredId: Long? = null,
  public val name: String,
  public val tag: String? = null,
)
```

Kotlin optional properties carry defaults — `= null`, or `= JsonNullable.nullValue()` for
`nullable: true, required: false` — so a positional call can omit trailing arguments while every
remaining position stays bound to the contract's order. Reorder two same-typed properties in the
spec (`name` and `tag` above) and an existing positional call still compiles while silently
swapping the values.

**Always construct generated Kotlin models with named arguments:**

```kotlin
Pet(id = pet.id, name = pet.name, tag = pet.tag)
```

Java models are records with the same component order, plus a secondary constructor taking only
the required properties, in declaration order:

```java
public record Pet(long id, @Nullable Long nonRequiredId, String name, @Nullable String tag) {
    public Pet(long id, String name) { this(id, null, name, null); }   // required-only
    public Pet withTag(@Nullable String tag) { /* … */ }               // one wither per component
}
```

Two constructors of different arity means an over- or under-supplied positional call can bind to
the other one. Nullability uses JSpecify (`org.jspecify.annotations.Nullable`) as a **type-use**
annotation, so its position in a qualified or generic type matters.

## Type mapping notes { #type-mapping }

| Schema | Generated type |
|---|---|
| `type: string, format: date-time` | `OffsetDateTime`, unless `typeMappings` maps `DateTime` (or `date-time`) to `Instant`, `ZonedDateTime` or `LocalDateTime` — simple or fully qualified name. Any other target falls back to `OffsetDateTime` |
| `type: object, additionalProperties: true` (free-form map) | `Map<String, Object>` / `Map<String, Any>` |
| `type: array` whose `items` is an inline `enum` | `List<Model.XxxEnum>` — the collection is kept, the nested enum is the element |

`typeMappings` is a property of the plugin's `GenerateTask`, not a `configOptions` entry:

```groovy
tasks.register("openApiGeneratePet", GenerateTask) {
    // …
    typeMappings = ["DateTime": "java.time.Instant"]
}
```

```kotlin
tasks.register<GenerateTask>("openApiGeneratePet") {
    // …
    typeMappings.set(mapOf("DateTime" to "java.time.Instant"))
}
```

Descriptions, summaries, response messages and string defaults are copied into Javadoc/KDoc and
default values as text, so a `%` (`%2B`) or `$` in the contract is safe; Kotlin string defaults get
their `$` escaped.

## `extensions` — annotations and interceptors { #extensions }

`extensions` replaces both `interceptors` and `additionalContractAnnotations` from 1.x. It is a
JSON document with an optional global `*` section, a `tags` map keyed by OpenAPI tag, and an
`operations` map keyed by `operationId`. All matching sections apply, in that order.

```groovy
configOptions = [
        mode              : "java-client",
        clientConfigPrefix: "httpClient.pet",
        extensions        : """
        {
          "*": {
            "additionalTypeAnnotations": ["@com.example.Audited"]
          },
          "tags": {
            "pet": {
              "interceptorType": "com.example.PetHttpClientInterceptor",
              "interceptorTag": ["com.example.PetTag"]
            }
          },
          "operations": {
            "getPetById": {
              "additionalMethodAnnotations": ["@com.example.Audited(client = \\"%{configPath}\\")"]
            }
          }
        }
        """,
]
```

| Key | Applies to |
|---|---|
| `additionalMethodAnnotations` | generated client methods |
| `additionalTypeAnnotations` | generated types (models and enums) |
| `additionalModelTypeAnnotations` | generated model types only |
| `additionalEnumTypeAnnotations` | generated enum types only |
| `interceptorType` | emits `@InterceptWith(<type>.class)`; omit it to use the default `HttpClientInterceptor` |
| `interceptorTag` | string or array; emits one `@InterceptWith(value = …, tag = <tag>.class)` per entry |
| `clientMapping.type` | replaces the per-status `@ResponseCodeMapper` set with a single `@Mapping(<type>.class)` |

Inside `additionalMethodAnnotations`, the placeholder `%{configPath}` is substituted with the
client's resolved config path — the same lower-camel value as the `@HttpClient` annotation. (It is
a generator placeholder for *your* annotation's member, unrelated to the `configPath` attribute
that `@HttpClient` carried in Kora 1.x and no longer has.)

`additionalTypeAnnotations` / `additionalModelTypeAnnotations` / `additionalEnumTypeAnnotations`
are read from the **global `*` section only**; per-tag and per-operation entries are ignored for
them.

Invalid JSON in `extensions` or `tags` fails generation with an explicit message naming the option
and the expected shape.

## `tags` — per-tag client and telemetry tags { #tags }

`tags` sets `httpClientTag` and `telemetryTag` on the generated `@HttpClient`, keyed by OpenAPI
tag; `*` is the fallback for tags not listed.

```groovy
configOptions = [
        mode: "java-client",
        tags: """
        {
          "*":   { "httpClientTag": "com.example.CommonTag", "telemetryTag": "com.example.CommonTag" },
          "pet": { "httpClientTag": "com.example.PetTag",    "telemetryTag": "com.example.PetTag" }
        }
        """,
]
```

Producing `@HttpClient(value = "httpClient.pet.petApi", httpClientTag = PetTag.class,
telemetryTag = PetTag.class)`. Use it to give one client its own transport instance or its own
telemetry configuration.

## OpenAPI normalizer { #normalizer }

`openapiNormalizer` rewrites the spec before generation. Plugin versions ≥ 7.0.0 enable
`SIMPLIFY_ONEOF_ANYOF` by default, which changes the output for polymorphic schemas:

```groovy
openapiNormalizer = [DISABLE_ALL: "true"]
```

Disable it when the contract relies on `oneOf` / `anyOf` and you want the generator to see the
schema exactly as written. `filterWithModels = true` extends the normalizer's `FILTER` option so
that models unreachable from the surviving operations are dropped too.

## Discriminators (oneOf + allOf) { #discriminators }

The pattern is `oneOf` (variants) + `allOf` (common base) + `discriminator` (selector):

```yaml
Pet:
  oneOf:
    - $ref: '#/components/schemas/PetCat'
    - $ref: '#/components/schemas/PetDog'
  allOf:
    - $ref: '#/components/schemas/PetCommon'
  discriminator:
    propertyName: pet_type
    mapping:
      CAT: '#/components/schemas/PetCat'
      DOG: '#/components/schemas/PetDog'
```

The generator emits a **sealed** base type carrying the Kora JSON discriminator annotation, plus
one implementation per variant:

```java
@Json
@JsonDiscriminatorField("pet_type")
public sealed interface Pet permits PetCommon, PetCat, PetDog {
    String petType();
}
```

Variants are ordinary generated models annotated with `@JsonDiscriminatorValue`. On the client
side, build a concrete variant to send and branch with pattern matching (`instanceof` / `when`) on
what comes back — the sealed hierarchy makes the switch exhaustive without a `default`.

Practical notes:

1. The discriminator property must exist on every variant, and `mapping` keys must match the
   values actually sent on the wire.
2. Keep the `allOf` base minimal — only genuinely shared properties.
3. With plugin ≥ 7.0.0, set `openapiNormalizer = [DISABLE_ALL: "true"]` so `SIMPLIFY_ONEOF_ANYOF`
   does not flatten the hierarchy.
4. An `example` on the polymorphic schema improves both generation diagnostics and the generated
   documentation.

## Testing a generated client { #testing }

Stub the remote with a MockServer container and point the client's `url` at it. The section name
must be the lower-camel config key, exactly as in production.

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
        return KoraConfigModification.ofString("""
            httpClient.pet.petApi {
              url = "%s"
              requestTimeout = 5s
            }
            """.formatted(mockserver.params().uri()));
    }

    @Test
    void getPetById() {
        mockserver.client()
            .when(request().withMethod("GET").withPath("/pet/1"))
            .respond(response().withBody("{\"id\":1,\"name\":\"Rex\",\"status\":\"available\"}"));

        var response = petApi.getPetById(1L);
        assertInstanceOf(PetApiResponses.GetPetByIdApiResponse.GetPetById200ApiResponse.class, response);
    }
}
```

A test that hangs until its timeout instead of failing is the signature of a misspelled config
section — including inside `KoraConfigModification.ofString`, which no `.conf` scanner will check.

---

## Related references

- [authorization-reference.md](authorization-reference.md) — `securitySchemes`, `ApiSecurity`,
  `HttpClientTokenProvider` tags and credential config paths
