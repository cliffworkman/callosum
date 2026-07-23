# Security audit — LibreOffice manual refresh mode (2026-07-23)

## Scope

Increment 349 adds a document-local preference that can pause automatic citation formatting independently of
automatic bibliography rebuilding. It changes existing LibreOffice mutation routing, adds one menu/macro action,
and updates the real-UNO harness. It adds no backend endpoint, external integration, dependency, or file path.

## Threat review

- **Input validation / output encoding:** the new state is a fixed `"0"`/`"1"` Writer user-property written only
  by the toggle. It is not interpolated into XML, HTML, SQL, a command, or a URL. Citation payload decoding and
  citeproc response handling are unchanged.
- **Injection:** no new interpreter, shell, SQL, or markup sink. The menu dispatch target is a fixed action name
  covered by the existing action-registry packaging test.
- **SSRF / external calls / egress:** no new host or request. When automatic work occurs, it uses the existing
  configured callosum base URL and existing `/citations/render-document` path. With both automatic surfaces
  paused, `_auto_refresh` returns before that request. Public-metadata and LLM paths are untouched.
- **Secrets:** none read, stored, or transmitted.
- **Resource caps:** manual mode reduces render frequency. Explicit refresh retains the existing full-document
  request and transactional mutation behavior; no new loops, queues, timers, or background tasks.
- **File-path safety:** no new file read/write path. The preference lives inside the open Writer document using
  the existing removable user-property mechanism.
- **Supply chain:** no dependency or packaging-source change; the existing local `.oxt` builder remains the only
  build path.

## Negative-path checks

- `test_auto_refresh_honors_the_two_independent_preferences` covers all four preference combinations and proves
  the both-paused branch makes zero render calls.
- `test_auto_refresh_preferences_default_on_and_explicit_zero_disables` proves missing/corrupt-absent preference
  state preserves the previous default-on behavior and only the explicit fixed `"0"` disables a surface.
- `test_every_menu_action_is_a_real_action` proves `toggleCiteAuto` resolves to the fixed local action registry.
- The real `run_roundtrip.py` Writer spike inserted a citation with both surfaces paused and proved the live
  ReferenceMark remained present while neither citation text nor the frozen bibliography was rewritten; explicit
  refresh then resolved both.

## Result

**Security Audit: PASS**
