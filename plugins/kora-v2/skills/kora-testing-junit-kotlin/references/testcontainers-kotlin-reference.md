# Testcontainers with `@KoraAppTest` (Kotlin, Kora 2.x)

Coordinates and patterns taken from the migrated Kotlin examples on
[`kora-examples@migration/2.0`](https://github.com/kora-projects/kora-examples/tree/migration/2.0) —
[`kora-kotlin-guide-testing-integration-app`](https://github.com/kora-projects/kora-examples/tree/migration/2.0/guides/kotlin/kora-kotlin-guide-testing-integration-app),
[`kora-kotlin-crud`](https://github.com/kora-projects/kora-examples/tree/migration/2.0/examples/kotlin/kora-kotlin-crud),
[`kora-kotlin-kafka`](https://github.com/kora-projects/kora-examples/tree/migration/2.0/examples/kotlin/kora-kotlin-kafka) —
and cross-checked against the framework's own
[`gradle/libs.versions.toml`](https://github.com/kora-projects/kora/blob/2.0.0.RC2/gradle/libs.versions.toml).

Kora ships **no** Testcontainers wrapper. The container is plain Testcontainers; the only Kora part is
feeding its coordinates into the graph through `KoraAppTestConfigModifier`.

## Contents

- [Which Testcontainers version](#which-testcontainers-version)
- [PostgreSQL + Flyway](#postgresql--flyway)
- [Cleanup with a TestApplication repository](#cleanup-with-a-testapplication-repository)
- [The goodforgod container extensions](#the-goodforgod-container-extensions)
- [Kafka](#kafka)
- [Cassandra](#cassandra)
- [Notes](#notes)

---

## Which Testcontainers version

Two different answers, and they are both correct in their own place:

| Where | Version | Module names |
|---|---|---|
| **Migrated Kotlin examples and guides** — what a consuming project should copy | **`1.21.4`** | classic: `org.testcontainers:junit-jupiter`, `:postgresql`, `:minio`, `:testcontainers` |
| **The Kora framework's own internal test modules** (`internal/test-postgres`, `internal/test-kafka`, `internal/test-cassandra`) | **`2.0.5`** | renamed: `org.testcontainers:testcontainers-postgresql`, `-kafka`, `-cassandra` |

Every Kotlin example and guide in the migrated corpus uses `1.21.4`; not one uses a `2.0.x`
coordinate. The framework's `2.0.5` entries are internal test fixtures and are not published.

**Recommendation:** start from `1.21.4` with the classic names, matching the examples. If you move to
Testcontainers 2.x, remember the module renames (`postgresql` → `testcontainers-postgresql`, and so
on) — a stale `org.testcontainers:postgresql:2.0.5` simply does not resolve. Note that the framework
does not use `org.testcontainers:junit-jupiter` at all (it starts containers by hand), so the 2.x
status of the JUnit integration is not established by the corpus — verify it before relying on it.

`org.testcontainers:junit-jupiter` is a Testcontainers integration with its **own** version line.
Do not align it to the JUnit BOM (`junitVersion=6.1.3`) — those are unrelated numbers.

---

## PostgreSQL + Flyway

```kotlin
dependencies {
    testImplementation(platform("org.junit:junit-bom:${property("junitVersion")}"))
    testImplementation("org.junit.jupiter:junit-jupiter")
    testImplementation("io.koraframework:test-junit5")
    testImplementation("io.koraframework:config-hocon")
    testImplementation("io.koraframework:database-jdbc")
    testImplementation("io.koraframework:database-flyway")
    // database-flyway ships flyway-core only; without the dialect artifact Flyway fails
    // at startup with "Unsupported Database: PostgreSQL"
    testImplementation("org.flywaydb:flyway-database-postgresql:13.9.0")
    testRuntimeOnly("org.postgresql:postgresql:42.7.3")

    testImplementation("org.testcontainers:junit-jupiter:1.21.4")
    testImplementation("org.testcontainers:postgresql:1.21.4")
}
```

```kotlin
@Testcontainers
@KoraAppTest(TestApplication::class)
class UserServiceIntegrationPostgresTest : KoraAppTestConfigModifier {

    companion object {
        @Container
        @JvmStatic
        val POSTGRES = PostgreSQLContainer("postgres:16-alpine")
            .withStartupTimeout(Duration.ofSeconds(30))
            .withLogConsumer(Slf4jLogConsumer(LoggerFactory.getLogger(PostgreSQLContainer::class.java)))
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

The section is **`jdbc`**, not `db` — `JdbcDatabaseModule` binds `new JdbcDatabaseFactoryModule("jdbc")`.
A leftover `db { … }` fails with
`ConfigValueException: Config expected value, but got null at path: 'ROOT.jdbc.username'`.

`@Testcontainers` + `@Container` + `@JvmStatic` in a `companion object` starts one container per test
class and stops it afterwards. The container is up before the graph is built, so `POSTGRES.jdbcUrl`
is valid inside `config()`. An instance (non-static) `@Container` would restart per test method — far
too slow for a graph test.

Interpolating the values directly is equally valid, and is what `kora-kotlin-crud` and
`kora-kotlin-petclinic` do — **quote them**, because a JDBC URL contains characters HOCON parses:

```kotlin
jdbc {
  jdbcUrl = "${connection.params().jdbcUrl()}"
  username = "${connection.params().username()}"
  password = "${connection.params().password()}"
}
```

---

## Cleanup with a TestApplication repository

Resetting state between tests needs a repository the production `@KoraApp` does not declare. Add it
through the `TestApplication` submodule pattern (see [SKILL.md](../SKILL.md)) and call it in
`@BeforeEach`:

```kotlin
@TestComponent
lateinit var testUserRepository: TestApplication.TestUserRepository

@BeforeEach
fun cleanup() = testUserRepository.deleteAll()
```

That module needs `kspTest("io.koraframework:symbol-processors:${property("koraVersion")}")`, and the
module compiling the production `@KoraApp` needs `ksp { arg("kora.app.submodule.enabled", "true") }`.

---

## The goodforgod container extensions

Most migrated Kotlin examples do **not** hand-roll containers — they use
`io.goodforgod:testcontainers-extensions-*:0.15.0`, which manages the container through its own JUnit
extension and injects a typed connection:

```kotlin
testImplementation("io.goodforgod:testcontainers-extensions-postgres:0.15.0")
testImplementation("org.testcontainers:junit-jupiter:1.21.4")
```

```kotlin
@TestcontainersPostgreSQL(
    network = Network(shared = true),
    mode = ContainerMode.PER_RUN,
    migration = Migration(
        engine = Migration.Engines.FLYWAY,
        apply = Migration.Mode.PER_METHOD,
        drop = Migration.Mode.PER_METHOD,
    ),
)
@KoraAppTest(TestApplication::class)
class IntegrationTests(@ConnectionPostgreSQL val connection: JdbcConnection) : KoraAppTestConfigModifier {

    @TestComponent lateinit var petService: PetService

    override fun config(): KoraConfigModification = KoraConfigModification.ofString(
        """
        jdbc {
          jdbcUrl = "${connection.params().jdbcUrl()}"
          username = "${connection.params().username()}"
          password = "${connection.params().password()}"
          poolName = "kora"
        }
        """.trimIndent()
    )
}
```

Note the constructor parameter: it is resolved by the goodforgod extension, **not** by
`@TestComponent`, so it does not trip the "config modifier + constructor injection" restriction — that
rule only fires when a `@TestComponent` or mock annotation appears on a constructor parameter.

`ContainerMode.PER_RUN` shares one container across the whole Gradle test run, and the `migration`
block gives per-method schema apply/drop, which removes the need for a cleanup repository. Available
flavours in the corpus: `-postgres`, `-kafka`, `-redis`, `-scylla`, `-minio`, `-mockserver`.

This is a third-party convenience, not part of Kora. Plain Testcontainers works identically.

---

## Kafka

The migrated Kafka examples do **not** embed a Kafka config block in `ofString`. The application's own
`application.conf` already contains a `${KAFKA_BOOTSTRAP}` placeholder, and the test only supplies it:

```kotlin
fun kafkaConfig(connection: KafkaConnection): KoraConfigModification =
    KoraConfigModification.ofSystemProperty("KAFKA_BOOTSTRAP", connection.params().bootstrapServers())
```

with `application.conf` holding a **named** consumer, matching the `@KafkaListener` config path:

```hocon
kafka {
  consumer {
    my-listener {
      pollTimeout: 250ms
      topics: "my-topic-consumer"
      driverProperties {
        "bootstrap.servers": ${KAFKA_BOOTSTRAP}
        "group.id": "my-group-id"
        "auto.offset.reset" = "earliest"
        "enable.auto.commit" = true
      }
      telemetry.logging.enabled = true
    }
  }
}
```

There is no bare `kafka.consumer.driverProperties` — every consumer and producer is a named section
under `kafka.consumer` / `kafka.producer`, and `@KafkaListener("kafka.consumer.my-listener")` names it.

The consumer container is a graph component that nothing else depends on, so it must be **requested**
or the listener never starts:

```kotlin
@TestcontainersKafka(mode = ContainerMode.PER_RUN, topics = Topics("my-topic-consumer"))
@KoraAppTest(Application::class)
class AutoCommitValueListenerTests : KoraAppTestConfigModifier {

    @ConnectionKafka
    lateinit var connection: KafkaConnection

    // the generated container Lifecycle for AutoCommitValueListener#process —
    // without this @TestComponent it is pruned and no message is consumed
    @Tag(AutoCommitValueListenerModule.AutoCommitValueListenerProcessTag::class)
    @TestComponent
    lateinit var consumerLifecycle: Lifecycle

    @TestComponent
    lateinit var consumer: AutoCommitValueListener

    override fun config(): KoraConfigModification = kafkaConfig(connection)

    @Test
    fun processed() {
        connection.send("my-topic-consumer", Event.ofValueAndRandomKey("Ivan"))
        Awaitility.await().atMost(Duration.ofSeconds(15))
            .pollExecutorService(Executors.newSingleThreadExecutor())
            .until { consumer.received().size == 1 }
    }
}
```

The generated tag follows `<ListenerClass>Module.<Method>Tag`; check the generated sources for the
exact name in your project, and see [`kora-kafka-consumer`](../../kora-kafka-consumer/SKILL.md) for
the listener contract itself.

Waiting is a real wait (Awaitility, or MockK's `verify(timeout = …)`) — there is no coroutine
scheduler to advance, because nothing suspends. See
[coroutines-migration-reference.md](coroutines-migration-reference.md).

---

## Cassandra

The Cassandra driver module moved off `com.datastax.oss` — it is
**`org.apache.cassandra:java-driver-core`** in 2.0. The migrated Kotlin Cassandra examples run against
Scylla through `io.goodforgod:testcontainers-extensions-scylla:0.15.0`; the framework's own internal
fixture uses `org.testcontainers:testcontainers-cassandra` (2.x naming) and explicitly excludes the
old `com.datastax.cassandra:cassandra-driver-core`. Repository and mapping details:
[`kora-database-cassandra`](../../kora-database-cassandra/SKILL.md).

---

## Notes

- Keep containers `@JvmStatic` in a `companion object`; an instance field restarts them per method.
- Prefer `ofString` (full HOCON, placeholders fed by `withSystemProperty`) when the test needs keys
  the packaged config does not have; prefer plain `ofSystemProperty` when you only need to fill a
  placeholder the application config already declares — that is the lighter, example-preferred shape.
- Telemetry `logging.enabled` and `metrics.enabled` default to **false**. A container test that
  asserts on log output or scraped metrics has to switch them on in the test config.
- Delete any `environment(["": ""])` left in a Gradle test block: an empty environment-variable name
  stops the test JVM on Windows with `CreateProcess error=87, The parameter is incorrect`.
- In-process container tests cover repositories and SQL well. Routing, serialization, validation,
  config loading and probes are better covered by
  [`kora-testing-blackbox`](../../kora-testing-blackbox/SKILL.md) over the packaged artifact — the
  migrated `kora-kotlin-crud` example states that preference in its own `TestApplication` docs.
