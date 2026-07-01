---
name: kora-mapstruct
description: "Integrates the MapStruct mapping library with Kora. A @Mapper interface (org.mapstruct.Mapper) is auto-discovered by Kora's MapStruct extension and its generated *MapperImpl is registered as a component in the DI graph - no @Component needed. Use when converting between request/response DTOs, domain entities, and persistence rows; when renaming fields with @Mapping, ignoring fields, computing values with expression/constant/defaultValue, dispatching to @Named helpers, or doing PATCH-style updates with @MappingTarget. Java uses the MapStruct annotationProcessor; Kotlin needs kapt and collides with KSP. Triggers - @Mapper, @Mapping, org.mapstruct mapstruct-processor, DTO-entity mapping."
---

# kora-mapstruct — MapStruct mappers as Kora components

MapStruct generates the mapper implementation at compile time. Kora's MapStruct
extension detects every `@Mapper` interface, finds the generated `*MapperImpl`,
and registers it as a singleton component in the DI graph. You inject the mapper
interface by constructor like any other component — **no `@Module` to plug in and
no `@Component` on the mapper**.

All Kora artifacts inherit their version from the `kora-parent` BOM
(`ru.tinkoff.kora:kora-parent:1.2.17` in the example repo) — never version
individual `ru.tinkoff.kora:*` dependencies. MapStruct artifacts are versioned
explicitly (`1.5.5.Final`).

## Quick Start (Java)

`build.gradle`:

```groovy
dependencies {
    koraBom platform("ru.tinkoff.kora:kora-parent:1.2.17")

    // Kora annotation processor (mandatory)
    annotationProcessor "ru.tinkoff.kora:annotation-processors"
    // MapStruct processor — generates the *MapperImpl classes
    annotationProcessor "org.mapstruct:mapstruct-processor:1.5.5.Final"
    // MapStruct runtime
    implementation "org.mapstruct:mapstruct:1.5.5.Final"
}
```

`PetMapper.java` (adapted from `.kora-agent/kora-examples/examples/java/kora-java-crud`):

```java
import org.mapstruct.Mapper;
import org.mapstruct.Mapping;
import org.mapstruct.ReportingPolicy;

@Mapper(unmappedTargetPolicy = ReportingPolicy.IGNORE) // no @Component needed
public interface CarMapper {

    @Mapping(source = "numberOfSeats", target = "seatCount")
    CarTO map(Car car);
}
```

Inject the mapper interface by constructor:

```java
import ru.tinkoff.kora.common.Component;

@Component
public final class CarService {
    private final CarMapper mapper;

    public CarService(CarMapper mapper) {
        this.mapper = mapper;
    }
}
```

**Kotlin:** MapStruct requires `kapt`, which collides with Kora's KSP. See
[`references/mapstruct-config-reference.md`](references/mapstruct-config-reference.md).
The Kora team's own Kotlin CRUD example keeps the MapStruct/kapt wiring commented
out and writes its mappers by hand.

---

## What's in `references/`

| Document | Purpose |
|----------|---------|
| [`mapstruct-mapper-reference.md`](references/mapstruct-mapper-reference.md) | `@Mapper`, `@Mapping` parameters, `@MappingTarget`, `@Named`, `@AfterMapping` |
| [`mapstruct-config-reference.md`](references/mapstruct-config-reference.md) | Java and Kotlin setup, kapt + KSP coexistence, version pins, troubleshooting |
| [`mapstruct-expressions-reference.md`](references/mapstruct-expressions-reference.md) | `expression`, `defaultValue`, `constant`, `nullValuePropertyMappingStrategy` |

## What's in `assets/`

- `OrderMapper.java.template` — top-level `@Mapper` with renames, ignores, expressions, PATCH update
- `mapstruct.gradle.snippet` — Java (Groovy DSL) dependencies
- `mapstruct.gradle.kts.snippet` — Kotlin DSL with kapt + KSP wiring

---

## Decision: use or skip MapStruct

| Use MapStruct | Skip (hand-written) |
|---------------|---------------------|
| 5+ DTO/entity pairs with high field overlap | 1–3 mappers |
| Java codebase | Kotlin codebase (kapt + KSP friction) |
| Compile-time shape verification needed | Significant per-field logic |

MapStruct is most valuable when many fields map by name and you want the compiler
to flag unmapped targets. For a couple of fields, a plain constructor mapping is
clearer than wiring the processor.

---

## Core patterns

- **Field rename:** `@Mapping(source = "numberOfSeats", target = "seatCount")`.
- **Ignore a target:** `@Mapping(target = "id", ignore = true)` (e.g. DB-generated id).
- **Suppress unmapped-target warnings:** `@Mapper(unmappedTargetPolicy = ReportingPolicy.IGNORE)`.
- **Computed value:** `@Mapping(target = "id", expression = "java(java.util.UUID.randomUUID())")`.
- **Enum ↔ String:** dispatch to a `@Named` static helper via `qualifiedByName`.
- **PATCH update:** `void applyPatch(@MappingTarget Order existing, PatchOrderDto patch)`
  with `@BeanMapping(nullValuePropertyMappingStrategy = NullValuePropertyMappingStrategy.IGNORE)`.

See the reference files for the full annotation parameter tables and examples.

---

## Common pitfalls

| Symptom | Fix |
|---------|-----|
| Mapper not found in the graph | Add `@Mapper` to the interface — Kora discovers only annotated mappers |
| Redundant binding / confusion | Remove `@Component` from the mapper; Kora wires the generated impl |
| `*MapperImpl` not found | Run `./gradlew classes` so the MapStruct processor generates it first |
| Unmapped-target build warnings | Add `unmappedTargetPolicy = ReportingPolicy.IGNORE` or map/ignore the field |
| Mapper nested in `@KoraApp` with extra nested types | Hoist the `@Mapper` to a top-level file |
| Kotlin first build fails | Expected with kapt + KSP — run `./gradlew build` a second time |
| Kotlin kapt + KSP conflict | Use Kotlin `1.9.10` + KSP `1.9.10-1.0.13`, or write the mapper by hand |
