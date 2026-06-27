# Security audit — OS-keychain key storage (optional, file fallback) (inc 152)

**Date:** 2026-06-27
**Trigger (audit gate):** a new secret-storage path (the OS keychain) for the BYOK provider keys.

## What it does

Per-provider API keys can be stored in the **OS keychain** (Windows Credential Manager / macOS Keychain / Linux
Secret Service) via the optional `keyring` library, instead of the gitignored `~/.callosum/app-settings.json` file.
`keyring` is **optional**: if it isn't installed or has no usable backend, everything falls back to the file store
(the inc-146 behavior). Non-secret settings (provider, base_url, model, egress/help flags) always stay in the file.

## Threat review

- **Stronger at-rest storage, opt-in.** When `keyring` + a real backend are present, keys live in the OS vault
  (encrypted at rest, OS-access-controlled) rather than a plaintext file. This is strictly an improvement; the file
  fallback is the already-audited inc-146 posture.
- **No key ever lost; no plaintext lingering.** `get_provider_key` reads the keychain first, then the file — so a
  key written before keyring was installed is still found. `set_provider_key`, when the keychain is available,
  writes the key to the vault **and removes any plaintext copy from the file** (migration on save). Clearing a key
  deletes it from both.
- **Fail-closed to the file, never crash.** Every keyring call is wrapped in `try/except`; any backend error →
  graceful fall-through to the file. A missing/`fail` backend → treated as unavailable.
- **Secret handling unchanged.** Keys are still **write-only over the wire** — `GET /settings` reports only which
  providers have a key (`provider_keys_set`) + the active source, never a value. Keys are never logged; provider
  errors stay redacted (inc 149). The keychain service name is the constant `"callosum"`; usernames are the
  constant per-provider field names — no request data reaches keyring.
- **Supply chain.** `keyring` is **optional**, documented (a commented entry in `requirements.txt` + the help
  corpus). It is NOT a hard dependency (the no-new-hard-dep ethos holds); the app + tests work without it.
- **No new endpoint, no migration, no new external fetch.** (`PUT/GET /settings` unchanged in shape; a
  `keychain` status field is additive.)

## Negative-path checks

- keyring unavailable (the default in dev/CI) → keys use the file store; all existing tests pass unchanged. ✅
- keyring available (mocked in-memory) → `set_provider_key` writes the vault + drops the file copy; `get_provider_key`
  reads the vault; `GET /settings` reports the key as set. ✅ (test)
- a pre-keychain file key is still readable once keyring is available (file fallback), and migrates to the vault on
  next save. ✅ (test)
- a keyring backend error → falls back to the file, no crash. ✅ (test)
- `GET /settings` never returns a key value (keychain or file). ✅ (inc-146 secrecy test still holds)

## Result

**Security Audit: PASS** — an optional, strictly-stronger at-rest store with a safe fallback; keys stay write-only;
no key loss; no new hard dependency.
