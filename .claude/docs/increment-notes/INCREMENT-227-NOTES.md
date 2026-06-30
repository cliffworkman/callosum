# Increment 227 — citation-equity audit, SP1 (backlog #25)

## Implemented

A new **Citation equity** METHODS panel: an **identity-agnostic, structural** audit of a library paper's
reference list (its OpenAlex `referenced_works`), shown against a sample of the paper's *field* — descriptive,
**never a score / target / accusation**, with every signal's basis inspectable. The gender/identity module stays
**deferred behind its own gate and absent from the core** (the canonical spec
`…/future-tracks/opus4.8_future-tracks_citationequitytool.md`). The topical "overlooked work" remediation is SP2.

- **`integrations/openalex/adapter.py`** — `_meta_from_work` extended (additive — existing callers ignore the new
  keys) to surface `venue`/`issn`/`institutions`/`country_codes`/`primary_topic` from the cached raw work blob; new
  `fetch_field_sample(conn, topic_id, *, size=200)` (cached `field:<id>`; `topic_id` validated `^T\d+$` **before**
  any request → no SSRF; fail-closed) + `fetch_work_meta_for(conn, ref)` (full meta from the cached by-ref fetch,
  no extra HTTP — gives the focal paper's `primary_topic`).
- **`app/backend/methods/citation_equity.py`** (NEW, pure, no-I/O) — `audit_reference_list(...)` → a
  `CitationEquityReport` of 5 descriptive `SignalView`s (self-citation [King et al. 2017], reliance on
  highly-cited work [Matthew; Merton 1968 / Perc 2014], venue concentration, institutional concentration,
  geographic / Global-South spread). Each carries its **list value**, the **field value** (where applicable), an
  **inspectable basis**, and an honest **coverage** count. A documented `GLOBAL_NORTH` ISO-2 set; **no
  composite score, no verdict, no identity inference.**
- **`app/backend/api/routers/citation_equity.py`** (NEW) — async `POST`/`GET /methods/citation-equity/run` (the
  `citation_counts.py` JobStore scaffold). The POST validates synchronously (404 missing / 422 no-DOI); the worker
  resolves the focal paper → `primary_topic` → `referenced_works` → per-ref `fetch_work_meta` (with progress) →
  `fetch_field_sample` → `audit_reference_list`. Ephemeral (no table/migration). Wired in `app.py`
  (`citation_equity_jobs` + `include_router`).
- **Frontend `app/frontend/js/08b_methods_citation_equity.jsx`** (NEW, 168) — a per-paper METHODS section
  (order 35, among the real tools): a **Run audit** button (user-initiated egress, not auto-run), `ProgressBar`,
  the field attribution, the 5 signal rows (a `This list` vs `Field` mini-bar + a descriptive summary + an
  expandable basis + coverage), the deferred-module honesty note, and the credit block. Tokens-only `.cite-equity-*`
  CSS. The inc-163 **citation-equity placeholder was removed** from `09_placeholders.jsx` (the inc-163/205
  convention — drop the stub in the increment its feature lands).

## Key technical detail

The **field baseline** is the focal paper's OpenAlex `primary_topic` (stated explicitly in the UI), sampled via
one cached `?filter=primary_topic.id:<T>&sample=200&seed=42` query — the descriptive "field" the reference list is
shown against (Matthew top-decile threshold, Global-South share, venue/institution spread). It is **context, not a
verdict**; a paper with no `primary_topic` degrades gracefully to the list's own shape (no field comparison). The
focal paper's `primary_topic` is read from the **same cached by-DOI fetch** `fetch_referenced_works` already made
(`fetch_work_meta_for`), so the audit adds only one OpenAlex query (the field sample) beyond the per-reference
metadata. Affiliation/country coverage on cited references is uneven — an absent country is recorded as *unknown*,
never assumed domestic (silence ≠ certificate), and each signal reports its coverage.

## Manual verification script

- **Unit/integration** (`tests/test_citation_equity.py`, hermetic, 14 tests): the additive `_meta_from_work` keys
  + `fetch_field_sample` (id-validated, fail-closed); each of the 5 signals over synthetic refs/field;
  **no-identity-inference** proven two ways (injecting `gender`/`sex`/`race` into inputs changes nothing; a static
  guard that the analyzer never keys on those); the async endpoint (run→report shape, 404/422, no-referenced-works
  → graceful, field-absent → own-shape, unknown-job → 404), all via an injected fake `openalex_client`.
- **Headed, no egress** (`.local/visual/drive_inc227_citation_equity.py`, fake OpenAlex injected): select a paper
  → METHODS → open **Citation equity** → **Run audit** → the 5 signals render with list-vs-field bars + the field
  attribution ("24 recent Decision neuroscience papers") + the geography country-breakdown basis + the deferred
  note + credit; **0 console/page/genai**.

## Gates

- **Security audit `.claude/security-audits/2026-06-30_citation-equity.md` PASS** (public-metadata egress — NOT
  the Gemini gate; SSRF-safe constant host + validated/bound topic id + the paper's own DOI; fail-closed parsing;
  bounded inputs; bound-param SQL; **no identity inference, proven by test**; no new ingestion path / dependency /
  migration).
- **Principles (rule #9) — aligned** (the statcheck/p-curve class; PRINCIPLES Example 3 + value A8): signal-not-
  verdict (#2), no opaque composite (#7 — raw shapes, never one number), inspectability (#8), human-is-the-filter
  (#5), silence-≠-certificate (#6). **Values (A-A):** A8 access-equity realized structurally; the veto-level
  no-accusation boundary honored (descriptive, identity-agnostic, no target/quota/per-author label; gender module
  absent). Declined paths: a "citation-equity score"/leaderboard, a gender-balance number, a "you under-cite
  group X" framing.
- **QA (rule #10):** new `route_51_methods_citation_equity.md`; surface **163/163 API + 723/723 FE, 0 uncovered**.
- **Rule #1:** all new files under cap (`citation_equity.py` analyzer ~290, router 166, chunk 168).

## Pytest

**(see footer — full suite green; +14 `test_citation_equity.py`).** `ruff` + `format` clean; frontend rebuilt
(`test_frontend_assembly` 5/5). No migration / new dependency. **NEXT — SP2:** the topical overlooked-work
remediation (surface relevant work the list omits, with a why-this-substitute trail; needs local embeddings + an
OpenAlex candidate pool — reuses this audit's field machinery).
