#!/usr/bin/env python3
"""
Kora Project Generator

Generates a new Kora framework project with proper structure, Gradle setup,
and base configuration files.

Usage:
    python generate_project.py --name my-app --package com.example
    python generate_project.py --name my-app --package com.example --lang kotlin
    python generate_project.py --name my-app --package com.example --multi-module
"""

import argparse
import os
import shutil
from pathlib import Path


def parse_args():
    parser = argparse.ArgumentParser(
        description="Generate a new Kora framework project"
    )
    parser.add_argument(
        "--name",
        required=True,
        help="Project name (e.g., my-app)"
    )
    parser.add_argument(
        "--package",
        required=True,
        help="Base package name (e.g., com.example)"
    )
    parser.add_argument(
        "--lang",
        choices=["java", "kotlin"],
        default="java",
        help="Programming language (default: java)"
    )
    parser.add_argument(
        "--multi-module",
        action="store_true",
        help="Create multi-module project structure"
    )
    parser.add_argument(
        "--output",
        default=".",
        help="Output directory (default: current directory)"
    )
    parser.add_argument(
        "--kora-version",
        default="1.2.15",
        help="Kora framework version (default: 1.2.15)"
    )
    return parser.parse_args()


def package_to_path(package: str) -> str:
    """Convert package name to directory path."""
    return os.path.join(*package.split("."))


def create_directory_structure(base_path: Path, package: str, multi_module: bool):
    """Create project directory structure."""
    package_path = package_to_path(package)

    if multi_module:
        # Multi-module structure
        modules = ["common", "app"]
        for module in modules:
            src_path = base_path / module / "src" / "main" / "java" / package_path / module.replace("-", "_")
            src_path.mkdir(parents=True, exist_ok=True)

            # Test directories
            test_path = base_path / module / "src" / "test" / "java" / package_path
            test_path.mkdir(parents=True, exist_ok=True)

            # Resources
            resources_path = base_path / module / "src" / "main" / "resources"
            resources_path.mkdir(parents=True, exist_ok=True)
    else:
        # Single-module structure
        src_path = base_path / "src" / "main" / "java" / package_path
        src_path.mkdir(parents=True, exist_ok=True)

        # Test directories
        test_path = base_path / "src" / "test" / "java" / package_path
        test_path.mkdir(parents=True, exist_ok=True)

        # Resources
        resources_path = base_path / "src" / "main" / "resources"
        resources_path.mkdir(parents=True, exist_ok=True)


def create_build_gradle(base_path: Path, lang: str, kora_version: str, package: str, multi_module: bool = False):
    """Create build.gradle file."""
    if lang == "kotlin":
        ext = ".kts"
    else:
        ext = ""

    if multi_module:
        # Root build.gradle for multi-module project
        content = f'''// Root build.gradle for multi-module Kora project
// See: https://github.com/kora-projects/kora-docs

subprojects {{
    apply plugin: "java"

    configurations {{
        koraBom
        annotationProcessor.extendsFrom(koraBom)
        compileOnly.extendsFrom(koraBom)
        implementation.extendsFrom(koraBom)
        api.extendsFrom(koraBom)
    }}

    dependencies {{
        koraBom platform("ru.tinkoff.kora:kora-parent:{kora_version}")
        annotationProcessor "ru.tinkoff.kora:annotation-processors"
    }}

    java {{
        sourceCompatibility = JavaVersion.VERSION_25
        targetCompatibility = JavaVersion.VERSION_25
    }}

    compileJava {{
        options.encoding("UTF-8")
        options.incremental(true)
        options.fork = false
    }}
}}
'''
    else:
        # Single-module build.gradle
        content = f'''plugins {{
    id "java"
    id "application"
}}

configurations {{
    koraBom
    annotationProcessor.extendsFrom(koraBom)
    compileOnly.extendsFrom(koraBom)
    implementation.extendsFrom(koraBom)
    api.extendsFrom(koraBom)
}}

dependencies {{
    koraBom platform("ru.tinkoff.kora:kora-parent:{kora_version}")
    annotationProcessor "ru.tinkoff.kora:annotation-processors"

    // Basic dependencies
    implementation "ru.tinkoff.kora:logging-logback"
    implementation "ru.tinkoff.kora:config-hocon"

    // Add more dependencies as needed:
    // implementation "ru.tinkoff.kora:database-jdbc"
    // implementation "ru.tinkoff.kora:validation-module"
    // implementation "ru.tinkoff.kora:micrometer-module"
}}

java {{
    sourceCompatibility = JavaVersion.VERSION_25
    targetCompatibility = JavaVersion.VERSION_25
}}

application {{
    applicationName = "application"
    mainClass = "{package}.Application"
    applicationDefaultJvmArgs = ["-Dfile.encoding=UTF-8"]
}}

compileJava {{
    options.encoding("UTF-8")
    options.incremental(true)
    options.fork = false
}}
'''

    build_file = base_path / f"build.gradle{ext}"
    build_file.write_text(content)


