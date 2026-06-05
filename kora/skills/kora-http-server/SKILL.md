---
name: kora-http-server
description: Build REST APIs in Kora with Undertow HTTP server, @HttpController declarative controllers, @HttpRoute routing, @Path/@Query/@Header/@Cookie parameters, JSON request/response via @Json, interceptors, error handling, and UndertowConfigurer customization. Use when creating REST endpoints, HTTP webhooks, or web APIs. Prefer kora-openapi for contract-first development with OpenAPI specs. Triggers: @HttpController, @HttpRoute, HttpMethod, @Path, @Query, @Header, HttpServerResponseException, UndertowHttpServerModule, HTTP interceptors.
---

# Kora HTTP Server — Building HTTP APIs in Kora Applications

## Purpose

Skill for building HTTP APIs in Kora: `@HttpController` + `@Component` for declarative controllers | `@HttpRoute(method, path)` for routing | `@Path/@Query/@Header/@Cookie` for parameters | `@Json` for JSON request/response | `HttpServerRequestMapper/HttpServerResponseMapper` for customization | `HttpServerInterceptor` for interceptors | Undertow HTTP server (async, non-blocking NIO).

**When to use:**
- When creating REST APIs, HTTP endpoints, webhooks
- **Contract-first development:** If an OpenAPI specification exists — use [kora-openapi](../kora-openapi/SKILL.md) to generate code from the contract (recommended)
- **Code-first approach:** If the contract is not yet defined, the application is a basic example or hello-world, it is an internal API without an external specification, or there is a **complex contract with binary data / specific formats** that are difficult to represent in OpenAPI or are generated incorrectly — implement such controllers manually

**Recommendation:** For external APIs and public contracts prefer the OpenAPI generator. For internal services, simple controllers, or complex cases with binary data — code-first with `@HttpController`.

Read this first when:
- adding REST endpoints with `@HttpController` and `@HttpRoute` annotations,
- choosing between code-first controllers vs OpenAPI-generated delegates,
- handling HTTP request/response parameters (`@Path`, `@Query`, `@Header`, `@Json`),
- implementing global error handlers or HTTP interceptors,
- configuring Undertow server (public/private ports, HTTPS, CORS).

---

## Quick Start

**1. Add the dependency:**
```groovy
dependencies { implementation "ru.tinkoff.kora:http-server-undertow" }
```

**2. Connect the module:**
```java
@KoraApp
public interface Application extends UndertowHttpServerModule {
    static void main(String[] args) { KoraApplication.run(ApplicationGraph::graph); }
}
```

**3. Configuration:**
```hocon
httpServer { publicApiHttpPort = 8080; privateApiHttpPort = 8085; telemetry.logging.enabled = true }
```

**4. First controller:**
```java
@Component @HttpController
public final class HelloController {
    @HttpRoute(method = HttpMethod.GET, path = "/hello")
    public String hello() { return "Hello World"; }
}
```

**5. CRUD controller:**
```java
@Component @HttpController
public final class UserController {
    private final ConcurrentHashMap<String, User> users = new ConcurrentHashMap<>();
    @Json public record UserRequest(String name, String email) {}
    @Json public record UserResponse(String id, String name, String email) {}
    
    // POST /users — create
    @HttpRoute(method = HttpMethod.POST, path = "/users") @Json
    public UserResponse create(@Json UserRequest request) {
        String id = UUID.randomUUID().toString();
        User user = new User(id, request.name(), request.email());
        users.put(id, user);
        return new UserResponse(user.id(), user.name(), user.email());
    }
    
    // GET /users/{id} — get by id
    @HttpRoute(method = HttpMethod.GET, path = "/users/{id}") @Json
    public UserResponse getById(@Path String id) {
        User user = users.get(id);
        if (user == null) throw HttpServerResponseException.of(404, "User not found");
        return new UserResponse(user.id(), user.name(), user.email());
    }
    
    // GET /users — list
    @HttpRoute(method = HttpMethod.GET, path = "/users") @Json
    public List<UserResponse> list(@Query("limit") @Nullable Integer limit, @Query("offset") @Nullable Integer offset) {
        return users.values().stream().skip(offset != null ? offset : 0).limit(limit != null ? limit : 100)
            .map(u -> new UserResponse(u.id(), u.name(), u.email())).toList();
    }
    
    // PUT /users/{id} — update
    @HttpRoute(method = HttpMethod.PUT, path = "/users/{id}") @Json
    public UserResponse update(@Path String id, @Json UserRequest request) {
        User existing = users.get(id);
        if (existing == null) throw HttpServerResponseException.of(404, "User not found");
        User updated = new User(id, request.name(), request.email());
        users.put(id, updated);
        return new UserResponse(updated.id(), updated.name(), updated.email());
    }
    
    // DELETE /users/{id} — delete
    @HttpRoute(method = HttpMethod.DELETE, path = "/users/{id}")
    public void delete(@Path String id) {
        User removed = users.remove(id);
        if (removed == null) throw HttpServerResponseException.of(404, "User not found");
    }
    
    private record User(String id, String name, String email) {}
}
```

