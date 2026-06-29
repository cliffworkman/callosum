# Callosum

[![CI](https://github.com/cliffworkman/callosum/actions/workflows/ci.yml/badge.svg)](https://github.com/cliffworkman/callosum/actions/workflows/ci.yml)
[![License: AGPL v3](https://img.shields.io/badge/License-AGPL_v3-blue.svg)](https://www.gnu.org/licenses/agpl-3.0)

**Callosum is a local-first, AI-assisted reference manager for scholarly PDFs.** Its thesis is simple and
load-bearing: *an LLM summary is only trustworthy if every citation is independently verified against the source.*
You import a library, Callosum extracts and chunks each PDF with page + bounding-box coordinates, embeds everything
locally, lets you cluster papers along your own semantic axes, and generates citation-grounded summaries where
**every sentence is checked back against the source and shown with its evidence** — the quote, the page, a
confidence — so you see signal, never a verdict.

It runs on your machine. After import it works **offline**, and nothing leaves your computer unless you explicitly
turn on an AI feature.

> **Status:** a working MVP, under active development and pre-1.0. It's used daily by its author and backed by a
> large test suite, but it's single-user-focused and the surface is still moving. Expect rough edges.

<!-- TODO(maintainer): add a screenshot of the synthesis + verified-citation view here. -->

## What it does today

**Library & metadata**
- Import from Zotero (metadata + available PDFs), or from **BibTeX / RIS / CSL-JSON** (also covers Mendeley/EndNote).
- **Scan / watch a folder** of PDFs — the library folder is watched by default and re-scanned on launch/focus.
- Metadata enrichment from Crossref/OpenAlex; an editable, Mendeley-style details pane; duplicate detection with
  reviewable reasons; **non-destructive merge**; Trash / restore / permanent delete.
- Free, rights-holder-authorized **open-access acquisition** (OpenAlex + a 7-source cascade) — OA only, no paywall
  circumvention.

**Read & annotate**
- In-browser PDF viewer (pdf.js) with zoom, fit-width / two-up, highlights + notes, a searchable/filterable Notes
  panel, next/prev-mark navigation, remembered scroll position, and a distraction-free reading mode.

**Verified synthesis (the core)**
- Citation-grounded summaries: generated sentences are re-checked **locally** (embedding similarity + NLI stance +
  verbatim quote) and shown verified / contrasted / **flagged**, each with its quote, page, and confidence. A
  citation's coordinates are labelled **exact / region / null** and never presented as more precise than they are.

**Cite-while-you-write**
- Formatted citations + bibliographies (APA/MLA/Chicago/IEEE/Nature/Harvard via citeproc-js, rendered locally).
- **Word-processor adapters:** a LibreOffice Writer extension, a Microsoft Word add-in, and a Google Docs add-on —
  insert/refresh live citations, switch styles, and **suggest citations for a sentence** from your library.

**Open-science & discovery signals** (descriptive, never accusatory; "a prompt to look, not a verdict")
- **statcheck** (recompute reported NHST p-values), **p-curve**, **GRIM/GRIMMER**, and **retraction** checks
  (Crossref / OpenAlex / a Retraction Watch mirror).
- A **literature gap-finder** (works cited by / citing several of your papers), a **My Publications** impact
  dashboard, user-defined **semantic axes**, and free-form **tags**.

**Selective, opt-in AI** — used for *generation only* (summaries, axis-term suggestions, a help assistant), **off
by default**, multi-provider (Gemini / OpenAI / Anthropic / a local OpenAI-compatible endpoint). A loopback **local**
model runs with **zero egress**. Verification is always local and never delegated to the LLM.

## Quickstart

Requires **Python 3.11+** and **Node.js** (the frontend build + the local citation engine). The shell examples
show PowerShell (Windows) and bash (macOS/Linux).

```bash
# 1. clone + a virtual environment
git clone https://github.com/cliffworkman/callosum.git && cd callosum
python -m venv .venv && source .venv/bin/activate          # Windows: .venv\Scripts\Activate.ps1

# 2. Python + JS dependencies
pip install -r requirements.txt
npm install                                                 # esbuild (frontend build) + citeproc (citation engine)

# 3. build the single-file frontend (re-run after any app/frontend/ edit)
python tools/build_frontend.py

# 4. run it, then open http://127.0.0.1:8080/
uvicorn app.backend.api.app:app --host 127.0.0.1 --port 8080
```

**First run downloads models.** Extraction/embedding/verification use local models (`sentence-transformers`
`all-MiniLM-L6-v2` + a small NLI cross-encoder) pulled from Hugging Face on first use — a few hundred MB, one-time,
then it works offline. The SQLite database auto-migrates to the latest schema on startup.

## Configuration & privacy

Everything is local by default. The only data that can leave your machine is **AI generation you turn on**.

| Setting | Effect |
|---|---|
| `CALLOSUM_DB_URL` | SQLite database URL (default: a file under `.local/`). |
| `CALLOSUM_ALLOW_DATA_EGRESS` = `1`/`true`/`yes` | Consent gate for AI **summary generation** (off by default). |
| `CALLOSUM_HELP_ASSISTANT_ENABLED` | Separate gate for the AI help assistant (sends only the question + public help docs, never your library). |
| `CALLOSUM_LIBRARY_DIR` | The watched library folder (default: `library/`). |

**BYOK from the UI:** you can also set your API key + provider and toggle AI features in **Settings → AI features**
(stored in your OS keychain or a local file under `~/.callosum/`, never in the repo, never returned over the wire).
Public-metadata lookups (Crossref/OpenAlex) are not the AI gate — set a contact email in **Settings → Metadata
access** for the polite pool.

## Cite from your word processor

Callosum can place live, formatted citations directly in **LibreOffice Writer**, **Microsoft Word** (desktop), and
**Google Docs** — search your library, insert, refresh/renumber, switch styles, build the bibliography, and suggest
citations for the sentence you're writing. See `adapters/`'s per-tool READMEs for setup.

## Security note

Callosum binds to **`127.0.0.1`** and ships with **no authentication** — it's designed for single-user, local use.
**Remote access** (Settings) is an opt-in, default-off bearer-token gate + rate-limiter, intended for the Google
Docs bridge via a local [cloudflared](https://github.com/cloudflare/cloudflared) tunnel with a **cite-only**
ingress; it is *not* a hardened multi-tenant deployment. Don't expose Callosum to a network without reviewing the
threat model (the folder-scan / file-serving routes read local files server-side).

There is also an **optional account** (Settings → Account → *Sign in with ORCID*, default-off): it's **opt-in and
identity-only** — signing in verifies who you are (and pre-fills *My Publications*), but sends **no** library text,
PDFs, or notes anywhere; the app works fully offline with no account. (It activates only on an instance where the
account service has been configured.) Cross-device sync — the only thing that *would* move library data
off-machine — is a separate, future, explicitly-consented step that does not exist yet.

## Development

```bash
pip install -r requirements-dev.txt   # ruff, pytest, playwright, etc.
pytest                                 # the test suite
ruff check . && ruff format --check .  # lint + format (CI gates both)
```

- Backend: `app/backend/` (FastAPI + SQLAlchemy Core + sqlite-vec + sentence-transformers + scikit-learn +
  PyMuPDF). Frontend source: `app/frontend/` (React JSX chunks + pdf.js, esbuild-precompiled into one file — no
  bundler). External adapters: `integrations/`. Word-processor clients: `adapters/`.
- `.claude/` is the project's working memory + planning suite (dev-only, not shipped app code).
- Contributions welcome — see [`CONTRIBUTING.md`](CONTRIBUTING.md).

## Principles

Callosum follows the commitments in [`.claude/PRINCIPLES.md`](.claude/PRINCIPLES.md): every claim carries its
evidence; signal, not verdict; facts are distinguished from candidates; the deterministic local substrate is the
source of truth and the model only narrates it; inspectability over authority; local-first and provider-swappable;
and — as a hard line — no paywall circumvention and no accusation of individuals. The README and the code should
never claim more certainty than the evidence can show.

## Known limitations

- Pre-1.0, single-user-focused; no auth for general/hosted deployment (the opt-in token targets the local tunnel).
- First run needs internet to fetch the local models.
- Node.js is required for the citation engine and the frontend build.
- AI summary quality depends on your chosen provider; **verification of citations is always local and runs on every
  result**, so a weaker model affects draft quality and coverage, never which citations are accepted.

## Built with AI assistance

Callosum is developed with heavy AI-coding assistance (Claude Code), under a human-reviewed,
test-and-verification-gated workflow. Its design commitments (above) are about *not* over-trusting AI output —
including its own.

## Credit & license

Third-party software and data (citeproc-js, bundled CSL styles, and the scholarly methods Callosum implements) are
credited in [`THIRD-PARTY-NOTICES.md`](THIRD-PARTY-NOTICES.md). Licensed under **AGPL-3.0-or-later** — see
[`LICENSE`](LICENSE).
