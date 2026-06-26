# Increment 130 — Findings subsystem (the FACT-vs-CANDIDATE backbone), foundation only

## Implemented

The architectural spine the METHODS "data-detective" features (statcheck, p-curve, GRIM, and the
coming retraction producer) plug into: a persistent, typed, per-paper **findings** store + a review
surface. **v1 ships the contract + UI only — no producer is wired yet** (retraction is the explicit
next increment). User-chosen scope: "foundation only."

- **Schema** (`app/backend/persistence/schema.py`): new **`paper_findings`** table — `id`,
  `paper_id` (FK → `papers` CASCADE), `source` (the producer id, e.g. `"retraction"`),
  `kind` (`fact` | `candidate`), `tier` (nullable — e.g. `primary`/`speculative`), `payload` (JSON),
  `content_key` (sha256 hex), `review_state` (nullable — `unreviewed` for candidates, NULL for facts),
  `review_reason` (Text), `reviewed_at`, `created_at`. Unique `(paper_id, source, content_key)` +
  index on `paper_id`. Migration **0016** (additive, guarded; head derived by tests, inc 99).
- **Data access** (`app/backend/persistence/findings_repo.py`, new):
  - `upsert_findings(conn, paper_id, source, findings)` — the **producer contract**: computes a
    deterministic `content_key` per finding (`sha256(source + canonical-json(payload))`), **deletes the
    superseded** (existing keys for this `(paper, source)` no longer present), and **inserts only new keys**
    — so a re-run preserves the `review_state` of unchanged candidates (idempotent) and drops stale ones.
    Candidates start `unreviewed`; facts get `review_state = NULL`.
  - `get_paper_findings(conn, paper_id)` → `{facts, candidates}` (candidates ordered primary-then-speculative,
    unreviewed-first).
  - `findings_overview(conn)` → `[{paper_id, unreviewed_count, has_facts}]` (one row per paper with ≥1
    finding) — drives the library badge with **no per-card fetch**.
  - `set_review_state(conn, finding_id, state, reason=None)` → a string status (`ok` / `not-found` /
    `not-candidate` / `bad-state` / `needs-reason`); candidates only; `accepted` requires a non-empty reason.
  - `get_finding_dict(conn, finding_id)`.
- **Endpoints** (`app/backend/api/routers/findings.py`, new; wired in `app.py`):
  - `GET /papers/{paper_id}/findings` (404 if the paper is missing).
  - `GET /findings/overview`.
  - `POST /findings/{finding_id}/review {state, reason?}` — maps the repo status → 404/422, commits, and
    returns the updated `FindingModel`.
- **Frontend** (`app/frontend/js/08_methods_findings.jsx`, new — self-registers as the METHODS "Review"
  section, `order: 40`): `FactMark` (neutral "◆ …" mark), `FindingCard` (Confirmed / Accepted[reason] /
  Noted; speculative = dashed; `show in paper` opens the page at **region** precision), `FindingsSection`
  (fetches per selected paper; honest empty states). The library card (`10_pdf_layer.jsx` `PaperCard`) shows
  a `◆ fact` mark + an `N to review` badge from the overview (`40_app.jsx` fetches `/findings/overview` into
  `findingsByPaper`, refetched via `onFindingsChanged` after a review). CSS in `styles.css` (tokens only).

## Key technical detail

**The idempotent producer contract.** A producer calls `upsert_findings(conn, paper_id, source, findings)`
with the *current complete set* for that `(paper, source)`. The repo diffs by `content_key`: keys present
in both old and new are **left untouched** (preserving a candidate's `review_state` + reason), keys only in
old are **deleted** (superseded), keys only in new are **inserted**. So re-running a producer never
resets a human's review, and a finding that the producer no longer asserts disappears. (SQLite reuses a
deleted max rowid, so the supersede test asserts the *payload changed*, not id inequality.)

**Honesty by construction.** `kind` is the FACT/CANDIDATE distinction in the schema, not a convention:
facts are non-reviewable marks (`review_state = NULL`), candidates are reviewable. The library badge counts
**unreviewed candidates** ("N to review") — the user's work state, not a quality score — and vanishes at
zero. Nothing auto-acts; nothing labels a paper or author (A-A no-accusation veto). Candidates route to a
page at **region** precision (coordinate-honesty: no fabricated exact rect). Principles gate run (audit
`2026-06-26_findings.md` §"Principle/value posture"): aligned with #2/#3/#5/#7/#8 + the no-accusation veto.

## Manual verification script

1. Copy a seeded DB; `paper_findings.create(engine, checkfirst=True)`; `upsert_findings(conn, pid, "demo",
   [{kind:fact, payload:{label:"retracted (demo)"}}, {kind:candidate, tier:primary,
   payload:{desc:"reported t(28)=2.10, p=.02 (demo)", page:4}}])`.
2. Start the app (egress unset), open `/`. The first library card shows **◆ fact** + **"1 to review"**.
3. Select that paper → METHODS → **Review**: the FactMark renders separately from the candidate card; the
   card has a **show in paper · p.4** link (opens the page at region precision).
4. Click **Confirmed** → the card flips to "✓ confirmed" and the card's **"to review"** badge drops.
5. Reload → the review persists (no badge; the candidate shows reviewed).

Automated equivalent: `.local/visual/drive_inc130_findings.py` — **PASS**, 0 console/page errors, **0 genai
hits** (fully local).

## Pytest

**478** (472 → +6 `test_findings.py`: upsert insert/idempotent-preserves-reviews/changed-payload-supersedes,
`set_review_state` rules, overview counts, the endpoint round-trip [200/404/422 + accepted-needs-reason +
count-drops]; route-surface assertions extended in `test_health.py`). `ruff` clean. QA surface 94/94 API +
496/496 FE, 0 uncovered (new `route_38_findings.md` + `04_layout.jsx` folded into `route_00`). Audit
`.claude/security-audits/2026-06-26_findings.md` **PASS**.

## Next

The first real **producer** = **retraction** (Crossref/Retraction Watch → a **FACT** with a TTL): its own
increment, trips the audit gate (new external fetch) + the Principles gate. Then statcheck/p-curve/GRIM can
optionally emit candidates into this same store, and a library-wide "needs review" facet can read the overview.
