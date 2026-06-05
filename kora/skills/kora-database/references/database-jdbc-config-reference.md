# JDBC Configuration Reference (database-jdbc)

**Source:** [.kora-agent/kora-docs/mkdocs/docs/en/documentation/database-jdbc.md](.kora-agent/kora-docs/mkdocs/docs/en/documentation/database-jdbc.md)  
**Examples:** `.kora-agent/kora-examples/kora-java-database-jdbc/`

**Module:** `ru.tinkoff.kora:database-jdbc`
**Connection Pool:** HikariCP (included in database-jdbc)

---

## Configuration Structure

### application.conf (HOCON)

```hocon
db {
    # Required: JDBC URL (use environment variables)
    jdbcUrl = ${POSTGRES_JDBC_URL}  # "jdbc:postgresql://localhost:5432/mydb"
    
    # Required: Credentials (use environment variables)
    username = ${POSTGRES_USER}
    password = ${POSTGRES_PASS}
    
    # HikariCP pool settings
    maxPoolSize = 10
    minIdle = 2
    connectionTimeout = 30000      # 30 seconds
    idleTimeout = 600000           # 10 minutes
    maxLifetime = 1800000          # 30 minutes
    validationTimeout = 5000       # 5 seconds
    leakDetectionThreshold = 0     # 0 = disabled
    
    # Pool name (optional, for logging)
    poolName = "kora"
    
    # Telemetry (optional)
    telemetry {
        logging {
            enabled = true
        }
        metrics {
            enabled = true
        }
        tracing {
            enabled = true
        }
    }
}
```

### application.yaml

```yaml
db:
  jdbcUrl: ${POSTGRES_JDBC_URL}
  username: ${POSTGRES_USER}
  password: ${POSTGRES_PASS}
  maxPoolSize: 10
  minIdle: 2
  connectionTimeout: 30000
  idleTimeout: 600000
  maxLifetime: 1800000
  validationTimeout: 5000
  poolName: "kora"
  telemetry:
    logging:
      enabled: true
    metrics:
      enabled: true
```

---

## HikariCP Pool Settings

| Setting | Default | Description |
|---------|---------|-------------|
| `maximumPoolSize` | 10 | Maximum number of connections in the pool |
| `minimumIdle` | 2 | Minimum idle connections to maintain |
| `connectionTimeout` | 30000 | Max time to wait for connection (ms) |
| `idleTimeout` | 600000 | Max time connection can sit idle (ms) |
| `maxLifetime` | 1800000 | Max lifetime of connection (ms) |
| `validationTimeout` | 5000 | Time to wait for connection validation (ms) |
| `leakDetectionThreshold` | 0 | Time before logging leak warning (ms, 0 = disabled) |

### Recommended Settings by Workload

**Low Traffic (development, internal tools):**
```hocon
db {
    maxPoolSize = 5
    minIdle = 1
    connectionTimeout = 30000
    idleTimeout = 300000
    maxLifetime = 1200000
}
```

**Medium Traffic (production microservices):**
```hocon
db {
    maxPoolSize = 20
    minIdle = 5
    connectionTimeout = 30000
    idleTimeout = 600000
    maxLifetime = 1800000
}
```

**High Traffic (high-throughput services):**
```hocon
db {
    maxPoolSize = 50
    minIdle = 10
    connectionTimeout = 30000
    idleTimeout = 900000
    maxLifetime = 1800000
}
```

---

## Database Drivers

### PostgreSQL
```groovy
dependencies {
    implementation "org.postgresql:postgresql:42.7.3"
}
```
```hocon
db {
    jdbcUrl = ${POSTGRES_JDBC_URL}  # "jdbc:postgresql://host:5432/dbname"
    username = ${POSTGRES_USER}
    password = ${POSTGRES_PASS}
}
```

### MySQL
```groovy
dependencies {
    implementation "com.mysql:mysql-connector-j:8.3.0"
}
```
```hocon
db {
    jdbcUrl = ${MYSQL_JDBC_URL}  # "jdbc:mysql://host:3306/dbname"
    username = ${MYSQL_USER}
    password = ${MYSQL_PASS}
}
```

### Oracle
```groovy
dependencies {
    implementation "com.oracle.database.jdbc:ojdbc11:21.9.0.0"
}
```
```hocon
db {
    jdbcUrl = ${ORACLE_JDBC_URL}  # "jdbc:oracle:thin:@host:1521:SID"
    username = ${ORACLE_USER}
    password = ${ORACLE_PASS}
}
```

