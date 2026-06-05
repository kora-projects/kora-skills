# Kora OpenAPI

OpenAPI codegen (clients/servers), management (Swagger UI, Rapidoc), discriminators (oneOf+allOf).

## When to Use

- Generating HTTP clients from OpenAPI
- Generating servers (controllers + models)
- Publishing specifications (Swagger UI)
- oneOf/allOf with discriminators

## Quick Start

```bash
/kora-openapi --generate server --spec api.yaml
```

## Key Features

- Codegen: HTTP clients/servers
- Management: Swagger UI, Rapidoc
- Discriminators: oneOf+allOf
- Synchronous contracts
- Unique outputDir per module

## Triggers

OpenAPI, codegen, Swagger UI, Rapidoc, discriminator, oneOf, allOf, .client, .server

## Resources

- **SKILL.md** — full documentation
- **references/** — 6 reference docs (validation, interceptors, Kotlin)
- **assets/** — 7 templates (.client/.server suffixes)
