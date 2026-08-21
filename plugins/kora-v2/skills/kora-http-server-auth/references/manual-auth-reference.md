# Manual Auth Reference (no OpenAPI)

Authenticate Kora HTTP endpoints without a generated `ApiSecurity` contract. Source of
truth: `.kora-agent/kora-docs/mkdocs/docs/en/documentation/http-server.md` (Interceptors,
Custom parameter / `HttpServerRequestMapper`).

## Contents

- [Two building blocks](#two-building-blocks)
- [Interceptor: validate and short-circuit](#interceptor-validate-and-short-circuit)
- [Request mapper: typed principal as an argument](#request-mapper-typed-principal-as-an-argument)
- [Reading credentials from the request](#reading-credentials-from-the-request)
- [401 vs 403](#401-vs-403)
- [Scoping interceptors](#scoping-interceptors)

---

## Two building blocks

| Need | Use |
|------|-----|
| Reject unauthenticated requests before the controller runs, uniformly | `HttpServerInterceptor` |
| Turn the request into a typed caller/principal object passed to the method | `HttpServerRequestMapper<T>` + `@Mapping` |

There is no thread-local current-user and no request-attribute bag in Kora. Pass
request-derived data as a typed `@Mapping` argument, or validate centrally in an
interceptor.

---

## Interceptor: validate and short-circuit

An interceptor implements `HttpServerInterceptor` and either calls `chain.process(...)`
to continue or returns an early `HttpServerResponse` to reject.

```java
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.CompletionStage;
import ru.tinkoff.kora.common.Component;
import ru.tinkoff.kora.common.Context;
import ru.tinkoff.kora.common.Tag;
import ru.tinkoff.kora.http.common.body.HttpBody;
import ru.tinkoff.kora.http.server.common.HttpServerInterceptor;
import ru.tinkoff.kora.http.server.common.HttpServerModule;
import ru.tinkoff.kora.http.server.common.HttpServerRequest;
import ru.tinkoff.kora.http.server.common.HttpServerResponse;

@Tag(HttpServerModule.class) // applies to every controller; at most one such interceptor
@Component
public final class ApiKeyInterceptor implements HttpServerInterceptor {

    private final String expectedKey;

    public ApiKeyInterceptor(AuthConfig config) {
        this.expectedKey = config.apiKey();
    }

    @Override
    public CompletionStage<HttpServerResponse> intercept(Context context, HttpServerRequest request, InterceptChain chain)
            throws Exception {
        var key = request.headers().getFirst("X-API-Key");
        if (key == null || !expectedKey.equals(key)) {
            return CompletableFuture.completedFuture(
                    HttpServerResponse.of(401, HttpBody.plaintext("Unauthorized")));
        }
        return chain.process(context, request);
    }
}
```

To scope to one controller or one method instead of globally, drop the
`@Tag(HttpServerModule.class)` and apply `@InterceptWith(ApiKeyInterceptor.class)` on the
controller class or the `@HttpRoute` method.

---

## Request mapper: typed principal as an argument

`HttpServerRequestMapper<T>` converts the request into any type, injected via `@Mapping`.
Throw to reject (combine with the error interceptor below to set the status code).

```java
import ru.tinkoff.kora.common.Mapping;
import ru.tinkoff.kora.common.Component;
import ru.tinkoff.kora.http.common.HttpMethod;
import ru.tinkoff.kora.http.server.common.HttpServerRequest;
import ru.tinkoff.kora.http.server.common.HttpServerRequestMapper;
import ru.tinkoff.kora.http.server.common.annotation.HttpController;
import ru.tinkoff.kora.http.server.common.annotation.HttpRoute;

@Component
@HttpController
public final class MeController {

    public record Caller(String userId) {}

    public static final class CallerMapper implements HttpServerRequestMapper<Caller> {
        @Override public Caller apply(HttpServerRequest request) {
            var userId = request.headers().getFirst("x-user-id");
            if (userId == null) {
                throw new SecurityException("Missing x-user-id");
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

---

## Reading credentials from the request

Use the header list API. There is no `request.getAttribute(...)` in Kora.

```java
String bearer = request.headers().getFirst("Authorization"); // e.g. "Bearer abc"
String apiKey = request.headers().getFirst("X-API-Key");
```

Parse the scheme prefix yourself:

```java
if (bearer != null && bearer.startsWith("Bearer ")) {
    String token = bearer.substring("Bearer ".length());
    // verify token ...
}
```

---

## 401 vs 403

- **401 Unauthorized** — no credentials, or credentials invalid (authentication failed).
- **403 Forbidden** — authenticated but lacking the required role/scope (authorization failed).

Return them with `HttpServerResponse.of(401|403, HttpBody.plaintext(...))`, or throw
`HttpServerResponseException.of(403, "...")` from a controller/delegate. Centralize the
exception-to-status mapping in an error `HttpServerInterceptor`:

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

---

## Scoping interceptors

| Scope | How |
|-------|-----|
| Single route | `@InterceptWith(MyInterceptor.class)` on the `@HttpRoute` method |
| Whole controller | `@InterceptWith(MyInterceptor.class)` on the `@HttpController` class |
| All controllers | `@Tag(HttpServerModule.class)` on the interceptor `@Component` (only one allowed) |

See [kora-http-server](../../kora-http-server/SKILL.md) for the full interceptor model.
