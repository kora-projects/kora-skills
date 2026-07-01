---
name: kora-journal
description: "Journal for Kora Framework incorrect usage (agent self-realized or user-pointed). Global shared journal at ~/.kora-journal/<project>/<module>/<YYYY-MM-DD>_slug.md. Each entry is a separate file. Use when - agent used wrong Kora annotation, hallucinated Kora API, misapplied Kora pattern, violated Kora best practices, skill docs unclear/wrong. Triggers - kora_journal.py add/list/export/integrate/status/search. NOT for project-specific business logic."
---

# Kora Journal — Continuous Improvement for Kora Skills

**Location:** `~/.kora-journal/<project>/<module>/<YYYY-MM-DD>_slug.md`

**Format:** Each entry is a **separate Markdown file** for easy management, export, and integration.

---

## ⚠️ READ FIRST — Purpose & Scope

**Purpose:** Journal for recording **Kora Framework incorrect usage** discovered during development — when the agent used Kora incorrectly and realized it or the user pointed it out.

**⚠️ SCOPE — Kora Incorrect Usage ONLY:**

| ✅ Record in Journal | ❌ Do NOT Record |
|----------------------|------------------|
| Agent used wrong Kora annotation (self-realized or user-pointed) | Application business logic |
| Agent hallucinated non-existent Kora API | Project-specific domain rules |
| Agent misapplied Kora pattern (DI, AOP, config, etc.) | Temporary project workarounds |
| Agent violated Kora best practices from skills | UI/UX preferences |
| Skill documentation was unclear/wrong | Non-Kora framework issues |

**Trigger:** When YOU (agent) realize OR USER points out that you used Kora Framework incorrectly.

**Why:** Journal feeds skill improvements. Non-Kora entries clutter the journal and dilute its value.

---

## Quick Start

```bash
# Add entry (creates separate .md file, tags auto-generated)
python kora-journal/scripts/kora_journal.py add "Fixed HTTP client example" \
  --context "Implementing interceptor" \
  --problem "Example missing error handling" \
  --solution "Added try-catch and logging" \
  --files kora-http-client/references/interceptors-reference.md

# Add entry with custom tags
python kora-journal/scripts/kora_journal.py add "OAuth2 token refresh" \
  --context "..." --problem "..." --solution "..." --files ... \
  --tags auth oauth2 client token

# Search journal by keywords (use AFTER reading references)
python kora-journal/scripts/kora_journal.py search "http interceptor auth" --limit 5

# Search by tags only (more precise)
python kora-journal/scripts/kora_journal.py search "auth oauth2" --by-tags

# View recent entries
python kora-journal/scripts/kora_journal.py list --limit 10

# Export pending entries from date
python kora-journal/scripts/kora_journal.py export --since 2026-05-01 --status pending

# Mark entry as integrated after applying to skills
python kora-journal/scripts/kora_journal.py integrate 2026-06-20_fixed-http-client.md

# Check status
python kora-journal/scripts/kora_journal.py status
```

---

## Storage Structure

**Global location:** `~/.kora-journal/` (shared across ALL sessions and projects)

```
~/.kora-journal/
├── kora-skills/                    # Project name (from git repo)
│   └── kora-iter4/                 # Gradle module name
│       ├── 2026-06-20_fixed-http-client-example.md
│       ├── 2026-06-19_jdbc-repository-mapper-auto-discovery.md
│       ├── 2026-06-18_openapi-oneof-workaround.md
│       └── ...                     # Each entry is a separate file
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
- ✅ Status tracking per entry (pending → integrated → archived)
- ✅ All sessions share the same journal location
- ✅ Survives project deletion

**Git:** Excluded via `~/.kora-journal/` in global `.gitignore`.

---

## Workflow

### 1. During Session — Record Discovery

When you fix a Kora issue or discover a pattern:

```bash
python kora-journal/scripts/kora_journal.py add "Title" \
  --context "What you were doing" \
  --problem "What went wrong / was unclear" \
  --solution "How you fixed it" \
  --files skills/kora-xxx/SKILL.md
```

Creates: `~/.kora-journal/<project>/<module>/YYYY-MM-DD_slug.md`

### 2. Before Similar Work — Review Journal

```bash
# Last 10 pending entries
python kora-journal/scripts/kora_journal.py list --limit 10 --status pending

