# Testcontainers Kafka Reference

**Source:** `.kora-agent/kora-docs/mkdocs/docs/en/documentation/kafka.md` (Kora Kafka
config shape), `.kora-agent/kora-docs/mkdocs/docs/en/documentation/junit5.md`
(`@KoraAppTest` / config modifier)

Integration testing Kora Kafka consumers (`@KafkaListener`) and producers
(`@KafkaPublisher`) against a real broker via Testcontainers.

## Contents

- [Dependencies](#dependencies)
- [Kora Kafka config shape](#kora-kafka-config-shape)
- [Test setup](#test-setup)
- [Producer verification with a raw consumer](#producer-verification-with-a-raw-consumer)
- [Consumer verification with Awaitility](#consumer-verification-with-awaitility)
- [Best practices](#best-practices)
- [Troubleshooting](#troubleshooting)

---

## Dependencies

```groovy
dependencies {
    koraBom platform("ru.tinkoff.kora:kora-parent:1.2.17")

    testImplementation "org.testcontainers:junit-jupiter:1.21.4"
    testImplementation "org.testcontainers:kafka:1.21.4"
    testImplementation "ru.tinkoff.kora:kafka"
    testImplementation "ru.tinkoff.kora:test-junit5"
}
```

---

## Kora Kafka config shape

Kora has **no** flat `kafka.bootstrapServers` key. Each `@KafkaListener("kafka.<name>")`
and each `@KafkaPublisher` reads its own config section, and the broker address goes into
`driverProperties` using the native Kafka client property names. The consumer offset is
controlled by `offset` (`"earliest"`/`"latest"`/a `Duration`), not `autoOffsetReset`.

```hocon
kafka {
  ordersConsumer {
    topics = ["orders-topic"]
    offset = "earliest"
    driverProperties {
      "bootstrap.servers" = ${KAFKA_BOOTSTRAP_SERVERS}
      "group.id" = "test-consumer-group"
    }
  }
  ordersProducer {
    driverProperties {
      "bootstrap.servers" = ${KAFKA_BOOTSTRAP_SERVERS}
    }
  }
}
```

Match the config paths to the strings used in your `@KafkaListener(...)` annotations and to
the publisher's configured path. See the `kora-kafka-consumer` and `kora-kafka-producer`
skills for the listener/publisher config classes (`KafkaListenerConfig`, etc.).

---

## Test setup

```java
@Testcontainers
@KoraAppTest(Application.class)
class KafkaIntegrationTest implements KoraAppTestConfigModifier {

    @Container
    static final KafkaContainer KAFKA = new KafkaContainer(
            DockerImageName.parse("confluentinc/cp-kafka:7.5.0"))
            .withStartupTimeout(Duration.ofSeconds(60));

    @TestComponent
    private OrderMessageProducer producer;

    @NotNull
    @Override
    public KoraConfigModification config() {
        return KoraConfigModification.ofString("""
                kafka {
                  ordersConsumer {
                    topics = ["orders-topic"]
                    offset = "earliest"
                    driverProperties {
                      "bootstrap.servers" = ${KAFKA_BOOTSTRAP_SERVERS}
                      "group.id" = "test-consumer-group"
                    }
                  }
                  ordersProducer {
                    driverProperties {
                      "bootstrap.servers" = ${KAFKA_BOOTSTRAP_SERVERS}
                    }
                  }
                }
                """)
                .withSystemProperty("KAFKA_BOOTSTRAP_SERVERS", KAFKA.getBootstrapServers());
    }
}
```

Kafka takes longer to start than PostgreSQL — keep a generous `withStartupTimeout`.

---

## Producer verification with a raw consumer

Send through the Kora producer, then read the topic with a plain `KafkaConsumer` to assert
the message landed:

```java
@Test
void shouldSendMessageToKafka() {
    var order = new OrderMessage("order-1", 99.99);

    var consumerProps = Map.of(
            ConsumerConfig.BOOTSTRAP_SERVERS_CONFIG, KAFKA.getBootstrapServers(),
            ConsumerConfig.GROUP_ID_CONFIG, "verify-group",
            ConsumerConfig.AUTO_OFFSET_RESET_CONFIG, "earliest",
            ConsumerConfig.KEY_DESERIALIZER_CLASS_CONFIG, StringDeserializer.class,
            ConsumerConfig.VALUE_DESERIALIZER_CLASS_CONFIG, StringDeserializer.class);

    try (var rawConsumer = new KafkaConsumer<String, String>(consumerProps)) {
        rawConsumer.subscribe(List.of("orders-topic"));

        producer.send(order);

        var records = rawConsumer.poll(Duration.ofSeconds(5));
        assertFalse(records.isEmpty());
        assertTrue(records.iterator().next().value().contains("order-1"));
    }
}
```

---

## Consumer verification with Awaitility

Kafka delivery is asynchronous, so poll the consumer's observable side effect with
Awaitility instead of `Thread.sleep`. Send with a plain `KafkaProducer` and assert that the
Kora `@KafkaListener` processed the record:

```java
@Test
void shouldConsumeMessageFromKafka() {
    var producerProps = Map.of(
            ProducerConfig.BOOTSTRAP_SERVERS_CONFIG, KAFKA.getBootstrapServers(),
            ProducerConfig.KEY_SERIALIZER_CLASS_CONFIG, StringSerializer.class,
            ProducerConfig.VALUE_SERIALIZER_CLASS_CONFIG, StringSerializer.class);

    try (var rawProducer = new KafkaProducer<String, String>(producerProps)) {
        rawProducer.send(new ProducerRecord<>("orders-topic", "order-1",
                "{\"orderId\":\"order-1\",\"amount\":99.99}"));
    }

    Awaitility.await()
            .atMost(Duration.ofSeconds(10))
            .untilAsserted(() -> assertEquals(1, consumer.getProcessedOrders().size()));
}
```

`Awaitility` comes from `org.awaitility:awaitility` (add it as a `testImplementation`).

---

## Best practices

1. Put `bootstrap.servers` in `driverProperties` per listener/publisher — there is no flat key.
2. Use `offset = "earliest"` so a freshly started consumer reads test messages.
3. Give Kafka a long `withStartupTimeout`.
4. Verify async delivery with Awaitility, not sleeps.
5. Use unique `group.id` values per test to avoid offset bleed-through.

---

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| Container never starts | Docker down / low memory | Start Docker, allocate more RAM |
| Startup timeout | Kafka slow to boot | Raise `withStartupTimeout(...)` |
| Message not consumed | Wrong topic or offset | Check `topics` and set `offset = "earliest"` |
| Consumer idle | Wrong config path | Match `@KafkaListener("kafka.<name>")` to the config section |
| Connection refused | Missing bootstrap servers | Set `driverProperties { "bootstrap.servers" = ... }` |
