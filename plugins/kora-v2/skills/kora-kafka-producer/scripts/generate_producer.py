#!/usr/bin/env python3
"""Scaffold a Kora 2.0 Kafka publisher (io.koraframework).

Generates, for one @KafkaPublisher interface:
  * the publisher interface (Java or Kotlin),
  * a HOCON snippet with the producer section and one topic section per topic,
  * optionally a @KoraAppTest + Testcontainers 2.0.5 integration test.

Every generated method carries @Topic, so the interface never mixes @Topic and
ProducerRecord shapes -- that mix makes the generated $X_TopicConfig record and the
$X_PublisherModule factory disagree on arity and the build fails inside generated code.

Output is deterministic: running the same command twice writes byte-identical files.
Existing files are left alone unless --force is given.

Usage:
    python3 generate_producer.py --name OrderPublisher --topics order-created order-shipped
    python3 generate_producer.py --name OrderPublisher --topics orders --lang kotlin --with-tests
    python3 generate_producer.py --name OrderPublisher --topics orders --dry-run
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

KORA_VERSION = "2.0.0.RC2"
TESTCONTAINERS_VERSION = "2.0.5"
KAFKA_IMAGE = "apache/kafka-native:4.3.1"


def lower_camel(name: str) -> str:
    return name[:1].lower() + name[1:] if name else name


def upper_camel(raw: str) -> str:
    parts = [p for p in raw.replace(".", "-").replace("_", "-").split("-") if p]
    return "".join(p[:1].upper() + p[1:] for p in parts)


def config_key(raw: str) -> str:
    """Topic name -> lowerCamel config key, e.g. order-created -> orderCreated."""
    return lower_camel(upper_camel(raw))


def java_publisher(package: str, interface: str, publisher_key: str, topics: list[str]) -> str:
    methods = []
    for topic in topics:
        suffix = upper_camel(topic)
        key = config_key(topic)
        methods.append(f"""
    @Topic(".{key}")
    void send{suffix}(String value);

    @Topic(".{key}")
    void send{suffix}(String key, String value);

    @Topic(".{key}")
    RecordMetadata send{suffix}WithMeta(String value);

    @Topic(".{key}")
    Future<RecordMetadata> send{suffix}Async(String value);
""")
    return f"""package {package}.publisher;

import java.util.concurrent.Future;
import org.apache.kafka.clients.producer.RecordMetadata;
import io.koraframework.kafka.common.annotation.KafkaPublisher;
import io.koraframework.kafka.common.annotation.KafkaPublisher.Topic;

// Topics: {", ".join(topics)}
// void and RecordMetadata block until the broker acks and throw KafkaPublishException
// on failure; the Future form returns immediately and reports failures on the future.
@KafkaPublisher("kafka.producer.{publisher_key}")
public interface {interface} {{
{"".join(methods)}}}
"""


def kotlin_publisher(package: str, interface: str, publisher_key: str, topics: list[str]) -> str:
    methods = []
    for topic in topics:
        suffix = upper_camel(topic)
        key = config_key(topic)
        methods.append(f"""
    @Topic(".{key}")
    fun send{suffix}(value: String)

    @Topic(".{key}")
    fun send{suffix}(key: String, value: String)

    @Topic(".{key}")
    fun send{suffix}WithMeta(value: String): RecordMetadata

    @Topic(".{key}")
    fun send{suffix}Async(value: String): Future<RecordMetadata>
""")
    return f"""package {package}.publisher

import java.util.concurrent.Future
import org.apache.kafka.clients.producer.RecordMetadata
import io.koraframework.kafka.common.annotation.KafkaPublisher
import io.koraframework.kafka.common.annotation.KafkaPublisher.Topic

