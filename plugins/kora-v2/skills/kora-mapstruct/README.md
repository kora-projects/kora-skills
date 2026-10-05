# Kora MapStruct / Konvert

DTO ↔ entity mapping in Kora 2.0. The module language picks the tool, with no crossover:

- **Java → MapStruct.** `org.mapstruct.@Mapper` + `annotationProcessor "org.mapstruct:mapstruct-processor"`;
  `mapstruct-java-extension` binds the generated `*MapperImpl`.
- **Kotlin → Konvert.** `io.mcarle.konvert.api.@Konverter` + `ksp("io.mcarle:konvert")`;
  `konvert-ksp-extension` binds the generated `object <Name>Impl`. Never MapStruct or `kapt` in Kotlin.

Kora generates no mappers — the extension binds the implementation the mapping library produced, so
the mapper interface becomes an injectable component with no `@Component` and no module to plug
into `@KoraApp`. The extensions ship inside `io.koraframework:annotation-processors` /
`io.koraframework:symbol-processors` and are never declared directly.
`ru.tinkoff.kora:mapstruct-extension` does not exist in 2.0.

## When to Use

- Mapping between request/response DTOs, domain entities and persistence rows
- Field renames, ignores, computed values, enum ↔ String conversion
- PATCH-style in-place updates via `@MappingTarget` (Java/MapStruct)
- A user asks for MapStruct in Kotlin — steer to Konvert
- Deciding between a mapping library and a hand-written mapper

## Entry point

Read `SKILL.md` for the language rule and both quick starts, then the files under `references/`.

## Resources

- `SKILL.md` — the rule, mechanism, Java (MapStruct) and Kotlin (Konvert) quick starts, Konvert limits, pitfalls
- `references/` — Java: mapper discovery and annotations, build configuration, MapStruct expressions; Kotlin: Konvert
- `assets/` — Java `@Mapper` and Kotlin `@Konverter` template twins, Gradle snippets for both
- `evals/` — regression cases: language rule, removed coordinate, kapt question, Konvert limits, version pinning
