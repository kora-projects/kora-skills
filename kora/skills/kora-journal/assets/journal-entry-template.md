# Journal Entry Template

Template for adding entries to the KORA SKILL improvement journal.

---

## Template

```markdown
### YYYY-MM-DD — Brief description of the change

**Context:** What the user was doing (what task was being solved)

**Problem:** What was wrong or missing

**Solution:** How it was fixed or improved

**Files affected:**
- `kora-<module>/references/<file>.md`
- `kora-<module>/SKILL.md`

**Author:** @username
```

---

## Examples

### Example 1: Documentation fix

```markdown
### 2026-05-18 — Added links to examples in all reference files

**Context:** The user requested that links to documentation and examples be added
to all reference files of KORA skills.

**Problem:** Reference files had no explicit links to external documentation
(.kora-agent/kora-docs) or examples (.kora-agent/kora-examples).

**Solution:** 
- Added a **Source:** line with a link to documentation in all 63 reference files
- Added an **Examples:** line with links to examples in all 63 reference files
- Used relative paths for cross-platform compatibility

**Files affected:**
- `kora-bootstrap/references/*.md` (8 files)
- `kora-database/references/*.md` (6 files)
- `kora-http-server/references/*.md` (5 files)
- `kora-http-client/references/*.md` (4 files)
- `kora-openapi/references/*.md` (6 files)
- `kora-json/references/*.md` (5 files)
- `kora-telemetry/references/*.md` (3 files)
- `kora-grpc/references/*.md` (2 files)
- `kora-kafka/references/*.md` (7 files)
- `kora-aop/references/*.md` (5 files)
- `kora-testing/references/*.md` (8 files)
- `kora-s3/references/s3-client.md` (1 file)
- `kora-mapstruct/references/mapstruct.md` (1 file)

**Author:** @anton-kurako
```

### Example 2: Version update

```markdown
### 2026-05-15 — Updated Gradle to version 9.5.1

**Context:** Kora Framework updated the minimum required Gradle version.

**Problem:** Project templates were using Gradle 8.x, which is incompatible with
the new version of Kora.

**Solution:** Updated all Gradle templates to version 9.5.1, added a version
compatibility table.

**Files affected:**
- `kora-bootstrap/assets/gradle-wrapper.properties.template`
- `kora-bootstrap/references/gradle-setup-reference.md`
- `kora-bootstrap/SKILL.md`

**Author:** @anton-kurako
```

---

## Usage

Copy the template and fill it in when adding a new entry:

```bash
python kora-journal/scripts/kora_journal.py add "Title" \
  --context "..." \
  --problem "..." \
  --solution "..." \
  --files file1.md file2.md
```
