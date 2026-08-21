# Kora Journal Entry Template

**Use this template when adding entries manually or as a reference for the `add` command.**

**Format:** Each entry is a **separate Markdown file** with YAML frontmatter.

---

## Entry File Template

```markdown
---
title: "Brief description of the fix/improvement"
date: YYYY-MM-DD
project: <project-name>
module: <module-name>
author: <username>
tags: ["http", "client", "auth", "oauth2"]  # Auto-generated or custom
---

**Tags:** Auto-generated from title/problem/solution. Override with `--tags`:
```bash
python kora-journal/scripts/kora_journal.py add "Title" \
  --context "..." --problem "..." --solution "..." --files ... \
  --tags http client auth oauth2
```

# {title}

**Date:** YYYY-MM-DD  
**Project:** <project-name>  
**Module:** <module-name>  
**Author:** <username>

---

## Context

What were you doing when you encountered this issue?
> Example: "Implementing custom authentication for HTTP server using interceptor pattern"

## Problem

What went wrong? What was unclear? What blocked you?
> Example: "Skill documentation showed Principal as controller parameter, but it caused 400 errors instead of 401"

## Solution

How did you fix it? Include code/config snippets if helpful.
> Example: "Use global @Tag(HttpServerModule) interceptor, store principal in Context, read via Principal.current() in controller. See authentication-reference.md for full pattern."

```java
// Include code snippets when helpful
@Tag(HttpServerModule.class)
@Component
public final class ApiKeyAuthInterceptor implements HttpServerInterceptor {
    // ...
}
```

## Files Affected

List the skill files that should be updated:

- `skills/kora-http-server/SKILL.md`
- `skills/kora-http-server/references/authentication-reference.md`

---

## Metadata

- **Created:** YYYY-MM-DD_HH-MM-SS
- **Status:** pending  # pending → integrated → archived
- **Integrated:** 

```

---

## Examples

### Good Entry

**File:** `2026-06-20_fixed-http-client-auth-interceptor.md`

```markdown
---
title: "Fixed HTTP client auth interceptor example"
date: 2026-06-20
project: kora-skills
module: kora-iter4
author: dsudomoin
tags: [http-client, auth, interceptor]
---

# Fixed HTTP client auth interceptor example

**Date:** 2026-06-20  
**Project:** kora-skills  
**Module:** kora-iter4  
**Author:** dsudomoin

---

## Context

Adding OAuth2 client credentials flow to HTTP client for service-to-service authentication.

## Problem

Skill example used hardcoded token, no refresh logic. Token expiration caused 401 errors without automatic refresh.

## Solution

Added TokenProvider interface with cache + refresh pattern:

```java
package com.example.auth;

import ru.tinkoff.kora.common.Component;
import ru.tinkoff.kora.http.client.common.HttpClientTokenProvider;

@Component
public class OAuth2TokenProvider implements HttpClientTokenProvider {
    private final TokenCache cache = new TokenCache(Duration.ofMinutes(5));
    
    @Override
    public String getToken() {
        return cache.getOrRefresh(this::fetchNewToken);
    }
    
    private String fetchNewToken() {
        // OAuth2 client credentials flow
    }
}
```

## Files Affected

- `skills/kora-http-client-auth/SKILL.md`
- `skills/kora-http-client-auth/references/oauth2-client-credentials-reference.md`

---

## Metadata

- **Created:** 2026-06-20_14-30-00
- **Status:** pending
- **Integrated:** 
```

### Bad Entry (Too Vague)

```markdown
---
title: "Fixed auth"
date: 2026-06-20
project: kora-skills
module: kora-iter4
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

- `skills/kora-http-client-auth/SKILL.md`
```

---

## Checklist

Before adding an entry, verify:

- [ ] **Kora-specific?** (not business logic)
- [ ] **Non-trivial?** (worth repeating)
- [ ] **Specific title?** (descriptive, not "fix")
- [ ] **Context clear?** (what were you doing)
- [ ] **Problem described?** (what went wrong)
- [ ] **Solution detailed?** (how you fixed, with code if helpful)
- [ ] **Files listed?** (which SKILL.md / references to update)
- [ ] **Author named?** (your username)

---

## When to Add Entry

| Situation | Add Entry? |
|-----------|------------|
| Fixed skill documentation error | ✅ Yes |
| Discovered Kora workaround | ✅ Yes |
| Added code example for pattern | ✅ Yes |
| Updated Kora version | ✅ Yes |
| Fixed typo in skill | ❌ No (fix directly) |
| Application bug (not Kora) | ❌ No |
| Personal preference (no functional difference) | ❌ No |

---

## Filename Convention

**Format:** `YYYY-MM-DD_slug-from-title.md`

**Examples:**
- `2026-06-20_fixed-http-client-auth-interceptor.md`
- `2026-06-19_jdbc-repository-mapper-auto-discovery.md`
- `2026-06-18_openapi-oneof-without-discriminator-workaround.md`

**Slug rules:**
- Lowercase only
- Replace spaces with hyphens
- Remove special characters
- Max 50 characters

---

## Status Values

| Status | Meaning | When to Use |
|--------|---------|-------------|
| `pending` | Not yet integrated | Default for new entries |
| `integrated` | Applied to skills | After applying changes to SKILL.md |
| `archived` | Old, ready for deletion | Quarterly cleanup |

Update status with:
```bash
python kora-journal/scripts/kora_journal.py integrate 2026-06-20_slug.md --status integrated
```
