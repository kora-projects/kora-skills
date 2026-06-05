# MockServer Testing Reference

**Source:** [.kora-agent/kora-docs/mkdocs/docs/en/documentation/testing.md](.kora-agent/kora-docs/mkdocs/docs/en/documentation/testing.md)  
**Examples:** `.kora-agent/kora-examples/kora-java-http-client/`

Testing HTTP clients using MockServer for mocking external services.

## Overview

**MockServer** is a tool for mocking HTTP services in tests.

**When to use:**
- Testing HTTP clients without access to the real API
- Isolating tests from external dependencies
- Simulating responses (success, errors, timeouts)
- Verifying sent requests

**When not to use:**
- Integration tests with real services (Testcontainers)
- Black-box tests of the full application (Black-Box Testing)
- Unit tests without HTTP calls (Mockito/MockK)

---

## Dependencies

### Option 1: testcontainers-extensions (recommended)

```groovy
dependencies {
    // Kora HTTP Client (OkHttp — recommended)
    implementation "ru.tinkoff.kora:http-client-ok"
    
    // Testcontainers MockServer (for @TestcontainersMockServer)
    testImplementation "io.goodforgod:testcontainers-extensions-mockserver:0.13.0"
    
    // MockServer Client (for fluent API)
    testImplementation "org.mock-server:mockserver-client-java:5.15.0"
    
    // Kora Test + JUnit 5
    testImplementation "ru.tinkoff.kora:test-junit5"
    testImplementation "org.junit.jupiter:junit-jupiter:5.10.2"
}
```

### Option 2: Base Testcontainers + MockServer Module

```groovy
dependencies {
    // Kora HTTP Client (OkHttp — recommended)
    implementation "ru.tinkoff.kora:http-client-ok"
    
    // Testcontainers MockServer Module (official module)
    testImplementation "org.testcontainers:mockserver:1.21.3"
    
    // MockServer Client (for fluent API)
    testImplementation "org.mock-server:mockserver-client-java:5.15.0"
    
    // Kora Test + JUnit 5
    testImplementation "ru.tinkoff.kora:test-junit5"
    testImplementation "org.junit.jupiter:junit-jupiter:5.10.2"
}
```

---

## HTTP client example (Kora)

```java
package ru.tinkoff.kora.example;

import ru.tinkoff.kora.http.client.common.annotation.HttpClient;
import ru.tinkoff.kora.http.common.annotation.HttpRoute;
import ru.tinkoff.kora.http.common.HttpMethod;
import ru.tinkoff.kora.http.common.annotation.Path;
import ru.tinkoff.kora.http.common.annotation.Json;

@HttpClient(configPath = "httpClient.externalApiClient")
public interface ExternalApiClient {

    @HttpRoute(method = HttpMethod.GET, path = "/api/users/{id}")
    User getUser(@Path("id") String id);

    @HttpRoute(method = HttpMethod.POST, path = "/api/users")
    User createUser(@Json CreateUserRequest request);
}

// Data models
record User(String id, String name) {}
record CreateUserRequest(String name) {}
```

### Client configuration (application.conf)

```hocon
httpClient {
  externalApiClient {
    url = ${EXTERNAL_API_CLIENT_URL}  // Variable from ENV or system property
    requestTimeout = "10s"
  }
}
```

---

## Quick Start (Java)