def create_settings_gradle(base_path: Path, name: str, multi_module: bool, lang: str):
    """Create settings.gradle file."""
    if lang == "kotlin":
        ext = ".kts"
    else:
        ext = ""

    if multi_module:
        content = f'''rootProject.name = "{name}"

include "common"
include "app"
'''
    else:
        content = f'''rootProject.name = "{name}"
'''

    settings_file = base_path / f"settings.gradle{ext}"
    settings_file.write_text(content)


def create_gradle_properties(base_path: Path, kora_version: str):
    """Create gradle.properties file."""
    content = f'''# Kora Framework Version
koraVersion={kora_version}

# Gradle settings
org.gradle.jvmargs=-Xmx2048m
org.gradle.parallel=true
org.gradle.caching=true
'''

    props_file = base_path / "gradle.properties"
    props_file.write_text(content)


def create_application_java(base_path: Path, package: str, lang: str, multi_module: bool):
    """Create Application.java or Application.kt file."""
    package_path = package_to_path(package)

    if multi_module:
        # Application in app module
        if lang == "kotlin":
            app_path = base_path / "app" / "src" / "main" / "java" / package_path / "Application.kt"
            content = f'''package {package}

import ru.tinkoff.kora.application.graph.ApplicationGraph
import ru.tinkoff.kora.application.KoraApplication

@KoraApp
interface Application {{
    companion object {{
        @JvmStatic
        fun main(args: Array<String>) {{
            KoraApplication.run(ApplicationGraph::graph)
        }}
    }}
}}
'''
        else:
            app_path = base_path / "app" / "src" / "main" / "java" / package_path / "Application.java"
            content = f'''package {package};

import ru.tinkoff.kora.application.graph.ApplicationGraph;
import ru.tinkoff.kora.application.KoraApplication;

@KoraApp
public interface Application {{
    static void main(String[] args) {{
        KoraApplication.run(ApplicationGraph::graph);
    }}
}}
'''
    else:
        # Application in root module
        if lang == "kotlin":
            app_path = base_path / "src" / "main" / "java" / package_path / "Application.kt"
            content = f'''package {package}

import ru.tinkoff.kora.application.graph.ApplicationGraph
import ru.tinkoff.kora.application.KoraApplication

@KoraApp
interface Application {{
    companion object {{
        @JvmStatic
        fun main(args: Array<String>) {{
            KoraApplication.run(ApplicationGraph::graph)
        }}
    }}
}}
'''
        else:
            app_path = base_path / "src" / "main" / "java" / package_path / "Application.java"
            content = f'''package {package};

import ru.tinkoff.kora.application.graph.ApplicationGraph;
import ru.tinkoff.kora.application.KoraApplication;

@KoraApp
public interface Application {{
    static void main(String[] args) {{
        KoraApplication.run(ApplicationGraph::graph);
    }}
}}
'''

    app_path.parent.mkdir(parents=True, exist_ok=True)
    app_path.write_text(content)


