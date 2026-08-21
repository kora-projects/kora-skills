# Kora JSON

JSON serialization with @Json annotations, sealed interfaces, enums, custom mappers.

## When to use

- DTO serialization/deserialization
- Sealed interfaces in JSON
- Enum serialization (snake_case, kebab-case)
- Custom JSON mappers

## Quick start

See [SKILL.md](SKILL.md) for the Gradle dependencies, module wiring, and a runnable
controller. In short: add `annotation-processors` + `json-module`, extend `JsonModule`
on the `@KoraApp` interface, and annotate DTO records/data classes with `@Json`.

## Key features

- @Json, @JsonField, @JsonReader, @JsonWriter
- Sealed interfaces support
- Enum serialization formats
- @Nullable, @JsonInclude, @JsonSkip
- Custom mappers

## Triggers

@Json, @JsonField, sealed interface JSON, enum serialization, custom mapper

## Resources

- **SKILL.md** — full documentation
- **references/** — DTOs, sealed types, custom mappers, configuration, best practices
- **assets/** — Java and Kotlin templates: DTO, enum, sealed interface (+ impl), custom mapper
