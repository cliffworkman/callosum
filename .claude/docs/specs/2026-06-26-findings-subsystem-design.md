# Design spec — findings subsystem (FACT-vs-CANDIDATE backbone) (inc 130)

**Date:** 2026-06-26 · **Status:** approved design (brainstorming) → spec under review.
**Source:** `.claude/docs/future-tracks/opus4.8_future-tracks_theorymethods.md` (the "findings + review subsystem"
prompt, lines 86–161). The UI-shell dependency (THEORY/METHODS accordion + module registry) shipped in inc 121.

## 0. Context
The shared backbone every METHODS check will emit into — a per-paper findings store, the FACT-vs-CANDIDATE
contract, a typed review workflow, and the library "N to review" badge. **Foundation only** (user's call): no real
producers; a **seeded fake** finding exercises the UI end-to-end. The first real producer (retraction) is the next
increment and slots into this contract. **statcheck stays exactly as-is** (its inc-95/97 `open_science_signals` +
"N flagged" chip are untouched; "port statcheck into findings" is a later, separate sub-project — this increment
does not disturb it).

## 1. Core contract (document in code; references DESIGN.md §5)
A **Finding** is one of two kinds:
- **FACT** — an established truth about the paper (e.g. retracted). A persistent mark. **Not resolvable**
  (`review_state` NULL — nothing to adjudicate).
- **CANDIDATE** — a possible concern surfaced for the user to check. **Reviewable**. Carries an optional **tier**
  (`primary` = structural/high-confidence vs `speculative` = semantic/low-confidence) and optional text-location
  anchors for click-to-highlight.

Badges describe the user's **WORK STATE** ("N to review" = unreviewed-candidate count), **never paper quality**.

## 2. Backend
### 2a. Schema + migration (`schema.py` + `alembic/versions/0016_paper_findings.py`)
New table **`paper_findings`** (head 0015 → 0016; guarded-additive like 0014/0015):
- `id` PK; `paper_id` FK→papers.id `ondelete=CASCADE`; `source` String (the producing check);
  `kind` String ('fact'|'candidate'); `tier` String nullable ('primary'|'speculative'); `payload` JSON;
  `content_key` String (stable idempotency hash); `review_state` String nullable
  ('unreviewed'|'confirmed'|'accepted'|'noted'); `review_reason` Text nullable; `reviewed_at` DateTime nullable;
  `created_at` DateTime server_default now.
- `UniqueConstraint(paper_id, source, content_key)`; `Index(paper_id)`.

### 2b. `persistence/findings_repo.py` — the producer contract
- `upsert_findings(conn, paper_id, source, findings)` where `findings` is a list of
  `{kind, tier?, payload}` dicts. **Idempotent + review-state-preserving:**
  - `content_key(source, payload) = sha256(source + canonical_json(payload))` (sorted keys). Producers that must
    refresh on text/world-state change fold a version field into `payload` so the key changes.
  - For each new finding: if a row `(paper_id, source, content_key)` exists → **leave it untouched** (reviews
    survive). Else **insert** (review_state = `'unreviewed'` for candidate, `None` for fact).
  - Rows for `(paper_id, source)` whose `content_key` is **not** in the new set → **delete** (superseded; a review
    on a vanished finding is moot — chosen over a `stale` flag for v1 simplicity, same user-facing result).
- `get_paper_findings(conn, paper_id) -> {facts: [...], candidates: [...]}` (candidates ordered primary-then-
  speculative, then by review_state/created_at).
- `findings_overview(conn) -> list[{paper_id, unreviewed_count, has_facts}]` (one row per paper that has any
  finding; `unreviewed_count` = candidates with review_state='unreviewed').
- `set_review_state(conn, finding_id, state, reason)` — **candidates only** (404/422 on a fact); `state` ∈
  {confirmed, accepted, noted}; **`accepted` requires a non-empty `reason`** (else 422); sets `reviewed_at`.
- A **`FakeFindingProducer`** (or `seed_demo_findings(conn, paper_id)`) writing one FACT (e.g. payload
  `{label: "retracted (demo)"}`) + one CANDIDATE (tier `primary`, payload with a `text_anchor` page) — a
  test/dev helper, **not** wired to a shipped endpoint.

### 2c. `routers/findings.py` (+ register in `app.py` after `methods.router`)
- `GET /papers/{paper_id}/findings` → `{facts, candidates}` (404 if paper missing).
- `GET /findings/overview` → `[{paper_id, unreviewed_count, has_facts}]`.
- `POST /findings/{finding_id}/review {state, reason?}` → 200 (updated card) / 404 (missing) / 422
  (fact, bad state, or accepted-without-reason). Sync, local, no egress.

## 3. Frontend — `app/frontend/js/08_methods_findings.jsx` (new chunk)
- **`FactMark`** — a neutral persistent chip (its own class, **visually distinct** from the review badge), label
  from the fact payload.
- **`FindingCard`** — a candidate: the description (rendered from payload), the **tier** (speculative shown
  distinctly), and review controls — **Confirmed** / **Accepted** (opens a required one-line reason) / **Noted**
  (optional note); optimistic update + `POST /findings/{id}/review`, then refetch the overview. If the payload has
  a text anchor, the card's "show in paper" reuses **`ctx.onOpenPaper({id, title}, {page, precision:"region"})`**
  (the statcheck/citation path — no new highlighter).
- **Review section** — `registerPaneSection({id:"findings", label:"Review", paneId:"methods", order:40})`: for
  `ctx.selectedPaper`, fetch `GET /papers/{id}/findings`; render facts (FactMark) then candidates (FindingCard,
  primary above speculative); **honest empty state** ("No findings for this paper yet."). Re-fetch on review +
  bump a refresh so the library badge updates.
- **Library badge** — App fetches `GET /findings/overview` (on mount + a `findingsRefresh` nonce bumped after a
  review), threads a `findingsByPaper` map into `libraryProps` → `PaperCard` renders, in `paper-foot`, a neutral
  **"N to review"** badge **only when `unreviewed_count > 0`**, plus a FactMark when `has_facts`. **Zero unreviewed
  → no badge** (reads as "nothing surfaced", not "passed"). Tokens-only CSS (read DESIGN.md; FactMark and the
  review badge get distinct, non-color-only treatments per the accessibility rule).

## 4. Gates
- **Principles (#9): aligned (this defines the substrate).** FACT vs CANDIDATE; badges = work-state not quality;
  facts not resolvable; the badge counts only unreviewed candidates; anchors → inspectable; state in the table;
  honest empty/zero states (zero ≠ "passed"). Declined easy paths: a quality score/rank; a green "passed" check;
  treating a fact as reviewable. Document the contract in `findings_repo.py` + extend DESIGN.md §5.
- **Audit (#1 new endpoints / #5 / new table):** `.claude/security-audits/2026-06-26_findings.md` — input
  validation (review state allowlist, accepted-needs-reason, reason length cap), bound-param SQL, no egress, no
  external fetch, FK CASCADE, idempotency. PASS.
- **Rule #10 (QA):** `route_NN_findings.md` (assert FACT-vs-CANDIDATE rendering, the review workflow incl.
  accepted-needs-reason, the badge = work-state-not-quality + zero-shows-nothing, anchors open the page, the
  idempotent review-preserving upsert is not user-visibly resettable) + surface-map regen. Route-surface test
  (`test_health.py`) gains the 3 routes.
- **Help corpus:** a "Reviewing findings" section (what facts vs candidates are; the review states; the badge is
  work-state); move the `HELP-DOCS-SYNCED` marker.

## 5. Verification (no egress — hermetic + headed)
- pytest: `findings_repo` — upsert idempotency (re-run same → no change, reviews preserved), a changed payload →
  fresh unreviewed, superseded → deleted, facts get NULL review_state; `set_review_state` (accepted-needs-reason
  422; fact → rejected); the 3 endpoints (happy + 404 + 422); `findings_overview` shape. Route-surface updated.
- Headed Playwright: seed one FACT + one CANDIDATE on a paper → the **Review** METHODS section shows the FactMark
  + the FindingCard; **Confirmed** drops the "N to review" count; **Accepted** requires a reason; the library card
  shows "N to review" + the FactMark, and **zero unreviewed shows no badge**; reload preserves review state; 0
  console/page errors, 0 genai requests.

## 6. Out of scope
Real producers (retraction/statcheck-port/transparency/prereg — later increments); EVALUATE; porting statcheck's
existing `open_science_signals` into findings; the tags↔findings filter cross-cut. Just the contract + store + API
+ fake-seeded review UI + library badge.
