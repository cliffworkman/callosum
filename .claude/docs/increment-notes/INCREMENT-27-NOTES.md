# Increment 27 Notes

## Implemented

- Updated `callosum-app.html` synthesis rendering to group sentences into:
  - `Verified`
  - `Flagged · needs review`
- Verified sentences render first.
- Flagged sentences render below in a visually distinct amber-accented section.
- Sentence ordering is preserved by `ordinal` within each section.
- Existing summary counts, sentence cards, citation cards, confidence scores, and coordinate-precision labels are unchanged.

## Empty-State Handling

- If there are no flagged sentences, the flagged section is omitted.
- If all sentences are flagged, the verified section is omitted and the flagged section includes a review note:
  - `No sentence in this synthesis cleared verification. Review the evidence below before relying on it.`
- A zero-sentence summary still uses the existing `No groundable summary produced` state.

## What Did Not Change

- No backend files changed.
- No API response fields changed.
- No confidence-based sorting was added.
- Flagged content is not hidden or collapsed.
- Citation provenance cards still show quote, paper/page, retrieval/quote/support scores, status, and exact/region/null coordinate precision.

## Manual Verification

Run the app:

```powershell
$env:CALLOSUM_DB_URL = "sqlite:///C:/Users/cliff/Dropbox/Dropbox/01_Work/callosum/.local/validation-summarize/validation.sqlite"
uvicorn app.backend.api.app:app --host 127.0.0.1 --port 8080
```

Open:

```text
http://127.0.0.1:8080/
```

Checklist:

1. Open the Synthesis pane.
2. Load a saved synthesis from History that has both verified and flagged sentences, or run a new mixed-result synthesis.
3. Confirm the header count still reads `N verified · M flagged`.
4. Confirm verified sentences appear first under `Verified`.
5. Confirm flagged sentences appear below under `Flagged · needs review`.
6. Confirm sentence order within each section follows the original `ordinal` order.
7. Open citation cards in both sections and confirm provenance details and coordinate precision labels are unchanged.
8. Load an all-verified synthesis and confirm there is no empty flagged section.
9. Load an all-flagged synthesis and confirm the flagged review note appears.

## Static Verification

I launched the app through FastAPI against the local validation database on port `8768` and opened it with Playwright. Result:

- Page title: `Callosum`
- Library panes loaded
- Synthesis pane loaded
- History list loaded
- `0` console errors
- Existing Babel standalone warning only

No pytest changes were needed for this frontend-only display increment.
