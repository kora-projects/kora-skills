# Mapper Reference (Java) — discovery, naming, and the MapStruct annotations

**Scope: Java only.** MapStruct is the Java mapping path in Kora 2.0; Kotlin uses Konvert — see
[`konvert-reference.md`](konvert-reference.md).

**Verified against** `mapping/mapstruct-java-extension` (sources and `MapstructKoraExtensionTest`)
on Kora `master` for `2.0.0.RC2` (<https://github.com/kora-projects/kora/tree/2.0.0.RC2/mapping>)
and the working examples on `kora-examples` branch `migration/2.0`. MapStruct annotation semantics come from MapStruct itself:
<https://mapstruct.org/documentation/stable/reference/html/>.

## Contents

- [How Kora discovers a mapper](#how-kora-discovers-a-mapper)
- [Generated implementation names](#generated-implementation-names)
- [Tagging a mapper](#tagging-a-mapper)
- [Mappers that need dependencies](#mappers-that-need-dependencies)
- [Interface vs abstract class](#interface-vs-abstract-class)
- [@Mapping parameters](#mapping-parameters)
- [@MappingTarget for PATCH updates](#mappingtarget-for-patch-updates)
- [@Named helpers](#named-helpers)
- [@AfterMapping / @BeforeMapping hooks](#aftermapping--beforemapping-hooks)
- [Complete Java example](#complete-java-example)

## How Kora discovers a mapper

There is **no module to plug into `@KoraApp`** and no `@Component` on the mapper. Discovery is a
graph-resolution fallback, and it runs in this exact order:

1. `GraphBuilder` cannot satisfy a dependency claim for `FooMapper` from declared components,
   `@Module` methods, templates, `@Nullable` or `Optional`.
2. It calls `Extensions.findExtension(...)`. Extensions are `ServiceLoader`-discovered from the
   **processor** classpath (`annotationProcessor` / `ksp`), which is why the aggregate processor
   artifact is what brings them in.
3. `MapstructKoraExtensionFactory` returns an extension only if `org.mapstruct.Mapper` resolves on
   the **compile** classpath. No MapStruct dependency → no extension → the claim just fails.
4. The extension checks: declared type, kind is interface or class, carries `@Mapper`, and its
   `@Tag` matches the claim's tag.
5. It looks up the generated implementation type. Missing → a `ProcessingErrorException` reading
   *"MapStruct mapper implementation was not generated for `Foo`… Kora expected generated class
   `pkg.FooImpl`"*.
6. It requires **exactly one public constructor** on that implementation and binds it, so the
   constructor's parameters become ordinary graph dependencies. Two or more public constructors →
   *"Generated class `…` must have exactly one public constructor so Kora can use it as a
   dependency."*

Two consequences worth internalising:

- **Order of `annotationProcessor` lines is irrelevant.** `KoraAppProcessor` builds the graph only
  in the final round (`roundEnv.processingOver()`), after every other processor has emitted its
  sources. Kora's own extension test registers `KoraAppProcessor` *before* MapStruct's
  `MappingProcessor` and passes.
- **A declaration of your own always wins**, silently. If you also write a `@Module` method
  returning `FooMapper`, the extension is never consulted and the generated `FooMapperImpl` is dead
  code. There is no "duplicate component" error for this — pick one.

```java
@Mapper  // ← nothing else needed
public interface CarMapper {
    CarDto toDto(Car car);
}
```

## Generated implementation names

Kora computes the expected name itself; it does not search. Getting the shape wrong is what produces
the "was not generated" error.

| Mapper | MapStruct / Kora expects |
|---|---|
| top-level `pkg.CarMapper` | `pkg.CarMapperImpl` |
| nested `pkg.SomeInterface.TestMapper` | `pkg.SomeInterface$TestMapperImpl` |

Enclosing type names are joined with `$` and the suffix `Impl` appended. **Nested `@Mapper`
interfaces are supported**; Kora's Java extension has a dedicated test for the nested case.

## Tagging a mapper

The extension reads `@Tag` off the mapper declaration and only answers a claim whose tag matches.
So two mappers producing the same type can coexist:

```java
import io.koraframework.common.annotation.Tag;

@Tag(Internal.class)
@Mapper
public interface InternalCarMapper { CarDto toDto(Car car); }
```

```java
public CarService(@Tag(Internal.class) InternalCarMapper mapper) { … }
```

An untagged mapper answers only untagged claims, and vice versa — a tag mismatch surfaces as an
ordinary unresolved dependency, not as a MapStruct error. Matching uses the graph's normal rule, so a
`@Tag(Tag.Any.class)` claim accepts the mapper whatever its tag, and the graph node is registered
under the mapper's tag. `@Tag` on a parameter of the generated `Impl` constructor (e.g. a tagged
`uses` collaborator) is honoured as well. Tagged mappers resolve correctly from `2.0.0.RC2` on; on
`2.0.0.RC1` a tagged `@Mapper` was not matched to a tagged claim.

## Mappers that need dependencies

Because Kora binds the generated implementation's **constructor**, a mapper can pull collaborators
out of the graph — but only if MapStruct actually emits a constructor for them. By default it does
not: it instantiates `uses` mappers itself. You have to ask for constructor injection:

```java
@Component
public final class DateMapper {
    public String asString(Date date) { … }
    public Date asDate(String date) { … }
}

@Mapper(uses = DateMapper.class,
        injectionStrategy = org.mapstruct.InjectionStrategy.CONSTRUCTOR,
        componentModel = "jakarta")
public interface CarMapper {
    @Mapping(source = "numberOfSeats", target = "seatCount")
    CarDto carToCarDto(Car car);
}
```

Kora then resolves `DateMapper` from the graph and passes it to `CarMapperImpl`'s constructor. This
is the shape Kora's own `testWithDependencies` covers, and it asserts a three-node graph:
`DateMapper`, the mapper, and the root.

`componentModel = "jakarta"` makes MapStruct annotate the generated class with `jakarta.inject`
annotations, so **`jakarta.inject:jakarta.inject-api` must be on the compile classpath** — Kora's
extension module adds exactly that dependency to build this test. Kora itself reads none of those
annotations; only the constructor matters. If you do not need `uses`, leave `componentModel` alone:
plain `@Mapper` works and the default generated implementation has a single implicit public
constructor.

## Interface vs abstract class

| Form | When |
|---|---|
| `interface` | Default. Pure mapping, no state |
| `abstract class` | Non-trivial helpers or state; MapStruct implements the abstract methods |

Both are accepted by the MapStruct extension (it allows `INTERFACE` and `CLASS`).

```java
@Mapper
public abstract class ComplexMapper {

    @Named("sanitize")
    protected String sanitize(String s) {
        return s == null ? null : s.trim().toLowerCase();
    }

    @Mapping(source = "name", target = "name", qualifiedByName = "sanitize")
    public abstract UserDto toDto(User user);
}
```

## @Mapping parameters

| Parameter | Purpose | Example |
|-----------|---------|---------|
| `source` | Source property name | `@Mapping(source = "numberOfSeats", target = "seatCount")` |
| `target` | Target property name | `@Mapping(target = "id", ignore = true)` |
| `ignore = true` | Skip this target | `@Mapping(target = "createdAt", ignore = true)` |
| `expression` | Inline Java expression | `@Mapping(target = "id", expression = "java(java.util.UUID.randomUUID())")` |
| `defaultValue` | Used when the source is null | `@Mapping(target = "status", defaultValue = "PENDING")` |
| `constant` | Fixed value, source ignored | `@Mapping(target = "type", constant = "INTERNAL")` |
| `qualifiedByName` | Dispatch to a `@Named` helper | `@Mapping(source = "status", target = "status", qualifiedByName = "statusToString")` |
| `dateFormat` | Date ↔ String format | `@Mapping(source = "date", target = "dateStr", dateFormat = "yyyy-MM-dd")` |
| `numberFormat` | Number ↔ String format | `@Mapping(source = "amount", target = "amountStr", numberFormat = "$0.00")` |

`@Mapper(unmappedTargetPolicy = ReportingPolicy.IGNORE)` silences unmapped-target reports. Every
MapStruct mapper in `kora-examples` uses it. It changes nothing about how Kora binds the
implementation.

## @MappingTarget for PATCH updates

Updates an existing instance instead of building a new one:

```java
@BeanMapping(nullValuePropertyMappingStrategy = NullValuePropertyMappingStrategy.IGNORE)
@Mapping(target = "id", ignore = true)
@Mapping(target = "createdAt", ignore = true)
void applyPatch(@MappingTarget Order existing, PatchOrderDto patch);
```

- `NullValuePropertyMappingStrategy.IGNORE` skips null source properties — PATCH semantics.
- To distinguish "field absent" from "explicitly null" in the request body, pair it with
  `JsonNullable<T>` from [`kora-json`](../../kora-json/SKILL.md).
- `@MappingTarget` needs a **mutable** target. Java records cannot be patched in place; map to a new
  instance instead.

## @Named helpers

```java
@Mapping(source = "status", target = "status", qualifiedByName = "statusToString")
OrderDto toDto(Order entity);

@Named("statusToString")
static String statusToString(OrderStatus s) {
    return s == null ? null : s.name().toLowerCase();
}
```

For a symmetric enum ↔ String pair, declare both directions and reference each by name.

## @AfterMapping / @BeforeMapping hooks

```java
@AfterMapping
default void postProcess(@MappingTarget OrderDto out, Order in) {
    out.setComputedField(in.amount().multiply(in.taxRate()));
}
```

Hooks run inside the generated implementation as plain synchronous code. Three or more of them is a
signal that a hand-written mapper would read better.

## Complete Java example

```java
package com.example.app.mapper;

import com.example.app.dto.CreateOrderDto;
import com.example.app.dto.OrderDto;
import com.example.app.entity.Order;
import com.example.app.entity.OrderStatus;
import org.mapstruct.Mapper;
import org.mapstruct.Mapping;
import org.mapstruct.Named;
import org.mapstruct.ReportingPolicy;

@Mapper(unmappedTargetPolicy = ReportingPolicy.IGNORE)
public interface OrderMapper {

    @Mapping(target = "id", expression = "java(java.util.UUID.randomUUID())")
    @Mapping(target = "createdAt", expression = "java(java.time.OffsetDateTime.now())")
    Order toEntity(CreateOrderDto dto);

    @Mapping(source = "createdAt", target = "created")
    @Mapping(source = "status", target = "status", qualifiedByName = "statusToString")
    OrderDto toDto(Order entity);

    @Named("statusToString")
    static String statusToString(OrderStatus s) {
        return s == null ? null : s.name().toLowerCase();
    }
}
```

Mapper methods are ordinary synchronous methods. Kora 2.0 has no reactive, `CompletionStage` or
`suspend` contracts — never give a mapper one.
