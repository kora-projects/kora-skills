#!/bin/bash
# Kora Telemetry Metrics - Quick Setup Script
# This script helps you add metrics to your Kora application

set -e

echo "🔧 Kora Telemetry Metrics Setup"
echo "================================"
echo ""

# Check if we're in a Gradle project
if [ ! -f "build.gradle" ] && [ ! -f "build.gradle.kts" ]; then
    echo "❌ No Gradle build file found. Run this script from your project root."
    exit 1
fi

echo "✅ Found Gradle project"

# Detect Kotlin or Java project
if [ -f "build.gradle.kts" ]; then
    BUILD_FILE="build.gradle.kts"
    BUILD_TYPE="kotlin"
else
    BUILD_FILE="build.gradle"
    BUILD_TYPE="groovy"
fi

echo "📝 Build file: $BUILD_FILE ($BUILD_TYPE)"
echo ""

# Add dependencies
echo "📦 Adding Micrometer dependencies..."

if [ "$BUILD_TYPE" = "kotlin" ]; then
    # Check if dependencies block exists
    if ! grep -q "implementation.*micrometer" "$BUILD_FILE" 2>/dev/null; then
        echo "Adding dependencies to $BUILD_FILE..."
        # For Kotlin DSL
        cat >> "$BUILD_FILE" << 'EOF'

// Kora Telemetry Metrics (versions come from the kora-parent BOM)
dependencies {
    ksp("ru.tinkoff.kora:symbol-processors")
    implementation("ru.tinkoff.kora:micrometer-module")
    implementation("ru.tinkoff.kora:http-server-undertow")
}
EOF
        echo "✅ Dependencies added"
    else
        echo "⚠️  Micrometer dependencies already present"
    fi
else
    # Groovy DSL
    if ! grep -q "implementation.*micrometer" "$BUILD_FILE" 2>/dev/null; then
        echo "Adding dependencies to $BUILD_FILE..."
        cat >> "$BUILD_FILE" << 'EOF'

// Kora Telemetry Metrics (versions come from the kora-parent BOM)
dependencies {
    annotationProcessor "ru.tinkoff.kora:annotation-processors"
    implementation "ru.tinkoff.kora:micrometer-module"
    implementation "ru.tinkoff.kora:http-server-undertow"
}
EOF
        echo "✅ Dependencies added"
    else
        echo "⚠️  Micrometer dependencies already present"
    fi
fi

echo ""
echo "📋 Next steps:"
echo ""
echo "1. Add MetricsModule to your Application interface:"
echo "   @KoraApp"
echo "   public interface Application extends MetricsModule, ... {}"
echo ""
echo "2. Configure metrics in application.conf:"
echo "   httpServer {"
echo "     privateApiHttpPort = 8085"
echo "     privateApiHttpMetricsPath = \"/metrics\""
echo "   }"
echo ""
echo "3. Inject MeterRegistry and create metrics:"
echo "   Timer timer = registry.timer(\"operation.duration\");"
echo "   Counter counter = registry.counter(\"operation.total\");"
echo ""
echo "4. Access metrics at http://localhost:8085/metrics"
echo ""
echo "📖 Full documentation: SKILL.md"
echo "📁 Templates: assets/"
echo ""
