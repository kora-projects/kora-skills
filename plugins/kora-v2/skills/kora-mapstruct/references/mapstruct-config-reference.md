# Build Configuration Reference (Java) — MapStruct

**Scope: Java only.** Kotlin modules map with Konvert and never with MapStruct — see
[`konvert-reference.md`](konvert-reference.md).

**Verified against** `mapping/mapstruct-java-extension`, `core/annotation-processors/build.gradle`
and `gradle/libs.versions.toml` on Kora `master` for `2.0.0.RC2`
(<https://github.com/kora-projects/kora/tree/2.0.0.RC2/mapping>), and the working build of
[`kora-java-crud`](https://github.com/kora-projects/kora-examples/tree/migration/2.0/examples/java/kora-java-crud)
on `kora-examples` branch `migration/2.0`.

## Contents

- [Artifacts: what exists and what you declare](#artifacts-what-exists-and-what-you-declare)
- [Java setup — MapStruct](#java-setup--mapstruct)
- [Versions](#versions)
- [componentModel](#componentmodel)
- [Shared configuration with @MapperConfig](#shared-configuration-with-mapperconfig)
- [Troubleshooting](#troubleshooting)

## Artifacts: what exists and what you declare

`ru.tinkoff.kora:mapstruct-extension` **does not exist in Kora 2.0.** The Java side is
`io.koraframework:mapstruct-java-extension`, which binds MapStruct-generated impls during javac
annotation processing.

**You do not declare it.** It is an `api` dependency of `io.koraframework:annotation-processors`,
which is constrained by `io.koraframework:kora-bom`, so no version goes on it either.

**`kora-bom` does not constrain third-party artifacts** — it is a `java-platform` built from Kora's
own subprojects. `org.mapstruct:*` and `io.mcarle:*` carry explicit versions, always.

## Java setup — MapStruct

`gradle.properties`:

```properties
koraVersion=2.0.0.RC2
```

`build.gradle`:

```groovy
repositories { mavenCentral() }

java {
    toolchain {
        languageVersion = JavaLanguageVersion.of(25)
        vendor = JvmVendorSpec.ADOPTIUM
    }
}

configurations {
    koraBom
    annotationProcessor.extendsFrom(koraBom); compileOnly.extendsFrom(koraBom)
    implementation.extendsFrom(koraBom); api.extendsFrom(koraBom)
    testImplementation.extendsFrom(koraBom); testAnnotationProcessor.extendsFrom(koraBom)
}

dependencies {
    koraBom platform("io.koraframework:kora-bom:$koraVersion")

    annotationProcessor "io.koraframework:annotation-processors"
    annotationProcessor "org.mapstruct:mapstruct-processor:1.6.3"

    implementation "org.mapstruct:mapstruct:1.6.3"
}
```

Three things must all be true, or the mapper never reaches the graph:

1. `annotation-processors` on `annotationProcessor` — brings `mapstruct-java-extension` and the
   `KoraAppProcessor` that consults it.
2. `mapstruct-processor` on `annotationProcessor` — the only thing that generates `*MapperImpl`.
3. `mapstruct` on `implementation` (compile classpath) — `MapstructKoraExtensionFactory` resolves
   `org.mapstruct.Mapper` through the processing environment and returns *no extension* when the
   type is absent. Processor-only wiring fails with a plain unresolved-dependency error that never
   mentions MapStruct.

The `koraBom` configuration with `extendsFrom` is not optional in Java: a `platform` on
`implementation` does not reach the `annotationProcessor` classpath, so `annotation-processors`
would fail to resolve.

### Declaration order does not matter

`kora-java-crud` lists `mapstruct-processor` before `annotation-processors`. That ordering is not
load-bearing. `KoraAppProcessor` builds the graph only when `roundEnv.processingOver()` — the final
annotation-processing round — so every `*MapperImpl` generated in an earlier round is already
visible. Kora's own extension test registers the processors in the opposite order and passes.

### Optional MapStruct compiler options

Standard MapStruct options, unrelated to Kora — see
<https://mapstruct.org/documentation/stable/reference/html/#configuration-options>:

```groovy
compileJava {
    options.compilerArgs += [
        "-Amapstruct.suppressGeneratorTimestamp=true",
        "-Amapstruct.suppressGeneratorVersionInfoComment=true"
    ]
}
```

Do not set `-Amapstruct.defaultComponentModel` to a DI framework's model on a whim; see
[componentModel](#componentmodel).

## Versions

| Library | Kora catalog (`gradle/libs.versions.toml`) | `kora-examples` on `migration/2.0` | Use |
|---|---|---|---|
| `org.mapstruct:mapstruct` / `:mapstruct-processor` | **`1.6.3`** | `1.5.5.Final` | `1.6.3` |
| `io.koraframework:*` | — | — | `2.0.0.RC2` via `kora-bom` |

The MapStruct disagreement is real, not a typo on either side. `1.6.3` is what Kora's own
`mapstruct-java-extension` is compiled and tested against.
`1.5.5.Final` predates the 2.0 work in the examples: it was introduced by the earlier
*"Refactored structure and more Kotlin examples"* commit, and the 2.0 migration commit rewrote Kora
coordinates without touching it. **Pick `1.6.3`**, and keep the API and the processor on the same
version — a split pin produces MapStruct's own errors, which say nothing about Kora.

Toolchain floor for consuming Kora 2.0: **JDK 25**.

## componentModel

Kora reads no MapStruct component-model annotation. It binds the generated implementation's single
public constructor and nothing else. Plain `@Mapper` is correct and is what every example uses:

```java
@Mapper                                     // ✔ default
@Mapper(unmappedTargetPolicy = ReportingPolicy.IGNORE)   // ✔ also just MapStruct config
```

`componentModel` becomes relevant only to force **constructor injection of `uses` mappers**:

```java
@Mapper(uses = DateMapper.class,
        injectionStrategy = org.mapstruct.InjectionStrategy.CONSTRUCTOR,
        componentModel = "jakarta")
public interface CarMapper { … }
```

Then MapStruct emits a constructor taking `DateMapper`, and Kora resolves it from the graph. This
requires `jakarta.inject:jakarta.inject-api` on the compile classpath for the generated
`jakarta.inject` annotations to compile — Kora's extension module adds exactly that dependency for
its own test of this shape. Do not set `componentModel = "spring"` or `"cdi"`: those generate
framework annotations Kora ignores and dependencies nothing satisfies.

The one hard requirement is structural: **exactly one public constructor** on the generated impl,
or Kora reports *"Generated class `…` must have exactly one public constructor so Kora can use it as
a dependency."*

## Shared configuration with @MapperConfig

Plain MapStruct, transparent to Kora:

```java
@MapperConfig(
    unmappedTargetPolicy = ReportingPolicy.IGNORE,
    nullValuePropertyMappingStrategy = NullValuePropertyMappingStrategy.IGNORE
)
public interface MappingConfig {}

@Mapper(config = MappingConfig.class)
public interface OrderMapper { … }
```

The `@MapperConfig` interface itself is not a mapper — it has no `@Mapper`, so Kora never looks at
it.

## Troubleshooting

| Symptom | Cause and fix |
|---|---|
| `Could not find io.koraframework:mapstruct-extension` | 1.x coordinate. Nothing replaces it — the extension is already inside `annotation-processors` |
| Unresolved dependency on `FooMapper`, no MapStruct message at all | MapStruct is missing from the compile classpath, so the extension factory returned nothing. Add `implementation "org.mapstruct:mapstruct:1.6.3"` |
| `MapStruct mapper implementation was not generated for FooMapper` | `mapstruct-processor` is not on `annotationProcessor`, or MapStruct itself errored earlier in the same compile — read the errors above this one first |
| A `@Mapper` written in a **Kotlin** module | Not a Kora 2.0 path — MapStruct cannot run under KSP. Rewrite it as a Konvert `@Konverter` ([`konvert-reference.md`](konvert-reference.md)) |
| `Generated class … must have exactly one public constructor` | A `componentModel` / `injectionStrategy` combination emitted several. Simplify, or declare the mapper yourself as a `@Component` |
| Mapper resolves but is never the generated impl | You also declared it in a `@Module`. Extensions are a fallback, so your declaration wins silently. Delete one |
| Phantom `ru.tinkoff.kora` errors from generated mapper code | Stale output under `build/`. `./gradlew clean` and rebuild. Never edit generated sources |
| IDE shows the mapper interface unimplemented | Expected before a build. `./gradlew classes` |
