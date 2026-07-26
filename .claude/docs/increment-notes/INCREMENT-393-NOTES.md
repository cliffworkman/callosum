# Increment 393 — evidence-linked positive correction records

**Date:** 2026-07-26
**Status:** complete

## Outcome

The existing Crossref/Retraction Watch correction fact now has a deliberate positive-integrity surface. A work
with an explicit, openable correction record receives:

- a read-only `system:self-correction:correction` tag, shown to the user as **Correction**;
- a green **CORRECTION** badge on its Library card; and
- a **Details → Positive integrity** row naming the registry sources/date and linking the exact correction record.

The existing Library metadata batch is now labeled **Integrity ↻** and reports checked, retracted, and
evidence-linked correction counts. It still refreshes the Retraction Watch mirror and performs the same bounded
public DOI metadata lookups; there is no second fetch path, new endpoint, migration, dependency, LLM, or document
egress.

## Honesty boundary

This implements only the part the available structured metadata can support. The green projection requires an
openable `notice_url`; correction metadata without one remains a stored generic fact but does not earn the badge.
The UI states that this is descriptive metadata, never a trust score, and that no badge means only “not surfaced
by these registries.”

Replication was deliberately not inferred. Crossref's documented controlled relationship vocabulary does not
contain a replication relation, and PubMed's current controlled Publication Types do not contain “Replication
Study.” Title/abstract matching would create a candidate, not the deterministic fact promised by this feature.
That slice remains deferred until an evidence-grade structured source exists.

## Principles / values pass

- Principles 1, 3, 4, 6, 7, and 8: the producer reuses an already-persisted deterministic registry fact, links the
  exact record, keeps the tag read-only, states coverage, and adds no score.
- Closest worked example: deterministic duplicate/retraction facts, not model judgment.
- Misaligned easy path declined: infer replication/null-engagement from prose or aggregate correction/retraction
  metadata into an integrity score.
- A-A drift: this deliberately adopts the future track's constructive integrity posture while preserving the
  no-accusation boundary. The signal is about a work/record, never a person.
- Credit-the-lineage: no scholarly method is implemented; this is a projection of public registry metadata, so
  no research-method lineage manifest is applicable.

## Experience pass

Persona: a deadline citer checking one source before relying on it. The initial implementation would have left an
already-open Details pane stale after the batch and would have allowed a green badge without an openable evidence
record. The same-increment fix threads the existing findings refresh counter into Details and requires
`notice_url` before projecting the positive tag/badge. The route from badge to evidence is now one paper selection
away, and an already-selected paper refreshes in place.

## Files changed

- `app/backend/methods/retraction.py`
- `app/backend/api/routers/methods_retraction.py`
- `app/backend/api/routers/paper_models.py`
- `app/backend/api/routers/papers.py`
- `app/backend/persistence/paper_query_repo.py`
- `app/backend/persistence/tags_repo.py`
- `app/frontend/js/00_lib.jsx`
- `app/frontend/js/03_library.jsx`
- `app/frontend/js/05_panes.jsx`
- `app/frontend/js/10b_libmenus.jsx`
- `app/frontend/js/10d_papercard.jsx`
- `app/frontend/js/25_detail.jsx`
- `app/frontend/js/40_app.jsx`
- `app/backend/help/help_content.md`
- `tests/test_retraction.py`
- `tests/test_frontend_assembly.py`
- `README.md`
- `.claude/qa-routes/route_39_retraction.md`
- `.claude/security-audits/2026-07-26_self-correction-signal.md`
- `.claude/docs/INCREMENT-BACKLOG.md`
- `.claude/docs/future-tracks/README.md`
- `.claude/docs/future-tracks/opus4.8_future-tracks_equityintegritysignals.md`
- `.claude/CLAUDE.md`
- `.claude/changes.md`
- `callosum-app.html`

## Verification

- Focused backend suite: **59 passed**.
- Frontend assembly: **53 passed** after the final rebuild.
- Full parallel project suite: **1636 passed, 1 skipped**.
- Ruff format/check, 404-file line budget, and frontend build parity: pass.
- QA surface map: **318/318 API + 1398/1419 frontend**; the same 21 frontend items remain report-only.
- Security audit: **PASS**.
- Headed browser script: at 375×812 and 1440×900, select the corrected fixture paper, confirm the Library
  **CORRECTION** badge, open Details, follow the registry record's visible URL, and click the read-only
  **Correction** tag. The tag filters to one paper; the link is exact and opens safely in a new tab; there is no
  horizontal overflow and the tested run emitted zero console errors/warnings. A final two-paper fixture gave
  both papers `status=correction` but only one an openable record: `/papers` returned
  `correction_evidence_linked=true/false` respectively, and only the linked work rendered the green badge and
  Positive integrity row.