```java
package ru.tinkoff.kora.example;

import static org.junit.jupiter.api.Assertions.*;
import static org.mockserver.model.HttpRequest.request;
import static org.mockserver.model.HttpResponse.response;
import static org.mockserver.model.MediaType.APPLICATION_JSON;

import io.goodforgod.testcontainers.extensions.ContainerMode;
import io.goodforgod.testcontainers.extensions.mockserver.*;
import org.junit.jupiter.api.Test;
import ru.tinkoff.kora.test.extension.junit5.KoraAppTest;
import ru.tinkoff.kora.test.extension.junit5.KoraAppTestConfigModifier;
import ru.tinkoff.kora.test.extension.junit5.KoraConfigModification;
import ru.tinkoff.kora.test.extension.junit5.TestComponent;

@TestcontainersMockServer(mode = ContainerMode.PER_RUN)
@KoraAppTest(Application.class)
class ExternalApiClientTest implements KoraAppTestConfigModifier {

    @ConnectionMockServer
    private MockServerConnection mockServerConnection;

    @TestComponent
    private ExternalApiClient client;

    @Override
    public KoraConfigModification config() {
        // Pass the MockServer URL via system property
        return KoraConfigModification.ofSystemProperty(
            "EXTERNAL_API_CLIENT_URL",
            mockServerConnection.params().uri().toString()
        );
    }

    @Test
    void shouldGetUserById() {
        // given
        mockServerConnection.client().when(
            request()
                .withMethod("GET")
                .withPath("/api/users/123")
        ).respond(
            response()
                .withStatusCode(200)
                .withContentType(APPLICATION_JSON)
                .withBody("{\"id\":\"123\",\"name\":\"John\"}")
        );

        // when
        var user = client.getUser("123");

        // then
        assertEquals("123", user.id());
        assertEquals("John", user.name());
    }

    @Test
    void shouldHandle404() {
        mockServerConnection.client().when(
            request().withMethod("GET").withPath("/api/users/notfound")
        ).respond(
            response().withStatusCode(404).withBody("{\"error\":\"Not found\"}")
        );

        var exception = assertThrows(
            HttpClientResponseException.class,
            () -> client.getUser("notfound")
        );
        assertEquals(404, exception.statusCode());
    }
}
```

---

## Quick Start (Kotlin)

```kotlin
package ru.tinkoff.kora.example

import io.goodforgod.testcontainers.extensions.ContainerMode
import io.goodforgod.testcontainers.extensions.mockserver.*
import org.junit.jupiter.api.Test
import ru.tinkoff.kora.test.extension.junit5.KoraAppTest
import ru.tinkoff.kora.test.extension.junit5.KoraAppTestConfigModifier
import ru.tinkoff.kora.test.extension.junit5.KoraConfigModification
import ru.tinkoff.kora.test.extension.junit5.TestComponent

@TestcontainersMockServer(mode = ContainerMode.PER_RUN)
@KoraAppTest(Application::class)
class ExternalApiClientTest : KoraAppTestConfigModifier {

    @ConnectionMockServer
    private lateinit var mockServerConnection: MockServerConnection

    @TestComponent
    private lateinit var client: ExternalApiClient

    override fun config(): KoraConfigModification {
        return KoraConfigModification.ofSystemProperty(
            "EXTERNAL_API_CLIENT_URL",
            mockServerConnection.params().uri().toString()
        )
    }

    @Test
    fun `should get user by id`() {
        mockServerConnection.client().`when`(
            request()
                .withMethod("GET")
                .withPath("/api/users/123")
        ).respond(
            response()
                .withStatusCode(200)
                .withContentType(MediaType.APPLICATION_JSON)
                .withBody("""{"id":"123","name":"John"}""")
        )

        val user = client.getUser("123")

        org.junit.jupiter.api.Assertions.assertEquals("123", user.id)
        org.junit.jupiter.api.Assertions.assertEquals("John", user.name)
    }

    @Test
    fun `should handle 404`() {
        mockServerConnection.client().`when`(
            request().withMethod("GET").withPath("/api/users/notfound")
        ).respond(
            response().withStatusCode(404).withBody("""{"error":"Not found"}""")
        )

        val exception = org.junit.jupiter.api.Assertions.assertThrows(
            HttpClientResponseException::class.java
        ) {
            client.getUser("notfound")
        }
        org.junit.jupiter.api.Assertions.assertEquals(404, exception.statusCode)
    }
}
```

---

## Advanced patterns

### POST request with a body

```java
@Test
void shouldCreateUser() {
    mockServerConnection.client().when(
        request()
            .withMethod("POST")
            .withPath("/api/users")
            .withContentType(APPLICATION_JSON)
    ).respond(
        response()
            .withStatusCode(201)
            .withBody("{\"id\":\"456\",\"name\":\"Jane\"}")
    );

    var result = client.createUser(new CreateUserRequest("Jane"));
    assertEquals("456", result.id());
    assertEquals("Jane", result.name());
}
```

### Request Verification

```java
@Test
void shouldVerifyHeaders() {
    client.getUserWithAuth("123", "Bearer token123");

    mockServerConnection.client().verify(
        request()
            .withMethod("GET")
            .withPath("/api/users/123")
            .withHeader("Authorization", "Bearer token123"),
        VerificationTimes.once()
    );
}
```

