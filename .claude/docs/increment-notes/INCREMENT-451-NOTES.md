# Increment 451 — AJOL as a fourth PUBLISHERS legitimacy source (backlog #40 slice)

## Implemented

Closes another slice of backlog #40's still-open regional-index list. PUBLISHERS ("where to submit,"
`app/backend/methods/publishers.py`, Discover → Journals) already wired DOAJ (live per-ISSN), SciELO (live
per-ISSN), and TOP Factor (a locally-mirrored periodic snapshot — inc 448). This increment adds a fourth source,
**AJOL** (African Journals Online), via a real, directly-inspected, CC-BY-4.0 third-party dataset on Zenodo
(Alonso-Álvarez 2025, DOI `10.5281/zenodo.14899380`) — chosen over AJOL's own live OAI-PMH feed (confirmed real
but article-indexed, needing a heavy multi-page harvest across ~750 journal "sets" with uncertain ISSN coverage)
and buildable today with no credentials.

**Mirrors TOP Factor's exact download→parse→replace→query-locally shape**, not SciELO's live-per-request shape,
since there is no usable live AJOL query API. New: `integrations/ajol/adapter.py` (`AjolClient`, `parse_ajol_csv`,
`download_ajol_database`), `app/backend/persistence/ajol_repo.py` (`replace_ajol_records`/`lookup_ajol_record`/
`ajol_db_status`), migration `0068_ajol_records.py`, new table `ajol_records` in `schema_findings.py`, router
`app/backend/api/routers/methods_ajol.py` (`GET /methods/ajol/database`, `POST .../refresh` + poll — mirrors
`methods_top_factor.py`). Wired into PUBLISHERS via the existing generalized `_by_issn(meta, table)` helper
(built in inc 448 specifically so a fourth source could reuse it — no new helper code needed):
`JournalProfile.ajol_status` (`{country, jpps_status, is_diamond, source_url}`), `"Indexed in AJOL"` in
`legitimacy_signals` (coverage fact only), `PublishersReport.ajol_coverage`. Frontend:
`08e_methods_publishers.jsx` gains an always-visible plain-text AJOL status line + a dedicated credit block;
`35e_maintenance.jsx` gains the "Download database" row.

## Key technical detail

**The real CSV encodes a missing ISSN as the literal string `"NA"`, not an empty cell** — 11 of 739 real rows
have `eissn="NA", issn_print="NA"` (confirmed by direct Python inspection of the downloaded file, not trusted
from its description). A naive empty-string-only missing-value check would silently store `"NA"` as a bogus
matchable ISSN key shared across every such row — every one of those 11 unrelated journals would then collide on
the same lookup key. `_clean_issn()` treats both `""` and the case-insensitive literal `"NA"` as absent; this was
caught and built correctly during the Plan-review phase, never actually shipped with the bug.

**AJOL's own official JPPS (Journal Publishing Practices and Standards) rating ranges positive-to-cautionary**
(`1/2/3 Stars`, `No Stars`, `New Title`, `Pending`, `Inactive Title`, `Ceased`, `NA`) — deliberately kept OUT of
the same-valence `legitimacy_signals` list (only the coverage fact "Indexed in AJOL" goes there) and shown
instead via a dedicated, always-visible `ajol_status` field with a plain-language tooltip gloss per status. The
`elevated_for` weighting-boost mechanic gates on a frozen `_AJOL_STAR_TIERS` **set-membership** check (not an
exclusion list), so `Ceased`/`Inactive Title`/`Pending`/`NA`/`No Stars` structurally cannot fall through a gap
into reading as a boost. `APPROACH-AVOIDANCE.md`'s no-accusation veto is scoped to *individuals*, not
institutional/venue operational-status facts — the same class already shown plainly today via
`retraction_records.status` — and Principles #6 (silence isn't a certificate) argues affirmatively *for* showing
a `Ceased` status plainly rather than hiding it behind an unqualified "Indexed in AJOL" chip.

**The "Refresh" honesty problem — a genuinely new UI-honesty vocabulary this codebase didn't have before.**
Unlike TOP Factor (COS periodically republishes the same OSF file — download-date ≈ data-currency), this AJOL
CSV is a one-time academic snapshot dated February 2024 with no update guarantee; a Zenodo record is immutable,
so a future update would land at a *new* record id. Reusing TOP Factor's "Refresh database" / "as of
{retrieved_at}" copy would make an implicit false-freshness claim on every future click. Fixed via a hand-updated
`AJOL_SNAPSHOT_DATE` backend constant kept visibly separate from the local `retrieved_at` download timestamp, and
a button that reads **"Download database"** — structurally honest on every future click, present or after a
hypothetical future re-pin.

