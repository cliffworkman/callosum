# Website review, inc 624 (2026-11-01)

Self-review by the implementing session. It is not an independent review, and it does not discharge the independent security
review still owed for the integrated modernization work.

## Baseline
| Item | Value |
|---|---|
| Last accepted review | inc 603, `c7a7c10b`, 2026-09-24 |
| Source fingerprint then | `f6022d6596cfa83651363c0b25e1730b1ba4723fc54efcab3e8ac8d551911d65` |
| Its note | "Reviewed cap-import and the Library map: the unverified DOI review correction changes no advertised acquisition capability or published screenshot. Candidate lookup remains explicit; packaged Mac acceptance of this local fix is pending." |
| Administrative decline, kept for history | 2026-10-31, `e7c30c5a`, inc 615, covering backend provisioning only |
| Published release | v0.5.16, tag target `2f01feef`, published 2026-10-05, not a pre-release. `c7a7c10b` is an ancestor |
| Reviewed head | `b9a631e5` plus this increment's corrections. Proposed 0.6.0 work is implemented there and unreleased |

## Drift inventory, `c7a7c10b..b9a631e5`
36 commits. The gate's fingerprint domain changed in 20 files (+552/-20). Adapters, `tui/` and `mcp_server/` did not change.

| File | Lines added | In v0.5.16? |
|---|---|---|
| `app/backend/help/help_content.md` | 35 | Part. 21 lines are after the tag |
| `app/frontend/js/35j_modernization.jsx` | 125 | No |
| `app/frontend/js/35i_retrieval_profiles.jsx` | 129 | No |
| `app/frontend/js/35h_browser_capture.jsx` | 71 | Part |
| `app/frontend/js/04f_modernization_logic.jsx` | 50 | No |
| `app/frontend/js/20e_model_provenance.jsx` | 34 | No |
| `app/frontend/js/10l_import_queue.jsx` | 28 | Yes |
| `app/frontend/js/04e_whatsnew.jsx` | 26 | No |
| `app/frontend/js/04c_status.jsx` | 24 | No |
| `app/frontend/js/03b_library_identity.jsx` | 19 | No |
| `app/frontend/js/00_bootstrap.jsx` | 8 | No |
| `app/frontend/js/30c_frame.jsx` | 4 | No |
| `app/frontend/js/40_app.jsx` | 4 | No |
| `app/frontend/js/20_synthesis.jsx`, `20c_synthesis_results.jsx` | 3 each | No |
| `app/frontend/styles.css` | 3 | Part |
| `app/frontend/js/10_pdf_layer.jsx`, `35_settings.jsx` | 2 each | `35_settings` part |
| `app/frontend/js/18_help.jsx`, `20d_scoped_ask.jsx` | 1 each | No |

Outside the fingerprint: `www/` had changed only in `showcase-coverage.json` since the review, `README.md` changed only before the
v0.5.16 tag (+28/-7), and `app/frontend/whatsnew.json` holds a staged 0.6.0 entry.

The website text was older than the drift suggests. Most findings below were already wrong at inc 603, because the gate checks hashes
and counts, not what the words or pixels say.

## Claim review
Classes: **A** accurate for 0.5.16; **B** accurate for 0.6.0, not yet released; **C** accurate only with a stated limitation;
**D** illustrative and needing identification; **E** incorrect, outdated or unsupported, corrected here; **F** no longer applicable.