---

## Imperative Approach

Alternative approach via `HttpServerRequestHandler` — functional style without annotations:

```java
public interface SomeModule {
    default HttpServerRequestHandler helloHandler() {
        return HttpServerRequestHandlerImpl.of(
            HttpMethod.POST, "/hello/{name}",
            (context, request) -> {
                String name = RequestHandlerUtils.parseStringPathParameter(request, "name");
                String query = RequestHandlerUtils.parseOptionalStringQueryParameter(request, "query");
                List<String> queries = RequestHandlerUtils.parseOptionalStringListQueryParameter(request, "queries");
                String header = RequestHandlerUtils.parseOptionalStringHeaderParameter(request, "X-Header");
                String body = "Hello, " + name + "!";
                return CompletableFuture.completedFuture(HttpServerResponse.of(200, HttpBody.plaintext(body)));
            }
        );
    }
}
```

**Advantages:** Full control | No annotation-processor overhead | Explicit dependency via module | **Dynamic enable/disable** via `enabled`.

**When to use:** For simple handlers, performance-critical sections, feature flags, functional style.

---

## Dynamic Enable/Disable (Imperative)

```java
public interface SomeModule {
    // Handler disabled by default
    default HttpServerRequestHandler debugHandler() {
        return HttpServerRequestHandlerImpl.of(
            HttpMethod.GET, "/debug/info",
            (context, request) -> CompletableFuture.completedFuture(HttpServerResponse.of(200, HttpBody.plaintext("Debug info"))),
            false  // enabled = false → handler will not be registered
        );
    }
    // Handler enabled via configuration
    default HttpServerRequestHandler metricsHandler() {
        boolean enabled = config.metricsEndpointEnabled();
        return HttpServerRequestHandlerImpl.of(HttpMethod.GET, "/metrics", (context, request) -> { /* metrics logic */ }, enabled);
    }
}
```

**Use cases:** Feature flags (enable/disable endpoints without redeployment) | A/B testing | Debug endpoints (dev/staging) | Graceful degradation.

---

## Assets (Templates)

| Template | Purpose |
|----------|---------|
| `controller.java.template` | CRUD controller with 5 endpoints |
| `request-dto.java.template` / `response-dto.java.template` | DTO records |
| `interceptor.java.template` | Global logging interceptor |
| `error-handler.java.template` | Global error handler (400/404/408/500) |
| `imperative-handler.java.template` | Imperative handler |
| `imperative-handler-config.java.template` | Imperative handler with `enabled` flag |
| `application.conf.template` / `application.yaml.template` | HOCON / YAML configuration |

**Usage:** Copy the template into the project and replace the placeholders.

---

## 📝 Core Concepts

**Controller Declaration:**
```java
@Component @HttpController  // Registration in the DI container
public final class UserController {
    @HttpRoute(method = HttpMethod.POST, path = "/users")
    public UserResponse create(...) { ... }
}
```

**Request Parameters:**

| Annotation | Source | Example |
|------------|--------|---------|
| `@Path("id")` | URL path | `/users/{id}` |
| `@Query("name")` | Query string | `?name=value` |
| `@Header("X-Trace")` | HTTP header | `X-Trace: abc123` |
| `@Cookie("session")` | Cookie | `session=xyz` |
| `@Json` | JSON body | `{"name": "John"}` |
| `@Nullable` | Optional | May be absent |

