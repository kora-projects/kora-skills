# Kora Kafka

Kafka integration: producers, consumers, serialization, testing.

## When to use

- Kafka message producers
- Kafka consumers (batch, single)
- Key/value serialization
- Testing with Embedded Kafka

## Quick Start

```bash
/kora-kafka --producer EventProducer --topic events
```

## Key features

- Producers: synchronous and asynchronous
- Consumers: single, batch
- Serialization: JSON, Avro, String
- Embedded Kafka for tests
- Configuration: consumer group, auto.offset.reset

## Triggers

Kafka, Producer, Consumer, @KafkaListener, serialization, Embedded Kafka, consumer group

## Resources

- **SKILL.md** — full documentation
- **scripts/** — validate_config.py
- **references/** — configuration, serialization, testing
