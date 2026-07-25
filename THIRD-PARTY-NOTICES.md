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

### Official CSL 1.0.2 validation schemas — MIT
Local style installation validates against the official CSL 1.0.2 RELAX NG schema and Schematron macro rules
from <https://github.com/citation-style-language/schema>. The generated XML schema, Schematron file, and complete
MIT license are preserved under `app/backend/citations/csl/schema/`.

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

### MEDLINE journal-title abbreviations — U.S. National Library of Medicine

The compressed index at `app/backend/citations/data/medline_journals.json.gz` is a modified/distilled snapshot
of NLM's public `J_Medline.txt` catalog, last modified **2026-07-25**. It retains only normalized full-title and
ISSN lookup keys mapped to NLM's `MedAbbr` value; it omits the source records' other fields. Runtime citation
rendering reads this bundled snapshot locally and does not contact NLM.

- Source: <https://ftp.ncbi.nlm.nih.gov/pubmed/J_Medline.txt>
- Refresh script: `tools/update_medline_journal_abbreviations.py`
- **Courtesy of the U.S. National Library of Medicine.** NLM does not endorse Callosum.
- The snapshot may not reflect NLM changes made after the date above. NLM provides the data without warranties;
  its general download terms apply: <https://www.nlm.nih.gov/databases/download/terms_and_conditions.html>.

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

### Bayesian auditor — default Bayes factors (inc 241 / 243)
The Bayesian auditor recomputes reported **default Bayes factors** for inline t-test and correlation results:
- **t-test** — Rouder, J. N., Speckman, P. L., Sun, D., Morey, R. D., & Iverson, G. (2009). *Bayesian t tests for
  accepting and rejecting the null hypothesis.* Psychonomic Bulletin & Review, 16(2), 225–237.
  <https://doi.org/10.3758/PBR.16.2.225>.
- **Pearson correlation** — Ly, A., Verhagen, J., & Wagenmakers, E.-J. (2016). *Harold Jeffreys's default Bayes factor
  hypothesis tests: Explanation, extension, and application in psychology.* Journal of Mathematical Psychology, 72,
  19–32. <https://doi.org/10.1016/j.jmp.2015.06.004> (the exact closed form of Wetzels, R., & Wagenmakers, E.-J.
  (2012), Psychonomic Bulletin & Review, 19, 1057–1064).
- Both credited + one-click added to the library from the panel. Re-implemented in Python from the papers (the closed
  forms JASP and the **`BayesFactor`** R package — Morey, R. D., & Rouder, J. N. — use) — credited, not reused by name
  or code. The correlation recompute is verified exactly against the **`pingouin`** `bayesfactor_pearson` value
  (a dev-only verification tool, not a runtime dependency). Surfaced via Daniël Lakens' automated-review catalog.

### LMM-reporting completeness auditor (inc 247, #23)
The mixed-model reporting auditor is a consumer-side reading aid — it reads reported text only and never runs a model,
an imputation, or a sensitivity analysis. Each check credits its methodological basis in-context and offers the source
to the library:
- Random-effects structure — Barr, D. J., Levy, R., Scheepers, C., & Tily, H. J. (2013). *Keep it maximal.* Journal of
  Memory and Language, 68(3), 255–278. <https://doi.org/10.1016/j.jml.2012.11.001>; and Matuschek, H., Kliegl, R.,
  Vasishth, S., Baayen, H., & Bates, D. (2017). *Balancing Type I error and power in linear mixed models.* Journal of
  Memory and Language, 94, 305–315. <https://doi.org/10.1016/j.jml.2017.01.001>.
- Degrees-of-freedom / inference method — Luke, S. G. (2017). *Evaluating significance in linear mixed-effects models
  in R.* Behavior Research Methods, 49(4), 1494–1502. <https://doi.org/10.3758/s13428-016-0809-y>.
- Convergence & estimation — Bates, D., Mächler, M., Bolker, B., & Walker, S. (2015). *Fitting Linear Mixed-Effects
  Models Using lme4.* Journal of Statistical Software, 67(1), 1–48. <https://doi.org/10.18637/jss.v067.i01>.
- Marginal vs conditional R² — Nakagawa, S., & Schielzeth, H. (2013). *A general and simple method for obtaining R²
  from generalized linear mixed-effects models.* Methods in Ecology and Evolution, 4(2), 133–142.
  <https://doi.org/10.1111/j.2041-210X.2012.00261.x>.
- Missing-data sensitivity — FDA / ICH E9(R1) addendum (*Estimands and Sensitivity Analysis in Clinical Trials*);
  Troendle et al. (2025); Cro, S., Morris, T. P., Kenward, M. G., & Carpenter, J. R. (2020), Statistics in Medicine;
  Moreno-Betancur, M., & Chavance, M. (2016), Statistical Methods in Medical Research.
- Credited + one-click added to the library from the panel. Surfaced via Daniël Lakens' automated-review catalog.

