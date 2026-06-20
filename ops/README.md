# Ops

`ops/` is mostly planning space right now.

Implemented local operations are simple:

- Install dependencies with `pip install -r requirements.txt`.
- Run the app with `uvicorn app.backend.api.app:app --host 127.0.0.1 --port 8080`.
- Run tests with `pytest`.
- Apply migrations with `alembic upgrade head` when needed; the app also checks migrations on startup.
- Keep secrets in environment variables such as `GOOGLE_API_KEY`, `CALLOSUM_DB_URL`, and `CALLOSUM_ALLOW_DATA_EGRESS`.

Packaging, desktop distribution, OS keychain integration, and GROBID service operations are planned or
exploratory, not implemented here — tracked under **"Packaging & distribution (post-V1)"** (Theme 4) in
`.claude/docs/INCREMENT-BACKLOG.md` (GROBID service ops follow Track C).
