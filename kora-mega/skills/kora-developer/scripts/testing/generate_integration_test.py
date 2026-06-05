#!/usr/bin/env python3
"""
Kora Integration Test Generator

Generates integration test templates with Testcontainers.

Usage:
    python generate_integration_test.py --name UserRepositoryTest --repository UserRepository --entity User --database postgres --lang java
    python generate_integration_test.py --name UserRepositoryTest --repository UserRepository --entity User --database cassandra --lang kotlin
"""

import argparse
import os
import sys
from pathlib import Path


def parse_args():
    parser = argparse.ArgumentParser(description='Generate Kora integration test')
    parser.add_argument('--name', required=True, help='Test class name (e.g., UserRepositoryTest)')
    parser.add_argument('--repository', required=True, help='Repository class name (e.g., UserRepository)')
    parser.add_argument('--entity', required=True, help='Entity class name (e.g., User)')
    parser.add_argument('--database', choices=['postgres', 'cassandra'], default='postgres', help='Database type')
    parser.add_argument('--package', default='ru.tinkoff.kora.example', help='Package name')
    parser.add_argument('--lang', choices=['java', 'kotlin'], default='java', help='Language')
    parser.add_argument('--output', default='.', help='Output directory')
    return parser.parse_args()


def generate_java_postgres(name, repository, entity, package):
    repo_var = repository[0].lower() + repository[1:]
    entity_var = entity[0].lower() + entity[1:]
    
    return f'''package {package};

import static org.junit.jupiter.api.Assertions.*;

import io.goodforgod.testcontainers.extensions.ContainerMode;
import io.goodforgod.testcontainers.extensions.jdbc.*;
import org.jetbrains.annotations.NotNull;
import org.junit.jupiter.api.Test;
import ru.tinkoff.kora.test.extension.junit5.KoraAppTest;
import ru.tinkoff.kora.test.extension.junit5.KoraAppTestConfigModifier;
import ru.tinkoff.kora.test.extension.junit5.KoraConfigModification;
import ru.tinkoff.kora.test.extension.junit5.TestComponent;

@TestcontainersPostgreSQL(
    mode = ContainerMode.PER_RUN,
    migration = @Migration(
        engine = Migration.Engines.FLYWAY,
        apply = Migration.Mode.PER_METHOD,
        drop = Migration.Mode.PER_METHOD,
        locations = {{"db/migration"}}
    )
)
@KoraAppTest(Application.class)
class {name} implements KoraAppTestConfigModifier {{

    @ConnectionPostgreSQL
    private JdbcConnection connection;

    @TestComponent
    private {repository} {repo_var};

    @NotNull
    @Override
    public KoraConfigModification config() {{
        return KoraConfigModification.ofSystemProperty(
            "DB_JDBC_URL", connection.params().jdbcUrl()
        )
        .withSystemProperty("DB_USER", connection.params().username())
        .withSystemProperty("DB_PASS", connection.params().password());
    }}

    @Test
    void shouldSaveAndFind() {{
        // given
        var {entity_var} = new {entity}("test-data");

        // when
        {repo_var}.save({entity_var});
        var found = {repo_var}.findById({entity_var}.id());

        // then
        assertNotNull(found);
        assertEquals({entity_var}.data(), found.data());
    }}

    @Test
    void shouldDelete() {{
        // given
        var {entity_var} = new {entity}("test-data");
        {repo_var}.save({entity_var});

        // when
        {repo_var}.deleteById({entity_var}.id());
        var found = {repo_var}.findById({entity_var}.id());

        // then
        assertNull(found);
    }}
}}
'''


def generate_java_cassandra(name, repository, entity, package):
    repo_var = repository[0].lower() + repository[1:]
    entity_var = entity[0].lower() + entity[1:]
    
    return f'''package {package};

import static org.junit.jupiter.api.Assertions.*;

import io.goodforgod.testcontainers.extensions.ContainerMode;
import io.goodforgod.testcontainers.extensions.cassandra.*;
import org.jetbrains.annotations.NotNull;
import org.junit.jupiter.api.Test;
import ru.tinkoff.kora.test.extension.junit5.KoraAppTest;
import ru.tinkoff.kora.test.extension.junit5.KoraAppTestConfigModifier;
import ru.tinkoff.kora.test.extension.junit5.KoraConfigModification;
import ru.tinkoff.kora.test.extension.junit5.TestComponent;

@TestcontainersCassandra(
    mode = ContainerMode.PER_RUN,
    migration = @Migration(
        engine = Migration.Engines.SCRIPTS,
        apply = Migration.Mode.PER_METHOD,
        drop = Migration.Mode.PER_METHOD,
        locations = {{"migrations"}}
    )
)
@KoraAppTest(Application.class)
class {name} implements KoraAppTestConfigModifier {{

    @ConnectionCassandra
    private CassandraConnection connection;

    @TestComponent
    private {repository} {repo_var};

    @NotNull
    @Override
    public KoraConfigModification config() {{
        return KoraConfigModification.ofSystemProperty(
            "CASSANDRA_CONTACT_POINTS", connection.params().contactPoint()
        )
        .withSystemProperty("CASSANDRA_USER", connection.params().username())
        .withSystemProperty("CASSANDRA_PASS", connection.params().password())
        .withSystemProperty("CASSANDRA_KEYSPACE", connection.params().keyspace());
    }}

    @Test
    void shouldSaveAndFind() {{
        // given
        var {entity_var} = new {entity}("1", "test-data");

        // when
        {repo_var}.save({entity_var});
        var found = {repo_var}.findById("1");

        // then
        assertNotNull(found);
        assertEquals("test-data", found.data());
    }}
}}
'''


