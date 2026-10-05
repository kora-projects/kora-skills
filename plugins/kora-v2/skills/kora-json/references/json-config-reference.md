# JSON Artifacts, Wiring and Jackson (Kora 2.x)

Verified against the Kora 2.0 build — [`settings.gradle`](https://github.com/kora-projects/kora/blob/2.0.0.RC2/settings.gradle),
[`gradle/libs.versions.toml`](https://github.com/kora-projects/kora/blob/2.0.0.RC2/gradle/libs.versions.toml),
[`json/json-common/build.gradle`](https://github.com/kora-projects/kora/blob/2.0.0.RC2/json/json-common/build.gradle),
[`json/jackson-module`](https://github.com/kora-projects/kora/tree/2.0.0.RC2/json/jackson-module).

## Contents

1. [Artifacts](#1-artifacts)
2. [Dependencies](#2-dependencies)
3. [Module wiring](#3-module-wiring)
4. [What JsonModule provides](#4-what-jsonmodule-provides)
5. [Jackson integration](#5-jackson-integration)
6. [Choosing JsonModule vs JacksonModule](#6-choosing-jsonmodule-vs-jacksonmodule)
7. [Migrating Jackson DTOs to Kora annotations](#7-migrating-jackson-dtos-to-kora-annotations)
8. [Quick reference](#8-quick-reference)

---

## 1. Artifacts

| Artifact | Contents |
|---|---|
| `io.koraframework:kora-bom` | version platform for every `io.koraframework:*` artifact |
| `io.koraframework:json-common` | runtime: `JsonModule`, `JsonReader`, `JsonWriter`, `JsonNullable`, `RawJson`, annotations |
| `io.koraframework:annotation-processors` | Java annotation processors (aggregate, includes `json-annotation-processor`) |
| `io.koraframework:symbol-processors` | Kotlin KSP processors (aggregate, includes `json-symbol-processor`) |
| `io.koraframework:json-annotation-processor` | the JSON processor alone (Java) |
| `io.koraframework:json-symbol-processor` | the JSON processor alone (Kotlin) |
| `io.koraframework:jackson-module` | `JacksonModule` — HTTP body mappers backed by a Jackson 3 `ObjectMapper` |

**`json-module` does not exist in Kora 2.0.** It was renamed to `json-common`. Likewise the
BOM is `io.koraframework:kora-bom`, not `ru.tinkoff.kora:kora-parent`.

`json-common` declares `tools.jackson.core:jackson-core` as an `api` dependency, so the
Jackson 3 streaming types are on the compile classpath of anything that uses it.

`json-common` does reach the compile classpath transitively when the HTTP server is present
(`http-server-undertow` → `api logging-common` → `api json-common`), but note that
`http-common` itself declares it `compileOnly`. Declare `json-common` explicitly in every
Gradle module that uses `@Json` — that is what every migrated example and guide does.

---

## 2. Dependencies

The annotation processor is mandatory — it generates the `JsonReader`/`JsonWriter` classes.
All Kora artifacts inherit their version from the `kora-bom` platform; never pin an
individual `io.koraframework:*` version.

### Version and repository

Pin the released **`2.0.0.RC2`** from Maven Central. Plain `mavenCentral()` resolves it — no
extra repository is required.

```properties
# gradle.properties
koraVersion=2.0.0.RC2
```

```groovy
repositories {
    mavenCentral()
}
```

`2.0.0-SNAPSHOT` is the `master` development line, not a version for a new project. It
resolves only from `https://central.sonatype.com/repository/maven-snapshots` (or a local
`publishToMavenLocal`). The `JsonReader`/`JsonWriter` contracts are described in
[the contracts](json-custom-mapper-reference.md#2-the-two-contracts).

Central still lists `kora-parent`, `cache-redis`, `scheduling-ksp` and other 1.x/alpha
leftovers under `io/koraframework/`. None is constrained by the 2.0 BOM; do not use them.

### Java (Gradle)

```groovy
configurations {
    koraBom
    annotationProcessor.extendsFrom(koraBom)
    implementation.extendsFrom(koraBom)
    testAnnotationProcessor.extendsFrom(koraBom)
    testImplementation.extendsFrom(koraBom)
}

dependencies {
    koraBom platform("io.koraframework:kora-bom:$koraVersion")

    annotationProcessor "io.koraframework:annotation-processors"
    implementation "io.koraframework:json-common"
}
```

### Kotlin (Gradle, KSP)

```kotlin
dependencies {
    implementation(platform("io.koraframework:kora-bom:${property("koraVersion")}"))

    ksp("io.koraframework:symbol-processors:${property("koraVersion")}")
    implementation("io.koraframework:json-common")
}
```

The migrated Kotlin examples pass the version explicitly on the `ksp(...)` line.

**Toolchain:** Kora 2.0 targets **JVM 25** (`kora-bom` declares `java.version = 25`), Kotlin
`2.4.x` with KSP `2.3.x`. See the `kora-project-setup-java` / `kora-project-setup-kotlin`
skills for the full build file.

---

## 3. Module Wiring

### Java

```java
import io.koraframework.application.graph.KoraApplication;
import io.koraframework.common.annotation.KoraApp;
import io.koraframework.json.common.JsonModule;

@KoraApp
public interface Application extends JsonModule {
    static void main(String[] args) {
        KoraApplication.run(ApplicationGraph::graph);
    }
}
```

### Kotlin

```kotlin
import io.koraframework.application.graph.KoraApplication
import io.koraframework.common.annotation.KoraApp
import io.koraframework.json.common.JsonModule

@KoraApp
interface Application : JsonModule

fun main() {
    KoraApplication.run(ApplicationGraph::graph)
}
```

Alongside other modules:

```java
@KoraApp
public interface Application extends
    HoconConfigModule, JsonModule, LogbackModule, UndertowPublicHttpServerModule {

    static void main(String[] args) {
        KoraApplication.run(ApplicationGraph::graph);
    }
}
```

There is **one** module interface — `io.koraframework.json.common.JsonModule`. Kora 1.x's
`JsonCommonModule` and `ru.tinkoff.kora.json.module.JsonModule` are both gone.

`JsonModule` carries no configuration section: there are no `json.*` config keys.

---

## 4. What `JsonModule` Provides

Every factory in `JsonModule` is a `@DefaultComponent`, so declaring your own plain
(non-default) component of the same type replaces it:

- **Free-form** — `JsonWriter<Object>` / `JsonReader<Object>` (arbitrary JSON trees),
  `JsonWriter<RawJson>`
- **Scalars** — `Short`, `Integer`, `Long`, `Float`, `Double`, `String`, `Boolean`,
  `BigDecimal`, `BigInteger`, `UUID`
- **Collections** — `List<T>`, `Set<T>`, `Map<String, T>` (reader + writer),
  `SortedSet<T>` (reader)
- **Date/time (ISO-8601)** — `LocalDate`, `LocalTime`, `LocalDateTime`, `OffsetTime`,
  `OffsetDateTime`, `ZonedDateTime`, `Instant`, `Year`, `YearMonth`, `MonthDay`, `Month`,
  `DayOfWeek`, `ZoneId`, `Duration`

It also exposes the shared `JsonModule.JSON_FACTORY` (a `tools.jackson.core.json.JsonFactory`
with a thread-local recycler pool and `WRITE_BIGDECIMAL_AS_PLAIN` enabled) used by the
`toByteArray` / `toString` / `read` default methods.

---

## 5. Jackson Integration

### What `jackson-module` actually does

`io.koraframework.json.jackson.module.JacksonModule` supplies **HTTP body mappers backed by
a Jackson `ObjectMapper`**, tagged `@Json`:

- `HttpServerRequestMapper<T>` / `HttpServerResponseMapper<T>`
- `HttpClientRequestMapper<T>` / `HttpClientResponseMapper<T>`
- `HttpClientResponseMapper<HttpResponseEntity<T>>`

It does **not** provide `JsonReader<T>` / `JsonWriter<T>`. `@Json` DTO code generation and
any direct `JsonReader`/`JsonWriter` injection keep working exactly as before; only the HTTP
body boundary moves onto Jackson. The Kora-native HTTP mappers are `@DefaultComponent`, so
`JacksonModule`'s plain factories take precedence over them automatically.

### Which Jackson

**Jackson 3, group `tools.jackson.core`.** `jackson-module` declares
`api tools.jackson.core:jackson-databind` and the version catalog pins `jackson = "3.2.3"`.
The `ObjectMapper` type is `tools.jackson.databind.ObjectMapper`.

The catalog also keeps a separate Jackson 2 line (`com.fasterxml.jackson.*`, `2.22.x`) for
unrelated compatibility modules — it is **not** what `jackson-module` binds. Adding
`com.fasterxml.jackson.core:jackson-databind` to a Kora 2.0 app gives you a second, unused
Jackson on the classpath and an `ObjectMapper` the graph will not accept.

### Dependency

Java:

```groovy
dependencies {
    annotationProcessor "io.koraframework:annotation-processors"
    implementation "io.koraframework:jackson-module"
}
```

Kotlin (KSP):

```kotlin
dependencies {
    ksp("io.koraframework:symbol-processors:${property("koraVersion")}")
    implementation("io.koraframework:jackson-module")
}
```

**What the consumer adds, exactly:**

| Item | Who provides it |
|---|---|
| `tools.jackson.core:jackson-databind:3.2.3` | `jackson-module` — declared `api`, arrives transitively. **Do not add it yourself.** |
| `tools.jackson.core:jackson-core:3.2.3` | `json-common` — declared `api` |
| a `tools.jackson.databind.ObjectMapper` **component** | **you**, as a factory in `@Module`/`@KoraApp` — `JacksonModule` supplies none |
| `http-server-common` / `http-client-common` | **you** (they are `compileOnly` in `jackson-module`) — normally already present via `http-server-undertow` |
| `io.koraframework:json-common` | **you** — `jackson-module` does not publish a dependency on it |
| anything under `com.fasterxml.jackson.*` | **nobody** — adding it is the classpath mistake described above |

`jackson-module` is additive: it redirects the HTTP body mappers and nothing else.

### The `ObjectMapper` is yours to provide

`JacksonModule` takes `ObjectMapper` as a **parameter** of every factory and supplies none.
Without a component of type `tools.jackson.databind.ObjectMapper` in the graph the build
fails with `No component found for dependency tools.jackson.databind.ObjectMapper`.

```java
import io.koraframework.json.jackson.module.JacksonModule;
import tools.jackson.databind.ObjectMapper;

@KoraApp
public interface Application extends JacksonModule, UndertowPublicHttpServerModule {

    default ObjectMapper objectMapper() {
        return buildTeamObjectMapper();   // your existing Jackson configuration
    }

    static void main(String[] args) {
        KoraApplication.run(ApplicationGraph::graph);
    }
}
```

Configure the mapper with **Jackson 3's own** builder API under `tools.jackson.databind`;
consult the Jackson 3 documentation for feature and builder names rather than carrying
Jackson 2 code over unchanged. Jackson 2 add-ons —
`com.fasterxml.jackson.datatype:jackson-datatype-jsr310`,
`com.fasterxml.jackson.module:jackson-module-kotlin` — live under a different group and do
not apply to a `tools.jackson` `ObjectMapper`. A Jackson Kotlin module would also drag
`kotlin-reflect` in, which is exactly the kind of dependency that breaks GraalVM native
builds; Kora's own generated JSON needs no reflection at all.

Kora's Jackson mappers use `objectMapper.readerFor(objectMapper.constructType(type))` and
`objectMapper.writerFor(...)`, and translate a `tools.jackson.core.JacksonException` on read
into `HttpServerResponseException.of(400, e)` — so a malformed request body surfaces as
HTTP 400.

Extending both is legal — the generated mappers still serve direct `JsonReader`/`JsonWriter`
injection while Jackson serves the HTTP bodies:

```java
@KoraApp
public interface Application extends JsonModule, JacksonModule { … }
```

---

## 6. Choosing `JsonModule` vs `JacksonModule`

### Use the generated mappers (`JsonModule`) — the default

- New code, ordinary DTOs, performance-sensitive paths
- Compile-time safety: an unsupported shape fails the build, not a request
- No reflection — the only option that stays native-image friendly for free
- Required anyway wherever `JsonReader<T>` / `JsonWriter<T>` is injected directly (Kafka
  payloads, cache values, custom codecs)

### Add `JacksonModule` when

- an existing Jackson `ObjectMapper` configuration (mix-ins, custom serializers, naming
  strategies) must keep governing the HTTP wire format
- a third-party library hands you objects only Jackson can map
- you need a Jackson dataformat (YAML/CBOR/Smile) at the HTTP boundary

`JacksonModule` does not remove the need for `@Json`/`json-common` — it only redirects the
HTTP body mappers.

---

## 7. Migrating Jackson DTOs to Kora Annotations

### Before (Jackson)

```java
import com.fasterxml.jackson.annotation.*;

@JsonInclude(JsonInclude.Include.NON_NULL)
public class UserDto {
    @JsonProperty("user_id")   private String userId;
    @JsonProperty("email_address") private String email;
    @JsonIgnore                private String internalField;
    // constructors, getters, setters
}
```

### After (Kora JSON)

```java
import io.koraframework.json.common.annotation.Json;
import io.koraframework.json.common.annotation.JsonField;
import io.koraframework.json.common.annotation.JsonInclude;
import io.koraframework.json.common.annotation.JsonSkip;

import static io.koraframework.json.common.annotation.JsonInclude.IncludeType.NON_NULL;

@Json
@JsonInclude(NON_NULL)
public record UserDto(
    @JsonField("user_id") String userId,
    @JsonField("email_address") String email,
    @JsonSkip String internalField
) {}
```

### Annotation mapping

| Jackson | Kora |
|---------|------|
| `@JsonProperty("name")` | `@JsonField("name")` |
| `@JsonIgnore` | `@JsonSkip` |
| `@JsonInclude(Include.NON_NULL)` | `@JsonInclude(IncludeType.NON_NULL)` |
| `@JsonNaming(SnakeCaseStrategy.class)` | `@NamingStrategy(SnakeCaseNameConverter.class)` |
| `@JsonTypeInfo` | `@JsonDiscriminatorField` |
| `@JsonSubTypes` | `@JsonDiscriminatorValue` (or the subtype simple name) |
| `@JsonCreator` on a constructor | `@JsonReader` on a constructor |
| `@JsonCreator(mode = DELEGATING)` factory + `@JsonValue` on a value type | `@JsonReader` on a `public static` factory + `@JsonWriter` on the value method ([single-value types](json-dto-reference.md#single-value-types)) |
| `@JsonValue` on an enum accessor | `@Json` on the enum accessor |
| `@JsonFormat(pattern = "…")` | custom `JsonReader`/`JsonWriter`, or `@Mapping` per field |

### Checklist

- [ ] Replace `@JsonProperty` → `@JsonField`, `@JsonIgnore` → `@JsonSkip`
- [ ] Replace the Jackson `@JsonInclude` import with Kora's
- [ ] Convert classes to records / Kotlin data classes where possible
- [ ] Convert polymorphic types to sealed hierarchies with discriminator annotations
- [ ] Drop `com.fasterxml.jackson.*` imports; the streaming types are `tools.jackson.core.*`
- [ ] Round-trip test every converted DTO

---

## 8. Quick Reference

### Dependencies

```properties
# gradle.properties
koraVersion=2.0.0.RC2
```

```groovy
repositories { mavenCentral() }

dependencies {
    koraBom platform("io.koraframework:kora-bom:$koraVersion")

    // Kora JSON (default) — the processor is mandatory
    annotationProcessor "io.koraframework:annotation-processors"
    implementation "io.koraframework:json-common"

    // Jackson 3 for the HTTP bodies (optional, additive)
    implementation "io.koraframework:jackson-module"   // brings tools.jackson.core:jackson-databind:3.2.3
}
```

### Modules

```java
@KoraApp public interface Application extends JsonModule {}                  // Kora JSON
@KoraApp public interface Application extends JacksonModule {}               // Jackson HTTP bodies (needs an ObjectMapper)
@KoraApp public interface Application extends JsonModule, JacksonModule {}   // both
```

### Renames from 1.x

| 1.x | 2.x |
|---|---|
| `ru.tinkoff.kora:kora-parent` | `io.koraframework:kora-bom` |
| `ru.tinkoff.kora:json-module` | `io.koraframework:json-common` |
| `ru.tinkoff.kora.json.module.JsonModule` | `io.koraframework.json.common.JsonModule` |
| `JsonCommonModule` | `JsonModule` |
| `ru.tinkoff.kora.json.common.annotation.*` | `io.koraframework.json.common.annotation.*` |
| `com.fasterxml.jackson.core:*` | `tools.jackson.core:*` (Jackson 3) |
| `com.fasterxml.jackson.databind.ObjectMapper` | `tools.jackson.databind.ObjectMapper` |
