---
name: kora-testing-junit-kotlin
description: "In-process JUnit 5 tests for Kotlin Kora 2.x services — io.koraframework:test-junit5, @KoraAppTest/@TestComponent from io.koraframework.test.extension.junit5, MockK @field:MockK/@SpyK, Mockito-Kotlin, KoraAppTestConfigModifier/KoraConfigModification.ofString, KoraAppTestGraphModifier/KoraGraphModification, the TestApplication submodule pattern with kspTest + kora.app.submodule.enabled, and Testcontainers. Use when writing or migrating a Kotlin @KoraAppTest, mocking a graph component, overriding test config, or wiring PostgreSQL/Kafka containers. Kora 2.0 contracts are synchronous — no runTest/coEvery around Kora calls. For Java see kora-testing-junit-java; for E2E over the packaged artifact see kora-testing-blackbox."
license: Apache-2.0
metadata:
  kora-version: "2.x"
---

# Kora Testing JUnit (Kotlin)

> **Kora sub-skill — obey the [kora-v2 meta rules](../../SKILL.md) on every task:** **R0** ground the workspace on Kora 2.0 refs before starting (framework source at tag `2.0.0.RC2` + `kora-examples` at `migration/2.0` + Kora 2.0 docs at koraframework.io/v2, which trail the source; 1.x `kora-docs` pages are never an authority) · **R1** read this sub-skill before writing code · **R2** Kora 2.0 APIs only — no Spring/Micronaut/Quarkus, no Kora 1.x APIs, no invented annotations or config keys · **R3** journal any incorrect Kora usage. Add comments/Javadoc only if asked.

| | |
|---|---|
| **Artifact** | `io.koraframework:test-junit5` (BOM `io.koraframework:kora-bom`, `2.0.0.RC2`) |
| **Extension package** | `io.koraframework.test.extension.junit5` — `@KoraAppTest`, `@TestComponent`, `KoraAppTestConfigModifier`, `KoraAppTestGraphModifier`, `KoraConfigModification`, `KoraGraphModification`, `KoraAppGraph` |
| **Mockito strictness** | `io.koraframework.test.extension.junit5.mockito.MockitoStrictness` |
| **Processor** | `ksp("io.koraframework:symbol-processors:${property("koraVersion")}")`; `kspTest(...)` **only** when `src/test` declares its own `@KoraApp` |
| **JUnit** | `6.1.3` via `platform("org.junit:junit-bom:${property("junitVersion")}")` (also arrives transitively — `test-junit5` declares `api junit-jupiter` + `api junit-platform-launcher`) |
| **MockK** | `1.14.11` — anything below `1.14.9` pulls a Byte Buddy that cannot read Java 25 class files |
| **Execution model** | **Synchronous.** Kora 2.0 repositories, controllers and HTTP clients are not `suspend`. No `runTest`/`coEvery` around Kora calls. |
| **Boundary** | Java twin: [`kora-testing-junit-java`](../kora-testing-junit-java/SKILL.md). E2E over the packaged artifact: [`kora-testing-blackbox`](../kora-testing-blackbox/SKILL.md). |

`@KoraAppTest` loads the class `<YourApp>Graph` that the symbol processor generated from your
`@KoraApp` interface, copies the draw, keeps only the slice reachable from the components the test
asks for, and injects them. There is no reflection-based runtime container — the test exercises the
same generated wiring that ships.

Read this first when:

- writing or migrating a Kotlin component test for a Kora service,
- mocking a graph dependency with `@field:MockK` + `@TestComponent`,
- overriding config via `KoraAppTestConfigModifier` (including HOCON embedded in `ofString`),
- adding or replacing a component via `KoraAppTestGraphModifier`,
- adding test-only repositories through the `TestApplication` submodule pattern,
- wiring PostgreSQL/Kafka Testcontainers into a `@KoraAppTest`,
- removing `runTest` / `coEvery` from tests that used to wrap `suspend` Kora contracts.

---

## Migrating a Kotlin test suite from Kora 1.x

