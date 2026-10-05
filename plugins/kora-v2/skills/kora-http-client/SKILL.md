---
name: kora-http-client
description: "Declarative Kora 2.x HTTP clients — io.koraframework @HttpClient(\"httpClient.x\") interfaces with @HttpRoute, @Path/@Query/@Header/@Cookie, @Json bodies, HttpResponseEntity, @Mapping, @ResponseCodeMapper, HttpClientInterceptor + @InterceptWith, and the OkHttp / JDK / Apache transports (http-client-ok, http-client-jdk, http-client-apache). Client contracts are synchronous on virtual threads — no CompletionStage, Mono or Kotlin suspend, and http-client-async no longer exists. Use for typed outbound calls, per-client httpClient.* config and timeouts, HttpClientResponseException handling, or \"No component found for dependency: HttpClientResponseMapper<...>\" graph errors. For OpenAPI-generated clients see kora-openapi-generator-client; for the inbound @HttpController server see kora-http-server."
license: Apache-2.0
metadata:
  kora-version: "2.x"
---

# Kora HTTP Client — declarative outbound calls

> **Kora sub-skill — obey the [kora-v2 meta rules](../../SKILL.md) on every task:** **R0** ground the workspace on Kora 2.0 refs before starting (framework source at tag `2.0.0.RC2` + `kora-examples` at `migration/2.0` + Kora 2.0 docs at koraframework.io/v2, which trail the source; 1.x `kora-docs` pages are never an authority) · **R1** read this sub-skill before writing code · **R2** Kora 2.0 APIs only — no Spring/Micronaut/Quarkus, no Kora 1.x APIs, no invented annotations or config keys · **R3** journal any incorrect Kora usage. Add comments/Javadoc only if asked.

**Version:** Kora 2.0 (`io.koraframework`, `2.0.0.RC2`) | **Java:** 25 | **Kotlin:** 2.4 + KSP | **Gradle:** 9+

Annotate an interface with `@HttpClient`, declare methods with `@HttpRoute`, and the annotation
processor (Java) or symbol processor (Kotlin) generates `$<Name>_ClientImpl` plus a
`$<Name>_Config` config interface and a `$<Name>_Module` that binds it. No reflection, no runtime
proxies — inject the client interface like any other component.

**Client contracts are synchronous.** Every generated method blocks on a virtual thread and
returns the decoded value. There is no `CompletionStage`, no `Mono`/`Flux`, and a Kotlin `suspend`
client method is a hard KSP error. See [execution-model-reference](references/execution-model-reference.md).

## Migrating from Kora 1.x

| Kora 1.x | Kora 2.x |
|---|---|
| BOM `ru.tinkoff.kora:kora-parent` | **`io.koraframework:kora-bom`** |
| `ru.tinkoff.kora.http.client.common.annotation.HttpClient` | `io.koraframework.http.client.common.annotation.HttpClient` |
| `@HttpClient(configPath = "httpClient.x")` | **`@HttpClient("httpClient.x")`** — the attribute is `value()`; `configPath` does not exist |
| `http.client.common.HttpClientResponseException` | **`http.client.common.exception.HttpClientResponseException`** |
| `http.client.common.HttpClientDecoderException` | **`http.client.common.exception.HttpClientDecoderException`** |
| `e.code()` on `HttpClientResponseException` | **`e.getCode()`** / `getHeaders()` / `getBytes()` |
| artifact `http-client-async` (`AsyncHttpClientModule`) | **removed** — move to `http-client-ok`, `http-client-jdk` or the new `http-client-apache` |
| artifact `json-module` | **`json-common`** (`io.koraframework.json.common.JsonModule`) |
| `CompletionStage<T>` / `Mono<T>` / `suspend fun` client methods | **synchronous `T`** |
| `processRequest(Context, InterceptChain, HttpClientRequest)` | **`processRequest(InterceptChain, HttpClientRequest)`** — `Context` is gone from the framework |
| `chain.process(ctx, request)` | **`chain.process(request)`** |
| `OkHttpConfigurer` | **`io.koraframework.common.Configurer<okhttp3.OkHttpClient.Builder>`** |
| `HttpClientRequest.of(...).templateParam(...)` | **`.pathParam(...)`** |
| telemetry key `pathTemplate` | **`pathFull`** |
| `resilient.circuitbreaker.<n>.slidingWindowSize` | `…countBased.windowSize` + a window `type` (see `kora-aop-resilient`) |

