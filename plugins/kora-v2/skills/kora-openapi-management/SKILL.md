---
name: kora-openapi-management
description: "Publish OpenAPI documents and the bundled Swagger UI / Scalar viewers over the Kora 2.0 public HTTP server with io.koraframework.openapi.management.OpenApiManagementModule (artifact io.koraframework:openapi-management). Covers the openapi.management config section — files (a list, mandatory), path, cache, swaggerui.*, scalar.* — the default /openapi, /swagger-ui, /scalar routes, gzip response caching, and gating the docs with a @Tag(HttpServer.class) interceptor. Use to expose a spec or an interactive viewer; also use when porting openapi.management.file / endpoint / rapidoc from Kora 1.x. Not for code generation — see kora-openapi-generator-server and kora-openapi-generator-client."
license: Apache-2.0
metadata:
  kora-version: "2.x"
---

# Kora OpenAPI Management

> **Kora sub-skill — obey the [kora-v2 meta rules](../../SKILL.md) on every task:** **R0** ground the workspace on Kora 2.0 refs before starting (framework source at tag `2.0.0.RC2` + `kora-examples` at `migration/2.0` + Kora 2.0 docs at koraframework.io/v2, which trail the source; 1.x `kora-docs` pages are never an authority) · **R1** read this sub-skill before writing code · **R2** Kora 2.0 APIs only — no Spring/Micronaut/Quarkus, no Kora 1.x APIs, no invented annotations or config keys · **R3** journal any incorrect Kora usage. Add comments/Javadoc only if asked.

| | |
|---|---|
| **Artifact** | `io.koraframework:openapi-management` (BOM `io.koraframework:kora-bom`, `2.0.0.RC2`) |
| **Graph module** | `io.koraframework.openapi.management.OpenApiManagementModule` |
| **Also required** | `io.koraframework:http-server-undertow` → `UndertowPublicHttpServerModule`; a config module (`HoconConfigModule` / `YamlConfigModule`) |
| **Config section** | `openapi.management` |
| **Bundled viewers** | Swagger UI and **Scalar**. RapiDoc does not exist in Kora 2.0 |
| **Default routes** | `GET /openapi` · `GET /swagger-ui` · `GET /swagger-ui/oauth2-redirect` · `GET /scalar` — all on the **public** server (`httpServer.port`) |

The module contributes plain `HttpServerRequestHandler` components, so the routes are ordinary
public-server routes: global interceptors see them, and the system server (`httpServer.system`)
never serves them. Both viewer pages ship inside the jar with every asset inlined (≈1.9 MB Swagger
UI, ≈3.9 MB Scalar) — no CDN call, so they work in an air-gapped network.

---

## Migrating from Kora 1.x — read this first

Every key in the 1.x `openapi.management` section was renamed, and unknown HOCON keys are ignored
without a warning. A copied 1.x block does not "mostly work".

| 1.x | 2.0 | If you skip it |
|---|---|---|
| `openapi.management.file` | **`files`** (still a list) | **The application does not start.** `files` has no default and is not `@Nullable`, so the missing key throws `ConfigValueException: Config expected value, but got null after parsing at path: 'ROOT.openapi.management.files'` while the graph is being built. `file` is simply an unknown key and is never read. |
| `openapi.management.endpoint` | **`path`** | Silent. `endpoint` is ignored, `path` falls back to `/openapi`, and the spec appears on the default route instead of yours — so does the Swagger UI link that is derived from it. |
| `openapi.management.rapidoc.*` | **`scalar.*`** | Silent. There is no RapiDoc handler in 2.0; the whole `rapidoc` block is dead config and no second viewer is served. |
| `@Tag(HttpServerModule.class)` on the interceptor gating the docs | **`@Tag(HttpServer.class)`** | **Compiles clean, never runs.** `HttpServerModule` still exists, so the annotation is legal, but `publicHttpApiRouter` collects interceptors by `@Tag(HttpServer.class)` only — the gate silently disappears and `/swagger-ui` is public. |
| `intercept(Context, request, chain)` → `CompletionStage` | **`intercept(request, chain)` → `HttpServerResponse`** | Compile error. `Context` no longer exists anywhere in Kora. |
| `UndertowHttpServerModule` | **`UndertowPublicHttpServerModule`** | Compile error — the 1.x type is gone. |
| `ru.tinkoff.kora.openapi.management.*` | **`io.koraframework.openapi.management.*`** | Compile error. |

