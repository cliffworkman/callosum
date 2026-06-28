# Increment 178 — README front-door (backlog #11)

Rewrote `README.md` into a current, contributor-facing front door (the prior one was accurate-but-stale: framed as
"Increment 73", missing ~100 increments of features and several onboarding essentials).

## What changed
- **Brought current:** the three word-processor adapters (LibreOffice/Word/Google Docs), BYOK multi-provider AI
  (incl. the zero-egress local provider), retraction/p-curve/GRIM/statcheck signals, the gap-finder, My
  Publications, OA acquisition, non-destructive merge, the reading-pane features, import beyond Zotero. Dropped the
  internal increment number from the public doc.
- **Added the contributor essentials it lacked:** the **`npm install` + `python tools/build_frontend.py`** step (a
  real onboarding trap — the README had no JS/build step), venv + cross-platform commands, a first-run
  model-download note, the auto-migrate note, a **Configuration & privacy** table (both egress gates + BYOK +
  `CALLOSUM_DB_URL`/`CALLOSUM_LIBRARY_DIR`), a **Security note** (127.0.0.1, no auth, opt-in cite-only Remote
  access), **Known limitations**, an honest **"Built with AI assistance"** note, and credit/license pointers
  (`THIRD-PARTY-NOTICES.md`, `CONTRIBUTING.md`, `LICENSE`).
- Kept the Principles framing + the CI/License badges.

## Boundary handling
#11 is tagged "your voice — never auto-shipped." This ships an **accurate draft** (replacing actively-stale public
content, sanctioned by CLAUDE.md "fix the README opportunistically") with **two items explicitly left to the
maintainer**: the **voice** (written neutral/factual) and a **screenshot** (a `<!-- TODO(maintainer) -->`
placeholder for the synthesis + verified-citation view). Trivially editable in git; revise on request.

## Gates
- Docs-only — no app code/migration/egress/surface change; no audit/Principles/QA trigger; pytest unaffected
  (**619**). Verified by recon of the repo root (CONTRIBUTING.md / LICENSE / THIRD-PARTY-NOTICES.md exist and are
  linked; SECURITY.md / CITATION.cff / .env.example do **not** exist yet — backlog #20 — so they're not linked).
