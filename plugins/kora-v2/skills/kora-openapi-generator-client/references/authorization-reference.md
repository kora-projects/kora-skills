# OpenAPI Client Authorization Reference — Kora 2.x

How a generated Kora 2.0 HTTP client authenticates outbound requests. Verified against
`ClientSecuritySchemaGenerator` and `ClientApiGenerator` in `io.koraframework:openapi-generator`
for `2.0.0.RC2`, the `io.koraframework.http.client.common.auth` / `.interceptor` packages, and the
migrated Java/Kotlin OpenAPI HTTP-client examples.

Everything here is **client-side** (outbound). `Principal` and `HttpServerPrincipalExtractor`
belong to the server generator — see `kora-openapi-generator-server`.

## Contents

- [How generated auth works](#how)
- [Names: tag vs config key](#names)
- [Schemes the generator wires for you](#generated-providers)
- [Schemes you must wire yourself: bearer and oauth2](#bearer-oauth)
- [Credential config paths](#config-paths)
- [Multiple schemes on one operation](#multiple)
- [`authAsMethodArgument`](#auth-arg)
- [Overriding a generated provider](#overriding)
- [Hand-wiring interceptors without securitySchemes](#manual)
- [Migrating from Kora 1.x](#migration)
- [Troubleshooting](#troubleshooting)

---

## How generated auth works { #how }

When the contract declares `components.securitySchemes`, the generator emits an `ApiSecurity`
`@Module` interface next to the `*Api` in `apiPackage`. It contains:

- a **marker class per security scheme** (`ApiSecurity.ApiKeyAuth`, `ApiSecurity.BearerAuth`, …)
  used as a Kora `@Tag`;
- a `SecurityConfig` record plus a `@DefaultComponent` factory that reads credentials from config;
- a `@DefaultComponent` `HttpClientTokenProvider` per scheme the generator can resolve on its own;
- a marker class and a `@DefaultComponent` `HttpClientInterceptor` per distinct **security
  requirement** appearing in the contract (the factory method is declared to return
  `HttpClientInterceptor`, not the generated class).

Each generated method then carries `@InterceptWith(value = HttpClientInterceptor.class, tag =
ApiSecurity.<Requirement>.class)`, so Kora looks the interceptor up by tag at graph build time.

`ApiSecurity` carries `@Module`, and the `@KoraApp` processor collects every `@Module`-annotated
interface in the compilation into the graph on its own. There is nothing to extend from `@KoraApp`
and nothing to register — the generated module is live as soon as it compiles.

The credential contract is one synchronous method:

```java
package io.koraframework.http.client.common.auth;

public interface HttpClientTokenProvider {
    @Nullable String getToken(HttpClientRequest request);
}
```

Returning `null` means "this scheme has nothing to contribute" — the interceptor moves on. In
Kora 1.x this returned a `CompletionStage<String>`; in 2.0 it is a plain nullable `String`.

## Names: tag vs config key { #names }

Two different transformations of the same scheme name, and mixing them up is a common failure:

| From `components.securitySchemes` | Generated `@Tag` marker | Credential config key |
|---|---|---|
| `apiKeyAuth` | `ApiSecurity.ApiKeyAuth` | `<prefix>.apiKeyAuth` |
| `bearerAuth` | `ApiSecurity.BearerAuth` | *(bearer reads no config)* |
| `basicAuth` | `ApiSecurity.BasicAuth` | `<prefix>.basicAuth.username` / `.password` |
| `ApiKeyAuth` | `ApiSecurity.ApiKeyAuth` | `<prefix>.ApiKeyAuth` |

The **tag** capitalises the first letter of the scheme name. The **config key** uses the scheme
name exactly as written in the contract. Rename a scheme in the spec and both move.

Ordinal `ApiSecurity.SecurityRequirementTag1` names from Kora 1.x do not exist. A provider tagged
that way is simply never found, and the graph fails to build with a missing-dependency error that
names `HttpClientTokenProvider`, not the tag you expected.

## Schemes the generator wires for you { #generated-providers }

| Scheme | Generated | Sends |
|---|---|---|
| `type: apiKey` (header / query / cookie) | `@DefaultComponent @Tag(<Scheme>) HttpClientTokenProvider` reading the config value | the configured parameter |
| `type: http, scheme: basic` | `@DefaultComponent @Tag(<Scheme>) BasicAuthHttpClientTokenProvider` built from `username` + `password` (UTF-8, base64) | `Authorization: Basic <base64>` |
| `type: http, scheme: bearer` | tag class only — **no provider** | `Authorization: Bearer <token>` — your provider returns the bare token |
| `type: oauth2` | tag class only — **no provider** | `Authorization: Bearer <token>` — your provider returns the bare token |
| `type: openIdConnect` | tag class only — **no provider** (handled exactly like `oauth2`) | `Authorization: Bearer <token>` — your provider returns the bare token |

Any other `type` aborts generation with
an explicit "unsupported security scheme" message rather than emitting something that silently
does nothing.

Spec and generator config:

```yaml
components:
  securitySchemes:
    apiKeyAuth:
      type: apiKey
      in: header
      name: X-API-KEY
security:
  - apiKeyAuth: []
```

```groovy
configOptions = [
        mode                : "java-client",
        clientConfigPrefix  : "httpClient.pet",
        securityConfigPrefix: "openapiAuth",   // credential root
        primaryAuth         : "apiKeyAuth",    // only needed when several schemes apply
]
```

```hocon
openapiAuth {
  apiKeyAuth = ${API_KEY}
  basicAuth { username = ${BASIC_USER}, password = ${BASIC_PASSWORD} }
}
```

## Schemes you must wire yourself: bearer and oauth2 { #bearer-oauth }

The generator has no way to obtain a bearer or OAuth token, so it emits the tag and stops. The
application must supply a `HttpClientTokenProvider` under that tag or the graph will not build:

```java
@KoraApp
public interface Application extends
        HoconConfigModule, LogbackModule, JsonModule, OkHttpClientModule {

    @Tag(ApiSecurity.BearerAuth.class)
    default HttpClientTokenProvider bearerAuthTokenProvider(TokenService tokens) {
        return request -> tokens.currentAccessToken();   // may return null
    }

    static void main(String[] args) {
        KoraApplication.run(ApplicationGraph::graph);
    }
}
```

```kotlin
@KoraApp
interface Application : HoconConfigModule, LogbackModule, JsonModule, OkHttpClientModule {

    @Tag(ApiSecurity.BearerAuth::class)
    fun bearerAuthTokenProvider(tokens: TokenService): HttpClientTokenProvider =
        HttpClientTokenProvider { tokens.currentAccessToken() }
}
```

The provider returns the **bare token**. The generated interceptor adds the scheme itself —
`Bearer ` for `http`/`bearer`, `oauth2` and `openIdConnect`, `Basic ` for `http`/`basic` — so a
provider that returns `"Bearer " + token` sends `Authorization: Bearer Bearer …`.

**A scheme you do not use still needs a provider, and it must return `null`.** When several
schemes share an operation, the generated interceptor walks them in order and uses the first
non-null token. A stub that returns a placeholder string will win the race and send the wrong
credential:

```java
// Required by ApiSecurity even though this service never uses OAuth.
// Must return null, or it pre-empts apiKeyAuth and the request goes out with the wrong header.
@Tag(ApiSecurity.OAuth.class)
default HttpClientTokenProvider oAuthTokenProvider() {
    return request -> null;
}
```

## Credential config paths { #config-paths }

`securityConfigPathPrefix()` resolves in this order:

| Condition | Prefix |
|---|---|
| `securityConfigPrefix` set | its value |
| else `clientConfigPrefix` set | `<clientConfigPrefix>.security` |
| else `clientConfig` set | `<clientConfig>.security` |
| else | `security` |

The scheme name is then appended verbatim. With `clientConfigPrefix = "httpClient.pet"` and no
`securityConfigPrefix`, the generated module reads:

```hocon
httpClient.pet.security {
  apiKeyAuth = ${API_KEY}
  basicAuth { username = ${BASIC_USER}, password = ${BASIC_PASSWORD} }
}
```

Note that the credential prefix is derived from the **prefix**, not from the per-client
lower-camel path — credentials are shared across every API generated from the spec, while
`url` and timeouts are per API class. Setting `securityConfigPrefix` explicitly avoids having to
reason about the fallback at all.

Every generated credential field is `@Nullable`. A missing value does not fail at startup; it
produces a provider that returns `null`, and the request goes out unauthenticated.

## Multiple schemes on one operation { #multiple }

The generator groups each distinct **security requirement** into its own tag and interceptor. For
an operation allowing `apiKeyAuth` OR `anotherApiKeyAuth`, it emits a combined marker
`ApiSecurity.ApiKeyAuth_AnotherApiKeyAuth` and an interceptor that injects both providers by tag
and tries them in turn. Requirements listing several schemes together (AND) produce names joined
with `And`, e.g. `ApiSecurity.Sec1AndSec2`; an operation that also permits anonymous access gets an
`_Anonymous` suffix.

`primaryAuth` names the scheme to prefer when several apply. `useSecurityDeclarationOrder = true`
makes the generator derive tags and try providers in the contract's declaration order instead of a
normalised order — use it when the order in the spec is meaningful.

## `authAsMethodArgument` { #auth-arg }

With `authAsMethodArgument: true`, the credential becomes a generated method parameter instead of
being applied by an interceptor:

```java
// authAsMethodArgument = false (default) — interceptor supplies the header
PetsApiResponses.ListPetsApiResponse listPets(@Query("limit") @Nullable Integer limit);

// authAsMethodArgument = true — caller supplies it per call
PetsApiResponses.ListPetsApiResponse listPets(
        @Header("X-API-KEY") @Nullable String ApiKeyAuth,
        @Query("limit") @Nullable Integer limit);
```

The parameter name is the security scheme name and its location follows the scheme (query, header,
cookie, or the `Authorization` header for `http` / `oauth2` / `openIdConnect`). No interceptor is
involved, so for an `Authorization` argument the caller passes the full header value, scheme
included (`"Bearer " + token`). Use it when the
credential varies per call — a per-user token, for instance — rather than per client instance. A
scheme whose location cannot be mapped to a parameter fails generation with a message naming the
operation and the scheme.

If the contract also declares an explicit `Authorization` header parameter, generation fails with a
name clash; rename the parameter or turn the option off.

## Overriding a generated provider { #overriding }

Every generated provider and interceptor is a `@DefaultComponent`, so declaring your own component
with the same type and tag replaces it — no generator option needed:

```java
@Component
@Tag(ApiSecurity.ApiKeyAuth.class)
public final class RotatingApiKeyProvider implements HttpClientTokenProvider {

    private final KeyVault vault;

    public RotatingApiKeyProvider(KeyVault vault) {
        this.vault = vault;
    }

    @Override
    public String getToken(HttpClientRequest request) {
        return vault.current();
    }
}
```

This is the right hook for tokens that rotate, are fetched over the network, or depend on the
outgoing request.

## Hand-wiring interceptors without securitySchemes { #manual }

If the contract declares no `securitySchemes` — or you want auth the contract does not describe —
attach a stock interceptor through the generator's `extensions` option, keyed by OpenAPI tag:

```groovy
configOptions = [
        mode              : "java-client",
        clientConfigPrefix: "httpClient.pet",
        extensions        : """
        {
          "tags": {
            "pet": { "interceptorType": "com.example.PetAuthInterceptor" }
          }
        }
        """,
]
```

Kora ships three ready-made client interceptors in
`io.koraframework.http.client.common.interceptor`:

| Interceptor | Constructor | Effect |
|---|---|---|
| `ApiKeyHttpClientInterceptor` | `(ApiKeyLocation location, String parameterName, String secret)` or `(ApiKeyLocation, String parameterName, HttpClientTokenProvider)` | header, query param or cookie (appended to an existing `Cookie` header); `ApiKeyLocation` is a nested enum with `HEADER`, `QUERY`, `COOKIE` |
| `BasicAuthHttpClientInterceptor` | `(String username, String password)` or `(HttpClientTokenProvider)` | `Authorization: Basic <base64>` |
| `BearerAuthHttpClientInterceptor` | `(String token)` or `(HttpClientTokenProvider)` | `Authorization: Bearer <token>` |

All three leave the request untouched when the value is `null` or blank, so a provider may return
`null` to mean "no credential for this call".

```java
@Module
public interface ApiKeyAuthModule {

    @ConfigSource("openapiAuth.apiKeyAuth")
    interface ApiKeyAuthConfig {
        String apiKey();
    }

    default ApiKeyHttpClientInterceptor apiKeyInterceptor(ApiKeyAuthConfig config) {
        return new ApiKeyHttpClientInterceptor(
                ApiKeyHttpClientInterceptor.ApiKeyLocation.HEADER, "X-API-KEY", config.apiKey());
    }
}
```

You cannot put `@InterceptWith` on a generated interface by hand — it is regenerated on every
build. Go through `extensions`, or hand-write the client (`kora-http-client`).

## Migrating from Kora 1.x { #migration }

| Kora 1.x | Kora 2.x |
|---|---|
| `ru.tinkoff.kora.http.client.common.auth.HttpClientTokenProvider` | `io.koraframework.http.client.common.auth.HttpClientTokenProvider` |
| `CompletionStage<String> getToken(request)` | `@Nullable String getToken(request)` — synchronous |
| `@Tag(ApiSecurity.SecurityRequirementTag1.class)` | `@Tag(ApiSecurity.<SchemeName>.class)` |
| `ApiKeyLocation` as a top-level enum | nested: `ApiKeyHttpClientInterceptor.ApiKeyLocation` |
| `configOptions.authAllowMultiple` | removed — multi-scheme interceptors are generated unconditionally |
| `configOptions.interceptors` | `configOptions.extensions` (`interceptorType` / `interceptorTag`) |

## Troubleshooting { #troubleshooting }

| Symptom | Cause / fix |
|---|---|
| `No component found for dependency: HttpClientTokenProvider` with a scheme tag | A `bearer` or `oauth2` scheme has no application-supplied provider — add one under `@Tag(ApiSecurity.<Scheme>.class)` |
| Request goes out with the wrong credential | Several schemes apply and an unused one returns a non-null token; make it return `null`, or set `primaryAuth` |
| Server sees `Authorization: Bearer Bearer …` | Your bearer/oauth2 provider returns the prefixed value; return the bare token, the generated interceptor adds `Bearer ` |
| Requests unauthenticated, no error anywhere | Credential config path wrong or unset — every generated credential is `@Nullable`, so a missing value yields a `null` token |
| `Multiple components match` on a provider | Your `@Component` and the generated one collide — the generated one is `@DefaultComponent`, so match its type *and* tag exactly rather than adding a second binding |
| Provider never called | The interceptor is bound by tag; a hand-written provider tagged `SecurityRequirementTagN` (1.x) is never resolved |
| Generation fails naming an operation and a scheme | `authAsMethodArgument` cannot map that scheme's location to a parameter, or an explicit `Authorization` header parameter clashes |

---

## Related references

- [openapi-codegen-reference.md](openapi-codegen-reference.md) — `configOptions`, config-path
  derivation, `extensions`, generated artifacts
