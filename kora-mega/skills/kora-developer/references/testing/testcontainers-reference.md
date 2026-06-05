# Testcontainers Reference

**Source:** [.kora-agent/kora-docs/mkdocs/docs/en/documentation/testing.md](.kora-agent/kora-docs/mkdocs/docs/en/documentation/testing.md)  
**Examples:** `.kora-agent/kora-examples/kora-java-database-jdbc/`

Using testcontainers-extensions for integration tests in Kora applications.

## Overview

**testcontainers-extensions** is a wrapper library over Testcontainers that provides annotations for automatic container startup in tests.

**What it provides:**
- `@TestcontainersPostgreSQL`, `@TestcontainersCassandra`, `@TestcontainersKafka` — annotations for auto-startup
- `@ConnectionPostgreSQL`, `@ConnectionCassandra`, `@ConnectionKafka` — connection object injection
- Automatic migrations (Flyway, Liquibase, Scripts, Cognitor)
- Startup modes: `PER_RUN`, `PER_CLASS`, `PER_METHOD`

---

## Dependencies

### PostgreSQL

```groovy
testImplementation "io.goodforgod:testcontainers-extensions-postgres:0.13.0"
testRuntimeOnly "org.postgresql:postgresql:42.7.3"
```

### Cassandra

```groovy
testImplementation "io.goodforgod:testcontainers-extensions-cassandra:0.13.0"
testImplementation "com.datastax.oss:java-driver-core:4.17.0"
```

### Kafka

```groovy
testImplementation "io.goodforgod:testcontainers-extensions-kafka:0.13.0"
testRuntimeOnly "org.apache.kafka:kafka-clients:3.5.1"
```

---

## PostgreSQL

### Basic test

```java
@TestcontainersPostgreSQL(
    mode = ContainerMode.PER_RUN,
    migration = @Migration(
        engine = Migration.Engines.FLYWAY,
        apply = Migration.Mode.PER_METHOD,
        drop = Migration.Mode.PER_METHOD,
        locations = {"db/migration"}
    )
)
@KoraAppTest(Application.class)
class UserRepositoryTest implements KoraAppTestConfigModifier {

    @ConnectionPostgreSQL
    private JdbcConnection connection;

    @TestComponent
    private UserRepository repository;

    @Override
    public KoraConfigModification config() {
        return KoraConfigModification.ofSystemProperty(
            "DB_URL", connection.params().jdbcUrl()
        )
        .withSystemProperty("DB_USER", connection.params().username())
        .withSystemProperty("DB_PASS", connection.params().password());
    }

    @Test
    void shouldSaveAndFind() {
        var user = new User("test@example.com");
        repository.save(user);

        var found = repository.findByEmail("test@example.com");
        assertNotNull(found);
    }
}
```

### Custom image

```java
@TestcontainersPostgreSQL(
    image = "postgis/postgis:15-3.3",  // Custom image
    mode = ContainerMode.PER_RUN
)
@KoraAppTest(Application.class)
class PostgisTest implements KoraAppTestConfigModifier {
    @ConnectionPostgreSQL
    private JdbcConnection connection;

    @Override
    public KoraConfigModification config() {
        return KoraConfigModification.ofSystemProperty(
            "DB_URL", connection.params().jdbcUrl()
        );
    }

    @Test
    void testWithPostgis() {
        // Test using PostGIS
    }
}
```

### Migrations

**Flyway:**
```java
@TestcontainersPostgreSQL(
    migration = @Migration(
        engine = Migration.Engines.FLYWAY,
        apply = Migration.Mode.PER_METHOD,
        drop = Migration.Mode.PER_METHOD
    )
)
```

**Liquibase:**
```java
@TestcontainersPostgreSQL(
    migration = @Migration(
        engine = Migration.Engines.LIQUIBASE,
        locations = {"db/changelog/db.changelog-master.xml"}
    )
)
```

### Startup modes

| Mode | Description | When to use |
|------|-------------|-------------|
| `PER_RUN` | One container for all tests | Default, fast |
| `PER_CLASS` | New container per class | Isolation between classes |
| `PER_METHOD` | New container per test | Full isolation, slow |

