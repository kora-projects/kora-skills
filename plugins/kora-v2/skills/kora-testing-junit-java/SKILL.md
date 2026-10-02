---
name: kora-testing-junit-java
description: "In-process JUnit 5 tests for Java Kora 2.0 services — io.koraframework:test-junit5 with @KoraAppTest, @TestComponent, KoraAppTestConfigModifier/KoraConfigModification, KoraAppTestGraphModifier/KoraGraphModification, KoraAppGraph, Mockito @Mock/@Spy plus @MockitoStrictness, the @KoraApp TestApplication submodule pattern behind -Akora.app.submodule.enabled=true, and Testcontainers for PostgreSQL/Kafka. Needs testAnnotationProcessor \"io.koraframework:annotation-processors\". Contracts are synchronous, so reactive/CompletionStage test shapes are gone, and HOCON embedded in KoraConfigModification.ofString must use 2.0 keys (jdbc, httpServer.port). Use when writing a Kora 2.0 Java test, mocking a component inside the graph, overriding test config, or starting a real database/broker. For Kotlin see kora-testing-junit-kotlin; for the packaged image see kora-testing-blackbox."
license: Apache-2.0
metadata:
  kora-version: "2.x"
---

# Kora Testing JUnit (Java)

> **Kora sub-skill — obey the [kora-v2 meta rules](../../SKILL.md) on every task:** **R0** ground the workspace on Kora 2.0 refs before starting (framework source at tag `2.0.0.RC2` + `kora-examples` at `migration/2.0` + Kora 2.0 docs at koraframework.io/v2, which trail the source; 1.x `kora-docs` pages are never an authority) · **R1** read this sub-skill before writing code · **R2** Kora 2.0 APIs only — no Spring/Micronaut/Quarkus, no Kora 1.x APIs, no invented annotations or config keys · **R3** journal any incorrect Kora usage. Add comments/Javadoc only if asked.

In-process JUnit 5 tests for **Java** Kora 2.0 services. `@KoraAppTest` loads the graph class
the annotation processor generated for your `@KoraApp`, trims it down to what the test actually
asks for, and injects those components into the test with `@TestComponent`. The production code
path is exercised as-is; selected nodes can be replaced by mocks or test-only components.

Everything lives in **`io.koraframework.test.extension.junit5`**, artifact
**`io.koraframework:test-junit5`**.

Three test levels:

- **Component test** — one component plus the dependencies needed to build it.
- **Inter-component test** — several real components interacting.
- **Integration test** — real components plus external systems (PostgreSQL, Kafka) via Testcontainers.

The Kora maintainers still recommend black-box testing of the packaged image as the primary
source of truth — see [kora-testing-blackbox](../kora-testing-blackbox/SKILL.md). For Kotlin
services (MockK, `lateinit var` injection, KSP wiring) use
[kora-testing-junit-kotlin](../kora-testing-junit-kotlin/SKILL.md) instead; this skill is Java-only.

---

## What changed from Kora 1.x

| 1.x | 2.0 |
|---|---|
| `ru.tinkoff.kora:test-junit5` | `io.koraframework:test-junit5` |
| `ru.tinkoff.kora.test.extension.junit5.*` | `io.koraframework.test.extension.junit5.*` |
| `ru.tinkoff.kora:kora-parent` BOM | `io.koraframework:kora-bom` |
| `@MockitoStrictness` in the root package | `io.koraframework.test.extension.junit5.mockito.MockitoStrictness` |
| `replaceComponent(type, List<Class<?>> tags, …)` | `replaceComponent(Type, @Nullable Class<?> tag, …)` — **one** tag class, or an overload with none |
| tests over `Mono`/`Flux`/`CompletionStage` contracts | contracts are synchronous; assert on the returned value |
| `Context` passed through test helpers | `Context` no longer exists anywhere in the framework |
| `db { … }` inside `ofString` | `jdbc { … }` |
| `publicApiHttpPort` / `privateApiHttpPort` | `httpServer.port` / `httpServer.system.port` |
| JUnit 5.x, Mockito 5.18 | JUnit **6.1.3**, Mockito **5.24.0** (Byte Buddy must accept Java 25) |

