#!/usr/bin/env python3
"""
Kora 2.x Project Generator

Scaffolds a Kora Framework 2.x project (group io.koraframework, BOM io.koraframework:kora-bom)
with a working @KoraApp graph, the mandatory annotation/symbol processor wiring, and Java 25
toolchain settings.

Usage:
    python3 generate_project.py --name my-app --package com.example --dry-run
    python3 generate_project.py --name my-app --package com.example
    python3 generate_project.py --name my-app --package com.example --lang kotlin
    python3 generate_project.py --name my-app --package com.example --multi-module

--dry-run prints every file that would be written, with its full content, and touches nothing.
Re-running over an existing directory is refused unless --force is given.
"""

import argparse
import os
import sys
from pathlib import Path
from typing import Dict

DEFAULT_KORA_VERSION = "2.0.0.RC2"
GRADLE_DISTRIBUTION = "gradle-9.8.0-bin.zip"
JAVA_TOOLCHAIN = 25
KOTLIN_PLUGIN_VERSION = "2.4.20"
KSP_PLUGIN_VERSION = "2.3.12"


def parse_args():
    parser = argparse.ArgumentParser(
        description="Generate a Kora Framework 2.x project skeleton"
    )
    parser.add_argument("--name", required=True, help="Project name (e.g. my-app)")
    parser.add_argument("--package", required=True, help="Base package (e.g. com.example)")
    parser.add_argument(
        "--lang", choices=["java", "kotlin"], default="java",
        help="Source language (default: java)"
    )
    parser.add_argument(
        "--multi-module", action="store_true",
        help="Multi-module layout: common (@KoraSubmodule) + app (@KoraApp)"
    )
    parser.add_argument("--output", default=".", help="Output directory (default: .)")
    parser.add_argument(
        "--kora-version", default=DEFAULT_KORA_VERSION,
        help=f"Kora version (default: {DEFAULT_KORA_VERSION})"
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Print what would be written and exit without touching the filesystem"
    )
    parser.add_argument(
        "--force", action="store_true",
        help="Overwrite files in an existing output directory"
    )
    return parser.parse_args()


def package_to_path(package: str) -> str:
    return os.path.join(*package.split("."))


def source_root(lang: str) -> str:
    """Kotlin sources belong in src/main/kotlin, not src/main/java."""
    return "kotlin" if lang == "kotlin" else "java"


# --------------------------------------------------------------------------------------
# Build files
# --------------------------------------------------------------------------------------

def build_gradle_java_single(package: str) -> str:
    return f'''plugins {{
    id "java"
    id "application"
}}

repositories {{
    mavenCentral()
}}

configurations {{
    koraBom
    annotationProcessor.extendsFrom(koraBom)
    compileOnly.extendsFrom(koraBom)
    implementation.extendsFrom(koraBom)
    testImplementation.extendsFrom(koraBom)
    testAnnotationProcessor.extendsFrom(koraBom)
}}

dependencies {{
    koraBom platform("io.koraframework:kora-bom:$koraVersion")

    // Mandatory: without it ApplicationGraph is never generated
    annotationProcessor "io.koraframework:annotation-processors"

    implementation "io.koraframework:config-hocon"
    implementation "io.koraframework:logging-logback"

    testAnnotationProcessor "io.koraframework:annotation-processors"
    testImplementation "io.koraframework:test-junit5"
}}

java {{
    toolchain {{
        languageVersion = JavaLanguageVersion.of({JAVA_TOOLCHAIN})
        vendor = JvmVendorSpec.ADOPTIUM
    }}
}}

application {{
    applicationName = "application"
    mainClass = "{package}.Application"
    applicationDefaultJvmArgs = ["-Dfile.encoding=UTF-8"]
}}

distTar {{
    archiveFileName = "application.tar"
}}

tasks.withType(JavaCompile).configureEach {{
    options.encoding = "UTF-8"
}}

test {{
    useJUnitPlatform()
    testLogging {{
        events "passed", "skipped", "failed"
        showStandardStreams = true
        exceptionFormat = "full"
    }}
}}
'''


