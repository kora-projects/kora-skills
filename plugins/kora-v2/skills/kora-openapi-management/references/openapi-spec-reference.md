# OpenAPI Spec Reference

**Source:** `.kora-agent/kora-docs/mkdocs/docs/en/documentation/openapi-management.md`, `.kora-agent/kora-docs/mkdocs/docs/en/guides/openapi-http-server.md`

## Contents

1. Overview
2. File Placement
3. Configuration
4. Versioning Strategies
5. Spec Organization
6. Integration with Codegen
7. Spec Validation
8. Best Practices
9. Troubleshooting

## 1. Overview

OpenAPI spec publishing: file placement, versioning strategies, and multi-spec management.

**Module:** `openapi-management`
**Requires:** HTTP server module (e.g., `http-server-undertow`)

## 2. File Placement

OpenAPI specs go in `src/main/resources/openapi/`:

```
src/main/resources/
└── openapi/
    ├── api-v1.yaml        # Version 1
    ├── api-v2.yaml        # Version 2
    ├── api-public.yaml    # External API
    ├── api-internal.yaml  # Internal API
    └── api-admin.yaml     # Admin/ops API
```

### Supported Formats

- **YAML** (recommended): `.yaml`, `.yml`
- **JSON**: `.json`

## 3. Configuration

### Single Spec

```hocon
openapi {
    management {
        file = ["openapi/api.yaml"]
        endpoint = "/api/openapi"
    }
}
```

**Endpoint:** `GET /api/openapi`

### Multiple Specs

```hocon
openapi {
    management {
        file = [
            "openapi/api-v1.yaml",
            "openapi/api-v2.yaml",
            "openapi/api-internal.yaml"
        ]
        endpoint = "/openapi"
    }
}
```

**Endpoints** (filename without directory or extension):
- `GET /openapi/api-v1`
- `GET /openapi/api-v2`
- `GET /openapi/api-internal`

### Configuration Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `file` | `List[String]` | — | Spec file paths (relative to resources) |
| `enabled` | `Boolean` | `false` | Enable the raw-spec endpoints |
| `endpoint` | `String` | `/openapi` | Base path for raw specs |

### Endpoint Behavior

**Single file:**
```hocon
openapi.management.file = ["openapi/api.yaml"]
```
- `GET /openapi` — returns spec content directly

**Multiple files:**
```hocon
openapi.management.file = ["openapi/api-v1.yaml", "openapi/api-v2.yaml"]
```
- `GET /openapi/api-v1` — returns first spec (filename without extension)
- `GET /openapi/api-v2` — returns second spec

**Files in subdirectories:**
```hocon
openapi.management.file = ["openapi/v1/api.yaml", "openapi/v2/api.yaml"]
```
- `GET /openapi/api` — directory path is stripped, only filename used

## 4. Versioning Strategies

### Strategy 1: Separate Files (Recommended)

Each version in its own file:

```
openapi/
├── api-v1.yaml    # Legacy /users
├── api-v2.yaml    # New /v2/users
└── api-v3.yaml    # Latest /v3/users
```

```hocon
openapi.management.file = [
    "openapi/api-v1.yaml",
    "openapi/api-v2.yaml",
    "openapi/api-v3.yaml"
]
```

**Pros:**
- Clear separation
- Easy deprecation
- Independent evolution

**Cons:**
- More files to maintain

### Strategy 2: Path-Based Versioning

Single spec with versioned paths:

```yaml
paths:
  /api/v1/users:
    get:
      operationId: getUsersV1
  /api/v2/users:
    get:
      operationId: getUsersV2
  /api/v3/users:
    get:
      operationId: getUsersV3
```

**Pros:**
- Single source of truth
- Easy to see all versions

**Cons:**
- Spec can become large
- Harder to deprecate

### Strategy 3: Audience-Based Separation

Group by API audience:

```
openapi/
├── api-public.yaml    # External partners
├── api-internal.yaml  # Microservice communication
└── api-admin.yaml     # Operations/admin
```

```hocon
openapi.management.file = [
    "openapi/api-public.yaml",
    "openapi/api-internal.yaml",
    "openapi/api-admin.yaml"
]
```