---

## Quick Start

### Dependencies

`gradle.properties`:

```properties
koraVersion=2.0.0.RC2
junitVersion=6.1.3
```

`build.gradle`:

```groovy
java {
    toolchain {
        languageVersion = JavaLanguageVersion.of(25)
    }
}

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
    testAnnotationProcessor "io.koraframework:annotation-processors"

    testImplementation platform("org.junit:junit-bom:$junitVersion")
    testImplementation "org.junit.jupiter:junit-jupiter"
    testImplementation "io.koraframework:test-junit5"
    testImplementation "org.mockito:mockito-core:5.24.0"
}

test {
    useJUnitPlatform()
    testLogging {
        showStandardStreams(true)
        events("passed", "skipped", "failed")
        exceptionFormat("full")
    }
}
```

Four things that are easy to get wrong:

1. **`testAnnotationProcessor "io.koraframework:annotation-processors"` is required** whenever the
   test source set declares its own `@KoraApp` (the `TestApplication` pattern). Without it no
   `TestApplicationGraph` is generated and the extension fails with *"Cannot find generated Kora
   application graph"*. Declaring it while `-proc:none` is set on `compileTestJava` silently
   disables it again.
2. **`kora-bom` constrains only `io.koraframework:*` artifacts.** JUnit, Mockito and Testcontainers
   versions are yours to pin — the BOM will not do it.
3. **`mockito-core` must be new enough for Java 25.** Kora 2.0 artifacts are class-file 69; an old
   Byte Buddy fails with `IllegalArgumentException: Java 25 (69) is not supported by the current
   version of Byte Buddy`, and it hides inside `Application graph failed to initialize with N errors`
   with no visible suppressed exception. Use `5.24.0` (Byte Buddy 1.18.x), which is what the
   framework's own version catalog pins.
4. **JVM 25 minimum.** Kora 2.0 class files cannot be loaded on anything older.

`test-junit5` already exposes `org.junit.jupiter:junit-jupiter` and
`org.junit.platform:junit-platform-launcher` as `api` dependencies at the framework's JUnit
version; declaring the JUnit BOM yourself keeps the version explicit and under your control.
Mockito is `compileOnly` inside `test-junit5`, so you must add it.

### Component test (real graph)

```java
@KoraAppTest(Application.class)
class UserServiceComponentTest {

    @TestComponent
    private UserService userService;

    @Test
    void createUserWithRealGraph() {
        var result = userService.createUser(new UserRequest("John", "john@example.com"));

        assertNotNull(result);
        assertEquals("John", result.name());
    }
}
```

`@KoraAppTest(Application.class)` names the `@KoraApp` interface whose generated
`ApplicationGraph` class is loaded. `@TestComponent` makes `userService` both an injection
target and a root of the trimmed graph: Kora keeps it and its transitive dependencies and
prunes everything else.

### Component test with a Mockito mock

```java
@KoraAppTest(Application.class)
class UserServiceComponentTest {

    @Mock
    @TestComponent
    private UserRepository userRepository;

    @TestComponent
    private UserService userService;

    @Test
    void getUserUsesRepositoryMock() {
        var expected = new UserResponse("1", "John", "john@example.com", LocalDateTime.now());
        when(userRepository.findById("1")).thenReturn(Optional.of(expected));

        var result = userService.getUser("1");

        assertEquals(Optional.of(expected), result);
        verify(userRepository).findById("1");
    }
}
```

`@Mock` **plus** `@TestComponent` replaces the `UserRepository` node in the graph, so the real
`UserService` receives the mock through its constructor and the test field points at the same
instance. `@Mock` on its own is invisible to the extension — it only reacts to elements that
also carry `@TestComponent`.

Do not add `@ExtendWith(MockitoExtension.class)`. `@KoraAppTest` already reads `org.mockito.Mock`
and `org.mockito.Spy`, creates the mocks, injects them into the graph, resets them between methods
and reports unused stubbing itself; the second extension would create a parallel set of mocks that
never reaches the graph.

---

## Core API