**All parameters are required by default** — use `@Nullable` for optional ones.

**Response Types:**
```java
@HttpRoute(method = HttpMethod.GET, path = "/text")
public String getText() { return "plain text"; }  // Simple response

@HttpRoute(method = HttpMethod.GET, path = "/json")
@Json
public UserResponse getJson() { return new UserResponse("John"); }  // JSON response

@HttpRoute(method = HttpMethod.GET, path = "/custom")
public HttpServerResponse custom() {  // Full HTTP response
    return HttpServerResponse.of(200, HttpHeaders.of("X-Custom", "value"), HttpBody.plaintext("body"));
}

@HttpRoute(method = HttpMethod.GET, path = "/entity")
@Json
public HttpResponseEntity<UserResponse> entity() {  // JSON with custom headers
    return HttpResponseEntity.of(200, HttpHeaders.of("X-Custom", "value"), new UserResponse("John"));
}
```

---

## 🔌 HTTP Controller Integration

**JSON Request + Response:**
```java
@Component @HttpController
public final class UserController {
    @Json public record UserRequest(String name, String email) {}
    @Json public record UserResponse(String id, String name, String email) {}
    
    @HttpRoute(method = HttpMethod.POST, path = "/users")
    @Json
    public UserResponse create(@Json UserRequest request) {
        return new UserResponse("123", request.name(), request.email());  // request is automatically deserialized
    }
    
    @HttpRoute(method = HttpMethod.GET, path = "/users/{id}")
    @Json
    public UserResponse getById(@Path String id) { return new UserResponse(id, "John", "john@example.com"); }
}
```

**How it works:** `@Json` on a parameter → Kora looks for `HttpRequestMapper<T>` tagged with `@Json` or generates one via `JsonReader` | `@Json` on a method → Kora looks for `HttpResultMapper<T>` tagged with `@Json` or generates one via `JsonWriter` | Requires `json-module`.

**Path Parameters:**
```java
@HttpRoute(method = HttpMethod.GET, path = "/users/{id}/posts/{postId}")
@Json
public PostResponse getPost(@Path("id") String userId, @Path("postId") Long postId) { ... }
```

**Query Parameters:**
```java
@HttpRoute(method = HttpMethod.GET, path = "/users")
@Json
public List<UserResponse> search(@Query("name") String name, @Query("limit") Integer limit, @Query("offset") @Nullable Integer offset) { ... }
```

**List query parameters:** `@Query("status") List<String> statuses` — `?status=active&status=pending`

**Header/Cookie Parameters:**
```java
@HttpRoute(method = HttpMethod.GET, path = "/users/{id}")
@Json
public UserResponse getById(@Path String id, @Header("X-Trace-Id") String traceId, @Header("Authorization") @Nullable String auth) { ... }
@HttpRoute(method = HttpMethod.GET, path = "/session")
@Json
public SessionResponse getSession(@Cookie("session_id") String sessionId) { ... }
```

---

## Advanced Patterns

**Custom Request Mapper:**
```java
@Component @HttpController
public final class AuthController {
    public record AuthContext(String userId, String traceId) {}
    public static final class AuthMapper implements HttpServerRequestMapper<AuthContext> {
        @Override public AuthContext apply(HttpServerRequest request) {
            return new AuthContext(request.headers().getFirst("X-User-Id"), request.headers().getFirst("X-Trace-Id"));
        }
    }
    @HttpRoute(method = HttpMethod.POST, path = "/auth")
    public String authenticate(@Mapping(AuthMapper.class) AuthContext ctx) { return "Authenticated as " + ctx.userId(); }
}
```

**Custom Response Mapper:**
```java
@Component @HttpController
public final class XmlController {
    public record Data(String value) {}
    public static final class XmlMapper implements HttpServerResponseMapper<Data> {
        @Override public HttpServerResponse apply(Context ctx, HttpServerRequest req, Data result) {
            return HttpServerResponse.of(200, HttpHeaders.of("Content-Type", "application/xml"), HttpBody.plaintext("<data>" + result.value() + "</data>"));
        }
    }
    @Mapping(XmlMapper.class) @HttpRoute(method = HttpMethod.GET, path = "/xml")
    public Data getXml() { return new Data("test"); }
}
```

