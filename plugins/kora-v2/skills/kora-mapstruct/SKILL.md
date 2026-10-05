---
name: kora-mapstruct
description: "DTO ↔ entity mapping in Kora 2.0, chosen by language with no crossover. Java: MapStruct — org.mapstruct @Mapper + mapstruct-processor on annotationProcessor. Kotlin: Konvert — @Konverter interface + the io.mcarle:konvert KSP processor; never MapStruct or kapt in Kotlin, never Konvert in Java. The extension inside annotation-processors / symbol-processors binds the generated *Impl with no @Component. Use for @Mapper, @Konverter, @Mapping, mapper wiring, and the removed mapstruct-extension coordinate."
license: Apache-2.0
metadata:
  kora-version: "2.x"
---

# kora-mapstruct — Java: MapStruct · Kotlin: Konvert

> **Kora sub-skill — obey the [kora-v2 meta rules](../../SKILL.md) on every task:** **R0** ground the workspace on Kora 2.0 refs before starting (framework source at tag `2.0.0.RC2` + `kora-examples` at `migration/2.0` + Kora 2.0 docs at koraframework.io/v2, which trail the source; 1.x `kora-docs` pages are never an authority) · **R1** read this sub-skill before writing code · **R2** Kora 2.0 APIs only — no Spring/Micronaut/Quarkus, no Kora 1.x APIs, no invented annotations or config keys · **R3** journal any incorrect Kora usage. Add comments/Javadoc only if asked.

## The rule: the language picks the tool

| Module language | Mapping library | Processor | Kora extension (already inside the aggregate) |
|---|---|---|---|
| **Java** | MapStruct (`org.mapstruct`) | `annotationProcessor "org.mapstruct:mapstruct-processor"` | `mapstruct-java-extension` in `io.koraframework:annotation-processors` |
| **Kotlin** | Konvert (`io.mcarle.konvert`) | `ksp("io.mcarle:konvert")` | `konvert-ksp-extension` in `io.koraframework:symbol-processors` |

There is no crossover in either direction:

- **Never MapStruct in Kotlin.** No Kotlin `@Mapper`, no `kotlin("kapt")`, no `kapt(...)` line.
  MapStruct is a javac annotation processor; Kora's Kotlin processors run in KSP, and KSP does not
  run javac processors. Konvert *is* a KSP processor, so it runs in the same compilation as Kora's
  own `symbol-processors` with no extra build wiring. (`symbol-processors` also carries a
  `mapstruct-ksp-extension`; it is not a supported mapping path — do not build on it.)
- **Never Konvert in Java.** Konvert generates Kotlin through KSP; a Java module has no KSP.

Kora generates no mappers itself. The extension binds an implementation the mapping library
generated, so the mapper interface is injectable like any component.

**Never `@Component` the mapper.** The extension supplies it, as a *last-resort fallback*:
`GraphBuilder` consults extensions only after declared components and `@Module` methods fail to
match the dependency claim. `@Component` on a mapper is `@Target(TYPE)`, so it compiles, and
`KoraAppProcessor.processComponents` then silently skips it because the mapper is an interface or
an abstract class. It does nothing. Delete it: it reads as wiring that isn't there.

There is **no `mapstruct-extension` in Kora 2.0**, and no extension is ever declared by hand — the
aggregate processors already contain them. What you declare is the third-party half: the mapping
library on the **compile** classpath plus its processor. The compile-classpath part is not optional:
each extension factory looks its annotation type up (`org.mapstruct.Mapper` /
`io.mcarle.konvert.api.Konverter`) and disables itself when it is absent, silently leaving you with
"no component found for `FooMapper`".

---

## Java: MapStruct

`gradle.properties`:

```properties
koraVersion=2.0.0.RC2
```

`build.gradle`:

```groovy
repositories { mavenCentral() }

configurations {
    koraBom
    annotationProcessor.extendsFrom(koraBom); compileOnly.extendsFrom(koraBom)
    implementation.extendsFrom(koraBom); api.extendsFrom(koraBom)
    testImplementation.extendsFrom(koraBom); testAnnotationProcessor.extendsFrom(koraBom)
}

dependencies {
    koraBom platform("io.koraframework:kora-bom:$koraVersion")

    annotationProcessor "io.koraframework:annotation-processors"          // carries mapstruct-java-extension
    annotationProcessor "org.mapstruct:mapstruct-processor:1.6.3"         // generates *MapperImpl
    implementation "org.mapstruct:mapstruct:1.6.3"                        // @Mapper on the compile classpath
}
```

`kora-bom` constrains only `io.koraframework:*`. **MapStruct is versioned by you**, and the API and
the processor must carry the *same* version.

```java
import org.mapstruct.Mapper;
import org.mapstruct.Mapping;
import org.mapstruct.ReportingPolicy;

@Mapper(unmappedTargetPolicy = ReportingPolicy.IGNORE)   // no @Component
public interface CarMapper {

    @Mapping(source = "numberOfSeats", target = "seatCount")
    CarTO map(Car car);
}
```

```java
import io.koraframework.common.annotation.Component;

@Component
public final class CarService {
    private final CarMapper mapper;

    public CarService(CarMapper mapper) {
        this.mapper = mapper;
    }
}
```

What the Java extension accepts and binds:

- `@Mapper` on an **interface or an abstract class**; nested mappers are supported
  (`pkg.Outer.Inner` → `pkg.Outer$InnerImpl`).
