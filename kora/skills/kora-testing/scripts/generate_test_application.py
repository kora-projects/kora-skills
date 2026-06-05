#!/usr/bin/env python3
"""
Kora TestApplication Generator

Generates TestApplication templates for integration testing with database cleanup utilities.

Usage:
    python generate_test_application.py --name TestApplication --entity Pet --table pets --package ru.tinkoff.kora.example.crud --lang java
    python generate_test_application.py --name TestApplication --entity Pet --table pets --package ru.tinkoff.kora.example.crud --lang kotlin
"""

import argparse
import os
import sys
from pathlib import Path


def parse_args():
    parser = argparse.ArgumentParser(description='Generate Kora TestApplication')
    parser.add_argument('--name', default='TestApplication', help='Application interface name (e.g., TestApplication)')
    parser.add_argument('--entity', required=True, help='Entity class name (e.g., Pet)')
    parser.add_argument('--table', required=True, help='Database table name (e.g., pets)')
    parser.add_argument('--package', required=True, help='Package name (e.g., ru.tinkoff.kora.example.crud)')
    parser.add_argument('--lang', choices=['java', 'kotlin'], default='java', help='Language')
    parser.add_argument('--output', default='.', help='Output directory')
    return parser.parse_args()


def generate_java(name, entity, table, package):
    template = '''package {package};

import java.util.List;
import ru.tinkoff.kora.common.Component;
import ru.tinkoff.kora.common.KoraApp;
import ru.tinkoff.kora.common.annotation.Root;
import ru.tinkoff.kora.database.common.annotation.Query;
import ru.tinkoff.kora.database.common.annotation.Repository;
import ru.tinkoff.kora.database.jdbc.JdbcRepository;

/**
 * Test application that extends the main Application and adds test-only repositories
 * for database cleanup and test data setup.
 *
 * Purpose:
 * - Add deleteAll()/truncate() methods for test cleanup
 * - Add repositories from common modules not used in production
 * - Fast test utilities for setup/teardown operations
 *
 * IMPORTANT: Black-box testing is recommended as the primary approach.
 * Use TestApplication only for auxiliary test operations.
 *
 * Usage in tests:
 * @code
 * @KoraAppTest(TestApplication.class)
 * class MyIntegrationTest {{
 *     @TestComponent
 *     private Test{entity}Repository test{entity}Repository;
 *
 *     @BeforeEach
 *     void setUp() {{
 *         test{entity}Repository.deleteAll(); // Clean DB before test
 *     }}
 * }}
 * @endcode
 */
@KoraApp
public interface {name} extends Application {{

    /**
     * Test repository for {entity} entities.
     * Adds methods for cleaning up test data.
     */
    @Root
    @Component
    @Repository
    interface Test{entity}Repository extends JdbcRepository {{

        /**
         * Get all records from the table.
         *
         * @return list of all entities
         */
        @Query("SELECT %{{return#selects}} FROM %{{return#table}}")
        List<{entity}> findAll();

        /**
         * Delete all records from the table.
         * Used for cleaning up database between tests.
         */
        @Query("DELETE FROM {table}")
        void deleteAll();

        /**
         * Optional: Method to insert test data.
         * Uncomment and adapt to your schema.
         *
         * @param entity entity to insert
         * @return ID of inserted record
         */
        // @Query("INSERT INTO {table} (name, category_id) VALUES (:name, :categoryId) RETURNING id")
        // Long insert({entity} entity);
    }}
}}
'''
    return template.format(package=package, entity=entity, name=name, table=table)


def generate_kotlin(name, entity, table, package):
    template = '''package {package}

import ru.tinkoff.kora.common.Component
import ru.tinkoff.kora.common.KoraApp
import ru.tinkoff.kora.common.annotation.Root
import ru.tinkoff.kora.database.common.annotation.Query
import ru.tinkoff.kora.database.common.annotation.Repository
import ru.tinkoff.kora.database.jdbc.JdbcRepository

/**
 * Test application that extends the main Application and adds test-only repositories
 * for database cleanup and test data setup.
 *
 * Purpose:
 * - Add deleteAll()/truncate() methods for test cleanup
 * - Add repositories from common modules not used in production
 * - Fast test utilities for setup/teardown operations
 *
 * IMPORTANT: Black-box testing is recommended as the primary approach.
 * Use TestApplication only for auxiliary test operations.
 *
 * Usage in tests:
 * @code
 * @KoraAppTest(TestApplication::class)
 * class MyIntegrationTest {{
 *     @TestComponent
 *     private lateinit var test{entity}Repository: Test{entity}Repository
 *
 *     @BeforeEach
 *     fun setUp() {{
 *         test{entity}Repository.deleteAll() // Clean DB before test
 *     }}
 * }}
 * @endcode
 */
@KoraApp
interface {name} : Application {{

    /**
     * Test repository for {entity} entities.
     * Adds methods for cleaning up test data.
     */
    @Root
    @Component
    @Repository
    interface Test{entity}Repository : JdbcRepository {{

        /**
         * Get all records from the table.
         *
         * @return list of all entities
         */
        @Query("SELECT %{{return#selects}} FROM %{{return#table}}")
        fun findAll(): List<{entity}>

        /**
         * Delete all records from the table.
         * Used for cleaning up database between tests.
         */
        @Query("DELETE FROM {table}")
        fun deleteAll()

        /**
         * Optional: Method to insert test data.
         * Uncomment and adapt to your schema.
         *
         * @param entity entity to insert
         * @return ID of inserted record
         */
        // @Query("INSERT INTO {table} (name, category_id) VALUES (:name, :categoryId) RETURNING id")
        // fun insert(entity: {entity}): Long
    }}
}}
'''
    return template.format(package=package, entity=entity, name=name, table=table)


def main():
    args = parse_args()

    if args.lang == 'java':
        content = generate_java(args.name, args.entity, args.table, args.package)
        filename = f'{args.name}.java'
    else:
        content = generate_kotlin(args.name, args.entity, args.table, args.package)
        filename = f'{args.name}.kt'

    output_path = Path(args.output) / filename
    output_path.write_text(content)

    print(f'Generated: {output_path}')
    print(f'\nUsage in tests:')
    print(f'  @KoraAppTest({args.name}.class)  // Java')
    print(f'  @KoraAppTest({args.name}::class) // Kotlin')
    print(f'\nInject test repository:')
    print(f'  @TestComponent')
    print(f'  private Test{args.entity}Repository test{args.entity}Repository;')
    print(f'\nBUILD SETUP REQUIRED (add to build.gradle):')
    if args.lang == 'java':
        print('''
  compileJava {
      options.compilerArgs += [
          "-Akora.app.submodule.enabled=true"
      ]
  }

  dependencies {
      testAnnotationProcessor "ru.tinkoff.kora:annotation-processors"
  }

  test {
      exclude("**/$*")
  }''')
    else:
        print('''
  ksp {
      arg("kora.app.submodule.enabled", "true")
  }

  dependencies {
      kspTest("ru.tinkoff.kora:symbol-processors")
  }

  test {
      exclude("**/$*")
  }''')


if __name__ == '__main__':
    main()
