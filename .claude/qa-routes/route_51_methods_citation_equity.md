<!-- qa-coverage
api: /methods/citation-equity*, /wip/manuscripts/{manuscript_id}/citation-equity/run, /wip/citation-equity/run/{job_id}
api: /manuscripts/{manuscript_id}/citation-equity/run, /citation-equity/run/{job_id}
fe: 08b_methods_citation_equity.jsx, 37b_meta_reference.jsx
-->

# ROUTE 51 - Methods: Citation concentration (structural reference-list audit; never categorizes the people cited)

**Tier:** 1 local-stateful
**Goal:** Exhaust the Citation-concentration audit over a library paper while preserving the load-bearing posture:
it **never categorizes the people cited** (no gender/race/nationality/region — the geography "Global South" signal
was removed inc 229, rejected on principle), it is **descriptive — never a score / target / quota / accusation**,
honest about coverage, and the field comparison is shown as context.

## Environment

Clean seeded instance (`_TEMPLATE.md` -> Environment). Inject a **fake `openalex_client`** (the audit needs
OpenAlex metadata; no real egress in QA) — or assert the run makes **no genai-host request** regardless. Register
listeners before navigation.

## Standing assertions

- **Console-error budget = 0.** Any console `error` >= Medium; any `pageerror` >= High.
- **No uncompletable control.** Any visible control that cannot be completed through the UI is a bug.
- **Egress gate.** The audit fetches **public OpenAlex metadata**, NOT library text. ANY request to a
  `generativelanguage`/Gemini/genai host during a run is **Critical** (this is not the Gemini gate).
- **No people-categorization (veto-level).** No gender/race/sex AND no nationality/country/Global-North-South of any
  author is inferred, shown, or used anywhere. A "gender balance" or "Global South share" number must NOT appear;
  the panel simply doesn't show any of it (no note about it either — the absence is clean, not editorialized). Any
  per-author identity or origin label is **Critical**. (The earlier geography signal was removed; if it reappears,
  **Critical**.)
- **Signal not verdict.** No composite score, no pass/fail, no rank, no accusation about the paper or any
  person. Each signal is a raw shape with an inspectable basis; the field value is context, not a target.
