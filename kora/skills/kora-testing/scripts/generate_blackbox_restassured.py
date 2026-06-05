#!/usr/bin/env python3
"""
Generator of black-box tests with RestAssured for Kora applications.

Creates tests for the HTTP API using the RestAssured DSL and AppContainer.
Supports two modes: without a DB and with PostgreSQL.

Usage:
    # Without a DB
    python generate_blackbox_restassured.py --name PetApiTests --package ru.tinkoff.kora.example --lang java

    # With PostgreSQL
    python generate_blackbox_restassured.py --name PetApiTests --package ru.tinkoff.kora.example --lang java --with-db

Options:
    --name        Test class name (e.g., PetApiTests)
    --package     Java/Kotlin package (e.g., ru.tinkoff.kora.example)
    --lang        Language: java or kotlin (default: java)
    --output      Output directory (default: current directory)
    --entity      Entity name for tests (default: entity)
    --endpoint    API endpoint (default: /api/entities)
    --with-db     Add PostgreSQL support via Testcontainers
"""

import argparse
import os
from pathlib import Path


def load_template(lang: str, with_db: bool) -> str:
    """Loads the template from assets."""
    script_dir = Path(__file__).parent
    template_name = f"BlackBoxTest-RestAssured.{lang}.template"
    template_path = script_dir.parent / "assets" / template_name
    
    if not template_path.exists():
        raise FileNotFoundError(f"Template not found: {template_path}")
    
    return template_path.read_text()


def generate_test(name: str, package: str, lang: str, entity: str, endpoint: str, with_db: bool) -> str:
    """Generates the test code."""
    template = load_template(lang, with_db)

    # Replace variables
    code = template.replace("${className}", name)
    code = code.replace("${package}", package)

    # Replace entity-specific variables
    code = code.replace("entities", entity.lower() + "s")
    code = code.replace("entity", entity.lower())
    code = code.replace("/api/entities", endpoint)

    # If with a DB, add imports and annotations
    if with_db:
        if lang == "java":
            db_imports = """import io.goodforgod.testcontainers.extensions.ContainerMode;
import io.goodforgod.testcontainers.extensions.Network;
import io.goodforgod.testcontainers.extensions.jdbc.ConnectionPostgreSQL;
import io.goodforgod.testcontainers.extensions.jdbc.JdbcConnection;
import io.goodforgod.testcontainers.extensions.jdbc.Migration;
import io.goodforgod.testcontainers.extensions.jdbc.TestcontainersPostgreSQL;
"""
            # Add imports
            code = code.replace(
                "import org.junit.jupiter.api.Test;",
                db_imports + "import org.junit.jupiter.api.Test;"
            )

            # Add class annotation
            testcontainers_annotation = f"""@TestcontainersPostgreSQL(
        network = @Network(shared = true),
        mode = ContainerMode.PER_RUN,
        migration = @Migration(
                engine = Migration.Engines.FLYWAY,
                apply = Migration.Mode.PER_METHOD,
                drop = Migration.Mode.PER_METHOD))
"""
            code = code.replace("class ${className}", testcontainers_annotation + "class ${className}")
            
            # Add the connection field
            connection_field = """
    @ConnectionPostgreSQL
    private JdbcConnection connection;
"""
            code = code.replace(
                "private static final AppContainer container = AppContainer.build();",
                connection_field + "    private static final AppContainer container = AppContainer.build()\n            .withNetwork(org.testcontainers.containers.Network.SHARED);"
            )

            # Update the setup method
            old_setup = """@BeforeAll
    static void setup() {
        // For applications with a DB, uncomment:
        // container.withEnv(Map.of(
        //     "DB_URL", "jdbc:postgresql://localhost:5432/test",
        //     "DB_USER", "postgres",
        //     "DB_PASS", "postgres"
        // ));
        container.start();
    }"""
            
            new_setup = """@BeforeAll
    static void setup(@ConnectionPostgreSQL JdbcConnection connection) {
        var params = connection.paramsInNetwork().orElseThrow();
        container.withEnv(java.util.Map.of(
                "DB_URL", params.jdbcUrl(),
                "DB_USER", params.username(),
                "DB_PASS", params.password(),
                "CACHE_MAX_SIZE", "0"));

        container.start();
    }"""
            
            code = code.replace(old_setup, new_setup)
            
        else:  # Kotlin
            db_imports = """import io.goodforgod.testcontainers.extensions.ContainerMode
import io.goodforgod.testcontainers.extensions.Network
import io.goodforgod.testcontainers.extensions.jdbc.*
"""
            code = code.replace(
                "import org.junit.jupiter.api.Test;",
                db_imports + "import org.junit.jupiter.api.Test;"
            )

            testcontainers_annotation = f"""@TestcontainersPostgreSQL(
    network = Network(shared = true),
    mode = ContainerMode.PER_RUN,
    migration = Migration(
        engine = Migration.Engines.FLYWAY,
        apply = Migration.Mode.PER_METHOD,
        drop = Migration.Mode.PER_METHOD
    )
)
"""
            code = code.replace("class ${className}", testcontainers_annotation + "class ${className}")

            connection_field = """
        @ConnectionPostgreSQL
        private lateinit var connection: JdbcConnection
"""
            code = code.replace(
                "private val container = AppContainer.build()",
                connection_field + "        private val container = AppContainer.build()\n            .withNetwork(org.testcontainers.containers.Network.SHARED)"
            )

            old_setup = """@BeforeAll
        @JvmStatic
        fun setup() {
            // For applications with a DB, uncomment:
            // container.withEnv(mapOf(
            //     "DB_URL" to "jdbc:postgresql://localhost:5432/test",
            //     "DB_USER" to "postgres",
            //     "DB_PASS" to "postgres"
            // ))
            container.start()
        }"""
            
            new_setup = """@BeforeAll
        @JvmStatic
        fun setup() {
            val params = connection.paramsInNetwork().orElseThrow()
            container.withEnv(mapOf(
                "DB_URL" to params.jdbcUrl(),
                "DB_USER" to params.username(),
                "DB_PASS" to params.password(),
                "CACHE_MAX_SIZE" to "0"
            ))
            container.start()
        }"""
            
            code = code.replace(old_setup, new_setup)
    
    return code


