<!-- section: getting-started -->
## Getting started
Callosum is for working through a scholarly PDF library on your own machine. Use it to browse papers, open PDFs, add highlights and notes, organize the library with axes, and ask synthesis questions that come back with evidence you can inspect.

The most important habit is to treat Callosum as an evidence workbench, not a magic answer box. When it writes a synthesis, the answer is AI-proposed, but each cited sentence is independently checked against the source PDFs. You see the supporting quote, page, confidence scores, and whether the sentence is verified or flagged.

The app is local-first. After your library has been imported and processed, extraction, search, embeddings, axis scoring, duplicate scanning, and verification run locally. The app remains useful offline. The optional Gemini features are off by default and only run when you explicitly enable data egress.

Start by:

- Open the app in your browser.
- Check that the Callosum logo in the left sidebar shows the connected state.
- Browse the Library in the center pane.
- Select a paper to show editable Detail information on the right.
- Double-click a paper, click a file in Details, or open a synthesis citation to view the PDF.

<!-- section: app-layout -->
## Finding your way around
Callosum uses three main areas:

- **Left pane:** Callosum identity, Help, Settings, and an **accordion** with **Axes**, **Synthesis**, and **Tags** — click a section header to open it (one open at a time).
- **Center pane:** the Library tab and any open PDF tabs.
- **Right pane:** a **Details** accordion section — the editable bibliographic information for the paper you have selected (it shows a hint until you select one).

The left and right side panels can be resized with the vertical grips, and either can be collapsed with the chevron next to it. Within a side pane, click a section header (e.g. **Synthesis**) to switch to it; the open section is remembered between sessions, and an in-progress synthesis keeps running while you look at another section.

The center pane always has a **Library** tab. When you open PDFs, each PDF gets its own tab. Switching tabs keeps open PDFs mounted, so you do not have to re-open the same document every time you move between the Library and a paper.

Tips:

- Select a paper once to inspect its metadata in Detail.
- Double-click a paper in the Library to open its PDF.
- Click paper titles inside an axis to open their PDFs and follow them in Detail.
- Use the Help button (`?`) in the sidebar for the in-app help viewer.

<!-- section: importing-from-zotero -->
## Importing your library from Zotero
Zotero import is for bringing your existing reference library into Callosum without turning Callosum into a cloud sync service. The importer reads your local Zotero library data and represents papers, metadata, collections, tags, notes, annotations, and attachments in Callosum.

During import, Callosum:

- Matches existing papers where it can, instead of blindly duplicating them.
- Records Zotero metadata such as title, authors, year, venue, DOI, citation key, and item type.
- Tracks local PDF attachments when available.
- Extracts PDF text into chunks with page information and bounding boxes.
- Preserves enough source-location information for later citation jumping and verification.
- Keeps URL-only or missing attachments as honest metadata entries rather than pretending the PDF is local.

Import does not make Gemini calls. Text extraction and local processing stay on your machine.

Gotchas:

- If a paper says **PDF not available locally**, the imported record may be URL-only, metadata-only, or pointed at a file that is no longer available on disk.
- A paper with **metadata not yet resolved** or **needs DOI** usually came from a raw or sparse record. Add or fix the DOI in Detail, then use the `🔎` button to re-resolve it from Crossref.
- Imported PDF text quality depends on the PDF. Scanned image-only pages may not produce useful selectable text or exact citation coordinates.

<!-- section: scanning-a-folder -->
## Watched folders (scanning for PDFs)
If your PDFs live in a folder (not Zotero), point Callosum at it: open **+ Add → Watched folders…** at the top of the Library, enter the folder's path on this computer, and click **Add + scan**.

Callosum walks the folder for PDFs and reconciles them with your library:

- **New** PDFs are added — text extracted, chunked, embedded, and metadata fetched from Crossref where a DOI is found. Any whose DOI doesn't resolve land under **Unsorted** so you can fix them.
- **Unchanged** PDFs (already in the library, matched by **content**, not filename) are skipped — re-scanning is safe and never creates duplicates.
- **Removed** PDFs (a previously-scanned file that's now gone from the folder) are flagged as missing, not deleted.

Once you've added a folder it becomes a **watched folder**: Callosum re-scans your watched folders **automatically each time the app starts**, so new PDFs you drop into them are picked up without re-adding (you can also click **Re-scan all** in the dialog). The dialog lists your watched folders with when each was last scanned; **remove** stops watching a folder but keeps the papers it already imported. Because matching is by content, the folder your existing library came from is safe to add — re-scanning it just confirms everything's already there. You can turn the on-launch re-scan off in **⚙ Settings → Library**.

Your PDFs stay where they are — watching links to them in place and never moves or copies anything. It reads only the folders you've added, on your own machine, and never sends your PDFs anywhere (only the DOI lookup talks to Crossref, the same public metadata service used elsewhere).

<!-- section: importing-citations -->
## Importing a citation file (BibTeX, RIS, CSL-JSON)
To bring in references from another reference manager, open **+ Add → Import file…** at the top of the Library and choose a **BibTeX** (`.bib`), **RIS** (`.ris`), or **CSL-JSON** (`.json`) file. Zotero, Mendeley, EndNote, and Callosum itself can all export one of these formats. This is the mirror image of **Exporting citations** — what you export, you can re-import.

Each entry in the file becomes a metadata-only library paper (title, authors, year, journal, DOI, type, …). Entries already in your library are skipped (matched by DOI, or by title + year + first author when there's no DOI), so re-importing the same file is safe and creates no duplicates. Anything the parser can't read is skipped and counted rather than failing the whole import; the summary reports "N imported · M already in library · K skipped".

Import brings in **metadata only** — no PDF is attached (add PDFs via **Scan folder**, Zotero, or **Acquire OA copy**). It runs **entirely on your machine**: the file is read in your browser and nothing is sent anywhere — no DOI lookup, no other network call. Imported papers are searchable and can be filtered by **type**; because the file is treated as your authoritative metadata, a later batch re-resolve won't overwrite it unless you explicitly re-resolve that paper.

<!-- section: browsing-and-searching -->
## Browsing and searching the Library
The Library is for quickly finding papers and opening the ones you want to read. It shows each paper's title, authors, year, venue, processing tier, and file count.

Use the search box to filter the library. By default it searches across **all** of a paper's stored fields — title, **every** author (not just the first), journal, year, DOI, abstract, and the rest of the bibliographic record — so searching your own surname finds every paper you co-authored, not only the ones you led. Use the dropdown beside the search box to narrow the scope to **Title**, **Author**, or **Journal** when a broad match returns too much. Search is debounced, so results update shortly after you stop typing. The list shows up to 50 papers per page; use **Prev** and **Next** when there are more results.

Use the **Sort** dropdown to order the library by date added (oldest or most recent), title (A–Z or Z–A), publication year (newest or oldest), or first author (A–Z or Z–A). Papers without a year or author sort to the end. Your sort choice is remembered across sessions, and sorting works alongside search, the Trash view, and an axis filter.

Use the **Type** dropdown (shown when your library has typed papers) to narrow the list to one document type — journal article, book, conference paper, preprint, and so on. It only offers types that are actually present, each with a count, and composes with search and sort.

Common Library actions:

- Click a paper once to select it and show its Detail pane.
- Double-click a paper to open the PDF.
- Click the small **clipboard icon** on a card (just left of its checkbox) to copy that paper's **BibTeX** to your clipboard.
- Use the checkbox beside papers to select them for bulk delete.
- Click **Unsorted** to see only the papers whose metadata still needs review.
- Click **Duplicates** to scan for likely duplicates.
- Click **Trash** to view deleted papers.

Click **Unsorted** in the Library header to narrow the list to papers that still need bibliographic review — raw PDF imports that were never enriched, papers whose DOI could not be resolved against Crossref, and papers with no recorded source. A banner shows the count with a **clear** link, and the button changes to **← Library** while the view is active. It is a view like Trash (it clears any axis or tag filter), but you can still tick checkboxes to bulk-fix the unsorted papers — for example, select them and re-resolve, export, or delete. To resolve a paper out of the Unsorted view, open it and use 🔎 to re-fetch its metadata, or edit its fields by hand; once it has a real source it drops out of the view.

Processing tiers are short status labels. A fully processed paper usually has chunks and a local file. A metadata-only paper can still be useful for bibliographic management, but it will not support PDF reading or source-grounded synthesis until it has usable text.

<!-- section: opening-and-reading-pdfs -->
## Opening and reading PDFs
The PDF viewer is for close reading, source checking, and annotation. Open a PDF by double-clicking a Library row, clicking a file in Detail, clicking a paper under an axis, or using **Open source** from a synthesis citation.

The toolbar shows:

- The paper title.
- Zoom out and zoom in controls.
- The current page number.
- A **Notes** button with the number of saved annotations.

Callosum renders the PDF pages and an invisible selectable text layer. That means you can select text to highlight, while the visible page stays aligned with highlights and citation overlays across zoom levels.

For distraction-free reading, click **⛶ Read** at the right of the tab bar — it hides both side panels to give the page the full width. Click **⤢ Exit** or press **Esc** to bring the panels back exactly as they were. (Reading mode is temporary; reloading the page returns to the normal layout.)

Gotchas:

- The PDF renderer is loaded when the first PDF opens. If it cannot load, the viewer will show an error instead of a blank page.
- If a PDF is not available locally, Callosum says so directly.
- Exact overlays are disabled for rotated pages. The viewer will still open the page, but it will not pretend to draw precise rectangles when alignment would be unreliable.

<!-- section: citation-jumps-and-coordinate-precision -->
## Opening citation sources
Citation jumps are for checking whether a synthesis sentence is actually supported by the cited PDF. In a citation card, click **Open source and highlight**, **Open source region**, or **Open source page**, depending on the evidence Callosum found.

Callosum is careful about coordinate precision:

- **exact quote coordinates:** the app found usable bounding boxes and can highlight the cited passage.
- **region-level:** the app can open the relevant page and show an approximate source area note, but it is not claiming an exact passage highlight.
- **no coordinate claim:** the app can point you to the page when known, but it has no coordinate evidence to draw.

Use exact highlights as a fast path to inspect the quoted passage. Use region-level and page-only jumps as navigation aids, then read around the page yourself.

Tip: The quote in the citation card is often the most important evidence. Read it before relying on the sentence, especially when a citation is flagged or only region/page precise.

<!-- section: highlights-and-notes -->
## Highlights and notes
Highlights are for marking passages you want to revisit. Notes are for adding your own reading comments on those passages.

To create a highlight:

- Open a PDF.
- Select text on a page.
- Choose a color from the small picker.
- Or click `✎ note` to highlight and immediately add a note.

To edit an existing highlight:

- Click the highlight in the PDF.
- Change the note text or color.
- Click **Save**.

To manage highlights:

- Click **Notes** in the PDF toolbar.
- Use the annotation panel to jump to a highlight, add or edit a note, or delete a highlight.

Callosum uses a fixed set of highlight colors. Notes can be long, but they are capped to keep the library responsive.

Gotchas:

- Highlights depend on selectable PDF text. If a scanned page has no text layer, you may not be able to create a text selection highlight there.
- A highlight saved from synthesis has a dashed outline so you can tell it came from verified citation evidence rather than your own manual reading.

<!-- section: paper-details-and-metadata -->
## Editing paper Details
The Detail pane is for fixing and completing bibliographic metadata. Select a paper in the Library, an axis list, or a PDF tab, and its Detail view appears in the **Details** section of the right pane.

Most fields are always editable:

- Literature Type
- Title
- Authors
- Year, Month, Day
- Volume, Issue, Pages
- Journal
- Language
- URL
- Abstract
- Identifiers such as DOI, ArXiv ID, PMID, Cite key, ISBN, and ISSN
- Extra fields in **More**, when available

Fields auto-save when you leave them. For authors, enter one author per line. For numeric date fields, non-numeric input is ignored and the previous value is restored.

The **More** section holds any extra bibliographic fields (for example ones a DOI lookup filled in beyond the core set), and lets you **add your own**: type a field name (letters, digits, `-`/`_`) and a value, then **+ add**. Fields that have their own editor above (title, DOI, …) are reserved and can't be re-added there.

The **Files** area lists available attachments. Click a file to open the paper's PDF.

Gotchas:

- There is no separate Save button for most Detail edits. If you type into a field and click away, Callosum tries to save that field.
- Hand edits are protected from ordinary batch metadata updates. If you explicitly re-resolve from Crossref, you are asking Callosum to refresh the record from that DOI.
- If the title is empty, Callosum will not save it. Every paper needs a title.

<!-- section: exporting-citations -->
## Exporting & formatting citations
Callosum can export your papers' bibliographic records in three machine-readable formats — **BibTeX** (`.bib`), **RIS** (`.ris`), and **CSL-JSON** — and can render **formatted citations** in real styles (APA, MLA, Chicago, IEEE, Nature, Harvard). Everything runs entirely on your machine — nothing is sent anywhere.

**Formatted citations (APA / MLA / Chicago / …):**

- In a paper's **Details** pane, the **Cite as** row has a **style dropdown** and a live preview of the formatted reference; click **Copy** to put it on your clipboard.
- For a whole reference list: in the Library, check the papers you want, then in the bulk bar open the **bibliography…** dropdown and pick a style — Callosum downloads a formatted `.html` bibliography (open it in your browser or word processor). *(Full cite-while-you-write inside Word/LibreOffice is on the way; this is the engine that powers it.)*

**Machine-readable export:**

To export several papers at once:

- In the Library, check the papers you want (use **select all** to grab the whole page; pair it with search or an axis filter to scope the set).
- In the bulk bar, open the **export…** dropdown and pick a format.
- Your browser downloads a single file (`callosum-citations.bib` / `.ris` / `.json`) with one entry per selected paper.

To copy one paper's citation:

- **Fastest:** each card in the Library has a small **clipboard button** just left of its checkbox — click it to copy that paper's **BibTeX** straight to your clipboard (the icon flips to a ✓). No need to open the paper.
- **From Details:** click a paper to open its Details pane, and in the **Cite** row click **BibTeX**, **RIS**, or **CSL-JSON** — the citation is copied to your clipboard (the link briefly shows "Copied ✓"). Paste it into your manuscript, a reference manager, or a `.bib` file.

Notes:

- BibTeX entry keys use the paper's cite key when present (Zotero imports), otherwise an author+year key; collisions get a letter suffix.
- Trashed papers are never exported.
- These are machine-readable interchange formats. Formatted "human" citation styles (APA, MLA, …) are not produced yet.

<!-- section: tags -->
## Tagging papers
Tags are lightweight, free-form labels for organizing your library — a quick complement to the semantic **axes**. (If you imported from Zotero, your existing Zotero tags already appear here.)

To tag a paper:

- Click a paper to open its Details pane.
- In the **Tags** row, type a tag and press Enter. As you type, Callosum suggests tags you've used before.
- A tag can be on as many papers as you like; the same name is shared (not duplicated) across papers.

To get tag ideas, click **✨ Suggest**: Callosum proposes candidate tags drawn from the words most distinctive of that paper compared to the rest of your library, and you click the ones you want to keep. This runs entirely on your machine — no AI is sent off-device, and nothing is added until you accept it.

Callosum also imports **author/index keywords** as tags so the authors' own concept work becomes a first-order set of labels:

- **Zotero tags** come in automatically when you import a Zotero library.
- **Crossref subject categories** are added whenever a paper is resolved against Crossref — including when you click **🔎** on its DOI. To apply this across an already-imported library in one pass, run `python tools/backfill_keyword_tags.py` (it reuses cached Crossref data where possible and only adds tags — it never overwrites your edited metadata).

The **✨ Suggest** pass then fills gaps the authors' keywords missed (it skips terms you already have).

Tags you added and tags that were **imported** (Zotero tags, Crossref subject keywords) are distinguished by a subtle visual difference rather than an extra label — imported keyword tags appear in a quieter, muted style, while the ones you typed keep the accent color. Hover any tag to see exactly where it came from. They all behave the same — click to filter, **×** to remove.

To browse and remove:

- The left pane's **Tags** accordion section lists every tag with its paper count (it's always available — when you have no tags yet it shows a hint pointing you to add them from a paper's Details). Click a tag to **filter the library** to it — a quick way to navigate by tag without opening a paper first. When your library has both imported keyword tags and tags you typed, an **All / Yours / Keywords** filter appears at the top of the section to narrow the list by source.
- Click a tag's name in a paper's **Tags** row to **filter the library** to every paper carrying that tag (a "Filtered to tag …" banner appears; click **clear** to return). The tag filter and the axis filter are mutually exclusive.
- Click the **×** on a tag to remove it from that paper. A tag that ends up on no papers is cleaned up automatically (and disappears from the sidebar panel).

Tags are stored locally; nothing is sent anywhere.

<!-- section: fixing-dois-and-crossref -->
## Fixing a DOI and re-resolving metadata
Use DOI re-resolve when a paper has sparse metadata, a wrong title, missing authors, or a DOI that you trust more than the current record.

To re-resolve:

- Select the paper.
- Open **Identifiers** in the Detail pane.
- Enter or correct the DOI.
- Click `🔎`.

Callosum saves the DOI first, then asks Crossref for bibliographic metadata. Only the DOI is sent to Crossref for this action. This is separate from the Gemini data-egress gate because it is normal public DOI lookup, not sending your library text to an LLM.

Possible outcomes:

- **Resolved from Crossref.** The record was updated from the DOI.
- **Crossref couldn't resolve that DOI.** Check for typos and try again.
- **That DOI is already on another paper.** Callosum prevents two papers from sharing the same DOI.

Gotcha: Re-resolve can overwrite fields from Crossref because you explicitly requested a refresh. If you have carefully hand-edited a record, use this intentionally.

<!-- section: acquiring-open-access -->
## Acquiring an open-access copy
When a paper in your library has no PDF, Callosum can try to fetch a **rights-holder-authorized open-access** copy and import it for you. Callosum never decides on its own that something is open access — it only downloads a copy that a maintained open-access database has already declared free to read.

To acquire a copy:

- Select a paper that has no PDF (it needs at least a DOI, PMID, or title).
- In the Detail pane, click **Acquire OA copy**.
- Callosum checks a cascade of open-access sources and stops at the first authorized copy.

The sources it tries, in order: **OpenAlex** (broadest), **DOAJ** (gold open-access journals), **Europe PMC** (open-access full text), **Crossref** (publisher links that carry an open license), **CORE** (repository copies), and the preprint servers **arXiv**, **bioRxiv/medRxiv**, and **OSF/PsyArXiv**.

Every acquired copy is labeled so you know exactly what you got:

- **OA color** — **gold**/**green** are durable open access; **bronze** means free-to-read on the publisher site without an open license, so it is flagged as unstable (it can revert to paywalled).
- **Version** — version of record, accepted manuscript, or preprint. A preprint is not the final published version.

Outcomes:

- **A copy was imported.** The PDF is saved into your local library, named like the rest of your library (`Authors - Year - Venue.pdf`), and opens in the viewer with its OA label.
- **No authorized open-access copy found.** No source had a free, authorized PDF. Callosum will not fetch anything paywalled.

Privacy: acquisition is local-first. The PDF is stored on your machine, not on any server. The only things that leave your computer are ordinary metadata lookups to the public open-access databases above (plus the download of the copy they point to) — this is normal public lookup, **not** the Gemini data-egress gate, and it never sends your library text to an LLM.

Optional: the **CORE** source needs a free API key. Set `CALLOSUM_CORE_API_KEY` in your environment to enable it; without a key, Callosum simply skips CORE and uses the other sources.

<!-- section: wanted-list -->
## Wanted list & re-checking for copies
The wanted list tracks papers you want an open-access copy of, so Callosum can keep looking for one. Open it from the **Wanted** button at the top of the library.

It holds two kinds of entries:

- **Library papers** that don't have a PDF yet — click **Sync from library** to add all of them at once.
- **External papers** you don't have yet — click **Add by DOI** to add one by its DOI.

Click **Re-check OA** to search every open-access source for each wanted paper and **import any authorized copy it finds**, in one pass. When it finishes you get a summary: how many were acquired (with their OA color), how many are still wanted, and how many need an identifier. A library paper that gets a copy now has its PDF; an external paper becomes a new paper in your library. The coverage line at the top shows how much of your library has PDFs and how many copies you've acquired, by OA color.

Notes:

- Re-checking only ever downloads authorized open-access copies (the same rule as Acquire OA copy) — nothing paywalled, and nothing leaves your machine except the open-access lookups.
- An external want needs a **DOI or PMID** to be fetched automatically; a title-only entry is marked "needs an identifier" so Callosum never imports the wrong paper from a fuzzy title match.
- A **bronze** copy is free-to-read but unlicensed and may revert to paywalled; a preprint is not the final published version.

<!-- section: axes-overview -->
## Axes: organizing papers by a lens
An axis is a lens for organizing your library around a construct, theme, method, population, theory, or question. It is not a folder, and it is not a permanent truth about a paper. It is a scored relationship between your curated vocabulary and the papers in your library.

The key idea:

- The **title** is a display name.
- The **search terms** are the vocabulary scored against your library.
- The optional **description** gives extra context.

For example, an axis titled "Resting-state networks" might include terms such as "resting-state connectivity", "default mode network", and "functional connectivity". Renaming the title makes the axis easier to read, but the terms and description are what guide scoring.

Use axes when you want to:

- Sort a mixed library by recurring themes.
- Track papers relevant to a construct.
- Review borderline candidates.
- Build a human-curated overview of a field.

<!-- section: creating-and-editing-axes -->
## Creating and editing an axis
Create an axis when you want a new lens over the library.

To create one:

- Click `+` in the Axes controls.
- Type a new axis name.
- Click **next →**.
- In the **New axis** modal, confirm the title.
- Add or select search terms.
- Add optional description context.
- Click **Create axis**.

To edit one:

- Click `✎` on the axis card.
- Change the title, description, or terms.
- Click **Save changes**.
- Re-score the axis if the scoring vocabulary changed.

Search terms are shown as chips. Selected chips are active; deselected chips are ignored. You can add a custom term with **add**.

The **search related terms** button can suggest terms for an axis. This uses Gemini and is egress-gated. Suggestions start deselected so you decide what belongs in the lens.

Gotchas:

- The title is not the main search query. Put the meaningful vocabulary in selected terms.
- Suggested terms are not automatically trusted. Select only the terms that actually fit your scholarly use of the axis.
- Editing terms or description can make the axis stale until you re-score.

<!-- section: scoring-axes-and-tiers -->
## Scoring axes, tiers, and confidence
Scoring an axis compares that axis's vocabulary with your library and lists papers that look relevant. It runs locally.

To score:

- Expand an axis.
- Adjust **Cutoff** if needed.
- Click **Score** or **Re-score**.
- Wait while Callosum scores the library.

Each paper under an axis can show:

- **assigned:** similarity is at or above the cutoff. This is the default state and has no extra tag.
- **uncertain:** similarity is below the cutoff but above the floor. Treat it as a candidate, not a match.
- **manual:** you added or confirmed it by hand. Manual overrides are human choices, not scorer decisions.

The confidence number is an embedding-similarity score. It is useful for ranking candidates inside an axis, but it is not a probability that the paper "is about" the axis.

The **Cutoff** slider controls how strict assigned status is:

- Lower cutoff: more papers become assigned.
- Higher cutoff: fewer papers become assigned.
- The default is `0.35`.

Gotchas:

- Scores are relative to this axis's vocabulary.
- A narrow or vague axis may show mostly uncertain papers.
- If no paper clears the usual floor, Callosum may still show a few closest candidates as uncertain so the axis is not a dead end.
- Re-scoring preserves manual additions and confirmations.

### Stale axes
An axis becomes stale when its current vocabulary no longer matches the last scoring run. This most often happens after you edit the terms or description, or after an axis merge changes the search vocabulary.

When an axis is stale, its current paper list may reflect the old wording. Re-score it before you rely on the assignments.

Re-scoring re-embeds the current axis vocabulary, recomputes assignments locally, keeps manual assignments and confirmations, and saves the current cutoff for that axis.

Tip: If an axis looks wrong after editing terms, do not keep adjusting the title. Open the axis editor, improve the selected search terms, then re-score.

<!-- section: reviewing-axis-assignments -->
## Reviewing and correcting axis assignments
Axis review is where you turn machine suggestions into a useful scholarly lens.

Useful controls:

- Click a paper title under an axis to open its PDF.
- Click `✓` on an uncertain paper to confirm it as manual.
- Click `×` to remove a paper from the axis.
- Click `👁` to hide uncertain papers and see only assigned/manual papers. (To start every axis card in this hidden view, turn on **Hide uncertain papers by default** in ⚙ Settings → Axes.)
- Click `＋` on an axis to add or remove papers from the main Library list.
- Click an axis's **count badge** (the number on the right of the axis) to **filter the Library to just that axis's papers**. A "Filtered to axis …" banner appears; click **clear** to return to the full library. From a filtered view you can **select all → summarize** to get a verified synthesis of the whole cluster in a few clicks. When uncertain papers are hidden, the count badge shows the visible (assigned + manual) total, and its tooltip notes how many uncertain are hidden.

When you click `＋`, Callosum enters a Library focus mode for that axis. Each Library row gets a button such as **+ add**, **✓ in axis**, **✓ staged**, or **- staged**. Changes are staged until you click **Save**. Use **Cancel** to leave focus mode without applying staged changes.

Tips:

- Use uncertain papers as a review queue.
- Confirm papers you know belong even if their score is modest.
- Remove false positives promptly so the axis stays readable.
- Use the eye toggle when you want a cleaner view for reading, and turn it back on when you want to audit candidates.

<!-- section: suggested-axes -->
## Suggesting new axes
Use **✨ Suggest** when you want Callosum to look across the library and propose new lenses you may not have created yet.

The suggestion scan clusters your library locally and looks for themes that your existing axes do not already cover. The modal shows candidate axes with:

- A proposed label.
- Suggested terms.
- The number of papers behind the suggestion.
- Example paper titles.

You can rename a suggestion, toggle term chips, and click **Create axis** for the ones you want. Created suggestions become normal axes.

Privacy note: the clustering is local. If Gemini labeling is enabled, Callosum may use it only to polish labels from representative paper titles. If egress is off or Gemini fails, the feature still has a local fallback.

Gotchas:

- Suggestions are starting points, not final taxonomy.
- Creating a suggested axis does not mean you have finished curation. Review the terms, score it, and inspect assignments.
- If no suggestions appear, your existing axes may already cover the library, or the library may be too small or too sparse.

<!-- section: merging-axes -->
## Merging axes
Merge axes when two or more lenses overlap enough that they would be easier to manage as one.

To merge:

- Select two or more axes with their checkboxes.
- Click **merge** in the bulk bar.
- Choose which axis survives as the merged identity.
- Curate the merged label, related terms, and description.
- Click **Merge axes**.

The merge view carries folded axis labels into the merged axis as related terms by default. This helps the merged axis keep the vocabulary that made the original axes useful. Manual paper assignments from the merged axes are combined.

After the merge, Callosum re-scores the surviving axis so the scored assignments reflect the merged vocabulary.

Gotchas:

- Merging axes deletes the folded axis records. Use it when you really want one lens.
- Scored assignments are recalculated. Manual assignments are the durable human choices.
- If the merged axis is too broad, raise the cutoff or split the idea back into more focused terms in a new axis.

<!-- section: my-publications -->
## My Publications
Callosum can gather your own papers into a pinned **My Publications** axis at the top of the Axes panel.

Set it up in Settings (⚙) → **My Publications**: enter your name, any other published-name variants (initials, maiden name), and — recommended — your **ORCID** (which gives an exact match). Then click **Refresh my papers**.

Callosum resolves your identity against **OpenAlex** (a public scholarly database) and matches its record of your works against your library:

- Papers matched by **DOI or ORCID** are **confirmed** — they appear as members of the axis.
- Papers matched only by **name** (e.g. a scanned PDF with no DOI) appear as **candidates** to review — click **✓** to confirm one as yours, or **✕** to reject it. Your choices stick: a rejected paper is never proposed again, and a confirmed one stays a member.

The card shows a publication count and doubles as a "show only my papers" filter (click the count badge). Newly imported papers that match are added automatically. The 🗑 button dismisses the card (your profile and confirm/reject choices are kept — Refresh rebuilds it). A no-match shows an honest "No OpenAlex author found for [name] — check the name/ORCID."

**The impact dashboard.** Click the **📊** button on the card to open a dashboard tab. At the top is a collapsible **Overview** — headline metrics from your OpenAlex record (total **citations**, **h-index**, **i10-index**, **indexed work count**) beside a year chart you can **flip between publications and citations** (last 10 years). These are OpenAlex's own authoritative figures over your *whole* indexed record (not just your library), shown as-is. The dashboard reads only cached data, so it never fetches on its own — to update it, click **Refresh from OpenAlex** on the **OpenAlex card** at the bottom (which also carries the "as of [date]" provenance, your 2-year mean citedness, affiliation, and a link to your OpenAlex profile), or use Refresh in Settings. Below the Overview is an **AI-generated research summary**: click **Generate** for a one-paragraph draft describing your work, drawn from your publication titles and abstracts; edit it and **Save**. The draft is yours to rewrite — a starting point, not an authoritative claim. To focus the summary on your most important work, **star** key publications (the ☆ button on each paper in the My Publications sidebar card) and tick **⭐ only** before clicking Generate (the toggle appears once you have starred papers).

**Your publications, as cards.** Below the summary, the dashboard lists every one of your in-library publications as library-style cards you can **search** and **sort**. Tick papers' checkboxes to **summarize** them into a verified synthesis, **export** their citations (BibTeX/RIS/CSL-JSON), download a formatted **bibliography**, or move them to Trash — the same actions as the main library. Double-click a card to open its PDF.

**Citation counts & citing articles.** Each own-pub card shows its **cited-by count** — OpenAlex's own figure, shown as-is (not a Callosum score), as of your last refresh — and you can **Sort → Most cited**. Click the count to open the **citing articles** for that paper: the works OpenAlex records as citing it (a discovery list — OpenAlex's coverage, not exhaustive). **Import** any of them (or **Import all**) to add them to your library as metadata records — they go into your general library, not My Publications, and the PDF is a separate **Acquire OA copy** step. If the counts aren't clickable yet, click **Refresh from OpenAlex** once to fetch the citation data.

**Research domains.** From the publications controls row, click **Break down by domain** to group your confirmed publications into research areas (clustered locally by similarity). Each domain shows its paper count and total citations — your **impact by area** — and clicking a domain re-filters the chart to just that domain's papers (the chart locks to **publications by year** while a domain is selected, and the Citations view returns when you clear it; click a domain again to clear, or select several to combine). Domains are a lens, not a fixed taxonomy: each is labeled from its papers' distinctive terms, and **Re-decompose** recomputes them. This is **LLM-free** local clustering.

Turn on **Group by domain** (in the Publications controls, and independently in the My Publications sidebar card) to lay your publications out **under domain headings** — starred papers first, then the rest, with a final **Other** group for any paper not in a domain. You can **rename** a domain with the **✎** beside it; the rename box suggests the closest-matching name from your existing **Axes**, so your domains and axes can share vocabulary. Renamed domains **keep their names across a Re-decompose** (matched to the new clustering by paper overlap).

**Works not in your library.** The OpenAlex card shows how many works OpenAlex indexes for you versus how many are in your library; click **Review N →** (or **Dismissed (N) →**) on that card to open the review modal. Each entry shows its title, year, citations, and DOI. Click **Import** to add one to your library (it's fetched as a metadata record from Crossref and joins My Publications automatically — only works OpenAlex attributes to *you* can be imported), or **Dismiss** to drop it from the list (useful when OpenAlex over-attributes works that aren't yours). Import brings in the record only; use a paper's **Acquire OA copy** button afterward if you also want the PDF. Changed your mind about a dismissal? The same modal lists **previously dismissed** works with a **Restore** button to send one back to the review queue.

Resolving your publications and the dashboard metrics are **LLM-free** and work offline — only your name/ORCID and public identifiers go to OpenAlex (the same kind of public lookup as resolving a DOI). The one exception is the optional research-summary **Generate**, which sends your own publication titles/abstracts to Gemini and therefore works only with the data-egress gate (`CALLOSUM_ALLOW_DATA_EGRESS`) on; with it off, the charts and metrics still render and Generate shows a consent note.

<!-- section: synthesis-overview -->
## Synthesis: asking questions over the library
Synthesis is for asking a question across your library and getting a citation-grounded answer. It is best for questions where you want a compact reading guide, not a final conclusion.

There are two ways to run a synthesis:

- **Ask a question.** Type a question in **Ask a synthesis question about the library...**, click **Synthesize**, and Callosum retrieves the most relevant chunks across your library, generates an answer, and verifies each citation. Read the result under **Verified** and **Flagged · needs review**.
- **Summarize a selection.** Check the papers you want in the **Library**, then click **summarize** in the selection bar. Callosum generates a verified synthesis of just those papers (the Synthesis pane shows a "N selected papers" note), spreading its attention across all the papers you picked. This is the fast path for "summarize these specific papers" without phrasing a question.

Saved syntheses appear in **History** (a question shows its text; a selection shows "N papers"), where you can reload or delete them.

If Gemini data egress is not enabled, synthesis will not run. The app will show an error explaining that summary generation requires opt-in egress and an API key.

Tips:

- Ask specific questions. "How do these papers define cognitive control?" will work better than "Summarize everything."
- Treat flagged sentences as prompts for reading, not as claims to cite.
- Use History to compare earlier syntheses as your library or question changes.

<!-- section: verifying-synthesis-citations -->
## How synthesis verification works
Callosum does not trust AI-generated citations by default. The AI proposes summary sentences and candidate citations, then Callosum independently checks each sentence against local source chunks.

For each cited sentence, Callosum shows:

- The sentence text.
- A **verified** or **flagged** badge.
- One or more citation cards.
- The paper title and page label.
- The evidence quote.
- Retrieval, Quote, and Support confidence scores.
- Coordinate precision: exact, region, or no coordinate claim.

A sentence is shown as verified when its citations clear the verification checks. A sentence is flagged when it has no citation or at least one citation does not verify cleanly.

**The Overview.** Above the verified claims, a synthesis shows a short **Overview** — a plain-language narration *of the verified claims*, labeled "Overview — synthesized from the verified claims below". It is **not** an independent authoritative summary: it restates only what was verified and adds no new facts, and **each Overview line links back to the verified claim(s) it restates** — click a line and the claim(s) it traces to flash below, each carrying its own quote, page, and confidence. The Overview only appears when AI generation is enabled (it requires data-egress consent, like the synthesis itself) and there is at least one verified claim to narrate; with egress off, the verified claims stand on their own.

The confidence scores are evidence signals, not proof:

- **Retrieval** reflects how well the source chunk matched the sentence.
- **Quote** reflects how well Callosum located a quote in the PDF text.
- **Support** reflects whether the cited source appears to support the sentence.

Always read the quote and, when needed, open the source. Verification reduces hallucinated citations, but it does not replace scholarly judgment.

### Saving verified citations as highlights
Use **Save as highlight** when a synthesis citation points to a passage you want to keep in the PDF.

The button is only available when the citation is:

- verified,
- exact-coordinate,
- attached to a local paper,
- and has usable bounding boxes.

When saved, the passage appears in the PDF as a durable highlight and shows up in the **Notes** panel. Synthesis-saved highlights use a dashed outline so you can distinguish them from hand-created highlights.

Gotchas:

- Region-level and page-only citations cannot be saved as precise highlights.
- Flagged citations cannot be saved through this path.
- Saving a highlight does not force-open the PDF; if the PDF is already open, the viewer refreshes its annotations.

<!-- section: checking-statistics -->
## Checking statistics (statcheck)
In the **METHODS** pane (the right-hand panel), open the **Statistics check** section; under **This paper** — with a paper selected — there's a **Check statistics** button. It scans the paper's extracted text for inline APA-style statistical tests — `t(28) = 2.10, p = .04`, `F(2, 45) = 3.1, p < .05`, `r(30) = .42, p = .01`, `χ²(1) = 5.2, p = .02`, `z = 2.1, p = .03` — **recomputes** the p-value from the reported test statistic and degrees of freedom, and shows where the reported and recomputed values disagree. It's the statcheck method: a "spellchecker for statistics."

This runs **entirely on your machine** — pure computation over the already-extracted text, no AI and no network. Each result shows the **verbatim matched text** and its **recomputed p**, with a status pill: **consistent** (green), **inconsistent** (amber — the values disagree), or **decision error** (amber — the disagreement flips significance at p = .05). A count summary reads "N checked · M inconsistent · K decision errors" — these are plain counts, never a hidden "reproducibility score." Click any result to open the PDF at the page the statistic was found on.

Read it as a **prompt to look, never a verdict**:

- An inconsistency is usually innocent — a typo, rounding, a one-tailed test, or an adjusted value. It is **not** an accusation of error or misconduct. The recomputation already accounts for the statistic's rounding and tries the one-tailed reading, so correctly-reported results are not flagged.
- It reads only **inline APA-format** tests — it cannot see statistics in tables, Bayesian reporting, or confidence-interval-only reporting. **A clean result is not a clean bill** — it means nothing was surfaced by this specific check.
- It needs the paper's **extracted text**, so it's available once a PDF has been processed (the button explains this otherwise). PDF-to-text conversion can garble symbols like `<`/`>`/`=`, which is why the exact matched text is always shown — so you can see an artifact for what it is.

**Across your whole library:** in the same **METHODS → Statistics check** section, under **Whole library**, click **Check all papers**. Callosum runs statcheck over every paper and reports "N papers with statistics checked · M with inconsistencies." If any are flagged, a **⚠ N flagged** chip also appears in the Library header as a shortcut. Either click that chip or **Show flagged papers** in the section to filter the Library to just them (a banner appears; **clear** to return) — then open any one to see its specific tests. This is a **list to review, not a ranking**: papers aren't scored or ordered by inconsistency, and the same caveats apply (usually innocent; inline-APA only; absence isn't a clean bill). Re-run the check after editing papers to refresh it.

<!-- section: p-curve -->
## p-curve: evidential value across a set of papers
p-curve is a **collection-level** check (Simonsohn, Nelson & Simmons, 2014): given a *set* of statistically significant findings, it asks whether their p-values are **right-skewed** (many very-small p-values like .01, more than near .05) — which is consistent with **evidential value** — or **flat** (consistent with no/inadequate evidential value). It is **never about a single paper**, and it never labels anything "p-hacked."

To run it: in the **Library**, tick the papers you want (checkbox-select), then click **p-curve** in the selection bar. Callosum reuses the statcheck extractor to pull the **significant** inline NHST p-values across your selection, then shows:

- The **p-curve plot** — the percentage of significant p-values in each bin (.01–.05) against a flat 20% null line.
- A **right-skew test** (Z and p) and a **binomial** robustness check, phrased descriptively (consistent with evidential value, or not) — **never a verdict, and never a score or rank**.
- The **included tests**, each of which opens its page so you can check it yourself.

Read it as a prompt to think, not a judgment:

- It is **collection-level only** — it describes a *body of work you chose to analyze*, never an individual paper or author.
- Coverage: it reads only **inline APA-style NHST tests** with exact statistics (tables, Bayesian, and CI-only reporting are invisible); it includes **every** extracted significant test rather than each study's chosen *focal* test (the method normally asks the analyst to pick that), and it conservatively drops results so significant their p rounds to ≈0. It is most meaningful on a **small, curated set** of related findings.
- Below about 5 significant results the curve is too sparse to interpret; the modal says so.
- The modal credits the method (Simonsohn, Nelson & Simmons, 2014) and offers a one-click **add to library**.

<!-- section: data-consistency-grim -->
## Data consistency (GRIM / GRIMMER)
GRIM (Brown & Heathers, 2017) and GRIMMER (Anaya 2016 / Allard 2018) check whether a reported **mean** (and **SD**) of **integer-scale** data — counts, or Likert-type items — is mathematically *possible* for the stated sample size. A mean of N integers must equal a whole number divided by N, so at a given decimal precision only certain means can occur; GRIMMER extends the same logic to the standard deviation.

It's an **assisted calculator**, not a scanner: in the **METHODS** pane, open **Data consistency (GRIM)**, then type a value you're reading — the **mean** (and optionally **SD**), **N**, and **items** (the number of scale items averaged per score; leave 1 for a single integer measure) — and click **Check**. You get:

- **GRIM:** consistent, or **impossible** with the **nearest possible** means shown (so you can see how far off it is).
- **GRIMMER** (when you enter an SD): consistent or impossible, for single- or multi-item scales (set **items**).
- A **no-power** note when N is large for the precision (then almost any mean is achievable, so GRIM can't say much).

Read it as a prompt, not a judgment:

- It only applies to **integer-scale** data — not continuous measures (reaction times, proportions). An inconsistency is usually a typo or a misreported N; it is **a prompt to look, never a verdict or an accusation**.
- Because *you* enter a specific value, it never scans, ranks, or labels papers or people.
- The section credits the methods (Brown & Heathers; Anaya / Allard) and offers a one-click **add to library**.

<!-- section: duplicates -->
## Finding possible duplicates
The **Duplicates** scan helps you find likely duplicate records without automatically deleting or merging anything.

To use it:

- Click **Duplicates** in the Library header.
- Wait while Callosum scans your library.
- Review each **Possible duplicates** group.
- Click **open** to inspect a paper.
- Click **delete** on the redundant copy if you are confident.
- Click **dismiss** if the group is not a duplicate.

Deleted duplicates go to Trash and can be restored. Dismissing a group marks those papers as "not a duplicate" and **persists** — future scans will not flag that group again, even across restarts.

Changed your mind? Open the **Duplicates** scan and expand **Previously dismissed** at the bottom — each dismissed pair has an **un-dismiss** button that lets the scan flag it again.

How to think about confidence:

- Very high confidence often means shared identifiers or near-identical title/author/year information.
- Lower confidence can still be useful, but you should inspect both records.
- Similar-topic papers can look close by embedding, so do not delete based on confidence alone.

Gotcha: Callosum currently flags likely duplicates; it does not merge records into one canonical paper.

<!-- section: trash-and-restore -->
## Trash and restore
Trash is for reversible cleanup. Deleting a paper moves it out of the active Library, axes, and duplicate suggestions, but keeps it restorable.

To move papers to Trash:

- In the Library, check one or more paper boxes.
- Click **delete** in the bulk bar.
- Confirm the move to Trash.

To restore:

- Click **Trash** in the Library header.
- Find the paper.
- Click **Restore**.
- Click **← Library** to return to the active Library.

To permanently delete (irreversible):

- Open **Trash**.
- Click **Delete forever** on a single paper to purge just that one, or **Empty Trash** in the header to purge everything in Trash.
- Confirm. This removes the paper along with its extracted text, highlights, and search index, and **cannot be undone**.
- Permanent delete is only reachable from Trash — a paper must be moved to Trash first, so a live paper can never be purged in one click.

Gotchas:

- Permanent delete is final — there is no undo. Restore from Trash if you are unsure.
- Trash selection does not carry back and forth between Library and Trash.
- Trashed papers are excluded from **new** synthesis retrieval, so a paper you move to Trash will not be cited in syntheses you generate afterward. Syntheses you generated *before* trashing it are a saved record and are left unchanged.

<!-- section: settings-and-connection -->
## Settings and connection status
Settings are intentionally small right now. Click the gear (`⚙`) in the sidebar to open **Settings**.

Available setting:

- **Dark mode:** switches the app chrome between light and dark themes. The PDF page itself stays light so paper rendering remains readable.

The Callosum logo also carries connection status:

- Connected: the logo shows the connected state, and its tooltip says **Connected** with the verifier version when available.
- Connecting: the app is still checking the local backend.
- Disconnected: the app could not reach the local backend.

If the Library fails to load, the app will show an error and a backend start command. Once the backend is running, reload the page.

<!-- section: ai-help-assistant -->
## Asking the help assistant
The help assistant — the **Ask the help assistant…** box at the top of this Help window — answers questions about using Callosum in plain language and links its answer to the relevant help sections. Click a reference chip under an answer to jump to and highlight that section below. It is conversational, so follow-up questions keep the thread.

It is **optional and off by default**, with its **own** switch — separate from the synthesis/Gemini data-egress gate. That separation is deliberate: the help assistant only ever sends your question and the **public help text** — never your library, PDFs, or metadata — so you can use it even when data egress for your library is turned off.

To enable it, start Callosum with `CALLOSUM_HELP_ASSISTANT_ENABLED=1` and a `GOOGLE_API_KEY`. When it is off, the box tells you how to turn it on, and the written help below still works normally.

Tips:

- Use it to find the right section fast, then read that section for the details.
- If a question is not covered by the help, it will say so — the written docs below are the source of truth.

<!-- section: privacy-and-data-egress -->
## Privacy and data egress
Callosum is local-first by design. Your PDFs, extracted text, chunks, embeddings, search, axis scoring, duplicate scanning, clustering, and citation verification run on your machine.

The app remains useful offline after import and processing. You can browse, read PDFs, edit details, score axes, manage highlights, scan duplicates, and inspect saved syntheses without sending library text to a remote service.

The features that can use Gemini are optional and off by default:

- **Synthesis generation:** sends selected source text needed to generate a draft answer.
- **Search related terms:** sends axis text so Gemini can suggest possible terms.
- **Suggested axis label polishing:** may send a small set of representative paper titles when egress is enabled; otherwise it falls back locally.

To enable Gemini-backed features, start Callosum with data egress explicitly allowed and a Gemini API key configured. In the current app, the relevant settings are `CALLOSUM_ALLOW_DATA_EGRESS=1` and `GOOGLE_API_KEY`.

Important distinctions:

- Crossref DOI re-resolve sends only the DOI to Crossref.
- Gemini synthesis can send library text, so it is behind the explicit egress gate.
- Axis term suggestions can send your axis wording, so they are also behind the egress gate.
- Verification of citations runs locally after generation; Gemini is not treated as citation evidence.

<!-- section: troubleshooting-and-faq -->
## Troubleshooting and FAQ
### Why is my axis empty?
The terms may be too narrow, the papers may have sparse metadata/text, or the cutoff may be too strict. Add better search terms, lower the cutoff, and re-score. You can also add papers manually with `＋` or confirm uncertain papers with `✓`.

### Why is everything uncertain?
The axis vocabulary may be close to several papers but not close enough to clear the cutoff. Review the uncertain list, confirm true matches, remove false positives, and adjust the cutoff if the axis is consistently too strict.

### Why did my axis show stale?
You changed the vocabulary that scoring depends on. Re-score so the assignments reflect the current terms and description.

### Why is a citation flagged?
The sentence had no citation, or at least one citation did not verify cleanly against the local evidence. Open the source and read the quote before relying on it.

### Why can I open a source page but not see a highlight?
The citation may be region-level, page-only, on a rotated page, or missing usable coordinates. Callosum opens what it can and avoids drawing fake exact highlights.

### Why is Save as highlight disabled?
Only verified citations with exact coordinates can be saved as precise highlights. Region-level, page-only, and flagged citations are not saveable through that button.

### Why did a metadata edit get overwritten?
Ordinary hand edits are protected from batch updates, but clicking `🔎` asks Callosum to re-resolve from Crossref and refresh the record from that DOI. Use re-resolve intentionally.

### Why does a paper say PDF not available locally?
The record may be metadata-only, URL-only, or linked to a file that is not present on disk. The paper can still be managed bibliographically, but PDF reading and exact citation jumps need a local PDF.

### Why does synthesis say it needs data egress?
Synthesis generation uses Gemini in the shipped app. Enable `CALLOSUM_ALLOW_DATA_EGRESS=1` and `GOOGLE_API_KEY` before starting Callosum if you want to use it.

### Why did duplicate scan not delete anything automatically?
Duplicate detection is flag-only. Callosum shows likely duplicate groups so you can inspect them and decide what to move to Trash.
