# Testcontainers JDBC Reference

Integration-testing a Kora 2.0 JDBC service against a real PostgreSQL.

## Contents

- [Testcontainers coordinates](#testcontainers-coordinates)
- [Dependencies](#dependencies)
- [Plain Testcontainers test](#plain-testcontainers-test)
- [The `io.goodforgod` extension variant](#the-iogoodforgod-extension-variant)
- [Config: the `jdbc` section](#config-the-jdbc-section)
- [Flyway](#flyway)
- [TestApplication submodule pattern](#testapplication-submodule-pattern)
- [Build wiring](#build-wiring)
- [CRUD test examples](#crud-test-examples)
- [Speed](#speed)
- [Troubleshooting](#troubleshooting)

---

## Testcontainers coordinates

`io.koraframework:kora-bom` does not constrain Testcontainers, so nothing in Kora forces a
version on you. Two facts to keep apart:

| Where | Version | Modules |
|---|---|---|
| The migrated Kora 2.0 examples and guides | **1.21.4** | `org.testcontainers:junit-jupiter`, `org.testcontainers:postgresql`, `org.testcontainers:testcontainers`, plus `io.goodforgod:testcontainers-extensions-*:0.15.0` |
| Kora's own internal test fixtures | **2.0.5** | `org.testcontainers:testcontainers-postgresql`, `testcontainers-kafka`, `testcontainers-cassandra` |

Testcontainers 2.x **renamed the database modules**: `org.testcontainers:postgresql` became
`org.testcontainers:testcontainers-postgresql`, and likewise for `kafka` and `cassandra`. If you
stay on 1.21.4 — the combination the migrated examples actually run — keep the old names. If you
move to 2.x, rename them.

`org.testcontainers:junit-jupiter` is a Testcontainers artifact whose version tracks Testcontainers,
not JUnit. Never "align" it with `org.junit:junit-bom`; Kora's own catalog does not carry it at all,
because the framework's internal fixtures manage containers without the JUnit extension.

---

## Dependencies

```groovy
dependencies {
    koraBom platform("io.koraframework:kora-bom:$koraVersion")

    testAnnotationProcessor "io.koraframework:annotation-processors"

    testRuntimeOnly "org.postgresql:postgresql:42.7.3"

    testImplementation platform("org.junit:junit-bom:$junitVersion")
    testImplementation "org.junit.jupiter:junit-jupiter"
    testImplementation "io.koraframework:test-junit5"
    testImplementation "io.koraframework:database-jdbc"
    testImplementation "io.koraframework:database-flyway"
    testImplementation "org.flywaydb:flyway-database-postgresql:13.9.0"
    testImplementation "io.koraframework:config-hocon"
    testImplementation "io.koraframework:logging-logback"

    testImplementation "org.testcontainers:junit-jupiter:1.21.4"
    testImplementation "org.testcontainers:postgresql:1.21.4"
}
```

When `TestApplication` extends another Gradle module's `@KoraApp`, every Kora module that graph
relies on must be a test dependency here too — the test compilation has to see them to build the
graph (`config-hocon`, `database-jdbc`, `database-flyway`, `http-server-undertow`, `json-common`,
`logging-logback`, whichever apply).

---

## Plain Testcontainers test

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

`@Container` on a `static` field starts the container once per class, before the extension builds
the graph — which matters, because `config()` reads `POSTGRES.getJdbcUrl()`.

---

## The `io.goodforgod` extension variant

Most migrated Kora examples use `io.goodforgod:testcontainers-extensions-postgres:0.15.0` instead
of driving `PostgreSQLContainer` by hand. It adds container reuse across the whole test run and
declarative migrations:

```groovy
testImplementation "io.goodforgod:testcontainers-extensions-postgres:0.15.0"
testImplementation "org.testcontainers:junit-jupiter:1.21.4"
```

```java
@TestcontainersPostgreSQL(
        network = @Network(shared = true),
        mode = ContainerMode.PER_RUN,
        migration = @Migration(
                engine = Migration.Engines.FLYWAY,
                apply = Migration.Mode.PER_METHOD,
                drop = Migration.Mode.PER_METHOD))
@KoraAppTest(TestApplication.class)
class IntegrationTests implements KoraAppTestConfigModifier {

    @ConnectionPostgreSQL
    private JdbcConnection connection;

    @TestComponent
    private PetService petService;

    @Override
    public KoraConfigModification config() {
        return KoraConfigModification.ofString("""
                jdbc {
                  jdbcUrl = ${POSTGRES_JDBC_URL}
                  username = ${POSTGRES_USER}
                  password = ${POSTGRES_PASS}
                  poolName = "kora"
                }""")
                .withSystemProperty("POSTGRES_JDBC_URL", connection.params().jdbcUrl())
                .withSystemProperty("POSTGRES_USER", connection.params().username())
                .withSystemProperty("POSTGRES_PASS", connection.params().password());
    }
}
```

`ContainerMode.PER_RUN` shares one container across every test class in the build, and
`@Migration(apply = PER_METHOD, drop = PER_METHOD)` gives each method a clean schema without a
manual `deleteAll()`. When migrations are driven by the extension, drop the `flyway { }` block
from the Kora config so the two do not race.

---

## Config: the `jdbc` section

Kora 2.0 renamed the JDBC config section from `db` to **`jdbc`** — `JdbcDatabaseModule` wires
`new JdbcDatabaseFactoryModule("jdbc")`. A test that kept the 1.x name fails with:

```
ConfigValueException: Config expected value, but got null at path: 'ROOT.jdbc.username'
```

The rename applies inside `KoraConfigModification.ofString` blocks exactly as it does in
`application.conf`, and that is where it is most often missed: the HOCON lives in Java source, so
resource scanners and migration scripts never touch it.

```hocon
jdbc {
  jdbcUrl = ${POSTGRES_JDBC_URL}
  username = ${POSTGRES_USER}
  password = ${POSTGRES_PASS}
  poolName = "kora-test"
  maxPoolSize = 4
}
```

Remember that `ofString` **replaces** `application.conf` for the test — the whole graph's config
must be in the block. Prefer `ofSystemProperty` when the production config already has the right
shape with `${PLACEHOLDER}` substitutions.

---

## Flyway

`io.koraframework:database-flyway` ships `flyway-core` only. Since Flyway 10 the database dialects
live in separate artifacts, so the application must add its own or startup fails with:

```
FlywayException: Unsupported Database: PostgreSQL 16.x
```

```groovy
testImplementation "io.koraframework:database-flyway"
testImplementation "org.flywaydb:flyway-database-postgresql:13.9.0"
```

```hocon
flyway {
  locations = "db/migration"
}
```

Migrations live in the application module's `src/main/resources/db/migration` and are on the test
classpath through the project dependency.

---

## TestApplication submodule pattern

Production graphs rarely contain cleanup or assertion-only repositories. Declare a second
`@KoraApp` in the test source set that extends the production one. Two source-backed shapes:

**A `@Root` default method that consumes the repository** — the repository itself stays a plain
`@Repository`, and the unused-node problem is solved by the method that depends on it:

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

**`@Root @Component` directly on the repository interface** — shorter when there are several:

```java
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
}
```

Both keep the repository in the trimmed graph. Import `Root`, `Component`, `Tag` and `KoraApp`
from `io.koraframework.common.annotation`, `Query`/`Repository` from
`io.koraframework.database.common.annotation`, and `JdbcRepository` from
`io.koraframework.database.jdbc`.

The Kora maintainers recommend black-box testing of the packaged image as the primary source of
truth (see the `kora-testing-blackbox` skill). Use this submodule pattern when component or
integration tests need direct repository access for setup, cleanup or assertions.

---

## Build wiring

Two settings, in **two different modules**.

Submodule generation goes on the module that declares the **production** `@KoraApp`:

```groovy
// production application module
tasks.named("compileJava", JavaCompile) {
    options.compilerArgs += ["-Akora.app.submodule.enabled=true"]
}
```

That makes `KoraSubmoduleProcessor` emit `<Application>SubmoduleImpl`, which the test graph needs
in order to inherit the parent application's components. When it is missing, the processor prints
a **warning**, not an error:

```
Expected @KoraApp as SubModule, but Submodule implementation not found for: com.example.Application
Check that @KoraApp was generated with compile annotation processor option: -Akora.app.submodule.enabled=true
```

The build stays green and the parent's components are silently absent from the test graph; the
failure appears later as *"No matching component was found in the application graph"*.

The processor and the JUnit filter go on the module that owns the **test** sources:

```groovy
dependencies {
    testAnnotationProcessor "io.koraframework:annotation-processors"
}

test {
    useJUnitPlatform()
    filter {
        excludeTestsMatching '*$*'
        excludeTestsMatching "*TestApplication"
    }
}
```

Watch for a module-wide `options.compilerArgs += ["-proc:none"]` — it silently disables the test
annotation processor you just declared. A test module that only consumes an already-generated
graph from another Gradle module does not need the processor at all; a module that declares its
own `@KoraApp` in `src/test` does.

---

## CRUD test examples

```java
@Test
void createUser_ShouldPersistUserInDatabase() {
    var result = userService.createUser(new UserRequest("John", "john@example.com"));

    assertEquals("John", result.name());
    assertTrue(Long.parseLong(result.id()) > 0);
    assertEquals(1, testUserRepository.findAll().size());
}

@Test
void getUsers_WithPagination_ShouldReturnCorrectPage() {
    List.of(new UserRequest("Alice", "alice@example.com"),
            new UserRequest("Bob", "bob@example.com"),
            new UserRequest("Charlie", "charlie@example.com"),
            new UserRequest("David", "david@example.com"))
        .forEach(userService::createUser);

    var result = userService.getUsers(1, 2, "name");

    assertEquals(2, result.size());
    assertEquals("Charlie", result.get(0).name());
    assertEquals("David", result.get(1).name());
}

@Test
void deleteUser_ShouldRemoveUserFromDatabase() {
    var created = userService.createUser(new UserRequest("John", "john@example.com"));

    userService.deleteUser(created.id());

    assertEquals(0, testUserRepository.findAll().size());
}
```

Repository contracts are synchronous in Kora 2.0 — `List<T>`, `Optional<T>`, `T`, `UpdateCount`,
`void`. There is nothing to subscribe to or join.

---

## Speed

Container startup and Flyway migrations dominate the runtime of these tests:

- `@TestInstance(TestInstance.Lifecycle.PER_CLASS)` builds the graph once per class instead of once
  per method. Safe when the class does not mutate shared state; combine with a `@BeforeEach`
  cleanup through the test repository.
- `ContainerMode.PER_RUN` (the `io.goodforgod` extension) or a static `@Container` on a shared base
  class reuses one database across classes.
- Config system properties force graph initialization to take an exclusive lock, so classes that
  use them serialize against each other. Where the production config already resolves
  `${PLACEHOLDER}`s, prefer `ofSystemProperty` over a full inline config for a small set of values.

---

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `Config expected value, but got null at path: 'ROOT.jdbc.username'` | `db { … }` left in the config block | Rename to `jdbc { … }` |
| `FlywayException: Unsupported Database: PostgreSQL` | `flyway-core` without a dialect | Add `org.flywaydb:flyway-database-postgresql` |
| `Expected @KoraApp as SubModule …` warning, missing components at runtime | Submodule generation off | `-Akora.app.submodule.enabled=true` on the production module |
| `Cannot find generated Kora application graph` | No processor on the test source set | `testAnnotationProcessor "io.koraframework:annotation-processors"`; check for `-proc:none` |
| Container never starts | Docker not running | Start the Docker daemon; raise `withStartupTimeout(...)` |
| Migrations not applied | Wrong `locations`, or the extension and `flyway { }` both migrating | Pick one migration owner; check `src/main/resources/db/migration` |
| JUnit tries to run `TestApplication` or `$…` classes | Generated/graph classes discovered as tests | Add the `filter { excludeTestsMatching … }` block |
| `Unresolved reference org.testcontainers.containers.PostgreSQLContainer` after a Testcontainers 2.x bump | Module renamed | `org.testcontainers:testcontainers-postgresql` |
