# Kafka Serialization Reference

**Source:** [.kora-agent/kora-docs/mkdocs/docs/en/documentation/kafka.md](.kora-agent/kora-docs/mkdocs/docs/en/documentation/kafka.md)  
**Examples:** `.kora-agent/kora-examples/kora-java-kafka/`

Serialization and deserialization of messages in Kora Kafka.

## JSON serialization with @Json

### Consumer (deserialization)

```java
@Component
public final class JsonListener {
    
    @Json
    public record MyEvent(String id, String name, Integer code) {}
    
    @KafkaListener("kafka.consumer.jsonListener")
    void process(@Json MyEvent event) {
        // event is automatically deserialized from JSON
    }
}
```

### Producer (serialization)

```java
@KafkaPublisher("kafka.producer.jsonPublisher")
public interface JsonPublisher {
    
    @Json
    record MyEvent(String id, String name, Integer code) {}
    
    @Topic("kafka.producer.events")
    void send(@Json MyEvent event);
}
```

## Custom serializers with @Tag

### Defining tags

```java
public final class MyKeyTag {}
public final class MyValueTag {}
```

### Consumer with tags

```java
@Component
public final class TaggedListener {
    
    @KafkaListener("kafka.consumer.listener")
    void process(
        @Tag(MyKeyTag.class) String key,
        @Tag(MyValueTag.class) String value
    ) { }
    
    @KafkaListener("kafka.consumer.listener")
    void process(
        ConsumerRecord<@Tag(MyKeyTag.class) String, @Tag(MyValueTag.class) String> record
    ) { }
}
```

### Producer with tags

```java
@KafkaPublisher("kafka.producer.publisher")
public interface TaggedPublisher {
    
    void send(
        ProducerRecord<@Tag(MyKeyTag.class) String, @Tag(MyValueTag.class) String> record
    );
    
    @Topic("kafka.producer.topic")
    void send(
        @Tag(MyKeyTag.class) String key,
        @Tag(MyValueTag.class) String value
    );
}
```

### Registering serializers

```java
@Component
public final class MySerializerModule implements Module {
    
    @Tag(MyValueTag.class)
    @DefaultComponent
    public Serializer<String> myValueSerializer() {
        return new MyCustomSerializer();
    }
}
```

## ByteArray serialization

By default, `Deserializer<byte[]>` is used for the value, which simply returns the raw bytes.

```java
@KafkaListener("kafka.consumer.listener")
void process(byte[] value) {
    // Raw message bytes
}
```

## Serializer configuration

```hocon
kafka {
  consumer {
    myListener {
      driverProperties {
        "bootstrap.servers" = "localhost:9093"
        "group.id" = "my-group"
        # Standard Kafka properties
        "key.deserializer" = "org.apache.kafka.common.serialization.StringDeserializer"
        "value.deserializer" = "org.apache.kafka.common.serialization.StringDeserializer"
      }
    }
  }
  producer {
    myPublisher {
      driverProperties {
        "bootstrap.servers" = "localhost:9093"
        # Standard Kafka properties
        "key.serializer" = "org.apache.kafka.common.serialization.StringSerializer"
        "value.serializer" = "org.apache.kafka.common.serialization.StringSerializer"
      }
    }
  }
}
```

## Avro serialization

For Avro, use custom serializers:

```java
@Tag(AvroTag.class)
@Component
public final class AvroSerializer implements Serializer<MyAvroRecord> {
    private final Schema schema;
    private final DatumWriter<MyAvroRecord> writer;
    
    @Override
    public byte[] serialize(MyAvroRecord data) {
        // Avro serialization
    }
}
```

## Protobuf serialization

For Protobuf, use custom serializers:

```java
@Tag(ProtobufTag.class)
@Component
public final class ProtobufSerializer implements Serializer<MyMessage> {
    @Override
    public byte[] serialize(MyMessage data) {
        return data.toByteArray();
    }
}
```
