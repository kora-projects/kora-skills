# OpenAPI Authorization Reference

**Source:** [.kora-agent/kora-docs/mkdocs/docs/en/documentation/openapi-codegen.md](.kora-agent/kora-docs/mkdocs/docs/en/documentation/openapi-codegen.md)  
**Examples:** `.kora-agent/kora-examples/kora-java-openapi-generator-http-server/`

## 1. Overview

Kora OpenAPI Generator supports multiple authentication mechanisms defined in OpenAPI `securitySchemes`. Generated server code uses `HttpServerPrincipalExtractor` to extract and validate credentials.

**Important:** Custom Principal class must implement `ru.tinkoff.kora.common.Principal` interface.

## 2. Supported Authentication Types

| Type | OpenAPI `securitySchemes` | Extractor Tag |
|------|---------------------------|---------------|
| Bearer Token | `type: http, scheme: bearer` | `ApiSecurity.BearerAuth.class` |
| API Key | `type: apiKey` | `ApiSecurity.ApiKeyAuth.class` |
| Basic Auth | `type: http, scheme: basic` | `ApiSecurity.BasicAuth.class` |
| OAuth 2.0 | `type: oauth2` | `ApiSecurity.OAuth2.class` |

## 3. Bearer Authentication

### OpenAPI Specification

```yaml
components:
  securitySchemes:
    bearerAuth:
      type: http
      scheme: bearer
      bearerFormat: JWT
```

### Principal Implementation

```java
public final class UserPrincipal implements ru.tinkoff.kora.common.Principal {
    private final String name;

    public UserPrincipal(String name) {
        this.name = name;
    }

    public String getName() {
        return name;
    }
}
```

### Extractor Implementation

```java
@Module
public interface AuthModule {
    @Tag(ApiSecurity.BearerAuth.class)
    default HttpServerPrincipalExtractor<Principal> bearerHttpServerPrincipalExtractor() {
        return (request, value) -> CompletableFuture.completedFuture(
            new UserPrincipal("user-123")
        );
    }
}
```

### Usage in Delegate

```java
@Component
public final class PetApiDelegate implements PetApiDelegate {
    @Override
    public PetApiResponses.GetPetByIdApiResponse getPetById(long petId, Principal principal) {
        // principal contains extracted bearer token
        return new PetApiResponses.GetPetByIdApiResponse.GetPetById200ApiResponse(
            petService.findById(petId)
        );
    }
}
```

## 4. API Key Authentication

### OpenAPI Specification

```yaml
components:
  securitySchemes:
    apiKeyAuth:
      type: apiKey
      in: header
      name: X-API-Key
```

### Extractor Implementation

```java
@Module
public interface AuthModule {
    @Tag(ApiSecurity.ApiKeyAuth.class)
    default HttpServerPrincipalExtractor<Principal> apiKeyHttpServerPrincipalExtractor() {
        return (request, value) -> CompletableFuture.completedFuture(
            new UserPrincipal("api-key-user")  // value contains API key
        );
    }
}
```

## 5. Basic Authentication

### OpenAPI Specification

```yaml
components:
  securitySchemes:
    basicAuth:
      type: http
      scheme: basic
```

### Extractor Implementation

```java
@Module
public interface AuthModule {
    @Tag(ApiSecurity.BasicAuth.class)
    default HttpServerPrincipalExtractor<Principal> basicHttpServerPrincipalExtractor() {
        return (request, value) -> {
            // Parse Basic auth header: "Basic base64(username:password)"
            String authHeader = request.headers().getFirst("Authorization");
            String credentials = authHeader.substring("Basic ".length());
            String decoded = new String(Base64.getDecoder().decode(credentials), StandardCharsets.UTF_8);
            String[] parts = decoded.split(":");
            String username = parts[0];
            String password = parts[1];
            // Validate credentials and return Principal
            return CompletableFuture.completedFuture(new UserPrincipal(username));
        };
    }
}
```

## 6. OAuth 2.0

### OpenAPI Specification

```yaml
components:
  securitySchemes:
    oauth2:
      type: oauth2
      flows:
        authorizationCode:
          authorizationUrl: https://example.com/oauth/authorize
          tokenUrl: https://example.com/oauth/token
          scopes:
            read:pets: Read pet information
            write:pets: Write pet information
```

### Extractor Implementation

```java
@Module
public interface AuthModule {
    @Tag(ApiSecurity.OAuth2.class)
    default HttpServerPrincipalExtractor<Principal> oauth2HttpServerPrincipalExtractor() {
        return (request, value) -> {
            // Validate OAuth2 token and extract scopes
            return CompletableFuture.completedFuture(
                new UserPrincipal("oauth-user")
            );
        };
    }
}
```

## 7. Multiple Authentication Schemes

When OpenAPI spec defines multiple `securitySchemes`, configure `primaryAuth`:

```groovy
configOptions = [
    mode: "java-server",
    primaryAuth: "bearerAuth"  // Primary authentication mechanism
]
```

### Allow Multiple Authentication

To generate interceptors for all authentication mechanisms:

```groovy
configOptions = [
    mode: "java-server",
    authAllowMultiple: "true"
]
```

## 8. Security Configuration

### Security Config Prefix

For Basic/ApiKey authentication, configure credentials via config:

```groovy
configOptions = [
    securityConfigPrefix: "auth"
]
```

```hocon
auth {
    apiKey = ${API_KEY}
    basicUsername = ${BASIC_USERNAME}
    basicPassword = ${BASIC_PASSWORD}
}
```

### Auth as Method Argument

Pass authentication as method argument instead of using interceptors:

```groovy
configOptions = [
    authAsMethodArgument: "true"
]
```

Generated delegate signature:
```java
public PetApiResponses.GetPetByIdApiResponse getPetById(long petId, Principal principal)
```

## 9. Principal Class Pattern

```java
import ru.tinkoff.kora.common.Principal;

public final class UserPrincipal implements Principal {
    private final String userId;
    private final String token;
    private final List<String> scopes;

    // Bearer token constructor
    public UserPrincipal(String token) {
        this.token = token;
        this.userId = extractUserId(token);
        this.scopes = List.of();
    }

    // OAuth2 constructor with scopes
    public UserPrincipal(String token, List<String> scopes) {
        this.token = token;
        this.userId = extractUserId(token);
        this.scopes = scopes;
    }

    private String extractUserId(String token) {
        // JWT decoding logic
        return "user-123";
    }

    public String getUserId() { return userId; }
    public String getToken() { return token; }
    public List<String> getScopes() { return scopes; }
}
```

## 10. Troubleshooting

| Problem | Solution |
|---------|----------|
| `HttpServerPrincipalExtractor` not found | Add `http-server-undertow` dependency |
| Multiple extractors for same type | Use `@Tag(ApiSecurity.*.class)` to distinguish |
| Auth not passed to delegate | Set `authAsMethodArgument: "true"` |
| Security scheme not recognized | Check `securitySchemes` name matches `primaryAuth` |
| Principal type mismatch | Ensure Principal implements `ru.tinkoff.kora.common.Principal` |

---

## Related References

- [openapi-codegen-reference.md](openapi-codegen-reference.md) — OpenAPI Generator configuration
- [interceptors-reference.md](interceptors-reference.md) — Interceptors for clients and servers
- [validation-reference.md](validation-reference.md) — Server-side validation
