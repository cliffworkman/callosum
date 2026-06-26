# Retraction producer — SP1 design (the first findings producer)

**Increment:** 131 (SP1 of the retraction arc; SP2 = the Retraction Watch DB bulk source).
**Goal:** Detect retractions / corrections / expressions-of-concern for library papers from **multiple
per-DOI sources** (Crossref + OpenAlex in SP1), emit them as **FACT** findings (inc-130 contract), record an
honest per-paper **check status** (silence ≠ clean), and let the user **filter the library to retracted papers**.

## Why / gates

- **Audit gate** — new external fetch (a new use of the Crossref + OpenAlex adapters). → `.claude/security-audits/2026-06-26_retraction.md`.
- **Principles gate** — a new *claim about the literature*. Aligned: the deterministic substrate is the
  **registry** (Crossref/OpenAlex), the producer only relays it; every FACT carries its **evidence** (the
  flagging `sources` + the notice link); **no accusation** (reports the record + links the notice, never judges
  authors — the A-A veto); **silence is honest** (a checked-clean paper gets a positive "none found" record; a
  paper with no DOI is "unchecked", never implied clean). Declined easy paths: an author "N retractions"
  reputation signal; treating unchecked as clean.
- Egress: **public DOI metadata lookups** — *not* the Gemini library-text gate (same posture as DOI resolve /
  OA acquisition).

## Architecture

### Two homes, complementary (mirrors statcheck's own dual nature)

1. **`paper_findings`** (inc 130) — the **FACT** (retracted papers only) → the Review-pane FactMark + the ◆-fact
   library card mark. `source="retraction"`, `kind="fact"` (so `review_state=None`, not reviewable).
2. **`open_science_signals`** (inc 97) — one **status row per checked paper** (`signal_type="retraction"`,
   `status` ∈ `retracted` | `none` | `unchecked`). This carries the **honesty record** (checked-clean vs never
   checked) and powers the **library filter** via the existing inc-97 `SIGNAL_FILTERS` mechanism — for free.

The finding is the rich reviewable surface; the signal is the per-paper status projection + the filter. A clean
paper has a `none` signal and **no** finding; an uncheckable paper (no DOI) has an `unchecked` signal and no finding.

### The checkers (pluggable, isolated, hermetically testable)

A checker is a callable `(conn, paper) -> RetractionSignal | None` (None = this source has nothing / couldn't
resolve). Each lives next to its integration; the merge/orchestration is pure and injects the checkers.

- **`integrations/crossref/adapter.py`** — extend with `lookup_retraction(conn, doi) -> RetractionSignal | None`:
  reuse `resolve_doi`'s fetch+cache, then read the **raw cached** `response_json`'s `message.update-to` /
  `message.relation` for an `update-to` of type `retraction` / `correction` / `expression_of_concern` (verify
  the exact Crossref field shape against a real cached response at build time). Yields `{status, nature, date,
  notice_doi, notice_url}`.
- **`integrations/openalex/adapter.py`** — extend with `lookup_retraction(conn, ref) -> RetractionSignal | None`:
  surface the `is_retracted` boolean from the work body (`_work_from_body` already parses the body). Thin
  (boolean → `status="retracted"`, no notice detail) — corroboration + coverage.

`RetractionSignal` (dataclass, in `methods/retraction.py`): `source`, `status` (`retracted`/`correction`/`concern`),
`nature?`, `date?`, `reason?`, `notice_doi?`, `notice_url?`.

### The orchestrator + producer (`app/backend/methods/retraction.py`, new — pure logic)

- `merge_signals(signals: list[RetractionSignal]) -> MergedRetraction | None` — union the per-source signals;
  prefer the richest detail (notice/date/reason) across sources; the merged `status` escalates
  `concern < correction < retracted` (a retraction outranks a correction); record **all** flagging `sources`.
  Returns None if no source flagged.
