# Repo scripts

## `version.py` — single source of truth for the plugin version

The plugin version appears in seven places across five files (two manifests carry it twice).
Never edit them by hand — they drift. The canonical value lives in
`plugins/kora-v1/.claude-plugin/plugin.json`; this script propagates it everywhere and verifies it.

```bash
python scripts/version.py            # print the canonical version
python scripts/version.py check      # exit 1 if any file drifts — wire into CI / pre-commit
python scripts/version.py set 0.3.0  # write an explicit version everywhere
python scripts/version.py bump patch # 0.2.0 -> 0.2.1 (also: minor, major)
```

Synced files: `.claude-plugin/marketplace.json` (marketplace + plugin entry),
`plugins/kora-v1/.claude-plugin/plugin.json`, `plugins/kora-v1/.codex-plugin/plugin.json`,
`plugins/kora-v1/skill.json`, `plugins/kora-v1/SKILL.md`, and
`plugins/kora-v1/skills/kora-starter/SKILL.md`.

`.agents/plugins/marketplace.json` carries no version field, so it is intentionally not touched.
Pure standard library — no `jq`, no PyYAML.
