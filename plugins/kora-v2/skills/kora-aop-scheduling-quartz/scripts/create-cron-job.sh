#!/usr/bin/env bash
# Generate one Kora 2.0 Quartz cron job class plus its config entry.
#
# Emits io.koraframework.* imports and the 2.0 config layout:
#   annotations  io.koraframework.scheduling.quartz.annotation.{ScheduleQuartzWithCron,DisallowConcurrentExecution}
#   component    io.koraframework.common.annotation.Component
#   config       jobs.<name>.cron  (referenced by @ScheduleQuartzWithCron(config = "jobs.<name>"))

set -euo pipefail

usage() {
    cat <<'USAGE'
Usage: create-cron-job.sh [options] <job-name> <cron-expression>

Options:
  -n, --dry-run          Print the generated file and config without writing them
  -l, --lang LANG        java (default) or kotlin
  -p, --package PKG      Package for the job class (default: com.example.app.jobs)
  -r, --root DIR         Project root (default: . if ./src/main exists, else ..)
      --config-driven    Use @ScheduleQuartzWithCron(config = "jobs.<name>") instead of an
                         inline expression, so the cron can change without recompiling
  -h, --help             Show this help

Arguments:
  job-name               PascalCase name; "Job" is appended to form the class name
  cron-expression        Quartz cron, 6 or 7 fields; one of day-of-month / day-of-week
                         must be '?' (validate it with ./validate-cron.sh)

Examples:
  ./create-cron-job.sh --dry-run NightlyReport '0 0 3 * * ?'
  ./create-cron-job.sh --lang kotlin --config-driven HourlyCheck '0 0 * * * ?'
USAGE
}

DRY_RUN=0
LANG_KIND="java"
PKG="com.example.app.jobs"
PROJECT_ROOT=""
CONFIG_DRIVEN=0
POSITIONAL=()

while [ $# -gt 0 ]; do
    case "$1" in
        -n|--dry-run)     DRY_RUN=1; shift ;;
        -l|--lang)        LANG_KIND="${2:-}"; shift 2 ;;
        -p|--package)     PKG="${2:-}"; shift 2 ;;
        -r|--root)        PROJECT_ROOT="${2:-}"; shift 2 ;;
        --config-driven)  CONFIG_DRIVEN=1; shift ;;
        -h|--help)        usage; exit 0 ;;
        -*)               echo "Unknown option: $1" >&2; usage >&2; exit 2 ;;
        *)                POSITIONAL+=("$1"); shift ;;
    esac
done

JOB_NAME="${POSITIONAL[0]:-}"
CRON_EXPR="${POSITIONAL[1]:-}"

if [ -z "$JOB_NAME" ] || [ -z "$CRON_EXPR" ]; then
    usage >&2
    exit 2
fi

case "$LANG_KIND" in
    java|kotlin) ;;
    *) echo "Error: --lang must be 'java' or 'kotlin', got '$LANG_KIND'" >&2; exit 2 ;;
esac

# Quartz accepts 6 or 7 fields — reject the 5-field Unix form early (the Kora processor would
# reject it at compile time anyway). The JDK scheduler's @ScheduleJdkWithCron takes 5 fields.
read -ra CRON_FIELDS <<< "$CRON_EXPR"
if [ "${#CRON_FIELDS[@]}" -lt 6 ] || [ "${#CRON_FIELDS[@]}" -gt 7 ]; then
    echo "Error: Quartz cron needs 6 or 7 fields, got ${#CRON_FIELDS[@]}: '$CRON_EXPR'" >&2
    echo "       Format: <sec> <min> <hour> <day-of-month> <month> <day-of-week> [year]" >&2
    exit 2
fi

if [ -z "$PROJECT_ROOT" ]; then
    if [ -d "src/main" ]; then PROJECT_ROOT="."; else PROJECT_ROOT=".."; fi
fi

CLASS_NAME="${JOB_NAME}Job"
# jobs.<lower-camel name> — the config node referenced by @ScheduleQuartzWithCron(config = ...)
JOB_KEY="$(printf '%s' "${JOB_NAME:0:1}" | tr '[:upper:]' '[:lower:]')${JOB_NAME:1}"
PKG_PATH="${PKG//.//}"

if [ "$LANG_KIND" = "kotlin" ]; then
    SRC_DIR="$PROJECT_ROOT/src/main/kotlin/$PKG_PATH"
    JOB_FILE="$SRC_DIR/$CLASS_NAME.kt"
else
    SRC_DIR="$PROJECT_ROOT/src/main/java/$PKG_PATH"
    JOB_FILE="$SRC_DIR/$CLASS_NAME.java"
fi

