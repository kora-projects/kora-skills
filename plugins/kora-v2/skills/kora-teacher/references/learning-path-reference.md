# Kora 2.0 learning path — complete reference

**Framework:** Kora 2.0, group `io.koraframework`, BOM `io.koraframework:kora-bom`, version
`2.0.0.RC2` | **Java:** 25 (hard floor) | **Kotlin:** 2.4.20 + KSP 2.3.12 |
**Gradle:** 9.8.0

Every stop below names a companion application from `kora-examples` at branch `migration/2.0`,
grounded on disk by **R0** as `.kora-agent/kora-examples-2.0/`. The learner compiles, runs and
breaks the companion app; the lesson is the commentary around it.

Java paths are `guides/java/kora-java-guide-<name>-app` and `examples/java/kora-java-<name>`.
Kotlin paths substitute `kotlin` for `java` in both the directory and the module name
(`guides/kotlin/kora-kotlin-guide-http-server-app`). Every guide app listed here exists in both
languages.

---

## 0. Before the first lesson

### Check the environment — this is where most first sessions actually fail

| Check | Command | Required |
|---|---|---|
| JDK on the path | `java -version` | **25 or newer**, for Java *and* Kotlin learners |
| JDK running Gradle | `./gradlew -version` (look at "Launcher JVM") | **25 or newer** |
| Gradle | `./gradlew -version` | 9.x — the framework pins the 9.8.0 wrapper |

Java 25 is not a recommendation. Kora 2.0 artifacts are compiled to class-file major version 69;
an older JVM cannot load them at all. And the toolchain block alone is not enough: the
`io.koraframework:openapi-generator` plugin lands on the **buildscript** classpath, which is
resolved by the JVM running Gradle itself, so on JDK 21 configuration fails outright with
`Dependency requires at least JVM runtime version 25. This build uses a Java 21 JVM.`

A learner whose `JAVA_HOME` points at 21 will read that message as "Kora is broken". Check first.

### Ask four questions, then choose the entry point

1. Java or Kotlin? (It changes the processor: `annotationProcessor` vs `ksp`.)
2. Have you used Kora 1.x? → if yes, teach
   [`kora-2-unlearning-reference.md`](kora-2-unlearning-reference.md) **before** stop 1.
3. What have you used before — Spring, Micronaut, plain servlets, nothing? (Not to draw analogies,
   but to know which habits will fight the compile-time model.)
4. What do you want to have built in two weeks? Steer the optional stops toward it.

---

## Phase 1 — Foundations

### Stop 1 — Getting started

- **Companion:** `guides/java/kora-java-guide-getting-started-app` (2 source files, 1 test)
- **Teaches:** `@KoraApp` on an *interface*, module composition via `extends`, the generated
  `<App>Graph`, `KoraApplication.run(ApplicationGraph::graph)`, `@Component`, `@HttpController`,
  `@HttpRoute`, `HttpServerResponse.of(...)`.
- **Modules pulled in:** `config-hocon`, `http-server-undertow`, `json-common`, `logging-logback`.
- **Run:** `./gradlew :guides:java:kora-java-guide-getting-started-app:test`
- **Break it:** drop `UndertowPublicHttpServerModule` from the extends clause → a compile-time graph
  error names the missing dependency. That error at build time, not at runtime, is the whole point.
- **Point out:** the generated graph is named after the interface — `Application` → `ApplicationGraph` —
  and does not exist before the first `./gradlew classes`.

### Stop 2 — The same service, one size up

- **Companion:** `examples/java/kora-java-helloworld`
- **Teaches:** what stop 1 left out — a real `application.conf`, `@Json` on a record and on a route,
  `HttpResponseEntity.of(200, body)` for explicit status codes, `logback.xml`, a Dockerfile and a
  black-box test that starts the packaged application in a container.