// Topics: {", ".join(topics)}
// Unit and RecordMetadata block until the broker acks and throw KafkaPublishException
// on failure; the Future form returns immediately and reports failures on the future.
// A suspend or Deferred return type also works, but needs
// implementation("org.jetbrains.kotlinx:kotlinx-coroutines-jdk8:1.10.2").
@KafkaPublisher("kafka.producer.{publisher_key}")
interface {interface} {{
{"".join(methods)}}}
"""


def hocon_snippet(publisher_key: str, topics: list[str]) -> str:
    topic_blocks = "".join(
        f"""      {config_key(topic)} {{
        topic = "{topic}"
      }}
"""
        for topic in topics
    )
    return f"""# Merge into application.conf.
# Env var default: HOCON writes it as a separate optional override, never as ${{VAR:default}}.
kafka {{
  producer {{
    {publisher_key} {{
      driverProperties {{
        "bootstrap.servers" = "localhost:9092"
        "bootstrap.servers" = ${{?KAFKA_BOOTSTRAP_SERVERS}}
        "acks" = "all"
        "enable.idempotence" = true
        "linger.ms" = 5
      }}

{topic_blocks}
      # Kora 2.0 defaults: logging.enabled = false, metrics.enabled = false,
      # tracing.enabled = true. Producer logs and meters stay silent until turned on.
      telemetry {{
        logging.enabled = true
        metrics.enabled = true
        tracing.enabled = true
      }}
    }}
  }}
}}
"""


def java_test(package: str, interface: str, topics: list[str]) -> str:
    topic = topics[0]
    suffix = upper_camel(topic)
    return f"""package {package}.publisher;

import static org.junit.jupiter.api.Assertions.*;

import java.time.Duration;
import java.util.List;
import java.util.Properties;
import org.apache.kafka.clients.consumer.ConsumerConfig;
import org.apache.kafka.clients.consumer.ConsumerRecord;
import org.apache.kafka.clients.consumer.KafkaConsumer;
import org.apache.kafka.common.serialization.StringDeserializer;
import org.junit.jupiter.api.Test;
import org.testcontainers.kafka.KafkaContainer;
import io.koraframework.test.extension.junit5.KoraAppTest;
import io.koraframework.test.extension.junit5.KoraAppTestConfigModifier;
import io.koraframework.test.extension.junit5.KoraConfigModification;
import io.koraframework.test.extension.junit5.TestComponent;
import {package}.Application;

// testImplementation "io.koraframework:test-junit5"
// testImplementation "org.testcontainers:testcontainers-kafka:{TESTCONTAINERS_VERSION}"
//
// Testcontainers 2.x renamed its modules: "org.testcontainers:kafka" no longer exists.
// The container starts from a static initializer so it is up before any JUnit extension
// callback -- the Kora extension builds the application graph in beforeAll.
//
// The publisher must be reachable from a @Root in MAIN sources, otherwise Kora prunes it
// and this test fails with "No matching component was found in the application graph".
@KoraAppTest(Application.class)
class {interface}Tests implements KoraAppTestConfigModifier {{

    private static final String TOPIC = "{topic}";

    static final KafkaContainer KAFKA = new KafkaContainer("{KAFKA_IMAGE}");

    static {{
        KAFKA.start();
    }}

    @TestComponent
    private {interface} publisher;

    @Override
    public KoraConfigModification config() {{
        return KoraConfigModification.ofSystemProperty("KAFKA_BOOTSTRAP_SERVERS", KAFKA.getBootstrapServers());
    }}

    @Test
    void send{suffix}() {{
        var value = "test-" + System.nanoTime();

        try (var consumer = consumer()) {{
            consumer.subscribe(List.of(TOPIC));
            consumer.poll(Duration.ofSeconds(1));

            publisher.send{suffix}(value);

            assertEquals(value, pollOne(consumer).value());
        }}
    }}

    @Test
    void send{suffix}WithMeta() {{
        var metadata = publisher.send{suffix}WithMeta("meta-" + System.nanoTime());

        assertEquals(TOPIC, metadata.topic());
        assertTrue(metadata.offset() >= 0);
    }}

