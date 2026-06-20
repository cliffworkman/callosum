# Security audit — Synthesis → annotation bridge / client `source` (increment 36 / suite C)

Date: 2026-06-17
Scope: `POST /papers/{id}/annotations` now accepts an optional client-supplied `source`
(to save a verified, exact-coordinate citation as a `source="synthesis"` annotation), plus a
frontend "Save as highlight" affordance. Builds on the A/B annotation audits
(`2026-06-16_annotations.md`, `2026-06-16_annotation-notes.md`).

## Threat review

- **Authn/authz.** Unchanged — local, single-user, loopback-bound, CORS restricted to
  localhost. No new route (the create endpoint already existed); only one new request field.
  There is **no trust boundary between the user and their own data**, so accepting `source`
  from the client is a data-integrity concern, not a privilege/escalation one. Pre-public
  gating (auth + rate-limiting on mutations) still tracked in `.claude/CLAUDE.md`.
- **Input validation — the one new input (`source`).** `AnnotationCreateRequest.source` is
  optional. `_validate_annotation_request` rejects any non-null value **not in the
  `NATIVE_ANNOTATION_SOURCES = ("user","synthesis")` allowlist** → **422** (the allowlist is
  imported from the repository — single source of truth, also used to scope reads). A forged
  or arbitrary provenance string (`"admin"`, `"zotero"`, `""`, …) can therefore never be
  persisted; an omitted source defaults to `"user"` (prior behavior preserved). Verified by
  `test_annotation_create_accepts_synthesis_source`,
  `test_annotation_create_defaults_source_to_user`,
  `test_annotation_create_rejects_forged_source`.
- **Coordinate-precision honesty contract.** Saving from synthesis is gated **client-side**
  (the Save control is enabled only for `coordinate_precision === "exact" && status ===
  "verified"` with ≥1 bbox; region/null/flagged → disabled + tooltip) **and re-checked in
  `App.saveCitationHighlight`** before the POST, so a region/null/flagged citation can never
  be turned into a precise highlight. This is a UI-truthfulness property, not an auth control;
  bypassing it (hand-crafting a POST) only lets the user mislabel *their own* highlight —
  no cross-user impact. The stored bboxes are pure geometry: `_annotation_bboxes_payload`
  copies only `page/x0/y0/x1/y1`, so the citation's `coordinate_precision` sub-key is dropped
  (no misleading precision marker is persisted on the annotation). Proven by the headless E2E
  (enabled-vs-disabled gating; `.pdf-synthesis-outline` reload-drift 0.0px).
- **Injection.** SQLAlchemy Core bound parameters throughout; `source` flows as a bound value
  into `create_annotation`; no string SQL. `bboxes`/`anchor_text`/`color` validated as before
  (finite + positive-area rects, color allowlist, note cap).
- **Output encoding / XSS.** The synthesis-saved annotation renders through the same safe paths
  as user highlights — `box.title`/`outline.title` (textContent-equivalent), percentage styles
  computed from numeric bbox coords, fill `color` constrained to the hex allowlist. No
  `innerHTML` of any quote/anchor/source value. `source` itself is never written to the DOM.
- **404 / not-found.** Create still 404s on an unknown paper before any write.
- **Egress / SSRF / path safety.** None added. No network egress; the save is a same-origin
  POST of local data. The PDF path is still resolved only from the trusted attachment row.
- **Resource caps.** No new unbounded field. Client-side re-save guard prevents accidental
  duplicate saves; there is no server-side dedupe (a determined client can create duplicates —
  local-disk concern only, noted in the increment notes).
- **Route-surface invariant.** Unchanged — no route added — so
  `test_api_exposes_only_read_only_get_routes` still passes without edits.

## Verdict
**Security Audit: PASS** for the current local, single-user context. The client-supplied
`source` is allowlist-validated server-side (forged → 422); the honesty contract is enforced in
the UI and re-checked before the write. Auth + rate-limiting on all mutating routes remain
required before any public deployment (tracked in CLAUDE.md → "Before going public").
