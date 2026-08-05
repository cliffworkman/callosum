<!-- qa-coverage
api: /citations/suggest, /usage/events
fe: 37_cite.jsx
-->

# ROUTE 42 - Cite (highlight-to-suggest / evaluate)

**Tier:** 1 local-stateful
**Goal:** Exercise the in-app Cite pane — paste a draft sentence, get ranked library suggestions with stance +
evidence, and confirm the honesty invariants (region-not-exact, stance-with-quote, candidates-not-verdicts,
local/no-egress). Cite is now **Work → Cite**'s entire content (no nested tab strip) — the paper-specific
citation-integrity audits that used to sit alongside it moved to **Work → Meta-Reference** as stacked subsections
(**Citation concentration**, route_51; **How it's cited**, route_53); this route covers Work → Cite (Suggest) only.
**Inc 449** adds Semantic Scholar recommendations as a third beyond-library candidate source, anchored on the
same local Cite matches the existing OpenAlex-neighborhood expansion already uses. **Inc 450** fires the local
`quote_located` usage event (backlog #38A, route 35's own surface) from "Open source region" here — the real
trigger for that event type lives on this route, not Settings.

## Environment

Clean seeded instance (`_TEMPLATE.md` -> Environment). **Egress UNSET.** Register listeners before navigation.
The seeded `social-perception`/facial papers give a real semantic match for the paste box.

## Standing assertions

- **Console-error budget = 0.** Any console `error` >= Medium; any `pageerror` >= High.
- **Egress gate (Critical).** In-library Suggest + evaluate is **fully local** (local embeddings + local NLI).
  With egress unset, ANY request to a `generativelanguage`/Gemini/genai host while using the Cite pane is
  **Critical**. The **beyond-library** path (backlog #30, "Also search beyond my library" checkbox) is a
  SEPARATE, opt-in metadata-provider egress (Crossref/PubMed/OpenAlex/Semantic Scholar) — real network egress,
  but not the Gemini/LLM gate; it must never fire unless the checkbox is explicitly checked, and
  default-unchecked-on-open is itself a Critical assertion (see
  `.claude/security-audits/2026-07-11_beyond-library-citation-suggest.md`).
- **Coordinate honesty (Critical).** A suggestion's evidence is a chunk -> `region` precision. "Open source
  region" must open the PDF attachment that supplied that chunk, scroll to the page + show the region note, and
  never draw an exact bbox rect. A non-PDF match may open the primary PDF only without transferring the source
  page/coordinates. An approximate location shown as an exact highlight, or coordinates applied to the wrong
  attachment, is **Critical**.
- **Signal not verdict.** The stance is a labeled signal shown WITH its quote + confidence — never a bare
  verdict. The match score is labeled a relevance/ranking aid, never a correctness claim or a hidden composite.
  Beyond-library cards must show a `reason`/relationship label per candidate, never a bare/citation-count score
  — the same standing invariant applied to a second, richer card type.
- **Candidates, not auto-insert.** The pane only *proposes*; nothing inserts a citation automatically. Beyond-
  library "Add to library" only ever creates a metadata-only record (`POST /discovery/save`) — it must never
  auto-cite, auto-insert, or silently attach a PDF. (Insert is the LibreOffice macro's job, SP1b — not in this
  surface; the LibreOffice macro also gained this same opt-in beyond-library checkbox 2026-07-22, own surface.)

## Adversarial checklist

- submit empty / whitespace-only text (expect a disabled button / no request, or a 422 that surfaces cleanly)
- paste ~50KB into the textarea; submit (oversized -> 422, surfaced as "Couldn't get suggestions", no crash)
- a sentence with no library match -> the "No related papers in your library" empty state
- double-click Suggest; rapid-click; navigate away mid-request
- resize to `375x812`, hard refresh - no horizontal overflow
- toggle "Also search beyond my library" ON, then submit with the SAME oversized/empty adversarial text above
  (the beyond-library path must fail as cleanly as the in-library one — no crash, no hung request)
- toggle the checkbox ON then immediately OFF before the response returns; confirm no stale beyond-library
  cards render from the in-flight request once it resolves
- an anchor paper's DOI unknown to Semantic Scholar (a real 404) must not crash the run — OpenAlex-neighborhood
  and keyword-search candidates still return cleanly, and the `semantic-scholar-recommendations` source-coverage
  entry reflects the miss honestly (not silently reported as "success")

## Steps

1. Open **Work → Cite**. Confirm the textarea + Suggest button render directly (no inner tab strip) with the
   "local, no egress" status hint, and the "Also search beyond my library" checkbox is present and **unchecked**.
2. Paste a sentence related to a seeded paper (e.g. about facial anomalies / social perception) -> Suggest
   (`POST /citations/suggest`). Confirm a ranked list renders, each card showing title · author/year, a stance
   pill (supports/contrasts/mentions, or "stance n/a"), a `match NN` pill, and the verbatim quote. Confirm no
   request to any public-metadata provider fired (the checkbox is unchecked).
3. Confirm the ranking note ("a ranking aid, not a correctness claim") and the per-card region note are present.
4. Click **Open source region** on a suggestion backed by a secondary PDF -> the request carries that matched
   attachment id, the PDF opens at the page with a region note and NO exact rect, and the viewer toolbar names the
   active file. At `375x812`, confirm the filename remains readable and neither the toolbar nor document overflows.
   Repeat with a non-PDF matched attachment: the button reads **Open primary PDF**, the request omits the matched
   attachment id, and no source page/region overlay is applied to the different file.
   Confirm a fire-and-forget `POST /usage/events {event_type: "quote_located", count: 1}` fired for the
   matched-attachment click only — **not** for the "Open primary PDF" degraded-fallback click (Settings →
   Your usage's count for "Quotes located" should increase by exactly 1, not 2, across both clicks).
5. Check **"Also search beyond my library"**, submit again -> confirm the request body carries
   `include_beyond_library: true` and beyond-library cards now render, each showing: title/author/year/journal, a
   `relationship_label` line when OpenAlex graph evidence OR a Semantic Scholar recommendation exists (e.g.
   "Cited by a locally relevant paper: …" or "Recommended by Semantic Scholar alongside a locally relevant
   paper: …"), the `reason` text, an evidence quote (abstract or metadata fallback, labeled as such), a
   metadata-overlap pill explicitly captioned as a ranking aid (not a correctness score), and an **Add to
   library** button. Confirm no S2-internal score/rank number appears anywhere on a Semantic-Scholar-sourced card.
6. Click **Add to library** on a beyond-library card -> confirm `POST /discovery/save` fires, the card updates
   to reflect it's now in-library (or a clear success state), and nothing else in the document/library changed
   (no auto-citation, no PDF fetch).
7. Submit empty / whitespace / oversized text (both checkbox states) -> clean validation, no crash, no genai
   request either way.
8. Confirm nothing auto-inserts a citation and no card (in-library or beyond-library) presents a paper as
   good/bad or ranked by a hidden composite score.

## Pass criteria

- Suggestions render with stance + quote + match score; the empty/oversized/whitespace paths fail cleanly in
  both checkbox states.
- "Open source region" honors both source attachment and region precision (no exact rect); non-PDF fallback never
  carries coordinates to the primary PDF, and the active filename is legible without overflow.
- The beyond-library checkbox defaults OFF, and toggling it is the ONLY thing that triggers metadata-provider
  egress; every beyond-library card shows an inspectable reason/relationship label, never a bare score.
- 0 console/page errors and **0 genai-host requests** (the whole flow — in-library AND beyond-library — never
  touches Gemini/LLM hosts; beyond-library's own metadata-provider requests are expected only once checked).
- Mobile viewport has no horizontal overflow.

## Deposit

Write `.claude/qa-inbox/<RUN_ID>/route_42_cite.md` + `screenshots/` (see `_TEMPLATE.md`).
