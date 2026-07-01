---
name: kora-testing-junit-java
description: "In-process JUnit 5 component and integration tests for Java Kora services. Covers @KoraAppTest, @TestComponent, @Mock/@Spy via Mockito, @Tag injection, KoraAppTestConfigModifier and KoraAppTestGraphModifier (KoraConfigModification, KoraGraphModification, TypeRef), the @KoraApp TestApplication submodule pattern, and Testcontainers (PostgreSQL + Flyway, Kafka). Use when writing JUnit 5 tests against a Kora dependency graph, mocking a component inside the graph, overriding test config/env, or spinning up a real database/broker. Artifact ru.tinkoff.kora:test-junit5."
---

# Kora Testing JUnit (Java)

In-process JUnit 5 tests for **Java** Kora services. `@KoraAppTest` builds a trimmed
version of your compile-time dependency graph, then injects the components you ask for
with `@TestComponent`. The same code that runs in production is exercised in the test;
selected dependencies can be replaced by mocks or test-only components.

Kora supports three test levels:

- **Component test** — one component plus the dependencies needed to build it.
- **Inter-component test** — several real components interacting.
- **Integration test** — real components plus external systems (PostgreSQL, Kafka) via Testcontainers.

For end-to-end confidence the Kora maintainers also recommend black-box testing of the
packaged image (see the `kora-testing-blackbox` skill).

---

## Quick Start

### Dependencies

```groovy
dependencies {
    koraBom platform("ru.tinkoff.kora:kora-parent:1.2.17")

    annotationProcessor "ru.tinkoff.kora:annotation-processors"

    testImplementation platform("org.junit:junit-bom:5.13.4")
    testImplementation "org.junit.jupiter:junit-jupiter"
    testImplementation "ru.tinkoff.kora:test-junit5"
    testImplementation "org.mockito:mockito-core:5.18.0"
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

The `kora-parent` BOM pins every `ru.tinkoff.kora:*` artifact — never set their versions
individually. The annotation processor is mandatory: without it the `@KoraApp` graph is
never generated and `@KoraAppTest` has nothing to load.

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

`@KoraAppTest(Application.class)` names the `@KoraApp` interface to use as the graph
source. `@TestComponent` makes `userService` both a requested injection target and a root
of the trimmed graph: Kora walks its constructor and adds only the dependencies it needs.

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

`@Mock` + `@TestComponent` injects the same mock into the test field **and** into every
graph component that needs a `UserRepository`, so the real `UserService` receives it
through its constructor. Do not add `@ExtendWith(MockitoExtension.class)` — `@KoraAppTest`
manages the mock lifecycle and the two extensions conflict.

---

## Core annotations

| Annotation | Origin | Purpose |
|------------|--------|---------|
| `@KoraAppTest(App.class)` | `ru.tinkoff.kora.test.extension.junit5` | Build a test graph from a `@KoraApp` interface; params `value`, `components`, `modules` |
| `@TestComponent` | `ru.tinkoff.kora.test.extension.junit5` | Inject a graph component into a field, constructor param, or test method param; marks it a graph root |
| `@Tag(X.class)` | `ru.tinkoff.kora.common` | Disambiguate a tagged component at the injection point |
| `@Mock` / `@Spy` | `org.mockito` | Stub / partial-stub a component; combine with `@TestComponent` |
| `@MockitoStrictness(...)` | `ru.tinkoff.kora.test.extension.junit5` | Set Mockito stub strictness for the test |

`@KoraAppTest` parameters:

- `value` — required; the `@KoraApp` interface.
- `components` — optional `Class[]` of components to initialize.
- `modules` — optional `Class[]` of extra `*Module` interfaces to include.

```java
@KoraAppTest(value = Application.class,
             components = { SomeComponent.class },
             modules = { SomeModule.class })
class SomeTests { }
```

**Rule:** every `@TestComponent` must be reachable from a graph root. The component you
inject is itself a root, so a service that pulls in its own dependencies is fine. A
standalone component nobody uses will be trimmed out unless it is annotated `@Root` in the
application graph.

See [references/korapptest-extension-reference.md](references/korapptest-extension-reference.md)
for injection styles, `@Tag`, lifecycle, and parameter details.

---

## Test config and graph modification

### KoraAppTestConfigModifier

Implement this interface on the test class to override or supply configuration. It must
not be used via the constructor (the config is needed before construction).

```java
@KoraAppTest(Application.class)
class SomeTests implements KoraAppTestConfigModifier {

