<!-- qa-coverage
api: /credit/statement, /credit/pending
fe: 38_credit.jsx
-->

# ROUTE 66 - Theory: CRediT contribution-statement builder (CRediTer)

**Tier:** 1 local-stateful
**Goal:** Exhaust the CRediT contribution-statement builder while preserving the load-bearing **build-never-infer**
boundary and the credit-the-lineage obligation. It is an **authoring aid**: the user assigns each author their NISO
CRediT roles (optionally lead / equal / supporting) and callosum **formats** the contributions the human *asserts*
into a contributorship statement (two layouts, by-author / by-role). It NEVER infers, verifies, scores, or judges
who did what — the human is the source of truth. Local, deterministic, no AI, no egress.

## Environment

Clean seeded instance (`_TEMPLATE.md` -> Environment). **Egress UNSET** (the builder is local/no-LLM — assert no
genai-host request regardless). Register listeners before navigation. The **CRediT statement** section lives in the
**THEORY** pane (authoring cluster: axes -> synthesis -> cite -> Where to submit -> **CRediT statement** -> Review).

## Standing assertions

- **Console-error budget = 0.** Any console `error` >= Medium; any `pageerror` >= High.
- **No uncompletable control.** Any visible control that cannot be completed through the UI is a bug.
- **Egress gate.** The builder is local; ANY request to a `generativelanguage`/Gemini/genai host is **Critical**.
- **Build, never infer (Critical if violated).** No control infers roles from the PDF, ranks contributors, scores
  contribution, or presents callosum as *assigning*/*verifying* who did what. The only inputs are what the user
  types/toggles; the panel copy states callosum formats the contributions the user asserts and does not verify them.
- **Facts != candidates / signal-not-verdict (#7).** The statement is the **author's asserted facts**, formatted —
  not a callosum claim about the literature. There is no confidence number, no composite score, no verdict badge.
- **Credit the lineage (mandatory).** The panel credits the **CRediT / NISO taxonomy** (Brand, Allen, Altman, Hlava
  & Scott 2015, *Learned Publishing*) **and** the prior tool **tenzing** (Holcombe, Kovacs, Aust & Aczel 2020,
  *PLOS ONE*) in-context, with a working **＋ add these sources to library** (idempotent). The feature never uses the
  name "tenzing" for itself.

## Adversarial checklist

- unknown role via the API (`{"role":"nope"}`) -> 422, no crash
- unknown degree via the API (`degree:"primary"`) -> 422, no crash
- over-cap author count (> MAX_AUTHORS) via the API -> 422
- over-long staged pending text (> 20000 chars) via `POST /credit/pending` -> 422
- empty grid / an author with no roles -> a valid **empty** statement (200), not an error, not a crash
- resize to `375x812`, no horizontal overflow (the role chips wrap)

## Steps

1. Open the **THEORY** pane -> **CRediT statement** section. Confirm the "formats the contributions **you assert** —
   does not verify who did what; you are the source of truth" intro + the NISO CRediT link.
2. With a paper selected, click **⤵ pull authors from this paper** -> the paper's author names seed the grid
   (non-destructive; `GET /papers/{id}`). Confirm no roles are pre-assigned (build-never-infer).
3. Assign roles: for author 1 toggle **Conceptualization** (set degree **lead**) + **Methodology**; for author 2
   toggle **Software**. Each toggle debounce-POSTs `/credit/statement`. Confirm the **By author** output reads
   e.g. `Jane Smith: Conceptualization (lead), Methodology.` / `Bob Lee: Software.` (roles in canonical taxonomy
   order; `(degree)` only when set).
4. Flip the **[By author | By role]** toggle -> the output switches to the by-role layout
   (`Conceptualization: Jane Smith (lead).` etc.) **without** a re-POST (both layouts come from one response).
5. Add a third author with **＋ add author**, assign a role, then **✕** remove them -> the grid + statement update;
   removing the last author leaves one blank row (never zero).
6. **Copy** (the **primary** action — universal) -> the statement text is on the clipboard (button shows
   `✓ copied`). **Send to LibreOffice** (the ghost/secondary action — add-on only; `POST /credit/pending`) -> the
   "Staged — switch to LibreOffice and run Callosum -> Insert CRediT statement" hint appears and **persists** (it is
   NOT a 6-second toast); confirm `GET /credit/pending` now returns the staged text. Then edit any grid cell ->
   the staged hint **clears** (the staged copy is now stale). Under the layout toggle, a one-line hint reads
   "Most journals ask for the by-author layout…".
7. Confirm the honesty caveat (formats what you assert / does not infer or verify / the 14 roles are the fixed open
   NISO taxonomy) + the **credit** block (Brand et al. 2015; tenzing / Holcombe et al. 2020) with a working
   **＋ add these sources to library** (idempotent — re-adding does not duplicate).
8. Adversarial (API): unknown role -> 422; unknown degree -> 422; > MAX_AUTHORS -> 422; over-long pending text ->
   422; empty grid -> 200 empty statement. Confirm NO infer/score/verify control exists in the UI.

## Pass criteria

- The builder formats the asserted authors x roles into both layouts (by-author / by-role), roles in canonical
  order, degree shown only when set, role-less authors omitted, an empty grid -> an empty statement.
- 0 console/page errors; **0 genai-host requests** (local).
- **No inference/score/verdict** control anywhere; the panel states callosum formats what the user asserts and does
  not verify who did what; the statement carries no confidence/composite number.
- The lineage is credited in-context (CRediT/NISO taxonomy + tenzing) with a working, idempotent library-add.
- Bad inputs fail closed (422-class); staging round-trips via `/credit/pending`; mobile viewport has no horizontal
  overflow.

## Deposit

Write `.claude/qa-inbox/<RUN_ID>/route_66_credit.md` + `screenshots/` (see `_TEMPLATE.md`).
