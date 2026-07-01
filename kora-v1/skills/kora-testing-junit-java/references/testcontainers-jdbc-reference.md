# Testcontainers JDBC Reference

**Source:** `.kora-agent/kora-docs/mkdocs/docs/en/guides/testing-integration.md`,
`.kora-agent/kora-examples/guides/java/kora-java-guide-testing-integration-app`

Integration testing a Kora JDBC service against a real PostgreSQL via Testcontainers.

## Contents

- [Dependencies](#dependencies)
- [PostgreSQL test](#postgresql-test)
- [TestApplication submodule pattern](#testapplication-submodule-pattern)
- [Build wiring](#build-wiring)
- [CRUD test examples](#crud-test-examples)
- [Flyway](#flyway)
- [Best practices](#best-practices)
- [Troubleshooting](#troubleshooting)

---

## Dependencies

```groovy
dependencies {
    koraBom platform("ru.tinkoff.kora:kora-parent:1.2.17")

    testRuntimeOnly "org.postgresql:postgresql:42.7.3"
    testImplementation "org.testcontainers:junit-jupiter:1.21.4"
    testImplementation "org.testcontainers:postgresql:1.21.4"
    testImplementation "ru.tinkoff.kora:database-jdbc"
    testImplementation "ru.tinkoff.kora:database-flyway"
    testImplementation "ru.tinkoff.kora:test-junit5"
}
```

When `TestApplication` extends another module's `@KoraApp`, add the database modules it
needs as explicit test dependencies (e.g. `database-jdbc`, `database-flyway`, plus
`config-hocon` and `logging-logback` if the production graph relies on them).

---

## PostgreSQL test

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

---

## TestApplication submodule pattern

Production graphs rarely contain cleanup or assertion-only repositories. Declare a second
`@KoraApp` in the test source set that extends the production one and adds those components.
Mark a `@Root` default method that consumes the test repository so the otherwise-unused
repository is included in the graph.

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

The Kora maintainers recommend black-box testing (see the `kora-testing-blackbox` skill)
as the primary source of truth, because a running production image can differ from a test
graph in JVM flags, base image, native libraries, and config completeness. Use this
submodule pattern when you need direct repository access for setup/cleanup/assertions.

---

## Build wiring

Submodule generation must be enabled on the **production application module** (the module
that declares the original `@KoraApp`), not on the test compilation:

```groovy
// in the production application module's build.gradle
compileJava {
    options.compilerArgs += ["-Akora.app.submodule.enabled=true"]
}
```

In the test module, add the annotation processor as a test dependency so the test graph
(`$TestApplicationImpl`) is generated, and exclude generated classes from JUnit discovery:

```groovy
dependencies {
    testAnnotationProcessor "ru.tinkoff.kora:annotation-processors"
}

test {
    useJUnitPlatform()
    filter {
        excludeTestsMatching '*$*'
        excludeTestsMatching "*TestApplication"
    }
}
```

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
    List.of(
                    new UserRequest("Alice", "alice@example.com"),
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

---

## Flyway

The `ru.tinkoff.kora:database-flyway` module runs migrations on startup. Point it at your
migration directory in the test config:

```hocon
flyway {
  locations = "db/migration"
}
```

Migrations live in `src/main/resources/db/migration` of the application module.

---

## Best practices

1. Use `@Testcontainers` + `@Container` for automatic container lifecycle.
2. Set an explicit `withStartupTimeout(...)` for slow CI environments.
3. Attach a `Slf4jLogConsumer` to debug container startup.
4. Clean up state in `@BeforeEach` via the test repository for isolation.
5. Pass credentials as system properties into the real config, not hardcoded strings.

---

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| Container never starts | Docker not running | Start the Docker daemon |
| Migration error | Migrations not found | Check `src/main/resources/db/migration` |
| Connection failed | Wrong JDBC URL | Use `POSTGRES.getJdbcUrl()` |
| `Expected @KoraApp as SubModule` | Submodule generation off | Add `-Akora.app.submodule.enabled=true` to the production module |
| JUnit runs `$...Impl`/`TestApplication` | Generated classes discovered | Add the `filter { excludeTestsMatching ... }` block |
| `AccessDeniedException` in Gradle cache | Locked cache | `./gradlew --stop` and retry |
