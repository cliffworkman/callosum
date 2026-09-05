"""Evidence-hygiene research prototype (dev-only, no production code path).

Scratch study answering: what is the minimum deterministic preprocessing needed to turn extracted
scholarly PDF text into evidence-ready retrieval units while preserving exact source provenance?

Safety envelope, enforced by construction:
  * imports ``app.backend.*`` READ-ONLY and modifies nothing under ``app/`` or ``integrations/``
  * opens the library database read-only (``mode=ro``); never writes to it
  * every derived value lands in a SIDECAR database under ``.local/evidence-hygiene/``, keyed by
    ``(chunk_id, raw_sha, chunk_version)``, so a re-ingest invalidates derived rows rather than
    silently poisoning them
  * ``chunks.char_start`` / ``chunks.char_end`` are NEVER read -- they index a synthetic
    concatenation of emitted chunk texts (``extraction.py:230-232``), not any real document, so any
    adjacency or offset inference from them is wrong

Run as ``python -m tools.evidence_hygiene.<module>``.
"""
