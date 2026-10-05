# Kora Journal Entry Template

**The `add` subcommand writes this file for you.** Use this template as a reference for what a good
entry contains — not as something to hand-write into `~/.kora-journal/`. A file dropped into the
store by hand has no slug, no `kora:` stamp and no tags, so `search --by-tags` and `integrate` will
not treat it as an entry.

**Format:** Each entry is a **separate Markdown file** with YAML front matter.

---

## Entry File Template

```markdown
---
title: "Brief description of the incorrect Kora usage"
date: YYYY-MM-DD
project: <project-name>
module: <module-name>
author: <username>
kora: "2.x"                                    # Kora line this entry was written against
tags: ["http-server", "di", "kora1x"]          # Auto-generated from the entry text, or --tags
---

# {title}

**Date:** YYYY-MM-DD
**Project:** <project-name>
**Module:** <module-name>
**Author:** <username>
**Kora line:** 2.x

---

## Context

What were you doing when you made the mistake?
> Example: "Adding an API-key auth interceptor to a Kora 2.0 HTTP server"

## Problem

What did you get wrong? Quote the exact annotation, config key, or error message.
> Example: "Wrote @Tag(HttpServerModule.class) on the HttpServerInterceptor. It compiled and the
> graph built, so nothing flagged it — but the interceptor was never invoked."

## Solution

How did you fix it? Name the 2.0 API, and how you proved the fix.
> Example: "HttpServerModule.publicHttpApiRouter collects @Tag(HttpServer.class)
> All<HttpServerInterceptor>. Retagged and added a test asserting 401 on a missing key."

```java
// Include code snippets when helpful
@Tag(HttpServer.class)
@Component
public final class ApiKeyAuthInterceptor implements HttpServerInterceptor {
    // ...
}
```

## Files Affected

List the skill files that should be updated:

- `skills/kora-http-server/SKILL.md`
- `skills/kora-http-server/references/interceptors-reference.md`

---

## Metadata

- **Created:** YYYY-MM-DD_HH-MM-SS
- **Status:** pending  # pending → integrated → archived
- **Integrated:**

```

**Tags** are derived from the whole entry text against a fixed Kora vocabulary
(see the table in [SKILL.md](../SKILL.md)). Override them when the text does not say enough:
```bash
python3 skills/kora-journal/scripts/kora_journal.py add "Title" \
  --context "..." --problem "..." --solution "..." --files ... \
  --tags http-server auth kora1x
```

---

## Examples

### Good Entry — a silent 2.0 failure

**File:** `2026-08-22_global-interceptor-tagged-with-httpservermodule-ne.md`

```markdown
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

Adding an API-key auth interceptor to every route of a Kora 2.0 HTTP server.

## Problem

Tagged the interceptor `@Tag(HttpServerModule.class)`, the way Kora 1.x does it. `HttpServerModule`
still exists in 2.0, so the code compiled, the annotation processors were happy and the graph built
— but nothing resolves interceptors by that tag. Every request went through unauthenticated and the
build stayed green. The only symptom was a request that should have been 401 returning 200.

## Solution

In 2.0 the router collects the tagged collection:

```java
// io.koraframework.http.server.common.HttpServerModule
default HttpServerRouter publicHttpApiRouter(All<HttpServerRequestHandler> handlers,
                                             @Tag(HttpServer.class) All<HttpServerInterceptor> interceptors,
                                             HttpServerConfig config) { ... }
```

So the tag is `io.koraframework.http.server.common.HttpServer`:

```java
package com.example.auth;

import io.koraframework.common.annotation.Component;
import io.koraframework.common.annotation.Tag;
import io.koraframework.http.server.common.HttpServer;
import io.koraframework.http.server.common.interceptor.HttpServerInterceptor;
import io.koraframework.http.server.common.request.HttpServerRequest;
import io.koraframework.http.server.common.response.HttpServerResponse;
import io.koraframework.http.server.common.response.HttpServerResponseException;

@Tag(HttpServer.class)
@Component
public final class ApiKeyAuthInterceptor implements HttpServerInterceptor {

    @Override
    public HttpServerResponse intercept(HttpServerRequest request, InterceptChain chain) throws Exception {
        if (request.headers().getFirst("x-api-key") == null) {
            throw HttpServerResponseException.of(401, "Unauthorized");
        }
        return chain.process(request);
    }
}
```

A compile check cannot catch this class of mistake — added a `@KoraAppTest` asserting 401 on a
request without the header, which fails against the old tag.

## Files Affected

- `skills/kora-http-server/SKILL.md`
- `skills/kora-http-server/references/interceptors-reference.md`

---

## Metadata

- **Created:** 2026-08-22_14-30-00
- **Status:** pending
- **Integrated:**
```

