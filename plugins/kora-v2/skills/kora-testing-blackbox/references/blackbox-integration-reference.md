# Black-Box Integration Testing Reference

**Purpose:** End-to-end testing of a packaged Kora 2.0 application through its HTTP API.

Everything here is written against Kora **2.0** (`io.koraframework`, BOM `io.koraframework:kora-bom`
at `2.0.0.RC2`), JDK 25, JUnit 6.1.3 and Testcontainers 1.21.4. See
[SKILL.md](../SKILL.md) for the port model and the dependency block.

## Contents

1. [Overview](#overview)
2. [Test architecture](#test-architecture)
3. [The AppContainer pattern](#the-appcontainer-pattern)
4. [Complete CRUD test (Java + HttpClient)](#complete-crud-test-java--httpclient)
5. [Kotlin variant](#kotlin-variant)
6. [RestAssured variant](#restassured-variant)
7. [Probe and metrics assertions](#probe-and-metrics-assertions)
8. [Kafka integration test](#kafka-integration-test)
9. [Error scenarios](#error-scenarios)
10. [Async assertions with Awaitility](#async-assertions-with-awaitility)
11. [Database verification](#database-verification)
12. [Native-image acceptance](#native-image-acceptance)
13. [Best practices](#best-practices)

---

## Overview

Black-box testing treats the application as an external system. The test does not call services,
repositories, generated graph classes (`ApplicationGraph`, generated repository implementations) or
controller methods directly. It starts the packaged Docker image, sends real HTTP requests, and
asserts real HTTP responses and persisted state.

Because Kora builds the dependency graph at compile time, application startup is fast enough to
make black-box tests a primary source of confidence, not just a small smoke suite.

**Characteristics:**
- Runs the same artifact `distTar` produced (or a GraalVM native binary) in a container
- Uses real infrastructure (PostgreSQL, Kafka) via Testcontainers
- Validates routing, JSON (de)serialization, validation, config key names, migrations, probes and
  reachability metadata together
- Slower than in-process `@KoraAppTest` component tests, and the only test type that can catch a
  packaging, config-key or native-metadata defect

Kora 2.0 contracts are **synchronous** — reactive and `suspend` controller signatures were removed,
and there is no `Context` type in the framework — so every response the test reads is fully
materialised by the time the handler returns.

---

## Test architecture

```
+-----------------------------------------------------------+
|                  Black-Box Test Class                     |
|  +-----------------------------------------------------+  |
|  |              Testcontainers (Network.SHARED)        |  |
|  |  +-------------+   +-----------------------------+  |  |
|  |  | PostgreSQL  |   |        AppContainer         |  |  |
|  |  | container   |<--| (GenericContainer subclass) |  |  |
|  |  | alias:      |   | 8080 public / 8085 system   |  |  |
|  |  | postgres    |   |                             |  |  |
|  |  +-------------+   +-----------------------------+  |  |
|  +-----------------------------------------------------+  |
|            |                              |               |
|   java.net.http.HttpClient        readiness probe         |
|            v                              v               |
|   public API on 8080          /system/readiness on 8085   |
+-----------------------------------------------------------+
```

The application reads its connection settings from environment variables that Testcontainers
injects with `withEnv(...)`. From the application's point of view this is ordinary environment
configuration; the values just happen to come from a sibling container.

---

## The AppContainer pattern

`AppContainer` is a class you write — Kora ships no Testcontainers integration. It:

- builds the image from the application `Dockerfile` (or reuses a prebuilt one in CI)
- exposes the public (`8080`) and system (`8085`) ports
- gates startup on `/system/readiness` on the **system** port
- exposes helpers for the public and system base URIs

```java
package com.example.blackbox;

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

### Why 8085, and why not a log line

`/system/readiness`, `/system/liveness` and `/metrics` are served by the **system** HTTP server,
whose config lives under `httpServer.system` and whose default port is `8085` —
`SystemHttpServerConfig` overrides `port()` rather than inheriting the public `8080`. Waiting on
`8080` gates on the public API instead, which starts independently of graph readiness.

`Wait.forLogMessage(...)` is the wrong gate for a Kora application at any version: the wording of
the startup messages is not part of the framework's contract and changed between 1.x and 2.0.
`Wait.forListeningPort()` is equally wrong — the socket binds before the graph finishes
initialising.

What readiness actually means: the handler resolves every registered `ReadinessProbe` promise. It
answers `503 Probe is not ready yet` while a promise is unresolved, `503 <message>` when a probe
fails, `408 Probe failed: timeout` after 30 s, and `200 OK` once all probes pass. An application
with **no** probes registered answers `200 OK` as soon as the system server is up.

In an HTTP application that degenerate case does not apply: `UndertowHttpServer implements
HttpServer, ReadinessProbe` and reports a failure until it reaches its `RUN` state, so a 200 does
mean the graph built and the public listener is accepting connections. What it still does not prove
is that PostgreSQL or Kafka is reachable — that holds only for components that register a probe of
their own. Assert those with a real request, not with the probe.

### Reusing a prebuilt image in CI

```java
static AppContainer build() {
    var appImage = System.getenv("APP_IMAGE");
    return (appImage != null && !appImage.isBlank())
            ? new AppContainer(DockerImageName.parse(appImage))
            : new AppContainer();
}
```

Keep the ports and the readiness gate identical in both branches. See the CI/CD section of
[docker-reference.md](docker-reference.md).

---

## Complete CRUD test (Java + HttpClient)

Containers are `static` and managed by `@Testcontainers` / `@Container`. `Network.SHARED` lets the
application resolve PostgreSQL by its network alias.

```java
package com.example.blackbox;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.time.Duration;
import java.util.UUID;
import org.json.JSONArray;
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
    void getUsers_WithPagination_ShouldReturnSizedResult() throws Exception {
        sendJson("POST", "/users", new JSONObject().put("name", "Alice").put("email", uniqueEmail("alice")));
        sendJson("POST", "/users", new JSONObject().put("name", "Bob").put("email", uniqueEmail("bob")));

        var request = HttpRequest.newBuilder()
                .GET()
                .uri(APP.getURI().resolve("/users?page=0&size=2&sort=name"))
                .timeout(Duration.ofSeconds(10))
                .build();
        var response = HttpClient.newHttpClient().send(request, HttpResponse.BodyHandlers.ofString());

        assertEquals(200, response.statusCode());
        assertEquals(2, new JSONArray(response.body()).length());
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

The environment variable names (`POSTGRES_JDBC_URL`, `POSTGRES_USER`, `POSTGRES_PASS`) must match
the substitution keys in the application's config. In Kora 2.0 the JDBC section is `jdbc`, not the
1.x `db`:

```hocon
jdbc {
  jdbcUrl = ${?POSTGRES_JDBC_URL}
  username = ${?POSTGRES_USER}
  password = ${?POSTGRES_PASS}
  maxPoolSize = 10
}
```

A leftover `db { ... }` section fails inside the container with
`ConfigValueException: Config expected value, but got null at path: 'ROOT.jdbc.username'`, which in
the test looks like a container that starts and immediately dies.

---

## Kotlin variant

Kotlin needs the containers in a `companion object` with `@JvmStatic` so the JUnit extension can see
them as static fields.

```kotlin
package com.example.blackbox

import org.testcontainers.containers.GenericContainer
import org.testcontainers.containers.wait.strategy.Wait
import org.testcontainers.images.builder.ImageFromDockerfile
import java.net.URI
import java.nio.file.Path
import java.time.Duration

class AppContainer : GenericContainer<AppContainer>(
    ImageFromDockerfile("my-service-black-box")
        .withDockerfile(Path.of("../my-service-app/Dockerfile"))
) {

    init {
        withExposedPorts(8080, 8085)
        withStartupTimeout(Duration.ofSeconds(30))
        waitingFor(Wait.forHttp("/system/readiness").forPort(8085).forStatusCode(200))
    }

    fun getURI(): URI = URI.create("http://$host:${getMappedPort(8080)}")

    fun getSystemURI(): URI = URI.create("http://$host:${getMappedPort(8085)}")
}
```

```kotlin
@Testcontainers
class BlackBoxTests {

    @Test
    fun createUserShouldReturn201() {
        val request = HttpRequest.newBuilder()
            .POST(HttpRequest.BodyPublishers.ofString(JSONObject().put("name", "John Doe").toString()))
            .uri(APP.getURI().resolve("/users"))
            .header("Content-Type", "application/json")
            .timeout(Duration.ofSeconds(10))
            .build()

        val response = HttpClient.newHttpClient().send(request, HttpResponse.BodyHandlers.ofString())
        assertEquals(201, response.statusCode())
    }

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
    }
}
```

The Kotlin module uses `ksp("io.koraframework:symbol-processors")` in place of the Java annotation
processor; the black-box test module itself needs neither, since nothing in it is Kora-generated.

---

## RestAssured variant

RestAssured gives a concise `given()/when()/then()` DSL. Add
`testImplementation "io.rest-assured:rest-assured:5.5.0"` and set the base URI once the container
has started.

```kotlin
package com.example.blackbox

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
}
```

`RestAssured.baseURI` must be assigned **after** the container starts, because `getMappedPort` is
only meaningful then — `@BeforeAll` runs after the `@Container` fields are started.

---

## Probe and metrics assertions

The system server is worth asserting on directly: it is the one surface that tells you the graph
came up whole.

```java
@Test
void systemProbes_ShouldBeHealthy() throws Exception {
    assertEquals(200, get(APP.getSystemURI().resolve("/system/liveness")).statusCode());
    assertEquals(200, get(APP.getSystemURI().resolve("/system/readiness")).statusCode());
}
```

`/metrics` needs more care. **A 200 is not evidence that metrics work.** When no `MetricsScraper`
is present in the graph the handler still answers 200, with the body `# Metric Scraper disabled`.
And component metrics are **off by default** in Kora 2.0 — `telemetry.metrics.enabled` defaults to
`false` per component.

Make the assertion meaningful by (1) putting `io.koraframework:micrometer-module` on the
application's runtime classpath and (2) enabling metrics in the container's config:

```hocon
httpServer {
  port = 8080
  system.port = 8085
  telemetry.metrics.enabled = true
}
```

```java
@Test
void metrics_ShouldExposeRealSeries() throws Exception {
    // drive at least one request so the HTTP server timer has a sample
    get(APP.getURI().resolve("/users/999999"));

    var response = get(APP.getSystemURI().resolve("/metrics"));

    assertEquals(200, response.statusCode());
    assertFalse(response.body().contains("Metric Scraper disabled"));
    assertTrue(response.body().contains("kora_up"));                        // registry is live
    assertTrue(response.body().contains("http_server_request_duration"));   // component metrics on
}
```

`micrometer-module` binds the JVM meters (class loader, memory, GC, threads, file descriptors,
processor, uptime) plus a `kora.up` gauge at graph init, which is why `kora_up` is a safe signal
that the registry itself is alive. `http.server.request.duration` and `http.server.active_requests`
are the HTTP server's own meters and appear only once `telemetry.metrics.enabled = true`.

Tracing behaves differently under `httpServer.system`: it is overridden to `false` there, so probe
and scrape traffic is not traced even though tracing defaults to `true` elsewhere.

---

## Kafka integration test

The migrated Kora 2.0 examples drive Kafka black-box tests through
`io.goodforgod:testcontainers-extensions-kafka:0.15.0` rather than the raw Testcontainers Kafka
module. That extension provisions the broker, declares topics, and hands the test a
`KafkaConnection` with both a host-facing and an in-network view of the bootstrap servers.

```groovy
testImplementation "io.goodforgod:testcontainers-extensions-kafka:0.15.0"
testImplementation "org.testcontainers:junit-jupiter:1.21.4"
```

```java
@TestcontainersKafka(
        network = @Network(shared = true),
        mode = ContainerMode.PER_RUN,
        topics = @Topics({ "tasks", "users" }))
class KafkaBlackBoxTests {

    private static final AppContainer CONTAINER = AppContainer.build()
            .withNetwork(org.testcontainers.containers.Network.SHARED);

    @ConnectionKafka
    private KafkaConnection connection;

    @BeforeAll
    static void setup(@ConnectionKafka KafkaConnection connection) {
        var params = connection.paramsInNetwork().orElseThrow();
        CONTAINER.withEnv(Map.of(
                // the broker advertises :9092 to the host and its in-network listener on :9093,
                // so a sibling container must bootstrap on the latter - otherwise it connects and
                // then receives metadata pointing back at localhost
                "KAFKA_BOOTSTRAP", params.bootstrapServers().replace(":9092", ":9093")));
        CONTAINER.start();
    }

    @Test
    void userEventReceivedAndTaskEventSent() {
        var consumerTask = connection.subscribe("tasks");
        connection.send("users", Event.ofValueAndRandomKey(
                new JSONObject().put("id", UUID.randomUUID().toString()).put("name", "Ivan")));

        consumerTask.assertReceivedEqualsInTime(1, Duration.ofSeconds(20));
    }
}
```

The application side reads the broker address through a substitution:

```yaml
kafka:
  listener:
    user:
      topics: "users"
      driverProperties:
        bootstrap.servers: ${KAFKA_BOOTSTRAP}
        group.id: "users-gi"
        auto.offset.reset: "earliest"
      telemetry.logging.enabled: true
  publisher:
    task:
      topic: "tasks"
      driverProperties:
        bootstrap.servers: ${KAFKA_BOOTSTRAP}
```

**The listener trap is the whole problem**, whichever container library you pick. A Kafka broker
advertises different addresses to different networks. The address the *test JVM* uses (host,
mapped port) is not the address the *application container* must use (network alias, in-network
listener port). Handing the host-facing bootstrap string to the application produces the worst
failure shape available: the initial connection succeeds, the broker returns metadata pointing at
`localhost`, and the consumer then silently never receives anything until the test times out.

> The migrated corpus does not use `org.testcontainers`' own Kafka container classes anywhere, so
> this skill cannot vouch for a particular class name or image there. If you prefer the raw module,
> check the container class, the image and the advertised-listener behaviour against the exact
> Testcontainers version you declare — those changed across the 1.x line and again in 2.x.

To assert a side effect through HTTP rather than through a consumer, see
[Async assertions with Awaitility](#async-assertions-with-awaitility).

---

## Error scenarios

Assert the status codes a real client would see. These exercise the full request path: routing,
`@Json` deserialization, `@Valid` validation, and the application's error mapping.

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

Kora's `ValidationModule` maps a `ViolationException` to 400 through
`ViolationExceptionHttpServerResponseMapper`; a black-box test is where you confirm that mapping is
actually wired in the shipped artifact rather than only in a unit test.

---

## Async assertions with Awaitility

Use Awaitility (`testImplementation "org.awaitility:awaitility:4.3.0"`, the version in Kora's own
catalog) when the side effect of a
request is processed asynchronously (Kafka consumer, scheduled job).

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

Do not substitute `Thread.sleep` for this. A fixed sleep either flakes on a loaded CI machine or
wastes the time it did not need.

---

## Database verification

Prefer verifying state through the HTTP API. When you must inspect the database directly (for
example to confirm a delete actually removed the row), use JDBC against the PostgreSQL container.

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

`POSTGRES.getJdbcUrl()` is the **host-facing** URL with the mapped port — correct for the test JVM,
wrong for the application container, which must be given `jdbc:postgresql://postgres:5432/...` over
the shared network. Mixing them up is the most common reason a black-box test "cannot connect".

Migrations run inside the application container on startup (`database-flyway` or
`database-liquibase`). Note that `database-flyway` ships `flyway-core` only — the application must
add its own dialect artifact (for PostgreSQL, `org.flywaydb:flyway-database-postgresql`), otherwise
the container dies at startup with `Unsupported Database: PostgreSQL` and the readiness wait simply
times out.

---

## Native-image acceptance

For a GraalVM native module, **a green `nativeCompile` is not evidence of anything** — missing or
misnamed reachability metadata compiles cleanly and fails only at runtime. A black-box test that
builds the native `Dockerfile` and runs the binary is the cheapest way to pin the five checks that
do count:

1. the binary starts and survives;
2. `GET /system/readiness` → 200 — the graph initialised in full;
3. `GET /metrics` returns real series, not the `# Metric Scraper disabled` stub and not a 500;
4. the module's scenario runs against a real dependency, not mocks;
5. no stack traces in the startup log.

Point 5 is the one a test cannot fully automate, and the one that matters most: a subsystem that
dropped out of the image often leaves nothing behind but a stack trace on an otherwise successful
startup. Attach the container output to the build log so it is visible in CI:

```java
withLogConsumer(new Slf4jLogConsumer(LoggerFactory.getLogger(AppContainer.class)));
```

and read it after a native run rather than trusting a green suite.

Give a native container more headroom than a JVM one — the migrated native examples allow 50–60
seconds of startup timeout, against 30 for the JVM image. The native `Dockerfile` is in
[docker-reference.md](docker-reference.md#graalvm-native-image-dockerfile).

---

## Best practices

1. **Wait on `/system/readiness` on port 8085** — never `forListeningPort()`, never
   `Wait.forLogMessage`, never the public port.
2. **Expose both ports** (`withExposedPorts(8080, 8085)`) or the wait strategy has nothing to map.
3. **Use `Network.SHARED`** with network aliases so the application resolves infrastructure by
   hostname on its container port, while the test uses `getMappedPort(...)`.
4. **Inject config via `withEnv(...)`** matching the application's `${VAR}` substitution keys, and
   confirm the keys themselves are 2.0 names (`httpServer.port`, `httpServer.system.port`, `jdbc`).
5. **Generate unique test data** so a shared static container can run every method without
   cross-test collisions.
6. **Do not modify the Kora graph from the test** — black-box runs the packaged artifact unchanged.
   To replace a collaborator, write an in-process test instead (`kora-testing-junit-java`).
7. **Assert at the HTTP boundary**; reach into the database only to confirm persistence.
8. **Assert on metrics content, not on the status code**, and enable metrics before doing so.

---

## Related

- [testcontainers-reference.md](testcontainers-reference.md) — Testcontainers coordinates and API
- [docker-reference.md](docker-reference.md) — Dockerfile and CI/CD strategies
- [docker-compose-reference.md](docker-compose-reference.md) — Compose as a local/CI environment
