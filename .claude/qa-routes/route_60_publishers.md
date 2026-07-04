<!-- qa-coverage
api: /methods/publishers*
fe: 08e_methods_publishers.jsx
-->

# ROUTE 60 - Methods: PUBLISHERS "where to submit" journal-finder (backlog #40, SP1a backend)

**Tier:** 1 local-stateful
**Goal:** Exercise the backend of the "where to submit" tool: from an abstract, match candidate journals **locally**
and return a uniform factual profile per journal, ranked by fit and optionally moved by an open-science weighting —
while preserving the veto-level lines (no composite score, no "predatory" label, every candidate appears, the
abstract never leaves the machine). SP1a shipped the backend (2 API endpoints); **SP1b (inc 246)** adds the THEORY
panel (`08e_methods_publishers.jsx`; moved METHODS -> THEORY in inc 261's authoring-cluster reorg) — the first-use
choice gate, the paper/abstract input, the profile cards, and the always-visible open-science weighting thumb.

## Environment

Clean seeded instance (`_TEMPLATE.md` -> Environment). The two external fetches (OpenAlex `/topics`+`/works`+
`/sources`; DOAJ journals) hit **public bibliographic metadata**, NOT the Gemini gate. In a seeded QA run the live
network is available; the hermetic pytest suite (`tests/test_publishers.py`) covers the deterministic contract.

## Standing assertions

- **Egress gate.** The tool fetches public OpenAlex/DOAJ metadata + embeds the abstract **locally**. ANY request to a
  `generativelanguage`/Gemini/genai host during a run is **Critical** (this is not the Gemini library-text gate).
- **The abstract never leaves the machine (veto-level).** The candidate pool is derived from a *topic* (a paper's
  `primary_topic`, or a subject keyword resolved to a topic), never from the abstract; the abstract is embedded
  locally. The abstract text appearing in ANY outbound request (topic/works/sources/DOAJ) is **Critical**.
- **No composite score (veto-level).** The response carries per-journal facts + one labeled `fit` similarity; there is
  no `openness_score` / `legitimacy_score` / any `*score*` composite. Emitting one is **Critical**.
- **No "predatory" label (veto-level).** The string "predatory" (or any per-journal quality verdict) anywhere in the
  response is **Critical**.
- **Gate the boost, not the listing.** Every candidate journal appears — including **closed** journals (with their
  OpenAlex facts) and journals clearing no legitimacy signal. An OA-only filter, or dropping a journal for lacking a
  signal, is **High**.
- **Elevate, don't denigrate.** When the weighting > 0, a journal's rise is shown via `elevated_for` (goods it
  offers: diamond/gold OA, DOAJ Seal); absence of a legitimacy signal is a neutral `legitimacy_absent` fact, never a
  flag/deficit. A deficit-framed or accusatory rationale is **High**.
- **Honest coverage (#6).** `legitimacy_absent` names the sources this version does NOT check (COPE/OASPA, PubMed/
  Scopus indexing, regional indexes, self-archiving/TOP) so silence isn't read as a clean bill.

## Adversarial checklist

- `POST /methods/publishers/run` with neither a `paper_id` nor an `abstract`+`subject` -> 422 (no crash)
- `POST` with BOTH a `paper_id` and an `abstract`/`subject` -> 422
- `POST {paper_id: <nonexistent>}` -> 404; `POST {paper_id: <a paper with no DOI>}` -> 422 (can't resolve a topic)
- `GET /methods/publishers/run/<unknown>` -> 404
- a run whose topic yields no candidate journals -> `done` with `shown: 0` (honest empty, never a crash)
- confirm a **closed** journal in the results carries `oa_color: "closed"` + its OpenAlex facts and is NOT filtered out

## Steps

1. `POST /methods/publishers/run {abstract, subject}` (or `{paper_id}` for a library paper) -> **202** + a `job_id`.
2. Poll `GET /methods/publishers/run/{job_id}` -> `pending`/`running` (+progress) -> `done` with a `report`.
3. Confirm the report: `topic_id`, `considered`, `shown`, `weighting`, and a `profiles` list where each profile has
   `fit`, `oa_color`, `is_in_doaj`, `apc_amount`/`apc_currency`, `apc_waiver`, `license`, `doaj_seal`,
   `two_year_mean_citedness`/`h_index`/`works_count`, `legitimacy_signals`, `legitimacy_absent`, `elevated_for`.
4. Confirm **no** `*score*` composite key anywhere; **no** "predatory" string; a closed journal appears.
5. Re-run with `weighting: 1.0` -> the order shifts to elevate open goods; elevated journals carry a non-empty
   `elevated_for`; a closed journal's `elevated_for` is empty. (SP1b will expose this via the visible weighting slider.)

## Frontend — the "Where to submit" panel (SP1b, `08e_methods_publishers.jsx`)

Open THEORY → **Where to submit**. Assert:
- **First-use choice gate.** On a fresh instance the panel shows a "set your preferences" step with **two** segmented
  controls (open-science weighting + result breadth) and **no option pre-selected** — no output/run controls appear
  until BOTH are set. **Save preferences** is disabled until both are chosen. Any pre-highlighted default is
  **Critical** (the veto). The weighting appearing as the *lone* forced choice is **High** (it re-singularizes it).
- **Local-only note at the point of choice** ("stored on this machine only — never transmitted"). Missing it is Medium.
- **Once set, the gate does not re-fire** — the panel shows the input (Selected paper / Paste abstract) + Find journals.
  The prefs stay editable in Settings → **Where to submit** (and via the output thumb).
- **Output legibility (non-negotiable).** After a run, the results view **always** shows the weighting's state inline
  ("Open-science weighting: <level> — N journals elevated for <goods> · adjust") with a segmented control that re-runs
  on change. Missing/absent output thumb is **High**.
- **Profile cards** show fit / OA color / cost (APC + waiver) / license / open impact (with the Matthew-bias caveat) /
  legitimacy signals / `elevated_for`; each links to its source (journal homepage, OpenAlex, DOAJ). A closed journal
  renders with its facts (not filtered). A "predatory" label or a composite/openness **score** shown per journal is
  **Critical**. Framing must be positive (goods offered), never a deficit of the others.
- **0 genai-host requests** during the flow; the abstract text is in no outbound request (SP1a's guarantee, unchanged).

## Pass criteria

- The endpoint resolves a topic, returns uniform per-journal profiles ranked by local fit, and applies the weighting
  as a re-order (no displayed composite).
- 0 genai-host requests; the abstract text is in no outbound request.
- No composite score, no "predatory" label; closed journals + no-signal journals still appear.
- Neither/both-input -> 422; nonexistent/no-DOI paper -> 404/422; unknown job -> 404; empty topic -> honest `shown:0`.

## Deposit

Write `.claude/qa-inbox/<RUN_ID>/route_60_publishers.md` + `screenshots/` (see `_TEMPLATE.md`) — capture the
first-use choice gate (nothing pre-selected), a results view with the output thumb, and a profile card.
