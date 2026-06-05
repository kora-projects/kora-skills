# Kora JSON

JSON serialization with @Json annotations, sealed interfaces, enums, custom mappers.

## When to use

- DTO serialization/deserialization
- Sealed interfaces in JSON
- Enum serialization (snake_case, kebab-case)
- Custom JSON mappers

## Quick start

```bash
/kora-json --dto UserDto --fields name,email,role
```

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
- **references/** — 5 reference docs (best practices, sealed interfaces)
- **assets/** — 12 templates (DTO, enum, sealed interface, custom mapper)
