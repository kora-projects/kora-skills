---
name: kora-mega
description: Unified mega-skill combining all 14 Kora Framework sub-skills: bootstrap, JSON, HTTP server/client, OpenAPI, AOP, Kafka, telemetry, database (JDBC/Cassandra), gRPC, S3, testing, MapStruct, and journal. Build production-grade Java/Kotlin microservices with compile-time DI, zero reflection, annotation-processor driven. Use for any Kora development task.
---

# Kora Mega — Unified Kora Framework Skill

**Kora Version:** 1.2.15+  
**Languages:** Java 25, Kotlin 1.9+  
**Build:** Gradle 9.5.1+ (recommended)

This mega-skill combines all 14 specialized Kora sub-skills into one comprehensive guide. Read the relevant section based on your task.

---

## Table of Contents

1. [Bootstrap](#1-bootstrap) — Project scaffolding, DI container, config, lifecycle
2. [JSON](#2-json) — DTOs, sealed discriminators, custom (de)serialization
3. [HTTP Server](#3-http-server) — Controllers, routes, request/response, error mapping
4. [HTTP Client](#4-http-client) — Declarative `@HttpClient`, interceptors
5. [OpenAPI](#5-openapi) — Codegen (server delegates/clients), Swagger UI, Rapidoc
6. [AOP](#6-aop) — Validation, logging, resilience, scheduling, caching
7. [Kafka](#7-kafka) — Producers/consumers, batch listeners, transactions
8. [Telemetry](#8-telemetry) — Metrics, tracing, structured logging, liveness/readiness
9. [Database](#9-database) — JDBC repositories, `@Query`, transactions, migrations
10. [gRPC](#10-grpc) — Server handlers + client stubs
11. [S3](#11-s3) — Object storage: AWS, MinIO, Yandex
12. [Testing](#12-testing) — `@KoraAppTest`, Testcontainers, black-box tests
13. [MapStruct](#13-mapstruct) — DTO ↔ entity mappers
14. [Journal](#14-journal) — Continuous improvement journal

---

## 1. Bootstrap

**Purpose:** Project scaffolding, DI container, lifecycle, config, env vars.

### Quick Start

```groovy
// build.gradle
plugins { id "java"; id "application" }
configurations { koraBom; annotationProcessor.extendsFrom(koraBom); implementation.extendsFrom(koraBom) }
dependencies {
    koraBom platform("ru.tinkoff.kora:kora-parent:1.2.15")
    annotationProcessor "ru.tinkoff.kora:annotation-processors"
}
java { sourceCompatibility = JavaVersion.VERSION_25 }
application { mainClass = "com.example.Application" }
```

```java
@KoraApp
public interface Application extends
    HoconConfigModule,
    JsonModule,
    LogbackModule,
    UndertowHttpServerModule {
    static void main(String[] args) { KoraApplication.run(ApplicationGraph::graph); }
}
```

### Core Concepts

- **`@KoraApp`** is the container root — generates `ApplicationGraph` at compile time
- **Components are singletons** — wired at compile time via `@Component`, `@Module`, `@KoraSubmodule`
- **`@Root`** for "no consumers but must start" — HTTP servers, Kafka consumers, schedulers
- **`@Tag`** differentiates same-type components
- **`ValueOf<T>`** — indirect dependency, decouples lifecycle
- **`Lifecycle`** — init/release for non-trivial components

### Configuration

```java
@ConfigSource("app.database")
public interface DatabaseConfig {
    String url();                    // required
    @Nullable String username();     // optional
    String password();               // required
    default int poolSize() { return 20; }
}
```

```hocon
app.database {
    url = ${DATABASE_URL}
    username = ${?DATABASE_USERNAME}
    password = ${?DATABASE_PASSWORD:-secret}
    pool-size = 20
}
```

### Common Pitfalls

- Missing `@Root` on long-running components → HTTP server/Kafka never starts
- Two `@Component` of same type without `@Tag` → ambiguous dependency error
- Injecting `Config` directly → every config edit reboots whole graph; use `@ConfigSource`
- Final class with non-public constructor + `@Component` → factory generation fails

**References:** `references/bootstrap/` | **Templates:** `assets/bootstrap/` | **Scripts:** `scripts/bootstrap/`

---

## 2. JSON

**Purpose:** JSON DTOs, sealed discriminators, custom (de)serialization.

### Quick Start

```groovy
dependencies { implementation "ru.tinkoff.kora:json-module" }
```

```java
@KoraApp
public interface Application extends JsonModule {}
```

```java
@Json
public record UserRequest(String name, String email) {}
```

### Annotations

| Annotation | Purpose | Example |
|------------|---------|---------|
| `@Json` | Reader + Writer | `@Json public record User(String id, String name)` |
| `@JsonReader` | Deserialization only | `@JsonReader public record ImportData(...)` |
| `@JsonWriter` | Serialization only | `@JsonWriter public record ExportData(...)` |
| `@JsonField("name")` | Rename field | `@JsonField("user_id") String userId` |
| `@JsonSkip` | Ignore field | `@JsonSkip String internalField` |
| `@JsonInclude` | Control serialization | `@JsonInclude(IncludeType.NON_NULL)` |

### Sealed Interfaces for Polymorphic JSON

```java
@Json
@JsonDiscriminatorField("type")
public sealed interface PaymentResult permits PaymentSuccess, PaymentError {}

@JsonDiscriminatorValue("SUCCESS")
public record PaymentSuccess(String type, String transactionId) implements PaymentResult {}

@JsonDiscriminatorValue("ERROR")
public record PaymentError(String type, String errorCode) implements PaymentResult {}
```

### Common Pitfalls

- Missing `@Json` on DTO/enum → compile-time mapper not generated
- All fields required by default → use `@Nullable` for optional fields
- Discriminator value mismatch → must match JSON exactly (case-sensitive)

**References:** `references/json/` | **Templates:** `assets/json/`

---

## 3. HTTP Server

**Purpose:** REST APIs with Undertow, `@HttpController`, `@HttpRoute`, interceptors.

### Quick Start

```groovy
dependencies { implementation "ru.tinkoff.kora:http-server-undertow" }
```

```java
@KoraApp
public interface Application extends UndertowHttpServerModule {}
```

```java
@Component
@HttpController
public final class UserController {
    @HttpRoute(method = HttpMethod.POST, path = "/users")
    @Json
    public UserResponse create(@Json UserRequest request) { ... }
}
```

### Request Parameters

| Annotation | Source | Example |
|------------|--------|---------|
| `@Path("id")` | URL path | `/users/{id}` |
| `@Query("name")` | Query string | `?name=value` |
| `@Header("X-Trace")` | HTTP header | `X-Trace: abc123` |
| `@Cookie("session")` | Cookie | `session=xyz` |
| `@Json` | JSON body | `{"name": "John"}` |

### Response Types

```java
@HttpRoute(method = HttpMethod.GET, path = "/text")
public String getText() { return "plain text"; }

@HttpRoute(method = HttpMethod.GET, path = "/json")
@Json
public UserResponse getJson() { return new UserResponse("John"); }

@HttpRoute(method = HttpMethod.GET, path = "/custom")
public HttpServerResponse custom() {
    return HttpServerResponse.of(200, HttpHeaders.of("X-Custom", "value"), HttpBody.plaintext("body"));
}
```

### Common Pitfalls

- Missing `@HttpController` or `@Component` → controller not discovered
- Final class controller → AOP can't proxy final classes
- Wrong path parameter syntax → use `{id}` not `:id`

**References:** `references/http-server/` | **Templates:** `assets/http-server/` | **Scripts:** `scripts/http-server/`

---

## 4. HTTP Client

**Purpose:** Declarative `@HttpClient`, interceptors, auth (Basic/Bearer/API Key).

### Quick Start

```groovy
dependencies {
    implementation "ru.tinkoff.kora:http-client-ok"
    implementation "ru.tinkoff.kora:json-module"
}
```

```java
@KoraApp
public interface Application extends OkHttpClientModule, HttpClientModule, JsonModule {}
```

```java
@HttpClient("public-api")
public interface PublicApiClient {
    @HttpRoute(method = HttpMethod.GET, path = "/users/{id}")
    @Json
    UserResponse getUser(@Path String id);
}
```

### Request Body Types

```java
@HttpClient("api")
public interface ApiClient {
    @HttpRoute(method = HttpMethod.POST, path = "/users")
    @Json UserResponse create(@Json UserRequest request);
    
    @HttpRoute(method = HttpMethod.POST, path = "/form")
    FormResponse submitForm(FormUrlEncoded form);
    
    @HttpRoute(method = HttpMethod.POST, path = "/upload")
    UploadResponse upload(FormMultipart multipart);
}
```

### Common Pitfalls

- Missing `@Json` on DTO → JSON mapper not generated
- No error handling → use sealed interface + `@ResponseCodeMapper`
- Missing `@Tag` for multiple clients → tag clients to avoid ambiguous injection

**References:** `references/http-client/` | **Templates:** `assets/http-client/` | **Scripts:** `scripts/http-client/`

---

## 5. OpenAPI

**Purpose:** Generate HTTP clients/servers from OpenAPI specs, Swagger UI, Rapidoc.

### Quick Start

```groovy
plugins { id "org.openapi.generator" version "7.14.0" }
buildscript {
    dependencies { classpath("ru.tinkoff.kora:openapi-generator:1.2.15") }
}
```

```groovy
def openApiGenerateHttpClient = tasks.register("openApiGenerateHttpClient", GenerateTask) {
    generatorName = "kora"
    inputSpec = "$projectDir/src/main/resources/openapi/my-api.yaml"
    outputDir = "$buildDir/generated/my-api-client"
    configOptions = [mode: "java-client", clientConfigPrefix: "httpClient.myApi"]
}
sourceSets.main { java.srcDirs += openApiGenerateHttpClient.get().outputDir }
compileJava.dependsOn openApiGenerateHttpClient
```

### Generation Modes

| Mode | Description | Return Type |
|------|-------------|-------------|
| `java-client` | Synchronous client | `T` |
| `java-async-client` | Asynchronous client | `CompletionStage<T>` |
| `java-server` | Synchronous server | `ApiResponses` subclass |
| `java-async-server` | Asynchronous server | `CompletionStage<ApiResponses>` |
| `kotlin-client` | Kotlin synchronous | `T` |
| `kotlin-server` | Kotlin synchronous | `ApiResponses` subclass |

### Common Pitfalls

- Duplicate endpoints → don't mix generated delegate + manual controller for same paths
- Wrong outputDir → each OpenAPI spec needs unique `outputDir`
- Missing discriminator in oneOf → define discriminators for polymorphic types

**References:** `references/openapi/` | **Templates:** `assets/openapi/` | **Scripts:** `scripts/openapi/`

---

## 6. AOP

**Purpose:** Cross-cutting concerns: validation, logging, resilience, scheduling, caching.

### Quick Start

```groovy
dependencies {
    implementation "ru.tinkoff.kora:validation-module"
    implementation "ru.tinkoff.kora:resilient-kora"
    implementation "ru.tinkoff.kora:scheduling-jdk"
    implementation "ru.tinkoff.kora:cache-caffeine"
}
```

```java
@KoraApp
public interface Application extends 
    ValidationModule,
    ResilientModule,
    SchedulingJdkModule,
    CaffeineCacheModule {}
```

### AOP Modules

| Concern | Module | Annotations |
|---------|--------|-------------|
| Validation | `validation-module` | `@Valid`, `@Validate`, `@NotBlank`, `@Size`, `@Range` |
| Method logging | `logging-common` | `@Log`, `@Log.in`, `@Log.out`, `@Mdc` |
| Resilience | `resilient-kora` | `@CircuitBreaker`, `@Retry`, `@Timeout`, `@Fallback` |
| Scheduling | `scheduling-jdk` / `scheduling-quartz` | `@ScheduleAtFixedRate`, `@ScheduleWithCron` |
| Caching | `cache-caffeine` / `cache-redis` | `@Cacheable`, `@CachePut`, `@CacheInvalidate` |

### Important

- **Class must be subclassable** — Java: not `final`; Kotlin: `open`
- **Annotation without module = silently ignored** — always plug matching `*Module` into `@KoraApp`
- **Aspect order matters** — outermost annotation runs first

### Common Pitfalls

- Forgetting `open`/non-final → compile error "aspect class must be non-final / open"
- Stacking aspects in wrong order → `@Timeout` outside `@Retry` = "whole retry budget timeout"
- Validation throwing 500 → map `ViolationException` to 400 in global `ErrorInterceptor`

**References:** `references/aop/` | **Templates:** `assets/aop/` | **Scripts:** `scripts/aop/`

---

## 7. Kafka

**Purpose:** Event-driven messaging with `@KafkaListener`, `@KafkaPublisher`, transactions.

### Quick Start

```groovy
dependencies {
    implementation "ru.tinkoff.kora:kafka"
    implementation "ru.tinkoff.kora:json-module"
}
```

```java
@KoraApp
public interface Application extends KafkaModule, JsonModule, HoconConfigModule {}
```

```java
@Component
public final class MyMessageListener {
    @KafkaListener("kafka.consumer.my-listener")
    void process(String value) {
        log.info("Received: {}", value);
    }
}
```

```java
@KafkaPublisher("kafka.producer.my-publisher")
public interface MyMessagePublisher {
    @KafkaPublisher.Topic("kafka.producer.my-topic")
    void send(String value);
}
```

### Transactional Publishers

```java
@KafkaPublisher("kafka.producer.myTransactionalPublisher")
public interface MyTransactionalPublisher extends TransactionalPublisher<MyPublisher> {}

// Usage
txPublisher.inTx(p -> {
    p.send("key1", "value1");
    p.send("key2", "value2");
});
```

### Common Pitfalls

- Missing `@KafkaListener` or `@Component` → consumer not discovered
- Wrong deserializer → match `keyDeserializer`/`valueDeserializer` to actual data format
- Transaction without `enableIdempotence` → enable for exactly-once semantics

**References:** `references/kafka/` | **Templates:** `assets/kafka/` | **Scripts:** `scripts/kafka/`

---

## 8. Telemetry

**Purpose:** Observability: metrics (Micrometer/Prometheus), tracing (OpenTelemetry), logging (Logback).

### Quick Start

```groovy
dependencies {
    implementation "ru.tinkoff.kora:micrometer-module"
    implementation "ru.tinkoff.kora:opentelemetry-tracing-exporter-grpc"
    implementation "ru.tinkoff.kora:logging-logback"
}
```

```java
@KoraApp
public interface Application extends 
    MetricsModule,
    OpentelemetryGrpcExporterModule,
    LogbackModule {}
```

### Configuration

```hocon
httpServer { privateApiHttpMetricsPath = "/metrics" }
tracing {
    exporter {
        endpoint = "http://localhost:4317"
        attributes { "service.name" = "my-service" }
    }
}
```

### Common Pitfalls

- Metrics not exported → add registry dependency (e.g., `micrometer-registry-prometheus`)
- Tracing not flowing → use `@Trace` on async boundaries
- SLF4J MDC vs Kora MDC → use `ru.tinkoff.kora.logging.common.MDC`, not `org.slf4j.MDC`

**References:** `references/telemetry/` | **Templates:** `assets/telemetry/` | **Scripts:** `scripts/telemetry/`

---

## 9. Database

**Purpose:** JDBC repositories, `@Query`, transactions, migrations. Prefer JDBC + Virtual Threads.

### Quick Start

```groovy
dependencies {
    implementation "ru.tinkoff.kora:database-jdbc"
    implementation "org.postgresql:postgresql:42.7.3"
}
```

```java
@KoraApp
public interface Application extends JdbcDatabaseModule {}
```

```java
@EntityJdbc
@Table("users")
public record User(
    @Column("id") @Id Long id,
    @Column("email") String email,
    @Column("created_at") LocalDateTime createdAt
) {}
```

```java
@Repository
public interface UserRepository extends JdbcRepository {
    @Query("SELECT * FROM users WHERE id = :id")
    User findById(Long id);
    
    @Query("INSERT INTO users (email, created_at) VALUES (:email, :createdAt)")
    void insert(String email, LocalDateTime createdAt);
}
```

### Important

- **ALWAYS prefer synchronous repository signatures** — use `Entity` or `@Nullable Entity`, not `CompletionStage`
- **Use `@EntityJdbc`** for JDBC entities to enable optimized result converters
- **Extend `JdbcRepository`** for base functionality

### Common Pitfalls

- Missing `@Repository` annotation → repositories must be annotated
- ID type mismatch → repository ID type must match entity's `@Id` field exactly
- Missing `RETURNING` for generated IDs → use `RETURNING` clause to get generated ID after insert

**References:** `references/database/` | **Templates:** `assets/database/` | **Scripts:** `scripts/database/`

---

## 10. gRPC

**Purpose:** gRPC clients and servers with protobuf.

### Quick Start

```groovy
plugins { id "com.google.protobuf" version "0.9.4" }
dependencies {
    implementation "ru.tinkoff.kora:grpc-server"
    implementation "io.grpc:grpc-protobuf:1.62.2"
}
```

```java
@KoraApp
public interface Application extends GrpcServerModule, HoconConfigModule {}
```

```java
@Component
public class GreeterService extends GreeterGrpc.GreeterImplBase {
    @Override
    public void sayHello(HelloRequest req, StreamObserver<HelloResponse> responseObserver) {
        HelloResponse response = HelloResponse.newBuilder()
            .setMessage("Hello, " + req.getName())
            .build();
        responseObserver.onNext(response);
        responseObserver.onCompleted();
    }
}
```

### Common Pitfalls

- Missing `@Component` on handler → gRPC handler not discovered
- Wrong stub type → match stub type to usage: `BlockingStub` for sync, `FutureStub` for async
- Server reflection not working → add `grpc-services` dependency + `reflectionEnabled = true`

**References:** `references/grpc/` | **Templates:** `assets/grpc/` | **Scripts:** `scripts/grpc/`

---

## 11. S3

**Purpose:** S3-compatible object storage (AWS S3, MinIO, Yandex).

### Quick Start

```groovy
dependencies {
    implementation "ru.tinkoff.kora.experimental:s3-client-aws"
    implementation "ru.tinkoff.kora:http-client-async"
}
```

```java
@KoraApp
public interface Application extends AwsS3ClientModule, AsyncHttpClientModule {}
```

```java
@S3.Client("s3client.documents")
public interface DocumentsClient {
    @S3.Get
    S3Object get(String key);
    
    @S3.Put
    void put(String key, S3Body body);
    
    @S3.Delete
    void delete(String key);
}
```

### S3Body Factory Methods

| Factory | Use when |
|---------|----------|
| `S3Body.ofBytes(byte[])` | Small payloads fully in memory |
| `S3Body.ofInputStream(InputStream, long size)` | Streaming, known length |
| `S3Body.ofInputStreamUnbound(InputStream)` | Streaming, unknown length → multipart upload |
| `S3Body.ofPublisher(Flow.Publisher<ByteBuffer>, long size)` | Reactive streaming, known length |

### Common Pitfalls

- Wrong artifact group → `ru.tinkoff.kora.experimental:s3-client-aws`, not `ru.tinkoff.kora:s3-client-aws`
- Forgetting HTTP client module for AWS → AWS SDK needs HTTP transport
- Key template doesn't include every method arg → compile error

**References:** `references/s3/` | **Templates:** `assets/s3/` | **Scripts:** `scripts/s3/`

---

## 12. Testing

**Purpose:** Component tests (`@KoraAppTest`), black-box tests (`AppContainer`), Testcontainers.

### Quick Start

```groovy
dependencies {
    testImplementation "ru.tinkoff.kora:test-junit5"
    testImplementation "org.mockito:mockito-core:5.18.0"
    testImplementation "org.testcontainers:junit-jupiter:1.21.3"
}
```

### Component Test

```java
@KoraAppTest(Application.class)
class UserServiceTest {
    @TestComponent
    private UserService userService;

    @Test
    void shouldCreateUser() {
        var user = userService.create("test@example.com");
        assertNotNull(user);
    }
}
```

### Black-Box Test

```java
@TestcontainersPostgreSQL
class BlackBoxTests {
    private static final AppContainer container = AppContainer.build();

    @Test
    void shouldCreateUserViaApi() throws Exception {
        var httpClient = HttpClient.newHttpClient();
        var request = HttpRequest.newBuilder()
            .POST(HttpRequest.BodyPublishers.ofString("{\"email\":\"test@example.com\"}"))
            .uri(container.getURI().resolve("/users"))
            .build();
        var response = httpClient.send(request, HttpResponse.BodyHandlers.ofString());
        assertEquals(200, response.statusCode());
    }
}
```

### Common Pitfalls

- Missing `@KoraAppTest` → test class not recognized
- `@TestComponent` without `@Component` → mock must be `@TestComponent` to replace real component
- AppContainer port conflict → use random port for black-box tests

**References:** `references/testing/` | **Templates:** `assets/testing/` | **Scripts:** `scripts/testing/`

---

## 13. MapStruct

**Purpose:** DTO-to-entity mappers with compile-time code generation.

### Quick Start

```groovy
dependencies {
    annotationProcessor "ru.tinkoff.kora:annotation-processors"
    annotationProcessor "org.mapstruct:mapstruct-processor:1.5.5.Final"
    implementation "org.mapstruct:mapstruct:1.5.5.Final"
}
```

```java
@Mapper
public interface OrderMapper {
    @Mapping(target = "id", ignore = true)
    @Mapping(target = "createdAt", expression = "java(java.time.OffsetDateTime.now())")
    Order toEntity(OrderDto dto);
    
    OrderDto toDto(Order entity);
}
```

```java
@Component
public final class OrdersController {
    private final OrderMapper mapper;
    
    public OrdersController(OrderMapper mapper) {
        this.mapper = mapper;
    }
}
```

### Common Pitfalls

- Missing `@Mapper` → interface not discovered without annotation
- kapt/KSP conflict (Kotlin) → use either kapt or KSP, not both for MapStruct
- Generated impl not found → ensure MapStruct processor runs before Kora's processor

**References:** `references/mapstruct/` | **Templates:** `assets/mapstruct/`

---

## 14. Journal

**Purpose:** Continuous improvement journal for collecting fixes and improvements.

### Quick Start

```bash
# Add an entry
python kora-journal/scripts/kora_journal.py add "Fixed HTTP client example" \
  --context "Implementing an interceptor" \
  --problem "Example did not show error handling" \
  --solution "Added try-catch and logging" \
  --files kora-http-client/references/interceptors-reference.md

# View recent entries
python kora-journal/scripts/kora_journal.py list --limit 10

# Export entries
python kora-journal/scripts/kora_journal.py export --since 2026-05-01
```

### When to Use

- ✅ Fixes for inaccuracies in KORA skill documentation
- ✅ Improvements to code examples for Kora
- ✅ New patterns for working with Kora
- ✅ Version updates for Kora, Gradle, Kora dependencies
- ✅ Working solutions for Kora issues

**Do not use for:**
- ❌ Temporary fixes specific to a single project
- ❌ Style preferences without functional difference
- ❌ Non-Kora things: application business logic

**References:** `references/journal/` | **Scripts:** `scripts/journal/`

---

## Kora Architectural Principles

These principles apply across all sections.

### 1. Compile-time first

Kora avoids reflection, dynamic proxies, and runtime bytecode generation. All magic happens at compile time:
- DI container → `*ComponentImpl.java`
- HTTP routes → `*HttpRouter.java`
- AOP aspects → `*Aspect.java`
- JSON readers/writers → `*JsonReader.java`, `*JsonWriter.java`
- Repositories → `*RepositoryImpl.java`

**Validate code by compiling + testing.** If code compiles and tests pass, implementation is correct.

### 2. Annotation processors are mandatory

```groovy
// Java
annotationProcessor "ru.tinkoff.kora:annotation-processors"

// Kotlin
ksp "ru.tinkoff.kora:symbol-processors"
```

Without them, **nothing works**.

### 3. BOM dependency

Always use the `kora-parent` BOM:

```groovy
dependencies {
    koraBom platform("ru.tinkoff.kora:kora-parent:1.2.15")
}
```

All Kora modules will be on the same version.

### 4. Modules as interfaces

External Kora capabilities are delivered as `*Module` interfaces. The `@KoraApp` interface declares which ones to plug in via `extends ...Module`.

### 5. Strongly typed config

Define `@ConfigSource("path.to.section")` interfaces and inject them as components. Externalize every credential: `${VAR}` / `${?VAR}` / `${?VAR:default}`.

### 6. Observability from day one

Plug in `metrics-micrometer`, `tracing-otel-*`, `probes`, `logging-logback`. Every Kora module emits telemetry that can be toggled in config.

### 7. Testing with Testcontainers

Integration tests should spin up real DB/Kafka/dependent service via Testcontainers, not mocks.

### 8. HTTP server defaults

- `httpServer.publicApiHttpPort` — public traffic
- `httpServer.privateApiHttpPort` — metrics/probes

Don't co-mingle them.

---

## Build Troubleshooting

| Problem | Solution |
|---------|----------|
| **Build hangs / fails after clean** | `./gradlew --stop` — terminate daemons, then retry |
| **Generated classes broken after refactor** | Clean `build/generated/`, rebuild |
| **"Required dependency not found: Foo"** | Check: `@Component` on class, `extends *Module` on `@KoraApp` |
| **`ApplicationGraph` missing after clean** | Run `./gradlew classes` — annotation processors must run first |
| **IDE shows errors but compilation passes** | IDE is caching — invalidate caches / restart |

---

## Local Documentation Setup

```bash
mkdir -p .kora-agent
git clone --depth 1 https://github.com/kora-projects/kora-docs.git .kora-agent/kora-docs
git clone --depth 1 https://github.com/kora-projects/kora-examples.git .kora-agent/kora-examples
rm -rf .kora-agent/kora-docs/.git .kora-agent/kora-examples/.git
echo ".kora-agent/" >> .gitignore
```

**Paths:**
- `.kora-agent/kora-docs/mkdocs/docs/en/documentation/` — per-module documentation
- `.kora-agent/kora-examples/` — working example projects

---

## Source Priority

1. **This mega-skill** — combined knowledge from all 14 sub-skills
2. **Reference documents** inside `references/<module>/`
3. **External documentation:** `.kora-agent/kora-docs/mkdocs/docs/en/documentation/<module>.md`
4. **Examples:** `.kora-agent/kora-examples/kora-java-<name>/`
5. **Changelog:** https://github.com/kora-projects/kora-docs

**If there's a discrepancy** between this skill and the source — trust the source and update the skill.
