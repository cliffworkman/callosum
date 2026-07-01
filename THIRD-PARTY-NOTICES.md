# Third-party notices

Callosum is licensed under the **GNU Affero General Public License v3.0** (see `LICENSE`). This file credits the
third-party work Callosum stands on, per the project's **credit-the-lineage** principle
(`.claude/CREDIT-THE-LINEAGE.md`). It currently documents the **citation & bibliography engine** (increment 106);
a fuller software-dependency NOTICE for the rest of the stack is a tracked follow-up (the "credit-help backfill",
`.claude/docs/future-tracks/opus4.8_future-tracks_credithelpbackfill.md`).

---

## Citation & bibliography engine (inc 106)

### citeproc-js
Formatted citations and bibliographies are rendered by **citeproc-js**, the reference CSL processor.
- © Frank G. Bennett, Jr. and contributors.
- Used under its **GNU AGPL-3.0** arm (citeproc-js is dual-licensed CPAL-1.0 OR AGPL-3.0; the AGPL arm combines
  cleanly with Callosum's AGPL-3.0). Source: <https://github.com/Juris-M/citeproc-js>.
- Obtained via the npm package [`citeproc`](https://www.npmjs.com/package/citeproc) (pinned; see `package.json` /
  `package-lock.json`), invoked locally as a Node sidecar (`app/backend/citations/citeproc_runner.js`).

### Citation Style Language (CSL) — the project
The styles and locales implement the **Citation Style Language** open standard. See the CSL project:
<https://citationstyles.org/>.

### Bundled CSL styles + locales — CC-BY-SA
The styles under `app/backend/citations/csl/styles/` and locales under `…/csl/locales/` are from the CSL
community repositories (<https://github.com/citation-style-language/styles>,
<https://github.com/citation-style-language/locales>) and are licensed
**Creative Commons Attribution-ShareAlike (CC-BY-SA)** — mostly 3.0 Unported, some 4.0
(<https://creativecommons.org/licenses/by-sa/3.0/>). They are **data the program operates on** (an aggregate), not
a derivative of Callosum's code, and **remain under CC-BY-SA — they are NOT relicensed under the AGPL.**
- Each style's embedded `<info>` block — its `<title>`, `<author>`/`<contributor>`, and `<rights>` metadata — is
  preserved **verbatim** in the bundled `.csl` files.
- **No modifications** have been made to the bundled styles or locales; they are committed as fetched from the CSL
  repositories. (If any style is ever modified, the change will be noted here and the file will remain CC-BY-SA.)

Bundled styles: APA (7th), MLA (9th), Chicago author-date (18th), Chicago notes-bibliography (18th), Harvard —
Cite Them Right (12th), IEEE, Nature. Bundled locales: en-US, en-GB.

---

## Word-processor adapters — Zotero `CSL_CITATION` field convention (inc 108)

The LibreOffice citation adapter (`adapters/libreoffice/`, the first of the three word-processor adapters) stores
each in-text citation as a live field whose payload is the cited work's **CSL-JSON**, and re-renders the whole
ordered set on demand. This **design follows the Zotero `ADDIN … CSL_CITATION` embedded-CSL-JSON field
convention** — reused as a documented *pattern*, **not code**. Zotero is © Corporation for Digital Scholarship and
contributors, free software under the AGPL-3.0 (<https://www.zotero.org/>). Crediting the prior tool's approach
(rather than appropriating its name) is the credit-the-lineage principle applied to a tool, not a paper.

---

## Methods — statistical-integrity checks (scholarly-method lineage)

These METHODS features **re-implement published algorithms in Python** (algorithms from papers are not
copyrightable); we credit the **method papers** in-context (each offers a one-click "add to library") and the
reference tools by citation — never by appropriating their names.

### p-curve (inc 126)
The collection-level evidential-value check is the **p-curve** method:
- Simonsohn, U., Nelson, L. D., & Simmons, J. P. (2014). *P-curve: A key to the file-drawer.* Journal of
  Experimental Psychology: General, 143(2), 534–547. <https://doi.org/10.1037/a0033242>.
- Re-implemented from the paper (right-skew Stouffer test + binomial test); the reference R implementation is
  **`scrutiny`** (Lukas Jung, <https://lhdjung.github.io/scrutiny/>) — credited, not reused by name or code.
- Surfaced via Daniël Lakens' **automated-review catalog** of meta-research tools
  (<https://lakens.github.io/automated_review_daily_build/>) and the review by Crone & Green (2025), *Tools of the
  data detective* (Personality & Social Psychology Review).

### statcheck (inc 95)
The per-paper NHST p-value recomputation is the **statcheck** method:
- Nuijten, M. B., Hartgerink, C. H. J., van Assen, M. A. L. M., Epskamp, S., & Wicherts, J. M. (2016). *The
  prevalence of statistical reporting errors in psychology (1985–2013).* Behavior Research Methods, 48, 1205–1226.
  <https://doi.org/10.3758/s13428-015-0664-2>.
- Re-implemented from the paper (the `statcheck` R package is by Nuijten & Epskamp) — credited, not reused.

### GRIM + GRIMMER (inc 127)
The data-consistency calculator implements the **GRIM** and **GRIMMER** methods:
- GRIM — Brown, N. J. L., & Heathers, J. A. J. (2017). *The GRIM test: A simple technique detects numerous
  anomalies in the reporting of results in psychology.* Social Psychological and Personality Science, 8(4),
  363–369. <https://doi.org/10.1177/1948550616673876>.
- GRIMMER — Anaya, J. (2016). *The GRIMMER test.* PeerJ Preprints 4:e2400v1; with the analytic refinement by
  Allard, A. (2018), *Analytic-GRIMMER.*
- Re-implemented from the papers (the reference R implementation is **`scrutiny`**, Lukas Jung,
  <https://lhdjung.github.io/scrutiny/>) — credited, not reused by name or code.

### Bayesian auditor — default JZS Bayes factor (inc 241)
The Bayesian auditor recomputes reported **default (JZS) Bayes factors** for inline t-test results:
- Rouder, J. N., Speckman, P. L., Sun, D., Morey, R. D., & Iverson, G. (2009). *Bayesian t tests for accepting and
  rejecting the null hypothesis.* Psychonomic Bulletin & Review, 16(2), 225–237.
  <https://doi.org/10.3758/PBR.16.2.225>. Credited + one-click added to the library from the panel.
- Re-implemented in Python from the paper (the closed form JASP and the **`BayesFactor`** R package — Morey, R. D.,
  & Rouder, J. N. — use) — credited, not reused by name or code. Surfaced via Daniël Lakens' automated-review catalog.

### Citation context / "smart citations" (inc 232, B4)
The **"How this paper is cited"** panel (support / contrast / mention over a paper's citing sentences) is a
**scite** analogue:
- scite — Nicholson, J. M., Mordaunt, M., Lopez, P., Uppala, A., Rosati, D., Rodrigues, N. P., Grabitz, P., &
  Rife, S. C. (2021). *scite: A smart citations index that displays the context of citations and classifies their
  intent using deep learning.* Quantitative Science Studies, 2(3), 882–898.
  <https://doi.org/10.1162/qss_a_00146>. Credited + one-click added to the library from the panel; the tool's name is
  not appropriated and its model is not reused — callosum classifies stance with its own local NLI.
- **Data source:** citing sentences (contexts) come from the **Semantic Scholar Academic Graph API**
  (Allen Institute for AI, <https://www.semanticscholar.org/>) — public bibliographic metadata; credited in-panel.

---

## Runtime & build dependencies (inc 181)
Callosum is built on the open-source projects below, each used under its own license (the authoritative text ships
with each project). Grouped by license:

**Python (backend, `requirements.txt`):**
- **MIT** — FastAPI, SQLAlchemy, Alembic
- **BSD-3-Clause** — Starlette, Uvicorn, httpx, scikit-learn, NumPy, SciPy
- **Apache-2.0** — sentence-transformers; google-genai (the optional Gemini client)
- **Apache-2.0 / MIT** (dual) — sqlite-vec
- **AGPL-3.0** (open edition; also offered commercially by Artifex) — **PyMuPDF** (`fitz`). Its copyleft is one
  reason Callosum itself is AGPL-3.0.

**JavaScript:**
- **MIT** — esbuild (build-time, `package.json`); React + ReactDOM (loaded at runtime from a CDN)
- **Apache-2.0** — pdf.js (PDF rendering, CDN)
- **AGPL-3.0** — citeproc-js (the citation engine; full credit in the *Citation & bibliography engine* section above)

**Models** Callosum downloads at first run (`all-MiniLM-L6-v2`, `cross-encoder/nli-MiniLM2-L6-H768`) are
distributed by their authors on the Hugging Face Hub under their own licenses; Callosum does not redistribute them.

---

## Corresponding source (AGPL §13)
Callosum is free software under the AGPL-3.0. The complete corresponding source is available at the project
repository; you may obtain it under the terms of the AGPL-3.0 (see `LICENSE`).