def build_gradle_java_root() -> str:
    return f'''// Root build for a multi-module Kora 2.x project.
// Declaring the processor here is what guarantees every subproject generates its
// <Name>SubmoduleImpl companion.

subprojects {{
    apply plugin: "java"

    repositories {{
        mavenCentral()
    }}

    configurations {{
        koraBom
        annotationProcessor.extendsFrom(koraBom)
        compileOnly.extendsFrom(koraBom)
        implementation.extendsFrom(koraBom)
        testImplementation.extendsFrom(koraBom)
        testAnnotationProcessor.extendsFrom(koraBom)
    }}

    dependencies {{
        koraBom platform("io.koraframework:kora-bom:$koraVersion")
        annotationProcessor "io.koraframework:annotation-processors"
        testAnnotationProcessor "io.koraframework:annotation-processors"
    }}

    java {{
        toolchain {{
            languageVersion = JavaLanguageVersion.of({JAVA_TOOLCHAIN})
            vendor = JvmVendorSpec.ADOPTIUM
        }}
    }}

    tasks.withType(JavaCompile).configureEach {{
        options.encoding = "UTF-8"
    }}

    test {{
        useJUnitPlatform()
    }}
}}
'''


def build_gradle_java_common() -> str:
    return '''plugins {
    id "java-library"
}

dependencies {
    // Just the Kora annotations. Use `api` for anything the @KoraSubmodule interface extends,
    // so the assembly project can see those types.
    api "io.koraframework:common"
}
'''


def build_gradle_java_app(package: str) -> str:
    return f'''plugins {{
    id "application"
}}

dependencies {{
    implementation project(":common")

    implementation "io.koraframework:config-hocon"
    implementation "io.koraframework:logging-logback"

    testImplementation "io.koraframework:test-junit5"
}}

application {{
    applicationName = "application"
    mainClass = "{package}.Application"
    applicationDefaultJvmArgs = ["-Dfile.encoding=UTF-8"]
}}

distTar {{
    archiveFileName = "application.tar"
}}
'''


def build_gradle_kts_single(package: str) -> str:
    return f'''plugins {{
    kotlin("jvm") version "{KOTLIN_PLUGIN_VERSION}"
    id("com.google.devtools.ksp") version "{KSP_PLUGIN_VERSION}"
    id("application")
}}

repositories {{
    mavenCentral()
}}

val koraVersion: String by project

dependencies {{
    implementation(platform("io.koraframework:kora-bom:$koraVersion"))

    // Mandatory. The ksp configuration is not covered by the BOM platform, so this needs
    // an explicit version.
    ksp("io.koraframework:symbol-processors:$koraVersion")

    implementation("io.koraframework:config-hocon")
    implementation("io.koraframework:logging-logback")

    kspTest("io.koraframework:symbol-processors:$koraVersion")
    testImplementation("io.koraframework:test-junit5")
}}

kotlin {{
    jvmToolchain {{
        languageVersion.set(JavaLanguageVersion.of({JAVA_TOOLCHAIN}))
        vendor.set(JvmVendorSpec.ADOPTIUM)
    }}
    sourceSets.main {{ kotlin.srcDir("build/generated/ksp/main/kotlin") }}
    sourceSets.test {{ kotlin.srcDir("build/generated/ksp/test/kotlin") }}
}}

application {{
    applicationName = "application"
    // A top-level `fun main()` compiles into <package>.ApplicationKt
    mainClass.set("{package}.ApplicationKt")
    applicationDefaultJvmArgs = listOf("-Dfile.encoding=UTF-8")
}}

tasks.distTar {{
    archiveFileName.set("application.tar")
}}

tasks.test {{
    useJUnitPlatform()
}}
'''


def build_gradle_kts_root() -> str:
    return f'''// Root build for a multi-module Kora 2.x Kotlin project.
// Declaring the KSP processor here is what guarantees every subproject generates its
// <Name>SubmoduleImpl companion.

plugins {{
    kotlin("jvm") version "{KOTLIN_PLUGIN_VERSION}" apply false
    id("com.google.devtools.ksp") version "{KSP_PLUGIN_VERSION}" apply false
}}

subprojects {{
    apply(plugin = "org.jetbrains.kotlin.jvm")
    apply(plugin = "com.google.devtools.ksp")

    repositories {{
        mavenCentral()
    }}

    pluginManager.withPlugin("org.jetbrains.kotlin.jvm") {{
        configure<org.jetbrains.kotlin.gradle.dsl.KotlinProjectExtension> {{
            jvmToolchain {{
                languageVersion.set(JavaLanguageVersion.of({JAVA_TOOLCHAIN}))
                vendor.set(JvmVendorSpec.ADOPTIUM)
            }}
            sourceSets.named("main") {{ kotlin.srcDir("build/generated/ksp/main/kotlin") }}
            sourceSets.named("test") {{ kotlin.srcDir("build/generated/ksp/test/kotlin") }}
        }}
    }}

    dependencies {{
        add("implementation", platform("io.koraframework:kora-bom:${{property("koraVersion")}}"))
        add("ksp", "io.koraframework:symbol-processors:${{property("koraVersion")}}")
        add("kspTest", "io.koraframework:symbol-processors:${{property("koraVersion")}}")
        add("testImplementation", "io.koraframework:test-junit5")
    }}

    tasks.withType<Test>().configureEach {{
        useJUnitPlatform()
    }}
}}
'''


