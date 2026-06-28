# Increment 185 — Literature discovery SP1b: the axis-relevance highlight

Backlog #28 SP1b (the design-blessed fast-follow after SP1's Search tab, inc 183/184). For each search result, score
its title+abstract against the user's **axis** embeddings and **highlight** the likely matches **within the complete
list** — a hint, never a filter. The user chose this next.

## Principles gate (rule #9) — a SIGNAL feature, run before building

Signal not verdict (#2) + silence-is-not-a-certificate (#6): the badge is "likely: <axis> · match 0.NN"; a
below-cutoff item carries **no badge** = *no strong axis match*, **not "irrelevant"**. Human-is-the-filter (#3/#5):
never hides/filters/reorders — the complete list stays; the user still saves. No opaque composite (#7): the match is
**one cosine similarity**, rounded to the 2 decimals an axis card shows (directly comparable to a paper's confidence).
The declined misaligned path = a curated "here's what matters" list that hides the rest. **Aligned.** (Full framing
in the audit.)

## Implemented

- **`app/backend/discovery/relevance.py`** (NEW) — `score_axis_relevance(conn, items, *, embedding_model, cutoff_default=0.35)`:
  reads the user's axes (`kind != my_publications`), embeds each axis's text (`strip_punctuation(description else
  label)` — the SAME prep the scorer uses, so numbers agree with the axis cards) + each item's `title+abstract`,
  computes cosine (numpy, unit-normalized), and returns `{dedup_key: {axis_id, axis_label, similarity}}` for items
  whose **best** axis match clears that axis's cutoff (`scoring_gain` or 0.35). **Pure read — no DB write, no egress.**
  Empty/axis-less → `{}`.
- **`app/backend/api/routers/discovery.py`** — `POST /discovery/relevance` (`RelevanceRequest`: `items` 1..50, each
  `{dedup_key≤400, title≤2000, abstract≤20000}`) → `{relevance: {...}}`; `_discovery_model(request)` caches the heavy
  embedding model on `app.state` (injected wins for tests; mirrors citations.py `_suggest_model`).
- **`app/frontend/js/30d_discover.jsx`** — after a search, best-effort `POST /discovery/relevance` over the rendered
  rows → a `relevance` map; a `.discover-relevance` badge ("likely: <axis> · match N.NN") renders on matched rows. The
  list is **never** filtered/reordered by it; a failed/empty call → no badges (the list still shows in full).
- **`app/frontend/styles.css`** — `.discover-relevance` = an accent chip (`--accent`/`--accent-soft`/`--accent-line`/
  `--radius-pill`), tokens only (DESIGN rule #8 — the accent = provenance/match semantics).

## Key technical detail

- **The match equals the axis-card confidence.** Same axis-text prep + `round(cosine, 2)` as
  `axis_scoring._confidence_from_cosine_distance` (which is `round(1 - distance, 2) = round(cos, 2)`), so a result's
  "match 0.42" is the same scale as a paper's "0.42" on that axis — inspectable, not a new opaque number.
- **Best-effort overlay.** Relevance is a separate POST fired after the search renders; the search endpoint (inc 183)
  is untouched (no re-audit of search). If relevance fails or returns `{}`, the complete list is already on screen.

## Manual verification script

Headed, no egress (a fake registry + a fake 2-D keyword model + a seeded "Attention models" axis):

```
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 python .local/visual/drive_inc185_relevance.py
```

→ search → **3 rows (complete list)**, **exactly 1** `.discover-relevance` badge ("likely: Attention models · match
1.00") on the matching row, **no badge** on the other two; 0 console/page/genai. **PASS.**

## Gates

- **pytest 639** (+5 `tests/test_discovery_relevance.py`: best-axis-above-cutoff, per-axis cutoff respected,
  my-publications excluded, no-axes/no-items → `{}`, endpoint shape + 422). `ruff` check + `format --check` clean.
- **QA (rule #10):** `route_43_discovery.md` gained `/discovery/relevance` + the highlight assertions → surface
  **124/124 API + 631/631 FE, 0 uncovered**.
- **Audit:** `.claude/security-audits/2026-06-28_discovery-relevance.md` **PASS** (local read-only signal; bounded
  inputs; no egress/DB-write; Principles aligned — augment-never-filter).
- **No migration, no new dependency** (numpy already present); the search/save endpoints are unchanged.

## NEXT (remaining #28)

- **SP1a:** a PubMed provider (NCBI E-utilities httpx client) — `register()` one provider, no UI edit, its own audit.
- **SP2:** the Feed tab (subscriptions + polling + a read/unread store; bioRxiv by category).
