# Security Audit — Pre-GitHub full-codebase sweep (2026-06-20)

**Trigger:** Release-readiness arc Phase 5 — callosum is going **public (AGPL-3.0) on GitHub**. This is a
consolidated whole-codebase review under the **new threat model of source exposure** (the code, not the
data, becomes public; the app itself stays local-first and single-user). Supersedes the per-feature audits
for the purpose of the initial publication; those remain the record for their increments.

## Threat model delta (what changes when the repo goes public)
- **Source + history become world-readable.** The dominant new risk is **secret leakage** into the tree or
  git history (API keys, DB paths, the user's library). The app's runtime threat model is unchanged
  (local, `127.0.0.1`, single user, offline after import).
- No new network-listening surface is added by publication. Auth + rate-limiting are still **not present**
  and remain **pre-requisites before any hosted/multi-user deployment** (already tracked in CLAUDE.md).

## Findings

### 1. Secrets in the tree — PASS (with Phase-6/7 actions)
- Grep sweep for hardcoded key/token/password patterns (`AIza…`, `sk-…`, `api_key=…literal`, etc.) across
  `app/ integrations/ tools/ tests/ alembic/ *.toml *.txt *.ini` → **no hardcoded secrets**.
- `GOOGLE_API_KEY` and `CALLOSUM_DB_URL` are read from the environment only (rule #2). Confirmed no literal
  assignment in `.py`.
- **Action (Phase 6/7, MUST precede first commit):** the user's real Gemini keys live in
  `.claude/GEMINI_API_KEYS.md` — relocate to a gitignored `.env` and ensure `.gitignore` excludes **`.env`,
  `.claude/GEMINI_API_KEYS.md`, `.claude/backups/`, `.claude/deprecated/`, `.claude/plans/`, `.local/`,
  `library/`, `*.sqlite|*.db|*.pdf`, `__pycache__/`, `.ruff_cache/`**. A `git` secret-scan of the working
  tree (and any local history) is a Phase-7 gate before push.

### 2. Data egress gate (invariant #3) — PASS
- Enforced provider-neutrally at the DI seam (`app/backend/llm/egress.py`, inc 58). Phase 4 added
  **direct unit tests** (`tests/test_egress_gate.py`) proving each `EgressGated*` wrapper raises **and never
  invokes the inner provider** when egress is off — closing the "implied by the API tests only" gap.
- Off by default (`CALLOSUM_ALLOW_DATA_EGRESS`); help assistant on a **separate** toggle
  (`CALLOSUM_HELP_ASSISTANT_ENABLED`) that sends only public help docs (never library text).

### 3. SQL injection — PASS
- SQLAlchemy Core **bound parameters** throughout; no string-interpolated SQL. Sort/order keys come from
  an **allowlist** mapping (inc 69), never request text (rule #3). Table/column identifiers are constants.

### 4. Untrusted-input validation — PASS
- PDFs validated/decoded at ingest (`pdf_processing/ingest.py`); external API responses (Crossref/Gemini)
  are shape-validated and fail closed; `httpx` calls set timeouts. Local threat model is resource-exhaustion
  + untrusted-content handling, addressed at the boundary (rule #4).

### 5. CORS / network posture — PASS
- App binds `127.0.0.1`; CORS `allow_origin_regex` limited to `localhost`/`127.0.0.1`, **GET-only**, no
  credentials (`app/backend/api/app.py`). No change this arc.

### 6. File-path safety — PASS
- Attachment paths resolved from stored records; no filesystem path is built from unsanitized request data.
  The new e2e harness (`tests/e2e/`) spawns a **local** `uvicorn` on `127.0.0.1` + an ephemeral port against
  a temp DB — dev/CI only, never shipped.

### 7. Dependency vulnerabilities (`pip-audit`) — RISK ACCEPTED (low, with follow-up)
`pip-audit` over the current environment reported:
- **`transformers 4.48.3`** — multiple CVEs (model-deserialization / ReDoS / unsafe-load classes), fixed in
  4.50–4.53+. **Risk in callosum's use: LOW** — callosum loads only **trusted, pinned local models**
  (`all-MiniLM-L6-v2`, the NLI cross-encoder), never user-supplied model files, and runs locally on the
  user's own corpus.
- **`urllib3 2.3.0`** — CVEs fixed in 2.5–2.7. **Risk: LOW** — outbound calls go only to trusted endpoints
  (Crossref/OpenAlex/Gemini) with timeouts; no untrusted-redirect handling of attacker URLs.
- **`yt-dlp 2025.1.26`** — **NOT a callosum dependency** (absent from `requirements.txt`/`pyproject.toml`);
  it is environment noise (a globally-installed tool). Out of scope for the repo.
- `torchaudio` (local CPU build) could not be audited (not on PyPI) — not used by callosum.
- **Disposition:** not release-blocking for a local single-user app. `requirements.txt` uses version
  **ranges** (e.g. `sentence-transformers>=3,<6`), so a fresh install pulls patched transitive versions; the
  audited env simply has older ones. **Follow-up:** `pip install -U transformers urllib3` + re-run `pytest`
  before any hosted deployment; add `pip-audit` to CI (Phase 7) as a non-blocking report.

### 8. Lint / static hygiene — PASS
- `ruff check` clean (F-series incl. unused-import/var/redefinition = the reliable dead-code signals);
  `ruff format` applied repo-wide. One genuinely-dead function removed
  (`canonicalize_quote_text_variants`, an unused back-compat alias).

## Negative-path checks performed
- Hardcoded-secret grep: none found.
- Egress-off: `EgressGated*` wrappers raise + never call inner (unit-tested).
- `pytest` full suite: **275 passed, 1 skipped** after every change in the arc.

## Verdict
**Security Audit: PASS** for the local, single-user, `127.0.0.1`-only model, with two tracked follow-ups:
1. **Secrets hygiene** — ✅ **DONE (2026-06-20):** the 4 Gemini keys relocated to a gitignored `.env` (no value
   ever printed), `.claude/GEMINI_API_KEYS.md` deleted, `.gitignore` hardened (`.env` / `.env.*` / `*GEMINI_API*`
   / `*.key` / `*.zip` + `.claude/{backups,deprecated,plans}` + scratch), and the live-tree sweep is clean (only
   `.env`). A throwaway `git init` + **`git check-ignore` confirmed** `.claude/backups/`, every `*.zip`, `.env`,
   and the key files are excluded → **the keys cannot reach GitHub.**
   - **Residual exposure (NOT a GitHub path):** scanning zip *contents* found the 4 key values embedded in **16
     local backup zips** (inc43–48: 1 key; inc64–73: 4 keys) inside the **old `.claude/GEMINI_API.txt`** filename
     (predating `GEMINI_API_KEYS.md`), plus Dropbox version history. gitignore neutralizes the GitHub vector, but
     the only way to neutralize the local/Dropbox copies is to **rotate the 4 keys (revoke + reissue in Google AI
     Studio, update `.env`) — RECOMMENDED** before/around publication.
   - **Remaining:** a git-*history* secret scan at first push (no history exists yet — Phase 7).
2. **Transitive-dependency upgrades** (transformers/urllib3) — low risk locally; do before any hosted
   deployment, and wire `pip-audit` into CI.

The standing pre-public-deployment requirements (authentication, rate-limiting, per-IP resource caps,
hosted-context CORS re-review) remain as documented in CLAUDE.md and are **out of scope for source
publication** (the app is not being hosted).

## Addendum (2026-07-22) — backlog #20: pip-audit wired into CI

Closes this audit's own follow-up #2 ("wire `pip-audit` into CI"). Re-ran `pip-audit` fresh a month later:

- **`requirements.txt` (runtime/shipped deps): clean.** The previously-flagged `transformers 4.48.3` and
  `urllib3 2.3.0` findings have self-resolved exactly as this audit anticipated — the version **ranges**
  (`sentence-transformers>=3,<6`, etc.) already pull patched transitive versions on a fresh resolve. CI now
  runs `pip-audit -r requirements.txt --strict` as a **blocking** gate (`.github/workflows/ci.yml`).
- **`requirements-dev.txt` (dev/CI-only, never shipped): one open finding.** `pytest 8.4.2` →
  **PYSEC-2026-1845** (fixed 9.0.3). **RISK ACCEPTED** — dev-tooling only, never runs against untrusted input
  or ships to a user. Not bumped blind: pytest 9 is a major version change across a 1396-test suite plus
  pytest-xdist/pytest-testmon/pytest-playwright, which deserves its own dedicated compatibility pass rather
  than a drive-by pin change riding along with unrelated CI infra work. CI runs `pip-audit -r
  requirements-dev.txt` **report-only** (`|| true`) so a *new* dev-tool finding still surfaces without
  blocking on this known, accepted one. Documented at the point of use (`requirements-dev.txt` +
  `pyproject.toml`'s `dev` dependency-group), not just here.
- **Dependabot enabled** (`.github/dependabot.yml`): `uv` (Python), `npm` (frontend build toolchain), and
  `github-actions` ecosystems, weekly — continuous signal alongside pip-audit's point-in-time CI check.

**Security Audit: PASS** (addendum) — the runtime dependency surface is clean and now continuously gated; the
one open dev-only finding is accepted, documented, and does not block merges.

## Addendum (2026-08-24) — pytest compatibility pass completed

The deferred PYSEC-2026-1845 risk acceptance is resolved. The dev constraint now requires patched
`pytest>=9.0.3,<10`; the lock selected pytest 9.1.1. The normal parallel root suite passed 2,453 tests with
3 skipped under pytest 9.1.1, pytest-xdist 3.8.0, pytest-testmon 2.2.0, pytest-playwright 0.8.0, and Tach 0.35.0.
The same dependency pass upgraded the shipped transitive `cryptography` package from 49.0.0 to 50.0.0 and passed
the focused sync encryption, sharing identity, sharing envelope, and OIDC verification tests. No application code,
runtime dependency range, cryptographic primitive, or trust boundary changed.

**Security Audit: PASS** (2026-08-24 addendum) — the accepted pytest finding and the cryptography 49.x advisory
are resolved by compatible patched versions with focused and repository-wide regression coverage.