---

## Cassandra

### Basic test

```java
@TestcontainersCassandra(
    mode = ContainerMode.PER_RUN,
    migration = @Migration(
        engine = Migration.Engines.SCRIPTS,
        apply = Migration.Mode.PER_METHOD,
        drop = Migration.Mode.PER_METHOD,
        locations = {"migrations"}
    )
)
@KoraAppTest(Application.class)
class EventRepositoryTest implements KoraAppTestConfigModifier {

    @ConnectionCassandra
    private CassandraConnection connection;

    @TestComponent
    private EventRepository repository;

    @Override
    public KoraConfigModification config() {
        return KoraConfigModification.ofSystemProperty(
            "CASSANDRA_CONTACT_POINTS", connection.params().contactPoint()
        )
        .withSystemProperty("CASSANDRA_USER", connection.params().username())
        .withSystemProperty("CASSANDRA_PASS", connection.params().password())
        .withSystemProperty("CASSANDRA_KEYSPACE", connection.params().keyspace());
    }

    @Test
    void shouldSaveAndFind() {
        var event = new Event("1", "test-event");
        repository.save(event);

        var found = repository.findById("1");
        assertNotNull(found);
    }
}
```

### Migrations

**Scripts:**
```java
@TestcontainersCassandra(
    migration = @Migration(
        engine = Migration.Engines.SCRIPTS,
        apply = Migration.Mode.PER_METHOD,
        drop = Migration.Mode.PER_METHOD,
        dropMode = Migration.DropMode.TRUNCATE
    )
)
```

**Cognitor:**
```java
@TestcontainersCassandra(
    migration = @Migration(
        engine = Migration.Engines.COGNITOR,
        locations = {"db/migration"}
    )
)
```

---

## Kafka

### Consumer test

```java
@TestcontainersKafka(
    mode = ContainerMode.PER_RUN,
    topics = @Topics({ "my-topic" })
)
@KoraAppTest(Application.class)
class KafkaConsumerTest implements KoraAppTestConfigModifier {

    @ConnectionKafka
    private KafkaConnection connection;

    @TestComponent
    private MyListener consumer;

    @Override
    public KoraConfigModification config() {
        return KoraConfigModification.ofSystemProperty(
            "KAFKA_BOOTSTRAP", connection.params().bootstrapServers()
        );
    }

    @Test
    void shouldProcessMessage() {
        var event = new JSONObject().put("id", "123");
        connection.send("my-topic", Event.ofValueAndRandomKey(event));

        Awaitility.await()
            .atMost(Duration.ofSeconds(15))
            .until(() -> consumer.received().size() == 1);
    }
}
```

### Producer test

```java
@TestcontainersKafka(
    mode = ContainerMode.PER_RUN,
    topics = @Topics({ "my-topic" })
)
@KoraAppTest(Application.class)
class KafkaProducerTest implements KoraAppTestConfigModifier {

    @ConnectionKafka
    private KafkaConnection connection;

    @TestComponent
    private MyPublisher publisher;

    @Override
    public KoraConfigModification config() {
        return KoraConfigModification.ofSystemProperty(
            "KAFKA_BOOTSTRAP", connection.params().bootstrapServers()
        );
    }

    @Test
    void shouldSendMessage() {
        var consumer = connection.subscribe("my-topic");
        publisher.send("message");

        var received = consumer.assertReceivedAtLeast(1).get(0);
        assertEquals("message", received.value());
    }
}
```

---

## External systems (without Docker)

For CI/CD or when Docker is unavailable:

```bash
export EXTERNAL_TEST_POSTGRES_JDBC_URL="jdbc:postgresql://ci-db:5432/test"
export EXTERNAL_TEST_POSTGRES_USERNAME="ci_user"
export EXTERNAL_TEST_POSTGRES_PASSWORD="ci_pass"
```

