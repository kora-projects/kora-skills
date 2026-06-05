---
name: kora-http-client
description: Build HTTP clients in Kora with OkHttp (recommended), @HttpClient declarative clients, @HttpRoute routing, @Path/@Query/@Header/@Cookie parameters, JSON request/response via @Json, FormUrlEncoded/FormMultipart bodies, @ResponseCodeMapper for custom responses, HttpClientInterceptor for auth (Basic/ApiKey/Bearer/OAuth), and imperative HttpClientRequestBuilder. Use when integrating with external REST APIs, microservices, or third-party services. Prefer kora-openapi for contract-first development. Triggers: @HttpClient, @HttpRoute, HttpMethod, @Path, @Query, @Header, OkHttpClientModule, HttpClientInterceptor, HTTP auth.
---

# Kora HTTP Client — Building HTTP Clients in Kora Applications

**Recommendation:** If you have an **OpenAPI contract** (spec file), use [kora-openapi](../kora-openapi/SKILL.md) to generate the client. Code generation from OpenAPI is preferable to writing clients by hand:
- Automatic synchronization with the API contract
- Less boilerplate code
- Built-in request/response validation
- Automatic documentation

Use manual client authoring (`@HttpClient`) when:
- An OpenAPI specification is not available
- Full control over the HTTP request is needed (dynamic URLs, custom headers)
- Integrating with a legacy API that has no contract

Read this first when:
- adding outbound HTTP calls to external REST APIs or microservices,
- choosing between declarative `@HttpClient` vs imperative `HttpClientRequestBuilder`,
- wiring authentication interceptors (Basic, Bearer, API Key, OAuth),
- handling HTTP error responses (4xx, 5xx) and retries,
- configuring OkHttp client (timeouts, connection pool, interceptors).

## Quick Start

### 1. Add the Dependency

**OkHttp is recommended** — it is the most mature implementation:

```groovy
dependencies {
    implementation "ru.tinkoff.kora:http-client-ok"
    implementation "ru.tinkoff.kora:json-module"
}
```

### 2. Register the Module

```java
@KoraApp
public interface Application extends OkHttpClientModule, HttpClientModule, JsonModule {
    static void main(String[] args) { KoraApplication.run(ApplicationGraph::graph); }
}
```

### 3. Configuration (application.conf)

```hocon
httpClient {
  publicApi {
    url = "https://api.example.com"
    requestTimeout = "30s"
    telemetry { logging { enabled = true }; metrics { enabled = true }; tracing { enabled = true } }
  }
}
```

### 4. First Client (Declarative)

```java
@HttpClient("public-api")
public interface PublicApiClient {
    @HttpRoute(method = HttpMethod.GET, path = "/users/{id}")
    @Json
    UserResponse getUser(@Path String id);
}
```

### 5. Full CRUD Client

```java
@HttpClient("user-api")
public interface UserApiClient {
    @HttpRoute(method = HttpMethod.POST, path = "/users")  // POST — create
    @Json UserResponse createUser(@Json UserRequest request);
    
    @HttpRoute(method = HttpMethod.GET, path = "/users/{id}")  // GET — read
    @Json UserResponse getUser(@Path String id);
    
    @HttpRoute(method = HttpMethod.GET, path = "/users")  // GET — list
    @Json List<UserResponse> getAllUsers();
    
    @HttpRoute(method = HttpMethod.PUT, path = "/users/{id}")  // PUT — update
    @ResponseCodeMapper(code = 200, mapper = UpdateUserSuccessMapper.class)
    @ResponseCodeMapper(code = ResponseCodeMapper.DEFAULT, mapper = UpdateUserErrorMapper.class)
    UpdateUserResult updateUser(@Path String id, @Json UserRequest request);
    
    @HttpRoute(method = HttpMethod.DELETE, path = "/users/{id}")  // DELETE — delete
    void deleteUser(@Path String id);
    
    @Json record UserRequest(String name, String email) {}  // request DTO
    @Json record UserResponse(String id, String name, String email, LocalDateTime createdAt) {}  // response DTO
}
```

