# Security audit — Annotation notes + PATCH (increment 31 / suite B)

Date: 2026-06-16
Scope: the project's first **update** endpoint (`PATCH /annotations/{id}`) + `note` on
create + an in-viewer management panel. Builds on the A audit
(`2026-06-16_annotations.md`).

## Threat review

- **Authn/authz.** Unchanged — local, single-user, loopback-bound, CORS restricted to
  localhost. PATCH is a new mutation but adds no new auth surface. Pre-public gating still
  tracked in `.claude/CLAUDE.md` → "Before going public".
- **Input validation.**
  - Create: `note` is now accepted (optional) and length-capped at
    `ANNOTATION_NOTE_MAX_LEN = 4000` via `_validate_annotation_note` → 422.
  - PATCH (`AnnotationUpdateRequest`): partial update read via Pydantic `model_fields_set`.
    Empty patch (neither `note` nor `color`) → 422. If `color` supplied it must be in the
    `ANNOTATION_COLORS` allowlist (an explicit `null` color is rejected) → 422. If `note`
    supplied, `null` clears it and a string is length-capped → 422. Verified by
    `test_annotation_patch_rejects_bad_requests` + `test_annotation_create_rejects_over_cap_note`.
- **Update scope (narrowness).** `update_annotation(conn, id, *, note=…, color=…)` writes
  **only** `note`/`color` (+ `updated_at`) on the single addressed row — geometry/page/
  anchor/source are never touched. The handler builds the kwargs solely from the validated,
  provided fields. `test_annotation_patch_updates_note_and_color` asserts page/anchor/bboxes
  are unchanged.
- **Injection.** SQLAlchemy Core bound parameters throughout
  (`update(annotations).where(c.id == ...).values(**kwargs)`); identifiers from schema
  constants; no string SQL.
- **Output encoding / XSS.** `note` reaches the DOM only via safe property assignments —
  `box.title` (textContent-equivalent), the panel's `.pdf-annot-note` via React text child
  (auto-escaped), and a controlled `<textarea value>`. No `innerHTML` of note/anchor text.
  `color` stays constrained to the hex allowlist.
- **404 / not-found.** PATCH and DELETE both 404 on unknown id before any write.
- **Egress / SSRF / path safety.** None added; notes are local-only.
- **Resource caps.** The note cap (4000) is the A-flagged public-hardening item, now done.
  (`bboxes`/`anchor`/`prefix`/`suffix` length caps remain deferred — local-disk concern.)
- **Route-surface invariant.** `test_api_exposes_only_read_only_get_routes` updated to admit
  exactly one new mutation (`PATCH /annotations/{id}`) and nothing else.

## Verdict
**Security Audit: PASS** for the current local, single-user context. Auth + rate-limiting on
all mutating routes remain required before any public deployment (tracked in CLAUDE.md).
