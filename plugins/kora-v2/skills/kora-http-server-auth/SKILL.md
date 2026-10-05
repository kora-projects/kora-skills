---
name: kora-http-server-auth
description: "HTTP server authentication in Kora 2.0 — HttpServerPrincipalExtractor<T, P> bound by @Tag(ApiSecurity.<SchemeName>.class), io.koraframework.common.Principal carried to the handler through Principal.with/Principal.current (a ScopedValue), PrincipalWithScopes for oauth2 scopes, and HttpServerResponseException for 401/403. Use when securing @HttpController endpoints, wiring an OpenAPI securityScheme, writing a global @Tag(HttpServer.class) auth interceptor, or fixing auth that silently stopped running after a Kora 1.x migration."
license: Apache-2.0
metadata:
  kora-version: "2.x"
---

# Kora HTTP Server Auth

> **Kora sub-skill — obey the [kora-v2 meta rules](../../SKILL.md) on every task:** **R0** ground the workspace on Kora 2.0 refs before starting (framework source at tag `2.0.0.RC2` + `kora-examples` at `migration/2.0` + Kora 2.0 docs at koraframework.io/v2, which trail the source; 1.x `kora-docs` pages are never an authority) · **R1** read this sub-skill before writing code · **R2** Kora 2.0 APIs only — no Spring/Micronaut/Quarkus, no Kora 1.x APIs, no invented annotations or config keys · **R3** journal any incorrect Kora usage. Add comments/Javadoc only if asked.

| | |
|---|---|
| **Artifacts** | `io.koraframework:http-server-undertow` (BOM `io.koraframework:kora-bom`, version `2.0.0.RC2`) |
| **Extractor** | `io.koraframework.http.server.common.auth.HttpServerPrincipalExtractor<T, P extends Principal>` |
| **Principal** | `io.koraframework.common.Principal` · `io.koraframework.http.common.auth.PrincipalWithScopes` |
| **Interceptor** | `io.koraframework.http.server.common.interceptor.HttpServerInterceptor` |
| **Global tag** | `@Tag(io.koraframework.http.server.common.HttpServer.class)` |
| **Errors** | `io.koraframework.http.server.common.response.HttpServerResponseException` |

Kora has no `@Secured`-style annotation. Authentication is either **contract-driven** — the OpenAPI
generator emits the whole interceptor and you supply one `HttpServerPrincipalExtractor` per security
scheme — or **manual**, a hand-written `HttpServerInterceptor`. Both end the same way: the
authenticated `Principal` is published with `Principal.with(...)` and read inside the handler with
`Principal.current()`.

---

## What changed from Kora 1.x — read this before porting auth code