`files` being mandatory is not a formality: **adding `OpenApiManagementModule` to `@KoraApp` and
configuring nothing at all fails startup**, even with `enabled = false`, because the whole config
object is mapped eagerly when the graph is built.

---

## Quick start

### 1. Dependencies (Java)

```groovy
configurations {
    koraBom
    annotationProcessor.extendsFrom(koraBom)
    compileOnly.extendsFrom(koraBom)
    implementation.extendsFrom(koraBom)
}

dependencies {
    koraBom platform("io.koraframework:kora-bom:$koraVersion")   // koraVersion=2.0.0.RC2
    annotationProcessor "io.koraframework:annotation-processors" // mandatory for @KoraApp

    implementation "io.koraframework:openapi-management"
    implementation "io.koraframework:http-server-undertow"       // required: the module serves over it
    implementation "io.koraframework:config-hocon"
    implementation "io.koraframework:logging-logback"
}
```

Kotlin replaces the processor with KSP:

```kotlin
implementation(platform("io.koraframework:kora-bom:${property("koraVersion")}"))
ksp("io.koraframework:symbol-processors:${property("koraVersion")}")
implementation("io.koraframework:openapi-management")
implementation("io.koraframework:http-server-undertow")
```

Java **25** is the floor. Artifacts other than the BOM are never versioned individually, and
`2.0.0.RC2` resolves from plain `mavenCentral()`.

### 2. Application graph

```java
@KoraApp
public interface Application extends
        HoconConfigModule,
        LogbackModule,
        UndertowPublicHttpServerModule,
        OpenApiManagementModule {

    static void main(String[] args) {
        KoraApplication.run(ApplicationGraph::graph);
    }
}
```

`OpenApiManagementModule` only produces request handlers — without an HTTP server module in the
graph nothing routes them.

### 3. Put the spec on the classpath

```
src/main/resources/
└── openapi/
    ├── api-v1.yaml
    └── api-v2.yaml
```

`files` entries are **classpath resource paths**, not filesystem paths. They are resolved with
`getResourceAsStream(path)` and then `getResourceAsStream("/" + path)`, so `openapi/api-v1.yaml`
and `/openapi/api-v1.yaml` both work. The file is read lazily on the first request, so a wrong path
does not fail startup — it returns **404 `OpenAPI file not found while reading: <path>`**.

### 4. Configure

Every toggle defaults to `false`; `files` has no default at all.

```hocon
openapi {
  management {
    enabled = true
    files = ["openapi/api-v1.yaml", "openapi/api-v2.yaml"]
    swaggerui {
      enabled = true
    }
    scalar {
      enabled = true
    }
  }
}
```

| Route | Serves |
|---|---|
| `GET /openapi/api-v1` | `openapi/api-v1.yaml` |
| `GET /openapi/api-v2` | `openapi/api-v2.yaml` |
| `GET /swagger-ui` | Swagger UI with a spec selector |
| `GET /swagger-ui/oauth2-redirect` | Swagger UI OAuth2 redirect page (registered with the UI) |
| `GET /scalar` | Scalar with a spec selector |

---

## Configuration reference — `openapi.management`

Every key below exists in `OpenApiManagementConfig`; nothing else in the section is read.