| 1.x | 2.0 | Why |
|---|---|---|
| `ru.tinkoff.kora.test.extension.junit5.*` | `io.koraframework.test.extension.junit5.*` | package rename |
| `ru.tinkoff.kora:test-junit5` | `io.koraframework:test-junit5` | group rename |
| `ru.tinkoff.kora.common.KoraApp` / `.Tag` | `io.koraframework.common.annotation.KoraApp` / `.Tag` / `.Root` | all DI annotations moved into `common.annotation` |
| `ru.tinkoff.kora:kora-parent` BOM | `io.koraframework:kora-bom` on `implementation(platform(...))` | `kora-parent` does not exist in 2.0 |
| `koraBom` configuration + `extendsFrom` | **do not create it in Kotlin modules** — BOM straight onto `implementation`, processor version explicit | migrated Kotlin `build.gradle.kts` files use no such configuration |
| `coEvery { repo.x() }` / `coVerify` | `every { repo.x() }` / `verify` | repository/controller/client contracts are synchronous |
| `@Test fun t() = runTest { ... }` around Kora calls | plain `@Test fun t() { ... }` | nothing suspends; `runTest`'s virtual clock cannot speed up blocking work |
| `withContext(Dispatchers.IO) { repo.find() }` | `repo.find()` | Kora runs on virtual threads; an IO dispatcher only adds a hop |
| `db { jdbcUrl = ... }` inside `ofString` | `jdbc { jdbcUrl = ... }` | `JdbcDatabaseModule` binds `new JdbcDatabaseFactoryModule("jdbc")`; symptom is `ConfigValueException: … null at path: 'ROOT.jdbc.username'` |
| `publicApiHttpPort` / `privateApiHttpPort` | `httpServer.port` / `httpServer.system.port` | stale keys are unknown HOCON keys — silently ignored, each server falls back to its own default (8080 / **8085**) |
| `slidingWindowSize` in a `resilient` block | `type = FIXED_WINDOW` + `countBased.windowSize` | `countBased` is `@Nullable` in the interface but `KoraCircuitBreaker` validates it, so omitting it fails graph init with `IllegalArgumentException: CircuitBreaker '<n>' property 'countBased' is not configured` |
| `Context` passed into a test double | — | `Context` no longer exists anywhere in the framework |
| `io.mockk:mockk:1.13.x` | `io.mockk:mockk:1.14.11` | old MockK's Byte Buddy logs `InliningClassTransformer - Failed to transform class … Java 25 (69) is not supported` |
| `environment(["": ""])` in a Gradle test block | delete the block | an empty env-var name stops the test JVM on Windows (`CreateProcess error=87`) |

Never fix these with a blanket search/replace: `kspTest` in particular must be decided per module (below),
and a `.map(` on a config extractor changed meaning in 2.0.

**Scenarios that have no 2.0 equivalent.** A test that asserted coroutine *cancellation* of a Kora
database call, or that collected a `Flow` returned by a repository, is not migrated — it is deleted,
because Kora 2.0 has no cancellable suspend contract and no `Flow`-returning repository to cancel.
Say so in the commit rather than leaving a weakened assertion. Real parallelism moves to Java
`StructuredTaskScope`; see [references/coroutines-migration-reference.md](references/coroutines-migration-reference.md).

---

## Quick Start

### 1. Dependencies (`build.gradle.kts`)

