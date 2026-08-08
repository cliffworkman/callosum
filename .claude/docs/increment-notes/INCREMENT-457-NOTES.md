# Increment 457 — Wire the self-citation field baseline into Citation Concentration (backlog #25/#37)

## Implemented

Inc 456 built the reusable primitive (`OpenAlexClient.fetch_self_citation_hit_count`) and ran a real empirical
study to pick N=40 for the self-citation field baseline, but deliberately stopped short of wiring it into the
shipped signal — `_self_citation()` in `app/backend/methods/citation_equity.py` still hardcoded `field_pct=None`.
This increment does that wiring, closing backlog #25/#37: the Library-paper Citation Concentration audit
(`POST /methods/citation-equity/run`) now computes and shows a real field comparison for self-citation, matching
the other three signals (Matthew effect, venue, institution).

### A router-local helper computes the baseline (I/O); the methods module stays pure

Mirrors the existing split: `routers/citation_equity.py` already does all the live OpenAlex fetching
(`field = client.fetch_field_sample(...)`); `methods/citation_equity.py`'s `_matthew`/`_venue`/`_institution` are
pure functions over an already-fetched `field` list. The new self-citation baseline follows the same pattern —
`_compute_self_citation_baseline(conn, client, field, *, jobs, job_id)` in the router does the live work;
`_self_citation()` just receives the already-computed `(pct, n)` and formats it.

```python
SELF_CITATION_BASELINE_TARGET_N = 40      # inc 456's chosen N
SELF_CITATION_BASELINE_MAX_CHECKS = 100   # bounds worst-case cost in a low-coverage field
```

**The dual cap is a deliberate, disclosed design choice, not an oversight.** Inc 456's study found "computable"
coverage (a field paper having both a reference list and author ids) varies 18%–74% by field. Chasing N=40
unconditionally could mean checking nearly all 200 field-sample papers for a low-coverage field like Cognitive
Neuroscience — a real, unbounded cost increase to a single interactive audit run. Capping raw checks at 100
bounds worst-case added latency/requests to a predictable amount regardless of field coverage; a low-coverage
field's baseline may honestly be based on fewer than 40 papers (visibly disclosed via the sample-size count in
the summary text), the same "computed over less than the target, shown but not hidden" honesty pattern
`Coverage.low` already uses elsewhere in this file.

**Deliberately did not change the focal paper's own self-citation matching methodology.** The focal paper's
`list_pct` still uses family-name overlap (`focal_author_families`, the existing, already-shipped heuristic) —
not upgraded to author-ID matching even though `_meta_from_work` now provides `author_ids` for the focal paper's
own references too. Upgrading that would be a real, separate behavior change to already-shipped, already-tested
logic, and the focal paper's references are already locally fetched with full metadata — no network benefit to
re-deriving that check via a live count-query. The field baseline uses the ID-based primitive because that's
what makes it cheap (a count-only query, no per-reference metadata fetch); the two signals answer a similar
question via genuinely different, appropriately-suited mechanisms.

### `audit_reference_list` / `_self_citation` signature changes (additive, backward-compatible)

```python
def audit_reference_list(
    *, refs, focal_author_families, field, field_topic, references_total,
    self_citation_field_baseline: float | None = None,   # NEW, default None
    self_citation_field_baseline_n: int = 0,               # NEW, default 0
) -> CitationEquityReport: ...
```

Default `None`/`0` means `wip_citation_equity.py`'s existing call (which never computes a field sample at all —
its own documented honest degraded path) needed **zero changes**.

`_self_citation()` gained the same two params. The existing early-return branch (no author names on the focal
paper) is unchanged — orthogonal to the field baseline. In the normal branch, `field_pct` is now the computed
baseline instead of a hardcoded `None`, and the summary gains a field-comparison sentence when a baseline
exists ("...In a comparable field sample (N papers checked), an average of X% are self-citations."). When no
baseline was computable (no topic, or zero computable field papers), the summary keeps the existing honest
"no field baseline" framing.

