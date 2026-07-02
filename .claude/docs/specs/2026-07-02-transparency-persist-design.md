# Design — #44 increment 1b: persist transparency signals (findings-FACTs + per-disclosure status + review filter + chip)

**Date:** 2026-07-02 · **Increment:** 251 (planned) · **Track:** #44 (Lakens) increment 1b

## Goal

Turn the inc-250 transparency auditor's **ephemeral per-paper panel** into **persistent, library-wide signal**: a batch
run persists each paper's *detected-present* disclosures as **findings-FACTs** (evidence-carrying marks in the Review
pane + a `◆` card mark) and its per-disclosure **check status** in `open_science_signals`, powering a **review-queue
library filter** (all 7 disclosures) + a **Library-header chip**. The consumer-side statcheck/retraction persistence
pattern (inc 97/131/133), applied to transparency.

## The load-bearing constraint (A-A no-accusation veto)

- Persist only **detected-present** disclosures as **FACTs** — evidence-carrying *positive* facts ("this paper
  discloses data availability at OSF, p.12"). **NEVER persist an absence as a fact** (silence≠certificate; the
  inc-250-declined "NO open data" fact).
- The per-disclosure `open_science_signals` **status** IS persisted for all 7 (detected / not-detected /
  not-applicable) — but a `not-detected` *status row* is not a claim about the paper; it's a **check result** ("the
  auditor ran and didn't find it in the text") that scopes an honest review queue.
- The library filter is a **review queue**, never a verdict: *"data-availability disclosure not detected — review
  these,"* scoped to **checked** papers. Never "papers with no open data / that hide their data." The **chip** counts
  a review queue, framed *"N · open data not detected → review,"* never "N papers hide data."
- **No composite transparency score, no rank** (same posture as inc 250, now persistent).

## Architecture (mirrors retraction inc 131 + statcheck inc 97 — no new pattern, no migration)

Both `paper_findings` (inc 130) and `open_science_signals` (inc 97, unique `(paper, signal_type, source)`) already
exist → **no migration**. No egress / LLM / dependency.

1. **Producer** `app/backend/methods/transparency_findings.py` (NEW pure-ish; takes a `conn` + a paper's chunks):
   `persist_transparency(conn, paper_id, chunks)` runs `detect_transparency(chunks)` (inc 250) and:
   - **Per-disclosure status** → `signals_repo.store_transparency_status(conn, paper_id, report)`: one
     `open_science_signals` row **per disclosure** (`signal_type="transparency"`, `source=<disclosure_key>`,
     `status` = present→`"detected"` / not-found→`"not-detected"` / not-applicable→`"not-applicable"`,
     `evidence_snippet` = the matched sentence for present rows), OR-REPLACE idempotent on the unique constraint.
   - **FACTs for present disclosures only** → `upsert_findings(conn, paper_id, "transparency", facts)` (inc 130): one
     `{kind:"fact", payload:{key,label,evidence,page,basis}}` per **present** disclosure (idempotent by content_key;
     a re-run that no longer detects a disclosure supersedes its stale FACT). **No FACT for not-found / n-a.**
2. **Batch** `routers/transparency.py` gains `POST /methods/transparency/run` + `GET /methods/transparency/run/{job_id}`
   (async JobStore + `mark_progress`, over `list_live_paper_ids` — the statcheck inc-97 shape) + `GET
   /methods/transparency/summary` → `{data_not_detected: N}` (the chip count). The inc-250 per-paper GET stays
   read-only (unchanged).
3. **Filter** — generalize `repository.SIGNAL_FILTERS` values from `(signal_type, status)` → `(signal_type,
   source|None, status)` (back-compat: existing statcheck/retraction entries pass `source=None`; the query adds a
   `source == :bound` clause only when non-None — rule #3, bound param). Add **7** entries + scope each honestly:
   - `transparency-data-not-detected` / `-code-` / `-coi-` / `-funding-` / `-preregistration-` →
     `("transparency", "<key>", "not-detected")` (a `not-detected` status only — a `not-applicable` row is never in a
     "not detected" queue).
   - `transparency-registration-not-detected` → `("transparency", "registration", "not-detected")` — **precondition-
     scoped for free**: a non-trial paper stores `registration="not-applicable"`, so it's excluded; only a
     trial/review where registration wasn't detected matches.
   - `transparency-upon-request` → `("transparency", "upon_request", "detected")` — the **PRESENT** case (upon_request
     has no "not detected" meaning; its presence is the weak-openness signal — "data/code offered only upon request,"
     a review queue, not an accusation).
4. **Frontend:** (a) a **"Check all papers"** batch trigger + progress in the transparency METHODS panel (`08h`, the
   statcheck-library pattern); (b) a **Library-header chip** "N · open data not detected → review" →
   `?signal=transparency-data-not-detected` (the statcheck inc-100 chip pattern) + a non-accusatory banner; (c) a
   **filter facet** (a small dropdown in the library header, shown when a transparency batch has run) offering all 7
   review queues by disclosure. The present-FACTs render as **FactMarks in the existing Review pane** (inc 130) + the
   `◆` card mark — for free — surfacing a paper's disclosures without opening the panel (partially addresses the
   inc-250 experience-pass F1 "buried panel" finding).

## Scope

- **In:** the producer + batch + summary + per-disclosure status + present-FACTs + the generalized filter (7 review
  queues) + the header chip + the panel batch trigger + the filter facet. No migration.
- **Deferred:** the `#19 system:transparency:*` **tags** (the tag-provenance model is an open design problem — FACTs +
  filter deliver the value without it); on-import auto-check (a later lifecycle slice, like retraction inc 134); a
  per-disclosure count breakdown / dashboard.

## Honesty acceptance criteria (test-pinned)

- No FACT is ever written for a `not-found` / `not-applicable` disclosure (only `present`).
- The filter labels + chip + banner never say "hides"/"no open data"/"missing"/"concealed"; they say "not detected —
  review" (silence≠certificate) and scope to checked papers.
- No `score`/`grade`/rank anywhere in the batch response or the summary.
- Registration filter excludes `not-applicable` (non-trial) papers; upon_request filter is the *present* case.
- Re-running the batch is idempotent (same content_keys → no churn; a now-absent disclosure supersedes its FACT and
  flips its status row to `not-detected`).

## Gates

Audit (a new batch endpoint + the persistence producer — light, local/no-egress; the A-A framing is the load-bearing
review). Principles + A-A gate — aligned (the statcheck-persist / retraction-FACT class; the declined path is a
"transparency score / no-open-data verdict / persist-an-absence-as-a-fact"). QA route_63 extended (the batch + filter +
chip + no-accusation assertions). Experience pass (open-science-vetter — this directly addresses the inc-250 F1/F4
findings: library-wide surfacing + a review queue). No new dependency, no migration.
