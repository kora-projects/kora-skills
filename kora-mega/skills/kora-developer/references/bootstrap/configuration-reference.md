# Configuration Reference

This is a reference of all available configuration options. Do not configure all parameters — most have default values. Specify only the parameters you need to change.

## HOCON (application.conf)

```hocon
services {
    foo {
        bar = "SomeValue"                    # (1) String value
        baz = 10                             # (2) Numeric value
        propRequired = ${REQUIRED_ENV}       # (3) Required from environment
        propOptional = ${?OPTIONAL_ENV}      # (4) Optional from environment
        propDefault = 10                     # (5) Default value
        propDefault = ${?NON_DEFAULT_ENV}    # (5) Default with override from env
        propReference = ${services.foo.bar}Other${services.foo.baz}  # (6) Reference
        propArray = ["v1", "v2"]             # (7) Array of strings
        propArrayAsString = "v1, v2"         # (8) Comma-separated string
        propMap = {                          # (9) Map/Dictionary
            "k1" = "v1"
            "k2" = "v2"
        }
        propObject = {                       # (10) Object (mapped to interface)
            p1 = "v1"
            p2 = "v2"
        }
        propObjects = [                      # (11) List of objects
            { p1 = "v1", p2 = "v2" },
            { p1 = "v3", p2 = "v4" }
        ]
    }
}
```

## YAML (application.yaml)

```yaml
services:
    foo:
        bar: "SomeValue"                     # (1) String value
        baz: 10                              # (2) Numeric value
        propRequired: ${REQUIRED_ENV}        # (3) Required from environment
        propOptional: ${?OPTIONAL_ENV}       # (4) Optional from environment
        propDefault: ${?NON_DEFAULT_ENV:10}  # (5) Default with override from env
        propReference: ${services.foo.bar}Other${services.foo.baz}  # (6) Reference
        propArray: ["v1", "v2"]              # (7) Array of strings
        propArrayAsString: "v1, v2"          # (8) Comma-separated string
        propMap:                             # (9) Map/Dictionary
            k1: "v1"
            k2: "v2"
        propObject:                          # (10) Object (mapped to interface)
            p1: "v1"
            p2: "v2"
        propObjects:                         # (11) List of objects
            - p1: "v1"
              p2: "v2"
            - p1: "v3"
              p2: "v4"
```

## Configuration Options

| # | Option | Description |
|---|--------|-------------|
| 1 | String | String configuration value |
| 2 | Numeric | Numeric value (int, long, double) |
| 3 | `${ENV_VAR}` | Required variable — must be in environment |
| 4 | `${?ENV_VAR}` | Optional variable — null if not present |
| 5 | Default | Default value or with override from env |
| 6 | Reference | Reference to other config parts |
| 7 | Array | Array of values |
| 8 | Comma-separated | Comma-separated string (parsed as array) |
| 9 | Map | Dictionary key-value |
| 10 | Object | Object (mapped to @ConfigValueExtractor interface) |
| 11 | List of objects | Array of objects |

## Supported Types

| Type | Example |
|------|---------|
| Boolean | `true`, `false` |
| Integer | `42`, `100` |
| Long | `1000000`, `1000000L` |
| Double | `3.14`, `2.5` |
| String | `"hello"`, `hello` |
| Duration | `5s`, `2m`, `1h` |
| Size | `1Mb`, `1Mib`, `1024b`, `1024` |
| LocalDate | `2024-01-15` |
| LocalDateTime | `2024-01-15T10:30:00` |
| UUID | `550e8400-e29b-41d4-a716-446655440000` |
| List<T> | `["a", "b", "c"]` |
| Set<T> | `["a", "b", "c"]` |
| Map<K,V> | `{ key = "value" }` |

## Environment Variables

| Syntax | Meaning |
|--------|---------|
| `${ENV_VAR}` | Required variable |
| `${?ENV_VAR}` | Optional variable |
| `${?ENV_VAR:-default}` | Optional with default value |

## File Priority

Configuration is loaded in this order:
1. `config.resource` (from resources)
2. `config.file` (from filesystem)
3. `application.conf` / `application.yaml` (from resources)
4. Empty configuration

**Best Practice:**
- `application.conf` / `application.yaml` — application configuration
- `reference.conf` / `reference.yaml` — library defaults
