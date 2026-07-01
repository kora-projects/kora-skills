#!/bin/bash
# Setup Quartz scheduling in a Kora project
# Usage: ./setup-quartz.sh <project-root>

set -e

PROJECT_ROOT="${1:-.}"

echo "Setting up Quartz scheduling in $PROJECT_ROOT"

# Check if project root exists
if [ ! -d "$PROJECT_ROOT" ]; then
    echo "Error: Project root '$PROJECT_ROOT' does not exist"
    exit 1
fi

# Add dependency to build.gradle.kts
BUILD_FILE="$PROJECT_ROOT/build.gradle.kts"
if [ -f "$BUILD_FILE" ]; then
    if ! grep -q "scheduling-quartz" "$BUILD_FILE"; then
        echo "Adding scheduling-quartz dependency..."
        sed -i '' '/dependencies {/a\
    implementation("ru.tinkoff.kora:scheduling-quartz")' "$BUILD_FILE"
        echo "  ✓ Added scheduling-quartz dependency"
    else
        echo "  ✓ scheduling-quartz already present"
    fi
else
    echo "Warning: build.gradle.kts not found"
fi

# Create jobs directory
JOBS_DIR="$PROJECT_ROOT/src/main/java/com/example/app/jobs"
mkdir -p "$JOBS_DIR"
echo "  ✓ Created jobs directory"

# Create Quartz jobs template
cat > "$JOBS_DIR/QuartzJobs.java" << 'EOF'
package com.example.app.jobs;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import ru.tinkoff.kora.common.Component;
import ru.tinkoff.kora.scheduling.quartz.DisallowConcurrentExecution;
import ru.tinkoff.kora.scheduling.quartz.ScheduleWithCron;

@Component
public class QuartzJobs {

    private static final Logger log = LoggerFactory.getLogger(QuartzJobs.class);

    /**
     * Daily at 3 AM - prevent concurrent execution
     */
    @DisallowConcurrentExecution
    @ScheduleWithCron("0 0 3 * * ?")
    void nightlyReport() {
        log.info("Generating nightly report");
        // ... generate report ...
    }

    /**
     * Every hour at :00
     */
    @ScheduleWithCron("0 0 * * * ?")
    void hourlyCheck() {
        log.info("Running hourly check");
        // ... run checks ...
    }
}
EOF
echo "  ✓ Created QuartzJobs.java template"

# Add configuration
CONFIG_DIR="$PROJECT_ROOT/src/main/resources"
mkdir -p "$CONFIG_DIR"

CONF_FILE="$CONFIG_DIR/application.conf"
if [ ! -f "$CONF_FILE" ]; then
    cat > "$CONF_FILE" << 'EOF'
quartz {
  "org.quartz.scheduler.instanceName" = "MyScheduler"
  "org.quartz.threadPool.threadCount" = "10"
}

scheduling {
  waitForJobComplete = true
  telemetry {
    logging.enabled = false
    metrics.enabled = true
    tracing.enabled = true
  }
}

jobs {
  nightly {
    cron = "0 0 3 * * ?"
  }
  hourly {
    cron = "0 0 * * * ?"
  }
}
EOF
    echo "  ✓ Created application.conf with Quartz config"
else
    if ! grep -q "quartz {" "$CONF_FILE"; then
        cat >> "$CONF_FILE" << 'EOF'

quartz {
  "org.quartz.scheduler.instanceName" = "MyScheduler"
  "org.quartz.threadPool.threadCount" = "10"
}

scheduling {
  waitForJobComplete = true
}
EOF
        echo "  ✓ Added Quartz config to application.conf"
    else
        echo "  ✓ Quartz config already present"
    fi
fi

echo ""
echo "Quartz scheduling setup complete!"
echo ""
echo "Next steps:"
echo "  1. Review and customize $JOBS_DIR/QuartzJobs.java"
echo "  2. Add QuartzModule to your @KoraApp interface"
echo "  3. Run the application to see scheduled jobs in action"
