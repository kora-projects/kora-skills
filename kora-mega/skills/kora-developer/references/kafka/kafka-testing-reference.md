# Kafka Testing Reference

**Source:** [.kora-agent/kora-docs/mkdocs/docs/en/documentation/kafka.md](.kora-agent/kora-docs/mkdocs/docs/en/documentation/kafka.md), [.kora-agent/kora-docs/mkdocs/docs/en/documentation/testing.md](.kora-agent/kora-docs/mkdocs/docs/en/documentation/testing.md)  
**Examples:** `.kora-agent/kora-examples/kora-java-kafka/`

Testing Kafka consumers and producers in Kora using **testcontainers-extensions-kafka** and the **Kora JUnit5 extension**.

## Resources

- [GitHub Repository](https://github.com/GoodforGod/testcontainers-extensions)
- [Kafka Extension README](https://github.com/GoodforGod/testcontainers-extensions/blob/master/kafka/README.md)
- [Kora JUnit5 Extension](https://kora-projects.github.io/kora-docs/en/documentation/junit5.html)
- [Kora Kafka Examples](https://github.com/kora-projects/kora-examples/tree/master/kora-java-kafka/src/test)

---

## Dependencies

```groovy
dependencies {
    testImplementation "ru.tinkoff.kora:test-junit5"
    testImplementation "io.goodforgod:testcontainers-extensions-kafka:0.13.1"
    testRuntimeOnly "org.apache.kafka:kafka-clients:3.5.1"
    testImplementation "org.json:json:20231013"
    testImplementation "org.awaitility:awaitility:4.2.0"
}
```

---

## Quick Start

### Consumer test

```java
@TestcontainersKafka(mode = ContainerMode.PER_RUN, topics = @Topics({ "my-topic" }))
@KoraAppTest(Application.class)
class KafkaConsumerTest implements KoraAppTestConfigModifier {

    @ConnectionKafka
    private KafkaConnection connection;

    @TestComponent
    private MyListener consumer;

    @Override
    public KoraConfigModification config() {
        return KoraConfigModification.ofSystemProperty("KAFKA_BOOTSTRAP", connection.params().bootstrapServers());
    }

    @Test
    void shouldProcessEvent() {
        var event = new JSONObject().put("id", "123").put("name", "test");
        connection.send("my-topic", Event.ofValueAndRandomKey(event));

        Awaitility.await()
            .atMost(Duration.ofSeconds(15))
            .pollExecutorService(Executors.newSingleThreadExecutor())
            .until(() -> consumer.received().size() == 1);
    }
}
```

### Producer test

```java
@TestcontainersKafka(mode = ContainerMode.PER_RUN, topics = @Topics({ "my-topic" }))
@KoraAppTest(Application.class)
class KafkaProducerTest implements KoraAppTestConfigModifier {

    @ConnectionKafka
    private KafkaConnection connection;

    @TestComponent
    private MyPublisher publisher;

    @Override
    public KoraConfigModification config() {
        return KoraConfigModification.ofSystemProperty("KAFKA_BOOTSTRAP", connection.params().bootstrapServers());
    }

    @Test
    void shouldSendMessage() {
        var consumer = connection.subscribe("my-topic");
        var event = new JSONObject().put("username", "Ivan").put("code", 42);

        publisher.send(event.toString());

        var received = consumer.assertReceivedAtLeast(1).get(0);
        assertEquals("Ivan", received.value().asJson().getString("username"));
    }
}
```

---

## Annotations

### @TestcontainersKafka

```java
@TestcontainersKafka(
    mode = ContainerMode.PER_RUN,
    image = "apache/kafka-native:4.1.0",
    topics = @Topics({
        @Topic(value = "topic-1", reset = Topics.Mode.PER_METHOD),
        @Topic("topic-2")
    }),
    network = @Network(shared = true)
)
```

| Parameter | Description |
|-----------|-------------|
| `mode` | `PER_RUN` (fast), `PER_CLASS`, `PER_METHOD` (isolated) |
| `image` | Kafka image (by default `apache/kafka-native:4.1.0`) |
| `topics` | Topics to create |
| `network` | Network for the container |

### @KoraAppTest

```java
@KoraAppTest(Application.class)
class MyTest implements KoraAppTestConfigModifier {
    @Override
    public KoraConfigModification config() {
        return KoraConfigModification.ofSystemProperty("KAFKA_BOOTSTRAP", connection.params().bootstrapServers());
    }
}
```

### @ConnectionKafka

```java
@ConnectionKafka
private KafkaConnection connection;

// With custom properties
@ConnectionKafka(properties = { "auto.offset.reset", "earliest" })
private KafkaConnection customConnection;
```

### @TestComponent

```java
@TestComponent
private MyListener consumer;

// With tag
@Tag(MyListenerModule.MyListenerProcessTag.class)
@TestComponent
private Lifecycle consumerLifecycle;
```

---

## KafkaConnection API

### Sending messages

```java
connection.send("topic", Event.ofValue("value"));
connection.send("topic", Event.ofValueAndRandomKey(event));
connection.send("topic", Event.ofKeyValue("key1", "value1"));
connection.send("topic", Event.ofValue("v1"), Event.ofValue("v2"), Event.ofValue("v3"));
```

### Subscribing and receiving

```java
var consumer = connection.subscribe("topic");
var records = consumer.receive(Duration.ofSeconds(5));
var received = consumer.assertReceivedAtLeast(2, Duration.ofSeconds(5));
consumer.assertReceivedExactly(3, Duration.ofSeconds(10));

var first = received.get(0);
String key = first.key();
String value = first.value();
JsonObject json = first.value().asJson();
```

---

## Testing patterns

### Consumer with Awaitility

```java
@Test
void shouldProcessMessage() {
    connection.send("orders", Event.ofValueAndRandomKey(new JSONObject().put("orderId", "123")));

    Awaitility.await()
        .atMost(Duration.ofSeconds(15))
        .pollExecutorService(Executors.newSingleThreadExecutor())
        .until(() -> consumer.processedCount() == 1);
}
```

### Producer with assertion

```java
@Test
void shouldPublishEvent() {
    var consumer = connection.subscribe("events");
    var eventData = new JSONObject().put("type", "ORDER_CREATED").put("orderId", "123");

    publisher.publish(eventData.toString());

    var received = consumer.assertReceivedAtLeast(1).get(0);
    assertEquals("ORDER_CREATED", received.value().asJson().getString("type"));
}
```

### Batch messages

```java
@Test
void shouldProcessBatch() {
    var consumer = connection.subscribe("orders");

    connection.send("orders",
        Event.ofKeyValue("order-1", new JSONObject().put("id", 1)),
        Event.ofKeyValue("order-2", new JSONObject().put("id", 2)),
        Event.ofKeyValue("order-3", new JSONObject().put("id", 3))
    );

    var received = consumer.assertReceivedAtLeast(3, Duration.ofSeconds(10));
    assertEquals(3, received.size());
}
```

### Integration test

```java
@TestcontainersKafka(mode = ContainerMode.PER_RUN, topics = @Topics({ "orders-in", "orders-out" }))
@KoraAppTest(Application.class)
class OrderProcessingIntegrationTest implements KoraAppTestConfigModifier {

    @ConnectionKafka
    private KafkaConnection connection;

    @TestComponent
    private OrderPublisher publisher;

    @Tag(OrderConsumerModule.OrderConsumerTag.class)
    @TestComponent
    private Lifecycle consumerLifecycle;

    @Override
    public KoraConfigModification config() {
        return KoraConfigModification.ofSystemProperty("KAFKA_BOOTSTRAP", connection.params().bootstrapServers());
    }

    @Test
    void shouldProcessOrderEndToEnd() {
        var outputConsumer = connection.subscribe("orders-out");
        var order = new JSONObject().put("orderId", "123").put("amount", 100.50);

        connection.send("orders-in", Event.ofValueAndRandomKey(order));

        var result = outputConsumer.assertReceivedAtLeast(1, Duration.ofSeconds(15)).get(0);
        assertEquals("123", result.value().asJson().getString("orderId"));
    }
}
```

---

## External Kafka (without Docker)

```bash
export EXTERNAL_TEST_KAFKA_BOOTSTRAP_SERVERS=kafka.ci.example.com:9092
export EXTERNAL_TEST_KAFKA_AUTO_OFFSET_RESET=earliest
```

```java
@TestcontainersKafka
@KoraAppTest(Application.class)
class ExternalKafkaTest implements KoraAppTestConfigModifier {
    @ConnectionKafka
    private KafkaConnection connection;

    @Override
    public KoraConfigModification config() {
        return KoraConfigModification.ofSystemProperty("KAFKA_BOOTSTRAP", connection.params().bootstrapServers());
    }
}
```

**Variable conversion:** `EXTERNAL_TEST_KAFKA_` is stripped, the rest is lowercased with `.` instead of `_`.

---

## Best Practices

1. **`PER_RUN` for speed** — one container for all tests
2. **Topic reset** — `reset = Topics.Mode.PER_METHOD`
3. **Awaitility for consumers** — async assertions
4. **Timeout 15s** — test stability
5. **External Kafka for CI** — `EXTERNAL_TEST_KAFKA_*`
6. **Unique topics** — avoid conflicts
7. **`@TestComponent`** — inject Kora components

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| Docker is not running | Use external Kafka |
| Receive timeout | Increase `Duration` or use Awaitility |
| Topic not created | Add `@Topics` to `@TestcontainersKafka` |
| State leaking between tests | `reset = Topics.Mode.PER_METHOD` |
| Slow tests | Use `PER_RUN` instead of `PER_METHOD` |
| Consumer does not start | Check `@TestComponent` and `Lifecycle` |

---

## Assert methods

| Method | Description |
|--------|-------------|
| `assertReceivedAtLeast(n)` | Assert ≥ N messages (timeout 5s) |
| `assertReceivedAtLeast(n, timeout)` | Assert ≥ N messages with timeout |
| `assertReceivedExactly(n)` | Assert exactly N messages |
| `receive(timeout)` | Receive records without assertions |
| `receiveAll()` | Receive all available records |

---

## Related resources

- [Testcontainers Kafka Module](https://www.testcontainers.org/modules/kafka/)
- [Kafka Native Docker](https://hub.docker.com/r/apache/kafka-native)
- [Kora Testing](https://kora-projects.github.io/kora-docs/en/documentation/junit5.html)
- [Kora Kafka Examples](https://github.com/kora-projects/kora-examples/tree/master/kora-java-kafka/src/test)
- [Awaitility](http://www.awaitility.org/)
