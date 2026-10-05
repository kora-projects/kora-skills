# OpenAPI Security Reference (Kora 2.0)

Everything the `kora` OpenAPI generator emits for `components.securitySchemes`, and the exact
contract your `HttpServerPrincipalExtractor` must satisfy.

## Contents

- [The contract](#the-contract)
- [What the generator emits](#what-the-generator-emits)
- [Tag naming rules](#tag-naming-rules)
- [The credential your extractor receives](#the-credential-your-extractor-receives)
- [Choosing the extractor's type arguments](#choosing-the-extractors-type-arguments)
- [Per-scheme extractors](#per-scheme-extractors)
- [OAuth2 and PrincipalWithScopes](#oauth2-and-principalwithscopes)
- [AND requirements and AuthData](#and-requirements-and-authdata)
- [OR alternatives and anonymous access](#or-alternatives-and-anonymous-access)
- [Reaching the principal from a delegate](#reaching-the-principal-from-a-delegate)
- [Shaping the 401 response](#shaping-the-401-response)
- [Registering the extractor](#registering-the-extractor)
- [Testing](#testing)

---

## The contract

```java
package io.koraframework.http.server.common.auth;

public interface HttpServerPrincipalExtractor<T, P extends Principal> {
    @Nullable
    P extract(HttpServerRequest request, @Nullable T token);
}
```

- **Two** type parameters: `T` = the credential the scheme yields, `P` = your principal type.
- Synchronous. No `CompletionStage`, no `Mono`, no `suspend`.
- Both the `token` argument and the result are `@Nullable`; the module is `@NullMarked`, so a Kotlin
  override must be `fun extract(request: HttpServerRequest, token: String?): Principal?`.
- **Returning `null` means "not authenticated"** — that is the whole rejection protocol.

`Principal` is `io.koraframework.common.Principal`; `PrincipalWithScopes` is
`io.koraframework.http.common.auth.PrincipalWithScopes` and adds `Collection<String> scopes()`.

```java
public interface Principal {
    ScopedValue<Principal> VALUE = ScopedValue.newInstance();

    @Nullable static Principal current() { … }

    static <T, X extends Throwable> T with(Principal principal, ScopedValue.CallableOp<T, X> op) throws X { … }
}
```

---

## What the generator emits

For

```yaml
components:
  securitySchemes:
    apiKeyAuth: { type: apiKey, in: header, name: X-API-KEY }
security:
  - apiKeyAuth: []
```

the generator writes `ApiSecurity.java` into the api package (abridged, but verbatim in shape):

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

  final class ApiKeyAuth {}                       // the tag — a bare marker class

  final class ApiKeyAuthHttpServerInterceptor implements HttpServerInterceptor {
    HttpServerPrincipalExtractor<String, Principal> ApiKeyAuth_;
    …
    @Override
    public HttpServerResponse intercept(HttpServerRequest request,
        HttpServerInterceptor.InterceptChain chain) throws Exception {
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

and puts this on each secured controller method:

```java
@InterceptWith(value = HttpServerInterceptor.class, tag = ApiSecurity.ApiKeyAuth.class)
```

Four consequences worth internalizing:

1. **`ApiSecurity` is a `@Module`.** The Kora processor discovers `@Module` interfaces compiled in
   the same round, so your `@KoraApp` interface must **not** extend it.
2. **You never write the interceptor.** You supply exactly one thing: the extractor, under the right
   tag, with the right type arguments.
3. **Rejection is `null`**, and the built-in failure response is `401 Unauthorized`. The only
   generated `403 Forbidden` is the oauth2 scope check below.
4. **The principal reaches the handler through `Principal.with(...)`**, a `ScopedValue` binding that
   lives exactly as long as `chain.process(request)`.

---

## Tag naming rules

The generator derives every tag from the **name in `components.securitySchemes`**, sanitized to a
Java identifier and PascalCased (`upperCase(toVarName(name))`). Ordinal `SecurityRequirementTagN`
names from Kora 1.x no longer exist.

| Source | Tag |
|---|---|
| `apiKeyAuth` | `ApiSecurity.ApiKeyAuth` |
| `bearerAuth` | `ApiSecurity.BearerAuth` |
| `basicAuth` | `ApiSecurity.BasicAuth` |
| `cookieAuth` | `ApiSecurity.CookieAuth` |
| `oAuth` | `ApiSecurity.OAuth` |

Two different tag families are generated, and they are named by different rules:

| Family | Rule | Example |
|---|---|---|
| **Extractor tag** — what you put on your extractor | scheme names of one requirement joined with `With` | `HeaderAuth1WithQueryAuth` |
| **Interceptor tag** — what the controller method references | schemes of one alternative joined with `And`; OR-alternatives joined with `_`; an empty requirement is `Anonymous` | `HeaderAuth1AndQueryAuth_HeaderAuth2_OAuth`, `Sec1_Anonymous` |

When one base interceptor tag would cover several different scope sets, the scope names are appended:
`OAuth2ClientCredentials_PetsRead`, `OAuth2ClientCredentials_PetsReadAndPetsWrite`,
`OAuth2ClientCredentials_NoScopes`. Those extra tags are **interceptor** tags only — a scheme still
needs just **one** extractor, tagged with the plain scheme name.

> Do not guess a tag. Open the generated `ApiSecurity` in `build/generated/**/api/` and copy it.

---

## The credential your extractor receives

This is the biggest behavioural trap when porting from Kora 1.x, which described the value as "the
credential after the scheme prefix". It is not.

| Scheme | What the interceptor reads | What `token` contains |
|---|---|---|
| `apiKey`, `in: header` | `request.headers().getFirst("<name>")` | the raw header value |
| `apiKey`, `in: query` | first value of `request.queryParams().get("<name>")` | the raw query value |
| `apiKey`, `in: cookie` | the matching cookie's `value()` | the raw cookie value |
| `http` / `bearer` | `request.headers().getFirst("authorization")` | **the whole header**, e.g. `Bearer eyJhbGci…` |
| `http` / `basic` | `request.headers().getFirst("authorization")` | **the whole header**, e.g. `Basic dXNlcjpwYXNz` |
| `oauth2`, `openIdConnect` | `request.headers().getFirst("authorization")` | **the whole header** |

So a bearer extractor must strip the prefix itself:

```java
if (value == null || !value.startsWith("Bearer ")) {
    return null;
}
var token = value.substring("Bearer ".length());
```

Any other scheme type fails the build with *"Unsupported OpenAPI server security scheme"*; an
`apiKey` without a valid `in` fails with *"Invalid OpenAPI apiKey security scheme"*.

---

## Choosing the extractor's type arguments

The generated `@DefaultComponent` factory parameter *is* the specification. Read it off the file, or
apply the rule the generator uses:

| Requirement | `T` | `P` |
|---|---|---|
| one scheme | `String` | `Principal` |
| one scheme, `oauth2` or `openIdConnect` | `String` | `PrincipalWithScopes` |
| several schemes ANDed | `ApiSecurity.<A>With<B>AuthData` | `Principal` |
| several ANDed, any of them `oauth2`/`openIdConnect` | `ApiSecurity.<A>With<B>AuthData` | `PrincipalWithScopes` |

Note `P` is the **framework interface**, not your concrete record — the generated parameter is
`HttpServerPrincipalExtractor<String, Principal>`. Your extractor returns your own type; the
declared type argument stays `Principal` (or `PrincipalWithScopes`).

---

## Per-scheme extractors

All of these are `default` methods on `@KoraApp` or on a `@Module` interface.

### API key

```java
@Tag(ApiSecurity.ApiKeyAuth.class)
default HttpServerPrincipalExtractor<String, Principal> apiKeyExtractor(ApiKeyConfig config) {
    return (request, value) -> config.value().equals(value)
        ? new ApiKeyPrincipal("api-client")
        : null;
}
```

For rotating keys inject your own lookup component instead of a single config value.

### Bearer / JWT

Kora ships no JWT verifier — `JwtVerifier` below is your own `@Component`.

```java
@Tag(ApiSecurity.BearerAuth.class)
default HttpServerPrincipalExtractor<String, Principal> bearerExtractor(JwtVerifier jwt) {
    return (request, value) -> {
        if (value == null || !value.startsWith("Bearer ")) {
            return null;
        }
        var claims = jwt.verifyOrNull(value.substring("Bearer ".length()));
        return claims == null ? null : new UserPrincipal(claims.subject());
    };
}
```

Prefer a verifier that *returns* `null` on an invalid token. If yours throws, catch it and return
`null`, or let a `HttpServerResponseException` out — never a bare `SecurityException`.

### Basic

```java
@Tag(ApiSecurity.BasicAuth.class)
default HttpServerPrincipalExtractor<String, Principal> basicExtractor(CredentialService creds) {
    return (request, value) -> {
        if (value == null || !value.startsWith("Basic ")) {
            return null;
        }
        final String decoded;
        try {
            decoded = new String(Base64.getDecoder().decode(value.substring("Basic ".length())), UTF_8);
        } catch (IllegalArgumentException e) {
            return null;                       // malformed base64 is a failed login, not a 500
        }
        var parts = decoded.split(":", 2);
        return parts.length == 2 && creds.validate(parts[0], parts[1])
            ? new UserPrincipal(parts[0])
            : null;
    };
}
```

Serve Basic auth over HTTPS only — the credential is encoded, not encrypted.

### Cookie

Same shape as the header API key; the interceptor hands you the cookie's value.

```java
@Tag(ApiSecurity.CookieAuth.class)
default HttpServerPrincipalExtractor<String, Principal> cookieExtractor(SessionStore sessions) {
    return (request, value) -> value == null ? null : sessions.lookup(value);
}
```

---

## OAuth2 and PrincipalWithScopes

For `oauth2` / `openIdConnect` the generated parameter is
`HttpServerPrincipalExtractor<String, PrincipalWithScopes>`, and the interceptor checks the
operation's scopes itself:

```java
var forbidden = false;
var OAuth = this.OAuth_.extract(request, oAuthHeader);
if (OAuth != null) {
  if (OAuth.scopes().contains("pets:read")) {
    if (OAuth.scopes().contains("pets:write")) {
      return Principal.with(OAuth, () -> chain.process(request));
    }
  }
  forbidden = true;
}

if (forbidden) {
  throw HttpServerResponseException.of(403, "Forbidden");
}
throw HttpServerResponseException.of(401, "Unauthorized");
```

- Required scopes are ANDed, and the check is a plain `scopes().contains(...)` on the exact strings
  from the contract.
- **A missing scope produces `403 Forbidden`; no principal at all produces `401`.** With several
  OR alternatives, a later alternative that authenticates still wins; `403` is thrown only when none
  did and at least one extractor returned a principal whose scopes fell short. An operation that
  also allows anonymous access never answers `403` — it falls through to the handler.
- Rules the contract cannot express (roles, ownership) stay in the delegate: check
  `Principal.current()` and throw `HttpServerResponseException.of(403, …)`.
- One extractor per scheme, no matter how many scope combinations the contract uses.

```java
public record UserPrincipal(String name, Collection<String> scopes) implements PrincipalWithScopes {}

@Tag(ApiSecurity.OAuth.class)
default HttpServerPrincipalExtractor<String, PrincipalWithScopes> oauthExtractor(JwtVerifier jwt) {
    return (request, value) -> {
        if (value == null || !value.startsWith("Bearer ")) {
            return null;
        }
        var claims = jwt.verifyOrNull(value.substring("Bearer ".length()));
        return claims == null ? null : new UserPrincipal(claims.subject(), claims.scopes());
    };
}
```

---

## AND requirements and AuthData

A single requirement listing several schemes means *all of them at once*. The generator then emits a
record carrying every credential and switches `T` to it:

```yaml
security:
  - headerAuth1: []
    queryAuth: []
```

```java
/**
 * @param headerAuth1 'X-API-KEY-1' header of request
 * @param queryAuth 'X-QUERY-KEY' query parameter value
 */
record HeaderAuth1WithQueryAuthAuthData(String headerAuth1, String queryAuth) {}
```

```java
@Tag(ApiSecurity.HeaderAuth1WithQueryAuth.class)
default HttpServerPrincipalExtractor<ApiSecurity.HeaderAuth1WithQueryAuthAuthData, Principal> pairExtractor() {
    return (request, value) -> {
        if (value == null || !valid(value.headerAuth1(), value.queryAuth())) {
            return null;
        }
        return new ApiKeyPrincipal(value.headerAuth1());
    };
}
```

The record's components are plain `String` but the underlying lookups can miss, so treat each one as
possibly `null`.

---

## OR alternatives and anonymous access

Several top-level entries under `security:` are alternatives, tried in order; the first extractor
returning non-`null` wins.

```yaml
security:
  - sec1: []
  - {}          # anonymous also allowed
```

With an empty requirement present the generated interceptor ends in `return chain.process(request)`
instead of throwing — the route stays reachable and `Principal.current()` is simply `null` inside
the handler. The interceptor tag becomes `ApiSecurity.Sec1_Anonymous`, distinct from
`ApiSecurity.Sec1` used by fully-protected operations; both are fed by the **same** `Sec1` extractor.

---

## Reaching the principal from a delegate

```java
@Component
public final class PetApiDelegateImpl implements PetApiDelegate {

    @Override
    public PetApiResponses.GetPetApiResponse getPet(long id) {
        var principal = (UserPrincipal) Principal.current();
        if (principal == null) {
            throw HttpServerResponseException.of(401, "Unauthorized");
        }
        if (!principal.scopes().contains("pets:admin")) {
            throw HttpServerResponseException.of(403, "Forbidden");
        }
        …
    }
}
```

`Principal.current()` is backed by `ScopedValue`, so it is visible on the request thread and on
threads forked from it inside a `StructuredTaskScope` — not on an arbitrary executor you submit to.
Capture the principal into a local before handing work to another thread.

---

## Shaping the 401 response

The generated interceptor throws `HttpServerResponseException.of(401, "Unauthorized")` (and
`of(403, "Forbidden")` for a failed scope check), both plaintext bodies. Two ways to change them:

- **Per scheme** — throw your own `HttpServerResponseException` from the extractor instead of
  returning `null`. It implements `HttpServerResponse`, so Undertow sends it verbatim. This
  short-circuits the remaining OR alternatives, so use it only when there is a single scheme.
- **Globally** — a `@Tag(HttpServer.class)` interceptor that catches `HttpServerResponseException`
  and re-renders it as JSON. This is the only layer outside the generated security interceptor; the
  OpenAPI `interceptors` generator option nests *inside* it and cannot see the `401`.

---

## Registering the extractor

Either form works; pick one, never both for the same tag.

```java
// A. default method on @KoraApp or a @Module interface — what the examples use
@Tag(ApiSecurity.ApiKeyAuth.class)
default HttpServerPrincipalExtractor<String, Principal> apiKeyExtractor(ApiKeyConfig config) { … }
```

```java
// B. a tagged @Component class
@Component
@Tag(ApiSecurity.ApiKeyAuth.class)
public final class ApiKeyExtractor implements HttpServerPrincipalExtractor<String, Principal> {
    private final ApiKeyConfig config;
    public ApiKeyExtractor(ApiKeyConfig config) { this.config = config; }

    @Override
    public @Nullable Principal extract(HttpServerRequest request, @Nullable String token) { … }
}
```

Declaring both yields `Multiple components match dependency`; declaring neither yields
`No component found for dependency`.

---

## Testing

The extractor is a plain function — call `extract` directly.

```java
@Test
void rejectsWrongApiKey() {
    var config = mock(ApiKeyConfig.class);
    when(config.value()).thenReturn("expected");

    var extractor = new Application() {}.apiKeyExtractor(config);

    assertNull(extractor.extract(mock(HttpServerRequest.class), "wrong"));
    assertNotNull(extractor.extract(mock(HttpServerRequest.class), "expected"));
}
```

A unit test cannot catch the two failure modes that matter most — a global interceptor bound to the
wrong tag, and a missing `security:` block. Both need a request through the real server:

```java
@KoraAppTest(Application.class)
class AuthIT {
    @Test
    void unauthenticatedRequestIsRejected() {
        assertEquals(401, http.send(get("/pets")).statusCode());
    }

    @Test
    void authenticatedRequestPasses() {
        assertEquals(200, http.send(get("/pets").header("X-API-KEY", "expected")).statusCode());
    }
}
```

See [kora-testing-junit-java](../../kora-testing-junit-java/SKILL.md),
[kora-testing-junit-kotlin](../../kora-testing-junit-kotlin/SKILL.md) and
[kora-testing-blackbox](../../kora-testing-blackbox/SKILL.md).
