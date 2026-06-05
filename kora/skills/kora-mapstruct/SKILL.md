---
name: kora-mapstruct
description: MapStruct DTO-to-entity mapper integration in Kora: @Mapper-annotated interfaces auto-discovered as @Components, compile-time generated mappers, injection into DI graph. Use when converting between request DTOs, domain entities, and persistence rows. Supports Java and Kotlin (kapt/KSP). Triggers: @Mapper, @Mapping, MapStruct processor, mapstruct-processor, MapstructKoraExtension, DTO mapping, entity mapping.
---

# kora-mapstruct — MapStruct mappers as Kora components

Read this first when:
- adding a mapper between request DTO and domain entity (or domain ↔ persistence row),
- wiring MapStruct's annotation processor alongside Kora's annotation processors,
- choosing between hand-written mappers and MapStruct-generated ones,
- configuring kapt + KSP compatibility on a Kotlin project,
- mapping nested objects, collections, or custom type conversions with `@Mapping`.

## How the integration works

Kora ships a compile-time extension (`MapstructKoraExtension` in `ru.tinkoff.kora.mapstruct.java.extension`) that **discovers `@Mapper`-annotated interfaces** during graph construction and registers their generated implementations as Kora components. You don't need `@Component` on the mapper interface — `@Mapper` is enough.

MapStruct's annotation processor runs first to generate the implementation class (e.g., `CarMapperImpl`). Kora's annotation processor then sees the `@Mapper` interface, knows the impl exists, and wires it into the graph as a singleton.

No `*Module` to plug in. Just add the right dependencies and `@Mapper`-annotated interfaces, and they become injectable.

## Setup — Java

```groovy
dependencies {
    annotationProcessor "ru.tinkoff.kora:annotation-processors"
    annotationProcessor "org.mapstruct:mapstruct-processor:1.5.5.Final"

    implementation "org.mapstruct:mapstruct:1.5.5.Final"
}
```

Order matters: MapStruct's processor runs first (generates the impl), then Kora's picks up the interface. Gradle handles the ordering for you when both are on the `annotationProcessor` classpath.

## Setup — Kotlin

> **MapStruct on Kotlin requires `kapt`, not KSP**. MapStruct doesn't support KSP yet; you must use kapt. That collides with Kora's KSP requirement, so you end up running both processors and need to wire them carefully.

```kotlin
plugins {
    kotlin("kapt") version "1.9.10"                            // pin to 1.9.10 — see compatibility note below
    id("com.google.devtools.ksp") version "1.9.10-1.0.13"     // last KSP version that works with this kapt
}

ksp {
    allowSourcesFromOtherPlugins = true                        // KSP must see kapt-generated stubs
}

// Make KSP run AFTER kapt so it sees the generated mapper impls
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

**Compatibility caveat (from Kora docs):**
- Kotlin `1.9.10` + KSP `1.9.10-1.0.13` is the **last working combination** for kapt + KSP coexistence at the Gradle Plugin level. Later KSP versions broke the integration.
- **First build often fails.** Run `./gradlew build` again — by the second run, kapt has produced the mapper impls and KSP sees them. This is known KSP behavior, not a bug in your setup.

If you're starting a new Kotlin Kora project today and MapStruct isn't a hard requirement, consider hand-written mappers (or `kora-server`'s `HttpServerRequestMapper` / `HttpServerResponseMapper`) instead — the kapt+KSP dance is a real maintenance cost.

## Usage

```java
@KoraApp
public interface Application extends /* ... */ {

    enum CarType { SEDAN, COUPE }

    record Car(String make, int numberOfSeats, CarType type) {}
    record CarDto(String make, int seatCount, String type) {}

    @Mapper                                                    // ← no @Component needed
    interface CarMapper {

        @Mapping(source = "numberOfSeats", target = "seatCount")
        @Mapping(source = "type", target = "type", qualifiedByName = "carTypeToString")
        CarDto toDto(Car car);

        @Named("carTypeToString")
        static String carTypeToString(CarType t) { return t.name().toLowerCase(); }
    }

    @Component
    default CarService carService(CarMapper carMapper) {       // mapper injected by Kora
        return new CarService(carMapper);
    }
}
```

The mapper interface lives inside the `@KoraApp` interface (or as a standalone interface in the same source set). MapStruct generates `CarMapperImpl`. Kora's extension wires the impl as a `CarMapper` component.

### Mapper in its own file (recommended for non-trivial cases)

```java
package com.example.app.mapper;

import com.example.app.dto.OrderDto;
import com.example.app.entity.Order;
import org.mapstruct.Mapper;
import org.mapstruct.Mapping;
import org.mapstruct.MappingTarget;

@Mapper                                                        // top-level interface
public interface OrderMapper {

    @Mapping(target = "id", ignore = true)
    @Mapping(target = "createdAt", expression = "java(java.time.OffsetDateTime.now())")
    Order toEntity(OrderDto dto);

    @Mapping(source = "createdAt", target = "created")
    OrderDto toDto(Order entity);