**Use with tags:**
```yaml
tags:
  - name: public
    description: Public API
  - name: internal
    description: Internal only

paths:
  /users:
    get:
      tags: [public]
  /admin/cache/clear:
    get:
      tags: [internal]
```

## 5. Spec Organization

### Recommended Structure

```
src/main/resources/openapi/
├── api.yaml           # Main spec
└── common/
    ├── schemas.yaml   # Reusable schemas
    ├── parameters.yaml # Reusable parameters
    └── responses.yaml  # Reusable responses
```

### Using $ref for Includes

```yaml
# api.yaml
components:
  schemas:
    User:
      $ref: './common/schemas.yaml#/User'
    Error:
      $ref: './common/schemas.yaml#/Error'

paths:
  /users:
    get:
      parameters:
        - $ref: './common/parameters.yaml#/limit'
```

## 6. Integration with Codegen

The contract-first pattern serves the *same* spec file that drives code generation, so documentation never drifts from the generated transport layer.

Keep the spec under `src/main/resources/openapi/` (it is already on the classpath, so `openapi-management` can read it directly — no copy task needed). Point both the generator's `inputSpec` and `openapi.management.file` at it.

```groovy
import org.openapitools.generator.gradle.plugin.tasks.GenerateTask

def openApiGenerate = tasks.register("openApiGenerate", GenerateTask) {
    generatorName = "kora"
    group = "openapi tools"
    inputSpec = "$projectDir/src/main/resources/openapi/my-api.yaml"
    outputDir = "$buildDir/generated/openapi"
    def corePackage = "com.example.myapi"
    apiPackage = "${corePackage}.api"
    modelPackage = "${corePackage}.model"
    invokerPackage = "${corePackage}.invoker"
    configOptions = [
        mode: "java-server",
        enableServerValidation: "true",
    ]
}
sourceSets.main { java.srcDirs += openApiGenerate.get().outputDir }
compileJava.dependsOn openApiGenerate
```

```hocon
openapi {
    management {
        file = ["openapi/my-api.yaml"]
        enabled = true
        swaggerui.enabled = true
    }
}
```

See the `kora-openapi-generator-server` skill for full generation options.

## 7. Spec Validation

Use the validation script before deployment:

```bash
# Basic validation
python scripts/validate_openapi.py --spec src/main/resources/openapi/api.yaml

# Strict mode (warnings = errors)
python scripts/validate_openapi.py --spec src/main/resources/openapi/api.yaml --strict

# JSON output for CI
python scripts/validate_openapi.py --spec src/main/resources/openapi/api.yaml --json
```

### External Tools

```bash
# swagger-cli
npx @apidevtools/swagger-cli validate src/main/resources/openapi/api.yaml

# spectral
npx spectral lint src/main/resources/openapi/api.yaml
```

## 8. Best Practices

### File Naming

```
api-v1.yaml          # Versioned API
api-public.yaml      # Audience-based
petstore.yaml        # Domain-based
```

### Spec Content

1. **Required fields:** `openapi`, `info.title`, `info.version`, `paths`
2. **Operation IDs:** Required for codegen (`operationId`)
3. **Responses:** Define at least one response per operation
4. **Schemas:** Use `components/schemas` for reusability

### Security

- Keep internal specs separate from public
- Consider disabling `swaggerui` in production
- Use environment variables for toggle:

```hocon
openapi {
    management {
        enabled = ${OPENAPI_ENABLED:true}
        swaggerui {
            enabled = ${SWAGGER_UI_ENABLED:true}
        }
    }
}
```

## 9. Troubleshooting

| Problem | Solution |
|---------|----------|
| Spec not found | Path is relative to `src/main/resources/` |
| 404 on endpoint | Check `endpoint` config, verify file in `file` list |
| Multiple specs not working | Each needs separate `file` entry |
| Empty response | Validate spec has `paths` section |

---

## Related References

- [swagger-ui-reference.md](swagger-ui-reference.md) — Swagger UI
- [rapidoc-reference.md](rapidoc-reference.md) — RapiDoc
- Code generation: see the `kora-openapi-generator-server` skill, or the doc `.kora-agent/kora-docs/mkdocs/docs/en/documentation/openapi-codegen.md`