### Timeout Simulation

```java
@Test
void shouldHandleTimeout() {
    mockServerConnection.client().when(
        request().withMethod("GET").withPath("/api/slow")
    ).respond(
        response().withDelay(java.time.Duration.ofSeconds(10))
    );

    assertThrows(java.util.concurrent.TimeoutException.class, () -> client.getSlow());
}
```

### Rate Limiting

```java
@Test
void shouldHandle429() {
    mockServerConnection.client().when(
        request().withMethod("GET").withPath("/api/users/1")
    ).respond(
        response()
            .withStatusCode(429)
            .withHeader("Retry-After", "60")
            .withBody("{\"error\":\"Rate limit exceeded\"}")
    );

    var exception = assertThrows(RateLimitException.class, () -> client.getUser("1"));
    assertEquals(429, exception.statusCode());
}
```

---

## Alternative: Base Testcontainers MockServer Module

If testcontainers-extensions-mockserver is not used (official Testcontainers module):

```java
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.mockserver.client.MockServerClient;
import org.testcontainers.containers.MockServerContainer;
import org.testcontainers.junit.jupiter.Container;
import org.testcontainers.junit.jupiter.Testcontainers;

import static org.mockserver.model.HttpRequest.request;
import static org.mockserver.model.HttpResponse.response;

@Testcontainers
@KoraAppTest(Application.class)
class ExternalApiClientTest implements KoraAppTestConfigModifier {

    @Container
    private static final MockServerContainer mockServer =
        new MockServerContainer("mockserver/mockserver:5.15.0");

    private MockServerClient mockServerClient;

    @TestComponent
    private ExternalApiClient client;

    @BeforeEach
    void setup() {
        // Connect to the MockServer in the container
        mockServerClient = new MockServerClient(
            mockServer.getHost(),
            mockServer.getServerPort()
        );
    }

    @Override
    public KoraConfigModification config() {
        return KoraConfigModification.ofSystemProperty(
            "EXTERNAL_API_CLIENT_URL",
            mockServer.getEndpoint()
        );
    }

    @AfterEach
    void tearDown() {
        mockServerClient.close();
    }

    @Test
    void shouldGetUserById() {
        mockServerClient.when(
            request().withMethod("GET").withPath("/api/users/123")
        ).respond(
            response().withStatusCode(200).withBody("{\"id\":\"123\"}")
        );

        var user = client.getUser("123");
        assertEquals("123", user.id());
    }
}
```

---

## Best Practices

### 1. Configuration via variable

```hocon
// Good — uses a variable
httpClient {
  externalApiClient {
    url = ${EXTERNAL_API_CLIENT_URL}
  }
}

// Bad — hardcoded URL
httpClient {
  externalApiClient {
    url = "http://localhost:8080"
  }
}
```

### 2. Cleanup

```java
// When using @TestcontainersMockServer — automatic
// When starting manually:
@AfterEach
void tearDown() {
    mockServer.stop();
}
```

### 3. MediaType

```java
// Good
.withContentType(MediaType.APPLICATION_JSON)

// Bad
.withHeader("Content-Type", "application/json")
```

### 4. Verify requests

```java
@Test
void shouldVerifyRequest() {
    client.getUser("123");

    mockServerConnection.client().verify(
        request().withMethod("GET").withPath("/api/users/123"),
        VerificationTimes.once()
    );
}
```

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| Client is not injected | Check `@HttpClient(configPath = "...")` |
| Mock not matching | Check method, path, headers, body |
| Verification failed | Call `verify()` after the request |
| Timeout in tests | Increase `requestTimeout` in the config |

---

## Comparison of approaches

| Approach | Speed | Realism | When to use |
|----------|-------|---------|-------------|
| **MockServer + @KoraAppTest** | Fast | Medium | Testing HTTP clients |
| **Testcontainers** | Slow | High | Integration with real services |
| **Mockito/MockK** | Very fast | Low | Unit tests without HTTP |

---

## Resources

- [MockServer Documentation](https://www.mock-server.com/)
- [MockServer GitHub](https://github.com/mock-server/mockserver)
- [Kora HTTP Client](https://kora-projects.github.io/kora-docs/en/documentation/http-client.html)
- [Kora @KoraAppTest](https://kora-projects.github.io/kora-docs/en/documentation/junit5.html)
