# Docker Compose Multi-Container Testing Reference

**Purpose:** Testing with multiple containers using Docker Compose.

## Contents

1. [Overview](#overview)
2. [When to use Docker Compose](#when-to-use-docker-compose)
3. [Basic setup (App + PostgreSQL)](#basic-docker-compose-setup)
4. [App + PostgreSQL + Kafka](#app--postgresql--kafka)
5. [App + Cassandra](#app--cassandra)
6. [Multiple microservices](#multiple-microservices)
7. [Test scripts](#test-scripts)
8. [Test implementation](#test-implementation)
9. [Health checks](#health-checks)
10. [Best practices](#best-practices)
11. [Troubleshooting](#troubleshooting)

---

## Overview

Docker Compose enables orchestrating multiple containers for complex integration scenarios:
- Application + PostgreSQL + Kafka
- Application + Redis + Cassandra
- Multiple microservices testing

---

## When to Use Docker Compose

**Use Docker Compose when:**
- Testing multiple services together
- Complex container networking required
- Reproducing production-like environment
- Local development environment

**Use Testcontainers when:**
- Unit/integration tests in CI/CD
- Per-test isolation needed
- Faster test execution required

---

## Basic Docker Compose Setup

### App + PostgreSQL

```yaml
# docker-compose.test.yml
version: '3.8'

services:
  app:
    build:
      context: .
      dockerfile: Dockerfile
    ports:
      - "8080:8080"
      - "8085:8085"
    environment:
      - APP_CONFIG_DATABASE_URL=jdbc:postgresql://postgres:5432/testdb
      - APP_CONFIG_DATABASE_USER=postgres
      - APP_CONFIG_DATABASE_PASSWORD=postgres
    depends_on:
      postgres:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8085/system/readiness"]
      interval: 10s
      timeout: 5s
      retries: 5
      start_period: 30s

  postgres:
    image: postgres:15-alpine
    environment:
      - POSTGRES_DB=testdb
      - POSTGRES_USER=postgres
      - POSTGRES_PASSWORD=postgres
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./src/test/resources/db/migration:/docker-entrypoint-initdb.d
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 5s
      timeout: 5s
      retries: 5

volumes:
  postgres_data:
```

### Running Tests

```bash
# Start all services
docker-compose -f docker-compose.test.yml up -d

# Wait for app to be ready
sleep 30

# Run tests
./gradlew test

# Stop services
docker-compose -f docker-compose.test.yml down -v
```

---

## App + PostgreSQL + Kafka

```yaml
# docker-compose.test.yml
version: '3.8'

services:
  app:
    build:
      context: .
      dockerfile: Dockerfile
    ports:
      - "8080:8080"
      - "8085:8085"
    environment:
      - APP_CONFIG_DATABASE_URL=jdbc:postgresql://postgres:5432/testdb
      - APP_CONFIG_DATABASE_USER=postgres
      - APP_CONFIG_DATABASE_PASSWORD=postgres
      - APP_CONFIG_KAFKA_BOOTSTRAP_SERVERS=kafka:9092
    depends_on:
      postgres:
        condition: service_healthy
      kafka:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8085/system/readiness"]
      interval: 10s
      timeout: 5s
      retries: 5
      start_period: 30s

  postgres:
    image: postgres:15-alpine
    environment:
      - POSTGRES_DB=testdb
      - POSTGRES_USER=postgres
      - POSTGRES_PASSWORD=postgres
    volumes:
      - ./src/test/resources/db/migration:/docker-entrypoint-initdb.d
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 5s
      timeout: 5s
      retries: 5

  kafka:
    image: apache/kafka:3.8.0
    ports:
      - "9092:9092"
    environment:
      - KAFKA_NODE_ID=1
      - KAFKA_PROCESS_ROLES=broker,controller
      - KAFKA_CONTROLLER_QUORUM_VOTERS=1@kafka:9093
      - KAFKA_LISTENERS=PLAINTEXT://:9092,CONTROLLER://:9093
      - KAFKA_ADVERTISED_LISTENERS=PLAINTEXT://kafka:9092
      - KAFKA_LISTENER_SECURITY_PROTOCOL_MAP=CONTROLLER:PLAINTEXT,PLAINTEXT:PLAINTEXT
      - KAFKA_CONTROLLER_LISTENER_NAMES=CONTROLLER
      - KAFKA_OFFSETS_TOPIC_REPLICATION_FACTOR=1
    healthcheck:
      test: ["CMD", "kafka-broker-api-versions", "--bootstrap-server", "kafka:9092"]
      interval: 10s
      timeout: 5s
      retries: 5
```

---

## App + Cassandra

```yaml
# docker-compose.test.yml
version: '3.8'

services:
  app:
    build:
      context: .
      dockerfile: Dockerfile
    ports:
      - "8080:8080"
      - "8085:8085"
    environment:
      - APP_CONFIG_CASSANDRA_CONTACT_POINTS=cassandra:9042
      - APP_CONFIG_CASSANDRA_USER=cassandra
      - APP_CONFIG_CASSANDRA_PASSWORD=cassandra
      - APP_CONFIG_CASSANDRA_KEYSPACE=test_keyspace
    depends_on:
      cassandra:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8085/system/readiness"]
      interval: 10s
      timeout: 5s
      retries: 5
      start_period: 60s

  cassandra:
    image: cassandra:5.0
    ports:
      - "9042:9042"
    environment:
      - CASSANDRA_DC=datacenter1
      - CASSANDRA_RACK=rack1
      - HEAP_NEWSIZE=128M
      - MAX_HEAP_SIZE=1024M
    volumes:
      - cassandra_data:/var/lib/cassandra
      - ./src/test/resources/migrations:/cassandra-init
    healthcheck:
      test: ["CMD", "cqlsh", "-e", "DESCRIBE KEYSPACES"]
      interval: 10s
      timeout: 5s
      retries: 10

volumes:
  cassandra_data:
```

---

## Multiple Microservices

```yaml
# docker-compose.test.yml
version: '3.8'

services:
  # API Gateway
  gateway:
    build:
      context: ./gateway
      dockerfile: Dockerfile
    ports:
      - "8080:8080"
    depends_on:
      - user-service
      - order-service

  # User Service
  user-service:
    build:
      context: ./user-service
      dockerfile: Dockerfile
    environment:
      - DATABASE_URL=jdbc:postgresql://postgres-users:5432/users
    depends_on:
      - postgres-users

  # Order Service
  order-service:
    build:
      context: ./order-service
      dockerfile: Dockerfile
    environment:
      - DATABASE_URL=jdbc:postgresql://postgres-orders:5432/orders
      - KAFKA_BOOTSTRAP_SERVERS=kafka:9092
    depends_on:
      - postgres-orders
      - kafka

  # Databases
  postgres-users:
    image: postgres:15-alpine
    environment:
      - POSTGRES_DB=users
      - POSTGRES_USER=postgres
      - POSTGRES_PASSWORD=postgres

  postgres-orders:
    image: postgres:15-alpine
    environment:
      - POSTGRES_DB=orders
      - POSTGRES_USER=postgres
      - POSTGRES_PASSWORD=postgres

  kafka:
    image: apache/kafka:3.8.0
    environment:
      - KAFKA_PROCESS_ROLES=broker,controller
      - KAFKA_CONTROLLER_QUORUM_VOTERS=1@kafka:9093
      - KAFKA_LISTENERS=PLAINTEXT://:9092,CONTROLLER://:9093
      - KAFKA_ADVERTISED_LISTENERS=PLAINTEXT://kafka:9092
```

---

## Test Scripts

### Bash Test Runner

```bash
#!/bin/bash
# run-tests.sh

set -e

echo "Starting Docker Compose services..."
docker-compose -f docker-compose.test.yml up -d

echo "Waiting for services to be ready..."
sleep 30

# Wait for app readiness
max_attempts=30
attempt=0
while [ $attempt -lt $max_attempts ]; do
    if curl -f http://localhost:8085/system/readiness 2>/dev/null; then
        echo "App is ready!"
        break
    fi
    echo "Waiting for app... ($attempt/$max_attempts)"
    sleep 5
    attempt=$((attempt + 1))
done

if [ $attempt -eq $max_attempts ]; then
    echo "App failed to start"
    docker-compose -f docker-compose.test.yml logs app
    docker-compose -f docker-compose.test.yml down -v
    exit 1
fi

echo "Running tests..."
./gradlew test
TEST_RESULT=$?

echo "Stopping services..."
docker-compose -f docker-compose.test.yml down -v

exit $TEST_RESULT
```

### Gradle Integration

```groovy
// build.gradle
tasks.register('dockerComposeUp', Exec) {
    commandLine 'docker-compose', '-f', 'docker-compose.test.yml', 'up', '-d'
}

tasks.register('dockerComposeDown', Exec) {
    commandLine 'docker-compose', '-f', 'docker-compose.test.yml', 'down', '-v'
}

tasks.register('waitForApp', Exec) {
    dependsOn dockerComposeUp
    commandLine 'bash', '-c', '''
        for i in {1..30}; do
            if curl -f http://localhost:8085/system/readiness 2>/dev/null; then
                exit 0
            fi
            sleep 5
        done
        exit 1
    '''
}

tasks.register('dockerComposeTest', Test) {
    dependsOn waitForApp
    finalizedBy dockerComposeDown
    
    // Pass app URL to tests
    systemProperty 'test.app.url', 'http://localhost:8080'
}
```

---

## Test Implementation

### Using System Properties

```java
class DockerComposeApiTest {
    
    private static final String APP_URL = System.getProperty("test.app.url", "http://localhost:8080");
    private final HttpClient httpClient = HttpClient.newHttpClient();

    @Test
    void shouldCreateUser() throws Exception {
        var requestBody = new JSONObject()
            .put("email", "test@example.com");

        var request = HttpRequest.newBuilder()
            .POST(HttpRequest.BodyPublishers.ofString(requestBody.toString()))
            .uri(URI.create(APP_URL + "/api/users"))
            .header("Content-Type", "application/json")
            .timeout(Duration.ofSeconds(5))
            .build();

        var response = httpClient.send(request, HttpResponse.BodyHandlers.ofString());
        assertEquals(200, response.statusCode());
    }
}
```

### Using Testcontainers with Compose

```java
import org.testcontainers.containers.DockerComposeContainer;
import org.junit.jupiter.api.*;

class DockerComposeTest {

    private static final DockerComposeContainer<?> compose = 
        new DockerComposeContainer<>(new File("docker-compose.test.yml"))
            .withExposedService("app", 8080, Wait.forHttp("/system/readiness").forPort(8085))
            .withExposedService("postgres", 5432)
            .withLocalCompose(true);

    @BeforeAll
    static void beforeAll() {
        compose.start();
    }

    @AfterAll
    static void afterAll() {
        compose.stop();
    }

    @Test
    void shouldWorkWithCompose() {
        String appHost = compose.getServiceHost("app", 8080);
        int appPort = compose.getServicePort("app", 8080);
        
        // Use appHost:appPort for HTTP requests
    }
}
```

---

## Health Checks

### Application Health Check

```yaml
healthcheck:
  test: ["CMD", "curl", "-f", "http://localhost:8085/system/readiness"]
  interval: 10s
  timeout: 5s
  retries: 5
  start_period: 30s
```

### PostgreSQL Health Check

```yaml
healthcheck:
  test: ["CMD-SHELL", "pg_isready -U postgres"]
  interval: 5s
  timeout: 5s
  retries: 5
```

### Kafka Health Check

```yaml
healthcheck:
  test: ["CMD", "kafka-broker-api-versions", "--bootstrap-server", "localhost:9092"]
  interval: 10s
  timeout: 5s
  retries: 5
```

### Cassandra Health Check

```yaml
healthcheck:
  test: ["CMD", "cqlsh", "-e", "DESCRIBE KEYSPACES"]
  interval: 10s
  timeout: 5s
  retries: 10
```

---

## Environment Profiles

### Development

```yaml
# docker-compose.dev.yml
version: '3.8'

services:
  app:
    build:
      context: .
      dockerfile: Dockerfile
    environment:
      - APP_CONFIG_LOG_LEVEL=DEBUG
    ports:
      - "8080:8080"
      - "8085:8085"
    volumes:
      - ./application.conf:/app/config/application.conf
```

### CI/CD

```yaml
# docker-compose.ci.yml
version: '3.8'

services:
  app:
    image: ${APP_IMAGE}
    environment:
      - APP_CONFIG_LOG_LEVEL=INFO
    # No volumes, use immutable image
```

---

## Best Practices

1. **Use health checks** — ensure services are ready before tests
2. **Isolate test data** — use `-v` flag to remove volumes after tests
3. **Pin image versions** — `postgres:15-alpine` not `postgres:latest`
4. **Use depends_on with conditions** — `condition: service_healthy`
5. **Set timeouts** — `start_period` for slow-starting services
6. **Clean up** — always run `down -v` after tests

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| Services won't start | Check `docker-compose logs <service>` |
| Health check fails | Increase `start_period`, verify endpoint |
| Port conflicts | Use different ports or remove port mappings |
| Network issues | Verify service names match DNS in compose |

---

## Related

- [testcontainers-reference.md](testcontainers-reference.md) — Standard Testcontainers usage
- [blackbox-integration-reference.md](blackbox-integration-reference.md) — E2E patterns
