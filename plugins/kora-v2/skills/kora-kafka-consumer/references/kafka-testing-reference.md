# Kafka Testing Reference

**Source:** [.kora-agent/kora-docs/mkdocs/docs/en/documentation/kafka.md](../../../.kora-agent/kora-docs/mkdocs/docs/en/documentation/kafka.md)
**Examples:** [.kora-agent/kora-examples/examples/java/kora-java-kafka/](../../../.kora-agent/kora-examples/examples/java/kora-java-kafka/)

Testing Kafka consumers and producers in Kora using Testcontainers and the Kora JUnit 5 extension (`@KoraAppTest`).

## Contents

- [Dependencies](#dependencies)
- [Quick Start](#quick-start)
- [Annotations](#annotations)
- [Testing Patterns](#testing-patterns)
- [Helper Methods](#helper-methods)
- [Kotlin Example](#kotlin-example)
- [Best Practices](#best-practices)
- [Troubleshooting](#troubleshooting)
- [Related References](#related-references)

---

## Dependencies

```groovy
dependencies {
    testImplementation "org.testcontainers:junit-jupiter:1.21.4"
    testImplementation "org.testcontainers:kafka:1.21.4"
    testImplementation "ru.tinkoff.kora:test-junit5"
    testImplementation "ru.tinkoff.kora:kafka"
    testImplementation "org.json:json:20231013"
    testImplementation "org.awaitility:awaitility:4.2.0"
    testImplementation "org.assertj:assertj-core:3.24.2"
}
```

---

## Quick Start

### Consumer Test

```java
@Testcontainers
@KoraAppTest(Application.class)
class KafkaConsumerTest implements KoraAppTestConfigModifier {

    @Container
    static final KafkaContainer KAFKA = new KafkaContainer(
        DockerImageName.parse("confluentinc/cp-kafka:7.5.0")
    ).withStartupTimeout(Duration.ofSeconds(60));

    @TestComponent
    private MyListener consumer;

    @Override
    public KoraConfigModification config() {
        return KoraConfigModification.ofString("""
            kafka.consumer.myListener {
                topics = ["my-topic"]
                offset = "earliest"
                driverProperties {
                    "bootstrap.servers" = "${KAFKA_BOOTSTRAP_SERVERS}"
                    "group.id" = "test-group"
                }
            }
            """)
            .withSystemProperty("KAFKA_BOOTSTRAP_SERVERS", KAFKA.getBootstrapServers());
    }

    @Test
    void shouldProcessEvent() {
        // given
        var event = new JSONObject().put("id", "123").put("name", "test");
        sendKafkaMessage("my-topic", event.toString());

        // then
        Awaitility.await()
            .atMost(Duration.ofSeconds(15))
            .until(() -> consumer.getProcessedCount() >= 1);
    }

    private void sendKafkaMessage(String topic, String value) {
        var props = new Properties();
        props.put(ConsumerConfig.BOOTSTRAP_SERVERS_CONFIG, KAFKA.getBootstrapServers());
        try (var producer = new KafkaProducer<>(
            props,
            new StringSerializer(),
            new StringSerializer()
        )) {
            producer.send(new ProducerRecord<>(topic, value));
        }
    }
}
```

### Producer Test

```java
@Testcontainers
@KoraAppTest(Application.class)
class KafkaProducerTest implements KoraAppTestConfigModifier {

    @Container
    static final KafkaContainer KAFKA = new KafkaContainer(
        DockerImageName.parse("confluentinc/cp-kafka:7.5.0")
    ).withStartupTimeout(Duration.ofSeconds(60));

    @TestComponent
    private MyPublisher publisher;

    @Override
    public KoraConfigModification config() {
        return KoraConfigModification.ofString("""
            kafka.producer.myPublisher {
                driverProperties {
                    "bootstrap.servers" = "${KAFKA_BOOTSTRAP_SERVERS}"
                }
            }
            """)
            .withSystemProperty("KAFKA_BOOTSTRAP_SERVERS", KAFKA.getBootstrapServers());
    }

    @Test
    void shouldSendMessage() throws Exception {
        // given
        var consumerProps = new Properties();
        consumerProps.put(ConsumerConfig.BOOTSTRAP_SERVERS_CONFIG, KAFKA.getBootstrapServers());
        consumerProps.put(ConsumerConfig.GROUP_ID_CONFIG, "test-group");
        consumerProps.put(ConsumerConfig.KEY_DESERIALIZER_CLASS_CONFIG, StringDeserializer.class);
        consumerProps.put(ConsumerConfig.VALUE_DESERIALIZER_CLASS_CONFIG, StringDeserializer.class);

        // when
        publisher.publish("test-data");

        // then
        try (var kafkaConsumer = new KafkaConsumer<String, String>(consumerProps)) {
            kafkaConsumer.subscribe(List.of("my-topic"));
            var records = kafkaConsumer.poll(Duration.ofSeconds(5));
            assertFalse(records.isEmpty());
            assertEquals("test-data", records.iterator().next().value());
        }
    }
}
```

---

## Annotations

### @Testcontainers

```java
@Testcontainers
@KoraAppTest(Application.class)
class MyTest implements KoraAppTestConfigModifier {
    // ...
}
```

Enables Testcontainers JUnit 5 extension for automatic container lifecycle management.

### @Container

```java
@Container
static final KafkaContainer KAFKA = new KafkaContainer(
    DockerImageName.parse("confluentinc/cp-kafka:7.5.0")
).withStartupTimeout(Duration.ofSeconds(60));
```

Declares a Testcontainers container. Must be `static final` for per-class lifecycle.

### @KoraAppTest

```java
@KoraAppTest(Application.class)
class MyTest implements KoraAppTestConfigModifier {
    @Override
    public KoraConfigModification config() {
        return KoraConfigModification.ofString("""
            kafka.consumer.myListener {
                topics = ["my-topic"]
                driverProperties {
                    "bootstrap.servers" = "${KAFKA_BOOTSTRAP_SERVERS}"
                }
            }
            """)
            .withSystemProperty("KAFKA_BOOTSTRAP_SERVERS", KAFKA.getBootstrapServers());
    }
}
```

Loads Kora application for testing with custom configuration.

### @TestComponent

```java
@TestComponent
private MyListener consumer;

// With tag for consumer lifecycle
@Tag(MyListenerModule.MyListenerProcessTag.class)
@TestComponent
private Lifecycle consumerLifecycle;
```

Injects Kora components into the test.

---

## Testing Patterns

### Consumer with Awaitility

```java
@Test
void shouldProcessMessage() {
    sendKafkaMessage("orders", new JSONObject()
        .put("orderId", "123")
        .toString());

    Awaitility.await()
        .atMost(Duration.ofSeconds(15))
        .pollExecutorService(Executors.newSingleThreadExecutor())
        .until(() -> consumer.getProcessedCount() == 1);
}
```

### Producer with Manual Consumer

```java
@Test
void shouldPublishEvent() throws Exception {
    // given
    var consumerProps = new Properties();
    consumerProps.put(ConsumerConfig.BOOTSTRAP_SERVERS_CONFIG, KAFKA.getBootstrapServers());
    consumerProps.put(ConsumerConfig.GROUP_ID_CONFIG, "test-group");
    consumerProps.put(ConsumerConfig.KEY_DESERIALIZER_CLASS_CONFIG, StringDeserializer.class);
    consumerProps.put(ConsumerConfig.VALUE_DESERIALIZER_CLASS_CONFIG, JsonDeserializer.class);

    // when
    publisher.publish(new OrderEvent("123", "ORDER_CREATED"));

    // then
    try (var kafkaConsumer = new KafkaConsumer<String, OrderEvent>(consumerProps)) {
        kafkaConsumer.subscribe(List.of("orders-topic"));
        var records = kafkaConsumer.poll(Duration.ofSeconds(5));
        assertFalse(records.isEmpty());
        assertEquals("ORDER_CREATED", records.iterator().next().value().getType());
    }
}
```

### Batch Messages

```java
@Test
void shouldProcessBatch() {
    // given
    for (int i = 0; i < 10; i++) {
        var event = new JSONObject()
            .put("id", i)
            .put("type", "BATCH_ITEM")
            .toString();
        sendKafkaMessage("batch-topic", event);
    }

    // when & then
    Awaitility.await()
        .atMost(Duration.ofSeconds(20))
        .until(() -> consumer.getProcessedCount() >= 10);
}
```

### Integration Test (End-to-End)

```java
@Testcontainers
@KoraAppTest(Application.class)
class OrderProcessingIntegrationTest implements KoraAppTestConfigModifier {

    @Container
    static final KafkaContainer KAFKA = new KafkaContainer(
        DockerImageName.parse("confluentinc/cp-kafka:7.5.0")
    ).withStartupTimeout(Duration.ofSeconds(60));

    @TestComponent
    private OrderPublisher publisher;

    @Tag(OrderConsumerModule.OrderConsumerProcessTag.class)
    @TestComponent
    private Lifecycle consumerLifecycle;

    @Override
    public KoraConfigModification config() {
        return KoraConfigModification.ofString("""
            kafka {
                consumer.orderConsumer {
                    topics = ["orders-in"]
                    driverProperties {
                        "bootstrap.servers" = "${KAFKA_BOOTSTRAP_SERVERS}"
                    }
                }
                producer.orderPublisher {
                    driverProperties {
                        "bootstrap.servers" = "${KAFKA_BOOTSTRAP_SERVERS}"
                    }
                }
            }
            """)
            .withSystemProperty("KAFKA_BOOTSTRAP_SERVERS", KAFKA.getBootstrapServers());
    }

    @Test
    void shouldProcessOrderEndToEnd() throws Exception {
        // given
        var order = new JSONObject().put("orderId", "123").put("amount", 100.50);

        // when
        sendKafkaMessage("orders-in", order.toString());

        // then - verify output
        Awaitility.await()
            .atMost(Duration.ofSeconds(15))
            .until(() -> orderProcessor.getProcessedCount() >= 1);

        assertThat(orderProcessor.getLastOrderId()).isEqualTo("123");
    }
}
```

---

## Helper Methods

### Send Kafka Message

```java
private void sendKafkaMessage(String topic, String value) {
    var props = new Properties();
    props.put(ConsumerConfig.BOOTSTRAP_SERVERS_CONFIG, KAFKA.getBootstrapServers());

    try (var producer = new KafkaProducer<>(
        props,
        new StringSerializer(),
        new StringSerializer()
    )) {
        producer.send(new ProducerRecord<>(topic, value));
    }
}
```

### Send Kafka Message with Key

```java
private void sendKafkaMessage(String topic, String key, String value) {
    var props = new Properties();
    props.put(ConsumerConfig.BOOTSTRAP_SERVERS_CONFIG, KAFKA.getBootstrapServers());

    try (var producer = new KafkaProducer<>(
        props,
        new StringSerializer(),
        new StringSerializer()
    )) {
        producer.send(new ProducerRecord<>(topic, key, value));
    }
}
```

### Manual Consumer for Verification

```java
private List<ConsumerRecord<String, String>> consumeMessages(String topic, int expectedCount, Duration timeout) {
    var props = new Properties();
    props.put(ConsumerConfig.BOOTSTRAP_SERVERS_CONFIG, KAFKA.getBootstrapServers());
    props.put(ConsumerConfig.GROUP_ID_CONFIG, "test-verify-group");
    props.put(ConsumerConfig.KEY_DESERIALIZER_CLASS_CONFIG, StringDeserializer.class);
    props.put(ConsumerConfig.VALUE_DESERIALIZER_CLASS_CONFIG, StringDeserializer.class);
    props.put(ConsumerConfig.AUTO_OFFSET_RESET_CONFIG, "earliest");

    var received = new ArrayList<ConsumerRecord<String, String>>();
    var endTime = System.currentTimeMillis() + timeout.toMillis();

    try (var consumer = new KafkaConsumer<String, String>(props)) {
        consumer.subscribe(List.of(topic));

        while (received.size() < expectedCount && System.currentTimeMillis() < endTime) {
            var records = consumer.poll(Duration.ofSeconds(1));
            records.forEach(received::add);
        }
    }

    assertThat(received).hasSize(expectedCount);
    return received;
}
```

---

## Kotlin Example

```kotlin
@Testcontainers
@KoraAppTest(Application::class)
class KafkaConsumerTests : KoraAppTestConfigModifier {

    companion object {
        @Container
        @JvmStatic
        val KAFKA = KafkaContainer(
            DockerImageName.parse("confluentinc/cp-kafka:7.5.0")
        ).withStartupTimeout(Duration.ofSeconds(60))
    }

    @TestComponent
    private lateinit var consumer: MyListener

    override fun config(): KoraConfigModification {
        return KoraConfigModification.ofString("""
            kafka.consumer.myListener {
                topics = ["my-topic"]
                offset = "earliest"
                driverProperties {
                    "bootstrap.servers" = "${KAFKA.bootstrapServers}"
                    "group.id" = "test-group"
                }
            }
            """.trimIndent())
            .withSystemProperty("KAFKA_BOOTSTRAP_SERVERS", KAFKA.bootstrapServers)
    }

    @Test
    fun `should process event`() {
        // given
        val event = JSONObject().put("id", "123").put("name", "test")

        // when
        sendKafkaMessage("my-topic", event.toString())

        // then
        Awaitility.await()
            .atMost(Duration.ofSeconds(15))
            .until { consumer.processedCount >= 1 }
    }

    private fun sendKafkaMessage(topic: String, value: String) {
        val props = Properties().apply {
            put(ConsumerConfig.BOOTSTRAP_SERVERS_CONFIG, KAFKA.bootstrapServers)
        }

        KafkaProducer<String, String>(
            props,
            StringSerializer(),
            StringSerializer()
        ).use { producer ->
            producer.send(ProducerRecord(topic, value))
        }
    }
}
```

---

## Best Practices

1. **Use `@Testcontainers`** — automatic container lifecycle management
2. **Increased startup timeout** — Kafka takes longer to start than PostgreSQL
3. **Use Awaitility for async** — reliable assertions for async processing
4. **Unique group IDs** — isolate tests from each other
5. **Cleanup between tests** — reset consumer state
6. **Test with real JSON** — use `JSONObject` for realistic payloads
7. **Verify with manual consumer** — use raw Kafka consumer for verification

---

## Troubleshooting

| Problem | Cause | Solution |
|---------|-------|----------|
| Container won't start | Docker not running / low memory | Start Docker, allocate more RAM |
| Startup timeout | Slow Kafka startup | Increase `withStartupTimeout()` |
| Message not delivered | Wrong topic / offset | Check `auto.offset.reset = earliest` |
| Consumer not listening | Wrong groupId | Ensure groupId is unique per test |
| Serialization error | Missing deserializers | Add proper serializers/deserializers |
| Test flakiness | Async timing | Use Awaitility with longer timeout |

---

## Related References

- [Kafka doc](../../../.kora-agent/kora-docs/mkdocs/docs/en/documentation/kafka.md)
- [JUnit 5 testing doc](../../../.kora-agent/kora-docs/mkdocs/docs/en/documentation/junit5.md)
- [Kafka example app](../../../.kora-agent/kora-examples/examples/java/kora-java-kafka/)
- [Kafka Consumer Reference](kafka-consumer-reference.md)
