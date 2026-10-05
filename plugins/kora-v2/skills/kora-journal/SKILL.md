---
name: kora-journal
description: "Journal for incorrect Kora usage (kora_journal.py add/search/integrate). Shared store at ~/.kora-journal/, one Markdown file per entry. Use when you or the user find a wrong Kora annotation, a hallucinated API or config key, a misapplied pattern, or a Kora 1.x API carried into a 2.0 project — and to search past entries before implementing anything non-trivial. Not for project business logic."
license: Apache-2.0
metadata:
  kora-version: "2.x"
---

# Kora Journal — Continuous Improvement for Kora Skills

> **Kora sub-skill — obey the [kora-v2 meta rules](../../SKILL.md) on every task:** **R0** ground the workspace on Kora 2.0 refs before starting (framework source at tag `2.0.0.RC2` + `kora-examples` at `migration/2.0` + Kora 2.0 docs at koraframework.io/v2, which trail the source; 1.x `kora-docs` pages are never an authority) · **R1** read this sub-skill before writing code · **R2** Kora 2.0 APIs only — no Spring/Micronaut/Quarkus, no Kora 1.x APIs, no invented annotations or config keys · **R3** journal any incorrect Kora usage. Add comments/Javadoc only if asked.

**This skill is tooling, not Kora API documentation.** It is the R3 feedback loop: a CLI that records
Kora mistakes so the next session does not repeat them.

**Location:** `~/.kora-journal/<project>/<module>/<YYYY-MM-DD>_slug.md`

**Format:** Each entry is a **separate Markdown file** for easy management, export, and integration.

**Kora line:** the store is shared with the Kora 1.x package. Entries written by this package carry
`kora: "2.x"` in their front matter; entries without that field are older and must be re-checked
against Kora 2.0 before you apply them. `search` prints the line for every hit.

---

## ⚠️ READ FIRST — Purpose & Scope

**Purpose:** Journal for recording **Kora Framework incorrect usage** discovered during development —
when the agent used Kora incorrectly and realized it or the user pointed it out.

**⚠️ SCOPE — Kora Incorrect Usage ONLY** (same table as R3 in the [meta-skill](../../SKILL.md)):

| ✅ Record in Journal | ❌ Do NOT Record |
|----------------------|------------------|
| Wrong Kora annotation used (self-realized or user-pointed) | Application business logic |
| Hallucinated Kora API or config key | Project-specific domain rules |
| **Kora 1.x API used in a 2.0 project** | Temporary project workarounds |
| Kora pattern misapplied (DI, AOP, config, telemetry) | UI/UX or style preferences |
| Kora best practice from a sub-skill violated | Non-Kora framework issues |
| Sub-skill documentation wrong, stale, or unclear | Anything already correct |
| Unrequested comments/Javadoc written (R2 breach) | |

**Trigger:** When YOU (agent) realize OR USER points out that you used Kora Framework incorrectly.

**Why:** The journal feeds skill improvements. Non-Kora entries clutter it and dilute its value.

**The highest-value entries in a 2.0 project are the silent ones** — code that compiles and a build
that stays green while the service is wrong. `@Tag(HttpServerModule.class)` on a global interceptor,
a `db { }` config section, `publicApiHttpPort`, telemetry left at its `false` default. Those are
exactly the mistakes nobody remembers a month later. See §4 of the [meta-skill](../../SKILL.md).

---

## Running the CLI

```bash
python3 skills/kora-journal/scripts/kora_journal.py <command> ...
```

- The script path is **relative to this skill package**, not to the project you are working in.
  From the `kora-starter` mirror it is `../kora-journal/scripts/kora_journal.py`. When the package
  is installed as a plugin, use the absolute path: the directory holding this `SKILL.md`, plus
  `scripts/kora_journal.py`.
- **Run it with the project as the working directory.** Project and module are derived from `cwd`
  (git remote name, then `settings.gradle[.kts]` `rootProject.name`), so running it from elsewhere
  files the entry under the wrong project.
- Use `python3`. On macOS and most Linux distributions there is no `python` on `PATH`. On a Windows
  install where only `python` exists, swap the two.
- No third-party packages. Python 3.7+.

---

## Quick Start

