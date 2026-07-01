---
name: kora-http-server
description: "Builds Kora HTTP server controllers on the Undertow transport — @HttpController, @HttpRoute, parameter binding (@Path/@Query/@Header/@Cookie), @Json bodies, HttpServerResponse / HttpResponseEntity responses, HttpServerResponseException errors, and HttpServerInterceptor (global via @Tag(HttpServerModule.class) or per-route via @InterceptWith). Use when building REST endpoints, mapping requests to typed methods, returning custom status codes/headers, handling errors centrally, or wiring UndertowHttpServerModule and httpServer ports/telemetry."
---

# Kora HTTP Server

Declarative HTTP request handlers compiled (not reflected) into a router. Annotate a `@Component` `@HttpController` with `@HttpRoute` methods; Kora generates the handler/router at build time via the annotation processor.

The base path lives on `@HttpRoute`, not on `@HttpController` — `@HttpController` takes no path argument.

---

## Quick Start

### 1. Dependencies (Java)

```groovy
configurations {
    koraBom
    annotationProcessor.extendsFrom(koraBom)
    implementation.extendsFrom(koraBom)
}

dependencies {
    koraBom platform("ru.tinkoff.kora:kora-parent:1.2.17")
    annotationProcessor "ru.tinkoff.kora:annotation-processors"  // mandatory

    implementation "ru.tinkoff.kora:http-server-undertow"
    implementation "ru.tinkoff.kora:json-module"
    implementation "ru.tinkoff.kora:config-hocon"
    implementation "ru.tinkoff.kora:logging-logback"
}
```

Kotlin uses KSP instead: `ksp "ru.tinkoff.kora:symbol-processors"`. All `ru.tinkoff.kora:*`
artifacts inherit their version from the BOM — never pin them individually.

### 2. Application graph

```java
@KoraApp
public interface Application extends
        HoconConfigModule,
        JsonModule,
        LogbackModule,
        UndertowHttpServerModule {

    static void main(String[] args) {
        KoraApplication.run(ApplicationGraph::graph);
    }
}
```

### 3. Controller

```java
@Component
@HttpController
public final class HelloController {

    @HttpRoute(method = HttpMethod.GET, path = "/hello/{name}")
    public String hello(@Path String name) {
        return "Hello " + name;   // 200 OK, text/plain
    }
}
```

### 4. Config (`application.conf`)

```hocon
httpServer {
  publicApiHttpPort = 8080   // application traffic
  privateApiHttpPort = 8085  // metrics / probes
  telemetry.logging.enabled = true
}
```

---

## CRUD controller

Adapted from `kora-java-guide-http-server-app`. JSON requires `@Json` on the method **and** on the
body parameter; optional inputs are marked `@Nullable` (Kotlin: a nullable type).

```java
@Component
@HttpController
public final class UserController {

    private final UserService userService;

    public UserController(UserService userService) {
        this.userService = userService;
    }

    @HttpRoute(method = HttpMethod.GET, path = "/users/{userId}")
    @Json
    public UserResponse getUser(@Path String userId) {
        return userService.getUser(userId)
                .orElseThrow(() -> HttpServerResponseException.of(404, "User not found: " + userId));
    }

    @HttpRoute(method = HttpMethod.GET, path = "/users")
    @Json
    public List<UserResponse> getUsers(@Nullable @Query("page") Integer page,
                                       @Nullable @Query("size") Integer size) {
        return userService.getUsers(page == null ? 0 : page, size == null ? 10 : size);
    }

    @HttpRoute(method = HttpMethod.POST, path = "/users")
    @Json
    public HttpResponseEntity<UserResponse> createUser(@Json UserRequest request) {
        UserResponse user = userService.createUser(request);
        return HttpResponseEntity.of(201, HttpHeaders.of("Location", "/users/" + user.id()), user);
    }

    @HttpRoute(method = HttpMethod.DELETE, path = "/users/{userId}")
    public HttpServerResponse deleteUser(@Path String userId) {
        userService.deleteUser(userId);
        return HttpServerResponse.of(204, HttpBody.empty());
    }
}
```

DTOs are plain records annotated `@Json`:
`UserRequest(String email, String name)`, `UserResponse(String id, String email, String name)`.

---

## Key annotations

