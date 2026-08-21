# Cassandra Configuration Reference

**Module:** `ru.tinkoff.kora:database-cassandra`  
**Driver:** DataStax Java Driver 4.x  
**Config interface:** `CassandraConfig`

## Contents

- [Configuration Structure](#configuration-structure)
- [Connection Settings](#connection-settings)
- [Timeout Configuration](#timeout-configuration)
- [Load Balancing](#load-balancing)
- [Telemetry Configuration](#telemetry-configuration)
- [Environment Variables](#environment-variables)
- [Docker Compose](#docker-compose)
- [Common Issues](#common-issues)

> **Config shape.** Top-level sections are `cassandra.auth`, `cassandra.basic`,
> `cassandra.advanced`, `cassandra.profiles`, and `cassandra.telemetry`.
> Request tuning is under `basic.request`; driver internals (connection pool,
> reconnection, SSL, Netty, metadata) are under `advanced`. There is no
> `healthCheck`, `additionalKeyspaces`, or `retryPolicy` key, and `@Repository`
> has no `keyspace` attribute. See the full key list in
> `.kora-agent/kora-docs/mkdocs/docs/en/documentation/database-cassandra.md`.

---

## Configuration Structure

### application.conf (HOCON)

```hocon
cassandra {
    # Authentication (optional)
    auth {
        login = ${CASSANDRA_USER}
        password = ${CASSANDRA_PASS}
    }

    # Basic connection settings
    basic {
        contactPoints = ${CASSANDRA_CONTACT_POINTS}  # required
        dc = ${CASSANDRA_DC}                          # local datacenter
        sessionKeyspace = ${CASSANDRA_KEYSPACE}

        request {
            timeout = "5s"
            consistency = "LOCAL_ONE"
            pageSize = 5000
        }

        loadBalancingPolicy.slowReplicaAvoidance = true
    }

    # Driver internals (optional)
    advanced {
        connection {
            connectTimeout = "10s"
            initQueryTimeout = "10s"
            pool {
                localSize = 10
                remoteSize = 10
            }
        }
        reconnectionPolicy {
            baseDelay = "1s"
            maxDelay = "60s"
        }
    }

    # Telemetry
    telemetry {
        logging.enabled = true
        metrics.enabled = true
        tracing.enabled = true
    }
}
```

### application.yaml

```yaml
cassandra:
  auth:
    login: ${CASSANDRA_USER}
    password: ${CASSANDRA_PASS}
  basic:
    contactPoints: ${CASSANDRA_CONTACT_POINTS}
    dc: ${CASSANDRA_DC}
    sessionKeyspace: ${CASSANDRA_KEYSPACE}
    request:
      timeout: "5s"
      consistency: "LOCAL_ONE"
      pageSize: 5000
    loadBalancingPolicy:
      slowReplicaAvoidance: true
  advanced:
    connection:
      connectTimeout: "10s"
      initQueryTimeout: "10s"
      pool:
        localSize: 10
        remoteSize: 10
    reconnectionPolicy:
      baseDelay: "1s"
      maxDelay: "60s"
  telemetry:
    logging:
      enabled: true
    metrics:
      enabled: true
    tracing:
      enabled: true
```

---

## Connection Settings

### Contact Points

```hocon
cassandra {
    basic {
        # Single node (development)
        contactPoints = ["localhost:9042"]
        
        # Multiple nodes (production)
        contactPoints = ["node1:9042", "node2:9042", "node3:9042"]
    }
}
```

### Datacenter

The local datacenter is `basic.dc`; the driver's load-balancing policy routes to
it first. Slow-replica avoidance is toggled separately.

```hocon
cassandra {
    basic {
        dc = "datacenter1"
        loadBalancingPolicy.slowReplicaAvoidance = true
    }
}
```

### Keyspace

```hocon
cassandra {
    basic {
        sessionKeyspace = "mykeyspace"
    }
}
```

---

## Timeout Configuration

| Setting | Section | Description |
|---------|---------|-------------|
| `basic.request.timeout` | basic | Per-query timeout |
| `advanced.connection.connectTimeout` | advanced | Time to establish a connection |
| `advanced.connection.initQueryTimeout` | advanced | Timeout for init queries |
| `advanced.connection.setKeyspaceTimeout` | advanced | Keyspace-set timeout |
| `advanced.controlConnection.timeout` | advanced | Control connection timeout |
| `advanced.metadata.schema.requestTimeout` | advanced | Schema metadata request timeout |

### Recommended Timeouts

**Low latency (real-time):**
```hocon
cassandra {
    basic.request.timeout = "2s"
    advanced.connection.connectTimeout = "3s"
}
```

**Bulk operations:**
```hocon
cassandra {
    basic.request.timeout = "30s"
    advanced.connection.connectTimeout = "10s"
}
```

---

## Load Balancing

Kora exposes the slow-replica avoidance flag on the driver's default DC-aware,
token-aware policy. The local DC is `basic.dc`.

```hocon
cassandra {
    basic {
        dc = "datacenter1"
        loadBalancingPolicy.slowReplicaAvoidance = true
    }
}
```

For deeper control of the `CqlSession` builder, register a `CassandraConfigurer`
component (see [Code configuration](#code-configuration)).

---

## Code configuration { #code-configuration }

Implement `CassandraConfigurer` as a `@Component` to customize the
`CqlSessionBuilder` directly:

```java
@Component
public final class MyCassandraConfigurer implements CassandraConfigurer {

    @Override
    public CqlSessionBuilder configure(CqlSessionBuilder builder) {
        return builder.withClientId(UUID.randomUUID());
    }
}
```

---

## Telemetry Configuration

Only these telemetry keys exist (`DatabaseTelemetryConfig`):

```hocon
cassandra {
    telemetry {
        logging.enabled = true
        metrics {
            enabled = true
            slo = [1, 10, 50, 100, 200, 500, 1000, 2000, 5000, 10000, 20000, 30000, 60000, 90000]
            tags = { key1 = "value1" }
        }
        tracing {
            enabled = true
            attributes = { key1 = "value1" }
        }
    }
}
```

---

## Environment Variables

```bash
export CASSANDRA_CONTACT_POINTS=127.0.0.1:9042
export CASSANDRA_USER=cassandra
export CASSANDRA_PASS=cassandra
export CASSANDRA_DC=datacenter1
export CASSANDRA_KEYSPACE=mykeyspace
```

---

## Docker Compose

```yaml
services:
  cassandra:
    image: cassandra:5.0
    environment:
      - CASSANDRA_DC=datacenter1
    ports:
      - "9042:9042"
  
  app:
    image: my-app:latest
    environment:
      - CASSANDRA_CONTACT_POINTS=cassandra:9042
      - CASSANDRA_DC=datacenter1
      - CASSANDRA_KEYSPACE=mykeyspace
      - CASSANDRA_USER=cassandra
      - CASSANDRA_PASS=cassandra
    depends_on:
      - cassandra
```

---

## Common Issues

### Connection Refused

```
com.datastax.oss.driver.api.core.connection.ConnectTimeoutException
```

**Solution:** Check contact points, network connectivity, Cassandra is running.

### Keyspace Does Not Exist

```
com.datastax.oss.driver.api.core.servererrors.InvalidQueryException:
    Keyspace 'mykeyspace' does not exist
```

**Solution:** Create keyspace before application startup.

### Read Timeout

```
com.datastax.oss.driver.api.core.servererrors.ReadTimeoutException
```

**Solution:** Increase `request.timeout`, check node health, reduce consistency level.

### Unavailable Exception

```
com.datastax.oss.driver.api.core.servererrors.UnavailableException:
    Not enough replica available
```

**Solution:** Reduce consistency level, add more nodes.

---

## See Also

- [Consistency Reference](consistency-reference.md) — Consistency levels, profiles
- [CQL Repository Reference](cql-repository-reference.md) — Query patterns
