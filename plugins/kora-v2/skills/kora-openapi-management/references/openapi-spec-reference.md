# OpenAPI Spec Publishing Reference — Kora 2.0

**Verified against** the Kora 2.0 framework source for `2.0.0.RC2`
(`openapi/openapi-management/src/main/java/io/koraframework/openapi/management/`: `OpenApiManagementConfig`,
`OpenApiManagementModule`, `OpenApiHttpServerHandler`, `ResourceUtils`, `CacheHttpServerResponse`) and
the migrated `kora-java-crud` / `kora-kotlin-crud` examples plus the
`kora-*-guide-openapi-http-server-app` guides on `kora-examples` branch `migration/2.0`.

## Contents

1. What gets published
2. Where the file lives
3. The `files` key
4. Route layout: one file vs several
5. Content type, caching and headers
6. Versioning and audience layouts
7. Contract-first: publish what you generate from
8. `$ref` and external files
9. Native image
10. Validating a spec offline
11. Troubleshooting

---

## 1. What gets published

`OpenApiManagementModule` serves the **bytes of the resource** named in `files`, unchanged. It does
not parse, validate, resolve `$ref`s, merge documents, or rewrite `servers`. Whatever is on the
classpath is what a client downloads.

| Artifact | `io.koraframework:openapi-management` |
|---|---|
| Graph module | `io.koraframework.openapi.management.OpenApiManagementModule` |
| Also required | `io.koraframework:http-server-undertow` (`UndertowPublicHttpServerModule`) + a config module |
| Config section | `openapi.management` |
| Server | public only (`httpServer.port`) — the handlers are untagged |

---

## 2. Where the file lives

```
src/main/resources/
└── openapi/
    ├── api-v1.yaml
    ├── api-v2.yaml
    └── api-internal.yaml
```

Anything under `src/main/resources/` is copied to `build/resources/main/` and ends up on the
classpath, which is the only requirement. Formats: `.yaml`, `.yml`, `.json` — the extension only
influences the response `Content-Type` and the route segment (§4, §5).

`files` entries are **classpath resource paths, not filesystem paths**. `ResourceUtils` tries
`getResourceAsStream(path)` and then `getResourceAsStream("/" + path)`, so `openapi/api.yaml` and
`/openapi/api.yaml` both resolve. A path like `src/main/resources/openapi/api.yaml` or
`/etc/app/api.yaml` will not.

The resource is read **lazily on the first request**, so a wrong path does not break startup — the
route answers `404 OpenAPI file not found while reading: <path>`. Check `build/resources/main/`
when you see it.

---

## 3. The `files` key

```hocon
openapi.management.files = ["openapi/api-v1.yaml", "openapi/api-v2.yaml"]
```

- **Type:** `List<String>`.
- **Default:** none. The key is **mandatory**, and it is read while the DI graph is being built.
- A single string is also accepted; Kora's collection mapper splits a string value on `,` and trims
  each element. `files = "openapi/http-server.yaml"` and `files = ["openapi/http-server.yaml"]` are
  the same thing. The migrated `kora-java-crud` example uses the string form.

**Omitting `files` fails startup, even with `enabled = false`:**

```
ConfigValueException: Config expected value, but got null after parsing
at path: 'ROOT.openapi.management.files' for origin '<your config>'
```

The whole `openapi.management` object is mapped eagerly when the module's config component is
constructed, so there is no lazy escape. The Kora 1.x name `file` is simply an unknown HOCON key —
it is never read, and leaving it in place produces exactly this error rather than a hint.

---

## 4. Route layout: one file vs several

`OpenApiManagementModule#openApiManagementController` picks the route from the size of `files`:

| `files` | Route | Example |
|---|---|---|
| exactly one | `GET {path}` | `GET /openapi` |
| two or more | `GET {path}/{file}` | `GET /openapi/api-v1` |

`{file}` is the resource basename with its directory **and** its `.json` / `.yml` / `.yaml`
suffix stripped:

| `files` entry | Route segment |
|---|---|
| `openapi/api-v1.yaml` | `api-v1` |
| `openapi/v1/users-api.yml` | `users-api` |
| `specs/admin.json` | `admin` |

Unknown segment ⇒ `404 OpenAPI file not registered: <name>`.

