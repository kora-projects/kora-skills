#!/usr/bin/env python3
"""
Kora Journal — Continuous improvement journal for Kora skills.

Storage: ~/.kora-journal/<project>/<module>/<YYYY-MM-DD>_<slug>.md

Each entry is a separate file for easy management, export, and integration.

Usage:
    python kora_journal.py add "Title" --files file1.md --context "..." --problem "..." --solution "..."
    python kora_journal.py list --limit 10
    python kora_journal.py export --since 2026-05-01
    python kora_journal.py status
    python kora_journal.py integrate <entry-file.md>
"""

import argparse
import os
import re
import shutil
from datetime import datetime
from pathlib import Path


def get_project_name():
    """
    Get project name from current directory or git remote.
    
    Priority:
    1. Git remote name (e.g., 'kora-skills' from 'github:user/kora-skills.git')
    2. Parent directory name
    3. Current directory name
    """
    current = Path.cwd()
    project_name = current.name
    
    # Try to get from git remote
    try:
        import subprocess
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
    
    # Sanitize
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
            content = settings_path.read_text()
            match = re.search(r'rootProject\.name\s*=\s*["\']([^"\']+)["\']', content)
            if match:
                return match.group(1)
    
    module_name = current.name
    module_name = re.sub(r'[^a-zA-Z0-9]+', '-', module_name).strip('-').lower()
    return module_name or 'default'


def get_journal_dir():
    """
    Get journal directory: ~/.kora-journal/<project>/<module>/
    
    Each entry is stored as a separate file: YYYY-MM-DD_slug.md
    """
    home = Path.home()
    project = get_project_name()
    module = get_gradle_module()
    
    journal_dir = home / '.kora-journal' / project / module
    journal_dir.mkdir(parents=True, exist_ok=True)
    
    return journal_dir


def slugify(title):
    """Convert title to URL-safe slug."""
    slug = title.lower()
    slug = re.sub(r'[^a-z0-9]+', '-', slug)
    slug = slug.strip('-')
    return slug[:50]  # Limit length


def get_entry_filename(title, date):
    """Generate filename for entry: YYYY-MM-DD_slug.md"""
    slug = slugify(title)
    return f"{date}_{slug}.md"


def add_entry(title, context, problem, solution, files, author, tags=None):
    """Add a new entry as a separate file."""
    journal_dir = get_journal_dir()
    date = datetime.now().strftime('%Y-%m-%d')
    timestamp = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
    
    filename = get_entry_filename(title, date)
    entry_path = journal_dir / filename
    
    # Handle duplicate filenames (same title on same day)
    counter = 1
    while entry_path.exists():
        filename = f"{date}_{slug}_{counter}.md"
        entry_path = journal_dir / filename
        counter += 1
    
    project = get_project_name()
    module = get_gradle_module()
    
    # Auto-generate tags from title and problem if not provided
    if not tags:
        tags = []
        # Extract keywords from title
        title_words = re.findall(r'\b[a-zA-Z]{4,}\b', title.lower())
        tags.extend([w for w in title_words if w not in ['fixed', 'added', 'updated', 'changed', 'with', 'from', 'that', 'this', 'what', 'when', 'were']])
        # Extract Kora-specific tags from problem/solution
        kora_tags = {
            'http': ['http', 'controller', 'route', 'interceptor', 'request', 'response'],
            'client': ['client', 'httpclient'],
            'database': ['database', 'jdbc', 'repository', 'query', 'sql'],
            'di': ['component', 'module', 'injection', 'dependency', 'graph'],
            'aop': ['cache', 'cacheable', 'retry', 'circuit', 'schedule', 'log', 'valid'],
            'config': ['config', 'hocon', 'yaml', 'source'],
            'openapi': ['openapi', 'delegate', 'controller', 'model', 'schema'],
            'kafka': ['kafka', 'listener', 'publisher', 'consumer', 'producer'],
            'grpc': ['grpc', 'server', 'client', 'stub'],
            'auth': ['auth', 'principal', 'token', 'bearer', 'apikey'],
            'test': ['test', 'koraapptest', 'testcontainers'],
            'json': ['json', 'dto', 'serialization'],
        }
        problem_lower = (problem + ' ' + solution).lower()
        for tag, keywords in kora_tags.items():
            if any(kw in problem_lower for kw in keywords):
                tags.append(tag)
        tags = list(set(tags))[:10]  # Limit to 10 tags
    
    tags_yaml = ', '.join(f'"{t}"' for t in tags) if tags else '[]'
    
    content = f"""---
title: "{title}"
date: {date}
project: {project}
module: {module}
author: {author}
tags: [{tags_yaml}]
---

# {title}

**Date:** {date}  
**Project:** {project}  
**Module:** {module}  
**Author:** {author}

---

## Context

{context}

## Problem

{problem}

## Solution

{solution}

## Files Affected

"""
    
    for f in files:
        content += f"- `{f}`\n"
    
    content += f"""
---

## Metadata

- **Created:** {timestamp}
- **Status:** pending  # pending → integrated → archived
- **Integrated:** 

"""
    
    entry_path.write_text(content, encoding='utf-8')
    print(f"✓ Entry added: {entry_path}")