- **The config file is the lesson:**

  ```hocon
  httpServer {
    port = 8080
    system.port = 8085
  }

  logging.levels {
    "root": "WARN"
    "io.koraframework": "INFO"
  }

  httpServer.telemetry.logging.enabled = true
  ```

  Three things to say about it. `port` and `system.port` are the 2.0 keys — the 1.x
  `publicApiHttpPort` / `privateApiHttpPort` are silently ignored (see §"Silent failures" in the
  [meta-skill](../../../SKILL.md) §4). The two servers are separate: the public one serves the app,
  the system one serves probes and metrics. And `telemetry.logging.enabled = true` is there because
  request logging is **off by default** in 2.0 — the example has to switch it on to demonstrate it.

### Stop 3 — Dependency injection, the introduction

- **Companion:** `guides/java/kora-java-guide-dependency-injection-introduction-app`
- **Teaches:** in one small app — `@Component` with constructor injection, a `@Module` interface
  with factory methods, `@DefaultComponent` and overriding it from the `@KoraApp` interface,
  `@Tag(SomeTag.class)` for disambiguation, `@Tag(Tag.Any.class) All<Notifier>` to collect every
  implementation, `@Nullable` for a genuinely optional dependency, and `@Root` to keep a component
  that nothing else depends on from being pruned out of the graph.
- All DI annotations come from **`io.koraframework.common.annotation`**. The nullability annotation
  is **JSpecify** (`org.jspecify.annotations.Nullable`) in Java, and simply `T?` in Kotlin.
- **Break it:** remove `@Root` from the service nobody injects and watch it disappear from the
  graph. Pruning is the single most surprising behaviour for a newcomer.
- **Hand off after this stop for anything deeper:**
  [`kora-di-compile`](../../kora-di-compile/SKILL.md), [`kora-di-runtime`](../../kora-di-runtime/SKILL.md).

### Stop 4 — Dependency injection across Gradle modules

- **Companion:** `guides/java/kora-java-guide-dependency-injection` (four Gradle modules: `-app`,
  `-common`, `-lib`, `-submodule`)
- **Teaches:** `@KoraSubmodule` — why a module compiled in a *different* Gradle project needs one,
  and why modules in the same compilation do not. This is the stop that explains the most common
  multi-module error a learner will hit later.
- **Optional** for someone building a single-module service; skip and come back.

### Stop 5 — Typed configuration

- **Companion:** `guides/java/kora-java-guide-config-hocon-app` (or `…-config-yaml-app`)
- **Teaches:** the two annotations, and why there are two.

  | Annotation | Use it for | Also generates |
  |---|---|---|
  | `@ConfigSource("app")` | one fixed path in the config file | a `<Name>Module`, so the type can be injected directly |
  | `@ConfigMapper` | nested types, list element types, reusable/library shapes — no path | only `$<Name>_ConfigValueMapper` |

  Both live in `io.koraframework.config.common.annotation`. **`@ConfigMapper` has no type
  parameter** — `ConfigMapper<T>` never compiles, and the similarly-named runtime contract
  `ConfigValueMapper<T>` is a different type entirely. Kora's own config interfaces
  (`HttpServerConfig`, `TelemetryConfig`) use `@ConfigMapper`.
- **Also teaches:** required vs `@Nullable` vs default-method values, and `${?ENV_VAR}` substitution.
- **Break it:** delete a required key from `application.conf` → `ConfigValueException` naming the
  exact path. Contrast with a *misspelled* key, which is silently ignored. That contrast is the
  lesson.
- **Hand off:** [`kora-config-hocon`](../../kora-config-hocon/SKILL.md) ·
  [`kora-config-yaml`](../../kora-config-yaml/SKILL.md)

---

## Phase 2 — HTTP and JSON

### Stop 6 — JSON

- **Companion:** `guides/java/kora-java-guide-json-app`
- **Teaches:** `@Json` from `io.koraframework.json.common.annotation` on records / data classes;
  Kora generates `$Foo_JsonReader` and `$Foo_JsonWriter` at compile time. No reflection, no
  Jackson databind on the hot path. Artifact is **`json-common`** (1.x called it `json-module`),
  graph module is `io.koraframework.json.common.JsonModule`.
