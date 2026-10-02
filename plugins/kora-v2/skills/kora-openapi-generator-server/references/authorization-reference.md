# OpenAPI Authorization Reference — Kora 2.x

When the contract declares `components.securitySchemes`, the server generator emits an
`ApiSecurity` interface into `apiPackage`. It contains marker classes, ready-made
`HttpServerInterceptor` implementations and the module bindings for them. You supply exactly one
thing per scheme: an `HttpServerPrincipalExtractor` tagged with the generated marker.

## Contents

- [1. Tag names come from the scheme name](#1-tag-names-come-from-the-scheme-name)
- [2. What `ApiSecurity` contains](#2-what-apisecurity-contains)
- [3. Supplying the principal extractor](#3-supplying-the-principal-extractor)
- [4. Where credentials come from](#4-where-credentials-come-from)
- [5. Alternatives (OR) and combinations (AND)](#5-alternatives-or-and-combinations-and)
- [6. OAuth2 scopes](#6-oauth2-scopes)
- [7. Anonymous access](#7-anonymous-access)
- [8. Reading the principal in the delegate](#8-reading-the-principal-in-the-delegate)
- [9. 401 vs 403](#9-401-vs-403)
- [10. Pitfalls](#10-pitfalls)

---

## 1. Tag names come from the scheme name

Each key under `components.securitySchemes` becomes a nested marker class named
`upperCase(toVarName(schemeName))` — in practice, the scheme name with its first letter
capitalised and separators removed:

| `securitySchemes` key | Generated marker |
|---|---|
| `BearerAuth` | `ApiSecurity.BearerAuth` |
| `bearerAuth` | `ApiSecurity.BearerAuth` |
| `ApiKeyAuth` | `ApiSecurity.ApiKeyAuth` |
| `api_key` | `ApiSecurity.ApiKey` |
| `oAuth2ClientCredentials` | `ApiSecurity.OAuth2ClientCredentials` |

Kora 1.x's ordinal names — `ApiSecurity.SecurityRequirementTag1`, `securityRequirementTag1` and
friends — **do not exist in 2.0**. Their absence is asserted by the generator's own tests, for
both languages, so this is a deliberate removal rather than a naming accident. An extractor still
tagged that way compiles fine and is simply never matched, so every request to a secured route
answers `401`.

## 2. What `ApiSecurity` contains

For a contract with one `apiKey` scheme named `ApiKeyAuth`:

```java
@Generated("io.koraframework.openapi.generator.javagen.ServerSecuritySchemaGenerator")
@Module
public interface ApiSecurity {

  @Tag(ApiKeyAuth.class)
  @DefaultComponent
  default ApiKeyAuthHttpServerInterceptor ApiKeyAuthHttpServerInterceptor(
      @Tag(ApiKeyAuth.class) HttpServerPrincipalExtractor<String, Principal> ApiKeyAuth_) {
    return new ApiKeyAuthHttpServerInterceptor(ApiKeyAuth_);
  }

  final class ApiKeyAuth { }                                  // the marker you tag

  final class ApiKeyAuthHttpServerInterceptor implements HttpServerInterceptor {
    @Override
    public HttpServerResponse intercept(HttpServerRequest request, InterceptChain chain) throws Exception {
      var ApiKeyAuthHeader = request.headers().getFirst("X-API-KEY");
      var ApiKeyAuth = this.ApiKeyAuth_.extract(request, ApiKeyAuthHeader);
      if (ApiKeyAuth != null) {
        return Principal.with(ApiKeyAuth, () -> chain.process(request));
      }
      throw HttpServerResponseException.of(401, "Unauthorized");
    }
  }
}
```

and the generated controller method carries

```java
@InterceptWith(value = HttpServerInterceptor.class, tag = ApiSecurity.ApiKeyAuth.class)
```

`ApiSecurity` is annotated `@Module`, and the `@KoraApp` processor discovers every `@Module`
interface in the compilation round — **do not add `ApiSecurity` to the `@KoraApp` `extends`
list**. The migrated examples list only framework modules.

`ApiSecurity` is generated for a server whenever `components.securitySchemes` is non-empty.

## 3. Supplying the principal extractor

```java
public interface HttpServerPrincipalExtractor<T, P extends Principal> {
    @Nullable P extract(HttpServerRequest request, @Nullable T token);
}
```

Returning `null` means "not authenticated" and produces the `401`. Implement `Principal`
(`io.koraframework.common.Principal`) on your own type, or `PrincipalWithScopes`
(`io.koraframework.http.common.auth.PrincipalWithScopes`) when the scheme declares OAuth2 scopes.

===! ":fontawesome-brands-java: `Java`"

    ```java
    public record UserPrincipal(String name) implements PrincipalWithScopes {
        @Override public Collection<String> scopes() { return List.of("read", "write"); }
    }

    @KoraApp
    public interface Application extends
            HoconConfigModule, LogbackModule, JsonModule,
            ValidationModule, UndertowPublicHttpServerModule {

        static void main(String[] args) { KoraApplication.run(ApplicationGraph::graph); }

        @Tag(ApiSecurity.BearerAuth.class)
        default HttpServerPrincipalExtractor<String, Principal> bearerHttpServerPrincipalExtractor() {
            return (request, value) -> value == null ? null : tokens.verify(value);
        }

        @Tag(ApiSecurity.ApiKeyAuth.class)
        default HttpServerPrincipalExtractor<String, Principal> apiKeyHttpServerPrincipalExtractor() {
            return (request, value) -> apiKeys.lookup(value);
        }
    }
    ```

=== ":simple-kotlin: `Kotlin`"

    ```kotlin
    data class UserPrincipal(val name: String) : PrincipalWithScopes {
        override fun scopes(): Collection<String> = listOf("read", "write")
    }

    @KoraApp
    interface Application : HoconConfigModule, LogbackModule, JsonModule,
                            ValidationModule, UndertowPublicHttpServerModule {

        @Tag(ApiSecurity.BearerAuth::class)
        fun bearerHttpServerPrincipalExtractor(): HttpServerPrincipalExtractor<String, Principal> =
            HttpServerPrincipalExtractor { _, value -> value?.let(tokens::verify) }
    }
    ```

    ```kotlin
    fun main() { KoraApplication.run { ApplicationGraph.graph() } }
    ```

A default method on the `@KoraApp` interface is a module factory method — do **not** also mark it
`@Component`. A standalone extractor class works too; then it needs `@Component` **and** the
`@Tag`.

The generated interceptor binding is `@DefaultComponent`, so you may replace a whole
interceptor by declaring your own `@Component` `HttpServerInterceptor` under the same tag — but
supplying the extractor is almost always what you want.

## 4. Where credentials come from

The generated interceptor reads the credential itself and hands it to your extractor as the
second argument. What it reads is fixed by the scheme:

| Scheme | What the interceptor extracts | Extractor `T` |
|---|---|---|
| `type: apiKey, in: header, name: X-API-KEY` | `request.headers().getFirst("X-API-KEY")` | `String` |
| `type: apiKey, in: query, name: token` | first value of `request.queryParams().get("token")` | `String` |
| `type: apiKey, in: cookie, name: SESSION` | matching cookie value | `String` |
| `type: http, scheme: basic` | the raw `Authorization` header | `String` |
| `type: http, scheme: bearer` | the raw `Authorization` header | `String` |
| `type: oauth2` / `openIdConnect` | the raw `Authorization` header | `String` |

The header is passed **raw**, including the `Bearer ` / `Basic ` prefix — strip and decode it in
your extractor. An `apiKey` scheme with an `in` value other than `header`/`query`/`cookie`, or any
other scheme type, aborts generation with an explicit message.

## 5. Alternatives (OR) and combinations (AND)

```yaml
# OR — either scheme authenticates the request
security:
  - ApiKeyAuth: []
  - AnotherApiKeyAuth: []

# AND — both credentials are required together
security:
  - cookieAuth1: []
    cookieAuth2: []
```

**OR** generates one interceptor that tries each scheme in turn and succeeds on the first
extractor that returns non-`null`. You still register one extractor per scheme, each under its own
scheme marker (`@Tag(ApiSecurity.ApiKeyAuth.class)`, `@Tag(ApiSecurity.AnotherApiKeyAuth.class)`).
The interceptor itself gets a combined tag, e.g. `ApiSecurity.ApiKeyAuth_AnotherApiKeyAuth` — you
never reference that one.

**AND** generates a record carrying every credential and a single extractor for the combination:

```java
record CookieAuth1WithCookieAuth2AuthData(String cookieAuth1, String cookieAuth2) { }
```

```java
@Tag(ApiSecurity.CookieAuth1WithCookieAuth2.class)
default HttpServerPrincipalExtractor<ApiSecurity.CookieAuth1WithCookieAuth2AuthData, Principal>
        cookiePairExtractor() {
    return (request, data) -> data == null ? null : sessions.verify(data.cookieAuth1(), data.cookieAuth2());
}
```

The naming rule: scheme markers joined by `With` name the **extractor** tag and its `AuthData`
record; joined by `And` they name the **interceptor** tag. You only ever write the `With` form.

`configOptions.useSecurityDeclarationOrder: "true"` keeps the OpenAPI declaration order when
deriving these names instead of normalising it — useful when a rename shuffles generated tags.

## 6. OAuth2 scopes

A scheme with `type: oauth2` or `type: openIdConnect` makes the extractor's principal type `PrincipalWithScopes`, and each
distinct scope set in the contract gets its own interceptor tag:

```yaml
security:
  - oAuth2ClientCredentials: [ "pets:read" ]
```

```java
@Tag(OAuth2ClientCredentials_PetsRead.class)
@DefaultComponent
default OAuth2ClientCredentials_PetsReadHttpServerInterceptor …(
    @Tag(OAuth2ClientCredentials.class) HttpServerPrincipalExtractor<String, PrincipalWithScopes> …) { … }
```

whose body is

```java
var forbidden = false;
var principal = /* extractor */.extract(request, request.headers().getFirst("authorization"));
if (principal != null) {
  if (principal.scopes().contains("pets:read")) {
    return Principal.with(principal, () -> chain.process(request));
  }
  forbidden = true;
}
if (forbidden) {
  throw HttpServerResponseException.of(403, "Forbidden");
}
throw HttpServerResponseException.of(401, "Unauthorized");
```

A principal that was extracted but lacks a required scope gets **`403 Forbidden`**; no principal at
all gets `401 Unauthorized`. When the operation also allows anonymous access (`- {}`), neither is
thrown and the request proceeds unauthenticated.

You register **one** extractor, tagged with the scheme marker (`ApiSecurity.OAuth2ClientCredentials`),
typed `HttpServerPrincipalExtractor<String, PrincipalWithScopes>`, and return a principal whose
`scopes()` reflects the token. The scope-specific tags
(`…_PetsRead`, `…_PetsReadAndPetsWrite`, `…_NoScopes`) are internal wiring.

Scope names are PascalCased for the tag: `pets:read` → `PetsRead`; an empty scope list produces
the `_NoScopes` suffix.

## 7. Anonymous access

An operation whose `security` list contains an empty requirement `- {}` alongside real ones is
allowed through when no credential matches — the generated interceptor ends with
`return chain.process(request);` instead of throwing. An operation with no `security` at all (and
no global `security`) gets no interceptor annotation and is unauthenticated.

## 8. Reading the principal in the delegate

The interceptor publishes the principal with
`Principal.with(principal, () -> chain.process(request))`, which binds a JDK `ScopedValue`. Read
it anywhere downstream:

```java
var principal = Principal.current();          // io.koraframework.common.Principal, @Nullable
if (principal instanceof UserPrincipal user) {
    log.info("acting as {}", user.name());
}
```

```kotlin
val user = Principal.current() as? UserPrincipal
```

This is the 2.0 replacement for passing request-scoped identity around — `Context` no longer
exists. `Principal.current()` returns `null` outside a bound scope, so guard it.

## 9. 401 vs 403

The generated interceptor answers:

| Situation | Status |
|---|---|
| no extractor returned a principal (missing or invalid credential) | `401 Unauthorized` |
| a principal was extracted, but it lacks an OAuth2 / OpenID Connect scope the operation requires | `403 Forbidden` |
| the operation also allows anonymous access (`- {}`) | neither — the request proceeds |

Only OAuth2 / OpenID Connect scopes produce the generated `403`. For any other authenticated-but-forbidden rule
(roles, ownership, tenant), decide in your own code — never by editing generated code:

- throw `HttpServerResponseException.of(403, …)` from the extractor (the exception is an
  `HttpServerResponse`, so it is returned as-is);
- return the contract's `403` response record from the delegate after checking authorisation
  there;
- register your own `@Component` `HttpServerInterceptor` under the generated interceptor tag,
  replacing the `@DefaultComponent` one.

## 10. Pitfalls

| Symptom | Cause and fix |
|---|---|
| Every secured request returns 401 | The extractor's `@Tag` does not name a generated `ApiSecurity` marker — check the exact nested class name in the generated `ApiSecurity`. |
| `No component found for dependency … HttpServerPrincipalExtractor<String, Principal>` with a tag | No extractor registered for that scheme. |
| `Multiple components match` for an extractor | Registered both as a `@KoraApp` default method and as a `@Component` class. |
| `ApiSecurity` not generated | The contract has no `components.securitySchemes`, or no operation references them. |
| Extractor never sees the token | The credential location in the contract does not match reality (`in: header` vs `in: cookie`). |
| `Bearer <token>` fails to parse | The raw `Authorization` header is passed through; strip the prefix yourself. |
| OAuth2 route 403s for a valid token | The principal's `scopes()` does not contain the scope the contract requires. |
| OAuth2 route 401s for a valid token | The extractor returned `null` — the token was not recognised, or the extractor's `@Tag` does not match. |
| Duplicate/renamed tags after a spec edit | Tag names derive from scheme and scope names; try `useSecurityDeclarationOrder: "true"`, and regenerate with `clean`. |

## Related

- [Controllers Reference](openapi-controllers-reference.md) — how `@InterceptWith` lands
- [Response Reference](openapi-response-reference.md) — returning contract errors
- `kora-http-server-auth` skill — auth without OpenAPI
