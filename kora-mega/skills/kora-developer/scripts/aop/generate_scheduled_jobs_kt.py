#!/usr/bin/env python3
"""
Generate a scheduled jobs template for Kora AOP (Kotlin).

Usage:
    python generate_scheduled_jobs_kt.py --package com.example.jobs --class-name CleanupJobs

Output:
    Creates a Kotlin scheduled jobs class with JDK and Quartz annotations.
"""

import argparse
from pathlib import Path

TEMPLATE = """// Kotlin scheduled jobs — JDK and Quartz examples.
// @ScheduleAtFixedRate / @ScheduleWithFixedDelay / @ScheduleOnce — JDK (scheduling-jdk).
// @ScheduleWithCron — Quartz (scheduling-quartz).
// Class must be `open` for aspect codegen.
// Replace `{package}` with your package.

package {package}

import ru.tinkoff.kora.common.Component
import ru.tinkoff.kora.scheduling.jdk.annotation.ScheduleAtFixedRate
import ru.tinkoff.kora.scheduling.jdk.annotation.ScheduleOnce
import ru.tinkoff.kora.scheduling.jdk.annotation.ScheduleWithFixedDelay
// Uncomment when using scheduling-quartz:
// import ru.tinkoff.kora.scheduling.quartz.ScheduleWithCron
// import org.quartz.DisallowConcurrentExecution
import java.time.temporal.ChronoUnit

@Component
open class {class_name} {{                                                  // open, not final

    // Fixed-rate: runs every period regardless of previous duration.
    @ScheduleAtFixedRate(initialDelay = 30, period = 60, unit = ChronoUnit.SECONDS)
    open fun heartbeat() {{
        // Lightweight tick — keep it under `period` or you'll get overlapping runs.
    }}

    // Fixed-delay with config-driven schedule. Annotation values become defaults; config wins.
    @ScheduleWithFixedDelay(config = "jobs.cleanup")
    open fun cleanup() {{
        if (Thread.currentThread().isInterrupted) return                  // respect graceful shutdown
        // ...do batch cleanup...
    }}

    // Single run after delay — useful for cache priming, late binding.
    @ScheduleOnce(delay = 5, unit = ChronoUnit.MINUTES)
    open fun warmup() {{
        // populate caches, fetch initial state
    }}

    // Cron (Quartz only). Uncomment when scheduling-quartz + QuartzModule are plugged in.
    // @DisallowConcurrentExecution                                      // optional Quartz modifier
    // @ScheduleWithCron(cron = "0 0 2 * * ?")                           // daily at 02:00
    // open fun nightlyReport() {{ ... }}
}}

// Config snippet (HOCON) — add to your application.conf:
//
// jobs.cleanup {{
//   period = "PT5M"            // ISO-8601: every 5 minutes
//   delay = "PT1M"
// }}
"""


def main():
    parser = argparse.ArgumentParser(description="Generate scheduled jobs template (Kotlin)")
    parser.add_argument("--package", required=True, help="Kotlin package name")
    parser.add_argument("--class-name", required=True, help="Jobs class name")
    parser.add_argument("--output", default="ScheduledJobs.kt.template", help="Output file name")

    args = parser.parse_args()

    content = TEMPLATE.format(
        package=args.package,
        class_name=args.class_name
    )

    output_path = Path(args.output)
    output_path.write_text(content)
    print(f"Generated {output_path}")


if __name__ == "__main__":
    main()
