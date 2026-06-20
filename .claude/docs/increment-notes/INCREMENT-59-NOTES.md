# Increment 59 Notes — Help corpus + navigable, corpus-driven help modal

The in-app help was a single static, hard-coded modal (axes/tiers tips only). This increment makes help a
real **surface**: extensive end-user documentation grounded in the current app, served as a structured
corpus and rendered in a navigable two-column modal (TOC + sections with stable anchor ids + scroll-to-flash).
It is the foundation for the inc-60 AI help assistant (whose deep-links key off these stable section ids).

## How the content was authored (token-saving Codex workflow)
- **Codex** (`codex --dangerously-bypass-approvals-and-sandbox exec`) generated the first draft: I gave it
  an end-user-audience prompt + the required `<!-- section: <id> -->` marker format + a coverage list, and
  told it to **read the real code** (`.claude/CLAUDE.md`, `routers/*`, `js/*`) so sections reflect shipped
  behavior. It produced a 22-section, ~515-line draft (`.claude/help-draft/help_draft.md`).
- **I reviewed it against the code** (the "second draft"): spot-verified claims — confirmed the Zotero
  importer really does handle collections/tags/notes/annotations (`_upsert_collections`/`_upsert_tags`) and
  the exact UI labels ("Merge axes", "search related terms", "Save changes"/"Create axis", "Re-score",
  "Synthesize", "Save as highlight"); fixed two labels to match the UI exactly (`next →`, `Flagged ·
  needs review`). The draft was accurate and end-user-focused, so it ships nearly verbatim as
  `app/backend/help/help_content.md`.

## Implemented
- **`app/backend/help/help_content.md`** — the shipped corpus (markdown asset; 22 sections; stable ids).
- **`app/backend/help/corpus.py`** (+`__init__.py`) — `load_help_corpus()` parses the marker-delimited
  markdown into `HelpSection(id, title, html, text)` (cached); `render_html` is a small, **allowlisted**
  markdown renderer (no new dependency: paragraphs, `ul/li`, `strong/em/code`, `h3`, `a[href]` limited to
  http(s)/`#`; all text escaped first); `help_corpus_prompt()` (the stuffed corpus string) is defined now,
  consumed by the inc-60 assistant.
- **`app/backend/api/routers/help.py`** — `GET /help/corpus` → `{sections:[{id,title,html}]}`. Stateless,
  no DB, **no egress** (the docs render even when the assistant is off / offline). Wired in `app.py`.
- **`app/frontend/js/18_help.jsx`** — rewritten: fetches `/help/corpus`, renders a wider two-column modal
  (a TOC + the section bodies, each `<section id="help-<id>">`), plus a reusable **`flashHelpSection(id)`**
  scroll-to + transient-highlight helper (mirrors `30_viewer.jsx`'s `jumpToAnnotation` flash). The corpus
  is now the single source of truth (the old hard-coded tips are retired). CSS added per DESIGN.md
  (token-based; section flash uses the indigo `--accent-soft`).

## Key technical detail
The section bodies are rendered to HTML server-side and injected with `dangerouslySetInnerHTML`. That is
safe here because the content is **app-owned and static** (no user input on the path) and `render_html`
escapes every text run and allowlists tags + link schemes (drops `javascript:`/`data:`) — the same posture
as the audited `clean_abstract_for_display`. `flashHelpSection` is a hoisted top-level function so the
inc-60 help-assistant reference chips can reuse the exact scroll+highlight (the workflow we want to
condition: probe → reference → routed-and-highlighted source).

## Help-doc maintenance: the `HELP-DOCS-SYNCED` marker (new convention)
To keep the corpus current without a blind diff each session, `.claude/changes.md` now carries an HTML-comment
marker `<!-- HELP-DOCS-SYNCED … -->` at the top of the entry of any increment that brings the corpus current.
Since changes.md is newest-first, **entries above the topmost marker are changes made since the last help
sync** — the candidate set to review for help updates. CLAUDE.md's Session-kickoff + Change-tracking
sections document the convention and add a start-of-session check. (User's idea — leverages the existing
changelog instead of re-scanning the code.)

## Manual verification / E2E
- **pytest: 210** (+7: 5 renderer/parsing unit tests — escaping, tag/scheme allowlist, duplicate-id guard,
  plain-text strip — plus the shipped-corpus + `GET /help/corpus` endpoint tests). Route-surface invariant
  updated (+`/help/corpus` GET).
- **Live E2E** (`.local/help_e2e/run.py`, Playwright): open the `?` modal → **22** sections render from the
  corpus; all guaranteed ids present; a TOC click scrolls the content (0→13800px) and applies the `.flash`
  highlight to the target section; **0 console errors**; screenshot captured (the formatted body — bold,
  bullets, `code` env-var chips — reads cleanly).
- Audit: `.claude/security-audits/2026-06-19_help-corpus.md` — **PASS**.

## Backlog
NEXT (after your review of the in-app docs): **increment 60** — the AI help assistant (`POST /help/ask`,
its own `CALLOSUM_HELP_ASSISTANT_ENABLED` gate via the inc-58 seam pattern, references → `flashHelpSection`).
Other queued items unchanged (library merge, terms-as-first-class, embedding-text JATS cleanup,
permanent-delete, persistent dedup-dismiss).
