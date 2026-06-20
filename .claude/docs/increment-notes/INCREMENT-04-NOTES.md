# Increment 04 Notes

## Implemented

- Local embedding package under `app/backend/embeddings/`.
- `EmbeddingModel` protocol plus `SentenceTransformerEmbeddingModel`, defaulting to `all-MiniLM-L6-v2`.
- Configurable model name, model version, and normalization setting.
- Text normalization setting: `whitespace-lower-v1`.
- Chunk embedding generation from existing `chunks` rows.
- Paper embedding generation from abstract/metadata text for abstract-embedded or metadata-only papers.
- One `embeddings` metadata row per vector, populated with target, model, dimension, normalization, source text version, source chunk version where applicable, vector store kind, and vector store reference.
- `VectorStore` protocol with `add()` and `search()` methods.
- sqlite-vec-backed vector store that creates dimension-specific virtual tables inside the same SQLite database.
- In-memory fake vector store for network-free tests and interface swap coverage.
- Similarity search over chunks and papers, returning score plus source identifiers: paper ID, chunk ID, page span, and bbox JSON where applicable.
- Stale embedding detection for model/version/dimension/normalization changes and changed chunk versions.

## Deferred

- Automatic re-embedding of stale records.
- Embeddings for axes, summary sentences, and claims.
- Clustering, BERTopic, summarization, Gemini/LLM calls, NLI verification, OpenAlex/Semantic Scholar, FastAPI routes, and frontend/pdf.js.
- sqlite-vec migration management beyond lazy virtual-table creation.

## Model Choice

- Runtime default: `all-MiniLM-L6-v2`, matching `pipelines/embeddings/README.md` as the fast first-pass model.
- Stronger models such as `BAAI/bge-base-en-v1.5` can be used by passing a different model name/version to `SentenceTransformerEmbeddingModel`.
- `sentence-transformers` may download model weights on first use if they are not already cached. No model weights are committed.

## Vector Store Choice

- Default implemented backend: `sqlite-vec`, consistent with `data/vector-store/README.md`.
- Vectors live in sqlite-vec virtual tables named by dimension, e.g. `callosum_vec_embeddings_4`.
- `embeddings.vector_store_ref` stores `<table_name>:<embedding_id>`.
- The vector-store boundary is protocol-based so FAISS or another backend can replace sqlite-vec later without changing embedding callers.

## Network-Free Tests

- Tests use a deterministic `FakeEmbeddingModel`; they do not import or download sentence-transformer model weights.
- Tests generate tiny PDFs programmatically and use existing extraction/chunking code.
- Tests exercise the real local `sqlite-vec` extension package for the sqlite vector-store path.
- `sqlite-vec` was installed locally for the test run. The first pip attempt hit a local certificate verification issue; retrying with trusted PyPI hosts succeeded.

## Schema Notes

- No schema change was needed.
- The existing `embeddings` table fit this increment as designed.
- Paper text staleness is represented by a coarse `paper-metadata-v1` source text version. Fine-grained metadata-change invalidation is deferred.

## Raw Pytest Output

```text
============================= test session starts =============================
platform win32 -- Python 3.12.7, pytest-7.4.4, pluggy-1.0.0
rootdir: C:\Users\cliff\Dropbox\Dropbox\01_Work\callosum
configfile: pyproject.toml
testpaths: tests
plugins: anyio-4.2.0
collected 14 items

tests\test_embeddings.py ....                                            [ 28%]
tests\test_pdf_processing.py ...                                         [ 50%]
tests\test_persistence_core.py ......                                    [ 92%]
tests\test_zotero_importer.py .                                          [100%]

============================= 14 passed in 16.16s =============================
```