> **Basenames must be unique.** The handler indexes specs in a map keyed by stripped basename, so
> `["openapi/v1/api.yaml", "openapi/v2/api.yaml"]` collapses to a single `/openapi/api` route
> serving whichever entry was registered last — and both viewer entries point at it. Rename the
> files (`api-v1.yaml`, `api-v2.yaml`) rather than relying on the directory to disambiguate; the
> directory is discarded.

Changing `path` moves the whole group:

```hocon
openapi.management.path = "/api/spec"    # GET /api/spec/api-v1, /api/spec/api-v2
```

The 1.x key for this was `endpoint`. It is ignored in 2.0, and the failure is silent: the specs
appear on the default `/openapi` instead.

---

## 5. Content type, caching and headers

| Extension | `Content-Type` |
|---|---|
| `.json` | `text/json; charset=utf-8` |
| anything else | `text/x-yaml; charset=utf-8` |

Every response carries `Vary: Accept-Encoding`. When the request advertises
`Accept-Encoding: gzip` (and not `gzip;q=0`), the body is gzipped and `Content-Encoding: gzip` is
set.

`openapi.management.cache` controls what is retained in memory:

| Mode | Gzipped response | Plain response |
|---|---|---|
| `NONE` | compressed per request | resource re-read per request |
| `GZIP` *(default)* | built once, reused for the process lifetime | resource re-read per request |
| `FULL` | cached | cached |

Cached content lives for the life of the process, so a rebuilt spec needs a restart to appear.

---

## 6. Versioning and audience layouts

### Separate file per version

```
openapi/
├── api-v1.yaml
├── api-v2.yaml
└── api-v3.yaml
```

```hocon
openapi.management.files = ["openapi/api-v1.yaml", "openapi/api-v2.yaml", "openapi/api-v3.yaml"]
```

Routes `/openapi/api-v1`, `/openapi/api-v2`, `/openapi/api-v3`, and both viewers get a selector.
Clear deprecation story; more files to keep in sync.

### One document, versioned paths

```yaml
paths:
  /api/v1/users: { get: { operationId: getUsersV1 } }
  /api/v2/users: { get: { operationId: getUsersV2 } }
```

Single route, single source of truth, but the document grows and retiring a version means editing
a shared file.

### Audience separation

```hocon
openapi.management.files = [
  "openapi/api-public.yaml",
  "openapi/api-internal.yaml",
  "openapi/api-admin.yaml"
]
```

Remember that publishing all three on one public route publishes all three to everyone. If
`api-internal` must not be reachable from outside, keep it out of `files` on that deployment (a
profile override) rather than relying on obscurity — and see §7 of
[swagger-ui-reference.md](swagger-ui-reference.md) for gating the routes with an interceptor.

---

## 7. Contract-first: publish what you generate from

The spec that drives code generation should be the spec that is published, so documentation cannot
drift from the generated transport layer. Keep it under `src/main/resources/openapi/`: it is
already on the classpath, so no copy task is needed, and point both at it.

```groovy
import org.openapitools.generator.gradle.plugin.tasks.GenerateTask

def openApiGenerateHttpServer = tasks.register("openApiGenerateHttpServer", GenerateTask) {
    generatorName = "kora"
    group = "openapi tools"
    inputSpec = layout.projectDirectory.file("src/main/resources/openapi/http-server.yaml")
    outputDir = layout.buildDirectory.dir("generated/openapi")
    def corePackage = "com.example.myapi"
    apiPackage = "${corePackage}.api"
    modelPackage = "${corePackage}.model"
    invokerPackage = "${corePackage}.invoker"
    configOptions = [
        mode                  : "java-server",
        enableServerValidation: "true",
    ]
}
sourceSets.main { java.srcDirs += openApiGenerateHttpServer.get().outputDir }
compileJava.dependsOn openApiGenerateHttpServer
```

```hocon
openapi {
  management {
    enabled = true
    files = ["openapi/http-server.yaml"]
    swaggerui { enabled = true }
    scalar    { enabled = true }
  }
}
```

This is exactly what the migrated `kora-java-crud` example does — one `http-server.yaml` used as
`inputSpec` and as the single entry of `files`.

