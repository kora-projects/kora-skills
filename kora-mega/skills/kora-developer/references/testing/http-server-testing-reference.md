# HTTP Server Testing Reference

**Source:** [.kora-agent/kora-docs/mkdocs/docs/en/documentation/http-server.md](.kora-agent/kora-docs/mkdocs/docs/en/documentation/http-server.md)  
**Examples:** `.kora-agent/kora-examples/kora-java-http-server/`

Testing the Kora HTTP server using **RestAssured** for concise API tests with BDD syntax.

## Overview

**RestAssured** is a Java DSL for testing REST APIs with BDD syntax (given/when/then), built-in JSON assertions, and automatic serialization.

**When to use RestAssured:**
- Black-box HTTP API tests
- API contract testing
- E2E scenarios with JSON requests/responses
- Tests with complex JSON assertions

**When to use JDK HttpClient:**
- Minimum dependencies
- Full control over HTTP requests
- Non-standard scenarios (WebSocket, SSE)

---

## Dependencies

### RestAssured (Recommended)

```groovy
dependencies {
    // RestAssured core
    testImplementation "io.rest-assured:rest-assured:6.0.0"
    
    // JSON assertions (JsonPath)
    testImplementation "io.rest-assured:json-path:6.0.0"
    testImplementation "io.rest-assured:json-schema-validator:6.0.0"
    
    // Kotlin support (optional)
    testImplementation "io.rest-assured:kotlin-extensions:6.0.0"
    
    // AppContainer for black-box tests
    testImplementation "org.testcontainers:junit-jupiter:1.21.3"
    
    // PostgreSQL (optional, only if a DB is needed)
    // testImplementation "io.goodforgod:testcontainers-extensions-postgres:0.13.0"
}
```

### JDK HttpClient (Alternative)

```groovy
dependencies {
    // Built into JDK 11+
    
    // JSON assertions
    testImplementation "org.skyscreamer:jsonassert:1.5.1"
    testImplementation "org.json:json:20231013"
    
    // AppContainer for black-box tests
    testImplementation "org.testcontainers:junit-jupiter:1.21.3"
    
    // PostgreSQL (optional, only if a DB is needed)
    // testImplementation "io.goodforgod:testcontainers-extensions-postgres:0.13.0"
}
```

---

## Testing options

### Option 1: Without a database

For applications without a DB (cache, in-memory, external API):

```java
import org.junit.jupiter.api.AfterAll;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.Test;

import static io.rest-assured.RestAssured.given;
import static org.hamcrest.Matchers.*;

class BlackBoxTests {

    private static final AppContainer container = AppContainer.build();

    @BeforeAll
    static void setup() {
        container.start();
    }

    @AfterAll
    static void cleanup() {
        container.stop();
    }

    @Test
    void shouldGetHealth() {
        given()
            .baseUri(container.getURI().toString())
        .when()
            .get("/system/health")
        .then()
            .statusCode(200);
    }
}
```

### Option 2: With a database (PostgreSQL)

For CRUD applications with a DB use `@TestcontainersPostgreSQL`:

```java
import io.goodforgod.testcontainers.extensions.ContainerMode;
import io.goodforgod.testcontainers.extensions.Network;
import io.goodforgod.testcontainers.extensions.jdbc.*;
import org.junit.jupiter.api.AfterAll;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.Test;

import static io.rest-assured.RestAssured.given;
import static org.hamcrest.Matchers.*;

@TestcontainersPostgreSQL(
        network = @Network(shared = true),
        mode = ContainerMode.PER_RUN,
        migration = @Migration(
                engine = Migration.Engines.FLYWAY,
                apply = Migration.Mode.PER_METHOD,
                drop = Migration.Mode.PER_METHOD))
class BlackBoxTests {

    private static final AppContainer container = AppContainer.build()
            .withNetwork(org.testcontainers.containers.Network.SHARED);

    @ConnectionPostgreSQL
    private JdbcConnection connection;

    @BeforeAll
    static void setup(@ConnectionPostgreSQL JdbcConnection connection) {
        var params = connection.paramsInNetwork().orElseThrow();
        container.withEnv(java.util.Map.of(
                "DB_URL", params.jdbcUrl(),
                "DB_USER", params.username(),
                "DB_PASS", params.password(),
                "CACHE_MAX_SIZE", "0"));
        container.start();
    }

    @AfterAll
    static void cleanup() {
        container.stop();
    }

    @Test
    void shouldCreateAndGetEntity() {
        var createBody = """\n            {"name": "test", "email": "test@example.com"}\n            """;

        var entityId = given()
                .baseUri(container.getURI().toString())
                .contentType(io.restassured.http.ContentType.JSON)
                .body(createBody)
        .when()
                .post("/api/entities")
        .then()
                .statusCode(200)
                .body("id", notNullValue())
                .extract().path("id");

        // Verify in database
        connection.assertCountsEquals(1, "entities");
    }
}
```

