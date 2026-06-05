#!/usr/bin/env python3
"""
KORA Journal — automatic skill improvement journal.

Usage:
    python kora_journal.py add "Title of change" --files file1.md file2.md
    python kora_journal.py list --limit 10
    python kora_journal.py export --since 2026-05-01
    python kora_journal.py status
"""

import argparse
import json
import os
from datetime import datetime
from pathlib import Path


def get_journal_path():
    """
    Path to the journal file at the project root.

    The journal is always stored at .kora-agent/journal/guideline.md relative to
    the project root (where the Claude Code agent runs).

    The project root is identified by the presence of:
    - .git/ (git repository)
    - CLAUDE.md or .claude/ (Claude Code project)
    """
    current = Path.cwd()

    # Walk up until the project root is found
    while current != current.parent:
        # Check for project root indicators
        is_root = (
            (current / '.git').exists() or
            (current / 'CLAUDE.md').exists() or
            (current / '.claude').exists()
        )

        if is_root:
            # Found the project root — create .kora-agent/journal here
            journal_dir = current / '.kora-agent' / 'journal'
            journal_dir.mkdir(parents=True, exist_ok=True)
            return journal_dir / 'guideline.md'

        current = current.parent

    # If the root was not found — fall back to the home directory
    home = Path.home()
    journal_dir = home / '.kora-agent' / 'journal'
    journal_dir.mkdir(parents=True, exist_ok=True)
    return journal_dir / 'guideline.md'


def get_kora_root():
    """KORA root directory (for internal use)."""
    return Path(__file__).parent.parent


def add_entry(title, context, problem, solution, files, author):
    """Add a new entry to the journal."""
    journal_path = get_journal_path()
    date = datetime.now().strftime('%Y-%m-%d')

    # Build the new entry
    entry = f"""
### {date} — {title}

**Context:** {context}

**Problem:** {problem}

**Solution:** {solution}

**Files affected:**
"""

    for f in files:
        entry += f"- `{f}`\n"

    entry += f"\n**Author:** {author}\n\n---\n"

    # Read the existing journal
    if journal_path.exists():
        with open(journal_path, 'r', encoding='utf-8') as f:
            content = f.read()
    else:
        content = "# KORA SKILL — Journal of Improvements\n\nAutomatic collection of improvements, fixes, and clarifications made during development.\n\n---\n\n"

    # Find the insertion point (after the header and intro, before the first entry)
    # Insert the new entry first
    parts = content.split('## Journal entries', 1)
    if len(parts) == 2:
        new_content = parts[0] + '## Journal entries\n' + entry + parts[1]
    else:
        new_content = content + '\n' + entry

    # Write the updated journal
    with open(journal_path, 'w', encoding='utf-8') as f:
        f.write(new_content)

    print(f"✓ Entry added to journal: {journal_path}")


def list_entries(limit=10):
    """Print the most recent entries from the journal."""
    journal_path = get_journal_path()

    if not journal_path.exists():
        print("Journal not found. Create the first entry.")
        return

    with open(journal_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Extract entry headers
    entries = []
    lines = content.split('\n')
    current_entry = None

    for line in lines:
        if line.startswith('### '):
            if current_entry:
                entries.append(current_entry)
            current_entry = line[4:]  # Strip "### "
        elif current_entry and line.startswith('**Author:**'):
            entries.append(current_entry)
            current_entry = None

    print(f"\nLast {min(limit, len(entries))} of {len(entries)} entries:\n")
    for i, entry in enumerate(entries[:limit], 1):
        print(f"{i}. {entry}")


def export_entries(since_date):
    """Export entries from the specified date."""
    journal_path = get_journal_path()

    if not journal_path.exists():
        print("Journal not found.")
        return

    with open(journal_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Simple filtering by date in the header
    lines = content.split('\n')
    exported = []
    current_entry = []
    in_entry = False

    for line in lines:
        if line.startswith('### '):
            # Check the date in the header (format: ### YYYY-MM-DD — ...)
            if in_entry and current_entry:
                exported.append('\n'.join(current_entry))

            header_date = line[4:14] if len(line) >= 14 else None
            if header_date and header_date >= since_date:
                in_entry = True
                current_entry = [line]
            else:
                in_entry = False
                current_entry = []
        elif in_entry:
            current_entry.append(line)

    if in_entry and current_entry:
        exported.append('\n'.join(current_entry))

    if exported:
        print(f"\nExporting entries since {since_date}:\n")
        print('=' * 80)
        for entry in exported:
            print(entry)
            print('=' * 80)
        print(f"\nTotal entries: {len(exported)}")
    else:
        print(f"No entries found since {since_date}.")


def status():
    """Show journal status."""
    journal_path = get_journal_path()
    kora_root = get_kora_root()

    print("\n📊 KORA Journal Status\n")
    print(f"KORA root: {kora_root}")
    print(f"Journal file: {journal_path}")

    if journal_path.exists():
        with open(journal_path, 'r', encoding='utf-8') as f:
            content = f.read()

        entry_count = content.count('### ')
        print(f"Entries in journal: {entry_count}")

        # Last 3 entries
        print("\nMost recent entries:")
        lines = content.split('\n')
        shown = 0
        for line in lines:
            if line.startswith('### '):
                print(f"  - {line[4:]}")
                shown += 1
                if shown >= 3:
                    break
    else:
        print("Journal not found.")


def main():
    parser = argparse.ArgumentParser(
        description='KORA Journal — skill improvement journal'
    )
    subparsers = parser.add_subparsers(dest='command', help='Commands')

    # Command: add
    add_parser = subparsers.add_parser('add', help='Add an entry to the journal')
    add_parser.add_argument('title', help='Title of the change')
    add_parser.add_argument('--context', required=True, help='Context (what was being done)')
    add_parser.add_argument('--problem', required=True, help='Problem (what was wrong)')
    add_parser.add_argument('--solution', required=True, help='Solution (how it was fixed)')
    add_parser.add_argument('--files', nargs='+', required=True, help='Affected files')
    add_parser.add_argument('--author', default=os.getenv('USER', 'anonymous'),
                          help='Author of the change')

    # Command: list
    list_parser = subparsers.add_parser('list', help='Show journal entries')
    list_parser.add_argument('--limit', type=int, default=10, help='Maximum number of entries')

    # Command: export
    export_parser = subparsers.add_parser('export', help='Export entries')
    export_parser.add_argument('--since', required=True, help='Date (YYYY-MM-DD)')

    # Command: status
    subparsers.add_parser('status', help='Show journal status')

    args = parser.parse_args()

    if args.command == 'add':
        add_entry(
            title=args.title,
            context=args.context,
            problem=args.problem,
            solution=args.solution,
            files=args.files,
            author=args.author
        )
    elif args.command == 'list':
        list_entries(limit=args.limit)
    elif args.command == 'export':
        export_entries(since_date=args.since)
    elif args.command == 'status':
        status()
    elif args.command == 'git':
        detect_changes_from_git()
    else:
        parser.print_help()


if __name__ == '__main__':
    main()
