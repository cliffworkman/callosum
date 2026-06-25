# Increment 125 — strengthen the front-matter classifier (live-validated)

A follow-up to inc 123 driven by a **live, real-Gemini** end-to-end check (the user authorized spending tokens).
Running an actual no-query papers-scope synthesis over the same papers that produced the broken summary #7
(`.local/visual/drive_inc124_live.py`) revealed inc-123's `is_front_matter_chunk` was **too conservative** — the
verified claims still contained paper titles, author/affiliation lines, journal running-headers, and funding
lines. This increment strengthens the classifier so the verified claims (and the inc-124 Overview built on them)
are real body text.

## Implemented

- **`app/backend/summarization/chunk_filtering.py`** — `is_front_matter_chunk` now also flags:
  - **Author/affiliation lines** via three superscript patterns: comma-superscripts (`,1*` `,2`, existing),
    **name-attached** superscripts (`Alves1`, `Uğurlar2`, `Unkelbach3` — `[A-Za-z][1-9](?![0-9])`, ≥2), and
    **digit-prefixed** affiliations (`1Department … 2Department` — `(?:^|\s)\d[A-Z][a-z]`, ≥2).
  - **Funding/acknowledgment lines** — `("grant"|"funding")` + a grant-id pattern (`[A-Z]{1,3}\s?\d{4,}`, e.g.
    "AG038893", "R03 DA042336").
  - **Titles / journal running-headers / headings** — the strong, prose-safe signal: **no terminal sentence
    punctuation AND ≥60% of words capitalized**. Body prose is mostly lowercase function words (low capitalized
    fraction) even when truncated mid-sentence, so this is safe for content; titles/headers ("Typical is
    Trustworthy - Evidence for a Generalized Heuristic", "Journal of Affective Disorders Reports 10 (2022)
    100380") are caught. (The earlier short+low-stopword rule is kept for short masthead labels.)
- **`tests/test_chunk_filtering.py`** — the actual front matter that leaked in the live run is now a regression
  set (FRONT_MATTER), and the actual body text that correctly stayed is asserted as CONTENT (guards against
  over-flagging).

## Key technical detail

- **Capitalized-fraction is the robust title/header discriminator.** A real sentence ends in `.`/`?`/`!` (kept),
  and prose has a low capitalized-word fraction; titles/headers/affiliation blocks have a high one and no
  terminal punctuation. So "no terminal punctuation AND caps-fraction ≥ 0.6" catches them without catching body
  prose — confirmed by the CONTENT regression cases (abstracts, body paragraphs stay content).
- **Still fallback-only** (the inc-123 two-phase `_select_no_query` is unchanged): front matter is deprioritized,
  never dropped — a paper with only front matter still contributes. So a more-aggressive classifier is safe.
- Backend-only: no `/summarize` contract change, no migration, no egress, no new dependency. Principles gate
  non-triggering (retrieval quality, like inc-66 / inc-123); inspectability/provenance/egress unchanged.

## Manual verification

- Hermetic: `tests/test_chunk_filtering.py` (the live-leaked front matter is flagged; the live body text stays
  content) + `tests/test_summarize_selected.py` (selection unchanged for body-only fixtures).
- **Live (real Gemini, egress on)**: re-ran `.local/visual/drive_inc124_live.py` over papers 1–3 → the verified
  claims are now all body text (no titles/author/journal/funding lines), and the inc-124 **Overview** populated
  with 3 real synthesis sentences, each tracing to the verified claims it restates (e.g. "For survival,
  continuously evaluating environmental risks is crucial…" → claims [2, 6]). The earlier empty Overview was
  confirmed transient (the overview Gemini call hit repeated 503s — model overloaded — and the fail-closed path
  correctly omitted it; it succeeded on retry over the cached summary).

## Pytest

449 passed, 1 skipped (no new test functions — the FRONT_MATTER/CONTENT regression lists were extended).
`ruff` clean.