| Surface | Claim | Class | Evidence | Outcome |
|---|---|---|---|---|
| Landing | "backed by 2,098 tests" (twice) | E | 3490 passed on the accepted 0.5.16 Browser Capture head | "more than 3,400 automated tests" |
| Landing, stance | "installers are unsigned" | E | `FIRST-LAUNCH-NOTE.md`: Windows unsigned, macOS ad-hoc signed and not notarized | Corrected |
| Download | "These builds are unsigned … one-time trust warning" | E | Same. The OS "may block" install or launch | Corrected, and tells readers to use the official release |
| Download | Three platform buttons | E | The release ships `Callosum-macos-x64.dmg`, and Intel Mac was missing | Intel button added |
| Download | "No Python, no command line — just an installer" | C | `python_runtime.rs` downloads the runtime at first run. Windows archive is 383 MB | Heading kept. Network and download disclosure added |
| Find | "Search Crossref & PubMed" (twice) | E | `discovery/providers.py`, released inc 599: also arXiv, Europe PMC, PsyArXiv | Corrected |
| Local-first | "every network action explicit and inspectable" | E | Updater, runtime and model downloads, automatic retraction checks on import | Now: library text and PDFs leave only through explicit doors |
| Privacy, doors | Doors list | C | As above. None sends library text | Downloads and automatic identifier lookups disclosed |
| Privacy | "A weaker model affects draft quality — never which citations get accepted" | E | Model proposes the candidates, so this overclaimed | Now: the generating model does not set verification status |
| Commitments | "the deterministic layer decides what holds" | E | NLI is probabilistic, and invariant 4 leaves the decision to the reader | Now: local checks set status, you decide what holds |
| Core feature | Sentences "labeled verified, contrasted, flagged, or contradicted" | C | Invariants 1 and 4 | Added: model-derived signals, not proof |
| Showcase | "Sentence-level claims, independently checked" | C | Same | Retitled, with the same caveat |
| Showcase | "Every long operation leaves a receipt" | E | Routine folder scans are deliberately excluded (invariant 5) | Now "Long operations", with the exception stated |
| Showcase | "The application keeps the connection state visible" | E | The image and app show setup state, not live connection state | Retitled |
| Showcase | Statements "funding and CRediT" | E | The tab covers seven disclosures. CRediT has its own tab | Corrected |
| Showcase | "August 2026" eyebrow | E | Stale date | "Callosum 0.5.16" |
| Source install | "read-only MCP server" | E | `mcp_server/server.py`: 5 read tools plus 4 gated write tools, off by default | Corrected |
| How It Works | "current models", "Default model" | A once labelled | True of 0.5.16, not of the proposed 0.6.0 Automatic | Labelled 0.5.16 |
| How It Works | "`bge-base-en-v1.5` is supported" | E | No constant, Settings choice or pin. `model_runtime.py` calls it an unpinned alternate | Removed |
| How It Works | "model versions" stored | E | 0.5.16 stores embedding, chunk and verification versions. Named-model provenance is 0.6.0 | Now "embedding and verification versions" |
| How It Works | Arctic S, DeBERTa, MiniLM, MiniLM2, Qwen2.5, modernization | B | Incs 608-622, `DEBERTA_RELEASE_GATES` has `packaged_runtime_acceptance: False` | New note, labelled "Planned for 0.6.0, not yet released" |
| How It Works | Thresholds 0.70, 1.00, 0.55, 0.55 | A | `VerificationConfig`, pinned by test | Kept |
| How It Works | "probabilistic signal … not proof", calibrated-threshold caveat | A | Same | Kept |
| How It Works | Hero sample | D | Labelled illustrative | Kept |
| Demo blurbs | "real shared frontend", saved workflow | D | Demo UI is current but its results are from an older snapshot (inc 623) | Earlier-version sentence added on all three pages |
| Acquire | Open-access cascade, 8 sources | C | Registry. CORE skips without a key | Kept. Limitation recorded here |
| Client surfaces | TUI ~140 actions, 13 groups | A | `tui/registry.py` | Kept |
| Requirements | Python 3.11+, Node, Qwen2.5 Local AI | A | `pyproject.toml`, `Cargo` pins | Kept |
| Reader, axis Ask, reference lookup | No showcase claim | A, no claim | Excluded routes 94-96 | Unchanged |
| Browser Capture | No website claim. README covers it with its evidence table. Integrations caption now names it | A, C | README, Help 90-102 | No new capability entry. Intel Mac and Windows 11 physical evidence only; Linux unsupported |
| Support, docs links | GitHub links | A | All 200, see below | Kept |
| Registry | `route_97` exclusion reason described "behind the unchanged MiniLM/MiniLM2 defaults" | E | Inc 618 made Automatic prefer Arctic S | Rewritten |

