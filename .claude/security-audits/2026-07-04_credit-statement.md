# Security Audit — CRediT contribution-statement builder (inc 261)

**Date:** 2026-07-04
**Feature:** `CRediTer` — a deterministic, local CRediT contribution-statement generator (an authoring aid).
**Triggers:** audit-gate #1 (new API endpoints `/credit/statement`, `/credit/pending`), #5 (net-new feature
spanning 3+ files / ~300+ LOC).

## Scope

A new pane section (THEORY) with an authors × 14-NISO-role grid that POSTs to a new stateless router
(`app/backend/api/routers/credit.py`) backed by a pure formatter (`app/backend/methods/credit.py`). Output is a
plain-text contributorship statement the user copies to their manuscript, or (LibreOffice v1) stages via an
in-memory `/credit/pending` holder for the UNO cite-macro to insert at the cursor. **No LLM, no DB, no egress.**

## Threat review

| Vector | Assessment |
|---|---|
| **Data egress** | **None.** No LLM seam, no `requires_egress`, no external fetch. The only network call in the feature is the *existing* `/library/import` OA-metadata add for the two credited works (tenzing + CRediT taxonomy) — the same class already shipped in every METHODS credit block (inc 180). The statement formatter never leaves the process. **To assert:** 0 requests to any `generativelanguage`/genai host during a run. |
| **Input validation** | Role keys + degree values are checked against **allowlists** (`CREDIT_ROLES` keys, `DEGREES`); unknown enum → `ValueError` → HTTP 422. Caps: `MAX_AUTHORS = 50`, `MAX_ROLES_PER_AUTHOR = 14`, name length `≤ 200`, pending-text length `≤ 20000`. Pydantic `Field(max_length=…)` mirrors these at the request boundary (rule #4). |
| **Output encoding** | The statement is **plain text**. In the UI React auto-escapes it (rendered as a text node / textarea value, never `dangerouslySetInnerHTML`). In the macro it is inserted as a literal string via `text.insertString(cursor, s, False)` — no formula/markup/field injection (it is not a spreadsheet cell, not a CSV, not HTML). |
| **State / secrets** | The `/credit/pending` holder is a single module-level variable in the (single-user, single-process) uvicorn — **transient, in-memory, no persistence, no secret.** No file-write path (so rule #4 file-path safety is not engaged), and it does **not** touch the machine-global `~/.callosum/app-settings.json`. |
| **Injection (SQL)** | None — the feature touches no database (rule #3 not engaged; no SQL at all). |
| **SSRF** | None — no server-side fetch of a user-supplied URL. |
| **AuthZ / exposure** | Both endpoints sit behind the existing `AccessControlMiddleware` bearer gate when Remote access is on (default-off → localhost only). `/credit/*` is **not** on the cloudflared cite-endpoint allowlist, so it is unreachable via the tunnel — correct (it is a desktop authoring tool, not a mobile-read surface). On a `CALLOSUM_READ_ONLY=1` instance the mutating `POST`s return 403 (method gate) — also correct. |
| **Resource exhaustion** | Bounded by the caps above; the formatter is O(authors × roles) with both capped, no recursion, no unbounded allocation. |
| **Supply chain** | **No new dependency** — pure Python stdlib (`dataclasses`), FastAPI/Pydantic already present; frontend is React already loaded. |

## Negative-path checks (concrete results — `pytest tests/test_credit.py`, 12 passed, 2026-07-04)

- [x] `POST /credit/statement` with an **unknown role key** (`{"role":"nope"}`) → **422** (`test_statement_endpoint_rejects_bad_input`). Formatter-level `ValueError` also asserted (`test_unknown_role_and_degree_raise`).
- [x] `POST /credit/statement` with an **unknown degree** (`degree:"primary"`) → **422** (`test_statement_endpoint_rejects_bad_input`).
- [x] `POST /credit/statement` with **> 50 authors** (`MAX_AUTHORS + 1`) → **422** via Pydantic `Field(max_length=MAX_AUTHORS)` (`test_statement_endpoint_rejects_bad_input`); formatter cap also raises (`test_caps_raise`).
- [x] `POST /credit/statement` with a **name > 200 chars** → **422** via `Field(max_length=MAX_NAME_LEN)` at the request boundary; formatter cap raises `ValueError` (`test_caps_raise`).
- [x] `POST /credit/pending` with **text > 20000 chars** (`"x" * 20_001`) → **422** via `Field(max_length=MAX_PENDING_LEN)` (`test_pending_roundtrip`).
- [x] Empty `authors: []` → **200** with an **empty** statement (`by_author == []`) — not an error (`test_statement_endpoint`, `test_empty_is_empty_statement_not_error`). An author with roles but a blank name, or a mid-entry grid, is likewise a valid (partial) statement, not a 4xx.
- [x] **Zero egress surface, statically proven.** `test_no_inference_code_path` AST-scans `methods/credit.py`: no `google`/`openai`/`anthropic`/`httpx`/`transformers`/`torch`/… import, and no `infer`/`score`/`judge`/`verify`/`classify`/`aggregate`/`predict`/`extract` function is defined. A grep of both new backend files (`methods/credit.py`, `api/routers/credit.py`) for `httpx|requests|urllib|google|openai|anthropic|generativelanguage|requires_egress|integrations.gemini|app.backend.llm` returns **no matches** — the feature has no code path that can reach a network. The QA route (`route_66_credit.md`) additionally asserts **0 genai-host requests** live.

**Build-never-infer boundary** (the principle-level control, not just a security one): `NO_INFERENCE = True` is pinned by the AST scan above, so a future edit that added an inference/model/aggregation path to the formatter would fail the test — the fact/candidate line is machine-enforced.

## Verdict

All seven negative paths behave as designed: unknown enums and over-cap inputs fail closed at the Pydantic
boundary (422) with a second formatter-level guard behind it; the empty/partial grid is a valid empty statement,
not an error; and the feature has **no network code path at all** (statically proven), so the egress invariant (#3)
holds by construction rather than by configuration. Output is plain text (React-escaped in the UI, inserted as a
literal string by the macro — no markup/formula/field injection). The `/credit/pending` holder is transient,
in-memory, secret-free, and touches no file or shared settings. No new dependency. No SQL, no SSRF, no file-write.

**Security Audit: PASS.**
