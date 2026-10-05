#!/usr/bin/env python3
"""Validate a Kora 2.0 Kafka HOCON configuration.

Read-only: this script never writes. It checks the kafka.consumer.* and kafka.producer.*
sections of an application.conf for the mistakes that Kora 2.0 reports late, badly, or not at all.

Checks
  errors
    * a consumer with neither topics nor topicsPattern
    * a missing driverProperties block, or one without bootstrap.servers
    * assign strategy (no group.id) without topics, or with topicsPattern
      — KafkaAssignConsumerContainer rejects both at startup
    * ru.tinkoff.kora anywhere in the file (Kora 1.x group)
    * the ${VAR:default} pseudo-placeholder, which is not HOCON
  warnings
    * enable.auto.commit = true — the driver commits on a timer, ahead of the handler
    * key.deserializer / value.deserializer in a consumer — ignored, the container always
      uses ByteArrayDeserializer and applies the Kora Deserializer from the method signature
    * threads = 0 — the listener is silently disabled
    * an offset key alongside group.id — ignored in subscribe mode
    * telemetry.logging / telemetry.metrics left off (both default to false in Kora 2.0)
    * logging.level instead of logging.levels
    * a required ${VAR} substitution with no literal fallback

Usage:
    validate_config.py --config src/main/resources/application.conf
    validate_config.py --config application.conf --quiet
"""

import argparse
import re
import sys
from pathlib import Path

KORA_1X_GROUP = "ru.tinkoff.kora"
SPRING_PLACEHOLDER = re.compile(r"\$\{[A-Za-z_][A-Za-z0-9_]*\s*:")


def strip_comments(text: str) -> str:
    """Blank out # and // comments while preserving offsets and line count."""
    out = []
    in_string = False
    i = 0
    while i < len(text):
        ch = text[i]
        if in_string:
            out.append(ch)
            if ch == "\\" and i + 1 < len(text):
                out.append(text[i + 1])
                i += 2
                continue
            if ch == '"':
                in_string = False
            i += 1
            continue
        if ch == '"':
            in_string = True
            out.append(ch)
            i += 1
            continue
        if ch == "#" or (ch == "/" and text[i:i + 2] == "//"):
            while i < len(text) and text[i] != "\n":
                out.append(" ")
                i += 1
            continue
        out.append(ch)
        i += 1
    return "".join(out)


def find_block(text: str, path: list[str]) -> str | None:
    """Return the body of a nested block such as ['kafka', 'consumer'], or None."""
    body = text
    for name in path:
        pattern = re.compile(r"(?:^|[\s{,])" + re.escape(name) + r"\s*[:=]?\s*\{")
        match = pattern.search(body)
        if match is None:
            return None
        start = body.index("{", match.start())
        end = matching_brace(body, start)
        if end is None:
            return None
        body = body[start + 1:end]
    return body


def matching_brace(text: str, start: int) -> int | None:
    depth = 0
    in_string = False
    i = start
    while i < len(text):
        ch = text[i]
        if in_string:
            if ch == "\\":
                i += 2
                continue
            if ch == '"':
                in_string = False
        elif ch == '"':
            in_string = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return i
        i += 1
    return None


def child_blocks(body: str) -> dict[str, str]:
    """Immediate `name { ... }` children of a block body."""
    result: dict[str, str] = {}
    for match in re.finditer(r'(?:^|[\s{,])"?([A-Za-z0-9_.\-]+)"?\s*[:=]?\s*\{', body):
        name = match.group(1)
        start = body.index("{", match.start())
        if body[:start].count("{") - body[:start].count("}") != 0:
            continue  # nested deeper than one level
        end = matching_brace(body, start)
        if end is None:
            continue
        result[name] = body[start + 1:end]
    return result


def top_level(body: str) -> str:
    """Blank out nested `{ ... }` blocks so a key lookup only sees this block's own keys."""
    out = []
    depth = 0
    in_string = False
    i = 0
    while i < len(body):
        ch = body[i]
        if in_string:
            out.append(ch if depth == 0 else " ")
            if ch == "\\" and i + 1 < len(body):
                out.append(body[i + 1] if depth == 0 else " ")
                i += 2
                continue
            if ch == '"':
                in_string = False
            i += 1
            continue
        if ch == '"':
            in_string = True
            out.append(ch if depth == 0 else " ")
        elif ch == "{":
            depth += 1
            out.append(" ")
        elif ch == "}":
            depth -= 1
            out.append(" ")
        else:
            out.append(ch if depth == 0 else (" " if ch != "\n" else "\n"))
        i += 1
    return "".join(out)


