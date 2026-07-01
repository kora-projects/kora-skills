---
name: kora-testing-junit-kotlin
description: "In-process JUnit 5 component and integration tests for Kora Kotlin services. Covers @KoraAppTest, @TestComponent, @MockK/@SpyK (and Mockito-Kotlin), KoraAppTestConfigModifier, KoraAppTestGraphModifier, the TestApplication submodule pattern, coroutine tests with runTest/coEvery, and Testcontainers. Use when writing the first Kora Kotlin test, mocking a graph dependency, overriding config in a test, adding/replacing graph components, or wiring a PostgreSQL Testcontainer with @KoraAppTest. Artifact ru.tinkoff.kora:test-junit5; processor ksp ru.tinkoff.kora:symbol-processors."
---

# Kora Testing JUnit (Kotlin)

In-process JUnit 5 tests that build a real Kora application Graph at compile time and inject its components into the test. `@KoraAppTest` reads a `@KoraApp` interface, builds only the slice of the Graph reachable from the requested `@TestComponent`s, and hands those components to the test. There is no reflection-based runtime container — the same generated `*Graph` code used in production runs in the test.

Read this first when:
- writing the first component test for a Kora Kotlin service,
- mocking a graph dependency with `@MockK` + `@TestComponent`,
- overriding config via `KoraAppTestConfigModifier`,
- adding or replacing a component via `KoraAppTestGraphModifier`,
- adding test-only repositories through the `TestApplication` submodule pattern,
- wiring a PostgreSQL Testcontainer into a `@KoraAppTest`.

## Quick Start

### 1. Dependencies (`build.gradle.kts`)

All Kora artifacts inherit their version from the `kora-parent` BOM — never pin a `ru.tinkoff.kora:*` version individually.

```kotlin
dependencies {
    // BOM already applied in the project (ru.tinkoff.kora:kora-parent)
    ksp("ru.tinkoff.kora:symbol-processors")

    testImplementation(platform("org.junit:junit-bom:5.13.4"))
    testImplementation("org.junit.jupiter:junit-jupiter")
    testImplementation("ru.tinkoff.kora:test-junit5")

    // Kotlin-idiomatic mocking
    testImplementation("io.mockk:mockk:1.13.11")
}

tasks.test {
    useJUnitPlatform()
    testLogging {
        showStandardStreams = true
        events("passed", "skipped", "failed")
        exceptionFormat = org.gradle.api.tasks.testing.logging.TestExceptionFormat.FULL
    }
}
```

`ksp("ru.tinkoff.kora:symbol-processors")` is mandatory in the main source set — without it no `@KoraApp` Graph is generated and `@KoraAppTest` has nothing to load.

### 2. Component test with a real Graph

```kotlin
@KoraAppTest(Application::class)
class UserServiceComponentTest {

    @TestComponent
    lateinit var userService: UserService

    @Test
    fun createUserWithRealGraph() {
        val result = userService.createUser(UserRequest("John", "john@example.com"))

        assertNotNull(result)
        assertEquals("John", result.name)
    }
}
```

`@KoraAppTest(Application::class)` names the `@KoraApp` interface to build from. `@TestComponent` on `userService` both injects the component and makes it a root of the test Graph, so Kora builds `UserService` and only the dependencies it needs.

### 3. Component test with a MockK mock

```kotlin
@KoraAppTest(Application::class)
class UserServiceMockTest {

    @MockK
    @TestComponent
    lateinit var userRepository: UserRepository

    @TestComponent
    lateinit var userService: UserService

    @Test
    fun getUserUsesRepositoryMock() {
        val expected = UserResponse("1", "John", "john@example.com", LocalDateTime.now())
        every { userRepository.findById("1") } returns expected

        val result = userService.getUser("1")

        assertEquals(expected, result)
        verify { userRepository.findById("1") }
    }
}
```

`@MockK` creates the mock; `@TestComponent` registers it in the Graph in place of the real `UserRepository`. The same mock instance is injected into the test field **and** into every graph component that depends on `UserRepository`, so `userService` stays real while its repository is the mock.

> Do not add `= mockk()` next to a `@MockK` field — the annotation already creates the mock. Do not combine `@KoraAppTest` with `MockKExtension`/`@ExtendWith(MockKExtension::class)`; `@KoraAppTest` owns the mock lifecycle.

---

## References and assets

