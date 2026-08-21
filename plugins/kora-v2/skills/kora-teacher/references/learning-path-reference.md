# Kora Learning Path — Complete Reference

**Version:** 1.x | **Languages:** Java 25+, Kotlin 1.9+ | **Gradle:** 9+

---

## Phase 1: Foundations

### 1. Getting Started
- **Guide:** `getting-started.md`
- **Guide App:** `kora-java-guide-getting-started-app`
- **Concepts:** @KoraApp, main(), KoraApplication.run(), minimal service

### 2. Dependency Injection (Introduction)
- **Guide:** `dependency-injection-introduction.md`
- **Guide App:** `kora-java-guide-dependency-injection-introduction-app`
- **Concepts:** @Component, constructor injection, final fields

### 3. Dependency Injection (Advanced)
- **Guide:** `dependency-injection.md`
- **Guide App:** `kora-java-guide-dependency-injection`
- **Concepts:** @Module, @Tag, All<T>, ValueOf, lazy dependencies

### 4. Configuration
- **Guide:** `config-hocon.md` OR `config-yaml.md`
- **Guide App:** `kora-java-guide-config-hocon-app` / `kora-java-guide-config-yaml-app`
- **Concepts:** @ConfigSource, typed config, environment substitution

---

## Phase 2: HTTP Services

### 5. HTTP Server (Basic)
- **Guide:** `http-server.md`
- **Guide App:** `kora-java-guide-http-server-app`
- **Concepts:** @HttpController, @HttpRoute, @Path, @Query, @Header

### 6. HTTP Server (Advanced)
- **Guide:** `http-server-advanced.md`
- **Guide App:** `kora-java-guide-http-server-advanced-app`
- **Concepts:** @Json, HttpResponseEntity, interceptors, error handling

### 7. HTTP Client (Basic)
- **Guide:** `http-client.md`
- **Guide App:** `kora-java-guide-http-client-app`
- **Concepts:** @HttpClient, declarative interfaces

### 8. HTTP Client (Advanced)
- **Guide:** `http-client-advanced.md`
- **Guide App:** `kora-java-guide-http-client-advanced-app`
- **Concepts:** Interceptors, retries, error handling

### 9. OpenAPI Server
- **Guide:** `openapi-http-server.md`
- **Guide App:** `kora-java-guide-openapi-http-server-app`
- **Concepts:** OpenAPI codegen, delegates, controllers

### 10. OpenAPI Client
- **Guide:** `openapi-http-client.md`
- **Guide App:** `kora-java-guide-openapi-http-client-app`
- **Concepts:** Typed API clients, codegen

---

## Phase 3: Data & Messaging

### 11. Database JDBC (Basic)
- **Guide:** `database-jdbc.md`
- **Guide App:** `kora-java-guide-database-jdbc-app`
- **Concepts:** @Repository, @Query, @EntityJdbc, ResultSet mapping

### 12. Database JDBC (Advanced)
- **Guide:** `database-jdbc-advanced.md`
- **Guide App:** `kora-java-guide-database-jdbc-advanced-app`
- **Concepts:** Transactions, Hikari pooling, batch operations

### 13. Database Cassandra
- **Guide:** `database-cassandra.md`
- **Guide App:** `kora-java-guide-database-cassandra-app`
- **Concepts:** @EntityCassandra, @UDT, CQL, profiles

### 14. Kafka Messaging
- **Guide:** `messaging-kafka.md`
- **Guide App:** `kora-java-guide-messaging-kafka-app`
- **Concepts:** @KafkaListener, @KafkaPublisher, batch, error handling

---

## Phase 4: Resilience & Observability

### 15. Resilience
- **Guide:** `resilient.md`
- **Guide App:** `kora-java-guide-resilient-app`
- **Concepts:** @Retry, @CircuitBreaker, @Timeout, @Fallback

### 16. Cache (Basic)
- **Guide:** `cache.md`
- **Guide App:** `kora-java-guide-cache-app`
- **Concepts:** @Cacheable, @CachePut, @CacheInvalidate, Caffeine/Redis

### 17. Cache (Multi-Level)
- **Guide:** `cache-multi-level.md`
- **Guide App:** `kora-java-guide-cache-multi-level-app`
- **Concepts:** Multi-level cache stacks, cache hierarchies

### 18. Observability
- **Guide:** `observability.md`
- **Guide App:** `kora-java-guide-observability-app`
- **Concepts:** Metrics, tracing, logging, probes

### 19. Validation
- **Guide:** `validation.md`
- **Guide App:** `kora-java-guide-validation-app`
- **Concepts:** @Valid, @Validate, JSR-380 constraints

---

## Phase 5: Advanced Topics

### 20. gRPC Server
- **Guide:** `grpc-server.md`
- **Guide App:** `kora-java-guide-grpc-server-app`
- **Concepts:** Protobuf, gRPC handlers, streaming

### 21. gRPC Client
- **Guide:** `grpc-client.md`
- **Guide App:** `kora-java-guide-grpc-client-app`
- **Concepts:** gRPC stubs, interceptors, deadlines

### 22. S3 Object Storage
- **Guide:** `s3.md`
- **Guide App:** `kora-java-guide-s3-app`
- **Concepts:** @S3.Client, multipart uploads, presigned URLs

### 23. Testing (JUnit)
- **Guide:** `testing-junit.md`
- **Guide App:** `kora-java-guide-testing-junit-app`
- **Concepts:** @KoraAppTest, @TestComponent, mocks

### 24. Testing (Integration)
- **Guide:** `testing-integration.md`
- **Guide App:** `kora-java-guide-testing-integration-app`
- **Concepts:** Testcontainers, E2E tests, Docker

### 25. Testing (Black-Box)
- **Guide:** `testing-black-box.md`
- **Guide App:** `kora-java-guide-testing-black-box-app`
- **Concepts:** AppContainer, black-box E2E, Docker compose

---

## Kotlin Equivalents

All guide apps have Kotlin versions. Replace `java` → `kotlin` in app names:
- `kora-java-guide-http-server-app` → `kora-kotlin-guide-http-server-app`
- `kora-java-guide-database-jdbc-app` → `kora-kotlin-guide-database-jdbc-app`
- etc.

Kotlin guides use KSP (Kotlin Symbol Processing) instead of annotation processors.
