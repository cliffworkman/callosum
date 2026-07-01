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
- POST for a paper with **no DOI** → 422; and the button path reflects "no DOI, Semantic Scholar can't find citations."
- Deep-link / GET a **nonexistent** citation-context job id → 404.
- A paper Semantic Scholar has **no citations** for → an honest "no recorded citations yet" (no crash).
- Resize to `375x812` — no horizontal overflow.

## Steps

1. Select a DOI'd paper → open METHODS → **How this paper is cited** (order 36). Confirm the intro frames it as
   "do later papers support, contrast, or mention it? A labeled signal to read, never a verdict."
2. Click **Fetch citations** (`POST /papers/citation-context/run`); poll (`GET .../run/{job_id}`) with the
   `ProgressBar`. Confirm **no genai-host request**.
3. Confirm the **breakdown as counts** (N supporting · M contrasting · K mentioning) — **not** a single score — and
   the coverage line ("classified M of N citations …").
4. Confirm each citing item shows a **stance pill** (support/contrast/mention, the `.cite-stance` colors) + a
   **confidence** + the **citing paper** (title · authors · year, a link) + the **citing sentence** (the evidence) +
   an optional "influential" marker.
5. Confirm the **credit** block (scite — Nicholson et al. 2021; Semantic Scholar as the data source) with a working
   **＋ add to library** (idempotent).
6. Adversarial: no-DOI paper → 422 / can't-fetch message; a fake job id → 404; a no-citations paper → honest empty;
   mobile viewport → no overflow.

## Pass criteria

- The run completes; the panel shows the **counts breakdown** + coverage + a list of citing sentences, each with a
  stance pill + confidence + the citing paper + credit.
- **0 console/page errors; 0 genai-host requests** (local classification; only the DOI → Semantic Scholar).
- **No composite score / rank / verdict / accusation**; every stance carries its citing sentence.
- 404 (no paper) / 422 (no DOI) / 404 (unknown job) honored; no-citations → honest empty; mobile → no overflow.

## Deposit

Write `.claude/qa-inbox/<RUN_ID>/route_53_citation_context.md` + `screenshots/` (see `_TEMPLATE.md`).
