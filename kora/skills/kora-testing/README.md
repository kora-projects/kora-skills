# Kora Testing

Testing: @KoraAppTest, @TestComponent, Mockito/MockK, testcontainers-extensions (14 extensions).

## When to use

- Component tests with @KoraAppTest
- Mockito/MockK mocks
- Integration tests with Testcontainers
- Blackbox tests (Docker)

## Quick start

```bash
/kora-testing --type component --name UserServiceTest
```

## Key features

- @KoraAppTest, @TestComponent
- Mockito (Java) / MockK (Kotlin)
- testcontainers-extensions v0.13.1 (14 extensions)
- AppContainer: APP_IMAGE, 2 ports (8080/8085), /system/readiness
- Migrations in tests

## Triggers

@KoraAppTest, @TestComponent, Mockito, MockK, Testcontainers, integration test, blackbox

## Resources

- **SKILL.md** — full documentation
- **references/** — 5 reference docs (Docker, HTTP server, MockServer)
- **5 confirmed evals:** component, mockito, integration, blackbox, test-application
