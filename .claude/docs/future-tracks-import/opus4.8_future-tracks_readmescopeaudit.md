# Top-level README — scope audit + expansion to a contributor front door

**Disposition for CC:** the current top-level `README.md` is **accurate and current — not stale.** It correctly
describes the implemented app at Increment 73. The issue is **scope**: it is written as an
*implemented-application description* (it says so: "this README describes the implemented application") and needs
to become the project's **front door** for a collaborator (Jeff) and a potential public audience — one that sets
expectations, enables setup on a machine that isn't Cliff's, and points to the onboarding and safety docs.
**Expand the scope; do not rewrite the tone or re-document what's already right.**

## Keep as-is (accurate; do not redo)
- The one-line description + core thesis (verification over authority).
- "What Exists Today" (accurate to inc 73).
- Stack, including Python 3.11+.
- Basic setup / run / test, the `CALLOSUM_DB_URL` note.
- The egress-gate explanation (`CALLOSUM_ALLOW_DATA_EGRESS` + `GOOGLE_API_KEY`).
- The Principles section + link, and especially the line **"READMEs and implementation should not claim more
  certainty than the code can show"** — preserve it; it is on-ethos and should govern this edit too.
- License.

## Add — must-have before sharing with Jeff or any non-Windows contributor

1. **Pre-release status + a "Known limitations / what's rough" section.** The README lists what exists but never
   the sharp edges. State plainly: pre-release, single-user, not hardened for network exposure; then list the
   current rough spots / deferred items honestly (e.g., the deferred embedding-text JATS cleanup, on-disk PDF
   not removed on purge, library merge not yet built — pull the real ones from the backlog). Expectations are
   the front door's job.

2. **A safety note.** The app binds to `127.0.0.1`, has **no authentication and no rate limiting**, and **must
   not be exposed to a network or the public internet as-is** (from the security baseline). Without this, a
   reader could mistake a local MVP for something deployable.

3. **Cross-platform setup.** The current block is **PowerShell-only**; Jeff may be on macOS/Linux. Provide bash
   equivalents (or a platform-agnostic path), and recommend a virtual environment (or uv, once adopted) rather
   than a bare `pip install`.

4. **Dev setup, distinct from user setup.** `requirements-dev.txt` (or the uv dev group); how to run the test
   suite; the **frontend build step** (`python tools/build_frontend.py` after editing anything under
   `app/frontend/`); and a pointer to CONTRIBUTING.md.

5. **First-run expectations.** The first run downloads a local embedding model (note rough size / disk), and the
   app is offline-capable after import — so a contributor isn't surprised by a download or a slow first run.

6. **Secrets / config.** Point to `.env.example` (variable **names** only), reiterate that `.env` and keys are
   never committed, and document **both** gates — `CALLOSUM_ALLOW_DATA_EGRESS` **and** the separate
   `CALLOSUM_HELP_ASSISTANT_ENABLED` (the README currently omits the help-assistant gate).

## Add — should-have

7. **Pointers to CONTRIBUTING.md, SECURITY.md, and CITATION.cff** once they exist (coordinate with Phase 7 of
   the harness plan, which creates them; create stubs if needed so the links resolve rather than 404).
8. **A one-line note on auto-migrate-on-startup** (the DB self-heals to head) — reassures a contributor.
9. **A brief, honest "Built with AI assistance" note**, and that contributions are reviewed against
   `PRINCIPLES.md` — transparency that's on-brand and sets the review expectation for AI-assisted PRs.
10. **A screenshot or short visual** of the browser UI — high leverage for a UI app's front door.

## Later (not now)
11. Status badges (after CI exists); a versioning/release section (after SemVer tagging begins).

## Instructions
- Keep every accurate section; **expand** scope, preserve tone.
- Add all must-haves; add should-haves where the referenced files exist (or create stubs / coordinate with the
  harness plan's Phase 7).
- Cross-platform the setup block.
- The README must not overclaim — honor its own principles line.

## Dependency note
Items 4, 6, and 7 reference files created in the harness/public-readiness plan (CONTRIBUTING.md, SECURITY.md,
`.env.example`, CITATION.cff). Either create those stubs first, or run this README pass **alongside Phase 7** of
the harness plan so the pointers resolve.
