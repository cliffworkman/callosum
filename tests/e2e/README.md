# End-to-end browser smoke

`tests/e2e/` holds the committed Playwright browser smoke (`test_smoke.py`) — the frontend gate for CI.

It launches the real `app.backend.api.app:app` against a freshly migrated + seeded temp database, loads
`/` in headless Chromium, and asserts the React app mounts and renders with **zero** console / page errors
(the property the old ephemeral `.local/*_e2e` manual checks verified by hand).

## Opt-in

The module is **skipped unless `CALLOSUM_RUN_E2E=1`** is set, so the default `pytest` run stays offline and
deterministic (no browser, no CDN dependency). CI sets the flag after installing the browser:

```powershell
pip install -r requirements-dev.txt
python -m playwright install chromium
$env:CALLOSUM_RUN_E2E = "1"; pytest tests/e2e
```

The deterministic, always-on frontend guard (assembly integrity, SRI, `callosum-app.html` sync) lives in
`tests/test_frontend_assembly.py` and runs in the default suite.