- **Show the generated reader.** It is short, readable Java, and seeing it ends the "so it's magic"
  phase permanently.
- **Hand off:** [`kora-json`](../../kora-json/SKILL.md)

### Stop 7 — HTTP server

- **Companion:** `guides/java/kora-java-guide-http-server-app` (controller + service + repository —
  the first stop with a realistic layering)
- **Teaches:** `@HttpRoute(method = HttpMethod.GET, path = "/users/{userId}")`, `@Path`, `@Query`,
  `@Header`, `@Cookie` — all from **`io.koraframework.http.common.annotation`** — `@Json` bodies,
  `HttpResponseEntity.of(201, HttpHeaders.of(), body)` for status plus headers, and
  `HttpServerResponseException.of(404, "…")` for errors.
- **Note the package split**, because it is the most common import mistake: the routing/parameter
  annotations are in `http.common.annotation`, while `@HttpController` and the response types are in
  `http.server.common.*`.
- **Show the generated code:** a controller `HelloController` produces a `HelloControllerModule`
  interface holding the route handlers.
- **Hand off:** [`kora-http-server`](../../kora-http-server/SKILL.md)

### Stop 8 — HTTP server, advanced

- **Companion:** `guides/java/kora-java-guide-http-server-advanced-app`
- **Teaches:** `HttpServerInterceptor` for cross-cutting concerns, and **the tag that matters**:

  ```java
  @Tag(HttpServer.class)   // io.koraframework.http.server.common.HttpServer
  @Component
  public final class ExceptionHandler implements HttpServerInterceptor {   // the app's own class
      @Override
      public HttpServerResponse intercept(HttpServerRequest request, InterceptChain chain) { … }
  }
  ```

  The 1.x form `@Tag(HttpServerModule.class)` still **compiles** — that class still exists — but
  nothing looks interceptors up by it, so the interceptor silently never runs. This is the single
  best teaching example of "compiles ≠ works", and the learner should verify it with a test that
  asserts the interceptor fired.
- **Also:** `@InterceptWith` for a single route, form handling, custom error mapping.

### Stop 9 — HTTP client

- **Companion:** `guides/java/kora-java-guide-http-client-app`, then `…-http-client-advanced-app`
- **Teaches:** the declarative `@HttpClient` interface from
  `io.koraframework.http.client.common.annotation`, per-client config, response mappers,
  `HttpClientResponseException`.
- **1.x carry-over to flag:** `@HttpClient(configPath = "x")` is now `@HttpClient("x")` — the
  `configPath` attribute does not exist in 2.0.
- **Hand off:** [`kora-http-client`](../../kora-http-client/SKILL.md) ·
  [`kora-http-client-auth`](../../kora-http-client-auth/SKILL.md)

---

## Phase 3 — Data

### Stop 10 — JDBC repositories

- **Companion:** `guides/java/kora-java-guide-database-jdbc-app`, then `…-database-jdbc-advanced-app`
- **Teaches:** `@Repository` interfaces extending `JdbcRepository`, `@Query` with named parameters,
  `@EntityJdbc` from **`io.koraframework.database.jdbc.annotation`**, `@Table` / `@Column` / `@Id`,
  the SQL macros (`%{return#selects}`, `%{entity#inserts}`, `%{entity#where = @id}`), `@Batch`,
  and `UpdateCount`. The generated implementation is `$FooRepository_Impl`.
- **Transactions** go through `executor().inTx(...)`. There is no `@Transaction` annotation in
  Kora 2.0 — do not teach one, and do not accept one in a learner's code.
- **Config section is `jdbc`, not `db`.** The 1.x name produces
  `ConfigValueException: … got null at path: 'ROOT.jdbc.username'`, which reads like a missing
  username rather than a wrong section name.