### Good Entry — a Kora 1.x API in a 2.0 project

**File:** `2026-08-21_carried-ru-tinkoff-kora-imports-into-a-2-0-service.md`

```markdown
---
title: "Carried ru.tinkoff.kora imports into a 2.0 service"
date: 2026-08-21
project: billing-service
module: billing-api
author: dsudomoin
kora: "2.x"
tags: ["di", "json", "kora1x", "migration"]
---

## Context

Porting a controller and its DTOs from a Kora 1.x service into a 2.0 module.

## Problem

Wrote `import ru.tinkoff.kora.common.annotation.Component;` and
`import ru.tinkoff.kora.json.module.JsonModule;` from memory. Neither package exists in 2.0, so the
build failed with `package ru.tinkoff.kora.common.annotation does not exist` — and after fixing the
imports the dependency was still wrong: the artifact `json-module` does not exist either.

## Solution

- `ru.tinkoff.kora.*` → `io.koraframework.*` for the whole framework
- `ru.tinkoff.kora.json.module.JsonModule` → `io.koraframework.json.common.JsonModule`
- artifact `json-module` → `json-common`; BOM `ru.tinkoff.kora:kora-parent` → `io.koraframework:kora-bom`

Verified against the framework source at tag `2.0.0.RC2`, not against the 1.x site
`kora-projects.github.io/kora-docs`.

## Files Affected

- `skills/kora-json/SKILL.md`
- `skills/kora-project-dependencies/SKILL.md`

---

## Metadata

- **Created:** 2026-08-21_11-05-00
- **Status:** pending
- **Integrated:**
```

### Bad Entry (Too Vague)

Nothing here can be folded back into a skill: no annotation, no error message, no 2.0 API.

```markdown
---
title: "Fixed auth"
date: 2026-08-22
project: billing-service
module: billing-api
author: anonymous
---

# Fixed auth

## Context

Auth stuff

## Problem

Didn't work

## Solution

Fixed it

## Files Affected

- `skills/kora-http-server-auth/SKILL.md`
```

---

## Checklist

Before adding an entry, verify:

- [ ] **Kora-specific?** (incorrect Kora usage — not business logic)
- [ ] **Non-trivial?** (worth repeating; a typo you caught immediately is not)
- [ ] **Specific title?** (names the annotation / key / API, not "fix")
- [ ] **Context clear?** (what you were building)
- [ ] **Problem described?** (exact annotation, config key, or error text)
- [ ] **Solution detailed?** (the 2.0 API that is correct, with code if helpful)
- [ ] **Silent failure flagged?** (say so explicitly when the build stayed green)
- [ ] **Verified against the 2.0 source?** (`.kora-agent/kora-source-2.0/`, not recollection)
- [ ] **Files listed?** (which SKILL.md / references to update)
- [ ] **Author named?** (your username)

---

## When to Add Entry

| Situation | Add Entry? |
|-----------|------------|
| Used a Kora 1.x API in a 2.0 project | ✅ Yes |
| Used a 1.x name that still compiles and silently does nothing | ✅ Yes — the most valuable kind |
| Invented a Kora annotation or config key | ✅ Yes |
| Misapplied a Kora pattern (DI, AOP, config, telemetry) | ✅ Yes |
| Found a skill's documentation wrong or stale | ✅ Yes |
| Discovered a Kora workaround worth repeating | ✅ Yes |
| Fixed a typo in a skill | ❌ No (fix it directly) |
| Application bug (not Kora) | ❌ No |
| Personal preference (no functional difference) | ❌ No |

---

## Filename Convention

**Format:** `YYYY-MM-DD_slug-from-title.md` — generated by `add`, not chosen by hand.

**Examples:**
- `2026-08-22_global-interceptor-tagged-with-httpservermodule-ne.md`
- `2026-08-21_carried-ru-tinkoff-kora-imports-into-a-2-0-service.md`
- `2026-08-20_openapi-client-config-path-not-lower-camel.md`

**Slug rules:**
- Lowercase only
- Non-alphanumeric runs collapse to a single hyphen
- Truncated to 50 characters
- A repeated title on the same day gets `_1`, `_2`, … rather than overwriting the earlier entry

---

## Status Values

| Status | Meaning | When to Use |
|--------|---------|-------------|
| `pending` | Not yet integrated | Default for new entries |
| `integrated` | Applied to skills | After applying changes to SKILL.md |
| `archived` | Old, ready for deletion | Quarterly cleanup |

Update status with:
```bash
python3 skills/kora-journal/scripts/kora_journal.py integrate 2026-08-22_slug.md --status integrated
```
