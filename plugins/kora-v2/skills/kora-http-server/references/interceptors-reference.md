# Interceptors Reference

`HttpServerInterceptor` lets you wrap request handling: logging, timing, security checks, CORS,
and error translation. The interceptor returns a `CompletionStage<HttpServerResponse>` and calls
`chain.process(context, request)` to continue.

## Contents

- [Interceptor interface](#interceptor-interface)
- [Scopes](#scopes)
- [Execution order](#execution-order)
- [After and error logic](#after-and-error-logic)
- [Pitfalls](#pitfalls)

---

## Interceptor interface

```java
import java.util.concurrent.CompletionStage;
import ru.tinkoff.kora.common.Component;
import ru.tinkoff.kora.common.Context;
import ru.tinkoff.kora.http.server.common.HttpServerInterceptor;
import ru.tinkoff.kora.http.server.common.HttpServerRequest;
import ru.tinkoff.kora.http.server.common.HttpServerResponse;

@Component
public final class LoggingInterceptor implements HttpServerInterceptor {

    @Override
    public CompletionStage<HttpServerResponse> intercept(Context context,
                                                         HttpServerRequest request,
                                                         InterceptChain chain) throws Exception {
        long started = System.nanoTime();
        return chain.process(context, request).whenComplete((response, error) -> {
            long ms = (System.nanoTime() - started) / 1_000_000;
            int code = response != null ? response.code() : 500;
            System.out.printf("%s %s -> %d (%d ms)%n", request.method(), request.path(), code, ms);
        });
    }
}
```

`InterceptChain` is the nested type `HttpServerInterceptor.InterceptChain` (referenced unqualified
inside an implementing class). `request.method()`, `request.path()`, and `request.headers()` give
access to request data; `response.code()` gives the resulting status.

---

## Scopes

| Scope | How to apply | Notes |
|---|---|---|
| Global | `@Tag(HttpServerModule.class)` + `@Component` on the interceptor | Runs for every route; only **one** global interceptor is allowed |
| Controller | `@InterceptWith(X.class)` on the controller class | Runs for every route in that controller |
| Method | `@InterceptWith(X.class)` on a single `@HttpRoute` method | Runs for that route only |

```java
// Global
@Tag(HttpServerModule.class)
@Component
public final class GlobalInterceptor implements HttpServerInterceptor { /* ... */ }

// Controller- or method-level
@Component
@HttpController
@InterceptWith(LoggingInterceptor.class)            // controller-level
public final class UserController {

    @InterceptWith(AuthInterceptor.class)           // method-level
    @HttpRoute(method = HttpMethod.POST, path = "/admin")
    public HttpServerResponse admin() { /* ... */ }
}
```

`@InterceptWith` references an interceptor type; that type may be a `@Component` (to receive
injected dependencies) or a plain nested class.

---

## Execution order

```
Global -> Controller -> Method -> Handler
```

Each interceptor must call `chain.process(context, request)` (and return its result) so the next
link runs.

---

## After and error logic

- Run logic **after** the handler by chaining `.whenComplete((response, error) -> ...)`.
- Translate exceptions by chaining `.exceptionally(throwable -> ...)` and returning an
  `HttpServerResponse`. See [Error Handling](error-handling-reference.md).

---

## Pitfalls

| Symptom | Fix |
|---|---|
| Global interceptor never runs | Add `@Tag(HttpServerModule.class)` and `@Component` |
| Request appears to hang / empty response | The interceptor must return `chain.process(...)`, not ignore it |
| Two global interceptors | Not allowed — merge them into one, or move one to controller/method scope |

**See also:** [Error Handling](error-handling-reference.md), [Controller & Routing](controller-routing-reference.md).