| 1.x | 2.0 | Why it matters |
|---|---|---|
| `HttpServerPrincipalExtractor<P>` | **`HttpServerPrincipalExtractor<T, P extends Principal>`** | Two type parameters. `T` is the credential the scheme yields, `P` the principal. A one-argument form does not compile. |
| `CompletionStage<P>` result | **`@Nullable P extract(HttpServerRequest, @Nullable T)`** | Synchronous. No `CompletableFuture`, no `Mono`, no `suspend`. |
| Throw `SecurityException` to reject | **Return `null` to reject** | `SecurityException` occurs **nowhere** in the Kora 2.0 source. Returning `null` is the contract the generated interceptor checks. |
| `Context` carries request state | **`Context` does not exist in 2.0** | The principal travels in a `ScopedValue`: `Principal.with(p, op)` / `Principal.current()`. |
| `Principal.current()` did not exist | **`Principal.current()` is the documented accessor** | The 1.x advice "there is no current-user accessor" is now wrong. |
| `intercept(Context, request, chain)` | **`HttpServerResponse intercept(HttpServerRequest, InterceptChain)`** | Throws `Exception`; returns the response directly. |
| `@Tag(HttpServerModule.class)` for a global interceptor | **`@Tag(HttpServer.class)`** | `HttpServerModule` still exists, so the old tag **compiles and silently never runs** — authentication disappears with no error. See [pitfalls](#pitfalls). |
| `ApiSecurity.SecurityRequirementTag1` | **`ApiSecurity.<SchemeName>`** | Tags are named after the security-scheme name. Ordinal forms are gone. |
| `ru.tinkoff.kora.*` | `io.koraframework.*` | Whole framework. |

---

## Quick start — OpenAPI security scheme

### 1. Declare the scheme in the contract

```yaml
security:
  - apiKeyAuth: []            # applies to every operation

components:
  securitySchemes:
    apiKeyAuth:
      type: apiKey
      in: header
      name: X-API-KEY
```

### 2. What the generator emits

The `kora` generator writes an `ApiSecurity` interface into your api package. It is annotated
`@Module`, so the Kora processor picks it up automatically — **do not add it to your `@KoraApp`
interface list**. For the contract above it contains:

- a marker class `ApiSecurity.ApiKeyAuth` — the tag,
- an interceptor `ApiSecurity.ApiKeyAuthHttpServerInterceptor` that reads the header, calls your
  extractor, publishes the principal and throws `401` when nothing authenticated,
- a `@DefaultComponent` factory whose only parameter is the extractor **you** must provide:

```java
@Tag(ApiKeyAuth.class)
@DefaultComponent
default ApiKeyAuthHttpServerInterceptor ApiKeyAuthHttpServerInterceptor(
    @Tag(ApiKeyAuth.class) HttpServerPrincipalExtractor<String, Principal> ApiKeyAuth_) { … }
```

That parameter type is the exact signature your extractor must have. See
[references/openapi-security-reference.md](references/openapi-security-reference.md) for the full
generated shape, the tag-naming rule, and the AND/OR/anonymous variants.

### 3. Define a Principal

```java
import io.koraframework.common.Principal;

public record DataApiPrincipal(String clientId) implements Principal {}
```

### 4. Supply the extractor

```java
import io.koraframework.common.Principal;
import io.koraframework.common.annotation.Tag;
import io.koraframework.http.server.common.auth.HttpServerPrincipalExtractor;

@Tag(ApiSecurity.ApiKeyAuth.class)
default HttpServerPrincipalExtractor<String, Principal> apiKeyHttpServerPrincipalExtractor(
        DataApiAuthConfig config) {
    return (request, value) -> {
        if (value == null || !config.value().equals(value)) {
            return null;               // → generated interceptor throws 401 Unauthorized
        }
        return new DataApiPrincipal("data-api-client");
    };
}
```

Kotlin — the SAM parameter is nullable, and so is the result:

```kotlin
@Tag(ApiSecurity.ApiKeyAuth::class)
fun apiKeyHttpServerPrincipalExtractor(
    config: DataApiAuthConfig
): HttpServerPrincipalExtractor<String, Principal> =
    HttpServerPrincipalExtractor { _, value ->
        if (value == null || config.value() != value) null
        else DataApiPrincipal("data-api-client")
    }
```

Externalize the secret — never inline it:

```java
@ConfigSource("auth.apiKey")
public interface DataApiAuthConfig { String value(); }
```

```hocon
auth { apiKey { value = ${API_KEY} } }
```

### 5. Read the principal in the handler

```java
import io.koraframework.common.Principal;

var principal = (DataApiPrincipal) Principal.current();   // null when the route is anonymous
```

`Principal.current()` reads a `ScopedValue` bound by the interceptor for the duration of the
request. It is `@Nullable`, and it is **not** visible on threads you start yourself.

---

## Rejecting a request

`extract` returning `null` is the only rejection signal the generated interceptor understands.

| You want | Do this |
|---|---|
| Plain `401 Unauthorized` | `return null` — the generated interceptor throws it for you |
| A specific status/message/body | `throw HttpServerResponseException.of(401, "Token expired")` — it *is* an `HttpServerResponse` and Undertow sends it verbatim |
| `403` for a missing OAuth2 scope declared in the contract | nothing — the generated interceptor answers `403 Forbidden` when the extractor authenticated the caller but a required scope is absent |
| `403` for any other right (roles, ownership) | `throw HttpServerResponseException.of(403, "…")` from the delegate, after `Principal.current()` |
| A JSON error body for every auth failure | a **global** `@Tag(HttpServer.class)` interceptor — see below |

**Do not throw `SecurityException`.** The string `SecurityException` appears in no Kora 2.0 source
file. An uncaught one reaches the Undertow handler, which turns any non-`HttpServerResponse`
throwable into **500** with the exception message as the plaintext body — leaking internals while
looking like a server bug.

---

## Global interceptors

```java
import io.koraframework.common.annotation.Component;
import io.koraframework.common.annotation.Tag;
import io.koraframework.http.server.common.HttpServer;
import io.koraframework.http.server.common.interceptor.HttpServerInterceptor;

@Tag(HttpServer.class)      // NOT HttpServerModule.class
@Component
public final class AuthErrorInterceptor implements HttpServerInterceptor {

    @Override
    public HttpServerResponse intercept(HttpServerRequest request, InterceptChain chain) throws Exception {
        try {
            return chain.process(request);
        } catch (HttpServerResponseException e) {
            return jsonError(e.code(), e.getMessage());
        }
    }
    …
}
```

`HttpServerModule` collects them as `@Tag(HttpServer.class) All<HttpServerInterceptor>`, so:

- **many** global interceptors are allowed (1.x's "only one" no longer applies);
- they are sorted by **simple class name**, and the chain is wound so the **alphabetically last name
  runs outermost**;
- they wrap everything, including the generated security interceptor — this is the only place that
  can reshape the generated `401`.

The OpenAPI `interceptors` generator option puts your interceptor *inside* the security interceptor,
so it cannot see the `401` the latter throws. Use `@Tag(HttpServer.class)` for that.

---

## Manual auth (no OpenAPI contract)

Mirror what the generator does: validate, then publish the principal.

```java
@Component
public final class ApiKeyInterceptor implements HttpServerInterceptor {

    private final AuthConfig config;

    public ApiKeyInterceptor(AuthConfig config) { this.config = config; }

    @Override
    public HttpServerResponse intercept(HttpServerRequest request, InterceptChain chain) throws Exception {
        var key = request.headers().getFirst("x-api-key");
        if (key == null || !this.config.apiKey().equals(key)) {
            throw HttpServerResponseException.of(401, "Unauthorized");
        }
        return Principal.with(new ApiKeyPrincipal(key), () -> chain.process(request));
    }
}
```

Scope it with `@InterceptWith(ApiKeyInterceptor.class)` on the `@HttpController` class or the
`@HttpRoute` method, or make it global with `@Tag(HttpServer.class)`. Full patterns, including
`HttpServerRequestMapper` + `@Mapping`:
[references/manual-auth-reference.md](references/manual-auth-reference.md).

---

## Pitfalls

| Symptom | Cause | Fix |
|---|---|---|
| Auth silently stops running; every request reaches the controller | `@Tag(HttpServerModule.class)` on a global interceptor — it compiles, but the router looks interceptors up under `@Tag(HttpServer.class)` | Use `@Tag(HttpServer.class)`. Cover it with a test that asserts `401`, not with a compile. |
| `HttpServerPrincipalExtractor<Principal>` — *wrong number of type arguments* | 1.x had one type parameter | `HttpServerPrincipalExtractor<String, Principal>` (or the `…AuthData` type for AND requirements) |
| `cannot find symbol: ApiSecurity.SecurityRequirementTag1` | Ordinal tags are gone | Use the scheme-named tag, e.g. `ApiSecurity.ApiKeyAuth.class` |
| `No component found for dependency … HttpServerPrincipalExtractor` | No extractor with the required `@Tag`, or the generic arguments do not match the generated parameter exactly | Copy the parameter type out of the generated `ApiSecurity` |
| `Multiple components match dependency` | Two providers for the same type+tag — usually a `@Component` extractor class *and* a `default` module method | Keep exactly one |
| Auth failure surfaces as `500` with your internal message in the body | `SecurityException` (or any plain exception) escaping the extractor | Return `null`, or throw `HttpServerResponseException.of(401, …)` |
| Kotlin: `'extract' overrides nothing` | Contracts are `@NullMarked`; the parameter and result are `@Nullable` | `override fun extract(request: HttpServerRequest, token: String?): Principal?` |
| `Principal.current()` returns `null` inside a handler | The route has no `security` requirement, or the work moved to a thread you started | Add `security:` to the operation; keep the work on the request thread |
| A `@Mapping` mapper is not found | The processor `new`s a mapper only when it is `final`, has a public no-arg constructor and carries no `@Tag`; otherwise it is injected | Add `@Component`, or make the class `final`/no-arg |

---

## What's in this skill

| File | Purpose |
|---|---|
| [references/openapi-security-reference.md](references/openapi-security-reference.md) | The generated `ApiSecurity` verbatim, tag-naming rules, per-scheme credential shapes, `PrincipalWithScopes`, AND/OR/anonymous requirements, testing. |
| [references/manual-auth-reference.md](references/manual-auth-reference.md) | Interceptors without OpenAPI, `HttpServerRequestMapper` + `@Mapping`, global-interceptor ordering, 401/403. |
| `assets/ApiKeyExtractor.java.template` / `.kt.template` | API-key extractor module, ready to copy. |
| `assets/BasicAuthExtractor.java.template` / `.kt.template` | HTTP Basic extractor module, ready to copy. |
| `scripts/setup.sh` | Copies the templates into a project; `--dry-run` supported. |
| `evals/evals.json` | Behavioural evals, including the 1.x→2.0 regressions. |

---

## Related skills

- [kora-http-server](../kora-http-server/SKILL.md) — controllers, routes, interceptors, error handling
- [kora-openapi-generator-server](../kora-openapi-generator-server/SKILL.md) — generator wiring that produces `ApiSecurity`
- [kora-http-client-auth](../kora-http-client-auth/SKILL.md) — outbound credentials (a different `ApiSecurity` shape)
- [kora-config-hocon](../kora-config-hocon/SKILL.md) — `@ConfigSource` for secrets
- [kora-json](../kora-json/SKILL.md) — JSON error bodies and JWT claim DTOs
- [kora-testing-junit-java](../kora-testing-junit-java/SKILL.md) · [kora-testing-junit-kotlin](../kora-testing-junit-kotlin/SKILL.md) — `@KoraAppTest` coverage for auth