# All entries
python kora-journal/scripts/kora_journal.py list
```

### 3. Export for Integration

```bash
# Export only pending entries from date
python kora-journal/scripts/kora_journal.py export --since 2026-05-01 --status pending
```

### 4. Apply Changes to Skills

Review exported entries and apply changes to:
- `skills/kora-xxx/SKILL.md`
- `skills/kora-xxx/references/xxx-reference.md`

### 5. Mark as Integrated

After applying changes:

```bash
python kora-journal/scripts/kora_journal.py integrate 2026-06-20_fixed-http-client.md
```

Updates entry status: `pending` → `integrated`

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

## Status Lifecycle

```
pending ──→ integrated ──→ archived
  │            │              │
  │            │              │
  └─ New entry └─ Applied to  └─ Old entries
     created      skills        (cleanup)
```

| Status | Meaning | Action |
|--------|---------|--------|
| `pending` | Not yet integrated | Export and apply to skills |
| `integrated` | Applied to skills | Review periodically |
| `archived` | Old, can be deleted | Clean up quarterly |

---

## Commands Reference

| Command | Description |
|---------|-------------|
| `add "Title" --context --problem --solution --files` | Add new entry (creates separate .md file) |
| `add "Title" ... --tags tag1 tag2` | Add entry with custom tags (auto-generated if omitted) |
| `search "keywords" --limit N --status STATUS` | Search entries by keywords (in content + tags) |
| `search "keywords" --by-tags` | Search only in tags (more precise) |
| `list --limit N --status STATUS` | Show entries (filter by status) |
| `export --since YYYY-MM-DD --status STATUS` | Export entries (filter by status) |
| `integrate FILENAME --status STATUS` | Mark entry as integrated/archived |
| `status` | Show journal location and counts |

---

## Tags System

**Tags are auto-generated** from title and problem/solution text when you add an entry. Common auto-detected tags:

| Category | Tags |
|----------|------|
| **HTTP** | `http`, `client`, `server`, `controller`, `interceptor`, `request`, `response` |
| **Database** | `database`, `jdbc`, `repository`, `query`, `sql` |
| **DI** | `di`, `component`, `module`, `injection`, `dependency`, `graph` |
| **AOP** | `aop`, `cache`, `cacheable`, `retry`, `circuit`, `schedule`, `log`, `valid` |
| **Config** | `config`, `hocon`, `yaml`, `source` |
| **OpenAPI** | `openapi`, `delegate`, `model`, `schema` |
| **Kafka** | `kafka`, `listener`, `publisher`, `consumer`, `producer` |
| **gRPC** | `grpc`, `stub` |
| **Auth** | `auth`, `principal`, `token`, `bearer`, `apikey` |
| **Test** | `test`, `koraapptest`, `testcontainers` |
| **JSON** | `json`, `dto`, `serialization` |

**Override auto-generated tags:**
```bash
python kora-journal/scripts/kora_journal.py add "OAuth2 token refresh" \
  --context "..." --problem "..." --solution "..." --files ... \
  --tags auth oauth2 client token
```

**Search by tags (more precise than content search):**
```bash
python kora-journal/scripts/kora_journal.py search "auth oauth2" --by-tags
```

---

## Common Pitfalls

| ❌ Wrong | ✅ Correct |
|----------|------------|
| Recording business logic | Recording Kora patterns only |
| Vague entries ("fixed bug") | Specific entries ("added @Tag(HttpServerModule)") |
| Not specifying files | Always list affected SKILL.md / reference files |
| Forgetting to mark as integrated | Run `integrate` after applying changes |
| Ignoring status filter | Use `--status pending` to focus on unprocessed |

---

## Best Practices

1. **Add immediately** — Record right after solving, don't rely on memory
2. **Be specific** — Include exact files, code snippets, commands
3. **Use status lifecycle** — `pending` → `integrated` → `archived`
4. **Export weekly** — `export --since YYYY-MM-DD --status pending`
5. **Integrate monthly** — Don't let pending entries accumulate beyond 20
6. **Archive quarterly** — Clean up old integrated entries

---

## See Also

- [Journal Workflow](references/journal-workflow.md) — Detailed workflow
- [Entry Template](assets/journal-entry-template.md) — Entry format template
