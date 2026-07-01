# Testcontainers Reference

**Purpose:** Standard Testcontainers usage for Kora application testing.

> **Important:** This document covers **standard Testcontainers** (`org.testcontainers:testcontainers`) without wrapper libraries. Kora does not ship its own Testcontainers integration; all examples use the plain Testcontainers API.

## Contents

1. [Overview](#overview)
2. [Dependencies](#dependencies)
3. [PostgreSQL](#postgresql)
4. [Kafka](#kafka)
5. [Wait strategies](#wait-strategies)
6. [Container reuse](#container-reuse)
7. [Best practices](#best-practices)

---

## Overview

Testcontainers provides JUnit 5 extensions for automatic container lifecycle management:

- `@Testcontainers` — enables extension on test class
- `@Container` — marks static/instance fields for lifecycle management
- `Network` — isolated container networking
- Wait strategies — `Wait.forHttp()`, `Wait.forLogMessage()`, etc.

---

## Dependencies

### PostgreSQL

```groovy
testImplementation "org.testcontainers:junit-jupiter:1.21.4"
testImplementation "org.testcontainers:postgresql:1.21.4"
testRuntimeOnly "org.postgresql:postgresql:42.7.4"
```

### Kafka

```groovy
testImplementation "org.testcontainers:junit-jupiter:1.21.4"
testImplementation "org.testcontainers:kafka:1.21.4"
testRuntimeOnly "org.apache.kafka:kafka-clients:3.9.0"
```

### MySQL

```groovy
testImplementation "org.testcontainers:junit-jupiter:1.21.4"
testImplementation "org.testcontainers:mysql:1.21.4"
testRuntimeOnly "com.mysql:mysql-connector-j:9.1.0"
```

---

## PostgreSQL

### Basic Test

```java
import org.junit.jupiter.api.Test;
import org.testcontainers.containers.PostgreSQLContainer;
import org.testcontainers.junit.jupiter.Container;
import org.testcontainers.junit.jupiter.Testcontainers;
import org.testcontainers.utility.DockerImageName;

import java.sql.Connection;
import java.sql.DriverManager;
import java.sql.ResultSet;
import java.sql.Statement;

import static org.junit.jupiter.api.Assertions.*;

@Testcontainers
class UserRepositoryTest {

    @Container
    static PostgreSQLContainer<?> postgres = new PostgreSQLContainer<>(
            DockerImageName.parse("postgres:15-alpine"))
        .withDatabaseName("testdb")
        .withUsername("test")
        .withPassword("test")
        .withInitScript("db/migration/V1__init.sql");

    @Test
    void shouldSaveAndFind() throws Exception {
        try (Connection conn = DriverManager.getConnection(
                postgres.getJdbcUrl(),
                postgres.getUsername(),
                postgres.getPassword());
             Statement stmt = conn.createStatement()) {
            
            stmt.execute("INSERT INTO users (email) VALUES ('test@example.com')");
            ResultSet rs = stmt.executeQuery("SELECT COUNT(*) FROM users");
            rs.next();
            assertEquals(1, rs.getInt(1));
        }
    }
}
```

### With Flyway Migrations

```java
import org.flywaydb.core.Flyway;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.testcontainers.containers.PostgreSQLContainer;
import org.testcontainers.junit.jupiter.Container;
import org.testcontainers.junit.jupiter.Testcontainers;
import org.testcontainers.utility.DockerImageName;

@Testcontainers
class FlywayMigrationTest {

    @Container
    static PostgreSQLContainer<?> postgres = new PostgreSQLContainer<>(
            DockerImageName.parse("postgres:15-alpine"))
        .withDatabaseName("testdb")
        .withUsername("test")
        .withPassword("test");

    @BeforeEach
    void migrate() {
        Flyway.configure()
            .dataSource(
                postgres.getJdbcUrl(),
                postgres.getUsername(),
                postgres.getPassword())
            .locations("db/migration")
            .load()
            .migrate();
    }

    @Test
    void testWithMigrations() {
        // Database is migrated before each test
    }
}
```

### Shared Network

Use `Network.SHARED` so the application container reaches infrastructure by its network alias (`postgres`). `AppContainer` is the `GenericContainer<AppContainer>` wrapper from [blackbox-integration-reference.md](blackbox-integration-reference.md).

```java
import org.junit.jupiter.api.Test;
import org.testcontainers.containers.Network;
import org.testcontainers.containers.PostgreSQLContainer;
import org.testcontainers.junit.jupiter.Container;
import org.testcontainers.junit.jupiter.Testcontainers;

@Testcontainers
class SharedNetworkTest {

    @Container
    static final PostgreSQLContainer<?> postgres = new PostgreSQLContainer<>("postgres:16-alpine")
        .withNetwork(Network.SHARED)
        .withNetworkAliases("postgres");

    @Container
    static final AppContainer app = new AppContainer()
        .withNetwork(Network.SHARED)
        .dependsOn(postgres)
        .withEnv("POSTGRES_JDBC_URL", "jdbc:postgresql://postgres:5432/" + postgres.getDatabaseName())
        .withEnv("POSTGRES_USER", postgres.getUsername())
        .withEnv("POSTGRES_PASS", postgres.getPassword());

    @Test
    void testWithSharedNetwork() {
        // Containers communicate via the "postgres" network alias;
        // @Container manages start/stop automatically.
    }
}
```

---

## Kafka

### Basic Test

```java
import org.apache.kafka.clients.consumer.ConsumerConfig;
import org.apache.kafka.clients.consumer.ConsumerRecord;
import org.apache.kafka.clients.consumer.KafkaConsumer;
import org.junit.jupiter.api.Test;
import org.testcontainers.containers.KafkaContainer;
import org.testcontainers.junit.jupiter.Container;
import org.testcontainers.junit.jupiter.Testcontainers;
import org.testcontainers.utility.DockerImageName;

import java.time.Duration;
import java.util.Collections;
import java.util.concurrent.TimeUnit;

import static org.awaitility.Awaitility.await;
import static org.junit.jupiter.api.Assertions.*;

@Testcontainers
class KafkaConsumerTest {

    @Container
    static KafkaContainer kafka = new KafkaContainer(
            DockerImageName.parse("confluentinc/cp-kafka:7.5.0"));

    @Test
    void shouldConsumeMessage() {
        // Create producer and send message
        // ...

        // Create consumer and verify message received
        var consumerProps = Map.of(
            ConsumerConfig.BOOTSTRAP_SERVERS_CONFIG, kafka.getBootstrapServers(),
            ConsumerConfig.GROUP_ID_CONFIG, "test-group",
            ConsumerConfig.AUTO_OFFSET_RESET_CONFIG, "earliest",
            ConsumerConfig.KEY_DESERIALIZER_CLASS_CONFIG, 
                "org.apache.kafka.common.serialization.StringDeserializer",
            ConsumerConfig.VALUE_DESERIALIZER_CLASS_CONFIG,
                "org.apache.kafka.common.serialization.StringDeserializer"
        );

        var consumer = new KafkaConsumer<String, String>(consumerProps);
        consumer.subscribe(Collections.singletonList("test-topic"));

        await().atMost(10, TimeUnit.SECONDS).untilAsserted(() -> {
            var records = consumer.poll(Duration.ofSeconds(1));
            assertFalse(records.isEmpty());
            ConsumerRecord<String, String> record = records.iterator().next();
            assertEquals("test-key", record.key());
            assertEquals("test-value", record.value());
        });
    }
}
```

### Kafka with the application container

Declare `KafkaContainer` next to the `AppContainer`, inject the broker via `withEnv("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092")`, then drive the application through HTTP. See the full example in [blackbox-integration-reference.md](blackbox-integration-reference.md#kafka-integration-test).

---

## Wait Strategies

### HTTP Wait

```java
import org.testcontainers.containers.GenericContainer;
import org.testcontainers.containers.wait.strategy.Wait;

new GenericContainer<>("myapp:latest")
    .waitingFor(Wait.forHttp("/system/readiness").forPort(8085).forStatusCode(200));
```

### Log Message Wait

```java
import org.testcontainers.containers.wait.strategy.Wait;

new PostgreSQLContainer<>(image)
    .waitingFor(Wait.forLogMessage(".*database system is ready.*", 1));
```

### Health Check Wait

```java
import org.testcontainers.containers.wait.strategy.Wait;

new MySQLContainer<>(image)
    .waitingFor(Wait.forHealthcheck());
```

---

## Container Reuse

### Static Container (Shared Across Tests)

```java
@Testcontainers
class SharedContainerTest {

    @Container
    static PostgreSQLContainer<?> postgres = new PostgreSQLContainer<>(
            DockerImageName.parse("postgres:15-alpine"))
        .withDatabaseName("testdb")
        .withUsername("test")
        .withPassword("test");

    // Container started once per JVM run
}
```

### Instance Container (Per-Test)

```java
@Testcontainers
class PerTestContainerTest {

    @Container
    PostgreSQLContainer<?> postgres = new PostgreSQLContainer<>(
            DockerImageName.parse("postgres:15-alpine"))
        .withDatabaseName("testdb")
        .withUsername("test")
        .withPassword("test");

    // New container for each test method
}
```

### Class-Level Container (Per-Class)

```java
@Testcontainers
@org.testcontainers.junit.jupiter.Testcontainers(discoveredTimeout = 120000)
class PerClassContainerTest {

    @Container
    static PostgreSQLContainer<?> postgres = new PostgreSQLContainer<>(
            DockerImageName.parse("postgres:15-alpine"))
        .withDatabaseName("testdb")
        .withUsername("test")
        .withPassword("test");

    // New container for each test class
}
```

---

## Best Practices

1. **Use `@Testcontainers`** — automatic container lifecycle management
2. **Static containers** — faster tests, shared across all methods
3. **Shared network** — containers communicate via aliases
4. **HTTP wait strategy** — for applications with slow startup
5. **Init scripts** — simple schema setup for tests

## Don't

- Don't create containers without the `@Container` annotation unless you also manage the lifecycle by hand
- Don't use `Wait.forListeningPort()` for the application — wait on `/system/readiness` (private port 8085) instead
- Don't create a fresh per-test network — share one with `Network.SHARED` so aliases stay stable
- Don't forget to stop manually-managed containers in `@AfterAll`

---

## Related Resources

- [Testcontainers Official Docs](https://www.testcontainers.org/)
- [Testcontainers Kafka Module](https://java.testcontainers.org/modules/kafka/)
- [Testcontainers PostgreSQL Module](https://java.testcontainers.org/modules/databases/postgres/)
- [Awaitility](http://www.awaitility.org/) — Async assertions
