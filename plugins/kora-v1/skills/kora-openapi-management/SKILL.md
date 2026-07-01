---
name: kora-openapi-management
description: "Serves OpenAPI specification files plus Swagger UI and RapiDoc viewers over the Kora HTTP server via the OpenApiManagementModule (ru.tinkoff.kora:openapi-management). Use when exposing an OpenAPI document at an /openapi endpoint, enabling a /swagger-ui or /rapidoc UI, publishing multiple spec versions with a selector, or gating documentation endpoints in production. Config lives under openapi.management (file, enabled, endpoint, swaggerui, rapidoc), all toggles default to false. Not for code generation from a spec (kora-openapi-generator-server / kora-openapi-generator-client)."
---

# Kora OpenAPI Management

**Focus:** Publish OpenAPI documents and serve interactive viewers (Swagger UI, RapiDoc) over the Kora HTTP server using `OpenApiManagementModule`.

## When to Use This Skill

Use when you need to:
- **Serve OpenAPI documents** at an HTTP endpoint (single file at `endpoint`, or `endpoint/{name}` per file when several are listed)
- **Enable Swagger UI** for interactive API documentation (`/swagger-ui`)
- **Enable RapiDoc** as an alternative viewer (`/rapidoc`)
- **Expose multiple specs** (v1/v2, public/internal/admin) with a selector
- **Control documentation visibility** (enabled in dev, disabled or gated in prod)

**Not for:** Code generation from OpenAPI specs — use `kora-openapi-generator-server` (server delegates) or `kora-openapi-generator-client` (typed clients).

The canonical end-to-end walkthrough (generate + publish) is the guide `.kora-agent/kora-docs/mkdocs/docs/en/guides/openapi-http-server.md`.

---

## Quick Start

### 1. Add Dependencies

All Kora artifacts inherit their version from the `kora-parent` BOM — never pin a `ru.tinkoff.kora:*` version directly.

```groovy
dependencies {
    koraBom platform("ru.tinkoff.kora:kora-parent:$koraVersion")
    annotationProcessor "ru.tinkoff.kora:annotation-processors"

    implementation "ru.tinkoff.kora:openapi-management"
    implementation "ru.tinkoff.kora:http-server-undertow" // required HTTP server
}
```

(Kotlin: `ksp "ru.tinkoff.kora:symbol-processors"` instead of `annotationProcessor`.)

### 2. Enable the Module

Add `OpenApiManagementModule` to the `@KoraApp` graph alongside the HTTP server and config modules.

```java
@KoraApp
public interface Application extends
        HoconConfigModule,
        UndertowHttpServerModule,
        OpenApiManagementModule {

    static void main(String[] args) {
        KoraApplication.run(ApplicationGraph::graph);
    }
}
```

`KoraApplication` is imported from `ru.tinkoff.kora.application.graph.KoraApplication`.

### 3. Place OpenAPI Specs

```
src/main/resources/
└── openapi/
    ├── api-v1.yaml
    └── api-v2.yaml
```

### 4. Configure

Every toggle defaults to `false`, so each one you want must be set explicitly.

```hocon
openapi {
  management {
    file = ["openapi/api-v1.yaml", "openapi/api-v2.yaml"]
    enabled = true
    endpoint = "/openapi"
    swaggerui {
      enabled = true
      endpoint = "/swagger-ui"
    }
  }
}
```

**Result:**
| Endpoint | Description |
|----------|-------------|
| `GET /swagger-ui` | Interactive UI with spec selector |
| `GET /openapi/api-v1` | v1 spec (filename without directory/extension) |
| `GET /openapi/api-v2` | v2 spec |

The OpenAPI controllers run on the **public** HTTP server (`httpServer.publicApiHttpPort`), not the private/management port.

---

## Configuration Reference

### Full Configuration

```hocon
openapi {
  management {
    file = ["openapi/api-v1.yaml", "openapi/api-v2.yaml"]
    enabled = true                    # serve raw specs (default: false)
    endpoint = "/openapi"             # base path for specs (default: /openapi)

    swaggerui {
      enabled = true                  # Swagger UI (default: false), recommended viewer
      endpoint = "/swagger-ui"        # UI path (default: /swagger-ui)
    }

    rapidoc {
      enabled = false                 # RapiDoc (default: false), limited on complex specs
      endpoint = "/rapidoc"           # UI path (default: /rapidoc)
    }
  }
}
```

### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `file` | `List[String]` | — | Spec file paths, relative to `resources` |
| `enabled` | `Boolean` | `false` | Enable the raw-spec endpoints |
| `endpoint` | `String` | `/openapi` | Base path for specs |
| `swaggerui.enabled` | `Boolean` | `false` | Enable Swagger UI |
| `swaggerui.endpoint` | `String` | `/swagger-ui` | Swagger UI path |
| `rapidoc.enabled` | `Boolean` | `false` | Enable RapiDoc |
| `rapidoc.endpoint` | `String` | `/rapidoc` | RapiDoc path |

### Endpoint behavior: single vs multiple files

- **Single file** in `file`: `GET {endpoint}` returns the file content directly.
- **Multiple files**: `endpoint` becomes a prefix and each spec is served at `{endpoint}/{name}`, where `{name}` is the filename without directories or extension. For `someDir/api-v1.yaml` the path is `{endpoint}/api-v1`.

```hocon
openapi {
  management {
    file = ["openapi/petstore.yaml"]   # single file
    enabled = true
    endpoint = "/api/openapi"
  }
}
```

Result: `GET /api/openapi` returns the spec content.

---

## References

Detailed guides in `references/`:

| Document | Description |
|----------|-------------|
| [swagger-ui-reference.md](references/swagger-ui-reference.md) | Swagger UI config, security, troubleshooting |
| [rapidoc-reference.md](references/rapidoc-reference.md) | RapiDoc config, limitations, when to avoid |
| [openapi-spec-reference.md](references/openapi-spec-reference.md) | Spec publishing, versioning strategies, validation |

---

## Best Practices

1. **Use Swagger UI** — full support for complex specs (discriminators, oneOf/anyOf); prefer it over RapiDoc.
2. **Toggles default to `false`** — set `enabled`, `swaggerui.enabled` (and `rapidoc.enabled`) explicitly; nothing is served otherwise.
3. **Disable or gate the UI in production** — keep specs for tooling, hide or protect the UI:
   ```hocon
   # application-prod.conf override
   openapi.management.swaggerui.enabled = false
   ```
   To keep the UI but require auth, gate it with an `HttpServerInterceptor` — see [swagger-ui-reference.md](references/swagger-ui-reference.md).
4. **Contract-first** — generate code and serve the *same* spec file so docs never drift; the spec is the source of truth.
5. **Group related APIs** — one file per audience (public/internal/admin), listed in `file`.
6. **Validate specs** — run `python scripts/validate_openapi.py` before deployment.

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| Swagger UI returns 404 | Set `swaggerui.enabled = true` (default is `false`) |
| Raw spec returns 404 | Set `enabled = true`; check `endpoint` and that the file is listed in `file` |
| Spec not found at build | Path is relative to `src/main/resources/`; the file must be on the classpath |
| Empty Swagger UI | Verify the spec is valid YAML/JSON and has a `paths` section |
| RapiDoc broken with complex specs | Switch to Swagger UI |
| Multiple specs not showing | Each spec needs its own entry in the `file` list |
| `OpenApiManagementModule` not found | Add `implementation "ru.tinkoff.kora:openapi-management"` and `extends OpenApiManagementModule` |

---

## Assets

Templates in `assets/` (English comments, BOM-pinned versions):

| Template | Description |
|----------|-------------|
| `openapi-spec.yaml.template` | Example OpenAPI 3.x spec with discriminator patterns |
| `build.gradle.server.template` | Gradle config: `openapi-management` + `org.openapi.generator` codegen |
| `Application.server.java.template` / `.kt.template` | `@KoraApp` module wiring `OpenApiManagementModule` |
| `application.conf.template` | Base HOCON config for management endpoints |
| `application.dev.conf.template` / `application.prod.conf.template` | Per-environment overrides |
| `SwaggerUiSecurityInterceptor.java.template` / `.kt.template` | `HttpServerInterceptor` gating the docs endpoints |

See [assets/README.md](assets/README.md) for usage.

---

## Related Skills

- **kora-openapi-generator-server** — generate server delegates from OpenAPI
- **kora-openapi-generator-client** — generate typed HTTP clients
- **kora-http-server** — HTTP server configuration, controllers, interceptors
