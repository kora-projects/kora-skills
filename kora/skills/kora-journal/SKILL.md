---
name: kora-journal
description: Continuous improvement journal for KORA SKILL — automatic collection of fixes and improvements during development. Use when fixing documentation issues, adding code examples, discovering Kora workarounds, updating Kora/Gradle versions, or formulating best practices. Triggers: kora_journal.py add/list/export/status, .kora-agent/journal/guideline.md, Kora-specific improvements, skill documentation fixes.
---

# Kora Journal SKILL

**Continuous improvement of KORA SKILL through a changelog journal.**

## Read This First

**Purpose:** A journal for automatically collecting fixes, clarifications, and improvements made during work with KORA SKILL.

> **⚠️ Important:** The journal is intended **ONLY for Kora-specific things**.  
> Record changes related to the Kora Framework: skill documentation, code examples,  
> scripts, templates, references. Do not record your application's business logic.

**When to use (Kora-specific):**
- ✅ Fixes for inaccuracies in KORA skill documentation
- ✅ Improvements to code examples for Kora (controllers, repositories, services)
- ✅ New patterns for working with Kora (DI, AOP, configuration)
- ✅ Version updates for Kora, Gradle, Kora dependencies
- ✅ Working solutions for Kora issues
- ✅ Formulated best practices for Kora development

**Do not use for:**
- ❌ Temporary fixes specific to a single project (unrelated to Kora)
- ❌ Style preferences without a functional difference
- ❌ Errors corrected immediately
- ❌ **Non-Kora things:** application business logic, domain rules, UI/UX

Read this first when:
- fixing documentation issues in KORA skill files during development sessions,
- adding new code examples or templates for Kora patterns,
- discovering working solutions for Kora framework issues or bugs,
- updating Kora, Gradle, or Kora dependency versions,
- formulating new best practices for Kora development,
- preparing skill releases by exporting and integrating journal entries.

## Quick Start

```bash
# Add an entry to the journal (from the project root)
python kora-journal/scripts/kora_journal.py add "Fixed HTTP client example" \
  --context "Implementing an interceptor" \
  --problem "Example did not show error handling" \
  --solution "Added try-catch and logging" \
  --files kora-http-client/references/interceptors-reference.md

# View the most recent entries
python kora-journal/scripts/kora_journal.py list --limit 10

# Export entries from a date
python kora-journal/scripts/kora_journal.py export --since 2026-05-01

# Journal status
python kora-journal/scripts/kora_journal.py status
```

**Important:** The journal is created at the **project root** (where the Claude Code agent runs):
```
/Users/a.kurako/IdeaProjects/opensource/claude-skills/
├── .kora-agent/
│   └── journal/
│       └── guideline.md  ← Journal (not in git)
├── 
│   └── kora-journal/     ← Skill with CLI script
```

## Core Concepts

### Architecture

```
Project (root, where the agent runs)
├── .kora-agent/
│   └── journal/
│       └── guideline.md  ← Local journal (not in git)
│
└── 
    └── kora-journal/
        ├── SKILL.md                       ← This file
        ├── scripts/
        │   └── kora_journal.py           ← CLI for journal management
        ├── references/
        │   └── journal-workflow.md       ← Detailed workflow
        └── assets/
            └── journal-entry-template.md ← Entry template
```

### Workflow

1. **During the session** — the user fixes something in code/documentation
2. **Record in journal** — the assistant adds an entry via the script
3. **Accumulation** — entries are collected in `.kora-agent/journal/guideline.md`
4. **Integration** — entries are periodically incorporated into the main SKILL.md files
5. **Cleanup** — the journal is cleared after integration

### Entry Format

```markdown
### YYYY-MM-DD — Brief description

**Context:** What the user was doing

**Problem:** What was wrong

**Solution:** How it was fixed

**Files affected:**
- `kora-<module>/...`

**Author:** @username
```

## Common Pitfalls

❌ **Recording temporary fixes** — only universal improvements  
❌ **Duplicating entries** — check existing entries before adding  
❌ **Committing to git** — `.kora-agent/` is excluded in .gitignore  
❌ **Ignoring the journal** — review and integrate entries regularly  

✅ **Be specific** — specify exact files and changes  
✅ **Export before release** — collect improvements before publishing  
✅ **Integrate weekly** — do not accumulate more than 10–15 entries  

## Scripts

| Script | Description |
|--------|-------------|
| `kora_journal.py add` | Add an entry to the journal |
| `kora_journal.py list` | Show the most recent entries |
| `kora_journal.py export` | Export entries from a date |
| `kora_journal.py status` | Show journal status |

## Resources

- **SKILL.md** — this file
- **references/journal-workflow.md** — detailed workflow
- **assets/journal-entry-template.md** — entry template
- **scripts/kora_journal.py** — CLI tool