| Element | Fully-qualified name | Purpose |
|---|---|---|
| `@KoraAppTest(App.class)` | `io.koraframework.test.extension.junit5.KoraAppTest` | Build a test graph from a `@KoraApp` interface; attributes `value`, `components`, `modules` |
| `@TestComponent` | `io.koraframework.test.extension.junit5.TestComponent` | Mark a field, constructor parameter or test-method parameter as a graph root and injection target |
| `KoraAppTestConfigModifier` | `io.koraframework.test.extension.junit5.KoraAppTestConfigModifier` | `KoraConfigModification config()` — supply the config for the test |
| `KoraConfigModification` | `io.koraframework.test.extension.junit5.KoraConfigModification` | `ofString` / `ofResourceFile` / `ofSystemProperty` / `withSystemProperty(-ies)` |
| `KoraAppTestGraphModifier` | `io.koraframework.test.extension.junit5.KoraAppTestGraphModifier` | `KoraGraphModification graph()` — add / replace / mock nodes |
| `KoraGraphModification` | `io.koraframework.test.extension.junit5.KoraGraphModification` | `create()`, `addComponent`, `replaceComponent`, `mockComponent` |
| `KoraAppGraph` | `io.koraframework.test.extension.junit5.KoraAppGraph` | Injectable graph view: `getFirst` / `findFirst` / `getAll` by `Class` or `Type` (+ tag) |
| `@MockitoStrictness(...)` | `io.koraframework.test.extension.junit5.mockito.MockitoStrictness` | Mockito stub strictness for the class; default is `Strictness.WARN` |
| `@Tag(X.class)` | `io.koraframework.common.annotation.Tag` | Select a tagged component at the injection point |
| `TypeRef.of(...)` | `io.koraframework.application.graph.TypeRef` | Describe a generic component type to the modifiers |
| `@Mock` / `@Spy` | `org.mockito` | Stub / partial-stub; always combined with `@TestComponent` |

`@KoraAppTest` attributes:

- `value` — required, the `@KoraApp` interface.
- `components` — `Class[]` of extra components to keep as graph roots (not injected anywhere).
- `modules` — `Class[]` of `@Module` **interfaces**; every factory method's return type becomes a
  root. A non-interface entry is rejected with an `ExtensionConfigurationException`.

```java
@KoraAppTest(value = Application.class,
             components = { SomeComponent.class },
             modules = { SomeModule.class })
class SomeTests { }
```

**Rule:** every `@TestComponent` must resolve to exactly one node in the graph. The component you
inject is itself a root, so a service that pulls in its own dependencies is fine. A component
nobody depends on is pruned unless it is `@Root` in the application graph, listed in
`components`, or reachable from a `modules` entry. Two matching nodes produce *"Expected one
matching graph component, but found N"* — add a `@Tag` to disambiguate.

Details in [references/korapptest-extension-reference.md](references/korapptest-extension-reference.md).

---

## Test configuration

Implement `KoraAppTestConfigModifier` on the test class. It cannot be combined with constructor
injection — the extension builds the graph while resolving constructor parameters, before the test
instance exists, and rejects the combination with an explicit error.

```java
@KoraAppTest(Application.class)
class SomeTests implements KoraAppTestConfigModifier {

    @Override
    public KoraConfigModification config() {
        return KoraConfigModification
            .ofSystemProperty("POSTGRES_JDBC_URL", "jdbc:postgresql://localhost:5432/postgres")
            .withSystemProperty("POSTGRES_USER", "postgres")
            .withSystemProperty("POSTGRES_PASS", "postgres");
    }
}
```

| Factory | Effect |
|---|---|
| `ofSystemProperty(k, v)` / `.withSystemProperty(k, v)` | Sets a JVM system property for the test. System properties are the highest-priority config layer, so this both fills `${PLACEHOLDER}` substitutions in the real `application.conf` and adds top-level keys |
| `ofResourceFile("application-test.conf")` | Sets `config.resource` — the named classpath file **replaces** `application.conf` |
| `ofString("""…""")` | Writes the text to a temp file and sets `config.file` — the inline text **replaces** `application.conf` |

