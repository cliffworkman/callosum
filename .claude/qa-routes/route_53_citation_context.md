<!-- qa-coverage
api: /papers/citation-context*
fe: 08c_methods_citation_context.jsx
-->

# ROUTE 53 - "How this paper is cited" (citation context; the scite analogue)

**Tier:** 1 local-stateful
**Goal:** Exercise the per-paper citation-context classifier while preserving the load-bearing posture: it is a
**signal, not a verdict** — the aggregate is **counts, never a composite score**; every citing sentence is shown as
the **evidence**; the stance is classified **locally** (only the DOI leaves); and a "contrast" describes the shown
sentence's rhetorical relationship, never an accusation of an author.

## Environment

Clean seeded instance (`_TEMPLATE.md` → Environment). Inject a **fake `semantic_scholar_client`** (canned citing
sentences; no network) + a fake/injected `stance_scorer` — or assert the run makes **no genai-host request**
regardless. Register listeners before navigation.

## Standing assertions

- **Console-error budget = 0.** Any console `error` >= Medium; any `pageerror` >= High.
- **No Gemini egress (veto-level here).** The classification runs locally; the only egress is the DOI → Semantic
  Scholar (public metadata). ANY request to a `generativelanguage`/Gemini/genai host during a run is **Critical**.
- **Signal not verdict / no composite score.** The breakdown is **counts** (N supporting · M contrasting · K
  mentioning). There is **no single "score", no pass/fail, no ranking**, and the copy frames it as "a labeled signal
  to read, never a verdict." A composite "scite-score"-style number is **High**.
- **Evidence always shown.** Every classified citation shows its **real citing sentence** + a confidence; the stance
  pill is over that sentence. A stance shown without its sentence is **High**.
- **Honest coverage.** The panel states how many of the total citations it could classify (some have no citing
  sentence); an unclassifiable citation is shown as such, never guessed.
- **No accusation.** No per-author judgment; a "contrast" is about the sentence, not the author.

## Adversarial checklist

- POST `/papers/citation-context/run` for a **nonexistent** paper → 404.
- POST for a paper with **no DOI** → 422 (not reachable from the UI: the Fetch button is absent); the no-DOI state shows
  "This paper has no DOI, so Semantic Scholar can't look up its citation graph. Add one under Identifiers in the Detail
  pane to enable it." — the hint points to the fix rather than dead-ending on the limitation (inc 260).
- Deep-link / GET a **nonexistent** citation-context job id → 404.
- A paper Semantic Scholar has **no citations** for → an honest "no recorded citations yet" (no crash).
- Resize to `375x812` — no horizontal overflow.

## Steps

1. Select a DOI'd paper → open **Work → Meta-Reference** → confirm **"How it's cited"** (`direction="citations"`,
   incoming — how others cite this paper) and **"How it cites its sources"** (`direction="references"`, outgoing
   — how this paper cites its own sources) are two **separate, always-visible** stacked subsections (the 4th and
   5th of Meta-Reference's 5), each with its own intro + fetch button — no toggle switches between them anymore
   (retired 2026-07-20; each direction is now its own `CitationContextSection` instance with its own fetch state).
2. In **"How it's cited"**, click **Fetch citations** (`POST /papers/citation-context/run {direction:"citations"}`);
   in **"How it cites its sources"**, independently click **Fetch references** (`{direction:"references"}`). Poll
   (`GET .../run/{job_id}`) with the `ProgressBar` in each. Confirm running one does **not** reset or clear the
   other's results — both can show completed results **simultaneously**. Confirm **no genai-host request** from
   either.
3. In each subsection, confirm the **breakdown as counts** (N supporting · M contrasting · K mentioning) — **not**
   a single score — and the coverage line ("classified M of N citations …").
4. Confirm each citing item shows a **stance pill** (support/contrast/mention, the `.cite-stance` colors) + a
   **confidence** + the **citing paper** (title · authors · year, a link) + the **citing sentence** (the evidence) +
   an optional "influential" marker.
5. Confirm each subsection's own **credit** block (scite — Nicholson et al. 2021; Semantic Scholar as the data
   source) with a working **＋ add to library** (idempotent — shared credit state, so accepting in one subsection
   is reflected in the other's button state too).
6. Adversarial: no-DOI paper → 422 / can't-fetch message in **both** subsections independently; a fake job id →
   404; a no-citations paper → honest empty in the affected direction only; mobile viewport → no overflow.

## Pass criteria

- Both directions are independently runnable, always-visible subsections — running one never resets or hides the
  other's results.
- Each run completes; its subsection shows the **counts breakdown** + coverage + a list of citing sentences, each
  with a stance pill + confidence + the citing paper + credit.
- **0 console/page errors; 0 genai-host requests** (local classification; only the DOI → Semantic Scholar).
- **No composite score / rank / verdict / accusation**; every stance carries its citing sentence.
- 404 (no paper) / 422 (no DOI) / 404 (unknown job) honored; no-citations → honest empty; mobile → no overflow.

## Deposit

Write `.claude/qa-inbox/<RUN_ID>/route_53_citation_context.md` + `screenshots/` (see `_TEMPLATE.md`).
