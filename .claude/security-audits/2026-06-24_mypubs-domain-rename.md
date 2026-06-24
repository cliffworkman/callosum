# Security audit — My Publications domain rename (inc 118, SP2 T2)

**Date:** 2026-06-24
**Feature:** `POST /my-publications/domains/rename` — rename a research domain (identified by its `paper_ids` set),
marking it `custom` so a Re-decompose preserves the name by paper-overlap. Local profile-JSON write.

**Trigger:** audit gate #1 (a new API endpoint).

## Threat review

- **Input validation (boundary):** request body `RenameDomainRequest{paper_ids: list[int], label: str}` (Pydantic —
  types enforced). `label` is `.strip()`-checked (empty → 422) and **capped at 80 chars** in `rename_domain`.
  `paper_ids` is used only as a Python `set[int]` for **exact-match** against stored `research_domains[i].paper_ids`;
  no match → 422. No request value reaches SQL text or a filesystem path.
- **Output encoding:** none rendered here; the label is later shown in the UI as **plain text** (React escapes it) —
  no `dangerouslySetInnerHTML` on the domain label.
- **Injection / SQL:** the only DB write is `set_research_domains` (SQLAlchemy Core `update(...).values(...)` with a
  bound JSON value + a bound `profile.id`); no string interpolation. The label is stored as a JSON string value, not
  executed.
- **SSRF / external calls / egress:** **none** — purely a local profile-JSON edit. No network, no LLM, not the Gemini
  gate.
- **Secret handling:** none involved.
- **Resource caps:** label capped (80 chars); `paper_ids` bounded by the existing domain sets (the endpoint only
  matches, never creates). No unbounded work.
- **File-path safety:** no file paths constructed.
- **AuthZ:** single-user local app (127.0.0.1, GET-only CORS); same posture as the sibling
  `/my-publications/works/{dismiss,undismiss}` mutations. To re-review before any hosted deployment (the standing
  Security-baseline note).
- **Supply chain:** no new dependency.

## Negative-path checks (covered by `tests/test_my_publications.py::test_rename_domain_endpoint`)
- Empty/whitespace label → **422**.
- `paper_ids` matching no domain → **422** (no silent write).
- Valid rename → 204; the matched domain's `label` is updated + `custom=True` (verified via `get_profile`).
- Route-surface invariant updated (`test_api_exposes_only_read_only_get_routes` allowlists the new POST).

## Result

**Security Audit: PASS** — a local, validated, bounded profile-JSON mutation with no egress, no injection surface,
and no new dependency; consistent with the existing My-Publications mutation endpoints.
