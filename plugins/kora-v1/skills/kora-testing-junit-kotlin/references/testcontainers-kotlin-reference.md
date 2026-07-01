# Testcontainers Reference (Kotlin)

**Source:** `.kora-agent/kora-docs/mkdocs/docs/en/documentation/junit5.md`
**Example:** `.kora-agent/kora-examples/guides/kotlin/kora-kotlin-guide-testing-integration-app`

Integration tests that combine `@Testcontainers` with `@KoraAppTest`. The container provides real infrastructure; `KoraAppTestConfigModifier` feeds its coordinates into the Kora config so the application Graph connects to it.

## Contents

- [Dependencies](#dependencies)
- [PostgreSQL pattern](#postgresql-pattern)
- [Cleanup with a TestApplication repository](#cleanup-with-a-testapplication-repository)
- [Kafka pattern](#kafka-pattern)
- [Notes](#notes)

---

## Dependencies

```kotlin
testImplementation("org.testcontainers:postgresql:1.20.4")
testImplementation("org.testcontainers:junit-jupiter:1.20.4")
```

For Flyway-based migrations in tests, add the JDBC runner module used by the application (e.g. `ru.tinkoff.kora:database-flyway`); it inherits its version from the `kora-parent` BOM.

---

## PostgreSQL pattern

Feed the container's JDBC coordinates into the config via `ofString` + `withSystemProperty`, exactly as the integration guide example does.

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

    @TestComponent
    lateinit var userService: UserService

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

    @Test
    fun shouldPersistUser() {
        val result = userService.createUser(UserRequest("John", "john@example.com"))
        assertEquals("John", result.name)
    }
}
```

`@Testcontainers` + `@Container` + `@JvmStatic` start one container for the test class and stop it after. The container starts before the Graph is built, so `POSTGRES.jdbcUrl` is available inside `config()`.

---

## Cleanup with a TestApplication repository

To reset DB state between tests, add a test-only repository through the `TestApplication` submodule pattern (see SKILL.md) and call it in `@BeforeEach`.

```kotlin
@TestComponent
lateinit var testUserRepository: TestApplication.TestUserRepository

@BeforeEach
fun cleanup() = testUserRepository.deleteAll()
```

---

## Kafka pattern

```kotlin
@Testcontainers
@KoraAppTest(Application::class)
class KafkaConsumerTest : KoraAppTestConfigModifier {

    companion object {
        @Container
        @JvmStatic
        val KAFKA = KafkaContainer(DockerImageName.parse("confluentinc/cp-kafka:7.5.0"))
    }

    override fun config(): KoraConfigModification =
        KoraConfigModification.ofString(
            """
            kafka {
              consumer {
                driverProperties { "bootstrap.servers" = ${'$'}{KAFKA_BOOTSTRAP} }
              }
            }
            """.trimIndent()
        ).withSystemProperty("KAFKA_BOOTSTRAP", KAFKA.bootstrapServers)
}
```

Adjust the config path (`kafka.consumer.driverProperties`) to match the keys your Kafka module config actually exposes.

---

## Notes

- Containers should be `@JvmStatic` in the `companion object` so `@Testcontainers` manages a single lifecycle per class.
- Prefer `ofString` (full HOCON with `${VAR}` placeholders) over `ofSystemProperty` alone when the test needs config that the default file does not contain (e.g. a distinct `poolName` or test-only Flyway locations).
- Black-box Testcontainers tests over the packaged artifact remain the strongest correctness signal; use these in-process integration tests for focused repository/SQL coverage.