```kotlin
plugins {
    id("org.jetbrains.kotlin.jvm")
    id("com.google.devtools.ksp")
}

dependencies {
    implementation(platform("io.koraframework:kora-bom:${property("koraVersion")}"))
    ksp("io.koraframework:symbol-processors:${property("koraVersion")}")

    testImplementation(platform("org.junit:junit-bom:${property("junitVersion")}"))
    testImplementation("org.junit.jupiter:junit-jupiter")
    testImplementation("io.koraframework:test-junit5")

    // Kotlin-idiomatic mocking; 1.14.9 is the floor for Java 25 Byte Buddy
    testImplementation("io.mockk:mockk:1.14.11")
}

kotlin {
    jvmToolchain {
        languageVersion.set(JavaLanguageVersion.of(25))
        vendor.set(JvmVendorSpec.ADOPTIUM)
    }
    sourceSets.main { kotlin.srcDir("build/generated/ksp/main/kotlin") }
    sourceSets.test { kotlin.srcDir("build/generated/ksp/test/kotlin") }
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

`gradle.properties` carries `koraVersion=2.0.0.RC2` and `junitVersion=6.1.3`, resolved from plain
`mavenCentral()`. In a Kotlin module the BOM goes **directly** on `implementation` and every
processor coordinate names its version explicitly — do not port the Java-side `koraBom`
configuration with `extendsFrom` into `build.gradle.kts`.

`ksp("io.koraframework:symbol-processors")` on the **main** source set is mandatory: without it no
`<App>Graph` is generated and `@KoraAppTest` has nothing to load.

### 2. Component test against the real graph

```kotlin
@KoraAppTest(Application::class)
class UserServiceComponentTest {

    @TestComponent
    lateinit var userService: UserService

    @Test
    fun createUserPersistsAndReturns() {
        val result = userService.createUser(UserRequest("John", "john@example.com"))

        assertEquals("John", result.name)
    }
}
```

`@KoraAppTest(Application::class)` names the `@KoraApp` interface. `@TestComponent` both injects the
component and makes it a root of the test graph, so Kora builds `UserService` and only what it needs.

### 3. Component test with a MockK mock

```kotlin
@KoraAppTest(Application::class)
class UserServiceMockTest {

