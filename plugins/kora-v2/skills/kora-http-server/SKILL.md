---
name: kora-http-server
description: "Kora 2.0 HTTP server on Undertow — @HttpController + @HttpRoute handlers generated at compile time, parameter binding with @Path/@Query/@Header/@Cookie from io.koraframework.http.common.annotation, @Json bodies, HttpServerResponse / HttpResponseEntity / HttpServerResponseException, and HttpServerInterceptor (global via @Tag(HttpServer.class), scoped via @InterceptWith). Covers the UndertowPublicHttpServerModule / UndertowSystemHttpServerModule split and the httpServer + httpServer.system config sections. Use when building REST endpoints on Kora 2.0, wiring ports and probes, or porting a Kora 1.x controller. For authentication see kora-http-server-auth; for outbound calls see kora-http-client."
license: Apache-2.0
metadata:
  kora-version: "2.x"
---

# Kora HTTP Server

> **Kora sub-skill — obey the [kora-v2 meta rules](../../SKILL.md) on every task:** **R0** ground the workspace on Kora 2.0 refs before starting (framework source at tag `2.0.0.RC2` + `kora-examples` at `migration/2.0` + Kora 2.0 docs at koraframework.io/v2, which trail the source; 1.x `kora-docs` pages are never an authority) · **R1** read this sub-skill before writing code · **R2** Kora 2.0 APIs only — no Spring/Micronaut/Quarkus, no Kora 1.x APIs, no invented annotations or config keys · **R3** journal any incorrect Kora usage. Add comments/Javadoc only if asked.

| | |
|---|---|
| **Artifact** | `io.koraframework:http-server-undertow` (BOM `io.koraframework:kora-bom`, `2.0.0.RC2`) |
| **Graph module** | `io.koraframework.http.server.undertow.UndertowPublicHttpServerModule` |
| **Processor** | `io.koraframework:annotation-processors` (Java) · `io.koraframework:symbol-processors` (KSP) |
| **Config sections** | `httpServer` (public) · `httpServer.system` (probes/metrics) · `httpServer.undertow` (transport) |
| **Execution model** | Synchronous handlers on virtual threads. No `CompletionStage`, no `Mono`/`Flux`, no `suspend` |

Handlers are generated at compile time. For each `@HttpController` the processor emits a
`<Controller>Module` `@Module` interface with one `HttpServerRequestHandler` factory method per
`@HttpRoute`, which the DI graph assembles into an `HttpServerRouter`. Nothing is reflective, and
nothing is discovered at runtime — a route that does not compile does not exist.

---

## Migrating from Kora 1.x — read this first

Five changes cause silent or confusing failures. Each is covered in depth in the linked reference.

| 1.x | 2.0 | If you skip it |
|---|---|---|
| `@Tag(HttpServerModule.class)` on a global interceptor | **`@Tag(HttpServer.class)`** | **Compiles clean, never runs.** `HttpServerModule` still exists so the annotation is legal, but nothing collects interceptors by that tag — the component is pruned from the graph without a warning. [Interceptors](references/interceptors-reference.md) |
| `httpServer.publicApiHttpPort` / `privateApiHttpPort` | **`httpServer.port`** / **`httpServer.system.port`** | **Starts green on the wrong ports.** A stale key is just an unknown HOCON key: ignored silently, so each server falls back to its own default (8080 public, 8085 system) and probes hit nothing. The startup log `HTTP Server <name> (Undertow) started on port <N> in …` (structured `port` marker) shows the port actually bound. [Configuration](references/configuration-reference.md) |
| `intercept(Context, request, chain)` → `CompletionStage` | **`intercept(request, chain)` → `HttpServerResponse`** | Compile error. `Context` no longer exists anywhere in Kora. [Interceptors](references/interceptors-reference.md) |
| `CompletionStage<T>` / `Mono<T>` / `suspend fun` handlers | plain synchronous return types | No reactive response mapper exists; KSP rejects `suspend` outright. [Response Types](references/response-types-reference.md) |
| `writer.toByteArrayUnchecked(v)` in a `try/catch (IOException)` | **`writer.toByteArray(v)`**, no catch | `error: exception IOException is never thrown in body of corresponding try statement`. [Error Handling](references/error-handling-reference.md) |