def list_entries(limit=10, status=None):
    """Print the most recent entries."""
    journal_dir = get_journal_dir()
    
    if not journal_dir.exists():
        print("Journal not found. Add the first entry.")
        return
    
    # Find all entry files
    entries = sorted(journal_dir.glob('*.md'), reverse=True)
    
    if not entries:
        print("No entries yet.")
        return
    
    print(f"\nLast {min(limit, len(entries))} of {len(entries)} entries:\n")
    
    for i, entry_path in enumerate(entries[:limit], 1):
        content = entry_path.read_text(encoding='utf-8')
        
        # Extract title from frontmatter
        title_match = re.search(r'^title:\s*"([^"]+)"', content, re.MULTILINE)
        date_match = re.search(r'^date:\s*(\d{4}-\d{2}-\d{2})', content, re.MULTILINE)
        status_match = re.search(r'Status:\s*(\w+)', content, re.MULTILINE)
        
        title = title_match.group(1) if title_match else entry_path.stem
        date = date_match.group(1) if date_match else 'unknown'
        status = status_match.group(1) if status_match else 'pending'
        
        # Filter by status if specified
        if status and status != status_match.group(1) if status_match else 'pending':
            continue
        
        print(f"{i}. [{status}] {date} — {title}")
        print(f"   File: {entry_path.name}")


def export_entries(since_date, status=None):
    """Export entries from the specified date."""
    journal_dir = get_journal_dir()
    
    if not journal_dir.exists():
        print("Journal not found.")
        return
    
    entries = sorted(journal_dir.glob('*.md'), reverse=True)
    exported = []
    
    for entry_path in entries:
        content = entry_path.read_text(encoding='utf-8')
        
        # Extract date from frontmatter
        date_match = re.search(r'^date:\s*(\d{4}-\d{2}-\d{2})', content, re.MULTILINE)
        if not date_match:
            continue
        
        entry_date = date_match.group(1)
        if entry_date < since_date:
            continue
        
        # Filter by status if specified
        if status:
            status_match = re.search(r'Status:\s*(\w+)', content, re.MULTILINE)
            entry_status = status_match.group(1) if status_match else 'pending'
            if entry_status != status:
                continue
        
        exported.append((entry_path, content))
    
    if exported:
        print(f"\nExporting {len(exported)} entries since {since_date}:\n")
        print('=' * 80)
        
        for entry_path, content in exported:
            print(f"\n## File: {entry_path.name}\n")
            # Print content without frontmatter
            body = re.sub(r'^---\n.*?\n---\n\n', '', content, flags=re.DOTALL)
            print(body)
            print('=' * 80)
        
        print(f"\nTotal: {len(exported)} entries")
    else:
        print(f"No entries found since {since_date}.")


