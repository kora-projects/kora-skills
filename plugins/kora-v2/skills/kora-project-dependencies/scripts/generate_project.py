#!/usr/bin/env python3
"""
Kora Project Generator - Kora Initializr (Kora 2.0)

Generates a ready-to-compile Kora 2.0 project for a chosen set of modules.

Everything it emits is 2.0-native: the io.koraframework group, the io.koraframework:kora-bom
platform, the Java koraBom/extendsFrom shape vs the Kotlin BOM-on-implementation shape, and the
2.0 config sections (httpServer.port, httpServer.system.port, jdbc { ... }).

Re-running with the same arguments reproduces byte-identical output; generated files are
overwritten in place. Use --dry-run to see the plan without touching the filesystem.
"""

import argparse
import shutil
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Coordinates and toolchain
# ---------------------------------------------------------------------------

GROUP = "io.koraframework"
GROUP_EXPERIMENTAL = "io.koraframework.experimental"

# 2.0.0.RC2 is published on Maven Central, so a generated
# project resolves from plain mavenCentral(). Override with --kora-version. A -SNAPSHOT version is
# the development line and additionally needs the Sonatype snapshot repository, which is why the
# generator adds that repository only when the requested version is a snapshot.
DEFAULT_KORA_VERSION = "2.0.0.RC2"

# Kora 2.0 artifacts are compiled at JVM 25, so 25 is the floor. The migration guides recommend
# the latest GA feature release - override with --jdk rather than editing this constant.
DEFAULT_JDK = 25

KOTLIN_VERSION = "2.4.20"
KSP_VERSION = "2.3.12"
OPENAPI_PLUGIN_VERSION = "7.25.0"
GRADLE_VERSION = "9.7.1"  # matches assets/gradle-wrapper/gradle-wrapper.properties

MYSQL_DRIVER = "com.mysql:mysql-connector-j:9.2.0"
# database-flyway ships flyway-core only; the dialect artifact is the application's job.
FLYWAY_POSTGRES_DIALECT = "org.flywaydb:flyway-database-postgresql:13.9.0"
FLYWAY_MYSQL_DIALECT = "org.flywaydb:flyway-mysql:13.9.0"

MOCKITO = "org.mockito:mockito-core:5.24.0"
MOCKK = "io.mockk:mockk:1.14.11"

