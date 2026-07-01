# Kora MapStruct

Integrate the MapStruct mapping library with Kora: `@Mapper`-annotated interfaces
are auto-discovered and the generated `*MapperImpl` is registered as a component
in the DI graph. Use for DTO to entity mapping.

## When to Use

- DTO to entity (or entity to DTO) mapping in a Java Kora service
- Field renames, ignores, inline expressions, enum/string conversion
- PATCH-style in-place updates via `@MappingTarget`

## Entry point

Read `SKILL.md` for the Quick Start and core patterns, then the files under
`references/` for depth.

## Resources

- `SKILL.md` — Quick Start, decision table, core patterns, pitfalls
- `references/` — mapper reference, configuration (Java/Kotlin), expressions
- `assets/` — `@Mapper` template and Gradle dependency snippets
