# Manual Auth Reference (Kora 2.0, no OpenAPI contract)

Authenticating `@HttpController` endpoints without a generated `ApiSecurity`. Everything here
mirrors what the OpenAPI generator does internally, so the two paths stay consistent.

## Contents

- [The interceptor contract](#the-interceptor-contract)
- [Publishing the principal](#publishing-the-principal)
- [Scoping an interceptor](#scoping-an-interceptor)
- [Interceptor ordering](#interceptor-ordering)
- [Reading credentials](#reading-credentials)
- [401 vs 403](#401-vs-403)
- [A global error interceptor](#a-global-error-interceptor)
- [HttpServerRequestMapper and @Mapping](#httpserverrequestmapper-and-mapping)
- [Kotlin notes](#kotlin-notes)
- [Testing](#testing)

---

## The interceptor contract

```java
package io.koraframework.http.server.common.interceptor;

public interface HttpServerInterceptor {

    HttpServerResponse intercept(HttpServerRequest request, InterceptChain chain) throws Exception;

    interface InterceptChain {
        HttpServerResponse process(HttpServerRequest request) throws Exception;
    }

    static HttpServerInterceptor noop() { … }
}
```

Synchronous, and there is **no `Context` parameter** — `Context` was removed from Kora 2.0
entirely. Any 1.x interceptor of the shape
`CompletionStage<HttpServerResponse> intercept(Context, HttpServerRequest, InterceptChain)` must be
rewritten, not merely re-imported.

```java
import io.koraframework.common.annotation.Component;
import io.koraframework.http.server.common.interceptor.HttpServerInterceptor;
import io.koraframework.http.server.common.request.HttpServerRequest;
import io.koraframework.http.server.common.response.HttpServerResponse;
import io.koraframework.http.server.common.response.HttpServerResponseException;

@Component
public final class ApiKeyInterceptor implements HttpServerInterceptor {

    private final AuthConfig config;

    public ApiKeyInterceptor(AuthConfig config) {
        this.config = config;
    }

    @Override
    public HttpServerResponse intercept(HttpServerRequest request, InterceptChain chain) throws Exception {
        var key = request.headers().getFirst("x-api-key");
        if (key == null || !this.config.apiKey().equals(key)) {
            throw HttpServerResponseException.of(401, "Unauthorized");
        }
        return chain.process(request);
    }
}
```

Rejecting by `return HttpServerResponse.of(401, HttpBody.plaintext("Unauthorized"))` is equally
valid. Throwing `HttpServerResponseException` is usually better: it is itself an
`HttpServerResponse`, so the Undertow handler sends it verbatim, and an outer interceptor can catch
it and re-render it.

**Never throw a bare `SecurityException`.** That type appears in no Kora 2.0 source file. The
Undertow handler converts any throwable that is *not* an `HttpServerResponse` into **500** with the
exception's message as the plaintext body — a leaked internal message dressed up as a server fault.

---

## Publishing the principal

`Context` is gone; the replacement is a `ScopedValue` on `Principal`:

```java
public interface Principal {
    ScopedValue<Principal> VALUE = ScopedValue.newInstance();

    @Nullable static Principal current() { … }

    static <T, X extends Throwable> T with(Principal principal, ScopedValue.CallableOp<T, X> op) throws X { … }
}
```

Wrap the rest of the chain so handlers can read it:

```java
public record ApiKeyPrincipal(String clientId) implements Principal {}

@Override
public HttpServerResponse intercept(HttpServerRequest request, InterceptChain chain) throws Exception {
    var key = request.headers().getFirst("x-api-key");
    if (key == null || !this.config.apiKey().equals(key)) {
        throw HttpServerResponseException.of(401, "Unauthorized");
    }
    return Principal.with(new ApiKeyPrincipal(key), () -> chain.process(request));
}
```

```java
@HttpRoute(method = HttpMethod.GET, path = "/me")
public String me() {
    var principal = (ApiKeyPrincipal) Principal.current();
    if (principal == null) {
        throw HttpServerResponseException.of(401, "Unauthorized");
    }
    return principal.clientId();
}
```

The binding lasts exactly as long as the `chain.process(request)` call. It is visible on the request
thread and on threads forked from it inside a `StructuredTaskScope`; it is **not** visible on an
arbitrary executor you submit to. Capture the principal into a local before handing work off.

---

## Scoping an interceptor

| Scope | How | Notes |
|---|---|---|
| One route | `@InterceptWith(ApiKeyInterceptor.class)` on the `@HttpRoute` method | `io.koraframework.http.common.annotation.InterceptWith` |
| One controller | `@InterceptWith(ApiKeyInterceptor.class)` on the `@HttpController` class | applies to every route in it |
| Every controller | `@Tag(HttpServer.class)` on the interceptor `@Component` | `io.koraframework.http.server.common.HttpServer` |

```java
@Tag(HttpServer.class)
@Component
public final class GlobalAuthInterceptor implements HttpServerInterceptor { … }
```

> **The tag changed in 2.0 and the old one fails silently.** `HttpServerModule` still exists, so
> `@Tag(HttpServerModule.class)` compiles — but the router asks for
> `@Tag(HttpServer.class) All<HttpServerInterceptor>`, so a mis-tagged interceptor is simply never
> invoked. For an auth interceptor that means **authentication disappears with no error, no warning
> and no log line**. A compile is not evidence; only a request that gets `401` is.

`@InterceptWith` also takes a `tag` attribute (`Class<?> tag() default Tag.class`) for selecting a
tagged implementation of an interceptor interface — that is how the generated controller references
`@InterceptWith(value = HttpServerInterceptor.class, tag = ApiSecurity.ApiKeyAuth.class)`.

---

## Interceptor ordering

Two independent layers, and the rules differ:

**Per-route (`@InterceptWith`)** — controller-level annotations first, then method-level ones, in
declaration order; the **first is outermost**. On a generated controller the security interceptor is
emitted first, so anything added through the OpenAPI `interceptors` option nests *inside* it and
cannot observe the `401` it throws.

**Global (`@Tag(HttpServer.class)`)** — all of them wrap the whole routed invocation, so they are
outside every `@InterceptWith`. Unlike Kora 1.x, **many are allowed**; the router sorts them by
**simple class name** and winds the chain so that the **alphabetically last name runs outermost**.
Do not rely on declaration order, and if one interceptor must see another's exceptions, make its
class name sort later.

---

## Reading credentials

There is no request-attribute bag and no `request.getAttribute(...)`.

```java
String authorization = request.headers().getFirst("authorization");     // header
List<String> keys    = request.queryParams().get("api_key");            // query
String session       = request.cookies().stream()                       // cookie
        .filter(c -> "SESSION".equals(c.name()))
        .map(Cookie::value)
        .findFirst()
        .orElse(null);
```

Header lookup is case-insensitive on the wire, but pass the name in the form your codebase uses
consistently. Strip scheme prefixes yourself:

```java
if (authorization != null && authorization.startsWith("Bearer ")) {
    var token = authorization.substring("Bearer ".length());
    …
}
```

---

## 401 vs 403

- **401 Unauthorized** — no credentials, or the credentials are invalid. Authentication failed.
- **403 Forbidden** — the caller is authenticated but lacks the required role/scope.

A hand-written interceptor chooses for itself. The OpenAPI-generated security interceptor answers
`401` when no alternative authenticated, and `403 Forbidden` when an oauth2/openIdConnect extractor
returned a principal but a scope the contract requires is missing. Any other authorization rule
(roles, ownership) is a `403` you throw from the delegate after `Principal.current()`.

```java
throw HttpServerResponseException.of(401, "Unauthorized");
throw HttpServerResponseException.of(403, "Required scope: pets:write");
throw HttpServerResponseException.of(401, "Unauthorized", HttpHeaders.of("www-authenticate", "Bearer"));
```

`HttpServerResponseException` exposes `.code()`, `.headers()` and `.body()`, and its static factories
build a `text/plain;charset=utf-8` body.

---

## A global error interceptor

The single place that can re-render every auth failure, including the generated `401`:

```java
import io.koraframework.common.annotation.Component;
import io.koraframework.common.annotation.Tag;
import io.koraframework.http.common.body.HttpBody;
import io.koraframework.http.server.common.HttpServer;
import io.koraframework.http.server.common.interceptor.HttpServerInterceptor;
import io.koraframework.http.server.common.request.HttpServerRequest;
import io.koraframework.http.server.common.response.HttpServerResponse;
import io.koraframework.http.server.common.response.HttpServerResponseException;
import io.koraframework.json.common.JsonWriter;

@Tag(HttpServer.class)
@Component
public final class HttpErrorInterceptor implements HttpServerInterceptor {

    private final JsonWriter<ErrorResponse> writer;

    public HttpErrorInterceptor(JsonWriter<ErrorResponse> writer) {
        this.writer = writer;
    }

    @Override
    public HttpServerResponse intercept(HttpServerRequest request, InterceptChain chain) throws Exception {
        try {
            return chain.process(request);
        } catch (HttpServerResponseException e) {
            return json(e.code(), e.getMessage());
        }
    }

    private HttpServerResponse json(int code, String message) {
        return HttpServerResponse.of(code, HttpBody.json(this.writer.toByteArray(new ErrorResponse(message))));
    }
}
```

Catch `HttpServerResponseException` narrowly. Swallowing every `Exception` here turns genuine bugs
into tidy JSON and hides them from your telemetry; let anything you do not recognise propagate.

---

## HttpServerRequestMapper and @Mapping

When you want request-derived data as a typed method argument rather than a principal:

```java
package io.koraframework.http.server.common.request;

public interface HttpServerRequestMapper<T> extends Mapping.MappingFunction {
    @Nullable
    T apply(HttpServerRequest request) throws Exception;
}
```

```java
@Component
@HttpController
public final class MeController {

    public record Caller(String userId) {}

    public static final class CallerMapper implements HttpServerRequestMapper<Caller> {
        @Override
        public Caller apply(HttpServerRequest request) {
            var userId = request.headers().getFirst("x-user-id");
            if (userId == null) {
                throw HttpServerResponseException.of(401, "Missing x-user-id");
            }
            return new Caller(userId);
        }
    }

    @HttpRoute(method = HttpMethod.GET, path = "/me")
    public String me(@Mapping(CallerMapper.class) Caller caller) {
        return caller.userId();
    }
}
```

**Whether the mapper needs `@Component` is decided by its shape, not by taste.** The processor
instantiates a `@Mapping` mapper inline (`new CallerMapper()`) only when **all three** hold:

1. the class is `final` (Kotlin: not `open`),
2. it has a single public no-argument constructor,
3. the `@Mapping` carries no `@Tag`.

Otherwise the mapper becomes a constructor parameter of the generated handler and must exist in the
graph — so it needs `@Component` (or a module factory method).

| Shape | `@Component`? | If you get it wrong |
|---|---|---|
| `final`, no-arg ctor, untagged | **no** | adding it → `Multiple components match dependency` |
| has constructor dependencies | **yes** | omitting it → `No component found for dependency` |
| tagged via `@Mapping` + `@Tag` | **yes** | omitting it → `No component found for dependency` |
| non-`final` / `open`, even with a no-arg ctor | **yes** | this one is easy to miss in Java — Kotlin classes are final by default, Java ones are not |

Prefer an interceptor plus `Principal.current()` for authentication itself; a mapper is the right
tool for non-security request context that a handler wants as an argument.

---

## Kotlin notes

```kotlin
@Component
class ApiKeyInterceptor(
    private val config: AuthConfig
) : HttpServerInterceptor {

    override fun intercept(
        request: HttpServerRequest,
        chain: HttpServerInterceptor.InterceptChain
    ): HttpServerResponse {
        val key = request.headers().getFirst("x-api-key")
            ?: throw HttpServerResponseException.of(401, "Unauthorized")
        if (config.apiKey() != key) {
            throw HttpServerResponseException.of(401, "Unauthorized")
        }
        return Principal.with<HttpServerResponse, RuntimeException>(ApiKeyPrincipal(key)) {
            chain.process(request)
        }
    }
}
```

- The nested chain type is spelled `HttpServerInterceptor.InterceptChain` in Kotlin.
- `Principal.with` is `<T, X : Throwable>`; `X` cannot be inferred from a lambda that throws nothing,
  so pass both type arguments explicitly — this is exactly what the generated Kotlin does.
- Kora contracts are `@NullMarked`. A Kotlin override must match the contract's nullability exactly:
  `HttpServerRequestMapper<T>.apply` returns `T?`, and
  `HttpServerPrincipalExtractor<T, P>.extract(request, token: T?): P?`. A mismatch reports
  `'apply' overrides nothing` / `'extract' overrides nothing`, which never mentions nullability.

---

## Testing

An interceptor is a plain object; hand it a chain lambda.

```java
@Test
void rejectsMissingKey() {
    var interceptor = new ApiKeyInterceptor(() -> "expected");
    var request = mock(HttpServerRequest.class);
    when(request.headers()).thenReturn(HttpHeaders.of());

    var e = assertThrows(HttpServerResponseException.class,
            () -> interceptor.intercept(request, r -> HttpServerResponse.of(200)));
    assertEquals(401, e.code());
}
```

A unit test cannot catch a wrong `@Tag` — that failure lives in the graph, not in the class. Add at
least one `@KoraAppTest` that sends an unauthenticated request and asserts `401`; it is the only
thing that distinguishes "auth works" from "auth silently never ran". See
[kora-testing-junit-java](../../kora-testing-junit-java/SKILL.md),
[kora-testing-junit-kotlin](../../kora-testing-junit-kotlin/SKILL.md) and
[kora-testing-blackbox](../../kora-testing-blackbox/SKILL.md).

For the full interceptor and controller model see
[kora-http-server](../../kora-http-server/SKILL.md).
