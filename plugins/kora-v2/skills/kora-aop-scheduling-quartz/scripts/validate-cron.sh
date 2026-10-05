#!/usr/bin/env bash
# Sanity-check a Quartz cron expression for
# io.koraframework.scheduling.quartz.annotation.ScheduleQuartzWithCron.
#
# Read-only: nothing is written, nothing is executed against your project.
#
# Enforces the rules org.quartz.CronExpression (Quartz 2.5.2) enforces at parse time:
#   - 6 or 7 space-separated fields (sec min hour day-of-month month day-of-week [year])
#   - '?' is legal only in day-of-month and day-of-week
#   - exactly one of day-of-month / day-of-week must be '?'
#   - 'L' and 'W' only in day-of-month; 'L' and '#' only in day-of-week
#   - numeric values within each field's range
#
# This is a linter, not the Quartz parser — it will not catch every malformed expression.
# The Kora annotation processor validates a literal @ScheduleQuartzWithCron cron at compile time;
# use this script for crons that live in configuration and are only parsed at startup.
# The Kora JDK scheduler (@ScheduleJdkWithCron) uses a different parser that also accepts
# 5 fields; this script deliberately rejects that form.

set -uo pipefail

usage() {
    cat <<'USAGE'
Usage: validate-cron.sh [-q|--quiet] <cron-expression>

Options:
  -q, --quiet    Only report problems; suppress the breakdown and the legend
  -h, --help     Show this help

Exit codes:
  0  expression passes every check
  1  expression is invalid
  2  wrong usage

Examples:
  ./validate-cron.sh '0 0 3 * * ?'
  ./validate-cron.sh '0 0 9 ? * MON-FRI'
  ./validate-cron.sh -q '* * * ? * * *'
USAGE
}

QUIET=0
CRON_EXPR=""

while [ $# -gt 0 ]; do
    case "$1" in
        -q|--quiet) QUIET=1; shift ;;
        -h|--help)  usage; exit 0 ;;
        -*)         echo "Unknown option: $1" >&2; usage >&2; exit 2 ;;
        *)          CRON_EXPR="$1"; shift ;;
    esac
done

if [ -z "$CRON_EXPR" ]; then
    usage >&2
    exit 2
fi

ERRORS=0
err()  { echo "ERROR: $*" >&2; ERRORS=$((ERRORS + 1)); }
warn() { echo "WARN:  $*" >&2; }
say()  { [ "$QUIET" -eq 1 ] || echo "$@"; }

read -ra FIELDS <<< "$CRON_EXPR"
FIELD_COUNT=${#FIELDS[@]}

say "Cron expression: $CRON_EXPR"
say "Fields:          $FIELD_COUNT"
say

if [ "$FIELD_COUNT" -lt 6 ] || [ "$FIELD_COUNT" -gt 7 ]; then
    err "Quartz needs 6 or 7 fields, got $FIELD_COUNT."
    echo "       Format: <sec> <min> <hour> <day-of-month> <month> <day-of-week> [year]" >&2
    if [ "$FIELD_COUNT" -eq 5 ]; then
        echo "       A 5-field Unix expression is rejected by Quartz. The JDK scheduler" >&2
        echo "       (io.koraframework.scheduling.jdk.annotation.ScheduleJdkWithCron) accepts it;" >&2
        echo "       for Quartz, prepend a seconds field: '0 $CRON_EXPR'." >&2
    fi
    exit 1
fi

# Deliberately not SECONDS/MINUTES — SECONDS is a special bash variable that would
# silently report elapsed shell time instead of the field's value.
CRON_SEC="${FIELDS[0]}"
CRON_MIN="${FIELDS[1]}"
CRON_HOUR="${FIELDS[2]}"
CRON_DOM="${FIELDS[3]}"
CRON_MONTH="${FIELDS[4]}"
CRON_DOW="${FIELDS[5]}"
CRON_YEAR="${FIELDS[6]:-}"

say "Field breakdown:"
say "  Seconds:      $CRON_SEC"
say "  Minutes:      $CRON_MIN"
say "  Hours:        $CRON_HOUR"
say "  Day of month: $CRON_DOM"
say "  Month:        $CRON_MONTH"
say "  Day of week:  $CRON_DOW"
[ -n "$CRON_YEAR" ] && say "  Year:         $CRON_YEAR"
say

# --- '?' placement ---------------------------------------------------------

for pair in "seconds:$CRON_SEC" "minutes:$CRON_MIN" "hours:$CRON_HOUR" \
            "month:$CRON_MONTH" "year:${CRON_YEAR:-*}"; do
    name="${pair%%:*}"; value="${pair#*:}"
    case "$value" in
        *\?*) err "'?' in the $name field. Quartz allows '?' only in day-of-month and day-of-week." ;;
    esac
done

DOM_NOSPEC=0; [ "$CRON_DOM" = "?" ] && DOM_NOSPEC=1
DOW_NOSPEC=0; [ "$CRON_DOW" = "?" ] && DOW_NOSPEC=1

if [ "$DOM_NOSPEC" -eq 1 ] && [ "$DOW_NOSPEC" -eq 1 ]; then
    err "Both day-of-month and day-of-week are '?'. Quartz: \"'?' can only be specified for Day-of-Month -OR- Day-of-Week.\""
elif [ "$DOM_NOSPEC" -eq 0 ] && [ "$DOW_NOSPEC" -eq 0 ]; then
    err "Neither day-of-month nor day-of-week is '?'. Quartz: \"Support for specifying both a day-of-week AND a day-of-month parameter is not implemented.\""
    echo "       Put '?' in whichever of the two you do not care about." >&2
