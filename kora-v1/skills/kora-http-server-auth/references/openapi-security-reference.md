# OpenAPI Security Reference

`HttpServerPrincipalExtractor<P>` bound to OpenAPI-generated `ApiSecurity` markers.
Source of truth: `.kora-agent/kora-docs/mkdocs/docs/en/documentation/openapi-codegen.md`
(Authorization section) and `.kora-agent/kora-examples/examples/java/kora-java-openapi-generator-http-server`.

## Contents

- [How it fits together](#how-it-fits-together)
- [Generated ApiSecurity markers](#generated-apisecurity-markers)
- [Principal and PrincipalWithScopes](#principal-and-principalwithscopes)
- [Bearer / JWT extractor](#bearer--jwt-extractor)
- [API-key extractor](#api-key-extractor)
- [Basic extractor](#basic-extractor)
- [OAuth extractor with scopes](#oauth-extractor-with-scopes)
- [Multiple schemes at once](#multiple-schemes-at-once)
- [Error mapping (401 / 403)](#error-mapping-401--403)
- [Testing an extractor](#testing-an-extractor)

---

## How it fits together

1. The OpenAPI contract declares `securitySchemes` and per-operation (or global) `security`.
2. The Kora `kora` generator emits an `ApiSecurity` class in the api package, with one
   nested marker type per scheme (`BearerAuth`, `BasicAuth`, `ApiKeyAuth`, `OAuth`).
3. You provide an `HttpServerPrincipalExtractor<P>` component tagged with
   `@Tag(ApiSecurity.<Scheme>.class)`.
4. The generated controller calls the matching extractor before invoking your delegate,
   passing the raw credential `value` parsed from the scheme's header.
5. The extractor returns a `CompletionStage<P>` (typically
   `CompletableFuture.completedFuture(principal)`), or throws `SecurityException` to reject.

The principal is **not** stored in a thread-local; there is no `Principal.current()` and
no request-attribute bag. If a delegate needs the principal, it is delivered through the
generated transport.

---

## Generated ApiSecurity markers

For a contract such as:

```yaml
components:
    securitySchemes:
        bearerAuth: { type: http, scheme: bearer, bearerFormat: JWT }
        apiKeyAuth: { type: apiKey, in: header, name: Authorization }
        basicAuth:  { type: http, scheme: basic }
```

the generator produces `ApiSecurity.BearerAuth`, `ApiSecurity.ApiKeyAuth`,
`ApiSecurity.BasicAuth`. An `oauth2` scheme produces `ApiSecurity.OAuth`. Reference these
markers from `@Tag` to bind the right extractor.

---

## Principal and PrincipalWithScopes

- `ru.tinkoff.kora.common.Principal` — base marker interface. Your principal record
  implements it.
- `ru.tinkoff.kora.http.common.auth.PrincipalWithScopes` — extends `Principal` with
  `Collection<String> scopes()`; required for OAuth scope enforcement.

```java
import ru.tinkoff.kora.common.Principal;

public record DataApiPrincipal(String name) implements Principal {}
```

```java
import java.util.Collection;
import java.util.List;
import ru.tinkoff.kora.http.common.auth.PrincipalWithScopes;

public record UserPrincipal(String name) implements PrincipalWithScopes {
    @Override public Collection<String> scopes() { return List.of("read", "write"); }
}
```

---

## Bearer / JWT extractor

`value` is the token after the `Bearer ` prefix. Validate it with your own JWT library
(Kora core does not ship a JWT verifier) and build the principal from the claims.

```java
import java.util.concurrent.CompletableFuture;
import ru.tinkoff.kora.common.Principal;
import ru.tinkoff.kora.common.Tag;
import ru.tinkoff.kora.http.server.common.auth.HttpServerPrincipalExtractor;

@Tag(ApiSecurity.BearerAuth.class)
default HttpServerPrincipalExtractor<Principal> bearerHttpServerPrincipalExtractor(JwtVerifier jwt) {
    return (request, value) -> {
        if (value == null) {
            throw new SecurityException("Missing bearer token");
        }
        var claims = jwt.verify(value); // your component; throws on invalid signature/expiry
        return CompletableFuture.completedFuture(new DataApiPrincipal(claims.subject()));
    };
}
```

`JwtVerifier` is your own `@Component`; nothing about it is Kora-specific.

---

## API-key extractor

`value` is the value of the header named in the `apiKey` scheme.

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

```java
import ru.tinkoff.kora.config.common.annotation.ConfigSource;

@ConfigSource("auth.apiKey")
public interface DataApiAuthConfig {
    String value();
}
```

For multiple rotating keys, inject your own lookup component instead of a single config
value.

---

## Basic extractor

`value` is the credential after the `Basic ` prefix — base64 of `username:password`.

```java
import java.nio.charset.StandardCharsets;
import java.util.Base64;
import java.util.concurrent.CompletableFuture;
import ru.tinkoff.kora.common.Principal;
import ru.tinkoff.kora.common.Tag;
import ru.tinkoff.kora.http.server.common.auth.HttpServerPrincipalExtractor;

@Tag(ApiSecurity.BasicAuth.class)
default HttpServerPrincipalExtractor<Principal> basicHttpServerPrincipalExtractor(CredentialService creds) {
    return (request, value) -> {
        if (value == null) {
            throw new SecurityException("Missing credentials");
        }
        var decoded = new String(Base64.getDecoder().decode(value), StandardCharsets.UTF_8);
        var parts = decoded.split(":", 2);
        if (parts.length != 2 || !creds.validate(parts[0], parts[1])) {
            throw new SecurityException("Invalid credentials");
        }
        return CompletableFuture.completedFuture(new DataApiPrincipal(parts[0]));
    };
}
```

Always serve Basic auth over HTTPS — credentials are only base64-encoded, not encrypted.

---

## OAuth extractor with scopes

Return a `PrincipalWithScopes` so the generated transport can compare the token's scopes
against the scopes the operation requires.

```java
import java.util.concurrent.CompletableFuture;
import ru.tinkoff.kora.common.Tag;
import ru.tinkoff.kora.http.common.auth.PrincipalWithScopes;
import ru.tinkoff.kora.http.server.common.auth.HttpServerPrincipalExtractor;

@Tag(ApiSecurity.OAuth.class)
default HttpServerPrincipalExtractor<PrincipalWithScopes> oauthHttpServerPrincipalExtractor(JwtVerifier jwt) {
    return (request, value) -> {
        var claims = jwt.verify(value);
        return CompletableFuture.completedFuture(new UserPrincipal(claims.subject()));
    };
}
```

---

## Multiple schemes at once

Declare one extractor per scheme on `@KoraApp` or a `@Module`. Each is selected by its
`@Tag`.

```java
@Tag(ApiSecurity.BearerAuth.class)
default HttpServerPrincipalExtractor<Principal> bearer() { ... }

@Tag(ApiSecurity.BasicAuth.class)
default HttpServerPrincipalExtractor<Principal> basic() { ... }

@Tag(ApiSecurity.ApiKeyAuth.class)
default HttpServerPrincipalExtractor<Principal> apiKey() { ... }

@Tag(ApiSecurity.OAuth.class)
default HttpServerPrincipalExtractor<PrincipalWithScopes> oauth() { ... }
```

---

## Error mapping (401 / 403)

`SecurityException` thrown by an extractor is not mapped to an HTTP status automatically.
Add a global `HttpServerInterceptor` (`@Tag(HttpServerModule.class)`) that translates it.
Use 401 for authentication failures and 403 for authorization (role/scope) failures.

```java
import java.util.concurrent.CompletionException;
import java.util.concurrent.CompletionStage;
import ru.tinkoff.kora.common.Component;
import ru.tinkoff.kora.common.Context;
import ru.tinkoff.kora.common.Tag;
import ru.tinkoff.kora.http.common.body.HttpBody;
import ru.tinkoff.kora.http.server.common.HttpServerInterceptor;
import ru.tinkoff.kora.http.server.common.HttpServerModule;
import ru.tinkoff.kora.http.server.common.HttpServerRequest;
import ru.tinkoff.kora.http.server.common.HttpServerResponse;
import ru.tinkoff.kora.http.server.common.HttpServerResponseException;

@Tag(HttpServerModule.class)
@Component
public final class AuthErrorInterceptor implements HttpServerInterceptor {
    @Override
    public CompletionStage<HttpServerResponse> intercept(Context context, HttpServerRequest request, InterceptChain chain)
            throws Exception {
        return chain.process(context, request).exceptionally(t -> {
            var cause = (t instanceof CompletionException && t.getCause() != null) ? t.getCause() : t;
            if (cause instanceof HttpServerResponseException ex) {
                return ex;
            }
            if (cause instanceof SecurityException) {
                return HttpServerResponse.of(401, HttpBody.plaintext(
                        cause.getMessage() != null ? cause.getMessage() : "Unauthorized"));
            }
            return HttpServerResponse.of(500, HttpBody.plaintext("Internal error"));
        });
    }
}
```

Inside a delegate or interceptor you can also short-circuit explicitly:
`throw HttpServerResponseException.of(403, "Required role: admin");`
(`HttpServerResponseException` exposes the status via `.code()`).

---

## Testing an extractor

The extractor is a plain functional interface — its SAM method is `extract`. Build it
directly and call `extract(request, value)`.

```java
@Test
void rejectsInvalidApiKey() {
    var config = mock(DataApiAuthConfig.class);
    when(config.value()).thenReturn("expected");
    var extractor = new Application(){}.apiKeyHttpServerPrincipalExtractor(config);

    assertThrows(SecurityException.class, () -> extractor.extract(mock(HttpServerRequest.class), "wrong"));
}
```

For full request lifecycle coverage (real status codes), prefer an integration test with
`@KoraAppTest` or a black-box test — see
[kora-testing-junit-java](../../kora-testing-junit-java/SKILL.md) and
[kora-testing-blackbox](../../kora-testing-blackbox/SKILL.md).
