# Increment 181 — third-party software NOTICE pass (credit-the-lineage Lane B, backlog #8)

`THIRD-PARTY-NOTICES.md` credited citeproc-js, the CSL data, and the scholarly **methods** (Lane A), but listed
**none of the runtime/build software dependencies** — a real gap for a public AGPL repo (compliance + the
credit-the-lineage Lane B).

## Implemented
- A **Runtime & build dependencies** section in `THIRD-PARTY-NOTICES.md`, crediting every shipped Python
  (`requirements.txt`) + JS (`package.json` + CDN) dependency with its license, grouped: MIT (FastAPI, SQLAlchemy,
  Alembic, esbuild, React/ReactDOM), BSD-3-Clause (Starlette, Uvicorn, httpx, scikit-learn, NumPy, SciPy),
  Apache-2.0 (sentence-transformers, google-genai, pdf.js), Apache-2.0/MIT (sqlite-vec), AGPL-3.0 (**PyMuPDF** —
  noted as a reason Callosum is AGPL; citeproc-js, cross-referenced to its existing section). Plus a note that the
  first-run **models** are distributed by their authors on the HF Hub (Callosum doesn't redistribute them).
- Licenses are the standard published ones (each project's own license is authoritative — stated in the section).

## Gates
- **Docs-only** — `THIRD-PARTY-NOTICES.md` only; no app/migration/egress/surface change; no audit/Principles/QA
  trigger; pytest unaffected (**619**). Strengthens credit-the-lineage (values-aligned).

## #8 status
Lane A (in-context **method** credit + add-to-library) done across statcheck/p-curve/GRIM (inc 180); Lane B
(software-dependency NOTICE) done here. The retraction / gap-finder surfaces are **data-source-driven** (Retraction
Watch / OpenAlex), not single-method-paper-driven, so the "add the source paper" pattern doesn't fit them — their
sources are credited at the NOTICE/data level instead. **#8 is effectively complete.**