    void update(@MappingTarget Order existing, OrderDto patch);  // in-place update
}
```

Inject `OrderMapper` like any other Kora component: `public OrderService(OrderMapper mapper) { ... }`.

## Common patterns

### DTO ↔ entity mapping at controller boundary

```java
@HttpController
public final class OrdersController {

    private final OrdersService service;
    private final OrderMapper mapper;

    public OrdersController(OrdersService service, OrderMapper mapper) {
        this.service = service;
        this.mapper = mapper;
    }

    @Json
    @HttpRoute(method = HttpMethod.POST, path = "/orders")
    public OrderDto create(@Json CreateOrderDto body) {
        var entity = mapper.toEntity(body);
        var saved = service.persist(entity);
        return mapper.toDto(saved);
    }
}
```

Three layers, two mappings — clean separation.

### Patch / partial update

```java
@Mapping(target = "id", ignore = true)
@Mapping(target = "createdAt", ignore = true)
@BeanMapping(nullValuePropertyMappingStrategy = NullValuePropertyMappingStrategy.IGNORE)
void applyPatch(@MappingTarget Order existing, PatchOrderDto patch);
```

`NullValuePropertyMappingStrategy.IGNORE` makes the mapper skip null fields in the source — perfect for PATCH semantics. Combine with `JsonNullable<T>` from `kora-json` to distinguish "absent" from "explicitly null".

### Enum ↔ String

```java
@Mapping(source = "status", target = "status", qualifiedByName = "statusToString")
OrderDto toDto(Order entity);

@Named("statusToString")
static String statusToString(OrderStatus s) {
    return s == null ? null : s.name().toLowerCase();
}
```

For symmetric enum ↔ String, define both `*ToString` and `*FromString` `@Named` methods.

## Choosing MapStruct vs hand-written mappers

| Situation | Pick |
|-----------|------|
| Many similar DTO ↔ entity pairs with 80% one-to-one field overlap | MapStruct |
| 2–3 mappers in the whole codebase | Hand-written — kapt+KSP overhead isn't worth it |
| Kotlin codebase, latest Kotlin/KSP versions | Hand-written (or factor mapping into the DTO class itself) — kapt compatibility is a maintenance burden |
| Partial updates with `JsonNullable<T>` | MapStruct + `nullValuePropertyMappingStrategy = IGNORE` works, but hand-written is often clearer |
| Mappers with significant business logic | Hand-written — MapStruct's `@AfterMapping` and expression strings get unreadable |

## What's in `references/`

- `mapstruct.md` — distilled doc with version pins, kapt+KSP recipe, full `@Mapping` parameter list.

## What's in `assets/`

- `OrderMapper.java.template` — top-level `@Mapper` interface with renames, ignores, expressions, in-place update.
- `mapstruct.gradle.snippet` (Groovy) — exact dependency block.
- `mapstruct.gradle.kts.snippet` (Kotlin DSL) — including kapt+KSP coexistence.

## Common pitfalls

- **Adding `@Component` on a `@Mapper` interface.** Redundant; Kora's MapStruct extension already registers it. Doesn't break anything, but obscures intent.
- **Putting MapStruct in `implementation` for the processor.** It must be `annotationProcessor` (Java) or `kapt` (Kotlin) — `implementation "org.mapstruct:mapstruct-processor"` does nothing.
- **Kotlin: upgrading Kotlin or KSP past 1.9.10 / 1.9.10-1.0.13.** Breaks kapt+KSP coexistence at the Gradle Plugin level. Stick to the pinned versions or migrate the mappers to hand-written.
- **Kotlin first build fails.** Expected — kapt+KSP need two passes. Re-run; if it still fails, check `ksp.allowSourcesFromOtherPlugins = true` and the `dependsOn(kaptKotlin)` task wiring.
- **Mapper inside `@KoraApp` interface with unresolved nested types.** MapStruct gets confused by deeply nested generic types. Hoist the mapper to its own file at top level.
- **Generated `CarMapperImpl` referenced before the build runs.** The IDE shows red squiggles until you build at least once. Run `./gradlew classes` to generate the impls.

## AGENTS.md alignment

- **Compile-time DI** — MapStruct's generated impls are real Java classes, not reflective proxies. Aligns with Kora's "no runtime reflection" principle.
- **Reuse Kora's annotation-processor pipeline** — no separate runtime component registry; the extension wires generated mappers into the regular graph.
- **Kotlin warning is explicit** — the kapt+KSP friction is documented honestly so users can make an informed call between MapStruct and hand-written mappers.

---

## Common Pitfalls

- **Missing `@Mapper`** → interface not discovered without `@Mapper` annotation.
- **kapt/KSP conflict** → Kotlin: use either kapt or KSP, not both for MapStruct.
- **Generated impl not found** → ensure MapStruct processor runs before Kora's processor.
- **Missing `@Component` assumption** → `@Mapper` is enough; `@Component` not needed (Kora extension handles it).
- **Cyclic mapping** → use `@Context` or custom methods for cyclic object graphs.
