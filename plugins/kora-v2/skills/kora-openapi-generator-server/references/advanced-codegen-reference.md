# Advanced Codegen — Kora 2.x OpenAPI Server

Options beyond `mode` and `enableServerValidation`, verified against `CodegenParams` and the
generator's own test fixtures for `2.0.0.RC2`.

## Contents

- [1. `extensions` — the one hook for extra annotations and interceptors](#1-extensions--the-one-hook-for-extra-annotations-and-interceptors)
- [2. `serverConfigPrefix` and `%{configPath}`](#2-serverconfigprefix-and-configpath)
- [3. Implicit headers](#3-implicit-headers)
- [4. `rawBodyMode`](#4-rawbodymode)
- [5. `filterWithModels` and `openapiNormalizer FILTER`](#5-filterwithmodels-and-openapinormalizer-filter)
- [6. `requestInDelegateParams` and `delegateMethodBodyMode`](#6-requestindelegateparams-and-delegatemethodbodymode)
- [7. `prefixPath`](#7-prefixpath)
- [8. Multi-spec projects](#8-multi-spec-projects)
- [9. Templates are not customisable any more](#9-templates-are-not-customisable-any-more)
- [10. Options that no longer exist](#10-options-that-no-longer-exist)

---

## 1. `extensions` — the one hook for extra annotations and interceptors

`configOptions.extensions` takes a JSON document with three optional sections:

```json
{
  "*":          { … },
  "tags":       { "<openapi tag baseName>": { … } },
  "operations": { "<operationId>": { … } }
}
```

Every matching section applies, in the order global → tag → operation. Each section object
accepts:

| Key | Type | Applies to | Effect |
|---|---|---|---|
| `additionalMethodAnnotations` | string or array | controller + delegate methods | Annotations added verbatim. `%{configPath}` is substituted (section 2). |
| `additionalTypeAnnotations` | string or array | models **and** enums | Global (`"*"`) section only. |
| `additionalModelTypeAnnotations` | string or array | models | Global section only. |
| `additionalEnumTypeAnnotations` | string or array | enums | Global section only. |
| `interceptorType` | string | controller methods | `@InterceptWith(TheType.class)` |
| `interceptorTag` | string or array | controller methods | `@InterceptWith(value = HttpServerInterceptor.class, tag = TheTag.class)`; combined with `interceptorType` it resolves that type by tag. |
| `clientMapping` | object | client mode only | see the client skill |

Annotation strings are parsed with a small parser: a leading `@` is optional, `Name(arg, k = v)`
is supported, and the type is resolved with `ClassName.bestGuess`, so **write fully-qualified
type names**.

```groovy
configOptions = [
    mode      : "java-server",
    extensions: """
        {
          "*": {
            "additionalModelTypeAnnotations": [
              "@io.koraframework.json.common.annotation.JsonInclude(io.koraframework.json.common.annotation.JsonInclude.IncludeType.ALWAYS)"
            ],
            "interceptorType": "com.example.api.AuditHttpServerInterceptor"
          },
          "tags": {
            "pet": { "additionalMethodAnnotations": ["@io.koraframework.logging.common.annotation.Log"] }
          },
          "operations": {
            "deletePet": { "interceptorTag": ["com.example.api.Tags.Admin"] }
          }
        }
        """,
]
```

Malformed JSON aborts generation with a message naming the option and the expected shape.

**Adding a method annotation opens the class.** The generator drops `final` (Java) / adds `open`
(Kotlin) on the controller as soon as `additionalMethodAnnotations` is non-empty anywhere, so
aspect-bearing annotations such as `@Log`, `@CircuitBreakable` or `@Cacheable` work.

## 2. `serverConfigPrefix` and `%{configPath}`

Some Kora annotations take a config path. `serverConfigPrefix` defines what `%{configPath}`
expands to inside `additionalMethodAnnotations`:

```
default: httpServer.controller.%{ControllerTypeNameInCamelCase}
```

`%{ControllerTypeNameInCamelCase}` is replaced with the controller type name, first letter
lower-cased — `PetApiController` → `petApiController`. So by default `%{configPath}` becomes
`httpServer.controller.petApiController`.

```groovy
configOptions = [
    mode              : "java-server",
    serverConfigPrefix: "myapp.api.%{ControllerTypeNameInCamelCase}",
    extensions        : """
        { "*": { "additionalMethodAnnotations": ["@com.example.RateLimited(\\"%{configPath}\\")"] } }
        """,
]
```

`%{configPath}` is substituted only in `additionalMethodAnnotations`, not in type annotations.

## 3. Implicit headers

`implicitHeaders: "true"` removes **every** header parameter from the generated controller and
delegate signatures, replacing it with a documentation annotation:

```java
@io.swagger.v3.oas.annotations.Parameter(name = "X-Request-Id", description = "", required = true,
    in = ParameterIn.HEADER)
```

`implicitHeadersRegex` does the same for header names matching a regex only:

```groovy
configOptions = [mode: "java-server", implicitHeadersRegex: "^X-Internal-.*"]
```

Use it when a gateway injects headers that every operation formally declares but no handler
reads. If a handler does need one of them, combine with `requestInDelegateParams: "true"` and
read it from `HttpServerRequest`. Note that the `@Parameter` annotation is Swagger's — it needs
`io.swagger.core.v3:swagger-annotations` on the compile classpath.

## 4. `rawBodyMode`

Controls the type used for a request/response body that is a bare `type: object` with no schema.

| Value | Server request body | Server response body |
|---|---|---|
| `BYTES` (default) | `byte[]` | `byte[]` |
| `BODY` | `HttpBodyInput` | `HttpBodyOutput` |
| `OBJECT` | `Object`, routed through the JSON mapper | `Object` |

`HttpBodyInput`/`HttpBodyOutput` are `io.koraframework.http.common.body.*` and let you stream
instead of materialising the payload. `OBJECT` is the right choice when the body really is
free-form JSON you intend to hand to a generic mapper. An invalid value fails generation with the
supported list.

Whenever a body is not JSON — including the `BYTES`/`BODY` bare-object cases — the delegate also
receives a leading `HttpHeaders _headers` parameter so it can read the real `Content-Type`.

## 5. `filterWithModels` and `openapiNormalizer FILTER`

Generating only part of a large shared contract:

```groovy
openapiNormalizer = [FILTER: "operationId:getPetById|addPet"]
configOptions = [mode: "java-server", filterWithModels: "true"]
```

`FILTER` (a plugin feature) drops the operations; `filterWithModels` (a Kora option) additionally
drops the models that only the removed operations referenced, so the output does not carry dead
DTOs. Without it you get the filtered API plus the full model set.

## 6. `requestInDelegateParams` and `delegateMethodBodyMode`

Both are covered in [Delegates Reference](openapi-delegates-reference.md). Summary:

- `requestInDelegateParams: "true"` prepends `HttpServerRequest _serverRequest` to every
  controller and delegate method — all-or-nothing.
- `delegateMethodBodyMode: "throwException"` makes delegate methods `default` bodies that throw
  and adds a `*ApiModule` supplying an anonymous delegate. The value `throw-exception` from 1.x
  is rejected. Because that module method is not `@DefaultComponent`, it collides with a
  hand-written `@Component` delegate.

## 7. `prefixPath`

Prefixes every route in the generated controller by filling `@HttpController`'s value.

The two languages emit it differently — Kotlin writes it as a quoted string (`%S`), Java writes it
verbatim into a JavaPoet format slot. In `java-server` mode pass the value already quoted:

```groovy
configOptions = [mode: "java-server",   prefixPath: '"/api/v1"']
```
```kotlin
configOptions.set(mapOf("mode" to "kotlin-server", "prefixPath" to "/api/v1"))
```

The safest option is to leave it unset and put the prefix in the contract's `paths`, so the served
URLs and the published spec cannot drift.

## 8. Multi-spec projects

One `GenerateTask` per spec, each with its own `outputDir`, `apiPackage` and `modelPackage`:

```groovy
def genPets = tasks.register("openApiGeneratePets", GenerateTask) {
    generatorName = "kora"
    inputSpec = layout.projectDirectory.file("src/main/resources/openapi/pets.yaml")
    outputDir = layout.buildDirectory.dir("generated/pets")
    apiPackage = "com.example.pets.api"
    modelPackage = "com.example.pets.model"
    configOptions = [mode: "java-server", enableServerValidation: "true"]
}

def genUsers = tasks.register("openApiGenerateUsers", GenerateTask) {
    generatorName = "kora"
    inputSpec = layout.projectDirectory.file("src/main/resources/openapi/users.yaml")
    outputDir = layout.buildDirectory.dir("generated/users")
    apiPackage = "com.example.users.api"
    modelPackage = "com.example.users.model"
    configOptions = [mode: "java-server", enableServerValidation: "true"]
}

sourceSets.main {
    java.srcDirs += genPets.get().outputDir
    java.srcDirs += genUsers.get().outputDir
}
compileJava.dependsOn genPets, genUsers
```

Each spec then produces its own `ApiSecurity`, so a marker is always
`com.example.pets.api.ApiSecurity.BearerAuth` — fully qualify it when two specs both declare
security, or the extractors will be tagged against the wrong package.

A server and a client generated from the same file must use different `apiPackage`s: both modes
emit an `ApiSecurity` and same-named model types.

## 9. Templates are not customisable any more

In Kora 2.0 the Mustache files under `openapi/templates/kora/` are one-line stubs that delegate
to JavaPoet/KotlinPoet generators (`javagen/*`, `kotlingen/*`). Overriding them with the plugin's
`templateDir` therefore cannot change the generated code. Shape output with `configOptions`, or
post-process by adding your own components — never by editing `build/generated`.

## 10. Options that no longer exist

`CodegenParams.parse` reads a fixed set of keys; anything else in `configOptions` is ignored
silently by the Kora generator. These 1.x-era keys are the ones most often left behind in a
migrated build file:

| Stale key | Replacement |
|---|---|
| `interceptors` | `extensions` with `interceptorType` / `interceptorTag` |
| `additionalContractAnnotations` | `extensions.*.additionalMethodAnnotations` |
| `enableJsonNullable` | none — `JsonNullable` is applied automatically to `nullable` + optional fields |
| `forceIncludeNonRequired` | none |
| `discriminatorCaseSensitive` | none — the constant exists in the source but is never parsed |
| `delegateMethodBodyMode: "throw-exception"` | `"throwException"` |
| `mode: "java-reactive-server"` etc. | `java-server` / `kotlin-server` |

`forceIncludeOptional` is a special case: it is parsed, but no generator consumes it, so setting
it changes nothing.

Because unknown keys are ignored rather than rejected, a stale option produces **no error and no
effect** — check the generated output, not the build log, when an option seems to do nothing.

## Related

- [Codegen Reference](openapi-codegen-reference.md)
- [Controllers Reference](openapi-controllers-reference.md)
- [Delegates Reference](openapi-delegates-reference.md)
- [Authorization Reference](authorization-reference.md)
