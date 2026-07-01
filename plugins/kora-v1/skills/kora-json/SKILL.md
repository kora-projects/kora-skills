---
name: kora-json
description: "Compile-time, reflection-free JSON in Kora via the json-module and @Json. Generates JsonReader/JsonWriter at build time for records and data classes. Use when defining HTTP request/response DTOs, polymorphic JSON with sealed types (@JsonDiscriminatorField/@JsonDiscriminatorValue), renaming or skipping fields (@JsonField/@JsonSkip), optional fields (@Nullable), distinguishing missing vs null on PATCH (JsonNullable), serialization levels (@JsonInclude), enums, or registering a custom JsonReader/JsonWriter factory for an unsupported type. Also covers swapping in Jackson via JacksonModule. Triggers - @Json, @JsonReader, @JsonWriter, @JsonField, @JsonSkip, @JsonInclude, @JsonDiscriminatorField, JsonNullable, JsonModule, sealed interface JSON, JsonReader not found."
---

# Kora JSON — compile-time JSON processing

Kora generates `JsonReader<T>` / `JsonWriter<T>` at compile time from `@Json`-annotated
records (Java) or data classes (Kotlin). No reflection, no runtime mapper discovery:
an unsupported shape fails the build instead of throwing at runtime. Put `@Json` on the
DTO type itself, not only on the controller parameter — that lets the mapper be generated
during normal annotation processing and reused across HTTP bodies, cache values, and
Kafka payloads.

## Quick Start

`build.gradle` (all Kora artifacts inherit their version from the `kora-parent` BOM —
never pin individual `ru.tinkoff.kora:*` versions):

```groovy
dependencies {
    koraBom platform("ru.tinkoff.kora:kora-parent:1.2.17")

    annotationProcessor "ru.tinkoff.kora:annotation-processors" // mandatory: generates readers/writers
    implementation "ru.tinkoff.kora:json-module"
}
```

Kotlin uses KSP instead: `ksp "ru.tinkoff.kora:symbol-processors"`.

Wire the module into the application graph:

```java
@KoraApp
public interface Application extends JsonModule {
    static void main(String[] args) {
        KoraApplication.run(ApplicationGraph::graph);
    }
}
```

Define DTOs and a controller (adapted from `kora-java-guide-json-app`):

```java
@Json
public record UserRequest(String name, String email) {}

@Json
public record UserResponse(String id, String name, String email, LocalDateTime createdAt) {}

@Component
@HttpController
public final class UserController {

    private final UserService userService;

    public UserController(UserService userService) {
        this.userService = userService;
    }

    @HttpRoute(method = HttpMethod.POST, path = "/users")
    @Json
    public UserResponse createUser(@Json UserRequest request) {
        return userService.createUser(request);
    }
}
```

`@Json` on the method marks the response body as JSON; `@Json` on the parameter marks
the request body. Both require the `JsonModule` to be wired.

---

Use this skill when:
- creating DTO records/data classes for HTTP request/response bodies with `@Json`,
- implementing polymorphic JSON with sealed types and `@JsonDiscriminatorField`,
- registering a custom `JsonReader`/`JsonWriter` factory for an unsupported type,
- handling optional fields with `@Nullable` or distinguishing missing vs null with `JsonNullable`,
- switching the JSON backend to Jackson via `JacksonModule`.

---

## Assets (Templates)

| Template | Purpose |
|----------|---------|
| `dto.java.template` | Basic DTO record with `@Json` |
| `dto.kt.template` | Kotlin data class with `@Json` |
| `enum.java.template` | Enum with custom JSON via `toString()` |
| `enum.kt.template` | Kotlin enum with JSON support |
| `sealed-dto.java.template` | Sealed interface for polymorphic JSON |
| `sealed-dto.kt.template` | Kotlin sealed interface |
| `sealed-dto-impl.java.template` | Sealed impl with `@JsonDiscriminatorValue` |
| `sealed-dto-impl.kt.template` | Kotlin sealed impl |
| `custom-mapper.java.template` | Module with custom `JsonReader`/`JsonWriter` |
| `custom-mapper.kt.template` | Kotlin custom mapper module |

**Usage:** Copy template, replace placeholders (`${package}`, `${entity_name}`, etc.).

---

## Quick Reference

### Core Annotations

