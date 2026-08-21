# Docker for Kora Applications

**Source:** `.kora-agent/kora-docs/mkdocs/docs/en/guides/testing-black-box.md` (Dockerfile setup), `.kora-agent/kora-docs/mkdocs/docs/en/documentation/probes.md` (readiness/liveness paths)
**Example:** `.kora-agent/kora-examples/guides/java/kora-java-guide-database-jdbc-app/Dockerfile`

Building and running a packaged Kora application in Docker for black-box tests.

## Table of Contents

1. [Basic Dockerfile](#basic-dockerfile)
2. [Multi-stage Dockerfile](#multi-stage-dockerfile)
3. [Comparison of approaches](#comparison-of-approaches)
4. [Usage in CI/CD](#usage-in-cicd)
5. [Docker Compose for tests](#docker-compose-for-tests)

---

## Basic Dockerfile

**File:** `Dockerfile`

Uses the pre-built distribution from `build/distributions/`. Requires a prior build on the host.

```dockerfile
ARG RUN_IMAGE=eclipse-temurin:25-jre-jammy
FROM ${RUN_IMAGE}

ARG TARGET_DIR=/opt/app
ARG SOURCE_DIR=build/distributions

COPY $SOURCE_DIR/*.tar application.tar

RUN mkdir $TARGET_DIR && \
    tar -xf application.tar -C $TARGET_DIR && \
    rm application.tar

ARG DOCKER_USER=app
RUN groupadd -r $DOCKER_USER && useradd -rg $DOCKER_USER $DOCKER_USER
USER $DOCKER_USER

EXPOSE 8080/tcp
EXPOSE 8085/tcp

CMD [ "/opt/app/application/bin/application" ]
```

### Building the image

```bash
# 1. Build the distribution
./gradlew installDist

# 2. Build the Docker image
docker build -t myapp:1.0.0 .

# 3. Run
docker run -p 8080:8080 -p 8085:8085 myapp:1.0.0
```

### When to use

- Local development (fast rebuilds)
- CI/CD with Gradle caching
- When you need control over the JDK version used for the build

---

## Multi-stage Dockerfile

**File:** `Dockerfile.self-build` (Java) or `Dockerfile.self-build-kotlin` (Kotlin)

Builds inside Docker. No JDK/Gradle required on the host.

### For Java projects (JDK 25, Alpine)

```dockerfile
# Stage 1: Build (JDK 25, Alpine)
FROM gradle:9.5.1-jdk25-alpine AS build

WORKDIR /home/gradle/src

# Cache dependencies
COPY build.gradle* settings.gradle* gradle.properties* ./
COPY gradle/ ./gradle/
RUN gradle dependencies --no-daemon || true

# Build
COPY . .
RUN gradle installDist --no-daemon

# Stage 2: Runtime (JRE 25, Jammy)
FROM eclipse-temurin:25-jre-jammy

ARG TARGET_DIR=/opt/app
COPY --from=build /home/gradle/src/build/distributions/*.tar application.tar

RUN mkdir $TARGET_DIR && \
    tar -xf application.tar -C $TARGET_DIR && \
    rm application.tar

ARG DOCKER_USER=app
RUN groupadd -r $DOCKER_USER && useradd -rg $DOCKER_USER $DOCKER_USER
USER $DOCKER_USER

EXPOSE 8080/tcp
EXPOSE 8085/tcp

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8085/system/readiness || exit 1

CMD [ "/opt/app/application/bin/application" ]
```

### Building the image

```bash
# One command for everything
docker build -t myapp:1.0.0 -f Dockerfile.self-build .

# Run
docker run -p 8080:8080 -p 8085:8085 myapp:1.0.0
```

### When to use

- CI/CD without JDK/Gradle setup
- Reproducible builds
- Different JDK versions for build and runtime
- Teams without Java on local machines

### For Kotlin projects (JDK 17, Alpine)

```dockerfile
# Stage 1: Build (JDK 17, Alpine — recommended for Kotlin)
FROM gradle:9.5.1-jdk17-alpine AS build

# ... (same as the Java version)

# Stage 2: Runtime (JRE 25, Jammy — unified for Java and Kotlin)
FROM eclipse-temurin:25-jre-jammy
```

**Why JDK 17 for Kotlin:**
- Stable Kotlin compiler support
- Compatibility with most Kotlin libraries
- Recommended in the Kotlin documentation

---

## Comparison of approaches

| Characteristic | Basic | Multi-stage (Java) | Multi-stage (Kotlin) |
|----------------|-------|--------------------|----------------------|
| **Requires JDK on host** | Yes | No | No |
| **Requires Gradle on host** | Yes | No | No |
| **JDK for build** | Your JDK | JDK 25 (Alpine) | JDK 17 (Alpine) |
| **JRE for runtime** | Your choice | JRE 25 (Jammy) | JRE 25 (Jammy) |
| **Build speed (with cache)** | Fast | Slower | Slower |
| **Reproducibility** | Depends on host | Guaranteed | Guaranteed |
| **Build image size** | N/A | ~250 MB (gradle:9.5.1-jdk25-alpine) | ~220 MB (gradle:9.5.1-jdk17-alpine) |
| **Final image size** | ~200 MB | ~200 MB | ~200 MB |
| **CI/CD setup** | More complex | Simpler | Simpler |
| **Local development** | More convenient | Requires Docker | Requires Docker |

> **Why Jammy for runtime:**
> - Full glibc compatibility (native libraries, JDBC drivers)
> - More debugging tools (bash, curl, ps)
> - Larger image size (~70 MB vs Alpine)
> - Slower pull in CI/CD (~45 s vs ~10 s)

> **Advantages of Alpine:**
> - Image size smaller by **~85-90%** compared to Debian
> - Fast download in CI/CD
> - Smaller attack surface (minimal packages)
> - Possible compatibility issues (musl libc instead of glibc)

---

## Usage in CI/CD

### GitHub Actions

```yaml
name: Build and Test

on: [push, pull_request]

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Set up JDK 17
        uses: actions/setup-java@v4
        with:
          java-version: '17'
          distribution: 'temurin'
      
      - name: Build with Gradle
        run: ./gradlew installDist
      
      - name: Build Docker image
        run: docker build -t myapp:${{ github.sha }} .
      
      - name: Run tests with Testcontainers
        run: ./gradlew test
        env:
          APP_IMAGE: myapp:${{ github.sha }}
      
      - name: Push to registry
        if: github.ref == 'refs/heads/main'
        run: |
          docker tag myapp:${{ github.sha }} registry.example.com/myapp:latest
          docker push registry.example.com/myapp:latest
```

### GitLab CI

```yaml
stages:
  - build
  - test
  - deploy

build:
  stage: build
  image: gradle:8.5-jdk17
  script:
    - gradle installDist
    - docker build -t myapp:$CI_COMMIT_SHA .
  artifacts:
    paths:
      - build/distributions/

test:
  stage: test
  image: docker:24-dind
  services:
    - docker:24-dind
  script:
    - docker build -t myapp:$CI_COMMIT_SHA .
    - export APP_IMAGE=myapp:$CI_COMMIT_SHA
    - docker run --rm -v $(pwd):/app -w /app \
        -e APP_IMAGE \
        eclipse-temurin:25-jre-jammy \
        ./gradlew test

deploy:
  stage: deploy
  script:
    - docker push registry.example.com/myapp:$CI_COMMIT_SHA
  only:
    - main
```

---

## Docker Compose for tests

### App + PostgreSQL

```yaml
version: '3.8'

services:
  app:
    build:
      context: .
      dockerfile: Dockerfile.self-build
    ports:
      - "8080:8080"
      - "8085:8085"
    environment:
      - APP_CONFIG_DATABASE_URL=jdbc:postgresql://postgres:5432/myapp
      - APP_CONFIG_DATABASE_USER=app
      - APP_CONFIG_DATABASE_PASSWORD=secret
    depends_on:
      postgres:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8085/system/readiness"]
      interval: 10s
      timeout: 5s
      retries: 5

  postgres:
    image: postgres:15-alpine
    environment:
      - POSTGRES_DB=myapp
      - POSTGRES_USER=app
      - POSTGRES_PASSWORD=secret
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U app"]
      interval: 5s
      timeout: 5s
      retries: 5

volumes:
  postgres_data:
```

### App + Kafka

```yaml
version: '3.8'

services:
  app:
    build:
      context: .
      dockerfile: Dockerfile.self-build
    ports:
      - "8080:8080"
      - "8085:8085"
    environment:
      - APP_CONFIG_KAFKA_BOOTSTRAP_SERVERS=kafka:9092
    depends_on:
      kafka:
        condition: service_healthy

  kafka:
    image: apache/kafka:3.5.1
    ports:
      - "9092:9092"
    environment:
      - KAFKA_NODE_ID=1
      - KAFKA_PROCESS_ROLES=broker,controller
      - KAFKA_CONTROLLER_QUORUM_VOTERS=1@localhost:9093
      - KAFKA_LISTENERS=PLAINTEXT://:9092,CONTROLLER://:9093
      - KAFKA_ADVERTISED_LISTENERS=PLAINTEXT://localhost:9092
      - KAFKA_LISTENER_SECURITY_PROTOCOL_MAP=CONTROLLER:PLAINTEXT,PLAINTEXT:PLAINTEXT
      - KAFKA_CONTROLLER_LISTENER_NAMES=CONTROLLER
      - KAFKA_OFFSETS_TOPIC_REPLICATION_FACTOR=1
    healthcheck:
      test: ["CMD", "kafka-broker-api-versions", "--bootstrap-server", "localhost:9092"]
      interval: 10s
      timeout: 5s
      retries: 5
```

---

## .dockerignore

Always create `.dockerignore` to speed up builds:

```dockerfile
# Gradle
.gradle/
build/
!gradle/wrapper/

# IDE
.idea/
*.iml
.vscode/

# OS
.DS_Store
Thumbs.db

# Logs
*.log
logs/

# Test results
test-results/
build/reports/tests/

# Local config
application-local.conf
*.local
.env

# Docker (do not copy Dockerfile into the image)
Dockerfile*
.dockerignore
docker-compose*.yml

# Documentation
*.md
docs/

# Git
.git/
.gitignore
```

---

## Environment variables

| Variable | Description | Default |
|----------|-------------|---------|
| `RUN_IMAGE` | Runtime image | `eclipse-temurin:25-jre-jammy` |
| `TARGET_DIR` | Installation directory | `/opt/app` |
| `SOURCE_DIR` | Distribution directory | `build/distributions` |
| `DOCKER_USER` | User inside the container | `app` |

### Configuring RUN_IMAGE

```bash
# For ARM/M1 Mac
docker build --build-arg RUN_IMAGE=eclipse-temurin:25-jre-jammy-arm64 -t myapp:1.0.0 .

# For Alpine (smaller size)
docker build --build-arg RUN_IMAGE=eclipse-temurin:25-jre-alpine -t myapp:1.0.0 .
```

---

## Verifying the image

```bash
# Check exposed ports
docker inspect myapp:1.0.0 | grep -A 10 ExposedPorts

# Check health check
docker inspect myapp:1.0.0 | grep -A 5 Healthcheck

# Run and verify
docker run -d --name test myapp:1.0.0
docker logs -f test
curl http://localhost:8085/system/liveness
docker stop test && docker rm test
```