`ofString` and `ofResourceFile` are replacements, not overlays: whatever the production
`application.conf` contained is gone for that test, and every key the graph needs must be present
in the block. Setting both `config.file` and `config.resource` is rejected with *"Application
config source is ambiguous"*.

### ⚑ HOCON inside `ofString` must use 2.0 keys

This is the single highest-value thing to check when porting a 1.x test. The block lives in Java
source, so resource-only config scanners and migration scripts never see it, and a stale key is
simply an unknown HOCON key: ignored without a warning.

```java
@Override
public KoraConfigModification config() {
    return KoraConfigModification.ofString("""
            jdbc {                                  // 1.x: db { … }
              jdbcUrl = ${POSTGRES_JDBC_URL}
              username = ${POSTGRES_USER}
              password = ${POSTGRES_PASS}
              poolName = "kora-test"
            }
            flyway {
              locations = "db/migration"
            }
            httpServer {
              port = 0                              // 1.x: publicApiHttpPort
              system.port = 0                       // 1.x: privateApiHttpPort
              telemetry.metrics.enabled = true      // defaults to false in 2.0
            }
            """)
        .withSystemProperty("POSTGRES_JDBC_URL", POSTGRES.getJdbcUrl())
        .withSystemProperty("POSTGRES_USER", POSTGRES.getUsername())
        .withSystemProperty("POSTGRES_PASS", POSTGRES.getPassword());
}
```

- `db { … }` → **`jdbc { … }`**. Symptom of leaving it: `ConfigValueException: Config expected
  value, but got null at path: 'ROOT.jdbc.username'`.
- `publicApiHttpPort` → **`httpServer.port`**, `privateApiHttpPort` → **`httpServer.system.port`**,
  `privateApiHttpReadinessPath|LivenessPath|MetricsPath` → **`httpServer.system.readinessPath|
  livenessPath|metricsPath`**. The stale keys do not collide: `SystemHttpServerConfig` overrides
  `port()` to `8085`, so each server just falls back to its own default (8080 public, 8085 system)
  and the test binds ports the test never meant to use.
- `port = 0` is worth knowing: Undertow binds an ephemeral port and the injected
  `io.koraframework.http.server.common.HttpServer` component reports the real one from `port()`,
  so parallel test classes never collide on 8080.
- `telemetry.logging.enabled` and `telemetry.metrics.enabled` default to **`false`**. A test that
  asserts on Kora component metrics (`http_server_*`, `db_*`) must enable them for that component;
  without it the meters are simply never registered. Tracing defaults to `true`, except under
  `httpServer.system`, where it is overridden to `false`.
- A `resilient.circuitbreaker.<name>` block needs `countBased.windowSize` — `type` is optional
  (default `STRIPED_APPROX`, which still requires `countBased`), but set it explicitly — plus
  `minimumRequiredCalls`, `failureRateThreshold`, `permittedCallsInHalfOpenState` and
  `waitDurationInOpenState`, which have no defaults. Omitting `countBased` fails graph
  initialization with `IllegalArgumentException: CircuitBreaker '<name>' property 'countBased' is
  not configured` (`slidingWindowSize` from 1.x no longer exists).

```java
return KoraConfigModification.ofString("""
        resilient {
          circuitbreaker.pet {
            type = FIXED_WINDOW
            countBased.windowSize = 2
            minimumRequiredCalls = 2
            failureRateThreshold = 100
            permittedCallsInHalfOpenState = 1
            waitDurationInOpenState = 15s
          }
          timeout.pet.duration = 5000ms
          retry.pet { delay = 100ms, attempts = 0 }
        }""");
```

---

## Graph modification

Implement `KoraAppTestGraphModifier` to add, replace or mock nodes. Constructor injection is
forbidden here too, for the same reason as the config modifier.

```java
@KoraAppTest(Application.class)
class SomeTests implements KoraAppTestGraphModifier {

    @Override
    public KoraGraphModification graph() {
        return KoraGraphModification.create()
            .addComponent(TypeRef.of(Supplier.class, Integer.class),
                          () -> (Supplier<Integer>) () -> 1);
    }

    @Test
    void example(@TestComponent Supplier<Integer> supplier) {
        assertEquals(1, supplier.get());
    }
}
```

