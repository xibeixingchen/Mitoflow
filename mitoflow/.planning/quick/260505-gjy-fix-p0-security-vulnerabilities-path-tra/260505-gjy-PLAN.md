# Quick Task 260505-gjy: Fix P0 Security Vulnerabilities

**Mode:** quick-validate
**Date:** 2026-05-05

## Task Description

Fix all P0 (critical) security vulnerabilities identified in REVIEW.md:

1. Path traversal in `download_result_file`, `download_file`, `delete_file`
2. XSS vulnerability in `ChatPanel.vue` (`v-html` with hand-rolled markdown)
3. Token secret non-persistence in `auth.py`
4. SQL injection in `sessions_sqlite.py` `search_messages`
5. Missing file upload size limit in `upload_files`

---

## must_haves

- All path checks use `Path.relative_to()` instead of string containment
- `ChatPanel.vue` sanitizes rendered HTML (DOMPurify or escape-first)
- `auth.py` reads secret from env var with startup warning
- `sessions_sqlite.py` uses parameterized `LIKE ?` queries
- `upload_files` rejects files exceeding `MAX_UPLOAD_SIZE`

---

## Tasks

### Task 1: Fix path traversal in main.py

**Files:** `deploy/web/backend/main.py`
**Action:**
- Fix `download_result_file` (line ~709): replace `str(allowed) not in str(target)` with `target.relative_to(allowed)`
- Fix `download_file` (line ~805): same pattern
- Fix `delete_file` (line ~814): same pattern
- Add helper `_safe_path(base, rel)` for consistent reuse

**Verify:**
- `curl` test with `../etc/passwd` returns 403
- Normal file download still works

**Done when:** all three endpoints reject path traversal attempts

### Task 2: Fix XSS in ChatPanel.vue

**Files:** `deploy/web/frontend/src/components/chat/ChatPanel.vue`
**Action:**
- Replace `v-html="renderMarkdown(msg.content)"` with escape-then-render approach
- Ensure `renderMarkdown` escapes HTML *before* applying markdown transforms
- Fix `escapeHtml` to run *first*, then apply `**`, `` ` ``, links, etc.

**Verify:**
- `<script>alert(1)</script>` in LLM response does not execute
- Markdown bold/code/link still renders correctly

**Done when:** XSS payload is displayed as plain text, not executed

### Task 3: Fix token secret persistence in auth.py

**Files:** `src/mitoflow/ai/auth.py`
**Action:**
- Change `_SECRET` to read from env var `MITOFLOW_SECRET`
- Add startup warning if env var is not set (log to stderr)
- Do NOT fall back to `os.urandom` — require explicit secret

**Verify:**
- Without env var, import raises ValueError or logs warning
- With env var set, token verification works across restarts

**Done when:** secret is deterministic when env var is provided

### Task 4: Fix SQL injection in sessions_sqlite.py

**Files:** `src/mitoflow/ai/sessions_sqlite.py`
**Action:**
- Fix `search_messages` (line ~228-249): change `f"%{query}%"` to parameterized `?` with tuple `(f"%{query}%",)`
- Fix `list_sessions` (line ~176-184): ORDER BY clause uses f-string with bool — safe but refactor to dict mapping for clarity

**Verify:**
- `search_messages` with `query="'; DROP TABLE messages; --"` does not execute malicious SQL
- Search results still return correct matches

**Done when:** all user input in SQL uses parameterized queries

### Task 5: Add file upload size limit in main.py

**Files:** `deploy/web/backend/main.py`
**Action:**
- Add `MAX_UPLOAD_SIZE = 500 * 1024 * 1024` (500MB)
- In `upload_files`, check `len(content) > MAX_UPLOAD_SIZE` before writing
- Return 413 Payload Too Large if exceeded

**Verify:**
- Upload small file succeeds
- Upload >500MB file returns 413

**Done when:** oversized uploads are rejected before disk write

---

## Notes

- Each task gets its own atomic commit
- No frontend dependency installation needed for Task 2 (pure escape logic)
- Task 3 may require updating test fixtures that rely on implicit secret generation
