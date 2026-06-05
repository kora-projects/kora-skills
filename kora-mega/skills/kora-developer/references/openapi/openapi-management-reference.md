# OpenAPI Management Reference

**Source:** [.kora-agent/kora-docs/mkdocs/docs/en/documentation/openapi-management.md](.kora-agent/kora-docs/mkdocs/docs/en/documentation/openapi-management.md)  
**Examples:** `.kora-agent/kora-examples/kora-java-openapi-generator-http-server/`

## 1. Overview

The `openapi-management` module provides:
- Access to OpenAPI files from the application
- Swagger UI for API documentation visualization (**recommended**)
- Rapidoc as an alternative documentation viewer

**Recommendation:** Use **Swagger UI** — the most mature and stable solution with full support for all OpenAPI features. Rapidoc is available as an alternative but may have limitations with complex specifications (discriminators, oneOf/anyOf).

**Requires:** HTTP server module (e.g., `http-server-undertow`).

## 2. Dependency

===! ":fontawesome-brands-java: `Java`"

    ```groovy
    dependencies {
        implementation "ru.tinkoff.kora:openapi-management"
    }
    ```

    Module:
    ```java
    @KoraApp
    public interface Application extends OpenApiManagementModule { }
    ```

=== ":simple-kotlin: `Kotlin`"

    ```kotlin
    dependencies {
        implementation("ru.tinkoff.kora:openapi-management")
    }
    ```

    Module:
    ```kotlin
    @KoraApp
    interface Application : OpenApiManagementModule
    ```

## 3. Configuration

### Full Configuration Example

```hocon
openapi {
    management {
        file = ["openapi/petstore.yaml", "openapi/shop.yaml"]  // (1)!
        enabled = true  // (2)!
        endpoint = "/openapi"  // (3)!
        swaggerui {
            enabled = true  // (4)! Recommended to use Swagger UI
            endpoint = "/swagger-ui"  // (5)!
        }
        rapidoc {
            enabled = false  // (6)! Not recommended, use only as an alternative
            endpoint = "/rapidoc"  // (7)!
        }
    }
}
```

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `file` | List[String] | - | Relative path to OpenAPI files in `resources` |
| `enabled` | Boolean | `true` | Enable/disable the OpenAPI controller |
| `endpoint` | String | `/openapi` | Path for accessing OpenAPI files |
| `swaggerui.enabled` | Boolean | `true` | Enable Swagger UI (**recommended**) |
| `swaggerui.endpoint` | String | `/swagger-ui` | Path for Swagger UI |
| `rapidoc.enabled` | Boolean | `false` | Enable Rapidoc (not recommended) |
| `rapidoc.endpoint` | String | `/rapidoc` | Path for Rapidoc |

### Single File Configuration

When a single file is specified:
```hocon
openapi {
    management {
        file = ["openapi/petstore.yaml"]
        endpoint = "/api/openapi"
    }
}
```
The file will be available at: `GET /api/openapi`

### Multiple Files Configuration

When multiple files are specified:
```hocon
openapi {
    management {
        file = ["openapi/petstore.yaml", "openapi/shop.yaml"]
        endpoint = "/api/openapi"
    }
}
```
Files will be available at:
- `GET /api/openapi/petstore.yaml`
- `GET /api/openapi/shop.yaml`

## 4. Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET {endpoint}/{filename}` | Access to an OpenAPI file |
| `GET {swaggerui.endpoint}` | Swagger UI interface |
| `GET {rapidoc.endpoint}` | Rapidoc interface |

### Example URLs

For the configuration:
```hocon
openapi {
    management {
        file = ["openapi/petstore.yaml"]
        endpoint = "/api/openapi"
        swaggerui {
            enabled = true
            endpoint = "/api/docs"
        }
        rapidoc {
            enabled = false  # Not recommended
        }
    }
}
```

Available URLs:
- OpenAPI spec: `GET /api/openapi/petstore.yaml`
- Swagger UI: `GET /api/docs`

## 5. Integration with OpenAPI Generator

When used with `openapi-codegen`:

**build.gradle:**
```groovy
dependencies {
    implementation "ru.tinkoff.kora:openapi-management"
    implementation "ru.tinkoff.kora:http-server-undertow"
}

def openApiGenerate = tasks.register("openApiGenerate", GenerateTask) {
    generatorName = "kora"
    inputSpec = "$projectDir/src/main/resources/openapi/petstore.yaml"
    outputDir = "$buildDir/generated/pet-api-server"
    configOptions = [
        mode: "java-server"
    ]
}

// Copy generated OpenAPI spec to resources
tasks.register('copyOpenApi', Copy) {
    from "$projectDir/src/main/resources/openapi/petstore.yaml"
    into "$buildDir/resources/main/openapi/"
    dependsOn openApiGenerate
    mustRunAfter processResources
}
```

**application.conf:**
```hocon
openapi {
    management {
        file = ["openapi/petstore.yaml"]
        enabled = true
        endpoint = "/api/openapi"
        swaggerui {
            enabled = true
            endpoint = "/api/docs"
        }
    }
}
```

## 6. Troubleshooting

| Problem | Solution |
|---------|----------|
| Swagger UI not accessible | Check `openapi.management.swaggerui.enabled = true` |
| OpenAPI file not found | Ensure the file is located under `src/main/resources/openapi/` |
| 404 on endpoint | Verify the `endpoint` value in the configuration |
| Multiple files not working | Each file requires a separate path entry in `file` |

## 7. Best Practices

1. **Development vs Production:**
   ```hocon
   openapi {
       management {
           enabled = ${OPENAPI_ENABLED:true}  // Can be disabled in prod
           swaggerui {
               enabled = ${SWAGGER_UI_ENABLED:true}  // Enable only in dev
           }
       }
   }
   ```

2. **Security:** Restrict access to Swagger UI in production via HTTP server interceptors

3. **Multiple APIs:** Group related APIs into a single file; keep unrelated APIs in separate files

---

## Related References

- [openapi-codegen-reference.md](openapi-codegen-reference.md) — OpenAPI Generator configuration
- [authorization-reference.md](authorization-reference.md) — Authorization for servers
- [interceptors-reference.md](interceptors-reference.md) — Interceptors for access control