**Dependency:**
```groovy
testImplementation "io.goodforgod:testcontainers-extensions-postgres:0.13.0"
```

---

## AppContainer

**AppContainer** is a Testcontainers container for running your Kora application in Docker for black-box testing via the HTTP API.

### Features

| Characteristic | Description |
|----------------|-------------|
| **Ports** | 8080 (API) + 8085 (system endpoints for telemetry) |
| **Health check** | `/readiness` on port 8085 |
| **System endpoints** | `/health`, `/readiness`, `/liveness`, `/metrics` on port 8085 |
| **CI/CD** | Supports `APP_IMAGE` for using a pre-built image |

### Environment variables for CI/CD

AppContainer uses the `APP_IMAGE` environment variable to load a pre-built Docker image (for example, one built in CI):

| Variable | Description | Example |
|----------|-------------|---------|
| `APP_IMAGE` | Name of the Docker image for testing | `myregistry/myapp:1.2.3` |


**How to use in CI:**

1. Build the Docker image of your application
2. Set the `APP_IMAGE` variable to the image name
3. Run the tests — AppContainer uses the specified image

If the variable is not set, AppContainer builds the image locally from `Dockerfile`.

```java
package ru.tinkoff.kora.example;

import java.net.URI;
import java.nio.file.Paths;
import java.time.Duration;
import org.slf4j.LoggerFactory;
import org.testcontainers.containers.GenericContainer;
import org.testcontainers.containers.output.Slf4jLogConsumer;
import org.testcontainers.containers.wait.strategy.Wait;
import org.testcontainers.images.builder.ImageFromDockerfile;
import org.testcontainers.utility.DockerImageName;

public final class AppContainer extends GenericContainer<AppContainer> {

    private AppContainer() {
        super(new ImageFromDockerfile("your-app-name")
                .withDockerfile(Paths.get("Dockerfile").toAbsolutePath()));
    }

    private AppContainer(DockerImageName image) {
        super(image);
    }

    public static AppContainer build() {
        String appImage = System.getenv("APP_IMAGE");
        return (appImage != null && !appImage.isBlank())
                ? new AppContainer(DockerImageName.parse(appImage))
                : new AppContainer();
    }

    @Override
    protected void configure() {
        super.configure();
        withExposedPorts(8080, 8085);  // 8080 = API, 8085 = system
        withStartupTimeout(Duration.ofSeconds(120));
        withLogConsumer(new Slf4jLogConsumer(LoggerFactory.getLogger(getClass())));
        waitingFor(Wait.forHttp("/readiness")
                .forPort(8085)  // readiness check on system port
                .forStatusCode(200));
    }

    public int getPort() {
        return getMappedPort(8080);  // Main API
    }

    public int getSystemPort() {
        return getMappedPort(8085);  // System endpoints
    }

    public URI getURI() {
        return URI.create(String.format("http://%s:%s", getHost(), getPort()));
    }

    public URI getSystemURI() {
        return URI.create(String.format("http://%s:%s", getHost(), getSystemPort()));
    }
}
```

### Example usage in tests

