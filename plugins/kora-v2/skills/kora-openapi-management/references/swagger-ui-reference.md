# Swagger UI Reference — Kora 2.0

**Verified against** the Kora 2.0 framework source for `2.0.0.RC2`
(`openapi/openapi-management/src/main/java/io/koraframework/openapi/management/`: `OpenApiManagementConfig`,
`OpenApiManagementModule`, `SwaggerUIHttpServerHandler`, `SwaggerOauthHttpServerHandler`), its tests
(`OpenApiTests`), and the migrated guide apps `kora-java-guide-openapi-http-server-app` /
`kora-kotlin-guide-openapi-http-server-app` on `kora-examples` branch `migration/2.0`.

## Contents

1. What the module gives you
2. Setup
3. Configuration keys
4. The `options` map
5. `withCredentials`
6. OAuth2 redirect
7. How the UI finds the spec
8. Response caching
9. Securing the UI
10. Troubleshooting

---

## 1. What the module gives you

`OpenApiManagementModule` contributes four `HttpServerRequestHandler` components:

| Handler | Route | Enabled by |
|---|---|---|
| `OpenApiHttpServerHandler` | `{path}` or `{path}/{file}` | `enabled` |
| `SwaggerUIHttpServerHandler` | `{swaggerui.path}` | `swaggerui.enabled` |
| `SwaggerOauthHttpServerHandler` | `{swaggerui.path}/oauth2-redirect` | `swaggerui.enabled` |
| `ScalarHttpServerHandler` | `{scalar.path}` | `scalar.enabled` |

A disabled handler is skipped by `HttpServerRouter` entirely, so its route is not registered and a
request to it falls through to the normal 404.

The handlers carry no tag, so they land on the **public** Undertow server
(`UndertowPublicHttpServerModule`, `httpServer.port`). The system server's handlers all carry
`@SystemApi`, so the docs never appear on `httpServer.system.port`.

The Swagger UI distribution is inlined into a single ≈1.9 MB page shipped inside the jar. There is
no CDN request and no version to pin.

---

## 2. Setup

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

### Minimal

```hocon
openapi {
  management {
    enabled = true
    files = ["openapi/api.yaml"]
    swaggerui {
      enabled = true
    }
  }
}
```

- `GET /swagger-ui` — the UI
- `GET /openapi` — the raw spec (single file ⇒ served directly at `path`)

**`enabled = true` is not optional when you want the UI to work.** The UI page always fetches the
raw-spec route; with `enabled = false` that route does not exist and Swagger UI renders
*Failed to load API definition*.

### Custom paths

```hocon
openapi {
  management {
    enabled = true
    files = ["openapi/api-v1.yaml", "openapi/api-v2.yaml"]
    path = "/api/spec"
    swaggerui {
      enabled = true
      path = "/api/docs"
    }
  }
}
```

| Route | Serves |
|---|---|
| `GET /api/docs` | Swagger UI with a spec selector |
| `GET /api/docs/oauth2-redirect` | OAuth2 redirect page |
| `GET /api/spec/api-v1` | `openapi/api-v1.yaml` |
| `GET /api/spec/api-v2` | `openapi/api-v2.yaml` |

### Complete key set under `openapi.management.swaggerui`

| Key | Type | Default |
|---|---|---|
| `enabled` | `boolean` | `false` |
| `path` | `String` | `/swagger-ui` |
| `withCredentials` | `boolean` | `true` |
| `cache` | `NONE` \| `GZIP` \| `FULL` | `GZIP` |
| `options` | `Map<String,String>` | 7 entries, see §4 |

There is no `endpoint` key — that was the Kora 1.x name for `path`, and an unknown HOCON key is
ignored without any diagnostic. There is no `rapidoc` sibling either; the second bundled viewer is
`scalar` — see [scalar-reference.md](scalar-reference.md).

`swaggerui` is one lowercase token. Kora matches config keys leniently only across
camelCase / kebab-case / snake_case forms of the *same* words, so `swaggerUi` and `swagger-ui`
are different keys and are silently ignored.

The whole `swaggerui` block may be omitted; a missing object maps to an all-defaults instance,
which leaves the UI off.

---

## 4. The `options` map

`swaggerui.options` is injected verbatim into the `SwaggerUIBundle({...})` call in the page, after
the fixed `dom_id`, `presets`, `plugins` and `withCredentials` entries. It is the escape hatch for
any Swagger UI init option Kora does not model.