    @field:MockK
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

`every`/`verify`, not `coEvery`/`coVerify`: `UserRepository.findById` is an ordinary blocking method
in 2.0. The same mock instance is injected into the test field **and** into every graph component
that depends on `UserRepository`, so `userService` stays real while its repository is the mock.

> **Use `@field:MockK`, not bare `@MockK`.** MockK's annotation also applies to a Kotlin *property*,
> and the extension only sees property annotations when `kotlin.reflect.jvm.ReflectJvmMapping` is on
> the test classpath (`test-junit5` declares `kotlin-reflect` `compileOnly`, so Kora does not supply
> it). `@field:MockK` targets the JVM field and works either way. Mockito's `@Mock` has no Kotlin
> `PROPERTY` target, so it lands on the field on its own and needs no prefix.
>
> Do not add `= mockk()` next to the annotation, and do not attach
> `@ExtendWith(MockKExtension::class)` — `@KoraAppTest` owns mock creation, injection and reset.

---

## References and assets

| File | Purpose |
|------|---------|
| [references/korapptest-kotlin-reference.md](references/korapptest-kotlin-reference.md) | `@KoraAppTest` attributes, `@TestComponent`, `@Tag`, injection styles, `Graph`/`KoraAppGraph` parameters, lifecycle, verbatim extension errors |
| [references/junit5-extension-reference.md](references/junit5-extension-reference.md) | `KoraAppTestConfigModifier`, `KoraAppTestGraphModifier`, the full `KoraGraphModification` API and its Kotlin SAM traps |
| [references/mockk-reference.md](references/mockk-reference.md) | MockK `1.14.11`, use-site targets, `every`/`verify`, `@SpyK`, relaxed mocks, the Byte Buddy floor |
| [references/mockito-reference.md](references/mockito-reference.md) | Mockito-Kotlin alternative, the `mockito-core` pin, `@MockitoStrictness` |
| [references/coroutines-migration-reference.md](references/coroutines-migration-reference.md) | What replaces `runTest`/`coEvery`; what has no 2.0 equivalent; testing `StructuredTaskScope` |
| [references/testcontainers-kotlin-reference.md](references/testcontainers-kotlin-reference.md) | PostgreSQL / Kafka containers with `@KoraAppTest`, coordinates the migrated examples use |
| `assets/ComponentTest.kt.template` | Component test scaffold with a MockK dependency |
| `assets/IntegrationTest.kt.template` | Testcontainers PostgreSQL integration scaffold |
| `assets/IntegrationTestWithPostgres.kt.template` | Integration scaffold using a `TestApplication` repository for cleanup |
| `assets/TestApplication.kt.template` | `TestApplication` submodule scaffold with a test-only repository |

---

## When to use vs NOT

| Use `@KoraAppTest` when | Do NOT use it when |
|-------------------------|--------------------|
| Testing a service/component through real graph wiring | Pure-unit testing a class with no Kora dependencies — just construct it |
| Replacing one dependency with a mock while keeping the rest real | Asserting the packaged image / JVM flags / full config — use [`kora-testing-blackbox`](../kora-testing-blackbox/SKILL.md) |
| Verifying config-driven behaviour via `KoraAppTestConfigModifier` | Testing routing/serialization end to end — prefer black-box HTTP tests |
| Integration tests against a real DB via Testcontainers | The service is Java — use [`kora-testing-junit-java`](../kora-testing-junit-java/SKILL.md) |

`@KoraAppTest` is the strongest in-process signal; black-box tests over the packaged artifact remain
the primary source of truth for full-application correctness. The migrated `kora-kotlin-crud` example
says so in its own `TestApplication` KDoc.

---

## Core patterns

### Injection styles

`@TestComponent` works on fields, the test constructor and test-method parameters.

```kotlin
@KoraAppTest(Application::class)
class FieldTest {
    @TestComponent lateinit var userService: UserService
}

@KoraAppTest(Application::class)
class CtorTest(@TestComponent val userService: UserService)

@KoraAppTest(Application::class)
class MethodTest {
    @Test
    fun example(@TestComponent userService: UserService) { /* ... */ }
}
```

Injected fields may be neither `static` nor `final` — the extension rejects both with a named error.
Repeat a component's `@Tag` next to the injection point to disambiguate:

```kotlin
@Test
fun example(@Tag(LifecycleComponent::class) @TestComponent component: TestComponent2) { /* ... */ }
```

`Graph` and `KoraAppGraph` are resolved as test-method parameters **without** `@TestComponent`, and
mocking either is rejected outright.

### Config overrides — `KoraAppTestConfigModifier`

Implement the interface on the class body. Combining a modifier with **constructor** `@TestComponent`
injection is a hard error (`Cannot use KoraAppTestConfigModifier with @KoraAppTest constructor
injection`) because the graph is built while constructor parameters resolve, before the instance exists.

```kotlin
@KoraAppTest(Application::class)
class ConfigTest : KoraAppTestConfigModifier {

    override fun config(): KoraConfigModification =
        KoraConfigModification.ofSystemProperty("POSTGRES_JDBC_URL", "jdbc:postgresql://localhost:5432/postgres")
            .withSystemProperty("POSTGRES_USER", "postgres")
            .withSystemProperty("POSTGRES_PASS", "postgres")
}
```

- `ofSystemProperty` / `withSystemProperty` only set system properties, so `${VAR}` placeholders in
  the application's own config resolve. The config file itself is untouched.
- `ofResourceFile("application-test.conf")` sets `config.resource` — the named classpath file
  **replaces** the application config.
- `ofString("""…""")` writes the text to a temp file and sets `config.file` — it also replaces the
  application config, and it may still carry `${VAR}` placeholders fed by `withSystemProperty`.

> **HOCON inside `ofString` is real configuration.** Resource-only scanners never see it, so 1.x keys
> survive migration there longer than anywhere else. Every `ofString` block must use 2.0 keys:
> `jdbc { }` not `db { }`; `httpServer.port` / `httpServer.system.port` not `publicApiHttpPort` /
> `privateApiHttpPort`; a `resilient.circuitbreaker.<n>` block must carry `countBased.windowSize`
> (`type` is optional and defaults to `STRIPED_APPROX`, which still needs `countBased`).
> Telemetry `logging.enabled` and `metrics.enabled` default to **false**, so
> a test that asserts on logs or metrics must switch them on explicitly.

### Graph modification — `KoraAppTestGraphModifier`

Add, replace or mock components that plain `@field:MockK` cannot express — generic types, tagged
components, or a replacement that must wrap the original. Same constructor-injection restriction as
the config modifier.

```kotlin
@KoraAppTest(Application::class)
class GraphTest : KoraAppTestGraphModifier {

    override fun graph(): KoraGraphModification =
        KoraGraphModification.create()
            .addComponent(TypeRef.of(Supplier::class.java, Int::class.java), Supplier { Supplier { 1 } })
            .replaceComponent(TestComponent2::class.java, LifecycleComponent::class.java,
                Supplier { mockkClass(TestComponent2::class) })

    @Test
    fun example(@TestComponent supplier: Supplier<Int>) = assertEquals(1, supplier.get())
}
```

The tag argument is a **single `Class<?>`** in the second position — not a list. In Kotlin the
zero-argument factory needs the explicit `Supplier { … }` SAM constructor, because `addComponent` and
`replaceComponent` are each overloaded on `Supplier<T>` and `Function<KoraAppGraph, T>`. Full API and
the `graph.getFirst` nullability rule: [references/junit5-extension-reference.md](references/junit5-extension-reference.md).

### Once-per-class initialization

The graph is rebuilt for every test method by default. Build it once per class with the standard
JUnit annotation:

```kotlin
@TestInstance(TestInstance.Lifecycle.PER_CLASS)
@KoraAppTest(Application::class)
class FastTests { /* one graph for all @Test methods */ }
```

Under `PER_CLASS` the extension rejects mocks declared as **test-method parameters** (one graph is
shared by all methods, a parameter mock is per-method) and rejects `@TestComponent` fields inside a
`@Nested` class of that outer test.

---

## `kspTest` — the rule, not the example list

`kspTest("io.koraframework:symbol-processors:${property("koraVersion")}")` is required **exactly when
the module's `src/test` declares its own `@KoraApp` interface** (a `TestApplication`). It is not
required for ordinary `@KoraAppTest` tests that point at a production `@KoraApp` compiled in
`src/main`. `@KoraAppTest` alone is not a trigger — do not read a `@KoraAppTest(X::class)` line as a
`@KoraApp`.

The framework says so itself: when `<App>Graph` is missing, `KoraJUnit5Extension` raises
`Cannot find generated Kora application graph for: …` and prints both halves of the fix —
`kspTest(...)` for "test application is declared in `src/test`", and
`ksp { arg("kora.app.submodule.enabled", "true") }` for "test application extends the main
application". They are **two independent settings, often in two different modules**:

| Setting | Required when | Belongs to |
|---|---|---|
| `kspTest("io.koraframework:symbol-processors:…")` | `src/test` declares a `@KoraApp` | that same module |
| `ksp { arg("kora.app.submodule.enabled", "true") }` | the extended production `@KoraApp` is compiled in a **different** Gradle module | the module owning that production `@KoraApp` |

In the migrated corpus, `kora-kotlin-guide-testing-integration-app` carries only `kspTest`, while the
submodule flag sits on `kora-kotlin-guide-database-jdbc-app`, whose `Application` it extends.
`kora-kotlin-http-server` keeps its `TestApplication` in the same module as `Application` and needs
only `kspTest`. `kora-kotlin-crud` is also single-module yet sets both — setting the flag when it is
not strictly needed is harmless, omitting it across a module boundary is not.

Never remove `kspTest` by blanket replacement, and never add it "just in case": an unnecessary
`kspTest` runs the whole Kora processor over every test source set for nothing.

---

## TestApplication submodule pattern

When tests need components the production `@KoraApp` does not declare — a repository with
`deleteAll()` for cleanup, an HTTP client that calls the app under test — extend the application
graph from the test source set. Added components must be reachable from a `@Root`, otherwise the
compile-time graph builder prunes them and `@TestComponent` cannot find them.

Two shapes are in use in the migrated examples; both are correct.

```kotlin
// Anchor method — one @Root that depends on the test-only components
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

```kotlin
// @Root directly on each test-only component
@KoraApp
interface TestApplication : Application {