- **Repository methods are synchronous.** There is nothing reactive to reach for; see
  [`kora-2-unlearning-reference.md`](kora-2-unlearning-reference.md).
- **Hand off:** [`kora-database-jdbc`](../../kora-database-jdbc/SKILL.md) ·
  [`kora-database-migration`](../../kora-database-migration/SKILL.md)

### Stop 11 — Testing

- **Companion:** `guides/java/kora-java-guide-testing-junit-app` → `…-testing-integration-app` →
  `…-testing-black-box-app`
- **Teaches:** `@KoraAppTest(Application.class)` + `@TestComponent` field injection (artifact
  `io.koraframework:test-junit5`), then Testcontainers against a real database, then black-box tests
  against the packaged distribution.
- **Teach this stop early — before the resilience and telemetry stops, not after.** Everything on
  the silent-failure list can only be proven by a test, so the learner needs the tool before they
  meet the traps.
- **Testcontainers: read the companion app's `build.gradle`, do not assume.** Every migrated example
  and guide app pins Testcontainers **1.21.4** with the classic module names —
  `org.testcontainers:junit-jupiter`, `org.testcontainers:postgresql`. Kora's *own* build has moved
  to Testcontainers **2.0.5**, which renamed the modules to `testcontainers-postgresql`,
  `testcontainers-kafka`, `testcontainers-cassandra`. So the rename is real but it belongs to the
  Testcontainers upgrade, not to Kora 2.0: a learner copying `org.testcontainers:postgresql` out of
  the companion app is correct, and only has to rename if they move their own build to 2.x.
- **Hand off:** [`kora-testing-junit-java`](../../kora-testing-junit-java/SKILL.md) ·
  [`kora-testing-junit-kotlin`](../../kora-testing-junit-kotlin/SKILL.md) ·
  [`kora-testing-blackbox`](../../kora-testing-blackbox/SKILL.md)

---

## Phase 4 — Production concerns

### Stop 12 — Observability

- **Companion:** `guides/java/kora-java-guide-observability-app`
- **Teaches:** metrics, tracing, logging, and the readiness/liveness probes on the **system** server.
- **The headline fact, and the reason this stop exists:** in Kora 2.0 component logging and metrics
  are **disabled by default**; tracing is enabled. The companion app's own `application.conf`
  carries a comment about exactly this, because without the explicit switch `/metrics` returns 200
  with only JVM series and the learner concludes metrics are broken:

  ```hocon
  httpServer {
    port = 8080
    system.port = 8085
    system.metricsPath = "/metrics"
    system.livenessPath = "/system/liveness"
    system.readinessPath = "/system/readiness"
    telemetry.logging.enabled = true
    telemetry.metrics.enabled = true
  }
  ```

  One exception worth mentioning once: on the system server tracing is overridden back to `false`.
- **Hand off:** [`kora-telemetry-metrics`](../../kora-telemetry-metrics/SKILL.md) ·
  [`kora-telemetry-tracing`](../../kora-telemetry-tracing/SKILL.md) ·
  [`kora-telemetry-logging`](../../kora-telemetry-logging/SKILL.md)

### Stop 13 — Validation

- **Companion:** `guides/java/kora-java-guide-validation-app`
- **Teaches:** `@Valid` on a type (generates a `Validator<T>`), `@Validate` on a method, and the
  constraint annotations — `@NotBlank`, `@NotEmpty`, `@Pattern`, `@Range`, `@Size`, `@Min`, `@Max`,
  `@Positive`, `@Past`, `@Future`, `@OneOf`, `@Url`, `@UUID` and the rest.
- **Say this explicitly:** these are **Kora's own** annotations in
  `io.koraframework.validation.common.annotation`. Kora validation is *not* Jakarta Bean
  Validation / JSR-380 — there is no `jakarta.validation` anywhere in the framework. A learner who
  imports `jakarta.validation.constraints.NotBlank` gets an annotation Kora ignores completely.