Only four generator modes exist in Kora 2.0: `java-client`, `java-server`, `kotlin-client`,
`kotlin-server`. The reactive and suspend variants were removed. Generation options belong to
[`kora-openapi-generator-server`](../../kora-openapi-generator-server/SKILL.md).

---

## 8. `$ref` and external files

The module serves one resource per route and performs **no `$ref` resolution**. A document that
splits schemas across files:

```yaml
components:
  schemas:
    User:
      $ref: './common/schemas.yaml#/User'
```

is published with that `$ref` intact. The client — including the bundled Swagger UI and Scalar
pages — then resolves it relative to the URL it downloaded the document from, which is
`{path}` or `{path}/{name}`, not the resource directory. A relative `./common/schemas.yaml` will
not resolve.

Two workable options:

1. **Bundle before publishing.** Flatten the document at build time and point `files` at the
   flattened output (also the safer input for code generation).
2. **List every part in `files`** and reference them by their published routes, accepting that the
   route layout, not the directory layout, is what the `$ref`s must match.

Prefer option 1.

---

## 9. Native image

`openapi-management` ships its own
`META-INF/native-image/io.koraframework.openapi.management/resource-config.json`, registering only
its three bundled pages:

```
kora/openapi/management/scalar/index.page
kora/openapi/management/swagger-ui/index.page
kora/openapi/management/swagger-ui/oauth2-redirect.page
```

Your spec is an **application** resource and is not covered by it. Under `nativeCompile` the
viewers will therefore load while the spec route answers 404 unless you register it yourself, in
`src/main/resources/META-INF/native-image/<your-group>/resource-config.json`:

```json
{
  "resources": {
    "includes": [
      { "pattern": "\\Qopenapi/http-server.yaml\\E" }
    ]
  }
}
```

The file **name** is load-bearing — GraalVM reads `resource-config.json`; `resources-config.json`
or `resource_config.json` is silently ignored.

---

## 10. Validating a spec offline

[`../scripts/validate_openapi.py`](../scripts/validate_openapi.py) is a dependency-light sanity
check (PyYAML only) for the things that break code generation and produce empty-looking
documentation: missing `openapi` / `info.title` / `info.version`, paths without `operationId` or
responses, self-referencing schemas, and security schemes Kora's generator handles specially.

```bash
python3 scripts/validate_openapi.py --spec src/main/resources/openapi/api.yaml
python3 scripts/validate_openapi.py --spec src/main/resources/openapi/api.yaml --strict
python3 scripts/validate_openapi.py --spec src/main/resources/openapi/api.yaml --json
```

Exit code `0` on success, `1` on failure — with `--strict`, warnings count as failures. It is a
lint, not an OpenAPI 3.x schema validator; for full validation use an external tool:

```bash
npx @apidevtools/swagger-cli validate src/main/resources/openapi/api.yaml
npx @stoplight/spectral-cli lint  src/main/resources/openapi/api.yaml
```

---

## 11. Troubleshooting

| Symptom | Cause |
|---|---|
| `ConfigValueException: … null after parsing at path: 'ROOT.openapi.management.files'` | `files` missing, or the 1.x `file` was carried over. Mandatory even when `enabled = false` |
| Spec route answers on `/openapi` though you configured another path | The 1.x `endpoint` key was used; the 2.0 key is `path` |
| `404 OpenAPI file not found while reading: …` | Not on the classpath at that path — check `build/resources/main/` |
| `404 OpenAPI file not registered: …` | The `{file}` segment matches no stripped basename from `files` |
| `GET /openapi` → 404 with several files configured | With two or more files the route is `{path}/{file}`; there is no combined document |
| Two specs configured, one unreachable | Duplicate stripped basenames — see §4 |
| Viewer shows an empty document | The published bytes have no `paths`; validate the file, then re-check which resource is actually on the classpath |
| Updated spec still serves the old content | Cached in memory (`cache = GZIP` / `FULL`) — restart, or set `cache = NONE` |
| Works on the JVM, spec 404s in a native image | The application resource is not registered — see §9 |

---

## Related references

- [swagger-ui-reference.md](swagger-ui-reference.md) — Swagger UI config, `options`, OAuth2 redirect, securing
- [scalar-reference.md](scalar-reference.md) — the Scalar viewer (replaces RapiDoc)
- Code generation: [`kora-openapi-generator-server`](../../kora-openapi-generator-server/SKILL.md)
