---
name: kora-testing-blackbox
description: "Black-box end-to-end testing of a packaged Kora application through its public HTTP API. Covers a GenericContainer AppContainer wrapper that builds the app Dockerfile, standard Testcontainers (PostgreSQLContainer, KafkaContainer) on Network.SHARED, readiness gating via Wait.forHttp(\"/system/readiness\") on the private port 8085, and driving the app with java.net.http.HttpClient or RestAssured. Use when testing the real Docker artifact end-to-end, wiring Testcontainers infrastructure for a Kora service, building the distTar/installDist image, or asserting HTTP status codes, JSON bodies, and persisted state without touching the Kora graph. For in-process component tests with @KoraAppTest see kora-testing-junit-java."
---

# Kora Testing Black-Box — E2E via HTTP API

Black-box tests run the **packaged application** (the `distTar`/`installDist` artifact) inside a Docker container and exercise it only through the public HTTP API. The test never injects into or modifies the Kora graph — it runs the same code that ships.

Kora builds its dependency graph at compile time, so startup is fast enough to make black-box tests a primary confidence source, not just a smoke suite. They catch what narrower tests miss: routing, `@Json` (de)serialization, `@Valid` validation, config loading, migrations, and probes all exercised together.

> Kora ships **no** Testcontainers wrapper. Use the standard `org.testcontainers:*` API directly. For in-process tests with `@KoraAppTest`/`@TestComponent`, use the `kora-testing-junit-java` / `kora-testing-junit-kotlin` skills instead.

---

## Contents

