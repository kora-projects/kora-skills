# Cassandra Configuration Reference (database-cassandra)

**Source:** [.kora-agent/kora-docs/mkdocs/docs/en/documentation/database-cassandra.md](.kora-agent/kora-docs/mkdocs/docs/en/documentation/database-cassandra.md)  
**Examples:** `.kora-agent/kora-examples/kora-java-database-cassandra/`

**Module:** `ru.tinkoff.kora:database-cassandra`  
**Driver:** DataStax Java Driver 4.x (included transitively)

---

## Configuration Structure

### application.conf (HOCON)

```hocon
cassandra {
    # Authentication (optional, use for secured clusters)
    auth {
        login = ${CASSANDRA_USER}
        password = ${CASSANDRA_PASS}
    }
    
    # Basic connection settings
    basic {
        contactPoints = ${CASSANDRA_CONTACT_POINTS}  # ["host1:9042", "host2:9042"]
        dc = ${CASSANDRA_DC}  # "datacenter1"
        sessionKeyspace = ${CASSANDRA_KEYSPACE}  # "mykeyspace"
        
        # Request timeout
        request {
            timeout = 5s
        }
        
        # Connection settings
        connection {
            connectTimeout = 5s
            initQueryTimeout = 5s
        }
        
        # Load balancing
        loadBalancing {
            policy = "DC_AWARE"  # DC_AWARE, ROUND_ROBIN, TOKEN_AWARE
            localDatacenter = ${CASSANDRA_DC}
        }
        
        # Retry policy
        retryPolicy = "DEFAULT"  # DEFAULT, FALLBACK, DOWNGRADE_CONSISTENCY, SKIP_READ_REPAIR, IGNORE
    }
    
    # Health check (optional)
    healthCheck {
        enabled = true
        timeout = 3s
    }
    
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
cassandra:
  auth:
    login: ${CASSANDRA_USER}
    password: ${CASSANDRA_PASS}
  basic:
    contactPoints: ${CASSANDRA_CONTACT_POINTS}
    dc: ${CASSANDRA_DC}
    sessionKeyspace: ${CASSANDRA_KEYSPACE}
    request:
      timeout: 5s
    connection:
      connectTimeout: 5s
      initQueryTimeout: 5s
    loadBalancing:
      policy: "DC_AWARE"
      localDatacenter: ${CASSANDRA_DC}
    retryPolicy: "DEFAULT"
  healthCheck:
    enabled: true
    timeout: 3s
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
        # Single node
        contactPoints = ["localhost:9042"]
        
        # Multiple nodes (recommended for production)
        contactPoints = ["node1:9042", "node2:9042", "node3:9042"]
    }
}
```

### Datacenter