```java
import org.testcontainers.junit.jupiter.Container;
import org.testcontainers.junit.jupiter.Testcontainers;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.time.Duration;

@Testcontainers
class BlackBoxTests {

    @Container
    private static final AppContainer container = AppContainer.build();

    @Test
    void shouldGetHealth() throws Exception {
        var httpClient = HttpClient.newHttpClient();
        var request = HttpRequest.newBuilder()
                .GET()
                .uri(container.getSystemURI().resolve("/health"))
                .timeout(Duration.ofSeconds(5))
                .build();
        
        var response = httpClient.send(request, HttpResponse.BodyHandlers.ofString());
        assertEquals(200, response.statusCode());
    }

    @Test
    void shouldGetMetrics() throws Exception {
        var httpClient = HttpClient.newHttpClient();
        var request = HttpRequest.newBuilder()
                .GET()
                .uri(container.getSystemURI().resolve("/metrics"))
                .timeout(Duration.ofSeconds(5))
                .build();
        
        var response = httpClient.send(request, HttpResponse.BodyHandlers.ofString());
        assertEquals(200, response.statusCode());
        assertFalse(response.body().isBlank());
    }
}
```

### Kotlin: AppContainer.kt

```kotlin
package ru.tinkoff.kora.example

import java.net.URI
import java.nio.file.Paths
import java.time.Duration
import org.slf4j.LoggerFactory
import org.testcontainers.containers.GenericContainer
import org.testcontainers.containers.output.Slf4jLogConsumer
import org.testcontainers.containers.wait.strategy.Wait
import org.testcontainers.images.builder.ImageFromDockerfile
import org.testcontainers.utility.DockerImageName

class AppContainer : GenericContainer<AppContainer> {

    private constructor() : super(
        ImageFromDockerfile("your-app-name")
            .withDockerfile(Paths.get("Dockerfile").toAbsolutePath())
    )

    private constructor(image: DockerImageName) : super(image)

    companion object {
        fun build(): AppContainer {
            val appImage = System.getenv("APP_IMAGE").takeUnless { it.isNullOrBlank() }
            
            return if (!appImage.isNullOrBlank()) {
                AppContainer(DockerImageName.parse(appImage))
            } else {
                AppContainer()
            }
        }
    }

    override fun configure() {
        super.configure()
        withExposedPorts(8080, 8085)  // 8080 = API, 8085 = system
        withStartupTimeout(Duration.ofSeconds(120))
        withLogConsumer(Slf4jLogConsumer(LoggerFactory.getLogger(javaClass)))
        waitingFor(Wait.forHttp("/readiness")
            .forPort(8085)
            .forStatusCode(200))
    }

    fun getPort(): Int = getMappedPort(8080)      // Main API
    fun getSystemPort(): Int = getMappedPort(8085) // System endpoints
    fun getURI(): URI = URI.create("http://${host}:${getPort()}")
    fun getSystemURI(): URI = URI.create("http://${host}:${getSystemPort()}")
}
```

### Example usage in tests (Kotlin)

```kotlin
import org.testcontainers.junit.jupiter.Container
import org.testcontainers.junit.jupiter.Testcontainers
import java.net.http.HttpClient
import java.net.http.HttpRequest
import java.time.Duration

@Testcontainers
class BlackBoxTests {

    companion object {
        @Container
        private val container = AppContainer.build()
    }

    @Test
    fun `should get health`() {
        val httpClient = HttpClient.newHttpClient()
        val request = HttpRequest.newBuilder()
            .GET()
            .uri(container.getSystemURI().resolve("/health"))
            .timeout(Duration.ofSeconds(5))
            .build()
        
        val response = httpClient.send(request, HttpResponse.BodyHandlers.ofString())
        assertEquals(200, response.statusCode())
    }
}
```

---

## RestAssured: Test examples

### Basic GET request

```java
import static io.restassured.RestAssured.given;
import static org.hamcrest.Matchers.*;

@Test
void shouldGetPetById() {
    given()
        .baseUri(container.getURI().toString())
        .pathParam("id", 123)
    .when()
        .get("/api/pets/{id}")
    .then()
        .statusCode(200)
        .body("id", equalTo(123))
        .body("name", notNullValue())
        .body("category.name", equalTo("Dogs"));
}
```

### POST request with JSON body

```java
import static io.restassured.RestAssured.given;
import static org.hamcrest.Matchers.*;

@Test
void shouldCreatePet() {
    var requestBody = """
        {
            "name": "doggie",
            "category": {"name": "Dogs"}
        }
        """;

    var petId = given()
        .baseUri(container.getURI().toString())
        .contentType(ContentType.JSON)
        .body(requestBody)
    .when()
        .post("/api/pets")
    .then()
        .statusCode(200)
        .body("id", notNullValue())
        .body("name", equalTo("doggie"))
        .body("category.name", equalTo("Dogs"))
        .extract()
        .path("id");

    // Use petId in subsequent tests
}
```