# Module definitions. Every artifact below appears in the Kora 2.0 settings.gradle.
#   group             - defaults to GROUP; only the experimental tree overrides it
#   extra_artifacts   - additional Kora artifacts, as (group, artifact)
#   external          - non-Kora implementation dependencies the app must version itself
#   module_interface  - (fully qualified name, simple name) contributed to @KoraApp, or None
#   buildscript       - Kora artifacts that belong on the buildscript classpath, not implementation
MODULES: Dict[str, dict] = {
    # ---- HTTP -------------------------------------------------------------
    "http-server": {
        "category": "HTTP",
        "artifact": "http-server-undertow",
        "module_interface": (
            "io.koraframework.http.server.undertow.UndertowPublicHttpServerModule",
            "UndertowPublicHttpServerModule",
        ),
        "package_example": "controller",
        "description": "HTTP Server (Undertow); brings the system server for metrics/probes",
    },
    "http-client": {
        "category": "HTTP",
        "artifact": "http-client-ok",
        "module_interface": ("io.koraframework.http.client.ok.OkHttpClientModule", "OkHttpClientModule"),
        "package_example": "client",
        "description": "HTTP Client, OkHttp transport (also: http-client-jdk, http-client-apache)",
    },
    "http-client-jdk": {
        "category": "HTTP",
        "artifact": "http-client-jdk",
        "module_interface": ("io.koraframework.http.client.jdk.JdkHttpClientModule", "JdkHttpClientModule"),
        "package_example": None,
        "description": "HTTP Client, JDK HttpClient transport",
    },
    "http-client-apache": {
        "category": "HTTP",
        "artifact": "http-client-apache",
        "module_interface": (
            "io.koraframework.http.client.apache.ApacheHttpClientModule",
            "ApacheHttpClientModule",
        ),
        "package_example": None,
        "description": "HTTP Client, Apache HttpClient 5 transport",
    },

    # ---- Database ---------------------------------------------------------
    "jdbc-postgres": {
        "category": "Database",
        # database-jdbc-postgres brings database-jdbc and the org.postgresql driver as api.
        "artifact": "database-jdbc-postgres",
        "extra_artifacts": [(GROUP, "database-flyway")],
        "external": [FLYWAY_POSTGRES_DIALECT],
        "module_interface": (
            "io.koraframework.database.jdbc.postgres.PostgresJdbcDatabaseModule",
            "PostgresJdbcDatabaseModule",
        ),
        "extra_module_interfaces": [
            ("io.koraframework.database.flyway.FlywayJdbcDatabaseModule", "FlywayJdbcDatabaseModule")
        ],
        "package_example": "repository",
        "description": "JDBC + PostgreSQL mappers and driver (Flyway migrations, config section `jdbc`)",
    },
    "jdbc-mysql": {
        "category": "Database",
        "artifact": "database-jdbc",
        "extra_artifacts": [(GROUP, "database-flyway")],
        "external": [MYSQL_DRIVER, FLYWAY_MYSQL_DIALECT],
        "module_interface": ("io.koraframework.database.jdbc.JdbcDatabaseModule", "JdbcDatabaseModule"),
        "extra_module_interfaces": [
            ("io.koraframework.database.flyway.FlywayJdbcDatabaseModule", "FlywayJdbcDatabaseModule")
        ],
        "package_example": "repository",
        "description": "JDBC + MySQL (Flyway migrations, config section `jdbc`)",
    },
    "cassandra": {
        "category": "Database",
        "artifact": "database-cassandra",
        "module_interface": (
            "io.koraframework.database.cassandra.CassandraDatabaseModule",
            "CassandraDatabaseModule",
        ),
        "package_example": "repository",
        "description": "Cassandra (driver ships with the module)",
    },

    # ---- Messaging --------------------------------------------------------
    "kafka": {
        "category": "Messaging",
        "artifact": "kafka",
        "module_interface": ("io.koraframework.kafka.common.KafkaModule", "KafkaModule"),
        "package_example": "kafka",
        "description": "Kafka producer + consumer (one artifact covers both)",
    },

    # ---- Telemetry --------------------------------------------------------
    "metrics": {
        "category": "Telemetry",
        "artifact": "micrometer-module",
        "module_interface": ("io.koraframework.micrometer.module.MetricsModule", "MetricsModule"),
        "package_example": None,
        "description": "Micrometer metrics (scraped on the system server; OFF until enabled in config)",
    },
    "tracing": {
        "category": "Telemetry",
        "artifact": "opentelemetry-tracing-exporter-grpc",
        "module_interface": (
            "io.koraframework.opentelemetry.tracing.exporter.grpc.OpentelemetryGrpcExporterModule",
            "OpentelemetryGrpcExporterModule",
        ),
        "package_example": None,
        "description": "OpenTelemetry tracing (OTLP/gRPC exporter)",
    },
    "logging-json": {
        "category": "Telemetry",
        "artifact": "logging-logback-json",
        "module_interface": None,
        "package_example": None,
        "description": "JSON console logs (Logback encoder picked automatically; KORA_LOGGING_ENCODER overrides)",
    },

    # ---- gRPC -------------------------------------------------------------
    "grpc-server": {
        "category": "gRPC",
        "artifact": "grpc-server",
        "module_interface": ("io.koraframework.grpc.server.GrpcServerModule", "GrpcServerModule"),
        "package_example": None,
        "description": "gRPC Server (pin grpc test transports to 1.84.0)",
    },
    "grpc-client": {
        "category": "gRPC",
        "artifact": "grpc-client",
        "module_interface": ("io.koraframework.grpc.client.GrpcClientModule", "GrpcClientModule"),
        "package_example": None,
        "description": "gRPC Client (pin grpc test transports to 1.84.0)",
    },

    # ---- OpenAPI ----------------------------------------------------------
    "openapi-server": {
        "category": "OpenAPI",
        "artifact": None,
        "buildscript": [(GROUP, "openapi-generator")],
        "extra_artifacts": [(GROUP, "http-server-undertow"), (GROUP, "openapi-management")],
        "extra_module_interfaces": [
            (
                "io.koraframework.http.server.undertow.UndertowPublicHttpServerModule",
                "UndertowPublicHttpServerModule",
            ),
            ("io.koraframework.openapi.management.OpenApiManagementModule", "OpenApiManagementModule"),
        ],
        "package_example": None,
        "description": "OpenAPI server codegen from a spec (mode java-server / kotlin-server)",
    },
    "openapi-client": {
        "category": "OpenAPI",
        "artifact": None,
        "buildscript": [(GROUP, "openapi-generator")],
        "extra_artifacts": [(GROUP, "http-client-ok")],
        "extra_module_interfaces": [
            ("io.koraframework.http.client.ok.OkHttpClientModule", "OkHttpClientModule")
        ],
        "package_example": None,
        "description": "OpenAPI client codegen from a spec (mode java-client / kotlin-client)",
    },

    # ---- AOP --------------------------------------------------------------
    "resilient": {
        "category": "AOP",
        "artifact": "resilient-kora",
        "module_interface": ("io.koraframework.resilient.ResilientModule", "ResilientModule"),
        "package_example": None,
        "description": "Resilience: @CircuitBreakable, @Retryable, @Timeout, @RateLimited, @Fallback",
    },
    "resilient-redis": {
        "category": "AOP",
        "artifact": "resilient-kora-distributed-redis-lettuce",
        "extra_artifacts": [(GROUP, "resilient-kora")],
        "module_interface": ("io.koraframework.resilient.ResilientModule", "ResilientModule"),
        "extra_module_interfaces": [
            (
                "io.koraframework.resilient.distributed.LettuceDistributedResilientModule",
                "LettuceDistributedResilientModule",
            )
        ],
        "package_example": None,
        "description": "Resilience + Redis-backed distributed rate limiter / retry budget (Lettuce)",
    },
    "caching": {
        "category": "AOP",
        "artifact": "cache-caffeine",
        "module_interface": ("io.koraframework.cache.caffeine.CaffeineCacheModule", "CaffeineCacheModule"),
        "package_example": None,
        "description": "In-process cache: @Cacheable, @CachePut, @CacheInvalidate, @CacheInvalidateAll",
    },
    "caching-redis": {
        "category": "AOP",
        "artifact": "cache-redis-lettuce",
        "module_interface": (
            "io.koraframework.cache.redis.lettuce.LettuceRedisCacheModule",
            "LettuceRedisCacheModule",
        ),
        "package_example": None,
        "description": "Distributed cache over Lettuce/Redis (cache-redis-common alone has no client)",
    },
    "validation": {
        "category": "AOP",
        "artifact": "validation-module",
        "module_interface": ("io.koraframework.validation.module.ValidationModule", "ValidationModule"),
        "package_example": None,
        "description": "Validation: @Valid, @Validate (Kora constraints, not Jakarta)",
    },
    "scheduling": {
        "category": "AOP",
        "artifact": "scheduling-jdk",
        "module_interface": ("io.koraframework.scheduling.jdk.SchedulingJdkModule", "SchedulingJdkModule"),
        "package_example": "scheduler",
        "description": "In-process scheduling: @ScheduleJdkAtFixedRate, @ScheduleJdkWithFixedDelay, @ScheduleJdkOnce, @ScheduleJdkWithCron",
    },
    "scheduling-quartz": {
        "category": "AOP",
        "artifact": "scheduling-quartz",
        "module_interface": ("io.koraframework.scheduling.quartz.QuartzModule", "QuartzModule"),
        "package_example": None,
        "description": "Quartz scheduling: @ScheduleQuartzWithCron, @ScheduleQuartzWithTrigger",
    },
    "scheduling-db": {
        "category": "AOP",
        "artifact": "scheduling-db-scheduler",
        "module_interface": (
            "io.koraframework.scheduling.db.scheduler.DbSchedulerModule",
            "DbSchedulerModule",
        ),
        "package_example": None,
        "description": "Clustered DB scheduling on db-scheduler (needs jdbc-postgres or jdbc-mysql)",
    },

    # ---- Other ------------------------------------------------------------
    "s3-aws": {
        "category": "Other",
        "artifact": "s3-client-aws",  # group io.koraframework - NOT experimental
        "extra_artifacts": [(GROUP, "http-client-apache")],
        "module_interface": ("io.koraframework.s3.client.aws.AwsS3ClientModule", "AwsS3ClientModule"),
        "extra_module_interfaces": [
            (
                "io.koraframework.http.client.apache.ApacheHttpClientModule",
                "ApacheHttpClientModule",
            )
        ],
        "package_example": None,
        "description": "S3 over the AWS SDK (AwsS3ClientModule; no @S3 annotations)",
    },
    "s3-kora": {
        "category": "Other",
        "group": GROUP_EXPERIMENTAL,
        "artifact": "s3-client-kora",
        "extra_artifacts": [(GROUP, "http-client-apache")],
        "module_interface": ("io.koraframework.s3.client.kora.KoraS3ClientModule", "KoraS3ClientModule"),
        "extra_module_interfaces": [
            (
                "io.koraframework.http.client.apache.ApacheHttpClientModule",
                "ApacheHttpClientModule",
            )
        ],
        "package_example": None,
        "description": "Declarative @S3 client (experimental group; needs an HTTP client transport)",
    },
    "soap": {
        "category": "Other",
        "artifact": "soap-client",
        "extra_artifacts": [(GROUP, "http-client-apache")],
        "module_interface": ("io.koraframework.soap.client.common.SoapClientModule", "SoapClientModule"),
        "extra_module_interfaces": [
            (
                "io.koraframework.http.client.apache.ApacheHttpClientModule",
                "ApacheHttpClientModule",
            )
        ],
        "package_example": None,
        "description": "SOAP Client (needs an HTTP client transport)",
    },
}

# Core modules added to every generated project (config + JSON + logging).
CORE_ARTIFACTS = ["logging-logback", "config-hocon", "json-common"]

CORE_MODULE_INTERFACES: List[Tuple[str, str]] = [
    ("io.koraframework.config.hocon.HoconConfigModule", "HoconConfigModule"),
    ("io.koraframework.json.common.JsonModule", "JsonModule"),
    ("io.koraframework.logging.logback.LogbackModule", "LogbackModule"),
]

