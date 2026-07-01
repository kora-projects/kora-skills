# MapStruct Configuration Reference

**Source:** `.kora-agent/kora-docs/mkdocs/docs/en/documentation/mapstruct.md`,
`.kora-agent/kora-examples/examples/java/kora-java-crud/build.gradle`,
`.kora-agent/kora-examples/examples/kotlin/kora-kotlin-crud/build.gradle.kts`

## Contents

- [Module mechanism](#module-mechanism)
- [Java setup](#java-setup)
- [Kotlin setup (kapt + KSP)](#kotlin-setup-kapt--ksp)
- [componentModel setting](#componentmodel-setting)
- [Shared configuration with @MapperConfig](#shared-configuration-with-mapperconfig)
- [Troubleshooting](#troubleshooting)

## Module mechanism

Kora's MapStruct integration is automatic — there is **no `*Module` to plug into
`@KoraApp`**. Kora's annotation processor detects every `@Mapper` interface, finds
the MapStruct-generated `*MapperImpl`, and registers it as a component in the DI
graph. This works whenever both the Kora annotation processor and the MapStruct
processor are on the annotation-processor classpath.

## Java setup

All Kora artifacts inherit their version from the `kora-parent` BOM
(`1.2.17` in the example repo). MapStruct artifacts are versioned explicitly.

```groovy
dependencies {
    koraBom platform("ru.tinkoff.kora:kora-parent:1.2.17")

    // Kora annotation processor (mandatory)
    annotationProcessor "ru.tinkoff.kora:annotation-processors"

    // MapStruct processor — generates *MapperImpl classes
    annotationProcessor "org.mapstruct:mapstruct-processor:1.5.5.Final"

    // MapStruct runtime
    implementation "org.mapstruct:mapstruct:1.5.5.Final"
}
```

This is the exact wiring used by
`.kora-agent/kora-examples/examples/java/kora-java-crud/build.gradle`.

**Order matters:** MapStruct's processor runs first (generates impls), then Kora's picks up the `@Mapper` interface and wires the impl into the graph.

### Compiler Arguments (Optional)

Enable verbose MapStruct output:

```groovy
compileJava {
    options.compilerArgs += [
        "-Amapstruct.suppressGeneratorTimestamp=true",
        "-Amapstruct.suppressGeneratorVersionInfoComment=true",
        "-Amapstruct.defaultComponentModel=default"
    ]
}
```

## Kotlin setup (kapt + KSP)

**MapStruct on Kotlin requires kapt, not KSP.** This collides with Kora's KSP
requirement — you must run both processors carefully.

> Reality check: the Kora team's own Kotlin example
> (`.kora-agent/kora-examples/examples/kotlin/kora-kotlin-crud/build.gradle.kts`)
> keeps the kapt + MapStruct wiring **commented out** with the note
> "KAPT & KSP broken since 1.9.11", runs on Kotlin `1.9.25` / KSP `1.9.25-1.0.20`,
> and writes its mappers by hand. If you are on Kotlin, prefer a hand-written
> mapper unless you can pin the exact versions below.

```kotlin
plugins {
    kotlin("jvm") version "1.9.10"
    kotlin("kapt") version "1.9.10"
    id("com.google.devtools.ksp") version "1.9.10-1.0.13"
}

ksp {
    allowSourcesFromOtherPlugins = true
}

// Force KSP to run AFTER kapt so it sees the generated mapper impls
tasks.withType<KspTask> {
    dependsOn(tasks.named("kaptGenerateStubsKotlin").get())
    dependsOn(tasks.named("kaptKotlin").get())
}

dependencies {
    kapt("org.mapstruct:mapstruct-processor:1.5.5.Final")
    ksp("ru.tinkoff.kora:symbol-processors")
    implementation("org.mapstruct:mapstruct:1.5.5.Final")
}
```

### Version Compatibility

| Component | Pinned Version |
|-----------|----------------|
| Kotlin | `1.9.10` |
| KSP | `1.9.10-1.0.13` |
| MapStruct | `1.5.5.Final` |

**Critical:** `1.9.10` + `1.9.10-1.0.13` is the **last working combination** for kapt + KSP coexistence at the Gradle Plugin level. Later KSP versions broke the integration.

### Two-Pass Build

First `./gradlew build` often fails on clean — kapt and KSP need each other's output, but on a clean build there's no output yet. **Second run succeeds.** This is documented KSP behavior.

```bash
./gradlew clean build  # may fail
./gradlew build        # succeeds
```

## componentModel Setting

The `@Mapper` annotation has a `componentModel` attribute, but **Kora doesn't require a specific value**:

```java
@Mapper  // default works
@Mapper(componentModel = "default")  // explicit default
```

Kora's extension picks up the mapper regardless — the generated impl is wired into the graph by Kora's own mechanism, not MapStruct's `componentModel`.

## Shared configuration with @MapperConfig

MapStruct supports a `@MapperConfig` annotation for shared configuration across multiple mappers:

```java
@MapperConfig(
    componentModel = "default",
    injectionStrategy = InjectionStrategy.CONSTRUCTOR,
    nullValuePropertyMappingStrategy = NullValuePropertyMappingStrategy.IGNORE
)
public interface MappingConfig {}

@Mapper(config = MappingConfig.class)
public interface OrderMapper { ... }
```

**Note:** Kora's integration doesn't require any specific config — the `MapstructKoraExtension` handles all `@Mapper` interfaces uniformly.

## Troubleshooting

| Problem | Solution |
|---------|----------|
| `*MapperImpl` not found | Run `./gradlew classes` — MapStruct processor must generate impl first |
| IDE shows red squiggles | Build the project — impls are generated during compilation |
| Kotlin first build fails | Expected — run `./gradlew build` again (two-pass build) |
| KSP doesn't see mapper impls | Check `dependsOn(kaptKotlin)` and `allowSourcesFromOtherPlugins = true` |
| Ambiguous mapper binding | Ensure only one `@Mapper` interface per type pair in the graph |