### Router wiring

Right after `field = client.fetch_field_sample(conn, field_topic["id"]) if field_topic else []` in
`_run_citation_equity_job`, the new helper runs and its result threads into `audit_reference_list(...)`. The
new phase reuses the existing `jobs.mark_progress` mechanism with its own label ("Computing field self-citation
baseline") so the Status popover reflects the extra work honestly (invariant #5) — `JobProgress` is a frozen
dataclass fully replaced on each call, so switching `total`/`label` mid-job for a second phase is the same
already-established idiom the reference-fetch loop itself uses.

### Frontend: no changes

Confirmed (both in inc 456's planning and re-confirmed here): `08b_methods_citation_equity.jsx` already renders
`field_pct` generically for any signal (`s.field_pct != null && <CiteEquityBar label="Field" pct={s.field_pct}
kind="field" />`). The backend now populates it for self-citation; the existing `CiteEquityBar` just renders.

## Key technical detail

The dual cap's interaction is what the new tests actually exercise: `_compute_self_citation_baseline` stops
at **whichever limit is hit first** — `len(rates) >= SELF_CITATION_BASELINE_TARGET_N` (a high-coverage field
reaches 40 resolved rates well before exhausting its checks) or `checked >= SELF_CITATION_BASELINE_MAX_CHECKS`
(a low-coverage field burns through 100 raw attempts without ever reaching 40 resolved rates). A field paper
missing either `referenced_works` or `author_ids` is skipped entirely — it costs neither a request nor a tick
against either cap, since it was never computable in the first place.

## Housekeeping / gates

- **Security audit addendum** appended to `.claude/security-audits/2026-06-30_citation-equity.md` (inc 457
  section): bounded new egress volume on an already-audited call shape (same host, same validated/bound-id
  posture as `fetch_works_by_ids`), no new endpoint/dependency/migration, the dual cap as a disclosed/tested
  design choice, no identity inference, user-initiated only.
- **QA route** `.claude/qa-routes/route_51_methods_citation_equity.md` extended: the self-citation card now
  shows a Field bar with an honest "N papers checked" disclosure when a baseline was computable, and an honest
  no-baseline note (never a fabricated 0%) when it wasn't.
- `.claude/docs/INCREMENT-BACKLOG.md`: #25 marked **✅ CLOSED inc 457**; the two #37 cross-references updated
  to reflect the baseline shipped rather than being open.
- `.claude/CLAUDE.md`: counter bumped to 457.

## Manual verification script

1. Start the app against the real testing library. Select a Library paper with a resolvable DOI/topic.
2. Work → Meta-Reference → Citation concentration → **Run audit**.
3. Confirm the self-citation card now shows a **Field** bar with a real percentage, and its summary names how
   many field papers the baseline was computed over.
4. Find (or note) a paper whose topic yields zero computable field papers; confirm the self-citation card still
   shows only the list's own percentage with an honest no-baseline note — no crash, no fabricated 0%.
5. Re-run on a WIP manuscript (Work → Meta-Reference in the WIP context) — confirm self-citation still reads
   "not computed" (WIP has no field topic; unaffected by this increment).

## Verification

- `pytest tests/test_citation_equity.py tests/test_wip_citation_equity.py -q` → **25 passed** (3 new tests: field
  baseline present/absent on the report; the dual-cap early-exit at the target-N boundary; the dual-cap early-exit
  at the max-checks boundary, proving exact request counts and honest thin-baseline disclosure).
- `python tools/check_line_budget.py`: clean.
- `ruff format` + `ruff check`: clean.
- Live Playwright verification against the real testing library: pending — see step below if not yet run.

## Rollback

Revert `app/backend/methods/citation_equity.py` and `app/backend/api/routers/citation_equity.py` to their
pre-457 state (both signature changes are additive/backward-compatible, so a partial revert of just the router
wiring — leaving the new kwargs unused — is also safe). Revert the 2 new tests in `tests/test_citation_equity.py`.
No schema/migration; no frontend change to revert.