```java
@Json                       // Reader + Writer
@JsonReader                 // Deserialization only (also valid on a constructor)
@JsonWriter                 // Serialization only
@JsonField("user_id")       // Rename field in JSON
@JsonSkip                   // Ignore field on read and write
@JsonInclude(IncludeType.X) // ALWAYS / NON_NULL (default) / NON_EMPTY
@Nullable                   // Optional field (any @Nullable annotation works)
JsonNullable<T>             // Distinguish missing vs explicit null (PATCH)
```

### Sealed Interfaces

```java
@Json
@JsonDiscriminatorField("type")
public sealed interface Result permits Success, Error {}

@Json
@JsonDiscriminatorValue("SUCCESS")
public record Success(String type, String data) implements Result {}

@Json
@JsonDiscriminatorValue("ERROR")
public record Error(String type, String code) implements Result {}
```

`@JsonDiscriminatorValue` must be present on every subtype; the discriminator field
(`type` here) is a normal record component on each subtype. JSON:
```json
{ "type": "SUCCESS", "data": "..." }
{ "type": "ERROR", "code": "NOT_FOUND" }
```

### Enum Serialization

```java
@Json
public enum Status { PENDING, PROCESSING, SHIPPED }
```

**JSON:** `"PENDING"`, `"PROCESSING"`, `"SHIPPED"`

### Controller Pattern

```java
@Component
@HttpController
public final class ApiController {
    @HttpRoute(method = HttpMethod.POST, path = "/items")
    @Json
    public ItemResponse create(@Json ItemRequest request) { ... }

    @HttpRoute(method = HttpMethod.GET, path = "/items/{id}")
    @Json
    public ItemResponse getById(@Path String id) { ... }

    @HttpRoute(method = HttpMethod.GET, path = "/items")
    @Json
    public List<ItemResponse> getAll() { ... }
}
```

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| JsonReader not found | Add `@Json` to DTO/enum, verify `JsonModule` is wired |
| Missing field error | Fields are required by default — add `@Nullable` |
| Discriminator not found | Check `@JsonDiscriminatorField` on sealed interface |
| Warning "mapper in new round" | Verify `@Json` on all DTOs and enums |
| Jackson mapper not working | Add `json-annotation-processor` + `jackson-module`, extend `JacksonModule` |

---

## Reference Files

| File | Description |
|------|-------------|
| [json-dto-reference.md](references/json-dto-reference.md) | DTOs, records, @Json annotations, field config, enums |
| [json-sealed-reference.md](references/json-sealed-reference.md) | Sealed interfaces, polymorphic JSON, discriminators |
| [json-custom-mapper-reference.md](references/json-custom-mapper-reference.md) | Custom JsonReader/JsonWriter, use cases |
| [json-config-reference.md](references/json-config-reference.md) | JsonModule, Jackson integration, configuration |
| [json-best-practices.md](references/json-best-practices.md) | Best practices, patterns, testing |

---

## JsonNullable — missing vs null (PATCH)

`JsonNullable<T>` distinguishes a field that was absent in the JSON from a field that was
explicitly `null`. Its API is `isDefined()`, `isNull()`, `value()` plus the factories
`JsonNullable.of(v)`, `JsonNullable.ofNullable(v)`, `JsonNullable.nullValue()`,
`JsonNullable.undefined()`:

```java
@Json
public record PatchUserRequest(JsonNullable<String> name, JsonNullable<String> email) {}

if (request.name().isDefined()) {       // field present in JSON (value may be null)
    user.setName(request.name().value()); // value() returns null when isNull() is true
}
// undefined field → isDefined() == false → leave the property untouched
```

See [json-dto-reference.md](references/json-dto-reference.md) for the full state table.

## Common Pitfalls

- **Missing `@Json` on DTO/enum/sealed type** → no `JsonReader`/`JsonWriter` generated. Annotate the type, not only the controller parameter.
- **All fields required by default** → use `@Nullable` for optional fields (Kotlin: nullable type `T?`).
- **Discriminator value mismatch** → `@JsonDiscriminatorValue` must match the JSON discriminator value exactly, and the discriminator field must exist as a component on each subtype.
- **`@JsonSkip` vs `@JsonInclude`** — `@JsonSkip` removes the field from both read and write; `@JsonInclude` only controls when a present field is written.
- **Wrong `JsonNullable` API** — use `isDefined()`/`isNull()`/`value()`, not `Optional`-style `isPresent()`/`get()`.
