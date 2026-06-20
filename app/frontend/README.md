# Frontend

`app/frontend/` is the implemented browser UI source for Callosum.

## What Is Here

- `index.html`: page shell and script/style mounting points.
- `styles.css`: application styling, including light/dark theme tokens.
- `js/*.jsx`: ordered React chunks for shared helpers, PDF rendering, axes, duplicates, help, synthesis, details, viewer, settings, and app composition.

The backend assembles these files through `app/backend/api/frontend.py` and serves the result at `/`. `tools/build_frontend.py` can rebuild `callosum-app.html` from the same source.

## Implemented UI Areas

- Library browsing and paper detail editing.
- PDF rendering through pdf.js with text layer and coordinate-based overlays.
- User highlights and synthesis-derived highlights.
- Axes creation, scoring, manual assignment, merge/delete, filtering, and term suggestions.
- Duplicate review with dismissals.
- Tags and tag suggestions.
- Citation-grounded synthesis with evidence, quote, page, confidence, and verification state.
- Citation export flows supported by backend endpoints.
- Settings, theme toggle, and in-app help.

## Development Note

After editing anything under `app/frontend/`, rebuild the generated single-file app if the checked-in `callosum-app.html` needs to stay current:

```powershell
python tools/build_frontend.py
```
