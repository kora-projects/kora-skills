# Kora Journal

Continuous improvement journal for KORA SKILL — automatic collection of fixes and improvements.

## When to Use

- Fixes for inaccuracies in documentation
- Improvements to examples and patterns
- New working patterns
- Version updates (Kora, Gradle)
- Working solutions for known issues
- Formulated best practices

## Quick Start

```bash
# From the project root (where the Claude Code agent runs)
python kora-journal/scripts/kora_journal.py add "Fixed example" \
  --context "Working on HTTP client" \
  --problem "Example did not show error handling" \
  --solution "Added try-catch" \
  --files kora-http-client/references/interceptors-reference.md
```

**The journal is created at the project root:**
```
/Users/a.kurako/IdeaProjects/opensource/claude-skills/
├── .kora-agent/journal/guideline.md  ← Journal (not in git)
```

## Key Features

- Local storage (.kora-agent/journal/, not in git)
- CLI for journal management
- Entry export for integration
- Entry templating
- Weekly review workflow

## Triggers

journal, improvement, fix, update, kora-journal, .kora-agent/journal

## Resources

- **SKILL.md** — full documentation
- **references/** — journal-workflow.md
- **assets/** — journal-entry-template.md
- **scripts/** — kora_journal.py CLI
