#!/bin/bash
# Setup JDK scheduling in a Kora project
# Usage: ./setup-jdk.sh <project-root>

set -e

PROJECT_ROOT="${1:-.}"

echo "Setting up JDK scheduling in $PROJECT_ROOT"

# Check if project root exists
if [ ! -d "$PROJECT_ROOT" ]; then
    echo "Error: Project root '$PROJECT_ROOT' does not exist"
    exit 1
fi

# Add dependency to build.gradle.kts
BUILD_FILE="$PROJECT_ROOT/build.gradle.kts"
if [ -f "$BUILD_FILE" ]; then
    if ! grep -q "scheduling-jdk" "$BUILD_FILE"; then
        echo "Adding scheduling-jdk dependency..."
        sed -i '' '/dependencies {/a\
    implementation("ru.tinkoff.kora:scheduling-jdk")' "$BUILD_FILE"
        echo "  ✓ Added scheduling-jdk dependency"
    else
        echo "  ✓ scheduling-jdk already present"
    fi
else
    echo "Warning: build.gradle.kts not found"
fi

# Create jobs directory
JOBS_DIR="$PROJECT_ROOT/src/main/java/com/example/app/jobs"
mkdir -p "$JOBS_DIR"
echo "  ✓ Created jobs directory"

# Copy template
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TEMPLATE_DIR="$(dirname "$SCRIPT_DIR")/assets"

if [ -f "$TEMPLATE_DIR/ScheduledJobs.java.template" ]; then
    cp "$TEMPLATE_DIR/ScheduledJobs.java.template" "$JOBS_DIR/ScheduledJobs.java"
    echo "  ✓ Copied ScheduledJobs.java template"
fi

# Add configuration
CONFIG_DIR="$PROJECT_ROOT/src/main/resources"
mkdir -p "$CONFIG_DIR"

CONF_FILE="$CONFIG_DIR/application.conf"
if [ ! -f "$CONF_FILE" ]; then
    cat > "$CONF_FILE" << 'EOF'
scheduling {
  threads = 2
  shutdownWait = "30s"
  telemetry {
    logging.enabled = false
    metrics.enabled = true
    tracing.enabled = true
  }
}

jobs {
  heartbeat {
    initialDelay = "10s"
    period = "30s"
  }
  cleanup {
    initialDelay = "30s"
    delay = "5m"
  }
}
EOF
    echo "  ✓ Created application.conf with scheduling config"
else
    if ! grep -q "scheduling {" "$CONF_FILE"; then
        cat >> "$CONF_FILE" << 'EOF'

scheduling {
  threads = 2
  shutdownWait = "30s"
  telemetry {
    logging.enabled = false
    metrics.enabled = true
    tracing.enabled = true
  }
}
EOF
        echo "  ✓ Added scheduling config to application.conf"
    else
        echo "  ✓ Scheduling config already present"
    fi
fi

echo ""
echo "JDK scheduling setup complete!"
echo ""
echo "Next steps:"
echo "  1. Review and customize $JOBS_DIR/ScheduledJobs.java"
echo "  2. Add SchedulingJdkModule to your @KoraApp interface"
echo "  3. Run the application to see scheduled jobs in action"
