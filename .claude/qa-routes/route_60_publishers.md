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
**Inc 448** wires in two more legitimacy sources (backlog #40, still-open item): **SciELO** (a live per-ISSN regional-
index lookup, same request shape as the existing DOAJ call) and **TOP Factor** (a locally-mirrored per-journal
transparency rubric — the database-refresh flow itself is route 85; this route only covers how its per-journal facts
render in a run's results). **Inc 451** wires in a fourth source, **AJOL** (African Journals Online) — a
locally-mirrored, third-party CC-BY-4.0 snapshot (route 86 covers the database-download flow; this route covers how
its per-journal `ajol_status` fact — including AJOL's own official, positive-to-cautionary `jpps_status` rating —
renders in a run's results). **Inc 452** wires in a fifth source, **NLM/MEDLINE indexing** — a live per-ISSN
lookup against NCBI's free E-utilities `esearch` endpoint (same live-lookup shape as SciELO, no Settings
UI/mirror of its own, so it stays covered entirely by this route, no new route file). The query checks MEDLINE
specifically, not PubMed broadly (a real distinction — a journal can be PubMed-"Currently-indexed" with no
MEDLINE entry at all, confirmed live for *World Psychiatry*) — the field/chip name says exactly that. **Inc 453**
adds **thumb auditability** — the design doc's own "far reach" item, now built (its sibling item, user
exclusion/filtering, stays explicitly deferred on ethical-valence grounds — see the doc): each profile gains
`fit_rank`/`weighted_rank` (1-based positions among the full considered pool, sorted by fit alone vs. the actual
blended order), surfaced per-card as a neutral "how much did the weighting move this journal" caveat.

## Environment

Clean seeded instance (`_TEMPLATE.md` -> Environment). The four external fetches (OpenAlex `/topics`+`/works`+
`/sources`; DOAJ journals; SciELO ArticleMeta journal lookup; NLM Catalog `esearch`) hit **public bibliographic
metadata**, NOT the Gemini gate. TOP Factor and AJOL are both local-only reads (`lookup_top_factor_record`/
`lookup_ajol_record`) — never a live fetch during a run; their mirrors are populated via route 85's / route 86's
Settings download. In a seeded QA run the live network is available; the hermetic pytest suite
(`tests/test_publishers.py`) covers the deterministic contract, including a real live-429 reproduction that
justified NLM's client-side pacing guard (no API key, no Settings surface — see the security audit SP4 addendum).

## Standing assertions

- **Egress gate.** The tool fetches public OpenAlex/DOAJ metadata + embeds the abstract **locally**. ANY request to a
  `generativelanguage`/Gemini/genai host during a run is **Critical** (this is not the Gemini library-text gate).
- **The abstract never leaves the machine (veto-level).** The candidate pool is derived from a *topic* (a paper's
  `primary_topic`, or a subject keyword resolved to a topic), never from the abstract; the abstract is embedded
  locally. The abstract text appearing in ANY outbound request (topic/works/sources/DOAJ) is **Critical**.
- **No composite score (veto-level).** The response carries per-journal facts + one labeled `fit` similarity; there is
  no `openness_score` / `legitimacy_score` / any `*score*` composite. Emitting one is **Critical**.
- **Thumb auditability is an ordinal position, never a score (inc 453, tied to the veto above).**
  `fit_rank`/`weighted_rank` are transparent 1-based ranks derived from the already-shown `fit` and the existing
  blended order — computed over the **full considered pool** (`considered`), not just the returned `shown` slice,
  so a journal only shown because the weighting elevated it still exposes its true (possibly much worse)
  fit-only rank. Rendering either as a percentage, a normalized 0-1 value, or any `*score*`-suffixed key is
  **Critical** (it would read as the vetoed composite). The per-card caveat line must render **only** when
  weighting is on AND `fit_rank !== weighted_rank` — showing it unconditionally (noise on every card) is Medium.
- **No "predatory" label (veto-level).** The string "predatory" (or any per-journal quality verdict) anywhere in the
  response is **Critical**.
- **Gate the boost, not the listing.** Every candidate journal appears — including **closed** journals (with their
  OpenAlex facts) and journals clearing no legitimacy signal. An OA-only filter, or dropping a journal for lacking a
  signal, is **High**.
- **Elevate, don't denigrate.** When the weighting > 0, a journal's rise is shown via `elevated_for` (goods it
  offers: diamond/gold OA, DOAJ Seal); absence of a legitimacy signal is a neutral `legitimacy_absent` fact, never a
  flag/deficit. A deficit-framed or accusatory rationale is **High**.
- **Honest coverage (#6).** `legitimacy_absent` names the sources this version does NOT check (COPE/OASPA,
  regional indexes (Redalyc, Latindex), self-archiving policy) so silence isn't read as a clean bill. SciELO, TOP
  Factor, AJOL, and MEDLINE indexing must NOT still appear in `legitimacy_absent` after inc 452 — they've moved
  from deferred to wired. "Scopus" must never appear anywhere in the response at all (never named, not flagged).