- **Hand off:** [`kora-aop-validation`](../../kora-aop-validation/SKILL.md)

### Stop 14 — Resilience and caching

- **Companion:** `guides/java/kora-java-guide-resilient-app`, `…-cache-app`, `…-cache-multi-level-app`
- **Teaches:** resilience aspects are **typed** in 2.0 — `@Retryable(X.class)`,
  `@CircuitBreakable(X.class)`, `@Timeout(X.class)`, `@RateLimited(X.class)`, where `X` is a spec
  interface annotated `@RetrySpec("resilient.retry.<name>")` (and so on) extending the matching base
  type. The 1.x string form `@Retry("name")` is gone; in Java it fails as
  `incompatible types: String cannot be converted to Class<? extends …>`, and in Kotlin KSP crashes
  with `ClassCastException: String cannot be cast to KSType`, which explains nothing.
- **The circuit-breaker trap, worth doing as an exercise:** a `circuitbreaker` section without a
  `countBased` block fails at graph init with
  `IllegalArgumentException: CircuitBreaker '<name>' property 'countBased' is not configured`.
  `CircuitBreakerConfig.validate(name, config)` is the first statement of `KoraCircuitBreaker`'s
  constructor, so the message names the breaker and the missing key — loud and precise, not an NPE.
  Note `type` itself is optional; it defaults to `STRIPED_APPROX`, which still needs `countBased`.
  Working shape, from the companion app:

  ```hocon
  resilient.circuitbreaker.default {
    type = FIXED_WINDOW
    countBased.windowSize = 2
    minimumRequiredCalls = 2
    failureRateThreshold = 100
    permittedCallsInHalfOpenState = 1
    waitDurationInOpenState = 200ms
  }
  ```

  Also worth saying: named sections **no longer inherit** from `default`. Each stands alone.
- **Caching:** `@Cacheable`, `@CachePut`, `@CacheInvalidate`, and `@CacheInvalidateAll(X.class)` —
  a separate annotation in 2.0, replacing 1.x's `invalidateAll = true` attribute. The `parameters`
  attribute is now `args`.
- **Hand off:** [`kora-aop-resilient`](../../kora-aop-resilient/SKILL.md) ·
  [`kora-aop-caching`](../../kora-aop-caching/SKILL.md)

### Stop 15 — Messaging

- **Companion:** `guides/java/kora-java-guide-messaging-kafka-app`
- **Teaches:** `@KafkaListener`, `@KafkaPublisher`, record (de)serialization, batch consumption,
  error handling.
- **Hand off:** [`kora-kafka-consumer`](../../kora-kafka-consumer/SKILL.md) ·
  [`kora-kafka-producer`](../../kora-kafka-producer/SKILL.md)

---

## Phase 5 — Optional, driven by what the learner is building

Pick from these; none is a prerequisite for another.

