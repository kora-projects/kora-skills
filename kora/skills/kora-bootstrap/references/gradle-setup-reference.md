# Kora Gradle Setup Reference

**Source:** [.kora-agent/kora-docs/mkdocs/docs/en/documentation/general.md](.kora-agent/kora-docs/mkdocs/docs/en/documentation/general.md)  
**Examples:** `.kora-agent/kora-examples/kora-java-helloworld/`

> **Important: Gradle (recommended)**
> 
> Kora **recommends Gradle** as the build system.
> 
> **Why Gradle is preferred:**
> - Kora relies on annotation processors (Java) and KSP (Kotlin) for compile-time code generation.
> - Gradle provides optimal incremental build support with annotation processors.
> - Gradle supports multi-round annotation processing — critical for Kora code generation.
> - Significantly faster builds due to incrementality.
> 
> Maven is technically possible but will be **significantly slower** due to worse annotation processing support and no incremental build.
> 
> Gradle **7+** is required.
> 
> **Documentation:** [Kora Build System](.kora-agent/kora-docs/mkdocs/docs/en/documentation/general.md#build-system)  
> **Examples:** `.kora-agent/kora-examples/kora-java-helloworld/`

**Important:** All string values in `build.gradle` must use double quotes (`"`) not single quotes (`'`). Always use Java 25 (`JavaVersion.VERSION_25`) for new projects.

## Java Project Setup

### Minimum build.gradle

```groovy
plugins {
    id "java"
    id "application"
}

configurations {
    koraBom
    annotationProcessor.extendsFrom(koraBom)
    compileOnly.extendsFrom(koraBom)
    implementation.extendsFrom(koraBom)
    api.extendsFrom(koraBom)
}

dependencies {
    koraBom platform("ru.tinkoff.kora:kora-parent:1.2.15")
    annotationProcessor "ru.tinkoff.kora:annotation-processors"

    // Basic dependencies
    implementation "ru.tinkoff.kora:logging-logback"
    implementation "ru.tinkoff.kora:config-hocon"

    // Add more dependencies as needed:
    // implementation "ru.tinkoff.kora:database-jdbc"
    // implementation "ru.tinkoff.kora:validation-module"
    // implementation "ru.tinkoff.kora:micrometer-module"
}

java {
    sourceCompatibility = JavaVersion.VERSION_25
    targetCompatibility = JavaVersion.VERSION_25
}

application {
    applicationName = "application"
    mainClass = "com.example.Application"
    applicationDefaultJvmArgs = ["-Dfile.encoding=UTF-8"]
}

compileJava {
    options.encoding("UTF-8")
    options.incremental(true)
    options.fork = false
}
```

### Test configuration (optional)

```groovy
// Add to configurations:
configurations {
    testAnnotationProcessor.extendsFrom(koraBom)
    testImplementation.extendsFrom(koraBom)
}

// Add to dependencies:
dependencies {
    testImplementation "org.junit.jupiter:junit-jupiter:5.10.2"
}

// Test task:
test {
    useJUnitPlatform()
}
```

## Kotlin Project Setup

### Minimum build.gradle.kts

```kotlin
plugins {
    kotlin("jvm") version "1.9.25"
    id("com.google.devtools.ksp") version "1.9.25-1.0.20"
    id("application")
}

val koraBom: Configuration by configurations.creating
configurations {
    ksp.get().extendsFrom(koraBom)
    compileOnly.get().extendsFrom(koraBom)
    api.get().extendsFrom(koraBom)
    implementation.get().extendsFrom(koraBom)
}

val koraVersion: String by project
dependencies {
    koraBom(platform("ru.tinkoff.kora:kora-parent:$koraVersion"))
    ksp("ru.tinkoff.kora:symbol-processors")

    // Basic dependencies
    implementation("ru.tinkoff.kora:logging-logback")
    implementation("ru.tinkoff.kora:config-hocon")

    // Add more dependencies as needed:
    // implementation("ru.tinkoff.kora:database-jdbc")
    // implementation("ru.tinkoff.kora:validation-module")
    // implementation("ru.tinkoff.kora:micrometer-module")
}

kotlin {
    jvmToolchain { languageVersion.set(JavaLanguageVersion.of(17)) }
    sourceSets.main { kotlin.srcDir("build/generated/ksp/main/kotlin") }
}

application {
    applicationName = "application"
    mainClass.set("com.example.ApplicationKt")
    applicationDefaultJvmArgs = listOf("-Dfile.encoding=UTF-8")
}

tasks.compileKotlin {
    kotlinOptions {
        jvmTarget = "17"
        freeCompilerArgs = listOf("-Xjsr305=strict")
    }
}
```

### Test configuration (optional)

```kotlin
// Add to configurations:
configurations {
    testAnnotationProcessor.extendsFrom(koraBom)
    testImplementation.extendsFrom(koraBom)
}

// Add to dependencies:
dependencies {
    testImplementation("org.junit.jupiter:junit-jupiter:5.10.2")
}

// Test task:
tasks.test {
    useJUnitPlatform()
}
```

## Multi-Module Project Setup

### Root build.gradle

```groovy
subprojects {
    apply plugin: "java"
    
    configurations {
        koraBom
        annotationProcessor.extendsFrom(koraBom)
        compileOnly.extendsFrom(koraBom)
        implementation.extendsFrom(koraBom)
        api.extendsFrom(koraBom)
    }
    
    dependencies {
        koraBom platform("ru.tinkoff.kora:kora-parent:1.2.15")
        annotationProcessor "ru.tinkoff.kora:annotation-processors"
    }
    
    java {
        sourceCompatibility = JavaVersion.VERSION_25
        targetCompatibility = JavaVersion.VERSION_25
    }
    
    compileJava {
        options.encoding("UTF-8")
        options.incremental(true)
        options.fork = false
    }
}
```

### settings.gradle

```groovy
rootProject.name = 'my-app'
include ':common'
include ':app'
```

## Key Points

1. **Double quotes required** - All string values in `build.gradle` must use double quotes (`"`)
2. **koraBom pattern** - Use BOM for all Kora dependencies
3. **Java 25+** - Recommended version
4. **Kotlin** - Recommended Java version 17 for building
5. **KSP for Kotlin** - Use KSP instead of kapt for better performance

---

## Code Style

### Oracle Java Code Conventions

Use [Oracle Java Code Conventions](https://www.oracle.com/java/technologies/javase/codeconventions-introduction.html) as the base standard:

**Naming:** Classes/Interfaces `CamelCase`, Methods/Variables `camelCase`, Constants `UPPER_SNAKE_CASE`, Packages lowercase reverse domain.

**Formatting:** K&R braces, 4 spaces indentation, 180 char max line length, spaces around operators.

**Imports:** Group by packages, no wildcards, static imports for constants only.

**Kotlin:** Use [Kotlin Coding Conventions](https://kotlinlang.org/docs/coding-conventions.html).

---

## Build Troubleshooting

### Gradle Clean Fails

**Symptom:** `./gradlew clean` fails with "Unable to delete directory..."

**Solution:**
```bash
./gradlew --stop  # Stop Gradle daemons
./gradlew clean   # Retry clean
```

### Build Commands Reference

| Command | Purpose |
|---------|---------|
| `./gradlew clean classes` | Quick compilation check |
| `./gradlew clean build` | Full build before commit |
| `./gradlew distTar` | Final artifact (tar.gz distribution) |
| `./gradlew --stop` | Stop Gradle daemons |

---

## Iterative Development Pattern

1. Write minimal code — small increments only
2. Compile frequently — `./gradlew clean classes` after each change
3. Test immediately — `./gradlew test` after compilation succeeds
4. Validate against examples — cross-reference with `kora-examples`