- **The abstract never leaves the machine extends to SciELO and NLM (veto-level).** The SciELO ArticleMeta call is
  ISSN-only (`?issn={issn}`, no abstract/title/free-text params); the NLM `esearch` call's `term` param is
  ISSN-only too. The abstract text appearing in the SciELO or NLM request is **Critical**, identical in severity
  to the existing OpenAlex/DOAJ assertion above.
- **MEDLINE indexing never elevates (veto-level).** `elevated_for` containing any "MEDLINE" string, at any
  weighting, is **Critical** — it's a `legitimacy_signals` coverage fact only, matching SciELO's identical
  precedent (an indexing/discoverability fact, not an open-science good).
- **The signal must never overclaim "PubMed."** Neither the field name nor the chip text may say "PubMed" —
  the query checks MEDLINE specifically (confirmed live: a journal can be PubMed-indexed with no MEDLINE entry
  at all, e.g. World Psychiatry). "PubMed" appearing anywhere in the response or the rendered chip is **High**
  (a real overclaim caught and fixed before this increment shipped — a regression, not a style nit).
- **TOP Factor's `Total` is never a bare/floating number (Principles #7, no opaque composite score — veto-level).**
  A `top_factor.total` value rendered on a profile card WITHOUT its adjacent category sub-scores + justifications
  (i.e. outside the "show the basis" `<details>`) is **Critical** — it would read as an opaque per-journal score.
- **TOP Factor's never-downloaded state is a report-level fact, not silence.** When the local TOP Factor mirror has
  never been refreshed (route 85), the report names this explicitly (distinct from "checked, no signal") rather than
  every card silently omitting TOP Factor with no explanation. Silent omission with no report-level note is Medium.
- **AJOL's `jpps_status` renders plainly, including cautionary values (veto-level, Principles #6).** A journal whose
  AJOL rating is `Ceased` or `Inactive Title` must render exactly as reported on its profile card — no filtering,
  softening, or omission. Hiding a cautionary `jpps_status` is **Critical**.
- **AJOL elevation is gated to star tiers only.** `elevated_for` may contain an AJOL string ONLY for `1/2/3 Stars`
  (`"AJOL <N> Star(s) rating"`) or a confirmed `is_diamond` (`"AJOL-confirmed diamond OA"`) — `Inactive Title`/
  `Ceased`/`Pending`/`NA`/`No Stars` must NEVER appear in `elevated_for`, even at full weighting. Any of those five
  values in `elevated_for` is **Critical**.
- **AJOL's never-downloaded state is a report-level fact, not silence** — same contract as TOP Factor above,
  disambiguated via `ajol_coverage`. Silent per-card omission with no report-level note is Medium.

## Adversarial checklist

