# Increment 447 — Meta-Reference for WIP manuscripts (closes backlog #48)

## Implemented

Backlog #48's last open slice: **reference-integrity** and **citation-concentration** are now available for WIP
manuscripts under **Work → Meta-Reference**, matching what already exists for published Library papers. A third
sub-tool there, citation-context ("who cites this paper"), stays permanently out of scope for WIP — an
unpublished manuscript has no DOI, so it can't have an indexed incoming-citation graph — and is replaced with a
plain explanatory note instead of silently vanishing (the maintainer's own final decision, 2026-07-27).

Both pure detector functions — `audit_reference_list` (`methods/citation_equity.py`) and `inspect_reference`
(`methods/reference_integrity.py`) — are reused **completely unmodified**, fed different inputs:

- **Citation-concentration** (`app/backend/api/routers/wip_citation_equity.py`, new) resolves each of the
  manuscript's "cited" `wip_references`-linked Library papers via OpenAlex (`fetch_work_meta_for`, the same
  call the Library router already uses for its own focal-paper lookup), then calls `audit_reference_list` with
  an honest empty `focal_author_families` (a WIP manuscript has no stored author identity) and `field=[]`/
  `field_topic=None` (no manuscript-of-its-own OpenAlex record to draw a field comparison from). Both are paths
  the function already degrades gracefully for — no fabricated author or field proxy. Fully ephemeral, exactly
  like the Library-paper version: no dedicated table, no migration.
- **Reference-integrity** (`app/backend/api/routers/wip_reference_integrity.py` +
  `app/backend/persistence/wip_reference_integrity_repo.py`, new) builds a `ReferenceCandidate` directly from
  each "cited" `wip_references`-linked paper's own stored title/authors/year/doi — no Semantic Scholar/OpenAlex
  discovery call, since the reference list is already known locally — then runs the same `inspect_reference`.
  A read-only, purely additive cross-space lookup (`_propagation_signal_for`) checks the existing, untouched
  Library `reference_entities` table by the cited paper's normalized DOI key, so a WIP manuscript can surface
  "this reference was previously flagged elsewhere in your library" without any change to the Library-side code.

New schema: `app/backend/persistence/schema_wip_reference_integrity.py` (`wip_reference_signals`,
`wip_reference_reviews`), migration `0065_wip_reference_integrity.py`. Frontend: `WipMetaReferenceList` +
`WipRefItem` (`08j_reference_integrity.jsx`), `CitationEquitySectionWip` (`08b_methods_citation_equity.jsx`),
the `ctx.researchContext.kind === "manuscript"` branch in `37b_meta_reference.jsx`, and one line wiring
`WipMetaReferenceList` into `WipDetails`' own Checks tab (`10f_wip.jsx`).

## Key technical detail

**Why this needed two new dedicated tables instead of reusing the generic WIP provenance tables.**
`reference_instances.citing_paper_id` (Library-paper reference-integrity) is a `NOT NULL FK → papers.id` — a
`wip_manuscripts.id` cannot go there (disjoint id space; even a numeric collision would attach a manuscript's
signals to the wrong `papers` row via the join). The generic `wip_tool_runs`/`wip_findings` tables don't fit
either: `wip_tool_runs.file_id`/`snapshot_id` and `wip_findings.file_id` are all `NOT NULL`, because every prior
WIP tool (Checklists, Critique) has a real manuscript-*file* content basis. This tool's real staleness
dimension is `wip_references` cited-set membership, which has nothing to do with file text — forcing it through
those columns would make the existing "current/stale" badge logic lie in both directions for every other tool
that depends on them being file-shaped. `wip_references.id` is already the canonical, deduped
`(manuscript_id, paper_id)` identity (its own unique constraint), so unlike the Library-paper version there is
no need for a `reference_entities`/`reference_instances` dedup layer — `wip_reference_signals` attaches directly
to a `wip_references` row.

**A real, pre-existing bug found and fixed in the same pass.** `status.py`'s `JOB_NAV_DEFAULTS` for
`citation_equity_jobs` and `overlooked_jobs` both pointed at `{"pane": "methods", "section": "citation-equity"}`
— verified by grepping every `registerPaneSection` call across the frontend that **no Methods-pane section with
id `"citation-equity"` exists anywhere** (the registered set is `details`/`grim`/`statcheck`/`checklists`).
Clicking either Status entry silently landed on the Methods pane's default "Details" section, never Work →
Meta-Reference where these tools actually render — a violation of invariant #5. Fixed both to
`{"workspace": "work", "tab": "meta-reference"}` in the same pass that added the two new WIP entries to the same
dict (there was a duplicate stale `overlooked_jobs` key further down the file that would otherwise have
silently overridden the fix — removed).

