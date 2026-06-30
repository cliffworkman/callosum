<!-- qa-coverage
api: /methods/citation-equity*
fe: 08b_methods_citation_equity.jsx
-->

# ROUTE 51 - Methods: citation-equity audit (identity-agnostic structural reference-list audit)

**Tier:** 1 local-stateful
**Goal:** Exhaust the citation-equity audit over a library paper while preserving the load-bearing posture:
**identity-agnostic** (no author-identity inference), **descriptive — never a score / target / quota /
accusation**, honest coverage, and the field comparison shown as context.

## Environment

Clean seeded instance (`_TEMPLATE.md` -> Environment). Inject a **fake `openalex_client`** (the audit needs
OpenAlex metadata; no real egress in QA) — or assert the run makes **no genai-host request** regardless. Register
listeners before navigation.

## Standing assertions

- **Console-error budget = 0.** Any console `error` >= Medium; any `pageerror` >= High.
- **No uncompletable control.** Any visible control that cannot be completed through the UI is a bug.
- **Egress gate.** The audit fetches **public OpenAlex metadata**, NOT library text. ANY request to a
  `generativelanguage`/Gemini/genai host during a run is **Critical** (this is not the Gemini gate).
- **No identity inference (veto-level).** No gender/race/sex of any author is inferred, shown, or used anywhere.
  A "gender balance" number must NOT appear; the deferred-module note states it is deliberately not produced. Any
  per-author identity label is **Critical**.
- **Signal not verdict.** No composite "equity score", no pass/fail, no rank, no accusation about the paper or any
  person. Each signal is a raw shape with an inspectable basis; the field value is context, not a target.
- **Honest coverage (#6).** Each signal reports how many references it could resolve; a reference with no
  affiliation/country data is shown as "unknown", never assumed domestic.

## Adversarial checklist

- run on a paper with **no DOI** -> the section says OpenAlex can't resolve its references; the run control is
  absent (POST would 422)
- run on a paper whose OpenAlex record has **no referenced_works** -> honest "nothing to audit" (no crash)
- run on a paper with **no primary_topic** -> the report shows the list's own shape, no field comparison, no crash
- deep-link / direct GET a non-existent citation-equity job id -> 404
- navigate away / switch the selected paper mid-job; rapid re-run; resize to `375x812`, no horizontal overflow

## Steps

1. Select a paper -> open METHODS -> the **Citation equity** section (order 35, among the real tools). Confirm the
   descriptive intro states it is "descriptive context, never a score or a target" + "Identity-agnostic: no
   author-identity inference."
2. Click **Run audit** (`POST /methods/citation-equity/run`); poll (`GET .../run/{job_id}`) with the
   `ProgressBar`. Confirm the **field attribution** ("compared with a sample of N recent <topic> papers").
3. Confirm the **5 signals** render: self-citation, reliance on highly-cited work (Matthew), venue concentration,
   institutional concentration, geographic / Global-South spread. Each shows a **This list vs Field** mini-bar
   (where applicable), a **descriptive summary** (never a verdict), an expandable **basis** (the refs / venues /
   countries behind the number), and a **coverage** line.
4. Expand a signal's **basis** -> the specific references/venues/countries are listed (inspectability).
5. Confirm the **deferred-module note** ("a gender or identity balance number is deliberately not produced …") and
   the **credit** block (King et al. 2017; Merton 1968; Perc 2014) with a working **＋ add to library** (idempotent).
6. **Overlooked work (SP2, inc 228).** Below the audit, the **Overlooked work** sub-section: click **Find overlooked
   work** (`POST /methods/citation-equity/overlooked`); poll (`GET .../overlooked/{job_id}`). Confirm the intro
   states it is "candidates to consider, never a 'you must cite this'; nothing is dropped or auto-added, and an
   author's identity is never the reason." Confirm each candidate shows a **topical match** chip (callosum's own
   local cosine), an optional **shared topics** "why", and either **✓ in library** or a one-click **＋ Add** that
   adds metadata-only (`POST /discovery/save` — NO PDF) and flips to **✓ added**. **Veto-level assertions:** there is
   **no "drop / remove this citation" control anywhere**; **no per-author identity** label and **no "gender balance"**
   number; **no quota / "add N to hit a target"** copy; candidates ranked by topical match, **never by citation
   count**. A no-candidate result shows an honest empty state.
7. Adversarial: a no-DOI paper -> can't-resolve message (audit + overlooked both 422-class); a fake job id -> 404;
   mobile viewport -> no overflow.

## Pass criteria

- The audit completes; the panel shows the field attribution + 5 descriptive signals (list-vs-field bars +
  inspectable bases + coverage) + the deferred-module note + credit.
- **Overlooked work**: candidates render with a topical-match chip + (optional) shared-topics why + ✓-in-library /
  ＋ Add; Add is metadata-only (`/discovery/save`, no PDF) and flips to ✓ added; **no drop/remove control, no
  per-author identity, no quota copy**; ranked by topical match, not citation count.
- 0 console/page errors; **0 genai-host requests** (OpenAlex metadata + a local embedding, never the Gemini gate).
- **No identity inference**: no gender/race label or "gender balance" number anywhere (audit or overlooked).
- No composite score / rank / pass-fail / accusation; the field value is shown as context.
- Empty/no-DOI/no-topic/error states are honest; mobile viewport has no horizontal overflow.

## Deposit

Write `.claude/qa-inbox/<RUN_ID>/route_51_methods_citation_equity.md` + `screenshots/` (see `_TEMPLATE.md`).