    private KafkaConsumer<String, String> consumer() {{
        var props = new Properties();
        props.put(ConsumerConfig.BOOTSTRAP_SERVERS_CONFIG, KAFKA.getBootstrapServers());
        props.put(ConsumerConfig.GROUP_ID_CONFIG, "test-" + System.nanoTime());
        props.put(ConsumerConfig.KEY_DESERIALIZER_CLASS_CONFIG, StringDeserializer.class.getName());
        props.put(ConsumerConfig.VALUE_DESERIALIZER_CLASS_CONFIG, StringDeserializer.class.getName());
        props.put(ConsumerConfig.AUTO_OFFSET_RESET_CONFIG, "earliest");
        return new KafkaConsumer<>(props);
    }}

    private static ConsumerRecord<String, String> pollOne(KafkaConsumer<String, String> consumer) {{
        var deadline = System.nanoTime() + Duration.ofSeconds(30).toNanos();
        while (System.nanoTime() < deadline) {{
            var records = consumer.poll(Duration.ofSeconds(1));
            if (!records.isEmpty()) {{
                return records.iterator().next();
            }}
        }}
        return fail("No record arrived within 30s");
    }}
}}
"""


def kotlin_test(package: str, interface: str, topics: list[str]) -> str:
    topic = topics[0]
    suffix = upper_camel(topic)
    return f"""package {package}.publisher

import java.time.Duration
import java.util.Properties
import org.apache.kafka.clients.consumer.ConsumerConfig
import org.apache.kafka.clients.consumer.ConsumerRecord
import org.apache.kafka.clients.consumer.KafkaConsumer
import org.apache.kafka.common.serialization.StringDeserializer
import org.junit.jupiter.api.Assertions.assertEquals
import org.junit.jupiter.api.Assertions.assertTrue
import org.junit.jupiter.api.Assertions.fail
import org.junit.jupiter.api.Test
import org.testcontainers.kafka.KafkaContainer
import io.koraframework.test.extension.junit5.KoraAppTest
import io.koraframework.test.extension.junit5.KoraAppTestConfigModifier
import io.koraframework.test.extension.junit5.KoraConfigModification
import io.koraframework.test.extension.junit5.TestComponent
import {package}.Application

// testImplementation("io.koraframework:test-junit5")
// testImplementation("org.testcontainers:testcontainers-kafka:{TESTCONTAINERS_VERSION}")
//
// Testcontainers 2.x renamed its modules: "org.testcontainers:kafka" no longer exists.
// The container starts from a companion initializer so it is up before any JUnit extension
// callback -- the Kora extension builds the application graph in beforeAll.
//
// The publisher must be reachable from a @Root in MAIN sources, otherwise Kora prunes it
// and this test fails with "No matching component was found in the application graph".
@KoraAppTest(Application::class)
class {interface}Tests : KoraAppTestConfigModifier {{

    companion object {{
        private const val TOPIC = "{topic}"

        @JvmStatic
        val KAFKA = KafkaContainer("{KAFKA_IMAGE}").also {{ it.start() }}
    }}

    @TestComponent
    lateinit var publisher: {interface}

    override fun config(): KoraConfigModification =
        KoraConfigModification.ofSystemProperty("KAFKA_BOOTSTRAP_SERVERS", KAFKA.bootstrapServers)

    @Test
    fun `send{suffix}`() {{
        val value = "test-" + System.nanoTime()

        consumer().use {{ consumer ->
            consumer.subscribe(listOf(TOPIC))
            consumer.poll(Duration.ofSeconds(1))

            publisher.send{suffix}(value)

            assertEquals(value, pollOne(consumer).value())
        }}
    }}

    @Test
    fun `send{suffix} with meta`() {{
        val metadata = publisher.send{suffix}WithMeta("meta-" + System.nanoTime())

        assertEquals(TOPIC, metadata.topic())
        assertTrue(metadata.offset() >= 0)
    }}

