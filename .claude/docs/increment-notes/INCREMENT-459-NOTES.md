# Increment 459 — Citation integrity preflight for the LibreOffice adapter (backlog #33/#34, P2 item #19)

## Implemented

The word-processor-plugins roadmap's P2 item #19 calls for a pre-submission "citation integrity preflight"
inside the LibreOffice adapter. Investigating the actual codebase (not the roadmap's abstract 13-item checklist)
found most of the value already built — `diagnose_document` already reports malformed/duplicate/orphaned
citation marks and bibliography health, and `inspect_reference`/`detect_retraction` already do multi-source
(Retraction Watch mirror + Crossref + OpenAlex) retraction detection, reused unmodified across 3+ call sites.
The one real gap: no way to force a **fresh** retraction re-check scoped to *just the papers cited in the
currently-open manuscript* — `GET /papers/{paper_id}/retraction` is read-only/cached (no network), and
`POST /methods/retraction/run` re-checks the *entire* library with no scoping. A paper could be retracted the
week after you cited it and nothing currently told you that before submission.

This increment closes that one gap, reuse-first and document-scoped (per the two decisions confirmed before
design): a new "Citation integrity preflight…" LibreOffice command that folds `diagnose_document`'s existing
mechanics into a combined report alongside a fresh, scoped retraction re-check.

### New backend endpoint: `POST /methods/retraction/check-selected`

Added to `app/backend/api/routers/methods_retraction.py` (the same file as the whole-library batch job, sharing
`app.state.retraction_checkers`). **Synchronous** — the input is bounded to "papers cited in one manuscript,"
not the whole library, and the LibreOffice adapter has no job-polling infra today (every existing adapter→backend
call is a single blocking request).

```python
class RetractionCheckSelectedRequest(BaseModel):
    paper_ids: list[int] = Field(min_length=1, max_length=MAX_CHECK_SELECTED)  # MAX_CHECK_SELECTED = 100
```

Per id, reuses the **exact same two calls** `_run_retraction_all_job`'s inner closure already makes
(`detect_retraction(...)` then `apply_retraction(...)`) via `run_write` — so a fresh check here also persists,
meaning the existing `GET /papers/{paper_id}/retraction` read (already shown in the LibreOffice "Citations in
this document" panel) benefits from this check too, for free. A missing paper id (`NoResultFound`) is collected
into `not_found` rather than failing the whole request. Ids are deduped/validated with `_unique_positive_ids`,
mirroring `reference_integrity.py::_unique_ids`.

### LibreOffice adapter: `adapters/libreoffice/callosum_cite.py`

- **`citation_integrity_preflight(doc, base) -> dict`** — calls the existing `diagnose_document(doc, base)`
  unchanged for the mechanics report, walks `doc.getReferenceMarks()` once more to collect distinct cited paper
  ids (excluding any already reported `orphaned`, since checking a paper no longer in the library is pointless),
  truncates to `MAX_INTEGRITY_PREFLIGHT_IDS` (100, mirroring the backend cap so a big manuscript gets a partial
  re-check rather than one oversize request the backend would 422 in full), and POSTs to the new endpoint.
  Returns `{**diagnose_document_result, "retraction_checked": [...], "retraction_flagged": [...],
  "retraction_check_error": str | None}`. A backend/network failure is caught and surfaced as
  `retraction_check_error` rather than losing the already-computed local mechanics report.
- **`citation_integrity_preflight_interactive(doc, base) -> None`** — the rendering wrapper, reusing a newly
  extracted `_diagnostics_issue_lines(report)` helper (factored out of `document_diagnostics_interactive`'s own
  formatting block, pure extraction, zero behavior change) for the mechanics section, plus a new "Retraction
  re-check" section listing flagged papers with status/date/notice URL and a clean-count summary.
- Registered `_ACTIONS["citationIntegrityPreflight"]` and wired one new `Addons.xcu` menu node
  ("Citation integrity preflight…", mirroring the existing "Document diagnostics…" node exactly).

## Key technical detail

**The client-side id extraction is a deliberate third small copy, not a forced refactor.** `diagnose_document`
and `list_document_citations` already each walk `getReferenceMarks()`/`scan_citations_in_order()` slightly
differently for their own purposes; rather than risk refactoring either mid-feature, `citation_integrity_preflight`
does its own short (~15-line) walk, reusing only the already-shared `_paper_id_from_item` helper. This keeps the
diff minimal and the risk near zero, at the cost of one more small, consistent-with-existing-style duplication.

**The real-UNO spike deliberately does not assert on live Crossref/OpenAlex output.** The seeded round-trip
papers carry synthetic `10.5555/callosum.*` DOIs specifically so they never collide with anything real — calling
the real endpoint against them still exercises live external network calls (Crossref/OpenAlex, since the RW
mirror is empty in the ephemeral temp DB), but what those registries *say* about a nonexistent DOI isn't
something the spike should depend on. `spike_citation_integrity_preflight` only asserts structural properties
that hold regardless of the live response: no error, exactly the two cited papers show up in `retraction_checked`,
and the persistence side-effect actually landed (`GET /papers/{id}/retraction` flips from `unchecked` to
`checked: true` afterward). The retraction *content* logic (retracted/correction/concern detection) already has
full deterministic pytest coverage via injected fake checkers in `tests/test_retraction.py` — the real-UNO spike's
job is to prove the wiring, not re-litigate `detect_retraction`'s own correctness.

## Housekeeping / gates

- **Security audit**: Addendum 3 appended to `.claude/security-audits/2026-06-26_retraction.md` — a fourth
  `detect_retraction`/`apply_retraction` call site, zero new fetch type/host/dependency/migration, bounded input,
  per-id resilience.
- **QA route**: `.claude/qa-routes/route_39_retraction.md` extended with the new endpoint in its coverage list, a
  note explaining its real exercise surface is the LibreOffice real-UNO harness (not the browser-driven route,
  which has no LibreOffice), plus a direct-API exercise step and adversarial cases within that route's own
  environment.
- `.claude/docs/INCREMENT-BACKLOG.md`: P2 item #19 marked **✅ CLOSED inc 459** within the #33/#34 entry; the
  remainder of the roadmap's #19 checklist (DOI resolution, metadata completeness, preprint-vs-VoR, etc.) noted
  as a deliberate v1 scope boundary, not built.
- `.claude/CLAUDE.md`: counter bumped to 459.

## Manual verification script

1. Install the built `.oxt` (or run `python adapters/libreoffice/run_roundtrip.py` for the automated proof —
   see Verification below) and open a real Writer document with a few Callosum citations.
2. Callosum menu → **Citation integrity preflight…**.
3. Confirm the dialog shows both a mechanics section (matching "Document diagnostics…"'s wording for any
   malformed/duplicate/orphaned marks or bibliography state) and a "Retraction re-check" section naming how many
   cited papers were checked and clean, with any flagged paper's status/date/notice URL called out individually.
4. Confirm the command never mutates the document (no Undo entry created).

## Verification

- `pytest tests/test_retraction.py tests/test_libreoffice_adapter.py -q` → **168 passed** (4 new backend endpoint
  tests + 7 new duck-typed-fake tests for `citation_integrity_preflight`/its interactive wrapper).
- `ruff format` + `ruff check`: clean on all touched files.
- `python tools/check_line_budget.py`: unaffected — `adapters/` is outside the line-budget tool's scope (only
  `app/`/`integrations/` are walked); `methods_retraction.py` (now ~310 lines) has ample headroom regardless.
- Real-UNO verification: `python adapters/libreoffice/run_roundtrip.py` — see the run's own output for the
  `spike_citation_integrity_preflight` result (real ReferenceMarks, a real HTTP round trip to the new endpoint,
  and a confirmed server-side persistence side-effect).

## Rollback

Revert `app/backend/api/routers/methods_retraction.py`, `adapters/libreoffice/callosum_cite.py`,
`adapters/libreoffice/oxt/Addons.xcu`, and `adapters/libreoffice/selftest_uno.py` to their pre-459 state. The
`_diagnostics_issue_lines` extraction is a pure refactor with no behavior change, so a partial revert (keeping
the extraction, dropping only the new command) is also safe. No schema/migration.