Every framework package moved from `ru.tinkoff.kora.*` to `io.koraframework.*`, and the HTTP
packages were also **re-split** — a blind group rename leaves imports that do not resolve. See
[Controller & Routing](references/controller-routing-reference.md#package-map).

---

## Quick start

### 1. Dependencies (Java)

```groovy
configurations {
    koraBom
    annotationProcessor.extendsFrom(koraBom)
    compileOnly.extendsFrom(koraBom)
    implementation.extendsFrom(koraBom)
}

dependencies {
    koraBom platform("io.koraframework:kora-bom:$koraVersion")   // koraVersion=2.0.0.RC2
    annotationProcessor "io.koraframework:annotation-processors" // mandatory

    implementation "io.koraframework:http-server-undertow"
    implementation "io.koraframework:json-common"
    implementation "io.koraframework:config-hocon"
    implementation "io.koraframework:logging-logback"
}
```

Kotlin replaces the processor with KSP:

```kotlin
implementation(platform("io.koraframework:kora-bom:${property("koraVersion")}"))
ksp("io.koraframework:symbol-processors:${property("koraVersion")}")
implementation("io.koraframework:http-server-undertow")
```

Java **25** is the floor — Kora 2.0 artifacts are class-file 69. Artifacts other than the BOM are
never versioned individually.

### 2. Application graph

```java
@KoraApp
public interface Application extends
        HoconConfigModule,
        LogbackModule,
        JsonModule,
        UndertowPublicHttpServerModule {

    static void main(String[] args) {
        KoraApplication.run(ApplicationGraph::graph);
    }
}
```

`UndertowPublicHttpServerModule` extends `UndertowSystemHttpServerModule`, so plugging in the
public module starts **both** servers: the application server on `httpServer.port` and the system
server (readiness, liveness, metrics) on `httpServer.system.port`. `UndertowHttpServerModule` from
1.x no longer exists.

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

`@HttpController` optionally takes a **path prefix** (`String value() default ""`), prepended to
every `@HttpRoute` path in the class. Leave it off and each route carries its full path.

### 4. Config (`application.conf`)

```hocon
httpServer {
  port = 8080
  system.port = 8085
  telemetry.logging.enabled = true   # off by default
}
```

---

## CRUD controller

JSON needs `@Json` on the method **and** on the body parameter. Optional inputs are `@Nullable`
(Java, JSpecify) or a nullable type (Kotlin).

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
        return userService.findById(userId)
                .orElseThrow(() -> HttpServerResponseException.of(404, "User not found: " + userId));
    }

    @HttpRoute(method = HttpMethod.GET, path = "/users")
    @Json
    public List<UserResponse> listUsers(@Nullable @Query Integer page,
                                        @Nullable @Query Integer size) {
        return userService.findAll(page == null ? 0 : page, size == null ? 10 : size);
    }

    @HttpRoute(method = HttpMethod.POST, path = "/users")
    @Json
    public HttpResponseEntity<UserResponse> createUser(@Json UserRequest request) {
        var created = userService.create(request);
        return HttpResponseEntity.of(201, HttpHeaders.of("Location", "/users/" + created.id()), created);
    }

    @HttpRoute(method = HttpMethod.DELETE, path = "/users/{userId}")
    public void deleteUser(@Path String userId) {
        userService.delete(userId);   // void -> 200 with an empty body, no mapper needed
    }
}
```

DTOs are plain records annotated `@Json`:
`UserRequest(String email, String name)`, `UserResponse(String id, String email, String name)`.

---

## Key annotations

| Annotation | Package | Level | Purpose |
|---|---|---|---|
| `@HttpController` | `io.koraframework.http.server.common.annotation` | class | Marks an HTTP controller (no path argument) |
| `@HttpRoute(method, path)` | `io.koraframework.http.common.annotation` | method | Binds an HTTP method + path to a handler |
| `@Path` | `io.koraframework.http.common.annotation` | parameter | Path segment `{name}` |
| `@Query` | `io.koraframework.http.common.annotation` | parameter | Query parameter |
| `@Header` | `io.koraframework.http.common.annotation` | parameter | Request header |
| `@Cookie` | `io.koraframework.http.common.annotation` | parameter | Cookie |
| `@InterceptWith(X.class)` | `io.koraframework.http.common.annotation` | class / method | Scoped interceptor (repeatable) |
| `@Json` | `io.koraframework.json.common.annotation` | method / parameter | JSON body |
| `@Mapping(X.class)` | `io.koraframework.common.annotation` | method / parameter | Custom request/response mapper |
| `@Component`, `@Tag` | `io.koraframework.common.annotation` | class | Graph registration and tagging |

`HttpMethod` (`io.koraframework.http.common.HttpMethod`) is a holder of **`String` constants**, not
an enum: `GET`, `HEAD`, `POST`, `PUT`, `DELETE`, `CONNECT`, `OPTIONS`, `TRACE`, `PATCH`, `QUERY`.
`@HttpRoute(method = ...)` takes a `String`, so `method = "GET"` is equally valid.

---

## Response types

| Return type | Status | Notes |
|---|---|---|
| `String` | 200 | `text/plain` |
| `byte[]` / `ByteBuffer` | 200 | `application/octet-stream` |
| `T` + `@Json` on the method | 200 | Serialized with the generated `JsonWriter<T>` |
| `HttpResponseEntity<T>` (+ `@Json`) | any | Body plus status code and headers |
| `HttpServerResponse` | any | Full control; returned as-is, no mapper involved |
| `void` (Kotlin `Unit`) | 200 | Empty body; **no response mapper required** |
| any other `T` | 200 | Needs an `HttpServerResponseMapper<T>` in the graph |

```java
return HttpResponseEntity.of(201, HttpHeaders.of("Location", "/users/" + id), user);
return HttpServerResponse.of(200, HttpHeaders.of("X-Trace", traceId), HttpBody.plaintext("OK"));
return HttpServerResponse.of(204);
```

**Reactive and suspending handlers are gone.** `http-server-common` ships no response mapper for
`Mono`/`Flux`/`CompletionStage`, and the Kotlin processor rejects `suspend` with
`Suspend methods are not supported by the HTTP server controller generator`. Run concurrent work
inside a synchronous handler with `StructuredTaskScope`.

See [Response Types](references/response-types-reference.md) for `HttpBody`, `HttpHeaders`
and custom `HttpServerResponseMapper` (including the Kotlin nullability rule).

---

## Error handling

Throw `HttpServerResponseException.of(code, message)` to short-circuit a handler.
`HttpServerResponseException` **is itself an `HttpServerResponse`**, so an interceptor can simply
return it. There is no `@ControllerAdvice` equivalent — centralized error translation is an
interceptor concern.

```java
return userService.find(id)
    .orElseThrow(() -> HttpServerResponseException.of(404, "Not found: " + id));