### PUT request with validation

```java
@Test
void shouldUpdatePet() {
    var updateBody = """
        {
            "name": "updated-doggie",
            "status": "pending"
        }
        """;

    given()
        .baseUri(container.getURI().toString())
        .pathParam("id", 123)
        .contentType(ContentType.JSON)
        .body(updateBody)
    .when()
        .put("/api/pets/{id}")
    .then()
        .statusCode(200)
        .body("id", equalTo(123))
        .body("name", equalTo("updated-doggie"))
        .body("status", equalTo("pending"));
}
```

### DELETE request

```java
@Test
void shouldDeletePet() {
    given()
        .baseUri(container.getURI().toString())
        .pathParam("id", 123)
    .when()
        .delete("/api/pets/{id}")
    .then()
        .statusCode(204);

    // Verify that the pet was deleted
    given()
        .baseUri(container.getURI().toString())
        .pathParam("id", 123)
    .when()
        .get("/api/pets/{id}")
    .then()
        .statusCode(404);
}
```

### Test with query parameters

```java
@Test
void shouldGetPetsWithPagination() {
    given()
        .baseUri(container.getURI().toString())
        .queryParam("page", 1)
        .queryParam("size", 10)
        .queryParam("sort", "name")
    .when()
        .get("/api/pets")
    .then()
        .statusCode(200)
        .body("pets", hasSize(10))
        .body("page", equalTo(1))
        .body("totalPages", greaterThan(0));
}
```

### Test with headers

```java
@Test
void shouldReturnCustomHeaders() {
    given()
        .baseUri(container.getURI().toString())
        .header("X-Request-ID", "test-123")
    .when()
        .get("/api/pets/123")
    .then()
        .statusCode(200)
        .header("X-Response-Time", notNullValue())
        .header("Content-Type", "application/json");
}
```

### JSON Schema validation

```java
import static io.restassured.module.jsv.JsonSchemaValidator.matchesJsonSchemaInClasspath;

@Test
void shouldReturnValidPetSchema() {
    given()
        .baseUri(container.getURI().toString())
        .pathParam("id", 123)
    .when()
        .get("/api/pets/{id}")
    .then()
        .statusCode(200)
        .body(matchesJsonSchemaInClasspath("pet-schema.json"));
}
```

**pet-schema.json:**
```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "required": ["id", "name"],
  "properties": {
    "id": {"type": "integer"},
    "name": {"type": "string"},
    "category": {
      "type": "object",
      "properties": {
        "id": {"type": "integer"},
        "name": {"type": "string"}
      }
    },
    "status": {
      "type": "string",
      "enum": ["available", "pending", "sold"]
    }
  }
}
```

### Test with Java object serialization

```java
import static io.restassured.RestAssured.given;

@Test
void shouldCreatePetFromObject() {
    var pet = new PetRequest("doggie", new CategoryRequest("Dogs"));

    given()
        .baseUri(container.getURI().toString())
        .contentType(ContentType.JSON)
        .body(pet)  // Automatic serialization to JSON
    .when()
        .post("/api/pets")
    .then()
        .statusCode(200)
        .body("name", equalTo("doggie"));
}
```

---

## JDK HttpClient: Test examples

### Basic GET request

```java
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;

@Test
void shouldGetPetById() throws Exception {
    var httpClient = HttpClient.newHttpClient();

    var request = HttpRequest.newBuilder()
        .GET()
        .uri(container.getURI().resolve("/api/pets/123"))
        .timeout(Duration.ofSeconds(5))
        .build();

    var response = httpClient.send(request, HttpResponse.BodyHandlers.ofString());

    assertEquals(200, response.statusCode());
    assertTrue(response.body().contains("\"id\":123"));
}
```

### POST request with JSON body

