<!-- qa-coverage
api: /papers/duplicates*, /papers/merge
fe: 19_duplicates.jsx, 38_merge.jsx
-->

# ROUTE 24 - Duplicate detection, dismissal, and merge

**Tier:** 1 local-stateful
**Goal:** Exhaust duplicate scan, polling, review, dismiss, undismiss, dismissed-pair recovery, and the
non-destructive **merge** (inc 161) — launched from a duplicate group AND from the library bulk bar.

## Environment

Clean seeded instance (`_TEMPLATE.md` -> Environment). **Egress UNSET.** Register listeners before navigation.

## Standing assertions

- **Console-error budget = 0.** Any console `error` >= Medium; any `pageerror` >= High.
- **No uncompletable control.** Any visible control that cannot be completed through the UI is a bug.
- **Egress gate.** With egress unset, any request to a `generativelanguage`/Gemini/genai host is **Critical**.
- **Coordinate honesty.** `exact` -> bbox rect; `region` -> scroll + note; `null` -> page-open, no rect. An approximate/absent location shown as an exact highlight is **Critical**.
- **Signal not verdict.** No hidden composite score; no "bad papers" accusation. Filters + visible counts only.
- **Merge is non-destructive.** A merge must NOT delete data: both PDFs/links/tags/highlights end on the survivor; the
  merged-away copies go to **Trash** (restorable), never hard-deleted; a "Merged from…" lineage note records their
  identifiers. A merge that silently drops a link/PDF, or hard-deletes a copy, is **Critical**.

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
   in its Details, and the merged-away copy is in **Trash** (not gone) — `GET /papers` excludes it, `GET /papers?deleted=true` includes it.
8. **Merge from the library bulk bar:** select ≥2 papers → **merge** → same dialog/flow.
9. Adversarial: `POST /papers/merge` with `survivor_id ∈ merged_ids` → 422; a chosen DOI that another live paper
   holds → 409; an unknown metadata field → 422. Confirm the messages surface, not a crash.

## Pass criteria

- Scan, polling, dismiss, undismiss, and **merge** (both entry points) are complete and replayable.
- 0 console/page errors and 0 genai-host requests.
- Similarity is presented as evidence only, never a hidden composite quality score.
- Merge loses nothing: both PDFs + all links/tags/highlights survive on the survivor; merged-away copies are in
  Trash (restorable), never hard-deleted; the lineage note is present. 422/409 surface on bad merge requests.
- Mobile viewport has no horizontal overflow.

## Deposit

Write `.claude/qa-inbox/<RUN_ID>/route_24_duplicates.md` + `screenshots/` (see `_TEMPLATE.md`).