    @Root
    @Component
    @Repository
    interface TestPetRepository : JdbcRepository {
        @Query("SELECT %{return#selects} FROM %{return#table}")
        fun findAll(): List<Pet>

        @Query("DELETE FROM pets")
        fun deleteAll()
    }
}
```

Imports are `io.koraframework.common.annotation.{KoraApp, Root, Tag, Component}`,
`io.koraframework.database.common.annotation.{Query, Repository}` and
`io.koraframework.database.jdbc.JdbcRepository`.

Build wiring, and keeping the generated `$`-prefixed classes out of JUnit discovery:

```kotlin
// module whose src/test declares the @KoraApp
dependencies { kspTest("io.koraframework:symbol-processors:${property("koraVersion")}") }

// module that compiles the production @KoraApp — needed when that is a DIFFERENT Gradle module
ksp { arg("kora.app.submodule.enabled", "true") }

tasks.test {
    exclude("**/\$*")           // generated classes start with $ and confuse discovery
    failOnNoDiscoveredTests = false
}
```

Then point the test at the extended graph: `@KoraAppTest(TestApplication::class)`.

---

## Testcontainers integration

Combine `@Testcontainers` with `@KoraAppTest` and feed container coordinates through
`KoraAppTestConfigModifier`. The container starts before the graph is built, so its accessors are
available inside `config()`.

```kotlin
@Testcontainers
@KoraAppTest(TestApplication::class)
class UserServiceIntegrationPostgresTest : KoraAppTestConfigModifier {

