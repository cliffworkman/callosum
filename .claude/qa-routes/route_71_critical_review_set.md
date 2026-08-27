<!-- qa-coverage
api: /critical-read/set, /critical-read/set/{job_id}, /critical-read/candidates/triage
fe: 08y_critical_set.jsx, 08z_critical_triage.jsx
-->

# ROUTE 71 - Set (multi-paper) critical review (fact-matrix + intra-set contradictions + AI cross-paper candidates + triage)

**Tier:** 2 local-stateful + egress-gated
**Goal:** Exercise the multi-paper "critical read" — the modal launched from a shown Synthesize → Ask result ("Critically review
these sources") or the library bulk bar ("critical read") — and prove it stays a **signal, never a verdict**: it is
button-gated (never auto-runs), the Tier-1 aggregate is a fact-matrix (no score), intra-set contradictions open the
right PDF, Tier-2 AI cross-paper candidates are egress-gated/verbatim-grounded/human-confirmed, and the optional AI
triage layer only ever labels/filters — never alters — the underlying facts or candidates. Extends route 67
(single-paper) to the set.

## Environment

Clean seeded instance (`_TEMPLATE.md` → Environment) with **≥3 processed papers** (some carrying stored method
signals, at least two that disagree). Run once with **egress UNSET** (the default) and once with egress enabled + a
fake/loopback provider. Register listeners before navigation.

## Standing assertions

- **Console-error budget = 0.** Any console `error` ≥ Medium; any `pageerror` ≥ High.
- **Signal, not verdict / no composite score.** The aggregate is a **fact-matrix** — per-paper stored check
  statuses + an intra-set contested count. **No** score/quality/grade/rank/rating field anywhere in the response or
  UI; an empty matrix cell reads as "this check found nothing on this paper," never "clean." A ranked or scored
  paper list is **Critical**.
- **Facts vs. candidates are distinct.** The matrix + "where these papers disagree" list are facts; Tier-2 AI items
  render as **candidates** (amber) the user confirms. A candidate shown as an established finding is **High**.
- **#13 verbatim bar + honest link framing.** Every Tier-2 candidate carries a verbatim `anchor_quote` from *some
  set paper* + which paper it anchors to + an NLI stance + a visible confidence. `related_paper_ids` is shown
  explicitly as **"the model's framing, not a verified link."** A candidate with no grounding quote is **High** (it
  should have been dropped server-side); a related-paper edge presented as a verified fact is **High**.
- **No author-directed judgment (A-A veto).** No copy/candidate accuses a person. Any author-directed language is
  **Critical**.
- **Egress gate (invariant #3).** With egress unset: the Tier-2 "Suggest cross-paper critiques (AI)" toggle is
  hidden (an "enable AI in Settings" note), the job's `llm_status.status == "unavailable"` if forced, and **zero**
  requests reach a `generativelanguage`/Gemini/genai host. Tier 1 still works fully. Any genai-host request with
  egress off is **Critical**.
- **Button-gated, not auto-run.** Opening the modal must NOT itself fire `POST /critical-read/set` — an idle state
  with a **"Run critique"** button (plus the two toggles below) must render first, unless the modal is reopened onto
  an already-running/finished job (a Status-popover click or a same-session sessionStorage resume), which may
  auto-attach without a fresh click. An automatic POST on open with no prior job is **High**.
- **AI triage is a reversible display layer (critique-triage feature).** With the "AI triage" toggle checked, both
  the contested-claims list and Tier-2 candidates may carry an `llm_triage` label (`prioritize`/`uncertain`/
  `likely_noise`) + rationale, and an "All rows"/"AI-focused" filter toggle appears once any item is labeled.
  Toggling to "AI-focused" must only **hide** likely-noise items, never delete/mutate the underlying fact or
  candidate — switching back to "All rows" must restore every item unchanged. A triage label that alters a
  contested claim's text, stance, confidence, or a candidate's status/quote is **Critical** (it must be display-only).
  With egress off, checking "AI triage" must not be reachable at all (same toggle-hidden gate as Suggest).

## Adversarial checklist

- `POST /critical-read/set` with `<2` or `>12` ids → **422**; an unknown id → **404**; a non-existent job id on GET
  → **404**, not a crash.
- double-click **Run critique**; close the modal mid-job and reopen from the Status popover (must reattach to the
  same job, not start a second one); reopen after the job finished (must show the finished report, not re-run).
- egress off → force `POST /critical-read/set {llm:true, triage:true}` → job completes with
  `llm_status.status == "unavailable"` and `triage_status.status == "unavailable"`, no candidates created, no
  contested claim gains an `llm_triage`, no genai host hit.
- toggle "AI-focused" when every item happens to be labeled `likely_noise` → an honest "all N triaged as lower-yield
  — switch to All rows" message, never a silently-empty section.
- resize to `375x812`, hard refresh — the matrix scrolls inside its own container; the modal body has no horizontal overflow.

## Steps

1. Select ≥2 papers in the library; click **critical read** in the bulk bar. Confirm the modal opens **idle** — a
   **"Run critique"** button plus two unchecked toggles ("Suggest cross-paper critiques (AI)", "AI triage") — and
   nothing POSTs until clicked. Click **Run critique** with both toggles off. Confirm it POSTs `/critical-read/set
   {llm:false, triage:false}` → polls `GET /critical-read/set/{job_id}` → renders: the **fact-matrix** (rows =
   papers, columns = the distinct method-signal kinds + a contested count) with the "not a score" caption, and the
   **"where these papers disagree"** list (each item: the claim, the contradicting quote, both titles, page, stance
   + confidence), with no candidates section populated and no triage filter shown (nothing triaged yet).
2. Click a disagreement item → it opens the **contradicting** paper at the page (region precision) and closes the
   modal. Confirm the right PDF/page.
3. Confirm an all-quiet set shows the honest "nothing surfaced by this check … only silence from these checks",
   never "these papers agree."
4. From a shown **Synthesize → Ask** result, click **"Critically review these sources (N)"** → the modal opens over the synthesis's
   cited papers (2..12), idle as in step 1. Confirm the button is hidden for a read-only instance and when <2 papers were cited.
5. **Egress OFF (default):** confirm both toggles are hidden (the "enable AI in Settings" note is shown instead).
   Directly `POST /critical-read/set {llm:true, triage:true}` → the job completes with both `llm_status.status` and
   `triage_status.status` == "unavailable" and no candidates; no genai host is contacted.
6. **Egress ON (fake/loopback provider):** re-open fresh, check **both** toggles, click **Run critique** — confirm
   this is **one** job (no second `/critical-read/set` POST). Confirm each returned candidate quotes a set paper
   verbatim, names which paper it anchors to, carries a stance + confidence, and (if present) shows "the model
   relates this to: …" labeled as framing, not a link. An ungrounded model draft must NOT appear (dropped by the
   #13 bar). Confirm any contested claims AND the candidates each may carry an **"AI triage · <label>"** badge with
   a rationale and the "display aid only" disclaimer; confirm the "All rows"/"AI-focused" toggle appears and
   correctly hides/shows `likely_noise` items without altering their underlying text/stance/confidence/status.
7. **Accept** a candidate (`POST /critical-read/candidates/{id}/accept`) → it persists as accepted. **Reject**
   another (`.../reject`) → it disappears and is never re-proposed on a re-generate (rejected-signature union).
8. Re-triage on demand: `POST /critical-read/candidates/triage {candidate_ids:[...]}` for already-persisted
   candidates from step 6/7 → confirm it returns/persists updated `llm_triage` labels without touching `concern`,
   `anchor_quote`, `stance`, `confidence`, or `status`.
9. Adversarial: `<2`/`>12`/unknown ids → 422/404; unknown job id → 404; confirm messaging, not a crash.

## Pass criteria

- The modal never auto-runs on open (except a genuine Status/session resume of an already-started job); Tier 1
  (job + fact-matrix + intra-set contradictions) and Tier 2 (toggle-driven generate + accept/reject) are complete
  and replayable from both entry points (synthesis + bulk bar), as **one** job per click.
- 0 console/page errors; 0 genai-host requests with egress off; both Tier-2 and AI-triage toggles gated (hidden +
  `unavailable` when off).
- No composite score / ranked-paper list anywhere; facts vs. candidates visually distinct; every candidate is
  verbatim-grounded with which-paper + stance + confidence; `related_paper_ids` shown as framing not a link; no
  author-directed language.
- AI triage is a strictly reversible display layer: labels/filter never alter underlying facts, candidate content,
  or status; toggling "All rows" always restores the complete, unfiltered list.
- Accept persists; reject never returns. The matrix scrolls in-container; mobile viewport has no horizontal overflow.

## Deposit

Write `.claude/qa-inbox/<RUN_ID>/route_71_critical_review_set.md` + `screenshots/` (see `_TEMPLATE.md`).