---

## Imperative Approach

An alternative approach using `HttpClient` directly — full control with asynchronous signatures:

```java
@Tag(HttpClientModule::class) @Component
public final class ManualApiClient {
    private final HttpClient httpClient;
    public ManualApiClient(HttpClient httpClient) { this.httpClient = httpClient; }
    
    public CompletionStage<UserResponse> getUser(String id) {
        HttpClientRequest request = HttpClientRequest.of(HttpMethod.GET, "https://api.example.com/users/" + id)
            .header("Accept", "application/json").build();
        return httpClient.execute(request).thenApply(r -> parseUserResponse(r.body().asString()));
    }
    
    public CompletionStage<UserResponse> createUser(UserRequest request) {
        HttpClientRequest httpRequest = HttpClientRequest.of(HttpMethod.POST, "https://api.example.com/users")
            .header("Content-Type", "application/json").body(HttpBody.json(serialize(request))).build();
        return httpClient.execute(httpRequest).thenApply(r -> parseUserResponse(r.body().asString()));
    }
}
```

**Advantages:** full control over the HTTP request, dynamic URL/header construction, custom response handling, asynchronous signatures (CompletionStage) for non-blocking processing.

**When to use:** complex scenarios, dynamic requests, custom auth flows, cases requiring full control over the HTTP request.

---

## Assets (Templates)

Ready-to-use templates in `assets/`:

**Java:** `declarative-client.java.template` (declarative client with CRUD), `imperative-client.java.template` (imperative client), `request-dto.java.template` / `response-dto.java.template` (DTO records), `sealed-response.java.template` (polymorphic responses), `basic-auth-interceptor.java.template` / `api-key-auth-interceptor.java.template` / `bearer-auth-interceptor.java.template` (auth), `custom-response-mapper.java.template` (custom mapper).

**Kotlin:** `declarative-client.kt.template`, `imperative-client.kt.template`, `request-dto.kt.template` / `response-dto.kt.template`, `sealed-response.kt.template`, `basic-auth-interceptor.kt.template` / `api-key-auth-interceptor.kt.template` / `bearer-auth-interceptor.kt.template`, `custom-response-mapper.kt.template`.

**Configuration:** `application.conf.template` (HOCON), `application.yaml.template` (YAML).

**Usage:** Copy the template into your project and replace the placeholders (`${package}`, `${client_name}`, etc.).

---

## 📝 Core Concepts

### Client Declaration

```java
@HttpClient("client-name")  // Name used for configuration lookup
public interface MyApiClient {
    @HttpRoute(method = HttpMethod.GET, path = "/api/resource/{id}")
    @Json  // JSON response
    ResourceResponse getResource(@Path String id);

}
```

### Request Parameters

| Annotation | Source | Example |
|-----------|--------|--------|
| `@Path("id")` | URL path | `/users/{id}` |
| `@Query("name")` | Query string | `?name=value` |
| `@Header("X-Trace")` | HTTP header | `X-Trace: abc123` |
| `@Cookie("session")` | Cookie | `session=xyz` |
| `@Json` | JSON body | `{"name": "John"}` |

**All parameters are required by default** — use `@Nullable` for optional parameters.

### Request Body Types

```java
@HttpClient("api")
public interface ApiClient {
    @HttpRoute(method = HttpMethod.POST, path = "/users")  // JSON body (requires @Json + json-module)
    @Json UserResponse create(@Json UserRequest request);
    
    @HttpRoute(method = HttpMethod.POST, path = "/form")  // Form URL-encoded
    FormResponse submitForm(FormUrlEncoded form);
    
    @HttpRoute(method = HttpMethod.POST, path = "/upload")  // Multipart form data
    UploadResponse upload(FormMultipart multipart);
    
    @HttpRoute(method = HttpMethod.POST, path = "/raw")  // Raw body
    String echo(String body);
}
```

