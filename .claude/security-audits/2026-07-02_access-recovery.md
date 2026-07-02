# Security audit — remote-access lockout recovery (`POST /access/recover`), inc 254

**Date:** 2026-07-02
**Author:** Claude (session)
**Trigger:** New API endpoint + new auth/recovery logic (audit-gate criteria #1 and #4) + a new file-write
path (#3) + a net-new feature spanning 3+ files (#5).

## What shipped

A user who turns on **Remote access** (inc 168) but whose browser holds no valid token is locked out of
*every* endpoint except the static shell — including `GET /settings`, the UI that could fix it. The only prior
escapes were editing the settings file or setting `CALLOSUM_DISABLE_REMOTE_ACCESS=1` and restarting — neither
discoverable in-app. This adds an in-app recovery:

- **Backend:** `app/backend/api/access_recovery.py` (in-process code state + local-file write/verify) +
  `app/backend/api/routers/access.py` (`POST /access/recover`). Path added to the middleware's `_RECOVERY_PATHS`
  in `access_control.py`; router registered in `app.py`.
- **Frontend:** a global 401 detector in the `api*` helpers (`00_lib.jsx`) that raises one honest
  `AccessLockOverlay` (`01_recovery.jsx`), wired in `40_app.jsx`; the misleading "start the backend" errbox and
  the stale Settings hint corrected.

**Two phases:** (1) `{}` → mint a 128-bit single-use code, write it to `~/.callosum/recovery-code.txt`
(owner-only), return **only the file path**; (2) `{code}` → constant-time verify → `set_remote_access_enabled(False)`
→ delete the file. The only privileged effect is **turning the gate off** (the safe local-only default).

## Threat review

| Concern | Assessment |
|---|---|
| **The core threat: a remote/tunnel caller disabling the gate** | The endpoint is reachable without a token (it must be — the user is locked out), so authorization rests on **local-machine possession**, not the request path. Phase 2 requires a code the server writes to a local file. A tunnel/remote caller can POST but **cannot read the local file** → cannot obtain the code. Brute force is defeated by 128-bit entropy (`secrets.token_urlsafe(16)`) + single-use + a 10-min TTL + rate limiting. Under the recommended cloudflared allowlist (`/papers`, `/papers/export`, `/citations/*`) the path isn't even forwarded — defense in depth. |
| **Directional safety** | The endpoint can only **disable** remote access — never enable it, never mint/rotate/reveal a token, never read library data. The worst a successful caller achieves is returning the app to its default local-only posture. No escalation path. |
| **Secret handling** | The recovery code is never logged and **never returned over the wire** — only its file path is (`RecoverResponse.code_path`). It lives in-process (`_pending`) + the visible local file, never in the settings store. The access token is never read or echoed by this path. Verified: `test_recover_start_returns_only_the_path_never_the_code`, `test_recover_never_reveals_the_token`. |
| **Input validation (rule #4)** | `RecoverRequest.code` is capped at `RECOVERY_CODE_MAX_LEN` (128) via a pydantic `Field(max_length=...)`, so an oversized body is rejected at the boundary **before** any comparison (`test_recover_oversized_code_is_rejected_at_the_boundary` → 422). Comparison is constant-time (`secrets.compare_digest`). |
| **File-path safety** | The write target is a fixed name beside the settings file (`settings_path().parent / "recovery-code.txt"`) — **no user input** contributes to the path, so no traversal surface. `CALLOSUM_SETTINGS_PATH` keeps it hermetic in tests and out of the repo/synced folder in production. Written owner-only (`S_IRUSR|S_IWUSR`; meaningful on POSIX, a no-op on Windows like the settings file). |
| **Resource exhaustion / DoS** | The path is rate-limited by the existing sliding-window limiter under a dedicated `"recover"` key (it was deliberately kept OUT of `_EXEMPT_PATHS`, which bypass the limiter). `test_recover_is_rate_limited` confirms 429 after the budget. Each mint overwrites the single in-process code + rewrites one small file — bounded. |
| **SQL injection (rule #3)** | N/A — this path touches no SQL. |
| **SSRF / external calls** | N/A — no outbound requests; no egress. The Gemini library-text egress gate (invariant #3) is a separate channel, untouched. |
| **Supply chain** | No new dependency (`secrets`, `stat`, `time`, `pathlib` are stdlib; FastAPI/pydantic already present). |
| **Read-only mode interaction** | On a `CALLOSUM_READ_ONLY=1` instance the middleware 403s the POST before the recovery branch (recovery targets the read-write desktop instance, not the read-only mobile reader — documented, acceptable). |

## Negative-path checks (concrete results)

Run: `python -m pytest tests/test_access_recovery.py tests/test_access_control.py -q` → **19 passed**.

- Wrong code → `status: "invalid"`, gate **stays on**, `/papers` still 401 (`test_recover_wrong_code_leaves_the_gate_on`).
- Expired code (past TTL) → rejected + file cleaned (`test_verify_rejects_expired_code`).
- Replay of a used code → rejected; single-use (`test_verify_is_single_use_and_consumes_the_file`).
- Stale code after a re-mint → rejected (`test_start_overwrites_the_previous_code`).
- Oversized code → 422 at the boundary.
- Rate limit → 429 after the budget.
- Token never present in any response body; only the file path is returned.
- Gate-exempt reachability while locked (no `Authorization` header) confirmed by the happy-path tests issuing the
  POST with no token.

## Residual risk

- A **local** attacker who can already read `~/.callosum/` can read the code — but such an attacker can already
  read the settings file / token / library, so this grants nothing new (and can only *disable* remote access).
- If a deployment wrongly forwards `/access/recover` through the tunnel AND an attacker can otherwise read the
  local file, they could disable the gate — but reading the local file already implies local access. The allowlist
  keeps the path off the tunnel regardless.

## Verdict

**Security Audit: PASS.** The endpoint is disable-only, discloses nothing, authorizes on local-file possession
(not the request path), validates + caps + constant-time-compares its one input, is rate-limited, adds no
dependency, and is covered by 11 tests including every negative path.
