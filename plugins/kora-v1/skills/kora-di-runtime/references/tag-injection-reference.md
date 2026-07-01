# Kora @Tag Disambiguation Reference

**Source:** [Kora Container Documentation](../../../.kora-agent/kora-docs/mkdocs/docs/en/documentation/container.md)

Complete reference for using `@Tag` to disambiguate same-type components in Kora applications.

---

## Table of Contents

1. [@Tag Annotation](#tag-annotation)
2. [Tag Classes](#tag-classes)
3. [Tagged Injection](#tagged-injection)
4. [Common Patterns](#common-patterns)
5. [Troubleshooting](#troubleshooting)

---

## @Tag Annotation

When multiple implementations of the same interface exist, use `@Tag` to specify which one to inject.

```java
// Tag classes (simple marker classes)
public final class RedisTag {}
public final class CaffeineTag {}

// Tagged implementations
@Tag(RedisTag.class)
@Component
public final class RedisCache implements Cache {
    // Redis implementation
}

@Tag(CaffeineTag.class)
@Component
public final class CaffeineCache implements Cache {
    // In-memory implementation
}

// Tagged injection
@Component
public final class UserService {
    private final Cache redisCache;
    private final Cache localCache;

    public UserService(
        @Tag(RedisTag.class) Cache redisCache,
        @Tag(CaffeineTag.class) Cache localCache
    ) {
        this.redisCache = redisCache;
        this.localCache = localCache;
    }
}
```

---

## Tag Classes

### Use Simple Marker Classes

**Recommended approach:**

```java
// GOOD: Simple tag class
public final class RedisTag {}
public final class PostgresTag {}
public final class PrimaryTag {}
```

**Avoid custom annotations:**

```java
// BAD: Unnecessary boilerplate
@Target({ElementType.TYPE, ElementType.PARAMETER})
@Retention(RetentionPolicy.RUNTIME)
@Tag(RedisTag.class)
public @interface RedisCache {}
```

### Why Simple Classes Are Better

| Aspect | Simple Class | Custom Annotation |
|--------|--------------|-------------------|
| Boilerplate | Minimal | Heavy (meta-annotations) |
| Annotation processing | Not needed | Required |
| Readability | Clear intent | Indirect |
| IDE navigation | Direct | Through meta-annotation |

### Tag Class Naming Conventions

```java
// By technology
public final class RedisTag {}
public final class PostgresTag {}
public final class KafkaTag {}
public final class ElasticsearchTag {}

// By role
public final class PrimaryTag {}
public final class SecondaryTag {}
public final class ReadOnlyTag {}
public final class WriteTag {}

// By environment
public final class ProdTag {}
public final class DevTag {}
public final class TestTag {}

// By strategy
public final class SyncTag {}
public final class AsyncTag {}
public final class BatchTag {}
public final class StreamingTag {}
```

---

## Tagged Injection

### On Constructor Parameters

```java
@Component
public final class PaymentService {
    private final PaymentGateway primaryGateway;
    private final PaymentGateway backupGateway;

    public PaymentService(
        @Tag(PrimaryTag.class) PaymentGateway primaryGateway,
        @Tag(SecondaryTag.class) PaymentGateway backupGateway
    ) {
        this.primaryGateway = primaryGateway;
        this.backupGateway = backupGateway;
    }
}
```

### On Class (Component-Level Tag)

```java
@Tag(PrimaryTag.class)
@Component
public final class PrimaryDatabase implements Database {
    public void query(String sql) { /* Primary DB */ }
}

@Tag(SecondaryTag.class)
@Component
public final class SecondaryDatabase implements Database {
    public void query(String sql) { /* Secondary DB */ }
}

// Injection point
@Component
public final class UserService {
    private final Database database;

    // Gets PrimaryDatabase
    public UserService(@Tag(PrimaryTag.class) Database database) {
        this.database = database;
    }
}
```

### On Factory Methods

```java
@Module
public interface CacheModule {

    @Tag(RedisTag.class)
    @DefaultComponent
    default Cache redisCache(Config config) {
        return new RedisCache(config.getConfig("redis"));
    }

    @Tag(CaffeineTag.class)
    default Cache caffeineCache() {
        return new CaffeineCache();
    }
}
```

---

## Common Patterns

### Pattern 1: Primary/Secondary Databases

```java
// Tag classes
public final class PrimaryTag {}
public final class SecondaryTag {}

// Primary database
@Tag(PrimaryTag.class)
@Component
public final class PrimaryDatabase implements Database {
    public void query(String sql) { /* Primary DB */ }
}

// Secondary database
@Tag(SecondaryTag.class)
@Component
public final class SecondaryDatabase implements Database {
    public void query(String sql) { /* Secondary DB */ }
}

// Service with primary/secondary
@Component
public final class UserService {
    private final Database primaryDb;
    private final Database secondaryDb;

    public UserService(
        @Tag(PrimaryTag.class) Database primaryDb,
        @Tag(SecondaryTag.class) Database secondaryDb
    ) {
        this.primaryDb = primaryDb;
        this.secondaryDb = secondaryDb;
    }

    public User get(String id) {
        // Read from secondary (read replica)
        return secondaryDb.query("SELECT * FROM users WHERE id = ?", id);
    }

    public void save(User user) {
        // Write to primary
        primaryDb.execute("INSERT INTO users VALUES (?, ?)", user.id(), user.name());
    }
}
```

### Pattern 2: Multi-Environment Configuration

```java
// Environment tags
public final class ProdTag {}
public final class DevTag {}
public final class TestTag {}

// Production email service
@Tag(ProdTag.class)
@Component
public final class ProdEmailService implements EmailService {
    private final SmtpClient smtp;

    public ProdEmailService(SmtpClient smtp) {
        this.smtp = smtp;
    }

    public void send(String to, String subject, String body) {
        smtp.send(to, subject, body);  // Real email
    }
}

// Dev email service (logs instead)
@Tag(DevTag.class)
@Component
public final class DevEmailService implements EmailService {
    public void send(String to, String subject, String body) {
        System.out.println("[DEV EMAIL] To: " + to);
        System.out.println("Subject: " + subject);
        System.out.println("Body: " + body);
    }
}

// Test email service (no-op)
@Tag(TestTag.class)
@Component
public final class TestEmailService implements EmailService {
    public void send(String to, String subject, String body) {
        // No-op in tests
    }
}
```

### Pattern 3: Multiple Message Brokers

```java
// Broker tags
public final class KafkaTag {}
public final class RabbitTag {}
public final class SqsTag {}

// Kafka producer
@Tag(KafkaTag.class)
@Component
public final class KafkaProducer implements MessageProducer {
    public void send(String topic, String message) {
        // Send to Kafka
    }
}

// RabbitMQ producer
@Tag(RabbitTag.class)
@Component
public final class RabbitProducer implements MessageProducer {
    public void send(String queue, String message) {
        // Send to RabbitMQ
    }
}

// SQS producer
@Tag(SqsTag.class)
@Component
public final class SqsProducer implements MessageProducer {
    public void send(String queueUrl, String message) {
        // Send to SQS
    }
}

// Message router
@Component
public final class MessageRouter {
    private final Map<String, MessageProducer> producers;

    public MessageRouter(
        @Tag(KafkaTag.class) MessageProducer kafka,
        @Tag(RabbitTag.class) MessageProducer rabbit,
        @Tag(SqsTag.class) MessageProducer sqs
    ) {
        this.producers = Map.of(
            "kafka", kafka,
            "rabbit", rabbit,
            "sqs", sqs
        );
    }

    public void send(String broker, String destination, String message) {
        producers.get(broker).send(destination, message);
    }
}
```

### Pattern 4: Cache Hierarchy

```java
// Cache level tags
public final class L1Tag {}  // Local cache
public final class L2Tag {}  // Distributed cache

// L1: Local Caffeine cache
@Tag(L1Tag.class)
@Component
public final class L1Cache implements Cache {
    private final Cache<String, Object> caffeine;

    public L1Cache() {
        this.caffeine = Caffeine.newBuilder()
            .maximumSize(1000)
            .expireAfterWrite(Duration.ofMinutes(5))
            .build();
    }

    public void put(String key, Object value) {
        caffeine.put(key, value);
    }

    public Object get(String key) {
        return caffeine.getIfPresent(key);
    }
}

// L2: Redis distributed cache
@Tag(L2Tag.class)
@Component
public final class L2Cache implements Cache {
    private final RedisClient redis;

    public L2Cache(RedisClient redis) {
        this.redis = redis;
    }

    public void put(String key, Object value) {
        redis.set(key, value);
    }

    public Object get(String key) {
        return redis.get(key);
    }
}

// Cache coordinator
@Component
public final class CacheCoordinator {
    private final Cache l1Cache;
    private final Cache l2Cache;

    public CacheCoordinator(
        @Tag(L1Tag.class) Cache l1Cache,
        @Tag(L2Tag.class) Cache l2Cache
    ) {
        this.l1Cache = l1Cache;
        this.l2Cache = l2Cache;
    }

    public Object get(String key) {
        // Try L1 first
        var value = l1Cache.get(key);
        if (value != null) {
            return value;
        }

        // Fall back to L2
        value = l2Cache.get(key);
        if (value != null) {
            l1Cache.put(key, value);  // Populate L1
        }
        return value;
    }

    public void put(String key, Object value) {
        l1Cache.put(key, value);
        l2Cache.put(key, value);
    }
}
```

### Pattern 5: Strategy Selection

```java
// Compression strategy tags
public final class GzipTag {}
public final class ZipTag {}
public final class Lz4Tag {}

// GZIP compressor
@Tag(GzipTag.class)
@Component
public final class GzipCompressor implements Compressor {
    public byte[] compress(byte[] data) { /* GZIP */ }
    public byte[] decompress(byte[] data) { /* GZIP */ }
}

// ZIP compressor
@Tag(ZipTag.class)
@Component
public final class ZipCompressor implements Compressor {
    public byte[] compress(byte[] data) { /* ZIP */ }
    public byte[] decompress(byte[] data) { /* ZIP */ }
}

// LZ4 compressor
@Tag(Lz4Tag.class)
@Component
public final class Lz4Compressor implements Compressor {
    public byte[] compress(byte[] data) { /* LZ4 */ }
    public byte[] decompress(byte[] data) { /* LZ4 */ }
}

// Compressor selector
@Component
public final class CompressionService {
    private final Map<String, Compressor> compressors;

    public CompressionService(
        @Tag(GzipTag.class) Compressor gzip,
        @Tag(ZipTag.class) Compressor zip,
        @Tag(Lz4Tag.class) Compressor lz4
    ) {
        this.compressors = Map.of(
            "gzip", gzip,
            "zip", zip,
            "lz4", lz4
        );
    }

    public byte[] compress(byte[] data, String algorithm) {
        return compressors.get(algorithm).compress(data);
    }
}
```

---

## Troubleshooting

### Ambiguous Dependency Error

**Error:** `Found multiple components of type Cache`

**Solution:** Add `@Tag` to disambiguate:

```java
// WRONG: Ambiguous
public UserService(Cache cache) {}

// CORRECT: Tagged
public UserService(@Tag(RedisTag.class) Cache cache) {}
```

### Wrong Implementation Injected

**Problem:** Getting CaffeineCache instead of RedisCache

**Check:**
1. Is the correct `@Tag` used on injection point?
2. Are both implementations tagged correctly?
3. Is the tag class the same (not a different class with same name)?

### Tag on Only One Implementation

**Problem:** Tagged injection fails

**Check:** ALL implementations of the same type should be tagged, or use `@DefaultComponent` for untagged:

```java
// WRONG: Only one tagged
@Tag(RedisTag.class)
@Component
public final class RedisCache implements Cache {}

@Component
public final class CaffeineCache implements Cache {}  // Untagged

// CORRECT: Both tagged
@Tag(RedisTag.class)
@Component
public final class RedisCache implements Cache {}

@Tag(CaffeineTag.class)
@Component
public final class CaffeineCache implements Cache {}
```

### Missing Tag Class Import

**Problem:** Compilation error — class not found

**Check:** Tag class is in correct package and imported:

```java
import com.example.config.tags.RedisTag;  // Full path
```

---

## See Also

- [SKILL.md](../SKILL.md) — Runtime DI overview
- [Collection Injection Reference](collection-injection-reference.md) — All<T>, Tag.Any patterns
- [Container Documentation](../../../.kora-agent/kora-docs/mkdocs/docs/en/documentation/container.md) — Official docs
