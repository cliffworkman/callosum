# Evidence-unit replication amendment 03: embedding-store identity

Status: **FROZEN BEFORE SAMPLE SELECTION OR OUTCOME INSPECTION**

Parent amendment commit: `c49c43da5f3cd37dbe859cefd6232da89e574dd2`

The preregistered pre/post embedding digest script initially assumed an `embeddings.vector` column. Callosum stores
embedding metadata in `embeddings` and vector bytes in the sqlite-vec virtual table and its backing tables; there is
no `embeddings.vector` column. The attempted read failed before writing its receipt and did not mutate the study
database.

The immutable embedding check will hash, in deterministic row order:

1. every column of `embeddings`;
2. every row/column of `callosum_vec_embeddings_384_rowids`;
3. every row/column of `callosum_vec_embeddings_384_vector_chunks00`;
4. every row/column of `callosum_vec_embeddings_384_chunks` and `_info`.

Counts and SHA-256 values must match before and after migration/backfill. This corrects physical-storage discovery
only; all scientific hypotheses, sampling, reconstruction, metrics, and interpretation rules remain unchanged.