Every method takes a `java.lang.reflect.Type` (a `Class` or a `TypeRef`), an **optional single
`Class<?>` tag**, and either a `Supplier<T>` or a `Function<KoraAppGraph, T>` when the new value
must be built from components already in the graph:

- `addComponent(type[, tag], supplier | graph -> value)` — add a node that was not there.
- `replaceComponent(type[, tag], supplier | graph -> value)` — replace a node; the `Function`
  form keeps the replaced node's dependencies in the graph, the `Supplier` form drops them.
- `mockComponent(type[, tag], supplier)` — replace with a stand-in and drop the original's
  dependencies.

The tag argument is a single class (`LifecycleComponent.class`), **not** a `List` as in Kora 1.x;
passing `null` is the same as calling the overload without it.

Full API in [references/korapptest-extension-reference.md](references/korapptest-extension-reference.md).

---

## Mocking with Mockito

`@Mock` and `@Spy` work on fields, constructor parameters and test-method parameters, always
together with `@TestComponent`. `@Spy` keeps the original behaviour: with a field initializer it
spies that instance, without one it spies the instance the graph builds.

```java
@Spy
@TestComponent
private Supplier<String> component1 = () -> "12345";
```

`@MockitoStrictness(Strictness.STRICT_STUBS)` on the class makes unused stubs fail the test; the
default when the annotation is absent is `Strictness.WARN`, which logs them. Mockito's
`Strictness` enum has exactly `LENIENT`, `WARN` and `STRICT_STUBS`.

Method-parameter mocks are incompatible with `@TestInstance(PER_CLASS)` — one graph is shared by
all methods, so the extension rejects per-method mocks with an explicit error.

See [references/mockito-integration-reference.md](references/mockito-integration-reference.md).

---

## Integration tests with Testcontainers

`kora-bom` does not pin Testcontainers. The migrated Kora 2.0 examples pin **Testcontainers
1.21.4** (`org.testcontainers:junit-jupiter`, `org.testcontainers:postgresql`), often via the
`io.goodforgod:testcontainers-extensions-*:0.15.0` helpers. If you move to Testcontainers 2.x the
module names change to `org.testcontainers:testcontainers-postgresql`,
`testcontainers-kafka`, `testcontainers-cassandra`. `org.testcontainers:junit-jupiter` is a
Testcontainers artifact — never align its version with the JUnit BOM.

### PostgreSQL + Flyway

```groovy
dependencies {
    testRuntimeOnly "org.postgresql:postgresql:42.7.3"
    testImplementation "org.testcontainers:junit-jupiter:1.21.4"
    testImplementation "org.testcontainers:postgresql:1.21.4"
    testImplementation "io.koraframework:database-jdbc"
    testImplementation "io.koraframework:database-flyway"
    testImplementation "org.flywaydb:flyway-database-postgresql:13.9.0"
}
```

`io.koraframework:database-flyway` ships `flyway-core` only — without the dialect artifact
migrations fail at startup with `Unsupported Database: PostgreSQL`.

```java
@Testcontainers
@KoraAppTest(TestApplication.class)
class UserServiceIntegrationPostgresTest implements KoraAppTestConfigModifier {

    @Container
    static final PostgreSQLContainer<?> POSTGRES =
        new PostgreSQLContainer<>("postgres:16-alpine")
            .withStartupTimeout(Duration.ofSeconds(30))
            .withLogConsumer(new Slf4jLogConsumer(LoggerFactory.getLogger(PostgreSQLContainer.class)));

    @TestComponent
    private UserService userService;

    @TestComponent
    private TestApplication.TestUserRepository testUserRepository;

    @Override
    public KoraConfigModification config() {
        return KoraConfigModification.ofString("""
            jdbc {
              jdbcUrl = ${POSTGRES_JDBC_URL}
              username = ${POSTGRES_USER}
              password = ${POSTGRES_PASS}
              poolName = "kora-test"
            }
            flyway {
              locations = "db/migration"
            }
            """)
            .withSystemProperty("POSTGRES_JDBC_URL", POSTGRES.getJdbcUrl())
            .withSystemProperty("POSTGRES_USER", POSTGRES.getUsername())
            .withSystemProperty("POSTGRES_PASS", POSTGRES.getPassword());
    }

    @BeforeEach
    void cleanup() {
        testUserRepository.deleteAll();
    }
}
```

