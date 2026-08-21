# MapStruct Expressions and Default Values Reference

**Source:** `.kora-agent/kora-docs/mkdocs/docs/en/documentation/mapstruct.md`

## Contents

- [expression — inline Java expression](#expression--inline-java-expression)
- [defaultValue — fallback for null source](#defaultvalue--fallback-for-null-source)
- [constant — fixed value](#constant--fixed-value)
- [nullValuePropertyMappingStrategy — PATCH semantics](#nullvaluepropertymappingstrategy--patch-semantics)
- [Combine with @Named for reusability](#combine-with-named-for-reusability)
- [Common expression patterns](#common-expression-patterns)
- [When NOT to use expressions](#when-not-to-use-expressions)

## expression — Inline Java Expression

Use for computed values at mapping time:

```java
@Mapping(target = "id", expression = "java(java.util.UUID.randomUUID())")
@Mapping(target = "createdAt", expression = "java(java.time.OffsetDateTime.now())")
@Mapping(target = "fullName", expression = "java(dto.getFirstName() + \" \" + dto.getLastName())")
Order toEntity(CreateOrderDto dto);
```

**Syntax:** `expression = "java(<expression>)"`

**Use cases:**
- Generate UUIDs
- Set timestamps (`OffsetDateTime.now()`, `Instant.now()`)
- Compute derived fields
- Call static utility methods

## defaultValue — Fallback for Null Source

Used when the source field is `null`:

```java
@Mapping(target = "status", defaultValue = "PENDING")
@Mapping(target = "priority", defaultValue = "0")
@Mapping(target = "notes", defaultValue = "No notes provided")
Order toEntity(CreateOrderDto dto);
```

**Important:** `defaultValue` applies only when source is `null`, not when a string is empty.

## constant — Fixed Value

Always uses the specified value regardless of source:

```java
@Mapping(target = "type", constant = "INTERNAL")
@Mapping(target = "version", constant = "1.0")
Order toEntity(CreateOrderDto dto);
```

**Difference from `defaultValue`:** `constant` ignores the source field entirely; `defaultValue` uses the source when present.

## nullValuePropertyMappingStrategy — PATCH Semantics

Combined with `@MappingTarget` for partial updates:

```java
@BeanMapping(nullValuePropertyMappingStrategy = NullValuePropertyMappingStrategy.IGNORE)
@Mapping(target = "id", ignore = true)
@Mapping(target = "createdAt", ignore = true)
void applyPatch(@MappingTarget Order existing, PatchOrderDto patch);
```

**Strategies:**

| Strategy | Behavior |
|----------|----------|
| `IGNORE` | Skip null source properties (PATCH semantics) |
| `SET_TO_NULL` | Set target to null when source is null |
| `SET_TO_DEFAULT` | Set target to Java default when source is null |

## combine with @Named for Reusability

For complex expressions used in multiple places:

```java
@Mapping(source = "amount", target = "amountWithTax", qualifiedByName = "addTax")
@Mapping(source = "discount", target = "finalAmount", qualifiedByName = "applyDiscount")
OrderDto toDto(Order order);

@Named("addTax")
default BigDecimal addTax(BigDecimal amount) {
    return amount.multiply(new BigDecimal("1.20"));  // 20% tax
}

@Named("applyDiscount")
default BigDecimal applyDiscount(BigDecimal amount) {
    return amount.multiply(new BigDecimal("0.90"));  // 10% discount
}
```

## Common Expression Patterns

### UUID Generation
```java
@Mapping(target = "id", expression = "java(java.util.UUID.randomUUID())")
```

### Timestamps
```java
@Mapping(target = "createdAt", expression = "java(java.time.OffsetDateTime.now())")
@Mapping(target = "updatedAt", expression = "java(java.time.Instant.now())")
```

### String Concatenation
```java
@Mapping(target = "fullName", expression = "java(dto.getFirstName() + \" \" + dto.getLastName())")
```

### Conditional Values
```java
@Mapping(target = "displayName", expression = "java(dto.getName() != null ? dto.getName() : \"Unknown\")")
```

### Static Method Calls
```java
@Mapping(target = "trimmed", expression = "java(com.example.StringUtils.trim(dto.getInput()))")
```

## When NOT to Use Expressions

Expressions become unreadable for complex logic. Prefer `@Named` methods or hand-written mappers when:

1. Expression exceeds one line
2. You need multiple statements
3. Logic involves validation or branching
4. You're calling external services

**Rule of thumb:** Three or more complex expressions → switch to `@AfterMapping` or hand-written mapper.