DB_MODULE_KEYS = ["jdbc-postgres", "jdbc-mysql", "cassandra"]


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args(argv: Optional[List[str]] = None):
    parser = argparse.ArgumentParser(
        description="Generate a Kora 2.0 project with selected modules",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --list-modules

  %(prog)s --name my-service --package com.example --lang java \\
           --modules http-server,jdbc-postgres,metrics --dry-run

  %(prog)s --name my-service --package com.example --lang java \\
           --modules http-server,http-client,jdbc-postgres,metrics

  %(prog)s --name kafka-service --package com.example --lang kotlin \\
           --modules kafka,metrics
        """,
    )
    parser.add_argument("--name", help="Project name (required unless --list-modules)")
    parser.add_argument("--package", help="Base package, e.g. com.example (required unless --list-modules)")
    parser.add_argument("--lang", choices=["java", "kotlin"], default="java", help="Language")
    parser.add_argument("--output", default=".", help="Output directory")
    parser.add_argument(
        "--kora-version",
        default=DEFAULT_KORA_VERSION,
        help=f"Kora version for kora-bom (default: {DEFAULT_KORA_VERSION})",
    )
    parser.add_argument(
        "--jdk",
        type=int,
        default=DEFAULT_JDK,
        help=f"JDK for the Gradle toolchain; {DEFAULT_JDK} is the Kora 2.0 floor (default: {DEFAULT_JDK})",
    )
    parser.add_argument("--modules", "-m", help="Comma-separated module keys (see --list-modules)")
    parser.add_argument("--list-modules", action="store_true", help="List available modules and exit")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the plan and the generated build script without writing anything",
    )
    return parser.parse_args(argv)


def list_modules() -> None:
    print("\nAvailable modules (Kora 2.0):\n")
    categories: Dict[str, List[str]] = {}
    for key, info in MODULES.items():
        categories.setdefault(info["category"], []).append(key)

    for category, keys in categories.items():
        print(f"{category}:")
        for key in keys:
            print(f"  {key:20} - {MODULES[key]['description']}")
        print()

    print("Always included: " + ", ".join(f"{GROUP}:{a}" for a in CORE_ARTIFACTS))
    print()


HTTP_CLIENT_KEYS = ["http-client", "http-client-jdk", "http-client-apache"]


def validate_modules(selected: List[str]) -> None:
    unknown = [m for m in selected if m not in MODULES]
    if unknown:
        print("error: unknown module(s): " + ", ".join(unknown), file=sys.stderr)
        print("       run with --list-modules to see the valid keys", file=sys.stderr)
        raise SystemExit(2)

    # Two database modules would emit two `jdbc { ... }` sections that silently merge.
    databases = [m for m in selected if m in DB_MODULE_KEYS]
    if len(databases) > 1:
        print("error: pick at most one database module, got: " + ", ".join(databases), file=sys.stderr)
        raise SystemExit(2)

    if "scheduling-db" in selected and not any(m in selected for m in ("jdbc-postgres", "jdbc-mysql")):
        print("error: scheduling-db stores its jobs in the database; add jdbc-postgres or jdbc-mysql",
              file=sys.stderr)
        raise SystemExit(2)

    transports = [m for m in selected if m in HTTP_CLIENT_KEYS]
    if len(transports) > 1:
        print("warning: more than one HTTP client transport selected (" + ", ".join(transports) + ");",
              file=sys.stderr)
        print("         a service normally needs exactly one.", file=sys.stderr)


def get_package_path(package: str) -> str:
    return package.replace(".", "/")


def db_identifier(name: str) -> str:
    """Project name usable as an unquoted database / keyspace identifier."""
    return name.replace("-", "_")


# ---------------------------------------------------------------------------
# Dependency resolution
# ---------------------------------------------------------------------------

def collect_dependencies(modules: List[str]):
    """Return (kora_coordinates, external_coordinates, buildscript_coordinates), each sorted."""
    kora = {f"{GROUP}:{artifact}" for artifact in CORE_ARTIFACTS}
    external = set()
    buildscript = set()

    for key in modules:
        info = MODULES[key]
        group = info.get("group", GROUP)

        if info.get("artifact"):
            kora.add(f"{group}:{info['artifact']}")

        for extra_group, extra_artifact in info.get("extra_artifacts", []):
            kora.add(f"{extra_group}:{extra_artifact}")

        for bs_group, bs_artifact in info.get("buildscript", []):
            buildscript.add(f"{bs_group}:{bs_artifact}")

        external.update(info.get("external", []))

    return sorted(kora), sorted(external), sorted(buildscript)


def collect_app_modules(modules: List[str]):
    """Return (imports, simple_names) for the @KoraApp interface, deduplicated and ordered."""
    seen = set()
    pairs: List[Tuple[str, str]] = []

    def add(pair):
        if pair and pair[1] not in seen:
            seen.add(pair[1])
            pairs.append(pair)

    for pair in CORE_MODULE_INTERFACES:
        add(pair)
    for key in modules:
        info = MODULES[key]
        add(info.get("module_interface"))
        for extra in info.get("extra_module_interfaces", []):
            add(extra)

    return [fq for fq, _ in pairs], [name for _, name in pairs]


def is_snapshot(kora_version: str) -> bool:
    return kora_version.endswith("-SNAPSHOT")


SNAPSHOT_REPO = "https://central.sonatype.com/repository/maven-snapshots"


def repository_lines(kora_version: str, kotlin: bool) -> List[str]:
    """Project repositories. Every release lives on Central; only snapshots need more."""
    lines = ["repositories {", "    mavenCentral()"]
    if is_snapshot(kora_version):
        lines.append("    // required only for the -SNAPSHOT development line")
        if kotlin:
            lines.append(f'    maven {{ url = uri("{SNAPSHOT_REPO}") }}')
        else:
            lines.append(f'    maven {{ url = "{SNAPSHOT_REPO}" }}')
    lines.append("}")
    return lines


def buildscript_repository_lines(kora_version: str, kotlin: bool) -> List[str]:
    inner = ["    repositories {", "        mavenCentral()"]
    if is_snapshot(kora_version):
        if kotlin:
            inner.append(f'        maven {{ url = uri("{SNAPSHOT_REPO}") }}')
        else:
            inner.append(f'        maven {{ url = "{SNAPSHOT_REPO}" }}')
    inner.append("    }")
    return inner


def openapi_mode(modules: List[str], lang: str) -> Optional[str]:
    if "openapi-server" in modules:
        return "java-server" if lang == "java" else "kotlin-server"
    if "openapi-client" in modules:
        return "java-client" if lang == "java" else "kotlin-client"
    return None


# ---------------------------------------------------------------------------
# Build script generation
# ---------------------------------------------------------------------------

def generate_build_gradle(package: str, lang: str, kora_version: str, jdk: int,
                          modules: List[str]) -> str:
    kora, external, buildscript = collect_dependencies(modules)
    mode = openapi_mode(modules, lang)
    return (_kotlin_build_script if lang == "kotlin" else _java_build_script)(
        package, kora_version, jdk, modules, kora, external, buildscript, mode
    )


def _openapi_task_groovy(package: str, mode: str) -> List[str]:
    return [
        "",
        'def openApiGenerate = tasks.register("openApiGenerate", GenerateTask) {',
        '    generatorName = "kora"',
        '    group = "openapi tools"',
        '    inputSpec = layout.projectDirectory.file("src/main/resources/openapi/openapi.yaml")',
        '    outputDir = layout.buildDirectory.dir("generated/openapi")',
        f'    def corePackage = "{package}.openapi"',
        '    apiPackage = "${corePackage}.api"',
        '    modelPackage = "${corePackage}.model"',
        '    invokerPackage = "${corePackage}.invoker"',
        "    configOptions = [",
        f'            mode: "{mode}",',
        "    ]",
        "}",
        "sourceSets.main { java.srcDirs += openApiGenerate.get().outputDir }",
        "compileJava.dependsOn openApiGenerate",
    ]


def _openapi_task_kotlin(package: str, mode: str) -> List[str]:
    return [
        "",
        'val openApiGenerate = tasks.register<GenerateTask>("openApiGenerate") {',
        '    generatorName = "kora"',
        '    group = "openapi tools"',
        '    inputSpec.set(layout.projectDirectory.file("src/main/resources/openapi/openapi.yaml"))',
        '    outputDir.set(layout.buildDirectory.dir("generated/openapi"))',
        f'    val corePackage = "{package}.openapi"',
        '    apiPackage = "${corePackage}.api"',
        '    modelPackage = "${corePackage}.model"',
        '    invokerPackage = "${corePackage}.invoker"',
        "    configOptions = mapOf(",
        f'        "mode" to "{mode}",',
        "    )",
        "}",
        "kotlin.sourceSets.main { kotlin.srcDir(layout.buildDirectory.dir(\"generated/openapi\")) }",
        "// KSP 2 no longer exports the KspTask type - match the tasks by name.",
        'tasks.matching { it.name.startsWith("ksp") }.configureEach {',
        "    dependsOn(openApiGenerate)",
        "}",
    ]


def _java_build_script(package, kora_version, jdk, modules, kora, external, buildscript, mode) -> str:
    lines: List[str] = []

    if buildscript:
        lines.append("import org.openapitools.generator.gradle.plugin.tasks.GenerateTask")
        lines.append("")
        lines.append("buildscript {")
        lines.extend(buildscript_repository_lines(kora_version, kotlin=False))
        lines.append("    dependencies {")
        for coordinate in buildscript:
            lines.append(f'        classpath "{coordinate}:{kora_version}"')
        lines.append("    }")
        lines.append("}")
        lines.append("")

    lines.append("plugins {")
    lines.append('    id "java"')
    lines.append('    id "application"')
    if mode:
        lines.append(f'    id "org.openapi.generator" version "{OPENAPI_PLUGIN_VERSION}"')
    lines.append("}")
    lines.append("")
    lines.extend(repository_lines(kora_version, kotlin=False))
    lines.extend([
        "",
        "java {",
        "    toolchain {",
        "        // Kora 2.0 artifacts are built at JVM 25 - that is the floor.",
        f"        languageVersion = JavaLanguageVersion.of({jdk})",
        "        vendor = JvmVendorSpec.ADOPTIUM",
        "    }",
        "}",
        "",
        "// A `platform` on implementation never reaches the annotationProcessor classpath,",
        "// so Java wires the BOM through a dedicated configuration.",
        "configurations {",
        "    koraBom",
        "    annotationProcessor.extendsFrom(koraBom)",
        "    compileOnly.extendsFrom(koraBom)",
        "    implementation.extendsFrom(koraBom)",
        "    api.extendsFrom(koraBom)",
        "    testImplementation.extendsFrom(koraBom)",
        "    testAnnotationProcessor.extendsFrom(koraBom)",
        "}",
        "",
        "dependencies {",
        f'    koraBom platform("{GROUP}:kora-bom:{kora_version}")',
        f'    annotationProcessor "{GROUP}:annotation-processors"',
        "",
        "    // Kora modules - no versions, the BOM owns them",
    ])
    lines.extend(f'    implementation "{coordinate}"' for coordinate in kora)

    if external:
        lines.append("")
        lines.append("    // Externally versioned - not in the Kora BOM")
        lines.extend(f'    implementation "{coordinate}"' for coordinate in external)

    lines.extend([
        "",
        "    // test-junit5 declares Mockito compileOnly - bring your own, new enough for Java 25.",
        f'    testImplementation "{GROUP}:test-junit5"',
        f'    testImplementation "{MOCKITO}"',
        "}",
        "",
        "application {",
        '    applicationName = "application"',
        f'    mainClass = "{package}.Application"',
        '    applicationDefaultJvmArgs = ["-Dfile.encoding=UTF-8"]',
        "}",
        "",
        "compileJava {",
        '    options.encoding = "UTF-8"',
        "    options.incremental = true",
        "    options.fork = false",
        "}",
        "",
        "test {",
        "    useJUnitPlatform()",
        "    testLogging {",
        '        events "passed", "skipped", "failed"',
        "        showStandardStreams = true",
        "    }",
        "}",
    ])

    if mode:
        lines.extend(_openapi_task_groovy(package, mode))

    return "\n".join(lines) + "\n"


def _kotlin_build_script(package, kora_version, jdk, modules, kora, external, buildscript, mode) -> str:
    lines: List[str] = []

    if buildscript:
        lines.append("import org.openapitools.generator.gradle.plugin.tasks.GenerateTask")
        lines.append("")
        lines.append("buildscript {")
        lines.extend(buildscript_repository_lines(kora_version, kotlin=True))
        lines.append("    dependencies {")
        for coordinate in buildscript:
            lines.append(f'        classpath("{coordinate}:{kora_version}")')
        lines.append("    }")
        lines.append("}")
        lines.append("")

    lines.append("plugins {")
    lines.append('    id("application")')
    lines.append(f'    kotlin("jvm") version "{KOTLIN_VERSION}"')
    lines.append(f'    id("com.google.devtools.ksp") version "{KSP_VERSION}"')
    if mode:
        lines.append(f'    id("org.openapi.generator") version "{OPENAPI_PLUGIN_VERSION}"')
    lines.append("}")
    lines.append("")
    lines.extend(repository_lines(kora_version, kotlin=True))
    lines.extend([
        "",
        "dependencies {",
        "    // Kotlin puts the BOM straight on implementation - no koraBom configuration.",
        f'    implementation(platform("{GROUP}:kora-bom:{kora_version}"))',
        "    // The BOM does not constrain the `ksp` configuration, so the processor keeps its version.",
        f'    ksp("{GROUP}:symbol-processors:{kora_version}")',
        "",
        "    // Kora modules - no versions, the BOM owns them",
    ])
    lines.extend(f'    implementation("{coordinate}")' for coordinate in kora)

    if external:
        lines.append("")
        lines.append("    // Externally versioned - not in the Kora BOM")
        lines.extend(f'    implementation("{coordinate}")' for coordinate in external)

    lines.extend([
        "",
        "    // test-junit5 declares MockK compileOnly - bring your own, new enough for Java 25.",
        f'    testImplementation("{GROUP}:test-junit5")',
        f'    testImplementation("{MOCKK}")',
        "    // Add kspTest only when test sources generate a Kora graph of their own:",
        f'    // kspTest("{GROUP}:symbol-processors:{kora_version}")',
        "}",
        "",
        "kotlin {",
        "    jvmToolchain {",
        f"        languageVersion.set(JavaLanguageVersion.of({jdk}))",
        "        vendor.set(JvmVendorSpec.ADOPTIUM)",
        "    }",
        "}",
        "",
        "application {",
        '    applicationName = "application"',
        f'    mainClass.set("{package}.ApplicationKt")',
        '    applicationDefaultJvmArgs = listOf("-Dfile.encoding=UTF-8")',
        "}",
        "",
        "tasks.test {",
        "    useJUnitPlatform()",
        "    testLogging {",
        '        events("passed", "skipped", "failed")',
        "        showStandardStreams = true",
        "    }",
        "}",
    ])

    if mode:
        lines.extend(_openapi_task_kotlin(package, mode))

    return "\n".join(lines) + "\n"


def generate_settings_gradle(name: str, lang: str) -> str:
    if lang == "kotlin":
        return f'rootProject.name = "{name}"\n'
    return f"rootProject.name = '{name}'\n"


def generate_gradle_properties(kora_version: str, lang: str) -> str:
    lines = [
        "# Kora BOM version - every io.koraframework:* artifact inherits it.",
        "# 2.0.0.RC2 is on Maven Central; check the releases page before moving to a newer one:",
        "# https://github.com/kora-projects/kora/releases",
        f"koraVersion={kora_version}",
        "",
        "# JVM",
        "org.gradle.jvmargs=-Xmx2g -Dfile.encoding=UTF-8",
        "",
        "# Gradle",
        "org.gradle.parallel=true",
        "org.gradle.caching=true",
    ]
    if lang == "kotlin":
        lines.extend([
            "",
            "# Kotlin/KSP",
            f"kotlinVersion={KOTLIN_VERSION}",
            f"kspVersion={KSP_VERSION}",
            "kotlin.jvm.target.validation.mode=warning",
        ])
    lines.extend([
        "",
        "# Do NOT commit org.gradle.java.home - the path is machine-specific. Kora 2.0 needs the JVM",
        "# running Gradle to be 25+ whenever io.koraframework:openapi-generator is on the buildscript",
        "# classpath; set JAVA_HOME instead.",
    ])
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Application sources
# ---------------------------------------------------------------------------

def generate_application_java(package: str, modules: List[str]) -> str:
    imports, names = collect_app_modules(modules)
    import_block = "\n".join(f"import {fq};" for fq in imports)
    extends_block = ",\n        ".join(names)
    return f"""package {package};

import io.koraframework.application.graph.KoraApplication;
import io.koraframework.common.annotation.KoraApp;
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
    imports, names = collect_app_modules(modules)
    import_block = "\n".join(f"import {fq}" for fq in imports)
    extends_block = ",\n    ".join(names)
    return f"""package {package}

import io.koraframework.application.graph.KoraApplication
import io.koraframework.common.annotation.KoraApp
{import_block}

@KoraApp
interface Application : {extends_block}

fun main() {{
    KoraApplication.run {{ ApplicationGraph.graph() }}
}}
"""


# ---------------------------------------------------------------------------
# application.conf
# ---------------------------------------------------------------------------

def generate_application_conf(name: str, modules: List[str]) -> str:
    """Generate a 2.0 application.conf for the selected modules.

    HOCON default pattern: declare a literal default, then allow an env override on the next line
    (the optional ${?ENV} replaces the value only when the variable is set).
    """
    # Component telemetry defaults to disabled in 2.0, so anything that should be observable has to
    # opt in explicitly - adding micrometer-module alone produces no metrics.
    metrics_on = "metrics" in modules
    telemetry_lines = ["  telemetry.logging.enabled = true"]
    if metrics_on:
        telemetry_lines.append("  telemetry.metrics.enabled = true")

    lines = [
        f"# Kora application config: {name}",
        "",
        "# Logging levels per logger",
        "logging.levels {",
        '  "root" = "WARN"',
        '  "io.koraframework" = "INFO"',
        "}",
    ]

    if "http-server" in modules or "openapi-server" in modules:
        lines.extend([
            "",
            "# HTTP server. The system server (metrics, readiness, liveness) is a sub-section,",
            "# not a separate `privateApiHttpPort` key. Unrecognised keys are ignored without an error,",
            "# so a leftover 1.x key does not fail - the server just uses its own default (8080 public,",
            "# 8085 system) and the service starts green on ports nothing is pointed at.",
            "httpServer {",
            "  port = 8080",
            "  port = ${?HTTP_PORT}",
            *telemetry_lines,
            "}",
            "",
            "httpServer.system {",
            "  port = 8085",
            "  port = ${?HTTP_SYSTEM_PORT}",
            "}",
        ])

    if "openapi-server" in modules:
        lines.extend([
            "",
            "# Serve the spec and a UI over the HTTP server. `files` is a list in 2.0.",
            "openapi.management {",
            "  enabled = true",
            '  files = ["openapi/openapi.yaml"]',
            "  swaggerui.enabled = true",
            "  scalar.enabled = true",
            "}",
        ])

    if any(m in modules for m in ("http-client", "http-client-jdk", "http-client-apache", "openapi-client")):
        lines.extend([
            "",
            "# HTTP client defaults",
            "httpClient {",
            '  connectTimeout = "5s"',
            '  readTimeout = "30s"',
            *telemetry_lines,
            "}",
        ])

    if "jdbc-postgres" in modules:
        lines.extend([
            "",
            "# PostgreSQL via JDBC + HikariCP. The section is `jdbc` in 2.0 (it was `db` in 1.x).",
            "jdbc {",
            f'  jdbcUrl = "jdbc:postgresql://localhost:5432/{db_identifier(name)}"',
            "  jdbcUrl = ${?DB_URL}",
            '  username = "postgres"',
            "  username = ${?DB_USER}",
            '  password = "postgres"',
            "  password = ${?DB_PASS}",
            "  maxPoolSize = 10",
            *telemetry_lines,
            "}",
        ])

    if "jdbc-mysql" in modules:
        lines.extend([
            "",
            "# MySQL via JDBC + HikariCP. The section is `jdbc` in 2.0 (it was `db` in 1.x).",
            "jdbc {",
            f'  jdbcUrl = "jdbc:mysql://localhost:3306/{db_identifier(name)}"',
            "  jdbcUrl = ${?DB_URL}",
            '  username = "root"',
            "  username = ${?DB_USER}",
            '  password = "root"',
            "  password = ${?DB_PASS}",
            "  maxPoolSize = 10",
            *telemetry_lines,
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
            f'    sessionKeyspace = "{db_identifier(name)}"',
            "  }",
            *telemetry_lines,
            "}",
        ])

    if "kafka" in modules:
        # @KafkaListener / @KafkaPublisher take a config path; these match the generated sources.
        lines.extend([
            "",
            "# Kafka consumer and publisher config paths",
            "kafka {",
            "  consumer.my-listener {",
            '    topics = ["users"]',
            "    driverProperties {",
            '      "bootstrap.servers" = "localhost:9092"',
            '      "bootstrap.servers" = ${?KAFKA_BOOTSTRAP_SERVERS}',
            f'      "group.id" = "{name}"',
            '      "auto.offset.reset" = "earliest"',
            "    }",
            *[f"  {line}" for line in telemetry_lines],
            "  }",
            "  producer.my-publisher {",
            "    driverProperties {",
            '      "bootstrap.servers" = "localhost:9092"',
            '      "bootstrap.servers" = ${?KAFKA_BOOTSTRAP_SERVERS}',
            "    }",
            *[f"  {line}" for line in telemetry_lines],
            "  }",
            "}",
        ])

    if "scheduling-db" in modules:
        lines.extend([
            "",
            "# db-scheduler keeps its jobs in the `jdbc` database; create its table on startup.",
            "scheduling {",
            "  dbScheduler {",
            "    tableInitialize = true",
            "  }",
            "}",
        ])

    if "caching-redis" in modules or "resilient-redis" in modules:
        lines.extend([
            "",
            "# Lettuce/Redis client",
            "lettuce {",
            '  uri = "redis://localhost:6379"',
            "  uri = ${?REDIS_URI}",
            "}",
        ])

    if "tracing" in modules:
        lines.extend([
            "",
            "# OpenTelemetry tracing exporter (tracing telemetry is enabled by default)",
            "tracing {",
            "  exporter {",
            '    endpoint = "http://localhost:4317"',
            "    endpoint = ${?OTEL_EXPORTER_ENDPOINT}",
            "  }",
            "  attributes {",
            f'    "service.name" = "{name}"',
            "  }",
            "}",
        ])

    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Example sources
# ---------------------------------------------------------------------------

def generate_example_controller(package: str, package_path: str, lang: str,
                                has_repository: bool,
                                insert_returns_id: bool = True) -> Dict[str, str]:
    """A UserController on @HttpController + @HttpRoute.

    The wire model is a nested `@Json UserTO`, never the `@EntityJdbc` / `@EntityCassandra`
    record. Two reasons, both load-bearing:

      * `@Json` on a *method* marks the body as JSON; it does not make the payload type
        serializable. Returning the entity without `@Json` on the entity itself fails the
        graph build with `No component found for dependency: JsonWriter<UserEntity>`.
      * Annotating the entity would work, but every one of the 54 `@EntityJdbc` types in the
        migrated Kora 2.0 corpus keeps DAO and wire model separate. A starter should teach
        the idiom the rest of the package documents.

    `insert_returns_id` is False for Cassandra, whose repository `insert` returns void.
    `create` echoes the created resource either way, so it compiles for all three databases.
    """
    if not has_repository:
        if lang == "kotlin":
            return {
                f"src/main/kotlin/{package_path}/controller/HelloController.kt": f"""package {package}.controller

import io.koraframework.common.annotation.Component
import io.koraframework.http.common.HttpMethod
import io.koraframework.http.common.annotation.HttpRoute
import io.koraframework.http.server.common.annotation.HttpController
import io.koraframework.json.common.annotation.Json

@Component
@HttpController
class HelloController {{

    @Json
    data class HelloResponse(val greeting: String)

    @Json
    @HttpRoute(method = HttpMethod.GET, path = "/hello")
    fun hello(): HelloResponse = HelloResponse("Hello world")
}}
"""
            }
        return {
            f"src/main/java/{package_path}/controller/HelloController.java": f"""package {package}.controller;

import io.koraframework.common.annotation.Component;
import io.koraframework.http.common.HttpMethod;
import io.koraframework.http.common.annotation.HttpRoute;
import io.koraframework.http.server.common.annotation.HttpController;
import io.koraframework.json.common.annotation.Json;

@Component
@HttpController
public final class HelloController {{

    @Json
    public record HelloResponse(String greeting) {{}}

    @Json
    @HttpRoute(method = HttpMethod.GET, path = "/hello")
    public HelloResponse hello() {{
        return new HelloResponse("Hello world");
    }}
}}
"""
        }

    # Cassandra has no generated keys, so its repository `insert` returns void.
    # `create` echoes the created resource either way, which keeps one controller shape
    # working across PostgreSQL, MySQL and Cassandra.
    if insert_returns_id:
        java_create_body = (
            "        Long id = userRepository.insert("
            "new UserEntity(user.id(), user.name(), user.email()));\n"
            "        return new UserTO(id, user.name(), user.email());"
        )
        kotlin_create_body = (
            "        val id = userRepository.insert("
            "UserEntity(user.id, user.name, user.email))\n"
            "        return user.copy(id = id)"
        )
    else:
        java_create_body = (
            "        userRepository.insert("
            "new UserEntity(user.id(), user.name(), user.email()));\n"
            "        return user;"
        )
        kotlin_create_body = (
            "        userRepository.insert("
            "UserEntity(user.id, user.name, user.email))\n"
            "        return user"
        )

    if lang == "kotlin":
        return {
            f"src/main/kotlin/{package_path}/controller/UserController.kt": f"""package {package}.controller

import io.koraframework.common.annotation.Component
import io.koraframework.http.common.HttpMethod
import io.koraframework.http.common.annotation.HttpRoute
import io.koraframework.http.common.annotation.Path
import io.koraframework.http.server.common.annotation.HttpController
import io.koraframework.json.common.annotation.Json
import {package}.repository.UserEntity
import {package}.repository.UserRepository

@Component
@HttpController
class UserController(
    private val userRepository: UserRepository
) {{

    @Json
    data class UserTO(val id: Long?, val name: String, val email: String)

    @Json
    @HttpRoute(method = HttpMethod.GET, path = "/users")
    fun getAll(): List<UserTO> = userRepository.findAll().map(::toTO)

    @Json
    @HttpRoute(method = HttpMethod.GET, path = "/users/{{id}}")
    fun getById(@Path id: Long): UserTO? = userRepository.findById(id)?.let(::toTO)

    @Json
    @HttpRoute(method = HttpMethod.POST, path = "/users")
    fun create(@Json user: UserTO): UserTO {{
{kotlin_create_body}
    }}

    private fun toTO(entity: UserEntity) = UserTO(entity.id, entity.name, entity.email)
}}
"""
        }

    return {
        f"src/main/java/{package_path}/controller/UserController.java": f"""package {package}.controller;

import java.util.List;
import org.jspecify.annotations.Nullable;
import io.koraframework.common.annotation.Component;
import io.koraframework.http.common.HttpMethod;
import io.koraframework.http.common.annotation.HttpRoute;
import io.koraframework.http.common.annotation.Path;
import io.koraframework.http.server.common.annotation.HttpController;
import io.koraframework.json.common.annotation.Json;
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
    public record UserTO(@Nullable Long id, String name, String email) {{}}

    @Json
    @HttpRoute(method = HttpMethod.GET, path = "/users")
    public List<UserTO> getAll() {{
        return userRepository.findAll().stream().map(UserController::toTO).toList();
    }}

    @Json
    @HttpRoute(method = HttpMethod.GET, path = "/users/{{id}}")
    public @Nullable UserTO getById(@Path long id) {{
        var entity = userRepository.findById(id);
        return entity == null ? null : toTO(entity);
    }}

    @Json
    @HttpRoute(method = HttpMethod.POST, path = "/users")
    public UserTO create(@Json UserTO user) {{
{java_create_body}
    }}

    private static UserTO toTO(UserEntity entity) {{
        return new UserTO(entity.id(), entity.name(), entity.email());
    }}
}}
"""
    }


def generate_example_repository(package: str, package_path: str, lang: str,
                                db_type: str) -> Dict[str, str]:
    """A UserRepository on @Repository + @Query.

    JDBC      -> extends JdbcRepository,      entity is @EntityJdbc
    Cassandra -> extends CassandraRepository, entity is @EntityCassandra
    """
    files: Dict[str, str] = {}
    is_cassandra = db_type == "cassandra"
    repo_iface = "CassandraRepository" if is_cassandra else "JdbcRepository"
    repo_import = (
        "io.koraframework.database.cassandra.CassandraRepository" if is_cassandra
        else "io.koraframework.database.jdbc.JdbcRepository"
    )
    entity_anno = "EntityCassandra" if is_cassandra else "EntityJdbc"
    entity_import = (
        "io.koraframework.database.cassandra.annotation.EntityCassandra" if is_cassandra
        else "io.koraframework.database.jdbc.annotation.EntityJdbc"
    )
    # Generated-key retrieval differs per database:
    #   PostgreSQL - RETURNING id in the SQL, the method returns the value
    #   MySQL      - no RETURNING; @Id on the method makes Kora read the generated key
    #   Cassandra  - no generated keys at all, the id is supplied by the caller
    if is_cassandra:
        insert_query = "INSERT INTO users(id, name, email) VALUES (:user.id, :user.name, :user.email)"
        insert_method_annotations = ""
        insert_return_java = "void"
        insert_return_kotlin = ""
    elif db_type == "jdbc-mysql":
        insert_query = "INSERT INTO users(name, email) VALUES (:user.name, :user.email)"
        insert_method_annotations = "@Id\n    "
        insert_return_java = "Long"
        insert_return_kotlin = ": Long"
    else:
        insert_query = "INSERT INTO users(name, email) VALUES (:user.name, :user.email) RETURNING id"
        insert_method_annotations = ""
        insert_return_java = "long"
        insert_return_kotlin = ": Long"

    # @Id on the method is the only case where the repository needs the annotation import.
    repo_id_import_java = "import io.koraframework.database.common.annotation.Id;\n" if insert_method_annotations else ""
    repo_id_import_kotlin = "import io.koraframework.database.common.annotation.Id\n" if insert_method_annotations else ""

    if lang == "kotlin":
        files[f"src/main/kotlin/{package_path}/repository/UserEntity.kt"] = f"""package {package}.repository

import io.koraframework.database.common.annotation.Column
import io.koraframework.database.common.annotation.Id
import io.koraframework.database.common.annotation.Table
import {entity_import}

@{entity_anno}
@Table("users")
data class UserEntity(
    @Id @Column("id") val id: Long?,
    @Column("name") val name: String,
    @Column("email") val email: String
)
"""
        files[f"src/main/kotlin/{package_path}/repository/UserRepository.kt"] = f"""package {package}.repository

{repo_id_import_kotlin}import io.koraframework.database.common.annotation.Query
import io.koraframework.database.common.annotation.Repository
import {repo_import}

@Repository
interface UserRepository : {repo_iface} {{

    @Query("SELECT id, name, email FROM users")
    fun findAll(): List<UserEntity>

    @Query("SELECT id, name, email FROM users WHERE id = :id")
    fun findById(id: Long): UserEntity?

    {insert_method_annotations}@Query("{insert_query}")
    fun insert(user: UserEntity){insert_return_kotlin}
}}
"""
        return files

    files[f"src/main/java/{package_path}/repository/UserEntity.java"] = f"""package {package}.repository;

import org.jspecify.annotations.Nullable;
import io.koraframework.database.common.annotation.Column;
import io.koraframework.database.common.annotation.Id;
import io.koraframework.database.common.annotation.Table;
import {entity_import};

@{entity_anno}
@Table("users")
public record UserEntity(
    @Id @Column("id") @Nullable Long id,
    @Column("name") String name,
    @Column("email") String email
) {{}}
"""
    files[f"src/main/java/{package_path}/repository/UserRepository.java"] = f"""package {package}.repository;

import java.util.List;
import org.jspecify.annotations.Nullable;
{repo_id_import_java}import io.koraframework.database.common.annotation.Query;
import io.koraframework.database.common.annotation.Repository;
import {repo_import};

@Repository
public interface UserRepository extends {repo_iface} {{

    @Query("SELECT id, name, email FROM users")
    List<UserEntity> findAll();

    @Query("SELECT id, name, email FROM users WHERE id = :id")
    @Nullable UserEntity findById(long id);

    {insert_method_annotations}@Query("{insert_query}")
    {insert_return_java} insert(UserEntity user);
}}
"""
    return files


def generate_initial_migration_sql(db_type: str) -> str:
    if db_type == "jdbc-mysql":
        return """-- V1__initial_schema.sql
-- Initial schema - users table

CREATE TABLE IF NOT EXISTS users (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    email VARCHAR(255) NOT NULL UNIQUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE INDEX idx_users_name ON users(name);
"""
    return """-- V1__initial_schema.sql
-- Initial schema - users table

CREATE TABLE IF NOT EXISTS users (
    id BIGSERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    email VARCHAR(255) NOT NULL UNIQUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_users_name ON users(name);
"""


def generate_cassandra_schema_cql(name: str) -> str:
    keyspace = db_identifier(name)
    return f"""-- Cassandra schema. database-cassandra has no migration runner - apply this with cqlsh
-- or your own tooling before the service starts.

CREATE KEYSPACE IF NOT EXISTS {keyspace}
WITH replication = {{'class': 'SimpleStrategy', 'replication_factor': 1}};

USE {keyspace};

CREATE TABLE IF NOT EXISTS users (
    id BIGINT PRIMARY KEY,
    name TEXT,
    email TEXT,
    created_at TIMESTAMP
);
"""


def generate_example_kafka(package: str, package_path: str, lang: str) -> Dict[str, str]:
    """A @KafkaPublisher interface and a @KafkaListener component.

    The config paths match the sections written into application.conf.
    """
    files: Dict[str, str] = {}

    if lang == "kotlin":
        files[f"src/main/kotlin/{package_path}/kafka/UserEvent.kt"] = f"""package {package}.kafka

import io.koraframework.json.common.annotation.Json

@Json
data class UserEvent(val id: Long, val email: String)
"""
        files[f"src/main/kotlin/{package_path}/kafka/UserPublisher.kt"] = f"""package {package}.kafka

import io.koraframework.json.common.annotation.Json
import io.koraframework.kafka.common.annotation.KafkaPublisher

@KafkaPublisher("kafka.producer.my-publisher")
interface UserPublisher {{

    @KafkaPublisher.Topic("kafka.producer.my-publisher.users")
    fun send(@Json event: UserEvent)
}}
"""
        files[f"src/main/kotlin/{package_path}/kafka/UserListener.kt"] = f"""package {package}.kafka

import io.koraframework.common.annotation.Component
import io.koraframework.json.common.annotation.Json
import io.koraframework.kafka.common.annotation.KafkaListener

@Component
class UserListener {{

    @KafkaListener("kafka.consumer.my-listener")
    fun process(@Json event: UserEvent) {{
        // Handle the incoming user event
    }}
}}
"""
        return files

    files[f"src/main/java/{package_path}/kafka/UserEvent.java"] = f"""package {package}.kafka;

import io.koraframework.json.common.annotation.Json;

@Json
public record UserEvent(long id, String email) {{}}
"""
    files[f"src/main/java/{package_path}/kafka/UserPublisher.java"] = f"""package {package}.kafka;

import io.koraframework.json.common.annotation.Json;
import io.koraframework.kafka.common.annotation.KafkaPublisher;

@KafkaPublisher("kafka.producer.my-publisher")
public interface UserPublisher {{

    @KafkaPublisher.Topic("kafka.producer.my-publisher.users")
    void send(@Json UserEvent event);
}}
"""
    files[f"src/main/java/{package_path}/kafka/UserListener.java"] = f"""package {package}.kafka;

import io.koraframework.common.annotation.Component;
import io.koraframework.json.common.annotation.Json;
import io.koraframework.kafka.common.annotation.KafkaListener;

@Component
public final class UserListener {{

    @KafkaListener("kafka.consumer.my-listener")
    public void process(@Json UserEvent event) {{
        // Handle the incoming user event
    }}
}}
"""
    return files


def generate_openapi_spec(name: str) -> str:
    return f"""openapi: 3.0.3
info:
  title: {name}
  version: 1.0.0
paths:
  /hello:
    get:
      operationId: hello
      responses:
        "200":
          description: OK
          content:
            application/json:
              schema:
                $ref: "#/components/schemas/HelloResponse"
components:
  schemas:
    HelloResponse:
      type: object
      required: [greeting]
      properties:
        greeting:
          type: string
"""


def generate_gitignore() -> str:
    return """# Compiled class files
*.class

# Log files
*.log

# Package files
*.jar
*.war
*.zip
*.tar.gz

# Gradle
.gradle/
build/
!gradle/wrapper/gradle-wrapper.jar

# IDE
.idea/
*.iml
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


def generate_dockerfile(name: str, jdk: int) -> str:
    return f"""# Build stage.
# Kora 2.0 artifacts are built at JVM 25, and openapi-generator on the buildscript classpath is
# resolved by the JVM running Gradle - so the builder image must be {jdk}, not just the toolchain.
FROM gradle:{GRADLE_VERSION}-jdk{jdk} AS builder

WORKDIR /home/gradle/project

COPY --chown=gradle:gradle . .
RUN gradle build --no-daemon

# Runtime stage
FROM eclipse-temurin:{jdk}-jre-alpine

WORKDIR /app

COPY --from=builder /home/gradle/project/build/libs/*.jar app.jar

# 8080 public traffic, 8085 system server (metrics, readiness, liveness)
EXPOSE 8080 8085

ENTRYPOINT ["java", "-jar", "app.jar"]
"""


def generate_readme(name: str, package: str, lang: str, kora_version: str, jdk: int,
                    modules: List[str]) -> str:
    module_list = "\n".join(f"- `{m}` - {MODULES[m]['description']}" for m in modules) or "- Core modules only"
    build_file = "build.gradle.kts" if lang == "kotlin" else "build.gradle"
    openapi_note = ""
    if openapi_mode(modules, lang):
        openapi_note = """
## OpenAPI

The spec lives in `src/main/resources/openapi/openapi.yaml` and is generated into
`build/generated/openapi` by the `openApiGenerate` task. For a server, implement the generated
`*ApiDelegate` as a `@Component`; for a client, inject the generated `*Api`.
"""
    wrapper_note = ""
    if wrapper_jar_missing():
        wrapper_note = (
            "\nThe wrapper JAR is binary and is not shipped with the generator - materialise it once:\n\n"
            "```bash\n"
            f"gradle wrapper --gradle-version {GRADLE_VERSION}\n"
            "```\n"
        )
    return f"""# {name}

Generated Kora {kora_version} project ({lang}, JDK {jdk}).

## Build

```bash
./gradlew clean build
```
{wrapper_note}
The JVM running Gradle must be {jdk} or newer - Kora 2.0 artifacts are built at JVM 25, and
`io.koraframework:openapi-generator` on the buildscript classpath is resolved by Gradle's own JVM.
Check with `JAVA_HOME=<jdk> ./gradlew projects`.

## Run

```bash
./gradlew run
```

## Configuration

Edit `src/main/resources/application.conf`.

Kora 2.0 section names differ from 1.x: `httpServer.port` (not `publicApiHttpPort`),
`httpServer.system.port` (not `privateApiHttpPort`), and `jdbc {{ ... }}` (not `db {{ ... }}`).
Component telemetry defaults to disabled - the generated config turns logging (and metrics, when
`micrometer-module` is selected) on explicitly.

Environment overrides declared in the generated config:
`HTTP_PORT`, `HTTP_SYSTEM_PORT`, `DB_URL`, `DB_USER`, `DB_PASS`, `KAFKA_BOOTSTRAP_SERVERS`,
`REDIS_URI`, `CASSANDRA_CONTACT_POINTS`, `OTEL_EXPORTER_ENDPOINT`.

## Modules

{module_list}

Dependencies are in `{build_file}`; Kora artifacts carry no version because
`io.koraframework:kora-bom` owns them.
{openapi_note}
## Docker

```bash
docker build -t {name} .
docker run -p 8080:8080 -p 8085:8085 {name}
```
"""


# ---------------------------------------------------------------------------
# Project assembly
# ---------------------------------------------------------------------------

def build_file_map(name: str, package: str, lang: str, kora_version: str, jdk: int,
                   modules: List[str]) -> Dict[str, str]:
    """Every text file the project consists of, as {relative path: content}."""
    package_path = get_package_path(package)
    files: Dict[str, str] = {}

    build_file = "build.gradle.kts" if lang == "kotlin" else "build.gradle"
    settings_file = "settings.gradle.kts" if lang == "kotlin" else "settings.gradle"

    files[build_file] = generate_build_gradle(package, lang, kora_version, jdk, modules)
    files[settings_file] = generate_settings_gradle(name, lang)
    files["gradle.properties"] = generate_gradle_properties(kora_version, lang)
    files[".gitignore"] = generate_gitignore()
    files["Dockerfile"] = generate_dockerfile(name, jdk)
    files["README.md"] = generate_readme(name, package, lang, kora_version, jdk, modules)

    source_root = "src/main/kotlin" if lang == "kotlin" else "src/main/java"
    app_file = "Application.kt" if lang == "kotlin" else "Application.java"
    app_content = (generate_application_kt if lang == "kotlin" else generate_application_java)(package, modules)
    files[f"{source_root}/{package_path}/{app_file}"] = app_content

    files["src/main/resources/application.conf"] = generate_application_conf(name, modules)

    db_type = next((m for m in modules if m in DB_MODULE_KEYS), None)
    if db_type:
        files.update(generate_example_repository(package, package_path, lang, db_type))
        if db_type == "cassandra":
            files["src/main/resources/cassandra/schema.cql"] = generate_cassandra_schema_cql(name)
        else:
            # Flyway's default `locations` is db/migration.
            files["src/main/resources/db/migration/V1__initial_schema.sql"] = \
                generate_initial_migration_sql(db_type)

    if "http-server" in modules:
        files.update(generate_example_controller(
            package, package_path, lang,
            has_repository=bool(db_type),
            insert_returns_id=db_type != "cassandra",
        ))

    if "kafka" in modules:
        files.update(generate_example_kafka(package, package_path, lang))

    if openapi_mode(modules, lang):
        files["src/main/resources/openapi/openapi.yaml"] = generate_openapi_spec(name)

    return files


# assets/gradle-wrapper holds the wrapper scripts plus gradle-wrapper.properties. Everything whose
# name starts with "gradle-wrapper" belongs under gradle/wrapper/; the launchers go to the root.
WRAPPER_LAUNCHERS = {"gradlew": 0o755, "gradlew.bat": 0o644}


def _wrapper_assets_dir() -> Path:
    return Path(__file__).resolve().parent.parent / "assets" / "gradle-wrapper"


def wrapper_plan() -> List[str]:
    """Relative paths the Gradle wrapper contributes, without touching the filesystem."""
    src = _wrapper_assets_dir()
    if not src.is_dir():
        return []
    plan = []
    for item in sorted(src.iterdir()):
        if not item.is_file():
            continue
        if item.name in WRAPPER_LAUNCHERS:
            plan.append(item.name)
        else:
            plan.append(f"gradle/wrapper/{item.name}")
    return plan


def wrapper_jar_missing() -> bool:
    """The wrapper cannot bootstrap without gradle-wrapper.jar, which is binary and not shipped."""
    return not (_wrapper_assets_dir() / "gradle-wrapper.jar").is_file()


def copy_gradle_wrapper(output_dir: Path) -> List[str]:
    """Copy the Gradle wrapper from assets/. Returns the relative paths copied."""
    src = _wrapper_assets_dir()
    if not src.is_dir():
        return []

    copied: List[str] = []
    (output_dir / "gradle" / "wrapper").mkdir(parents=True, exist_ok=True)

    for item in sorted(src.iterdir()):
        if not item.is_file():
            continue
        if item.name in WRAPPER_LAUNCHERS:
            dst = output_dir / item.name
            shutil.copy2(item, dst)
            dst.chmod(WRAPPER_LAUNCHERS[item.name])
            copied.append(item.name)
        else:
            shutil.copy2(item, output_dir / "gradle" / "wrapper" / item.name)
            copied.append(f"gradle/wrapper/{item.name}")

    return copied


def dry_run(name: str, package: str, lang: str, kora_version: str, jdk: int,
            modules: List[str], output_dir: Path) -> None:
    files = build_file_map(name, package, lang, kora_version, jdk, modules)
    build_file = "build.gradle.kts" if lang == "kotlin" else "build.gradle"

    print(f"\n[dry-run] Kora project: {name}")
    print(f"   Package:      {package}")
    print(f"   Language:     {lang}")
    print(f"   Kora version: {kora_version}")
    print(f"   JDK:          {jdk}")
    print(f"   Modules:      {', '.join(modules) if modules else 'core only'}")
    print(f"   Destination:  {output_dir}")

    print("\n[dry-run] Files that would be written:")
    for path in sorted(files) + wrapper_plan():
        print(f"   {path}")

    print(f"\n[dry-run] ----- {build_file} -----")
    print(files[build_file])
    print("[dry-run] ----- src/main/resources/application.conf -----")
    print(files["src/main/resources/application.conf"])
    print("[dry-run] nothing was written.")


def generate_project(args) -> None:
    selected = [m.strip() for m in args.modules.split(",")] if args.modules else []
    selected = [m for m in selected if m]
    validate_modules(selected)

    output_dir = Path(args.output) / args.name

    if args.dry_run:
        dry_run(args.name, args.package, args.lang, args.kora_version, args.jdk, selected, output_dir)
        return

    print(f"\nGenerating Kora project: {args.name}")
    print(f"   Package:      {args.package}")
    print(f"   Language:     {args.lang}")
    print(f"   Kora version: {args.kora_version}")
    print(f"   JDK:          {args.jdk}")
    print(f"   Modules:      {', '.join(selected) if selected else 'core only'}")

    files = build_file_map(args.name, args.package, args.lang, args.kora_version, args.jdk, selected)

    for relative, content in files.items():
        path = output_dir / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    (output_dir / "src" / "test" / ("kotlin" if args.lang == "kotlin" else "java")
     / get_package_path(args.package)).mkdir(parents=True, exist_ok=True)

    copied = copy_gradle_wrapper(output_dir)
    if not copied:
        print("   note: the Gradle wrapper assets were not found - run `gradle wrapper` yourself")
    elif wrapper_jar_missing():
        print("   note: gradle-wrapper.jar is not shipped with this skill - materialise it once with")
        print(f"         gradle wrapper --gradle-version {GRADLE_VERSION}")

    print(f"\nDone. {len(files) + len(copied)} files written to {output_dir.resolve()}")
    print("\nNext steps:")
    print(f"   cd {args.name}")
    print(f"   JAVA_HOME=<jdk-{args.jdk}+> ./gradlew clean build")
    print("   # edit src/main/resources/application.conf")
    if "http-server" in selected:
        print("   # HTTP: public 8080, system 8085 (metrics, readiness, liveness)")


def main(argv: Optional[List[str]] = None) -> None:
    args = parse_args(argv)

    if args.list_modules:
        list_modules()
        return

    missing = [flag for flag, value in (("--name", args.name), ("--package", args.package)) if not value]
    if missing:
        print("error: the following arguments are required: " + ", ".join(missing), file=sys.stderr)
        raise SystemExit(2)

    generate_project(args)


if __name__ == "__main__":
    main()