See [references/testcontainers-jdbc-reference.md](references/testcontainers-jdbc-reference.md).

### Kafka

The broker address goes into the **per-consumer / per-producer** `driverProperties` of the Kora
Kafka config — there is no flat `kafka.bootstrapServers` key. A consumer with a `group.id` reads
from the beginning via `"auto.offset.reset" = "earliest"` in `driverProperties`; the
`KafkaListenerConfig.offset` key applies to the assign strategy (no `group.id`). Kafka consumers
are usually not reachable from any injected component, so pull them in with
`@KoraAppTest(modules = ...ConsumerModule.class)` or by injecting the tagged consumer `Lifecycle`.

See [references/testcontainers-kafka-reference.md](references/testcontainers-kafka-reference.md).

---

## TestApplication submodule pattern

When tests need components the production graph never wires (a cleanup repository, for example),
declare a second `@KoraApp` in the test source set that extends the production one:

```java
@KoraApp
public interface TestApplication extends Application {

    @Repository
    interface TestUserRepository extends JdbcRepository {

        @Query("SELECT id, name, email, created_at FROM users ORDER BY id")
        List<UserDAO> findAll();

        @Query("DELETE FROM users")
        void deleteAll();
    }

    @Tag(TestApplication.class)
    @Root
    default String testRoot(TestUserRepository ignored) {
        return "test-root";
    }
}
```

The `@Root` default method forces the otherwise-unused repository into the graph. (The equivalent
in the `kora-java-crud` example is to put `@Root @Component` directly on the nested `@Repository`
interface — both are source-backed.)

Two build settings are needed, in **different** modules:

```groovy
// the PRODUCTION module that declares the original @KoraApp
tasks.named("compileJava", JavaCompile) {
    options.compilerArgs += ["-Akora.app.submodule.enabled=true"]
}

// the module that owns the test sources
dependencies {
    testAnnotationProcessor "io.koraframework:annotation-processors"
}
test {
    filter {
        excludeTestsMatching '*$*'
        excludeTestsMatching "*TestApplication"
    }
}
```

`-Akora.app.submodule.enabled=true` makes `KoraSubmoduleProcessor` emit
`<Application>SubmoduleImpl` next to the app. When the test compilation cannot find it, the
processor emits a **warning**, not an error:
`Expected @KoraApp as SubModule, but Submodule implementation not found for: …` — the build stays
green and the parent application's components are simply missing from the test graph, which
surfaces much later as *"No matching component was found in the application graph"*.

---

## Assertions

Kora contracts are synchronous, so a component test asserts on the returned value. Standard
JUnit Jupiter assertions cover most cases (`assertEquals`, `assertNotNull`, `assertAll`,
`assertThrows`); AssertJ adds fluent checks; Mockito's `verify`/`ArgumentCaptor` check
interactions; Awaitility covers genuinely asynchronous side effects such as a Kafka listener.
**`StepVerifier` and other Reactor test helpers no longer apply** — `Mono`/`Flux` and
`CompletionStage` are not Kora 2.0 contracts. Catalog in
[references/assertion-patterns-reference.md](references/assertion-patterns-reference.md).

---

## Templates (assets/)