```java
@TestcontainersPostgreSQL
@KoraAppTest(Application.class)
class ExternalTest implements KoraAppTestConfigModifier {
    @ConnectionPostgreSQL
    private JdbcConnection connection;

    @Override
    public KoraConfigModification config() {
        return KoraConfigModification.ofSystemProperty(
            "DB_URL", connection.params().jdbcUrl()
        );
    }
}
```

---

## Shared Network

For black-box tests with multiple containers:

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
    void shouldCreateResource() throws Exception {
        var httpClient = HttpClient.newHttpClient();
        var requestBody = new JSONObject().put("name", "test");

        var request = HttpRequest.newBuilder()
            .POST(HttpRequest.BodyPublishers.ofString(requestBody.toString()))
            .uri(container.getURI().resolve("/api/resources"))
            .timeout(Duration.ofSeconds(5))
            .build();

        var response = httpClient.send(request, HttpResponse.BodyHandlers.ofString());
        assertEquals(200, response.statusCode());
    }
}
```

---

## Assertions

### PostgreSQL/Cassandra

```java
@Test
void testWithAssertions() {
    // Insert
    connection.assertInserted("INSERT INTO users VALUES(1, 'test');");

    // Count
    connection.assertCountsEquals(1, "users");

    // Query
    var users = connection.queryMany(
        "SELECT * FROM users;",
        rs -> rs.getString("email")
    );

    // Query one
    var user = connection.queryOne(
        "SELECT * FROM users WHERE id = 1;",
        rs -> rs.getString("email")
    );
}
```

### Kafka

```java
@Test
void testWithAssertions() {
    var consumer = connection.subscribe("my-topic");

    // Assert received
    var received = consumer.assertReceivedAtLeast(1);

    // Assert exactly
    consumer.assertReceivedExactly(3, Duration.ofSeconds(10));

    // Access messages
    var first = received.get(0);
    String key = first.key();
    String value = first.value();
}
```

---

## Base Testcontainers (custom scenarios)

Use base `org.testcontainers:testcontainers` only when:

1. **Non-standard DB** — not available in testcontainers-extensions (DB2, Vertica)
2. **Multiple linked containers** — requires `Network`, `DockerComposeContainer`
3. **Complex customization** — needs low-level container API

### Dependencies

```groovy
testImplementation "org.testcontainers:testcontainers:1.21.3"
testImplementation "org.testcontainers:postgresql:1.21.3"
testImplementation "org.testcontainers:junit-jupiter:1.21.3"
```

### Example with a custom image

```java
import org.junit.jupiter.api.Test;
import org.testcontainers.containers.PostgreSQLContainer;
import org.testcontainers.junit.jupiter.Container;
import org.testcontainers.junit.jupiter.Testcontainers;

@Testcontainers
class CustomPostgresTest {

    @Container
    private static final PostgreSQLContainer<?> postgres = 
        new PostgreSQLContainer<>("postgis/postgis:15-3.3")
            .withDatabaseName("testdb")
            .withUsername("test")
            .withPassword("test");

    @Test
    void testWithCustomImage() {
        // Test using a custom image
    }
}
```

---

## Best Practices

1. **`PER_RUN` for speed** — one container for all tests
2. **Migrations with `drop = PER_METHOD`** — cleanup between tests
3. **Shared Network for black-box** — shared application + DB
4. **External systems for CI** — `EXTERNAL_TEST_*` variables
5. **Awaitility for async** — consumer tests with Kafka
6. **Custom image via `image`** — in the `@Testcontainers*` annotation

---

## Troubleshooting

| Problem | Solution |
|---------|---------|
| Docker unavailable | Use `EXTERNAL_TEST_*` variables |
| Slow tests | `PER_RUN` instead of `PER_METHOD` |
| Migrations not applied | Check the path: `locations = {"db/migration"}` |
| Driver conflict | Explicitly specify the driver version |

---

## Resources

- [Testcontainers Extensions GitHub](https://github.com/GoodforGod/testcontainers-extensions)
- [Testcontainers](https://www.testcontainers.org/)
- [Kora JUnit5](https://kora-projects.github.io/kora-docs/en/documentation/junit5.html)
