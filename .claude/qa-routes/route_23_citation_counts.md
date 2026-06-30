<!-- qa-coverage
api: POST /papers/citation-counts/refresh
api: GET /papers/citation-counts/refresh/{job_id}
fe: 10b_libmenus.jsx
-->

# ROUTE 23 - Library-wide citation counts

**Tier:** 1 local-stateful (external metadata — OpenAlex; allowed, NOT the Gemini gate)
**Goal:** Exercise the per-paper OpenAlex cited-by counts (inc 210, A2) — the **"Citations ↻"** header control →
`POST /papers/citation-counts/refresh` (async) → each live paper's `cited_by_count` (by DOI) stored → the library
cards show the **verbatim** count + an "as of <date>", plus an explicit **"Most cited"** sort. A displayed fact,
attributed — never a composite or a silent rank.

## Environment

Clean seeded instance (`_TEMPLATE.md` -> Environment). **Gemini egress UNSET** (this feature does NOT use it). The
OpenAlex fetch hits a public-metadata host; in a hermetic run the count store can be exercised directly via the
endpoint with the seeded papers (a live OpenAlex call may return real counts or none — both are valid). Register
listeners before navigation.

## Standing assertions

- **Console-error budget = 0.** Any console `error` >= Medium; any `pageerror` >= High.
- **No uncompletable control.** Any visible control that cannot be completed through the UI is a bug.
- **NOT the library-text egress gate.** The only thing that leaves is the paper's **DOI** → OpenAlex (public
  metadata, like My-Pubs / gap-finder). With Gemini egress unset, a request to a `generativelanguage`/Gemini/genai
  host is **Critical** — citation counts must never route through the LLM gate.
- **Verbatim, not a composite (Principles #7).** The chip shows the raw OpenAlex count ("N cited-by"); it must NOT
  be folded into any "score". A composite/derived "impact" number is **Critical**.
- **Signal not verdict / no silent rank (#2).** "Most cited" is an **explicit, opt-in** sort option — never the
  default and never auto-applied. A default citations-ranked library, or a "high-impact"/"must-read" label, is a bug.
- **Silence is not a certificate (#6).** A paper with no DOI / no OpenAlex record shows **no chip** (honest "—"),
  never a fabricated "0 cited-by". A genuine 0 (work exists, 0 cites) showing "0 cited-by" is correct + distinct.
- **Attribution visible (#8).** The source + date are reachable — the control reads "Citations · <date>" once
  fetched, and each chip's tooltip says "per OpenAlex · as of <date>".

## Adversarial checklist

- `GET /papers/citation-counts/refresh/nope` (unknown job id) → **404**, never 500
- click "Citations ↻" repeatedly / while a run is in flight — the button disables; no duplicate runaway jobs
- `POST /papers/citation-counts/refresh` with a stray body → still accepted (no body params) → 202
- a library with no DOI papers → refresh completes with `summary.total == 0`, no error, no chips appear
- resize to `375x812`, hard refresh — no horizontal overflow in the header action row

## Steps

1. In the Library header, click **Citations ↻**. It shows progress ("Citations X/N") then settles. (`POST
   /papers/citation-counts/refresh` → poll `GET …/{job_id}`.)
2. Library cards for DOI papers now show a **"N cited-by"** chip (static — no click target in the library); hover →
   the tooltip reads "Cited by N, per OpenAlex · as of <date>". A paper with no DOI / no OpenAlex record shows **no**
   chip (not "0 cited-by").
3. The header control now reads **"Citations · <date>"** (the attribution + freshness, visible).
4. Open the **Sort** dropdown → choose **Most cited**. The list reorders by count (desc); papers without a fetched
   count sort **last**. Switching back to "Date added" restores the default — "Most cited" is never the default.
5. Poll an unknown job: `GET /papers/citation-counts/refresh/does-not-exist` → **404** (not 500).

## Pass criteria

- Refresh → chips + attribution + Most-cited sort all complete through the UI.
- Counts are verbatim + attributed; no composite/score; "Most cited" is opt-in (not default); no-record → no chip
  (never a fabricated 0); a real 0 shows "0 cited-by".
- Unknown job id → 404; 0 console/page errors; **0 Gemini/genai-host requests** (DOI→OpenAlex is the only egress).
- Mobile viewport has no horizontal overflow.

## Deposit

Write `.claude/qa-inbox/<RUN_ID>/route_23_citation_counts.md` + `screenshots/` (see `_TEMPLATE.md`).