- [Quick Start](#quick-start) — deps, Dockerfile, AppContainer, first test
- [What's in references/](#whats-in-references) and [assets/](#whats-in-assets)
- [When to use vs NOT](#when-to-use-vs-not)
- [Core patterns](#core-patterns)
- [Common pitfalls](#common-pitfalls)

---

## Quick Start

Pin all Kora artifacts through the `kora-parent` BOM; never version `ru.tinkoff.kora:*` deps individually. The example repo uses BOM `1.2.17`.

### 1. Dependencies (`build.gradle`)

```groovy
dependencies {
    koraBom platform("ru.tinkoff.kora:kora-parent:1.2.17")

    // Annotation processor is mandatory for any Kora module to generate code.
    annotationProcessor "ru.tinkoff.kora:annotation-processors"
    testAnnotationProcessor "ru.tinkoff.kora:annotation-processors"

    testImplementation platform("org.junit:junit-bom:5.14.3")
    testImplementation "org.junit.jupiter:junit-jupiter"
    testImplementation project(":my-service-app")          // the packaged app module
    testImplementation "ru.tinkoff.kora:test-junit5"
    testImplementation "org.json:json:20231013"
    testImplementation "org.testcontainers:junit-jupiter:1.21.4"
    testImplementation "org.testcontainers:testcontainers:1.21.4"
    testImplementation "org.testcontainers:postgresql:1.21.4"
}

test {
    // Build the distribution archive the Dockerfile copies, before tests run.
    dependsOn ":my-service-app:distTar"
    inputs.file("../my-service-app/Dockerfile")
    inputs.file("../my-service-app/build/distributions/application.tar")
    useJUnitPlatform()
}
```

Kotlin uses `ksp "ru.tinkoff.kora:symbol-processors"` instead of the annotation processor.

### 2. Dockerfile (in the application module)

Packages the `distTar` output into a JRE image exposing the public (`8080`) and private (`8085`) ports.

```dockerfile
FROM eclipse-temurin:25-jre-jammy

ARG TARGET_DIR=/opt/app
COPY build/distributions/application.tar /application.tar
RUN mkdir -p ${TARGET_DIR} && tar -xf /application.tar -C ${TARGET_DIR} && rm /application.tar

ARG DOCKER_USER=app
RUN groupadd -r ${DOCKER_USER} && useradd -rg ${DOCKER_USER} ${DOCKER_USER}
USER ${DOCKER_USER}

EXPOSE 8080/tcp
EXPOSE 8085/tcp
CMD ["/opt/app/application/bin/application"]
```

### 3. AppContainer wrapper

A `GenericContainer` subclass that builds the image, exposes both ports, and gates on `/system/readiness` on the private port.

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

### 4. Black-box test with PostgreSQL

`Network.SHARED` lets the application reach PostgreSQL by its alias; `withEnv(...)` supplies the connection settings the application reads via `${POSTGRES_JDBC_URL}` etc. in its `@ConfigSource` config.

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
import org.testcontainers.containers.Network;
import org.testcontainers.containers.PostgreSQLContainer;
import org.testcontainers.junit.jupiter.Container;
import org.testcontainers.junit.jupiter.Testcontainers;

@Testcontainers
class BlackBoxTests {

    @Container
    private static final PostgreSQLContainer<?> POSTGRES = new PostgreSQLContainer<>("postgres:16-alpine")
            .withNetwork(Network.SHARED)
            .withNetworkAliases("postgres");

    @Container
    private static final AppContainer APP = new AppContainer()
            .withNetwork(Network.SHARED)
            .dependsOn(POSTGRES)
            .withEnv("POSTGRES_JDBC_URL", "jdbc:postgresql://postgres:5432/" + POSTGRES.getDatabaseName())
            .withEnv("POSTGRES_USER", POSTGRES.getUsername())
            .withEnv("POSTGRES_PASS", POSTGRES.getPassword());

    @Test
    void createUser_ShouldReturn201() throws Exception {
        var body = new JSONObject().put("name", "John Doe").put("email", uniqueEmail("john"));
        var request = HttpRequest.newBuilder()
                .POST(HttpRequest.BodyPublishers.ofString(body.toString()))
                .uri(APP.getURI().resolve("/users"))
                .header("Content-Type", "application/json")
                .timeout(Duration.ofSeconds(10))
                .build();

        var response = HttpClient.newHttpClient().send(request, HttpResponse.BodyHandlers.ofString());

        assertEquals(201, response.statusCode());
        assertTrue(new JSONObject(response.body()).has("id"));
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

    private String uniqueEmail(String prefix) {
        return prefix + "-" + UUID.randomUUID() + "@example.com";
    }
}
```

### 5. Build and run

```bash
./gradlew test          # distTar runs first via the dependsOn above
```

The application's migrations (Flyway/Liquibase) run on startup inside the container, so the schema is ready before the first request.

---

## What's in references/

| Document | Use it for |
|----------|-----------|
| [blackbox-integration-reference.md](references/blackbox-integration-reference.md) | Full AppContainer pattern, CRUD, RestAssured, Kafka, error scenarios, Awaitility, DB verification |
| [testcontainers-reference.md](references/testcontainers-reference.md) | Standard Testcontainers API: PostgreSQL/Kafka/MySQL, wait strategies, container reuse |
| [docker-reference.md](references/docker-reference.md) | Dockerfile strategies (basic, multi-stage), `APP_IMAGE` reuse, CI/CD |
| [docker-compose-reference.md](references/docker-compose-reference.md) | Multi-container Compose tests, health checks, microservices |

## What's in assets/

| Asset | Purpose |
|-------|---------|
| `BlackBoxTest.java.template` / `.kt.template` | HttpClient black-box test skeleton |
| `BlackBoxTest-RestAssured.java.template` / `.kt.template` | RestAssured DSL black-box test skeleton |
| `Dockerfile.template` | Basic Dockerfile (requires `installDist`/`distTar` first) |
| `Dockerfile.self-build.template` / `-kotlin.template` | Multi-stage build (no JDK on host) |
| `README.md` | How to use the templates |

---

## When to use vs NOT

**Use black-box when:**
- Validating the real Docker artifact end-to-end (routing + JSON + validation + migrations + probes)
- Verifying HTTP contracts: status codes, headers, JSON bodies a client actually sees
- Testing async side effects (Kafka consumer, scheduled jobs) observed through the API
- Reproducing deployment problems: wrong ports, broken packaging, missing env config

**Do NOT use black-box (use `kora-testing-junit-java`/`-kotlin`) when:**
- You want fast feedback on business logic in a single component
- You need to mock a collaborator with `@TestComponent` + Mockito/MockK
- You need to inject into the Kora graph or override config with `KoraConfigModification`

---

## Core patterns

- **Readiness gating:** `Wait.forHttp("/system/readiness").forPort(8085).forStatusCode(200)` — the private port (`httpServer.privateApiHttpPort`) serves `/system/readiness`, `/system/liveness`, `/metrics`. Never `Wait.forListeningPort()` on the public port.
- **Shared network:** declare every container on `Network.SHARED` with `withNetworkAliases("postgres")`; the app reaches it as `postgres:5432`.
- **Config injection:** `withEnv("POSTGRES_JDBC_URL", ...)` — names must match the `${VAR}` substitution keys in the app's `@ConfigSource`, not magic Testcontainers names.
- **Startup ordering:** `.dependsOn(POSTGRES)` so infrastructure starts first.
- **CI image reuse:** branch the `AppContainer` constructor on `System.getenv("APP_IMAGE")` to skip the Dockerfile build (see [docker-reference.md](references/docker-reference.md)).
- **Async assertions:** wrap polling reads in Awaitility `await().atMost(...).untilAsserted(...)`.

---

## Common pitfalls

| Symptom | Cause | Fix |
|---------|-------|-----|
| Container never becomes ready | Waiting on the public port or `forListeningPort()` | Wait on `/system/readiness` on port 8085 |
| `application.tar` not found at build | `distTar`/`installDist` did not run | Add `test { dependsOn ":app:distTar" }` |
| App cannot reach the DB | Per-test `Network.newNetwork()` or using the host-mapped port | Use `Network.SHARED` + alias `postgres:5432` |
| Config not applied | Env var names differ from `${VAR}` keys | Match `withEnv(...)` names to the app config |
| Duplicate-key failures across tests | Shared static container + fixed test data | Generate unique values (e.g. unique emails) |
| Trying `@KoraAppTest` with `GenericContainer` | Mixing in-process and black-box paradigms | Pick one: black-box runs the image, `@KoraAppTest` runs in-process |
