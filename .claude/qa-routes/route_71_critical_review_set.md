<!-- qa-coverage
api: /critical-read/set, /critical-read/set/{job_id}
fe: 08y_critical_set.jsx
-->

# ROUTE 71 - Set (multi-paper) critical review (fact-matrix + intra-set contradictions + AI cross-paper candidates)

**Tier:** 2 local-stateful + egress-gated
**Goal:** Exercise the multi-paper "critical read" — the modal launched from a shown synthesis ("Critically review
these sources") or the library bulk bar ("critical read") — and prove it stays a **signal, never a verdict**: the
Tier-1 aggregate is a fact-matrix (no score), intra-set contradictions open the right PDF, and Tier-2 AI cross-paper
candidates are egress-gated, verbatim-grounded, and human-confirmed. Extends route 67 (single-paper) to the set.

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
- **Egress gate (invariant #3).** With egress unset: the Tier-2 "Suggest cross-paper critiques (AI)" control is
  hidden (an "enable AI in Settings" note), the job's `llm_status.status == "unavailable"` if forced, and **zero**
  requests reach a `generativelanguage`/Gemini/genai host. Tier 1 still works fully. Any genai-host request with
  egress off is **Critical**.

## Adversarial checklist

- `POST /critical-read/set` with `<2` or `>12` ids → **422**; an unknown id → **404**; a non-existent job id on GET
  → **404**, not a crash.
- double-click the "critical read" / "Suggest cross-paper critiques (AI)" buttons; close the modal mid-job and reopen.
- egress off → force `POST /critical-read/set {llm:true}` → job completes with `llm_status.status == "unavailable"`,
  no candidates created, no genai host hit.
- resize to `375x812`, hard refresh — the matrix scrolls inside its own container; the modal body has no horizontal overflow.

## Steps

1. Select ≥2 papers in the library; click **critical read** in the bulk bar. Confirm the modal POSTs
   `/critical-read/set` → polls `GET /critical-read/set/{job_id}` → renders: the **fact-matrix** (rows = papers,
   columns = the distinct method-signal kinds + a contested count) with the "not a score" caption, and the **"where
   these papers disagree"** list (each item: the claim, the contradicting quote, both titles, page, stance +
   confidence).
2. Click a disagreement item → it opens the **contradicting** paper at the page (region precision) and closes the
   modal. Confirm the right PDF/page.
3. Confirm an all-quiet set shows the honest "nothing surfaced by this check … only silence from these checks",
   never "these papers agree."
4. From a **shown synthesis**, click **"Critically review these sources (N)"** → the modal opens over the synthesis's
   cited papers (2..12). Confirm the button is hidden for a read-only instance and when <2 papers were cited.
5. **Egress OFF (default):** confirm the Tier-2 control is hidden (the "enable AI in Settings" note). Directly
   `POST /critical-read/set {llm:true}` → the job completes with `llm_status.status == "unavailable"` and no
   candidates; no genai host is contacted.
6. **Egress ON (fake/loopback provider):** click **Suggest cross-paper critiques (AI)**. Confirm each returned
   candidate quotes a set paper verbatim, names which paper it anchors to, carries a stance + confidence, and (if
   present) shows "the model relates this to: …" labeled as framing, not a link. An ungrounded model draft must NOT
   appear (dropped by the #13 bar).
7. **Accept** a candidate (`POST /critical-read/candidates/{id}/accept`) → it persists as accepted. **Reject**
   another (`.../reject`) → it disappears and is never re-proposed on a re-generate (rejected-signature union).
8. Adversarial: `<2`/`>12`/unknown ids → 422/404; unknown job id → 404; confirm messaging, not a crash.

## Pass criteria

- Tier 1 (job + fact-matrix + intra-set contradictions) and Tier 2 (generate + accept/reject) are complete and
  replayable from both entry points (synthesis + bulk bar).
- 0 console/page errors; 0 genai-host requests with egress off; Tier-2 gated (control hidden + `unavailable` when off).
- No composite score / ranked-paper list anywhere; facts vs. candidates visually distinct; every candidate is
  verbatim-grounded with which-paper + stance + confidence; `related_paper_ids` shown as framing not a link; no
  author-directed language.
- Accept persists; reject never returns. The matrix scrolls in-container; mobile viewport has no horizontal overflow.

## Deposit

Write `.claude/qa-inbox/<RUN_ID>/route_71_critical_review_set.md` + `screenshots/` (see `_TEMPLATE.md`).