### H2 (In-Memory, Testing)
```groovy
dependencies {
    implementation "com.h2database:h2:2.2.224"
}
```
```hocon
db {
    jdbcUrl = "jdbc:h2:mem:testdb;DB_CLOSE_DELAY=-1"
    username = "sa"
    password = ""
}
```

---

## Multiple Databases

### Configuration

```hocon
db {
    # Primary database
    jdbcUrl = ${PRIMARY_JDBC_URL}
    username = ${PRIMARY_USER}
    password = ${PRIMARY_PASS}
}

# Secondary database with @Tag
secondary {
    jdbcUrl = ${SECONDARY_JDBC_URL}
    username = ${SECONDARY_USER}
    password = ${SECONDARY_PASS}
}
```

### Tag Definition

```java
@Tag
public @interface SecondaryDatabase {}
```

### Secondary Database Configuration

```java
@Module
public interface SecondaryDatabaseModule {
    
    @SecondaryDatabase
    @Component
    static HikariConfig secondaryJdbcConfig(Config config) {
        return new HikariConfig(config.get("database.secondary.jdbc"));
    }
    
    @SecondaryDatabase
    @Component
    static HikariDataSource secondaryDataSource(HikariConfig config) {
        return new HikariDataSource(config);
    }
    
    @SecondaryDatabase
    @Component
    static JdbcDatabase secondaryDatabase(
        JdbcDatabaseSchemaManager schemaManager,
        HikariDataSource dataSource,
        JdbcTelemetry telemetry
    ) {
        return schemaManager.newDatabase(dataSource, telemetry);
    }
}
```

### Repository with Tag

```java
@Repository(executorTag = @Tag(SecondaryDatabase.class))
public interface SecondaryRepository extends JdbcRepository {
    
    @Query("SELECT * FROM secondary_table WHERE id = :id")
    SecondaryEntity findById(Long id);
}
```

---

## Telemetry Configuration

### Logging

```hocon
db {
    telemetry {
        logging {
            enabled = true
            level = "DEBUG"  # TRACE, DEBUG, INFO, WARN, ERROR
        }
    }
}
```

### Metrics (Micrometer)

```hocon
db {
    telemetry {
        metrics {
            enabled = true
            prefix = "kora.database"
        }
    }
}
```

### Tracing (OpenTelemetry)

```hocon
db {
    telemetry {
        tracing {
            enabled = true
            includeQuery = true  # Include SQL query in span
        }
    }
}
```

---

## Environment Variables

### Docker Compose Example

```yaml
version: '3.8'
services:
  postgres:
    image: postgres:16
    environment:
      POSTGRES_DB: mydb
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: secret
    ports:
      - "5432:5432"
  
  app:
    image: my-app:latest
    environment:
      POSTGRES_JDBC_URL: "jdbc:postgresql://postgres:5432/mydb"
      POSTGRES_USER: postgres
      POSTGRES_PASS: secret
    depends_on:
      - postgres
```

### Kubernetes Secret

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: database-credentials
type: Opaque
stringData:
  jdbc-url: "jdbc:postgresql://db-host:5432/mydb"
  username: "db-user"
  password: "db-password"
```

```yaml
env:
  - name: POSTGRES_JDBC_URL
    valueFrom:
      secretKeyRef:
        name: database-credentials
        key: jdbc-url
  - name: POSTGRES_USER
    valueFrom:
      secretKeyRef:
        name: database-credentials
        key: username
  - name: POSTGRES_PASS
    valueFrom:
      secretKeyRef:
        name: database-credentials
        key: password
```

---

## Common Issues

### 1. Connection Timeout
```
com.zaxxer.hikari.pool.HikariPool$PoolEntryCreator: Connection timeout after 30000ms
```
**Solution:** Increase `connectionTimeout` or check database availability.

### 2. Pool Exhaustion
```
com.zaxxer.hikari.pool.HikariPool: Connection is not available, request timed out after 30000ms
```
**Solution:** Increase `maximumPoolSize` or investigate long-running queries.

### 3. Leak Detection
```
com.zaxxer.hikari.pool.LeakTask: Possible connection leak detected
```
**Solution:** Set `leakDetectionThreshold` to identify unclosed connections.

### 4. Driver Not Found
```
java.lang.ClassNotFoundException: org.postgresql.Driver
```
**Solution:** Add PostgreSQL driver to dependencies.

---

## See Also

- [Database Common Reference](database-common-reference.md) — Entity mapping, SQL macros, custom mappers
- [Database JDBC Reference](database-jdbc-reference.md) — Transaction management, batch operations, custom mappers
- [HikariCP Documentation](https://github.com/brettwooldridge/HikariCP) — Official HikariCP documentation
