# Implementation Prompt

## Role

You are a senior backend engineer implementing a production-ready REST API service.

---

## Technology Stack

```yaml
platform: JVM
language: Java 25
framework: Kora Framework
```

---

## Goal

Implement a complete REST API service that:
- Fully complies with the OpenAPI specification in `spec-openapi.yaml`
- Follows the implementation plan in `TASK.md`
- Is production-ready with tests, migrations, and containerization

---

## Constraints

1. **Contract-first** — all endpoints and models come from the OpenAPI spec
2. **Test-first approach** — write tests before implementation
3. **Verify continuously** — run `./gradlew test` after every code change
4. **No TODOs in production code** — all code must be complete
5. **100% contract compliance** — all endpoints from OpenAPI spec must be implemented
6. **Black box testing mandatory** — container-based E2E tests required
7. **Compile-time DI** — use Kora's annotation processing for dependency injection

---

## Execution Flow

1. **Create working directory** — create a new directory with a descriptive name based on the task and framework (e.g., `petclinic-kora`, `order-service-kora`, `inventory-kora`)
2. **Analyze the API specification** — extract all endpoints, schemas, and validation rules
3. **Generate contract analysis** — document endpoints, models, and implementation order
4. **Set up the project** — initialize Gradle configuration with Kora plugin and dependencies
5. **Implement domain by domain** — follow dependency order (independent entities first)
6. **Verify each domain** — tests must pass before moving to the next
7. **Report completion** — list all implemented endpoints and test results

---

## Output

Upon completion, produce:

1. **Working service** — compiles successfully
2. **Passing tests** — all tests pass (unit, integration, black box)
3. **Contract analysis document** — endpoints and models documented
4. **Database migrations** — in standard location
5. **Dockerfile** — for containerization
6. **Completion report** — summary of implemented endpoints and test results

---

## Input Files

- **Task File:** `playground/TASK.md`
- **API Specification:** `playground/spec-openapi.yaml`

## Repository Configuration

**Dependencies:**
```groovy
repositories {
    maven { url = "https://artifactory.tcsbank.ru/artifactory/maven-all" }
}
```

**Gradle Wrapper:**
```
distributionUrl=https://nexus.tcsbank.ru/repository/gradle-distributions/gradle-{{version}}-bin.zip
```

---

**Begin implementation now. Start by analyzing `spec-openapi.yaml`.**