if [ "$CONFIG_DRIVEN" -eq 1 ]; then
    SCHEDULE_ANNOTATION="@ScheduleQuartzWithCron(config = \"jobs.$JOB_KEY\")"
    SCHEDULE_NOTE="cron read from jobs.$JOB_KEY in application.conf"
else
    SCHEDULE_ANNOTATION="@ScheduleQuartzWithCron(\"$CRON_EXPR\")"
    SCHEDULE_NOTE="cron: $CRON_EXPR"
fi

if [ "$LANG_KIND" = "kotlin" ]; then
    JOB_SOURCE="$(cat <<EOF
package $PKG

import io.koraframework.common.annotation.Component
import io.koraframework.scheduling.quartz.annotation.DisallowConcurrentExecution
import io.koraframework.scheduling.quartz.annotation.ScheduleQuartzWithCron
import org.slf4j.LoggerFactory

/**
 * Scheduled job: $JOB_NAME ($SCHEDULE_NOTE).
 *
 * The class need not be \`open\` — Kora generates a \$${CLASS_NAME}_execute_Job wrapper that
 * calls this component directly instead of proxying it. Scheduled functions must not be
 * \`suspend\`; KSP rejects them.
 */
@Component
class $CLASS_NAME {

    @DisallowConcurrentExecution
    $SCHEDULE_ANNOTATION
    fun execute() {
        log.info("Executing $JOB_NAME")
        // TODO implement. On shutdown a run still going after scheduling.quartz.shutdownWait
        // (default 30s) is interrupted: bound long work and stop when Thread.currentThread().isInterrupted.
    }

    private companion object {
        private val log = LoggerFactory.getLogger($CLASS_NAME::class.java)
    }
}
EOF
)"
else
    JOB_SOURCE="$(cat <<EOF
package $PKG;

import io.koraframework.common.annotation.Component;
import io.koraframework.scheduling.quartz.annotation.DisallowConcurrentExecution;
import io.koraframework.scheduling.quartz.annotation.ScheduleQuartzWithCron;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

/**
 * Scheduled job: $JOB_NAME ($SCHEDULE_NOTE).
 *
 * The class may stay final — Kora generates a \$${CLASS_NAME}_execute_Job wrapper that calls
 * this component directly instead of proxying it.
 */
@Component
public final class $CLASS_NAME {

    private static final Logger log = LoggerFactory.getLogger($CLASS_NAME.class);

    @DisallowConcurrentExecution
    $SCHEDULE_ANNOTATION
    void execute() {
        log.info("Executing $JOB_NAME");
        // TODO implement. On shutdown a run still going after scheduling.quartz.shutdownWait
        // (default 30s) is interrupted: bound long work and stop when Thread.currentThread().isInterrupted().
    }
}
EOF
)"
fi

CONFIG_FILE="$PROJECT_ROOT/src/main/resources/application.conf"
CONFIG_SNIPPET="$(cat <<EOF

jobs.$JOB_KEY {
  cron = "$CRON_EXPR"
}
EOF
)"

if [ "$DRY_RUN" -eq 1 ]; then
    echo "DRY RUN — nothing written"
    echo
    echo "--- $JOB_FILE ---"
    printf '%s\n' "$JOB_SOURCE"
    echo
    echo "--- appended to $CONFIG_FILE ---"
    printf '%s\n' "$CONFIG_SNIPPET"
    exit 0
fi

if [ -f "$JOB_FILE" ]; then
    echo "= $JOB_FILE already exists, left untouched"
else
    mkdir -p "$SRC_DIR"
    printf '%s\n' "$JOB_SOURCE" > "$JOB_FILE"
    echo "+ created $JOB_FILE"
fi

if [ -f "$CONFIG_FILE" ]; then
    if grep -q "jobs\.$JOB_KEY" "$CONFIG_FILE"; then
        echo "= jobs.$JOB_KEY already present in application.conf"
    else
        printf '%s\n' "$CONFIG_SNIPPET" >> "$CONFIG_FILE"
        echo "+ added jobs.$JOB_KEY to $CONFIG_FILE"
    fi
else
    echo "! $CONFIG_FILE not found — add manually:"
    printf '%s\n' "$CONFIG_SNIPPET"
fi

echo
echo "Created $CLASS_NAME ($SCHEDULE_NOTE)"
echo "  1. Make sure QuartzModule is on your @KoraApp interface"
if [ "$CONFIG_DRIVEN" -eq 0 ]; then
    echo "  2. The jobs.$JOB_KEY config entry is unused until you switch the annotation to"
    echo "     @ScheduleQuartzWithCron(config = \"jobs.$JOB_KEY\") (or re-run with --config-driven)"
else
    echo "  2. jobs.$JOB_KEY.cron drives the schedule; the entry is required at graph build"
fi
echo "  3. Drop @DisallowConcurrentExecution if overlapping runs are acceptable"
