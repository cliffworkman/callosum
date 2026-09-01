# Static online demo

The online demo is a build of the real Callosum React frontend over an immutable, versioned public snapshot. It
has no Python service, database, API credentials, analytics, AI provider, or live Callosum endpoint.

```text
Shared Callosum frontend
          |
   callosumFetch()
          |
    +-----+-----+
    |           |
FastAPI fetch   Static demo provider
(normal app)    (snapshot-v1.json)
```

`app/frontend/js/00_lib.jsx` is the only transport seam. Normal builds delegate to the browser's `fetch`; the
demo injects `demo-runtime.js`, which answers the same GET response shapes from the snapshot. Capability
differences live in `manifest.capabilities` and the per-surface `manifest.workspace_capabilities` map. Mutations and unknown reads return local errors and never become
network requests. The production and desktop builds do not load the demo runtime.

## What the visitor sees

The demo opens in the ordinary Library workspace. Visitors can search and filter the five-work library, open paper
metadata and bundled PDFs, and inspect each paper's saved statcheck, Transparency, mixed-model, Bayesian, and
meta-analysis results. The saved library also includes a real cosine-scored **Anomalous-is-bad bias** axis over all
five papers, automatic OpenAlex topic tags, locally generated c-TF-IDF tag suggestions for every paper, and a
five-item reading queue (one high priority, one normal, three unprioritized).
**My Publications** is scoped to the four Workman-authored papers in this curated demo corpus.
The Library's real **WIP** sub-workspace contains two prominently labeled synthetic drafts generated from a fresh
Callosum sandbox. Visitors can open their ordinary manuscript tabs and inspect structure state, tasks, all five
linked Library sources, activity, exact content checkpoints, reference-integrity state, and authentic saved runs
from all five deterministic manuscript checks. Reruns, edits, filesystem actions, and finding dispositions remain
disabled because the static artifact has no backend.
Selecting **Synthesize**—or the completed synthesis receipt in **Status**—opens
**“What is the anomalous-is-bad bias?”** with every saved sentence, citation, evidence quotation, source location,
coverage state, and verification result available for inspection. Its short Overview was generated from the
verified claims by Callosum's production Overview generator and every Overview sentence retains its claim trace.
The complete top-level application map remains
visible: My Publications, Library, Synthesize, Discover, Work, Help, and Settings, including every real subtab.
Each surface is centrally labeled as a saved view, browser-local preview, or visible orientation-only view.

The real **Critique** tab loads a saved deterministic scrutiny backbone for each paper, composed from its saved
method results. The real **Meta-Preregistration** tab shows He et al.'s confirmed OSF source and a twelve-row
deterministic crosswalk covering the study identity, timing, hypotheses, sampling, design, outcomes, analyses,
exclusions, missing data, and amendments. Rows retain both bounded excerpts, publication locations, comparison
basis, search scope, and uncertainty—never a compliance or author score. Saved, evidence-bounded AI triage helps
focus the display without changing the crosswalk. Reruns, new AI triage, and review edits remain unavailable.

The synthesis, evidence, coordinates, confidences, method results, verification states, and completed Status
receipt are prerecorded Callosum records. Run/rescan controls remain visible but disabled. Generating or deleting
a synthesis, importing/editing/deleting papers, annotations, provider configuration, keys, sync,
discovery/acquisition, external metadata, and desktop integrations are unavailable. The banner explains that the
saved results remain inspectable.

## Corpus and license audit

Every byte in `demo/` is public. Complete documents are included only after explicit license verification:

| Work | Bundled material | License and basis |
|---|---|---|
| He, Workman, He, & Chatterjee (2024), *What is good is beautiful (and what isn’t, isn’t): How moral character affects perceived facial attractiveness*. DOI 10.1037/aca0000454 | Complete author manuscript | [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/); the bundled PsyArXiv version has an explicit CC BY 4.0 license. The final DOI remains the canonical article link. |
| Workman et al. (2021), *Morality is in the eye of the beholder: the neurocognitive basis of the ‘anomalous-is-bad’ stereotype*. DOI 10.1111/nyas.14575 | Complete PDF | [CC BY-NC 4.0](https://creativecommons.org/licenses/by-nc/4.0/); the [PMC Open Access record](https://pmc.ncbi.nlm.nih.gov/articles/PMC8247878/) identifies the article as CC BY-NC. The public demo is noncommercial. |
| Rasset, Montalan, & Mange (2023), *Only human after all? a pre-registered study on gaze behavior and humanity attributions to people with facial difference*. DOI 10.1371/journal.pone.0295617 | Complete PDF | [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/); the [PLOS article](https://doi.org/10.1371/journal.pone.0295617) and [PMC record](https://pmc.ncbi.nlm.nih.gov/articles/PMC10715648/) state the license. The preregistration is at [OSF](https://osf.io/grytk). |
| He et al. OSF registration `b9faw` | Metadata and bounded evidence only; no complete registration | The registration has no explicit redistribution license. The snapshot stores verified metadata, twelve bounded commitment excerpts, the canonical OSF URL, and the license audit record. |
| Workman, Smith, Apicella, & Chatterjee (2022), *Evidence against the "anomalous-is-bad" stereotype in Hadza hunter gatherers*. DOI 10.1038/s41598-022-12440-w | Complete PDF | [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/); Scientific Reports is fully Gold Open Access — the Crossref license record and [Europe PMC record](https://europepmc.org/article/MED/35610269) (PMC9130266) both state CC BY 4.0. Added 2026-08-30 to reach the 4-paper minimum for a real `/my-publications/domains` decomposition (backlog demo-coverage fixwave, cap-domains). |
| Bilici, Paruzel-Czachura, Workman, Humphries, Hamilton, & Chatterjee (2026), *Changing the narrative: stories reduce biases against anomalous faces*. DOI 10.1186/s40359-026-04964-x | Metadata and bounded evidence only (title/authors/abstract/DOI); no bundled PDF | [CC BY-NC-ND 4.0](https://creativecommons.org/licenses/by-nc-nd/4.0/) — confirmed via the Crossref license record and the Semantic Scholar Graph API. The No-Derivatives clause does not permit redistributing full text/chunks, so only standard bibliographic metadata is stored, per this table's own `metadata-and-evidence-only` fallback (see the paragraph below). Added 2026-08-30 alongside the Hadza paper, for the same reason. |

Attribution, canonical URLs, notices, verification source/date, document hashes, and redistribution basis are
also present in the snapshot and generated `demo-about.html`. “Open access” alone is never treated as permission.
When adding a work, verify the license at the publisher or repository record, record that evidence in `CORPUS`,
and include full text only if redistribution is explicit. Otherwise set `bundled_material` to
`metadata-and-evidence-only`, omit the asset, and retain the canonical external link.

## Curate and export

Never export an ordinary working database. Build or copy a **dedicated curated demo database**, inspect it for
public-only content, add the licensed He et al. manuscript and bounded registration fixture when preparing a new
curated database, and run:

```powershell
python tools/demo/curate_good_beautiful_study.py `
  --source-db .local/nli-01-anomalous/good-beautiful-export-v2.sqlite `
  --confirm-public-demo-source
python tools/demo/generate_demo_library_state.py `
  --source-db .local/nli-01-anomalous/good-beautiful-export-v2.sqlite `
  --confirm-public-demo-source
python tools/demo/generate_demo_wip_state.py
python tools/demo/generate_demo_synthesis_state.py `
  --source-db .local/nli-01-anomalous/good-beautiful-export-v2.sqlite `
  --confirm-public-demo-source
python tools/demo/capture_demo_extended_state.py --confirm-public-demo-source
python tools/demo/capture_demo_prospection.py `
  --confirm-public-demo-source `
  --confirm-metadata-egress
python tools/demo/capture_demo_meta_reference.py `
  --confirm-public-demo-source `
  --confirm-metadata-egress
python tools/demo/triage_demo_state.py `
  --confirm-public-demo-source `
  --confirm-ai-egress
python tools/demo/export_demo_snapshot.py `
  --source-db .local/nli-01-anomalous/good-beautiful-export-v2.sqlite `
  --confirm-public-demo-source
```

Prepare that file as a dedicated curated copy with the attachment-label migration or newer; never migrate or
export an ordinary working database for this purpose. The library-state generator applies Callosum's production
`all-MiniLM-L6-v2` cosine scorer and local c-TF-IDF tag suggester, then validates the versioned
`library-state-v1.json` fixture. It defaults to cached model files; pass `--allow-model-download` only when
intentionally bootstrapping the public curation environment. Automatic topic tags are an explicit OpenAlex
allowlist in `tools/demo/curated_library.py`, not a build-time network dependency. The exporter then opens it read-only, uses explicit SQL
field whitelists, computes the saved deterministic method responses, copies only the five licensed assets declared
in `CORPUS`, verifies hashes and PDF signatures, validates shared live API models, rejects unknown fields, and
scans for secrets and machine paths. The acknowledgement is deliberately required. `curate_good_beautiful_study.py` is
an explicit, idempotent fixture-preparation step and never runs during an ordinary build. The same curated source
library-state fixture, and application version produce byte-identical JSON.

To change the showcased synthesis, create/verify it in the dedicated database, update the curated IDs and license
records if the corpus changed, regenerate the library state, then rerun the exporter. Do not put prose, citations,
evidence, tags, axis assignments, or queue records in a UI component.

The WIP generator never reads a working library. It migrates a new temporary database, inserts only the same five
allowlisted bibliographic records, scans the two public synthetic Markdown fixtures, then drives the real WIP
workflow, checkpoint, reference-link, and deterministic-check endpoints. Its strict `wip-state-v1.json` output
omits UUIDs and filesystem keys, replaces its temporary location with a virtual demo label, normalizes timestamps,
and is rejected if any sandbox path survives. The manuscript prose is curated fixture input; sections, tasks,
hashes, detector receipts, structured results, and findings are generated application state.

The Synthesize-state generator reads the dedicated database in SQLite read-only mode and validates the committed
snapshot. Critique responses are composed from the genuine saved method results. Registration classifications use
Callosum's production deterministic comparator and a whitelist-exported fixture whose publication excerpts must
still be found verbatim in the curated He et al. manuscript; regeneration fails if that evidence drifts. The strict state
records the OSF license audit, and the complete unlicensed registration never enters the artifact.

The extended-state capture migrates a fresh temporary database, inserts only the five public bibliographic
records, and drives Callosum's real discovery, journal, funding, saved-check, CRediT, and workbench endpoints. Its
strict response models reject extra fields. Volatile citation-provider refreshes are not required for deterministic
regeneration; unavailable graph evidence remains an explicit zero/empty result rather than fabricated coverage.

`triage_demo_state.py` is a separate, explicitly egress-authorized curation step. It sends only the already-public,
bounded Funding cards, paired Meta-Preregistration evidence, and verified synthesis claims through the production
triage and Overview generators. It saves provider/model/prompt provenance, claim traces, and a fingerprint of the
exact verified claims narrated by the Overview. Export fails with a regeneration instruction if those claims drift.
Ordinary snapshot exports and builds never invoke AI.

`capture_demo_prospection.py` likewise requires explicit metadata-egress authorization. It creates a fresh
five-paper database, resolves the public ORCID identity, confirms only the four Workman-authored demo papers, and
runs the production dashboard, citation-gap, emerging-citing-topic, and citing-author workflows against OpenAlex.
The same fresh author refresh supplies the headline metrics, publication and citation year charts, per-paper
counts, OpenAlex provenance, and graph surfaces. The saved responses retain graph evidence, scope, window dates,
caps, and coverage caveats; the static demo never refreshes them or reads the working library.

`capture_demo_meta_reference.py` creates another fresh five-paper sandbox and runs every published-paper
Meta-Reference path for each article: reference integrity, citation concentration with the production field
baseline, overlooked-work discovery/ranking, incoming citation context, and outgoing reference context. Public
DOIs and bibliographic metadata reach OpenAlex, Semantic Scholar, and Crossref; SPECTER ranking and NLI stance
classification run locally. A provider's genuine zero-result remains an inspectable saved outcome, while the
capture fails if a paper has no reference/concentration/overlooked coverage or no citation graph in either direction.

The current personal Feed has an additional human-review gate because subscription labels and cached titles may
be personally revealing. Generate a private review packet (JSON, CSV, SHA-256) under `.local`, inspect every row,
then approve exactly those bytes only if appropriate:

```powershell
python tools/demo/export_feed_review.py
python tools/demo/export_feed_review.py `
  --approve-digest <reviewed-sha256> `
  --candidate .local/demo-feed-review/candidate.json
```

The first command never changes public demo files. Approval fails if one byte changed and is required before Feed
records can enter `extended-state-v1.json`.

## Coverage program

`coverage-v1.json` is the machine-validated catalogue of result-bearing workspaces. The finer-grained
`experience-coverage-v1.json` classifies every capability claimed by `www/showcase.html` (and every homepage
feature link) as saved and inspectable, partial, browser-local, legitimately live/external-only,
scientifically inapplicable, or missing. `python tools/qa/check_demo_experience_coverage.py` fails on an added,
removed, duplicated, or unclassified website claim; the demo build runs the same check and publishes the ledger
with the artifact. A partial or missing classification is an audit finding, never an implied success.

The workspace catalogue additionally fails the build if a registered workspace is missing or if its
saved/disabled status disagrees with the centralized capability map. Current Wave 1 state:

| Surface | Current saved coverage | Next snapshot wave |
|---|---|---|
| Library | Five curated records (three full-text plus two added 2026-08-30: a CC BY complete-PDF paper and a CC BY-NC-ND metadata-and-evidence-only paper), licensed PDFs, methods, axes, tags, queue, My Publications, annotations, saved searches, GRIM/DEBIT/repeated values, reference state | Deep reader/maintenance parity and lock audit in progress |
| WIP | Two synthetic drafts; structure, tasks, sources, checkpoints, activity, five deterministic checks, reference state, funding and journal receipts | Provider-dependent WIP graph results only when authentic public evidence can be captured deterministically |
| Synthesize | Evidence-linked Ask spanning all three original curated papers with a genuine verified + flagged (weak-retrieval) citation mix; saved per-paper Critique; saved He et al. OSF source and twelve-row crosswalk | A single sentence citing more than one paper at once, a real contradicted example, bounded registration inspector, and stronger Critique example are open findings |
| Discover | Reviewed saved Feed, Search, Journals, Funding with bounded AI fit triage, followed-author identity, My Publications prospection (now 4 confirmed papers, real /my-publications/domains decomposition), Wanted, literature Gaps, axis Overlooked lens, and a saved beyond-library candidate | Crossref search lacks an authentic saved example; `cap-pdf-search` claims a feature (in-reader PDF find) that doesn't exist yet in the app -- backlogged, not a demo gap |
| Work | Saved Cite, Meta-Reference, CRediT, Statements, and Meta-Analyze project/results | Authentic extraction provenance, multi-citation breadth, and editor-only orientation remain under review |

New coverage belongs in generated state and shared response contracts, never in demo-only UI prose. This table is
the audit record; a visible-disabled surface is a deliberate limitation, not implied coverage.

## Build and test locally

```powershell
npm ci
python tools/demo/build_demo.py --output .local/demo-preview/callosum-demo --base-path /callosum-demo/
python -m http.server 8081 --directory .local/demo-preview
# open http://127.0.0.1:8081/callosum-demo/
```

For a simple root-path local preview, use `--base-path /` and serve `dist-demo` itself. A realistic subpath smoke
test and all contract/security checks are automated:

```powershell
python tools/qa/check_demo_experience_coverage.py
pytest tests/test_demo_snapshot.py -q
pytest tests/test_demo_experience_coverage.py -q
$env:CALLOSUM_RUN_E2E='1'; pytest tests/e2e/test_demo_static.py -q
```

The build validates the committed snapshot, assembles the shared frontend, vendors pinned React/ReactDOM/PDF.js,
emits `dist-demo/`, scans text assets for CDN/loopback markers, and writes CSP/security headers. The browser smoke
loads a direct synthesis route, reloads it, opens evidence in the PDF, and asserts zero console errors and zero
requests outside the static base path.

## Schema drift

`app/backend/demo_snapshot.py` embeds the live Pydantic response models and forbids extra fields at every snapshot
layer. A changed live contract therefore fails tests or the demo build. The runtime also rejects incompatible
snapshot schema versions. Increment `SNAPSHOT_SCHEMA_VERSION` only for an intentional contract migration and
either add an explicit migration or regenerate; malformed or old data is never accepted silently. Ordinary JSX
or CSS improvements flow into the demo without snapshot regeneration.

## Deploy

Generation/build and deployment are separate. The manual `demo-static.yml` workflow always validates and uploads
the built artifact; it deploys to GitHub Pages only when its `deploy` input is explicitly enabled:

```powershell
gh workflow run demo-static.yml -f base_path=/callosum/demo/ -f deploy=false
gh workflow run demo-static.yml -f base_path=/callosum/demo/ -f deploy=true
```

Before the first deployment, configure GitHub Pages to use **GitHub Actions** and confirm the repository subpath.
No ordinary frontend build writes or publishes public files.
