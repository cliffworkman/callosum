<!-- qa-coverage
api: /papers/{paper_id}/critical-read*, /critical-read/*
fe: 08x_methods_critical.jsx
-->

# ROUTE 67 - Critical read (scrutiny surface: Tier-1 facts + Tier-2 AI candidates)

**Tier:** 2 local-stateful + egress-gated
**Goal:** Exercise the single-paper **Synthesize → Critique** tab — the deterministic Tier-1 backbone (async
job) and the opt-in, egress-gated Tier-2 AI critique candidates (accept/reject) — and prove it stays a **signal,
never a verdict**: no score, facts vs. candidates distinct, no author accusation, egress honored.

## Environment

Clean seeded instance (`_TEMPLATE.md` → Environment). Run once with **egress UNSET** (the default) and once with
egress enabled + a fake/loopback provider. Register listeners before navigation.

## Standing assertions

- **Console-error budget = 0.** Any console `error` ≥ Medium; any `pageerror` ≥ High.
- **Signal, not verdict.** No composite/quality/score/grade field anywhere in the response or UI. A number
  presented as an overall paper "quality" is **Critical**.
- **Facts vs. candidates are distinct.** Tier-1 items render as facts; Tier-2 AI items render as **candidates**
  (amber) the user confirms. A candidate shown as an established finding is **High**.
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
7. Adversarial: unknown paper/job/candidate ids → 404; confirm messaging, not a crash.

## Pass criteria

- Tier 1 (job + backbone) and Tier 2 (generate + accept/reject) are complete and replayable.
- 0 console/page errors; 0 genai-host requests with egress off; Tier-2 gated (control hidden + 422 when off).
- No composite score anywhere; facts vs. candidates visually distinct; every candidate is verbatim-grounded with a
  stance + confidence; no author-directed language.
- Accept persists; reject never returns. Mobile viewport has no horizontal overflow.

## Deposit

Write `.claude/qa-inbox/<RUN_ID>/route_67_critical_review.md` + `screenshots/` (see `_TEMPLATE.md`).