```hocon
cassandra {
    basic {
        dc = "datacenter1"
        loadBalancing {
            policy = "DC_AWARE"
            localDatacenter = "datacenter1"
        }
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

| Setting | Default | Description |
|---------|---------|-------------|
| `request.timeout` | 5s | Default timeout for all requests |
| `connection.connectTimeout` | 5s | Time to establish connection |
| `connection.initQueryTimeout` | 5s | Timeout for initialization queries |
| `controlConnection.timeout` | 5s | Control connection timeout |
| `metadata.schemaRequestTimeout` | 10s | Schema metadata request timeout |

### Recommended Timeouts by Workload

**Low Latency (real-time queries):**
```hocon
cassandra {
    basic {
        request {
            timeout = 2s
        }
        connection {
            connectTimeout = 3s
        }
    }
}
```

**Standard (general purpose):**
```hocon
cassandra {
    basic {
        request {
            timeout = 5s
        }
        connection {
            connectTimeout = 5s
        }
    }
}
```

**Bulk Operations (batch imports, analytics):**
```hocon
cassandra {
    basic {
        request {
            timeout = 30s
        }
        connection {
            connectTimeout = 10s
        }
    }
}
```

---

## Consistency Levels

### Profile-Based Configuration

```hocon
cassandra {
    profiles {
        # Fast, low durability (cache, session data)
        fast {
            consistency = "ONE"
            serialConsistency = "ANY"
            requestTimeout = 2s
        }
        
        # Balanced (general purpose)
        balanced {
            consistency = "QUORUM"
            serialConsistency = "SERIAL"
            requestTimeout = 5s
        }
        
        # High durability (financial data)
        durable {
            consistency = "ALL"
            serialConsistency = "SERIAL"
            requestTimeout = 10s
            retryPolicy = "DEFAULT"
        }
        
        # Local DC only
        local {
            consistency = "LOCAL_QUORUM"
            serialConsistency = "LOCAL_SERIAL"
            requestTimeout = 5s
        }
    }
}
```

### Consistency Level Options

| Level | Description | Latency | Durability |
|-------|-------------|---------|------------|
| `ANY` | At least one node (hints allowed) | Lowest | Lowest |
| `ONE` | At least one node | Low | Low |
| `TWO` | At least two nodes | Medium | Medium |
| `THREE` | At least three nodes | Medium | Medium |
| `QUORUM` | Majority of nodes | High | High |
| `ALL` | All nodes | Highest | Highest |
| `LOCAL_ONE` | One node in local DC | Low | Low |
| `LOCAL_QUORUM` | Majority in local DC | High | High |
| `EACH_QUORUM` | Quorum in each DC | Highest | Highest |
| `SERIAL` | Paxos consensus (LWT) | Variable | Highest |
| `LOCAL_SERIAL` | Paxos in local DC only | Variable | High |

---

## Retry Policies

| Policy | Description | Use Case |
|--------|-------------|----------|
| `DEFAULT` | Default retry logic | General purpose |
| `FALLBACK` | Retry on next node | High availability |
| `DOWNGRADE_CONSISTENCY` | Reduce consistency on failure | Degraded operation |
| `SKIP_READ_REPAIR` | Skip read repair on timeout | Performance |
| `IGNORE` | No automatic retry | Manual handling |

```hocon
cassandra {
    basic {
        retryPolicy = "DEFAULT"
    }
    
    profiles {
        critical {
            retryPolicy = "DEFAULT"
        }
        
        analytics {
            retryPolicy = "SKIP_READ_REPAIR"
        }
    }
}
```

---

## Load Balancing Policies

| Policy | Description | Use Case |
|--------|-------------|----------|
| `DC_AWARE` | Route to local DC first | Multi-DC clusters |
| `ROUND_ROBIN` | Round-robin across nodes | Single DC, even distribution |
| `TOKEN_AWARE` | Route based on token | Partition-aware routing |

```hocon
cassandra {
    basic {
        loadBalancing {
            policy = "DC_AWARE"
            localDatacenter = "datacenter1"
        }
    }
}
```

---

## Multiple Keyspaces

### Configuration

```hocon
cassandra {
    basic {
        sessionKeyspace = "primary_keyspace"
    }
    
    # Additional keyspaces for @Repository(keyspace = "...")
    additionalKeyspaces = ["secondary_keyspace", "analytics_keyspace"]
}
```

### Repository with Keyspace

```java
@Repository(keyspace = "analytics_keyspace")
public interface AnalyticsRepository extends CassandraRepository {
    
    @Query("SELECT * FROM events WHERE type = :type")
    List<Event> findByType(String type);
}
```

---

## Profile-Based Configuration

### Profile Annotation

```java
@Repository
@CassandraProfile("analytics")
public interface AnalyticsRepository extends CassandraRepository {
    
    @Query("SELECT * FROM events WHERE type = :type")
    List<Event> findByType(String type);
    
