---
name: kora-http-server-auth
description: "HTTP server authentication and authorization in Kora. Covers HttpServerPrincipalExtractor<T> wired to OpenAPI-generated ApiSecurity markers (BearerAuth/BasicAuth/ApiKeyAuth/OAuth) via @Tag, the Principal / PrincipalWithScopes marker interfaces, SecurityException-to-403 mapping through an HttpServerInterceptor, and the manual HttpServerInterceptor + HttpServerRequestMapper path for non-OpenAPI auth. Use when securing @HttpController/@HttpRoute endpoints, validating Bearer/JWT/API-key/Basic credentials, integrating an OpenAPI security scheme, or returning 401/403 from a Kora HTTP server."
---

# Kora HTTP Server Auth

Authenticate and authorize Kora HTTP server endpoints. Kora has no `@Secured`-style
annotation and no thread-local "current user". Authentication is implemented in one of
two ways:

- **OpenAPI-driven** (preferred when you generate the server from a contract):
  implement `HttpServerPrincipalExtractor<P>` and bind it with `@Tag(ApiSecurity.<Scheme>.class)`.
  The generated controller invokes the matching extractor before your delegate runs.
- **Manual** (no OpenAPI contract): an `HttpServerInterceptor` validates credentials and
  short-circuits, and/or an `HttpServerRequestMapper<P>` turns the request into a typed
  argument injected via `@Mapping`.

All Kora artifacts inherit the version from the `kora-parent` BOM (`1.2.17` in
`.kora-agent/kora-examples`). Never pin individual `ru.tinkoff.kora:*` versions.

---

## Quick Start (OpenAPI security)

### 1. Dependencies

```groovy
dependencies {
    koraBom platform("ru.tinkoff.kora:kora-parent:1.2.17")
    annotationProcessor "ru.tinkoff.kora:annotation-processors" // mandatory: generates the graph + controllers

    implementation "ru.tinkoff.kora:http-server-undertow"
    implementation "ru.tinkoff.kora:json-module"
    implementation "ru.tinkoff.kora:config-hocon"
    implementation "ru.tinkoff.kora:logging-logback"
}
```

The OpenAPI `kora` generator produces the `ApiSecurity` class (one nested marker per
`securityScheme`) from the contract's `components.securitySchemes`. See
[kora-openapi-generator-server](../kora-openapi-generator-server/SKILL.md) for the
generator wiring.

### 2. Declare the security scheme in the contract

```yaml
security:
    -   apiKeyAuth: [ ]            # apply globally to every operation

components:
    securitySchemes:
        apiKeyAuth:
            type: apiKey
            in: header
            name: Authorization
```

Generation emits `ApiSecurity.ApiKeyAuth` (and `BearerAuth`, `BasicAuth`, `OAuth` for
the corresponding scheme types).

### 3. Define a Principal

`Principal` is the framework marker interface `ru.tinkoff.kora.common.Principal`.
Implement it on your own record.

```java
import ru.tinkoff.kora.common.Principal;

public record DataApiPrincipal(String name) implements Principal {}
```

### 4. Bind the extractor with @Tag(ApiSecurity.<Scheme>.class)

Declare the extractor as a `default` method on `@KoraApp` (or on a `@Module` interface).
The lambda receives the `HttpServerRequest` and the raw credential `value` parsed from
the scheme's header. Throw `SecurityException` to reject; the generated transport wraps
the returned `CompletionStage`.

```java
import java.util.concurrent.CompletableFuture;
import ru.tinkoff.kora.common.Principal;
import ru.tinkoff.kora.common.Tag;
import ru.tinkoff.kora.http.server.common.auth.HttpServerPrincipalExtractor;

@Tag(ApiSecurity.ApiKeyAuth.class)
default HttpServerPrincipalExtractor<Principal> apiKeyHttpServerPrincipalExtractor(DataApiAuthConfig config) {
    return (request, value) -> {
        if (value == null || !config.value().equals(value)) {
            throw new SecurityException("Invalid API key");
        }
        return CompletableFuture.completedFuture(new DataApiPrincipal("data-api-client"));
    };
}
```

Externalize the expected secret via `@ConfigSource`:

```java
import ru.tinkoff.kora.config.common.annotation.ConfigSource;

@ConfigSource("auth.apiKey")
public interface DataApiAuthConfig {
    String value();
}
```

```hocon
auth { apiKey { value = ${API_KEY} } }
```

### 5. Map SecurityException to 403

Kora does not translate `SecurityException` to an HTTP status automatically. Register an
error-handling `HttpServerInterceptor` (tag with `@Tag(HttpServerModule.class)` to apply
to every controller).

```java
import ru.tinkoff.kora.common.Component;
import ru.tinkoff.kora.common.Context;
import ru.tinkoff.kora.common.Tag;
import ru.tinkoff.kora.http.common.body.HttpBody;
import ru.tinkoff.kora.http.server.common.HttpServerInterceptor;
import ru.tinkoff.kora.http.server.common.HttpServerModule;
import ru.tinkoff.kora.http.server.common.HttpServerRequest;
import ru.tinkoff.kora.http.server.common.HttpServerResponse;
import ru.tinkoff.kora.http.server.common.HttpServerResponseException;

import java.util.concurrent.CompletionException;
import java.util.concurrent.CompletionStage;

@Tag(HttpServerModule.class)
@Component
public final class AuthErrorInterceptor implements HttpServerInterceptor {

    @Override
    public CompletionStage<HttpServerResponse> intercept(Context context, HttpServerRequest request, InterceptChain chain)
            throws Exception {
        return chain.process(context, request).exceptionally(throwable -> {
            var cause = (throwable instanceof CompletionException && throwable.getCause() != null)
                    ? throwable.getCause() : throwable;
            if (cause instanceof HttpServerResponseException ex) {
                return ex;
            }
            if (cause instanceof SecurityException) {
                var msg = cause.getMessage() != null ? cause.getMessage() : "Access denied";
                return HttpServerResponse.of(403, HttpBody.plaintext(msg));
            }
            return HttpServerResponse.of(500, HttpBody.plaintext("Internal error"));
        });
    }
}
```

---

## What's in this skill

| File | Purpose |
|------|---------|
| [references/openapi-security-reference.md](references/openapi-security-reference.md) | `HttpServerPrincipalExtractor` + `ApiSecurity` markers for Bearer/Basic/API-Key/OAuth, `PrincipalWithScopes`, scope checks. |
| [references/manual-auth-reference.md](references/manual-auth-reference.md) | Non-OpenAPI auth: `HttpServerInterceptor`, `HttpServerRequestMapper` + `@Mapping`, header parsing, 401/403 responses. |
| `assets/ApiKeyExtractor.java.template` / `.kt.template` | API-key `HttpServerPrincipalExtractor` skeleton. |
| `assets/BasicAuthExtractor.java.template` / `.kt.template` | HTTP Basic `HttpServerPrincipalExtractor` skeleton. |
| [assets/README.md](assets/README.md) | How to copy and wire the templates. |
| `evals/evals.json` | Behavioral evals for this skill. |

---

## Auth scheme reference

| Scheme | OpenAPI `type`/`scheme` | Header (typical) | `@Tag` marker | `value` passed to extractor |
|--------|-------------------------|------------------|---------------|------------------------------|
| **Bearer / JWT** | `http` / `bearer` | `Authorization: Bearer <token>` | `ApiSecurity.BearerAuth.class` | the credential after the scheme prefix |
| **API Key** | `apiKey` (`in: header`) | the header named in the scheme | `ApiSecurity.ApiKeyAuth.class` | the header value |
| **Basic** | `http` / `basic` | `Authorization: Basic <base64>` | `ApiSecurity.BasicAuth.class` | the credential after the scheme prefix |
| **OAuth (scopes)** | `oauth2` | `Authorization: Bearer <token>` | `ApiSecurity.OAuth.class` | the credential after the scheme prefix |

For OAuth, return a `PrincipalWithScopes` so the generated transport can enforce the
operation's required scopes:

```java
import ru.tinkoff.kora.http.common.auth.PrincipalWithScopes;

public record UserPrincipal(String name) implements PrincipalWithScopes {
    @Override public java.util.Collection<String> scopes() { return java.util.List.of("read", "write"); }
}

@Tag(ApiSecurity.OAuth.class)
default HttpServerPrincipalExtractor<PrincipalWithScopes> oauthHttpServerPrincipalExtractor() {
    return (request, value) -> CompletableFuture.completedFuture(new UserPrincipal("name"));
}
```

---

## Key principles

1. **`Principal` is `ru.tinkoff.kora.common.Principal`** — a framework marker interface.
   Your principal record must `implements Principal`. Do not define a local `Principal`.
2. **One extractor per scheme, bound by `@Tag(ApiSecurity.<Scheme>.class)`** — the
   generated controller picks the extractor matching the operation's security requirement.
3. **Reject by throwing `SecurityException`** (or completing the future exceptionally).
   There is no `Principal.current()` and no request-attribute bag — the principal flows
   through the generated transport, not a thread-local.
4. **Map auth failures to HTTP codes yourself** via an `HttpServerInterceptor`:
   401 = authentication failed (bad/missing credentials), 403 = authorization failed
   (missing role/scope).
5. **`PrincipalWithScopes` for OAuth scope enforcement** — the only built-in
   authorization hook; richer role checks live in your delegate or interceptor.
6. **Externalize secrets with `@ConfigSource`** and `${ENV}` substitution — never inline
   keys/passwords.

---

## Manual auth (no OpenAPI)

When there is no generated `ApiSecurity`, validate credentials in an
`HttpServerInterceptor` and/or derive a typed principal with an
`HttpServerRequestMapper` injected via `@Mapping`. Full patterns:
[references/manual-auth-reference.md](references/manual-auth-reference.md).

```java
import ru.tinkoff.kora.common.Mapping;
import ru.tinkoff.kora.http.common.HttpMethod;
import ru.tinkoff.kora.http.server.common.HttpServerRequest;
import ru.tinkoff.kora.http.server.common.HttpServerRequestMapper;

public record CallerContext(String userId) {}

public static final class CallerMapper implements HttpServerRequestMapper<CallerContext> {
    @Override public CallerContext apply(HttpServerRequest request) {
        var userId = request.headers().getFirst("x-user-id");
        if (userId == null) {
            throw new SecurityException("Missing x-user-id");
        }
        return new CallerContext(userId);
    }
}

@HttpRoute(method = HttpMethod.GET, path = "/me")
public String me(@Mapping(CallerMapper.class) CallerContext caller) {
    return caller.userId();
}
```

---

## Common pitfalls

| Symptom | Cause | Fix |
|---------|-------|-----|
| `cannot find symbol: method current()` on `Principal` | `Principal.current()` does not exist in Kora | Receive the principal through the generated delegate, or derive it with `HttpServerRequestMapper` + `@Mapping`. |
| `cannot find symbol: getAttribute` on `HttpServerRequest` | Kora has no request-attribute bag | Read headers via `request.headers().getFirst(...)`; pass data as a typed `@Mapping` argument. |
| Extractor never runs | Missing/wrong `@Tag(ApiSecurity.<Scheme>.class)`, or the operation has no `security` requirement | Add `security:` in the contract and tag the extractor with the matching marker. |
| `SecurityException` surfaces as HTTP 500 | No error interceptor mapping it | Add an `HttpServerInterceptor` tagged `@Tag(HttpServerModule.class)` that maps `SecurityException` to 403. |
| `Required dependency not found: ...PrincipalExtractor` | Extractor not declared as a graph component | Add the `default` extractor method to `@KoraApp` or a `@Module` the app extends. |
| OAuth scopes not enforced | Returning a plain `Principal` | Return a `PrincipalWithScopes` so the transport can check the operation's scopes. |

---

## Related skills

- [kora-http-server](../kora-http-server/SKILL.md) — controllers, routes, interceptors, error handling
- [kora-openapi-generator-server](../kora-openapi-generator-server/SKILL.md) — generates `ApiSecurity` markers and delegates
- [kora-http-client-auth](../kora-http-client-auth/SKILL.md) — outbound credential interceptors
- [kora-config-hocon](../kora-config-hocon/SKILL.md) — `@ConfigSource` for secrets
- [kora-json](../kora-json/SKILL.md) — JWT claim DTO serialization
