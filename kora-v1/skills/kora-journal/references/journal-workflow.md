# Kora Journal Workflow

**Journal Location:** `~/.kora-journal/<project>/<module>/<YYYY-MM-DD>_slug.md`

**Format:** Each entry is a **separate Markdown file** for easy management.

---

## Overview

Continuous improvement journal for Kora skills — a centralized mechanism for collecting and integrating fixes discovered during Kora development.

> **⚠️ Important:** Journal is for **Kora-specific improvements ONLY**. Do not record application business logic.

---

## Workflow

### 1. Adding an Entry (During Session)

```bash
# From any Kora project directory
python kora-journal/scripts/kora_journal.py add "Title" \
  --context "What you were doing" \
  --problem "What went wrong / was unclear" \
  --solution "How you fixed it" \
  --files skills/kora-xxx/SKILL.md
```

**Creates:** `~/.kora-journal/<project>/<module>/YYYY-MM-DD_slug.md`

**Triggers (Kora-specific):**
- ✅ Fixed error in Kora skill documentation
- ✅ Added new Kora code example / template
- ✅ Discovered working workaround for Kora issue
- ✅ Updated Kora/Gradle dependency version
- ✅ Formulated new Kora best practice

**Do NOT record:**
- ❌ Application business logic
- ❌ Domain-specific rules
- ❌ Temporary project-specific fixes
- ❌ Errors corrected immediately

---

### 2. Viewing Entries

```bash
# Last 10 pending entries
python kora-journal/scripts/kora_journal.py list --limit 10 --status pending

# All entries
python kora-journal/scripts/kora_journal.py list

# Only integrated entries
python kora-journal/scripts/kora_journal.py list --status integrated
```

---

### 3. Export for Integration

```bash
# Export only pending entries from date
python kora-journal/scripts/kora_journal.py export --since 2026-05-01 --status pending
```

---

### 4. Apply Changes to Skills

Review exported entries and apply changes to:
- `skills/kora-xxx/SKILL.md`
- `skills/kora-xxx/references/xxx-reference.md`

---

### 5. Mark as Integrated

After applying changes:

```bash
python kora-journal/scripts/kora_journal.py integrate 2026-06-20_fixed-http-client.md
```

Updates entry status: `pending` → `integrated`

To mark as archived:
```bash
python kora-journal/scripts/kora_journal.py integrate 2026-06-20_fixed-http-client.md --status archived
```

---

### 6. Journal Status

```bash
python kora-journal/scripts/kora_journal.py status
```

Shows:
- Project name
- Module name
- Journal directory path
- Entry count by status (pending / integrated / archived)
- Recent entries

---

## Storage Structure

```
~/.kora-journal/                        # Global shared location
├── kora-skills/                        # Project (from git repo name)
│   └── kora-iter4/                     # Module (from settings.gradle.kts)
│       ├── 2026-06-20_fixed-http-client-example.md
│       ├── 2026-06-19_jdbc-repository-mapper-auto-discovery.md
│       ├── 2026-06-18_openapi-oneof-workaround.md
│       └── ...                         # Each entry is a separate file
├── another-project/
│   └── service-module/
│       └── ...
└── ...
```

**Filename format:** `YYYY-MM-DD_slug-from-title.md`

**Benefits:**
- ✅ Each entry is atomic — easy to manage, move, delete
- ✅ No merge conflicts (separate files)
- ✅ Easy to export specific entries
- ✅ Status tracking per entry
- ✅ Shared across ALL sessions and projects
- ✅ Survives project deletion

**Git:** Add `~/.kora-journal/` to global `.gitignore`

---

## Status Lifecycle

```
pending ──→ integrated ──→ archived
  │            │              │
  │            │              │
  └─ New entry └─ Applied to  └─ Old entries
     created      skills        (cleanup)
```

| Status | Meaning | When to Use |
|--------|---------|-------------|
| `pending` | Not yet integrated | Default for new entries |
| `integrated` | Applied to skills | After applying changes to SKILL.md |
| `archived` | Old, ready for deletion | Quarterly cleanup |

---

## Best Practices

| Practice | Why |
|----------|-----|
| **Record immediately** | Don't rely on memory — add entry right after solving |
| **Be specific** | "Added @Tag(HttpServerModule)" not "fixed interceptor" |
| **List affected files** | Makes integration easier |
| **Use --status filter** | Focus on pending entries when exporting |
| **Review weekly** | `list --limit 20 --status pending` |
| **Integrate monthly** | Don't let pending entries grow beyond 20 |
| **Archive quarterly** | Clean up old integrated entries |

---

## Entry File Format

Each entry is a Markdown file with YAML frontmatter:

```yaml
---
title: "Fixed HTTP client example"
date: 2026-06-20
project: kora-skills
module: kora-iter4
author: dsudomoin
tags: []
---

# Fixed HTTP client example

**Date:** 2026-06-20  
**Project:** kora-skills  
**Module:** kora-iter4  
**Author:** dsudomoin

---

## Context

What you were doing when you encountered this issue.

## Problem

What went wrong? What was unclear? What blocked you?

## Solution

How you fixed it. Include code/config snippets if helpful.

## Files Affected

- `skills/kora-http-client/SKILL.md`
- `skills/kora-http-client/references/interceptors-reference.md`

---

## Metadata

- **Created:** 2026-06-20_14-30-00
- **Status:** pending  # pending → integrated → archived
- **Integrated:** 
```

---

## Troubleshooting

### Journal not found

Run `status` to see the expected path. Journal directory is created on first `add` command.

### Wrong project/module detected

Project name comes from git remote or directory name. Module name comes from `settings.gradle.kts` rootProject.name.

To override, rename the directory or edit the journal path manually.

### Too many pending entries

Export and integrate older entries:
```bash
python kora-journal/scripts/kora_journal.py export --since 2026-01-01 --status pending
# After integrating, mark each as integrated:
python kora-journal/scripts/kora_journal.py integrate 2026-01-15_*.md
```

### Entry file corrupted

Each entry is independent. If one file is corrupted, others are unaffected. You can delete and recreate the corrupted entry.

---

## See Also

- [Kora Journal SKILL.md](../SKILL.md) — Main skill documentation
- [Entry Template](../assets/journal-entry-template.md) — Entry format template