    @Query("SELECT * FROM events WHERE created_at > :ts")
    List<Event> findByTimestamp(LocalDateTime ts);
}
```

### Profile Configuration

```hocon
cassandra {
    basic {
        # Default profile settings
        request {
            timeout = 5s
        }
        consistency = "QUORUM"
    }
    
    profiles {
        analytics {
            consistency = "ONE"
            serialConsistency = "ANY"
            requestTimeout = 30s
            pageSize = 1000
        }
        
        critical {
            consistency = "QUORUM"
            serialConsistency = "SERIAL"
            requestTimeout = 5s
            retryPolicy = "DEFAULT"
        }
    }
}
```

---

## Telemetry Configuration

### Logging

```hocon
cassandra {
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
cassandra {
    telemetry {
        metrics {
            enabled = true
            prefix = "kora.cassandra"
        }
    }
}
```

### Tracing (OpenTelemetry)

```hocon
cassandra {
    telemetry {
        tracing {
            enabled = true
            includeQuery = true  # Include CQL query in span
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
  cassandra:
    image: cassandra:5.0
    environment:
      CASSANDRA_DC: datacenter1
      CASSANDRA_RACK: rack1
    ports:
      - "9042:9042"
  
  app:
    image: my-app:latest
    environment:
      CASSANDRA_CONTACT_POINTS: "cassandra:9042"
      CASSANDRA_DC: datacenter1
      CASSANDRA_KEYSPACE: mykeyspace
      CASSANDRA_USER: cassandra
      CASSANDRA_PASS: cassandra
    depends_on:
      - cassandra
```

### Kubernetes Secret

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: cassandra-credentials
type: Opaque
stringData:
  contact-points: "cassandra-1.cassandra.default.svc:9042,cassandra-2.cassandra.default.svc:9042"
  dc: "datacenter1"
  keyspace: "mykeyspace"
  user: "cassandra"
  password: "cassandra"
```

```yaml
env:
  - name: CASSANDRA_CONTACT_POINTS
    valueFrom:
      secretKeyRef:
        name: cassandra-credentials
        key: contact-points
  - name: CASSANDRA_DC
    valueFrom:
      secretKeyRef:
        name: cassandra-credentials
        key: dc
  - name: CASSANDRA_KEYSPACE
    valueFrom:
      secretKeyRef:
        name: cassandra-credentials
        key: keyspace
  - name: CASSANDRA_USER
    valueFrom:
      secretKeyRef:
        name: cassandra-credentials
        key: user
  - name: CASSANDRA_PASS
    valueFrom:
      secretKeyRef:
        name: cassandra-credentials
        key: password
```

---

## Health Check

```hocon
cassandra {
    healthCheck {
        enabled = true
        timeout = 3s
        query = "SELECT now() FROM system.local"  # Custom health query
    }
}
```

---

## Common Issues

### 1. Connection Refused
```
com.datastax.oss.driver.api.core.connection.ConnectTimeoutException: Connect timeout
```
**Solution:** Check contact points, network connectivity, and Cassandra is running.

### 2. Keyspace Does Not Exist
```
com.datastax.oss.driver.api.core.servererrors.InvalidQueryException: Keyspace 'mykeyspace' does not exist
```
**Solution:** Create keyspace before application startup or set `sessionKeyspace` correctly.

### 3. Read Timeout
```
com.datastax.oss.driver.api.core.servererrors.ReadTimeoutException: Operation timed out
```
**Solution:** Increase `request.timeout`, check node health, or reduce consistency level.

### 4. Unavailable Exception
```
com.datastax.oss.driver.api.core.servererrors.UnavailableException: Not enough replica available
```
**Solution:** Reduce consistency level or add more nodes to the cluster.

---

## See Also

- [Database Common Reference](database-common-reference.md) — Entity mapping, SQL macros, custom mappers
- [Database Cassandra Reference](database-cassandra-reference.md) — UDTs, async signatures, lightweight transactions
- [DataStax Driver Documentation](https://docs.datastax.com/en/developer/java-driver/) — Official driver docs