    companion object {
        @Container
        @JvmStatic
        val POSTGRES = PostgreSQLContainer("postgres:16-alpine")
            .withStartupTimeout(Duration.ofSeconds(30))
    }

    @TestComponent lateinit var userService: UserService
    @TestComponent lateinit var testUserRepository: TestApplication.TestUserRepository

    override fun config(): KoraConfigModification =
        KoraConfigModification.ofString(
            """
            jdbc {
              jdbcUrl = ${'$'}{POSTGRES_JDBC_URL}
              username = ${'$'}{POSTGRES_USER}
              password = ${'$'}{POSTGRES_PASS}
              poolName = "kora-test"
            }
            flyway {
              locations = "db/migration"
            }
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

```kotlin
testImplementation("org.testcontainers:junit-jupiter:1.21.4")
testImplementation("org.testcontainers:postgresql:1.21.4")
```

`io.koraframework:database-flyway` ships `flyway-core` only — a PostgreSQL test also needs
`org.flywaydb:flyway-database-postgresql`, or Flyway fails with `Unsupported Database: PostgreSQL`.
Kafka wiring, the `goodforgod` container extensions the examples prefer, and the Testcontainers 2.x
module renames: [references/testcontainers-kotlin-reference.md](references/testcontainers-kotlin-reference.md).

---

## Mocking framework choice

| | When to pick |
|---|---|
| **MockK** (`@field:MockK`, `every {}`, `@field:SpyK`) | Pure-Kotlin codebase. Idiomatic DSL. Pin `io.mockk:mockk:1.14.11`. Recommended default. |
| **Mockito-Kotlin** (`@Mock`, ``Mockito.`when` ``, `org.mockito.kotlin.any`) | Mixed Java/Kotlin codebase or a team standardized on Mockito. `mockito-kotlin` pulls its own older `mockito-core`, so pin `mockito-core` explicitly next to it. |

Both are driven by `@TestComponent` and the mock is wired into the graph identically. Pick one per
module and stay consistent — `@TestComponent` may not be both a mock and a spy, nor both a mock and a
plain component.

---

## Common pitfalls

| Symptom | Cause | Fix |
|---------|-------|-----|
| `Cannot find generated Kora application graph for: …TestApplication` | test `@KoraApp` compiled without the test processor, or the parent app not generated as a submodule | add `kspTest(...)` here and `ksp { arg("kora.app.submodule.enabled", "true") }` in the module that owns the production `@KoraApp` |
| `Cannot inject Kora component: … No matching component was found` | component pruned (not reachable from a `@Root`), or `@Tag` mismatch | mark it `@Root`, add it to `@KoraAppTest(components = [...])`, or fix the `@Tag` |
| `Expected one matching graph component, but found N` | several graph nodes match the type | add or correct `@Tag` at the injection point |
| `@field:MockK` field is a real object | `= mockk()` initializer left next to the annotation | remove the initializer — the annotation creates the mock |
| Bare `@MockK` silently ignored, real component injected | annotation landed on the Kotlin property and `kotlin-reflect` is absent | use `@field:MockK` |
| Mock not applied / inconsistent instance | `MockKExtension` / `MockitoExtension` attached alongside `@KoraAppTest` | remove the extra `@ExtendWith(...)` |
| `Cannot use KoraAppTestConfigModifier with @KoraAppTest constructor injection` | modifier + constructor `@TestComponent` | move injection to fields or test-method parameters |
| `Cannot inject mocks through test method parameters with TestInstance.Lifecycle.PER_CLASS` | per-method mock under a per-class graph | switch to `PER_METHOD`, or declare mocks as fields |
| `IllegalArgumentException: Graph node belongs to another application graph` (`GraphImpl$GraphConditionKey.hashCode`) at graph init | the test graph contains a `@Conditional` component (any full-graph test of such an app): the extension always `copy()`s the draw and `subgraph()`s it for declared roots/mocks, and both keep the original node condition, which reads the original condition node on the derived graph | fixed in `2.0.0.RC2` (kora-projects/kora PR #963) — only `2.0.0.RC1` is affected; on RC1 no practical workaround besides keeping `@Conditional` out of the graph under test |
| `PER_CLASS` tests fail in `beforeEach` (`KoraJUnit5Extension.resetMocks`) with `Graph node value was not initialized because condition failed` | with MockK or Mockito on the classpath `resetMocks` reads every graph node, and a condition-failed `@Conditional` node throws on read; `KoraAppGraph.getAll` throws the same way instead of skipping it. Reachable once #963 is in | fixed in `2.0.0.RC2` (kora-projects/kora PR #964) — only `2.0.0.RC1` is affected; on RC1 use `PER_METHOD` and avoid `getAll` over that type |
| `Injected fields cannot be static` / `cannot be final` | `@TestComponent` on a `const`/companion/`val` field | use `lateinit var`, or constructor injection |
| `ConfigValueException: … null at path: 'ROOT.jdbc.username'` | `db { }` left in an `ofString` block | rename the section to `jdbc { }` |
| App comes up on 8080/8085 despite custom ports | `publicApiHttpPort` / `privateApiHttpPort` in test config — unknown keys, silently ignored | use `httpServer.port` and `httpServer.system.port` |
| `IllegalArgumentException: CircuitBreaker '<n>' property 'countBased' is not configured` | `resilient.circuitbreaker.<n>` without `countBased` | add `countBased.windowSize` (and set `type` explicitly, e.g. `FIXED_WINDOW`) |
| `InliningClassTransformer - Failed to transform class … Java 25 (69) is not supported` | MockK (or `mockito-kotlin`'s transitive `mockito-core`) on an old Byte Buddy | raise MockK to `1.14.11`; pin `mockito-core` next to `mockito-kotlin`. `-Dnet.bytebuddy.experimental=true` only disables the safety check — not a fix |
| Kotlin test double: `'apply' overrides nothing` | Kora contracts are `@NullMarked` + JSpecify `@Nullable`; the override used `T` where the contract says `@Nullable T` | declare the parameter `T?`. A Java fake compiles where its Kotlin twin does not |
| JUnit picks up generated `$` classes | submodule generation writes `$…` classes into the test source set | `tasks.test { exclude("**/\$*") }` |
| Test JVM will not start on Windows, `CreateProcess error=87` | `environment(["": ""])` left in the Gradle test block | delete the block |