def create_application_conf(base_path: Path, multi_module: bool):
    """Create application.conf configuration file."""
    content = '''# Kora Application Configuration (HOCON format)
# See: https://github.com/kora-projects/kora-docs

# Application settings
app {
    name = ${APP_NAME:-my-app}
    version = ${APP_VERSION:-1.0.0}
    environment = ${APP_ENV:-development}
}

# Logging configuration
logging {
    level = ${LOG_LEVEL:-INFO}

    # Console appender
    console {
        enabled = true
        pattern = "%d{{HH:mm:ss.SSS}} [%thread] %-5level %logger{{36}} - %msg%n"
    }
}

# HTTP Server configuration (uncomment when using http-server module)
# kora {
#     http {
#         server {
#             publicApiHttpPort = ${HTTP_PORT:-8080}
#             publicApiHttpHost = "0.0.0.0"
#         }
#     }
# }

# Database configuration (uncomment when using database-jdbc module)
# database {
#     url = ${DATABASE_URL:-jdbc:postgresql://localhost:5432/mydb}
#     username = ${DATABASE_USERNAME:-postgres}
#     password = ${DATABASE_PASSWORD:-postgres}
#     pool-size = 10
# }
'''

    if multi_module:
        conf_path = base_path / "app" / "src" / "main" / "resources" / "application.conf"
    else:
        conf_path = base_path / "src" / "main" / "resources" / "application.conf"

    conf_path.parent.mkdir(parents=True, exist_ok=True)
    conf_path.write_text(content)


def create_logback_xml(base_path: Path, multi_module: bool):
    """Create logback.xml configuration file."""
    content = '''<?xml version="1.0" encoding="UTF-8"?>
<configuration>
    <appender name="CONSOLE" class="ch.qos.logback.core.ConsoleAppender">
        <encoder>
            <pattern>%d{HH:mm:ss.SSS} [%thread] %-5level %logger{36} - %msg%n</pattern>
        </encoder>
    </appender>

    <root level="INFO">
        <appender-ref ref="CONSOLE"/>
    </root>

    <!-- Application logger -->
    <logger name="com.example" level="DEBUG"/>

    <!-- Kora framework logger -->
    <logger name="ru.tinkoff.kora" level="INFO"/>
</configuration>
'''

    if multi_module:
        xml_path = base_path / "app" / "src" / "main" / "resources" / "logback.xml"
    else:
        xml_path = base_path / "src" / "main" / "resources" / "logback.xml"

    xml_path.parent.mkdir(parents=True, exist_ok=True)
    xml_path.write_text(content)


def create_gitignore(base_path: Path):
    """Create .gitignore file."""
    content = '''# Compiled class files
*.class

# Log files
*.log

# Package files
*.jar
*.war
*.ear
*.nar

# Gradle
.gradle/
build/
!gradle-wrapper.jar
!**/src/main/**/build/
!**/src/test/**/build/

# IDE
.idea/
*.iml
*.iws
*.ipr
.vscode/
.settings/
.project
.classpath

# Kora generated files
**/*Graph.java
**/*Graph.kt

# Environment
.env
.env.local
.env.*.local

# OS
.DS_Store
Thumbs.db
'''

    gitignore = base_path / ".gitignore"
    gitignore.write_text(content)