| Template | Purpose |
|----------|---------|
| [ComponentTest.java.template](assets/ComponentTest.java.template) | Component test with a Mockito mock dependency and an inline config block |
| [ComponentTestWithMock.java.template](assets/ComponentTestWithMock.java.template) | Annotated component-test scaffold with given/when/then |
| [IntegrationTest.java.template](assets/IntegrationTest.java.template) | PostgreSQL via plain `@Testcontainers` + `PostgreSQLContainer` |
| [IntegrationTestWithPostgres.java.template](assets/IntegrationTestWithPostgres.java.template) | PostgreSQL via the `io.goodforgod` `@TestcontainersPostgreSQL` extension with Flyway migrations |
| [IntegrationTestWithKafka.java.template](assets/IntegrationTestWithKafka.java.template) | Kafka Testcontainers producer/consumer test with Awaitility |
| [TestApplication.java.template](assets/TestApplication.java.template) | `TestApplication` submodule, `@Root` default-method style |
| [TestApplicationWithCleanup.java.template](assets/TestApplicationWithCleanup.java.template) | `TestApplication` submodule, `@Root @Component @Repository` style with truncate |
| [MockTemplate.java.template](assets/MockTemplate.java.template) | Mockito pattern catalog (mock, spy, verify, captor, strictness) |

---

## References

- [KoraAppTest Extension](references/korapptest-extension-reference.md) — `@KoraAppTest`, `@TestComponent`, `@Tag`, `KoraAppGraph`, config/graph modifiers, lifecycle
- [Mockito Integration](references/mockito-integration-reference.md) — `@Mock`, `@Spy`, strictness, matchers, verify, the Byte Buddy floor
- [Testcontainers JDBC](references/testcontainers-jdbc-reference.md) — PostgreSQL, Flyway, `TestApplication` submodule, build wiring
- [Testcontainers Kafka](references/testcontainers-kafka-reference.md) — container options, real 2.0 Kafka config, async verification
- [Assertion Patterns](references/assertion-patterns-reference.md) — JUnit 5, AssertJ, Awaitility, verify, captor, metrics

---

## Related skills

- [kora-testing-junit-kotlin](../kora-testing-junit-kotlin/SKILL.md) — the same extension from Kotlin (MockK, KSP)
- [kora-testing-blackbox](../kora-testing-blackbox/SKILL.md) — testing the packaged image end to end
- [kora-project-setup-java](../kora-project-setup-java/SKILL.md) — BOM, toolchain, annotation processor wiring
- [kora-config-hocon](../kora-config-hocon/SKILL.md) — the config keys an `ofString` block must use
- [kora-database-jdbc](../kora-database-jdbc/SKILL.md) — repositories under test, the `jdbc` config section
- [kora-kafka-consumer](../kora-kafka-consumer/SKILL.md) · [kora-kafka-producer](../kora-kafka-producer/SKILL.md) — listener/publisher config paths
- [kora-telemetry-metrics](../kora-telemetry-metrics/SKILL.md) — enabling metrics a test asserts on
- [kora-di-runtime](../kora-di-runtime/SKILL.md) — `@Root`, `Lifecycle`, `@Tag`, why a node gets pruned

---

## Common pitfalls