def main():
    parser = argparse.ArgumentParser(
        description="Generator of black-box tests with RestAssured for Kora applications"
    )
    parser.add_argument(
        "--name",
        required=True,
        help="Test class name (e.g., PetApiTests)"
    )
    parser.add_argument(
        "--package",
        required=True,
        help="Java/Kotlin package (e.g., ru.tinkoff.kora.example)"
    )
    parser.add_argument(
        "--lang",
        choices=["java", "kotlin"],
        default="java",
        help="Language: java or kotlin (default: java)"
    )
    parser.add_argument(
        "--output",
        default=".",
        help="Output directory (default: current directory)"
    )
    parser.add_argument(
        "--entity",
        default="entity",
        help="Entity name for tests (default: entity)"
    )
    parser.add_argument(
        "--endpoint",
        default="/api/entities",
        help="API endpoint (default: /api/entities)"
    )
    parser.add_argument(
        "--with-db",
        action="store_true",
        help="Add PostgreSQL support via Testcontainers"
    )
    
    args = parser.parse_args()
    
    # Generate the code
    code = generate_test(
        name=args.name,
        package=args.package,
        lang=args.lang,
        entity=args.entity,
        endpoint=args.endpoint,
        with_db=args.with_db
    )
    
    # Determine the output file path
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    if args.lang == "java":
        filename = f"{args.name}.java"
    else:
        filename = f"{args.name}.kt"
    
    output_path = output_dir / filename
    
    # Write the file
    output_path.write_text(code)
    
    print(f"Created: {output_path}")
    print(f"\n📝 Next steps:")
    print(f"   1. Update endpoint paths in the test to match your API")
    print(f"   2. Update JSON bodies to match your DTOs")
    print(f"   3. Ensure AppContainer.java exists in src/test/java/{args.package.replace('.', '/')}/")
    if args.with_db:
        print(f"   4. Add testcontainers-extensions-postgres dependency to build.gradle")
    print(f"   5. Run tests: ./gradlew test --tests {args.package}.{args.name}")


if __name__ == "__main__":
    main()