**A real bug found while writing the WIP repo's report query.** The first implementation of
`manuscript_reference_report`'s underlying `_current_rows` didn't filter by `relationship_state == "cited"` —
it joined every `wip_references` row for the manuscript regardless of state, so a paper linked as
"background-reading" (never run through the detector at all) inflated `checked_count`. Fixed by scoping the
query to `relationship_state == "cited"`, caught by a test asserting the exact count.

## Housekeeping / gates

- **Security-audit stub written** (`.claude/security-audits/2026-08-04_wip-meta-reference.md`) — two new API
  endpoints reusing the existing Crossref/OpenAlex/retraction clients from new routes trips the gate.
- **Principles-alignment gate (rule #9):** reference-integrity touches commitments #2 (signal not verdict), #3
  (facts vs. candidates), #6 (silence isn't a certificate); closest worked example is **PRINCIPLES.md Example 2**
  (duplicate detection) — deterministic layered signals, flag-only, fingerprint-scoped dismissals that reopen on
  new evidence, exactly what `ensure_current_review` already does and this ports verbatim. Easiest misaligned
  path: shoehorn a manuscript into `citing_paper_id` via a fake `papers` row or a numeric-id collision — declined
  by design (separate tables, separate id space). Citation-concentration touches #2, #6, #7 (no opaque
  composite); closest worked example is **Example 3** (effect sizes) — show each signal beside a real benchmark
  or honestly mark that none exists, never fabricate one. Easiest misaligned path: infer a plausible field/topic
  from the manuscript's title to always show a comparison bar — declined; the already-supported
  `field=[]`/`field_topic=None` path is the honest one.
- **QA routes extended, not forked** — `route_68_reference_integrity.md` and
  `route_51_methods_citation_equity.md` each gained a WIP Standing Assertion and new numbered Steps, mirroring
  how `route_67_critical_review.md` folded in Critique's WIP variant.
- **Backlog #48 closed** — this was its last open slice.

## Manual verification script

1. Open a WIP manuscript. Link two Library papers as "cited" via the References tab (one retracted in the local
   Retraction Watch mirror, one clean), and one as "background-reading".
2. Open **Work → Meta-Reference**. Click **Check references** — confirm the retracted reference shows a
   **Known retraction signal** badge, the clean and background-reading ones don't appear (no active signals /
   not checked), and clicking the retracted reference's title opens the Library paper.
3. Dismiss the signal — confirm the count clears and the same receipt appears in the manuscript's own **Checks**
   tab (`WipDetails`).
4. In **Citation concentration**, click **Run audit** — confirm the field-comparison line reads "No field
   comparison available for an unpublished manuscript" and self-citation reads "not computed."
5. Confirm **How it's cited** shows the plain no-DOI explanatory note with no interactive controls.
6. From a Library paper's citation-equity/overlooked-work Status entries, confirm they now click through to
   Work → Meta-Reference (previously landed on the wrong Methods-pane section).

## Verification

- `pytest tests/test_wip_reference_integrity.py tests/test_wip_citation_equity.py tests/test_status.py
  tests/test_reference_integrity.py tests/test_citation_equity.py tests/test_wip_workflow.py
  tests/test_wip_critical_review.py tests/test_frontend_assembly.py -q` → **131 passed**.
- `alembic upgrade head` + `alembic check` on a scratch DB: clean, no drift.
- `python tools/check_line_budget.py`: **473/473 application-source files within the 600-line cap.**
- `ruff format` + `ruff check` on every touched `.py`/test file: clean.
- `python tools/build_frontend.py`: rebuilt cleanly (20,606 lines / 2,104,157 bytes).

## Rollback

Drop `wip_reference_signals`/`wip_reference_reviews` (additive migration, `0001` owns eventual metadata
teardown); remove the two new routers, the new repo file, the two new `JobStore`s and router mounts in
`app.py`, the new `status.py` entries (restoring the two stale nav entries is optional — they were a pre-
existing bug, not part of this feature), and the frontend additions. Existing Library-paper reference-integrity
and citation-equity are untouched and require no rollback.
