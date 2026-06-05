# Testcontainers Extensions Reference

**Source:** [.kora-agent/kora-docs/mkdocs/docs/en/documentation/testing.md](.kora-agent/kora-docs/mkdocs/docs/en/documentation/testing.md)  
**Examples:** `.kora-agent/kora-examples/kora-java-database-jdbc/`, `.kora-agent/kora-examples/kora-java-blackbox/`

**Integration and black-box testing with testcontainers-extensions for the Kora Framework.**

> **Important:** This document describes the **default** approach for integration and black-box tests in Kora. Use `testcontainers-extensions` for all integration tests with databases. Use the base `testcontainers` only when customization not available in the extensions is explicitly required.

---

## Why testcontainers-extensions?

`testcontainers-extensions` (GoodforGod) is a specialized library for testing with Kora that provides:

- **Ready-made JUnit5 extensions** for PostgreSQL, Cassandra, MySQL, Oracle, and more
- **Automatic container lifecycle management**
- **Built-in migration support** (Flyway, Liquibase, Scripts)
- **Kora-specific annotations** (`@ConnectionPostgreSQL`, `@ConnectionCassandra`)
- **Assertions API** for data verification
- **External DB support** for CI/CD via environment variables

---

## Available implementations

**Version:** `0.13.1` (build on top of Testcontainers 1.21.3)

### Relational databases (JDBC)

