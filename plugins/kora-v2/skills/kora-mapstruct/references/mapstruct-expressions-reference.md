# MapStruct Expressions and Default Values Reference

**Scope: Java only.** Everything here is MapStruct's own annotation language, unchanged by Kora —
see <https://mapstruct.org/documentation/stable/reference/html/>. Kora contributes nothing to it and
constrains nothing in it; it only binds the generated implementation
(see [`mapstruct-mapper-reference.md`](mapstruct-mapper-reference.md)).

In a Kotlin Kora 2.0 module there is no MapStruct — mapping goes through Konvert
([`konvert-reference.md`](konvert-reference.md)), whose per-field options are documented at
<https://mcarleio.github.io/konvert/>. `expression = "java(…)"` in
particular embeds **Java** source into the generated implementation and has no Kotlin analogue.

## Contents

- [expression — inline Java expression](#expression--inline-java-expression)
- [defaultValue — fallback for a null source](#defaultvalue--fallback-for-a-null-source)
- [constant — fixed value](#constant--fixed-value)
- [nullValuePropertyMappingStrategy — PATCH semantics](#nullvaluepropertymappingstrategy--patch-semantics)
- [Combine with @Named for reusability](#combine-with-named-for-reusability)
- [Common expression patterns](#common-expression-patterns)
- [When not to use expressions](#when-not-to-use-expressions)

## expression — Inline Java Expression

Computed values at mapping time:

```java
@Mapping(target = "id", expression = "java(java.util.UUID.randomUUID())")
@Mapping(target = "createdAt", expression = "java(java.time.OffsetDateTime.now())")
@Mapping(target = "fullName", expression = "java(dto.getFirstName() + \" \" + dto.getLastName())")
Order toEntity(CreateOrderDto dto);
```

**Syntax:** `expression = "java(<expression>)"`. The text is spliced verbatim into the generated
`*MapperImpl`, so a typo surfaces as a compile error in generated code, not as a MapStruct message.
Fully-qualify types, or add `imports` to `@Mapper`.

Typical uses: generate UUIDs, stamp `OffsetDateTime.now()` / `Instant.now()`, derive a field, call a
static utility.

## defaultValue — Fallback for a Null Source

```java
@Mapping(target = "status", defaultValue = "PENDING")
@Mapping(target = "priority", defaultValue = "0")
Order toEntity(CreateOrderDto dto);
```

Applies only when the source is `null` — not when a String is empty.

## constant — Fixed Value

```java
@Mapping(target = "type", constant = "INTERNAL")
@Mapping(target = "version", constant = "1.0")
Order toEntity(CreateOrderDto dto);
```

`constant` ignores the source entirely; `defaultValue` uses the source when it is present.

## nullValuePropertyMappingStrategy — PATCH Semantics

Pairs with `@MappingTarget` for partial updates:

```java
@BeanMapping(nullValuePropertyMappingStrategy = NullValuePropertyMappingStrategy.IGNORE)
@Mapping(target = "id", ignore = true)
@Mapping(target = "createdAt", ignore = true)
void applyPatch(@MappingTarget Order existing, PatchOrderDto patch);
```

| Strategy | Behaviour |
|----------|-----------|
| `IGNORE` | Skip null source properties — PATCH semantics |
| `SET_TO_NULL` | Write null into the target |
| `SET_TO_DEFAULT` | Write the Java default into the target |

The target must be mutable. A Java record cannot be patched in place — map to a new instance.

To tell "field absent" apart from "explicitly null" in the request body, use `JsonNullable<T>` from
[`kora-json`](../../kora-json/SKILL.md); `IGNORE` alone cannot distinguish the two.

## Combine with @Named for Reusability

```java
@Mapping(source = "amount", target = "amountWithTax", qualifiedByName = "addTax")
@Mapping(source = "discount", target = "finalAmount", qualifiedByName = "applyDiscount")
OrderDto toDto(Order order);

@Named("addTax")
default BigDecimal addTax(BigDecimal amount) {
    return amount.multiply(new BigDecimal("1.20"));
}

@Named("applyDiscount")
default BigDecimal applyDiscount(BigDecimal amount) {
    return amount.multiply(new BigDecimal("0.90"));
}
```

A `@Named` helper is real Java in a real file: it is refactorable, testable and debuggable. An
`expression` string is none of those.

## Common Expression Patterns

```java
// identifier
@Mapping(target = "id", expression = "java(java.util.UUID.randomUUID())")

// timestamps
@Mapping(target = "createdAt", expression = "java(java.time.OffsetDateTime.now())")

// concatenation
@Mapping(target = "fullName", expression = "java(dto.getFirstName() + \" \" + dto.getLastName())")

// conditional
@Mapping(target = "displayName", expression = "java(dto.getName() != null ? dto.getName() : \"Unknown\")")

// static utility
@Mapping(target = "trimmed", expression = "java(com.example.StringUtils.trim(dto.getInput()))")
```

Values that come from the graph — a clock, a config value, an ID generator — do **not** belong in an
`expression`. Take them as a constructor dependency of the mapper instead
(see [Mappers that need dependencies](mapstruct-mapper-reference.md#mappers-that-need-dependencies)),
or compute them in the caller.

## When Not to Use Expressions

Switch to a `@Named` method, `@AfterMapping`, or a hand-written mapper when:

1. the expression exceeds one line,
2. you need more than one statement,
3. the logic validates or branches,
4. it would call a service or touch I/O.

**Rule of thumb:** three or more non-trivial expressions in one mapper means the mapper should be
hand-written.
