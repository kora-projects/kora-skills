# Migrations Reference (Flyway/Liquibase)

**Source:** `.kora-agent/kora-docs/mkdocs/docs/en/documentation/database-migration.md`
**Module:** `ru.tinkoff.kora:database-jdbc`

Kora does not include built-in schema migration — use Flyway or Liquibase as standalone dependencies. Kora also provides dedicated migration modules (`flyway`, `liquibase`); for those, see the `kora-database-migration-flyway` / `kora-database-migration-liquibase` skills.

## Contents

- [Flyway integration](#flyway-integration)
- [Liquibase integration](#liquibase-integration)
- [Flyway vs Liquibase](#flyway-vs-liquibase)
- [Best practices](#best-practices)

---

## Flyway Integration

### Dependency

```groovy
dependencies {
    implementation "org.flywaydb:flyway-core:10.10.0"
    implementation "org.flywaydb:flyway-database-postgresql:10.10.0"  // PostgreSQL-specific
}
```

### Configuration

```hocon
db {
    jdbcUrl = ${POSTGRES_JDBC_URL}
    username = ${POSTGRES_USER}
    password = ${POSTGRES_PASS}
}

flyway {
    url = ${db.jdbcUrl}
    user = ${db.username}
    password = ${db.password}
    locations = ["classpath:db/migration"]
    defaultSchema = "public"
    validateOnMigrate = true
    cleanDisabled = false
}
```

### Migration Files

Location: `src/main/resources/db/migration/`

**Naming convention:** `V{version}__{description}.sql`

```
db/migration/
├── V1__init_schema.sql
├── V1.1__add_users_table.sql
├── V1.2__add_orders_table.sql
└── V2__add_indexes.sql
```

### Example Migration

```sql
-- V1__init_schema.sql
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

CREATE TABLE users (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    email VARCHAR(255) NOT NULL UNIQUE,
    name VARCHAR(255) NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE orders (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id BIGINT NOT NULL REFERENCES users(id),
    total_amount DECIMAL(10, 2) NOT NULL,
    status VARCHAR(50) NOT NULL DEFAULT 'PENDING',
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_orders_user_id ON orders(user_id);
CREATE INDEX idx_orders_status ON orders(status);
```

### Programmatic Execution

```java
@Component
public class DatabaseMigrator {
    private final DataSource dataSource;
    
    public DatabaseMigrator(DataSource dataSource) {
        this.dataSource = dataSource;
    }
    
    public void migrate() {
        Flyway flyway = Flyway.configure()
            .dataSource(dataSource)
            .locations("classpath:db/migration")
            .load();
        flyway.migrate();
    }
}
```

### Gradle Task

```groovy
plugins {
    id "org.flywaydb.flyway" version "10.10.0"
}

flyway {
    url = System.getenv("POSTGRES_JDBC_URL")
    user = System.getenv("POSTGRES_USER")
    password = System.getenv("POSTGRES_PASS")
    locations = ["filesystem:src/main/resources/db/migration"]
}
```

```bash
./gradlew flywayMigrate
./gradlew flywayValidate
./gradlew flywayClean
```

---

## Liquibase Integration

### Dependency

```groovy
dependencies {
    implementation "org.liquibase:liquibase-core:4.27.0"
}
```

### Configuration

```hocon
db {
    jdbcUrl = ${POSTGRES_JDBC_URL}
    username = ${POSTGRES_USER}
    password = ${POSTGRES_PASS}
}

liquibase {
    url = ${db.jdbcUrl}
    username = ${db.username}
    password = ${db.password}
    changeLogFile = "db/changelog/db.changelog-master.yaml"
}
```

### Changelog File (YAML)

Location: `src/main/resources/db/changelog/db.changelog-master.yaml`

```yaml
databaseChangeLog:
  - includeAll:
      path: db/changelog/changes/
  
  - changeSet:
      id: 1
      author: app
      changes:
        - createTable:
            tableName: users
            columns:
              - column:
                  name: id
                  type: BIGINT
                  autoIncrement: true
                  constraints:
                    primaryKey: true
              - column:
                  name: email
                  type: VARCHAR(255)
                  constraints:
                    nullable: false
                    unique: true
              - column:
                  name: name
                  type: VARCHAR(255)
                  constraints:
                    nullable: false
              - column:
                  name: created_at
                  type: TIMESTAMP
                  defaultValueComputed: NOW()
                  constraints:
                    nullable: false

  - changeSet:
      id: 2
      author: app
      changes:
        - createTable:
            tableName: orders
            columns:
              - column:
                  name: id
                  type: UUID
                  defaultValueComputed: uuid_generate_v4()
                  constraints:
                    primaryKey: true
              - column:
                  name: user_id
                  type: BIGINT
                  constraints:
                    nullable: false
                    foreignKeyName: fk_orders_user
                    references: users(id)
              - column:
                  name: total_amount
                  type: DECIMAL(10,2)
                  constraints:
                    nullable: false
              - column:
                  name: status
                  type: VARCHAR(50)
                  defaultValue: PENDING
                  constraints:
                    nullable: false
```

### Programmatic Execution

```java
@Component
public class DatabaseMigrator {
    private final DataSource dataSource;
    
    public DatabaseMigrator(DataSource dataSource) {
        this.dataSource = dataSource;
    }
    
    public void migrate() throws LiquibaseException {
        Liquibase liquibase = new Liquibase(
            "db/changelog/db.changelog-master.yaml",
            new ClassLoaderResourceAccessor(),
            new JdbcConnection((java.sql.Connection) dataSource.getConnection())
        );
        liquibase.migrate();
    }
}
```

### Gradle Task

```groovy
plugins {
    id "org.liquibase.gradle" version "2.2.1"
}

liquibase {
    activities {
        main {
            driver "org.postgresql.Driver"
            url System.getenv("POSTGRES_JDBC_URL")
            username System.getenv("POSTGRES_USER")
            password System.getenv("POSTGRES_PASS")
            changeLogFile "src/main/resources/db/changelog/db.changelog-master.yaml"
        }
    }
}
```

```bash
./gradlew liquibase
./gradlew liquibaseStatus
./gradlew liquibaseRollback
```

---

## Flyway vs Liquibase

| Feature | Flyway | Liquibase |
|---------|--------|-----------|
| **Format** | SQL (native), Java | XML, YAML, JSON, SQL |
| **Complexity** | Simple, straightforward | More features, steeper learning curve |
| **Rollback** | Manual (undo scripts) | Automatic (for most changes) |
| **Contexts** | Limited | Full support |
| **Best for** | SQL-first teams, simple migrations | Complex schemas, multi-DB support |

---

## Best Practices

1. **Version control migrations** — Store all migration files in git
2. **Immutable migrations** — Never modify applied migrations
3. **Test migrations** — Run on staging before production
4. **Backup before migrate** — Especially for destructive operations
5. **Use transactions** — Wrap related changes in single migration
6. **Document changes** — Clear commit messages and changelog descriptions

---

## See Also

- [Connection Pool Reference](connection-pool-reference.md) — HikariCP configuration
- [Entity Mapping Reference](entity-mapping-reference.md) — Table/column mapping
