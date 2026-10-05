# Scalar Reference — Kora 2.0

**Verified against** the Kora 2.0 framework source for `2.0.0.RC2`
(`openapi/openapi-management/src/main/java/io/koraframework/openapi/management/ScalarHttpServerHandler.java`,
`OpenApiManagementConfig.ScalarConfig`, `OpenApiManagementModule#scalarManagementController`), the
bundled page `src/main/resources/kora/openapi/management/scalar/index.page`, the module tests
(`OpenApiTests#scalarSourcesSingleFile`, `#scalarSourcesMultipleFiles`), and the migrated examples
`kora-java-crud` / `kora-kotlin-crud` on `kora-examples` branch `migration/2.0`.

## Contents

1. RapiDoc is gone — Scalar replaced it
2. Setup
3. Configuration keys
4. What the bundled page fixes for you
5. How Scalar finds the specs
6. Response caching
7. Choosing between Scalar and Swagger UI
8. Migrating a 1.x `rapidoc` block
9. Troubleshooting

---

## 1. RapiDoc is gone — Scalar replaced it

Kora 2.0 ships **two** OpenAPI viewers, Swagger UI and [Scalar](https://scalar.com). RapiDoc is not
one of them.

Evidence, not recollection — `io.koraframework.openapi.management` contains exactly these types:

```
CacheHttpServerResponse        OpenApiManagementConfig     ResourceUtils
OpenApiHttpServerHandler       OpenApiManagementModule     ScalarHttpServerHandler
SwaggerOauthHttpServerHandler  SwaggerUIHttpServerHandler
```

There is no RapiDoc handler, `OpenApiManagementConfig` has no `rapidoc()` accessor, and
`OpenApiManagementModule` registers no fourth viewer route. A `rapidoc { … }` block left in
`application.conf` is an unknown HOCON key: **it is ignored without any warning**, and no second
viewer is served.

The bundled Scalar page is a single ≈3.9 MB file inside the jar with every asset inlined — no CDN
request, so it renders in an air-gapped network exactly as it does with internet access.

---

## 2. Setup

Same module and dependencies as Swagger UI; only the config block differs.

**Java**

```groovy
dependencies {
    koraBom platform("io.koraframework:kora-bom:$koraVersion")   // 2.0.0.RC2
    annotationProcessor "io.koraframework:annotation-processors"

    implementation "io.koraframework:openapi-management"
    implementation "io.koraframework:http-server-undertow"
    implementation "io.koraframework:config-hocon"
}
```

```java
@KoraApp
public interface Application extends
        HoconConfigModule,
        UndertowPublicHttpServerModule,
        OpenApiManagementModule {

    static void main(String[] args) {
        KoraApplication.run(ApplicationGraph::graph);
    }
}
```

**Kotlin**

```kotlin
dependencies {
    implementation(platform("io.koraframework:kora-bom:${property("koraVersion")}"))
    ksp("io.koraframework:symbol-processors:${property("koraVersion")}")

    implementation("io.koraframework:openapi-management")
    implementation("io.koraframework:http-server-undertow")
    implementation("io.koraframework:config-hocon")
}
```

```kotlin
@KoraApp
interface Application :
    HoconConfigModule,
    UndertowPublicHttpServerModule,
    OpenApiManagementModule

fun main() {
    KoraApplication.run(ApplicationGraph::graph)
}
```

---

## 3. Configuration keys

```hocon
openapi {
  management {
    enabled = true
    files = ["openapi/api.yaml"]
    scalar {
      enabled = true
    }
  }
}
```

- `GET /scalar` — the Scalar viewer
- `GET /openapi` — the raw spec

Complete key set under `openapi.management.scalar`:

| Key | Type | Default |
|---|---|---|
| `enabled` | `boolean` | `false` |
| `path` | `String` | `/scalar` |
| `cache` | `NONE` \| `GZIP` \| `FULL` | `GZIP` |

That is all of it. Unlike `swaggerui`, Scalar has **no `options` map, no `withCredentials`, and no
companion redirect route** — its behaviour is fixed by the bundled page (§4).

**`enabled = true` at the `management` level is required**, because the viewer fetches the raw-spec
route. With `openapi.management.enabled = false` the route does not exist and Scalar renders no
document.

The whole `scalar` block may be omitted; a missing object maps to an all-defaults instance, which
leaves the viewer off.

### Both viewers at once

They are independent handlers on independent routes, so enabling both is normal — the migrated
`kora-java-crud` example does exactly that:

```hocon
openapi {
  management {
    enabled = true
    files = "openapi/http-server.yaml"
    swaggerui { enabled = true }
    scalar    { enabled = true }
  }
}
```

### Custom path

```hocon
openapi {
  management {
    enabled = true
    files = ["openapi/api.yaml"]
    path = "/api/spec"
    scalar {
      enabled = true
      path = "/api/reference"
    }
  }
}
```

`GET /api/reference` renders the viewer; `GET /api/spec` serves the document.

---

## 4. What the bundled page fixes for you

The page calls `Scalar.createApiReference('#app', { … })` with these settings baked in — they are
not configurable through `openapi.management`:

| Setting | Value | Effect |
|---|---|---|
| `telemetry` | `false` | Scalar sends no usage telemetry |
| `persistAuth` | `true` | credentials entered in the viewer survive a reload |
| `searchHotKey` | `'f'` | opens search |
| `withDefaultFonts` | `false` | no external web fonts are requested |
| `localization.locale` | `'en'` | English UI |
| `mcp.disabled` / `agent.disabled` | `true` | the MCP and AI-agent panels are turned off |
| `hiddenClients` | curated list | trims the per-language client-snippet menu |

`telemetry: false`, `withDefaultFonts: false` and the fully inlined bundle together mean the page
makes **no outbound request of its own** — worth knowing before exposing it in a restricted
network, and worth not undoing by editing the page.

---

## 5. How Scalar finds the specs

`ScalarHttpServerHandler` substitutes a `sources: [ … ]` array into the page. Each entry takes the
current browser URL, strips any `#…` fragment, and string-replaces `scalar.path` with the raw-spec
route:

- **one file** ⇒ one source pointing at `path`, titled with the file's stripped basename
- **several files** ⇒ one source per file pointing at `path/{basename}`, each titled with that
  basename — this is what renders the document selector

Consequences:

- It works unchanged behind a reverse proxy that adds a path prefix, because the prefix survives
  the replacement.
- `path` and `scalar.path` should be siblings at the same depth; nesting the viewer under the spec
  path makes the replacement produce a wrong URL.
- Titles are the stripped basenames of `files`, so `["openapi/v1/api.yaml", "openapi/v2/api.yaml"]`
  yields two identically titled entries pointing at the same route. Use distinct basenames.

---

## 6. Response caching

`scalar.cache` uses the same three-mode response cache as the rest of the module:

| Mode | Behaviour |
|---|---|
| `NONE` | the page is re-rendered (and re-gzipped) on every request |
| `GZIP` *(default)* | the gzipped page is rendered once and reused; non-gzip clients re-render |
| `FULL` | both the gzipped and the plain page are cached |

Every response carries `Vary: Accept-Encoding`; `Accept-Encoding: gzip;q=0` gets the uncompressed
page. The page is ≈3.9 MB before compression, so leave the default unless you have a reason not to.

---

## 7. Choosing between Scalar and Swagger UI

Both are first-class in Kora 2.0 and cost the same to enable. The difference visible from the
framework side is how much you can tune:

| | Swagger UI | Scalar |
|---|---|---|
| Config keys | `enabled`, `path`, `withCredentials`, `cache`, `options` | `enabled`, `path`, `cache` |
| Arbitrary viewer options | yes — `options` is spliced into `SwaggerUIBundle({…})` | no |
| OAuth2 redirect route | yes, `{path}/oauth2-redirect` | no |
| Sends cookies on try-it-out | `withCredentials`, default `true` | not configurable |
| Bundled page size | ≈1.9 MB | ≈3.9 MB |
| Outbound requests | none | none |

Pick Swagger UI when you need OAuth2 redirect handling, cookie-credentialed try-it-out, or a
specific viewer option. Pick Scalar for a modern reading experience with zero configuration
surface. Enabling both is a perfectly ordinary setup.

Judgements about how either viewer renders a particular `oneOf` or `discriminator` are properties
of the viewer, not of Kora, and this skill does not assert them — verify against your own document.

---

## 8. Migrating a 1.x `rapidoc` block

```hocon
# Kora 1.x — none of these keys exist in 2.0
openapi.management.file = ["openapi/api.yaml"]
openapi.management.rapidoc.enabled  = true
openapi.management.rapidoc.endpoint = "/rapidoc"
```

```hocon
# Kora 2.0
openapi.management.enabled      = true
openapi.management.files        = ["openapi/api.yaml"]
openapi.management.scalar.enabled = true
openapi.management.scalar.path    = "/scalar"
```

Three separate renames, and only one of them is loud:

| 1.x | 2.0 | Failure if skipped |
|---|---|---|
| `file` | `files` | **Startup fails** — `ConfigValueException: Config expected value, but got null after parsing at path: 'ROOT.openapi.management.files'` |
| `rapidoc` | `scalar` | Silent — the block is ignored, no viewer is served |
| `endpoint` | `path` | Silent — the default `/openapi` (or `/scalar`) is used instead |

Anything still pointing users at `/rapidoc` — a bookmark, an ingress rule, a README, a smoke
test — needs updating to the new route.

---

## 9. Troubleshooting

| Symptom | Cause |
|---|---|
| `GET /rapidoc` → 404 | RapiDoc does not exist in Kora 2.0. Enable `scalar` and use `/scalar` |
| `GET /scalar` → 404 | `scalar.enabled` is `false` (the default), or `path` was changed |
| Viewer loads but shows no document | `openapi.management.enabled` is `false`, so the raw-spec route is unregistered |
| Viewer loads but the document 404s | Wrong classpath path in `files`; the response body names the path it tried |
| Two entries with the same title | Duplicate basenames in `files` |
| `IllegalStateException: Scalar file doesn't contain ${scalarSources} placeholder` | The bundled page was replaced or corrupted — restore the stock `openapi-management` jar |
| 404 `Scalar file not found` | `kora/openapi/management/scalar/index.page` is missing from the classpath, e.g. a shaded jar dropped it, or a native image without the module's `resource-config.json` |
| Interceptor gating `/scalar` never runs | `@Tag(HttpServerModule.class)` instead of `@Tag(HttpServer.class)` |

---

## Related references

- [swagger-ui-reference.md](swagger-ui-reference.md) — the other bundled viewer, its `options` map and OAuth2 redirect
- [openapi-spec-reference.md](openapi-spec-reference.md) — spec placement, multi-spec layouts, validation
- Code generation: [`kora-openapi-generator-server`](../../kora-openapi-generator-server/SKILL.md)
