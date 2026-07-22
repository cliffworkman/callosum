<!-- qa-coverage
api: /papers/duplicates*, /papers/merge, /merge/*, /papers/{paper_id}/merge-origin
fe: 19_duplicates.jsx, 38_merge.jsx, 25_detail.jsx
-->

# ROUTE 24 - Duplicate detection, dismissal, merge, and reversible un-merge

**Tier:** 1 local-stateful
**Goal:** Exhaust duplicate scan, polling, review, dismiss, undismiss, dismissed-pair recovery, the
non-destructive **merge** (inc 161) — launched from a duplicate group AND from the library bulk bar — and the
**reversible un-merge** (#16): a merge is reversible from the survivor's Details pane.

## Environment

Clean seeded instance (`_TEMPLATE.md` -> Environment). **Egress UNSET.** Register listeners before navigation.

## Standing assertions

- **Console-error budget = 0.** Any console `error` >= Medium; any `pageerror` >= High.
- **No uncompletable control.** Any visible control that cannot be completed through the UI is a bug.
- **Egress gate.** With egress unset, any request to a `generativelanguage`/Gemini/genai host is **Critical**.
- **Coordinate honesty.** `exact` -> bbox rect; `region` -> scroll + note; `null` -> page-open, no rect. An approximate/absent location shown as an exact highlight is **Critical**.
- **Signal not verdict.** No hidden composite score; no "bad papers" accusation. Filters + visible counts only.
- **Merge is non-destructive.** A merge must NOT delete data: both PDFs/links/tags/highlights end on the survivor;
  the merged-away copies become **merged-away husks** (hidden from the live library AND the plain Trash list),
  never hard-deleted; a "Merged from…" lineage note records their identifiers. A merge that silently drops a
  link/PDF, or hard-deletes a copy, is **Critical**.
- **Merge is reversible (#16).** The survivor's Details pane shows a "Merged from … — Un-merge" banner; un-merge
  restores the merged-away copies with their moved data (PDFs/tags/highlights) and reverts the survivor's record.
  A merge that cannot be un-done, or an un-merge that leaves data on the wrong record, is **High**.

## Adversarial checklist

- paste ~50KB into every editable field; submit empty / whitespace-only
- double-click submit; rapid-click; navigate away mid-async-job
- malformed input where an identifier is expected
- deep-link / direct state for a non-existent id
- resize to `375x812`, hard refresh - no horizontal overflow

## Steps

1. Open the Duplicates view. Confirm dismissed pairs load (`GET /papers/duplicates/dismissed`) and empty states are explicit.
2. Start duplicate detection (`POST /papers/duplicates`). Poll (`GET /papers/duplicates/{job_id}`) until done. Navigate away mid-job and return.
3. Review candidate pairs. Confirm similarity evidence is visible as a signal, not a verdict that one paper is bad.
4. Dismiss a pair (`POST /papers/duplicates/dismiss`). Confirm it leaves candidates and appears in dismissed pairs.
5. Undismiss the pair (`POST /papers/duplicates/undismiss`). Confirm it can be reviewed again.
6. Directly open a fake job id and malformed pair state. Confirm 404/validation messaging, not a crash.
7. **Merge from a duplicate group** (`38_merge.jsx`): click a group's **merge** → the dialog loads each paper
   (`GET /papers/{id}`), offers a survivor pick + per-field conflict radios + a primary-PDF pick. Confirm
   (`POST /papers/merge`). Verify the survivor keeps **both PDFs** + every link/tag, a "Merged from…" note appears
   in its Details, and the merged-away copy leaves **both** the live library (`GET /papers` excludes it) **and** the
   plain Trash list (`GET /papers?deleted=true` excludes it — it is merged-away, not naively-restorable trash).
   **Per-attachment serving (#5):** in the survivor's Details → Files list, confirm **both** PDF buttons are present
   and click each — before this backlog item every Files button opened the same (primary) PDF regardless of which
   was clicked; confirm each one now opens *its own* distinct document (`GET /papers/{id}/pdf?attachment_id=`),
   not just "a PDF opens." The non-primary file's button is the concrete regression guard for this whole feature.
8. **Merge from the library bulk bar:** select ≥2 papers → **merge** → same dialog/flow.
9. **Un-merge (#16)** (`25_detail.jsx`): on the survivor's Details, confirm the "Merged from … — Un-merge" banner
   is present (`GET /papers/{id}/merge-origin` returns the copies' titles). Click **Un-merge** (`POST
   /merge/{id}/undo`); confirm the merged-away copies reappear in the live library with their PDFs/tags, the
   survivor's adopted DOI/lineage note revert, and the banner disappears. A second undo of the same op → 422.
10. Adversarial: `POST /papers/merge` with `survivor_id ∈ merged_ids` → 422; a chosen DOI that another live paper
   holds → 409; an unknown metadata field → 422; `POST /merge/999999/undo` (unknown op) → 422. Confirm the
   messages surface, not a crash.

## Pass criteria

- Scan, polling, dismiss, undismiss, **merge** (both entry points), and **un-merge** are complete and replayable.
- 0 console/page errors and 0 genai-host requests.
- Similarity is presented as evidence only, never a hidden composite quality score.
- Merge loses nothing: both PDFs + all links/tags/highlights survive on the survivor; merged-away copies are
  merged-away husks (hidden from live + plain Trash), never hard-deleted; the lineage note is present.
- Un-merge fully reverses a merge: the merged-away copies return to the live library with their moved data, and
  the survivor's record reverts. 422/409 surface on bad merge/un-merge requests.
- Mobile viewport has no horizontal overflow.

## Deposit

Write `.claude/qa-inbox/<RUN_ID>/route_24_duplicates.md` + `screenshots/` (see `_TEMPLATE.md`).
