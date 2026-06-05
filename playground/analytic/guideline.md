# Kora Journal — PetClinic API Implementation

Journal of fixes, clarifications, and improvements made during PetClinic API implementation.

---

## 2026-06-05 — PetClinic API Implementation Issues

### 1. Wrong Kora version in build.gradle

**Context:** Setting up PetClinic project build.gradle with Kora Framework dependencies

**Problem:** Used non-existent versions `1.15.0` and `1.15.1` instead of correct `1.2.15`. This caused all dependencies to fail resolution.

**Solution:** Use `koraVersion = '1.2.15'` and check Maven Central for available versions before specifying.

**Files affected:**
- `playground/build.gradle`

**Author:** @anton-kurako

---

### 2. Wrong artifact names for Kora modules

**Context:** Adding Kora module dependencies

**Problem:** Used incorrect artifact names:
- `ru.tinkoff.kora:validation` → should be `ru.tinkoff.kora:validation-module`
- `ru.tinkoff.kora:resilient` → should be `ru.tinkoff.kora:resilient-kora`
- `ru.tinkoff.kora:scheduling` → should be `ru.tinkoff.kora:scheduling-jdk`
- `ru.tinkoff.kora:telemetry-micrometer` → should be `ru.tinkoff.kora:micrometer-module`
- `ru.tinkoff.kora:json-jackson` → should be `ru.tinkoff.kora:json-module`

**Solution:** Check kora-examples for correct artifact names.

**Files affected:**
- `playground/build.gradle`
- `kora-bootstrap/SKILL.md` (needs update with correct artifact names)

**Author:** @anton-kurako

---

### 3. Wrong Repository annotation import

**Context:** Creating JDBC repositories

**Problem:** Used `@Repository` from wrong package. Tried:
- `ru.tinkoff.kora.database.common.annotation.Repository`
- `ru.tinkoff.kora.database.jdbc.Repository`

**Solution:** Correct import is `ru.tinkoff.kora.database.common.annotation.Repository` (same as in kora-examples).

**Files affected:**
- `playground/src/main/java/ru/tbank/petclinic/repository/*.java`
- `kora-database/SKILL.md` (needs example update)

**Author:** @anton-kurako

---

### 4. Wrong EntityJdbc annotation format

**Context:** Creating entity classes for JDBC repository

**Problem:** Used `@EntityJdbc("table_name")` with table name parameter and wrong import:
- Wrong: `import ru.tinkoff.kora.database.common.annotation.EntityJdbc`
- Wrong: `@EntityJdbc("pet_type")`

**Solution:** Correct format:
- Import: `import ru.tinkoff.kora.database.jdbc.EntityJdbc`
- Annotation: `@EntityJdbc` (no parameters, table name inferred from record name)

**Files affected:**
- `playground/src/main/java/ru/tbank/petclinic/entity/*.java`
- `kora-database/SKILL.md` (needs example update)

**Author:** @anton-kurako

---

### 5. Kora openapi-generator plugin not found

**Context:** Configuring OpenAPI code generation with Kora generator

**Problem:** Plugin `ru.kora.openapi.generator` version `1.2.15` not found in Gradle Plugin Portal. The `openapi-generator` artifact is only available as buildscript classpath dependency.

**Solution:** Use standard `org.openapi.generator` plugin version `7.14.0` with `generatorName = "kora"` and add buildscript dependency:
```groovy
buildscript {
    dependencies {
        classpath("ru.tinkoff.kora:openapi-generator:1.2.15")
    }
}
```

**Files affected:**
- `playground/build.gradle`
- `kora-openapi/SKILL.md` (already has correct example)

**Author:** @anton-kurako

---

### 6. Generated models use different constructor signature

**Context:** Writing mappers for generated OpenAPI models

**Problem:** Kora OpenAPI generator creates models as records with:
- Compact constructor with subset of fields: `new Pet(id, type, visits)`
- Full constructor via builder pattern: `new Pet(name, birthDate, typeId, id, type, visits)`
- With-methods for fluent updates: `.withName()`, `.withBirthDate()`, etc.

Initial mappers used wrong constructor signatures causing compilation errors.

