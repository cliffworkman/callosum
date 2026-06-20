# Increment 40 Notes — Axis punctuation normalization

## Problem
Axes differing only in punctuation/spacing scored differently: "anomalous-is-bad" (4) vs
"anomalous is bad" (5); "resting-state" (31) vs "resting state" (28). Root cause:
`normalize_text("whitespace-lower-v1")` only lowercases + collapses whitespace — it **keeps hyphens
and punctuation** — and `SentenceTransformerEmbeddingModel.encode_texts` applies it before encoding, so
MiniLM tokenizes "anomalous-is-bad" ≠ "anomalous is bad" → different embeddings → different results.

## Fix (axis-side only)
- New `strip_punctuation(text)` util in `app/backend/embeddings/models.py` — collapses runs of
  punctuation/symbols/underscores to a single space (unicode-aware: keeps accented letters + digits),
  e.g. "anomalous-is-bad" → "anomalous is bad", "5-HT" → "5 HT". Downstream `normalize_text` still
  lowercases + collapses whitespace, so case + punctuation + spacing all converge.
- `axis_scoring.py` applies it to the axis text at the two sites that define an axis's identity:
  `_embed_axis` (the embedding input AND the stored `source_text_version`) and `axis_score_state` (the
  staleness recompute) — so two punctuation-variant phrasings embed identically and share a text-version.
- **Axis-side only**: papers are unchanged (no re-embed, no migration). The axis-vs-paper vectors are
  still comparable MiniLM embeddings; the user's reported discrepancy (equivalent axes → different
  results) is fully resolved because the two phrasings now produce the *same* axis embedding.

## Not a bug: the N difference (4 vs 31)
"anomalous-is-bad" surfacing far fewer papers than "resting-state" is mostly real library composition
(many resting-state/neuro papers, few facial-anomaly) + the 0.2 floor — not a defect. Raising recall on
niche axes is the job of the **next** increment (Gemini synonym-suggestion modal — egress-gated, with a
user-curated review step; deferred here).

## Verification
- **pytest: 140** (138 + 2 new): a unit test for `strip_punctuation`, and an integration test using a
  punctuation-sensitive fake model where "resting-state" and "resting state" produce **identical**
  assignments (and the matching paper is assigned) — which only holds because the axis text is cleaned.
- Existing tests unaffected — `strip_punctuation` is a no-op on the (un-punctuated) test axis labels.
- No frontend change / rebuild (display still shows the user's verbatim text; only the embedding input
  is cleaned). No migration, no security audit (no new endpoint/egress/ingestion).

## User action
Re-score existing **punctuated** axes once: cleaning changes their text-version → they show **stale** →
re-score for stable results. Un-punctuated axes are unaffected (version unchanged, no stale prompt).
