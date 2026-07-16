<!-- qa-coverage
api: /overlooked, /overlooked/refresh, /overlooked/refresh/{job_id}
fe: 36b_overlooked.jsx
-->

# ROUTE 72 - Overlooked-work lens (per-axis discovery: relevance + same-vintage percentile, two separate inputs)

**Tier:** 2 local-stateful + public-metadata egress (OpenAlex, NOT the Gemini gate)
**Goal:** Exercise the per-axis "Possibly overlooked work" lens (header **Overlooked** button beside **Gaps**) and
prove it stays a **signal, never a verdict**: two SEPARABLE visible inputs (axis relevance + citations-vs-same-vintage
percentile) that are **never fused** into a composite score, **identity-agnostic** (no author/identity field), honest
about silence, and pull-not-push (opened per axis, nothing auto-added). Distinct from the citation-equity per-paper
"Overlooked work" card (route covering `/methods/citation-equity/overlooked`).

## Environment

Clean seeded instance (`_TEMPLATE.md` → Environment) with **≥1 axis** carrying at least a few scored members, and a
**fake OpenAlex sources client** on `app.state.openalex_sources_client` returning a topic + a set of same-year works
(some relevant + under-cited, some relevant + well-cited, some irrelevant) so the lens has a candidate pool without
network. Register a request listener before navigation. No egress consent needed (this is the public-metadata channel).

## Standing assertions

- **Console-error budget = 0.** Any console `error` ≥ Medium; any `pageerror` ≥ High.
- **Two separate inputs, never fused (Principles #2/#7).** Each row shows **relevance** (labeled, a cosine value)
  AND **cited N · Nth-percentile for {year}** as **two distinct chips**. There is **no** composite
  score/grade/rank/"hidden-gem"/quality field anywhere in the response or UI. A single fused number, or ranking the
  library by a composite, is **Critical**.
- **Identity-agnostic (A-A no-accusation veto).** No author/identity field on any candidate (API response or UI), and
  no copy attributes the neglect to a person or sorts authors. Any author/identity signal is **Critical**.
- **Signal-not-verdict + silence-not-a-certificate (#6).** The framing is "relevant to [axis], under-cited for its
  year — possibly overlooked, possibly just low-impact; your call." The empty state reads "nothing surfaced — not
  evidence none exists," and only works with enough same-year peers to rank appear (null-percentile works are not
  shown as "0"). A verdict-toned label ("overlooked gem", "the field wrongly buried this") is **High**.
- **Provenance one click away (#8).** Each row's title links to the work (DOI). A candidate with no source link is Medium.
- **Augment-never-filter.** Nothing is auto-added or auto-dismissed; Add/Dismiss are the user's and reuse the gap flow.
- **Egress posture (invariant #3).** This is **public-metadata** egress (OpenAlex `/topics` + `/works`), NOT the
  Gemini library-text gate. **No library text is transmitted**: only the axis label + topic id leave; candidate
  abstracts are embedded on-device. Any request carrying paper/abstract text to an external host is **Critical**; any
  `generativelanguage`/genai host request is **Critical** (the lens never uses the LLM).

## Adversarial checklist

- `GET /overlooked` with no `axis_id` → **422**; `POST /overlooked/refresh` with `{}` → **422**; a non-existent job
  id on `GET /overlooked/refresh/{job_id}` → **404**, not a crash.
- `POST /overlooked/refresh` for an axis that resolves to no topic (or an empty works list) → job **done** with
  `count: 0`; the UI shows the honest empty state, not an error.
- double-click **Refresh**; switch the axis mid-scan; **Refresh** disabled until an axis is chosen.
- resize to `375x812`, hard refresh — rows scroll inside the modal; no horizontal overflow.

## Steps

1. Open the library; click **Overlooked** in the header. Confirm the modal opens with an axis picker defaulting to
   "Choose an axis…" and **Refresh disabled** until an axis is chosen; the coverage line prompts to choose an axis.
2. Choose an axis → **Refresh**. Confirm it POSTs `/overlooked/refresh` → polls `GET /overlooked/refresh/{job_id}`
   → then `GET /overlooked?axis_id=` renders rows, each with **two distinct chips** (relevance + `cited N ·
   Nth-percentile for {year}`), the title as a DOI link, and **Add** / **Dismiss**.
3. Confirm the relevant-but-well-cited work is **not** surfaced (correctly not flagged), and rows are ranked by
   relevance (descending). Confirm no composite score / hidden-gem label / author field anywhere.
4. **Dismiss** a row → it disappears (re-GET, read-time filtered) and does not resurface on the next open. **Add** a
   row → it imports metadata-only (reuses `/gaps/add`) and the now-in-library row drops on re-GET.
5. Confirm the empty/low-peer axis shows the honest "nothing surfaced … not evidence none exists; low citations can
   just mean low-impact" hint, never "these are all overlooked."
6. Adversarial: missing `axis_id` → 422; unknown job id → 404; confirm messaging, not a crash. No external request
   carries library/abstract text; no genai host is contacted.

## Pass criteria

- Refresh → poll → list is complete and replayable; 0 console/page errors.
- Every row shows the two separate inputs as distinct chips; no composite/hidden-gem score, no author/identity field,
  no verdict-toned copy anywhere; provenance (DOI) one click away.
- Empty/low-peer state reads honestly; Add imports metadata-only; Dismiss never resurfaces.
- Only the axis label + topic id egress (public-metadata channel); no library/abstract text leaves; no genai host hit.
- Refresh disabled until an axis is chosen; mobile viewport has no horizontal overflow.

## Deposit

Write `.claude/qa-inbox/<RUN_ID>/route_72_overlooked_work.md` + `screenshots/` (see `_TEMPLATE.md`).