### Response Types

```java
@HttpClient("api")
public interface ApiClient {
    void delete();  // No response
    String getText();  // Plain text
    byte[] getBinary();  // Binary data
    @Json UserResponse getUser();  // JSON object
    @Json List<UserResponse> listUsers();  // JSON array
    HttpResponseEntity<UserResponse> getFull();  // Full response
}
```

**Details:** [references/client-annotation-reference.md](references/client-annotation-reference.md) — full reference for @HttpClient, @HttpRoute, and method parameters.

---

## Advanced Patterns

### @ResponseCodeMapper

Type-safe handling of different HTTP status codes via sealed interfaces:

```java
@HttpClient("user-api")
public interface UserApiClient {
    @HttpRoute(method = HttpMethod.PUT, path = "/users/{id}")
    @ResponseCodeMapper(code = 200, mapper = UpdateSuccessMapper.class)
    @ResponseCodeMapper(code = ResponseCodeMapper.DEFAULT, mapper = UpdateErrorMapper.class)
    UpdateUserResult updateUser(@Path String id, @Json UserRequest request);
}
```

### HttpClientInterceptor

Authentication, logging, metrics:

```java
@Component
public class AuthInterceptor implements HttpClientInterceptor {
    @Override
    public CompletionStage<HttpClientResponse> intercept(Context ctx, HttpClientRequest request, InterceptChain chain) {
        HttpClientRequest authRequest = request.toBuilder().header("Authorization", "Bearer " + token).build();
        return chain.process(ctx, authRequest);
    }
}
// Usage: @HttpClient("api") @InterceptWith(AuthInterceptor.class)
public interface ApiClient { ... }
```

### Custom Mappers

Custom formats (XML, CSV, protobuf):

```java
@HttpClient("xml-api")
public interface XmlApiClient {
    @HttpRoute(method = HttpMethod.POST, path = "/xml")
    @Mapping(XmlRequestMapper.class)
    XmlResponse sendXml(@Mapping(XmlRequestMapper.class) XmlRequest request);
}
```

**Details:** [references/advanced-patterns-reference.md](references/advanced-patterns-reference.md) — @ResponseCodeMapper, custom mappers, auth patterns.

---

## Quick Reference

```java
// Annotations: @HttpClient("name"), @HttpRoute(method, path), @Path/@Query/@Header/@Cookie, @Json, @ResponseCodeMapper(code, mapper), @Mapping(Mapper.class), @InterceptWith(Interceptor.class), @Nullable
// HTTP Methods: HttpMethod.GET / POST / PUT / PATCH / DELETE / HEAD / OPTIONS
// Request Body: @Json T / FormUrlEncoded / FormMultipart / String / byte[]
// Response Types: void / String / byte[] / @Json T / HttpResponseEntity<T>
// Modules: @KoraApp interface Application extends OkHttpClientModule, HttpClientModule, JsonModule {}
```

**Configuration:** [references/configuration-reference.md](references/configuration-reference.md) — OkHttp settings, proxy, telemetry.

**Interceptors:** [references/interceptors-reference.md](references/interceptors-reference.md) — HttpClientInterceptor, auth patterns.

**Templates:** `assets/` — ready-to-use templates for clients, DTOs, and interceptors (Java + Kotlin).

---

## Common Pitfalls

- **Missing `@Json` on DTO** → JSON mapper not generated. Always annotate DTOs with `@Json`.
- **No error handling** → use sealed interface + `@ResponseCodeMapper` for type-safe error handling.
- **Missing `@Tag` for multiple clients** → tag clients to avoid ambiguous injection.
- **Interceptor not applied** → interceptor must be `@Component`; apply via `@InterceptWith` on client.
- **FormUrlEncoded without `@FormField`** → annotate each form field explicitly.