def build_gradle_kts_common() -> str:
    return '''plugins {
    id("java-library")
}

dependencies {
    // Just the Kora annotations. Use `api` for anything the @KoraSubmodule interface extends,
    // so the assembly project can see those types.
    api("io.koraframework:common")
}
'''


def build_gradle_kts_app(package: str) -> str:
    return f'''plugins {{
    id("application")
}}

dependencies {{
    implementation(project(":common"))

    implementation("io.koraframework:config-hocon")
    implementation("io.koraframework:logging-logback")
}}

application {{
    applicationName = "application"
    mainClass.set("{package}.ApplicationKt")
    applicationDefaultJvmArgs = listOf("-Dfile.encoding=UTF-8")
}}

tasks.distTar {{
    archiveFileName.set("application.tar")
}}
'''


def settings_gradle(name: str, multi_module: bool, lang: str) -> str:
    quote = '"'
    header = f"rootProject.name = {quote}{name}{quote}\n"
    if not multi_module:
        return header
    if lang == "kotlin":
        return header + '\ninclude(":common")\ninclude(":app")\n'
    return header + '\ninclude ":common"\ninclude ":app"\n'


def gradle_properties(kora_version: str) -> str:
    return f'''# Kora framework version — the same value for every Kora dependency.
koraVersion={kora_version}

org.gradle.parallel=true
org.gradle.caching=true
'''


def gradle_wrapper_properties(assets_dir: Path) -> str:
    template = assets_dir / "gradle-wrapper.properties.template"
    if template.exists():
        return template.read_text()
    return f'''distributionBase=GRADLE_USER_HOME
distributionPath=wrapper/dists
distributionUrl=https\\://services.gradle.org/distributions/{GRADLE_DISTRIBUTION}
networkTimeout=10000
validateDistributionUrl=true
zipStoreBase=GRADLE_USER_HOME
zipStorePath=wrapper/dists
'''


# --------------------------------------------------------------------------------------
# Sources
# --------------------------------------------------------------------------------------

def application_java(package: str, extra_supertype: str = "") -> str:
    supertypes = "\n        HoconConfigModule,\n        LogbackModule"
    imports = ""
    if extra_supertype:
        supertypes = f"\n        {extra_supertype},{supertypes}"
    return f'''package {package};

import io.koraframework.application.graph.KoraApplication;
import io.koraframework.common.annotation.KoraApp;
import io.koraframework.config.hocon.HoconConfigModule;
import io.koraframework.logging.logback.LogbackModule;
{imports}
/**
 * Kora 2.x application graph.
 *
 * <p>ApplicationGraph is generated by the annotation processor into THIS package — it is never
 * imported from io.koraframework. Modules shipped as artifacts must be listed in extends;
 * a @Module interface compiled in this same Gradle module is discovered automatically.
 */
@KoraApp
public interface Application extends{supertypes} {{

    static void main(String[] args) {{
        KoraApplication.run(ApplicationGraph::graph);
    }}
}}
'''


def application_kotlin(package: str, extra_supertype: str = "") -> str:
    supertypes = "HoconConfigModule, LogbackModule"
    if extra_supertype:
        supertypes = f"{extra_supertype}, {supertypes}"
    return f'''package {package}

import io.koraframework.application.graph.KoraApplication
import io.koraframework.common.annotation.KoraApp
import io.koraframework.config.hocon.HoconConfigModule
import io.koraframework.logging.logback.LogbackModule

/**
 * Kora 2.x application graph.
 *
 * ApplicationGraph is generated by the symbol processor into THIS package — it is never imported
 * from io.koraframework. `application {{ mainClass }}` must point at <package>.ApplicationKt.
 */
@KoraApp
interface Application : {supertypes}

fun main() {{
    KoraApplication.run(ApplicationGraph::graph)
}}
'''


def common_module_java(package: str) -> str:
    return f'''package {package}.common;

import io.koraframework.common.annotation.KoraSubmodule;

/**
 * Exports every @Component and @Module provider compiled in this Gradle subproject.
 *
 * <p>The processor generates CommonModuleSubmoduleImpl next to this interface; the assembly
 * project's @KoraApp extends CommonModule and picks the companion up automatically. An empty
 * body is normal — the interface is only the handle.
 */
@KoraSubmodule
public interface CommonModule {{
}}
'''


