#!/usr/bin/env python3
"""
Kora Component Test Generator

Generates component test templates with Mockito/MockK mocks.

Usage:
    python generate_component_test.py --name UserServiceTest --component UserService --dependency UserRepository --lang java
    python generate_component_test.py --name UserServiceTest --component UserService --dependency UserRepository --lang kotlin
"""

import argparse
import os
import sys
from pathlib import Path


def parse_args():
    parser = argparse.ArgumentParser(description='Generate Kora component test')
    parser.add_argument('--name', required=True, help='Test class name (e.g., UserServiceTest)')
    parser.add_argument('--component', required=True, help='Component class name (e.g., UserService)')
    parser.add_argument('--dependency', required=True, help='Dependency class name to mock (e.g., UserRepository)')
    parser.add_argument('--package', default='ru.tinkoff.kora.example', help='Package name')
    parser.add_argument('--lang', choices=['java', 'kotlin'], default='java', help='Language')
    parser.add_argument('--output', default='.', help='Output directory')
    return parser.parse_args()


def generate_java(name, component, dependency, package):
    component_var = component[0].lower() + component[1:]
    dependency_var = dependency[0].lower() + dependency[1:]
    
    return f'''package {package};

import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.ArgumentMatchers.*;
import static org.mockito.Mockito.*;

import org.jetbrains.annotations.NotNull;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.mockito.Mock;
import ru.tinkoff.kora.test.extension.junit5.KoraAppTest;
import ru.tinkoff.kora.test.extension.junit5.KoraAppTestConfigModifier;
import ru.tinkoff.kora.test.extension.junit5.KoraConfigModification;
import ru.tinkoff.kora.test.extension.junit5.TestComponent;

@KoraAppTest(Application.class)
class {name} implements KoraAppTestConfigModifier {{

    @Mock
    @TestComponent
    private {dependency} {dependency_var};

    @TestComponent
    private {component} {component_var};

    @NotNull
    @Override
    public KoraConfigModification config() {{
        return KoraConfigModification.ofString("""
            # Test configuration
            """);
    }}

    @BeforeEach
    void setup() {{
        // Setup mocks
        // when({dependency_var}.someMethod(any())).thenReturn(someValue);
    }}

    @Test
    void shouldDoSomething() {{
        // given
        // when
        // var result = {component_var}.doSomething();

        // then
        // assertNotNull(result);
        // verify({dependency_var}).someMethod(any());
    }}
}}
'''


def generate_kotlin(name, component, dependency, package):
    component_var = component[0].lower() + component[1:]
    dependency_var = dependency[0].lower() + dependency[1:]
    
    return f'''package {package}

import io.mockk.every
import io.mockk.mockk
import io.mockk.verify
import org.junit.jupiter.api.Assertions.*
import org.junit.jupiter.api.BeforeEach
import org.junit.jupiter.api.Test
import ru.tinkoff.kora.test.extension.junit5.KoraAppTest
import ru.tinkoff.kora.test.extension.junit5.KoraAppTestConfigModifier
import ru.tinkoff.kora.test.extension.junit5.KoraConfigModification
import ru.tinkoff.kora.test.extension.junit5.TestComponent

@KoraAppTest(Application::class)
class {name} : KoraAppTestConfigModifier {{

    @MockK
    @TestComponent
    private val {dependency_var}: {dependency} = mockk()

    @TestComponent
    private lateinit var {component_var}: {component}

    override fun config(): KoraConfigModification {{
        return KoraConfigModification.ofString(
            """
            # Test configuration
            """.trimIndent()
        )
    }}

    @BeforeEach
    fun setup() {{
        // Setup mocks
        // every {{ {dependency_var}.someMethod(any()) }} returns someValue
    }}

    @Test
    fun `should do something`() {{
        // given
        // when
        // val result = {component_var}.doSomething()

        // then
        // assertNotNull(result)
        // verify {{ {dependency_var}.someMethod(any()) }}
    }}
}}
'''


def main():
    args = parse_args()
    
    if args.lang == 'java':
        content = generate_java(args.name, args.component, args.dependency, args.package)
        filename = f"{args.name}.java"
    else:
        content = generate_kotlin(args.name, args.component, args.dependency, args.package)
        filename = f"{args.name}.kt"
    
    output_path = Path(args.output) / filename
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(content)
    
    print(f"Generated: {output_path}")
    return 0


if __name__ == '__main__':
    sys.exit(main())
