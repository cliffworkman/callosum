# Increment 266 — Critical-review supplement (#12): a single-paper scrutiny surface

## What shipped

A **"Critical read"** METHODS-pane section for one paper — a grounded *scrutiny surface* (signal, never a
verdict) with two epistemically-distinct tiers. Backlog #12. (Tasks T1–T4 were built earlier on the branch;
this increment finished T5–T7 and rebased the branch onto `main`.)

- **Tier 1 — deterministic, local, auto-runs** (`methods/critical_review.py`, T2/T3): composes the paper's
  already-stored method-check signals (statcheck/GRIM/LMM/transparency/retraction/open-science) + a novel
  **cross-corpus contradiction detector** — claim sentences from this paper that another paper in the corpus
  takes a confident CONTRAST stance toward (local NLI + vector store), each grounded with the contradicting
  passage (verbatim, page) + confidence. No LLM, no network.
- **Tier 2 — egress-gated, opt-in** (`integrations/gemini/critical_review.py`, T5): the LLM *proposes* concerns;
  each is admitted only through the **#13 verbatim bar** (`canonical_text_contains(anchor_quote, paper_text)`),
  annotated with a local NLI stance + confidence + a stable signature, and persisted as a **candidate** the
  human accepts/rejects (`critical_review_candidates`, T1). Ungrounded drafts are dropped (honest shortfall).
- **Router** (`routers/critical_review.py`, T4/T5): async Tier-1 job + candidate list/accept/reject +
  the egress-gated `POST …/candidates/generate`.
- **Frontend** (`08x_methods_critical.jsx`, T6): the panel — Tier-1 facts + Tier-2 candidates (amber, distinct).

## Key technical details

- **Contradiction-as-signal, never resolution.** The detector surfaces disagreement the corpus already contains
  (a CONTRAST stance ≥ threshold from another paper) and stops there — the THEORY contract ("surface
  disagreement, do not smooth it"). Every heavy dep (embed model / vector store / stance scorer / chunk
  resolver) is injected, so Tier 1 is pure + hermetically testable and imports nothing from any LLM module.
- **The #13 bar makes the LLM safe.** `verify_candidates` keeps a draft only if its quote is verbatim in the
  paper; the model can never inject a "quote" that isn't there. Untrusted model output → defensive parse ([] on
  failure). A rejected candidate's signature is never re-proposed.
- **Egress gate (invariant #3).** Tier 1: no external call. Tier 2's generate endpoint gates on
  `GeminiConfig.from_environment()` exactly like `summaries._summary_generator` — egress-off ⇒ honest 422; a
  loopback provider ⇒ zero egress; the gate fires before the generator, so a fake still refuses when egress off.
- **Signal, not verdict.** No composite/quality/score field anywhere (guard test); Tier-1 facts vs. Tier-2
  amber candidates are visually distinct; critique is of claims + methods, never the authors (A-A veto; guard
  test scans a banned-phrase list; the prompt says so explicitly).

## Branch rebase (the migration snarl, resolved)

The branch's migration `0035_critical_review_candidates` chained off `0034`, colliding with `main`'s
`0035_merge_operations` + `0036_papers_merged_into` (the reversible-merge work, inc 265). Merged `main` in and
re-chained: `→ 0037_critical_review_candidates`, `down_revision = 0036_papers_merged_into`. Single alembic head
restored; a fresh DB migrates cleanly with all three features' schema.

## Manual verification (frontend — run in a browser; no browser automation in the repo)

1. Scratch instance on a non-8888 port. Select a paper with a processed PDF + at least one method flag (or a
   corpus contradicter). Open METHODS → **Critical read**. Confirm Tier 1 auto-runs and renders the facts, each
   grounded (contradicting passage + page + confidence).
2. With **AI off** (default): confirm the Tier-2 button is hidden (an "enable AI in Settings" note) and no
   genai-host request is made. Force `POST …/candidates/generate` → honest 422.
3. With **AI on** (fake/loopback): **Suggest critiques (AI)** → each candidate quotes the paper verbatim, shows a
   stance + confidence, in amber. **Accept** persists (survives reload); **Reject** disappears + isn't re-proposed.

## Experience pass (rule #11 — the deadline citer)

The panel lives where a citer vetting a paper before citing it looks (the paper's METHODS pane), and **degrades
honestly**: AI off → Tier 1 (facts) still delivers the corpus-contested claims + method flags, with an explicit
note that AI critiques need Settings — no dead-end. The amber candidate treatment + "candidates you confirm"
copy keep a suggestion from being mistaken for a finding. **Finding (cheap, in-increment):** the "nothing
surfaced ≠ clean bill of health" copy prevents the citer over-trusting an empty result. No blocking UX gaps;
recorded here per the doc.

## Pytest

Full `pytest --ignore=tests/test_mcp_server.py` green (count confirmed by the final run below);
`tests/test_critical_review.py` = 16 (T1–T5 + the T7 Principles guard). QA API surface coverage 215/215 (route
67 added). Security audit `2026-07-08_critical-review.md` PASS.
