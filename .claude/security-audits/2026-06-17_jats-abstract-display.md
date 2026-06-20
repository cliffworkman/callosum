# Security audit — JATS abstract display rendering (increment 33)

Date: 2026-06-17
Scope: introduces the app's **first `dangerouslySetInnerHTML`** — the Detail pane renders
`abstract_display`, an HTML string produced by `clean_abstract_for_display`
(`app/backend/metadata/abstract_display.py`) from the stored JATS abstract.

## Threat
A stored abstract is third-party content (Crossref publisher markup). Rendering it as HTML
is a markup/script-injection (XSS) sink if any source tag/attribute reaches the DOM verbatim.

## Mitigation — safe by construction
- The transform **never copies source tags or attributes**. It parses with the stdlib
  `HTMLParser` and emits only a fixed allowlist of **attribute-free** tags:
  `<p> <em> <strong> <sub> <sup>`. Source attributes (`onclick`, `href`, `style`, …) are
  dropped; unknown tags (`<script>`, `<a>`, `<img>`, …) are dropped (their text is kept).
- All text runs are `html.escape`-d, so a literal `<`/`>`/`&` in the abstract renders as an
  entity, never as markup.
- The frontend injects **only** this backend output (commented as such); the raw `abstract`
  fallback path stays plain-text (React-escaped), never injected.
- Output is well-formed even from malformed input (unclosed inline tags are force-closed);
  a parser exception falls back to escaped plain text.

## Verification
`tests/test_abstract_display.py::test_disallowed_tags_and_attributes_are_stripped` asserts a
fragment containing `<script>`, an `onclick` attribute, and an `<a href>` yields output with
**no** `<script`, `onclick`, `href`, or `<a` — only the allowlisted attribute-free `<em>`.
Entity/`<`-as-text handling covered by `test_entities_and_sub_sup_preserved`. Headless Firefox
render confirmed no `<jats:…>` text and no console errors.

## Verdict
**Security Audit: PASS.** No new endpoint/auth/fetch/upload surface; the only new surface is the
allowlisted HTML injection, mitigated and tested. Stored data is untouched (display-only).