```java
import org.json.JSONObject;

@Test
void shouldCreatePet() throws Exception {
    var httpClient = HttpClient.newHttpClient();
    var requestBody = new JSONObject()
        .put("name", "doggie")
        .put("category", new JSONObject().put("name", "Dogs"));

    var request = HttpRequest.newBuilder()
        .POST(HttpRequest.BodyPublishers.ofString(requestBody.toString()))
        .uri(container.getURI().resolve("/api/pets"))
        .header("Content-Type", "application/json")
        .timeout(Duration.ofSeconds(5))
        .build();

    var response = httpClient.send(request, HttpResponse.BodyHandlers.ofString());

    assertEquals(200, response.statusCode());
    var responseBody = new JSONObject(response.body());
    assertNotNull(responseBody.opt("id"));
    assertEquals("doggie", responseBody.getString("name"));
}
```

### JSON Assertions with JsonAssert

```java
import org.skyscreamer.jsonassert.JSONAssert;
import org.skyscreamer.jsonassert.JSONCompareMode;

@Test
void shouldReturnExpectedPet() throws Exception {
    var httpClient = HttpClient.newHttpClient();

    var request = HttpRequest.newBuilder()
        .GET()
        .uri(container.getURI().resolve("/api/pets/123"))
        .timeout(Duration.ofSeconds(5))
        .build();

    var response = httpClient.send(request, HttpResponse.BodyHandlers.ofString());

    assertEquals(200, response.statusCode());

    var expectedJson = """
        {
            "id": 123,
            "name": "doggie",
            "category": {"name": "Dogs"}
        }
        """;

    JSONAssert.assertEquals(expectedJson, response.body(), JSONCompareMode.LENIENT);
}
```

---

## Complete example: BlackBoxTests with RestAssured (without a DB)

### Java

```java
package ru.tinkoff.kora.example;

import static io.restassured.RestAssured.given;
import static org.hamcrest.Matchers.*;

import io.goodforgod.testcontainers.extensions.ContainerMode;
import io.goodforgod.testcontainers.extensions.Network;
import io.goodforgod.testcontainers.extensions.jdbc.ConnectionPostgreSQL;
import io.goodforgod.testcontainers.extensions.jdbc.JdbcConnection;
import io.goodforgod.testcontainers.extensions.jdbc.Migration;
import io.goodforgod.testcontainers.extensions.jdbc.TestcontainersPostgreSQL;
import io.restassured.http.ContentType;
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
                drop = Migration.Mode.PER_METHOD))
class BlackBoxTests {

    private static final AppContainer container = AppContainer.build()
            .withNetwork(org.testcontainers.containers.Network.SHARED);

    @ConnectionPostgreSQL
    private JdbcConnection connection;

    @BeforeAll
    static void setup(@ConnectionPostgreSQL JdbcConnection connection) {
        var params = connection.paramsInNetwork().orElseThrow();
        container.withEnv(java.util.Map.of(
                "DB_URL", params.jdbcUrl(),
                "DB_USER", params.username(),
                "DB_PASS", params.password(),
                "CACHE_MAX_SIZE", "0"));

        container.start();
    }

    @AfterAll
    static void cleanup() {
        container.stop();
    }

    @Test
    void shouldCreateAndGetPet() {
        // Create pet
        var createBody = """
            {
                "name": "doggie",
                "category": {"name": "Dogs"}
            }
            """;

        var petId = given()
                .baseUri(container.getURI().toString())
                .contentType(ContentType.JSON)
                .body(createBody)
        .when()
                .post("/api/pets")
        .then()
                .statusCode(200)
                .body("id", notNullValue())
                .body("name", equalTo("doggie"))
                .extract()
                .path("id");

        // Get pet
        given()
                .baseUri(container.getURI().toString())
                .pathParam("id", petId)
        .when()
                .get("/api/pets/{id}")
        .then()
                .statusCode(200)
                .body("id", equalTo(petId))
                .body("name", equalTo("doggie"))
                .body("category.name", equalTo("Dogs"));
    }

    @Test
    void shouldUpdatePet() {
        // Create pet first
        var createBody = """
            {
                "name": "original",
                "category": {"name": "Dogs"}
            }
            """;

        var petId = given()
                .baseUri(container.getURI().toString())
                .contentType(ContentType.JSON)
                .body(createBody)
        .when()
                .post("/api/pets")
        .then()
                .statusCode(200)
                .extract().path("id");

        // Update pet
        var updateBody = """
            {
                "name": "updated",
                "status": "pending"
            }
            """;

        given()
                .baseUri(container.getURI().toString())
                .pathParam("id", petId)
                .contentType(ContentType.JSON)
                .body(updateBody)
        .when()
                .put("/api/pets/{id}")
        .then()
                .statusCode(200)
                .body("id", equalTo(petId))
                .body("name", equalTo("updated"))
                .body("status", equalTo("pending"));
    }

    @Test
    void shouldDeletePet() {
        // Create pet first
        var createBody = """
            {
                "name": "to-delete",
                "category": {"name": "Dogs"}
            }
            """;

        var petId = given()
                .baseUri(container.getURI().toString())
                .contentType(ContentType.JSON)
                .body(createBody)
        .when()
                .post("/api/pets")
        .then()
                .statusCode(200)
                .extract().path("id");

        // Delete pet
        given()
                .baseUri(container.getURI().toString())
                .pathParam("id", petId)
        .when()
                .delete("/api/pets/{id}")
        .then()
                .statusCode(204);

        // Verify deleted
        given()
                .baseUri(container.getURI().toString())
                .pathParam("id", petId)
        .when()
                .get("/api/pets/{id}")
        .then()
                .statusCode(404);
    }

    @Test
    void shouldReturn404ForNotFoundPet() {
        given()
                .baseUri(container.getURI().toString())
                .pathParam("id", 99999)
        .when()
                .get("/api/pets/{id}")
        .then()
                .statusCode(404);
    }

    @Test
    void shouldReturnCustomHeaders() {
        given()
                .baseUri(container.getURI().toString())
                .header("X-Request-ID", "test-123")
        .when()
                .get("/api/pets/123")
        .then()
                .statusCode(200)
                .header("Content-Type", "application/json");
    }
}
```