### Meta-analysis reporting auditor (inc 249, #36)
The meta-analysis reporting auditor is a consumer-side reading aid — it reads a published meta-analysis's reported text
only and never pools, models heterogeneity, meta-regresses, computes an effect size, or does bias inference. Each check
credits its methodological basis in-context and offers the source to the library:
- Effect sizes & general — Borenstein, M., Hedges, L. V., Higgins, J. P. T., & Rothstein, H. R. (2009). *Introduction
  to Meta-Analysis.* Wiley; and Viechtbauer, W. (2010). *Conducting meta-analyses in R with the metafor package.*
  Journal of Statistical Software, 36(3), 1–48. <https://doi.org/10.18637/jss.v036.i03>.
- Model (fixed vs random-effects) — DerSimonian, R., & Laird, N. (1986). *Meta-analysis in clinical trials.* Controlled
  Clinical Trials, 7(3), 177–188. <https://doi.org/10.1016/0197-2456(86)90046-2>; and IntHout, J., Ioannidis, J. P. A.,
  & Borm, G. F. (2014). *The Hartung-Knapp-Sidik-Jonkman method …* BMC Medical Research Methodology, 14, 25.
  <https://doi.org/10.1186/1471-2288-14-25>.
- Heterogeneity (I² / τ² / Q) — Higgins, J. P. T., Thompson, S. G., Deeks, J. J., & Altman, D. G. (2003). *Measuring
  inconsistency in meta-analyses.* BMJ, 327(7414), 557–560. <https://doi.org/10.1136/bmj.327.7414.557>.
- Publication bias — Egger, M., Davey Smith, G., Schneider, M., & Minder, C. (1997). *Bias in meta-analysis detected by
  a simple, graphical test.* BMJ, 315(7109), 629–634. <https://doi.org/10.1136/bmj.315.7109.629>; Duval, S., & Tweedie,
  R. (2000). *Trim and fill.* Biometrics, 56(2), 455–463. <https://doi.org/10.1111/j.0006-341X.2000.00455.x>; and
  Sterne, J. A. C., et al. (2011). *Recommendations for examining and interpreting funnel plot asymmetry …* BMJ, 343,
  d4002. <https://doi.org/10.1136/bmj.d4002>.
- Sensitivity / influence — Viechtbauer, W., & Cheung, M. W.-L. (2010). *Outlier and influence diagnostics for
  meta-analysis.* Research Synthesis Methods, 1(2), 112–125. <https://doi.org/10.1002/jrsm.11>.
- Study count & search/selection reporting — Page, M. J., et al. (2021). *The PRISMA 2020 statement.* BMJ, 372, n71.
  <https://doi.org/10.1136/bmj.n71>.
- Credited + one-click added to the library from the panel. Surfaced via Daniël Lakens' automated-review catalog.

### Transparency-signals auditor (inc 250, #44)
The transparency-signals auditor is a consumer-side reading aid — it reads a paper's reported text only and detects
whether it *discloses* seven open-science artifacts (data/code availability, conflict-of-interest, funding, protocol/
trial registration, preregistration, "available upon request"). It never runs anything, scores a paper, or accuses the
authors; a not-detected row is a prompt to look. The rule-based detectors are derived from published, credited tools:
- Data & code availability detection — Riedel, N., Kip, M., & Bobrov, E. (2020). *ODDPub — a text-mining algorithm to
  detect data sharing in biomedical publications.* Data Science Journal, 19, 42. <https://doi.org/10.5334/dsj-2020-042>.
- Conflict-of-interest, funding & registration indicators — Serghiou, S., Contopoulos-Ioannidis, D. G., Boyack, K. W.,
  Riedel, N., Wallach, J. D., & Ioannidis, J. P. A. (2021). *Assessment of transparency indicators across the
  biomedical literature: How open is open?* PLOS Biology, 19(3), e3001107.
  <https://doi.org/10.1371/journal.pbio.3001107> (the *rtransparent* tool).
- Preregistration — Nosek, B. A., Ebersole, C. R., DeHaven, A. C., & Mellor, D. T. (2018). *The preregistration
  revolution.* Proceedings of the National Academy of Sciences, 115(11), 2600–2606.
  <https://doi.org/10.1073/pnas.1708274114>.
- Credited + one-click added to the library from the panel. Surfaced via Daniël Lakens' automated-review catalog.

### Effect-size converter (inc 252) — meta-analysis workbench SP1
The effect-size converter turns one study's reported statistics into a common meta-analytic metric + variance + a 95%
CI, using standard formulas, with the conversion path shown and the source cited in-context. It converts one study at
a time — it never pools, models heterogeneity, or does bias inference. Formula lineage (credited + one-click library-
addable from the panel):
- **The conversion formulas + variances** — Borenstein, M., Hedges, L. V., Higgins, J. P. T., & Rothstein, H. R.
  (2009). *Introduction to Meta-Analysis.* Wiley. ISBN 978-0-470-05724-7.
