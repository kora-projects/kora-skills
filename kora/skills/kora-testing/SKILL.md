---
name: kora-testing
description: Test Kora applications with @KoraAppTest component tests, @TestComponent mocks, Mockito/MockK, KoraAppTestConfigModifier, KoraAppTestGraphModifier, AppContainer black-box tests, TestApplication for test-only components, and Testcontainers (PostgreSQL, Cassandra, Kafka). Use both in-process tests for speed and black-box tests for production realism. Triggers: @KoraAppTest, @TestComponent, Mockito, MockK, Testcontainers, AppContainer, integration tests, component tests, black-box tests.
---

# Kora Testing — In-Process + Black-Box Testing

Read this first when:
- adding first test to a Kora service (component, integration, or black-box),
- choosing between `@KoraAppTest` component tests vs `AppContainer` black-box tests,
- wiring `@TestComponent` mocks with Mockito or MockK,
- configuring test DI graph via `KoraAppTestConfigModifier` or `KoraAppTestGraphModifier`,
- using Testcontainers for PostgreSQL, Kafka, or other infrastructure,
- creating test-only components with `TestApplication` (DB cleanup, stubs).

## Quick Start

### 1. Dependencies

```groovy
dependencies {
    testImplementation "ru.tinkoff.kora:test-junit5"
    
    // Java
    testImplementation "org.mockito:mockito-core:5.18.0"
    
    // Kotlin
    testImplementation "io.mockk:mockk:1.13.11"
    
    // Testcontainers (integration/black-box)
    testImplementation "org.testcontainers:junit-jupiter:1.21.3"
    testImplementation "io.goodforgod:testcontainers-extensions-postgres:0.13.1"
}
```

### 2. JUnit Platform

```groovy
test {
    useJUnitPlatform()
    testLogging {
        showStandardStreams = true
        events("passed", "skipped", "failed")
        exceptionFormat = "full"
    }
}
```

### 3. Basic Component Test

```java
@KoraAppTest(Application.class)
class UserServiceTest {

    @TestComponent
    private UserService userService;

    @Test
    void shouldCreateUser() {
        var user = userService.create("test@example.com");
        assertNotNull(user);
        assertEquals("test@example.com", user.email());
    }
}
```

### 4. Test with Mocks

```java
@KoraAppTest(Application.class)
class OrderServiceTest {

    @Mock
    @TestComponent
    private UserRepository userRepository;

    @TestComponent
    private OrderService orderService;

    @Test
    void shouldCreateOrder() {
        Mockito.when(userRepository.findById(1L))
               .thenReturn(Optional.of(new User(1L, "test@example.com")));

        var order = orderService.create(1L, 99.99);
        assertNotNull(order);
        assertEquals(1L, order.userId());
    }
}
```

---

## Choosing Test Tier

| You want to verify | Tier | Tooling |
|--------------------|------|---------|
| One component's logic in isolation | **Component test** | `@KoraAppTest` + `@TestComponent` + mocked deps |
| Multiple components wired together | **Inter-component test** | `@KoraAppTest` with real components, mocked external systems |
| Real DB / Kafka participating | **Integration test** | `@KoraAppTest` + Testcontainers for upstream + real components |
| The whole packaged artifact serves traffic | **Black-box test** | `AppContainer` + Testcontainers + raw HTTP/gRPC client |
| CI smoke check on every PR | **Black-box (1–3 cases)** | same |

A typical service has all four. Don't skip black-box — it catches deployment bugs.

---

## Core Annotations

See [JUnit5 Extension Reference](references/junit5-extension-reference.md) for complete documentation.

**Key annotations:**
- `@KoraAppTest(Application.class)` — initializes DI container for tests
- `@TestComponent` — inject components (field/constructor/method)
- `@Mock` + `@TestComponent` — mock dependencies (Mockito)
- `@MockK` + `@TestComponent` — mock dependencies (MockK)

**Important:** All `@TestComponent` components must be used by at least one `@Root` component.

## Configuration

### KoraAppTestConfigModifier

```java
@KoraAppTest(Application.class)
class MyTest implements KoraAppTestConfigModifier {

    @Override
    public KoraConfigModification config() {
        return KoraConfigModification
            .ofSystemProperty("DB_URL", "jdbc:postgresql://localhost:5432/test")
            .withSystemProperty("DB_USER", "postgres")
            .withSystemProperty("DB_PASS", "postgres");
    }
}
```