| File | Purpose |
|------|---------|
| [references/korapptest-kotlin-reference.md](references/korapptest-kotlin-reference.md) | `@KoraAppTest`, `@TestComponent`, `@Tag`, injection styles, lifecycle |
| [references/junit5-extension-reference.md](references/junit5-extension-reference.md) | Config and Graph modifiers, `@KoraAppTest` parameters, troubleshooting |
| [references/mockk-reference.md](references/mockk-reference.md) | MockK `@MockK`/`@SpyK`, `every`/`verify`, matchers, slots, relaxed mocks |
| [references/mockito-reference.md](references/mockito-reference.md) | Mockito-Kotlin alternative (`@Mock`, `whenever`, `@MockitoStrictness`) |
| [references/coroutines-testing-reference.md](references/coroutines-testing-reference.md) | `runTest`, `coEvery`/`coVerify`, `TestDispatcher`, Flow tests |
| [references/testcontainers-kotlin-reference.md](references/testcontainers-kotlin-reference.md) | PostgreSQL / Kafka Testcontainers wiring with `@KoraAppTest` |
| `assets/ComponentTest.kt.template` | Component test scaffold with a MockK dependency |
| `assets/IntegrationTest.kt.template` | Testcontainers PostgreSQL integration scaffold |
| `assets/IntegrationTestWithPostgres.kt.template` | Integration scaffold using a `TestApplication` repository for cleanup |
| `assets/TestApplication.kt.template` | `TestApplication` submodule scaffold with a test-only repository |

---

## When to use vs NOT

| Use `@KoraAppTest` when | Do NOT use it when |
|-------------------------|--------------------|
| Testing a service/component through real graph wiring | Pure-unit testing a class with no Kora dependencies — just `new` it |
| Replacing one dependency with a mock while keeping the rest real | Asserting the packaged image / JVM flags / full config — use black-box Testcontainers tests |
| Verifying config-driven behavior via `KoraAppTestConfigModifier` | Testing routing/serialization end to end — prefer black-box HTTP tests |
| Integration tests against a real DB via Testcontainers | — |

`@KoraAppTest` is the strongest in-process signal; black-box tests over the packaged artifact remain the primary source of truth for full-application correctness.

---

## Core patterns

### Injection styles

`@TestComponent` works on fields, the test constructor, and test-method parameters.

```kotlin
// Field
@KoraAppTest(Application::class)
class FieldTest {
    @TestComponent lateinit var userService: UserService
}

// Constructor
@KoraAppTest(Application::class)
class CtorTest(@TestComponent val userService: UserService)

// Method parameter
@KoraAppTest(Application::class)
class MethodTest {
    @Test
    fun example(@TestComponent userService: UserService) { /* ... */ }
}
```

Inject a tagged component by repeating its `@Tag` next to the parameter:

```kotlin
@Test
fun example(@Tag(Supplier::class) @TestComponent supplier: Supplier<String>) {
    assertEquals("tag1", supplier.get())
}
```

### Config overrides — `KoraAppTestConfigModifier`

Implement the interface on the test class (not via the constructor — the modifier must run before injection).

```kotlin
@KoraAppTest(Application::class)
class ConfigTest : KoraAppTestConfigModifier {

    override fun config(): KoraConfigModification =
        KoraConfigModification
            .ofSystemProperty("POSTGRES_JDBC_URL", "jdbc:postgresql://localhost:5432/postgres")
            .withSystemProperty("POSTGRES_USER", "postgres")
            .withSystemProperty("POSTGRES_PASS", "postgres")
}
```

Other factories: `KoraConfigModification.ofResourceFile("application-test.conf")` (loads a classpath config) and `KoraConfigModification.ofString("""...""")` (replaces all config with the given HOCON text). `ofSystemProperty`/`withSystemProperty` only substitute `${VAR}` placeholders in the default config.

### Graph modification — `KoraAppTestGraphModifier`

Add or replace components that are not declared in the `@KoraApp`. Implement the interface on the class, never via the constructor.

```kotlin
@KoraAppTest(Application::class)
class GraphAddTest : KoraAppTestGraphModifier {

    override fun graph(): KoraGraphModification =
        KoraGraphModification.create()
            .addComponent(TypeRef.of(Supplier::class.java, Int::class.java), Supplier { Supplier { 1 } })

    @Test
    fun example(@TestComponent supplier: Supplier<Int>) {
        assertEquals(1, supplier.get())
    }
}
```

Replace a component, optionally deriving the new value from the existing one:

```kotlin
override fun graph(): KoraGraphModification =
    KoraGraphModification.create()
        .replaceComponent(TypeRef.of(Supplier::class.java, Int::class.java)) { graph ->
            @Suppress("UNCHECKED_CAST")
            val existing = graph.getFirst(TypeRef.of(Supplier::class.java, Int::class.java)) as Supplier<Int>
            Supplier { 1 + existing.get() }
        }
```

`addComponent` registers a new type; `replaceComponent` swaps an existing one. `graph.getFirst(TypeRef.of(...))` resolves the original component. Prefer `@MockK` + `@TestComponent` for plain mock-replacement; reach for the Graph modifier when the replacement type is generic, tagged, or must wrap the real component.

### Coroutines

Use `runTest` for suspend tests and the `co*` MockK DSL for suspend mocks. See [references/coroutines-testing-reference.md](references/coroutines-testing-reference.md).

```kotlin
@KoraAppTest(Application::class)
class UserServiceCoroutineTest {

    @MockK @TestComponent lateinit var userRepository: UserRepository
    @TestComponent lateinit var userService: UserService

    @Test
    fun createUserAsync() = runTest {
        coEvery { userRepository.save(any()) } returns "1"

        val result = userService.createUser(UserRequest("John", "john@example.com"))

        assertNotNull(result)
        coVerify { userRepository.save(any()) }
    }
}
```

