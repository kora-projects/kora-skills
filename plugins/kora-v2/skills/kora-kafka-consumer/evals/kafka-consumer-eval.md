# Kora Kafka Consumer Skill Evals

## Eval Setup

**Prerequisites:**
- Kora 1.x project with Kafka module
- Testcontainers for Kafka
- JUnit 5

**Dependencies:**
```groovy
testImplementation "org.testcontainers:junit-jupiter:1.21.4"
testImplementation "org.testcontainers:kafka:1.21.4"
testImplementation "ru.tinkoff.kora:test-junit5"
testImplementation "ru.tinkoff.kora:kafka"
testImplementation "org.json:json:20231013"
testImplementation "org.awaitility:awaitility:4.2.0"
testImplementation "org.assertj:assertj-core:3.24.2"
```

**Test Scenarios:**
1. Basic message consumption
2. JSON deserialization
3. Error handling (deserialization, business logic)
4. Manual commit
5. Batch processing
6. Rebalance handling
7. Consumer group behavior

---

## Test Cases

### 1. Basic Consumption

**Goal:** Verify basic message consumption works.

```java
@Testcontainers
@KoraAppTest(Application.class)
class BasicConsumptionTest implements KoraAppTestConfigModifier {
    
    @Container
    static final KafkaContainer KAFKA = new KafkaContainer(
        DockerImageName.parse("confluentinc/cp-kafka:7.5.0")
    ).withStartupTimeout(Duration.ofSeconds(60));
    
    @TestComponent
    private TestConsumer consumer;
    
    @Override
    public KoraConfigModification config() {
        return KoraConfigModification.ofString("""
            kafka.consumer.testConsumer {
                topics = ["test-topic"]
                driverProperties {
                    "bootstrap.servers" = "${KAFKA_BOOTSTRAP_SERVERS}"
                    "group.id" = "test-group"
                }
            }
            """)
            .withSystemProperty("KAFKA_BOOTSTRAP_SERVERS", KAFKA.getBootstrapServers());
    }
    
    @Test
    void shouldConsumeMessage() {
        // given
        sendKafkaMessage("test-topic", "test-message");
        
        // when/then
        Awaitility.await()
            .atMost(Duration.ofSeconds(10))
            .until(() -> consumer.getMessages().contains("test-message"));
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

**Pass Criteria:** Message is consumed within timeout.

---

### 2. JSON Deserialization

**Goal:** Verify JSON messages are properly deserialized.

```java
@Test
void shouldDeserializeJson() {
    // given
    var event = new JSONObject()
        .put("id", "123")
        .put("name", "Test")
        .put("timestamp", LocalDateTime.now().toString());
    
    // when
    sendKafkaMessage("json-topic", event.toString());
    
    // then
    Awaitility.await().until(() -> consumer.getLastEvent() != null);
    assertThat(consumer.getLastEvent().id()).isEqualTo("123");
}
```

**Pass Criteria:** JSON is deserialized to typed object with correct field values.

---

### 3. Deserialization Error Handling

**Goal:** Verify invalid JSON is handled gracefully.

```java
@Test
void shouldHandleInvalidJson() {
    // given - invalid JSON
    String invalidJson = "{\"id\": 123}";  // Missing required fields
    
    // when
    sendKafkaMessage("json-topic", invalidJson);
    
    // then
    Awaitility.await().until(() -> consumer.getErrorCount() > 0);
    // Consumer should not crash
}
```

**Pass Criteria:** Consumer handles error without crashing, error is logged/counted.

---

### 4. Business Logic Error Handling

**Goal:** Verify business logic errors are handled correctly.

```java
@Test
void shouldHandleBusinessLogicError() {
    // given - event that will cause business logic error
    var event = new JSONObject()
        .put("id", "error-test")
        .put("invalidField", null)  // Will cause NPE or validation error
        .put("timestamp", LocalDateTime.now().toString());
    
    // when
    sendKafkaMessage("business-topic", event.toString());
    
    // then
    Awaitility.await()
        .atMost(Duration.ofSeconds(10))
        .until(() -> consumer.getBusinessErrorCount() > 0);
}
```

**Pass Criteria:** Error is caught and handled, consumer continues processing.

---

### 5. Manual Commit

**Goal:** Verify manual offset commit works correctly.

```java
@Test
void shouldCommitOffsetManually() throws Exception {
    // given
    var latch = new CountDownLatch(1);
    
    // when
    sendKafkaMessage("commit-topic", "test-message");
    
    // then
    latch.await(10, TimeUnit.SECONDS);
    assertThat(consumer.getCommittedOffset()).isGreaterThan(0);
}
```

**Pass Criteria:** Offset is committed after successful processing.

---

### 6. Batch Processing

**Goal:** Verify batch message processing.

```java
@Test
void shouldProcessBatch() {
    // given - send multiple messages
    int batchSize = 10;
    for (int i = 0; i < batchSize; i++) {
        var event = new JSONObject()
            .put("id", "batch-" + i)
            .put("data", "value-" + i)
            .toString();
        sendKafkaMessage("batch-topic", event);
    }
    
    // when & then
    Awaitility.await()
        .atMost(Duration.ofSeconds(20))
        .until(() -> consumer.getProcessedCount() >= batchSize);
    
    assertThat(consumer.getProcessedCount()).isGreaterThanOrEqualTo(batchSize);
}
```

**Pass Criteria:** All messages in batch are processed.

---

### 7. Consumer Group Behavior

**Goal:** Verify consumer group behavior and message distribution.

```java
@Test
void shouldDistributeMessagesAcrossGroup() {
    // given - single consumer instance test
    int messageCount = 20;
    for (int i = 0; i < messageCount; i++) {
        sendKafkaMessage("group-topic", "message-" + i);
    }
    
    // when & then - all messages processed by single instance
    Awaitility.await()
        .atMost(Duration.ofSeconds(15))
        .until(() -> consumer.getProcessedCount() >= messageCount);
}
```

**Pass Criteria:** Messages are distributed across consumer group instances.

---

### 8. Rebalance Handling

**Goal:** Verify consumer handles rebalance correctly.

```java
@Test
void shouldHandleRebalance() {
    // given - simulate rebalance scenario
    sendKafkaMessage("rebalance-topic", "message-1");
    
    // when - consumer should handle rebalance
    // (full test requires multiple consumers)
    
    // then
    Awaitility.await()
        .atMost(Duration.ofSeconds(15))
        .until(() -> consumer.getRebalanceCount() >= 0);
}
```

**Pass Criteria:** Consumer handles rebalance without losing messages.

---

### 9. High Volume Processing

**Goal:** Verify consumer can handle high message volume.

```java
@Test
void shouldHandleHighVolume() {
    // given
    int volume = 100;
    for (int i = 0; i < volume; i++) {
        var event = new JSONObject()
            .put("id", "volume-" + i)
            .put("data", "data-" + i)
            .toString();
        sendKafkaMessage("volume-topic", event);
    }
    
    // when & then
    Awaitility.await()
        .atMost(Duration.ofSeconds(30))
        .until(() -> consumer.getProcessedCount() >= volume);
}
```

**Pass Criteria:** All high-volume messages are processed without loss.

---

### 10. Duplicate Event Handling

**Goal:** Verify duplicate events are handled (idempotency).

```java
@Test
void shouldHandleDuplicates() {
    // given
    String duplicateMessage = "duplicate-test";
    sendKafkaMessage("duplicate-topic", duplicateMessage);
    sendKafkaMessage("duplicate-topic", duplicateMessage);  // Send twice
    
    // when & then
    Awaitility.await()
        .atMost(Duration.ofSeconds(15))
        .until(() -> consumer.getProcessedCount() >= 2);
    
    // Both messages processed (Kafka doesn't deduplicate)
    // Business logic should handle idempotency
}
```

**Pass Criteria:** Both duplicate messages are processed; business logic handles idempotency.

---

## Helper Methods for Tests

```java
// Send message without key
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

// Send message with key
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

// Consume messages for verification
private List<ConsumerRecord<String, String>> consumeMessages(
    String topic, int expectedCount, Duration timeout
) {
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

## Kotlin Tests

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
    private lateinit var consumer: TestConsumer

    override fun config(): KoraConfigModification {
        return KoraConfigModification.ofString("""
            kafka.consumer.testConsumer {
                topics = ["test-topic"]
                driverProperties {
                    "bootstrap.servers" = "${KAFKA.bootstrapServers}"
                    "group.id" = "test-group"
                }
            }
            """.trimIndent())
            .withSystemProperty("KAFKA_BOOTSTRAP_SERVERS", KAFKA.bootstrapServers)
    }

    @Test
    fun `should consume message`() {
        // given
        sendKafkaMessage("test-topic", "test-message")

        // when/then
        Awaitility.await()
            .atMost(Duration.ofSeconds(10))
            .until { consumer.messages.contains("test-message") }
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