Most of the table fails the build if you miss it. Three things in this domain do **not**, and need
a test rather than a compiler:

- **Telemetry defaults flipped.** `telemetry.metrics.enabled` and `telemetry.logging.enabled` are
  `false` in 2.0 (only `tracing` is `true`). A 1.x config that relied on the old defaults comes up
  green with no client metrics.
- **A `@Mapping` response mapper on a method disables the 2xx status check** — the mapper is called
  for every status and non-2xx stops throwing `HttpClientResponseException`. Same for an `Either`
  return type, by design.
- **A redundant `@Component` on a self-instantiated mapper** is latent: it only becomes
  `Multiple components match` once something resolves that `HttpClientResponseMapper<T>` from the
  graph, which may be a later, unrelated change.

---

## Quick Start

### 1. Dependencies

`gradle.properties`:

```properties
koraVersion=2.0.0.RC2
```

Java (`build.gradle`) — resolve from plain `mavenCentral()`:

```groovy
configurations {
    koraBom
    annotationProcessor.extendsFrom(koraBom)
    compileOnly.extendsFrom(koraBom)
    implementation.extendsFrom(koraBom)
    testImplementation.extendsFrom(koraBom)
    testAnnotationProcessor.extendsFrom(koraBom)
}

dependencies {
    koraBom platform("io.koraframework:kora-bom:$koraVersion")

    annotationProcessor "io.koraframework:annotation-processors"

    implementation "io.koraframework:http-client-ok"   // or http-client-jdk / http-client-apache
    implementation "io.koraframework:json-common"      // required for @Json bodies
    implementation "io.koraframework:config-hocon"
}
```

Kotlin (`build.gradle.kts`):

```kotlin
dependencies {
    implementation(platform("io.koraframework:kora-bom:${property("koraVersion")}"))
    ksp("io.koraframework:symbol-processors:${property("koraVersion")}")

    implementation("io.koraframework:http-client-ok")
    implementation("io.koraframework:json-common")
    implementation("io.koraframework:config-hocon")
}
```

`json-common` is a `compileOnly` dependency of `http-common`, so it is **not** pulled in
transitively — declare it in every module that uses `@Json` on a client.

### 2. Plug the transport module into `@KoraApp`

```java
@KoraApp
public interface Application extends
        HoconConfigModule,
        JsonModule,
        OkHttpClientModule {

    static void main(String[] args) {
        KoraApplication.run(ApplicationGraph::graph);
    }
}
```

Exactly one transport module at a time — each one registers `HttpClient` under the same
`httpClient` base config path.

### 3. Declare the client interface

```java
@HttpClient("httpClient.userApi")
public interface UserApiClient {

    @HttpRoute(method = HttpMethod.GET, path = "/users/{userId}")
    @Json
    UserResponse getUser(@Path String userId);

    @HttpRoute(method = HttpMethod.GET, path = "/users")
    @Json
    List<UserResponse> listUsers(@Nullable @Query("page") Integer page,
                                @Nullable @Query("size") Integer size);

    @HttpRoute(method = HttpMethod.POST, path = "/users")
    @Json
    HttpResponseEntity<UserResponse> createUser(@Json CreateUserRequest request);

    @HttpRoute(method = HttpMethod.DELETE, path = "/users/{userId}")
    void deleteUser(@Path String userId);
}
```

`@HttpClient` value is the **full** config path. Omit it and the client resolves
`httpClient.<lowerCamelInterfaceName>` — `UserApiClient` → `httpClient.userApiClient`.

