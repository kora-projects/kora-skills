# Kora + MapStruct — distilled reference

**Source:** [.kora-agent/kora-docs/mkdocs/docs/en/documentation/mapper.md](.kora-agent/kora-docs/mkdocs/docs/en/documentation/mapper.md)  
**Examples:** `.kora-agent/kora-examples/kora-java-mapper-mapstruct/`

Focused condensation of `kora-docs/.../documentation/mapstruct.md`.

## Module mechanism

Kora's `MapstructKoraExtension` (in `ru.tinkoff.kora.mapstruct.java.extension`) is registered automatically when the kora annotation processor sees a `@Mapper`-annotated interface. The extension:

1. Detects the `org.mapstruct.Mapper` annotation on an interface or abstract class.
2. Looks up the MapStruct-generated implementation class (e.g., `CarMapperImpl`).
3. Registers it as a singleton component in the graph, injectable wherever the mapper interface is requested.

No `*Module` to plug into `@KoraApp` — the extension is loaded via Java SPI when both Kora and MapStruct processors are on the classpath.

## Versions (pinned by Kora docs)

| Component | Pin |
|-----------|-----|
| MapStruct | `1.5.5.Final` |
| Kotlin (for kapt) | `1.9.10` |
| KSP | `1.9.10-1.0.13` |

Newer combinations are not guaranteed to work — kapt+KSP coexistence broke at the Gradle Plugin level past these versions per Kora's docs.

## Java setup

```groovy
dependencies {
    annotationProcessor "ru.tinkoff.kora:annotation-processors"
    annotationProcessor "org.mapstruct:mapstruct-processor:1.5.5.Final"

    // MapStruct runtime
    implementation "org.mapstruct:mapstruct:1.5.5.Final"
}
```

That's the whole setup. Gradle orders annotation processors by classpath order; placing MapStruct first generally works.

## Kotlin setup (kapt + KSP)

```kotlin
plugins {
    kotlin("jvm") version "1.9.10"
    kotlin("kapt") version "1.9.10"
    id("com.google.devtools.ksp") version "1.9.10-1.0.13"
}

ksp {
    allowSourcesFromOtherPlugins = true
}

tasks.withType<com.google.devtools.ksp.gradle.KspTask> {
    dependsOn(tasks.named("kaptGenerateStubsKotlin"))
    dependsOn(tasks.named("kaptKotlin"))
}

dependencies {
    kapt("org.mapstruct:mapstruct-processor:1.5.5.Final")
    ksp("ru.tinkoff.kora:symbol-processors")
    implementation("org.mapstruct:mapstruct:1.5.5.Final")
}
```

The two `tasks.dependsOn` calls force KSP to run after kapt, so KSP sees the kapt-generated mapper impl classes when scanning for components.

**Two-pass build.** First `./gradlew build` often fails — kapt and KSP need each other's output, but on a clean build there's no output yet. The second run succeeds. This is documented KSP behavior, not a Kora bug.

## `@Mapper` annotation

From `org.mapstruct.Mapper`. The Kora extension recognizes it on:
- `interface`s (preferred)
- `abstract class`es (for cases where you need state or non-trivial helper methods)

`componentModel` doesn't need to be `"kora"` — the default works. Kora's extension picks up the mapper regardless of how MapStruct's `componentModel` is set, but leaving it default is the clean choice.

## Useful `@Mapping` parameters

| Parameter | Purpose |
|-----------|---------|
| `source = "..."` | Source field name in the input class |
| `target = "..."` | Target field name in the output class |
| `ignore = true` | Skip this target field (use with `@MappingTarget` to preserve existing values) |
| `expression = "java(...)"` | Inline Java expression for the value |
| `defaultValue = "..."` | Used when source is null |
| `qualifiedByName = "..."` | Dispatch to a `@Named("...")` helper method |
| `dateFormat = "..."` | For Date ↔ String mappings |
| `numberFormat = "..."` | For Number ↔ String mappings |

## `@MappingTarget` for in-place update

```java
void applyPatch(@MappingTarget Order existing, PatchOrderDto patch);
```

The target is already an instance; the mapper writes the source's values into it. Pair with `@BeanMapping(nullValuePropertyMappingStrategy = NullValuePropertyMappingStrategy.IGNORE)` to skip null source fields — exactly the PATCH semantic.

## `@AfterMapping` / `@BeforeMapping` hooks

```java
@AfterMapping
default void postProcess(@MappingTarget OrderDto out, Order in) {
    out.setComputedField(in.amount().multiply(in.taxRate()));
}
```

Useful when the mapping needs derived fields that can't be expressed as a simple `@Mapping`. Don't overuse — once you have three of these in a mapper, switch to a hand-written one.

## Decision: use it or skip it

**Use MapStruct when:**
- You have ≥5 DTO/entity pairs in the same module with mostly 1:1 field overlap.
- You want compile-time verification that the source and target shapes match.
- Java codebase (kapt+KSP friction doesn't apply).

**Skip MapStruct when:**
- You have 1–3 mappers — hand-written is shorter and easier to read.
- Kotlin codebase that doesn't otherwise need kapt — the version pinning is a maintenance burden.
- Mappers have significant logic (string parsing, validation, multi-field derivation) — expressions and `@AfterMapping` hooks get unreadable.
