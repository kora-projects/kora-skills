# Kora AOP

5 AOP modules: validation, logging, resilience, scheduling, cache. Compile-time annotations.

## When to Use

- Validation (@Validated)
- Logging (@LogExecution)
- Resilience (@Retry, @CircuitBreaker)
- Caching (@Cacheable)
- Scheduling (@Scheduled)

## Quick Start

```bash
/kora-aop --module validation --class UserService
```

## Key Features

- 5 modules: validation, logging, resilience, scheduling, cache
- Compile-time annotations
- non-final/open classes
- 12 scripts (6 Java + 6 Kotlin)
- Generic types: KeyType/ValueType

## Triggers

@Validated, @LogExecution, @Retry, @CircuitBreaker, @Cacheable, @Scheduled, AOP

## Resources

- **SKILL.md** — full documentation
- **scripts/** — 12 generators (Java + Kotlin)
- **assets/** — 12 templates
- **evals/** — 6 confirmed scenarios