### Once-per-class initialization

By default the Graph is rebuilt for every test method. Build it once per class with the standard JUnit annotation:

```kotlin
@TestInstance(TestInstance.Lifecycle.PER_CLASS)
@KoraAppTest(Application::class)
class FastTests { /* one Graph for all @Test methods */ }
```

---

## TestApplication submodule pattern

When tests need components the production `@KoraApp` does not declare — e.g. a repository with `deleteAll()` for cleanup — extend the application graph in the test source set. Mark added components `@Root` so they are not pruned.

```kotlin
@KoraApp
interface TestApplication : Application {

    @Repository
    interface TestUserRepository : JdbcRepository {

        @Query("SELECT id, name, email, created_at FROM users ORDER BY id")
        fun findAll(): List<UserDAO>

        @Query("DELETE FROM users")
        fun deleteAll()
    }

    @Tag(TestApplication::class)
    @Root
    fun testRoot(ignored: TestUserRepository): String = "test-root"
}
```

Enable submodule generation and run the symbol processor over the test source set in `build.gradle.kts`:

```kotlin
ksp {
    arg("kora.app.submodule.enabled", "true")
}

dependencies {
    kspTest("ru.tinkoff.kora:symbol-processors")
}

tasks.test {
    exclude("**/\$*") // generated classes start with $ and confuse JUnit discovery
}
```

Then point the test at the extended graph: `@KoraAppTest(TestApplication::class)`.

---

## Testcontainers integration

Combine `@Testcontainers` with `@KoraAppTest` and feed container coordinates through `KoraAppTestConfigModifier`. Full templates: [references/testcontainers-kotlin-reference.md](references/testcontainers-kotlin-reference.md).

```kotlin
@Testcontainers
@KoraAppTest(TestApplication::class)
class UserServiceIntegrationPostgresTest : KoraAppTestConfigModifier {

    companion object {
        @Container
        @JvmStatic
        val POSTGRES = PostgreSQLContainer("postgres:16-alpine")
    }

    @TestComponent lateinit var userService: UserService
    @TestComponent lateinit var testUserRepository: TestApplication.TestUserRepository

    override fun config(): KoraConfigModification =
        KoraConfigModification.ofString(
            """
            db {
              jdbcUrl = ${'$'}{POSTGRES_JDBC_URL}
              username = ${'$'}{POSTGRES_USER}
              password = ${'$'}{POSTGRES_PASS}
              poolName = "kora-test"
            }
            flyway { locations = "db/migration" }
            """.trimIndent()
        )
            .withSystemProperty("POSTGRES_JDBC_URL", POSTGRES.jdbcUrl)
            .withSystemProperty("POSTGRES_USER", POSTGRES.username)
            .withSystemProperty("POSTGRES_PASS", POSTGRES.password)

    @BeforeEach
    fun cleanup() = testUserRepository.deleteAll()

    @Test
    fun createUserShouldPersistUserInDatabase() {
        userService.createUser(UserRequest("John", "john@example.com"))
        assertEquals(1, testUserRepository.findAll().size)
    }
}
```

Test dependencies for this pattern:

```kotlin
testImplementation("org.testcontainers:postgresql:1.20.4")
testImplementation("org.testcontainers:junit-jupiter:1.20.4")
```

---

## Mocking framework choice

| | When to pick |
|---|---|
| **MockK** (`@MockK`, `every {}`, `coEvery {}`) | Pure Kotlin codebase; idiomatic DSL, first-class coroutine and suspend-function support. Recommended default. |
| **Mockito-Kotlin** (`@Mock`, `whenever`, `verify`) | Mixed Java/Kotlin codebase or a team standardized on Mockito. Add `org.mockito.kotlin:mockito-kotlin:5.4.0`. See [references/mockito-reference.md](references/mockito-reference.md). |

Both are driven by `@TestComponent`; the mock is injected into the Graph the same way regardless of framework. Pick one per module and stay consistent.

---

## Common pitfalls

| Symptom | Fix |
|---------|-----|
| Component is `null` / not injected | Make it a `@TestComponent` and ensure it is reachable from a `@Root` (or itself a root via `@TestComponent`) |
| `@MockK` field is a real object, not a mock | Remove the `= mockk()` initializer — `@MockK` creates the mock itself |
| Mock not applied to graph / inconsistent instance | Do not attach `MockKExtension`/`MockitoExtension` alongside `@KoraAppTest` |
| `lateinit property has not been initialized` | Use `lateinit var` for field/property injection, not `val` without an initializer |
| Slow suite | Add `@TestInstance(TestInstance.Lifecycle.PER_CLASS)` to build the Graph once per class |
| `coVerify`/`every` fails on suspend method | Use `coEvery`/`coVerify` and wrap the test body in `runTest { }` |
| JUnit picks up generated `$` classes (submodule) | Add `exclude("**/\$*")` to `tasks.test` |
| `TestApplication` component pruned from graph | Mark it `@Root` (directly or through a `@Root` that depends on it) |