| Topic | Companion app(s) | Hand off to |
|---|---|---|
| OpenAPI server | `…-openapi-http-server-app`, `…-openapi-http-server-advanced-app` | [`kora-openapi-generator-server`](../../kora-openapi-generator-server/SKILL.md) |
| OpenAPI client | `…-openapi-http-client-app` | [`kora-openapi-generator-client`](../../kora-openapi-generator-client/SKILL.md) |
| Serving the spec | — | [`kora-openapi-management`](../../kora-openapi-management/SKILL.md) |
| gRPC | `…-grpc-server-app`, `…-grpc-server-advanced-app`, `…-grpc-client-app`, `…-grpc-client-advanced-app` | [`kora-grpc-server`](../../kora-grpc-server/SKILL.md) · [`kora-grpc-client`](../../kora-grpc-client/SKILL.md) |
| Cassandra | `…-database-cassandra-app` | [`kora-database-cassandra`](../../kora-database-cassandra/SKILL.md) |
| S3 | `…-s3-app` | [`kora-s3`](../../kora-s3/SKILL.md) |
| PostgreSQL types (arrays, ranges, `interval`, `jsonb`) | — | [`kora-database-jdbc`](../../kora-database-jdbc/references/postgres-mappers-reference.md) |
| Scheduling — in-process, Quartz, database-backed cluster jobs | — | [`kora-aop-scheduling-jdk`](../../kora-aop-scheduling-jdk/SKILL.md) · [`kora-aop-scheduling-quartz`](../../kora-aop-scheduling-quartz/SKILL.md) · [`kora-aop-scheduling-db`](../../kora-aop-scheduling-db/SKILL.md) |
| Distributed rate limiting and retry budgets on Redis | — | [`kora-aop-resilient`](../../kora-aop-resilient/SKILL.md) |
| JSON logs, masking secrets in telemetry logs | — | [`kora-telemetry-logging`](../../kora-telemetry-logging/SKILL.md) · [`kora-aop-logging`](../../kora-aop-logging/SKILL.md) |
| DTO mapping — MapStruct (Java), Konvert (Kotlin) | `examples/java/kora-java-crud`, `examples/kotlin/kora-kotlin-crud` | [`kora-mapstruct`](../../kora-mapstruct/SKILL.md) |

**Topics with no guide app — use the plain examples, and say so.** There is no
`kora-java-guide-scheduling-app`; do not invent one. Use `examples/java/kora-java-scheduling-jdk`
and `examples/java/kora-java-scheduling-quartz` — written against `2.0.0.RC1`, so they still use the
annotation names that Kora PR #952 renamed (`@ScheduleAtFixedRate` → `@ScheduleJdkAtFixedRate`,
Quartz `@ScheduleWithCron` → `@ScheduleQuartzWithCron`); teach the new names. The database-backed scheduler, the PostgreSQL
module, distributed resilience and the JSON log encoder have no example app at all — teach them from
the domain sub-skill and the framework tests. Likewise `examples/java/kora-java-soap-client`,
`examples/java/kora-java-telemetry`, `examples/java/kora-java-cache-caffeine`,
`examples/java/kora-java-cache-redis`.

**Capstone applications**, once the phases are done — full services worth reading end to end:
`examples/java/kora-java-crud`, `examples/java/kora-java-crud-submodule` (multi-module),
`examples/java/kora-java-petclinic`.

---

## Assessment — check before moving between phases

Ask the learner to *do* these, not to describe them.

**After Phase 1**

- [ ] Writes a `@KoraApp` interface and a `@Component` from memory, with correct imports.
- [ ] Explains why `ApplicationGraph` is red in the IDE before the first compile.
- [ ] Explains what `@Root` prevents, and can name a component that needs it.
- [ ] Adds a `@ConfigSource` section and reads a value in a component.
- [ ] States why Kora has no field injection — and does not answer "because Spring does X".

**After Phase 2**

- [ ] Adds a route with a path parameter and a query parameter, and gets the imports right first try.
- [ ] Returns 201 with a header using `HttpResponseEntity`.
- [ ] Writes a global interceptor with `@Tag(HttpServer.class)` and a test proving it fires.
- [ ] Finds their own generated `$Foo_JsonReader` and reads it.

**After Phase 3**

- [ ] Writes a `@Repository` with `@Query` and an `@EntityJdbc` record.
- [ ] Runs a multi-statement transaction through `executor().inTx(...)`.
- [ ] Writes a `@KoraAppTest` that injects a `@TestComponent` and asserts on it.
- [ ] Knows the config section is `jdbc` and can say what happens if it is called `db`.

**After Phase 4**

- [ ] Turns on component metrics and shows `http_server_*` series appearing.
- [ ] Writes a resilience spec interface and applies the typed annotation to a method.
- [ ] Names three things that compile cleanly and fail silently, and how to test each.

---

## Frequently asked, answered from 2.0

### "What is Kora?"

