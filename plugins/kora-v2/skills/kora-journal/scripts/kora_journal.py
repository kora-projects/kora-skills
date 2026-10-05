#!/usr/bin/env python3
"""
Kora Journal — continuous-improvement journal for the Kora skills.

Storage: ~/.kora-journal/<project>/<module>/<YYYY-MM-DD>_<slug>.md

The store is deliberately shared by every Kora skill package (1.x and 2.x alike) and by
every project, so a mistake recorded once is found again from anywhere. New entries are
stamped with the Kora line they were written against (`kora:` in the frontmatter); entries
without that field predate the stamp and must be checked against 2.0 before being applied.

Each entry is a separate file for easy management, export, and integration.

Usage:
    python3 kora_journal.py add "Title" --context "..." --problem "..." --solution "..." --files file1.md
    python3 kora_journal.py search "http interceptor auth" --limit 5
    python3 kora_journal.py list --limit 10
    python3 kora_journal.py export --since 2026-05-01
    python3 kora_journal.py integrate <entry-file.md>
    python3 kora_journal.py status

Requires Python 3.7+ (no third-party packages).
"""

import argparse
import os
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

# Kora line this copy of the tool belongs to. Stamped into every new entry so a shared
# store can be read safely from a project on either line.
KORA_LINE = "2.x"

JOURNAL_DIR_NAME = ".kora-journal"

# Markdown hard line break — two trailing spaces, kept out of the source so editors and
# linters that strip trailing whitespace cannot break the entry header layout.
BR = "  "

# Emit UTF-8 regardless of the platform console codepage (Windows defaults to
# cp1252, which cannot encode the checkmark/arrow/emoji this CLI prints and would
# otherwise crash every command). Safe no-op where the stream can't be reconfigured.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass


# Curated tag vocabulary. A tag is applied when any of its keywords appears in the
# entry text. Keywords are Kora-specific on purpose: generic words such as "server" or
# "client" used to pull unrelated tags (an HTTP-server entry came out tagged `grpc`),
# which made `search --by-tags` useless.
KORA_TAG_KEYWORDS = {
    'kora1x': ['ru.tinkoff.kora', 'kora-parent', 'json-module', 'r2dbc', 'vertx',
               'configvalueextractor', 'httpservermodule', 'publicapihttpport', 'privateapihttpport',
               'kora 1.x', '1.x api', 'suspend repository', 'mono<', 'flux<', 'completionstage'],
    'migration': ['migrat', 'ported from 1', 'carried over', 'openrewrite'],
    'http-server': ['httpcontroller', 'httproute', 'httpserver', 'interceptor', 'undertow', 'httpresponseentity'],
    'http-client': ['httpclient', 'http client', 'responsecodemapper'],
    'database': ['jdbc', 'repository', 'entityjdbc', 'cassandra', 'flyway', 'liquibase', 'sql', 'intx',
                 'postgres', 'pgrange', '@pgjson'],
    'di': ['koraapp', 'component', 'submodule', 'graph', 'valueof', 'lifecycle', 'conditional', '@root',
           'dependency injection'],
    'aop': ['cacheable', 'cacheinvalidate', 'cacheput', 'aspect', '@mapping'],
    'config': ['configsource', 'configmapper', 'hocon', 'application.conf', 'application.yaml', 'configvaluemapper'],
    'openapi': ['openapi', 'delegate', 'apisecurity', 'swagger', 'scalar'],
    'kafka': ['kafka'],
    'grpc': ['grpc', 'protobuf', 'stub'],
    'auth': ['principal', 'bearer', 'apikey', 'oauth', 'authorization', 'authentication'],
    'json': ['json', 'jackson', 'serializ'],
    'telemetry': ['telemetry', 'metrics', 'tracing', 'micrometer', 'opentelemetry', 'logback',
                  'datamasker', 'masking', 'jsonrecordencoder'],
    'resilient': ['circuitbreak', 'retryable', '@retry', 'timeout', 'fallback', 'resilient', 'ratelimit',
                  'retrybudget', 'nonretryable', 'noncircuitable'],
    'scheduling': ['schedule', 'quartz', 'cron'],
    'validation': ['@valid', 'validate', 'violation', 'constraint'],
    's3': ['@s3', 's3client', 'bucket'],
    'test': ['koraapptest', 'testcontainers', 'junit', 'mockk', 'mockito'],
    'build': ['gradle', 'annotationprocessor', 'annotation processor', 'ksp', 'kora-bom', 'toolchain'],
    'nullability': ['jspecify', '@nullable', 'nullmarked'],
}

SCOPES = ('module', 'project', 'all')