**Live re-verification of the other two deferred regional indexes (not re-assumed from inc 448's note).**
**Latindex**: still no public API (403/404 on every plausible endpoint, reconfirmed). **Redalyc**: has a
documented free API (`api.redalyc.org`, registration-gated), but its host's TLS certificate currently fails
hostname validation (`SEC_E_WRONG_PRINCIPAL`, reproduced live via `curl -v` this session) — doubly blocked, not
just credential-gated.

## Housekeeping / gates

- **Security audit**: `.claude/security-audits/2026-07-01_publishers.md` gains a `## Addendum — SP3` — PASS.
  Zero request-time HTTP (a local mirror only), the `source_url` prefix-allowlist, the `"NA"`/malformed-bool
  fail-closed handling, size/row bounds, no new secret/dependency.
- **QA routes**: new `.claude/qa-routes/route_86_ajol.md` (mirrors `route_85_top_factor.md`); extended
  `route_60_publishers.md`'s standing assertions/adversarial checklist/steps (AJOL off the deferred list, the
  plain-Ceased/Inactive-display veto-level assertion, the star-tier-only elevation gate).
- `THIRD-PARTY-NOTICES.md`: added the AJOL/Zenodo entry (both DOIs) and backfilled the missing SciELO + TOP
  Factor entries from inc 448 (never added at the time).
- `.claude/CREDIT-THE-LINEAGE.md`: extended the PUBLISHERS lineage line with SciELO (backfill) + AJOL.
- `.claude/docs/INCREMENT-BACKLOG.md` #40: AJOL wired; Redalyc/Latindex re-verification recorded.

## Manual verification script

1. Open Settings → **Local maintenance**. Confirm an **"AJOL database"** row reading "Not downloaded — download
   to include AJOL in Where-to-submit results" with a **Download database** button (never "Refresh").
2. Click **Download database** (real network) — confirm the status line updates to
   `"{count} journals · February 2024 snapshot, downloaded {today's date}"`.
3. Run PUBLISHERS (Discover → Journals) for a Nigeria/South-Africa/Ethiopia-affiliated topic (best-represented
   countries in the real 739-row dataset). Confirm a matched card shows "Indexed in AJOL" plus a plain
   `AJOL status: {jpps_status} · {country}` line with a tooltip.
4. If a `Ceased`/`Inactive Title` journal surfaces, confirm it renders identically to a positive-status journal
   (no filtering, no extra warning chrome beyond the tooltip); confirm it does NOT appear in `elevated_for` at
   full open-science weighting.
5. Confirm the credit block near the AJOL row/panel cites both Zenodo DOIs and states the third-party,
   not-AJOL-official framing.

## Verification

- `pytest tests/test_ajol.py -q` → **10 passed**.
- `pytest tests/test_publishers.py -q` → **25 passed** (2 new AJOL-wiring tests + the never-downloaded honesty
  test + the narrowed `legitimacy_absent` assertion).
- `pytest tests/test_migrations.py -q` → includes the new `test_ajol_records_table_is_at_head`.
- `python tools/check_line_budget.py`: clean (489 files); `publishers.py` 292 lines, `routers/publishers.py` 321
  lines, `08e_methods_publishers.jsx` 443 lines, `35e_maintenance.jsx` 173 lines — all comfortably under the cap.
- `alembic upgrade head` + `alembic check` on a scratch DB: clean, no drift.
- `python tools/build_frontend.py`: clean; `pytest tests/test_frontend_assembly.py -q` → 64 passed.

## Rollback

Drop `ajol_records` (additive migration); remove `integrations/ajol/`, `ajol_repo.py`, `methods_ajol.py`, and
their `app.py`/`status.py` mounts; revert `methods/publishers.py`/`routers/publishers.py`'s AJOL params (each a
clearly separable addition); remove the AJOL block from `08e_methods_publishers.jsx` and `35e_maintenance.jsx`.
No other source's behavior (DOAJ/SciELO/TOP Factor) is touched by any of this.