```bash
# Add entry (creates a separate .md file, tags auto-generated from the text)
python3 skills/kora-journal/scripts/kora_journal.py add "Global interceptor tagged with HttpServerModule never ran" \
  --context "Adding an API-key auth interceptor to a Kora 2.0 HTTP server" \
  --problem "Used @Tag(HttpServerModule.class); it compiled, the graph built, and the interceptor was never invoked" \
  --solution "2.0 collects global interceptors as @Tag(HttpServer.class) All<HttpServerInterceptor> in HttpServerModule.publicHttpApiRouter; retagged and added a test asserting 401" \
  --files skills/kora-http-server/SKILL.md

# Add entry with custom tags
python3 skills/kora-journal/scripts/kora_journal.py add "Carried ru.tinkoff.kora imports into a 2.0 service" \
  --context "..." --problem "..." --solution "..." --files ... \
  --tags kora1x migration di

# Search the journal by keywords (use AFTER reading references, BEFORE implementing)
python3 skills/kora-journal/scripts/kora_journal.py search "http interceptor auth" --limit 5

# Search by tags only (more precise)
python3 skills/kora-journal/scripts/kora_journal.py search "kora1x migration" --by-tags

# View recent entries of the current module
python3 skills/kora-journal/scripts/kora_journal.py list --limit 10

# Export pending entries from a date, across the whole store
python3 skills/kora-journal/scripts/kora_journal.py export --since 2026-08-01 --status pending

# Mark an entry as integrated after folding it into the skills
python3 skills/kora-journal/scripts/kora_journal.py integrate 2026-08-22_global-interceptor-tagged-with-httpservermodule-ne.md

# Check status
python3 skills/kora-journal/scripts/kora_journal.py status
```

---

## Storage Structure

**Shared location:** `~/.kora-journal/` — one store for **all** projects, sessions, and Kora skill
packages.

```
~/.kora-journal/
├── billing-service/                # Project name (git remote, else directory name)
│   └── billing-api/                # Gradle module (rootProject.name, else directory name)
│       ├── 2026-08-22_global-interceptor-tagged-with-httpservermodule-ne.md
│       ├── 2026-08-21_jdbc-config-section-still-named-db.md
│       ├── 2026-08-20_openapi-client-config-path-not-lower-camel.md
│       └── ...                     # Each entry is a separate file
├── another-project/
│   └── service-module/
│       └── ...
└── ...
```

**Filename format:** `YYYY-MM-DD_slug-from-title.md` (a repeated title on the same day gets `_1`, `_2`, …)

**Why one shared store rather than one per Kora version:**

- The store is keyed by project and module, not by framework version. A service mid-migration
  legitimately holds both 1.x and 2.0 entries; splitting them would cut one project's history in two.
- Entries written under the 1.x package stay valuable — most describe what an aspect, processor or
  config key actually does, which is still true, and the ones that describe a 1.x API are precisely
  the material you need when that API shows up in a 2.0 project.
- Both packages can be installed at once. A version-specific path would silently show a different
  journal depending on which one the agent happened to route through.
- The one real risk — applying a 1.x entry verbatim to 2.0 code — is handled by the `kora:` stamp
  and the `kora1x` tag, not by hiding the entries.

**Benefits:**
- ✅ Each entry is atomic — easy to manage, move, delete
- ✅ No merge conflicts (separate files)
- ✅ Easy to export specific entries
- ✅ Status tracking per entry (pending → integrated → archived)
- ✅ All sessions, projects and Kora packages share one journal
- ✅ Survives project deletion

**Git:** the store lives in your home directory, outside every repository — there is nothing to
`.gitignore`.

---

## Scope of a Command

Every read command takes `--scope`:

| Scope | Means | Default for |
|---|---|---|
| `module` | current project + module only | `list` |
| `project` | every module of the current project | — |
| `all` | the whole shared store, every project | `search`, `export` |

`search` defaults to `all` on purpose: a mistake made in another service is exactly the one you
want to find. Results outside the current module are printed as `<project>/<module>/<file>.md`,
which `integrate` accepts verbatim.

---

## Workflow

### 1. Before Implementing — Search First

Step 3 of the meta-skill's per-task procedure. Search before writing anything non-trivial:

```bash
python3 skills/kora-journal/scripts/kora_journal.py search "http interceptor auth" --limit 5
```

Hit → apply it, then `integrate <entry-file>`. Miss → continue, and expect to add an entry under R3.