No current page markets DeBERTa or Arctic S as available, says MiniLM is retired, or claims a verification-performance advantage. A new
test holds both names to the labelled note. G1 stays CONDITIONAL and is described as conditional.

## Screenshots
All 21 tracked images were opened and looked at. "Represents" names the version the context claims. Retained images were checked by eye
against current code strings, not pixel-diffed against a fresh render.

| File | Page, context | Depicts | Represents | UI accurate? | Caption accurate? | Function changed? | Disposition | Evidence |
|---|---|---|---|---|---|---|---|---|
| `app_current.png` | Home, showcase map | Dark Library, testing DB | 0.5.16 | Yes | Yes | No | Retain | 53 measured hotspots depend on it |
| `citation_evidence_current.png` | Evidence | Retrieval 1.000, quote 1.000, support 0.632, exact | 0.5.16 | Yes | Yes | No | Retain | Scores match thresholds |
| `cite_current.png` | Cite | Suggestion pane | 0.5.16 | Yes | Yes | No | Retain | |
| `dark_mode_current.png` | Theme | Dark UI | 0.5.16 | Yes | Yes | No | Retain | |
| `feed_current.png` | Feed | Now saved demo | 0.5.16 UI | **Was no** | Now yes | Tab retired 2026-08-27 | **Recaptured** | Old image showed the retired Followed Authors tab |
| `gaps_current.png` | Indexed gaps | Public OpenAlex records | 0.5.16 | Yes | Yes | No | Retain | |
| `meta_preregistration_current.png` | Meta-Prereg | Public OSF registration | 0.5.16 | Yes | Yes | No | Retain | |
| `meta_reference_current.png` | Meta-Reference | Citation audits | 0.5.16 | Yes | Yes | No | Retain | Candidate compared |
| `metaanalysis_current.png` | Reporting | Crop | 0.5.16 | Yes | Yes | No | Retain | |
| `methods_data_current.png` | Data checks | Details panel | 0.5.16 | Yes | Yes | No | Retain | |
| `mobile_current.png` | Phone layout | Now saved demo | 0.5.16 UI | **Was no** | Now yes | Banner removed | **Recaptured** | Old image showed a "New layout" banner absent from current source |
| `my_publications_current.png` | My Publications | Maintainer's public record | 0.5.16 | Yes | Yes | No | Retain, flagged | Identifies the maintainer, not private. Their decision |
| `publishers_current.png` | Journals | Now saved run | 0.5.16 UI | **Was no** | Now yes | Tab retired | **Recaptured** | Same retired tab |
| `reader_current.png` | Reader | Now demo article, page 2 | 0.5.16 UI | **Was no** | Now yes | Find added, inc 590 | **Recaptured** | Lacked Find. Old image also showed a full journal page with no license check |
| `saved_note_current.png` | Note | Small crop | 0.5.16 | Yes | Yes | No | Retain | |
| `statcheck_current.png` | statcheck | Public paper crop | 0.5.16 | Yes | Yes | No | Retain | |
| `statements_current.png` | Statements | Disclosure drafts | 0.5.16 | Yes | **Was no** | No | **Relabel** | Alt and caption said funding and CRediT |
| `status_current.png` | Status | Saved demo popover | 0.5.16 UI | Yes | **Was no** | No | **Relabel** | Named as demo; "Done in 0s" is replay |
| `synthesis_current.png` | Core synthesis | Real synthesis, public paper | **0.5.x** | Yes for that version | **Was no** | 0.6.0 adds a model line | **Relabel, not recaptured** | See below |
| `usage_current.png` | Integrations | Now source checkout, disposable library | Current branch, same card as 0.5.16 | **Was no** | Now yes | Word web and Browser Capture added | **Recaptured** | Old image said Word on the web was unsupported |
| `wip_workspace_current.png` | WIP | Now two synthetic drafts | 0.5.16 UI | Yes | Now yes | No | **Recaptured** | Now uses the saved demo's fixture data |

