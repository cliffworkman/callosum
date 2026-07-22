# Contributing to Callosum

Thanks for your interest! Callosum is a local-first, AI-assisted reference manager whose defining
commitment is that **every AI claim is independently verified against the source** and shown with its
evidence. Contributions must keep that promise.

## Orient yourself first

- **Read [`.claude/CLAUDE.md`](.claude/CLAUDE.md)** — the authoritative briefing (architecture, invariants,
  conventions, directory map, decision log).
- **[`.claude/PRINCIPLES.md`](.claude/PRINCIPLES.md)** is the charter (10 commitments + the THEORY contract +
  worked aligned-vs-misaligned examples); **[`.claude/APPROACH-AVOIDANCE.md`](.claude/APPROACH-AVOIDANCE.md)**
  is the deeper value substrate. Any change that produces a claim/signal/judgment about the literature, or that
  touches inspectability / provenance / the fact-vs-candidate distinction / the data-egress posture, must run
  the **Principles alignment gate**: name the principle(s) touched, name the easier misaligned path, and — when
  at odds — **propose the aligned alternative**, don't just object.

## Dev setup

```bash
uv sync                                    # installs the pinned dev/CI toolchain from uv.lock into .venv
pre-commit install                         # wires the fast pre-commit gate (ruff, whitespace/EOF, line budget)
uv run uvicorn app.backend.api.app:app --host 127.0.0.1 --port 8080   # then open http://127.0.0.1:8080/
```

No `uv`? The pip fallback still works (kept in sync by hand):

```bash
python -m venv .venv && . .venv/bin/activate      # Windows: .venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
```

Secrets come from the environment or a **gitignored `.env`** — never commit keys. Optional Gemini summary
generation is **off by default** and requires `CALLOSUM_ALLOW_DATA_EGRESS=1` + `GOOGLE_API_KEY`.

The library database is a SQLite file under `.local/` by default; set **`CALLOSUM_DB_URL`** to persist a stable
location (and ideally keep it out of a cloud-synced folder) — see
[Choosing a stable database location](README.md#choosing-a-stable-database-location).

## Before you open a PR

- **Lint + format:** `ruff check .` and `ruff format .` (config in `pyproject.toml`; line-length 120).
- **Tests:** `pytest` must be green; add/adjust tests for new behavior.
- **Frontend changes:** edit the source under `app/frontend/` (not the generated `callosum-app.html`), then
  `python tools/build_frontend.py`. To run the opt-in browser smoke: `python -m playwright install chromium`
  then `CALLOSUM_RUN_E2E=1 pytest tests/e2e`.
- CI runs ruff + pytest + the e2e smoke on every PR.

## House rules (enforced in review)

- **600-line cap** on any file under `app/` or `integrations/` (tests/tools exempt). Split by concern.
- **Minimal diffs** — no drive-by refactors bundled into a feature change.
- **Parameterized SQL only** (SQLAlchemy Core bound params); validate untrusted input (PDFs, external API
  responses) at the boundary.
- Read [`.claude/DESIGN.md`](.claude/DESIGN.md) before any CSS / inline-style change.
- **Security-sensitive changes** (a new endpoint, a new external fetch, a new ingestion/file-write path, auth,
  a new dependency, or a ~300+ LOC feature) trigger a security review — see the audit gate in CLAUDE.md.
  Found an actual vulnerability rather than making a change? See [`SECURITY.md`](SECURITY.md) — please don't
  open a public issue for anything sensitive.
- Development proceeds in numbered **increments** with notes under `.claude/docs/increment-notes/`.

## License

By contributing, you agree that your contributions are licensed under the project's **AGPL-3.0** license.