| Symptom | Fix |
|---------|-----|
| `Cannot find generated Kora application graph for: …TestApplication` | Add `testAnnotationProcessor "io.koraframework:annotation-processors"`, and make sure `-proc:none` is not set on `compileTestJava` |
| `Expected @KoraApp as SubModule …` (warning) then a missing component at runtime | Add `-Akora.app.submodule.enabled=true` to the **production** module's `compileJava` |
| `No matching component was found in the application graph` | The node was pruned — inject something that depends on it, mark it `@Root`, or list it in `components` / `modules` |
| Same message for `@TestComponent JsonReader<Dto>` | `@TestComponent` only selects nodes that already exist in the application graph, and the JSON extension creates `JsonReader<T>` only where a component reads `T` — an app that only writes `Dto` has a `JsonWriter<Dto>` node and no reader. Parse the body in the test itself (or assert on the raw string) |
| A `@KoraAppTest` whose graph contains a `@Conditional` component (any full-graph test of such an app) fails to initialize: `IllegalArgumentException: Graph node belongs to another application graph` from `GraphImpl$GraphConditionKey.hashCode` | The extension always runs the draw through `ApplicationGraphDraw.copy()` (and `subgraph()` when roots or mocks are declared); both rebind factory node references but keep the original node condition, which then looks up the original condition node on the derived graph. Fixed in `2.0.0.RC2` (kora-projects/kora PR #963) — only `2.0.0.RC1` is affected. On RC1 there is no practical workaround short of keeping `@Conditional` out of the graph under test |
| `@TestInstance(PER_CLASS)` tests fail in `beforeEach` (`KoraJUnit5Extension.resetMocks`) with `Graph node value was not initialized because condition failed` | With Mockito (or MockK) on the classpath, `resetMocks` reads every graph node, and a `@Conditional` node whose condition failed throws on read; `KoraAppGraph.getAll` throws the same way instead of skipping it like `All<T>`. Reachable only with #963 in place. Fixed in `2.0.0.RC2` (kora-projects/kora PR #964) — only `2.0.0.RC1` is affected; on RC1 use the default `PER_METHOD` lifecycle and avoid `getAll` over that type |
| `Expected one matching graph component, but found N` | Add `@Tag(X.class)` at the injection point |
| `Java 25 (69) is not supported by the current version of Byte Buddy`, or `Application graph failed to initialize with N errors` with no cause | Bump `mockito-core` to `5.24.0`; check with `dependencyInsight --dependency byte-buddy --configuration testRuntimeClasspath` |
| `Config expected value, but got null at path: 'ROOT.jdbc.username'` | The `ofString` block still says `db { … }` |
| Metrics assertions see nothing | `telemetry.metrics.enabled` defaults to `false`; enable it per component in the test config |
| `Application config source is ambiguous` | Only one of `ofString` / `ofResourceFile` per test class |
| Mock behaviour ignored / duplicated mocks | Remove `@ExtendWith(MockitoExtension.class)` — `@KoraAppTest` owns the Mockito lifecycle |
| `@Mock` field stays `null` | `@Mock` alone is invisible to the extension; add `@TestComponent` |
| `Cannot use KoraAppTestConfigModifier with @KoraAppTest constructor injection` | Use field or test-method injection instead of a constructor |
| JUnit tries to run generated `$…` classes or `TestApplication` | `test { filter { excludeTestsMatching '*$*'; excludeTestsMatching "*TestApplication" } }` |
| Test written around `Mono`/`Flux`/`CompletionStage`/`Context` | Those contracts are gone in 2.0 — assert on the value the synchronous method returns |

---

## Source of truth

Version-aligned authorities for Kora 2.0, highest first. The Kora 2.0 documentation
([JUnit5](https://koraframework.io/v2/en/documentation/junit5/)) explains concepts but can trail the
framework — confirm every annotation, attribute and message in the source below. The 1.x pages
(`ru.tinkoff.kora`) are never an authority for 2.0.

- Framework source, tag `2.0.0.RC2`:
  [test/test-junit5](https://github.com/kora-projects/kora/tree/2.0.0.RC2/test/test-junit5) (main sources and the extension's own tests) ·
  [telemetry-common](https://github.com/kora-projects/kora/tree/2.0.0.RC2/telemetry/telemetry-common) ·
  [http-server-common](https://github.com/kora-projects/kora/tree/2.0.0.RC2/http/http-server-common)
- Migrated guide apps, branch `migration/2.0`:
  [kora-java-guide-testing-junit-app](https://github.com/kora-projects/kora-examples/tree/migration/2.0/guides/java/kora-java-guide-testing-junit-app) ·
  [kora-java-guide-testing-integration-app](https://github.com/kora-projects/kora-examples/tree/migration/2.0/guides/java/kora-java-guide-testing-integration-app) ·
  [kora-java-guide-messaging-kafka-app](https://github.com/kora-projects/kora-examples/tree/migration/2.0/guides/java/kora-java-guide-messaging-kafka-app) ·
  [kora-java-guide-observability-app](https://github.com/kora-projects/kora-examples/tree/migration/2.0/guides/java/kora-java-guide-observability-app)
- Migrated examples, branch `migration/2.0`:
  [kora-java-crud](https://github.com/kora-projects/kora-examples/tree/migration/2.0/examples/java/kora-java-crud) ·
  [kora-java-kafka](https://github.com/kora-projects/kora-examples/tree/migration/2.0/examples/java/kora-java-kafka)