### Kotlin

```kotlin
package ru.tinkoff.kora.example

import io.restassured.RestAssured.given
import io.restassured.http.ContentType
import org.hamcrest.Matchers.*
import org.junit.jupiter.api.AfterAll
import org.junit.jupiter.api.BeforeAll
import org.junit.jupiter.api.Test

class BlackBoxTests {

    companion object {
        private val container = AppContainer.build()

        @BeforeAll
        @JvmStatic
        fun setup() {
            container.start()
        }

        @AfterAll
        @JvmStatic
        fun cleanup() {
            container.stop()
        }
    }

    @Test
    fun `should create and get pet`() {
        val createBody = """
            {
                "name": "doggie",
                "category": {"name": "Dogs"}
            }
            """

        val petId = given()
            .baseUri(container.getURI().toString())
            .contentType(ContentType.JSON)
            .body(createBody)
        .`when`()
            .post("/api/pets")
        .then()
            .statusCode(200)
            .body("id", notNullValue())
            .body("name", equalTo("doggie"))
            .extract()
            .path<Int>("id")

        given()
            .baseUri(container.getURI().toString())
            .pathParam("id", petId)
        .`when`()
            .get("/api/pets/{id}")
        .then()
            .statusCode(200)
            .body("id", equalTo(petId))
            .body("name", equalTo("doggie"))
            .body("category.name", equalTo("Dogs"))
    }

    @Test
    fun `should update pet`() {
        val createBody = """
            {
                "name": "original",
                "category": {"name": "Dogs"}
            }
            """

        val petId = given()
            .baseUri(container.getURI().toString())
            .contentType(ContentType.JSON)
            .body(createBody)
        .`when`()
            .post("/api/pets")
        .then()
            .statusCode(200)
            .extract().path<Int>("id")

        val updateBody = """
            {
                "name": "updated",
                "status": "pending"
            }
            """

        given()
            .baseUri(container.getURI().toString())
            .pathParam("id", petId)
            .contentType(ContentType.JSON)
            .body(updateBody)
        .`when`()
            .put("/api/pets/{id}")
        .then()
            .statusCode(200)
            .body("id", equalTo(petId))
            .body("name", equalTo("updated"))
            .body("status", equalTo("pending"))
    }

    @Test
    fun `should delete pet`() {
        val createBody = """
            {
                "name": "to-delete",
                "category": {"name": "Dogs"}
            }
            """

        val petId = given()
            .baseUri(container.getURI().toString())
            .contentType(ContentType.JSON)
            .body(createBody)
        .`when`()
            .post("/api/pets")
        .then()
            .statusCode(200)
            .extract().path<Int>("id")

        given()
            .baseUri(container.getURI().toString())
            .pathParam("id", petId)
        .`when`()
            .delete("/api/pets/{id}")
        .then()
            .statusCode(204)

        given()
            .baseUri(container.getURI().toString())
            .pathParam("id", petId)
        .`when`()
            .get("/api/pets/{id}")
        .then()
            .statusCode(404)
    }

    @Test
    fun `should return 404 for not found pet`() {
        given()
            .baseUri(container.getURI().toString())
            .pathParam("id", 99999)
        .`when`()
            .get("/api/pets/{id}")
        .then()
            .statusCode(404)
    }

    @Test
    fun `should return custom headers`() {
        given()
            .baseUri(container.getURI().toString())
            .header("X-Request-ID", "test-123")
        .`when`()
            .get("/api/pets/123")
        .then()
            .statusCode(200)
            .header("Content-Type", "application/json")
    }
}
```