```

See [Error Handling](references/error-handling-reference.md) for the global error interceptor.

---

## Interceptors

```java
public interface HttpServerInterceptor {
    HttpServerResponse intercept(HttpServerRequest request, InterceptChain chain) throws Exception;

    interface InterceptChain {
        HttpServerResponse process(HttpServerRequest request) throws Exception;
    }
}
```

Synchronous, one request argument, `throws Exception` — so a plain `try/catch` around
`chain.process(request)` is the way to handle downstream errors.

| Scope | How | Applies to |
|---|---|---|
| **Server** | `@Tag(HttpServer.class)` + `@Component` | Every route on the **public** server. Any number of them |
| **Controller** | `@InterceptWith(X.class)` on the controller class | Every route in that controller |
| **Method** | `@InterceptWith(X.class)` on a `@HttpRoute` method | That route only |

```java
@Tag(HttpServer.class)   // io.koraframework.http.server.common.HttpServer
@Component
public final class LoggingInterceptor implements HttpServerInterceptor {

    private static final Logger log = LoggerFactory.getLogger(LoggingInterceptor.class);

    @Override
    public HttpServerResponse intercept(HttpServerRequest request, InterceptChain chain) throws Exception {
        long started = System.nanoTime();
        HttpServerResponse response = chain.process(request);
        log.info("{} {} -> {} ({} ms)", request.method(), request.path(), response.code(),
                (System.nanoTime() - started) / 1_000_000);
        return response;
    }
}
```

Server-scoped interceptors are **sorted by simple class name**, not by declaration order, and they
never run on the system server. See [Interceptors](references/interceptors-reference.md).

---

## Configuration

```hocon
httpServer {
  port = 8080
  ignoreTrailingSlash = false
  shutdownWait = "30s"
  maxRequestBodySize = "256MiB"
  headerServerNameEnabled = false   # default false: no `Server` response header
  headerServerDateEnabled = true    # default true: `Date` on every response

  telemetry {
    logging.enabled = true    # default false
    logging.maskHeaders = ["authorization", "cookie", "set-cookie"]   # the default set
    metrics.enabled = true    # default false
    tracing.enabled = true    # default true (but false under httpServer.system)
  }

  system {
    port = 8085
    metricsPath   = "/metrics"
    readinessPath = "/system/readiness"
    livenessPath  = "/system/liveness"
  }

  undertow {
    ioThreads = 4             # transport tuning lives in its own section
  }
}
```

`telemetry.logging.enabled` and `telemetry.metrics.enabled` default to **`false`** everywhere — an
example that claims to demonstrate them must switch them on. See
[Configuration](references/configuration-reference.md) for every key that actually exists.

**Response headers.** Undertow sends no `Server` header unless `headerServerNameEnabled = true`
(then it is `Server: Kora`). A `server` header set on an `HttpServerResponse` is dropped either
way — the server owns that header, like `content-length` and `transfer-encoding`.

**Log masking.** `maskHeaders` / `maskQueries` choose *which* header and query values are masked;
*how* they are masked is the `@Tag(HttpServerTelemetry.class) MaskingStrategy` component (default:
`***`). Bodies are logged only at `TRACE`, and a body is masked only when a
`@Tag(HttpServerTelemetry.class) DataMasker` for its format (`json`, `xml`, `form-urlencoded`) is
in the graph. There is no `mask` config key. See
[Configuration → Log masking](references/configuration-reference.md#log-masking) and the shared
masking model in [kora-aop-logging](../kora-aop-logging/references/logging-masking.md).

---

## References

| Reference | Covers |
|---|---|
| [Controller & Routing](references/controller-routing-reference.md) | `@HttpController`, `@HttpRoute`, package map, generated code, routing/405/404 |
| [Request Mapping](references/request-mapping-reference.md) | `@Path`/`@Query`/`@Header`/`@Cookie`, supported types, bodies, forms, `HttpServerRequestMapper` |
| [Response Types](references/response-types-reference.md) | `HttpServerResponse`, `HttpResponseEntity`, `HttpBody`, response mappers, `@Component` rules |
| [Interceptors](references/interceptors-reference.md) | `HttpServerInterceptor`, tag/scope, order, request enrichment |
| [Error Handling](references/error-handling-reference.md) | `HttpServerResponseException`, global error interceptor, JSON error bodies |
| [Configuration](references/configuration-reference.md) | `httpServer`, `httpServer.system`, `httpServer.undertow`, telemetry, port migration |
| [Authentication](references/authentication-reference.md) | Where auth lives in 2.0 and how it plugs into this server |
| [Request Enrichment](references/context-propagation-reference.md) | Passing values from an interceptor to a handler now that `Context` is gone |

## Assets

| Template | Purpose |
|---|---|
| [UserController.java](assets/templates/java/UserController.java.template) | CRUD controller (Java) |
| [UserController.kt](assets/templates/kotlin/UserController.kt.template) | CRUD controller (Kotlin) |
| [LoggingInterceptor.java](assets/templates/java/LoggingInterceptor.java.template) | Server-scoped logging interceptor (Java) |
| [LoggingInterceptor.kt](assets/templates/kotlin/LoggingInterceptor.kt.template) | Server-scoped logging interceptor (Kotlin) |
| [ErrorInterceptor.java](assets/templates/java/ErrorInterceptor.java.template) | Server-scoped error-to-JSON interceptor (Java) |
| [ErrorInterceptor.kt](assets/templates/kotlin/ErrorInterceptor.kt.template) | Server-scoped error-to-JSON interceptor (Kotlin) |

`scripts/validate_controller.py` statically checks a controller or interceptor file for the
regressions above (`--json` for machine output, `--help` for usage).

---

## Pitfalls

| Symptom | Cause and fix |
|---|---|
| Global interceptor never runs, no error | Tagged `@Tag(HttpServerModule.class)` or left untagged. Both compile and are silently pruned. Use `@Tag(HttpServer.class)` |
| Service starts fine but probes/LB hit nothing | Stale `publicApiHttpPort`/`privateApiHttpPort`. Unknown keys are ignored; rename to `port` / `system.port` |
| `Address already in use` at startup | Stale keys collapsed both servers onto one port |
| `No component found for dependency: X` on a mapper | `@Mapping(X.class)` injects the **concrete class** — `X` must be `@Component`, even with no constructor arguments |
| `Multiple components match dependency: HttpServerResponseMapper<T>` | Two untagged `@Component` mappers for the same `T`. Keep one, or separate with `@Tag` |
| `'apply' overrides nothing` (Kotlin) | Kora contracts are `@NullMarked`: `HttpServerResponseMapper<T>.apply` takes `result: T?` |
| `Suspend methods are not supported…` | Remove `suspend`; use `StructuredTaskScope` for concurrency |
| `exception IOException is never thrown…` | `JsonWriter.toByteArray` no longer declares a checked exception — delete the `catch` |
| 404 on a valid URL | `{var}` has no matching `@Path` argument, or the `@HttpController` prefix is not what you think — in **Kotlin** the prefix is concatenated raw, so it must start with `/` and must not end with one |
| `Cannot add path template …, matcher already contains an equivalent pattern` | Two routes on one method resolve to the same template (e.g. `/a/{x}` and `/a/{y}`) |
| Metrics endpoint returns nothing useful | `telemetry.metrics.enabled` defaults to `false` — enable it explicitly |
| Responses — including a large `/metrics` scrape — go out uncompressed, and no `compression`/`gzip` key works | Neither Undertow server (public or system) wires response compression, and `HttpServerConfig` / `SystemHttpServerConfig` / `UndertowConfig` have no key for it; an unknown key is ignored silently. Compress at the reverse proxy or ingress |
| No `Server` header, or a custom `Server` value never reaches the client | `headerServerNameEnabled` defaults to `false`; when on, the value is fixed to `Kora`, and a `server` header from the handler is always dropped |
| `telemetry.logging.mask = "..."` has no effect | The key does not exist. Replace the replacement text through a `@Tag(HttpServerTelemetry.class) MaskingStrategy` component |
| Passwords/tokens appear in `TRACE` body logs | Body masking needs a `@Tag(HttpServerTelemetry.class)` `DataMasker` (e.g. `JsonDataMasker`) for that content type; without one the body is logged verbatim |

---

## Evals

Self-check rubric: [evals/evals.json](evals/evals.json).
