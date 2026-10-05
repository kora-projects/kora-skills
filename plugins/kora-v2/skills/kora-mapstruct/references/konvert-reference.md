# Konvert Reference (Kotlin) — build wiring, discovery, limits

**Scope: Kotlin only.** Konvert is the Kotlin mapping path in Kora 2.0; Java uses MapStruct — see
[`mapstruct-mapper-reference.md`](mapstruct-mapper-reference.md). Never MapStruct or `kapt` in a
Kotlin module, never Konvert in a Java module.

**Verified against** `mapping/konvert-ksp-extension` (`KonvertKoraExtension`,
`KonvertKoraExtensionFactory`, `KonvertKoraExtensionTest`), `core/symbol-processors/build.gradle` and
`gradle/libs.versions.toml` on Kora `master` for `2.0.0.RC2`
(<https://github.com/kora-projects/kora/tree/2.0.0.RC2/mapping/konvert-ksp-extension>), and
[`kora-kotlin-crud`](https://github.com/kora-projects/kora-examples/tree/migration/2.0/examples/kotlin/kora-kotlin-crud)
on `kora-examples` branch `migration/2.0`. Konvert's own annotations are documented upstream:
<https://mcarleio.github.io/konvert/>.

## Contents

- [Build wiring](#build-wiring)
- [Why Konvert and not MapStruct in Kotlin](#why-konvert-and-not-mapstruct-in-kotlin)
- [How Kora discovers a @Konverter](#how-kora-discovers-a-konverter)
- [Limits](#limits)
- [Mappers that need graph components](#mappers-that-need-graph-components)
- [Tagging a mapper](#tagging-a-mapper)
- [Troubleshooting](#troubleshooting)

## Build wiring

`gradle.properties`:

```properties
koraVersion=2.0.0.RC2
```

`build.gradle.kts`:

```kotlin
plugins {
    kotlin("jvm") version "2.4.20"
    id("com.google.devtools.ksp") version "2.3.12"
}

repositories { mavenCentral() }

kotlin {
    jvmToolchain {
        languageVersion.set(JavaLanguageVersion.of(25))
        vendor.set(JvmVendorSpec.ADOPTIUM)
    }
}

dependencies {
    implementation(platform("io.koraframework:kora-bom:${property("koraVersion")}"))

    ksp("io.koraframework:symbol-processors:${property("koraVersion")}")
    ksp("io.mcarle:konvert:4.5.1")

    implementation("io.mcarle:konvert-api:4.5.1")
}
```

Three lines, three jobs — all three are required:

| Line | Job |
|---|---|
| `ksp("io.koraframework:symbol-processors:…")` | Kora's KSP processors; `konvert-ksp-extension` is an `api` dependency of this aggregate, so it is never declared on its own. The BOM does not reach the `ksp` configuration, so this line carries the version |
| `ksp("io.mcarle:konvert:4.5.1")` | Konvert's KSP processor — the only thing that generates `object <Name>Impl` |
| `implementation("io.mcarle:konvert-api:4.5.1")` | `@Konverter` and Konvert's other annotations on the compile classpath. `KonvertKoraExtensionFactory` resolves `io.mcarle.konvert.api.Konverter` and returns no extension when it is absent |

Versions: Kora's catalog pins `konvert = "4.5.1"` (`libs.konvert.api`, used by the extension's
tests), and `kora-kotlin-crud` pins both `io.mcarle:konvert` and `io.mcarle:konvert-api` at `4.5.1`.
`kora-bom` does not constrain `io.mcarle:*` — keep the processor and the API on the same version.

Kotlin does **not** use a `koraBom` configuration or `extendsFrom`, and it adds **no `kapt`
plugin**. Konvert runs in the same KSP pass as Kora's processors.

## Why Konvert and not MapStruct in Kotlin

- MapStruct ships only a javac annotation processor. Kora's Kotlin processors are KSP processors,
  and KSP does not run javac processors, so a `@Mapper` in Kotlin source never gets an
  implementation.
- Running MapStruct on Kotlin would need `kapt`, a separate compilation pipeline that is not part of
  the Kora 2.0 toolchain. The migrated Kotlin examples contain no `kapt` and map with Konvert.
- Konvert is a KSP processor: one more `ksp(...)` line, same compilation, same compile-time checks.

## How Kora discovers a @Konverter

Same fallback path as every mapping extension: `GraphBuilder` consults extensions only when no
declared component, `@Module` method, `@Nullable` or `Optional` satisfies the claim. Then
`KonvertKoraExtension`:

1. accepts the claimed type only if it is a class declaration of kind **`INTERFACE`**;
2. requires `io.mcarle.konvert.api.Konverter` on it;
3. requires the mapper's `@Tag` to equal the claim's tag;
4. looks up `<package>.<SimpleName>Impl` and, if present, emits a reference to that **object** with
   empty dependency lists; if absent it fails with *"Generated Konvert implementation was not found:
   expected type: `pkg.FooMapperImpl`"*.

So there is no `@Component` on the mapper and no module to include in `@KoraApp`:

```kotlin
import io.mcarle.konvert.api.Konverter

@Konverter
interface CarMapper {
    fun carToCarDto(car: Car): CarDto
}

@Component
class CarService(private val carMapper: CarMapper)
```

Kora's `KonvertKoraExtensionTest` asserts the resulting graph has two nodes — the mapper and the
root — and that a plain interface without `@Konverter` is **not** provided.

## Limits

| Limit | Source | Consequence |
|---|---|---|
| Interface only | `classKind != ClassKind.INTERFACE → return null` | `@Konverter` on an abstract class is ignored; the claim fails as an ordinary unresolved dependency |
| Generated `object` | the extension emits `CodeBlock.of("%T", implClassName)` — an object reference, not a constructor call | one singleton per mapper; there is no constructor to inject into |
| No graph dependencies | `ExtensionResult.CodeBlockResult(..., emptyList(), emptyList())` | the mapper can never receive a component — no repository, clock, config |
| Top-level impl name | `declaration.simpleName + "Impl"` in the mapper's package | Konvert drops enclosing type names, so two nested `@Konverter`s with the same simple name in one package collide |

## Mappers that need graph components

Delegate through a regular `@Component`. The `@Konverter` does the name-matched field copy; the
component takes the mapper **and** its collaborators and adds what needs the graph:

```kotlin
@Konverter
interface CarMapper {
    fun carToCarDto(car: Car): CarDto
}

@Component
class CarDtoAssembler(
    private val carMapper: CarMapper,
    private val registry: ManufacturerRegistry,
) {
    fun toView(car: Car): CarView = CarView(
        car = carMapper.carToCarDto(car),
        manufacturer = registry.displayName(car.make),
    )
}
```

Inject `CarDtoAssembler` where the enriched result is needed. Keep graph-derived values out of the
`@Konverter` target type, so Konvert never has to fill a property it has no source for. This is the Kotlin counterpart of the
Java MapStruct `uses` + constructor-injection pattern.

## Tagging a mapper

```kotlin
@Tag(Internal::class)
@Konverter
interface InternalCarMapper {
    fun carToCarDto(car: Car): CarDto
}

@Component
class CarService(@Tag(Internal::class) private val mapper: InternalCarMapper)
```

An untagged mapper answers only untagged claims, and vice versa; a mismatch surfaces as an ordinary
unresolved dependency.

## Troubleshooting

| Symptom | Cause and fix |
|---|---|
| Unresolved dependency on `FooMapper`, no Konvert message | `io.mcarle:konvert-api` is not on `implementation`, so the extension factory disabled itself — or `FooMapper` is an abstract class, or the tags differ |
| `Generated Konvert implementation was not found: expected type: pkg.FooMapperImpl` | `ksp("io.mcarle:konvert:…")` is missing, Konvert failed earlier in the same compilation (fix its first error), or two nested `@Konverter`s share a simple name |
| A `@Mapper` / `kapt` setup copied from Kora 1.x | Not a Kora 2.0 path. Remove `kotlin("kapt")`, the `kapt(...)` lines and the MapStruct dependencies; rewrite the mapper as a `@Konverter` interface |
| Mapper resolves but is never the generated object | A `@Module` method or `@Component` also provides the type. Extensions are the fallback, so your declaration wins silently. Delete one |
| IDE shows the interface unimplemented | Expected before a build. `./gradlew kspKotlin` or `./gradlew classes` |
