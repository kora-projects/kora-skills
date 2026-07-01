#!/usr/bin/env python3
"""
Kora Project Generator — Kora Initializr

Generates a complete ready-to-compile Kora project with selected modules.
"""

import argparse
import os
import shutil
from pathlib import Path
from typing import List, Dict, Optional

# Module definitions with dependencies and templates.
# Artifact names verified against the Kora docs and example apps.
# "group" defaults to "ru.tinkoff.kora"; experimental modules override it.
MODULES = {
    # HTTP
    "http-server": {
        "artifact": "http-server-undertow",
        "package_example": "controller",
        "description": "HTTP Server (Undertow)",
    },
    "http-client": {
        "artifact": "http-client-ok",
        "package_example": "client",
        "description": "HTTP Client (OkHttp transport)",
    },

    # Database
    "jdbc-postgres": {
        "artifact": "database-jdbc",
        "extra_artifacts": ["database-flyway"],
        "driver": "org.postgresql:postgresql:42.7.7",
        "package_example": "repository",
        "description": "JDBC + PostgreSQL (Flyway migrations)",
    },
    "jdbc-mysql": {
        "artifact": "database-jdbc",
        "extra_artifacts": ["database-flyway"],
        "driver": "com.mysql:mysql-connector-j:8.3.0",
        "package_example": "repository",
        "description": "JDBC + MySQL (Flyway migrations)",
    },
    "cassandra": {
        "artifact": "database-cassandra",
        "package_example": "repository",
        "description": "Cassandra",
    },

    # Kafka (single artifact covers producer and consumer)
    "kafka": {
        "artifact": "kafka",
        "package_example": "kafka",
        "description": "Kafka producer + consumer",
    },

    # Telemetry
    "metrics": {
        "artifact": "micrometer-module",
        "package_example": None,
        "description": "Micrometer metrics (Prometheus on the private HTTP port)",
    },
    "tracing": {
        "artifact": "opentelemetry-tracing-exporter-grpc",
        "package_example": None,
        "description": "OpenTelemetry tracing (OTLP/gRPC exporter)",
    },

    # gRPC
    "grpc-server": {
        "artifact": "grpc-server",
        "package_example": "grpc",
        "description": "gRPC Server",
    },
    "grpc-client": {
        "artifact": "grpc-client",
        "package_example": None,
        "description": "gRPC Client",
    },

    # OpenAPI
    "openapi-server": {
        "artifact": "openapi-generator",
        "package_example": "api",
        "description": "OpenAPI Server (from spec)",
    },
    "openapi-client": {
        "artifact": "openapi-generator",
        "package_example": "client",
        "description": "OpenAPI Client (from spec)",
    },

    # AOP
    "resilient": {
        "artifact": "resilient-kora",
        "package_example": None,
        "description": "Resilience (@Retry, @CircuitBreaker, @Timeout, @Fallback)",
    },
    "caching": {
        "artifact": "cache-caffeine",
        "package_example": None,
        "description": "Caching (@Cacheable, @CachePut, @CacheInvalidate)",
    },
    "validation": {
        "artifact": "validation-module",
        "package_example": None,
        "description": "Validation (@Valid, @Validate)",
    },
    "scheduling": {
        "artifact": "scheduling-jdk",
        "package_example": "scheduler",
        "description": "Scheduling (@ScheduleAtFixedRate, @ScheduleWithCron)",
    },

    # Other (experimental group)
    "s3": {
        "group": "ru.tinkoff.kora.experimental",
        "artifact": "s3-client-aws",
        "package_example": "s3",
        "description": "S3 Client (AWS)",
    },
    "soap": {
        "artifact": "soap-client",
        "package_example": "soap",
        "description": "SOAP Client",
    },
}

# Core modules added to every generated project (config + JSON + logging).
CORE_MODULES = ["config-hocon", "json-module", "logging-logback"]


