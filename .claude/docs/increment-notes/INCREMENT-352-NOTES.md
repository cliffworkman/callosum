# Increment 352 — WIP content checkpoints and exact text identity

## Context

WIP workflow existed, but no tool or user action could name the exact manuscript content it referred to. This
increment adds the deterministic identity layer required before tool-run provenance and findings can be honest.

## Implemented

- Migration `0050` adds `wip_snapshots` and `wip_files.extracted_from_whole_hash`.
- Reusable local extraction now supports ODT and bounded Markdown/plain-text/TeX alongside PDF, DOCX, HTML, and
  JATS/XML.
- Primary-file selection, stage transition, and a manual **Create checkpoint** action capture whole-file and
  normalized extracted-text SHA-256 identities, extractor version, optional honest section hashes, and at most six
  500-character evidence contexts.
- Identical content/reason/detail checkpoints deduplicate. Full manuscript files and full extracted text are never
  copied into SQLite.
- Checkpoint status is derived conservatively: current, potentially stale pending re-extraction, or stale after
  extracted-text change/primary replacement. Current is neutral and does not imply a successful tool check.
- All routes remain local-only/read-only denied and WIP remains outside sync and provider egress.

## Principles gate

Principles 4, 6, and 8 apply. The exact content hash is the deterministic substrate; unknown current extracted text
is shown as potentially stale; and each checkpoint exposes its provider, version, time, reason, and bounded context.
The rejected shortcut was treating mtime or a whole-file checksum as proof that tool-relevant text was unchanged.

## Verification

- `pytest -n auto -q` — **1449 passed, 1 skipped**.
- Frontend build, Ruff, line budget, and QA map pass; route 75 claims all **289/289** API surfaces.
- Headless Chromium at 1440×900 and 375×812: all seven WIP tabs, two checkpoint rows, explicit no-tool-result
  boundary, zero horizontal overflow, and zero console/page errors.

## Next slice

Add general tool runs, WIP run associations, deterministic check findings, and hash-derived run validity on top of
these checkpoints. Absence of findings must never read as a clean manuscript.
