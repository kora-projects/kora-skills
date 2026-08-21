# MapStruct Mapper Reference

**Source:** `.kora-agent/kora-docs/mkdocs/docs/en/documentation/mapstruct.md`,
`.kora-agent/kora-examples/examples/java/kora-java-crud/src/main/java/ru/tinkoff/kora/example/crud/model/mapper/PetMapper.java`

## Contents

- [@Mapper interface discovery](#mapper-interface-discovery)
- [Mapper interface vs abstract class](#mapper-interface-vs-abstract-class)
- [@Mapping annotation parameters](#mapping-annotation-parameters)
- [@MappingTarget for in-place updates](#mappingtarget-for-in-place-updates)
- [@Named helper methods](#named-helper-methods)
- [@AfterMapping / @BeforeMapping hooks](#aftermapping--beforemapping-hooks)
- [Complete example](#complete-example)

## @Mapper interface discovery

Kora's MapStruct extension (`MapstructKoraExtension`) automatically discovers and
registers MapStruct mappers during annotation processing:

1. Detects the `org.mapstruct.Mapper` annotation on an interface or abstract class
2. Looks up the MapStruct-generated implementation class (e.g. `CarMapperImpl`)
3. Wires that generated impl into the DI graph as a component

**No `@Component` needed** — `@Mapper` is sufficient. Kora's extension wires the
generated impl as an injectable component.

```java
@Mapper  // ← no @Component needed
public interface CarMapper {
    CarDto toDto(Car car);
}
```

```kotlin
@Mapper  // ← no @Component needed
interface CarMapper {
    fun toDto(car: Car): CarDto
}
```

## Mapper Interface vs Abstract Class

| Form | When to Use |
|------|-------------|
| `interface` (preferred) | Standard case — pure mapping, no state |
| `abstract class` | Need non-trivial helper methods or state |

```java
@Mapper
public abstract class ComplexMapper {
    // Can have fields and non-trivial helper methods.
    // A method referenced via qualifiedByName must carry @Named.
    @Named("sanitize")
    protected String sanitize(String s) {
        return s == null ? null : s.trim().toLowerCase();
    }

    @Mapping(source = "name", target = "name", qualifiedByName = "sanitize")
    public abstract UserDto toDto(User user);
}
```

## @Mapping Annotation Parameters

| Parameter | Purpose | Example |
|-----------|---------|---------|
| `source` | Source field name | `@Mapping(source = "numberOfSeats", target = "seatCount")` |
| `target` | Target field name | `@Mapping(target = "id", ignore = true)` |
| `ignore = true` | Skip this target field | `@Mapping(target = "createdAt", ignore = true)` |
| `expression` | Inline Java expression | `@Mapping(target = "id", expression = "java(java.util.UUID.randomUUID())")` |
| `defaultValue` | Used when source is null | `@Mapping(target = "status", defaultValue = "PENDING")` |
| `constant` | Fixed value | `@Mapping(target = "type", constant = "INTERNAL")` |
| `qualifiedByName` | Dispatch to `@Named` helper | `@Mapping(source = "status", target = "status", qualifiedByName = "statusToString")` |
| `dateFormat` | Date ↔ String format | `@Mapping(source = "date", target = "dateStr", dateFormat = "yyyy-MM-dd")` |
| `numberFormat` | Number ↔ String format | `@Mapping(source = "amount", target = "amountStr", numberFormat = "$0.00")` |

## @MappingTarget for In-Place Updates

Use for PATCH semantics — updates an existing instance instead of creating a new one:

```java
@Mapping(target = "id", ignore = true)
@Mapping(target = "createdAt", ignore = true)
@BeanMapping(nullValuePropertyMappingStrategy = NullValuePropertyMappingStrategy.IGNORE)
void applyPatch(@MappingTarget Order existing, PatchOrderDto patch);
```

**Key points:**
- `NullValuePropertyMappingStrategy.IGNORE` skips null source fields
- Combine with `JsonNullable<T>` from `kora-json` to distinguish "absent" from "explicitly null"

## @Named Helper Methods

Define custom mapping logic for specific fields:

```java
@Mapping(source = "status", target = "status", qualifiedByName = "statusToString")
OrderDto toDto(Order entity);

@Named("statusToString")
static String statusToString(OrderStatus s) {
    return s == null ? null : s.name().toLowerCase();
}
```

For symmetric enum ↔ String, define both directions:

```java
@Named("statusToString")
static String statusToString(OrderStatus s) { return s.name().toLowerCase(); }

@Named("stringToStatus")
static OrderStatus stringToStatus(String s) { return OrderStatus.valueOf(s.toUpperCase()); }
```

## @AfterMapping / @BeforeMapping Hooks

```java
@AfterMapping
default void postProcess(@MappingTarget OrderDto out, Order in) {
    out.setComputedField(in.amount().multiply(in.taxRate()));
}
```

**Warning:** Don't overuse. Three or more `@AfterMapping` hooks suggests a hand-written mapper would be clearer.

## Complete Example

```java
package com.example.app.mapper;

import com.example.app.dto.CreateOrderDto;
import com.example.app.dto.OrderDto;
import com.example.app.entity.Order;
import org.mapstruct.Mapper;
import org.mapstruct.Mapping;
import org.mapstruct.Named;

@Mapper
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
