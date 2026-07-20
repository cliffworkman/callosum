<!-- qa-coverage
api: /citations/suggest
fe: 37_cite.jsx
-->

# ROUTE 42 - Cite (highlight-to-suggest / evaluate)

**Tier:** 1 local-stateful
**Goal:** Exercise the in-app Cite pane — paste a draft sentence, get ranked library suggestions with stance +
evidence, and confirm the honesty invariants (region-not-exact, stance-with-quote, candidates-not-verdicts,
local/no-egress). Cite is now **Work → Cite**'s entire content (no nested tab strip) — the paper-specific
citation-integrity audits that used to sit alongside it moved to **Work → Meta-Reference** as stacked subsections
(**Citation concentration**, route_51; **How it's cited**, route_53); this route covers Work → Cite (Suggest) only.

## Environment

Clean seeded instance (`_TEMPLATE.md` -> Environment). **Egress UNSET.** Register listeners before navigation.
The seeded `social-perception`/facial papers give a real semantic match for the paste box.

## Standing assertions

- **Console-error budget = 0.** Any console `error` >= Medium; any `pageerror` >= High.
- **Egress gate (Critical).** Suggest + evaluate is **fully local** (local embeddings + local NLI). With egress
  unset, ANY request to a `generativelanguage`/Gemini/genai host while using the Cite pane is **Critical**.
- **Coordinate honesty (Critical).** A suggestion's evidence is a chunk -> `region` precision. "Open source
  region" must scroll to the page + show the region note, never draw an exact bbox rect. An approximate location
  shown as an exact highlight is **Critical**.
- **Signal not verdict.** The stance is a labeled signal shown WITH its quote + confidence — never a bare
  verdict. The match score is labeled a relevance/ranking aid, never a correctness claim or a hidden composite.
- **Candidates, not auto-insert.** The pane only *proposes*; nothing inserts a citation automatically. (Insert
  is the LibreOffice macro's job, SP1b — not in this surface.)

## Adversarial checklist

- submit empty / whitespace-only text (expect a disabled button / no request, or a 422 that surfaces cleanly)
- paste ~50KB into the textarea; submit (oversized -> 422, surfaced as "Couldn't get suggestions", no crash)
- a sentence with no library match -> the "No related papers in your library" empty state
- double-click Suggest; rapid-click; navigate away mid-request
- resize to `375x812`, hard refresh - no horizontal overflow

## Steps

1. Open **Work → Cite**. Confirm the textarea + Suggest button render directly (no inner tab strip) with the
   "local, no egress" status hint.
2. Paste a sentence related to a seeded paper (e.g. about facial anomalies / social perception) -> Suggest
   (`POST /citations/suggest`). Confirm a ranked list renders, each card showing title · author/year, a stance
   pill (supports/contrasts/mentions, or "stance n/a"), a `match NN` pill, and the verbatim quote.
3. Confirm the ranking note ("a ranking aid, not a correctness claim") and the per-card region note are present.
4. Click **Open source region** on a suggestion -> the PDF opens at the page with a region note, NO exact rect.
5. Submit empty / whitespace / oversized text -> clean validation, no crash, no genai request.
6. Confirm nothing auto-inserts a citation and no card presents a paper as good/bad or ranked by a hidden score.

## Pass criteria

- Suggestions render with stance + quote + match score; the empty/oversized/whitespace paths fail cleanly.
- "Open source region" honors region precision (no exact rect).
- 0 console/page errors and **0 genai-host requests** (the whole flow is local).
- Mobile viewport has no horizontal overflow.

## Deposit

Write `.claude/qa-inbox/<RUN_ID>/route_42_cite.md` + `screenshots/` (see `_TEMPLATE.md`).
