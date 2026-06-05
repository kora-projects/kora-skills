# Kora Bootstrap

Basic setup for Kora applications: Gradle, DI, configuration, lifecycle.

## When to Use

- Creating a new Kora service (Java/Kotlin)
- Configuring the DI container and components
- Configuration via HOCON/YAML
- Debugging graph build errors

## Quick Start

```bash
/kora-bootstrap --name my-app --package com.example --lang java
```

## Key Features

- Gradle 9.5.1+ setup (Java 25 / Kotlin JVM 17)
- @KoraApp, @Component, @Module, @KoraSubmodule
- HOCON/YAML configuration with validation
- Lifecycle management
- Multi-module architecture (500+ classes)

## Triggers

@KoraApp, KoraApplication.run, @Component, @Module, @ConfigSource, HoconConfigModule, YamlConfigModule

## Resources

- **SKILL.md** — full documentation
- **references/** — 8 reference guides
- **scripts/** — generate_project.py, validate_gradle.py
- **assets/** — Gradle templates, Application templates
