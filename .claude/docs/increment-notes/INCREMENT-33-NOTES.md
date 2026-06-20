# Increment 33 Notes

Render Crossref **JATS abstracts** cleanly in the Detail pane — store raw, render structured.
Pure-frontend-visible result; no schema/migration change; stored data untouched.

## Implemented

- **New transform** `app/backend/metadata/abstract_display.py` → `clean_abstract_for_display(raw)`:
  converts a stored JATS XML abstract fragment to a small **allowlisted HTML** string
  (`<p> <em> <strong> <sub> <sup>`, attribute-free, all text escaped). Maps `jats:p`→`<p>`,
  `jats:italic`→`<em>`, `jats:bold`→`<strong>`, `jats:sub`/`jats:sup`→`<sub>`/`<sup>`; drops a
  redundant leading `<jats:title>Abstract</jats:title>` (keeps a real title as a bold label).
  Parses with stdlib `html.parser.HTMLParser` (no new dependency) — lenient: unclosed/malformed
  tags degrade (open inline tags are force-closed), entities decode, plain text → one `<p>`,
  fully entity-encoded JATS is `html.unescape`d once first.
- **API:** `PaperDetailResponse` gains `abstract_display: str | None` (derived); `_paper_detail`
  sets it from `clean_abstract_for_display(row["abstract"])`. `abstract` stays the **raw** stored
  value — additive, no existing shape repurposed.
- **Frontend:** Detail pane renders `p.abstract_display` via `dangerouslySetInnerHTML` (the app's
  only such use — consumes only the backend's allowlisted output; raw-text fallback kept), plus
  `.abstract p` paragraph spacing.

## Decisions

- **Allowlisted HTML over plain text:** sub/sup (chemical formulae, p-values) and italic/bold
  can't survive as plain text and the corpus needs them.
- **`abstract_display` (new field), not repurposing `abstract`:** keeps the raw JATS faithful and
  available (store-raw ethos; we may want the structure later), purely additive.
- **stdlib HTMLParser, not regex strip:** a naive `<[^>]*>` strip mangles entities / literal `<`;
  HTMLParser is lenient and entity-aware. No heavy dependency.

## Security

First `dangerouslySetInnerHTML` in the app. Safe by construction: only attribute-free allowlisted
tags are emitted, source tags/attributes are never copied, all text is escaped. See
`.claude/security-audits/2026-06-17_jats-abstract-display.md`.

## Verification

- **pytest: 122 passed** (113 + 9 new): both real fixtures (HBM/serotonin + Alves), plain-text
  passthrough, malformed/unclosed, entities+sub/sup, allowlist/security, transform purity, and an
  API test asserting `GET /papers/{id}` returns raw `abstract` + cleaned `abstract_display` while
  the stored `papers.abstract` column is byte-identical afterward.
- **Headless Firefox:** the HBM abstract renders as a clean paragraph with italic citation + bold
  copyright, no `<jats:…>` visible, no console errors (screenshot confirmed).

## JATS elements not specially handled

Degraded to their text content (tag dropped, text kept): `jats:sec`, `jats:list`/`jats:list-item`,
`jats:xref`, `jats:sc` (small-caps), `jats:related-article`, MathML (`mml:*`), and links. Add
mappings later if the corpus needs them.

## Launch

`uvicorn app.backend.api.app:app --host 127.0.0.1 --port 8888` → open a paper with a JATS abstract
(most Crossref-resolved ones) → Detail tab shows clean structured text.