- `RetractionOutcome` = `{status_kind: "retracted"|"none"|"unchecked", merged?: MergedRetraction, sources_checked: list[str]}`.
  `detect_retraction(conn, paper, *, checkers) -> RetractionOutcome` — if the paper has no DOI → `unchecked`
  (don't call checkers); else run each checker (best-effort, a checker error → skip that source, never abort),
  merge → `retracted` (merged present) or `none` (all checkers ran, nothing flagged) or `unchecked` (DOI present
  but **no** checker resolved at all — honest: we couldn't actually check).
- `apply_retraction(conn, paper_id, outcome) -> None` — writes both homes:
  - the **finding**: `upsert_findings(conn, paper_id, "retraction", [fact])` when `retracted` (the FACT payload
    below); when **not** retracted, call `upsert_findings(conn, paper_id, "retraction", [])` so any prior FACT
    is **superseded** (a paper later un-flagged loses its mark).
  - the **signal**: `store_retraction_status(conn, paper_id, status=..., sources=..., checked_at=...)`.

**FACT payload** (drives `content_key` idempotency):
```
{ "status": "retracted",            # or "correction" | "concern"
  "nature": "Retraction",
  "date": "2021-03-15",             # notice date, if known
  "reason": null,                    # SP2 (RW) fills this; SP1 usually null
  "notice_doi": "10.…/retraction",  # if known
  "notice_url": "https://doi.org/…",
  "sources": ["crossref", "openalex"] }   # which sources flagged it — inspectable
```
Re-running with the same merged result → identical `content_key` → no-op (review state N/A for facts). A changed
result (new corroborating source, or a richer notice) → new key → supersedes the old FACT.

### Triggers (mirror statcheck exactly)

- **Per-paper:** `GET /papers/{id}/retraction` (sync, read-only — runs `detect_retraction` live, stores both
  homes, returns the outcome). The "refresh retraction status" button.
- **Library-wide batch:** `POST /methods/retraction/run` + `GET /methods/retraction/run/{job_id}` (async,
  `api.state.retraction_jobs = JobStore`, over `list_live_paper_ids` — the inc-97 statcheck-batch shape).
- **Summary:** `GET /methods/retraction/summary` → `{retracted: N}` (count of `status="retracted"` signals)
  for the header chip.
- **On-import auto-check:** **deferred** to a follow-up (keep import latency + coupling out of SP1; the batch
  covers the whole library, and per-paper covers new ones). Noted, not built.

`methods.py` is 296 lines; +retraction (~140) ≈ ~440 (< 600) → extend it. If it crosses ~560 during the build,
extract a `routers/retraction.py` (precedent: duplicates.py).

### The library "Retracted" filter (reuse inc-97/100, for free)

- `repository.SIGNAL_FILTERS` gains `"retraction-retracted": ("retraction", "retracted")` → `GET
  /papers?signal=retraction-retracted` narrows to retracted papers (bound IN-subquery, rule #3; one allowlist line).
- `signals_repo`: `store_retraction_status`, `count_retraction_flagged`, `get_retraction_status(paper_id)`.
- Frontend (mirror the inc-100 statcheck chip): a **"⚠ N retracted"** library-header chip → the filter view +
  a non-accusatory banner ("Papers a registry records as retracted/corrected — verify before citing.").

### Surface (frontend)

- **FactMark** (`08_methods_findings.jsx`): make it **retraction-aware** — when `finding.source === "retraction"`,
  render the status (`Retracted` / `Correction` / `Concern`) + a **notice link** (`notice_url`, opens in a new
  tab) + the flagging `sources` as a tooltip. Other facts keep the plain `◆ text` mark.
- **Review section status line:** show the per-paper retraction *status* even when there's no FACT — "Retraction:
  checked <date> · none found" or "unchecked — no DOI" (the honesty surface; fetched from
  `GET /papers/{id}/retraction`). Subtle, not a loud card mark.
- **Library:** the header chip + filter above; the ◆-fact card mark already shows for retracted papers (inc 130).

## Honesty / Principles invariants (asserted in tests + the QA route)

- Retraction = **FACT**, never a "candidate to confirm" (registry-authoritative).
- **Silence ≠ clean:** a checked-clean paper has a `none` signal (positive record); no-DOI → `unchecked`; the UI
  never presents unchecked as clean.
- **No accusation:** reports the registry record + links the notice; never an author-level or reputation signal.
- **Evidence carried:** the FACT lists its flagging `sources` + the notice link.
- Not a score/rank: the chip is a *filter* count (papers to verify), not a verdict.

## Out of scope (SP1 → later)

- The **Retraction Watch DB** bulk source (SP2 / inc 132) — the third checker (`RetractionWatchChecker`) + a
  `retraction_records` table + a download/index "refresh database" job. The merge layer already accepts it as
  another checker, so SP2 is additive.
- On-import auto-check; automatic TTL expiry (SP1 = explicit refresh, with `checked_at` recorded).
- `reason` text is usually null in SP1 (Crossref/OpenAlex rarely give it); RW fills it in SP2.

## Tests (hermetic — injected fake checkers, no network)

- `merge_signals`: crossref-only / openalex-only / both / status-escalation (correction+retraction→retracted) /
  richest-detail-wins / empty→None.
- `detect_retraction`: no DOI → unchecked (no checker calls); all-ran-none → none; one flags → retracted; a
  checker raises → skipped, others still merge; DOI present but no checker resolved → unchecked.
- `apply_retraction`: retracted → FACT in findings + `retracted` signal; none → no finding + `none` signal;
  re-run idempotent; previously-retracted now-clean → FACT superseded + signal flips to `none`.
- Crossref/OpenAlex checkers with injected fake fetchers: parse `update-to` retraction; `is_retracted` true/false.
- Endpoints: per-paper `GET /papers/{id}/retraction`, batch run, summary; `GET /papers?signal=retraction-retracted`;
  route-surface (`test_health.py`).

## Verification

- pytest green (+ ~14 `test_retraction.py`); ruff clean; build + assembly + surface-map (new `route_39`) 0-uncovered.
- Headed, **no egress**, with **injected fake checkers** (so the run is deterministic + offline): seed a paper as
  retracted → batch run → the card shows ◆ fact + the header chip shows "1 retracted" → the filter narrows to it
  → the Review pane shows the retraction FactMark with a notice link → a clean paper shows "checked · none found"
  → a no-DOI paper shows "unchecked". 0 console/page errors, **0 genai hits**.
- A real-source eyeball (one known-retracted DOI via live Crossref) is an optional manual check, noted.