### 4. Configuration (HOCON)

```hocon
httpClient {
  userApi {
    url = "http://localhost:8080"
    url = ${?USER_API_URL}
    requestTimeout = 10s

    telemetry.logging.enabled = true
    telemetry.metrics.enabled = true      # false by default in 2.0

    getUser {                             # per-method override, keyed by method name
      requestTimeout = 3s
    }
  }
}
```

`url` is the only required key. Transport-wide settings (`connectTimeout`, `readTimeout`, `proxy`)
live at `httpClient`, transport-specific ones at `httpClient.ok` / `.jdk` / `.apache`.

### 5. Inject and use

```java
@Component
public final class UserService {

    private final UserApiClient client;

    public UserService(UserApiClient client) {
        this.client = client;
    }

    public UserResponse getUser(String id) {
        return client.getUser(id);
    }
}
```

---

## When to use vs NOT

**Use this skill when:**
- Building a typed outbound client with `@HttpClient` + `@HttpRoute`.
- Mapping parameters with `@Path`, `@Query`, `@Header`, `@Cookie`, `@Json`, `@Mapping`.
- Adding `@InterceptWith` interceptors for auth, logging, or extra headers.
- Configuring per-client or per-method timeouts, proxy, HTTP version, or telemetry under `httpClient.*`.
- Diagnosing `No component found for dependency: HttpClientResponseMapper<…>` or
  `Multiple components match`.

**Do NOT use when:**
- You have an OpenAPI contract and want a generated client → `kora-openapi-generator-client`.
- You need the inbound HTTP server (`@HttpController`) → `kora-http-server`.
- You are wiring Basic/Bearer/API-key token flows in depth → `kora-http-client-auth`.

---

## Core rules

### Transports

| Module interface | Artifact | Transport config section | HTTP versions | Notes |
|---|---|---|---|---|
| `OkHttpClientModule` | `io.koraframework:http-client-ok` | `httpClient.ok` | `HTTP_1_1` (default), `HTTP_2`, `HTTP_3` | **default choice** |
| `JdkHttpClientModule` | `io.koraframework:http-client-jdk` | `httpClient.jdk` | `HTTP_1_1` (default), `HTTP_2` | no extra dependency; drops the restricted headers `connection`/`content-length`/`expect`/`host`/`upgrade` |
| `ApacheHttpClientModule` | `io.koraframework:http-client-apache` | `httpClient.apache` | Apache HttpClient 5, no `httpVersion` key | **new in 2.0**; `httpClient.apache` holds only `followRedirects`, `maxRedirects`, `maxConnections` |

Prefer `http-client-ok`; `http-client-jdk` is the dependency-free alternative. Every transport reads
`connectTimeout` / `readTimeout` / `proxy` / `useEnvProxy` from the shared `httpClient` block, and
every transport reports a failure to connect (refused, connect timeout) as
`HttpClientConnectionException`.

`http-client-async` / `AsyncHttpClientModule` **do not exist in 2.0** and have no drop-in
replacement. Details and every config key: [transports-reference](references/transports-reference.md).

### Which mappers and interceptors need `@Component`

Decided by **how the generated constructor obtains them**, not by taste:

| Wired as | `@Component` |
|---|---|
| `@InterceptWith(X.class)` interceptor | **always required** — always a constructor parameter |
| `@Mapping(X.class)` on a **body parameter** (`HttpClientRequestMapper`) | **always required** — always a constructor parameter |
| A response mapper you supply for a type the client resolves from the graph — e.g. `HttpClientResponseMapper<Void>` behind `HttpResponseEntity<Void>` | **always required** |
| `@Mapping(X.class)` on a **method** or `@ResponseCodeMapper(mapper = X.class)` | **only if the class is not instantiable by the generator** |

