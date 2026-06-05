#!/usr/bin/env python3
"""
Generate a scheduled jobs template for Kora AOP.

Usage:
    python generate_scheduled_jobs.py --package com.example.jobs --class-name CleanupJobs

Output:
    Creates a Java class with JDK and Quartz scheduled methods.
"""

import argparse
from pathlib import Path

TEMPLATE = """// Scheduled jobs — JDK and Quartz examples.
// @ScheduleAtFixedRate / @ScheduleWithFixedDelay / @ScheduleOnce — JDK (scheduling-jdk).
// @ScheduleWithCron — Quartz (scheduling-quartz).
// Class is non-final (Java) / open (Kotlin) for aspect codegen.
// Replace `{package}` with your package.

package {package};

import ru.tinkoff.kora.common.Component;
import ru.tinkoff.kora.scheduling.jdk.annotation.ScheduleAtFixedRate;
import ru.tinkoff.kora.scheduling.jdk.annotation.ScheduleOnce;
import ru.tinkoff.kora.scheduling.jdk.annotation.ScheduleWithFixedDelay;
// Uncomment when using scheduling-quartz:
// import ru.tinkoff.kora.scheduling.quartz.ScheduleWithCron;
// import org.quartz.DisallowConcurrentExecution;

import java.time.temporal.ChronoUnit;

@Component
public class {class_name} {{                                       // non-final

    // Fixed-rate: runs every period regardless of previous duration.
    @ScheduleAtFixedRate(initialDelay = 30, period = 60, unit = ChronoUnit.SECONDS)
    public void heartbeat() {{
        // Lightweight tick — keep it under `period` or you'll get overlapping runs.
    }}

    // Fixed-delay with config-driven schedule. Annotation values become defaults; config wins.
    @ScheduleWithFixedDelay(config = "jobs.cleanup")
    public void cleanup() {{
        if (Thread.currentThread().isInterrupted()) return;        // respect graceful shutdown
        // ...do batch cleanup...
    }}

    // Single run after delay — useful for cache priming, late binding.
    @ScheduleOnce(delay = 5, unit = ChronoUnit.MINUTES)
    public void warmup() {{
        // populate caches, fetch initial state
    }}

    // Cron (Quartz only). Uncomment when scheduling-quartz + QuartzModule are plugged in.
    // @DisallowConcurrentExecution                                // optional Quartz modifier
    // @ScheduleWithCron(cron = "0 0 3 * * ?", config = "jobs.nightly")
    // public void nightlyReport() {{
    //     // runs daily at 03:00
    // }}
}}

// Config snippet (HOCON) — add to your application.conf:
//
// jobs.cleanup {{
//   initialDelay = "30s"
//   delay = "1m"
// }}
//
// scheduling {{
//   threads = 4                                   # ScheduledExecutorService pool size
//   shutdownWait = "30s"                          # grace period for in-flight jobs
// }}
//
// # Quartz-only (if using scheduling-quartz):
// quartz {{
//   org.quartz.scheduler.instanceName = "{class_name}Scheduler"
//   org.quartz.threadPool.threadCount = 4
// }}
"""


def main():
    parser = argparse.ArgumentParser(description="Generate scheduled jobs template")
    parser.add_argument("--package", required=True, help="Java package name")
    parser.add_argument("--class-name", required=True, help="Jobs class name")
    parser.add_argument("--output", default="ScheduledJobs.java.template", help="Output file name")

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