### Recapture record
- App commit `b9a631e5`, Chromium 149.0.7827.55, 1600x1000 (phone 390x844), light scheme, zero page errors, zero aborted off-site requests.
- Sources: supported `build_demo` over `demo/snapshot-v1.json`, except `usage_current.png`, which is `tools/qa/_qa_serve.py` with a disposable
  seeded library, egress off, model provisioning off. Its page loaded React from the frontend's own CDN.
- No model ran or downloaded, and no image was edited or generated. Procedure: `.local\validation-624\recapture.py`, `reader_and_find.py`.
- The orientation banner was dismissed so it did not cover the navigation. Images keep their demo notes and Read-only pill, and captions name the source.

### `synthesis_current.png`
Left in place and described truthfully as the released 0.5.x interface. It was not spliced. The saved demo cannot produce the provenance
line because its snapshot has `model_provenance: null`. A genuine image needs one real synthesis on 0.6.0 with a disposable, non-sensitive
library, which needs separate authorization for model inference. Smallest legitimate procedure: during packaged-runtime validation, run one
Ask on a public-paper library, capture it, and update the caption.

## Help and documentation
- Help corpus sections checked against code: Library modernization, Automatic model selection, resumability, disk and memory waits, model
  failures and Try again (1546-1560), provenance and "possible disagreement" (1529-1533, 808), Browser Capture (90-102), Status.
  **Consistent.** Inc 620 and 622 closed the matrix item about disk waits.
- Help line 808 names "source disagrees" and does not mention the "possible disagreement" variant, which is covered at 1531. Low.
- **The reader's Find control has no Help entry** (inc 590, released). Low. Not fixed: any Help edit would stale the demo gate and reopen inc 623.
- Help's install notes match the website after this correction.
- Demo Help (66 sections against 69) is an older snapshot with an on-page earlier-version notice. Retained. No journey on the website
  depends on the missing sections: website links reach the app and README, not Help anchors.
- **Help marker not moved.** The corpus did not change, so the inc-622 marker stays accurate. Entries above it (inc 623, 624) change no Help behaviour.

## Findings left open
- **App defect, Find hides the text it found.** `.pdf-find-layer` (`z-index: 2`) creates a stacking context, so `.pdf-find-hit`'s
  `mix-blend-mode: multiply` blends only inside the layer and the hit paints as a solid block. Measured: darkest pixel 105 on the current hit
  and 237 on other hits, against 0 for bare text. Setting the blend on the layer in the browser gave 0, confirming the cause. It is in the
  shared frontend, so it affects the released app and the demo. Inc 623's Find check counted matches and did not look at legibility.
  Not fixed: the app is under feature freeze, this is a website increment, and a frontend edit would stale both gates. Recommended as a
  one-line CSS fix in a release-stabilization increment. The reader image was taken with Find closed so it does not show this.
- Website copy describes 0.5.16 and a labelled 0.6.0 plan. If 0.6.0 ships, the labels, model rows and `route_97` exclusion need another pass.
- Old GitHub links point at `main`, whose docs will change when this branch merges. Not misleading today.

## Corrections beyond copy
**Deep links were broken.** `.shot.compact img` is `width:auto`, so six unloaded lazy images collapsed to 0x0, and the page grew 3,950 px as
they loaded. A fresh link to `showcase.html#fig-wip` stopped 4,192 px short at 1440 px, and the homepage's 12 deep links were affected in
the same way. The compact images now load eagerly. A test pins it.

## Rendered browser
Script `.local\validation-624\site_acceptance.py`, results `.local\validation-624\site-final\result.json`. Website at `/callosum/`, supported
demo build at `/callosum/demo/`, local static server, Chromium headless, 1440x900 and 375x812. No production request. Outcome is recorded in
the inc-624 notes.

External links were checked separately and read-only from a shell: GitHub repo, README, CONTRIBUTING, first-launch note and issues returned 200.
`releases/latest` and all four installers returned 206 for a one-byte range after redirects. Assets were not downloaded.
