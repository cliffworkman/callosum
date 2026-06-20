# Security audit — Annotation highlights (increment 30)

Date: 2026-06-16
Scope: first user-authoring + first substantial mutating endpoints
(`POST /papers/{id}/annotations`, `GET /papers/{id}/annotations`,
`DELETE /annotations/{id}`) + the extended `annotations` table + frontend selection/render.

## Threat review

- **Authn/authz.** No auth — consistent with the rest of this local, single-user,
  loopback-bound app (CORS already restricted to localhost). These are the first
  *mutating* routes; before any public exposure they MUST be gated (already tracked in
  `.claude/CLAUDE.md` → "Before going public"). No cross-user/ownership surface today.
- **Input validation.** `AnnotationCreateRequest` (Pydantic) enforces `page ≥ 1`,
  `bboxes` non-empty, `anchor_text` non-empty. `_validate_annotation_request` rejects
  colors outside the server-side `ANNOTATION_COLORS` allowlist and bboxes that are
  non-finite or non-positive-area → HTTP 422. Verified by `test_annotation_create_rejects_invalid_payloads`.
- **Injection.** All DB access is SQLAlchemy Core with bound parameters
  (`insert(annotations).values(...)`, `select(...).where(c.id == ...)`,
  `delete(...).where(c.id == ...)`); table/column identifiers come from schema
  constants, never request data. No SQL string building.
- **Output encoding / XSS.** Annotation data reaches the DOM only via safe property
  assignments — `box.style.*` (numeric %s), `box.dataset.annotationId`, and
  `box.title` (textContent-equivalent). No `innerHTML` is fed annotation/anchor text.
  `color` is constrained to the hex allowlist. `note` is null this increment.
- **SSRF / external calls / data egress.** None added. Annotations are local-only;
  nothing is sent off-machine. The Gemini egress gate is untouched.
- **Path safety.** No filesystem path is derived from annotation input; the PDF route
  is unchanged and still resolves paths only from trusted attachment rows.
- **Delete scope.** `DELETE /annotations/{id}` removes exactly one row by id (404 on
  unknown), and commits. Verified by `test_annotation_create_list_delete_round_trip`
  and the headless E2E (UI + DB both show 0 after delete).
- **Cascade / data safety.** `annotations.paper_id`/`attachment_id` keep
  `ON DELETE CASCADE`; deleting a paper deletes its annotations
  (`test_annotation_cascade_on_paper_delete`). The migration is additive (nullable
  columns), idempotent, and a simulated upgrade of a pre-0002 DB preserved the existing
  Zotero-import row, the FK CASCADE, and the indexes.
- **Route-surface invariant.** `test_api_exposes_only_read_only_get_routes` updated and
  asserts ONLY the two new mutations + one new GET were added; `POST /papers` still 405.

## Hardening items deferred to public-exposure work (not blocking local use)
- Auth + rate-limiting on the mutating routes.
- Length caps on `anchor_text`/`prefix`/`suffix` and a max `bboxes` count (currently
  unbounded `Text`/list — a large payload is a local-disk concern only today).
- (Pre-existing, out of scope) `\.claude/GEMINI_API.txt` stores a key in plaintext; the
  app reads `GOOGLE_API_KEY` from the env, so this file is just a user stash — keep it
  out of any future repo/deploy surface.

## Verdict
**Security Audit: PASS** for the current local, single-user context. The deferred items
above are required before any public/internet-facing deployment and are tracked in
`.claude/CLAUDE.md`.
