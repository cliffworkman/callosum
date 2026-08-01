# Increment 437 — quiet routine scans in Status

## Outcome

Routine Library scans and WIP folder scans no longer appear in the Status popover, either while running or as finished
receipts. Their source surfaces continue to report state; the Library scan modal retains its determinate inline bar.

## Architecture

`STATUS_HIDDEN_STORES` is the centralized, explicit noise-exception seam. Status still discovers both stores so lazy
expiry and clear/dismiss behavior remain structurally safe, but `list_status_jobs` prunes and then omits them before
serialization. Their label, navigation, and compute mappings were removed so structural tests distinguish visible
stores from intentionally hidden ones.

## Principles and experience pass

This refines the Increment 436 visibility invariant around the **Multi-tasker** experience: global visibility stops
helping when frequent ambient maintenance receipts displace work the user deliberately wants to track. The aligned
choice is a narrow, named exception with inline feedback preserved; the risky shortcut would be scattered frontend
filtering that allows scans to reappear through another client or leaves backend receipts accumulating silently.

## Security and privacy

No endpoint, egress, model invocation, persistence, file operation, or dependency changes. The API exposes less status
metadata than before. Hidden stores still participate in existing expiry and clear-finished paths.

## Tests

A hermetic backend regression starts both scan stores plus a visible synthesis job and proves that Status returns only
the synthesis row. Structural coverage pins both hidden names as real application stores, excludes them from visible
destination/compute maps, and continues to require every other application store to be covered.

Verification completed after a restart interrupted the first full-suite attempt:

- `pytest tests/test_status.py -q` — **17 passed**.
- `pytest -n auto -q` — **1787 passed, 1 skipped**.
- `ruff format --check app/backend/api/routers/status.py tests/test_status.py` and targeted `ruff check` — clean.
- `python tools/check_line_budget.py` — all **459** application-source files within the 600-line cap.
- `python tools/qa/build_surface_map.py check --strict` — **352/352 API** and **1545/1545 frontend** surfaces covered.

## Rollback

Remove the scan names from `STATUS_HIDDEN_STORES` and restore their entries in `JOB_LABELS`, `JOB_NAV_DEFAULTS`, and
`JOB_COMPUTE_KINDS`. No data or schema rollback is required.