| Key | Type | Default | Meaning |
|---|---|---|---|
| `enabled` | `boolean` | `false` | Register the raw-spec route. `false` ⇒ the route is not registered at all (404), **and the viewers have nothing to fetch** |
| `files` | `List<String>` | **none — mandatory** | Classpath resource paths of the specs |
| `path` | `String` | `/openapi` | Base route for the raw specs |
| `cache` | `NONE` \| `GZIP` \| `FULL` | `GZIP` | Response caching for the raw specs — see [Caching](#caching) |
| `swaggerui.enabled` | `boolean` | `false` | Register `GET {swaggerui.path}` and its `/oauth2-redirect` companion |
| `swaggerui.path` | `String` | `/swagger-ui` | Swagger UI route |
| `swaggerui.withCredentials` | `boolean` | `true` | Emits `withCredentials: true` plus a `requestInterceptor` that sets `request.credentials = "include"` |
| `swaggerui.cache` | `NONE` \| `GZIP` \| `FULL` | `GZIP` | Response caching for the rendered UI page |
| `swaggerui.options` | `Map<String,String>` | see below | Raw Swagger UI init options, injected verbatim into `SwaggerUIBundle({...})` |
| `scalar.enabled` | `boolean` | `false` | Register `GET {scalar.path}` |
| `scalar.path` | `String` | `/scalar` | Scalar route |
| `scalar.cache` | `NONE` \| `GZIP` \| `FULL` | `GZIP` | Response caching for the rendered Scalar page |

`swaggerui.options` default:

```
layout=StandaloneLayout · validatorUrl=null · defaultModelsExpandDepth=0
deepLinking=true · persistAuthorization=true · displayOperationId=true · filter=true
```

**Setting `options` replaces the whole map — it does not merge.** The default is used only when the
key is absent, so `options { filter = "false" }` also drops `layout`, `deepLinking` and the rest.
Repeat every entry you want to keep. Details and value-literal rules in
[swagger-ui-reference.md](references/swagger-ui-reference.md).

**The `swaggerui` key is spelled exactly `swaggerui`.** Kora relaxes key names only across
camelCase / kebab-case / snake_case, and `swaggerui` is a single lowercase token — `swaggerUi` and
`swagger-ui` do not match it and are silently ignored.

The `swaggerui` and `scalar` blocks may be omitted entirely; a missing object maps to an
all-defaults instance, which means both viewers are off.

### YAML

Same keys, same nesting, via `io.koraframework:config-yaml` + `YamlConfigModule`:

```yaml
openapi:
  management:
    enabled: true
    files:
      - "openapi/api-v1.yaml"
      - "openapi/api-v2.yaml"
    swaggerui:
      enabled: true
    scalar:
      enabled: true
```

### `files` accepts a list or a comma-separated string

A HOCON array is the clear form, but a plain string is also valid — Kora's collection mapper splits
a string value on `,` and trims each element. Both of these are one file:

```hocon
files = ["openapi/http-server.yaml"]
files = "openapi/http-server.yaml"
```

---

## Route layout

The number of entries in `files` changes the raw-spec route shape.

- **One file** → `GET {path}` returns it directly. Default: `GET /openapi`.
- **Several files** → the route becomes `GET {path}/{file}`, where `{file}` is the resource
  basename with its directory and its `.json` / `.yml` / `.yaml` suffix stripped.
  `openapi/v1/users-api.yaml` ⇒ `GET /openapi/users-api`.

An unknown `{file}` returns **404 `OpenAPI file not registered: <name>`**.

> **Basenames must be unique.** The handler indexes the specs by stripped basename, so
> `["openapi/v1/api.yaml", "openapi/v2/api.yaml"]` collapses to a single `/openapi/api` route
> serving whichever entry was registered last, and both viewer entries point at it. Name the files
> `api-v1.yaml` / `api-v2.yaml` instead.

`Content-Type` follows the extension: `text/json; charset=utf-8` for `.json`, otherwise
`text/x-yaml; charset=utf-8`.

---

## Caching

The raw-spec and viewer responses go through the module's own small response cache. Every response
carries `Vary: Accept-Encoding`. When the request advertises `Accept-Encoding: gzip` (and not
`gzip;q=0`), the body is gzipped and `Content-Encoding: gzip` is set.

| `cache` | Gzipped response | Plain response |
|---|---|---|
| `NONE` | content re-loaded and re-gzipped on every request | content re-loaded on every request |
| `GZIP` *(default)* | gzipped once, reused for the process lifetime | content re-loaded on every request |
| `FULL` | cached | cached |

"Content" is the spec resource for `/openapi` and the rendered page for the viewers. Anything
cached lives for the life of the process, so an updated spec needs a restart. `NONE` is the option
to pick if you want the resource re-read every time; it costs a full gzip pass per request.

The three values are matched **case-sensitively** against the enum constants — `NONE`, `GZIP`,
`FULL`. `gzip` raises `ConfigValueException: Unknown enum value: gzip when expected one of […]`.

---

## Securing the documentation routes

Two options, in order of preference.

1. **Turn it off where it does not belong.** `openapi.management.swaggerui.enabled = false` (and
   `scalar.enabled = false`) in the production override leaves the raw spec available to tooling
   while removing the interactive viewers. Setting `enabled = false` as well removes the spec too.
2. **Gate it with a global interceptor.** The handlers come from the module, not from your code, so
   there is nothing to annotate with `@InterceptWith`. Register one `HttpServerInterceptor` as a
   `@Component` tagged **`@Tag(HttpServer.class)`** (`io.koraframework.http.server.common.HttpServer`),
   check `request.path()` against the docs prefixes and call `chain.process(request)` for
   everything else. Ready-to-copy templates:
   [`assets/SwaggerUiSecurityInterceptor.java.template`](assets/SwaggerUiSecurityInterceptor.java.template),
   [`assets/SwaggerUiSecurityInterceptor.kt.template`](assets/SwaggerUiSecurityInterceptor.kt.template).

`@Tag(HttpServerModule.class)` from 1.x still compiles and the gate silently never runs. Cover it
with a test that asserts an unauthenticated `GET /swagger-ui` is rejected.

---

## Contract-first: publish the spec you generate from

Keep the spec under `src/main/resources/openapi/` and point both the generator and the management
module at the same file — it is already on the classpath, so no copy task is needed and the
published document cannot drift from the generated transport layer.

```groovy
inputSpec = layout.projectDirectory.file("src/main/resources/openapi/http-server.yaml")
```
```hocon
openapi.management.files = ["openapi/http-server.yaml"]
```

Generation options belong to [`kora-openapi-generator-server`](../kora-openapi-generator-server/SKILL.md).

---

## Troubleshooting

| Symptom | Cause |
|---|---|
| Startup fails: `Config expected value, but got null after parsing at path: 'ROOT.openapi.management.files'` | `files` is missing, or you wrote the 1.x `file`. It is mandatory even when `enabled = false` |
| Swagger UI loads but shows *Failed to load API definition* | `openapi.management.enabled` is still `false`, so the raw-spec route the UI fetches is not registered |
| `GET /swagger-ui` → 404 | `swaggerui.enabled` is `false` (the default), or the key is misspelled `swaggerUi` / `swagger-ui` |
| `GET /scalar` → 404 | `scalar.enabled` is `false`. If you were looking for `/rapidoc`, RapiDoc does not exist in 2.0 |
| Spec route answers on `/openapi` instead of your path | You set the 1.x `endpoint`; the key is `path` |
| 404 `OpenAPI file not found while reading: …` | The resource is not on the classpath at that path — check it lands in `build/resources/main/` |
| 404 `OpenAPI file not registered: …` | The `{file}` segment does not match any stripped basename from `files` |
| Two specs, only one reachable | Duplicate basenames — see [Route layout](#route-layout) |
| Swagger UI lost its filter / deep-linking after adding one option | `options` replaces the default map wholesale |
| Docs interceptor never fires | `@Tag(HttpServerModule.class)` instead of `@Tag(HttpServer.class)` |
| Routes missing on the system port | By design — the handlers are untagged, so they are public-server only |
| `nativeCompile` build serves the viewers but 404s the spec | The module registers only its own `kora/openapi/management/**` pages in `resource-config.json`; your spec is an application resource and needs its own entry |

---

## References

| Document | Contents |
|---|---|
| [swagger-ui-reference.md](references/swagger-ui-reference.md) | Swagger UI config, the `options` map and its literal rules, OAuth2 redirect, securing, troubleshooting |
| [scalar-reference.md](references/scalar-reference.md) | Scalar config, how it replaced RapiDoc, viewer comparison |
| [openapi-spec-reference.md](references/openapi-spec-reference.md) | Spec placement, multi-spec layouts, versioning, contract-first wiring, validation |

## Assets

| Template | Contents |
|---|---|
| `assets/Application.server.java.template` · `.kt.template` | `@KoraApp` wiring `OpenApiManagementModule` + `UndertowPublicHttpServerModule` |
| `assets/application.conf.template` | Base HOCON with every real key annotated |
| `assets/application.dev.conf.template` · `assets/application.prod.conf.template` | Environment overrides |
| `assets/build.gradle.server.template` | Gradle: `openapi-management` + contract-first codegen |
| `assets/SwaggerUiSecurityInterceptor.java.template` · `.kt.template` | `@Tag(HttpServer.class)` interceptor gating `/openapi`, `/swagger-ui`, `/scalar` |
| `assets/openapi-spec.yaml.template` | Example OpenAPI 3.x document |
| `scripts/validate_openapi.py` | Offline spec sanity check (`--strict`, `--json`) |

## Related skills

- [`kora-openapi-generator-server`](../kora-openapi-generator-server/SKILL.md) — generate server delegates from a spec
- [`kora-openapi-generator-client`](../kora-openapi-generator-client/SKILL.md) — generate typed HTTP clients
- [`kora-http-server`](../kora-http-server/SKILL.md) — server config, ports, interceptors
- [`kora-http-server-auth`](../kora-http-server-auth/SKILL.md) — principal extraction for the API itself
