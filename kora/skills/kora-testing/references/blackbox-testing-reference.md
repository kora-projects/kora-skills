# Black-Box Testing Reference

**Source:** [.kora-agent/kora-docs/mkdocs/docs/en/documentation/testing.md](.kora-agent/kora-docs/mkdocs/docs/en/documentation/testing.md)  
**Examples:** `.kora-agent/kora-examples/kora-java-blackbox/`

Testing an application via the HTTP API using Testcontainers.

## Overview

**Black-box tests** are integration tests that verify the application through its external interface (HTTP API) without access to internal components.

**When to use:**
- E2E testing of user scenarios
- Verifying the integration of all system components
- API contract validation
- Testing DB migrations in action

**When not to use:**
- Fast unit tests (use Component Tests)
- Isolated logic testing (use Integration Tests)
- Tests that require access to internal components

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                  Black-Box Test                         │
│  ┌─────────────────────────────────────────────────┐    │
│  │              Testcontainers                     │    │
│  │  ┌─────────────┐  ┌─────────────────────────┐  │    │
│  │  │ PostgreSQL  │  │    AppContainer         │  │    │
│  │  │ Container   │  │  (HTTP Server)          │  │    │
│  │  │ + Flyway    │  │  Port: 8080             │  │    │
│  │  └─────────────┘  └─────────────────────────┘  │    │
│  └─────────────────────────────────────────────────┘    │
│                          │                               │
│                    HttpClient                            │
│                          ↓                               │
│              HTTP Requests (REST API)                    │
└─────────────────────────────────────────────────────────┘
```

---

## Dependencies

```groovy
dependencies {
    // Testcontainers Extensions
    testImplementation "io.goodforgod:testcontainers-extensions-postgres:0.13.0"
    testImplementation "io.goodforgod:testcontainers-extensions-jdbc:0.13.0"

    // Kora Test
    testImplementation "ru.tinkoff.kora:testing:1.14.0"

    // HTTP Client (Java 11+)
    // built into the JDK

    // JSON Assertions
    testImplementation "org.skyscreamer:jsonassert:1.5.1"
    testImplementation "org.json:json:20231013"

    // Testcontainers
    testImplementation "org.testcontainers:postgresql:1.21.3"
    testImplementation "org.testcontainers:junit-jupiter:1.21.3"

    // PostgreSQL Driver
    runtimeOnly "org.postgresql:postgresql:42.7.3"
}
```

---

## Kotlin: Black-Box Test

### Basic template

```kotlin
package ru.tinkoff.kora.example

import io.goodforgod.testcontainers.extensions.ContainerMode
import io.goodforgod.testcontainers.extensions.Network
import io.goodforgod.testcontainers.extensions.jdbc.*
import org.junit.jupiter.api.AfterAll
import org.junit.jupiter.api.BeforeAll
import org.junit.jupiter.api.Test
import java.net.http.HttpClient
import java.net.http.HttpRequest
import java.net.http.HttpResponse
import java.time.Duration
import org.json.JSONObject

@TestcontainersPostgreSQL(
    network = @Network(shared = true),
    mode = ContainerMode.PER_RUN,
    migration = @Migration(
        engine = Migration.Engines.FLYWAY,
        apply = Migration.Mode.PER_METHOD,
        drop = Migration.Mode.PER_METHOD
    )
)
class ResourceApiTest {

    companion object {
        private val container = AppContainer.build()
            .withNetwork(org.testcontainers.containers.Network.SHARED)

        @JvmStatic
        @BeforeAll
        fun setup(@ConnectionPostgreSQL connection: JdbcConnection) {
            val params = connection.paramsInNetwork().orElseThrow()
            container.withEnv(
                mapOf(
                    "DB_JDBC_URL" to params.jdbcUrl(),
                    "DB_USER" to params.username(),
                    "DB_PASS" to params.password()
                )
            )
            container.start()
        }

        @JvmStatic
        @AfterAll
        fun cleanup() {
            container.stop()
        }
    }

    @ConnectionPostgreSQL
    private lateinit var connection: JdbcConnection

    private val httpClient = HttpClient.newHttpClient()
    private val baseUrl get() = container.uri