def parse_args():
    parser = argparse.ArgumentParser(
        description="Generate a Kora project with selected modules",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --name my-service --package com.example --lang java \\
           --modules http-server,http-client,json-module,jdbc-postgres,metrics

  %(prog)s --name kafka-service --package com.example --lang kotlin \\
           --modules kafka,metrics
        """
    )
    parser.add_argument("--name", help="Project name (required unless --list-modules)")
    parser.add_argument("--package", help="Base package, e.g. com.example (required unless --list-modules)")
    parser.add_argument("--lang", choices=["java", "kotlin"], default="java", help="Language")
    parser.add_argument("--output", default=".", help="Output directory")
    parser.add_argument("--kora-version", default="1.2.17", help="Kora version")
    parser.add_argument("--modules", "-m", help="Comma-separated modules")
    parser.add_argument("--list-modules", action="store_true", help="List available modules")
    parser.add_argument("--multi-module", action="store_true", help="Create multi-module project")
    return parser.parse_args()


def list_modules():
    print("\nAvailable modules:\n")
    categories = {
        "HTTP": ["http-server", "http-client"],
        "Database": ["jdbc-postgres", "jdbc-mysql", "cassandra"],
        "Kafka": ["kafka"],
        "Telemetry": ["metrics", "tracing"],
        "gRPC": ["grpc-server", "grpc-client"],
        "OpenAPI": ["openapi-server", "openapi-client"],
        "AOP": ["resilient", "caching", "validation", "scheduling"],
        "Other": ["s3", "soap"],
    }

    for category, mods in categories.items():
        print(f"{category}:")
        for mod in mods:
            print(f"  {mod:20} — {MODULES[mod]['description']}")
        print()


def get_package_path(package: str) -> str:
    return package.replace(".", "/")


def generate_build_gradle(name: str, package: str, lang: str, kora_version: str,
                          modules: List[str], multi_module: bool = False) -> str:
    """Generate build.gradle or build.gradle.kts content."""

    is_kotlin = lang == "kotlin"
    package_path = get_package_path(package)

    # Collect all artifacts (deduplicated)
    artifacts_set = set()
    runtime_deps = []

    for mod in modules:
        if mod in MODULES:
            module_info = MODULES[mod]
            group = module_info.get("group", "ru.tinkoff.kora")
            artifacts_set.add(f"{group}:{module_info['artifact']}")

            if "extra_artifacts" in module_info:
                for extra in module_info["extra_artifacts"]:
                    artifacts_set.add(f"{group}:{extra}")

            if "driver" in module_info:
                # JDBC driver is not in the BOM - use a normal implementation dependency
                runtime_deps.append(f'implementation "{module_info["driver"]}"' if not is_kotlin
                                   else f'implementation("{module_info["driver"]}")')

    artifacts = sorted(list(artifacts_set))

    # jakarta.annotation-api comes transitively with Kora BOM

    if is_kotlin:
        lines = [
            'plugins {',
            '    application',
            '    kotlin("jvm") version "1.9.25"',
            '    id("com.google.devtools.ksp") version "1.9.25-1.0.20"',
            '}',
            '',
            'val koraBom: Configuration by configurations.creating',
            'configurations {',
            '    ksp.get().extendsFrom(koraBom)',
            '    compileOnly.get().extendsFrom(koraBom)',
            '    implementation.get().extendsFrom(koraBom)',
            '}',
            '',
            'dependencies {',
            f'    koraBom(platform("ru.tinkoff.kora:kora-parent:{kora_version}"))',
            '    ksp("ru.tinkoff.kora:symbol-processors")',
            '',
            '    // Core modules',
            '    implementation("ru.tinkoff.kora:logging-logback")',
            '    implementation("ru.tinkoff.kora:config-hocon")',
            '    implementation("ru.tinkoff.kora:json-module")',
            '',
            '    // Selected modules',
        ]

        for artifact in artifacts:
            lines.append(f'    implementation("{artifact}")')

        if runtime_deps:
            lines.append('')
            lines.append('    // Runtime dependencies')
            lines.extend(f'    {dep}' for dep in runtime_deps)

        lines.extend([
            '}',
            '',
            'kotlin {',
            '    jvmToolchain {',
            '        languageVersion.set(JavaLanguageVersion.of(21))',
            '        vendor.set(JvmVendorSpec.ADOPTIUM)',
            '    }',
            '    sourceSets.main { kotlin.srcDir("build/generated/ksp/main/kotlin") }',
            '    sourceSets.test { kotlin.srcDir("build/generated/ksp/test/kotlin") }',
            '}',
            '',
            'application {',
            f'    mainClass.set("{package}.ApplicationKt")',
            '}',
        ])

        return '\n'.join(lines)

    else:  # Java
        lines = [
            'plugins {',
            '    id "java"',
            '    id "application"',
            '}',
            '',
            'java {',
            '    toolchain {',
            '        languageVersion = JavaLanguageVersion.of(21)',
            '        vendor = JvmVendorSpec.ADOPTIUM',
            '    }',
            '}',
            '',
            'configurations {',
            '    koraBom',
            '    annotationProcessor.extendsFrom(koraBom)',
            '    compileOnly.extendsFrom(koraBom)',
            '    implementation.extendsFrom(koraBom)',
            '}',
            '',
            'dependencies {',
            f'    koraBom platform("ru.tinkoff.kora:kora-parent:{kora_version}")',
            '    annotationProcessor "ru.tinkoff.kora:annotation-processors"',
            '',
            '    // Core modules',
            '    implementation "ru.tinkoff.kora:logging-logback"',
            '    implementation "ru.tinkoff.kora:config-hocon"',
            '    implementation "ru.tinkoff.kora:json-module"',
            '',
            '    // Selected modules',
        ]

        for artifact in artifacts:
            lines.append(f'    implementation "{artifact}"')

        if runtime_deps:
            lines.append('')
            lines.append('    // Runtime dependencies')
            lines.extend(f'    {dep}' for dep in runtime_deps)

        lines.extend([
            '}',
            '',
            'compileJava {',
            '    options.encoding = "UTF-8"',
            '    options.incremental = true',
            '    options.fork = false',
            '}',
            '',
            'application {',
            f'    mainClass = "{package}.Application"',
            '}',
        ])

        return '\n'.join(lines)


def generate_settings_gradle(name: str, lang: str, multi_module: bool = False) -> str:
    """Generate settings.gradle content."""
    if lang == "kotlin":
        return f'rootProject.name = "{name}"'
    else:
        return f"rootProject.name = '{name}'"


def generate_gradle_properties(kora_version: str = "1.2.17") -> str:
    """Generate gradle.properties content."""
    return f"""# Kora Framework
koraVersion={kora_version}

# Kotlin (if using Kotlin)
kotlinVersion=1.9.25
kspVersion=1.9.25-1.0.20

# JVM
org.gradle.jvmargs=-Xmx2g -Dfile.encoding=UTF-8

# Gradle
org.gradle.parallel=true
org.gradle.caching=true
"""


# Maps a module key to the Kora *Module interface it contributes to @KoraApp,
# as (fully qualified import, simple name). Modules without an app interface
# (codegen-only or driven purely by annotations) are omitted.
MODULE_INTERFACES = {
    "http-server":   ("ru.tinkoff.kora.http.server.undertow.UndertowHttpServerModule", "UndertowHttpServerModule"),
    "http-client":   ("ru.tinkoff.kora.http.client.ok.OkHttpClientModule", "OkHttpClientModule"),
    "jdbc-postgres": ("ru.tinkoff.kora.database.jdbc.JdbcDatabaseModule", "JdbcDatabaseModule"),
    "jdbc-mysql":    ("ru.tinkoff.kora.database.jdbc.JdbcDatabaseModule", "JdbcDatabaseModule"),
    "cassandra":     ("ru.tinkoff.kora.database.cassandra.CassandraDatabaseModule", "CassandraDatabaseModule"),
    "kafka":         ("ru.tinkoff.kora.kafka.common.KafkaModule", "KafkaModule"),
    "metrics":       ("ru.tinkoff.kora.micrometer.module.MetricsModule", "MetricsModule"),
    "grpc-server":   ("ru.tinkoff.kora.grpc.server.GrpcServerModule", "GrpcServerModule"),
    "grpc-client":   ("ru.tinkoff.kora.grpc.client.GrpcClientModule", "GrpcClientModule"),
    "validation":    ("ru.tinkoff.kora.validation.module.ValidationModule", "ValidationModule"),
    "soap":          ("ru.tinkoff.kora.soap.client.SoapClientModule", "SoapClientModule"),
}

# Always-on core modules (config + JSON + logging).
CORE_MODULE_INTERFACES = [
    ("ru.tinkoff.kora.config.hocon.HoconConfigModule", "HoconConfigModule"),
    ("ru.tinkoff.kora.json.module.JsonModule", "JsonModule"),
    ("ru.tinkoff.kora.logging.logback.LogbackModule", "LogbackModule"),
]


def _collect_app_modules(modules: List[str]):
    """Return (imports, simple_names) for the @KoraApp interface, deduplicated and ordered."""
    seen = set()
    pairs = []
    for fq, name in CORE_MODULE_INTERFACES:
        if name not in seen:
            seen.add(name)
            pairs.append((fq, name))
    for mod in modules:
        pair = MODULE_INTERFACES.get(mod)
        if pair and pair[1] not in seen:
            seen.add(pair[1])
            pairs.append(pair)
    imports = [fq for fq, _ in pairs]
    names = [name for _, name in pairs]
    return imports, names


def generate_application_java(package: str, modules: List[str]) -> str:
    """Generate Application.java: a @KoraApp interface extending the selected modules."""
    imports, names = _collect_app_modules(modules)
    import_block = "\n".join(f"import {fq};" for fq in imports)
    extends_block = ",\n        ".join(names)
    return f"""package {package};

import ru.tinkoff.kora.application.graph.KoraApplication;
import ru.tinkoff.kora.common.KoraApp;
{import_block}

@KoraApp
public interface Application extends
        {extends_block} {{

    static void main(String[] args) {{
        KoraApplication.run(ApplicationGraph::graph);
    }}
}}
"""


def generate_application_kt(package: str, modules: List[str]) -> str:
    """Generate Application.kt: a @KoraApp interface extending the selected modules."""
    imports, names = _collect_app_modules(modules)
    import_block = "\n".join(f"import {fq}" for fq in imports)
    extends_block = ",\n    ".join(names)
    return f"""package {package}

import ru.tinkoff.kora.application.graph.KoraApplication
import ru.tinkoff.kora.common.KoraApp
{import_block}

@KoraApp
interface Application : {extends_block}

fun main() {{
    KoraApplication.run {{ ApplicationGraph.graph() }}
}}
"""


def generate_application_conf(name: str, modules: List[str]) -> str:
    """Generate application.conf (HOCON) with config sections for the selected modules.

    HOCON default pattern: declare a literal default, then allow an env override on
    the next line (the optional ${?ENV} replaces the value only when the variable is set).
    """
    lines = [
        f"# Kora application config: {name}",
        "",
        "# Logging levels per logger",
        "logging {",
        "  levels {",
        '    "root" = "WARN"',
        '    "ru.tinkoff.kora" = "INFO"',
        "  }",
        "}",
    ]

    if "http-server" in modules:
        # The private port serves metrics, probes, and the OpenAPI/system endpoints.
        lines.extend([
            "",
            "# HTTP server: public traffic and a private port for metrics/probes",
            "httpServer {",
            "  publicApiHttpPort = 8080",
            "  privateApiHttpPort = 8085",
            "}",
        ])

    if "http-client" in modules:
        lines.extend([
            "",
            "# HTTP client defaults",
            "httpClient {",
            '  connectTimeout = "5s"',
            '  readTimeout = "30s"',
            "}",
        ])

    if "jdbc-postgres" in modules:
        lines.extend([
            "",
            "# PostgreSQL via JDBC + HikariCP",
            "db {",
            '  jdbcUrl = "jdbc:postgresql://localhost:5432/' + name + '"',
            "  jdbcUrl = ${?DB_URL}",
            '  username = "postgres"',
            "  username = ${?DB_USER}",
            '  password = "postgres"',
            "  password = ${?DB_PASS}",
            "  maxPoolSize = 10",
            "}",
        ])

    if "jdbc-mysql" in modules:
        lines.extend([
            "",
            "# MySQL via JDBC + HikariCP",
            "db {",
            '  jdbcUrl = "jdbc:mysql://localhost:3306/' + name + '"',
            "  jdbcUrl = ${?DB_URL}",
            '  username = "root"',
            "  username = ${?DB_USER}",
            '  password = "root"',
            "  password = ${?DB_PASS}",
            "  maxPoolSize = 10",
            "}",
        ])

    if "cassandra" in modules:
        lines.extend([
            "",
            "# Cassandra",
            "cassandra {",
            "  basic {",
            '    contactPoints = "127.0.0.1:9042"',
            "    contactPoints = ${?CASSANDRA_CONTACT_POINTS}",
            '    dc = "datacenter1"',
            '    sessionKeyspace = "' + name + '"',
            "  }",
            "}",
        ])

    if "kafka" in modules:
        # A consumer reads a config path (e.g. "kafka.someConsumer") via @KafkaListener;
        # a publisher reads its driverProperties via @KafkaPublisher(value="kafka.somePublisher").
        lines.extend([
            "",
            "# Kafka consumer and publisher config paths",
            "kafka {",
            "  someConsumer {",
            '    topics = ["users"]',
            "    driverProperties {",
            '      "bootstrap.servers" = "localhost:9092"',
            '      "bootstrap.servers" = ${?KAFKA_BOOTSTRAP_SERVERS}',
            '      "group.id" = "' + name + '"',
            "    }",
            "  }",
            "  somePublisher {",
            "    driverProperties {",
            '      "bootstrap.servers" = "localhost:9092"',
            '      "bootstrap.servers" = ${?KAFKA_BOOTSTRAP_SERVERS}',
            "    }",
            "  }",
            "}",
        ])

    if "metrics" in modules:
        # Micrometer/Prometheus scrape is exposed on the private HTTP port.
        lines.extend([
            "",
            "# Metrics (scraped on the private HTTP port)",
            "metrics {",
            '  opentelemetrySpec = "V120"',
            "}",
        ])

    if "tracing" in modules:
        lines.extend([
            "",
            "# OpenTelemetry tracing exporter",
            "tracing {",
            "  exporter {",
            '    endpoint = "http://localhost:4317"',
            "    endpoint = ${?OTEL_EXPORTER_ENDPOINT}",
            "  }",
            "}",
        ])

    return '\n'.join(lines)


def generate_example_controller(package: str, package_path: str, lang: str) -> Dict[str, str]:
    """Generate a UserController using @HttpController + @HttpRoute (real Kora HTTP API)."""
    files = {}

    if lang == "kotlin":
        files[f"src/main/kotlin/{package_path}/controller/UserController.kt"] = f"""package {package}.controller

import ru.tinkoff.kora.common.Component
import ru.tinkoff.kora.http.common.HttpMethod
import ru.tinkoff.kora.http.common.annotation.HttpRoute
import ru.tinkoff.kora.http.common.annotation.Path
import ru.tinkoff.kora.http.server.common.annotation.HttpController
import ru.tinkoff.kora.json.common.annotation.Json
import {package}.repository.UserEntity
import {package}.repository.UserRepository

@Component
@HttpController
class UserController(
    private val userRepository: UserRepository
) {{

    @Json
    @HttpRoute(method = HttpMethod.GET, path = "/users")
    fun getAll(): List<UserEntity> = userRepository.findAll()

    @Json
    @HttpRoute(method = HttpMethod.GET, path = "/users/{{id}}")
    fun getById(@Path id: Long): UserEntity? = userRepository.findById(id)

    @HttpRoute(method = HttpMethod.POST, path = "/users")
    fun create(@Json user: UserEntity): Long = userRepository.insert(user)
}}
"""
    else:
        files[f"src/main/java/{package_path}/controller/UserController.java"] = f"""package {package}.controller;

import jakarta.annotation.Nullable;
import java.util.List;
import ru.tinkoff.kora.common.Component;
import ru.tinkoff.kora.http.common.HttpMethod;
import ru.tinkoff.kora.http.common.annotation.HttpRoute;
import ru.tinkoff.kora.http.common.annotation.Path;
import ru.tinkoff.kora.http.server.common.annotation.HttpController;
import ru.tinkoff.kora.json.common.annotation.Json;
import {package}.repository.UserEntity;
import {package}.repository.UserRepository;

@Component
@HttpController
public final class UserController {{

    private final UserRepository userRepository;

    public UserController(UserRepository userRepository) {{
        this.userRepository = userRepository;
    }}

    @Json
    @HttpRoute(method = HttpMethod.GET, path = "/users")
    public List<UserEntity> getAll() {{
        return userRepository.findAll();
    }}

    @Json
    @HttpRoute(method = HttpMethod.GET, path = "/users/{{id}}")
    @Nullable
    public UserEntity getById(@Path long id) {{
        return userRepository.findById(id);
    }}

    @HttpRoute(method = HttpMethod.POST, path = "/users")
    public long create(@Json UserEntity user) {{
        return userRepository.insert(user);
    }}
}}
"""

    return files


def generate_example_repository(package: str, package_path: str, lang: str, db_type: str) -> Dict[str, str]:
    """Generate a UserRepository using the real Kora @Repository + @Query API.

    JDBC -> @Repository extends JdbcRepository, entity is @EntityJdbc.
    Cassandra -> @Repository extends CassandraRepository, entity is @EntityCassandra.
    """
    files = {}
    is_cassandra = db_type == "cassandra"
    repo_iface = "CassandraRepository" if is_cassandra else "JdbcRepository"
    repo_import = (
        "ru.tinkoff.kora.database.cassandra.CassandraRepository" if is_cassandra
        else "ru.tinkoff.kora.database.jdbc.JdbcRepository"
    )
    entity_anno = "EntityCassandra" if is_cassandra else "EntityJdbc"
    entity_import = (
        "ru.tinkoff.kora.database.cassandra.annotation.EntityCassandra" if is_cassandra
        else "ru.tinkoff.kora.database.jdbc.EntityJdbc"
    )

    if lang == "kotlin":
        files[f"src/main/kotlin/{package_path}/repository/UserEntity.kt"] = f"""package {package}.repository

import jakarta.annotation.Nullable
import ru.tinkoff.kora.database.common.annotation.Column
import ru.tinkoff.kora.database.common.annotation.Id
import {entity_import}

@{entity_anno}
data class UserEntity(
    @Id @Column("id") val id: Long?,
    @Column("name") val name: String,
    @Column("email") val email: String
)
"""
        files[f"src/main/kotlin/{package_path}/repository/UserRepository.kt"] = f"""package {package}.repository

import jakarta.annotation.Nullable
import ru.tinkoff.kora.database.common.annotation.Query
import ru.tinkoff.kora.database.common.annotation.Repository
import {repo_import}

@Repository
interface UserRepository : {repo_iface} {{

    @Query("SELECT id, name, email FROM users")
    fun findAll(): List<UserEntity>

    @Nullable
    @Query("SELECT id, name, email FROM users WHERE id = :id")
    fun findById(id: Long): UserEntity?

    @Query("INSERT INTO users(name, email) VALUES (:user.name, :user.email) RETURNING id")
    fun insert(user: UserEntity): Long
}}
"""
    else:
        files[f"src/main/java/{package_path}/repository/UserEntity.java"] = f"""package {package}.repository;

import ru.tinkoff.kora.database.common.annotation.Column;
import ru.tinkoff.kora.database.common.annotation.Id;
import {entity_import};

@{entity_anno}
public record UserEntity(
    @Id @Column("id") Long id,
    @Column("name") String name,
    @Column("email") String email
) {{}}
"""
        files[f"src/main/java/{package_path}/repository/UserRepository.java"] = f"""package {package}.repository;

import jakarta.annotation.Nullable;
import java.util.List;
import ru.tinkoff.kora.database.common.annotation.Query;
import ru.tinkoff.kora.database.common.annotation.Repository;
import {repo_import};

@Repository
public interface UserRepository extends {repo_iface} {{

    @Query("SELECT id, name, email FROM users")
    List<UserEntity> findAll();

    @Nullable
    @Query("SELECT id, name, email FROM users WHERE id = :id")
    UserEntity findById(long id);

    @Query("INSERT INTO users(name, email) VALUES (:user.name, :user.email) RETURNING id")
    long insert(UserEntity user);
}}
"""

    return files


def generate_initial_migration_sql(db_type: str) -> str:
    """Generate initial SQL migration for users table."""
    if db_type == "jdbc-mysql":
        return """-- V1__initial_schema.sql
-- Initial schema - users table

CREATE TABLE IF NOT EXISTS users (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    email VARCHAR(255) NOT NULL UNIQUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Index for findByName query
CREATE INDEX idx_users_name ON users(name);

-- rollback DROP TABLE users;
"""
    elif db_type == "cassandra":
        return """-- V1__initial_schema.sql
-- Initial schema - users table

CREATE KEYSPACE IF NOT EXISTS kora
WITH replication = {'class': 'SimpleStrategy', 'replication_factor': 1};

USE kora;

CREATE TABLE IF NOT EXISTS users (
    id BIGINT PRIMARY KEY,
    name TEXT,
    email TEXT,
    created_at TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
CREATE INDEX IF NOT EXISTS idx_users_name ON users(name);

-- rollback DROP TABLE users; DROP KEYSPACE kora;
"""
    else:  # postgres (default)
        return """-- V1__initial_schema.sql
-- Initial schema - users table

CREATE TABLE IF NOT EXISTS users (
    id BIGSERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    email VARCHAR(255) NOT NULL UNIQUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Index for findByName query
CREATE INDEX IF NOT EXISTS idx_users_name ON users(name);

-- rollback DROP INDEX idx_users_name; DROP TABLE users;
"""


def generate_example_kafka(package: str, package_path: str, lang: str, has_producer: bool, has_consumer: bool) -> Dict[str, str]:
    """Generate a Kafka @KafkaPublisher interface and a @KafkaListener component.

    Each annotation references a config path that matches the generated application.conf
    ("kafka.somePublisher" / "kafka.someConsumer").
    """
    files = {}

    # The event DTO is defined inline so the Kafka sample compiles without a DB module.
    if has_producer:
        if lang == "kotlin":
            files[f"src/main/kotlin/{package_path}/kafka/UserPublisher.kt"] = f"""package {package}.kafka

import ru.tinkoff.kora.json.common.annotation.Json
import ru.tinkoff.kora.kafka.common.annotation.KafkaPublisher
import ru.tinkoff.kora.kafka.common.annotation.KafkaPublisher.Topic

@Json
data class UserEvent(val id: Long, val email: String)

@KafkaPublisher("kafka.somePublisher")
interface UserPublisher {{

    @Topic("kafka.somePublisher.users")
    fun send(@Json event: UserEvent)
}}
"""
        else:
            files[f"src/main/java/{package_path}/kafka/UserEvent.java"] = f"""package {package}.kafka;

import ru.tinkoff.kora.json.common.annotation.Json;

@Json
public record UserEvent(long id, String email) {{}}
"""
            files[f"src/main/java/{package_path}/kafka/UserPublisher.java"] = f"""package {package}.kafka;

import ru.tinkoff.kora.json.common.annotation.Json;
import ru.tinkoff.kora.kafka.common.annotation.KafkaPublisher;

@KafkaPublisher("kafka.somePublisher")
public interface UserPublisher {{

    @KafkaPublisher.Topic("kafka.somePublisher.users")
    void send(@Json UserEvent event);
}}
"""

    if has_consumer:
        if lang == "kotlin":
            # If no producer was generated, define the DTO here instead.
            dto_decl = "" if has_producer else "\n@Json\ndata class UserEvent(val id: Long, val email: String)\n"
            files[f"src/main/kotlin/{package_path}/kafka/UserListener.kt"] = f"""package {package}.kafka

import ru.tinkoff.kora.common.Component
import ru.tinkoff.kora.json.common.annotation.Json
import ru.tinkoff.kora.kafka.common.annotation.KafkaListener
{dto_decl}
@Component
class UserListener {{

    @KafkaListener("kafka.someConsumer")
    fun process(@Json event: UserEvent) {{
        // Handle the incoming user event
    }}
}}
"""
        else:
            files[f"src/main/java/{package_path}/kafka/UserListener.java"] = f"""package {package}.kafka;

import ru.tinkoff.kora.common.Component;
import ru.tinkoff.kora.json.common.annotation.Json;
import ru.tinkoff.kora.kafka.common.annotation.KafkaListener;

@Component
public final class UserListener {{

    @KafkaListener("kafka.someConsumer")
    public void process(@Json UserEvent event) {{
        // Handle the incoming user event
    }}
}}
"""
            if not has_producer:
                files[f"src/main/java/{package_path}/kafka/UserEvent.java"] = f"""package {package}.kafka;

import ru.tinkoff.kora.json.common.annotation.Json;

@Json
public record UserEvent(long id, String email) {{}}
"""

    return files


def generate_gitignore() -> str:
    """Generate .gitignore for Gradle project."""
    return """# Compiled class files
*.class

# Log files
*.log

# Package files
*.jar
*.war
*.nar
*.ear
*.zip
*.tar.gz
*.rar

# Gradle
.gradle/
build/
!gradle/wrapper/gradle-wrapper.jar

# IDE
.idea/
*.iml
*.iws
*.ipr
.vscode/
.settings/
.project
.classpath

# Kora generated
build/generated/

# OS
.DS_Store
Thumbs.db

# Config with secrets
application-local.conf
application-local.yaml
.env
"""


def generate_dockerfile(name: str, lang: str) -> str:
    """Generate Dockerfile for the service."""
    return f"""# Build stage
FROM gradle:9.0-jdk21 AS builder

WORKDIR /home/gradle/project

COPY --chown=gradle:gradle . .
RUN gradle build --no-daemon

# Runtime stage
FROM eclipse-temurin:21-jre-alpine

WORKDIR /app

COPY --from=builder /home/gradle/project/build/libs/*.jar app.jar

# 8080 public traffic, 8085 private (metrics/probes)
EXPOSE 8080 8085

ENTRYPOINT ["java", "-jar", "app.jar"]
"""


def create_directory_structure(output_dir: Path, package: str, lang: str, multi_module: bool = False):
    """Create project directory structure."""
    package_path = get_package_path(package)

    if multi_module:
        # Multi-module structure
        modules = ["common", "app"]
        for mod in modules:
            (output_dir / mod / "src" / "main" / "java" / package_path).mkdir(parents=True, exist_ok=True)
            if mod == "app":
                (output_dir / mod / "src" / "test" / "java" / package_path).mkdir(parents=True, exist_ok=True)
    else:
        # Single module
        (output_dir / "src" / "main" / "java" / package_path).mkdir(parents=True, exist_ok=True)
        (output_dir / "src" / "test" / "java" / package_path).mkdir(parents=True, exist_ok=True)

        if lang == "kotlin":
            # Also create kotlin directories
            (output_dir / "src" / "main" / "kotlin" / package_path).mkdir(parents=True, exist_ok=True)


def generate_project(args):
    """Main project generation function."""
    output_dir = Path(args.output) / args.name
    package_path = get_package_path(args.package)

    print(f"\n🚀 Generating Kora project: {args.name}")
    print(f"   Package: {args.package}")
    print(f"   Language: {args.lang}")
    print(f"   Kora version: {args.kora_version}")

    # Parse modules
    selected_modules = []
    if args.modules:
        selected_modules = [m.strip() for m in args.modules.split(',')]

    print(f"   Modules: {', '.join(selected_modules) if selected_modules else 'core only'}")

    # Create directory structure
    print("\n📁 Creating directory structure...")
    create_directory_structure(output_dir, args.package, args.lang, args.multi_module)

    # Generate build files
    print("📝 Generating build files...")
    build_file = "build.gradle.kts" if args.lang == "kotlin" else "build.gradle"
    settings_file = "settings.gradle.kts" if args.lang == "kotlin" else "settings.gradle"

    (output_dir / build_file).write_text(
        generate_build_gradle(args.name, args.package, args.lang, args.kora_version, selected_modules, args.multi_module)
    )

    (output_dir / settings_file).write_text(
        generate_settings_gradle(args.name, args.lang, args.multi_module)
    )

    (output_dir / "gradle.properties").write_text(generate_gradle_properties(args.kora_version))

    # Copy Gradle wrapper
    assets_dir = Path(__file__).parent.parent / "assets"
    gradle_wrapper_src = assets_dir / "gradle-wrapper"
    gradle_wrapper_dst = output_dir / "gradle" / "wrapper"
    if gradle_wrapper_src.exists():
        shutil.copytree(gradle_wrapper_src, gradle_wrapper_dst, dirs_exist_ok=True)

    # Copy gradlew scripts
    gradlew_src = assets_dir / "gradlew"
    gradlew_dst = output_dir / "gradlew"
    if gradlew_src.exists():
        shutil.copy2(gradlew_src, gradlew_dst)
        gradlew_dst.chmod(0o755)

    gradlew_bat_src = assets_dir / "gradlew.bat"
    gradlew_bat_dst = output_dir / "gradlew.bat"
    if gradlew_bat_src.exists():
        shutil.copy2(gradlew_bat_src, gradlew_bat_dst)

    # Generate Application class
    print("🏗️  Generating Application class...")
    if args.lang == "kotlin":
        app_content = generate_application_kt(args.package, selected_modules)
        app_path = output_dir / "src" / "main" / "kotlin" / package_path / "Application.kt"
    else:
        app_content = generate_application_java(args.package, selected_modules)
        app_path = output_dir / "src" / "main" / "java" / package_path / "Application.java"

    app_path.parent.mkdir(parents=True, exist_ok=True)
    app_path.write_text(app_content)

    # Generate application.conf
    print("⚙️  Generating application.conf...")
    (output_dir / "src" / "main" / "resources").mkdir(parents=True, exist_ok=True)
    (output_dir / "src" / "main" / "resources" / "application.conf").write_text(
        generate_application_conf(args.name, selected_modules)
    )

    # Generate example files based on modules
    print("📦 Generating example files...")
    example_files = {}

    # HTTP Controller
    if "http-server" in selected_modules:
        example_files.update(generate_example_controller(args.package, package_path, args.lang))

    # Database Repository + Migration SQL
    db_modules = ["jdbc-postgres", "jdbc-mysql", "cassandra"]
    db_type = next((m for m in selected_modules if m in db_modules), None)
    if db_type:
        example_files.update(generate_example_repository(args.package, package_path, args.lang, db_type))

        # Generate initial migration SQL
        (output_dir / "src" / "main" / "resources" / "migrations").mkdir(parents=True, exist_ok=True)
        migration_sql = generate_initial_migration_sql(db_type)
        (output_dir / "src" / "main" / "resources" / "migrations" / "V1__initial_schema.sql").write_text(migration_sql)

    # Kafka producer + consumer (single "kafka" module)
    if "kafka" in selected_modules:
        example_files.update(generate_example_kafka(
            args.package, package_path, args.lang, has_producer=True, has_consumer=True
        ))

    # Write example files
    for path, content in example_files.items():
        file_path = output_dir / path
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content)

    # Generate .gitignore
    (output_dir / ".gitignore").write_text(generate_gitignore())

    # Generate Dockerfile
    (output_dir / "Dockerfile").write_text(generate_dockerfile(args.name, args.lang))

    # Generate README
    readme = f"""# {args.name}

Generated Kora Framework project.

## Build

```bash
./gradlew clean build
```

## Run

```bash
./gradlew run
```

## Configuration

Edit `src/main/resources/application.conf` for application configuration.

Environment variable overrides:
- `DB_URL`, `DB_USER`, `DB_PASS` - Database connection
- `KAFKA_BOOTSTRAP_SERVERS` - Kafka brokers
- `OTEL_EXPORTER_ENDPOINT` - OpenTelemetry endpoint

## Modules

{'- ' + chr(10).join('- ' + m for m in selected_modules) if selected_modules else '- Core modules only'}

## Docker

```bash
docker build -t {args.name} .
docker run -p 8080:8080 {args.name}
```
"""
    (output_dir / "README.md").write_text(readme)

    print(f"\n✅ Project generated successfully!")
    print(f"\n📂 Location: {output_dir.absolute()}")
    print("\n👉 Next steps:")
    print(f"   cd {args.name}")
    print("   ./gradlew clean build  # Build the project")
    print("   # Edit src/main/resources/application.conf for configuration")
    if "http-server" in selected_modules:
        print("   # HTTP server: public port 8080, private port 8085 (metrics/probes)")
        print("   curl http://localhost:8080/users  # Sample endpoint")


def main():
    args = parse_args()

    if args.list_modules:
        list_modules()
        return

    missing = [flag for flag, value in (("--name", args.name), ("--package", args.package)) if not value]
    if missing:
        print("error: the following arguments are required: " + ", ".join(missing))
        raise SystemExit(2)

    generate_project(args)


if __name__ == "__main__":
    main()