def common_module_kotlin(package: str) -> str:
    return f'''package {package}.common

import io.koraframework.common.annotation.KoraSubmodule

/**
 * Exports every @Component and @Module provider compiled in this Gradle subproject.
 *
 * The processor generates CommonModuleSubmoduleImpl next to this interface; the assembly
 * project's @KoraApp extends CommonModule and picks the companion up automatically. An empty
 * body is normal — the interface is only the handle.
 */
@KoraSubmodule
interface CommonModule
'''


def application_conf(package: str) -> str:
    return f'''# Kora 2.x configuration — HOCON, loaded by HoconConfigModule from application.conf.

logging {{
  levels {{
    "ROOT": "WARN"
    "{package}": "INFO"
    "io.koraframework": "INFO"
  }}
}}

# Environment substitution:
#   ${{VAR}}   required — startup fails if unset
#   ${{?VAR}}  optional — the key is left unset if absent
'''


def logback_xml(package: str) -> str:
    return f'''<?xml version="1.0" encoding="UTF-8"?>
<configuration>
    <appender name="CONSOLE" class="ch.qos.logback.core.ConsoleAppender">
        <encoder>
            <pattern>%d{{HH:mm:ss.SSS}} [%thread] %-5level %logger{{36}} - %msg%n</pattern>
        </encoder>
    </appender>

    <root level="INFO">
        <appender-ref ref="CONSOLE"/>
    </root>

    <logger name="{package}" level="DEBUG"/>
    <logger name="io.koraframework" level="INFO"/>
</configuration>
'''


def gitignore() -> str:
    return '''*.class
*.log

.gradle/
build/
!gradle/wrapper/gradle-wrapper.jar

.idea/
*.iml
.vscode/

.env
.DS_Store
'''


def readme(name: str, package: str, lang: str, multi_module: bool, kora_version: str) -> str:
    src = source_root(lang)
    pkg_path = package_to_path(package)
    main_file = "Application.kt" if lang == "kotlin" else "Application.java"
    generated = ("build/generated/ksp/main/kotlin/" if lang == "kotlin"
                 else "build/generated/sources/annotationProcessor/java/main/")

    if multi_module:
        tree = f'''```
{name}
├── common/                          # @KoraSubmodule — shared components
│   └── src/main/{src}/{pkg_path}/common/CommonModule.{ 'kt' if lang == 'kotlin' else 'java' }
├── app/                             # @KoraApp — assembly and entry point
│   └── src/main/{src}/{pkg_path}/{main_file}
├── build.gradle{'.kts' if lang == 'kotlin' else ''}
├── settings.gradle{'.kts' if lang == 'kotlin' else ''}
└── gradle.properties
```'''
    else:
        tree = f'''```
{name}
├── src/main/{src}/{pkg_path}/{main_file}
├── src/main/resources/{{application.conf, logback.xml}}
├── build.gradle{'.kts' if lang == 'kotlin' else ''}
├── settings.gradle{'.kts' if lang == 'kotlin' else ''}
└── gradle.properties
```'''

    return f'''# {name}

Kora Framework {kora_version} service ({lang.capitalize()}).

## Structure

{tree}

## Prerequisites

- **JDK 25 or newer** — Kora 2.0 artifacts are Java 25 class files
- Gradle wrapper (included)

## Build and run

```bash
./gradlew classes      # runs the processor and generates ApplicationGraph
./gradlew build
./gradlew run
```

## Generated code

The dependency graph is generated as `{package}.ApplicationGraph` under:

```
{generated}
```

Never edit it. After renaming a package, regenerate:

```bash
./gradlew clean classes --no-build-cache
```

## Adding a module

Modules that arrive as artifacts must be named in the `@KoraApp` supertype list; a `@Module`
interface compiled in this same Gradle module is discovered automatically.

```
implementation "io.koraframework:json-common"           // JsonModule
implementation "io.koraframework:database-jdbc"         // JdbcDatabaseModule
implementation "io.koraframework:http-server-undertow"  // UndertowPublicHttpServerModule
```

## Configuration

`src/main/resources/application.conf` is read by `HoconConfigModule`.
'''


# --------------------------------------------------------------------------------------
# Plan construction
# --------------------------------------------------------------------------------------