def plural(count, word='entries', singular='entry'):
    return f"{count} {singular if count == 1 else word}"


def sanitize_path_component(name):
    """Strip anything a filesystem (Windows included) would reject in a directory name."""
    return re.sub(r'[^A-Za-z0-9._-]+', '-', name).strip('-. ')


def get_project_name():
    """
    Get project name from current directory or git remote.

    Priority:
    1. Git remote name (e.g., 'kora-skills' from 'github:user/kora-skills.git')
    2. Current directory name
    """
    project_name = Path.cwd().name

    try:
        result = subprocess.run(
            ['git', 'config', '--get', 'remote.origin.url'],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            url = result.stdout.strip()
            match = re.search(r'/([^/]+?)(?:\.git)?$', url)
            if match:
                project_name = match.group(1)
    except Exception:
        pass

    project_name = re.sub(r'[^a-zA-Z0-9]+', '-', project_name).strip('-').lower()
    return project_name or 'kora-project'


def get_gradle_module():
    """
    Get Gradle module name from current directory.

    Priority:
    1. settings.gradle.kts / settings.gradle rootProject.name
    2. Current directory name
    """
    current = Path.cwd()

    for settings_file in ['settings.gradle.kts', 'settings.gradle']:
        settings_path = current / settings_file
        if settings_path.exists():
            content = settings_path.read_text(encoding='utf-8', errors='replace')
            match = re.search(r'rootProject\.name\s*=\s*["\']([^"\']+)["\']', content)
            if match:
                # rootProject.name becomes a directory name: keep it portable. Ordinary
                # names ("billing-api", "my.service") pass through unchanged.
                return sanitize_path_component(match.group(1)) or 'default'

    module_name = re.sub(r'[^a-zA-Z0-9]+', '-', current.name).strip('-').lower()
    return module_name or 'default'


def get_journal_root():
    """Root of the shared store: ~/.kora-journal/ (never created by read commands)."""
    return Path.home() / JOURNAL_DIR_NAME


def get_journal_dir(create=False):
    """
    Directory for the current project/module: ~/.kora-journal/<project>/<module>/

    Only `add` passes create=True. Read-only commands must not materialise empty
    directories for every project they are run from.
    """
    journal_dir = get_journal_root() / get_project_name() / get_gradle_module()
    if create:
        journal_dir.mkdir(parents=True, exist_ok=True)
    return journal_dir


def iter_entry_files(scope):
    """Entry files for the requested scope, newest filename first."""
    root = get_journal_root()
    if not root.exists():
        return []

    if scope == 'module':
        base = get_journal_dir()
        paths = base.glob('*.md') if base.exists() else []
    elif scope == 'project':
        base = root / get_project_name()
        paths = base.glob('*/*.md') if base.exists() else []
    else:
        paths = root.glob('*/*/*.md')

    return sorted(paths, key=lambda p: p.name, reverse=True)


def yaml_escape(value):
    """Escape a value for a YAML double-quoted scalar."""
    return value.replace('\\', '\\\\').replace('"', '\\"')


def yaml_unescape(value):
    return value.replace('\\"', '"').replace('\\\\', '\\')


def parse_entry(path):
    """
    Read one entry into a dict. Tolerant by design: a corrupted or hand-written file
    still yields usable fields instead of breaking the whole command.
    """
    try:
        content = path.read_text(encoding='utf-8')
    except OSError as exc:
        print(f"! Skipped unreadable entry {path}: {exc}", file=sys.stderr)
        return None

    title_match = re.search(r'^title:\s*"(.*)"\s*$', content, re.MULTILINE)
    date_match = re.search(r'^date:\s*(\d{4}-\d{2}-\d{2})', content, re.MULTILINE)
    status_match = re.search(r'Status:\**\s*(\w+)', content, re.MULTILINE)
    kora_match = re.search(r'^kora:\s*"?([^"\n]+?)"?\s*$', content, re.MULTILINE)
    tags_match = re.search(r'^tags:\s*\[([^\]]*)\]', content, re.MULTILINE)

    tags = []
    if tags_match:
        tags = [t.strip().strip('"').strip("'") for t in tags_match.group(1).split(',') if t.strip()]

    date = date_match.group(1) if date_match else ''
    if not date:
        name_date = re.match(r'(\d{4}-\d{2}-\d{2})_', path.name)
        date = name_date.group(1) if name_date else 'unknown'

    return {
        'path': path,
        'content': content,
        'title': yaml_unescape(title_match.group(1)) if title_match else path.stem,
        'date': date,
        'status': status_match.group(1) if status_match else 'pending',
        'kora': kora_match.group(1) if kora_match else '',
        'tags': tags,
        'project': path.parent.parent.name,
        'module': path.parent.name,
    }


def load_entries(scope, status=None):
    entries = []
    for path in iter_entry_files(scope):
        entry = parse_entry(path)
        if entry is None:
            continue
        if status and status != 'all' and entry['status'] != status:
            continue
        entries.append(entry)
    entries.sort(key=lambda e: (e['date'], e['path'].name), reverse=True)
    return entries


def entry_ref(entry, scope):
    """Identifier to print. Outside module scope it stays resolvable by `integrate`."""
    if scope == 'module':
        return entry['path'].name
    return f"{entry['project']}/{entry['module']}/{entry['path'].name}"


def kora_line_note(entry):
    if entry['kora']:
        return f"Kora line: {entry['kora']}"
    return "Kora line: unset — older entry, re-check against Kora 2.0 before applying"


def slugify(title):
    """Convert title to a filesystem-safe slug."""
    slug = re.sub(r'[^a-z0-9]+', '-', title.lower()).strip('-')
    return slug[:50]


def auto_tags(text):
    """Derive the curated tag set from the entry text. Deterministic and sorted."""
    lowered = text.lower()
    return sorted(tag for tag, keywords in KORA_TAG_KEYWORDS.items()
                  if any(kw in lowered for kw in keywords))


def add_entry(title, context, problem, solution, files, author, tags=None):
    """Add a new entry as a separate file."""
    journal_dir = get_journal_dir(create=True)
    now = datetime.now()
    date = now.strftime('%Y-%m-%d')
    timestamp = now.strftime('%Y-%m-%d_%H-%M-%S')

    slug = slugify(title) or 'entry'
    entry_path = journal_dir / f"{date}_{slug}.md"

    # Same title twice on one day is legitimate — suffix instead of overwriting.
    counter = 1
    while entry_path.exists():
        entry_path = journal_dir / f"{date}_{slug}_{counter}.md"
        counter += 1

    project = get_project_name()
    module = get_gradle_module()

    if tags:
        tags = sorted({t.strip().lower() for t in tags if t.strip()})
    else:
        tags = auto_tags(' '.join([title, context, problem, solution]))

    tags_yaml = ', '.join(f'"{yaml_escape(t)}"' for t in tags)

    files_block = ''.join(f"- `{f}`\n" for f in files)

    content = f"""---
title: "{yaml_escape(title)}"
date: {date}
project: "{yaml_escape(project)}"
module: "{yaml_escape(module)}"
author: "{yaml_escape(author)}"
kora: "{KORA_LINE}"
tags: [{tags_yaml}]
---

# {title}

**Date:** {date}{BR}
**Project:** {project}{BR}
**Module:** {module}{BR}
**Author:** {author}{BR}
**Kora line:** {KORA_LINE}

---

## Context

{context}

## Problem

{problem}

## Solution

{solution}

## Files Affected

{files_block}
---

## Metadata

- **Created:** {timestamp}
- **Status:** pending  # pending → integrated → archived
- **Integrated:**
"""

    entry_path.write_text(content, encoding='utf-8')
    print(f"✓ Entry added: {entry_path}")
    if not tags:
        print("  No tag matched the entry text. Re-run with --tags <tag> ... to make it findable "
              "via `search --by-tags`.")


def list_entries(limit=10, status=None, scope='module'):
    """Print the most recent entries."""
    entries = load_entries(scope, status)

    if not entries:
        where = f" in scope '{scope}'" if scope != 'module' else ""
        print(f"No entries with status '{status}'{where}." if status
              else f"No entries yet{where}. Add the first one with `add`.")
        return

    shown = entries[:limit]
    scope_label = f" [{status}]" if status else ""
    print(f"\nLast {len(shown)} of {plural(len(entries))}{scope_label} (scope: {scope}):\n")

    for i, entry in enumerate(shown, 1):
        print(f"{i}. [{entry['status']}] {entry['date']} — {entry['title']}")
        print(f"   File: {entry_ref(entry, scope)}")


def export_entries(since_date, status=None, scope='all'):
    """Export entries from the specified date, ready to fold back into the skills."""
    exported = [e for e in load_entries(scope, status) if e['date'] >= since_date]

    if not exported:
        print(f"No entries found since {since_date} (scope: {scope}).")
        return

    print(f"\nExporting {plural(len(exported))} since {since_date} (scope: {scope}):\n")
    print('=' * 80)

    for entry in exported:
        print(f"\n## File: {entry_ref(entry, scope)}\n")
        print(f"_{kora_line_note(entry)}_\n")
        body = re.sub(r'^---\n.*?\n---\n\n', '', entry['content'], flags=re.DOTALL)
        print(body)
        print('=' * 80)

    print(f"\nTotal: {plural(len(exported))}")


def resolve_entry_path(entry_file):
    """
    Resolve the argument of `integrate` to a file inside the journal store.

    Accepted: an absolute/relative path inside ~/.kora-journal/, a
    <project>/<module>/<file>.md path relative to the store root, a bare filename in the
    current module, or a bare filename that is unique across the whole store.

    Anything resolving outside the store is refused: this command rewrites the file it is
    given, and a skill document handed to it by mistake would be silently edited.

    Returns the resolved path, or None when the argument could not be resolved safely.
    """
    root = get_journal_root().resolve()
    candidates = []

    direct = Path(entry_file).expanduser()
    if direct.is_file():
        candidates.append(direct.resolve())

    for base in (root, get_journal_dir()):
        candidate = base / entry_file
        if candidate.is_file():
            candidates.append(candidate.resolve())

    if not candidates:
        matches = sorted({p.resolve() for p in iter_entry_files('all') if p.name == entry_file})
        if len(matches) > 1:
            print(f"Ambiguous entry '{entry_file}' — {len(matches)} files match:")
            for match in matches:
                print(f"  - {match.relative_to(root)}")
            print("Pass the <project>/<module>/<file>.md form.")
            return None
        candidates.extend(matches)

    if not candidates:
        print(f"Entry not found: {entry_file}")
        print(f"Looked in {root} and {get_journal_dir()}")
        return None

    entry_path = candidates[0]
    try:
        entry_path.relative_to(root)
    except ValueError:
        print(f"Refusing to modify {entry_path}: it is outside the journal store ({root}).")
        return None

    return entry_path


def integrate_entry(entry_file, new_status='integrated'):
    """Mark an entry as integrated/archived. Returns False when nothing was resolved."""
    entry_path = resolve_entry_path(entry_file)
    if entry_path is None:
        return False

    content = entry_path.read_text(encoding='utf-8')
    current = re.search(r'Status:\**\s*(\w+)', content, re.MULTILINE)
    current_status = current.group(1) if current else 'pending'

    if current_status == new_status:
        print(f"Entry is already {new_status}: {entry_path.name} (nothing changed)")
        return True

    today = datetime.now().strftime('%Y-%m-%d')
    content = re.sub(rf'(Status:\**\s*){re.escape(current_status)}', rf'\g<1>{new_status}', content, count=1)
    content = re.sub(r'(\*\*Integrated:\*\*)[^\n]*', rf'\g<1> {today}', content, count=1)

    entry_path.write_text(content, encoding='utf-8')
    print(f"✓ Entry marked as {new_status} ({current_status} → {new_status}): {entry_path.name}")
    return True


def search_entries(query, limit=10, status=None, by_tags=False, scope='all'):
    """Search entries by keywords in title/context/problem/solution, or by tag."""
    keywords = query.lower().split()
    if not keywords:
        print("Empty search query.")
        return

    results = []
    for entry in load_entries(scope, status):
        content_lower = entry['content'].lower()

        if by_tags:
            if not any(kw in entry['tags'] for kw in keywords):
                continue
            relevance = sum(1 for kw in keywords if kw in entry['tags'])
        else:
            if not all(kw in content_lower for kw in keywords):
                continue
            relevance = sum(1 for kw in keywords if kw in content_lower)
            relevance += sum(2 for kw in keywords if kw in entry['tags'])

        results.append((relevance, entry))

    if not results:
        print(f"No entries found matching '{query}' (scope: {scope}).")
        return

    results.sort(key=lambda r: (r[0], r[1]['date'], r[1]['path'].name), reverse=True)

    print(f"\nFound {plural(len(results))} matching '{query}' (scope: {scope}):\n")
    for i, (relevance, entry) in enumerate(results[:limit], 1):
        tags_str = ', '.join(entry['tags'][:5]) if entry['tags'] else 'no tags'
        print(f"{i}. [{entry['date']}] {entry['title']}")
        print(f"   File: {entry_ref(entry, scope)}")
        print(f"   Tags: {tags_str}")
        print(f"   {kora_line_note(entry)}")
        print(f"   Status: {entry['status']} | Relevance: {relevance} points")
        print()

    if len(results) > limit:
        print(f"... and {len(results) - limit} more. Use --limit to see all.")


def show_status():
    """Show journal status for the current module and for the whole store."""
    journal_dir = get_journal_dir()
    root = get_journal_root()

    print("\n📊 Kora Journal Status\n")
    print(f"Project:    {get_project_name()}")
    print(f"Module:     {get_gradle_module()}")
    print(f"Store root: {root}")
    print(f"Journal:    {journal_dir}" + ("" if journal_dir.exists() else "  (not created yet)"))
    print(f"Kora line:  {KORA_LINE} (stamped into new entries)")

    if not root.exists():
        print("\nStore: empty — no entries anywhere yet (created by the first `add`).")
        return

    for label, scope in (("This module", 'module'), ("Whole store", 'all')):
        entries = load_entries(scope)
        counts = {'pending': 0, 'integrated': 0, 'archived': 0}
        for entry in entries:
            counts[entry['status']] = counts.get(entry['status'], 0) + 1
        print(f"\n{label}: {plural(len(entries))}")
        print(f"  - Pending:    {counts.get('pending', 0)}")
        print(f"  - Integrated: {counts.get('integrated', 0)}")
        print(f"  - Archived:   {counts.get('archived', 0)}")

    recent = load_entries('all')[:5]
    if recent:
        print("\nRecent entries (whole store):")
        for entry in recent:
            print(f"  - {entry_ref(entry, 'all')}: {entry['title']}")


def add_scope_argument(parser, default):
    parser.add_argument('--scope', choices=SCOPES, default=default,
                        help=f"module = current project+module, project = all its modules, "
                             f"all = the whole shared store (default: {default})")


def main():
    parser = argparse.ArgumentParser(
        description='Kora Journal — continuous improvement for the Kora skills')
    subparsers = parser.add_subparsers(dest='command', help='Commands')

    # add
    add_parser = subparsers.add_parser('add', help='Add journal entry as separate file')
    add_parser.add_argument('title', help='Entry title')
    add_parser.add_argument('--context', required=True, help='What was being done')
    add_parser.add_argument('--problem', required=True, help='What went wrong')
    add_parser.add_argument('--solution', required=True, help='How it was fixed')
    add_parser.add_argument('--files', nargs='+', required=True, help='Affected files')
    add_parser.add_argument('--author', default=os.getenv('USER') or os.getenv('USERNAME') or 'anonymous',
                            help='Author')
    add_parser.add_argument('--tags', nargs='+', help='Keywords/tags for search (auto-generated if not provided)')

    # list
    list_parser = subparsers.add_parser('list', help='List entries')
    list_parser.add_argument('--limit', type=int, default=10, help='Max entries')
    list_parser.add_argument('--status', choices=['pending', 'integrated', 'archived'], help='Filter by status')
    add_scope_argument(list_parser, 'module')

    # export
    export_parser = subparsers.add_parser('export', help='Export entries')
    export_parser.add_argument('--since', required=True, help='Date YYYY-MM-DD')
    export_parser.add_argument('--status', choices=['pending', 'integrated', 'archived'], default='pending',
                               help='Filter by status')
    add_scope_argument(export_parser, 'all')

    # integrate
    integrate_parser = subparsers.add_parser('integrate', help='Mark entry as integrated')
    integrate_parser.add_argument('entry', help='Entry filename, <project>/<module>/<file>.md, or path in the store')
    integrate_parser.add_argument('--status', default='integrated', choices=['integrated', 'archived'],
                                  help='New status')

    # search
    search_parser = subparsers.add_parser('search', help='Search entries by keywords or tags')
    search_parser.add_argument('query', help='Search query (keywords or tags)')
    search_parser.add_argument('--limit', type=int, default=10, help='Max results')
    search_parser.add_argument('--status', choices=['pending', 'integrated', 'archived', 'all'], default='all',
                               help='Filter by status')
    search_parser.add_argument('--by-tags', action='store_true', help='Search only in tags (not in content)')
    add_scope_argument(search_parser, 'all')

    # status
    subparsers.add_parser('status', help='Show status')

    args = parser.parse_args()

    if args.command == 'add':
        add_entry(args.title, args.context, args.problem, args.solution, args.files, args.author, args.tags)
    elif args.command == 'list':
        list_entries(args.limit, args.status, args.scope)
    elif args.command == 'export':
        export_entries(args.since, args.status, args.scope)
    elif args.command == 'integrate':
        # Non-zero on failure: an unnoticed failure here leaves the entry pending forever.
        if not integrate_entry(args.entry, args.status):
            sys.exit(1)
    elif args.command == 'search':
        search_entries(args.query, args.limit, args.status, args.by_tags, args.scope)
    elif args.command == 'status':
        show_status()
    else:
        parser.print_help()


if __name__ == '__main__':
    main()
