---
name: kora-testing-blackbox
description: "Black-box E2E tests of a packaged Kora 2.0 service — Testcontainers builds the application Dockerfile and runs the real artifact, an AppContainer (a GenericContainer subclass you write) exposes 8080 public + 8085 system, and startup is gated on Wait.forHttp(\"/system/readiness\").forPort(8085).forStatusCode(200) — never on a log line. Covers distTar packaging, eclipse-temurin:25-jre-jammy and GraalVM native images, Network.SHARED with PostgreSQL/Kafka, withEnv config injection for httpServer.port / httpServer.system.port, and asserting real /metrics series instead of the \"# Metric Scraper disabled\" stub. Use for real-artifact E2E; for in-process @KoraAppTest see kora-testing-junit-java / kora-testing-junit-kotlin."
license: Apache-2.0
metadata:
  kora-version: "2.x"
---

# Kora Testing Black-Box — E2E via HTTP API

> **Kora sub-skill — obey the [kora-v2 meta rules](../../SKILL.md) on every task:** **R0** ground the workspace on Kora 2.0 refs before starting (framework source at tag `2.0.0.RC2` + `kora-examples` at `migration/2.0` + Kora 2.0 docs at koraframework.io/v2, which trail the source; 1.x `kora-docs` pages are never an authority) · **R1** read this sub-skill before writing code · **R2** Kora 2.0 APIs only — no Spring/Micronaut/Quarkus, no Kora 1.x APIs, no invented annotations or config keys · **R3** journal any incorrect Kora usage. Add comments/Javadoc only if asked.