fi

# --- special characters ----------------------------------------------------

case "$CRON_SEC$CRON_MIN$CRON_HOUR" in
    *L*) err "'L' is not allowed in the seconds, minutes or hours fields." ;;
esac
case "$CRON_DOM" in
    *\#*) err "'#' is only allowed in the day-of-week field." ;;
esac
case "$CRON_DOW" in
    *W*) err "'W' is only allowed in the day-of-month field." ;;
esac
if [ -n "$CRON_DOW" ] && [ "$(tr -cd '#' <<<"$CRON_DOW" | wc -c | tr -d ' ')" -gt 1 ]; then
    err "Multiple '#' in day-of-week: Quartz does not implement multiple \"nth\" days."
fi

# --- numeric ranges --------------------------------------------------------

# check_range <field-name> <value> <min> <max>
check_range() {
    local name="$1" value="$2" min="$3" max="$4" token
    # strip Quartz specials, then test whatever numbers remain
    for token in $(tr ',-/#' ' ' <<<"$value"); do
        token="${token//\*/}"
        token="${token//\?/}"
        token="${token//L/}"
        token="${token//W/}"
        [ -z "$token" ] && continue
        case "$token" in
            ''|*[!0-9]*) continue ;;   # names like MON or JAN are checked by Quartz itself
        esac
        if [ "$token" -lt "$min" ] || [ "$token" -gt "$max" ]; then
            err "$name value '$token' is outside $min-$max."
        fi
    done
}

check_range "Seconds"      "$CRON_SEC"   0 59
check_range "Minutes"      "$CRON_MIN"   0 59
check_range "Hours"        "$CRON_HOUR"  0 23
check_range "Day-of-month" "$CRON_DOM"   1 31
check_range "Month"        "$CRON_MONTH" 1 12
check_range "Day-of-week"  "$CRON_DOW"   1 7
[ -n "$CRON_YEAR" ] && check_range "Year" "$CRON_YEAR" 1970 2099

# --- advisory --------------------------------------------------------------

if [ "$CRON_SEC" = "*" ]; then
    warn "The seconds field is '*' — this job fires every second."
fi

# --- description -----------------------------------------------------------

DESCRIPTION=""
if [ "$CRON_SEC" = "*" ] && [ "$CRON_MIN" = "*" ] && [ "$CRON_HOUR" = "*" ]; then
    DESCRIPTION="Every second"
elif [ "$CRON_SEC" = "0" ] && [ "$CRON_MIN" = "*" ] && [ "$CRON_HOUR" = "*" ]; then
    DESCRIPTION="Every minute"
elif [ "$CRON_SEC" = "0" ] && [[ "$CRON_MIN" =~ ^\*/([0-9]+)$ ]]; then
    DESCRIPTION="Every ${BASH_REMATCH[1]} minutes"
elif [ "$CRON_SEC" = "0" ] && [ "$CRON_MIN" = "0" ] && [ "$CRON_HOUR" = "*" ]; then
    DESCRIPTION="Every hour at :00"
elif [ "$CRON_SEC" = "0" ] && [ "$CRON_MIN" = "0" ] && [[ "$CRON_HOUR" =~ ^\*/([0-9]+)$ ]]; then
    DESCRIPTION="Every ${BASH_REMATCH[1]} hours at :00"
elif [ "$CRON_SEC" = "0" ] && [[ "$CRON_MIN" =~ ^[0-9]+$ ]] && [[ "$CRON_HOUR" =~ ^[0-9]+$ ]]; then
    DESCRIPTION="$(printf 'Daily at %02d:%02d' "$CRON_HOUR" "$CRON_MIN")"
fi

if [ -n "$DESCRIPTION" ] && [ "$ERRORS" -eq 0 ]; then
    case "$CRON_DOW" in
        MON-FRI) DESCRIPTION="$DESCRIPTION on weekdays (Mon-Fri)" ;;
        SAT,SUN|SUN,SAT) DESCRIPTION="$DESCRIPTION at weekends" ;;
        MON|TUE|WED|THU|FRI|SAT|SUN) DESCRIPTION="$DESCRIPTION on ${CRON_DOW}" ;;
    esac
    case "$CRON_DOM" in
        L)  DESCRIPTION="$DESCRIPTION on the last day of the month" ;;
        1W) DESCRIPTION="$DESCRIPTION on the first weekday of the month" ;;
        LW) DESCRIPTION="$DESCRIPTION on the last weekday of the month" ;;
    esac
    say "Reads as: $DESCRIPTION"
    say
fi

# --- result ----------------------------------------------------------------

if [ "$ERRORS" -gt 0 ]; then
    echo "Invalid: $ERRORS problem(s) found." >&2
    exit 1
fi

say "OK — passes the Quartz structural checks."
say
if [ "$QUIET" -eq 0 ]; then
    cat <<'LEGEND'
Special characters:
  *  all values
  ?  no specific value (day-of-month / day-of-week only, exactly one of them)
  -  range           1-5
  ,  list            MON,WED,FRI
  /  step            */10
  L  last            L in day-of-month = last day; 6L = last Friday
  W  nearest weekday 1W = first weekday of the month
  #  nth weekday     6#2 = second Friday

Time zone: a @Tag(SchedulingModule.class) ZoneId component if the graph has one,
otherwise the JVM default; @ScheduleQuartzWithCron has no time-zone attribute.
LEGEND
fi
