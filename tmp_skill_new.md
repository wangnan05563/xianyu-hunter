---
name: backend-code-review
description: "Review backend code (`.py` under `api/`) for quality/security/maintainability. Use for pending-change, snippet, or file-focused review. Not for frontend (`.tsx/.ts/.js`)."
---

# Backend Code Review

## When to use this skill

Use this skill whenever the user asks to **review, analyze, or improve** backend code (e.g., `.py`) under the `api/` directory. Supports the following review modes:

- **Pending-change review**: when the user asks to review current changes (inspect staged/working-tree files slated for commit to get the changes).
- **Code snippets review**: when the user pastes code snippets (e.g., a function/class/module excerpt) into the chat and asks for a review.
- **File-focused review**: when the user points to specific files and asks for a review of those files (one file or a small, explicit set of files, e.g., `api/...`, `api/app.py`).

Do NOT use this skill when:

- The request is about frontend code or UI (e.g., `.tsx`, `.ts`, `.js`, `web/`).
- The user is not asking for a review/analysis/improvement of backend code.
- The scope is not under `api/` (unless the user explicitly asks to review backend-related changes outside `api/`).

## How to use this skill

Follow these steps when using this skill:

1. **Identify the review mode** (pending-change vs snippet vs file-focused) based on the user's input. Keep the scope tight: review only what the user provided or explicitly referenced.
2. Follow the rules defined in **Checklist** to perform the review. If no Checklist rule matches, apply **General Review Rules** as a fallback to perform the best-effort review.
3. Compose the final output strictly follow the **Required Output Format**.

Notes when using this skill:
- Always include actionable fixes or suggestions (including possible code snippets).
- Use best-effort `File:Line` references when a file path and line numbers are available; otherwise, use the most specific identifier you can.

## Checklist

| Scope pattern | Rule file |
|---|---|
| `api/models/`, `api/migrations/` | [references/db-schema-rule.md](references/db-schema-rule.md) |
| controller/service/core/libs layering, dependency direction, repository abstraction | [references/architecture-rule.md](references/architecture-rule.md) |
| SQLAlchemy session/query, transaction, raw SQL | [references/sqlalchemy-rule.md](references/sqlalchemy-rule.md) |

## General Review Rules

### 1. Security Review

Check for:
- SQL injection vulnerabilities
- Server-Side Request Forgery (SSRF)
- Command injection
- Insecure deserialization
- Hardcoded secrets/credentials
- Improper authentication/authorization
- Insecure direct object references

### 2. Performance Review

Check for:
- N+1 queries
- Missing database indexes
- Memory leaks
- Blocking operations in async code
- Missing caching opportunities

### 3. Code Quality Review

Check for:
- Code forward compatibility
- Code duplication (DRY violations)
- Functions doing too much (SRP violations)
- Deep nesting / complex conditionals
- Magic numbers/strings
- Poor naming
- Missing error handling
- Incomplete type coverage

### 4. Testing Review

Check for:
- Missing test coverage for new code
- Tests that don't test behavior
- Flaky test patterns
- Missing edge cases

## Required Output Format

When this skill invoked, the response must exactly follow one of the two templates:

### Template A (has findings)

```markdown
# Code Review Summary

## 🔴 Critical (Must Fix)

### N. <brief>
FilePath: <path> line <line>
<relevant code snippet or pointer>

#### Explanation

<detailed explanation and references of the issue>

#### Suggested Fix

1. <brief description of suggested fix>
2. <code example> (optional, omit if not applicable)

---
## 🟡 Suggestions (Should Consider)

(same structure as Critical)

## 🟢 Nits (Optional)

(same structure as Critical)

## ✅ What's Good

- <Positive feedback on good patterns>
```

Rules:
- Omit any empty section.
- For 10+ issues of a type, show first 10 with "Found 10+ critical issues/suggestions/optional nits" header.
- Don't compress the blank lines between sections; keep them as-is for readability.
- If any issue requires code changes, append a brief follow-up question to ask whether the user wants to apply the fix(es). For example: "Would you like me to apply the Suggested fix(es) to address these issues?"

### Template B (no issues)

```markdown
## Code Review Summary
✅ No issues found.
```