- **The `metafor` R package** (the standard implementation these formulas underlie) — Viechtbauer, W. (2010).
  *Conducting meta-analyses in R with the metafor package.* Journal of Statistical Software, 36(3), 1–48.
  <https://doi.org/10.18637/jss.v036.i03>. Credited, not reused — Callosum re-implements the formulas in Python.
- **Fisher's z transform** — Fisher, R. A. (1915). *Frequency distribution of the values of the correlation
  coefficient in samples from an indefinitely large population.* Biometrika, 10(4), 507–521.
- **The Hedges small-sample correction (J)** — Hedges, L. V. (1981). *Distribution theory for Glass's estimator of
  effect size and related estimators.* Journal of Educational Statistics, 6(2), 107–128.
- **Estimating an SD from an IQR** — the normal-quantile rule (Cochrane Handbook; Higgins et al.), with Wan, X., Wang,
  X., Liu, J., & Tong, T. (2014). *Estimating the sample mean and standard deviation from the sample size, median,
  range and/or interquartile range.* BMC Medical Research Methodology, 14, 135. <https://doi.org/10.1186/1471-2288-14-135>.
- **The zero-cell continuity correction** — Haldane, J. B. S. (1940) / Anscombe, F. J. (1956).
- **The log-odds↔d approximation** — Hasselblad, V., & Hedges, L. V. (1995). *Meta-analysis of screening and
  diagnostic tests.* Psychological Bulletin, 117(1), 167–178.

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

### PUBLISHERS "where to submit" journal-finder (inc 245, #40)
The journal-matching tool draws on public bibliographic metadata + a scientific-paper embedding model:
- **OpenAlex** (<https://openalex.org/>, CC0) — journal/source metadata (OA color, APC, open-impact stats, ISSNs,
  topics) via the `/topics`, `/works`, and `/sources` endpoints. Public metadata; polite-pool `mailto`.
- **DOAJ — Directory of Open Access Journals** (<https://doaj.org/>) — journal-level facts (APC, waiver, license,
  the DOAJ Seal) via the public journals API.
- **SPECTER** — the scientific-document embedding model (`sentence-transformers/allenai-specter`, Allen Institute for
  AI; Cohan, Feldman, Beltagy, Downey & Weld, *SPECTER: Document-level Representation Learning using Citation-informed
  Transformers*, ACL 2020) — runs **locally** to match the abstract to candidate journals; the abstract is never
  transmitted. Distributed by its authors on the Hugging Face Hub under its own license; Callosum does not redistribute it.

### Overlooked-work lens (inc 279, #37)
The per-axis lens surfaces external works highly relevant to an axis but under-cited for their vintage — making the
literature's attention machinery inspectable rather than letting citation counts silently stand in for relevance. It
operationalizes the **Matthew effect in science** (cumulative advantage in citation/recognition):
- Merton, R. K. (1968). *The Matthew Effect in Science.* Science, 159(3810), 56–63.
  <https://doi.org/10.1126/science.159.3810.56>. Credited in-context on the panel. It is a **signal, not a verdict**:
  two separate visible inputs (local relevance + citations-vs-same-vintage percentile), never fused, never author-directed.
- **OpenAlex** (<https://openalex.org/>, CC0) — a topic's works (id, title, year, cited-by count, abstract inverted
  index) via `/topics` + `/works`. Public metadata; polite-pool `mailto`. Candidate abstracts are embedded **locally**
  (default `all-MiniLM-L6-v2`); no library text is transmitted.

---

## Runtime & build dependencies (inc 181)
Callosum is built on the open-source projects below, each used under its own license (the authoritative text ships
with each project). Grouped by license:

**Python (backend, `requirements.txt`):**
- **MIT** — FastAPI, SQLAlchemy, Alembic
- **BSD-3-Clause** — Starlette, Uvicorn, httpx, lxml, scikit-learn, NumPy, SciPy
- **Apache-2.0** — sentence-transformers; google-genai (the optional Gemini client)
- **Apache-2.0 / MIT** (dual) — sqlite-vec
- **AGPL-3.0** (open edition; also offered commercially by Artifex) — **PyMuPDF** (`fitz`). Its copyleft is one
  reason Callosum itself is AGPL-3.0.

**JavaScript:**
- **MIT** — esbuild (build-time, `package.json`); React + ReactDOM (loaded at runtime from a CDN)
- **Apache-2.0** — pdf.js (PDF rendering, CDN)
- **AGPL-3.0** — citeproc-js (the citation engine; full credit in the *Citation & bibliography engine* section above)

**Models** Callosum downloads at first run (`all-MiniLM-L6-v2`, `cross-encoder/nli-MiniLM2-L6-H768`, and
`sentence-transformers/allenai-specter` for the overlooked-work + where-to-submit tools) are distributed by their
authors on the Hugging Face Hub under their own licenses; Callosum does not redistribute them.

---

## Corresponding source (AGPL §13)
Callosum is free software under the AGPL-3.0. The complete corresponding source is available at the project
repository; you may obtain it under the terms of the AGPL-3.0 (see `LICENSE`).
