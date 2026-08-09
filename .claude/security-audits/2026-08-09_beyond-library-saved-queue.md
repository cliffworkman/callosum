# Security Audit — Persistent beyond-library saved queue (inc 465, backlog #30's last open piece)

**Date:** 2026-08-09
**Feature:** A new "Save for later" action on beyond-library citation suggestion cards (web Cite pane +
LibreOffice adapter) persisting the suggestion into a reviewable, add-or-dismiss queue — a new modal
(`BeyondLibrarySavedModal`) opened from Discover → Search.
**Triggers:** audit-gate #1 (4 new endpoints under `POST`/`GET /citations/beyond-library/*`), #5 (net-new
feature spanning 6+ files: `app/backend/api/routers/beyond_library_saved.py`,
`app/backend/persistence/schema_findings.py`, `app/frontend/js/36c_beyond_library_saved.jsx`,
`app/frontend/js/37_cite.jsx`, `app/frontend/js/30d_discover.jsx`, `adapters/libreoffice/callosum_cite.py`).

## Scope

`POST /citations/beyond-library/save` upserts a suggestion (by its existing `dedup_key` identity) into a new
`saved_beyond_library_suggestions` table; `GET /citations/beyond-library/saved` lists pending rows, read-time
filtered against the live library (mirrors `gaps.py`'s own filter); `POST .../add` imports the row via the
existing `save_item` helper (the same write path `/discovery/save` and `/gaps/add` already use) and marks it
`added`; `POST .../dismiss` marks it `dismissed`. Both the web Cite pane and the LibreOffice adapter's Suggest
dialog gained a "Save for later" trigger calling the save endpoint with the exact same fields already displayed
on the card — nothing new is computed, fetched, or inferred anywhere in this feature.

## Threat review

| Vector | Assessment |
|---|---|
| **Data egress** | **None.** Every one of the 4 endpoints touches only the local SQLite engine — no `httpx`/`urllib`/provider SDK in `beyond_library_saved.py`. The suggestion itself was already fetched by the pre-existing, already-audited `POST /citations/suggest` (`.claude/security-audits/2026-07-11_beyond-library-citation-suggest.md`); saving/listing/adding/dismissing it here never re-contacts any provider. **To assert:** a grep of `app/backend/api/routers/beyond_library_saved.py` for `httpx\|requests\|urllib\|generativelanguage\|google-genai\|anthropic\|openai` returns no matches. |
| **Input validation** | The suggestion payload originates from a public-metadata search result (already untrusted-shaped content per the base beyond-library audit) — `SaveBeyondLibraryRequest` bounds every text field (`title` ≤2000, `abstract`/`reason`/`evidence_text`/`source_query` ≤4000/8000, `dedup_key` ≤512) via Pydantic `Field(max_length=…)` (rule #4); a missing `dedup_key`/`title` → **422** before any DB write (`test_save_rejects_missing_required_fields`). `DedupKeyRequest` bounds the add/dismiss identity the same way. |
| **Output encoding** | Plain JSON fields (strings/ints/lists) — no HTML/script surface. The web card renders them the same way the live suggestion card already does (React auto-escaping, no `dangerouslySetInnerHTML`); the LibreOffice adapter only ever inserts confirmation text via `_msgbox`, never the untrusted title/abstract into a document range. |
| **Injection (SQL)** | None — plain SQLAlchemy Core bound-parameter `select`/`insert`/`update` (rule #3), the identical pattern every other router in this codebase uses; no raw SQL string construction anywhere in the new file. |
| **File-path safety** | Not engaged — no file read/write in this feature (rule #4's file-path clause N/A). |
| **SSRF** | None — no server-side fetch of any caller-supplied URL; `url`/`doi`/etc. are stored verbatim as opaque display strings, never dereferenced server-side. |
| **AuthZ / exposure** | All 4 endpoints sit behind the existing `AccessControlMiddleware` bearer gate when Remote access is on (default-off → localhost only). None of `/citations/beyond-library/*` is on the cloudflared cite-only ingress allowlist (`adapters/googledocs/cloudflared-config.yml`'s exact-match `path: ^/(papers\|papers/export\|citations/render-document\|citations/suggest\|citations/styles)$`, confirmed by grep) — unreachable via the Google-Docs tunnel, correct for a desktop-authoring review surface. On a `CALLOSUM_READ_ONLY=1` instance the three mutating routes (`save`/`add`/`dismiss`) return 403 (method gate); `GET .../saved` stays readable. |
| **Resource exhaustion** | Bounded per-field lengths (above); no unbounded loop over untrusted input — `list_saved_beyond_library_suggestions` reads the whole (naturally small, explicit-action-only) table, no pagination needed at this scale, matching `gaps_list`'s own unbounded-but-naturally-small read. |
| **Supply chain** | **No new dependency.** Stdlib/SQLAlchemy/Pydantic/FastAPI already present; the adapter reuses its existing `urllib`-based `_post_json`/`_get_json`. |

## Negative-path checks (concrete results — 2026-08-09)

- [x] `POST /citations/beyond-library/save` with a **missing `dedup_key`** or **missing `title`** → **422**
  (`test_save_rejects_missing_required_fields`).
- [x] `POST /citations/beyond-library/add` / `POST .../dismiss` on an **unknown `dedup_key`** → **404**, no crash
  (`test_add_and_dismiss_unknown_dedup_key_404`).
- [x] **Upsert, not duplicate**: saving the same `dedup_key` twice produces exactly one row, with the latest
  fields (`test_saving_twice_upserts_not_duplicates`).
- [x] **Read-time in-library filter**: a saved suggestion whose DOI already resolves to a live library paper
  never appears in `GET .../saved` (`test_list_excludes_a_suggestion_already_in_the_library`).
- [x] **Add never fabricates duplicates**: re-adding an already-`added` dedup_key (via a fresh save + add)
  resolves to the *same* existing paper (`created: False`), not a second copy
  (`test_add_imports_the_paper_and_removes_it_from_the_queue`).
- [x] **Dismiss never touches the library**: `GET /papers` stays empty after a dismiss with nothing else saved
  (`test_dismiss_removes_from_queue_without_touching_the_library`).
- [x] **A dismissed item can be re-flagged**: saving the same `dedup_key` again after a dismiss returns it to
  the pending queue (`test_saving_a_dismissed_item_again_returns_it_to_the_queue`) — an explicit, visible
  re-save, never a silent resurrection.
- [x] **Zero egress surface.** A grep of `app/backend/api/routers/beyond_library_saved.py` for
  `httpx|requests|urllib|google|openai|anthropic|generativelanguage` returns no matches.
- [x] `pytest tests/test_beyond_library_saved.py tests/test_libreoffice_adapter.py tests/test_gapfinder.py
  tests/test_discovery.py -q` → **230 passed** (2026-08-09).
- [x] Real-UNO (`adapters/libreoffice/run_roundtrip.py`, `spike_beyond_library_save_for_later`): a mixed
  selection of library + beyond-library rows correctly saves only the beyond-library ones and reports the
  library-only case with an explanatory message rather than silently no-op'ing.

## Principles posture (rule #9)

A pure bookkeeping layer over an already-audited, already-principled signal — no new claim/signal/judgment
about the literature is introduced. `status` (pending/dismissed/added) is user-driven state, not a computed
score; the persisted fields are the exact same `reason`/`evidence_text`/`relationship_label` the live suggestion
card already showed (Principles Example 1: "no source inserted merely because a model ranked it highly" — this
feature never inserts anything at all, it only remembers what the user explicitly flagged). Matches this
codebase's consistent soft-delete-over-hard-delete posture (papers → Trash, not straight deletion) — `dismiss`
is a status flip, never a row delete, so nothing is silently, irrecoverably discarded from the DB even though
it's hidden from the UI.

## Verdict

Every negative path fails closed (422 at the Pydantic boundary on save; 404 on an unknown identity for add/
dismiss) and is covered by an executed test. The feature has no network code path at all (statically confirmed
by grep) and is unreachable via the cite-only tunnel allowlist (confirmed against the real
`cloudflared-config.yml` regex). Bound parameters throughout (rule #3); no new file-write path; no SSRF; no new
dependency; every text field is length-bounded against untrusted upstream provider metadata.

**Security Audit: PASS.**
