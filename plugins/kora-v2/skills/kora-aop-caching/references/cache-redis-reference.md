# Redis cache reference

**Artifact:** `io.koraframework:cache-redis-lettuce`
**Module:** `io.koraframework.cache.redis.lettuce.LettuceRedisCacheModule`
**Contract:** `io.koraframework.cache.redis.RedisCache<K, V> extends Cache<K, V>`
**Config type:** `io.koraframework.cache.redis.RedisCacheConfig`
**Driver:** Lettuce (`io.koraframework:redis-lettuce`, config path `lettuce`)

---

## Contents

- [Which module, which artifact](#which-module-which-artifact)
- [Setup](#setup)
- [The lettuce driver section](#the-lettuce-driver-section)
- [Per-cache configuration](#per-cache-configuration)
- [keyPrefix](#keyprefix)
- [Value serialisation](#value-serialisation)
- [Key serialisation](#key-serialisation)
- [The RedisCache contract](#the-rediscache-contract)
- [Errors are swallowed](#errors-are-swallowed)
- [Customising the Lettuce client](#customising-the-lettuce-client)
- [Telemetry](#telemetry)
- [Testing](#testing)
- [Troubleshooting](#troubleshooting)

---

## Which module, which artifact

Kora 2.0 splits the Redis cache in two:

| Artifact | Module | Provides |
|---|---|---|
| `io.koraframework:cache-redis-common` | `RedisCacheModule` | telemetry factory, `RedisCacheMapperModule` (key/value mappers), the `AbstractRedisCache` base. **No `RedisCacheClient`.** |
| `io.koraframework:cache-redis-lettuce` | **`LettuceRedisCacheModule`** | everything above (it extends `RedisCacheModule` and `LettuceModule`) **plus** the `RedisCacheClient` built on Lettuce |

Connect **`LettuceRedisCacheModule`**. `RedisCacheModule` is transport-neutral and compiles fine on
its own, but the generated `$Cache_Module` needs a `RedisCacheClient`, so the graph fails with:

```
No component found for dependency:
  io.koraframework.cache.redis.RedisCacheClient (no tags)
```

The Kora 1.x artifact `cache-redis` **does not exist in 2.0** — it is not in the `2.0.0.RC2` BOM.
A `cache-redis` directory still shows in the Maven Central listing; that is a 1.x leftover.

---

## Setup

```groovy
dependencies {
    koraBom platform("io.koraframework:kora-bom:$koraVersion")
    annotationProcessor "io.koraframework:annotation-processors"

    implementation "io.koraframework:cache-redis-lettuce"
    implementation "io.koraframework:config-hocon"
    implementation "io.koraframework:json-common"      // only if values are @Json DTOs
}
```

```java
@KoraApp
public interface Application extends
        HoconConfigModule,
        LogbackModule,
        JsonModule,                 // only if values are @Json DTOs
        LettuceRedisCacheModule {

    static void main(String[] args) {
        KoraApplication.run(ApplicationGraph::graph);
    }
}
```

```java
@Cache("orders.cache")
public interface OrderCache extends RedisCache<UUID, @Json OrderDto> {}
```

```kotlin
@Cache("orders.cache")
interface OrderCache : RedisCache<UUID, @Json OrderDto>
```

---

## The lettuce driver section

One Lettuce client is shared by every `RedisCache`. `LettuceModule` wires
`new LettuceFactoryModule("lettuce")`, so the section is called `lettuce`:

```hocon
lettuce {
  uri                = ${REDIS_URL}     # REQUIRED
  user               = ${?REDIS_USER}
  password           = ${?REDIS_PASS}
  database           = 0
  protocol           = "RESP3"          # RESP2 (Redis 2–5) or RESP3 (Redis 6+), default RESP3
  forceClusterClient = false            # default false
  socketTimeout      = 15s              # default 10s
  commandTimeout     = 15s              # default 30s

  ssl {
    ciphers          = ["TLS_CHACHA20_POLY1305_SHA256"]   # default []
    handshakeTimeout = 10s                                # default 10s
  }

  telemetry {
    logging.enabled = false
    metrics.enabled = false
  }
}
```

`uri` has no default; leaving it out fails graph init with
`Config expected value, but got null at path: 'ROOT.lettuce.uri' for origin '…'`.

A comma-separated URI (`redis://host1:6379,host2:6379`) or `forceClusterClient = true` selects the
cluster client; a single URI selects the standalone client. `rediss://` enables TLS.

---

## Per-cache configuration

```hocon
orders.cache {
  keyPrefix         = "orders"   # REQUIRED
  expireAfterWrite  = "1h"       # optional
  expireAfterAccess = "30m"      # optional
  enabled           = true       # default true

  telemetry {
    logging.enabled = false      # default false
    metrics.enabled = false      # default false
    tracing.enabled = true       # default true
  }
}
```

| Key | Type | Default | Notes |
|---|---|---|---|
| `keyPrefix` | String | **none — required** | see below |
| `expireAfterWrite` | Duration | *unset* | writes use `PSETEX` instead of `SET` |
| `expireAfterAccess` | Duration | *unset* | reads use `GETEX` instead of `GET`, sliding the TTL |
| `enabled` | boolean | `true` | `false` makes every operation a no-op / miss |
| `telemetry.*` | | see table | logging and metrics off, tracing on |

There is no `maximumSize` — sizing is Redis' business, not the client's.

---

## keyPrefix

`RedisCacheConfig.keyPrefix()` has **no default and is not `@Nullable`**. Omit it and the
application dies during graph init:

```
io.koraframework.config.common.exception.ConfigValueException:
  Config expected value, but got null at path: 'ROOT.orders.cache.keyPrefix' for origin '…'
```

This is a **startup** failure, not a compile error — the generated module resolves the config with
`mapper.mapOrThrow(config.get("orders.cache"))` when the graph is built.

The effective Redis key is `<keyPrefix>:<mapped key bytes>` — the `:` separator
(`RedisCacheKeyMapper.DELIMITER`) is appended for you, so `keyPrefix = "orders"` produces
`orders:<key>`.

A **blank** prefix is accepted but dangerous, and it changes `invalidateAll()`:

| `keyPrefix` | `invalidateAll()` |
|---|---|
| non-blank | `SCAN <prefix>:*` then `DEL` on the matches |
| `""` | **`FLUSHALL`** — every key in the Redis instance, including other applications' |

Two warnings exist for this — at startup
`Redis Cache key prefix is empty! This can lead to key collisions or flushAll keys for invalidateAll command.`
and at invalidation time
`Redis Cache key prefix is empty! Initiating flushAll for invalidateAll command.`

**Do not rely on seeing either.** `AbstractRedisCache` resolves its logger once in the constructor as
`config.telemetry().logging().enabled() ? LoggerFactory.getLogger(getClass()) : NOPLogger.NOP_LOGGER`,
and `telemetry.logging.enabled` defaults to `false`. With the default configuration a blank
`keyPrefix` therefore wipes the Redis instance **silently**. Set `telemetry.logging.enabled = true`
on that cache section if you want the warnings, and set a distinct non-blank prefix per cache
regardless.

---

## Value serialisation

The generated `$Cache_Module` asks the graph for a `RedisCacheValueMapper<V>`, carrying whatever tag
sits on the **value type argument** of the `@Cache` interface. That is why the `@Json` goes there:

```java
@Cache("orders.cache")
public interface OrderCache extends RedisCache<UUID, @Json OrderDto> {}
```

`@Json` (`io.koraframework.json.common.annotation.Json`) is itself `@Tag(Json.class)` and is
`TYPE_USE`-targetable, so it works in that position in both Java and Kotlin. The `OrderDto` record
or data class **also** needs `@Json` so a `JsonReader`/`JsonWriter` pair is generated for it.

`RedisCacheMapperModule` ships `@DefaultComponent` value mappers, so these value types need no
`@Json` at all: `String`, `byte[]`, `Boolean`, `Character`, `Short`, `Integer`, `Long`,
`BigInteger`, `Float`, `Double`, `BigDecimal`, `UUID`, `Instant`, `LocalDate`, `LocalDateTime`,
`ZonedDateTime`, `Duration`, `Period`, and any `Enum` (stored as `toString()`; an unknown value
deserialises to `null` with a warning).

For anything else, declare your own:

```java
@Component
public final class OrderDtoRedisValueMapper implements RedisCacheValueMapper<OrderDto> {

    @Override
    public byte[] write(OrderDto value) { … }

    @Override
    public @Nullable OrderDto read(byte @Nullable [] serializedValue) { … }
}
```

In Kotlin, remember that `JsonReader.read` returns a nullable value — wrap with `requireNotNull`
where you need a non-null result.

---

## Key serialisation

Keys are turned into bytes by a `RedisCacheKeyMapper<K>`; the built-ins cover the same scalar types
as above plus `Collection<T>` (sorted, `:`-joined). For a **record** (Java) or **data class**
(Kotlin) key type, the generated `$Cache_Module` adds a composite mapper that maps each component
and joins with `:`. Details and the custom-mapper shape:
[cache-key-mapper-reference.md](cache-key-mapper-reference.md).

---

## The `RedisCache` contract

`RedisCache<K, V>` adds a per-call TTL override to `Cache<K, V>`:

```java
V putExpireAfterWrite(K key, V value, Duration expireAfterWrite);
Map<K, V> putExpireAfterWrite(Map<K, V> keyAndValues, Duration expireAfterWrite);
```

`put(key, value)` is `putExpireAfterWrite` with the configured `expireAfterWrite` (or a plain `SET`
when it is unset). Passing `null` as the `Duration` to the explicit form throws
`RedisCache#putExpireAfterWrite received nullable expireAfterWrite argument`.

There is **no** asynchronous variant of the contract in 2.0 — no `CompletionStage` methods. What
*is* asynchronous is the write side of an annotation declared `mode = CacheMode.ASYNC`; the
contract itself stays synchronous.

Like Caffeine, `put` silently skips null keys and null values.

---

## Errors are swallowed

`AbstractRedisCache` catches every exception from the client, reports it to telemetry, and then
returns as if nothing happened: `get` yields `null` (a miss), `put` returns the value it was given,
`invalidate` returns normally. **A Redis outage degrades the service to "always miss", it does not
raise.**

Consequences:

- `@Cacheable` keeps working during a Redis outage — every call hits the underlying method.
- `@CachePut` and `@CacheInvalidate` can silently fail to write or evict, so a stale L1 or another
  pod's cache may keep serving old data. Do not rely on Redis eviction for correctness.
- Alert on the cache error telemetry, not on application exceptions.

Only failures of Redis itself are swallowed. An exception thrown by the loader passed to
`computeIfAbsent` — which is the `@Cacheable` method body — is recorded in telemetry and
**propagates** to the caller, and nothing is written to Redis for that key.

This is the opposite of the Caffeine cache, which lets exceptions propagate.

---

## Customising the Lettuce client

Kora 1.x `LettuceConfigurator` **does not exist in 2.0**. The three hooks are separate
`io.koraframework.common.Configurer<T>` components, each requested with `@Tag(Tag.Factory.class)`:

```java
@Component
@Tag(Tag.Factory.class)
public final class RedisClientResourcesConfigurer implements Configurer<DefaultClientResources.Builder> {

    @Override
    public DefaultClientResources.Builder configure(DefaultClientResources.Builder builder) {
        return builder.ioThreadPoolSize(4);
    }
}
```

| Builder type | Applies to |
|---|---|
| `DefaultClientResources.Builder` | shared client resources (threads, event loops) |
| `io.lettuce.core.ClientOptions.Builder` | standalone client options |
| `io.lettuce.core.cluster.ClusterClientOptions.Builder` | cluster client options |

`Configurer<T>` is a single-method interface — `T configure(T t)` — so a lambda-shaped module method
works too. Whole-factory replacement is also possible: `LettuceFactory` and `AbstractRedisClient`
are `@DefaultComponent @Tag(Tag.Factory.class)`.

---

## Telemetry

Cache telemetry defaults: `logging.enabled = false`, `metrics.enabled = false`,
`tracing.enabled = true`. Unlike Caffeine, the Redis cache does emit Kora's own Micrometer series
when metrics are enabled:

| Metric | Type | Tags |
|---|---|---|
| `cache.operation.duration` | Timer | `system.config`, `system.name.simple`, `system.name.canonical`, `cache.origin` (`redis`), `cache.operation`, `error.type` + configured `telemetry.metrics.tags` |
| `cache.requests` | Counter | the same, with `cache.result` = `hit` \| `miss` instead of `error.type` |

2.0.0.RC1 named the counter `cache.ratio` with tags `origin` / `operation` / `type`; RC2 (#972)
renamed them. Spans carry the same `cache.operation` / `cache.origin` attributes.
`cache.operation` is one of `GET`, `GET_MANY`, `GET_ALL`, `PUT`, `PUT_MANY`, `COMPUTE_IF_ABSENT`,
`COMPUTE_IF_ABSENT_MANY`, `INVALIDATE`, `INVALIDATE_MANY`, `INVALIDATE_ALL`.

The Lettuce driver has its own `lettuce.telemetry.{logging,metrics}` section, separate from the
per-cache one.

---

## Testing

The migrated examples run a real Redis with the `testcontainers-extensions-redis` JUnit extension
and feed its coordinates in through system properties:

```java
@TestcontainersRedis(mode = ContainerMode.PER_RUN)
@KoraAppTest(Application.class)
class OrderCacheTests implements KoraAppTestConfigModifier {

    @ConnectionRedis
    private RedisConnection connection;

    @TestComponent
    private OrderCache cache;

    @Override
    public KoraConfigModification config() {
        return KoraConfigModification
                .ofSystemProperty("REDIS_URL", connection.params().uri().toString())
                .withSystemProperty("REDIS_USER", connection.params().username())
                .withSystemProperty("REDIS_PASS", connection.params().password());
    }

    @BeforeEach
    void cleanup() {
        cache.invalidateAll();
    }
}
```

with `lettuce { uri = ${REDIS_URL} … }` in the test config. Any Testcontainers Redis setup works;
what matters is that `lettuce.uri` resolves. See `kora-testing-junit-java` /
`kora-testing-junit-kotlin`.

---

## Troubleshooting

| Symptom | Cause |
|---|---|
| `No component found for dependency: io.koraframework.cache.redis.RedisCacheClient (no tags)` | `RedisCacheModule` connected instead of `LettuceRedisCacheModule`, or `cache-redis-lettuce` missing |
| `Could not find io.koraframework:cache-redis` | that artifact does not exist in 2.0 — use `cache-redis-lettuce` |
| `Config expected value, but got null at path: 'ROOT.<cache>.keyPrefix'` | `keyPrefix` is required |
| `Config expected value, but got null at path: 'ROOT.lettuce.uri'` | the `lettuce` section is missing or `uri` is unset |
| `invalidateAll()` emptied the whole Redis instance | blank `keyPrefix` → `FLUSHALL` |
| `No component found for dependency: … RedisCacheValueMapper<OrderDto> with @Tag(….Json.class)` | `@Json` on the value type argument but the DTO itself is not `@Json`, or `JsonModule` / `json-common` is missing |
| values come back `null` after a deploy | the serialised form changed; `keyPrefix` is also the versioning lever |
| everything is a miss and no errors | Redis is unreachable — the cache swallows the failure; check the cache telemetry |
| `@Cache interface '…' implements both Redis and Caffeine cache contracts.` | one contract per `@Cache` interface; declare two interfaces for L1/L2 |

---

## See also

- [cacheable-reference.md](cacheable-reference.md) — the operation annotations and `CacheMode`
- [cache-key-mapper-reference.md](cache-key-mapper-reference.md) — key mapping
- [cache-caffeine-reference.md](cache-caffeine-reference.md) — the in-process backend
- [multi-level-cache-reference.md](multi-level-cache-reference.md) — Redis as L2