    @NotNull
    @Override
    public KoraConfigModification config() {
        return KoraConfigModification
            .ofSystemProperty("POSTGRES_JDBC_URL", "jdbc:postgresql://localhost:5432/postgres")
            .withSystemProperty("POSTGRES_USER", "postgres")
            .withSystemProperty("POSTGRES_PASS", "postgres");
    }
}
```

`KoraConfigModification` factory methods:

- `ofSystemProperty(name, value)` / `.withSystemProperty(...)` — substitute env-style
  placeholders in the real `application.conf`/`application.yaml`.
- `ofResourceFile("application-test.conf")` — load a test config file.
- `ofString("""...""")` — inline config; replaces all config files for the test.

### KoraAppTestGraphModifier

Implement this interface to add or replace components in the graph (also constructor-forbidden).

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

`replaceComponent(TypeRef, List<Class<?>> tags, supplier)` swaps an existing component;
the middle argument is the list of `@Tag` classes attached to the target. Both
`addComponent` and `replaceComponent` have an overload taking a `graph -> ...` lambda so
you can build the new value from an existing component via `graph.getFirst(TypeRef.of(...))`.

See [references/korapptest-extension-reference.md](references/korapptest-extension-reference.md)
for the full modifier API.

---

## Mocking with Mockito

`@Mock` and `@Spy` (plus their parameters) work alongside `@TestComponent`; Kora injects
the mock/spy into the graph. `@Spy` keeps the original behavior and lets you override
selected methods, e.g. from a field initializer:

```java
@Spy
@TestComponent
private Supplier<String> component1 = () -> "12345";
```

`@MockitoStrictness(Strictness.STRICT_STUBS)` on the test class flags unused stubs with
`UnnecessaryStubbingException`.

See [references/mockito-integration-reference.md](references/mockito-integration-reference.md)
for stubbing chains, argument matchers, `ArgumentCaptor`, and `verify` patterns.

---

## Integration tests with Testcontainers

### PostgreSQL + Flyway

```groovy
dependencies {
    testRuntimeOnly "org.postgresql:postgresql:42.7.3"
    testImplementation "org.testcontainers:junit-jupiter:1.21.4"
    testImplementation "org.testcontainers:postgresql:1.21.4"
    testImplementation "ru.tinkoff.kora:database-jdbc"
    testImplementation "ru.tinkoff.kora:database-flyway"
}
```

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

    @NotNull
    @Override
    public KoraConfigModification config() {
        return KoraConfigModification.ofString("""
            db {
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

See [references/testcontainers-jdbc-reference.md](references/testcontainers-jdbc-reference.md)
for the `TestApplication` submodule pattern, build wiring, and CRUD test examples.

### Kafka

Use a `KafkaContainer` and feed its bootstrap servers into the **per-listener**
`driverProperties` of your Kora Kafka config (Kora has no flat `kafka.bootstrapServers`
key). See [references/testcontainers-kafka-reference.md](references/testcontainers-kafka-reference.md)
for the correct config shape and async verification with Awaitility.

---

## TestApplication submodule pattern

When tests need components that the production graph never wires (e.g. a cleanup
repository), declare a second `@KoraApp` in the test source set that extends the
production one:

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

The `@Root` default method forces the otherwise-unused repository into the graph. This
requires submodule generation on the **production application module** plus the test
annotation processor — details in
[references/testcontainers-jdbc-reference.md](references/testcontainers-jdbc-reference.md).

---

## Assertions

Standard JUnit Jupiter assertions cover most cases (`assertEquals`, `assertNotNull`,
`assertTrue`, `assertThrows`). AssertJ (`org.assertj:assertj-core`) adds fluent checks and
`assertThatThrownBy`; Mockito's `verify`/`ArgumentCaptor` check interactions. For reactive
return types add `io.projectreactor:reactor-test` and use `StepVerifier`. Full catalog in
[references/assertion-patterns-reference.md](references/assertion-patterns-reference.md).

---

## Templates (assets/)

| Template | Purpose |
|----------|---------|
| [ComponentTest.java.template](assets/ComponentTest.java.template) | Component test with a Mockito mock dependency |
| [ComponentTestWithMock.java.template](assets/ComponentTestWithMock.java.template) | Annotated component test scaffold with given/when/then |
| [IntegrationTest.java.template](assets/IntegrationTest.java.template) | PostgreSQL Testcontainers CRUD test |
| [IntegrationTestWithPostgres.java.template](assets/IntegrationTestWithPostgres.java.template) | PostgreSQL + Flyway test |
| [IntegrationTestWithKafka.java.template](assets/IntegrationTestWithKafka.java.template) | Kafka Testcontainers producer/consumer test |
| [TestApplication.java.template](assets/TestApplication.java.template) | TestApplication submodule with cleanup repository |
| [TestApplicationWithCleanup.java.template](assets/TestApplicationWithCleanup.java.template) | TestApplication with deleteAll/truncate/findAll |
| [MockTemplate.java.template](assets/MockTemplate.java.template) | Mockito pattern catalog (mock, spy, verify, captor) |

---

## References

- [KoraAppTest Extension](references/korapptest-extension-reference.md) — `@KoraAppTest`, `@TestComponent`, `@Tag`, config/graph modifiers, lifecycle
- [Mockito Integration](references/mockito-integration-reference.md) — `@Mock`, `@Spy`, strictness, matchers, verify
- [Testcontainers JDBC](references/testcontainers-jdbc-reference.md) — PostgreSQL, Flyway, TestApplication submodule, build wiring
- [Testcontainers Kafka](references/testcontainers-kafka-reference.md) — `KafkaContainer`, real Kora Kafka config, async verification
- [Assertion Patterns](references/assertion-patterns-reference.md) — JUnit 5, AssertJ, StepVerifier, verify, captor

---

## Common pitfalls

| Symptom | Fix |
|---------|-----|
| Injected component is `null` | Make it reachable from a graph root; mark the application component `@Root` or inject something that depends on it |
| Mock behavior ignored / lifecycle errors | Remove `@ExtendWith(MockitoExtension.class)` — it conflicts with `@KoraAppTest` |
| Container never starts | Start the Docker daemon; raise `withStartupTimeout(...)` |
| `Expected @KoraApp as SubModule` | Add `-Akora.app.submodule.enabled=true` to the production module's `compileJava` |
| JUnit tries to run generated `$...Impl` classes | Exclude them: `test { filter { excludeTestsMatching '*$*' } }` |
| Config override not applied | Implement `KoraAppTestConfigModifier` via the interface method, not the constructor |