def create_readme(base_path: Path, name: str, package: str, multi_module: bool):
    """Create README.md file."""
    pkg_path = package_to_path(package)

    if multi_module:
        structure = f"""```
{name}
├── common/          # Shared types and utilities
│   ├── build.gradle
│   └── src/main/java/{pkg_path}/common/
├── app/             # Application assembly
│   ├── build.gradle
│   └── src/main/java/{pkg_path}/
├── build.gradle     # Root build configuration
├── settings.gradle  # Module includes
└── gradle.properties
```"""
        arch_title = "### Multi-Module Architecture"
    else:
        structure = f"""```
{name}
├── src/
│   ├── main/
│   │   ├── java/{pkg_path}/
│   │   │   └── Application.java
│   │   └── resources/
│   │       ├── application.conf
│   │       └── logback.xml
│   └── test/
│       └── java/{pkg_path}/
├── build.gradle
├── settings.gradle
└── gradle.properties
```"""
        arch_title = "### Single-Module Architecture"

    content = f"""# {name}

Kora framework application.

## Project Structure

{arch_title}

{structure}

## Getting Started

### Prerequisites

- Java 25 or higher
- Gradle 8.x

### Build

```bash
./gradlew clean build
```

### Run

```bash
./gradlew run
```

### Configuration

Edit `src/main/resources/application.conf` (or `app/src/main/resources/application.conf` for multi-module) to configure the application.

Environment variables can be used:
```hocon
app {{
    name = ${{APP_NAME:-my-app}}
    version = ${{APP_VERSION:-1.0.0}}
}}
```

## Kora Documentation

- [Kora Framework Docs](https://github.com/kora-projects/kora-docs)
- [Kora Examples](https://github.com/kora-projects/kora-examples)

"""

    readme = base_path / "README.md"
    readme.write_text(content)


def create_gradle_wrapper(base_path: Path, assets_dir: Path):
    """Create Gradle wrapper files from template."""
    wrapper_dir = base_path / "gradle" / "wrapper"
    wrapper_dir.mkdir(parents=True, exist_ok=True)

    # gradle-wrapper.properties from template
    template = assets_dir / "gradle-wrapper.properties.template"
    if template.exists():
        content = template.read_text()
    else:
        content = '''distributionBase=GRADLE_USER_HOME
distributionPath=wrapper/dists
distributionUrl=https\\://services.gradle.org/distributions/gradle-9.5.1-bin.zip
networkTimeout=10000
validateDistributionUrl=true
zipStoreBase=GRADLE_USER_HOME
zipStorePath=wrapper/dists
'''
    properties = wrapper_dir / "gradle-wrapper.properties"
    properties.write_text(content)


def main():
    args = parse_args()

    base_path = Path(args.output) / args.name
    assets_dir = Path(__file__).parent.parent / "assets"

    # Check if directory exists
    if base_path.exists():
        print(f"Error: Directory {base_path} already exists")
        return 1

    # Create directory structure
    base_path.mkdir(parents=True, exist_ok=True)
    print(f"✓ Created project directory: {base_path}")

    # Create structure
    create_directory_structure(base_path, args.package, args.multi_module)
    print(f"✓ Created source directories")

    # Create Gradle files
    create_build_gradle(base_path, args.lang, args.kora_version, args.package, args.multi_module)
    print(f"✓ Created build.gradle")

    create_settings_gradle(base_path, args.name, args.multi_module, args.lang)
    print(f"✓ Created settings.gradle")

    create_gradle_properties(base_path, args.kora_version)
    print(f"✓ Created gradle.properties")

    create_gradle_wrapper(base_path, assets_dir)
    print(f"✓ Created gradle wrapper")

    # Create Application file
    create_application_java(base_path, args.package, args.lang, args.multi_module)
    print(f"✓ Created Application.{args.lang}")

    # Create configuration files
    create_application_conf(base_path, args.multi_module)
    print(f"✓ Created application.conf")

    create_logback_xml(base_path, args.multi_module)
    print(f"✓ Created logback.xml")

    # Create .gitignore
    create_gitignore(base_path)
    print(f"✓ Created .gitignore")

    # Create README
    create_readme(base_path, args.name, args.package, args.multi_module)
    print(f"✓ Created README.md")

    print(f"\nProject '{args.name}' created successfully!")
    print(f"\nNext steps:")
    print(f"  cd {args.name}")
    print(f"  ./gradlew clean build")
    print(f"  ./gradlew run")

    return 0


if __name__ == "__main__":
    exit(main())