| Extension | Dependency | Documentation | JDBC driver |
|-----------|-------------|--------------|--------------|
| PostgreSQL | `io.goodforgod:testcontainers-extensions-postgres:0.13.1` | [README](https://raw.githubusercontent.com/GoodforGod/testcontainers-extensions/refs/heads/master/postgres/README.md) | `org.postgresql:postgresql:42.7.4` |
| MySQL | `io.goodforgod:testcontainers-extensions-mysql:0.13.1` | [README](https://raw.githubusercontent.com/GoodforGod/testcontainers-extensions/refs/heads/master/mysql/README.md) | `com.mysql:mysql-connector-j:9.1.0` |
| MariaDB | `io.goodforgod:testcontainers-extensions-mariadb:0.13.1` | [README](https://raw.githubusercontent.com/GoodforGod/testcontainers-extensions/refs/heads/master/mariadb/README.md) | `org.mariadb.jdbc:mariadb-java-client:3.4.1` |
| Oracle (XE) | `io.goodforgod:testcontainers-extensions-oracle:0.13.1` | [README](https://raw.githubusercontent.com/GoodforGod/testcontainers-extensions/refs/heads/master/oracle/README.md) | `com.oracle.database.jdbc:ojdbc8:21.5.0.0` |
| CockroachDB | `io.goodforgod:testcontainers-extensions-cockroachdb:0.13.1` | [README](https://raw.githubusercontent.com/GoodforGod/testcontainers-extensions/refs/heads/master/cockroachdb/README.md) | `org.postgresql:postgresql:42.7.4` |
| ClickHouse | `io.goodforgod:testcontainers-extensions-clickhouse:0.13.1` | [README](https://raw.githubusercontent.com/GoodforGod/testcontainers-extensions/refs/heads/master/clickhouse/README.md) | `com.clickhouse:clickhouse-jdbc:0.9.2` |

### NoSQL databases

| Extension | Dependency | Documentation | Driver |
|-----------|-------------|--------------|----------|
| Cassandra | `io.goodforgod:testcontainers-extensions-cassandra:0.13.1` | [README](https://raw.githubusercontent.com/GoodforGod/testcontainers-extensions/refs/heads/master/cassandra/README.md) | `org.apache.cassandra:java-driver-core:4.18.1` |
| ScyllaDB | `io.goodforgod:testcontainers-extensions-scylladb:0.13.1` | [README](https://raw.githubusercontent.com/GoodforGod/testcontainers-extensions/refs/heads/master/scylladb/README.md) | `org.apache.cassandra:java-driver-core:4.18.1` |
| Redis | `io.goodforgod:testcontainers-extensions-redis:0.13.1` | [README](https://raw.githubusercontent.com/GoodforGod/testcontainers-extensions/refs/heads/master/redis/README.md) | `redis.clients:jedis:5.2.0` |

### Message queues

| Extension | Dependency | Documentation | Client |
|-----------|-------------|--------------|----------|
| Kafka | `io.goodforgod:testcontainers-extensions-kafka:0.13.1` | [README](https://raw.githubusercontent.com/GoodforGod/testcontainers-extensions/refs/heads/master/kafka/README.md) | `org.apache.kafka:kafka-clients:3.8.0` |
| Redpanda | `io.goodforgod:testcontainers-extensions-redpanda:0.13.1` | [README](https://raw.githubusercontent.com/GoodforGod/testcontainers-extensions/refs/heads/master/redpanda/README.md) | `org.apache.kafka:kafka-clients:3.8.0` |
| NATS | `io.goodforgod:testcontainers-extensions-nats:0.13.1` | [README](https://raw.githubusercontent.com/GoodforGod/testcontainers-extensions/refs/heads/master/nats/README.md) | `io.nats:jnats:2.22.0` |

### Object Storage and mocks

| Extension | Dependency | Documentation | Client |
|-----------|-------------|--------------|----------|
| MinIO | `io.goodforgod:testcontainers-extensions-minio:0.13.1` | [README](https://raw.githubusercontent.com/GoodforGod/testcontainers-extensions/refs/heads/master/minio/README.md) | `io.minio:minio:8.5.12` |
| MockServer | `io.goodforgod:testcontainers-extensions-mockserver:0.13.1` | [README](https://raw.githubusercontent.com/GoodforGod/testcontainers-extensions/refs/heads/master/mockserver/README.md) | `org.mock-server:mockserver-client-java:5.15.0` |

---

## Dependencies

### PostgreSQL (JDBC)

```groovy
dependencies {
    testImplementation "ru.tinkoff.kora:test-junit5"
    testImplementation "io.goodforgod:testcontainers-extensions-postgres:0.13.1"
    testRuntimeOnly "org.postgresql:postgresql:42.7.4"
}
```

### Cassandra

```groovy
dependencies {
    testImplementation "ru.tinkoff.kora:test-junit5"
    testImplementation "io.goodforgod:testcontainers-extensions-cassandra:0.13.1"
    testImplementation "org.apache.cassandra:java-driver-core:4.18.1"
}
```

### MySQL

```groovy
dependencies {
    testImplementation "ru.tinkoff.kora:test-junit5"
    testImplementation "io.goodforgod:testcontainers-extensions-mysql:0.13.1"
    testRuntimeOnly "com.mysql:mysql-connector-j:9.1.0"
}
```

### MariaDB

```groovy
dependencies {
    testImplementation "ru.tinkoff.kora:test-junit5"
    testImplementation "io.goodforgod:testcontainers-extensions-mariadb:0.13.1"
    testRuntimeOnly "org.mariadb.jdbc:mariadb-java-client:3.4.1"
}
```

### Oracle (XE)

```groovy
dependencies {
    testImplementation "ru.tinkoff.kora:test-junit5"
    testImplementation "io.goodforgod:testcontainers-extensions-oracle:0.13.1"
    testRuntimeOnly "com.oracle.database.jdbc:ojdbc8:21.5.0.0"
}
```

### ClickHouse

```groovy
dependencies {
    testImplementation "ru.tinkoff.kora:test-junit5"
    testImplementation "io.goodforgod:testcontainers-extensions-clickhouse:0.13.1"
    testRuntimeOnly "com.clickhouse:clickhouse-jdbc:0.9.2"
}
```

### Redis

```groovy
dependencies {
    testImplementation "ru.tinkoff.kora:test-junit5"
    testImplementation "io.goodforgod:testcontainers-extensions-redis:0.13.1"
    testImplementation "redis.clients:jedis:5.2.0"
}
```

### Kafka

```groovy
dependencies {
    testImplementation "ru.tinkoff.kora:test-junit5"
    testImplementation "io.goodforgod:testcontainers-extensions-kafka:0.13.1"
    testImplementation "org.apache.kafka:kafka-clients:3.8.0"
}
```

### MinIO

```groovy
dependencies {
    testImplementation "ru.tinkoff.kora:test-junit5"
    testImplementation "io.goodforgod:testcontainers-extensions-minio:0.13.1"
    testImplementation "io.minio:minio:8.5.12"
}
```

---

## Quick start

### PostgreSQL + Flyway

```java
import io.goodforgod.testcontainers.extensions.ContainerMode;
import io.goodforgod.testcontainers.extensions.jdbc.*;
import org.jetbrains.annotations.NotNull;
import org.junit.jupiter.api.Test;
import ru.tinkoff.kora.test.extension.junit5.*;

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

    @NotNull
    @Override
    public KoraConfigModification config() {
        return KoraConfigModification.ofSystemProperty("POSTGRES_JDBC_URL", connection.params().jdbcUrl())
            .withSystemProperty("POSTGRES_USER", connection.params().username())
            .withSystemProperty("POSTGRES_PASS", connection.params().password());
    }

    @Test
    void shouldInsertAndFindUser() {
        var user = new User("1", "test@example.com", LocalDateTime.now());
        repository.insert(user);

        var found = repository.findById("1");
        assertNotNull(found);
        assertEquals("test@example.com", found.email());
    }
}
```

### Cassandra + Scripts

```java
import io.goodforgod.testcontainers.extensions.ContainerMode;
import io.goodforgod.testcontainers.extensions.cassandra.*;
import org.jetbrains.annotations.NotNull;
import org.junit.jupiter.api.Test;
import ru.tinkoff.kora.test.extension.junit5.*;

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

    @NotNull
    @Override
    public KoraConfigModification config() {
        return KoraConfigModification.ofSystemProperty("CASSANDRA_CONTACT_POINTS", connection.params().contactPoint())
            .withSystemProperty("CASSANDRA_USER", connection.params().username())
            .withSystemProperty("CASSANDRA_PASS", connection.params().password())
            .withSystemProperty("CASSANDRA_DC", connection.params().datacenter())
            .withSystemProperty("CASSANDRA_KEYSPACE", connection.params().keyspace());
    }

    @Test
    void shouldInsertAndFindEvent() {
        var event = new Event("1", "test-event", 42);
        repository.insert(event);

        var found = repository.findById("1");
        assertNotNull(found);
        assertEquals("test-event", found.name());
    }
}
```

---

## Container startup modes

| Mode | Description | When to use |
|------|-------------|-------------|
| `PER_RUN` | One container for all tests in the class | **Recommended by default** — fast and clean |
| `PER_CLASS` | New container per test class | Isolation between test classes |
| `PER_METHOD` | New container per test | Full isolation (slow, use rarely) |

---

## Migrations

### Flyway (PostgreSQL, MySQL)

```java
@TestcontainersPostgreSQL(
    migration = @Migration(
        engine = Migration.Engines.FLYWAY,
        apply = Migration.Mode.PER_METHOD,
        drop = Migration.Mode.PER_METHOD
    )
)
```

**Structure:**
```
src/test/resources/db/migration/
├── V1__create_users.sql
├── V2__create_orders.sql
└── V3__add_indexes.sql
```

**Example (V1__create_users.sql):**
```sql
CREATE TABLE IF NOT EXISTS users (
    id VARCHAR PRIMARY KEY,
    email VARCHAR NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);
```

### Liquibase (PostgreSQL, MySQL)

```java
@TestcontainersPostgreSQL(
    migration = @Migration(
        engine = Migration.Engines.LIQUIBASE,
        locations = {"db/changelog/db.changelog-master.xml"}
    )
)
```

### Scripts (Cassandra)

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

**Structure:**
```
src/test/resources/migrations/
├── 1_setup.cql
└── 2_add_tables.cql
```

**Example (1_setup.cql):**
```cql
CREATE KEYSPACE IF NOT EXISTS test_keyspace
WITH replication = {'class': 'SimpleStrategy', 'replication_factor': 1};

CREATE TABLE IF NOT EXISTS test_keyspace.events (
    id TEXT PRIMARY KEY,
    name TEXT,
    value INT
);
```

---

## Kora Integration

### Connection configuration

```java
@KoraAppTest(Application.class)
class MyTest implements KoraAppTestConfigModifier {
    @ConnectionPostgreSQL  // or @ConnectionCassandra
    private JdbcConnection connection;

    @Override
    public KoraConfigModification config() {
        return KoraConfigModification.ofSystemProperty(
            "POSTGRES_JDBC_URL", connection.params().jdbcUrl()
        )
        .withSystemProperty("POSTGRES_USER", connection.params().username())
        .withSystemProperty("POSTGRES_PASS", connection.params().password());
    }
}
```

### Repository injection

```java
@TestComponent
private UserRepository repository;
```

### Tagging (for multiple DBs)

```java
@Tag(UserRepositoryModule.UserRepositoryTag.class)
@TestComponent
private UserRepository repository;
```

---

## Assertions API

### PostgreSQL

```java
@Test
void testWithAssertions() {
    // Insert with verification
    connection.assertInserted("INSERT INTO users VALUES(1, 'test');");
    
    // Row count check
    connection.assertQueriesEquals(1, "SELECT * FROM users;");
    
    // Query with mapper (multiple results)
    var emails = connection.queryMany(
        "SELECT * FROM users;",
        rs -> rs.getString("email")
    );
    
    // Query with single result
    var email = connection.queryOne(
        "SELECT * FROM users WHERE id = 1;",
        rs -> rs.getString("email")
    );
}
```

### Cassandra

```java
@Test
void testWithAssertions() {
    // Insert
    connection.execute("INSERT INTO events(id, name, value) VALUES('1', 'test', 42);");
    
    // Query with mapper (multiple results)
    var names = connection.queryMany(
        "SELECT * FROM events;",
        row -> row.getString("name")
    );
    
    // Query with single result
    var name = connection.queryOne(
        "SELECT * FROM events WHERE id = '1';",
        row -> row.getString("name")
    );
}
```

---

## Advanced patterns

### Container customization

```java
@TestcontainersPostgreSQL(mode = ContainerMode.PER_CLASS)
class CustomTests {
    @ContainerPostgreSQL
    private static final PostgreSQLContainer<?> container = 
        new PostgreSQLContainer<>("postgres:15-alpine")
            .withDatabaseName("testdb")
            .withInitScript("init.sql");
}
```

### Shared Network (for multiple containers)

```java
@TestcontainersPostgreSQL(network = @Network(shared = true))
class NetworkTests {
    // Container will be on the shared network
}
```

### External DB (CI/CD)

For CI/CD or when Docker is unavailable, use an external DB via environment variables:

```bash
# PostgreSQL
export EXTERNAL_TEST_POSTGRES_JDBC_URL="jdbc:postgresql://ci-db:5432/test"
export EXTERNAL_TEST_POSTGRES_USERNAME="ci_user"
export EXTERNAL_TEST_POSTGRES_PASSWORD="ci_pass"

# Cassandra
export EXTERNAL_TEST_CASSANDRA_HOST="ci-cassandra"
export EXTERNAL_TEST_CASSANDRA_PORT="9042"
export EXTERNAL_TEST_CASSANDRA_USERNAME="cassandra"
export EXTERNAL_TEST_CASSANDRA_PASSWORD="cassandra"
export EXTERNAL_TEST_CASSANDRA_DATACENTER="datacenter1"
export EXTERNAL_TEST_CASSANDRA_KEYSPACE="test_keyspace"
```

---

## Best Practices

1. **PER_RUN by default** — one container for all tests in the class + `drop = PER_METHOD` for cleanliness
2. **Group tests by repository** — `UserRepositoryTests`, `OrderRepositoryTests`
3. **Use `@TestComponent`** — auto-injection from Kora DI
4. **`CREATE IF NOT EXISTS` in migrations** — protection against re-application
5. **`TRUNCATE` for Cassandra** — fast cleanup between tests
6. **Assertions for verification** — `assertInserted`, `assertQueriesEquals`
7. **External DB for CI** — use `EXTERNAL_TEST_*` variables

---

## Troubleshooting

| Problem | Solution |
|---------|---------|
| Docker unavailable | Use `EXTERNAL_TEST_*` variables for an external DB |
| Migrations not applied | Check the path: `locations = {"db/migration"}` |
| Tests are slow | Use `PER_RUN` instead of `PER_METHOD` |
| Driver conflict | Explicitly specify the driver in `testRuntimeOnly` / `testImplementation` |
| Keyspace not created (Cassandra) | Specify the keyspace in the migration: `CREATE TABLE my_keyspace.events` |

---

## Test examples

### JdbcCrudSyncTests

```java
@TestcontainersPostgreSQL(
    mode = ContainerMode.PER_RUN,
    migration = @Migration(
        engine = Migration.Engines.FLYWAY,
        apply = Migration.Mode.PER_METHOD,
        drop = Migration.Mode.PER_METHOD
    )
)
@KoraAppTest(Application.class)
class JdbcCrudSyncTests implements KoraAppTestConfigModifier {

    @ConnectionPostgreSQL
    private JdbcConnection connection;

    @TestComponent
    private JdbcCrudSyncRepository repository;

    @Override
    public KoraConfigModification config() {
        return KoraConfigModification.ofSystemProperty("POSTGRES_JDBC_URL", connection.params().jdbcUrl())
            .withSystemProperty("POSTGRES_USER", connection.params().username())
            .withSystemProperty("POSTGRES_PASS", connection.params().password());
    }

    @Test
    void syncSingle() {
        var entity = new Entity("1", 1, "2", null);
        repository.insert(entity);

        var found = repository.findById("1");
        assertNotNull(found);
        assertEquals("1", found.id());
    }
}
```

### CassandraUdtTests

```java
@TestcontainersCassandra(
    mode = ContainerMode.PER_RUN,
    migration = @Migration(
        engine = Migration.Engines.SCRIPTS,
        apply = Migration.Mode.PER_METHOD,
        drop = Migration.Mode.PER_METHOD
    )
)
@KoraAppTest(Application.class)
class CassandraUdtTests implements KoraAppTestConfigModifier {

    @ConnectionCassandra
    private CassandraConnection connection;

    @TestComponent
    private CassandraUdtRepository repository;

    @Override
    public KoraConfigModification config() {
        return KoraConfigModification.ofSystemProperty("CASSANDRA_CONTACT_POINTS", connection.params().contactPoint())
            .withSystemProperty("CASSANDRA_USER", connection.params().username())
            .withSystemProperty("CASSANDRA_PASS", connection.params().password())
            .withSystemProperty("CASSANDRA_DC", connection.params().datacenter())
            .withSystemProperty("CASSANDRA_KEYSPACE", connection.params().keyspace());
    }

    @Test
    void udtInsertAndSelect() {
        var user = new User("1", new Name("John", "Doe"));
        repository.insert(user);

        var found = repository.findById("1");
        assertNotNull(found);
        assertEquals("John", found.name().first());
    }
}
```

---

## When to use base testcontainers

See [testcontainers-reference.md](testcontainers-reference.md) — full guide on base testcontainers for custom scenarios.

**In brief:** use base testcontainers only when:
1. Non-standard DB (not available in extensions)
2. Complex customization (custom images, scripts)
3. Multiple linked containers (Network, Docker Compose)

---

## Resources

- [GitHub Repository](https://github.com/GoodforGod/testcontainers-extensions) — source code and examples
- [Kora JUnit5 Extension](https://kora-projects.github.io/kora-docs/en/documentation/junit5.html) — Kora testing
- [Kora JDBC Examples](https://github.com/kora-projects/kora-examples/tree/master/kora-java-database-jdbc/src/test) — JDBC test examples
- [Kora Cassandra Examples](https://github.com/kora-projects/kora-examples/tree/master/kora-java-database-cassandra/src/test) — Cassandra test examples

### Extension documentation (README.md)

**Databases (JDBC):**
- [PostgreSQL](https://raw.githubusercontent.com/GoodforGod/testcontainers-extensions/refs/heads/master/postgres/README.md)
- [MySQL](https://raw.githubusercontent.com/GoodforGod/testcontainers-extensions/refs/heads/master/mysql/README.md)
- [MariaDB](https://raw.githubusercontent.com/GoodforGod/testcontainers-extensions/refs/heads/master/mariadb/README.md)
- [Oracle](https://raw.githubusercontent.com/GoodforGod/testcontainers-extensions/refs/heads/master/oracle/README.md)
- [CockroachDB](https://raw.githubusercontent.com/GoodforGod/testcontainers-extensions/refs/heads/master/cockroachdb/README.md)
- [ClickHouse](https://raw.githubusercontent.com/GoodforGod/testcontainers-extensions/refs/heads/master/clickhouse/README.md)

**NoSQL databases:**
- [Cassandra](https://raw.githubusercontent.com/GoodforGod/testcontainers-extensions/refs/heads/master/cassandra/README.md)
- [ScyllaDB](https://raw.githubusercontent.com/GoodforGod/testcontainers-extensions/refs/heads/master/scylladb/README.md)
- [Redis](https://raw.githubusercontent.com/GoodforGod/testcontainers-extensions/refs/heads/master/redis/README.md)

**Queues:**
- [Kafka](https://raw.githubusercontent.com/GoodforGod/testcontainers-extensions/refs/heads/master/kafka/README.md)
- [Redpanda](https://raw.githubusercontent.com/GoodforGod/testcontainers-extensions/refs/heads/master/redpanda/README.md)
- [NATS](https://raw.githubusercontent.com/GoodforGod/testcontainers-extensions/refs/heads/master/nats/README.md)

**Object Storage and mocks:**
- [MinIO](https://raw.githubusercontent.com/GoodforGod/testcontainers-extensions/refs/heads/master/minio/README.md)
- [MockServer](https://raw.githubusercontent.com/GoodforGod/testcontainers-extensions/refs/heads/master/mockserver/README.md)