Default map:

| Option | Default value |
|---|---|
| `layout` | `StandaloneLayout` |
| `validatorUrl` | `null` |
| `defaultModelsExpandDepth` | `0` |
| `deepLinking` | `true` |
| `persistAuthorization` | `true` |
| `displayOperationId` | `true` |
| `filter` | `true` |

### Setting `options` replaces the default map

The default applies only when the key is **absent**. A HOCON `options { … }` object is mapped as a
whole, so this:

```hocon
swaggerui {
  enabled = true
  options { filter = "false" }
}
```

produces a UI with `layout` unset (Swagger UI's own `BaseLayout` default), no deep linking, no
persisted authorization and no operation ids. Repeat every entry you intend to keep:

```hocon
swaggerui {
  enabled = true
  options {
    layout = "StandaloneLayout"
    validatorUrl = "null"
    defaultModelsExpandDepth = "0"
    deepLinking = "true"
    persistAuthorization = "true"
    displayOperationId = "true"
    filter = "false"
  }
}
```

### Values are HOCON strings, emitted as JS literals

The map is `Map<String,String>`, so every value is quoted in config. The handler then decides
whether to emit it as a raw JS literal or as a JS string:

| Trimmed value | Emitted as |
|---|---|
| `null`, `true`, `false` | the bare JS literal |
| a number (`0`, `-1`, `2.5`) | the bare number |
| starts with `{` or `[` | raw JS object / array |
| starts with `function` or `(` | raw JS function |
| empty | `""` |
| anything else | a quoted, escaped JS string |

So `validatorUrl = "null"` disables the validator (emits `"validatorUrl": null`) while
`validatorUrl = "https://validator.example.com"` emits a quoted URL. Advanced values work the same
way:

```hocon
options {
  syntaxHighlight = "{ activated: false }"
  onComplete      = "() => window.swaggerReady = true"
}
```

Because the value is inserted into the page as written, treat it as code: never build it from
untrusted input.

---

## 5. `withCredentials`

`withCredentials` defaults to **`true`**, which emits both `withCredentials: true` and a
`requestInterceptor` that sets `request.credentials = "include"` on every try-it-out call — so
cookies are sent cross-origin. Set it to `false` when the UI is served from a different origin than
the API and you do not want ambient credentials attached:

```hocon
swaggerui {
  enabled = true
  withCredentials = false
}
```

---

## 6. OAuth2 redirect

When `swaggerui.enabled = true`, the module also registers
`GET {swaggerui.path}/oauth2-redirect`, serving Swagger UI's standard `oauth2-redirect.html`
page. The page computes its own `oauth2RedirectUrl` from the browser location, so a UI reachable at
`/api/docs` gets `/api/docs/oauth2-redirect` with no extra configuration.

Register that exact URL as the redirect URI in your identity provider. Nothing else needs to be
configured on the Kora side; the OAuth flows themselves come from the `securitySchemes` in your
spec.

---

## 7. How the UI finds the spec

The page does not hard-code an absolute URL. It takes the current browser URL, strips any `#…`
fragment, and string-replaces `swaggerui.path` with `path`:

- one file ⇒ `url: <current URL with /swagger-ui → /openapi>`
- several files ⇒ `urls: [ { url: …/openapi/api-v1, name: "api-v1" }, … ]`, which is what renders
  the spec selector

Consequences worth knowing:

- It works unchanged behind a reverse proxy that adds a path prefix, because the prefix survives
  the replacement.
- `path` and `swaggerui.path` should be siblings at the same depth. Nesting the UI under the spec
  path (`path = "/openapi"`, `swaggerui.path = "/openapi/ui"`) makes the replacement produce a
  wrong URL.
- The names in the selector are the stripped basenames of `files`, so duplicate basenames produce
  duplicate entries pointing at the same route.

---

## 8. Response caching

`swaggerui.cache` controls how the rendered page is cached, using the same three-mode cache as the
raw specs:

| Mode | Behaviour |
|---|---|
| `NONE` | the page is re-rendered (and re-gzipped) on every request |
| `GZIP` *(default)* | the gzipped page is rendered once and reused; non-gzip clients re-render |
| `FULL` | both the gzipped and the plain page are cached |

Every response carries `Vary: Accept-Encoding`. A client that sends `Accept-Encoding: gzip;q=0`
gets the uncompressed page.

Rendering the page means splicing ~1.9 MB of inlined assets, so leave the default unless you have a
reason not to.

---

## 9. Securing the UI

### Option 1 — turn it off

```hocon
# production override
openapi.management.swaggerui.enabled = false
openapi.management.scalar.enabled = false
```

The raw spec stays available for tooling. Add `openapi.management.enabled = false` to remove that
as well. An environment-driven toggle works too:

```hocon
openapi.management.swaggerui.enabled = false
openapi.management.swaggerui.enabled = ${?SWAGGER_UI_ENABLED}
```

### Option 2 — a global interceptor

The docs handlers are produced by the module, so there is no method of yours to annotate with
`@InterceptWith`. Register one `HttpServerInterceptor` as a `@Component` tagged
`@Tag(HttpServer.class)`; `publicHttpApiRouter` collects interceptors by exactly that tag and runs
them on every routed request, including the module's.

```java
import io.koraframework.common.annotation.Component;
import io.koraframework.common.annotation.Tag;
import io.koraframework.http.common.body.HttpBody;
import io.koraframework.http.server.common.HttpServer;
import io.koraframework.http.server.common.interceptor.HttpServerInterceptor;
import io.koraframework.http.server.common.request.HttpServerRequest;
import io.koraframework.http.server.common.response.HttpServerResponse;

@Tag(HttpServer.class)
@Component
public final class DocsSecurityInterceptor implements HttpServerInterceptor {

    @Override
    public HttpServerResponse intercept(HttpServerRequest request, InterceptChain chain) throws Exception {
        var path = request.path();
        if (path.startsWith("/swagger-ui") || path.startsWith("/scalar") || path.startsWith("/openapi")) {
            if (request.headers().getFirst("Authorization") == null) {
                return HttpServerResponse.of(401, HttpBody.plaintext("Unauthorized"));
            }
        }
        return chain.process(request);
    }
}
```

The contract is synchronous — `HttpServerResponse intercept(HttpServerRequest, InterceptChain)`.
There is no `Context` parameter and no `CompletionStage`; both were removed in Kora 2.0.

**`@Tag(HttpServerModule.class)` compiles and does nothing.** `HttpServerModule` is still a type in
`io.koraframework.http.server.common`, so the annotation is legal, but no injection point claims
that tag — the component is never collected and the docs stay open. Assert the 401 in a test rather
than trusting the annotation.

A ready-to-copy version with token comparison lives in
[`../assets/SwaggerUiSecurityInterceptor.java.template`](../assets/SwaggerUiSecurityInterceptor.java.template)
and [`../assets/SwaggerUiSecurityInterceptor.kt.template`](../assets/SwaggerUiSecurityInterceptor.kt.template).

---

## 10. Troubleshooting

| Symptom | Cause |
|---|---|
| Startup fails with `…null after parsing at path: 'ROOT.openapi.management.files'` | `files` missing or written as the 1.x `file`. Mandatory even when everything is disabled |
| `GET /swagger-ui` → 404 | `swaggerui.enabled` is `false`, or the block is spelled `swaggerUi` / `swagger-ui` |
| UI renders but *Failed to load API definition* | `openapi.management.enabled` is `false`, so the spec route is unregistered |
| UI renders but the spec is 404 | Wrong classpath path in `files`; the response body names the path it tried |
| Spec route is on `/openapi` though you configured something else | You used the 1.x `endpoint` key instead of `path` |
| Options you did not touch reverted to Swagger UI defaults | Setting `options` replaces the whole default map |
| A JS option arrives as a quoted string | It did not match a raw-literal shape — see the table in §4 |
| Try-it-out sends no cookies | `withCredentials = false` |
| Interceptor gating the docs never runs | `@Tag(HttpServerModule.class)` instead of `@Tag(HttpServer.class)` |
| Only one of two specs is reachable | The two `files` entries share a basename |

---

## Related references

- [scalar-reference.md](scalar-reference.md) — the second bundled viewer (replaces RapiDoc)
- [openapi-spec-reference.md](openapi-spec-reference.md) — spec placement, multi-spec layouts, validation
- Code generation: [`kora-openapi-generator-server`](../../kora-openapi-generator-server/SKILL.md)
