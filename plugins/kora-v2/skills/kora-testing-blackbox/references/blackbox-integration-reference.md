# Black-Box Integration Testing Reference

**Purpose:** End-to-end testing of a packaged Kora application through its HTTP API.

**Source:** `.kora-agent/kora-docs/mkdocs/docs/en/guides/testing-black-box.md`; example `.kora-agent/kora-examples/guides/java/kora-java-guide-testing-black-box-app`.

## Contents

1. [Overview](#overview)
2. [Test architecture](#test-architecture)
3. [The AppContainer pattern](#the-appcontainer-pattern)
4. [Complete CRUD test (Java + HttpClient)](#complete-crud-test-java--httpclient)
5. [RestAssured variant (Kotlin)](#restassured-variant-kotlin)
6. [Kafka integration test](#kafka-integration-test)
7. [Error scenarios](#error-scenarios)
8. [Async assertions with Awaitility](#async-assertions-with-awaitility)
9. [Database verification](#database-verification)
10. [Best practices](#best-practices)

---

## Overview

Black-box testing treats the application as an external system. The test does not call services, repositories, generated graph classes (`*RepositoryImpl`, `ApplicationGraph`), or controller methods directly. It starts the packaged Docker image, sends real HTTP requests, and asserts real HTTP responses and persisted state.

Because Kora builds the dependency graph at compile time, application startup is fast enough to make black-box tests a primary source of confidence, not just a small smoke suite.

**Characteristics:**
- Runs the same artifact produced by `distTar`/`installDist` in a container
- Uses real infrastructure (PostgreSQL, Kafka) via standard Testcontainers
- Validates routing, JSON (de)serialization, validation, config loading, migrations, and probes together
- Slower than `@KoraAppTest` component tests, but the most realistic test type

---

## Test architecture

```
+-----------------------------------------------------------+
|                  Black-Box Test Class                     |
|  +-----------------------------------------------------+  |
|  |              Testcontainers (Network.SHARED)        |  |
|  |  +-------------+   +-----------------------------+   |  |
|  |  | PostgreSQL  |   |        AppContainer         |   |  |
|  |  | Container   |<--| (GenericContainer subclass) |   |  |
|  |  | alias:      |   | public 8080 / private 8085  |   |  |
|  |  | postgres    |   |                             |   |  |
|  |  +-------------+   +-----------------------------+   |  |
|  +-----------------------------------------------------+  |
|                          |                                |
|                  java.net.http.HttpClient                 |
|                          v                                |
|              HTTP requests to the public API (8080)       |
+-----------------------------------------------------------+
```

The application reads its DB connection from environment variables that Testcontainers injects via `withEnv(...)`. From the application's point of view this is ordinary environment configuration; the values just happen to come from the PostgreSQL container.

---

## The AppContainer pattern

Wrap the application image in a `GenericContainer` subclass so the test class stays focused on scenarios. The wrapper:

- builds the image from the application `Dockerfile`
- exposes the public (`8080`) and private (`8085`) ports
- waits for `/system/readiness` on the private port before tests run
- exposes helpers to build the public and private base URIs

```java
package ru.tinkoff.kora.example.blackbox;

import java.net.URI;
import java.nio.file.Path;
import java.time.Duration;
import org.slf4j.LoggerFactory;
import org.testcontainers.containers.GenericContainer;
import org.testcontainers.containers.output.Slf4jLogConsumer;
import org.testcontainers.containers.wait.strategy.Wait;
import org.testcontainers.images.builder.ImageFromDockerfile;

final class AppContainer extends GenericContainer<AppContainer> {

    AppContainer() {
        super(new ImageFromDockerfile("my-service-black-box")
                .withDockerfile(Path.of("../my-service-app/Dockerfile")));

        withExposedPorts(8080, 8085);
        withStartupTimeout(Duration.ofSeconds(30));
        waitingFor(Wait.forHttp("/system/readiness").forPort(8085).forStatusCode(200));
        withLogConsumer(new Slf4jLogConsumer(LoggerFactory.getLogger(AppContainer.class)));
    }

    URI getURI() {
        return URI.create("http://" + getHost() + ":" + getMappedPort(8080));
    }

    URI getSystemURI() {
        return URI.create("http://" + getHost() + ":" + getMappedPort(8085));
    }
}
```

`8080` is the public API port (`httpServer.publicApiHttpPort`); `8085` is the private port (`httpServer.privateApiHttpPort`) that serves `/system/readiness`, `/system/liveness`, and `/metrics`. Always wait on readiness on the private port, not on the public port.

To reuse a pre-built image in CI instead of building from the `Dockerfile`, branch on an environment variable when constructing the container (see the CI/CD section of [docker-reference.md](docker-reference.md)): when `APP_IMAGE` is set, build the container from `DockerImageName.parse(System.getenv("APP_IMAGE"))`; otherwise build from the application `Dockerfile`.

---

## Complete CRUD test (Java + HttpClient)

Containers are declared `static` and managed by `@Testcontainers`/`@Container`. `Network.SHARED` lets the application reach PostgreSQL by its network alias.

```java
package ru.tinkoff.kora.example.blackbox;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.time.Duration;
import java.util.UUID;
import org.json.JSONObject;
import org.junit.jupiter.api.Test;
import org.slf4j.LoggerFactory;
import org.testcontainers.containers.Network;
import org.testcontainers.containers.PostgreSQLContainer;
import org.testcontainers.containers.output.Slf4jLogConsumer;
import org.testcontainers.junit.jupiter.Container;
import org.testcontainers.junit.jupiter.Testcontainers;

@Testcontainers
class BlackBoxTests {

    @Container
    private static final PostgreSQLContainer<?> POSTGRES = new PostgreSQLContainer<>("postgres:16-alpine")
            .withNetwork(Network.SHARED)
            .withNetworkAliases("postgres")
            .withStartupTimeout(Duration.ofSeconds(30))
            .withLogConsumer(new Slf4jLogConsumer(LoggerFactory.getLogger(PostgreSQLContainer.class)));

    @Container
    private static final AppContainer APP = new AppContainer()
            .withNetwork(Network.SHARED)
            .dependsOn(POSTGRES)
            .withEnv("POSTGRES_JDBC_URL", "jdbc:postgresql://postgres:5432/" + POSTGRES.getDatabaseName())
            .withEnv("POSTGRES_USER", POSTGRES.getUsername())
            .withEnv("POSTGRES_PASS", POSTGRES.getPassword());

    @Test
    void createUser_ShouldCreateAndReturnUser() throws Exception {
        var response = sendJson("POST", "/users", new JSONObject()
                .put("name", "John Doe")
                .put("email", uniqueEmail("john")));

        assertEquals(201, response.statusCode());
        var body = new JSONObject(response.body());
        assertTrue(body.has("id"));
        assertEquals("John Doe", body.getString("name"));
    }

    @Test
    void getUser_NotFound_ShouldReturn404() throws Exception {
        var request = HttpRequest.newBuilder()
                .GET()
                .uri(APP.getURI().resolve("/users/999999"))
                .timeout(Duration.ofSeconds(10))
                .build();

        var response = HttpClient.newHttpClient().send(request, HttpResponse.BodyHandlers.ofString());
        assertEquals(404, response.statusCode());
    }

    private HttpResponse<String> sendJson(String method, String path, JSONObject payload) throws Exception {
        var request = HttpRequest.newBuilder()
                .uri(APP.getURI().resolve(path))
                .header("Content-Type", "application/json")
                .timeout(Duration.ofSeconds(10));

        if ("POST".equals(method)) {
            request.POST(HttpRequest.BodyPublishers.ofString(payload.toString()));
        } else if ("PUT".equals(method)) {
            request.PUT(HttpRequest.BodyPublishers.ofString(payload.toString()));
        } else {
            throw new IllegalArgumentException("Unsupported method: " + method);
        }

        return HttpClient.newHttpClient().send(request.build(), HttpResponse.BodyHandlers.ofString());
    }

    private String uniqueEmail(String prefix) {
        return prefix + "-" + UUID.randomUUID() + "@example.com";
    }
}
```

The environment variable names (`POSTGRES_JDBC_URL`, `POSTGRES_USER`, `POSTGRES_PASS`) must match the substitution keys in the application's `@ConfigSource` config (for example `url = ${POSTGRES_JDBC_URL}`). They are not magic Testcontainers names.

---

## RestAssured variant (Kotlin)

RestAssured gives a concise `given()/when()/then()` DSL. Add `testImplementation("io.rest-assured:rest-assured:5.5.0")` and expose the base URI in `@BeforeAll`.

```kotlin
package ru.tinkoff.kora.example.blackbox

import io.restassured.RestAssured
import io.restassured.RestAssured.given
import io.restassured.http.ContentType
import org.hamcrest.Matchers.equalTo
import org.hamcrest.Matchers.notNullValue
import org.junit.jupiter.api.BeforeAll
import org.junit.jupiter.api.Test
import org.testcontainers.containers.Network
import org.testcontainers.containers.PostgreSQLContainer
import org.testcontainers.junit.jupiter.Container
import org.testcontainers.junit.jupiter.Testcontainers

@Testcontainers
class UserApiTest {

    companion object {
        @Container
        @JvmStatic
        private val POSTGRES = PostgreSQLContainer("postgres:16-alpine")
            .withNetwork(Network.SHARED)
            .withNetworkAliases("postgres")

        @Container
        @JvmStatic
        private val APP = AppContainer()
            .withNetwork(Network.SHARED)
            .dependsOn(POSTGRES)
            .withEnv("POSTGRES_JDBC_URL", "jdbc:postgresql://postgres:5432/${POSTGRES.databaseName}")
            .withEnv("POSTGRES_USER", POSTGRES.username)
            .withEnv("POSTGRES_PASS", POSTGRES.password)

        @BeforeAll
        @JvmStatic
        fun setup() {
            RestAssured.baseURI = APP.getURI().toString()
        }
    }

    @Test
    fun `should create user`() {
        given()
            .contentType(ContentType.JSON)
            .body("""{"name": "Test User", "email": "test@example.com"}""")
        .`when`()
            .post("/users")
        .then()
            .statusCode(201)
            .body("id", notNullValue())
            .body("name", equalTo("Test User"))
    }

    @Test
    fun `should return 404 for non-existent user`() {
        given()
        .`when`()
            .get("/users/999999")
        .then()
            .statusCode(404)
    }
}
```

`AppContainer` here is the Kotlin equivalent of the wrapper above (`class AppContainer : GenericContainer<AppContainer>(...)`).

---

## Kafka integration test

Add `testImplementation "org.testcontainers:kafka:1.21.4"`. Start a `KafkaContainer`, inject its bootstrap servers into the application, send a record with a plain `KafkaProducer`, then assert the side effect through the HTTP API.

```java
package ru.tinkoff.kora.example.blackbox;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.awaitility.Awaitility.await;

import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.time.Duration;
import java.util.Map;
import org.apache.kafka.clients.producer.KafkaProducer;
import org.apache.kafka.clients.producer.ProducerRecord;
import org.apache.kafka.common.serialization.StringSerializer;
import org.junit.jupiter.api.Test;
import org.testcontainers.containers.KafkaContainer;
import org.testcontainers.containers.Network;
import org.testcontainers.junit.jupiter.Container;
import org.testcontainers.junit.jupiter.Testcontainers;
import org.testcontainers.utility.DockerImageName;

@Testcontainers
class KafkaEventTests {

    @Container
    private static final KafkaContainer KAFKA = new KafkaContainer(
            DockerImageName.parse("confluentinc/cp-kafka:7.5.0"))
            .withNetwork(Network.SHARED)
            .withNetworkAliases("kafka");

    @Container
    private static final AppContainer APP = new AppContainer()
            .withNetwork(Network.SHARED)
            .dependsOn(KAFKA)
            .withEnv("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092");

    @Test
    void shouldProcessKafkaEvent() throws Exception {
        try (var producer = new KafkaProducer<String, String>(Map.of(
                "bootstrap.servers", KAFKA.getBootstrapServers(),
                "key.serializer", StringSerializer.class.getName(),
                "value.serializer", StringSerializer.class.getName()))) {
            producer.send(new ProducerRecord<>("events", "user-1",
                    "{\"type\":\"USER_CREATED\",\"userId\":\"1\"}")).get();
        }

        var client = HttpClient.newHttpClient();
        var request = HttpRequest.newBuilder()
                .GET()
                .uri(APP.getURI().resolve("/events/status"))
                .timeout(Duration.ofSeconds(10))
                .build();

        await().atMost(Duration.ofSeconds(15)).untilAsserted(() -> {
            var response = client.send(request, HttpResponse.BodyHandlers.ofString());
            assertEquals(200, response.statusCode());
            assertTrue(response.body().contains("PROCESSED"));
        });
    }
}
```

The application reaches the broker via the `kafka` network alias on the internal port (`9092`); the test producer uses `getBootstrapServers()` for the host-mapped port.

---

## Error scenarios

Assert the same status codes a real client would see. These exercise the full request path: routing, `@Json` deserialization, `@Valid` validation, and the application's error mapping.

```java
@Test
void invalidBody_ShouldReturn400() throws Exception {
    var request = HttpRequest.newBuilder()
            .POST(HttpRequest.BodyPublishers.ofString("{}"))
            .uri(APP.getURI().resolve("/users"))
            .header("Content-Type", "application/json")
            .timeout(Duration.ofSeconds(10))
            .build();

    var response = HttpClient.newHttpClient().send(request, HttpResponse.BodyHandlers.ofString());
    assertEquals(400, response.statusCode());
}

@Test
void duplicateEmail_ShouldReturn409() throws Exception {
    var email = uniqueEmail("dup");
    sendJson("POST", "/users", new JSONObject().put("name", "A").put("email", email));

    var response = sendJson("POST", "/users", new JSONObject().put("name", "B").put("email", email));
    assertEquals(409, response.statusCode());
}
```

| Operation | HTTP method | Endpoint           | Typical status |
|-----------|-------------|--------------------|----------------|
| Create    | POST        | `/users`           | 201            |
| Read      | GET         | `/users/{id}`      | 200            |
| Update    | PUT/PATCH   | `/users/{id}`      | 200            |
| Delete    | DELETE      | `/users/{id}`      | 204            |
| Invalid   | POST        | `/users`           | 400            |
| Missing   | GET         | `/users/{id}`      | 404            |
| Conflict  | POST        | `/users`           | 409            |

---

## Async assertions with Awaitility

Use Awaitility (`testImplementation "org.awaitility:awaitility:4.2.2"`) when the side effect of a request is processed asynchronously (Kafka consumer, scheduled job).

```java
import static org.awaitility.Awaitility.await;

await()
    .atMost(Duration.ofSeconds(30))
    .pollInterval(Duration.ofSeconds(1))
    .untilAsserted(() -> {
        var request = HttpRequest.newBuilder()
                .GET()
                .uri(APP.getURI().resolve("/events/count"))
                .build();
        var response = HttpClient.newHttpClient().send(request, HttpResponse.BodyHandlers.ofString());
        assertEquals("1", response.body());
    });
```

---

## Database verification

Prefer verifying state through the HTTP API. When you must inspect the database directly (for example to confirm a delete actually removed the row), use JDBC against the PostgreSQL container.

```java
import java.sql.Connection;
import java.sql.DriverManager;
import java.sql.ResultSet;
import java.sql.Statement;

try (Connection conn = DriverManager.getConnection(
        POSTGRES.getJdbcUrl(), POSTGRES.getUsername(), POSTGRES.getPassword());
     Statement stmt = conn.createStatement()) {
    ResultSet rs = stmt.executeQuery("SELECT COUNT(*) FROM users");
    rs.next();
    assertEquals(0, rs.getInt(1));
}
```

Migrations run inside the application container on startup (Flyway/Liquibase). If you need explicit schema control in the test lifecycle, run Flyway from `@BeforeAll` against the same PostgreSQL container instead.

---

## Best practices

1. **Wait on `/system/readiness`** on the private port (8085), never `Wait.forListeningPort()` on the public port.
2. **Use `Network.SHARED`** and network aliases so the application can reach infrastructure by hostname.
3. **Inject config via `withEnv(...)`** matching the application's `${VAR}` substitution keys.
4. **Generate unique test data** (unique emails) so static, shared containers can run all methods without cross-test collisions.
5. **Do not modify the Kora graph from the test** — black-box runs the packaged artifact unchanged. To add test-only repositories, use `@KoraAppTest` component tests instead (`kora-testing-junit-java`).
6. **Assert only the HTTP boundary**; reach into the database only to confirm persistence.

---

## Related

- [testcontainers-reference.md](testcontainers-reference.md) — standard Testcontainers usage
- [docker-reference.md](docker-reference.md) — Dockerfile and CI/CD strategies
- [docker-compose-reference.md](docker-compose-reference.md) — multi-container Compose tests
