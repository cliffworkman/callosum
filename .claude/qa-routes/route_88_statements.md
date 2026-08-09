<!-- qa-coverage
api: /statements/pending
fe: 38b_statements.jsx
-->

# ROUTE 88 - Work -> Statements: open-science statement staging

**Tier:** 1 local-stateful
**Goal:** Exhaust the open-science statement builder (data availability, code availability, preregistration,
funding, conflict of interest, ethics, AI use) while preserving CRediT's own **build-never-infer** boundary,
extended here: callosum offers common starting phrasing for each statement, but never asserts a fact about the
user's own study on their behalf. The human is the source of truth for every statement. Local, deterministic,
no AI, no egress.

## Environment

Clean seeded instance (`_TEMPLATE.md` -> Environment). **Egress UNSET** (the builder is local/no-LLM — assert no
genai-host request regardless). Register listeners before navigation. The section lives at **Work -> Statements**
(next to Work -> CRediT).

## Standing assertions

- **Console-error budget = 0.** Any console `error` >= Medium; any `pageerror` >= High.
- **No uncompletable control.** Any visible control that cannot be completed through the UI is a bug.
- **Egress gate.** The builder is local; ANY request to a `generativelanguage`/Gemini/genai host is **Critical**.
- **Build, never infer (Critical if violated).** No control infers funding, ethics approval, AI use, data/code
  availability, or preregistration status from anything callosum already knows about the paper/manuscript. The
  only inputs are what the user types or picks from a canned-phrase button; the panel copy states callosum
  offers starting phrasing and does not assert facts about the study.
- **Canned phrases are a one-click starting point, never silently applied.** Clicking a phrase button sets that
  kind's textarea to the phrase text; if the box already holds text the user typed/changed, a confirm prompt
  must appear before replacing it. A phrase is always fully editable afterward — no locked/read-only state.
- **Facts != candidates / signal-not-verdict (#7).** A statement is the **author's asserted content**, staged —
  never a callosum claim, score, or verdict about the manuscript.
- **CRediT stays untouched.** Work -> CRediT's own tab, `/credit/*` endpoints, and its "Insert CRediT statement"
  LibreOffice command are unaffected by this feature landing alongside it.

## Adversarial checklist

- unknown kind via the API (`{"kind":"not_a_real_kind","text":"x"}`) -> 422, no crash
- over-long text via the API (`text` > 4000 chars) -> 422
- staging an empty/whitespace-only `text` for a kind that was previously staged -> that kind disappears from
  `GET /statements/pending` (un-staged), not stored as an empty string
- staging two different kinds -> both coexist independently; re-staging one never clobbers the other
- resize to `375x812`, no horizontal overflow (phrase buttons wrap)

## Steps

1. Open **Work -> Statements**. Confirm the intro states callosum offers common starting phrasing and never
   asserts a fact about the study on the user's behalf, and all 7 sections render: Data availability, Code
   availability, Preregistration, Funding, Conflict of interest, Ethics, AI use.
2. For **Data availability**, click the **"Openly available"** phrase button -> the textarea fills with the
   canned sentence (containing a `[repository name]`/`[URL/DOI]` placeholder). Edit the placeholder text.
3. Click a **different** phrase button (e.g. "No new data") for the same section -> a confirm prompt appears
   (since the box has user-edited content); confirm -> the textarea is replaced. Cancel the confirm on a repeat
   attempt -> the textarea keeps the prior text.
4. **Copy** on Data availability -> the statement text is on the clipboard (button shows `✓ copied`).
5. **Send to LibreOffice** on Data availability AND on Funding (pick a phrase first) -> `POST /statements/pending`
   fires for each; the "Staged — switch to LibreOffice and run Callosum -> Insert statement…" hint appears under
   BOTH sections and **persists** (not a timed toast); `GET /statements/pending` now returns both kinds. Edit
   the Data availability textarea -> only ITS staged hint clears (Funding's stays, since it wasn't touched).
6. Leave a section's textarea empty and click **Send to LibreOffice** -> `GET /statements/pending` no longer
   includes that kind (an explicit un-stage), and the button remains clickable even with no text.
7. Adversarial (API): unknown kind -> 422; over-long text -> 422; empty text un-stages a previously-staged kind;
   two kinds staged independently persist correctly through repeated GETs.
8. Confirm no control anywhere infers, scores, or asserts a fact about funding/ethics/AI-use/data-or-code
   availability/preregistration — every section is either blank or exactly what the user typed/picked.
9. Switch to **Work -> CRediT** -> confirm it renders unchanged (its own grid, formatting, and staging still
   work exactly as before this feature landed).

## Pass criteria

- All 7 statement sections render with working canned-phrase buttons (each a full starting sentence, never a
  silent auto-fill), an editable textarea, Copy, and Send to LibreOffice.
- A phrase click never silently discards user-edited text — a confirm gate protects it.
- 0 console/page errors; **0 genai-host requests** (local).
- **No inference/score/verdict** control anywhere; the panel states callosum offers starting phrasing and does
  not assert facts about the study.
- Bad inputs fail closed (422-class); staging round-trips via `/statements/pending`; an empty send un-stages a
  kind rather than storing empty text; multiple kinds coexist independently; mobile viewport has no horizontal
  overflow.
- Work -> CRediT's own builder, endpoints, and LibreOffice command are unaffected.

## Deposit

Write `.claude/qa-inbox/<RUN_ID>/route_88_statements.md` + `screenshots/` (see `_TEMPLATE.md`).
