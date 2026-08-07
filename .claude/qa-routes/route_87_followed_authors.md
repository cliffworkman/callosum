<!-- qa-coverage
api: /followed-authors, /followed-authors/{author_id}, /followed-authors/candidates, /followed-authors/refresh, /followed-authors/refresh/{job_id}, /followed-authors/add, /followed-authors/dismiss
fe: 30f_followed_authors.jsx, 31d_mypubs_citing_authors.jsx#L9
-->

# ROUTE 87 — Followed authors (gap-finder source, backlog #29)

**Tier:** 2 external (OpenAlex metadata)
**Goal:** Exhaust the followed-authors subscription — follow by name/ORCID and by the My-Publications
citing-authors quick-action, refresh a followed author's works (cached, per-author), the absent-work candidate
list → Add / Dismiss, and unfollow — while preserving candidates-not-verdicts, the disclosed no-axis-ranking
limitation, and the shared dismissal list with gap-finder's own `/gaps`. Public OpenAlex metadata, **never**
the Gemini gate.

## Environment

Clean seeded instance (`_TEMPLATE.md` → Environment). **Egress UNSET** (the library-text gate must never fire;
OpenAlex metadata is fine). Register console/pageerror/request listeners before navigation.

**Seed note:** the real refresh hits OpenAlex per followed author (network + slow) and resolve-by-name/ORCID
hits OpenAlex too. To exercise the flow **offline + deterministically**, inject `app.state.openalex_author_client`
with a fake exposing `resolve_author(conn, *, orcid=None, name=None)` and `fetch_author_works(conn, author_id, *,
refresh=False)` (mirror `tests/test_followed_authors.py::_FakeAuthorClient`), returning at least one work whose
DOI is **not** in the seeded library (a gap) and one whose DOI **is** `10.123/facial` or `10.123/renderable`
(already in the library — must never surface as a candidate).

**Use a free port** — stray uvicorns from prior runs can serve a stale app (assert your own process is alive +
that `/followed-authors` doesn't 404).

## Standing assertions

- **Console-error budget = 0.** Any console `error` >= Medium; any `pageerror` >= High.
- **Egress gate.** ANY request to a `generativelanguage`/Gemini/genai host is **Critical** (this feature is
  public OpenAlex metadata only, never the LLM gate).
- **Candidates not verdicts.** Nothing is auto-added; each candidate row has **Add** + **Dismiss**; the human
  decides.
- **Disclosed limitation, not a silent gap.** The persistent note states candidates are **not filtered or
  ranked by relevance to your research axes** — only deduplicated against the library. This must be visible,
  not buried.
- **Cache, not a live recompute.** `GET /followed-authors/candidates` reads the persisted cache; only an
  explicit **Refresh** (all or a single author) recomputes and calls OpenAlex.
- **Zero-egress reads.** Follow/unfollow (direct-id path), listing followed authors, and reading candidates
  never call the injected author client — only Refresh and name/ORCID-follow do.
- **Shared dismissal.** A candidate dismissed here must also be excluded from `/gaps`' own candidate list (same
  underlying dismissed-work set) — confirms this isn't a second, disconnected dismissal domain.
- **Provenance.** Each candidate row shows `by <author> (followed)`.

## Adversarial checklist

- Follow the same author twice (by name, then by the My-Publications quick-action) → `already-following`, no
  duplicate chip
- Follow with a name that matches nothing → an honest "no match" message, never a 4xx/crash
- Refresh a single author vs. "Refresh all" → only the targeted author's cache row changes
- Add a candidate → it drops from the list (now in library); adding again is idempotent
- Dismiss a candidate → it drops and never resurfaces; also check `/gaps` (same dismissal set)
- Unfollow an author → their candidates disappear immediately (no stale rows)
- double-click Follow/Refresh/Add; resize to `375x812` → no horizontal overflow
- oversized name input (~500 chars) → rejected (422), not silently truncated

## Steps

1. Open **Discover → Followed Authors**. Confirm the empty state ("Follow an author to start surfacing their
   absent works") and the persistent disclosure note (Add/Dismiss + the no-axis-ranking limitation).
2. Follow an author by name (offline, seeded as above) → a chip appears; the tooltip shows the OpenAlex id +
   "never refreshed" (or "matched by name, not ORCID — lower confidence" if that's the match path).
3. **Refresh all** → `<ProgressBar>` appears (Status popover entry too); on completion, a coverage line
   ("Refreshed N authors, checked M works…") plus the candidate list: **absent** work with `by <author>
   (followed)`, in-library work never shown.
4. **Add** a candidate → row drops; verify in the library list that it was imported metadata-only (no PDF
   fetch).
5. **Dismiss** another candidate → drops; reload the tab → still gone. Open **Discover → Search**'s gap-finder
   modal (`/gaps`) if reachable in this route's seed and confirm the same work/DOI does not resurface there
   either.
6. Go to **My Publications → Authors citing your work** (if the seed has a citing-author card) and click
   **Follow** on a card → it flips to "✓ Following" and the author now also appears in the Followed Authors tab
   without a second resolve call (this is the zero-egress direct-id path).
7. **Unfollow** an author (× on the chip) → their candidates vanish from the list immediately.
8. Adversarial: a Refresh with an author who has zero absent works → an honest empty state, no crash; mobile
   viewport has no overflow; **0** genai-host requests throughout.

## Pass criteria

- Follow (name/ORCID/direct-id), unfollow, refresh (single + all), and the candidate list's Add/Dismiss all
  work end-to-end against the cache.
- The no-axis-ranking limitation is visibly disclosed, not silently omitted.
- Dismissal is shared with `/gaps`; Add is metadata-only; ordinary reads never egress.
- 0 console/page errors; **0 genai-host requests**.
- Bad inputs fail closed (422 on oversized name / malformed author id); mobile viewport has no horizontal
  overflow.

## Deposit

Write `.claude/qa-inbox/<RUN_ID>/route_87_followed_authors.md` + `screenshots/` (see `_TEMPLATE.md`).