For that last row the generator emits `private static final X mapper = new X();` when the class is
`final` (Kotlin: not `open`) **and** has a public no-arg constructor — in Kotlin, exactly one
constructor, taking no arguments. Otherwise — a constructor dependency such as a `JsonReader<T>`,
or a non-final class — it becomes a constructor parameter and must be in the graph.

- Missing where required → `No component found for dependency: … (no tags)`.
- Added on a self-instantiated mapper it is redundant, and it registers a second
  `HttpClientResponseMapper<T>` in the graph: as soon as anything resolves that type from the
  graph, that is `Multiple components match`.

### `HttpResponseEntity<Void>` needs its own payload mapper

`HttpClientResponseMapperModule` supplies concrete mappers for `String`, `byte[]`, `ByteBuffer`
and `HttpBodyInput`, plus **template** factories for `HttpResponseEntity<T>`, `Either<T, E>` and
their `@Json` variants. The entity factory needs a mapper for the payload `T`, so
`HttpResponseEntity<Void>` fails the graph:

```
No component found for dependency: HttpClientResponseMapper<java.lang.Void> (no tags)
```

Declare the payload mapper as a component and **do not** reference it with `@Mapping`:

```java
@Component
final class VoidResponseMapper implements HttpClientResponseMapper<Void> {

    @Override
    public Void apply(HttpClientResponse response) throws IOException {
        try (var body = response.body()) {
            body.asInputStream().readAllBytes();
        }
        return null;
    }
}

@HttpRoute(method = HttpMethod.DELETE, path = "/users/{userId}")
HttpResponseEntity<Void> deleteUser(@Path String userId);
```

With `@Mapping(VoidResponseMapper.class)` the generator calls the mapper directly instead of
wrapping it, so the mapper would have to produce the whole entity:

```
error: incompatible types: Void cannot be converted to HttpResponseEntity<Void>
```

A method that returns plain `void` (Kotlin `Unit`) needs no mapper at all.

### Kotlin nullability

Kora's HTTP contracts are `@NullMarked` (JSpecify). `HttpClientResponseMapper<T>.apply` returns
`@Nullable T`, so a Kotlin mapper that has to return `null` must declare the nullable type:

```kotlin
@Component
class VoidResponseMapper : HttpClientResponseMapper<Void> {
    override fun apply(response: HttpClientResponse): Void? {
        response.body().use { it.asInputStream().readAllBytes() }
        return null
    }
}
```

`JsonReader<T>.read(...)` is nullable too — Kotlin needs `requireNotNull(...)` inside mappers.
An override whose nullability does not match the contract fails with `'apply' overrides nothing`,
which never mentions nullability.

---

## What's in `references/` and `assets/`

| File | Purpose |
|------|---------|
| [declarative-client-reference](references/declarative-client-reference.md) | `@HttpClient`, `@HttpRoute`, parameters, bodies, mappers, `@ResponseCodeMapper`, per-client/per-method config, the imperative `HttpClient` |
| [execution-model-reference](references/execution-model-reference.md) | Synchronous contracts, what `CompletionStage`/`Mono`/`suspend` migrate to, parallel fan-out |
| [error-handling-guide](references/error-handling-guide.md) | `HttpClientException` hierarchy, `HttpResponseEntity`, `Either`, status-aware decoding, resilience |
| [interceptors-reference](references/interceptors-reference.md) | `HttpClientInterceptor`, `@InterceptWith`, built-in Basic/ApiKey/Bearer interceptors |
| [transports-reference](references/transports-reference.md) | OkHttp / JDK / Apache modules, every config key, `Configurer`, proxy, telemetry |
| `assets/UserApiClient.java.template` | CRUD client incl. the `HttpResponseEntity<Void>` mapper (Java) |
| `assets/UserApiClient.kt.template` | Same client in Kotlin, with the nullability rules applied |
| `assets/CustomMapperClient.java.template` | `@Mapping` request body + `@ResponseCodeMapper` pair (Java) |
| `assets/CustomMapperClient.kt.template` | Same in Kotlin, incl. `requireNotNull` on `JsonReader.read` |
| `assets/ApiKeyAuthInterceptor.java.template` | `HttpClientInterceptor` reading a `@ConfigSource` key |
| `assets/ResilientApiClient.java.template` | Client with `@Retryable`/`@CircuitBreakable`/`@Timeout`/`@Fallback` typed specs |

