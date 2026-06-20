# Security Audit — Auto-suggest tags (local c-TF-IDF) (increment 72)

**Date:** 2026-06-20
**Trigger:** One new API endpoint (`GET /papers/{id}/suggested-tags`) + a new local-only feature module. No
new schema/migration, no external service.

## What changed
A "✨ Suggest" affordance on the Details Tags row proposes candidate tags for a paper via **local c-TF-IDF**
(the per-paper analogue of inc-52's axis suggestion). New `clustering/tag_suggestion.py` ranks the terms most
distinctive of the paper vs the library; the endpoint returns them (minus the paper's current tags) as plain
strings the user curates. Accepting a candidate adds it via the existing inc-71 tag-add path.

## Threat review
- **Local, no egress, no AI off-device.** Purely token statistics over the user's own stored title/abstract
  text (the same tokenizer the axis suggester uses, `_paper_tokens`, which JATS-strips abstracts). **No
  embeddings, no clustering, no Gemini** — the user explicitly chose local-only. Nothing leaves the machine.
- **Read-only.** The endpoint computes + returns; it mutates nothing. (Accepting a suggestion goes through
  the already-audited `POST /papers/{id}/tags`.)
- **SQL injection (rule #3):** the only query is `select(papers.c.id, title, abstract).where(deleted_at IS
  NULL)` — bound-param Core, no interpolation. Live papers only.
- **Input/output:** `paper_id` is an int path param; unknown paper → 404. Suggested strings are derived from
  the paper's **own** tokenized text and returned as JSON strings, rendered by React as plain-text chips (no
  `dangerouslySetInnerHTML`) — no injection vector. Tokens are length-≥3, non-stopword, non-digit.
- **Resource:** each call tokenizes the live library once (O(papers × tokens)); capped at
  `MAX_LIBRARY_PAPERS = 5000`. Sync is fine for a single-user local tool; the call is triggered only on an
  explicit "✨ Suggest" click (no hover/auto firing).
- **API surface:** one new **GET** route (read-only), added to the route-surface read allowlist
  (`tests/test_health.py`). 3-segment literal `/papers/{paper_id}/suggested-tags` — no collision with
  `/papers/{paper_id}` or `/papers/{paper_id}/tags`. CORS unchanged.
- **Migration / deps:** none (reuses numpy-free stdlib `Counter`/`math` + the existing tokenizer).

## Negative-path checks (results)
- Distinctive term ranks first; a term shared across the library (high df) is demoted below an equally-frequent
  rare term (idf) (`test_idf_demotes_a_common_term_below_a_rare_one`). **PASS.**
- The paper's existing tags are **excluded** (case-insensitive); trashed/missing paper → `[]`
  (`test_suggest_ranks_distinctive_excludes_existing_and_handles_trashed`). **PASS.**
- Endpoint: 200 + candidates; a just-added tag drops out of the next suggestion; unknown paper → 404
  (`test_suggested_tags_endpoint_excludes_added_and_404s`). **PASS.**
- **Live E2E** (`.local/tag_suggest_e2e/`): ✨ Suggest → candidate chips → accepting "photosynthesis" adds it
  as a tag and removes it from the suggestions. **0 console errors.** **PASS.**

Full suite: **251 passed** (+3). No new dependency; no migration; no egress.

**Security Audit: PASS.**