---

## Best Practices

### 1. Set baseUri once

```java
// Correct
private static String baseUri;

@BeforeAll
static void setup() {
    baseUri = container.getURI().toString();
}

@Test
void test() {
    given()
        .baseUri(baseUri)
        ...
}

// Wrong (creates a new URI on every call)
given()
    .baseUri(container.getURI().toString())
    ...
```

### 2. Extract values for test chains

```java
// Extract ID for use in subsequent steps
var petId = given()
    .baseUri(baseUri)
    .body(createBody)
.when()
    .post("/api/pets")
.then()
    .statusCode(200)
    .extract().path("id");

// Use petId in subsequent requests
```

### 3. Group assertions

```java
// All assertions in a single then()
.then()
    .statusCode(200)
    .body("id", notNullValue())
    .body("name", equalTo("doggie"))
    .body("status", equalTo("available"));

// Separate then() calls are slower
.then().statusCode(200);
.then().body("id", notNullValue());
```

### 4. Use ResponseSpecification for common checks

```java
// Common spec for all responses
private static ResponseSpecification commonSpec;

@BeforeAll
static void setup() {
    commonSpec = new ResponseSpecBuilder()
        .expectStatusCode(200)
        .expectHeader("Content-Type", containsString("application/json"))
        .build();
}

@Test
void test() {
    given()
        .baseUri(baseUri)
    .when()
        .get("/api/pets/123")
    .then()
        .spec(commonSpec)
        .body("id", equalTo(123));
}
```

### 5. Logging for debugging

```java
// Log only on failure
given()
    .baseUri(baseUri)
    .log().ifValidationFails()  // Log on failure
.when()
    .get("/api/pets/123")
.then()
    .log().ifValidationFails()  // Log on failure
    .statusCode(200);

// Or always log
given()
    .baseUri(baseUri)
    .log().all()  // All logs
.when()
    .get("/api/pets/123")
.then()
    .log().all()  // All logs
    .statusCode(200);
```

### 6. Timeouts for HTTP requests

```java
import io.restassured.config.RestAssuredConfig;
import io.restassured.config.HttpClientConfig;

@BeforeAll
static void setup() {
    RestAssured.config = RestAssuredConfig.config()
        .httpClient(HttpClientConfig.httpClientConfig()
            .setParam("http.connection.timeout", 5000)
            .setParam("http.socket.timeout", 5000));
}
```

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| Container does not start | Check Docker, increase `withStartupTimeout` |
| 404 on health check | Check the path `/system/readiness` in the application |
| RestAssured does not serialize Kotlin objects | Add the `kotlin-extensions` dependency |
| JSON assertions do not work | Check the path in JSON (`.body("data.id", ...)`) |
| Port conflicts | Use `@Network(shared = true)` |
| Testcontainers is slow | Use `ContainerMode.PER_RUN` instead of `PER_METHOD` |

---

## Related resources

- [RestAssured Documentation](https://rest-assured.io/)
- [RestAssured GitHub](https://github.com/rest-assured/rest-assured)
- [RestAssured Usage Guide](https://github.com/rest-assured/rest-assured/wiki/Usage)
- [Testcontainers Extensions](references/testcontainers-reference.md)
- [Black-Box Testing Reference](references/blackbox-testing-reference.md)
- [MockServer Testing Reference](references/mockserver-testing-reference.md)