Also: `ofResourceFile("application-test.conf")`, `ofString("...")`. See [JUnit5 Extension Reference](references/junit5-extension-reference.md#koraapptestconfigmodifier).

---

## Graph Modification

### KoraAppTestGraphModifier

```java
@KoraAppTest(Application.class)
class MyTest implements KoraAppTestGraphModifier {

    @Override
    public KoraGraphModification graph() {
        return KoraGraphModification.create()
            .addComponent(
                TypeRef.of(Supplier.class, Integer.class),
                () -> (Supplier<Integer>) () -> 42
            );
    }

    @Test
    void test(@TestComponent Supplier<Integer> supplier) {
        assertEquals(42, supplier.get());
    }
}
```

Also: `replaceComponent(...)`. See [JUnit5 Extension Reference](references/junit5-extension-reference.md#koraapptestgraphmodifier).

---

## TestApplication Pattern

Extend production `@KoraApp` to add **test-only components**:
- Repositories with cleanup methods (deleteAll, truncate)
- Components from common modules (not used in production)
- Test utilities for setup/teardown
- Stub components for isolation

```java
// TestApplication.java
@KoraApp
public interface TestApplication extends Application {

    @Root
    @Component
    @Repository
    interface TestPetRepository extends JdbcRepository {

        @Query("SELECT %{return#selects} FROM %{return#table}")
        List<Pet> findAll();

        @Query("DELETE FROM pets")
        void deleteAll();
    }
    
    // Any other test-only component
    @Root
    @Component
    default TestExternalService testExternalService() {
        return new FakeExternalService(); // Stub for tests
    }
}
```

**Usage:**

```java
@KoraAppTest(TestApplication.class)
class PetIntegrationTest {

    @TestComponent
    private TestPetRepository testPetRepository;
    
    @TestComponent
    private TestExternalService testExternalService;

    @BeforeEach
    void setUp() {
        testPetRepository.deleteAll(); // Cleanup before test
    }

    @Test
    void shouldCreatePet() {
        var pet = petService.create("Fluffy", "cat");
        assertNotNull(pet.id());
    }
}
```

**Build Requirements (MANDATORY):**

Enable submodule for `TestApplicationGraph` generation:

**Java (build.gradle):**
```groovy
compileJava {
    options.compilerArgs += ["-Akora.app.submodule.enabled=true"]
}

dependencies {
    testAnnotationProcessor "ru.tinkoff.kora:annotation-processors"
}

test {
    exclude("**/\$*")  // Exclude generated classes
}
```

**Kotlin (build.gradle.kts):**
```kotlin
ksp {
    arg("kora.app.submodule.enabled", "true")
}

dependencies {
    kspTest("ru.tinkoff.kora:symbol-processors")
}

tasks.test {
    exclude("**/\$*")
}
```

**When to use:**
- DB cleanup between tests (deleteAll, truncate)
- Adding any test-only components (not just DB!)
- Components from common modules (not in production)
- Fast test utilities for setup/teardown
- **Not recommended** as primary approach — prefer black-box tests

**Generate:** `python scripts/generate_test_application.py --entity Pet --table pets --package com.example --lang java`

---

## Black-Box Tests

Test application as black-box via HTTP API.

```java
@TestcontainersPostgreSQL(
    network = @Network(shared = true),
    mode = ContainerMode.PER_RUN,
    migration = @Migration(
        engine = Migration.Engines.FLYWAY,
        apply = Migration.Mode.PER_METHOD,
        drop = Migration.Mode.PER_METHOD
    )
)
class BlackBoxTests {

    private static final AppContainer container = AppContainer.build()
        .withNetwork(org.testcontainers.containers.Network.SHARED);

    @ConnectionPostgreSQL
    private JdbcConnection connection;

    @BeforeAll
    static void setup(@ConnectionPostgreSQL JdbcConnection connection) {
        var params = connection.paramsInNetwork().orElseThrow();
        container.withEnv(Map.of(
            "DB_URL", params.jdbcUrl(),
            "DB_USER", params.username(),
            "DB_PASS", params.password()
        ));
        container.start();
    }

    @AfterAll
    static void cleanup() {
        container.stop();
    }

    @Test
    void shouldCreateUserViaApi() throws Exception {
        var httpClient = HttpClient.newHttpClient();
        var requestBody = new JSONObject()
            .put("email", "test@example.com");

        var request = HttpRequest.newBuilder()
            .POST(HttpRequest.BodyPublishers.ofString(requestBody.toString()))
            .uri(container.getURI().resolve("/users"))
            .timeout(Duration.ofSeconds(5))
            .build();

        var response = httpClient.send(request, HttpResponse.BodyHandlers.ofString());
        assertEquals(200, response.statusCode());
    }
}
```

---

## Don't Do

- **Don't import `application.conf` from test classpath** when running black-box. The container has its own copy from the image; test classpath isn't propagated. Use `withEnv(...)` to inject config.
- **Don't try to inspect running container's components.** Black-box is black-box — talk through HTTP/gRPC only.
- **Don't share container instance across test classes without thought.** Static `@Container` in JUnit 5 is per-class; for cross-class reuse, manage lifecycle manually.
- **Don't use `@KoraAppTest` with `AppContainer`.** Confused layers — in-process doesn't need Docker, black-box doesn't need DI. Pick one per test class.
- **Don't use `Wait.forListeningPort()` for slow-starting services.** Listener opens immediately, but app may still be loading. Use `Wait.forHttp("/system/readiness").forPort(8085)`.

---

## Common Pitfalls

| Problem | Solution |
|---------|----------|
| Component not injected | Check component is used by `@Root` component |
| Mock not working | Ensure `@Mock` + `@TestComponent` together, remove `@ExtendWith(MockitoExtension.class)` |
| Long test initialization | Use `@TestInstance(PER_CLASS)` for one graph per class |
| Docker unavailable | Use `EXTERNAL_TEST_*` env vars for external DB |
| AppContainer builds image every run | Build once in CI, push, pin via `APP_IMAGE` env var |

---

## Best Practices

1. **Use `PER_RUN` mode** — one container for all tests, fast + clean
2. **Mockito/MockK only with `@TestComponent`** — don't use `MockitoExtension`/`MockKExtension`
3. **`@TestInstance(PER_CLASS)`** — init container once per class
4. **Isolate tests** — reset state between tests (DROP/TRUNCATE)
5. **Black-box as source of truth** — test app like in production
6. **Use Awaitility** — for async assertions in integration tests
7. **External systems via Testcontainers** — PostgreSQL, Kafka, Redis, etc.

---

## Scripts

```bash
# Generate component test
python scripts/generate_component_test.py \
    --name UserServiceTest \
    --component UserService \
    --lang java

# Generate integration test
python scripts/generate_integration_test.py \
    --name UserRepositoryTest \
    --repository UserRepository \
    --database postgres \
    --lang java

# Generate black-box test (HttpClient)
python scripts/generate_blackbox_test.py \
    --name BlackBoxTests \
    --port 8080 \
    --lang java

# Generate black-box test (RestAssured)
python scripts/generate_blackbox_restassured.py \
    --name BlackBoxRestAssuredTests \
    --port 8080 \
    --lang java

# Generate TestApplication
python scripts/generate_test_application.py \
    --entity Pet \
    --table pets \
    --package com.example \
    --lang java
```

---

## Docker for Testing

For black-box tests with `AppContainer`.

**Dockerfile Options:**

| File | Description | When to Use |
|------|-------------|-------------|
| `assets/Dockerfile.template` | Basic (requires `./gradlew installDist`) | Local dev |
| `assets/Dockerfile.self-build.template` | Multi-stage (build inside Docker) | CI/CD, reproducible |
| `assets/.dockerignore.template` | Docker build exclusions | Mandatory for speed |

**Quick Start:**

```bash
# Option 1: Basic (faster with cache)
./gradlew installDist
docker build -t myapp:1.0.0 .

# Option 2: Multi-stage (no JDK on host required)
docker build -t myapp:1.0.0 -f Dockerfile.self-build .

# Run tests with image
export APP_IMAGE=myapp:1.0.0
./gradlew test
```

**Detailed:** [Docker Reference](references/docker-reference.md) — comparison, CI/CD, Docker Compose.

---

## Related Resources

- [Kora JUnit5 Documentation](https://kora-projects.github.io/kora-docs/en/documentation/junit5.html)
- [Kora Examples](https://github.com/kora-projects/kora-examples)
- [Testcontainers](https://www.testcontainers.org/)
- [JUnit5 Extension Reference](references/junit5-extension-reference.md) — @KoraAppTest, @TestComponent, modifiers
- [Mockito Reference](references/mockito-reference.md) — Java
- [MockK Reference](references/mockk-reference.md) — Kotlin
- [Awaitility](http://www.awaitility.org/)
- [Testcontainers Extensions Reference](references/testcontainers-extensions-reference.md) — default for PostgreSQL/Cassandra/Kafka
- [Testcontainers Reference](references/testcontainers-reference.md) — base testcontainers for custom scenarios
- [Black-Box Testing Reference](references/blackbox-testing-reference.md) — E2E HTTP API tests
- [MockServer Testing Reference](references/mockserver-testing-reference.md) — mock external HTTP services
- [HTTP Server Testing Reference](references/http-server-testing-reference.md) — RestAssured for black-box
- [Docker Reference](references/docker-reference.md) — Docker images for Kora apps

---

## Common Pitfalls

- **Missing `@KoraAppTest`** → test class not recognized without annotation.
- **`@TestComponent` without `@Component`** → mock must be `@TestComponent` to replace real component.
- **Testcontainers not starting** → ensure `@KoraAppTest` extends test modules with containers.
- **AppContainer port conflict** → use random port (`server.port: 0`) for black-box tests.
- **Mockito/MockK mismatch** → use Mockito for Java, MockK for Kotlin; don't mix.
- **Test-only components** → use `TestApplication` for components needed only in tests.