**Error Handling:**
```java
@HttpRoute(method = HttpMethod.GET, path = "/users/{id}")
@Json
public UserResponse getById(@Path String id) {
    if (id == null || id.isBlank()) throw HttpServerResponseException.of(400, "Invalid ID");
    if ("notfound".equals(id)) throw HttpServerResponseException.of(404, "User not found");
    return new UserResponse(id, "John", "john@example.com");
}
```

**Global Error Interceptor:**
```java
@Tag(HttpServerModule.class) @Component
public final class GlobalErrorInterceptor implements HttpServerInterceptor {
    @Override public CompletionStage<HttpServerResponse> intercept(Context ctx, HttpServerRequest request, InterceptChain chain) {
        return chain.process(ctx, request).exceptionally(e -> {
            if (e instanceof CompletionException) e = e.getCause();
            if (e instanceof HttpServerResponseException ex) return ex.getResponse();
            if (e instanceof IllegalArgumentException) return HttpServerResponse.of(400, HttpBody.plaintext(e.getMessage()));
            if (e instanceof TimeoutException) return HttpServerResponse.of(408, HttpBody.plaintext("Timeout"));
            return HttpServerResponse.of(500, HttpBody.plaintext("Internal error"));
        });
    }
}
```

**Method Interceptor:**
```java
@Component @HttpController
public final class LoggedController {
    public static final class LogInterceptor implements HttpServerInterceptor {
        @Override public CompletionStage<HttpServerResponse> intercept(Context ctx, HttpServerRequest req, InterceptChain chain) {
            System.out.println("Request: " + req.uri()); return chain.process(ctx, req);
        }
    }
    @InterceptWith(LogInterceptor.class) @HttpRoute(method = HttpMethod.GET, path = "/logged")
    public String logged() { return "Logged response"; }
}
```

## Quick Reference

```java
// Annotations: @Component, @HttpController, @HttpRoute(method, path), @Path/@Query/@Header/@Cookie, @Json, @Nullable, @Mapping(Mapper.class), @InterceptWith(Interceptor.class), @Tag(HttpServerModule.class)
// HTTP Methods: HttpMethod.GET / POST / PUT / PATCH / DELETE / HEAD / OPTIONS
// Response Types: String / byte[] / ByteBuffer / HttpServerResponse / HttpResponseEntity<T> / @Json T
// Module: @KoraApp interface Application extends UndertowHttpServerModule {}
```

---

## Configuration

**Important:** This is a reference of all available options. **You do not need to configure every parameter** — most values have sensible defaults.

**Basic configuration:**
```hocon
httpServer { publicApiHttpPort = 8080; privateApiHttpPort = 8085 }
```

**Undertow customization:**
```java
@Component
public class CustomUndertowConfigurer implements UndertowConfigurer {
    @Override public Undertow.Builder configure(Undertow.Builder builder) {
        return builder.setBufferSize(1024 * 16).setIoThreads(4);
    }
}
@Component
public class CorsHttpHandlerConfigurer implements HttpHandlerConfigurer {
    @Override public HttpHandler configure(HttpHandler next) {
        return exchange -> { exchange.getResponseHeaders().put("Access-Control-Allow-Origin", "*"); next.handleRequest(exchange); };
    }
}
```

**More details:** [references/configuration-reference.md](references/configuration-reference.md) — full reference for configuration options, UndertowConfigurer, and HttpHandlerConfigurer.

---

## Common Pitfalls

- **Missing `@HttpController` or `@Component`** → controller not discovered. Both annotations required.
- **Final class controller** → AOP can't proxy final classes. Controllers must be non-final.
- **Wrong path parameter syntax** → use `{id}` not `:id` in `@HttpRoute` paths.
- **Sync controller + async interceptor** → controllers are always sync; interceptors can return `CompletionStage`.
- **Missing `@Tag` for multiple controllers** → tag controllers of same type to avoid ambiguity.