def integrate_entry(entry_file, new_status='integrated'):
    """Mark an entry as integrated."""
    entry_path = Path(entry_file)
    
    if not entry_path.exists():
        # Try in journal dir
        journal_dir = get_journal_dir()
        entry_path = journal_dir / entry_file
        
        if not entry_path.exists():
            print(f"Entry not found: {entry_file}")
            return
    
    content = entry_path.read_text(encoding='utf-8')
    
    # Update status
    today = datetime.now().strftime('%Y-%m-%d')
    content = re.sub(
        r'Status:\s*pending',
        f'Status: {new_status}\n**Integrated:** {today}',
        content
    )
    
    entry_path.write_text(content, encoding='utf-8')
    print(f"✓ Entry marked as {new_status}: {entry_path.name}")


def search_entries(query, limit=10, status=None, by_tags=False):
    """Search entries by keywords in title, context, problem, solution, or tags."""
    journal_dir = get_journal_dir()
    
    if not journal_dir.exists():
        print("Journal not found.")
        return
    
    entries = list(journal_dir.glob('*.md'))
    keywords = query.lower().split()
    results = []
    
    for entry_path in entries:
        content = entry_path.read_text(encoding='utf-8')
        content_lower = content.lower()
        
        # Extract tags from frontmatter
        tags_match = re.search(r'^tags:\s*\[([^\]]*)\]', content, re.MULTILINE)
        entry_tags = []
        if tags_match:
            tags_str = tags_match.group(1)
            entry_tags = [t.strip().strip('"').strip("'") for t in tags_str.split(',') if t.strip()]
        
        # Search by tags if --by-tags flag is set
        if by_tags:
            # Match if any keyword matches any tag
            if not any(kw in entry_tags for kw in keywords):
                continue
        else:
            # Check if all keywords match in content (title, context, problem, solution, tags)
            if not all(kw in content_lower for kw in keywords):
            # Filter by status if specified
            if status and status != 'all':
                status_match = re.search(r'Status:\s*(\w+)', content, re.MULTILINE)
                entry_status = status_match.group(1) if status_match else 'pending'
                if entry_status != status:
                    continue
            
            # Extract metadata
            title_match = re.search(r'^title:\s*"([^"]+)"', content, re.MULTILINE)
            date_match = re.search(r'^date:\s*(\d{4}-\d{2}-\d{2})', content, re.MULTILINE)
            
            # Calculate relevance
            if by_tags:
                relevance = sum(1 for kw in keywords if kw in entry_tags)
            else:
                relevance = sum(1 for kw in keywords if kw in content_lower)
                # Boost relevance if keywords match tags
                relevance += sum(1 for kw in keywords if kw in entry_tags) * 2
            
            results.append({
                'path': entry_path,
                'title': title_match.group(1) if title_match else entry_path.stem,
                'date': date_match.group(1) if date_match else 'unknown',
                'relevance': relevance,
                'tags': entry_tags
            })
    
    # Sort by relevance (keyword matches) and date
    results.sort(key=lambda x: (-x['relevance'], x['date']), reverse=False)
    
    if results:
        print(f"\nFound {len(results)} entries matching '{query}':\n")
        for i, result in enumerate(results[:limit], 1):
            tags_str = ', '.join(result['tags'][:5]) if result['tags'] else 'no tags'
            print(f"{i}. [{result['date']}] {result['title']}")
            print(f"   File: {result['path'].name}")
            print(f"   Tags: {tags_str}")
            print(f"   Relevance: {result['relevance']} points")
            print()
        
        if len(results) > limit:
            print(f"... and {len(results) - limit} more. Use --limit to see all.")
    else:
        print(f"No entries found matching '{query}'.")