A **compile-time** dependency-injection framework for Java and Kotlin. Every piece of wiring is
generated during the build by annotation processors (Java) or KSP (Kotlin): the DI graph, HTTP
routers, JSON readers and writers, repository implementations, AOP proxies. At runtime there is no
reflection, no classpath scanning and no dynamic proxies — the application is plain compiled code.
The consequences a learner will feel: fast startup, small memory footprint, and wiring mistakes that
surface as build errors instead of runtime surprises.

### "Why is there no `@Autowired`?"

Because there is nothing at runtime to do the injecting. Dependencies arrive through the
constructor, and the constructor call is written into the generated graph at build time. Field
injection is not "discouraged" in Kora — it is not expressible.

```java
@Component
public final class UserService {
    private final UserRepository repository;

    public UserService(UserRepository repository) {
        this.repository = repository;
    }
}
```

### "What does Kora actually generate?"

Verified naming, worth showing rather than describing:

| You write | Kora generates |
|---|---|
| `@KoraApp interface Application` | `ApplicationGraph` — `<InterfaceName>` + `Graph` |
| `@Json record UserResponse` | `$UserResponse_JsonReader`, `$UserResponse_JsonWriter` |
| `@Repository interface UserRepository` | `$UserRepository_Impl` |
| `@HttpController class UserController` | `UserControllerModule` — the route handlers |
| an AOP-annotated class `UserService` | `$UserService__AopProxy` |
| `@ConfigSource interface AppConfig` | `$AppConfig_ConfigValueMapper`, `AppConfig_Impl`, `AppConfigModule` |

Java output lands in `build/generated/sources/annotationProcessor/`, Kotlin in `build/generated/ksp/`.
**Never edit generated code to fix something** — regenerate.

### "Do I need to add the generated `*Module` to my `@KoraApp` extends clause?"

Not for modules generated in the same compilation — those are discovered automatically. A module
compiled in a *different* Gradle project needs `@KoraSubmodule` (stop 4).

### "Is Kora asynchronous?"

No, and this is the question most likely to be answered from stale knowledge. Kora 2.0 contracts are
**synchronous, executed on virtual threads** — the Undertow transport dispatches each request onto a
virtual thread. Writing blocking code is correct. See
[`kora-2-unlearning-reference.md`](kora-2-unlearning-reference.md) for what this replaced and how to
do real parallelism.

### "The build fails with hundreds of `package ru.tinkoff.kora does not exist` in files I never wrote"

Stale generator output in `build/generated` from an earlier state of the project. Fix it with
`./gradlew clean --continue`, then `./gradlew classes testClasses --continue --no-build-cache`.
Never by editing the generated files.

---

## Kotlin-specific notes

The curriculum is identical; four things differ and each has bitten a learner.

1. **The processor is KSP**, not `annotationProcessor`:
   `ksp("io.koraframework:symbol-processors")`, plugin `com.google.devtools.ksp` version `2.3.12`
   with Kotlin `2.4.20`. Mismatched Kotlin/KSP versions produce processor failures that look like
   framework bugs.
2. **Aspects need `open`.** An AOP-annotated Kotlin class and method must be `open`, or the aspect
   is silently not generated — no error, just no behaviour.
3. **Nullability is the type**, `T?`. Do not carry JSpecify annotations into Kotlin;
   `@field:Nullable` is not even a valid target under Kotlin 2.4. And because Kora contracts are
   `@NullMarked`, an override must match exactly: `HttpServerResponseMapper<T>.apply(request, result: T?)`
   written with a non-null `result` fails as `'apply' overrides nothing` — a message that never
   mentions nullability.
4. **No `suspend`.** Kora 2.0 has no suspend contracts for repositories, controllers or HTTP
   clients. This is the deepest change for a Kotlin learner arriving from 1.x; teach it from
   [`kora-2-unlearning-reference.md`](kora-2-unlearning-reference.md) before they write a line.
