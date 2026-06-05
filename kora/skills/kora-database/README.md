# Kora Database

JDBC and Cassandra integration in Kora applications. Virtual Threads preferred over reactive approaches.

## When to use

- Creating repositories with @Query methods
- Configuring HikariCP connection pooling
- Cassandra integration
- Database migrations (Flyway/Liquibase)

## Quick start

```bash
/kora-database --entity User --table users --id uuid
```

## Key features

- JDBC + HikariCP (PostgreSQL, MySQL, Oracle)
- Cassandra integration
- Synchronous signatures (not CompletionStage/Mono/Flux)
- @Transaction support
- Migrations: Flyway, Liquibase

## Triggers

JdbcRepository, @Query, @Transaction, CassandraRepository, HikariConfig, Flyway, Liquibase

## Resources

- **SKILL.md** — full documentation
- **references/** — 8 reference docs
- **assets/** — 5 entity/CRUD templates
