<!-- qa-coverage
api: /papers/{paper_id}/critical-read*, /critical-read/*, /papers/{paper_id}/findings, /findings/{finding_id}/review, /findings/overview
fe: 08x_methods_critical.jsx
-->

# ROUTE 67 - Critical read (scrutiny surface: Tier-1 facts + the findings queue + Tier-2 AI candidates)

**Tier:** 2 local-stateful + egress-gated
**Goal:** Exercise the single-paper **Synthesize → Critique** tab — the deterministic Tier-1 backbone (async job,
which already includes the paper's retraction/statcheck/transparency status facts), the reviewable
**findings CANDIDATE queue** (e.g. a statcheck batch's flagged inconsistencies — absorbed here 2026-07-20 from
the retired left-pane "Review" accordion), and the opt-in, egress-gated Tier-2 AI critique candidates
(accept/reject) — and prove it stays a **signal, never a verdict**: no score, the three item kinds stay visually
and functionally distinct, no author accusation, egress honored.

## Environment

Clean seeded instance (`_TEMPLATE.md` → Environment). Run once with **egress UNSET** (the default) and once with
egress enabled + a fake/loopback provider. Register listeners before navigation.

## Standing assertions

- **Console-error budget = 0.** Any console `error` ≥ Medium; any `pageerror` ≥ High.
- **Signal, not verdict.** No composite/quality/score/grade field anywhere in the response or UI. A number
  presented as an overall paper "quality" is **Critical**.
- **Facts vs. candidates are distinct — and the three item kinds stay distinct from each other.** Tier-1 items
  render as facts (no review action — the "What the checks surfaced" list, including retraction/statcheck/
  transparency status). The **findings queue** ("Needs your review") renders **CANDIDATE** cards with **Confirmed
  / Accepted [needs reason] / Noted** (`POST /findings/{id}/review`) — never Accept/Reject. Tier-2 AI items render
  as separate **candidates** (amber) with **Accept/Reject** the user confirms. A candidate of either kind shown as
  an established finding, or the two candidate kinds' review actions bleeding into each other, is **High**.
- **#13 verbatim bar.** Every Tier-2 candidate carries a verbatim `anchor_quote` from the paper + an NLI stance +
  a visible confidence. A candidate with no grounding quote is **High** (it should have been dropped server-side).
- **No author-directed judgment (A-A veto).** No copy or candidate accuses a person ("the authors are…",
  "sloppy", "dishonest"). Any author-directed language is **Critical**.
- **Egress gate (invariant #3).** With egress unset: the Tier-2 "Suggest critiques (AI)" control is hidden (or its
  POST returns an honest 422), and **zero** requests reach a `generativelanguage`/Gemini/genai host. Tier 1 still
  works fully. Any genai-host request with egress off is **Critical**.

## Adversarial checklist

- deep-link / direct call with a non-existent paper id / job id / candidate id → 404, not a crash
- double-click the run + generate buttons; navigate away mid-job and return
- egress off → force `POST …/candidates/generate` → honest 422, no candidates created, no genai host hit
- click a findings-candidate's **Accepted…** then **save** with an empty reason → rejected (save disabled), no crash
- double-click a findings-candidate review button; rapid-click → at most one review applied, no console error
- `POST /findings/{id}/review` for a non-existent id → 404-class; an unknown `state` → 422-class
- resize to `375x812`, hard refresh — no horizontal overflow

## Steps

1. Select a paper with a processed PDF. Open **Synthesize → Critique**. Confirm the Tier-1 job runs
   (`POST /papers/{id}/critical-read` → poll `GET /critical-read/{job_id}`) and the backbone renders: method-check
   flags + any corpus-contested claims, each with its grounding (the contesting passage + page) and confidence.
2. Confirm a paper with nothing flagged shows an **honest** "nothing surfaced by these checks — not a clean bill of
   health" message, never "clean"/"good".
3. Navigate to a paper without text → the honest "process a PDF first" message, not an error.
4. **Egress OFF (default):** confirm the Tier-2 control is hidden (an explicit "enable AI in Settings" note) and no
   genai host is contacted. Directly `POST /papers/{id}/critical-read/candidates/generate` → **422** honest refusal.
5. **Egress ON (fake/loopback provider):** click **Suggest critiques (AI)** (`POST …/candidates/generate`). Confirm
   each returned candidate quotes the paper verbatim (`GET …/critical-read/candidates`), is marked a **candidate**,
   and carries a stance + confidence. An ungrounded model draft must NOT appear (dropped by the #13 bar).
6. **Accept** a candidate (`POST /critical-read/candidates/{id}/accept`) → it persists as accepted (survives reload).
   **Reject** another (`.../reject`) → it disappears and is never re-proposed on a re-generate.
7. **The findings queue.** Run a statcheck batch (METHODS → Statistics check → "Check all papers") on a paper with
   an inconsistency, or seed a `kind:"candidate"` row via `upsert_findings` directly (`_TEMPLATE.md`-style fixture).
   Reopen **Synthesize → Critique** for that paper → a **"Needs your review"** block renders below the Tier-1
   backbone with a `FindingCard` per candidate (its `show in paper · p.N` anchor opens at **region** precision — no
   fabricated exact highlight). Confirm the paper-card library badge ("N to review", `GET /findings/overview`)
   reflects the unreviewed count beforehand.
8. Click **Confirmed** (`POST /findings/{id}/review`). The card flips to reviewed ("✓ confirmed") and the library
   "N to review" badge **drops live** (no manual refresh). Reload → the review **persists**.
9. Click **Accepted…** on another candidate, type a reason, **save** → persists with the reason shown. Click
   **Noted** on a third → persists. A paper with no findings candidates shows no "Needs your review" block at all
   (silent, matching the Tier-2 candidates list's own empty convention — no empty-state clutter).
10. Adversarial: unknown paper/job/candidate/finding ids → 404; an unknown review `state` → 422; empty-reason
    Accepted is not saveable; confirm messaging, not a crash.

## Pass criteria

- Tier 1 (job + backbone), the findings queue (Confirmed/Accepted[+reason]/Noted), and Tier 2 (generate +
  accept/reject) are all complete and replayable, and visually/functionally distinct from each other.
- 0 console/page errors; 0 genai-host requests with egress off; Tier-2 gated (control hidden + 422 when off).
- The findings queue is local (no genai-host request ever, egress state irrelevant to it).
- The library "N to review" badge reflects the findings queue's unreviewed count live, drops to nothing at zero,
  and never reads as a quality/verdict signal.
- No composite score anywhere; facts vs. candidates visually distinct; every Tier-2 candidate is verbatim-grounded with a
  stance + confidence; no author-directed language.
- Accept persists; reject never returns. Mobile viewport has no horizontal overflow.

## Deposit

Write `.claude/qa-inbox/<RUN_ID>/route_67_critical_review.md` + `screenshots/` (see `_TEMPLATE.md`).
