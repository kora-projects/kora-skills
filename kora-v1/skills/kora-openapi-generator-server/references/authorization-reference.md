# OpenAPI Server Authorization Reference

**Source:** [openapi-codegen.md](../../../.kora-agent/kora-docs/mkdocs/docs/en/documentation/openapi-codegen.md) (Authorization section)
**Example:** `.kora-agent/kora-examples/examples/java/kora-java-openapi-generator-http-server/`

## Contents

- [1. How It Works](#1-how-it-works)
- [2. Security Scheme to Tag Mapping](#2-security-scheme-to-tag-mapping)
- [3. The Principal Type](#3-the-principal-type)
- [4. Extractors in the Application](#4-extractors-in-the-application)
- [5. Per-Scheme Examples](#5-per-scheme-examples)
- [6. Multiple Schemes](#6-multiple-schemes)
- [7. Notes and Pitfalls](#7-notes-and-pitfalls)
- [8. Related](#8-related)

---

## 1. How It Works

When the OpenAPI contract declares `securitySchemes` and a `security` requirement,
the `kora` server generator emits:

- a generated `ApiSecurity` class in your **`apiPackage`** (e.g.
  `com.example.api.ApiSecurity`) with one nested marker class per scheme
  (`ApiSecurity.BearerAuth`, `ApiSecurity.BasicAuth`, `ApiSecurity.ApiKeyAuth`,
  `ApiSecurity.OAuth`),
- generated controller code that, before calling the delegate, resolves a
  `Principal` for the request using an `HttpServerPrincipalExtractor` tagged with
  the matching `ApiSecurity.*` class.

You supply each extractor as a tagged component (typically a `default` method in
`@KoraApp` or in a `@Module`). The generator handles invoking it; you do not add
auth annotations to the delegate.

---

## 2. Security Scheme to Tag Mapping

The tag class name comes from the **scheme name in the contract**, not a fixed
list. For the example petstore contract:

```yaml
components:
  securitySchemes:
    bearerAuth:   { type: http,   scheme: bearer, bearerFormat: JWT }
    apiKeyAuth:   { type: apiKey, in: header, name: X-API-KEY }
    basicAuth:    { type: http,   scheme: basic }
    oAuth:        { type: oauth2, flows: { ... } }
security:
  - bearerAuth: []
  - apiKeyAuth: []
  - basicAuth: []
  - oAuth: [ ... ]
```

| Scheme (`securitySchemes` key) | Generated tag |
|--------------------------------|---------------|
| `bearerAuth` | `ApiSecurity.BearerAuth.class` |
| `apiKeyAuth` | `ApiSecurity.ApiKeyAuth.class` |
| `basicAuth` | `ApiSecurity.BasicAuth.class` |
| `oAuth` | `ApiSecurity.OAuth.class` |

Import `ApiSecurity` from your configured `apiPackage`, e.g.
`import com.example.api.ApiSecurity;`.

---

## 3. The Principal Type

A principal implements `ru.tinkoff.kora.common.Principal`. To carry OAuth-style
scopes, implement `ru.tinkoff.kora.http.common.auth.PrincipalWithScopes`
(`PrincipalWithScopes` extends `Principal` and adds `scopes()`):

```java
package com.example.auth;

import java.util.Collection;
import java.util.List;
import ru.tinkoff.kora.http.common.auth.PrincipalWithScopes;

public record UserPrincipal(String name) implements PrincipalWithScopes {

    @Override
    public Collection<String> scopes() {
        return List.of("read", "write");
    }
}
```

For schemes without scopes, implementing plain `ru.tinkoff.kora.common.Principal`
is enough.

---

## 4. Extractors in the Application

An `HttpServerPrincipalExtractor<P>` receives the request and the raw credential
value, and returns a `CompletableFuture<P>`. Declare one per scheme, tagged with
the matching `ApiSecurity.*` class. This mirrors the example's `Application`:

```java
@KoraApp
public interface Application extends
        HoconConfigModule,
        LogbackModule,
        ValidationModule,
        JsonModule,
        UndertowHttpServerModule {

    static void main(String[] args) {
        KoraApplication.run(ApplicationGraph::graph);
    }

    @Tag(ApiSecurity.BearerAuth.class)
    default HttpServerPrincipalExtractor<Principal> bearerHttpServerPrincipalExtractor() {
        return (request, value) ->
            CompletableFuture.completedFuture(new UserPrincipal("name"));
    }

    @Tag(ApiSecurity.BasicAuth.class)
    default HttpServerPrincipalExtractor<Principal> basicHttpServerPrincipalExtractor() {
        return (request, value) ->
            CompletableFuture.completedFuture(new UserPrincipal("name"));
    }

    @Tag(ApiSecurity.ApiKeyAuth.class)
    default HttpServerPrincipalExtractor<Principal> apiKeyHttpServerPrincipalExtractor() {
        return (request, value) ->
            CompletableFuture.completedFuture(new UserPrincipal("name"));
    }

    @Tag(ApiSecurity.OAuth.class)
    default HttpServerPrincipalExtractor<PrincipalWithScopes> oauthHttpServerPrincipalExtractor() {
        return (request, value) ->
            CompletableFuture.completedFuture(new UserPrincipal("name"));
    }
}
```

Imports used above:

```java
import java.util.concurrent.CompletableFuture;
import ru.tinkoff.kora.common.Principal;
import ru.tinkoff.kora.common.Tag;
import ru.tinkoff.kora.http.common.auth.PrincipalWithScopes;
import ru.tinkoff.kora.http.server.common.auth.HttpServerPrincipalExtractor;
import com.example.api.ApiSecurity;   // generated into your apiPackage
```

Kotlin form:

```kotlin
@Module
interface AuthModule {

    @Tag(ApiSecurity.BearerAuth::class)
    fun bearerHttpServerPrincipalExtractor(): HttpServerPrincipalExtractor<Principal> =
        HttpServerPrincipalExtractor { request, value ->
            CompletableFuture.completedFuture(UserPrincipal("name"))
        }
}
```

---

## 5. Per-Scheme Examples

### Bearer (JWT)

```yaml
components:
  securitySchemes:
    bearerAuth:
      type: http
      scheme: bearer
      bearerFormat: JWT
security:
  - bearerAuth: []
```

```java
@Tag(ApiSecurity.BearerAuth.class)
default HttpServerPrincipalExtractor<Principal> bearerHttpServerPrincipalExtractor(
        JwtTokenValidator validator) {
    return (request, value) -> {
        // value is the raw Authorization header value
        if (value == null) {
            return CompletableFuture.completedFuture(null);
        }
        var claims = validator.validate(value);
        return CompletableFuture.completedFuture(new UserPrincipal(claims.subject()));
    };
}
```

### API Key

```yaml
components:
  securitySchemes:
    apiKeyAuth:
      type: apiKey
      in: header
      name: X-API-KEY
```

```java
@Tag(ApiSecurity.ApiKeyAuth.class)
default HttpServerPrincipalExtractor<Principal> apiKeyHttpServerPrincipalExtractor(
        ApiKeyRepository keys) {
    return (request, value) ->
        keys.find(value)
            .<Principal>map(k -> new UserPrincipal(k.owner()))
            .map(CompletableFuture::completedFuture)
            .orElseGet(() -> CompletableFuture.completedFuture(null));
}
```

### Basic

```yaml
components:
  securitySchemes:
    basicAuth:
      type: http
      scheme: basic
```

```java
@Tag(ApiSecurity.BasicAuth.class)
default HttpServerPrincipalExtractor<Principal> basicHttpServerPrincipalExtractor(
        UserRepository users) {
    return (request, value) -> {
        // value is the raw "Basic <base64>" header value
        return CompletableFuture.completedFuture(new UserPrincipal("name"));
    };
}
```

### OAuth (scopes)

```yaml
components:
  securitySchemes:
    oAuth:
      type: oauth2
      flows:
        authorizationCode:
          authorizationUrl: https://auth.example.com/authorize
          tokenUrl: https://auth.example.com/token
          scopes:
            read: Read access
            write: Write access
security:
  - oAuth: [ read, write ]
```

```java
@Tag(ApiSecurity.OAuth.class)
default HttpServerPrincipalExtractor<PrincipalWithScopes> oauthHttpServerPrincipalExtractor() {
    return (request, value) ->
        CompletableFuture.completedFuture(new UserPrincipal("name"));
}
```

When a `security` requirement lists scopes (`oAuth: [ read, write ]`), the
generated controller checks that the resolved `PrincipalWithScopes.scopes()`
covers the required scopes for the operation.

---

## 6. Multiple Schemes

If the contract lists several schemes under `security`, declare one extractor per
scheme, each with its own `ApiSecurity.*` tag (as in section 4). The generator
wires each scheme to its tagged extractor.

---

## 7. Notes and Pitfalls

- **`ApiSecurity` lives in your `apiPackage`**, not in a Kora framework package.
  Import it from there (`com.example.api.ApiSecurity`).
- **Tag class names follow the scheme names** in the contract. A scheme named
  `oAuth` yields `ApiSecurity.OAuth`, not `OAuth2`.
- **Return `null`/`CompletableFuture.completedFuture(null)`** from an extractor to
  signal that authentication did not succeed; the generated controller turns that
  into the appropriate unauthorized response.
- **Use `PrincipalWithScopes`** only when you need scope checks; otherwise plain
  `Principal` is sufficient.
- The extractor is the auth boundary. Keep business authorization in services; do
  not add framework auth annotations to the generated delegate.

---

## 8. Related

- [OpenAPI Codegen Reference](openapi-codegen-reference.md)
- [OpenAPI Codegen doc — Authorization](../../../.kora-agent/kora-docs/mkdocs/docs/en/documentation/openapi-codegen.md)
- [HTTP Server](../../../.kora-agent/kora-docs/mkdocs/docs/en/documentation/http-server.md)