def value_of(body: str, key: str) -> str | None:
    match = re.search(r'"?' + re.escape(key) + r'"?\s*[:=]\s*([^\n},]+)', body)
    return match.group(1).strip() if match else None


def topic_count(body: str) -> int | None:
    """Number of entries in `topics`, or None when the key is absent."""
    match = re.search(r'"?topics"?\s*[:=]\s*(\[[^\]]*\]|"[^"]*"|[^\s,}]+)', body)
    if match is None:
        return None
    raw = match.group(1).strip()
    if raw.startswith("["):
        inner = raw[1:-1].strip()
        return 0 if not inner else len([p for p in inner.split(",") if p.strip()])
    return 1


class Report:
    def __init__(self) -> None:
        self.errors: list[str] = []
        self.warnings: list[str] = []

    def error(self, message: str) -> None:
        self.errors.append(message)

    def warn(self, message: str) -> None:
        self.warnings.append(message)


def check_consumer(name: str, body: str, report: Report) -> None:
    where = "consumer '%s'" % name
    own = top_level(body)
    driver = find_block(body, ["driverProperties"])
    topics = topic_count(own)
    has_pattern = re.search(r'"?topicsPattern"?\s*[:=]', own) is not None

    if topics is None and not has_pattern:
        report.error("%s: neither topics nor topicsPattern is set" % where)
    if driver is None:
        report.error("%s: driverProperties block is missing" % where)
        return
    if value_of(driver, "bootstrap.servers") is None:
        report.error("%s: driverProperties has no bootstrap.servers" % where)

    group_id = value_of(driver, "group.id")
    if group_id is None:
        # assign strategy
        if has_pattern:
            report.error(
                "%s: assign strategy (no group.id) does not support topicsPattern — "
                "list the topics, or add group.id" % where)
        elif topics is None or topics < 1:
            report.error(
                "%s: assign strategy (no group.id) requires at least one topic, found none" % where)
        if value_of(own, "offset") is None:
            report.warn("%s: assign strategy never commits — set `offset` so restarts are "
                        "predictable (earliest | latest | a Duration)" % where)
    else:
        if value_of(own, "offset") is not None:
            report.warn("%s: `offset` is ignored in subscribe mode (group.id is set); use "
                        "driverProperties auto.offset.reset instead" % where)

    auto_commit = value_of(driver, "enable.auto.commit")
    if auto_commit is not None and auto_commit.strip('"').lower() == "true":
        report.warn("%s: enable.auto.commit = true hands committing to the driver's timer, "
                    "which can commit ahead of the handler and lose records; leave it unset "
                    "so Kora commits after the handler returns" % where)

    for key in ("key.deserializer", "value.deserializer"):
        if value_of(driver, key) is not None:
            report.warn("%s: %s is ignored — the container always uses ByteArrayDeserializer "
                        "and applies the Kora Deserializer chosen by the method signature"
                        % (where, key))

    threads = value_of(own, "threads")
    if threads is not None and threads.strip().strip('"') == "0":
        report.warn("%s: threads = 0 disables the listener entirely (no logs, no error)" % where)

    check_telemetry(where, body, report)


def check_producer(name: str, body: str, report: Report) -> None:
    where = "producer '%s'" % name
    own = top_level(body)
    is_topic_section = value_of(own, "topic") is not None
    is_transactional = any(value_of(own, k) is not None
                           for k in ("idPrefix", "maxPoolSize", "maxWaitTime"))
    if is_topic_section or is_transactional:
        return  # @Topic section or transactional wrapper — no driverProperties of its own

    driver = find_block(body, ["driverProperties"])
    if driver is None:
        report.error("%s: driverProperties block is missing" % where)
        return
    if value_of(driver, "bootstrap.servers") is None:
        report.error("%s: driverProperties has no bootstrap.servers" % where)
    check_telemetry(where, body, report)