---

## Common pitfalls

| Symptom | Cause / fix |
|---|---|
| `cannot find symbol: method configPath()` | 2.0 declares `String value()`; write `@HttpClient("httpClient.x")` |
| `@HttpClient(baseUrl = …)` does not compile | There is no `baseUrl`. The target comes from the `url` key in the client's config block |
| `No component found for dependency: HttpClientResponseMapper<java.lang.Void>` | `HttpResponseEntity<Void>` — add a `@Component HttpClientResponseMapper<Void>`, without `@Mapping` |
| `incompatible types: T cannot be converted to HttpResponseEntity<T>` | A payload mapper was wired through `@Mapping`; drop `@Mapping` and let the entity factory wrap it |
| `No component found for dependency: …RequestMapper` / interceptor | Request mappers and `@InterceptWith` classes are always injected — add `@Component` |
| `Multiple components match` on a response mapper | A `final` no-arg `@Mapping`/`@ResponseCodeMapper` mapper is built by the generated code; `@Component` on it is a duplicate binding |
| `Suspend methods are not supported by the HTTP client generator` | Remove `suspend`; do not replace it with a `withContext(Dispatchers.IO)` default wrapper |
| `Method has async signature, this might not work correctly` (warning), then a missing mapper | `CompletionStage`/`Mono` return type — make the method synchronous |
| `ConfigValueException` at `httpClient.<x>.url`, or calls going to the wrong host | The config path is the `@HttpClient` value, or `httpClient.<lowerCamelInterfaceName>` when omitted. An absent block throws; a stale block that still exists is read as-is |
| `@Json` body not serialized | Add `io.koraframework:json-common`, extend `io.koraframework.json.common.JsonModule`, annotate the DTO with `@Json` |
| Catching `HttpClientTimeoutException` misses "service down" | A refused connection or elapsed `connectTimeout` is `HttpClientConnectionException` on every transport; catch both, or `HttpClientException` |
| A `Host`/`Connection`/`Expect` header set by an interceptor never reaches the server | JDK transport — `java.net.http` owns those names, so Kora skips them |
| `telemetry.logging.mask` has no effect / secrets in `TRACE` bodies | There is no `mask` key; the replacement is a `@Tag(HttpClientTelemetry.class) MaskingStrategy`, and bodies are masked only by a `@Tag(HttpClientTelemetry.class) DataMasker` — see [transports-reference → Log masking](references/transports-reference.md#log-masking) |
| Interceptor header change ignored | `request.toBuilder().header(…).build()` — the request is never mutated in place |
| No `http.client.request.duration` metric | `telemetry.metrics.enabled` defaults to **false**; enable it per client |
| Phantom `ru.tinkoff.kora` errors after the rename | Stale generated sources — `./gradlew clean` with `--no-build-cache`; never edit `build/generated` |

---

## Related skills

- [`kora-http-client-auth`](../kora-http-client-auth/SKILL.md) — Basic / Bearer / API-key token flows
- [`kora-http-server`](../kora-http-server/SKILL.md) — inbound `@HttpController`
- [`kora-openapi-generator-client`](../kora-openapi-generator-client/SKILL.md) — generate a client from an OpenAPI spec
- [`kora-json`](../kora-json/SKILL.md) — `@Json` DTOs, `JsonReader`/`JsonWriter`
- [`kora-aop-resilient`](../kora-aop-resilient/SKILL.md) — `@Retryable`, `@CircuitBreakable`, `@Timeout`, `@Fallback`
- [`kora-telemetry-metrics`](../kora-telemetry-metrics/SKILL.md) — Micrometer wiring for `http.client.*`