| Annotation | Level | Purpose |
|---|---|---|
| `@HttpController` | class | Marks an HTTP controller (no path argument) |
| `@HttpRoute(method, path)` | method | Binds an `HttpMethod` + path to a handler |
| `@Path` | parameter | Path segment `{name}`; name defaults to the argument name |
| `@Query` | parameter | Query parameter; name defaults to the argument name |
| `@Header` | parameter | Request header value |
| `@Cookie` | parameter | Cookie value |
| `@Json` | method / parameter | JSON serialization for the body |
| `@Mapping(X.class)` | parameter / method | Custom request/response mapper |
| `@InterceptWith(X.class)` | method / class | Apply an interceptor to a route or controller |
| `@Nullable` | parameter | Marks a request parameter optional (Java) |

`HttpMethod` values: `GET`, `POST`, `PUT`, `DELETE`, `PATCH`, `OPTIONS`, `HEAD`, `TRACE`.

---

## Response types

| Return type | Status | Notes |
|---|---|---|
| `String` / `byte[]` / `ByteBuffer` | 200 | Body written directly with the matching content type |
| `T` + `@Json` on method | 200 | Body serialized to JSON |
| `HttpResponseEntity<T>` + `@Json` | any | Body + custom status code + headers |
| `HttpServerResponse` | any | Full control over status, headers and raw body |

```java
// JSON body with custom status and headers
return HttpResponseEntity.of(201, HttpHeaders.of("Location", "/users/" + id), user);

// Full manual control
return HttpServerResponse.of(200, HttpHeaders.of("X-Trace", traceId), HttpBody.plaintext("OK"));
return HttpServerResponse.of(204, HttpBody.empty());
```

Async signatures are supported: Java `CompletionStage<T>` / `Mono<T>`, Kotlin `suspend fun`.

See [Response Types](references/response-types-reference.md) for `HttpBody`, `HttpHeaders`,
and custom `HttpServerResponseMapper`.

---

## Error handling

Throw `HttpServerResponseException.of(code, message)` from a handler to short-circuit with a
status code. Centralize cross-cutting error translation in a global interceptor (there is no
dedicated "exception handler" type — error handling is an interceptor concern).

```java
@HttpRoute(method = HttpMethod.GET, path = "/users/{id}")
@Json
public UserResponse get(@Path String id) {
    return userService.find(id)
        .orElseThrow(() -> HttpServerResponseException.of(404, "Not found: " + id));
}
```

See [Error Handling](references/error-handling-reference.md) for the global error interceptor.

---

## Interceptors

`HttpServerInterceptor.intercept(Context, HttpServerRequest, InterceptChain)` returns
`CompletionStage<HttpServerResponse>`. Call `chain.process(context, request)` to continue the
chain; wrap it with `.whenComplete(...)` / `.exceptionally(...)` for after/error logic.

```java
@Tag(HttpServerModule.class)   // makes it global (only one global interceptor allowed)
@Component
public final class LoggingInterceptor implements HttpServerInterceptor {

    private static final Logger log = LoggerFactory.getLogger(LoggingInterceptor.class);

    @Override
    public CompletionStage<HttpServerResponse> intercept(Context context,
                                                         HttpServerRequest request,
                                                         InterceptChain chain) throws Exception {
        long started = System.nanoTime();
        return chain.process(context, request).whenComplete((response, error) -> {
            long ms = (System.nanoTime() - started) / 1_000_000;
            int code = response != null ? response.code() : 500;
            log.info("{} {} -> {} ({} ms)", request.method(), request.path(), code, ms);
        });
    }
}
```

Scopes:
- **Global** — one interceptor tagged `@Tag(HttpServerModule.class)`, runs for every route.
- **Controller** — `@InterceptWith(X.class)` on the controller class.
- **Method** — `@InterceptWith(X.class)` on a single `@HttpRoute` method.

Order: global -> controller -> method -> handler.

See [Interceptors](references/interceptors-reference.md).

---

## Authentication & Principal

For custom authentication in Kora 1.2.x, use the interceptor pattern — **do NOT** use `Principal` as a controller parameter (not auto-wired in 1.2.x, causes 401→400 downgrade).

**Pattern:** Global `@Tag(HttpServerModule)` interceptor → store principal in `Context` → read via `Principal.current()` in controller.