def check_telemetry(where: str, body: str, report: Report) -> None:
    telemetry = find_block(body, ["telemetry"])
    flat_logging = value_of(body, "telemetry.logging.enabled")
    flat_metrics = value_of(body, "telemetry.metrics.enabled")

    logging_enabled = flat_logging
    metrics_enabled = flat_metrics
    if telemetry is not None:
        if logging_enabled is None:
            logging_block = find_block(telemetry, ["logging"])
            logging_enabled = (value_of(logging_block, "enabled") if logging_block
                               else value_of(telemetry, "logging.enabled"))
        if metrics_enabled is None:
            metrics_block = find_block(telemetry, ["metrics"])
            metrics_enabled = (value_of(metrics_block, "enabled") if metrics_block
                               else value_of(telemetry, "metrics.enabled"))

    if logging_enabled is None or logging_enabled.strip('"').lower() != "true":
        report.warn("%s: telemetry.logging.enabled defaults to false in Kora 2.0 — the component "
                    "logs nothing at all, not even lifecycle lines" % where)
    if metrics_enabled is None or metrics_enabled.strip('"').lower() != "true":
        report.warn("%s: telemetry.metrics.enabled defaults to false in Kora 2.0 — no "
                    "messaging.* meters are published" % where)


def check_global(text: str, report: Report) -> None:
    if KORA_1X_GROUP in text:
        report.error("file references %s — Kora 2.0 is io.koraframework" % KORA_1X_GROUP)

    for match in SPRING_PLACEHOLDER.finditer(text):
        snippet = text[match.start():match.start() + 40].split("\n")[0]
        report.error("not HOCON: %s... — there is no ${VAR:default} placeholder. Assign the "
                     "literal first, then override it with ${?VAR}" % snippet)

    if re.search(r"(?:^|[\s{,])logging\s*\.\s*level\s*[:={]", text) or \
            (find_block(text, ["logging", "level"]) is not None):
        report.warn("logging.level is not a Kora key — the section is logging.levels")

    for match in re.finditer(r'"?bootstrap\.servers"?\s*[:=]\s*\$\{(?!\?)([A-Za-z_][A-Za-z0-9_]*)\}',
                             text):
        report.warn("bootstrap.servers uses the required substitution ${%s} — startup aborts when "
                    "it is unset; a literal followed by ${?%s} keeps a local default"
                    % (match.group(1), match.group(1)))


def validate(path: Path, quiet: bool) -> bool:
    if not path.exists():
        print("configuration file not found: %s" % path, file=sys.stderr)
        return False

    raw = path.read_text(encoding="utf-8")
    text = strip_comments(raw)
    report = Report()

    check_global(text, report)

    kafka = find_block(text, ["kafka"])
    if kafka is None:
        report.warn("no kafka { } section found")
    else:
        consumers = find_block(kafka, ["consumer"])
        producers = find_block(kafka, ["producer"])
        if consumers is None:
            report.warn("no kafka.consumer section found")
        else:
            children = child_blocks(consumers)
            if not children:
                report.warn("kafka.consumer has no listener sections")
            for name, body in children.items():
                check_consumer(name, body, report)
        if producers is not None:
            for name, body in child_blocks(producers).items():
                check_producer(name, body, report)

    if not quiet:
        print("validating %s" % path)
        print("-" * 60)
    if report.errors:
        print("ERRORS:")
        for item in report.errors:
            print("  - %s" % item)
    if report.warnings:
        print("WARNINGS:")
        for item in report.warnings:
            print("  - %s" % item)
    if not report.errors and not report.warnings:
        print("no problems found")
    if not quiet:
        print("-" * 60)
        print("%d error(s), %d warning(s)" % (len(report.errors), len(report.warnings)))

    return not report.errors


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Validate a Kora 2.0 Kafka HOCON configuration (read-only)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--config", required=True,
                        help="Path to application.conf")
    parser.add_argument("--quiet", action="store_true",
                        help="Print findings only, without the header and summary")

    args = parser.parse_args()
    sys.exit(0 if validate(Path(args.config), args.quiet) else 1)


if __name__ == "__main__":
    main()