**Solution:** Use compact constructor + with-methods pattern:
```java
return new Pet(entity.id(), null, Collections.emptyList())
    .withName(entity.name())
    .withBirthDate(entity.birthDate())
    .withTypeId(entity.typeId());
```

**Files affected:**
- `playground/src/main/java/ru/tbank/petclinic/mapper/*.java`
- `kora-openapi/SKILL.md` (needs mapper example)

**Author:** @anton-kurako

---

### 7. JsonReader.nextString() API change

**Context:** Creating custom JsonReader for URI type

**Problem:** Used `parser.nextString(null)` which doesn't exist in Kora's JsonParser API.

**Solution:** Use `parser.nextString()` without arguments or `parser.getText()` after checking token type:
```java
default JsonReader<URI> uriJsonReader() {
    return parser -> {
        var token = parser.currentToken();
        if (token == com.fasterxml.jackson.core.JsonToken.VALUE_NULL) {
            parser.nextToken();
            return null;
        }
        var value = parser.getText();
        parser.nextToken();
        return (value == null) ? null : URI.create(value);
    };
}
```

**Files affected:**
- `playground/src/main/java/ru/tbank/petclinic/JsonModule.java`
- `kora-json/SKILL.md` (needs custom reader example)

**Author:** @anton-kurako

---

### 8. OpenAPI spec missing response body for 201 status

**Context:** Implementing POST endpoints that return 201 Created

**Problem:** OpenAPI spec for `/owner/{ownerId}/pet` and `/owner/{ownerId}/pet/{petId}/visit` doesn't define response body schema for 201 status. Generated `AddPet201ApiResponse` and `AddVisit201ApiResponse` don't accept content parameter.

**Solution:** Either:
1. Fix OpenAPI spec to include response schema for 201
2. Use empty response and let client fetch created resource

For this implementation, used empty response as per generated code.

**Files affected:**
- `playground/spec-openapi.yaml` (needs fix)
- `playground/src/main/java/ru/tbank/petclinic/api/*ApiDelegateImpl.java`

**Author:** @anton-kurako

---

### 9. Gradle 9 shadowJar conflict with application plugin

**Context:** Building fat JAR with Shadow plugin

**Problem:** Gradle 9 + Shadow 9.0.0 has conflict between `startScripts` task from application plugin and shadowJar task.

**Solution:** Either:
1. Disable distribution tasks: `tasks.named('distTar') { enabled = false }`
2. Add explicit dependency: `tasks.named('startScripts') { dependsOn shadowJar }`

**Files affected:**
- `playground/build.gradle`
- `kora-bootstrap/SKILL.md` (needs Gradle 9 note)

**Author:** @anton-kurako

---

### 10. URI type in generated RestError requires custom JsonWriter

**Context:** Using generated RestError model with URI field

**Problem:** Kora JSON module doesn't have built-in JsonWriter/JsonReader for `java.net.URI`. Generated RestError model uses URI for `path` field.

**Solution:** Create custom JsonModule with URI reader/writer:
```java
@Component
public interface JsonModule {
    default JsonWriter<URI> uriJsonWriter() { ... }
    default JsonReader<URI> uriJsonReader() { ... }
}
```

And include it in application graph.

**Files affected:**
- `playground/src/main/java/ru/tbank/petclinic/JsonModule.java`
- `playground/src/main/java/ru/tbank/petclinic/PetClinicApplication.java`
- `kora-json/SKILL.md` (needs URI example)

**Author:** @anton-kurako

---

## Summary

| Issue | Category | Status |
|-------|----------|--------|
| Wrong Kora version | Dependencies | Fixed |
| Wrong artifact names | Dependencies | Fixed |
| Wrong Repository annotation | Code | Fixed |
| Wrong EntityJdbc format | Code | Fixed |
| openapi-generator plugin | Build | Fixed |
| Model constructor signature | Code | Fixed |
| JsonReader API | Code | Fixed |
| Missing response body | OpenAPI Spec | Workaround |
| ShadowJar conflict | Build | Fixed |
| URI JsonWriter | Code | Fixed |

**Total entries:** 10
**Files to update in KORA SKILL:** 5 (kora-bootstrap, kora-database, kora-openapi, kora-json)