    private fun consumer(): KafkaConsumer<String, String> {{
        val props = Properties().apply {{
            put(ConsumerConfig.BOOTSTRAP_SERVERS_CONFIG, KAFKA.bootstrapServers)
            put(ConsumerConfig.GROUP_ID_CONFIG, "test-" + System.nanoTime())
            put(ConsumerConfig.KEY_DESERIALIZER_CLASS_CONFIG, StringDeserializer::class.java.name)
            put(ConsumerConfig.VALUE_DESERIALIZER_CLASS_CONFIG, StringDeserializer::class.java.name)
            put(ConsumerConfig.AUTO_OFFSET_RESET_CONFIG, "earliest")
        }}
        return KafkaConsumer(props)
    }}

    private fun pollOne(consumer: KafkaConsumer<String, String>): ConsumerRecord<String, String> {{
        val deadline = System.nanoTime() + Duration.ofSeconds(30).toNanos()
        while (System.nanoTime() < deadline) {{
            val records = consumer.poll(Duration.ofSeconds(1))
            if (!records.isEmpty) {{
                return records.iterator().next()
            }}
        }}
        return fail("No record arrived within 30s")
    }}
}}
"""


def emit(path: Path, content: str, dry_run: bool, force: bool) -> None:
    label = str(path)
    if dry_run:
        print(f"[dry-run] would write {label} ({len(content.splitlines())} lines)")
        return
    if path.exists() and not force:
        if path.read_text(encoding="utf-8") == content:
            print(f"  unchanged {label}")
        else:
            print(f"  skipped   {label} (exists; pass --force to overwrite)")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    print(f"  wrote     {label}")


def generate(name: str, topics: list[str], package: str, lang: str, output_dir: str,
             with_tests: bool, dry_run: bool, force: bool) -> None:
    is_kotlin = lang == "kotlin"
    interface = name if name.endswith("Publisher") else f"{name}Publisher"
    publisher_key = lower_camel(interface)
    package_path = package.replace(".", "/")
    ext = "kt" if is_kotlin else "java"
    src_root = "kotlin" if is_kotlin else "java"

    main_dir = Path(output_dir) / src_root / package_path / "publisher"
    emit(main_dir / f"{interface}.{ext}",
         (kotlin_publisher if is_kotlin else java_publisher)(package, interface, publisher_key, topics),
         dry_run, force)
    emit(main_dir / f"{interface}.conf", hocon_snippet(publisher_key, topics), dry_run, force)

    if with_tests:
        test_dir = Path(output_dir).parent / "test" / src_root / package_path / "publisher"
        emit(test_dir / f"{interface}Tests.{ext}",
             (kotlin_test if is_kotlin else java_test)(package, interface, topics),
             dry_run, force)

    print()
    print(f"Publisher    {package}.publisher.{interface}")
    print(f"Config path  kafka.producer.{publisher_key}")
    print(f"Topics       {', '.join(f'{t} -> .{config_key(t)}' for t in topics)}")
    print(f"Kora         io.koraframework:kafka (BOM io.koraframework:kora-bom:{KORA_VERSION})")
    print()
    print("Next: merge the .conf snippet into application.conf, add KafkaModule to the @KoraApp,")
    print("and make sure something reachable from a @Root injects the publisher.")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate a Kora 2.0 Kafka publisher interface, its HOCON section and tests.")
    parser.add_argument("--name", required=True, help="Publisher name, e.g. OrderPublisher")
    parser.add_argument("--topics", required=True, nargs="+", help="Kafka topic names")
    parser.add_argument("--package", default="com.example", help="Base package (default: com.example)")
    parser.add_argument("--lang", choices=["java", "kotlin"], default="java", help="Source language")
    parser.add_argument("--output", default="src/main", help="Source root (default: src/main)")
    parser.add_argument("--with-tests", action="store_true", help="Also generate an integration test")
    parser.add_argument("--dry-run", action="store_true", help="Print what would be written, write nothing")
    parser.add_argument("--force", action="store_true", help="Overwrite existing files")
    args = parser.parse_args()

    try:
        generate(args.name, args.topics, args.package, args.lang, args.output,
                 args.with_tests, args.dry_run, args.force)
    except Exception as e:  # noqa: BLE001 - CLI boundary
        print(f"Error: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