def status():
    """Show journal status."""
    journal_dir = get_journal_dir()
    project = get_project_name()
    module = get_gradle_module()
    
    print("\n📊 Kora Journal Status\n")
    print(f"Project: {project}")
    print(f"Module:  {module}")
    print(f"Journal: {journal_dir}")
    
    if journal_dir.exists():
        entries = list(journal_dir.glob('*.md'))
        
        # Count by status
        status_counts = {'pending': 0, 'integrated': 0, 'archived': 0}
        for entry in entries:
            content = entry.read_text(encoding='utf-8')
            status_match = re.search(r'Status:\s*(\w+)', content, re.MULTILINE)
            status = status_match.group(1) if status_match else 'pending'
            status_counts[status] = status_counts.get(status, 0) + 1
        
        print(f"Total entries: {len(entries)}")
        print(f"  - Pending:    {status_counts.get('pending', 0)}")
        print(f"  - Integrated: {status_counts.get('integrated', 0)}")
        print(f"  - Archived:   {status_counts.get('archived', 0)}")
        
        # Recent entries
        if entries:
            print("\nRecent entries:")
            for entry in sorted(entries, reverse=True)[:5]:
                content = entry.read_text(encoding='utf-8')
                title_match = re.search(r'^title:\s*"([^"]+)"', content, re.MULTILINE)
                title = title_match.group(1) if title_match else entry.stem
                print(f"  - {entry.name}: {title}")
    else:
        print("Status: No journal yet (add first entry)")


def main():
    parser = argparse.ArgumentParser(description='Kora Journal — continuous improvement for Kora skills')
    subparsers = parser.add_subparsers(dest='command', help='Commands')
    
    # add
    add_parser = subparsers.add_parser('add', help='Add journal entry as separate file')
    add_parser.add_argument('title', help='Entry title')
    add_parser.add_argument('--context', required=True, help='What was being done')
    add_parser.add_argument('--problem', required=True, help='What went wrong')
    add_parser.add_argument('--solution', required=True, help='How it was fixed')
    add_parser.add_argument('--files', nargs='+', required=True, help='Affected files')
    add_parser.add_argument('--author', default=os.getenv('USER', 'anonymous'), help='Author')
    add_parser.add_argument('--tags', nargs='+', help='Keywords/tags for search (auto-generated if not provided)')
    
    # list
    list_parser = subparsers.add_parser('list', help='List entries')
    list_parser.add_argument('--limit', type=int, default=10, help='Max entries')
    list_parser.add_argument('--status', choices=['pending', 'integrated', 'archived'], help='Filter by status')
    
    # export
    export_parser = subparsers.add_parser('export', help='Export entries')
    export_parser.add_argument('--since', required=True, help='Date YYYY-MM-DD')
    export_parser.add_argument('--status', choices=['pending', 'integrated', 'archived'], default='pending', help='Filter by status')
    
    # integrate
    integrate_parser = subparsers.add_parser('integrate', help='Mark entry as integrated')
    integrate_parser.add_argument('entry', help='Entry filename or path')
    integrate_parser.add_argument('--status', default='integrated', choices=['integrated', 'archived'], help='New status')
    
    # search
    search_parser = subparsers.add_parser('search', help='Search entries by keywords or tags')
    search_parser.add_argument('query', help='Search query (keywords or tags)')
    search_parser.add_argument('--limit', type=int, default=10, help='Max results')
    search_parser.add_argument('--status', choices=['pending', 'integrated', 'archived', 'all'], default='all', help='Filter by status')
    search_parser.add_argument('--by-tags', action='store_true', help='Search only in tags (not in content)')
    
    # status
    subparsers.add_parser('status', help='Show status')
    
    args = parser.parse_args()
    
    if args.command == 'add':
        add_entry(args.title, args.context, args.problem, args.solution, args.files, args.author, args.tags)
    elif args.command == 'list':
        list_entries(args.limit, args.status)
    elif args.command == 'export':
        export_entries(args.since, args.status)
    elif args.command == 'integrate':
        integrate_entry(args.entry, args.status)
    elif args.command == 'search':
        search_entries(args.query, args.limit, args.status if args.status != 'all' else None, args.by_tags)
    elif args.command == 'status':
        status()
    else:
        parser.print_help()


if __name__ == '__main__':
    main()
