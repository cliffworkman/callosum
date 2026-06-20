# Increment 08 Notes

## Implemented

- Added abstract-first automatic clustering in `app/backend/clustering/abstract_clustering.py`.
- Added relative axis-assignment modes to `app/backend/clustering/axis_scoring.py`.
- Added an axis-calibration probe to `tools/validation_harness.py`.
- Added hermetic tests for abstract clustering, relative assignment, and calibration reporting.
- Added `scikit-learn>=1.4,<2` to `pyproject.toml`.

## Abstract-First Clustering

- Algorithm: `sklearn.cluster.AgglomerativeClustering` with cosine distance and average linkage.
- Representation: existing paper-level title/abstract embeddings.
- Default cluster count: `round(sqrt(n_papers))`, clamped to `1..min(n_papers, 12)`.
- Persistence: provisional cluster nodes use `axis_id=NULL`, `parent_id=NULL`, labels like `[auto] Abstract cluster 1`, and descriptions containing the algorithm and cluster count.
- Reruns delete and replace only previous `[auto] Abstract cluster ...` nodes; user axis nodes are left intact.
- BERTopic and LLM cluster labeling are deferred.

## Relative Axis Assignment

- Existing absolute-threshold behavior remains available with `assignment_mode="absolute"`.
- Added `assignment_mode="top_n"` with `top_n`.
- Added `assignment_mode="largest_gap"` with `minimum_gap`.
- Default mode is `largest_gap`, because real embedding scores often have a noisy mid-score tail and a relative score break is safer than a fixed absolute cutoff.
- If largest-gap mode finds no sufficient gap and the top score is below `assignment_threshold`, no assignments are recorded; this prevents a flat noisy 0.6 tail from becoming persisted uncertainty.
- The uncertainty tier is preserved: selected scores above `assignment_threshold` are `assigned`; selected scores above `uncertainty_threshold` are `uncertain`; unselected scores remain visible in result scores but are not persisted.

## Calibration Probe

- CLI option: `--axis`, accepting either `Label::description` or a plain label.
- The probe scores all papers against each provided axis and reports sorted scores, rank, title, gap-to-next, and largest adjacent score gap.
- It does not choose a threshold automatically.
- It uses the same scratch database/report path as the validation harness and `SentenceTransformerEmbeddingModel(local_files_only=True)` when no test model is supplied.

## Real-Data Run

- I did not run the calibration probe against the real library in this increment.
- Tests used synthetic fixtures only.

## Ambiguities / Questions

- None surfaced.
- No schema gap required a migration.

## Raw Pytest Output

Targeted clustering / axis / harness suite:

```text
.............                                                            [100%]
13 passed in 13.38s
```

Full suite:

```text
...................................                                      [100%]
35 passed in 21.99s
```