See [Authentication & Principal](references/authentication-reference.md) for complete guide with examples.

---

## Context Propagation

Pass computed values from interceptor to controller (auth session, user profile, request metadata) via `ru.tinkoff.kora.common.Context`:

1. Define `Context.Key<T>` static singleton
2. Interceptor sets value **BEFORE** `chain.process()`
3. Controller reads with null-check

See [Context Propagation](references/context-propagation-reference.md) for complete guide.

---

## Configuration

```hocon
httpServer {
  publicApiHttpPort = 8080
  privateApiHttpPort = 8085
  privateApiHttpMetricsPath  = "/metrics"
  privateApiHttpReadinessPath = "/system/readiness"
  privateApiHttpLivenessPath  = "/system/liveness"
  virtualThreadsEnabled = false   // true requires Java 21+
  maxRequestBodySize = "256MiB"
  telemetry {
    logging { enabled = false }
    metrics { enabled = true }
    tracing { enabled = true }
  }
}
```

Keep `publicApiHttpPort` (traffic) and `privateApiHttpPort` (metrics/probes) separate.
See [Configuration](references/configuration-reference.md) for every key and env substitution.

---

## References

| Reference | Covers |
|---|---|
| [Controller & Routing](references/controller-routing-reference.md) | `@HttpController`, `@HttpRoute`, path composition |
| [Request Mapping](references/request-mapping-reference.md) | `@Path`, `@Query`, `@Header`, `@Cookie`, `@Json`, bodies, `@Mapping` |
| [Response Types](references/response-types-reference.md) | `HttpServerResponse`, `HttpResponseEntity`, `HttpBody`, mappers |
| [Interceptors](references/interceptors-reference.md) | `HttpServerInterceptor`, `@InterceptWith`, `@Tag`, order |
| [Error Handling](references/error-handling-reference.md) | `HttpServerResponseException`, global error interceptor |
| [Configuration](references/configuration-reference.md) | `httpServer` keys, ports, telemetry, env vars |
| [Authentication & Principal](references/authentication-reference.md) | Custom auth via interceptor, `Principal` pattern (Kora 1.2.x) |
| [Context Propagation](references/context-propagation-reference.md) | Passing values from interceptor to controller via `Context` |

## Assets

| Template | Purpose |
|---|---|
| [UserController.java](assets/templates/java/UserController.java.template) | CRUD controller (Java) |
| [UserController.kt](assets/templates/kotlin/UserController.kt.template) | CRUD controller (Kotlin) |
| [LoggingInterceptor.java](assets/templates/java/LoggingInterceptor.java.template) | Global logging interceptor (Java) |
| [LoggingInterceptor.kt](assets/templates/kotlin/LoggingInterceptor.kt.template) | Global logging interceptor (Kotlin) |
| [ErrorInterceptor.java](assets/templates/java/ErrorInterceptor.java.template) | Global error-to-JSON interceptor (Java) |

---

## Pitfalls

| Symptom | Fix |
|---|---|
| 404 on a valid URL | The `{var}` in `@HttpRoute path` must have a matching `@Path` argument; base path lives on `@HttpRoute`, not `@HttpController` |
| Request body is null / not parsed | Add `@Json` on the method and on the body parameter, and depend on `json-module` |
| `@HttpController("/api")` does not compile | `@HttpController` takes no value; put the prefix in each `@HttpRoute(path = "/api/...")` |
| Required parameter throws when missing | Mark it `@Nullable` (Java) or use a nullable type (Kotlin) |
| Global interceptor never runs | Add `@Tag(HttpServerModule.class)` and `@Component`; only one global interceptor is allowed |
| Looking for `HttpServerResponse.ok()` builder | It does not exist — use `HttpServerResponse.of(...)` / `HttpResponseEntity.of(...)` |
| Principal as controller parameter returns 400 | Kora 1.2.x doesn't auto-bridge `HttpServerPrincipalExtractor` — use interceptor + `Context` pattern (see [Authentication](references/authentication-reference.md)) |
| Context.get() returns null in controller | Value must be set in interceptor BEFORE `chain.process()`; add null-check (see [Context Propagation](references/context-propagation-reference.md)) |

---

## Evals

Self-check rubric: [evals/evals.json](evals/evals.json).