    @Test
    fun `should create resource`() {
        // given
        val requestBody = JSONObject().put("name", "test-resource")

        // when
        val request = HttpRequest.newBuilder()
            .POST(HttpRequest.BodyPublishers.ofString(requestBody.toString()))
            .uri(baseUrl.resolve("/api/resources"))
            .timeout(Duration.ofSeconds(5))
            .build()

        val response = httpClient.send(request, HttpResponse.BodyHandlers.ofString())

        // then
        org.junit.jupiter.api.Assertions.assertEquals(200, response.statusCode())
        val responseBody = JSONObject(response.body())
        org.junit.jupiter.api.Assertions.assertNotNull(responseBody.get("id"))
        org.junit.jupiter.api.Assertions.assertEquals("test-resource", responseBody.get("name"))
    }

    @Test
    fun `should get resource by id`() {
        // given: create resource
        val createResponse = httpClient.send(
            HttpRequest.newBuilder()
                .POST(HttpRequest.BodyPublishers.ofString("{\"name\":\"test\"}"))
                .uri(baseUrl.resolve("/api/resources"))
                .timeout(Duration.ofSeconds(5))
                .build(),
            HttpResponse.BodyHandlers.ofString()
        )
        val resourceId = JSONObject(createResponse.body()).get("id")

        // when: get resource
        val getRequest = HttpRequest.newBuilder()
            .GET()
            .uri(baseUrl.resolve("/api/resources/$resourceId"))
            .timeout(Duration.ofSeconds(5))
            .build()

        val getResponse = httpClient.send(getRequest, HttpResponse.BodyHandlers.ofString())

        // then
        org.junit.jupiter.api.Assertions.assertEquals(200, getResponse.statusCode())
        val responseBody = JSONObject(getResponse.body())
        org.junit.jupiter.api.Assertions.assertEquals("test", responseBody.get("name"))
    }

    @Test
    fun `should delete resource`() {
        // given: create resource
        val createResponse = httpClient.send(
            HttpRequest.newBuilder()
                .POST(HttpRequest.BodyPublishers.ofString("{\"name\":\"test\"}"))
                .uri(baseUrl.resolve("/api/resources"))
                .timeout(Duration.ofSeconds(5))
                .build(),
            HttpResponse.BodyHandlers.ofString()
        )
        val resourceId = JSONObject(createResponse.body()).get("id")

        // when: delete resource
        val deleteRequest = HttpRequest.newBuilder()
            .DELETE()
            .uri(baseUrl.resolve("/api/resources/$resourceId"))
            .timeout(Duration.ofSeconds(5))
            .build()

        val deleteResponse = httpClient.send(deleteRequest, HttpResponse.BodyHandlers.ofString())

        // then
        org.junit.jupiter.api.Assertions.assertEquals(200, deleteResponse.statusCode())
        
        // and: verify in database
        connection.assertCountsEquals(0, "resources")
    }
}
```

---

## Java: Black-Box Test

### Basic template

```java
package ru.tinkoff.kora.example;

import static org.junit.jupiter.api.Assertions.*;

import io.goodforgod.testcontainers.extensions.ContainerMode;
import io.goodforgod.testcontainers.extensions.Network;
import io.goodforgod.testcontainers.extensions.jdbc.*;
import java.net.http.*;
import java.time.Duration;
import java.util.Map;
import org.json.JSONObject;
import org.junit.jupiter.api.AfterAll;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.Test;

@TestcontainersPostgreSQL(
    network = @Network(shared = true),
    mode = ContainerMode.PER_RUN,
    migration = @Migration(
        engine = Migration.Engines.FLYWAY,
        apply = Migration.Mode.PER_METHOD,
        drop = Migration.Mode.PER_METHOD
    )
)
class ResourceApiTest {

    private static final AppContainer container = AppContainer.build()
        .withNetwork(org.testcontainers.containers.Network.SHARED);

    @ConnectionPostgreSQL
    private JdbcConnection connection;

    private final HttpClient httpClient = HttpClient.newHttpClient();