- `POST /methods/publishers/run` with neither a `paper_id` nor an `abstract`+`subject` -> 422 (no crash)
- `POST` with BOTH a `paper_id` and an `abstract`/`subject` -> 422
- `POST {paper_id: <nonexistent>}` -> 404; `POST {paper_id: <a paper with no DOI>}` -> 422 (can't resolve a topic)
- `GET /methods/publishers/run/<unknown>` -> 404
- a run whose topic yields no candidate journals -> `done` with `shown: 0` (honest empty, never a crash)
- confirm a **closed** journal in the results carries `oa_color: "closed"` + its OpenAlex facts and is NOT filtered out
- a journal not indexed in SciELO (the common case for most candidates) -> `scielo_collections: []`, no fabricated
  "Indexed in SciELO" signal, journal still appears unchanged
- with the TOP Factor mirror never downloaded -> every profile's `top_factor: null`, but `top_factor_coverage`
  reports `{"count": 0, "retrieved_at": null}` (not silently absent from the report shape)
- a journal not indexed in AJOL (the common case) -> `ajol_status: null`, no fabricated "Indexed in AJOL" signal,
  journal still appears unchanged
- an AJOL-matched journal with `jpps_status: "Ceased"` -> renders plainly on its card; NOT present in `elevated_for`
  even at `weighting: 1.0`
- with the AJOL mirror never downloaded -> every profile's `ajol_status: null`, but `ajol_coverage` reports
  `{"count": 0, "retrieved_at": null}` (not silently absent from the report shape)
- a journal not MEDLINE-indexed (the common case for most candidates) -> `indexed_in_medline: false`, no
  fabricated "Indexed in MEDLINE" signal, journal still appears unchanged
- a MEDLINE-indexed journal at `weighting: 1.0` -> its `elevated_for` never contains a "MEDLINE" string
- at `weighting: 0` -> every profile's `fit_rank == weighted_rank` (the blended order IS the fit order)
- a journal only shown because the weighting elevated it (its `weighted_rank` inside `top_k` but `fit_rank` well
  beyond it) -> `fit_rank` reflects its TRUE position among `considered`, never capped/re-based to the shown set

## Steps

1. `POST /methods/publishers/run {abstract, subject}` (or `{paper_id}` for a library paper) -> **202** + a `job_id`.
2. Poll `GET /methods/publishers/run/{job_id}` -> `pending`/`running` (+progress) -> `done` with a `report`.
3. Confirm the report: `topic_id`, `considered`, `shown`, `weighting`, `top_factor_coverage`, `ajol_coverage`, and a
   `profiles` list where each profile has `fit`, `oa_color`, `is_in_doaj`, `apc_amount`/`apc_currency`, `apc_waiver`,
   `license`, `doaj_seal`, `two_year_mean_citedness`/`h_index`/`works_count`, `scielo_collections`, `top_factor`,
   `ajol_status`, `indexed_in_medline`, `fit_rank`, `weighted_rank`, `legitimacy_signals`, `legitimacy_absent`,
   `elevated_for`.
4. Confirm **no** `*score*` composite key anywhere; **no** "predatory" string; a closed journal appears.
5. Re-run with `weighting: 1.0` -> the order shifts to elevate open goods; elevated journals carry a non-empty
   `elevated_for`; a closed journal's `elevated_for` is empty. (SP1b will expose this via the visible weighting slider.)
6. Run a topic likely to surface a SciELO-indexed and/or TOP-Factor-rated journal (e.g. a Latin-American public
   health or social-science abstract; TOP Factor coverage requires route 85's mirror to have been refreshed first).
   Confirm a hit's `scielo_collections` is a non-empty list and/or `top_factor` carries `{total, categories: [...]}`
   with each category's `name`/`score`/`max`/`justification`.
7. Run a topic likely to surface an AJOL-indexed journal (a Nigeria/South-Africa/Ethiopia-affiliated abstract works
   well; AJOL coverage requires route 86's mirror to have been downloaded first). Confirm a hit's `ajol_status`
   carries `{country, jpps_status, is_diamond, source_url}`; confirm a `1/2/3 Stars` hit's `elevated_for` contains
   `"AJOL <N> Star(s) rating"`; confirm a `Ceased`/`Inactive Title` hit (if seeded) renders its status plainly and
   is absent from `elevated_for`.
8. Run a topic likely to surface a well-known MEDLINE-indexed journal (e.g. a mainstream biomedical/psychiatric
   abstract). Confirm a hit's `indexed_in_medline: true` + `"Indexed in MEDLINE"` in `legitimacy_signals`;
   confirm it never appears in `elevated_for` even at `weighting: 1.0`. Run a **broad** (~25-candidate) search and
   confirm the whole run completes without any candidate silently reading `false` due to a 429 — i.e. re-run the
   same search and get the same `indexed_in_medline` values both times (proves the pacing guard, not just the
   hermetic fake-fetcher tests).
9. Confirm `fit_rank`/`weighted_rank` on every profile: at `weighting: 0` they're equal for every journal; at
   `weighting: 1.0` on a topic where fit and openness disagree, at least one journal's values diverge, and any
   journal whose `weighted_rank <= top_k` but `fit_rank > top_k` proves the full-pool (not shown-slice) scope.

## Frontend — the "Where to submit" panel (SP1b, `08e_methods_publishers.jsx`)

Open Discover → **Journals**. Assert:
- **First-use choice gate.** On a fresh instance the panel shows a "set your preferences" step with **two** segmented
  controls (open-science weighting + result breadth) and **no option pre-selected** — no output/run controls appear
  until BOTH are set. **Save preferences** is disabled until both are chosen. Any pre-highlighted default is
  **Critical** (the veto). The weighting appearing as the *lone* forced choice is **High** (it re-singularizes it).
- **Local-only note at the point of choice** ("stored on this machine only — never transmitted"). Missing it is Medium.
- **Once set, the gate does not re-fire** — the panel shows the input (Selected paper / Paste abstract) + Find journals.
  The prefs stay editable in Settings → **Where to submit** (and via the output thumb).
- **Recent journal searches.** After a selected-paper run and a pasted abstract+subject run, the **Recent journal
  searches** dropdown appears. Recalling a row re-runs that stored input shape with fresh results (it does not replay
  cached result cards); **Clear history** removes the browser-local list and it stays gone after reload.
- **Output legibility (non-negotiable).** After a run, the results view **always** shows the weighting's state inline
  ("Open-science weighting: <level> — N journals elevated for <goods> · adjust") with a segmented control that re-runs
  on change. Missing/absent output thumb is **High**.
- **Profile cards** show fit / OA color / cost (APC + waiver) / license / open impact (with the Matthew-bias caveat) /
  legitimacy signals / `elevated_for`; each links to its source (journal homepage, OpenAlex, DOAJ). A closed journal
  renders with its facts (not filtered). A "predatory" label or a composite/openness **score** shown per journal is
  **Critical**. Framing must be positive (goods offered), never a deficit of the others.
- **Thumb auditability (inc 453).** With weighting on, a journal whose blended position differs from its
  fit-only position shows a caveat line ("Ranked #N here with weighting on · #M by topical fit alone"). It must
  be absent at weighting off and for any journal whose rank didn't change. This is the design doc's own "neutral
  pre-weighting ordering viewable beside the weighted one" — its sibling item, per-journal exclusion/filtering,
  remains intentionally unbuilt (an ethical-valence deferral, not an oversight — do not flag its absence).
- **SciELO + TOP Factor (inc 448).** A SciELO-indexed card shows an "Indexed in SciELO (<collections>)" signal chip.
  A TOP-Factor-rated card shows a **"show the basis"** `<details>` block (reusing `08b_methods_citation_equity.jsx`'s
  idiom) — expanding it must reveal every category name + its sub-score + `/max` + justification text; the `Total`
  must NOT appear anywhere on the card outside this expanded block. If the local TOP Factor mirror was never
  refreshed (route 85), the results view shows one report-level footer note ("TOP Factor data hasn't been
  downloaded yet…") rather than every card silently having no TOP Factor section with no explanation.
- **AJOL (inc 451).** An AJOL-matched card shows an "Indexed in AJOL" signal chip PLUS an always-visible plain-text
  line ("AJOL status: <jpps_status> · <country> · diamond OA (AJOL-confirmed)" when applicable) with a `title=`
  tooltip glossing the status in plain language. This line renders identically for a positive (`1/2/3 Stars`) and a
  cautionary (`Ceased`/`Inactive Title`) status — no filtering, no extra warning chrome beyond the tooltip. A
  credit block near the card/panel cites both Zenodo DOIs and states this is a third-party CC-BY-4.0 compilation,
  not AJOL-official. If the local AJOL mirror was never downloaded (route 86), the results view shows one
  report-level footer note rather than every card silently having no AJOL section with no explanation.
- **NLM/MEDLINE (inc 452).** A MEDLINE-indexed card shows an "Indexed in MEDLINE" signal chip (never "PubMed" —
  a real overclaim caught live pre-ship, see the security audit SP4 addendum) via the same generic
  `legitimacy_signals` chip list every other source already uses — **no new frontend code exists for this
  source** (verified: the chip list is a plain `.map()`); a missing chip for this specific source with every
  other chip present is a regression, not an intentional gap. It must never appear alongside an "elevated for"
  reason.
- **0 genai-host requests** during the flow; the abstract text is in no outbound request (SP1a's guarantee, unchanged;
  now also covers the SciELO and NLM fetches).

## Pass criteria

- The endpoint resolves a topic, returns uniform per-journal profiles ranked by local fit, and applies the weighting
  as a re-order (no displayed composite).
- 0 genai-host requests; the abstract text is in no outbound request (OpenAlex, DOAJ, SciELO, and NLM alike).
- No composite score, no "predatory" label; closed journals + no-signal journals still appear.
- SciELO/TOP Factor facts render as inspectable evidence (collections list; category-by-category basis), never a
  bare score; TOP Factor's never-downloaded state is an honest report-level note, not silent omission.
- AJOL's `jpps_status` renders plainly for every value including cautionary ones; only `1/2/3 Stars`/confirmed
  diamond ever elevates; AJOL's never-downloaded state is an honest report-level note, not silent omission; the
  credit block names both Zenodo DOIs and the third-party (not AJOL-official) framing.
- MEDLINE indexing renders as a plain `legitimacy_signals` chip via existing generic frontend code, never
  elevates, and a broad multi-candidate run completes without a 429-driven false negative. The signal claims
  exactly what it checks — "PubMed" never appears in the field name, chip text, or response shape.
- `fit_rank`/`weighted_rank` render as ordinal positions only (never a score/percentage), computed over the full
  considered pool, and the per-card caveat appears only when weighting is on and the ranks actually diverge.
- Neither/both-input -> 422; nonexistent/no-DOI paper -> 404/422; unknown job -> 404; empty topic -> honest `shown:0`.
- Recent journal-search recall re-runs stored inputs for fresh results; clearing history only clears the local recall
  list and does not affect settings or saved papers.

## Deposit

Write `.claude/qa-inbox/<RUN_ID>/route_60_publishers.md` + `screenshots/` (see `_TEMPLATE.md`) — capture the
first-use choice gate (nothing pre-selected), a results view with the output thumb, a profile card, and (if a
SciELO/TOP-Factor/AJOL hit is reachable) the expanded TOP Factor "show the basis" block and the plain AJOL status
line.
