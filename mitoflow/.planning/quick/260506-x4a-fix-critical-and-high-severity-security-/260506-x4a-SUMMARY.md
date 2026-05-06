---
phase: quick
plan: x4a
subsystem: security
tags: [security, auth, jwt, cors, rate-limiting, deadlock-fix]
key_files_created: []
key_files_modified:
  - src/mitoflow/ai/auth.py
  - deploy/web/backend/routes/ai.py
  - deploy/web/backend/routes/files.py
  - deploy/web/backend/config.py
  - src/mitoflow/ai/providers.py
  - deploy/web/backend/routes/auth.py
  - deploy/web/backend/main.py
  - src/mitoflow/ai/rate_limiter.py
  - deploy/web/frontend/src/api/files.ts
  - deploy/web/frontend/src/stores/file.ts
key_files_deleted:
  - src/mitoflow/ai/service_deep.py
  - src/mitoflow/ai/langchain_agent.py
  - src/mitoflow/ai/langchain_bridge.py
  - src/mitoflow/ai/langchain_tools.py
decisions:
  - "File-based JWT secret fallback (0o600 permissions) when MITOFLOW_SECRET env var is not set"
  - "Reject all access to orphan sessions rather than allowing any authenticated user"
  - "Atomic claim_session return-value check to eliminate TOCTOU race condition"
  - "Generic error messages to clients with full details only in server logs"
  - "5GB upload cap instead of 100GB to limit DoS vector"
  - "Explicit api_key parameter in AnthropicAdapter replaces unsafe os.environ manipulation"
  - "Per-IP rate limiting (20 req/min, burst 5) for auth endpoints"
  - "CORS restricted to GET,POST,PATCH,DELETE,OPTIONS"
  - "Blob URL revocation in frontend preview to prevent memory leaks"
---

# Quick Task 260506-x4a: Fix Critical and High Severity Security Issues Summary

Hardened backend with persistent JWT, atomic session claims, rate-limited auth, restricted CORS, generic error responses, and cleaned dead LangChain code.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Fix critical security vulnerabilities (C1,C2,C3,H1,H3,H4,H5,M4) | d225b89 | auth.py, ai.py, files.py, config.py, providers.py, routes/auth.py |
| 2 | Fix rate limiting, CORS, blob leaks, dead code (H2,M1,M2,M3) | 26973bc | main.py, rate_limiter.py, files.ts, file.ts, service_deep.py (deleted) |

## Changes by Severity

### Critical (C1-C3)

**C1 -- Orphan session access:** Changed `_require_session_ownership()` in both `ai.py` and `files.py` from `owner is not None and owner != user["id"]` to `owner is None or owner != user["id"]`. Orphan sessions (NULL owner) are now rejected for all users.

**C2 -- JWT secret persistence:** Added file-based fallback at `_DB_DIR/.jwt_secret` with `os.chmod(0o600)`. If the env var `MITOFLOW_SECRET` is unset, the file is read or generated with `os.urandom(32).hex()`. Falls back to random (with warning) if file I/O fails.

**C3 -- Session claiming race:** Replaced TOCTOU pattern in `_ensure_session_for_chat()` with atomic `claim_session()` return-value check. The SQL `UPDATE ... WHERE user_id IS NULL` is inherently atomic; the fix ensures the Python code checks the return value.

### High (H1-H5)

**H1 -- Error info leakage:** Both `ai_chat()` and `ai_chat_stream()` now return `"Internal error. Please try again."` to clients while logging full exceptions server-side via `logging.exception()`.

**H2 -- Auth rate limiting:** Added `check_auth()` method to `RateLimiter` (20 req/min per IP, burst 5) and integrated into `rate_limit_middleware` for `/api/auth/login` and `/api/auth/register`.

**H3 -- Password policy:** Upgraded from 6-char minimum to 8+ chars requiring at least one letter and one digit via `re.search()`. Applied to both `register_user()` and `change_password()`.

**H4 -- Upload cap:** Reduced `MAX_UPLOAD_SIZE` from 100GB to 5GB.

**H5 -- AnthropicAdapter env race:** Removed `os.environ.pop/restore` pattern. The explicit `api_key` parameter to `anthropic.Anthropic()` takes priority over env vars.

### Medium (M1-M4)

**M1 -- CORS methods:** Changed `allow_methods=["*"]` to `["GET", "POST", "PATCH", "DELETE", "OPTIONS"]`.

**M2 -- Blob URL leak:** Added `_currentPreviewUrl` tracking in `files.ts` with `revokeObjectURL()` on each new preview. Updated `file.ts` store to revoke on preview change and detect blob vs text type.

**M3 -- Dead code:** Deleted `service_deep.py` (no active importers), `langchain_agent.py`, `langchain_bridge.py`, `langchain_tools.py` (only internal cross-imports, no external usage).

**M4 -- API key logging:** Removed `key_prefix={req.api_key[:6]}` from test-connection log output.

## Deviations from Plan

None -- plan executed exactly as written.

## Verification

- Backend import succeeds: `from deploy.web.backend.main import app` -- OK
- 220 existing tests pass (2 pre-existing failures unrelated to changes)
- All inline verification checks pass for both tasks
- All modified Python files pass `py_compile`

## Self-Check: PASSED

All 10 modified files exist, 4 dead code files deleted, 2 commits found, SUMMARY.md found.