    @BeforeAll
    static void setup(@ConnectionPostgreSQL JdbcConnection connection) {
        var params = connection.paramsInNetwork().orElseThrow();
        container.withEnv(Map.of(
            "DB_JDBC_URL", params.jdbcUrl(),
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
        // given
        var requestBody = new JSONObject()
            .put("name", "test-resource");

        // when
        var request = HttpRequest.newBuilder()
            .POST(HttpRequest.BodyPublishers.ofString(requestBody.toString()))
            .uri(container.getURI().resolve("/api/resources"))
            .timeout(Duration.ofSeconds(5))
            .build();

        var response = httpClient.send(request, HttpResponse.BodyHandlers.ofString());

        // then
        assertEquals(200, response.statusCode());
        var responseBody = new JSONObject(response.body());
        assertNotNull(responseBody.get("id"));
        assertEquals("test-resource", responseBody.get("name"));
    }

    @Test
    void shouldGetResourceById() throws Exception {
        // given: create resource
        var createRequest = HttpRequest.newBuilder()
            .POST(HttpRequest.BodyPublishers.ofString("{\"name\":\"test\"}"))
            .uri(container.getURI().resolve("/api/resources"))
            .timeout(Duration.ofSeconds(5))
            .build();
        var createResponse = httpClient.send(createRequest, HttpResponse.BodyHandlers.ofString());
        var resourceId = createResponse.body();

        // when: get resource
        var getRequest = HttpRequest.newBuilder()
            .GET()
            .uri(container.getURI().resolve("/api/resources/" + resourceId))
            .timeout(Duration.ofSeconds(5))
            .build();

        var getResponse = httpClient.send(getRequest, HttpResponse.BodyHandlers.ofString());

        // then
        assertEquals(200, getResponse.statusCode());
    }

    @Test
    void shouldDeleteResource() throws Exception {
        // given: create resource
        var createRequest = HttpRequest.newBuilder()
            .POST(HttpRequest.BodyPublishers.ofString("{\"name\":\"test\"}"))
            .uri(container.getURI().resolve("/api/resources"))
            .timeout(Duration.ofSeconds(5))
            .build();
        var createResponse = httpClient.send(createRequest, HttpResponse.BodyHandlers.ofString());
        var resourceId = new JSONObject(createResponse.body()).get("id");

        // when: delete resource
        var deleteRequest = HttpRequest.newBuilder()
            .DELETE()
            .uri(container.getURI().resolve("/api/resources/" + resourceId))
            .timeout(Duration.ofSeconds(5))
            .build();

        var deleteResponse = httpClient.send(deleteRequest, HttpResponse.BodyHandlers.ofString());

        // then
        assertEquals(200, deleteResponse.statusCode());
        
        // and: verify in database
        connection.assertCountsEquals(0, "resources");
    }
}
```

---

## Advanced Patterns

### JSON Assert with JSONAssert

```kotlin
import org.skyscreamer.jsonassert.JSONAssert
import org.skyscreamer.jsonassert.JSONCompareMode

@Test
fun `should return resource with expected structure`() {
    // when
    val response = httpClient.send(
        HttpRequest.newBuilder()
            .GET()
            .uri(baseUrl.resolve("/api/resources/1"))
            .build(),
        HttpResponse.BodyHandlers.ofString()
    )

    // then
    val expected = """
        {
            "id": "1",
            "name": "test",
            "createdAt": "${'$'}{json-unit.any-string}"
        }
    """.trimIndent()
    
    JSONAssert.assertEquals(expected, response.body(), JSONCompareMode.LENIENT)
}
```

### Error testing

```kotlin
@Test
fun `should return 404 for non-existent resource`() {
    // when
    val response = httpClient.send(
        HttpRequest.newBuilder()
            .GET()
            .uri(baseUrl.resolve("/api/resources/non-existent"))
            .build(),
        HttpResponse.BodyHandlers.ofString()
    )

    // then
    org.junit.jupiter.api.Assertions.assertEquals(404, response.statusCode())
}

@Test
fun `should return 400 for invalid input`() {
    // when
    val response = httpClient.send(
        HttpRequest.newBuilder()
            .POST(HttpRequest.BodyPublishers.ofString("{\"invalid\":\"data\"}"))
            .uri(baseUrl.resolve("/api/resources"))
            .header("Content-Type", "application/json")
            .build(),
        HttpResponse.BodyHandlers.ofString()
    )

    // then
    org.junit.jupiter.api.Assertions.assertEquals(400, response.statusCode())
}
```

### Testing with authorization

```kotlin
@Test
fun `should require authentication`() {
    // when
    val response = httpClient.send(
        HttpRequest.newBuilder()
            .GET()
            .uri(baseUrl.resolve("/api/protected"))
            .build(),
        HttpResponse.BodyHandlers.ofString()
    )

    // then
    org.junit.jupiter.api.Assertions.assertEquals(401, response.statusCode())
}

@Test
fun `should accept valid token`() {
    // given
    val token = getValidAuthToken()

    // when
    val response = httpClient.send(
        HttpRequest.newBuilder()
            .GET()
            .uri(baseUrl.resolve("/api/protected"))
            .header("Authorization", "Bearer $token")
            .build(),
        HttpResponse.BodyHandlers.ofString()
    )

    // then
    org.junit.jupiter.api.Assertions.assertEquals(200, response.statusCode())
}
```

### Parameterized tests

```kotlin
@ParameterizedTest
@ValueSource(strings = ["/api/resources", "/api/users", "/api/orders"])
fun `should return 200 for valid endpoints`(endpoint: String) {
    // when
    val response = httpClient.send(
        HttpRequest.newBuilder()
            .GET()
            .uri(baseUrl.resolve(endpoint))
            .build(),
        HttpResponse.BodyHandlers.ofString()
    )

    // then
    org.junit.jupiter.api.Assertions.assertEquals(200, response.statusCode())
}
```

---

## AppContainer for Kotlin

```kotlin
object AppContainer {
    private var instance: GenericContainer<*>? = null

    fun build(): GenericContainer<*> {
        if (instance == null) {
            instance = GenericContainer("myapp:latest")
                .withExposedPorts(8080)
                .waitingFor(Wait.forHttp("/health").forPort(8080))
        }
        return instance!!
    }
}

// Extension property for retrieving the URI
val GenericContainer<*>.uri: URI
    get() = URI.create("http://${container.host}:${container.getMappedPort(8080)}")
```

---

## Best Practices

### 1. Shared Network

Use `@Network(shared = true)` to connect the database and the application to the same network:

```kotlin
@TestcontainersPostgreSQL(
    network = @Network(shared = true),
    mode = ContainerMode.PER_RUN
)
```

### 2. Migrations with cleanup

Always use `drop = Migration.Mode.PER_METHOD` for test isolation:

```kotlin
migration = @Migration(
    engine = Migration.Engines.FLYWAY,
    apply = Migration.Mode.PER_METHOD,
    drop = Migration.Mode.PER_METHOD
)
```

### 3. Verification in the DB

Use `connection` to validate data in the database:

```kotlin
// After DELETE
connection.assertCountsEquals(0, "resources")

// After INSERT
val count = connection.queryOne("SELECT COUNT(*) FROM resources") { 
    it.getInt(1) 
}
assertEquals(1, count)
```

### 4. Timeouts

Always set timeouts for HTTP requests:

```kotlin
.timeout(Duration.ofSeconds(5))
```

### 5. Reusing HttpClient

Create `HttpClient` once per test class:

```kotlin
private val httpClient = HttpClient.newHttpClient()
```

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| Container does not start | Check Docker: `docker ps` |
| Port already in use | Use `mode = PER_METHOD` for isolation |
| Migrations are not applied | Check path: `locations = {"db/migration"}` |
| HTTP timeout | Increase `.timeout(Duration.ofSeconds(10))` |
| Shared Network does not work | Make sure both containers are on the same network |

---

## Comparison with other test types

| Type | Component access | Speed | Realism |
|------|-----------------|-------|---------|
| **Component Test** | `@TestComponent` | Fast | Low |
| **Integration Test** | `@KoraAppTest` | Medium | Medium |
| **Black-Box Test** | HTTP API | Slow | High |

---

## Resources

- [Testcontainers Extensions](https://github.com/GoodforGod/testcontainers-extensions)
- [Kora Testing](https://kora-projects.github.io/kora-docs/en/documentation/testing.html)
- [Java HttpClient](https://docs.oracle.com/en/java/javase/17/docs/api/java.net.http/java/net/http/HttpClient.html)
- [JSONAssert](https://github.com/skyscreamer/JSONassert)
