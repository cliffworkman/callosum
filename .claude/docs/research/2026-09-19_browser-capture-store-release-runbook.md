# Browser capture (#61) — store-release runbook

**Status (2026-09-19): a plan, not a record of anything done.** Nothing here has been submitted to any store, no
production extension ID exists, and `production_extension_ids` is `[]`. This runbook exists so the path from the proven
branch to a store-installed extension is written down once, with the unknowns left visibly open.

Contribution lineage for the underlying feature and for the decisions below is recorded chronologically on #61 and #98
per `.claude/CREDIT-THE-LINEAGE.md`. Store policy is kept separate from Callosum architecture: an external review
recommendation never silently becomes a product requirement.

> **Scope correction (2026-09-20) — macOS is the target platform.** The first concrete user of browser capture is on **macOS
> and uses Google Chrome** (product fact supplied by Cliff; the repository records neither). A Windows-only connector proves the
> architecture while failing the intended utility target, so **macOS (Chrome) is now a hard Phase-1 criterion**, Edge on
> macOS is best-effort, and **Linux is not a supported browser-capture platform** (the Linux shell must still build, with no
> connector). Everything below written before this date describes Windows/Edge because that was the implementation sequence,
> not the release scope; it is left as written and qualified where it would now mislead. Windows Chrome/Edge stay supported.

## 0. What is already true