- The generated `<Name>Impl` must have **exactly one public constructor**; its parameters become
  ordinary graph dependencies. That is how a MapStruct mapper takes collaborators from the graph
  (`uses` + `injectionStrategy = CONSTRUCTOR` — see the
  [mapper reference](references/mapstruct-mapper-reference.md#mappers-that-need-dependencies)).
- `@Tag` on the mapper is honoured: it answers only a claim with the same tag.

**Processor order in the `dependencies` block does not matter.** `KoraAppProcessor` builds the graph
only when `roundEnv.processingOver()` is true — the last annotation-processing round — by which point
every `*MapperImpl` from earlier rounds is already in the element table. Kora's own extension test
registers `KoraAppProcessor` *before* MapStruct's `MappingProcessor` and passes.

### MapStruct version: `1.6.3` vs `1.5.5.Final` — both are real, pick `1.6.3`

| Source | Version |
|---|---|
| Kora's version catalog (`mapstruct = "1.6.3"`, used to compile and test `mapstruct-java-extension`) | **`1.6.3`** |
| `kora-examples` on `migration/2.0` — all four Java examples | `1.5.5.Final` |

`1.5.5.Final` entered those example builds long before the 2.0 work and was never touched by the
migration. **Recommend `1.6.3`**: it is what Kora's own extension is compiled and tested against.
Whichever you pick, `org.mapstruct:mapstruct` and `org.mapstruct:mapstruct-processor` must match; a
split pin fails at generation time with MapStruct's own errors, which mention nothing about Kora.

---

## Kotlin: Konvert

`build.gradle.kts`:

```kotlin
plugins {
    kotlin("jvm") version "2.4.20"
    id("com.google.devtools.ksp") version "2.3.12"
}

repositories { mavenCentral() }

dependencies {
    implementation(platform("io.koraframework:kora-bom:${property("koraVersion")}"))

    ksp("io.koraframework:symbol-processors:${property("koraVersion")}")  // carries konvert-ksp-extension
    ksp("io.mcarle:konvert:4.5.1")                                        // generates object <Name>Impl
    implementation("io.mcarle:konvert-api:4.5.1")                         // @Konverter on the compile classpath
}
```

```kotlin
import io.mcarle.konvert.api.Konverter

@Konverter                                   // interface only; no @Component
interface PetMapper {
    fun petWithCategoryToPetTO(pet: PetWithCategory): PetTO
    fun petCategoryToCategoryTO(category: PetCategory): CategoryTO
}
```

```kotlin
@Component
class PetService(private val mapper: PetMapper)
```

This is exactly what `kora-examples`' `kora-kotlin-crud` does on `migration/2.0`. Kora's catalog pins
`konvert = "4.5.1"` and the example pins both `io.mcarle:konvert` and `io.mcarle:konvert-api` at
`4.5.1`. Keep the two on the same version; `kora-bom` does not manage them.

### What the Konvert extension accepts — and its limits

`KonvertKoraExtension` is deliberately narrower than the MapStruct one:

| Limit | Consequence |
|---|---|
| `@Konverter` is recognised on an **interface only** | an abstract class with `@Konverter` is never provided — the claim just fails |
| Konvert generates a top-level **`object <SimpleName>Impl`**; Kora references that object as the component | there is no constructor, so the mapper is a singleton |
| The binding has **no dependencies** (empty dependency list) | a `@Konverter` can never receive graph components — no clock, repository, config |
| The impl is looked up as `<SimpleName>Impl` in the mapper's package, **enclosing type name dropped** | two nested `@Konverter`s with the same simple name in one package collide — rename one |

**Needs a graph dependency? Delegate through a `@Component`.** Keep the `@Konverter` for the
name-matched fields and put everything that needs the graph — generated ids, timestamps, lookups — in
a regular `@Component` that takes the mapper plus its collaborators:

```kotlin
@Component
class OrderViewAssembler(
    private val mapper: OrderMapper,          // the Konvert object, bound by the extension
    private val customers: CustomerRepository,
) {
    fun toView(order: Order): OrderView = OrderView(
        order = mapper.toDto(order),
        customerName = customers.findName(order.customerId),
    )
}
```

`@Tag` works as for MapStruct: `@Tag(X::class)` on the `@Konverter` interface, the same tag at the
injection point. Per-field mapping options are Konvert's own API — see
<https://mcarleio.github.io/konvert/>; Kora neither adds to nor constrains them.

---

## Asked for MapStruct in Kotlin?

Steer to Konvert and say why, briefly:

1. MapStruct ships only a javac annotation processor (`org.mapstruct.ap.MappingProcessor`). Kora's
   Kotlin processors are KSP processors, and KSP cannot run a javac processor, so nothing would
   generate the `*MapperImpl` for a Kotlin `@Mapper`.
2. The only way to run it would be `kapt` — a second, separate compilation pipeline. `kapt` is not
   part of the Kora 2.0 toolchain: the migrated Kotlin examples contain no `kapt` at all and map with
   Konvert.
3. Konvert gives the same compile-time mapping as one more `ksp(...)` line.

Then write the `@Konverter` version of what they asked for. Do not offer `kapt`, and do not offer a
Kotlin `@Mapper` "that only needs an existing impl".

## Decision: which tool

| Situation | Use |
|---|---|
| Java module, 5+ DTO/entity pairs with high field overlap | MapStruct |
| Kotlin module | Konvert |
| Kotlin mapping that needs graph components | Konvert for the field copy, wrapped by a `@Component` |
| 1–3 mappers, or significant per-field logic | Hand-written mapping — no processor, no extension |

## Mapper contracts in 2.0

- Mapper methods are **ordinary synchronous methods**. Never `Mono`/`Flux`/`CompletionStage`, never
  `suspend` — those are not Kora 2.0 contracts.
- Java nullability is **JSpecify** (`org.jspecify.annotations.Nullable`), and it is *type-use*:
  `List<@Nullable String>`, `Outer.@Nullable Inner`. Kotlin nullability is the type (`T?`).

---

## What's in `references/`

| Document | Purpose |
|----------|---------|
| [`mapstruct-mapper-reference.md`](references/mapstruct-mapper-reference.md) | Java: discovery rules, generated-impl naming, `@Tag`, mappers with dependencies, `@Mapper`/`@Mapping`/`@MappingTarget`/`@Named` |
| [`mapstruct-config-reference.md`](references/mapstruct-config-reference.md) | Java: MapStruct build wiring, versions, `componentModel`, `@MapperConfig`, troubleshooting |
| [`mapstruct-expressions-reference.md`](references/mapstruct-expressions-reference.md) | Java: MapStruct `expression`, `defaultValue`, `constant`, `nullValuePropertyMappingStrategy` |
| [`konvert-reference.md`](references/konvert-reference.md) | Kotlin: Konvert build wiring, discovery, limits, `@Tag`, delegating through a `@Component`, troubleshooting |

## What's in `assets/`

| Java (MapStruct) | Kotlin (Konvert) |
|---|---|
| `OrderMapper.java.template` — `@Mapper` with renames, expressions, PATCH update | `OrderMapper.kt.template` — `@Konverter` plus the `@Component` that adds what Konvert cannot express |
| `CarMapper.java.template` — `uses` + constructor injection of a graph helper | `CarMapper.kt.template` — `@Konverter` delegated through a `@Component` with a graph helper |
| `mapstruct.gradle.snippet` — Groovy DSL MapStruct wiring | `konvert.gradle.kts.snippet` — Kotlin DSL Konvert wiring |

---

## Common pitfalls

| Symptom | Cause / fix |
|---|---|
| `io.koraframework:mapstruct-extension` does not resolve | It does not exist in 2.0. Declare nothing — `annotation-processors` / `symbol-processors` already carry the right extension |
| No component found for `FooMapper` | The mapping library is missing from the **compile** classpath, so the extension factory disabled itself. Java: `implementation "org.mapstruct:mapstruct:…"`. Kotlin: `implementation("io.mcarle:konvert-api:…")` |
| `MapStruct mapper implementation was not generated for FooMapper` (Java) | Kora found `@Mapper` but no `FooMapperImpl`. `mapstruct-processor` is not on `annotationProcessor`, or MapStruct errored earlier in the same compile |
| A Kotlin `@Mapper` never gets an implementation | MapStruct cannot run under KSP. Rewrite it as a `@Konverter` interface |
| `Generated Konvert implementation was not found: expected type: pkg.FooMapperImpl` | `ksp("io.mcarle:konvert:…")` is missing, Konvert failed earlier in the same compile, or two nested `@Konverter`s share a simple name |
| `@Konverter` abstract class is never injected | The extension accepts interfaces only. Make it an interface |
| A `@Konverter` needs a repository / clock / config | Impossible — the generated `object` has no dependencies. Wrap it in a `@Component` |
| `Generated class FooMapperImpl must have exactly one public constructor` (Java) | A `componentModel` / `injectionStrategy` combination produced several. Pin one strategy, or provide the mapper as a plain `@Component` yourself |
| `@Component` on the mapper changes nothing | Correct — it is silently skipped (interface / abstract class). Remove the annotation |
| A hand-written `@Module` method shadows the mapper | Extensions are the fallback, so your declaration silently wins and the generated `*Impl` is never used. Delete one of the two |
| Stale `ru.tinkoff.kora` errors from generated mapper code | Old output under `build/`. `./gradlew clean` and rebuild; never edit generated sources |

---

## Upstream references

- Kora extensions: <https://github.com/kora-projects/kora/tree/2.0.0.RC2/mapping>
  (`mapstruct-java-extension`, `konvert-ksp-extension`)
- Kora 2.0 docs: <https://koraframework.io/v2/en/documentation/mapstruct/>
- Working Java example: <https://github.com/kora-projects/kora-examples/tree/migration/2.0/examples/java/kora-java-crud>
- Working Kotlin (Konvert) example: <https://github.com/kora-projects/kora-examples/tree/migration/2.0/examples/kotlin/kora-kotlin-crud>
- MapStruct: <https://mapstruct.org/documentation/stable/reference/html/>
- Konvert: <https://mcarleio.github.io/konvert/>
