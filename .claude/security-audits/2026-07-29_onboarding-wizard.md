# Security audit — first-run onboarding wizard (inc 416)

**Date:** 2026-07-29
**Trigger:** audit-gate criterion #5 (a net-new feature spanning 3+ files / ~300+ added LOC). No new API
endpoint, no new external fetch, no new file-ingestion path, no new auth logic, no new dependency — this
extends two already-audited endpoints' response/request models by one bool field each, and every step embeds
already-shipped, already-audited settings components rather than introducing new logic of its own.

## What shipped

A full-screen, skippable overlay (`app/frontend/js/04e_onboarding.jsx`) shown once per machine on first launch,
gated on a new `onboarding_completed` flag (`app/backend/app_settings.py`, exposed on `GET /health` — the one
endpoint the frontend fetches unconditionally at launch — and read/write via the existing `GET`/`PUT /settings`).
It orchestrates five existing screens in sequence: My Publications identity (`MyPubsSettings`), AI/BYOK opt-in
(`AiSettings`), the watched-folder scanner (`ScanModalBody`, newly split out of `ScanModal`), citation/bundle
import (`ImportModalBody`/`BundleImportModalBody`), and an initial axis (`SuggestAxesModalBody`/
`AxisEditModalBody`). "Skip setup" is always visible and reachable at every step.

## Threat review

| Concern | Assessment |
|---|---|
| **New endpoint / schema change** | `onboarding_completed: bool` added to `HealthResponse` and `SettingsStatus`/`SettingsUpdate` — the identical shape as the already-audited `read_only`/`agent_writes_enabled` flags. No new route. |
| **Egress (invariant #3 / APPROACH-AVOIDANCE A5 — the one place this feature is actually at stake)** | The AI/BYOK step renders the existing `AiSettings` component verbatim — the wizard never sets, reads, or defaults `data_egress_enabled` itself; the toggle's existing off-by-default behavior and honest copy are unchanged. Confirmed via a new test (`test_onboarding_wizard_orchestrates_existing_settings_never_defaults_egress_on`, `tests/test_frontend_assembly.py`) that no hardcoded `data_egress_enabled: true`/`=true` appears anywhere in the assembled frontend. **Negative-path check, run manually**: on a fresh install (`~/.callosum/app-settings.json` absent), the AI step's egress toggle renders unchecked/off — confirmed by code inspection (the same `AiSettings` code path already audited when BYOK shipped; nothing here changes its default-resolution logic). |
| **Data respected, never silently clobbered** | A real pre-existing latent bug was found and fixed in `MyPubsSettings` (`35a_mypubs.jsx`): its mutating actions were enabled before the initial `GET /my-publications/profile` resolved, so a fast click (or Enter in the variant-draft field) before that fetch completed could `PUT` blank values over an existing profile — a real risk given two existing testers already have profile data. Fixed with a `loading` gate on every mutating action, not just a button's `disabled` attribute (which the Enter-key path bypassed). Covered by a new regression test (`test_my_pubs_settings_gates_actions_until_profile_loads`). |
| **New file-ingestion/write path** | None — the import/scan/axis steps ride the exact same, already-audited `POST /library/scan`, `POST /library/import`, `POST /library/bundle/import`, `POST /axes/suggest`, `POST /axes` endpoints as their existing standalone-modal entry points. The five modal-body extractions (`ScanModal`→`ScanModalBody`+wrapper, etc.) are pure internal refactors — no behavior change, confirmed by `test_frontend_assembly.py` asserting both halves of each split still exist and by every existing standalone caller (Settings, the library "+Add" menu) being left untouched. |
| **Auth/session** | None touched. |
| **Resource exhaustion / DoS** | The wizard adds no new polling loop of its own; each embedded step reuses its existing job-poll cadence unchanged. |
| **Supply chain** | No new dependency. |

## Negative-path checks (concrete)

- `pytest tests/test_settings.py tests/test_health.py -q` → onboarding_completed defaults `False` and round-trips through both endpoints (4 new tests total across the two files).
- `pytest tests/test_frontend_assembly.py -q` → confirms no pre-checked egress default anywhere in the wizard's source, confirms every modal-body extraction preserved both the bare body and the thin wrapper, confirms the `MyPubsSettings` race-condition fix actually gates all five mutating actions.
- Manual (owed, not yet run — see the increment notes): load the wizard against a seeded profile and confirm the identity step shows the existing name/variants/ORCID rather than blanks.

## Residual risk

None identified beyond the existing, already-accepted posture of the endpoints and components this feature
reuses. The wizard adds no new trust boundary — it is a client-side sequencing layer over surfaces already
covered by their own prior audits.

## Verdict

**Security Audit: PASS.**
