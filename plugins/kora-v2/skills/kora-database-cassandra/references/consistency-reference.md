# Consistency Levels Reference

**Module:** `ru.tinkoff.kora:database-cassandra`  
**Driver:** DataStax Java Driver 4.x

## Contents

- [Overview](#overview)
- [Consistency Level Options](#consistency-level-options)
- [Profile-Based Configuration](#profile-based-configuration)
- [Serial Consistency (LWT)](#serial-consistency-lwt)
- [Recommended Configurations by Use Case](#recommended-configurations-by-use-case)
- [Consistency Tuning](#consistency-tuning)
- [Troubleshooting](#troubleshooting)

> **Config keys.** All request tuning lives under `cassandra.basic.request`:
> `consistency`, `serialConsistency`, `timeout`, `pageSize`, `defaultIdempotence`.
> A profile under `cassandra.profiles.<name>` overrides any `basic.request.*`
> (and `advanced.*`) key. There are no `readConsistency`, `writeConsistency`,
> `requestTimeout`, or `retryPolicy` keys.

---

## Overview

Consistency levels determine how many replicas must acknowledge a read/write operation for it to be considered successful.

**Trade-offs:**
- **Higher consistency** → More durability, higher latency
- **Lower consistency** → Lower latency, potential stale reads

---

## Consistency Level Options

| Level | Description | Latency | Durability | Use Case |
|-------|-------------|---------|------------|----------|
| `ANY` | At least one node (hints allowed) | Lowest | Lowest | Hints only |
| `ONE` | At least one node | Low | Low | Cache, session |
| `TWO` | At least two nodes | Medium | Medium | Balanced |
| `THREE` | At least three nodes | Medium | Medium | Balanced |
| `QUORUM` | Majority of nodes | High | High | General purpose |
| `ALL` | All nodes | Highest | Highest | Critical data |
| `LOCAL_ONE` | One node in local DC | Low | Low | Multi-DC reads |
| `LOCAL_QUORUM` | Majority in local DC | High | High | Multi-DC writes |
| `EACH_QUORUM` | Quorum in each DC | Highest | Highest | Global consistency |
| `SERIAL` | Paxos consensus (LWT) | Variable | Highest | Lightweight transactions |
| `LOCAL_SERIAL` | Paxos in local DC only | Variable | High | LWT local only |

---

## Profile-Based Configuration

### Default Request Settings

```hocon
cassandra {
    basic {
        request {
            consistency = "QUORUM"        # default consistency for all queries
            serialConsistency = "SERIAL"  # consistency for lightweight transactions
            timeout = "5s"
        }
    }
}
```

### Multiple Profiles

A profile only needs to declare the keys it overrides; everything else is
inherited from `basic`.

```hocon
cassandra {
    basic {
        request {
            consistency = "QUORUM"
            serialConsistency = "SERIAL"
            timeout = "5s"
        }
    }

    profiles {
        # Fast, low durability (cache, session data)
        fast {
            basic.request.consistency = "ONE"
            basic.request.serialConsistency = "LOCAL_SERIAL"
            basic.request.timeout = "2s"
        }

        # Analytics with relaxed consistency and larger pages
        analytics {
            basic.request.consistency = "ONE"
            basic.request.timeout = "30s"
            basic.request.pageSize = 1000
        }

        # Critical data with high durability
        critical {
            basic.request.consistency = "QUORUM"
            basic.request.serialConsistency = "SERIAL"
            basic.request.timeout = "5s"
        }

        # Local DC only (multi-DC deployments)
        local {
            basic.request.consistency = "LOCAL_QUORUM"
            basic.request.serialConsistency = "LOCAL_SERIAL"
            basic.request.timeout = "5s"
        }
    }
}
```

### Using Profiles

`@CassandraProfile` is `@Target(METHOD)` — apply it to each `@Query` method, not
to the repository interface.

```java
@Repository
public interface EventRepository extends CassandraRepository {

    @CassandraProfile("analytics")
    @Query("SELECT * FROM events WHERE type = :type ALLOW FILTERING")
    List<Event> findByType(String type);

    @CassandraProfile("critical")
    @Query("SELECT * FROM accounts WHERE id = :id")
    @Nullable
    Account findById(String id);
}
```

---

## Serial Consistency (LWT)

Serial consistency is used for Lightweight Transactions (LWT) with `IF NOT EXISTS` or `IF` clauses:

```java
@Repository
public interface UserRepository extends CassandraRepository {
    
    // The [applied] flag is the first column of an LWT result
    @Query("INSERT INTO users (id, name) VALUES (:user.id, :user.name) IF NOT EXISTS")
    boolean insertIfNotExists(User user);

    @Query("UPDATE users SET email = :email WHERE id = :id IF email = :oldEmail")
    boolean updateIfEmailMatches(UUID id, String email, String oldEmail);
}
```

**Serial consistency options:**
- `SERIAL` — Full Paxos consensus across all DCs
- `LOCAL_SERIAL` — Paxos within local DC only (faster, less consistent)

---

## Recommended Configurations by Use Case

### General Purpose (Balanced, default)

```hocon
cassandra {
    basic {
        request {
            consistency = "QUORUM"
            serialConsistency = "SERIAL"
            timeout = "5s"
        }
    }
}
```

### Session / Analytics / Critical Profiles

```hocon
cassandra {
    profiles {
        session {
            basic.request.consistency = "ONE"
            basic.request.timeout = "2s"
        }
        analytics {
            basic.request.consistency = "ONE"
            basic.request.timeout = "30s"
            basic.request.pageSize = 1000
        }
        critical {
            basic.request.consistency = "QUORUM"
            basic.request.serialConsistency = "SERIAL"
            basic.request.timeout = "5s"
        }
    }
}
```

### Multi-DC Deployment

The local datacenter is set with `basic.dc`; the driver routes to it first.

```hocon
cassandra {
    basic {
        dc = "datacenter1"
        request {
            consistency = "LOCAL_QUORUM"
            serialConsistency = "LOCAL_SERIAL"
        }
        loadBalancingPolicy.slowReplicaAvoidance = true
    }
    profiles {
        global {
            basic.request.consistency = "EACH_QUORUM"
            basic.request.timeout = "10s"
        }
    }
}
```

---

## Consistency Tuning

For **N** replicas:

| Read CL | Write CL | Guarantees |
|---------|----------|------------|
| ONE | ONE | No strong consistency |
| ONE | QUORUM | Read-your-writes |
| QUORUM | ONE | Read-your-writes |
| QUORUM | QUORUM | Strong consistency |
| ALL | ALL | Strongest consistency |

**Rule:** `readCL + writeCL > N` ensures strong consistency.

---

## Troubleshooting

### Consistency Errors

```
com.datastax.oss.driver.api.core.servererrors.UnavailableException:
    Not enough replica available

com.datastax.oss.driver.api.core.servererrors.ReadTimeoutException:
    Operation timed out - received X responses, but quorum is Y
```

**Solutions:**
1. Reduce consistency level
2. Add more nodes to cluster
3. Check node health

---

## See Also

- [Cassandra Config Reference](cassandra-config-reference.md) — Timeouts, load balancing, multiple keyspaces
- [CQL Repository Reference](cql-repository-reference.md) — Query patterns