| | |
|---|---|
| **BOM** | `io.koraframework:kora-bom`, `koraVersion=2.0.0.RC2` from plain `mavenCentral()` |
| **Java / Kotlin** | JDK 25 (hard floor) · Kotlin 2.4 + KSP 2.3 |
| **JUnit** | `org.junit:junit-bom:6.1.3` |
| **Testcontainers** | `1.21.4` — `junit-jupiter`, `testcontainers`, `postgresql` (see [coordinates](#testcontainers-coordinates)) |
| **Runtime image** | `eclipse-temurin:25-jre-jammy` · native: `ghcr.io/graalvm/native-image-community:25` |
| **Ports** | `8080` public API · `8085` **system** API (`/system/readiness`, `/system/liveness`, `/metrics`) |

Black-box tests run the **packaged application** (the `distTar` artifact, or a GraalVM native
binary) inside a Docker container and exercise it only through its HTTP API. The test never
injects into or modifies the Kora graph — it runs exactly the bytes that ship.

Kora builds its dependency graph at compile time, so startup is fast enough to make black-box
tests a primary confidence source, not just a smoke suite. They catch what narrower tests miss:
routing, `@Json` (de)serialization, `@Valid` validation, config key names, migrations, probes and
reachability metadata all exercised together.

> Kora ships **no** Testcontainers wrapper. Use the `org.testcontainers:*` API directly. For
> in-process tests with `@KoraAppTest` / `@TestComponent`, use `kora-testing-junit-java` or
> `kora-testing-junit-kotlin` instead.

---

## Contents

- [Quick Start](#quick-start) — deps, Dockerfile, AppContainer, first test
- [The two servers and their ports](#the-two-servers-and-their-ports)
- [Testcontainers coordinates](#testcontainers-coordinates)
- [Asserting on `/metrics`](#asserting-on-metrics)
- [GraalVM native images](#graalvm-native-images)
- [What's in references/](#whats-in-references) and [assets/](#whats-in-assets)
- [When to use vs NOT](#when-to-use-vs-not)
- [Core patterns](#core-patterns)
- [Common pitfalls](#common-pitfalls)

---

## Quick Start

Pin every Kora artifact through the `io.koraframework:kora-bom` platform; never version an
`io.koraframework:*` dependency individually. `kora-parent` does not exist in 2.0.

### 1. Dependencies (`build.gradle`)

```groovy
configurations {
    koraBom
    annotationProcessor.extendsFrom(koraBom)
    compileOnly.extendsFrom(koraBom)
    implementation.extendsFrom(koraBom)
    testImplementation.extendsFrom(koraBom)
    testAnnotationProcessor.extendsFrom(koraBom)
}

dependencies {
    koraBom platform("io.koraframework:kora-bom:$koraVersion")   // koraVersion=2.0.0.RC2

    annotationProcessor "io.koraframework:annotation-processors"
    testAnnotationProcessor "io.koraframework:annotation-processors"

    testImplementation platform("org.junit:junit-bom:$junitVersion")   // junitVersion=6.1.3
    testImplementation "org.junit.jupiter:junit-jupiter"
    testImplementation project(":my-service-app")                      // build ordering only
    testImplementation "org.json:json:20231013"
    testImplementation "org.testcontainers:junit-jupiter:1.21.4"
    testImplementation "org.testcontainers:testcontainers:1.21.4"
    testImplementation "org.testcontainers:postgresql:1.21.4"
}

test {
    // Build the archive the Dockerfile copies, before tests run.
    dependsOn ":my-service-app:distTar"
    inputs.file("../my-service-app/Dockerfile")
    inputs.file("../my-service-app/build/distributions/application.tar")
    useJUnitPlatform()
}
```

Kotlin swaps the processors for `ksp "io.koraframework:symbol-processors"`.

Two notes on that block. The `project(":my-service-app")` dependency is there for build ordering,
not for code — a black-box test must not import application classes; if it does, it has stopped
being a black-box test. And `io.koraframework:test-junit5` is the in-process `@KoraAppTest`
extension: the migrated black-box guides declare it out of habit but never import from it, and
nothing here builds a graph in the test JVM.

The application module must produce the archive the Dockerfile unpacks:

```groovy
application {
    applicationName = "application"
    mainClass = "com.example.Application"
}
distTar { archiveFileName = "application.tar" }
```

### 2. Dockerfile (in the application module)

```dockerfile
FROM eclipse-temurin:25-jre-jammy

ARG TARGET_DIR=/opt/app

COPY build/distributions/application.tar /application.tar
RUN mkdir -p ${TARGET_DIR}
RUN tar -xf /application.tar -C ${TARGET_DIR}
RUN rm /application.tar

ARG DOCKER_USER=app
RUN groupadd -r ${DOCKER_USER} && useradd -rg ${DOCKER_USER} ${DOCKER_USER}
USER ${DOCKER_USER}

EXPOSE 8080/tcp
EXPOSE 8085/tcp
CMD ["/opt/app/application/bin/application"]
```

JDK 25 is a hard floor: `kora-bom` declares `java.version = 25` and the published jars are
class-file major 69. A `21-jre` base image fails with `UnsupportedClassVersionError`.

### 3. AppContainer wrapper

`AppContainer` is **your** class, not a Kora type — a `GenericContainer` subclass that keeps image
construction, port exposure and readiness gating out of the test class.

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

**Never wait on a log line.** `Wait.forLogMessage(...)` binds the test to Kora's startup message
wording, which is not part of its contract and changed between 1.x and 2.0. `Wait.forHttp` on the
readiness probe is the only stable gate.

### 4. Black-box test with PostgreSQL

`Network.SHARED` lets the application reach PostgreSQL by alias; `withEnv(...)` supplies the values
the application's HOCON/YAML reads through `${POSTGRES_JDBC_URL}` substitutions.

```java
package com.example.blackbox;

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

Contracts in Kora 2.0 are **synchronous** — no `Mono`/`Flux`, no `CompletionStage`, no `suspend`
controllers — so the assertions above see a fully materialised response. There is no `Context` type
anywhere in the framework to propagate.

### 5. Build and run

```bash
./gradlew test          # distTar runs first via the dependsOn above
```

Flyway/Liquibase migrations run inside the application container on startup, so the schema is ready
before the first request reaches the API.

---

## The two servers and their ports

Kora 2.0 runs two HTTP servers from separate config sections and separate Undertow modules:

| Server | Module | Config path | Default port |
|---|---|---|---|
| Public API | `UndertowPublicHttpServerModule` | `httpServer` | `8080` |
| System API | `UndertowSystemHttpServerModule` | `httpServer.system` | **`8085`** |

`SystemHttpServerConfig` **overrides** `port()` to `8085`; it does not inherit the public default.
Its other defaults are `readinessPath = /system/readiness`, `livenessPath = /system/liveness`,
`metricsPath = /metrics` — all served by the system server, so all on `8085` unless reconfigured.

```hocon
httpServer {
  port = 8080
  system.port = 8085
}
```

### Renamed keys — a silent failure, not a build error

| 1.x key | 2.0 key |
|---|---|
| `httpServer.publicApiHttpPort` | `httpServer.port` |
| `httpServer.privateApiHttpPort` | `httpServer.system.port` |
| `httpServer.privateApiHttpReadinessPath` | `httpServer.system.readinessPath` |
| `httpServer.privateApiHttpLivenessPath` | `httpServer.system.livenessPath` |
| `httpServer.privateApiHttpMetricsPath` | `httpServer.system.metricsPath` |

A leftover 1.x key is an unrecognised HOCON key: it is **ignored without a warning**, and each
server falls back to its own default. A service that deliberately ran on custom ports therefore
comes up green on 8080/8085 instead. In a black-box test that shows up as a readiness wait that
never succeeds, or `HTTP/1.1 header parser received no bytes` from a request aimed at a port
nothing is listening on. Grep the application's config — and any inline HOCON in test sources —
for the old keys before blaming the container.

---

## Testcontainers coordinates

Use **`1.21.4`** with the classic module names. `kora-bom` constrains only `io.koraframework:*`
artifacts, so it has no opinion on Testcontainers — the version is entirely the application's
choice, and `1.21.4` is what the migrated Kora 2.0 examples run against JDK 25:

```groovy
testImplementation "org.testcontainers:junit-jupiter:1.21.4"
testImplementation "org.testcontainers:testcontainers:1.21.4"
testImplementation "org.testcontainers:postgresql:1.21.4"
```

> **If you move to Testcontainers 2.x**, the database and broker modules were renamed —
> `org.testcontainers:testcontainers-postgresql`, `testcontainers-kafka`,
> `testcontainers-cassandra` (Kora's own internal test fixtures use those at `2.0.5`). The old
> `org.testcontainers:postgresql` / `:kafka` / `:cassandra` coordinates do not resolve on the 2.x
> line. Kora's catalog pins only the core and those three modules, and says nothing about
> `junit-jupiter` — resolve that one's version separately rather than assuming a single property
> covers every module. Verify the API you use against the version you actually declare, and never
> mix a 1.x coordinate with a 2.x version.

Some migrated examples reach for `io.goodforgod:testcontainers-extensions-*:0.15.0` instead of the
raw modules; that is a convenience layer for provisioning and migrations, not a Kora requirement.
See [testcontainers-reference.md](references/testcontainers-reference.md).

---

## Asserting on `/metrics`

**A 200 from `/metrics` proves nothing.** With no `MetricsScraper` in the graph the handler still
answers 200, with the literal body `# Metric Scraper disabled`. Two things must be true before a
metrics assertion means anything:

1. `io.koraframework:micrometer-module` is on the application's runtime classpath — that is what
   supplies the Prometheus registry, the JVM binders and the `kora_up` gauge.
2. **Component metrics are off by default in 2.0** (`telemetry.metrics.enabled` defaults to
   `false`). Enable them per component in the container's config:

```hocon
httpServer {
  port = 8080
  system.port = 8085
  telemetry.metrics.enabled = true
}
```

Then assert on real series, not on the status code:

```java
var response = HttpClient.newHttpClient().send(
        HttpRequest.newBuilder().GET().uri(APP.getSystemURI().resolve("/metrics")).build(),
        HttpResponse.BodyHandlers.ofString());

assertEquals(200, response.statusCode());
assertFalse(response.body().contains("Metric Scraper disabled"));
assertTrue(response.body().contains("kora_up"));                          // registry is live
assertTrue(response.body().contains("http_server_request_duration"));     // component metrics on
```

Note that tracing, which defaults to `true` elsewhere, is overridden to `false` under
`httpServer.system` — the system server does not trace its own probe traffic.

---

## GraalVM native images

Black-box tests are the cheapest way to prove a native image actually works, because
**a green `nativeCompile` proves nothing**: missing or misnamed reachability metadata builds
cleanly and fails only at runtime. Treat a native module as verified only when all five hold:

1. the binary starts and is still alive a few seconds later;
2. `GET /system/readiness` → **200** — the graph initialised in full;
3. `GET /metrics` returns real series, not the `# Metric Scraper disabled` stub and not a 500;
4. the module's scenario runs against a **real** dependency (database, broker), not mocks;
5. no stack traces in the startup log — often the only sign a subsystem silently dropped out.

The same `AppContainer` drives it; only the `Dockerfile` differs (multi-stage
`ghcr.io/graalvm/native-image-community:25` builder → slim runtime, exposing 8080 and 8085). Native
startup is slower than JVM startup, so raise the timeout — the migrated native examples allow
50–60 s. Full Dockerfile in [docker-reference.md](references/docker-reference.md#graalvm-native-image-dockerfile).

Application-owned metadata file names are load-bearing: only `reflect-config.json`,
`resource-config.json`, `proxy-config.json`, `serialization-config.json`, `jni-config.json`,
`native-image.properties` and `reachability-metadata.json` are read. `reflection-config.json` —
with the extra `ion` — is silently ignored, and the build stays green.

---

## What's in references/

| Document | Use it for |
|----------|-----------|
| [blackbox-integration-reference.md](references/blackbox-integration-reference.md) | Full AppContainer pattern, CRUD, RestAssured, Kafka, error scenarios, Awaitility, probe/metrics assertions, DB verification |
| [testcontainers-reference.md](references/testcontainers-reference.md) | Testcontainers coordinates and API: PostgreSQL, Kafka, wait strategies, container lifecycle |
| [docker-reference.md](references/docker-reference.md) | Dockerfile strategies (JRE, multi-stage, GraalVM native), `APP_IMAGE` reuse, CI/CD |
| [docker-compose-reference.md](references/docker-compose-reference.md) | Compose as a local/CI environment, health checks, multi-service stacks |

## What's in assets/

| Asset | Purpose |
|-------|---------|
| `BlackBoxTest.java.template` / `.kt.template` | HttpClient black-box test skeleton (AppContainer + PostgreSQL on `Network.SHARED`) |
| `BlackBoxTest-RestAssured.java.template` / `.kt.template` | RestAssured DSL black-box test skeleton |
| `Dockerfile.template` | Runtime image over a prebuilt `distTar` archive |
| `Dockerfile.self-build.template` / `-kotlin.template` | Multi-stage build inside Docker (no JDK on the host) |

---

## When to use vs NOT

**Use black-box when:**
- Validating the real Docker artifact end-to-end (routing + JSON + validation + migrations + probes)
- Verifying HTTP contracts: status codes, headers, JSON bodies a client actually sees
- Proving a **GraalVM native image** is more than a green build
- Testing async side effects (Kafka consumer, scheduled jobs) observed through the API
- Reproducing deployment problems: wrong ports, stale config keys, broken packaging, missing env

**Do NOT use black-box (use `kora-testing-junit-java` / `-kotlin`) when:**
- You want fast feedback on business logic in a single component
- You need to mock a collaborator with `@TestComponent` + Mockito/MockK
- You need to inject into the Kora graph or override config with `KoraConfigModification`

---

## Core patterns

- **Readiness gating:** `Wait.forHttp("/system/readiness").forPort(8085).forStatusCode(200)`. The
  probe lives on the **system** server. Never `Wait.forListeningPort()`, never `Wait.forLogMessage`.
- **Both ports exposed:** `withExposedPorts(8080, 8085)` — the wait strategy needs 8085 mapped, and
  `/metrics` assertions need it too.
- **Shared network:** every container on `Network.SHARED` with `withNetworkAliases("postgres")`; the
  app reaches it as `postgres:5432` (container port), while the test uses `getMappedPort(...)`.
- **Config injection:** `withEnv("POSTGRES_JDBC_URL", ...)` — names must match the `${VAR}`
  substitution keys in the application's config, not magic Testcontainers names.
- **Startup ordering:** `.dependsOn(POSTGRES)` so infrastructure starts first.
- **CI image reuse:** branch the `AppContainer` constructor on an env var (`APP_IMAGE`) to skip the
  Dockerfile build — see [docker-reference.md](references/docker-reference.md).
- **Async assertions:** wrap polling reads in Awaitility `await().atMost(...).untilAsserted(...)`.

---

## Common pitfalls

| Symptom | Cause | Fix |
|---------|-------|-----|
| Container never becomes ready | Waiting on the public port, `forListeningPort()`, or a log line | `Wait.forHttp("/system/readiness").forPort(8085).forStatusCode(200)` |
| Readiness wait times out, app log looks healthy | 8085 not in `withExposedPorts` | Expose both `8080` and `8085` |
| Probes/scrapers hit nothing, app is "green" | Stale `publicApiHttpPort` / `privateApiHttpPort` silently ignored | Rename to `httpServer.port` / `httpServer.system.port` |
| `UnsupportedClassVersionError` on container start | Base image below JRE 25 | `eclipse-temurin:25-jre-jammy` |
| `application.tar` not found at image build | `distTar` did not run | `test { dependsOn ":app:distTar" }`, and `COPY build/distributions/*.tar` needs `distTar`, not `installDist` |
| `Config expected value, but got null at path: 'ROOT.jdbc.username'` | 1.x `db { ... }` section | Rename the section to `jdbc { ... }` |
| App cannot reach the DB | Per-test `Network.newNetwork()`, or the host-mapped port used inside the network | `Network.SHARED` + alias, container port `5432` |
| `/metrics` returns `# Metric Scraper disabled` | No `micrometer-module` in the app | Add `io.koraframework:micrometer-module` |
| `/metrics` is 200 but has no `http_server_*` series | `telemetry.metrics.enabled` defaults to `false` | Set `httpServer.telemetry.metrics.enabled = true` |
| Native image builds green, dies at runtime | Metadata file named `reflection-config.json` | Rename to `reflect-config.json`, then re-run the 5-point checklist |
| Duplicate-key failures across tests | Shared static container + fixed test data | Generate unique values (unique emails) |
| Trying `@KoraAppTest` with `GenericContainer` | Mixing in-process and black-box paradigms | Pick one: black-box runs the image, `@KoraAppTest` runs in-process |
