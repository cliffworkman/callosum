# Increment 593 — Release-keyed "what's new" banner + a MECHANICAL drift gate (#43)

The bespoke `LocalAiWhatsNewHint` (`30c_frame.jsx`) was a one-off hardcoded banner with a per-feature
localStorage key — no systematic tie to a release. Per the steering, a CLAUDE.md reminder alone is **not** the
fix: the point is to prevent release↔banner drift **mechanically**.

## The generic mechanism
- **Single source of truth:** `app/frontend/whatsnew.json` — `entries` maps an **exact semantic version** →
  `{headline, actionKind}`, plus `no_banner` (versions that deliberately ship without a banner). `build_frontend`
  (`frontend.py::build_frontend_document`) injects **only** `entries` into the page as `window.CALLOSUM_WHATSNEW`
  (a new `{{WHATSNEW}}` template slot); the gate reads the whole file.
- **Banner** (`04e_whatsnew.jsx`, `WhatsNewBanner`): on mount, compares the running `app_version` (`/health`) to
  `callosum.whatsnew.lastseen` and shows the single **newest entry** with `version > lastSeen` **and**
  `version ≤ app_version` (never announces a future version). Dismiss stamps `lastSeen = app_version`.
- **Semantic-version ordering, not lexical** (`_semverCmp`) — `0.5.10 > 0.5.9`. A malformed/legacy stored
  `lastSeen` **fails safe** (sorts lowest → shows the newest, never throws); a malformed `app_version` → no
  banner.
- **Typed, bounded action** (`actionKind`): `_whatsNewAction` maps `"local-ai"` → the "Set up Local AI" button;
  any unknown/absent kind yields no button. **Behavior is never derived from arbitrary prose in the registry.**
- **Accessibility:** the banner is a `role="region"` with `aria-label="What's new"`.

## Migration (rule #5)
`LocalAiWhatsNewHint` is **removed**; the Local AI announcement is a registry entry keyed at its ship version
(`0.5.5`, `actionKind:"local-ai"`). A **one-time migration** seeds `lastSeen = 0.5.5` when the legacy
`callosum.local-ai-whatsnew.v1` dismissal is present and the new key is unset — so a user who already dismissed
the old hint doesn't see it again.

## The drift GATE (the core of #43)
`tools/check_whatsnew_coverage.py` reads the current desktop-shell version (`tauri.conf.json`) and **fails**
unless that version has **either** an `entries` banner **or** a recorded `no_banner` decline — mirroring the
existing demo/website drift-gate idiom (`--decline --note`, printed on pass, never a silent bypass). Wired into
`ci.yml` beside the website/demo gates. A patch release with nothing to announce records an explicit decline
(no fake copy) — silence is deliberate, not accidental. A CLAUDE.md release-flow note points at it as a reminder,
**not** the guardrail. (0.5.12 is pre-recorded as a `no_banner` decline: it shipped before this mechanism.)

## Verification
- **Pure logic** (standalone node, 10 cases): multi-digit semver ordering; unseen→newest; never-announce-future;
  equal/newer `lastSeen`→hidden; malformed `lastSeen`→newest (fail safe); malformed `app_version`→null; bad
  registry key / non-string headline ignored.
- **Gate** (`tests/test_whatsnew_gate.py`, 7): entry passes, decline passes, neither fails, malformed entry
  fails, `--decline` records + then passes, blank note rejected.
- **Live (Playwright, `CALLOSUM_APP_VERSION=0.5.13`):** fresh state → banner shows with the Local AI headline +
  "Set up Local AI" button + `aria-label`; dismiss → gone, `lastSeen=0.5.13` persisted; reload → stays gone;
  legacy-dismissal migration → seeded `lastSeen=0.5.5`, banner hidden.
- `test_frontend_assembly.py` updated for the new mechanism (the stale `LocalAiWhatsNewHint` assertions replaced);
  ruff + line budget + QA OK.

## Note
The banner only shows on a clean-semver `app_version` — a source-checkout dev build reports `dev-<sha>` and
(correctly) shows nothing; the packaged app reports `0.5.x`.