- Real-Edge acceptance (R1–R4, clean build, 2026-09-19) is proven for the **development** identity only.
- One shared native-host manifest is registered under both `HKCU\Software\Google\Chrome\NativeMessagingHosts\` and
  `HKCU\Software\Microsoft\Edge\NativeMessagingHosts\`; its `allowed_origins` comes from `connector/identity.json`
  and nothing else. Microsoft's native-messaging documentation requires both stores' IDs in `allowed_origins` when an
  extension is on both stores (only the manifest at the first registry location found is read). **Keep this structure;
  do not split it per browser without new evidence.**
- **macOS registration (2026-09-20; CI/hardware status below).** macOS has no installer hook, so the desktop shell registers the
  same identity at **every launch** (`src-tauri/src/connector_registration.rs`): it writes
  `org.callosum.connector.json` into Chrome Stable's per-user `NativeMessagingHosts` directory (always) and Edge's (only if
  Edge's user-data directory exists), with the host name and `allowed_origins` taken from `connector/identity.json` and an
  absolute path to the connector, which ships as an executable **sidecar** (`bundle.externalBin`), not a resource. It refuses to
  persist a path under `/AppTranslocation/` or `/Volumes/`. **Uninstall caveat:** dragging the app to the Trash runs no code, so
  the manifest is left pointing at a path that no longer exists; the browser then fails closed (host unavailable), and any later
  Callosum launch repairs it. Document this in the listing and reviewer instructions; do not present it as a clean uninstall.
- **Browser/store identity ≠ Callosum pairing/session identity.** They are independent layers: the store ID decides who may
  *launch the host*; the per-install pairing secret and session token bound what a launched host can do. The backend never
  sees an extension ID.
- The production extension manifest in the repository is **keyless** and must stay keyless (`tests/test_connector_identity.py`,
  `build_extension_package.py`).

## 1. Hard prerequisites before any production browser-capture release

These are not optional. **Cliff decides when and how**; none is done by this runbook.

1. **Integration.** The connector host, extension, capture backend and installer hooks exist only on the
   `browser-capture-research` branch (nothing in `main` or `v0.5.15`). They must be integrated into a release branch where
   the workflows can actually exercise them. *(Update 2026-09-20: draft PR #103 carries the branch to `main`; it is unmerged and
   its first GitHub run found two blockers, remediated on the branch — see the PR. Nothing is release-ready.)*
2. **CI proof.** `.github/workflows/ci.yml` (`connector-and-extension`) and `desktop-shell-windows.yml` (connector + src-tauri
   `cargo test`, and the registration check against `identity.json`) were *authored* locally. They are **not CI-proven** until
   GitHub runs them after an authorized push. Do not record CI as passed before that. *(Update 2026-09-20: PR #103's first run
   executed them; Windows passed, Linux and macOS shell builds failed on the connector resource, and CodeQL raised six alerts.
   Treat CI as proven only from the fresh runs on the remediation head, never from the failed first runs.)*
3. **A genuine real-Chrome capture with the development identity** (§5). Edge has R1–R4; Chrome has none.
   **On macOS this is a separate, harder gate (§5b)** and is the one that decides whether browser capture is useful to its
   first user; a green GitHub macOS runner does not satisfy it.
4. **Privacy/listing workstream** (§6) — needs Cliff's review; not code.
5. **The lint gates that CI enforces currently fail on this branch** (found 2026-09-19 by running them locally; they predate the
   store-readiness pass, and the repo's pre-commit hooks were not running because `core.hooksPath` points at a directory that
   does not exist): `tools/check_line_budget.py` reports four application files over the 600-line cap
   (`app/backend/capture/provisional.py` 1090, `app/backend/api/app.py` 628, `app/backend/persistence/schema.py` 607,
   `app/frontend/js/10_pdf_layer.jsx` 602 — all within budget on `main` except the new `provisional.py`); and `ruff check .` /
   `ruff format --check .` flag seven tracked `.claude/**` Python scripts (15 findings, 5 files needing format) that exist
   only on this branch. Disposition (Cliff, 2026-09-19): resolve by behavior-preserving extraction along responsibility
   boundaries and mechanical Ruff compliance — no blanket exclusions — in commits separate from this runbook; repair the hook
   configuration only after the debt is gone. Until GitHub itself runs the workflows, none of this is CI-proven.

## 2. Identity bootstrap (external store actions — each needs Cliff's explicit go-ahead)

Build the one shared package first: `python app/desktop-shell/packaging/build_extension_package.py` (keyless, reproducible,
prints a SHA-256). Upload **that** file to both stores; never a dev-staged copy.

```text
Chrome Web Store
  register developer account
  → Add new item → upload the package (do NOT submit for review)
  → Package tab → View public key            (first-party: developer.chrome.com/docs/extensions/reference/manifest/key)
  → derive/confirm the 32-char extension ID  (the same derivation tests/test_connector_identity.py checks for the dev key)
  → record the ID and public key OUTSIDE the repository manifest

Microsoft Edge Add-ons (Partner Center)
  register developer account
  → Create new extension → upload the SAME package
  → inspect whether the FINAL Microsoft Catalog / CRX extension ID is already assigned (Extension overview)

    IF the final production ID is available:
        proceed with the symmetric two-ID bootstrap
    ELSE:
        STOP and design the smallest supported bootstrap sequence from actual Partner Center behavior.
        Do NOT substitute the sideloaded Edge ID: Microsoft states the published ID "might differ from the ID that's
        used while sideloading."
```

**Established vs. unknown (as of 2026-09-19):** for Chrome, current first-party documentation establishes that the item's
public key (and so its ID) is available from a *draft* before publication. For Edge, the timing of the final production ID is
**not established from first-party text** and must be observed in Partner Center. Community reports (Microsoft Q&A, 2023–24,
non-authoritative) say Edge rejects a `key` on first upload and can assign an ID different from Chrome's even when a key is
reused — so plan for **two different IDs**, and never rely on ID pinning across stores.

Use the 32-character extension (CRX) ID, not a Partner Center Store/Product ID. `generate_connector_nsh.py` rejects
anything that is not 32 lowercase letters `a`–`p`.

## 3. Populating and releasing

1. Update `connector/identity.json` (`production_extension_ids`, both stores) **in the same reviewed change** as
   `PINNED_PRODUCTION_EXTENSION_IDS` in `tests/test_connector_identity.py`. The generator, the Rust binary (compiled in via
   `include_str!`) and the CI registration check all read this one file; no other place holds an ID.
2. Build and release the **app** first. Existing installs only learn the IDs through an app update (the installer rewrites the
   manifest on every install/update; update-mode uninstall preserves the registration).
3. Pre-review production-path test (Chrome): load an *unpacked copy* of the extension with the Chrome Web Store **public key**
   in a **temporary staged manifest only** (never the repository manifest, never committed); it then has the production
   ID and exercises the real production host name and allowlist. Edge has no equivalent until a certified/Hidden build exists.
4. Submit both stores (prefer Unlisted on Chrome / Hidden on Edge first); publish the extension only after the app release
   carrying the IDs is live. Extension updates keep their ID; a **new** store item or an ID change requires a new app release.

**Core production matrix:** Chrome + the Chrome Web Store build; Edge + the Edge Add-ons build.
**Post-core compatibility evidence (not a Phase-1 blocker unless Cliff defines it as supported):** Edge running the
Chrome-Web-Store build (Chrome ID, shared manifest).

## 4. Release-gate policy (D1 — settled 2026-09-19; NOT yet implemented)

The policy is decided; the mechanism is deliberately not wired yet. When it is implemented, the authoritative release state
lives in `connector/identity.json` — machine-meaningful identity/release state only; chronology and explanation live in docs
like this one. No second independent source of truth.

```text
released field absent, or false     browser capture is not yet a publicly released capability
                                    (empty production identity is allowed: development, test and ordinary builds)
released field true                 BOTH the Chrome and the Edge production IDs are required, and every ID must pass the
                                    existing canonical validation (connector_identity.validate_identity)
```

**Ratchet (tag-triggered public releases):** once any earlier public release tag has `released == true`, later public releases may
not silently return to false, and production IDs present in the previous browser-capture-capable release may not disappear. A
strict-superset requirement is acceptable for the first implementation. Git history (the previous release tag's `identity.json`)
is the ratchet — not a second file. Legitimate future store-ID rotation gets an explicit, reviewed migration path rather than a
weakened ratchet; store-ID rotation is not solved preemptively.

`PINNED_PRODUCTION_EXTENSION_IDS` in `tests/test_connector_identity.py` is an **interim** deliberate-change tripwire. It is to be
*replaced* by this release-aware mechanism when it is implemented, not kept alongside it as a second policy authority.

The check belongs in the tag-triggered release workflow. It is not wired in the Bucket-A pass; wiring needs separate authorization.

## 5. Manual real-Chrome click-through with the DEVELOPMENT identity (a hard pre-store gate)

Purpose: one genuine Chrome capture through the real packaged app, native messaging, pairing, capture and promotion.
Chrome ≥137 refuses `--load-extension`, so the extension is loaded by hand. Uses only the existing dev mechanism (dev host name
`org.callosum.connector.dev`, dev extension ID, `CALLOSUM_CONNECTOR_ALLOW_DEV_BUILD`). **No production key anywhere.**

1. **Prepare** (once): `cargo build --release --manifest-path app/desktop-shell/connector-host/Cargo.toml`;
   `python app/desktop-shell/extension/dev/build_dev_manifest.py` → `.local/dev-extension` (dev key + dev host name; a staged
   copy that must never be uploaded).
2. **Isolate** exactly as the acceptance harness does: park the real `%APPDATA%\com.callosum.desktop` and record the
   `callosum.sqlite` SHA-256; disposable Library via `CALLOSUM_LIBRARY_DIR_OVERRIDE` outside Dropbox; disposable settings via
   `CALLOSUM_SETTINGS_PATH` so Word-HTTPS cannot start (#99). Because a browser-launched host cannot see that variable (#99), seed
   the disposable settings directory with a read-only copy of the real `capture-pairing.json` and delete it afterwards.
3. **Start** the packaged `callosum-shell.exe` with that environment; wait for `/health`; check `GET /word-https/status` reports
   `enabled: false`.
4. **Register** the dev connector: `python -c "from tools.run_dev import _register_dev_connector as r; r()"` (writes the dev host
   under both browsers' HKCU keys; its manifest allows only the dev extension ID).
5. **Launch Chrome** with a throwaway profile:
   `chrome.exe --user-data-dir=%TEMP%\callosum-chrome-dev-profile --no-first-run --no-default-browser-check <a real PDF URL>`
   (on this machine `C:\Program Files (x86)\Google\Chrome\Application\chrome.exe`). At `chrome://extensions`: Developer mode →
   **Load unpacked** → `.local/dev-extension`. **Checkpoint 1:** the displayed ID equals `dev_extension_id` in `identity.json`.
   Record `chrome://version`.
6. **Positive capture:** click the extension's toolbar icon on the PDF tab. **Checkpoint 2:** `connector-host.log` (in the
   disposable app-data dir) gains `resolved runtime_state=available`; `backend.log` shows `/capture/session`, `/capture/item` and
   `/capture/item/{id}/pdf` all 200; `GET /library/import-queue` lists one item. Then complete review/confirm over HTTP as in
   `run_acceptance_import_queue_review.py` R1. **Pass:** `promoted`, one canonical PDF, queue empty.
7. **Negative — a different extension identity:** copy `.local/dev-extension`, delete **only** the `key` field from the copy's
   `manifest.json` (its host-name constant stays patched to the dev host, so the registered dev host is still the one
   addressed), load that copy, and click. Its ID is path-derived, hence not in `allowed_origins`. **Expected:** the extension
   reports its host-unavailable state, and `connector-host.log` gains **no** new line for that click (the browser refused to
   launch the host).
8. **Negative — no host registered:** run `_clear_dev_connector()` and click again. **Expected:** host-unavailable.
9. **Clean up:** `_clear_dev_connector()`; close Chrome; delete the temp profile and the seeded pairing copy; stop the app; restore
   app-data; **verify the real DB SHA-256 equals the baseline** and the real `~/.callosum` tree is unchanged.

Evidence to keep: Chrome version, screenshots of the loaded extension ID and the capture result, the connector/backend log
excerpts above, the promoted result, the hash verification. A small orchestrating script can be added on request; none is
included in this pass.

## 5b. Real-macOS Chrome acceptance (a hard gate — the first user's platform)

**Not executed in the remediation pass that introduced it; designed here so it can be run once, cleanly, on real hardware.**
GitHub's macOS runners prove packaging and build only. Whether a browser-launched connector works on a real Mac is decided by the
choices below that depend on the actual bundle layout, browser manifest lookup, host argv/env, Gatekeeper behavior and process
identity. Each is a **seam**: the code makes the conservative choice, and the hardware — not a guess — adjudicates it. Record what
is observed; do not code around an unobserved failure.

**Hardware and evidence taxonomy (record all, every run):** Mac model and year, `uname -m`, `sw_vers` (version and build), whether
OpenCore Legacy Patcher (OCLP) is in use, `chrome://version`, and the Callosum build's architecture (`lipo -archs` on the
connector). A late-2015 iMac is **Intel**; a run on it is *real Intel-macOS product-boundary evidence* and is **not** proof of Apple
Silicon behavior. GitHub's arm64 runner is *packaging/build evidence only*. **Bella's Mac architecture is not yet known**; do not
claim her exact environment is proven until it is (ask; both arm64 and x64 jobs are built and asserted in CI meanwhile).

**Seams to observe (write down the answer for each):**
- **S1 — sidecar location.** Where Tauri placed the `externalBin` connector inside the `.app` (assumed `Contents/MacOS/`, asserted by
  CI from the observed layout); the registered manifest's `path` must equal it.
- **S2 — manifest lookup for an explicit profile.** Chrome is assumed to read `<user-data-dir>/NativeMessagingHosts/` for a
  `--user-data-dir` profile. Verify by whether the host launches; if it does not, record which directory Chrome does read.
- **S3 — host argv and environment.** `argv[1]` is `chrome-extension://<id>/`; and whether `CALLOSUM_SETTINGS_PATH` reaches a
  browser-launched host on macOS (#99). Record **present/absent only, never the value**. Do not assume the Windows finding either way.
- **S4 — Gatekeeper/quarantine.** Whether a Chrome-launched sidecar inside a quarantined, ad-hoc-signed app is blocked or prompts.
  Only if it is, decide on quarantine handling from that evidence.
- **S5 — process identity.** Whether "Callosum is starting" detection (`pgrep -x callosum-shell`) is needed; not implemented until observed.

**Procedure (dev identity in a throwaway profile; the production check is step 9):**
1. **Baseline** before anything runs: SHA-256 of the real `callosum.sqlite` under
   `~/Library/Application Support/com.callosum.desktop/`; a file listing plus hashes of `~/.callosum`; the SHA-256 (hash only) of the
   real `~/.callosum/capture-pairing.json`.
2. **Install** the macOS build for this Mac's architecture (DMG from the CI artifact on the tested head); first launch per
   `FIRST-LAUNCH-NOTE.md` (right-click → Open). Record any Gatekeeper prompt (S4).
3. **Disposable backend:** run the app binary directly so its environment is inherited, with `CALLOSUM_LIBRARY_DIR_OVERRIDE` set to a
   disposable Library **outside Dropbox/iCloud** and `CALLOSUM_SETTINGS_PATH` set to a disposable directory. Because the variable
   may not reach a browser-launched host (S3), **seed that directory with a read-only, byte-identical copy of the real
   `capture-pairing.json`** and delete it afterwards. Confirm `/health` reports role `ui` and `/word-https/status` is
   `enabled: false`.
4. **Register the dev host into the throwaway profile:** with `dev_connector_launcher` and `callosum_connector` built, call
   `tools.run_dev._register_dev_connector(manifest_dirs=[<profile>/NativeMessagingHosts])`. It writes only
   `org.callosum.connector.dev.json` (allows only the dev extension ID).
5. **Launch Chrome** (`/Applications/Google Chrome.app/Contents/MacOS/Google Chrome --user-data-dir=<throwaway> --no-first-run
   --no-default-browser-check <a real PDF URL>`), Developer mode → **Load unpacked** → the dev extension.
   **Checkpoint 1:** the ID shown equals `dev_extension_id`.
6. **Positive capture** exactly as §5 step 6: `connector-host.log` shows `resolved runtime_state=available`, the three `/capture/*`
   calls return 200, the item reaches the Import Queue, review promotes it (one attachment, chunks and embeddings present).
7. **Negative — wrong identity:** a copy of the extension with only the `key` removed (different ID). **Expected:** host-unavailable
   and no new connector-host log line.
8. **Negative — manifest absent:** clear the dev registration and click. **Expected:** host-unavailable, nothing reachable.
9. **Production registration (separate check, same Mac):** launch the installed app from `/Applications` and confirm
   `~/Library/Application Support/Google/Chrome/NativeMessagingHosts/org.callosum.connector.json` appears with the exact host
   name, `allowed_origins` equal to `identity.json`, and an absolute path to the installed connector containing no
   `AppTranslocation`. Move the app, relaunch, and confirm the manifest is rewritten to the new path; then move it to the Trash and
   confirm the browser reports host-unavailable (stale manifest fails closed). Remove the test manifest afterwards.
10. **Restore and prove it:** delete the seeded pairing copy, the throwaway profile and the dev manifests; **the real
    `callosum.sqlite` hash and the `~/.callosum` listing/hashes must equal the step-1 baseline.**

**Pass:** steps 6–8 as stated, step 9 as stated, step 10 byte-identical, and every seam S1–S5 answered in writing. Evidence (versions,
hardware taxonomy, screenshots of the loaded ID and capture result, log excerpts, hashes) is summarized on #61.

## 6. Privacy / listing workstream (needs Cliff's review — not code)

The extension deliberately reads the active page's metadata (or a PDF the user has opened) **on a click** and hands it to the
user's local Callosum. Both stores require accurate disclosure of that. Nothing below is drafted here; each is an explicit
pre-submission deliverable for Cliff to author or approve:

- privacy policy (public URL; the existing site is the natural home — decision D3) and store data-usage disclosures;
- single-purpose statement; a justification for each permission (`nativeMessaging`, `activeTab`, `scripting`, and the loopback
  `host_permissions`); the "no remote code" answer;
- reviewer/certification instructions and the **desktop-app dependency** explanation (the extension does nothing without the
  Callosum desktop app; registration is implemented for Windows (Chrome, Edge) and macOS (Chrome; Edge best-effort) — Linux is not
  supported; see §0 for the macOS launch-time registration and its stale-manifest-after-Trash behavior); the installer must be
  publicly downloadable to reviewers;
- store assets: Chrome — 128×128 icon (present), a 440×280 small promo image, at least one 1280×800 or 640×400 screenshot;
  Edge — logo (≥128, 300×300 recommended) and a description of at least 250 characters. Reconfirm dimensions in each dashboard.

Chrome Web Store policy updated 2026-07-01 (enforcement from 2026-08-01): user-data use must be strictly necessary to the
disclosed single purpose, with proactive disclosure of practice changes.

## Sources (first-party unless marked; accessed 2026-09-19)

- developer.chrome.com/docs/extensions/reference/manifest/key
- developer.chrome.com/docs/extensions/develop/concepts/native-messaging
- learn.microsoft.com/microsoft-edge/extensions/developer-guide/native-messaging (updated 2026-09-02)
- learn.microsoft.com/microsoft-edge/extensions/publish/publish-extension (ms.date 2026-05-05)
- learn.microsoft.com/microsoft-edge/extensions/developer-guide/port-chrome-extension (updated 2026-08-12)
- developer.chrome.com/docs/webstore/{publish,prepare,register,images,review-process,program-policies/policies} and
  developer.chrome.com/blog/cws-policy-updates-2026
- Non-authoritative, context only: Microsoft Q&A "keep the same extension ID on Chrome and Edge" (2023–24).