- **Honest coverage (#6).** Each signal reports how many references it could resolve; a reference with no data for
  that signal is shown as "unknown", never assumed.
- **Low coverage is flagged, not hidden (#4/#6 — inc 229).** A signal computed over <50% of the references carries
  `low_coverage:true` + a `coverage_fraction`, and the UI shows a **⚠ low coverage (N%)** badge — the number is
  still shown (never suppressed) but it must not read as comparable to a fully-resolved signal or the field baseline.
- **WIP has no fabricated field or author identity (inc 447).** A WIP manuscript has no DOI and no stored author
  list, so `field_topic` is always `None` (an honest "no field comparison available" note, never a guessed topic)
  and self-citation always reads "not computed" (never a fabricated 0%). The reference list itself comes from the
  manuscript's own "cited" `wip_references` links, never an OpenAlex `referenced_works` graph traversal.

## Adversarial checklist

- run on a paper with **no DOI** -> **both** run controls are absent (inc 257): the audit shows "This paper has no
  DOI, so OpenAlex can't resolve its references. Add one under Identifiers in the Detail pane to enable this audit."
  with **no Run audit button**, and Overlooked work shows "This paper has no DOI, so OpenAlex can't relate work to it.
  Add one under Identifiers in the Detail pane to enable the overlooked-work search." with **no Find overlooked work
  button** (previously the overlooked button was clickable → a silent 422). Neither POST is reachable from the UI; the
  hint points the user to the fix (add a DOI in the Detail pane) rather than dead-ending on the limitation (inc 260).
- run on a paper whose OpenAlex record has **no referenced_works** -> honest "nothing to audit" (no crash)
- run on a paper with **no primary_topic** -> the report shows the list's own shape, no field comparison, no crash
- deep-link / direct GET a non-existent citation-equity job id -> 404
- navigate away / switch the selected paper mid-job; rapid re-run; resize to `375x812`, no horizontal overflow

## Steps

1. Select a paper -> open **Work -> Meta-Reference** -> the **Citation concentration** subsection (stacked between
   Meta Reference List and How it's cited on one scrollable panel — no tab-switching).
   Confirm the descriptive intro frames it as concentration ("does it lean on your own work, famous work, a few
   venues, a few elite institutions?") and states it "never looks at who the cited authors are — only what is cited."
2. Click **Run audit** (`POST /methods/citation-equity/run` — the path keeps the historical slug); poll
   (`GET .../run/{job_id}`) with the `ProgressBar`. Confirm the **field attribution** ("sample of N recent <topic>").
3. Confirm the **4 signals** render: self-citation, reliance on highly-cited work (Matthew), venue concentration,
   institutional concentration. **There is NO geography / Global-South signal.** Each shows a **This list vs Field**
   mini-bar (where applicable), a **descriptive summary** (never a verdict), an expandable **basis** (the refs /
   venues / institutions behind the number), and a **coverage** line.
4. Expand a signal's **basis** -> the specific references/venues/institutions are listed (inspectability).
5. Confirm the **credit** block (King et al. 2017; Merton 1968; Perc 2014) with a working **＋ add to library**
   (idempotent). There is **no** "we don't categorize people" disclaimer in the UI — the absence is clean, not a note.
6. **Overlooked work (SP2, inc 228).** Below the audit, the **Overlooked work** sub-section: click **Find overlooked
   work** (`POST /methods/citation-equity/overlooked`); poll (`GET .../overlooked/{job_id}`). Confirm the intro
   states it is "candidates to consider, never a 'you must cite this'; nothing is dropped or auto-added, and an
   author's identity is never the reason." Confirm each candidate shows a **topical match** chip (callosum's own
   local cosine), an optional **shared topics** "why", and either **✓ in library** or a one-click **＋ Add** that
   adds metadata-only (`POST /discovery/save` — NO PDF) and flips to **✓ added**. **Veto-level assertions:** there is
   **no "drop / remove this citation" control anywhere**; **no per-author identity** label and **no "gender balance"**
   number; **no quota / "add N to hit a target"** copy; candidates ranked by topical match, **never by citation
   count**. A no-candidate result shows an honest empty state.
7. Adversarial: a no-DOI paper -> **both** controls are gated OFF (inc 257) with their own honest no-DOI hints — no
   Run-audit button AND no Find-overlooked-work button (neither POST is reachable, so no silent 422); a fake job id
   -> 404; mobile viewport -> no overflow.
8. Open a WIP manuscript with at least one Library paper linked as **cited** -> **Work -> Meta-Reference** ->
   **Citation concentration**. Click **Run audit** (no DOI gate — the button is always available for WIP, unlike
   the Library-paper path). Confirm the field-comparison line reads "No field comparison available for an
   unpublished manuscript" and the self-citation signal reads "not computed" rather than a number.
9. Confirm **Find overlooked work** does not appear for a WIP manuscript — instead a plain
   "isn't available for WIP manuscripts yet" note, with no reachable control.
10. Link a paper as **to-cite** (not cited) and confirm it never contributes to `references_total` on a WIP run.

## Pass criteria

- The audit completes; the panel shows the field attribution + **4** descriptive signals (list-vs-field bars +
  inspectable bases + coverage) + credit. **No geography signal, and no per-author identity/origin anywhere.**
- **Overlooked work**: candidates render with a topical-match chip + (optional) shared-topics why + ✓-in-library /
  ＋ Add; Add is metadata-only (`/discovery/save`, no PDF) and flips to ✓ added; **no drop/remove control, no
  per-author identity, no quota copy**; ranked by topical match, not citation count.
- 0 console/page errors; **0 genai-host requests** (OpenAlex metadata + a local embedding, never the Gemini gate).
- **No people-categorization**: no gender/race/nationality label, no "gender balance" or "Global South" number,
  and no geography signal anywhere (audit or overlooked).
- No composite score / rank / pass-fail / accusation; the field value is shown as context.
- Empty/no-DOI/no-topic/error states are honest; a **no-DOI paper gates BOTH the Run-audit and Find-overlooked-work
  controls off** (inc 257) with honest hints (no reachable 422); mobile viewport has no horizontal overflow.

## Deposit

Write `.claude/qa-inbox/<RUN_ID>/route_51_methods_citation_equity.md` + `screenshots/` (see `_TEMPLATE.md`).
