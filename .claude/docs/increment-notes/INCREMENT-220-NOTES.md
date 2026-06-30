# Increment 220 — read/unread + priority markers (+ a forced repository.py split)

## Implemented

Two per-paper, **user-set** reading markers on each library card (Bella's beta ask, the other half of the inc-219
thread). The maintainer's design calls (via AskUserQuestion): read/unread = a **manual** toggle (no auto-on-open);
priority = **a few named levels** (high/normal/low). Both are hand triage labels — **never an AI score/judgment**
(the inc-207 declined-ratings logic applies: a user dimension like a color tag, not a composite).

- **`papers.read_at`** (DateTime, NULL = unread) + **`papers.priority`** (String, NULL = unset; allowlist
  high/normal/low) — columns on `papers` (workflow state, like `deleted_at`), **migration 0031** (guarded ADD
  COLUMN + guarded downgrade, the inc-24 `tags.color` pattern).
- **`repository.py`:** `PRIORITY_LEVELS` + a `_PRIORITY_RANK` CASE; a `"priority"` sort key (high→normal→low→unset,
  NULL last); `read_status` ("read"/"unread") + `priority` filters on `list_papers`. The setters live in the new
  `paper_lifecycle_repo.py` (below).
- **Endpoints** (`routers/papers.py`): `POST /papers/{id}/read {read:bool}` (404 if missing) + `POST
  /papers/{id}/priority {priority}` (422 off-allowlist, 404 if missing); `read_status`/`priority` query params on
  `GET /papers`; `read_at`/`priority` on the list-item + detail responses.
- **Frontend:** new chunk **`16b_readmark.jsx`** = `ReadPriorityControl` (a read toggle + a priority badge/popover,
  **optimistic** — local state mirrors the prop, reverts on a failed write, the persisted value shows on the next
  list fetch → no cross-pane refresh wiring, so **zero `40_app.jsx` change**). Rendered in PaperCard's foot
  (`10_pdf_layer.jsx`, 1 line, function-hoisted — the inc-208 `10b_libmenus` pattern); a **"By priority"** Sort
  option added there too. `styles.css` `.paper-read`/`.paper-priority`/`.priority-pop` — **neutral** tokens (NOT
  verified-green / flag-amber / danger-red), so priority reads as a plain user label, not a severity/score.

### The forced repository.py split (rule #1)

`repository.py` was **662 at HEAD** — a pre-existing rule-#1 violation the CLAUDE watch note ("~556") had drifted
from; my inc-220 additions took it to 698. Since a feature landed in an over-cap file, rule #1 required a split. One
extraction wasn't enough (the file was deeply over), so two cohesive clusters moved out, both **re-exported** from
`repository` (the inc-137 schema_findings / inc-67 dedup_repo pattern → zero call-site changes):

- **`paper_lifecycle_repo.py`** — the paper state/lifecycle cluster: `update_paper_metadata`, the Trash lifecycle
  (`soft_delete_paper`/`restore_paper`/`purge_paper`/`purge_all_trashed`/`_purge_paper_embeddings`), the new
  read/priority setters, and `compute_processing_tier`/`refresh_processing_tier`. (`compute_processing_tier` inlines
  its paper query instead of calling `repository.get_paper`, so there's no import cycle.)
- **`summaries_repo.py`** — the synthesis CRUD (`list_summaries`/`get_summary`/`delete_summary`), genuinely a
  separate concern from the papers store.

→ `repository.py` **565** (healthy headroom). `BEGIN IMMEDIATE`-style fixes were not needed; this is purely a
size/cohesion split.

## Key technical detail

- **Priority is NOT the declined star rating (inc 207).** The maintainer declined ratings because a unidimensional
  star is an AI-suggestible *score* that flattens a paper. A **user-set** priority (high/normal/low) is a personal
  triage label — never computed, never AI, shown neutrally (no severity colors), and orthogonal to tags/axes. So
  it's Principles-aligned (the inc-207 color-tag class), not the thing that was declined.
- **The card control is optimistic to dodge the `40_app.jsx` cap.** `40_app.jsx` is at 599/600; adding cross-pane
  refresh state for the markers would bust it. Optimistic local state in `ReadPriorityControl` (reverting on a
  failed write; reconciled on the next list fetch) keeps the whole feature out of `40_app.jsx`.
- **Re-export, not repoint.** The two extractions are re-exported with `# noqa: E402,F401`, so every existing
  `from …repository import soft_delete_paper` (≈19 files) is unchanged — verified behavior-preserving by the
  summaries/merge/health/reading-queue tests passing untouched.

## Manual verification script

Headed, **no egress**, deterministic across **5/5 runs**: `.local/visual/drive_inc220_readmark.py` (own free port +
own seeded SQLite). **Harness note:** the driver sets `CALLOSUM_LIBRARY_DIR` to an empty dir, because the frontend
auto-rescans the default-watched library folder on load (inc 98/136/160) and would otherwise scan the real `library/`
PDFs into the seeded DB (the bug that made an early run's `read_status=unread` return 50 papers — a test-harness
artifact, not a product defect; the direct-API check confirmed the filter is correct). Steps:

1. Seed 3 papers; assert the served library is the seeded 3 (a sanity guard against serving the default DB).
2. Toggle read on the first card → `GET /papers?read_status=read == [a]`; `?read_status=unread == {b,c}`.
3. Set priority "high" via the card popover → `GET /papers?priority=high == [a]`.
4. Select **"By priority"** in the Sort dropdown → `GET /papers?sort=priority` returns the high paper first.
5. 0 console (non-500) / page / genai; only a known reading-queue-class transient lock is tolerated.

The backend filter/sort is also pytest-proven directly (`test_papers.py::test_paper_read_marker` +
`test_paper_priority_marker`), and the read_status/priority filter was confirmed correct via a direct-API check.

## Pytest

`tests/test_papers.py` +2 (read marker: set/clear + read/unread filters + 404; priority marker: set/clear + filter +
422-off-allowlist + 404 + the By-priority sort). Full suite: **785 passed** (+2 vs inc 219's 783). QA surface
**161/161 API + 715/715 FE, 0 uncovered** (`route_50_reading_markers.md`).

## NEXT

- **Fast-follow (backlogged):** the library-HEADER read/priority **filter facet** (an "Unread" / "High priority"
  filter chip in the library header) — deferred because `40_app.jsx` is at the 600-line cap; it needs a `40_app.jsx`
  split first (the overdue refactor). The backend filter params + the By-priority sort already ship, so this is a
  tight fast-follow.
- **Standing rule-#1 watch:** `15_axes.jsx` is **614 (>600)** (pre-existing from inc 211/212) — a separate
  behavior-preserving split, untouched here.
- Otherwise the design-gated B-items (B2 collaboration, B3 OCR, B4 citation-context classifier, B5 mobile).