### 2. During Session — Record the Mistake

When you realise you used Kora incorrectly:

```bash
python3 skills/kora-journal/scripts/kora_journal.py add "Title" \
  --context "What you were doing" \
  --problem "What went wrong / was unclear" \
  --solution "How you fixed it" \
  --files skills/kora-xxx/SKILL.md
```

Creates: `~/.kora-journal/<project>/<module>/YYYY-MM-DD_slug.md`

Always use the CLI. Hand-writing a file into the store skips the slug, the front matter, the
`kora:` stamp and the tags, so `search` and `integrate` will not see the entry properly.

### 3. Review Pending Work

```bash
# Last 10 pending entries of this module
python3 skills/kora-journal/scripts/kora_journal.py list --limit 10 --status pending

# Everything, everywhere
python3 skills/kora-journal/scripts/kora_journal.py list --scope all
```

### 4. Export for Integration

```bash
python3 skills/kora-journal/scripts/kora_journal.py export --since 2026-08-01 --status pending
```

### 5. Apply Changes to Skills

Review the exported entries and apply them to:
- `skills/kora-xxx/SKILL.md`
- `skills/kora-xxx/references/xxx-reference.md`

An entry whose `Kora line` is `unset` was written before the stamp existed, possibly against Kora
1.x — verify its claim against the 2.0 source before folding it into a 2.x skill.

### 6. Mark as Integrated

```bash
python3 skills/kora-journal/scripts/kora_journal.py integrate 2026-08-22_global-interceptor-tagged-with-httpservermodule-ne.md
```

Updates entry status: `pending` → `integrated`. Exits non-zero if the entry could not be resolved,
and refuses any path outside `~/.kora-journal/`.

---

## Entry File Format

Each entry is a Markdown file with YAML front matter:

```yaml
---
title: "Global interceptor tagged with HttpServerModule never ran"
date: 2026-08-22
project: billing-service
module: billing-api
author: dsudomoin
kora: "2.x"
tags: ["di", "http-server", "kora1x"]
---

# Global interceptor tagged with HttpServerModule never ran

**Date:** 2026-08-22
**Project:** billing-service
**Module:** billing-api
**Author:** dsudomoin
**Kora line:** 2.x

---

## Context

Adding an API-key auth interceptor to a Kora 2.0 HTTP server.

## Problem

Wrote `@Tag(HttpServerModule.class)` on the `HttpServerInterceptor`. It compiled and the graph
built — `HttpServerModule` still exists in 2.0 — but nothing looks interceptors up by it, so every
request went through unauthenticated.

## Solution

`HttpServerModule.publicHttpApiRouter` collects `@Tag(HttpServer.class) All<HttpServerInterceptor>`.
Retagged with `io.koraframework.http.server.common.HttpServer` and added a test asserting 401.

## Files Affected

- `skills/kora-http-server/SKILL.md`
- `skills/kora-http-server/references/interceptors-reference.md`

---

## Metadata

- **Created:** 2026-08-22_14-30-00
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
| `add "Title" --context --problem --solution --files` | Add new entry (creates a separate .md file) |
| `add "Title" ... --tags tag1 tag2` | Add entry with custom tags (auto-generated if omitted) |
| `search "keywords" --limit N --status STATUS --scope SCOPE` | Search entries by keywords (content + tags) |
| `search "keywords" --by-tags` | Search only in tags (more precise) |
| `list --limit N --status STATUS --scope SCOPE` | Show entries (filter by status) |
| `export --since YYYY-MM-DD --status STATUS --scope SCOPE` | Export entries (filter by status) |
| `integrate FILENAME --status STATUS` | Mark entry as integrated/archived |
| `status` | Show journal location, Kora line, and counts |

`--status` values: `pending`, `integrated`, `archived` (`search` also takes `all`, its default).
`--scope` values: `module`, `project`, `all`.

---

## Tags System

**Tags are auto-generated** from the whole entry text (title + context + problem + solution) when you
add an entry. The vocabulary is fixed and Kora-specific, so `--by-tags` stays precise:

| Tag | Applied when the entry mentions |
|---|---|
| `kora1x` | `ru.tinkoff.kora`, `kora-parent`, `json-module`, `HttpServerModule`, `publicApiHttpPort`, R2DBC/Vert.x, `Mono`/`Flux`/`CompletionStage`, suspend repositories |
| `migration` | migrating, porting from 1.x, OpenRewrite |
| `http-server` | `@HttpController`, `@HttpRoute`, `HttpServer*`, interceptor, Undertow, `HttpResponseEntity` |
| `http-client` | `@HttpClient`, `@ResponseCodeMapper` |
| `database` | JDBC, repository, `@EntityJdbc`, Cassandra, Flyway, Liquibase, SQL, `inTx`, PostgreSQL, `PgRange`, `@PgJson` |
| `di` | `@KoraApp`, component, submodule, graph, `ValueOf`, `Lifecycle`, `@Conditional`, `@Root` |
| `aop` | `@Cacheable`, `@CachePut`, `@CacheInvalidate`, aspect, `@Mapping` |
| `config` | `@ConfigSource`, `@ConfigMapper`, `ConfigValueMapper`, HOCON, `application.conf/.yaml` |
| `openapi` | OpenAPI, delegate, `ApiSecurity`, Swagger, Scalar |
| `kafka` | Kafka |
| `grpc` | gRPC, protobuf, stub |
| `auth` | principal, bearer, API key, OAuth, authorization |
| `json` | JSON, Jackson, serialization |
| `telemetry` | telemetry, metrics, tracing, Micrometer, OpenTelemetry, Logback, masking, `DataMasker`, `JsonRecordEncoder` |
| `resilient` | `@CircuitBreakable`, `@Retryable`, `@Timeout`, `@RateLimited`, `@Fallback`, `RetryBudget`, `NonRetryableException`, `NonCircuitableException` |
| `scheduling` | `@Schedule*`, Quartz, db-scheduler, cron |
| `validation` | `@Valid`, `@Validate`, violation, constraint |
| `s3` | `@S3`, `S3Client`, bucket |
| `test` | `@KoraAppTest`, Testcontainers, JUnit, MockK, Mockito |
| `build` | Gradle, annotation processor, KSP, `kora-bom`, toolchain |
| `nullability` | JSpecify, `@Nullable`, `@NullMarked` |

When nothing matches, `add` says so and the entry is stored untagged — pass `--tags` to make it
findable by tag.

**Override auto-generated tags:**
```bash
python3 skills/kora-journal/scripts/kora_journal.py add "Carried ru.tinkoff.kora imports into a 2.0 service" \
  --context "..." --problem "..." --solution "..." --files ... \
  --tags kora1x migration di