def generate_kotlin_postgres(name, repository, entity, package):
    repo_var = repository[0].lower() + repository[1:]
    entity_var = entity[0].lower() + entity[1:]
    
    return f'''package {package}

import io.goodforgod.testcontainers.extensions.ContainerMode
import io.goodforgod.testcontainers.extensions.jdbc.*
import org.junit.jupiter.api.Assertions.*
import org.junit.jupiter.api.Test
import ru.tinkoff.kora.test.extension.junit5.KoraAppTest
import ru.tinkoff.kora.test.extension.junit5.KoraAppTestConfigModifier
import ru.tinkoff.kora.test.extension.junit5.KoraConfigModification
import ru.tinkoff.kora.test.extension.junit5.TestComponent

@TestcontainersPostgreSQL(
    mode = ContainerMode.PER_RUN,
    migration = @Migration(
        engine = Migration.Engines.FLYWAY,
        apply = Migration.Mode.PER_METHOD,
        drop = Migration.Mode.PER_METHOD,
        locations = ["db/migration"]
    )
)
@KoraAppTest(Application::class)
class {name} : KoraAppTestConfigModifier {{

    @ConnectionPostgreSQL
    private lateinit var connection: JdbcConnection

    @TestComponent
    private lateinit var {repo_var}: {repository}

    override fun config(): KoraConfigModification {{
        return KoraConfigModification.ofSystemProperty(
            "DB_JDBC_URL", connection.params().jdbcUrl()
        )
            .withSystemProperty("DB_USER", connection.params().username())
            .withSystemProperty("DB_PASS", connection.params().password())
    }}

    @Test
    fun `should save and find`() {{
        // given
        val {entity_var} = {entity}("test-data")

        // when
        {repo_var}.save({entity_var})
        val found = {repo_var}.findById({entity_var}.id())

        // then
        assertNotNull(found)
        assertEquals({entity_var}.data(), found?.data())
    }}

    @Test
    fun `should delete`() {{
        // given
        val {entity_var} = {entity}("test-data")
        {repo_var}.save({entity_var})

        // when
        {repo_var}.deleteById({entity_var}.id())
        val found = {repo_var}.findById({entity_var}.id())

        // then
        assertNull(found)
    }}
}}
'''


def generate_kotlin_cassandra(name, repository, entity, package):
    repo_var = repository[0].lower() + repository[1:]
    entity_var = entity[0].lower() + entity[1:]
    
    return f'''package {package}

import io.goodforgod.testcontainers.extensions.ContainerMode
import io.goodforgod.testcontainers.extensions.cassandra.*
import org.junit.jupiter.api.Assertions.*
import org.junit.jupiter.api.Test
import ru.tinkoff.kora.test.extension.junit5.KoraAppTest
import ru.tinkoff.kora.test.extension.junit5.KoraAppTestConfigModifier
import ru.tinkoff.kora.test.extension.junit5.KoraConfigModification
import ru.tinkoff.kora.test.extension.junit5.TestComponent

@TestcontainersCassandra(
    mode = ContainerMode.PER_RUN,
    migration = @Migration(
        engine = Migration.Engines.SCRIPTS,
        apply = Migration.Mode.PER_METHOD,
        drop = Migration.Mode.PER_METHOD,
        locations = ["migrations"]
    )
)
@KoraAppTest(Application::class)
class {name} : KoraAppTestConfigModifier {{

    @ConnectionCassandra
    private lateinit var connection: CassandraConnection

    @TestComponent
    private lateinit var {repo_var}: {repository}

    override fun config(): KoraConfigModification {{
        return KoraConfigModification.ofSystemProperty(
            "CASSANDRA_CONTACT_POINTS", connection.params().contactPoint()
        )
            .withSystemProperty("CASSANDRA_USER", connection.params().username())
            .withSystemProperty("CASSANDRA_PASS", connection.params().password())
            .withSystemProperty("CASSANDRA_KEYSPACE", connection.params().keyspace())
    }}

    @Test
    fun `should save and find`() {{
        // given
        val {entity_var} = {entity}("1", "test-data")

        // when
        {repo_var}.save({entity_var})
        val found = {repo_var}.findById("1")

        // then
        assertNotNull(found)
        assertEquals("test-data", found?.data())
    }}
}}
'''


def main():
    args = parse_args()
    
    if args.lang == 'java':
        if args.database == 'postgres':
            content = generate_java_postgres(args.name, args.repository, args.entity, args.package)
        else:
            content = generate_java_cassandra(args.name, args.repository, args.entity, args.package)
        filename = f"{args.name}.java"
    else:
        if args.database == 'postgres':
            content = generate_kotlin_postgres(args.name, args.repository, args.entity, args.package)
        else:
            content = generate_kotlin_cassandra(args.name, args.repository, args.entity, args.package)
        filename = f"{args.name}.kt"
    
    output_path = Path(args.output) / filename
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(content)
    
    print(f"Generated: {output_path}")
    return 0


if __name__ == '__main__':
    sys.exit(main())
