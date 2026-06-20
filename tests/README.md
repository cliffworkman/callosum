# Tests

`tests/` contains the implemented pytest suite for the local application.

## Current Coverage

The suite covers persistence, startup migrations, health checks, Zotero import, PDF extraction and quote matching, embeddings and retrieval, abstract clustering, user-defined axes, duplicate detection, tags and tag suggestions, Crossref-backed metadata enrichment, citation export, paper edits, annotations, summaries, local verification/NLI support, LLM cache behavior, the data-egress gate (`test_egress_gate.py` — the `EgressGated*` wrappers raise and never reach the inner provider when egress is off), token-usage logging (`test_usage_logging.py`), help, frontend assembly (`test_frontend_assembly.py` — every JS chunk is included, placeholders consumed, SRI present, and `callosum-app.html` is in sync), and validation harness behavior.

Tests are organized by resource or feature, with shared fixtures and app helpers in:

- `conftest.py`
- `api_helpers.py`

## Browser smoke (opt-in)

`tests/e2e/test_smoke.py` is a committed Playwright smoke that launches the real app against a seeded
temp database, loads `/` in headless Chromium, and asserts the React app mounts with **zero** console
errors. It is **skipped by default** (so the core suite stays offline and deterministic) and runs only
when `CALLOSUM_RUN_E2E=1` is set — which CI does after installing the browser:

```powershell
pip install -r requirements-dev.txt
python -m playwright install chromium
$env:CALLOSUM_RUN_E2E = "1"; pytest tests/e2e
```

## Run

From the project root:

```powershell
pytest
```

Focused runs are useful during development, for example:

```powershell
pytest tests/test_summaries.py
pytest tests/test_tags.py
pytest tests/test_axes.py
```

## Fixture Policy

Current tests mostly use inline fixtures, temporary files, fake models/clients, and `conftest.py`. Do not commit private libraries, generated local databases, or copyrighted PDFs as fixtures.
