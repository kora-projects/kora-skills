# RapiDoc Reference

**Source:** `.kora-agent/kora-docs/mkdocs/docs/en/documentation/openapi-management.md`

## Contents

1. Overview
2. Quick Setup
3. Configuration
4. Configuration Parameters
5. Known Limitations
6. Comparison: Swagger UI vs RapiDoc
7. Troubleshooting
8. When to Switch to Swagger UI

## 1. Overview

RapiDoc is an alternative OpenAPI documentation viewer. **Not recommended** for complex specs due to limited support for advanced OpenAPI features.

**When to use:**
- Simple APIs without discriminators
- Preference for RapiDoc's UI style
- Testing/development only

**When NOT to use:**
- Complex specs with `oneOf`/`anyOf`
- Polymorphic schemas with discriminators
- Production APIs with intricate type hierarchies

## 2. Quick Setup

===! ":fontawesome-brands-java: `Java`"

    ```groovy
    dependencies {
        implementation "ru.tinkoff.kora:openapi-management"
        implementation "ru.tinkoff.kora:http-server-undertow"
    }
    ```

    ```java
    @KoraApp
    public interface Application extends OpenApiManagementModule { }
    ```

=== ":simple-kotlin: `Kotlin`"

    ```kotlin
    dependencies {
        implementation("ru.tinkoff.kora:openapi-management")
        implementation("ru.tinkoff.kora:http-server-undertow")
    }
    ```

    ```kotlin
    @KoraApp
    interface Application : OpenApiManagementModule
    ```

## 3. Configuration

### Minimal Configuration

```hocon
openapi {
    management {
        file = ["openapi/api.yaml"]
        rapidoc {
            enabled = true
            endpoint = "/rapidoc"
        }
    }
}
```

**Endpoints:**
- `GET /rapidoc` — RapiDoc UI
- `GET /openapi` — Raw spec (single file served directly at `endpoint`)

### Full Configuration

```hocon
openapi {
    management {
        file = ["openapi/api.yaml"]
        enabled = true
        endpoint = "/api/spec"
        rapidoc {
            enabled = true
            endpoint = "/api/docs"
        }
    }
}
```

## 4. Configuration Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `file` | `List[String]` | — | Paths to OpenAPI specs |
| `enabled` | `Boolean` | `false` | Enable the raw-spec endpoints |
| `endpoint` | `String` | `/openapi` | Base path for raw specs |
| `rapidoc.enabled` | `Boolean` | `false` | Enable RapiDoc |
| `rapidoc.endpoint` | `String` | `/rapidoc` | RapiDoc path |

## 5. Known Limitations

RapiDoc has **limited support** for:

| Feature | Support | Notes |
|---------|---------|-------|
| `oneOf` | Partial | May not render correctly |
| `anyOf` | Partial | Limited validation |
| `discriminator` | Limited | Polymorphic types may break |
| Complex `$ref` chains | Partial | Deep nesting issues |

### Example: Discriminator Issues

```yaml
components:
  schemas:
    Task:
      oneOf:
        - $ref: '#/components/schemas/TaskUnconfirmed'
        - $ref: '#/components/schemas/TaskConfirmed'
      discriminator:
        propertyName: migrationType
```

**RapiDoc:** May not correctly show the discriminator dropdown.
**Swagger UI:** Full support.

## 6. Comparison: Swagger UI vs RapiDoc

| Feature | Swagger UI | RapiDoc |
|---------|------------|---------|
| Complex spec support | Full | Partial |
| Discriminator support | Yes | Limited |
| oneOf/anyOf | Full | Partial |
| Maturity | High | Medium |
| **Recommendation** | Production | Dev/Test only |

## 7. Troubleshooting

| Problem | Solution |
|---------|----------|
| RapiDoc shows empty | Verify spec at `/openapi/{file}` |
| Missing discriminator dropdown | Switch to Swagger UI |
| oneOf not rendering | Use Swagger UI for complex types |
| 404 on `/rapidoc` | Check `rapidoc.enabled = true` |

## 8. When to Switch to Swagger UI

Switch if your spec has:
- Polymorphic types with discriminators
- Complex `oneOf`/`anyOf` hierarchies
- Production API documentation needs

```hocon
# Switch to Swagger UI
openapi {
    management {
        rapidoc {
            enabled = false
        }
        swaggerui {
            enabled = true  # Recommended
        }
    }
}
```

---

## Related References

- [swagger-ui-reference.md](swagger-ui-reference.md) — Swagger UI (recommended)
- [openapi-spec-reference.md](openapi-spec-reference.md) — Spec publishing
