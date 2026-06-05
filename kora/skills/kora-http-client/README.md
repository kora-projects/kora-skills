# Kora HTTP Client

HTTP clients: declarative (synchronous), imperative (CompletionStage), interceptors.

## When to Use

- Integration with external APIs
- Client generation from OpenAPI (kora-openapi)
- Retry, timeout, circuit breaker
- Custom interceptors

## Quick Start

```bash
/kora-http-client --name UserService --base-url https://api.example.com
```

## Key Features

- Declarative clients (synchronous)
- Imperative (CompletionStage)
- Interceptors (Retry, Timeout, Circuit Breaker)
- OpenAPI codegen (preferred)
- JSON serialization

## Triggers

HttpClient, @HttpRoute, declarative client, interceptor, retry, timeout, OpenAPI client

## Resources

- **SKILL.md** — full documentation
- **references/** — 16 assets (Java + Kotlin)
- **Recommendation:** when an OpenAPI spec is available, use kora-openapi
