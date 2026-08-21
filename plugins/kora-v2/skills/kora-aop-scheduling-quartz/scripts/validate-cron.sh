#!/bin/bash
# Validate cron expression syntax
# Usage: ./validate-cron.sh <cron-expression>

set -e

CRON_EXPR="${1:-}"

if [ -z "$CRON_EXPR" ]; then
    echo "Usage: ./validate-cron.sh <cron-expression>"
    echo ""
    echo "Example:"
    echo "  ./validate-cron.sh '0 0 3 * * ?'"
    exit 1
fi

# Parse cron expression (7 fields: sec min hour dom month dow [year])
IFS=' ' read -ra FIELDS <<< "$CRON_EXPR"
FIELD_COUNT=${#FIELDS[@]}

echo "Cron Expression: $CRON_EXPR"
echo "Fields: $FIELD_COUNT"
echo ""

# Validate field count (6 or 7)
if [ "$FIELD_COUNT" -lt 6 ] || [ "$FIELD_COUNT" -gt 7 ]; then
    echo "❌ Invalid: Expected 6 or 7 fields, got $FIELD_COUNT"
    echo ""
    echo "Format: <sec> <min> <hour> <dom> <month> <dow> [year]"
    exit 1
fi

# Field descriptions
SECONDS="${FIELDS[0]}"
MINUTES="${FIELDS[1]}"
HOURS="${FIELDS[2]}"
DOM="${FIELDS[3]}"
MONTH="${FIELDS[4]}"
DOW="${FIELDS[5]}"

echo "Field Breakdown:"
echo "  Seconds:      $SECONDS"
echo "  Minutes:      $MINUTES"
echo "  Hours:        $HOURS"
echo "  Day of Month: $DOM"
echo "  Month:        $MONTH"
echo "  Day of Week:  $DOW"
if [ "$FIELD_COUNT" -eq 7 ]; then
    echo "  Year:         ${FIELDS[6]}"
fi
echo ""

# Human-readable description
DESCRIPTION=""

# Hours/Minutes
if [[ "$HOURS" == "*" ]] && [[ "$MINUTES" == "0" ]]; then
    DESCRIPTION="Every hour at :00"
elif [[ "$HOURS" == "*" ]] && [[ "$MINUTES" =~ ^\*/([0-9]+)$ ]]; then
    INTERVAL="${BASH_REMATCH[1]}"
    DESCRIPTION="Every $INTERVAL minutes"
elif [[ "$MINUTES" == "0" ]] && [[ "$HOURS" =~ ^\*/([0-9]+)$ ]]; then
    INTERVAL="${BASH_REMATCH[1]}"
    DESCRIPTION="Every $INTERVAL hours at :00"
elif [[ "$HOURS" == "3" ]] && [[ "$MINUTES" == "0" ]]; then
    DESCRIPTION="Daily at 03:00"
elif [[ "$HOURS" == "9" ]] && [[ "$MINUTES" == "0" ]]; then
    DESCRIPTION="Daily at 09:00"
fi

# Day of week
if [[ "$DOW" == "MON-FRI" ]]; then
    DESCRIPTION="$DESCRIPTION on weekdays (Mon-Fri)"
elif [[ "$DOW" == "MON" ]]; then
    DESCRIPTION="$DESCRIPTION on Mondays"
elif [[ "$DOW" == "SUN" ]]; then
    DESCRIPTION="$DESCRIPTION on Sundays"
fi

# Day of month
if [[ "$DOM" == "L" ]]; then
    DESCRIPTION="$DESCRIPTION on the last day of month"
elif [[ "$DOM" == "1W" ]]; then
    DESCRIPTION="$DESCRIPTION on the first weekday of month"
fi

if [ -n "$DESCRIPTION" ]; then
    echo "Human-readable: $DESCRIPTION"
fi

echo ""
echo "✓ Cron expression appears valid"
echo ""
echo "Special Characters:"
echo "  * = All values"
echo "  ? = No specific value"
echo "  - = Range (e.g., 1-5)"
echo "  , = List (e.g., 1,3,5)"
echo "  / = Step (e.g., */10)"
echo "  L = Last"
echo "  W = Weekday"
echo "  # = Nth occurrence (e.g., 5#2 = second Friday)"
