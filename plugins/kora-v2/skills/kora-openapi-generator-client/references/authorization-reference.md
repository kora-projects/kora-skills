# OpenAPI Client Authorization Reference

**Source:** `.kora-agent/kora-docs/mkdocs/docs/en/documentation/openapi-codegen.md`,
`.kora-agent/kora-docs/mkdocs/docs/en/documentation/http-client.md` (Authorization section)
**Example:** `.kora-agent/kora-examples/examples/java/kora-java-openapi-generator-http-client`

## Contents

- [Two ways to authorize a generated client](#two-ways)
- [Generator-driven auth (securitySchemes)](#generator-driven)
- [Manual interceptors](#manual-interceptors)
  - [ApiKey](#apikey)
  - [Basic](#basic)
  - [Bearer / OAuth](#bearer)
- [Attaching an interceptor](#attaching)
- [Troubleshooting](#troubleshooting)

---

## Two ways to authorize a generated client { #two-ways }

A generated client is a standard Kora `@HttpClient`. Authorization is applied
through HTTP **client interceptors** (`HttpClientInterceptor`). There are two
ways to wire them:

1. **Generator-driven** — when the OpenAPI spec declares `securitySchemes`, the
   generator emits the interceptor wiring. You select the scheme with
   `primaryAuth` and point credentials at config via `securityConfigPrefix`.
2. **Manual** — you declare the interceptor as a `@Module` component and attach
   it to the generated `*Api` (or specific methods) with `@InterceptWith`.

> All auth here is **client-side** (outbound requests). `HttpServerPrincipalExtractor`
> and `Principal` belong to the **server** generator — see `kora-openapi-generator-server`.

---

## Generator-driven auth (securitySchemes) { #generator-driven }

OpenAPI spec:

```yaml
components:
  securitySchemes:
    apiKeyAuth:
      type: apiKey
      in: header
      name: X-API-Key
```

Generator config:

```groovy
configOptions = [
    mode                : "java-client",
    clientConfigPrefix  : "httpClient.pet",
    primaryAuth         : "apiKeyAuth",   // scheme name; required only if multiple schemes exist
    securityConfigPrefix: "openapiAuth",  // config root for credentials
]
```

Credentials resolve from `<securityConfigPrefix>.<schemeName>`:

```hocon
openapiAuth.apiKeyAuth = ${API_KEY}
```

Relevant `configOptions`:

| Option | Meaning |
|--------|---------|
| `primaryAuth` | Which `securitySchemes` entry is the primary one when several are defined |
| `securityConfigPrefix` | Config prefix for Basic/ApiKey credentials; final path is `prefix + schemeName` (or just `schemeName` if omitted) |
| `authAsMethodArgument` | Pass authorization as a method argument instead of via interceptor (`true`/`false`) |
| `authAllowMultiple` | Generate interceptors for multi-authentication (`true`/`false`) |

---

## Manual interceptors { #manual-interceptors }

Kora ships ready-made client interceptors. Declare them in a `@Module` and attach
with `@InterceptWith`.

### ApiKey { #apikey }

```java
@Module
public interface ApiKeyAuthModule {

    @ConfigSource("openapiAuth.apiKeyAuth")
    interface ApiKeyAuthConfig {
        String apiKey();
    }

    default ApiKeyHttpClientInterceptor apiKeyAuther(ApiKeyAuthConfig config) {
        return new ApiKeyHttpClientInterceptor(ApiKeyLocation.HEADER, "X-API-KEY", config.apiKey());
    }
}
```

`ApiKeyLocation` selects where the key goes (e.g. `HEADER`).

### Basic { #basic }

```java
@Module
public interface BasicAuthModule {

    @ConfigSource("openapiAuth.basicAuth")
    interface BasicAuthConfig {
        String username();
        String password();
    }

    default BasicAuthHttpClientInterceptor basicAuther(BasicAuthConfig config) {
        return new BasicAuthHttpClientInterceptor(config.username(), config.password());
    }
}
```

### Bearer / OAuth { #bearer }

Bearer needs an `HttpClientTokenProvider` (or a constructor that takes a static token).
OAuth is wired the same way — supply your own `HttpClientTokenProvider`.

```java
public interface HttpClientTokenProvider {
    CompletionStage<String> getToken(HttpClientRequest request);
}

@Module
public interface BearerAuthModule {

    default BearerAuthHttpClientInterceptor bearerAuther(HttpClientTokenProvider tokenProvider) {
        return new BearerAuthHttpClientInterceptor(tokenProvider);
    }
}
```

---

## Attaching an interceptor { #attaching }

`@InterceptWith` goes on the generated `*Api` interface or individual methods.
Since the `*Api` is generated, the common path is to attach interceptors through
the generator `interceptors` config option (see
[openapi-codegen-reference.md](openapi-codegen-reference.md#interceptors)) keyed by
the OpenAPI tag. For a hand-written `@HttpClient`, attach directly:

```java
@HttpClient
public interface SomeClient {

    @InterceptWith(ApiKeyHttpClientInterceptor.class)
    @HttpRoute(method = HttpMethod.GET, path = "/hello/world")
    void hello();
}
```

---

## Troubleshooting { #troubleshooting }

| Problem | Solution |
|---------|----------|
| Interceptor not applied to generated client | Wire it via generator `interceptors` config option keyed by the OpenAPI tag, or set `primaryAuth`/`securityConfigPrefix` |
| Credentials not resolved | `securityConfigPrefix` + scheme name must match the config path; externalize via `${ENV_VAR}` |
| Multiple `securitySchemes`, wrong one used | Set `primaryAuth` to the scheme name; use `authAllowMultiple` for multi-auth |
| `BearerAuthHttpClientInterceptor` needs a token | Provide an `HttpClientTokenProvider` component or use the static-token constructor |
| Confusing with server `Principal` | `Principal`/`HttpServerPrincipalExtractor` are server-side; this skill is client-only |

---

## Related references

- [openapi-codegen-reference.md](openapi-codegen-reference.md) — generator configuration, interceptors, tags
