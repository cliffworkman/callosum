<!-- qa-coverage
api: /papers/duplicates*
fe: 19_duplicates.jsx
-->

# ROUTE 24 - Duplicate detection and dismissal

**Tier:** 1 local-stateful
**Goal:** Exhaust duplicate scan, polling, review, dismiss, undismiss, and dismissed-pair recovery.

## Environment

Clean seeded instance (`_TEMPLATE.md` -> Environment). **Egress UNSET.** Register listeners before navigation.

## Standing assertions

- **Console-error budget = 0.** Any console `error` >= Medium; any `pageerror` >= High.
- **No uncompletable control.** Any visible control that cannot be completed through the UI is a bug.
- **Egress gate.** With egress unset, any request to a `generativelanguage`/Gemini/genai host is **Critical**.
- **Coordinate honesty.** `exact` -> bbox rect; `region` -> scroll + note; `null` -> page-open, no rect. An approximate/absent location shown as an exact highlight is **Critical**.
- **Signal not verdict.** No hidden composite score; no "bad papers" accusation. Filters + visible counts only.

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

## Pass criteria

- Scan, polling, dismiss, and undismiss are complete and replayable.
- 0 console/page errors and 0 genai-host requests.
- Similarity is presented as evidence only, never a hidden composite quality score.
- Mobile viewport has no horizontal overflow.

## Deposit

Write `.claude/qa-inbox/<RUN_ID>/route_24_duplicates.md` + `screenshots/` (see `_TEMPLATE.md`).

