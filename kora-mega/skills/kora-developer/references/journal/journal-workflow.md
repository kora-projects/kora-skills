# Kora Journal Workflow

**Source:** `.kora-agent/journal/guideline.md` (at the project root)

## Overview

Continuous improvement journal for KORA SKILL — a mechanism for collecting and integrating fixes during development.

> **⚠️ Important:** The journal is intended **ONLY for Kora-specific things**.  
> Do not record your application's business logic — only improvements to Kora skills.

## Workflow

### 1. Adding an entry (during a session)

```bash
# From the project root (where the Claude Code agent runs)
python kora-journal/scripts/kora_journal.py add "Title" \
  --context "..." \
  --problem "..." \
  --solution "..." \
  --files kora-module/file.md
```

**Triggers for adding (Kora-specific):**
- User fixed an error in KORA skill documentation
- User added a new code example for Kora
- A working solution for Kora was discovered and recorded
- Kora, Gradle, or a Kora dependency version was updated
- A new best practice for Kora development was formulated

### 2. Viewing entries

```bash
# Last 10 entries
python kora-journal/scripts/kora_journal.py list --limit 10

# All entries
python kora-journal/scripts/kora_journal.py list
```

### 3. Export for integration

```bash
# Export entries since May 1, 2026
python kora-journal/scripts/kora_journal.py export --since 2026-05-01
```

### 4. Integration into SKILL.md

After export:
1. Review the exported entries
2. Apply changes to the corresponding SKILL.md and reference files
3. Update the journal (clear the integrated entries)

### 5. Journal status

```bash
python kora-journal/scripts/kora_journal.py status
```

## Storage

**Location:** `.kora-agent/journal/guideline.md` at the **project root**

**For example:**
```
/Users/a.kurako/IdeaProjects/opensource/claude-skills/  ← Project root
├── .kora-agent/
│   └── journal/
│       └── guideline.md  ← Journal (not in git)
├── 
│   └── kora-journal/     ← Skill with CLI
```

**Git:** Excluded via `.gitignore`  
**Transfer:** Via export/import between developers

## Best Practices

- **Regularity:** Integrate entries weekly
- **Specificity:** Specify exact files and changes
- **Timeliness:** Do not accumulate more than 10–15 entries
- **Export:** Export before a skill release
