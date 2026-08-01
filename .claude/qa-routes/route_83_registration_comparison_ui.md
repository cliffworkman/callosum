<!-- qa-coverage
fe: 08h_methods_transparency.jsx, 08i_registration_comparison.jsx
-->

# ROUTE 83 — End-to-end registration comparison UI

**Tier:** 2 local-stateful + explicit registry egress/acquisition where selected
**Goal:** Use the workflow as a reader and verify every state/action/evidence boundary.

## Environment

Fresh migrated fixture DB with: printed OSF URL/DOI and hidden “here” cases; multiple/false candidates; OSF and
AsPredicted acquisitions; local PDF; multi-study paper; all curated comparison outcomes; amendment; unavailable/
withdrawn candidate. Capture browser requests, console, and page errors. AI egress remains disabled.

## Steps

1. Open Transparency. Verify local detection/reference state and no registry/acquisition/comparison request on open.
2. Run candidate discovery through its disclosure, confirm one candidate, acquire it explicitly, and inspect the
   stored registration independently. Verify each preceding state and that no step silently starts the next.
3. Select a version, toggle relevant supplements/expansion, and choose **Compare now**. Navigate away/back during the
   job; verify Status and final state. Double-submit is disabled.
4. Inspect every curated row side by side. Open both available source locations and verify exact attachment/page and
   honest region precision. Inspect search scope and uncertainty, especially every “not located” row.
5. Mark reviewed, dismiss a flag, add/edit a note, and reload. Verify state persists while source evidence does not
   change. Exercise a failed save and verify the inline error.
6. Change registration/article/included-supplement basis. Verify stale state/reasons and **Re-run comparison**. Select
   the prior registration version and verify its historical run remains inspectable.
7. Choose **Incorrect registration match**. Verify recovery instructions, stale prior run, disabled compare for that
   version, fresh search/another confirmation path, and backend refusal if a stale client submits anyway.
8. Use a run with no difference flags. Verify it says no positive certificate is implied and shows no green “pass,”
   compliance/integrity/risk/deviation score, author judgment, or “authors followed/failed” wording.
9. Use an unsupported/empty registration extraction. Verify one **Extraction uncertain** document row appears, no
   publication search is claimed, and the run does not look like an empty successful crosswalk.
10. While acquisition/comparison is running, reject the candidate or choose **Incorrect registration match**. Verify
    the stale job cannot import/save. Re-role a local registration to **Other** and verify the panel refreshes, the
    link becomes unavailable, and existing runs stale.
11. Inspect a timing row and verify its searched chunk IDs/source attachment checksums match the visible evidence;
    an out-of-scope dated passage must not change the result.
12. Repeat at 375px. Verify evidence columns stack, controls do not overflow, and source/review actions remain usable.

## Pass criteria

The workflow is discoverable, explicit, recoverable, paired-evidence-first, responsive, and state-complete; all
egress is gated; source anchors are honest; stale/incorrect matches cannot appear current; and no verdict/score exists.
