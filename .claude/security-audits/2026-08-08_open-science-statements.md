# Security Audit — Open-science statement staging (inc 462)

**Date:** 2026-08-08
**Feature:** A new "Statements" builder (Work workspace) extending CRediT's own "build in the web UI → stage →
LibreOffice pulls & inserts" pattern (inc 261) to 7 more author-asserted manuscript disclosures: data
availability, code availability, preregistration, funding, conflict of interest, ethics, and AI use.
**Triggers:** audit-gate #1 (new API endpoints `POST`/`GET /statements/pending`), #5 (net-new feature spanning
3+ files: `app/backend/api/routers/statements.py`, `app/frontend/js/38b_statements.jsx`,
`adapters/libreoffice/callosum_cite.py`).

## Scope

A new tab (Work → Statements) with 7 small builders (a labeled textarea per statement kind, plus click-to-fill
canned starting phrases — pure client-side text, no backend involvement) that POSTs to a new stateless router
backed by an in-memory dict keyed by kind. LibreOffice's own "Insert statement…" command pulls whatever is
staged and inserts the chosen one at the cursor via the existing `_choice_box` picker. **No LLM, no DB, no
egress, no formatting/inference logic at all** — unlike CRediT's own `/credit/statement`, this router does not
compute anything; it only stores and returns the exact text the caller sent.

## Threat review

| Vector | Assessment |
|---|---|
| **Data egress** | **None.** No LLM seam, no `requires_egress`, no external fetch anywhere in `statements.py`. The staged text never leaves the process. **To assert:** 0 requests to any `generativelanguage`/genai host during a run. |
| **Input validation** | `kind` is checked against a fixed allowlist (`STATEMENT_KINDS`, 7 values) — an unrecognized kind → **422** (`HTTPException`) before any storage. `text` is capped at `MAX_STATEMENT_LEN = 4000` via Pydantic `Field(max_length=…)` (rule #4), enforced at the request boundary. |
| **Output encoding** | The statement is **plain text**. In the UI React auto-escapes it (rendered in a `<textarea>` value, never `dangerouslySetInnerHTML`). In the adapter it is inserted as a literal string via `text.insertString(cursor, s, False)` — no formula/markup/field injection, the exact `insert_statement`/CRediT precedent. |
| **State / secrets** | `_pending_statements` is a single module-level dict in the (single-user, single-process) uvicorn — **transient, in-memory, no persistence, no secret.** No file-write path (rule #4 file-path safety not engaged); does not touch `~/.callosum/app-settings.json`. Clearing a kind's text (an empty POST) removes that key from the dict entirely rather than storing an empty string — keeps the LibreOffice picker's list honest (it never offers a blank/meaningless choice). |
| **Injection (SQL)** | None — the feature touches no database (rule #3 not engaged; no SQL at all, no persistence layer). |
| **SSRF** | None — no server-side fetch of a user-supplied URL. |
| **AuthZ / exposure** | Both endpoints sit behind the existing `AccessControlMiddleware` bearer gate when Remote access is on (default-off → localhost only). `/statements/*` is **not** on the cloudflared cite-endpoint allowlist (`/papers`, `/papers/export`, `/citations/render-document`, `/citations/suggest`, `/citations/styles` — confirmed by grep), so it is unreachable via the tunnel — correct, matching `/credit/*`'s own precedent exactly (a desktop authoring tool, not a mobile-read surface). On a `CALLOSUM_READ_ONLY=1` instance the mutating `POST` returns 403 (method gate). |
| **Resource exhaustion** | Bounded: one dict entry per kind (at most 7, the fixed allowlist size), each capped at 4000 chars. No recursion, no unbounded allocation, no loop over untrusted input. |
| **Supply chain** | **No new dependency** — FastAPI/Pydantic already present; the frontend is React already loaded. |

## Negative-path checks (concrete results — `pytest tests/test_statements.py`, 7 passed, 2026-08-08)

- [x] `POST /statements/pending` with an **unknown kind** (`"not_a_real_kind"`) → **422** (`test_unknown_kind_rejected`).
- [x] `POST /statements/pending` with **text > 4000 chars** → **422** via `Field(max_length=MAX_STATEMENT_LEN)` (`test_oversized_text_rejected`).
- [x] Empty (or whitespace-only) `text` **un-stages** the kind — removed from the returned dict entirely, not stored as `""` (`test_empty_text_unstages`, `test_whitespace_only_text_unstages`).
- [x] Multiple kinds **coexist independently** — staging one never clobbers another; re-staging a kind only replaces that kind's own entry (`test_multiple_kinds_coexist_independently`).
- [x] All 7 allowlisted kinds accepted; `GET /statements/pending` with nothing staged → `{}` (`test_all_seven_kinds_accepted`, `test_pending_roundtrip_single_kind`).
- [x] **Zero egress surface.** A grep of `app/backend/api/routers/statements.py` for
  `httpx|requests|urllib|google|openai|anthropic|generativelanguage|requires_egress|integrations.gemini|app.backend.llm`
  returns no matches — the router imports only `fastapi`/`pydantic`. No AST-scan test was added (unlike CRediT's
  own `test_no_inference_code_path`) because there is no formatting/inference *logic* here to statically guard
  against drifting — the entire router is a bounded dict get/set, so the negative-path tests above already
  exhaust its behavior. The QA route (`route_88_statements.md`) additionally asserts **0 genai-host requests**
  live.

## Principles posture (rule #9)

This is the **same posture as CRediT** (`.claude/security-audits/2026-07-04_credit-statement.md`): a
formatting/staging aid for content the author asserts, never a claim, signal, or verification surface. callosum
never infers or verifies funding/ethics/COI/AI-use facts about the user's own study — the canned starting
phrases in the frontend are pure client-side text a user must explicitly click and can freely edit before
sending; the backend never sees or influences which phrase (if any) was chosen. The misaligned easy path here
would have been auto-suggesting or inferring a statement (e.g., "detect whether callosum's own AI features were
used on this manuscript" for the AI-use statement) — declined: callosum has no visibility into a user's writing
process outside the app, and asserting anything about it would be exactly the kind of unverifiable claim the
principles gate exists to prevent.

## Verdict

Every negative path fails closed at the Pydantic/allowlist boundary (422); an empty statement un-stages rather
than storing meaningless text; multiple kinds are provably independent. The feature has no network code path at
all (statically confirmed by grep, matching CRediT's own zero-egress finding), so the egress invariant (#3)
holds by construction. Output is plain text (React-escaped in the UI, inserted as a literal string by the
adapter — no markup/formula/field injection). The pending store is transient, in-memory, secret-free, and
touches no file, database, or shared settings. No new dependency. No SQL, no SSRF, no file-write.

**Security Audit: PASS.**