def build_plan(args, assets_dir: Path) -> Dict[str, str]:
    """Return {relative path -> content} for every file the run would create."""
    package = args.package
    pkg_path = package_to_path(package)
    lang = args.lang
    src = source_root(lang)
    kts = ".kts" if lang == "kotlin" else ""
    ext = "kt" if lang == "kotlin" else "java"

    files: Dict[str, str] = {
        f"settings.gradle{kts}": settings_gradle(args.name, args.multi_module, lang),
        "gradle.properties": gradle_properties(args.kora_version),
        "gradle/wrapper/gradle-wrapper.properties": gradle_wrapper_properties(assets_dir),
        ".gitignore": gitignore(),
        "README.md": readme(args.name, package, lang, args.multi_module, args.kora_version),
    }

    if args.multi_module:
        if lang == "kotlin":
            files[f"build.gradle{kts}"] = build_gradle_kts_root()
            files[f"common/build.gradle{kts}"] = build_gradle_kts_common()
            files[f"app/build.gradle{kts}"] = build_gradle_kts_app(package)
            files[f"common/src/main/{src}/{pkg_path}/common/CommonModule.{ext}"] = \
                common_module_kotlin(package)
            files[f"app/src/main/{src}/{pkg_path}/Application.{ext}"] = \
                application_kotlin(package, "CommonModule")
        else:
            files[f"build.gradle{kts}"] = build_gradle_java_root()
            files[f"common/build.gradle{kts}"] = build_gradle_java_common()
            files[f"app/build.gradle{kts}"] = build_gradle_java_app(package)
            files[f"common/src/main/{src}/{pkg_path}/common/CommonModule.{ext}"] = \
                common_module_java(package)
            files[f"app/src/main/{src}/{pkg_path}/Application.{ext}"] = \
                application_java(package, "CommonModule")

        # The @KoraApp imports the submodule from a sibling package
        app_key = f"app/src/main/{src}/{pkg_path}/Application.{ext}"
        import_line = f"import {package}.common.CommonModule;" if lang == "java" \
            else f"import {package}.common.CommonModule"
        files[app_key] = files[app_key].replace(
            "import io.koraframework.logging.logback.LogbackModule" + (";" if lang == "java" else ""),
            "import io.koraframework.logging.logback.LogbackModule"
            + (";" if lang == "java" else "") + "\n" + import_line,
        )

        files[f"app/src/main/resources/application.conf"] = application_conf(package)
        files[f"app/src/main/resources/logback.xml"] = logback_xml(package)
        files[f"common/src/test/{src}/{pkg_path}/common/.gitkeep"] = ""
        files[f"app/src/test/{src}/{pkg_path}/.gitkeep"] = ""
    else:
        if lang == "kotlin":
            files[f"build.gradle{kts}"] = build_gradle_kts_single(package)
            files[f"src/main/{src}/{pkg_path}/Application.{ext}"] = application_kotlin(package)
        else:
            files[f"build.gradle{kts}"] = build_gradle_java_single(package)
            files[f"src/main/{src}/{pkg_path}/Application.{ext}"] = application_java(package)

        files["src/main/resources/application.conf"] = application_conf(package)
        files["src/main/resources/logback.xml"] = logback_xml(package)
        files[f"src/test/{src}/{pkg_path}/.gitkeep"] = ""

    return files


def main() -> int:
    args = parse_args()

    base_path = Path(args.output) / args.name
    assets_dir = Path(__file__).parent.parent / "assets"

    plan = build_plan(args, assets_dir)

    if args.dry_run:
        print(f"DRY RUN — no files written. Target: {base_path}")
        print(f"  language     : {args.lang}")
        print(f"  package      : {args.package}")
        print(f"  layout       : {'multi-module' if args.multi_module else 'single-module'}")
        print(f"  kora version : {args.kora_version}")
        print(f"  files        : {len(plan)}")
        for relative in sorted(plan):
            content = plan[relative]
            print()
            print(f"===== {base_path / relative} =====")
            print(content if content else "(empty file)")
        return 0

    if base_path.exists() and not args.force:
        print(f"Error: {base_path} already exists (use --force to overwrite)", file=sys.stderr)
        return 1

    for relative in sorted(plan):
        target = base_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(plan[relative])
        print(f"  wrote {target}")

    print(f"\nProject '{args.name}' created at {base_path}")
    print("\nNext steps:")
    print(f"  cd {base_path}")
    print("  gradle wrapper --gradle-version 9.8.0   # if you do not already have the wrapper jar")
    print("  ./gradlew classes")
    print("  ./gradlew run")
    print("\nKora 2.0 requires JDK 25 or newer.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