```

**Search by tags (more precise than content search):**
```bash
python3 skills/kora-journal/scripts/kora_journal.py search "kora1x" --by-tags
```

---

## Common Pitfalls

| ❌ Wrong | ✅ Correct |
|----------|------------|
| Recording business logic | Recording Kora usage mistakes only |
| Vague entries ("fixed bug") | Specific entries ("`@Tag(HttpServerModule.class)` compiled but the interceptor never ran; 2.0 uses `@Tag(HttpServer.class)`") |
| Hand-writing a file into `~/.kora-journal/` | Always `add` — it owns the slug, front matter, `kora:` stamp and tags |
| Not specifying files | Always list the affected SKILL.md / reference files |
| Forgetting to mark as integrated | Run `integrate` after applying changes |
| Ignoring status filter | Use `--status pending` to focus on unprocessed |
| Applying an entry with `Kora line: unset` as-is | Verify it against the 2.0 source first — it may be a 1.x entry |

---

## Best Practices

1. **Search first** — step 3 of the per-task procedure, before you write the code
2. **Add immediately** — record right after solving, don't rely on memory
3. **Be specific** — exact annotation, exact config key, exact error message, exact files
4. **Prefer the silent failures** — a mistake the compiler caught is already self-correcting; one
   that left a green build is what the journal exists for
5. **Use the status lifecycle** — `pending` → `integrated` → `archived`
6. **Export weekly** — `export --since YYYY-MM-DD --status pending`
7. **Integrate monthly** — don't let pending entries accumulate beyond 20
8. **Archive quarterly** — clean up old integrated entries

---

## See Also

- [Journal Workflow](references/journal-workflow.md) — Detailed workflow
- [Entry Template](assets/journal-entry-template.md) — Entry format template
- [kora-v2 meta-skill](../../SKILL.md) — R3 and the silent-failure list
