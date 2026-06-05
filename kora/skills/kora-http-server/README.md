# Kora HTTP Server

REST API with @HttpController and @HttpRoute annotations. Synchronous controllers, CompletionStage for interceptors.

## When to use

- Creating REST API endpoints
- OpenAPI documentation (ru.tinkoff.kora:openapi-management)
- Global exception handlers
- Health checks and readiness probes

## Quick Start

```bash
/kora-http-server --controller UserController --route /users
```

## Key features

- @HttpController, @HttpRoute annotations
- Synchronous controllers
- CompletionStage for interceptors
- Automatic OpenAPI documentation
- Exception handlers

## Triggers

@HttpController, @HttpRoute, HttpServer, OpenAPI, Swagger UI, exception handler

## Resources

- **SKILL.md** — full documentation
- **references/** — 9 reference docs
- **assets/** — 16 controller templates (Java + Kotlin)
