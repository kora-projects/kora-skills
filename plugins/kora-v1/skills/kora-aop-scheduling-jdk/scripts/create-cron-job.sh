#!/bin/bash
# Create a new cron-scheduled job
# Usage: ./create-cron-job.sh <job-name> <cron-expression>

set -e

JOB_NAME="${1:-}"
CRON_EXPR="${2:-}"

if [ -z "$JOB_NAME" ] || [ -z "$CRON_EXPR" ]; then
    echo "Usage: ./create-cron-job.sh <job-name> <cron-expression>"
    echo ""
    echo "Example:"
    echo "  ./create-cron-job.sh NightlyReport '0 0 3 * * ?'"
    exit 1
fi

# Convert to camelCase for class name
CLASS_NAME="${JOB_NAME}Job"
FILE_NAME="${CLASS_NAME}.java"
JOB_NAME_LOWER=$(echo "$JOB_NAME" | tr '[:upper:]' '[:lower:]')

# Get project root (current directory or parent)
if [ -d "src/main/java" ]; then
    PROJECT_ROOT="."
else
    PROJECT_ROOT=".."
fi

JOBS_DIR="$PROJECT_ROOT/src/main/java/com/example/app/jobs"
mkdir -p "$JOBS_DIR"

# Create job class
cat > "$JOBS_DIR/$FILE_NAME" << EOF
package com.example.app.jobs;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import ru.tinkoff.kora.common.Component;
import ru.tinkoff.kora.scheduling.quartz.ScheduleWithCron;

/**
 * Scheduled job: ${JOB_NAME}
 * Cron: ${CRON_EXPR}
 */
@Component
public class ${CLASS_NAME} {

    private static final Logger log = LoggerFactory.getLogger(${CLASS_NAME}.class);

    @ScheduleWithCron("${CRON_EXPR}")
    public void execute() {
        log.info("Executing ${JOB_NAME}");
        // TODO: Implement job logic
    }
}
EOF

echo "✓ Created $JOBS_DIR/$FILE_NAME"

# Add config entry
CONFIG_FILE="$PROJECT_ROOT/src/main/resources/application.conf"
if [ -f "$CONFIG_FILE" ]; then
    if ! grep -q "jobs.${JOB_NAME_LOWER}" "$CONFIG_FILE"; then
        cat >> "$CONFIG_FILE" << EOF

jobs.${JOB_NAME_LOWER} {
  cron = "${CRON_EXPR}"
}
EOF
        echo "✓ Added config entry to $CONFIG_FILE"
    else
        echo "✓ Config entry already exists"
    fi
fi

echo ""
echo "Created job: ${CLASS_NAME}"
echo "  Cron expression: ${CRON_EXPR}"
echo "  Class: $JOBS_DIR/$FILE_NAME"
echo ""
echo "To customize:"
echo "  1. Implement the execute() method"
echo "  2. Add @DisallowConcurrentExecution if needed"
echo "  3. Update config in application.conf if desired"
