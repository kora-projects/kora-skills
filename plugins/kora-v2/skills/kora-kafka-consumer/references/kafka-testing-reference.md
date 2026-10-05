# Kafka Consumer Testing Reference (Kora 2.0)

Integration-testing `@KafkaListener` against a real broker with `@KoraAppTest` and Testcontainers.

## Contents

- [Dependencies](#dependencies)
- [Testcontainers 2.x renamed its modules](#testcontainers-2x-renamed-its-modules)
- [The two things every Kafka test needs](#the-two-things-every-kafka-test-needs)
- [Java test](#java-test)
- [Kotlin test](#kotlin-test)
- [Raw Testcontainers](#raw-testcontainers)
- [Overriding configuration](#overriding-configuration)
- [Asserting asynchronously](#asserting-asynchronously)
- [Testing a batch listener](#testing-a-batch-listener)
- [Pitfalls](#pitfalls)

---

## Dependencies

The Kora 2.0 example and guide applications drive Kafka through the GoodForGod Testcontainers
extension, which starts the broker, creates topics and gives the test a producer/consumer handle:

```groovy
dependencies {
    testImplementation "io.koraframework:test-junit5"            // versioned by kora-bom
    testImplementation "io.goodforgod:testcontainers-extensions-kafka:0.15.0"

    // Not managed by kora-bom. The versions below are the ones the migrated example and guide
    // apps pin on `migration/2.0`; bump them freely.
    testImplementation "org.awaitility:awaitility:4.2.0"
    testImplementation "org.json:json:20231013"                  // convenient JSON payloads
}
```

Kotlin adds nothing extra for tests unless the test sources declare their own `@KoraApp`, in which
case `kspTest("io.koraframework:symbol-processors")` is needed as well.

JUnit itself comes from the `kora-bom` (JUnit `6.1.3` in the 2.0 catalog) through
`io.koraframework:test-junit5`; do not pin `junit-jupiter` separately.

---

## Testcontainers 2.x renamed its modules

Kora 2.0 builds against Testcontainers **2.0.5**, where the module coordinates and packages changed:

| Testcontainers 1.x | Testcontainers 2.x |
|---|---|
| `org.testcontainers:kafka` | **`org.testcontainers:testcontainers-kafka`** |
| `org.testcontainers.containers.KafkaContainer` | **`org.testcontainers.kafka.KafkaContainer`** |
| `org.testcontainers:postgresql` | `org.testcontainers:testcontainers-postgresql` |
| `org.testcontainers:cassandra` | `org.testcontainers:testcontainers-cassandra` |

A build file still asking for `org.testcontainers:kafka` resolves an old 1.x artifact (or fails),
and `org.testcontainers.containers.KafkaContainer` does not exist in 2.x. Kora's own internal test
module uses `org.testcontainers.kafka.KafkaContainer` with the image `apache/kafka-native:4.3.1` —
`confluentinc/cp-kafka` is not required.

---

## The two things every Kafka test needs

**1. Point the consumer at the container.** The listener's `bootstrap.servers` must resolve to the
broker the test started. The examples do this with a system property that the config substitutes:

```hocon
driverProperties {
  "bootstrap.servers" = "localhost:9092"
  "bootstrap.servers" = ${?KAFKA_BOOTSTRAP}
}
```

```java
@Override
public KoraConfigModification config() {
    return KoraConfigModification.ofSystemProperty("KAFKA_BOOTSTRAP", connection.params().bootstrapServers());
}
```

**2. Force the container into the test graph.** `@KoraAppTest` builds only the subgraph the test
asks for. Inject the generated container by its tag so the consumer actually starts:

```java
@Tag(OrderListenerModule.OrderListenerProcessTag.class)
@TestComponent
private Lifecycle consumerLifecycle;
```

The tag is `<Class>Module.<Class><Method>Tag`. Skipping this is the single most common reason a
Kafka test times out with an idle listener.

---

## Java test

```java
@TestcontainersKafka(mode = ContainerMode.PER_RUN, topics = @Topics({"orders"}))
@KoraAppTest(Application.class)
class OrderListenerTests implements KoraAppTestConfigModifier {

    @ConnectionKafka
    private KafkaConnection connection;

    @Tag(OrderListenerModule.OrderListenerProcessTag.class)
    @TestComponent
    private Lifecycle consumerLifecycle;

    @TestComponent
    private OrderListener listener;

    @Override
    public KoraConfigModification config() {
        return KoraConfigModification.ofSystemProperty("KAFKA_BOOTSTRAP", connection.params().bootstrapServers());
    }

    @Test
    void consumesOrder() {
        var event = new JSONObject().put("orderId", "1").put("amount", 10.5);

        connection.send("orders", Event.ofValueAndRandomKey(event));

        Awaitility.await()
            .atMost(Duration.ofSeconds(15))
            .until(() -> listener.received().size() == 1);
    }

    @Test
    void reportsDeserializationFailure() {
        connection.send("orders", Event.ofValueAndRandomKey("not-json"));

        Awaitility.await()
            .atMost(Duration.ofSeconds(15))
            .until(() -> listener.failed().size() == 1);
        assertEquals(0, listener.received().size());
    }
}
```

`ContainerMode.PER_RUN` starts one broker for the whole test run — much faster than per-class.

To assert that the listener **published** something, subscribe before sending:

```java
var output = connection.subscribe("orders-processed");
connection.send("orders", Event.ofValue("payload"));
assertTrue(output.assertReceivedAtLeast(1).stream()
    .anyMatch(e -> "processed:payload".equals(e.value().asString())));
```

For a transactional pipeline, ask the extension's consumer for committed records only:

```java
@ConnectionKafka(properties = {ConsumerConfig.ISOLATION_LEVEL_CONFIG, "read_committed"})
KafkaConnection connection;
```

---

## Kotlin test

```kotlin
@TestcontainersKafka(mode = ContainerMode.PER_RUN, topics = Topics("orders"))
@KoraAppTest(Application::class)
class OrderListenerTests : KoraAppTestConfigModifier {

    @ConnectionKafka
    lateinit var connection: KafkaConnection

    @Tag(OrderListenerModule.OrderListenerProcessTag::class)
    @TestComponent
    lateinit var consumerLifecycle: Lifecycle

    @TestComponent
    lateinit var listener: OrderListener

    override fun config(): KoraConfigModification =
        KoraConfigModification.ofSystemProperty("KAFKA_BOOTSTRAP", connection.params().bootstrapServers())

    @Test
    fun consumesOrder() {
        connection.send("orders", Event.ofValueAndRandomKey("""{"orderId":"1","amount":10.5}"""))

        Awaitility.await()
            .atMost(Duration.ofSeconds(15))
            .until { listener.received().size == 1 }

        assertEquals("1", listener.received()[0].orderId)
    }
}
```

Tests are ordinary functions — Kora 2.0 contracts are synchronous, so there is no `runTest`,
no `suspend` and no coroutine dispatcher anywhere in a listener test.

---

## Raw Testcontainers

If you would rather not add the extension, drive the container yourself:

```groovy
testImplementation "org.testcontainers:testcontainers-kafka:2.0.5"
testImplementation "org.testcontainers:junit-jupiter:2.0.5"
```

```java
import org.testcontainers.kafka.KafkaContainer;

@Testcontainers
@KoraAppTest(Application.class)
class OrderListenerTests implements KoraAppTestConfigModifier {

    @Container
    static final KafkaContainer KAFKA = new KafkaContainer(DockerImageName.parse("apache/kafka-native:4.3.1"));

    @Tag(OrderListenerModule.OrderListenerProcessTag.class)
    @TestComponent
    private Lifecycle consumerLifecycle;

    @TestComponent
    private OrderListener listener;

    @Override
    public KoraConfigModification config() {
        return KoraConfigModification.ofSystemProperty("KAFKA_BOOTSTRAP", KAFKA.getBootstrapServers());
    }

    private void send(String topic, String value) {
        var props = new Properties();
        props.put(ProducerConfig.BOOTSTRAP_SERVERS_CONFIG, KAFKA.getBootstrapServers());
        try (var producer = new KafkaProducer<>(props, new StringSerializer(), new StringSerializer())) {
            producer.send(new ProducerRecord<>(topic, value));
        }
    }
}
```

You then own topic creation (or `auto.create.topics.enable`) and the wait for the consumer group to
stabilise, which is what the extension does for you.

---

## Overriding configuration

`KoraConfigModification` has three factories and a chainable system-property setter:

| Factory | Use |
|---|---|
| `ofSystemProperty(key, value)` | inject one substitution into the real `application.conf` |
| `ofString("""…""")` | replace the config wholesale with an inline HOCON document |
| `ofResourceFile("application-test.conf")` | replace it from a test resource |
| `.withSystemProperty(key, value)` | chain more substitutions onto any of the above |

`ofSystemProperty` is preferable for Kafka: it keeps the production config under test and only swaps
the bootstrap address. When you do use `ofString`, remember it **replaces** the whole config — the
inline block must contain every section the graph needs, and it carries the same key names, so a
stale 1.x key inside a test string is as wrong as one in `application.conf`.

For a test that needs a deterministic group, override it as well:

```java
return KoraConfigModification
    .ofSystemProperty("KAFKA_BOOTSTRAP", connection.params().bootstrapServers())
    .withSystemProperty("KAFKA_GROUP", "orders-test-" + UUID.randomUUID());
```

---

## Asserting asynchronously

Consumption is asynchronous and group membership takes a moment to settle, so never assert straight
after `send`. Expose observable state on the listener (a counter, a `CopyOnWriteArrayList`) and poll
it with Awaitility, `atMost` 10–20 seconds. Use `auto.offset.reset = "earliest"` in the test config
so a record published before the consumer joined is still delivered.

`org.testcontainers.shaded.org.awaitility.Awaitility` is available transitively, but depend on
`org.awaitility:awaitility` explicitly rather than importing a shaded package.

---

## Testing a batch listener

Send several records, then wait for the accumulated total. Batch boundaries are not deterministic —
assert on the total processed, never on `records.count()` for a given call:

```java
for (int i = 0; i < 10; i++) {
    connection.send("orders", Event.ofValue("order-" + i));
}
Awaitility.await().atMost(Duration.ofSeconds(20)).until(() -> listener.received().size() == 10);
```

To exercise the empty-poll path, set `allowEmptyRecords = true` and assert the counter advances with
no records sent at all.

---

## Pitfalls

| Symptom | Cause | Fix |
|---|---|---|
| Listener never runs | the container was not injected into the test graph | `@Tag(<Class>Module.<Class><Method>Tag.class) @TestComponent Lifecycle` |
| `org.testcontainers.containers.KafkaContainer` not found | Testcontainers 2.x moved it | `org.testcontainers.kafka.KafkaContainer`, module `testcontainers-kafka` |
| `Could not find org.testcontainers:kafka` | 1.x coordinate | `org.testcontainers:testcontainers-kafka` |
| Test consumes nothing published before it started | group defaults to `latest` | `"auto.offset.reset" = "earliest"` |
| Flaky first test only | group rebalance on join | Awaitility with a longer `atMost`, `PER_RUN` container mode |
| Tests interfere with each other | shared `group.id` and topic | unique group per test class, or unique topics |
| Config override ignored | `ofString` replaced the whole config and dropped a section | include every needed section, or use `ofSystemProperty` |
| `${KAFKA_BOOTSTRAP}` unresolved at startup | required substitution with nothing set | use the literal-then-`${?VAR}` pattern |
| No logs from the consumer during a failing test | `telemetry.logging.enabled` defaults to `false` | enable it in the test config |

---

## Related references

- [Listener signatures](kafka-listener-reference.md) — the generated tag
- [Consumer configuration](kafka-consumer-reference.md)
- [Transactions](kafka-transactions-reference.md)
- [kora-testing-junit-java](../../kora-testing-junit-java/SKILL.md) · [kora-testing-junit-kotlin](../../kora-testing-junit-kotlin/SKILL.md)

**Source:** framework tag `2.0.0.RC2` —
[test-junit5](https://github.com/kora-projects/kora/tree/2.0.0.RC2/test/test-junit5) ·
[internal test-kafka](https://github.com/kora-projects/kora/tree/2.0.0.RC2/internal/test-kafka);
migrated examples on `migration/2.0` —
[kora-java-kafka tests](https://github.com/kora-projects/kora-examples/tree/migration/2.0/examples/java/kora-java-kafka/src/test) ·
[kora-kotlin-kafka tests](https://github.com/kora-projects/kora-examples/tree/migration/2.0/examples/kotlin/kora-kotlin-kafka/src/test)
