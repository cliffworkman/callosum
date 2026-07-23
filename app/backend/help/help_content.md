<!-- section: getting-started -->
## Getting started
Callosum is for working through a scholarly PDF library on your own machine. Use it to browse papers, open PDFs, add highlights and notes, organize the library with axes, and ask synthesis questions that come back with evidence you can inspect.

The most important habit is to treat Callosum as an evidence workbench, not a magic answer box. When it writes a synthesis, the answer is AI-proposed, but each cited sentence is independently checked against the source PDFs. You see the supporting quote, page, confidence scores, and whether the sentence is verified, flagged, or **contradicted** (a cited source actively disagrees).

The app is local-first. After your library has been imported and processed, extraction, search, embeddings, axis scoring, duplicate scanning, and verification run locally. The app remains useful offline. The optional Gemini features are off by default and only run when you explicitly enable data egress.

Start by:

- Open the app in your browser.
- Check that the Callosum logo in the left sidebar shows the connected state.
- Browse the Library in the center pane.
- Select a paper to show editable Detail information on the right.
- Double-click a paper, click a file in Details, or open a synthesis citation to view the PDF.

<!-- section: app-layout -->
## Finding your way around
Callosum has three panes, plus a **menu bar** across the top of the center pane that switches **workspaces** (what you're doing right now):

- **Menu bar (top of the center pane):** switch between **My Publications** (your publications + impact), **Library** (your collection + open PDFs), **Synthesize** (Ask + Critique), **Discover** (Feed, Search, Wanted, Gaps, Overlooked, Journals, Funding), and **Work** (Cite, Meta-Reference, CRediT, Meta-Analyze — citing, reference-list analysis, credit statements, and meta-analysis dataset prep). **Help** and **Settings** sit at the right of the menu bar and open as full-width views.
- **Left pane:** an **accordion** with **Axes** (plus a **Tags** tab — your labels alongside your conceptual lenses), the reading queue, and review/findings sections — click a section header to open it (one at a time).
- **Right pane:** a **Details** accordion — the editable bibliographic info for the paper you've selected (a hint until you select one).

The three panes stay put; only the center changes as you switch workspaces. On a phone-width screen, the center pane uses a compact **Workspace** dropdown instead of the full desktop tab strip. The side panels resize with the vertical grips and collapse with the chevron next to each. Within a side pane the open section is remembered between sessions, and in-progress workspace tasks stay mounted while you switch away.

Under **Library**, the workspace has a **Library** tab (your list), a temporary tab for the selected-but-unopened paper, and one tab per open PDF. Click the temporary selected-paper tab to open the PDF; once open, it becomes a normal PDF tab. Open PDF tabs can be dragged to reorder them, and switching workspaces keeps those PDFs mounted so you don't re-open a document each time. Open papers live under Library; switch to My Publications / Synthesize / Discover / Work and they're tucked away until you come back.

In **Discover → Journals** and **Discover → Funding**, the selected paper appears before the Discover sub-tabs using that same tab language: dashed accent if it is selected but not open, and the normal open-PDF tab style if it is already open. Click the cue to open or return to the reader for that paper.

Tips:

- Select a paper once to inspect its metadata in **Details** (right pane).
- Double-click a paper in the Library to open its PDF.
- Click paper titles inside an axis to open their PDFs and follow them in Details.
- **Help** and **Settings** are on the menu bar (top-right of the center pane).

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
Your **library folder is watched by default** — it's pinned at the top of the **+ Add → Watched folders…** dialog as the "always watched" default (you can't remove it). Drop a PDF into it and Callosum picks it up on its own (see below). To watch additional folders, open that dialog, enter a folder's path on this computer, and click **Add + scan**. (The library folder is where Callosum keeps acquired PDFs; set a custom location with the `CALLOSUM_LIBRARY_DIR` environment variable.)

Callosum walks the folder for PDFs and reconciles them with your library:

- **New** PDFs are added — text extracted, chunked, embedded, and metadata fetched from Crossref where a DOI is found. Any whose DOI doesn't resolve land under **Unsorted** so you can fix them.
- **Unchanged** PDFs (already in the library, matched by **content**, not filename or folder provenance) are skipped — re-scanning is safe and never creates duplicates.
- **Removed** PDFs (a previously-scanned file that's now gone from the folder) are flagged as missing, not deleted.

Once you've added a folder it becomes a **watched folder**: Callosum re-scans your watched folders **automatically each time the app starts and whenever you switch back to the app** — so if you drop a new PDF into a watched folder and return to Callosum, it appears on its own within a moment (you can also click **Re-scan all** in the dialog). If a scan or re-scan is already running, another scan request reuses that active job instead of starting a second writer. A newly-picked-up PDF has its DOI read from the file, its metadata filled in from Crossref, and (if you've run a retraction check) it's checked for retraction automatically. The dialog lists your watched folders with when each was last scanned; **remove** stops watching a folder but keeps the papers it already imported. Because matching is by content, the folder your existing library came from is safe to add — re-scanning it just confirms everything's already there. You can turn the on-launch re-scan off in **⚙ Settings → Library**.

Your PDFs stay where they are — watching links to them in place and never moves or copies anything. It reads only the folders you've added, on your own machine, and never sends your PDFs anywhere (only the DOI lookup talks to Crossref, the same public metadata service used elsewhere).

<!-- section: ocr-scanned-pdfs -->
## Making a scanned PDF searchable (OCR)
Some PDFs are **scanned images** with no underlying text — you can see the words, but the computer can't read them, so they never show up in search, don't get embedded, and can't be cited. When a paper's PDF has no text layer, its **Details** pane shows an **"OCR this paper (scanned)"** button. Click it and Callosum runs **OCR** (optical character recognition) **entirely on your machine** — nothing is uploaded.

It renders each page, recognizes the text, and saves a **searchable copy** of the PDF with an invisible, correctly-positioned text layer over the original page images. After it finishes (you'll see page-by-page progress), the paper is fully first-class: it turns up in search, gets embedded for synthesis, and its citations highlight **exactly** on the page — and you can select and copy text in the viewer. Your original scanned file is kept; the searchable copy just becomes the one Callosum reads.

This needs the free **Tesseract** OCR engine installed on your computer (a one-time setup: `winget install UB-Mannheim.TesseractOCR` on Windows, `brew install tesseract` on macOS, or `apt install tesseract-ocr` on Linux). Callosum finds it automatically in the standard install locations — you don't need to add it to your PATH; if it's installed somewhere unusual, set the `CALLOSUM_TESSERACT_PATH` environment variable to its path. If it isn't installed at all, the button tells you so and nothing else happens.

<!-- section: importing-citations -->
## Importing a citation file (BibTeX, RIS, CSL-JSON)
To bring in references from another reference manager, open **+ Add → Import file…** at the top of the Library and choose a **BibTeX** (`.bib`), **RIS** (`.ris`), or **CSL-JSON** (`.json`) file. Zotero, Mendeley, EndNote, and Callosum itself can all export one of these formats. This is the mirror image of **Exporting citations** — what you export, you can re-import.

Each entry in the file becomes a metadata-only library paper (title, authors, year, journal, DOI, type, …). Entries already in your library are skipped (matched by DOI, or by title + year + first author when there's no DOI), so re-importing the same file is safe and creates no duplicates. Anything the parser can't read is skipped and counted rather than failing the whole import; the summary reports "N imported · M already in library · K skipped".

Import brings in **metadata only** — no PDF is attached (add PDFs via **Scan folder**, Zotero, or **Acquire OA copy**). It runs **entirely on your machine**: the file is read in your browser and nothing is sent anywhere — no DOI lookup, no other network call. Imported papers are searchable and can be filtered by **type**; because the file is treated as your authoritative metadata, a later batch re-resolve won't overwrite it unless you explicitly re-resolve that paper.

<!-- section: sharing-a-library -->
## Sharing a library (bundle export/import)
A **library bundle** is a single `.json` file that carries your **paper metadata, tags, highlights + notes, axis definitions, and syntheses** — but **no PDF files**. It's how you hand a library (or a slice of one) to a collaborator without a server and without redistributing copyrighted PDFs: they re-acquire their own copies (via **Acquire OA copy** or their own reference manager), while your notes and organization travel.

**Export.** Open **+ Add ▾** at the top of the Library:
- **Export library bundle…** saves your *whole* library (axis definitions + all syntheses) as `callosum-library-bundle.json`.
- Or select some papers (checkbox) and use the selection bar's **bundle** action to export just those papers + their tags + highlights + any synthesis over exactly those papers (a selection doesn't carry axes).

**Import.** **+ Add ▾ → Import bundle…** → pick a `.json` bundle → **Import**. Merging is **additive and non-destructive**: a paper you already have (matched by DOI, or title + year + first author) keeps *your* metadata and simply gains the bundle's tags + highlights; papers you don't have are created (metadata-only). Tags merge by name; a keyword axis arrives as a definition you can **Score** locally; a curated axis brings its hand-picked members. Re-importing the same bundle changes nothing (it's idempotent).

**Imported syntheses are relayed, not re-verified.** A synthesis you receive is shown clearly as **the sender's assessment, not re-checked in your library** — its verified/flagged statuses were computed against the sender's PDFs. Each citation opens at the source paper's **page** (region precision, never a fabricated exact highlight), and a citation whose source paper you don't have still shows its quote (marked "Source not in your library"). You always see the evidence and decide; the app never re-labels a relayed synthesis as your own verified one.

**Re-verify against your library.** An imported synthesis carries a **Re-verify against my library** button. It re-runs the local verifier (embedding retrieval + NLI + quote-location) over *your* copies of the cited papers and turns the synthesis into a native, locally-verified one — the "imported" banner disappears and the statuses become *yours*. It runs **entirely on your machine** (no AI, no network). A claim your library actually supports (with the same quote in your PDF) gets an exact highlight; a claim it doesn't support flips to flagged; a claim whose source paper you don't have is shown flagged with no citation (never silently "verified").

Everything stays on your machine — the file is read in your browser and merged locally; nothing is sent anywhere. One honest limit remains: a **highlight's box** only re-appears once you have the *same* PDF (the note, page, and highlighted text always land, since the bundle carries no PDF). Bundles are the portable, no-lock-in form of your library — plain JSON you can open and inspect.

<!-- section: reading-on-your-phone -->
## Reading on your phone (mobile)

callosum's window is **responsive** — open it on a phone-width screen and the three-pane layout collapses to a single column with a bottom nav (**Library · Panels · Details**). In the Library region, use the compact **Workspace** dropdown to switch between Library, Synthesize, Discover, Work, Help, and Settings without side-scrolling a desktop menu. You browse and search the library, open a paper (its metadata, abstract, and the PDF, rendered by your phone's own viewer), and read its verified syntheses. On a wider screen the usual desktop layout returns.

To reach it from your phone you use a **cloudflared tunnel** (the same outbound-only bridge the Google Docs add-on uses), configured **read-only**. Read-only is a deployment: you run a second callosum instance for the tunnel with **`CALLOSUM_READ_ONLY=1`** (which makes the server reject *every* change — scan, edit, tag, delete — with a 403) and Remote access on (so an access token gates all access). Your desktop instance stays fully editable; the phone reads the same library. The full runbook is `adapters/mobile/README.md`. You can't accidentally change anything from your phone.

When callosum is running read-only, it shows a small **Read-only** badge and hides the write controls — no "+ Add", no edit fields (bibliographic details show as plain text), no scan/import/enrich, no tag or axis editing, no synthesis-generate. You browse, read PDFs, and read your saved syntheses; everything is view-only, so nothing you tap can change your library.

On a phone the PDF reader is tuned for touch: pages fit the screen width by default, **pinch to zoom** in and out, and the zoom buttons still work if you prefer. When you tap a verified citation in a synthesis, callosum jumps to the source PDF on the highlighted page and shows a **"← Synthesis"** pill — one tap takes you back to the exact synthesis you came from, so you can read a claim, check its source, and return without losing your place.

You can also **highlight by touch**: long-press to select a passage in the PDF (drag the handles to extend it), and the color-picker pill appears next to your selection — tap a color to highlight it, or **＋ note** to highlight and jot a note. It's the same highlights you make on the desktop; tap a highlight later to recolor it or edit its note.

<!-- section: browsing-and-searching -->
## Browsing and searching the Library
The Library is for quickly finding papers and opening the ones you want to read. It shows each paper's title, authors, year, venue, processing tier, and file count.

Use the search box to filter the library. By default it searches across **all** of a paper's stored fields — title, **every** author (not just the first), journal, year, DOI, abstract, and the rest of the bibliographic record — so searching your own surname finds every paper you co-authored, not only the ones you led. Use the dropdown beside the search box to narrow the scope to **Title**, **Author**, or **Journal** when a broad match returns too much. Search is debounced, so results update shortly after you stop typing. The list shows up to 50 papers per page; use **Prev** and **Next** when there are more results.

Use the **Sort** dropdown to order the library by **date added**, **title**, **publication year**, or **first author**, and the **▲/▼** toggle beside it to flip the direction (ascending ↔ descending). Papers without a year or author sort to the end. (**Most cited**, **By priority**, and **Unread first** are explicit one-way sorts with no direction toggle.) Your sort choice is remembered across sessions, and sorting works alongside search, the Trash view, and an axis filter.

**Saved searches.** Once you've set up a combination you return to — a search term, a scope, a sort, an axis or tag filter, the Unsorted view — open the **Saved ▾** menu in the Library header and choose **Save current search…** to name it. Pick it from that menu any time to re-apply the whole combination at once, or **×** to delete it. A saved search just remembers your existing filters; it's distinct from an **axis** (a semantic lens that scores papers by meaning) — and Callosum never reduces a paper to a rating or score, so saved searches and tags stay the flexible, multi-dimensional way you organize.

**Searching inside your PDFs (full text).** Set the search scope to **Full text (PDFs)** to search the extracted text *inside* your papers — the exact-wording complement to axes and synthesis. Type a phrase and you get a list of matches: each result shows the paper, a snippet with your terms **highlighted**, and the page, with **Open at page** to jump straight to it in the PDF. This is a literal/verbatim search ("find the exact phrase"), not a meaning-based one — for concepts and themes, use an **Axis** or a **Synthesis** instead. Only papers whose text has been extracted are searched, and Callosum computes no relevance score you'd cite — the ordering just surfaces the strongest verbatim matches first.

**Citation counts.** Click **Citations ↻** in the Library header to fetch each paper's cited-by count from OpenAlex (using its DOI). Once fetched, every card shows a **"N cited-by"** chip, and a **Most cited** option appears in the Sort dropdown — an explicit, opt-in ordering you choose, never the default. The count is shown verbatim and attributed (hover for "per OpenAlex · as of <date>", and the control itself shows the date) — Callosum never folds it into a hidden "impact score" or silently re-ranks your library by it. A paper with no DOI or no OpenAlex record shows **no** chip (not a misleading "0") — absence means "not looked up," not "uncited"; a genuine zero shows "0 cited-by". Only the DOI is sent to OpenAlex (public metadata) — this is not the AI/Gemini setting, and no library text leaves your machine.

Use the **Type** dropdown (shown when your library has typed papers) to narrow the list to one document type — journal article, book, conference paper, preprint, and so on. It only offers types that are actually present, each with a count, and composes with search and sort.

Use the **◫ Missing PDF** toggle to show only papers with no local PDF — the ones you still need to fetch a copy for (the same set the Text-Health check flags as "no local PDF"). The **read**, **priority**, and **Missing PDF** filters are all available in the **Trash** view too, so you can search and narrow deleted papers the same way as the live library.

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

The **Notes** panel lists every highlight in the paper (with its page and a snippet of the highlighted text); click a row to scroll to it and flash it. When you have at least one highlight, the panel header offers **Copy** and **Export .md** — they assemble all your highlights and notes for the paper into a Markdown digest (each as the highlighted text, its page, and your note), so you can copy them out or save a `*-notes.md` file to take your marked-up reading elsewhere.

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
- **Search** the list (matches a note *or* the highlighted text) or tick **Noted** to show only highlights that carry a note.
- **Copy** or **Export .md** turns all of a paper's highlights + notes into a page-ordered Markdown digest.
- Step through marks in the page without the panel: **◂ Mark / Mark ▸** in the toolbar (or the **[** and **]** keys) jump to the previous/next highlight. The reader also remembers where you left off and reopens a PDF at that scroll position.

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
- URL, plus additional labeled URLs for preprints, OSF pages, project pages, code, data, or publisher alternatives
- Abstract
- Identifiers such as DOI, ArXiv ID, PMID, Cite key, ISBN, and ISSN
- Extra fields in **More**, when available

Fields auto-save when you leave them. For authors, enter one author per line. For numeric date fields, non-numeric input is ignored and the previous value is restored.

The **More** section holds any extra bibliographic fields (for example ones a DOI lookup filled in beyond the core set), and lets you **add your own**: type a field name (letters, digits, `-`/`_`) and a value, then **+ add**. Fields that have their own editor above (title, DOI, …) are reserved and can't be re-added there.

The **Files** area lists available attachments. Click a file to open *that specific* PDF — useful after a merge
(see Duplicates & merge) leaves a paper with more than one, e.g. a preprint alongside the published copy.

If a local PDF already has extracted text, Details also shows **Reprocess PDF text**. Use it after Callosum learns a
better extraction pattern or when an older import is missing newer text metadata such as section labels. It re-reads
the same local PDF and replaces only its extracted text chunks; your bibliographic metadata, files, tags, highlights,
notes, and annotations are preserved.

The Library header also has **Text Health**. It opens a queue grouped by local PDFs with no extracted text, unusually
little extracted text, stale extraction provenance, or older chunks missing section labels. From there you can inspect
affected papers, open them, filter the Library to one text-health group, or reprocess only the papers missing section
labels or stale extraction rows. If you select papers with checkboxes, the bulk bar offers **reprocess text** for that
explicit selection. These actions do not OCR, do not fetch metadata, and do not send PDFs or text anywhere. Papers with
no extracted text get a **details for OCR** action that selects the paper and opens Details so you can decide whether
to run the separate **OCR this paper (scanned)** workflow.

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
- BibTeX / RIS / CSL-JSON are machine-readable interchange formats; the **Cite as** row (above) also renders formatted human styles (APA, MLA, …).

<!-- section: suggesting-citations -->
## Suggesting citations for a draft sentence
The **Work → Cite** tab helps you find which papers to consider citing for a sentence you're writing. By default it searches **your library** only and tells you whether each candidate **supports**, **contrasts**, or merely **mentions** your claim. That default path runs entirely on your machine (no AI is sent off-device).

To use it:

- Open **Work → Cite**, paste a sentence from your draft into the box, and click **Suggest**.
- Callosum ranks your library by how closely each paper's text matches your sentence and shows a card per paper with:
  - a **stance** pill — **supports** (green), **contrasts** (amber), or **mentions** (grey) — read from a local language model over the matched passage. If the model can't be loaded, the card says "stance unavailable" rather than guessing.
  - a **match** score (relevance to your sentence — a ranking aid, **not** a correctness claim).
  - the **verbatim quote** from the matched passage — the evidence; read it to decide whether the paper really fits.
- **Open source region** opens that paper's PDF at the page so you can read the passage in context (the match is a passage *region*, not an exact highlight).
- **Copy BibTeX** puts the paper's citation on your clipboard to drop into a reference manager or your manuscript.
- To widen the pool, turn on **Also search beyond my library** before clicking **Suggest**. Callosum sends only the draft sentence/description you pasted to public metadata providers such as Crossref, PubMed, and OpenAlex, then shows outside-library candidates in a separate section. It also uses the top local library matches as OpenAlex graph anchors, so an outside-library candidate may be labeled as **cited by**, **cites**, or **related to** a locally relevant paper. These candidates are based on public metadata, abstracts, and graph relationships; if stance is shown, it is **abstract-level** and weaker than full-text library evidence.
- Outside-library candidates can be added as metadata-only library records with **Add to library**. A public metadata miss is not evidence that no relevant paper exists.

The first **Suggest** in a session loads the local models, so it can take a few seconds; later suggestions are fast. Ranking is by relevance to your sentence (never by citation count), and Callosum only **proposes** — you decide which paper is the right citation. The same library-only Suggest is also available **inside LibreOffice Writer** (see *Citing in LibreOffice Writer*).

<!-- section: cite-in-libreoffice -->
## Citing in LibreOffice Writer
Cite straight from your callosum library while you write in **LibreOffice Writer** — like Zotero or Mendeley, with a dedicated **Callosum** menu and toolbar.

**Install it once:** open **Settings → LibreOffice plugin → Install plugin**. LibreOffice's Extension Manager opens — click Install, then restart Writer. (Or use **Download .oxt** and double-click the file.) The callosum app must be running for the plugin to reach it.

A **Callosum** menu (and toolbar) then appears in Writer:

- **Add citation…** — the composer: search your library **live as you type**, add one or more results to the citation you're building, and watch a **real rendered preview** update as you go, before you click **Insert**. Building a grouped citation like `(Smith, 2020; Jones, 2021)` from scratch is one composer session, not insert-then-merge. Select an assembled source and click **Options…** to set a **locator** (page / chapter / section / … — a fixed vocabulary), a **prefix**/**suffix** (e.g. "see …"), or **suppress the author** / show **author only** — each applies to this citation only, your library record is never touched. **Move ↑ / ↓** reorders sources manually (a citation style with its own sort rule, like APA, may still reorder them at render time regardless — the preview always shows the real result, so you'll see this rather than be surprised by it). Check **Also search beyond my library** to widen the search the same way the in-app Cite panel does (see *Verified citation suggestions*) — off by default, opt-in each time; picking an outside-library result adds it to your library first, then cites it.
- **Suggest citation** — select the sentence you're writing; callosum suggests papers by relevance, with stance + a quote (and the same beyond-library option), the same engine as the in-app Cite panel.
- **Insert citation by id…** — if you already know a paper's callosum id.
- **Edit citation…** — place your cursor inside an existing citation and reopen the same composer, pre-populated with its current sources and options — add, remove, reorder, or change locators/prefixes without starting over. It's still the same citation; only its contents change.
- **Delete citation** — removes the citation, both the field and its rendered text.
- **Merge with next / previous citation** — combines the citation at the cursor with the adjacent one into a single grouped citation.
- **Split citation** — reverses a grouped citation back into that many separate single-work citations.
- **Open in callosum** — opens the cited paper's page in the callosum app (a browser tab). For a grouped citation, opens the first source only.
- **Refresh / renumber + bibliography** — re-render every citation and rebuild the bibliography (numeric styles renumber by position; run it after edits or after moving citations). For a large document, **Refresh citations only** leaves the bibliography untouched, while **Refresh bibliography only** leaves citation text untouched and works even when automatic bibliography rebuilding is paused.
- **Toggle automatic citation formatting** — switch to manual refresh mode for a large document. Citation inserts and edits remain structured live fields, but visible text waits for **Refresh / renumber + bibliography** or **Refresh citations only**; new pending inserts show `{citation}`. Turning automatic formatting back on affects later changes, so run one explicit refresh for existing pending changes. Bibliography auto-rebuilding is controlled separately. Whenever a Callosum operation leaves citation formatting or the bibliography pending, Writer shows a non-dismissible **Callosum refresh pending** bar naming the stale surface(s); **Refresh pending** updates exactly those surfaces and removes the bar. The flags persist in the document, and the bar returns on the next Callosum command after reopen. Writer-only manual moves are not yet detected, so run a full refresh after those edits.
- **Citation style…** — pick a CSL style (apa, ieee, nature, …) and locale; the whole document re-renders.
- **Insert bibliography here** — moves the bibliography to the cursor (run it again elsewhere to move it there instead).
- **Toggle automatic bibliography rebuild** — pause the bibliography specifically; citations still update normally on Refresh.
- **Document diagnostics…** — a read-only health check: reports a malformed citation, one written by a newer callosum schema this plugin doesn't understand, a citation-id collision, a citation whose source paper is no longer in your library, or a damaged/not-yet-built bibliography. Never changes your document.
- **Citations in this document…** — shows each unique cited work, occurrence count, missing/retraction status, and a jump-to-first-occurrence action. From the same snapshot you can exclude a cited work from the bibliography or add an uncited work as further reading; reopen the panel after document edits to refresh its list.
- **Prepare submission copy…** (recommended for hand-off) — saves a **separate** copy with citations converted to static text; your open document is never changed.
- **Flatten to static text** — the advanced, in-place option: converts citations to plain text in *this* document directly. One-way — prefer Prepare submission copy unless you specifically want to keep editing the flattened version.
- **Insert CRediT statement** — inserts the contribution statement you built in **Theory → CRediT statement → Send to LibreOffice**, as plain text at the cursor.
- **Server URL…** — only needed if you run callosum on a non-default port.

Everything is local: the plugin talks only to callosum on your own machine (plus public metadata providers, only if you opt into "Also search beyond my library"), and all formatting is done by callosum's citation engine (so it matches the in-app "Cite as…"). Nothing else leaves your machine.

<!-- section: cite-in-word -->
## Citing in Microsoft Word (desktop)
You can also cite from your callosum library inside **desktop Microsoft Word** (Windows/Mac) with a task pane that searches your library and inserts citations. Because a Word add-in is a small web page, Word requires it to be served over HTTPS — so callosum serves it **on your own machine**, and nothing leaves your computer (it can't run in Word-on-the-web, which has no access to your local library).

**Set it up once:**

1. **Trust a local certificate** — run `npx office-addin-dev-certs install` (so Word accepts `https://localhost`).
2. **Run callosum over HTTPS** — run `python tools/run_https.py`, then open the app at **https://localhost:8443**. (Plain HTTP on :8080 still works for everyday use; HTTPS is only needed while citing in Word.)
3. **Add the manifest to Word** — in **Settings → Microsoft Word add-in → Download manifest**, then sideload it (Windows: register the folder as a Trusted Add-in Catalog; Mac: drop it in Word's `wef` folder — see `adapters/word/README.md`).

Then in Word: **Home → Callosum → Show Citations**. The task pane mirrors the LibreOffice plugin:

- **Search → insert** a live citation at the cursor (pick a style, type author/title/year, click a result).
- **Suggest from the sentence** — place your cursor in the sentence you're writing and Callosum ranks your library by relevance, showing each candidate's stance (supports / contrasts / mentions) and a quote; pick one to insert after the sentence.
- **Refresh / renumber + bibliography** — re-render every citation in document order and rebuild the **References** list (numeric styles renumber by position, like Zotero).
- **Citation style** — changing the dropdown re-renders the whole document in the new style (remembered per document).
- **Flatten to static text** — convert the live citations + bibliography to plain text for hand-off (one-way).

Everything is local: the task pane talks only to callosum on your own machine, and all formatting is done by callosum's citation engine.

<!-- section: tags -->
## Tagging papers
Tags are lightweight, free-form labels for organizing your library — a quick complement to the semantic **axes**. (If you imported from Zotero, your existing Zotero tags already appear here.)

To tag a paper:

- Click a paper to open its Details pane.
- In the **Tags** row, type a tag and press Enter. As you type, Callosum suggests tags you've used before. If a tag edit is rejected, the row shows the reason inline.
- A tag can be on as many papers as you like; the same name is shared (not duplicated) across papers.

To get tag ideas, click **✨ Suggest**: Callosum proposes candidate tags drawn from the words most distinctive of that paper compared to the rest of your library, and you click the ones you want to keep. This runs entirely on your machine — no AI is sent off-device, and nothing is added until you accept it.

Callosum also imports **author/index keywords** as tags so the authors' own concept work becomes a first-order set of labels:

- **Zotero tags** come in automatically when you import a Zotero library.
- **Crossref subject categories** are added whenever a paper is resolved against Crossref — including when you click **🔎** on its DOI. To apply this across an already-imported library in one pass, run `python tools/backfill_keyword_tags.py` (it reuses cached Crossref data where possible and only adds tags — it never overwrites your edited metadata).

The **✨ Suggest** pass then fills gaps the authors' keywords missed (it skips terms you already have).

Tags you added and tags that were **imported** (Zotero tags, Crossref subject keywords) are distinguished by a subtle visual difference rather than an extra label — imported keyword tags appear in a quieter, muted style, while the ones you typed keep the accent color. Hover any tag to see exactly where it came from. They all behave the same — click to filter, **×** to remove.

**Coloring a tag.** Click the small dot at the left of any tag chip (in a paper's Details) to pick a color from a fixed palette — or clear it with **×**. A colored tag stands out across the library (the sidebar Tags tab shows a matching dot). Colors are just a visual aid you choose; Callosum never rates or scores a paper itself — tags (with or without color) are the flexible, multi-dimensional way to judge papers, and there is no single star rating that would flatten a paper to one number.

To browse and remove:

- The left pane's **Tags** tab (the second tab of the **Axes** section) lists every tag with its paper count (it's always available — when you have no tags yet it shows a hint pointing you to add them from a paper's Details). Click a tag to **filter the library** to it — a quick way to navigate by tag without opening a paper first. When your library has both imported keyword tags and tags you typed, an **All / Yours / Keywords** filter appears at the top of the section to narrow the list by source, and — whenever the visible list spans more than one source — the list itself groups under a small header per source ("Your tags," "Crossref subjects," "Zotero import," …) so you can tell at a glance where each tag came from.
- Click a tag's name in a paper's **Tags** row to **filter the library** to every paper carrying that tag (a "Filtered to tag …" banner appears; click **clear** to return). The tag filter and the axis filter are mutually exclusive.
- Click the **×** on a tag to remove it from that paper. A tag that ends up on no papers is cleaned up automatically (and disappears from the sidebar panel). Removing an **imported keyword** tag is durable: a later re-resolve or keyword backfill will not silently bring it back. (Re-adding the tag by name lets it return.)

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
- **That DOI is already on another paper.** Callosum now allows this temporarily so a raw PDF record can be identified, enriched, and merged with a metadata-only duplicate. Use duplicate detection or the merge action to clean it up.

Gotcha: Re-resolve can overwrite fields from Crossref because you explicitly requested a refresh. If you have carefully hand-edited a record, use this intentionally.

<!-- section: enriching-metadata -->
## Filling in missing metadata (gap-fill enrichment)
Records often come in with gaps — a missing DOI, no abstract, a blank venue. **Enrichment fills only the empty fields**, drawing on several public sources in turn, and **never overwrites a value you typed**. (This is the opposite of 🔎 re-resolve, which deliberately *refreshes* a record from its DOI.)

How it works, per paper:
- If the paper has **no DOI**, Callosum tries to recover one — first from the PDF, then by searching Crossref for the title (it only adopts a DOI when the title clearly matches and the year agrees, so it never guesses a wrong one).
- It then asks each source in turn for a bibliographic record and **fills any blank field** (abstract, venue, year, authors, type, …) from the first source that supplies it. The sources, in order, are **Crossref**, **OpenAlex**, **Europe PMC**, and **PubMed** (the last two are especially good at supplying a missing abstract). Only public bibliographic metadata (a DOI, PMID, or title) leaves your machine — this is **not** the Gemini library-text gate.

Two ways to run it:
- **One paper:** open its Detail pane and click **Fill missing fields** (next to the 🔎). It reports which fields it filled.
- **Your whole library:** click **Metadata ↻** in the Library header. It runs in the background with a progress count; the tooltip reports how many DOIs it recovered, how many fields it filled, and how many papers still have no DOI.

Because it only ever fills blanks, it's safe to run across everything — including papers you've hand-edited (your typed values stay exactly as you left them, and a hand-edited paper keeps its "hand-edited" status).

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

### Get a paper through your library (OpenURL)

When no open-access copy is found and your institution subscribes to the journal, Callosum can hand you off to your library's **own official link resolver** so you can get a copy you're legitimately entitled to — without leaving Callosum to hunt for it. It is **optional and off until you set it up.**

- Set it up once in **Settings → Library access**: paste your library's **link-resolver (OpenURL) base URL** (find it on your library's "off-campus access" or "get full text" help page).
- Then, after an open-access miss, click **Get via my library**. Callosum builds a standard **OpenURL** from the paper's DOI and details and **opens your library's resolver in your browser**. You sign in there exactly as you normally would; your resolver routes you to the licensed full text; you download it and attach it to the paper (or drop it in your library folder, where Callosum picks it up).

What Callosum does and doesn't do here: it **only builds a link and opens it in your browser.** It never signs in for you, never stores your login or session, never fetches the paper itself, and never scrapes — your own browser and your own credentials do all the access, the same as clicking a "Get it @ your library" link anywhere else. This keeps it firmly on the right side of publisher rules (no automated or bulk downloading). If you have no institution, nothing changes — the free open-access route stays the default and Callosum is fully useful without it. (Uses the NISO OpenURL standard; you can one-click add the OpenURL paper, Van de Sompel & Beit-Arie 2001, to your library from Settings.)

<!-- section: wanted-list -->
## Wanted list & re-checking for copies
The wanted list tracks papers you want an open-access copy of, so Callosum can keep looking for one. Open it from **Discover → Search → Wanted**.

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

**Curated axes (hand-picked, hand-ordered).** Most axes are *keyword* axes — you write the vocabulary and Callosum scores every paper's similarity. A **curated axis** is the other kind: you put the papers in **by hand** and arrange them in the order you want (e.g. "the 12 papers for Aim 2, in citation order"). It's still an Axis — just marked with a small 📌 and with the scoring controls hidden, since there's nothing to score. Create one with the **📌** button in the axes header (then drag papers from the library onto the card to add them, and **drag a member by its ⠿ grip** to reorder). You can also **freeze** a keyword axis into a curated one (the **❄** action on its card): once you've tuned the cutoff and you're happy with the members, freezing snapshots them (the uncertain ones below your cutoff are dropped) and unlocks manual ordering — your hand-picks are never lost. **Convert** a curated axis back to a keyword axis any time (the **↩** action): your members are kept, but the manual order is replaced by fit order, so you'll re-score. A curated axis carries no score or ranking — it's purely the set you chose, in the order you chose.

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
- **Drag a paper** from the Library onto an axis card to add it (a quick manual override — the axis card highlights as you drag over it). The My Publications card is the exception: it's resolved from authorship (use `✓`/`✕`), so it isn't a drop target.
- Click an axis's **count badge** (the number on the right of the axis) to **filter the Library to just that axis's papers**. A "Filtered to axis …" banner appears; click **clear** to return to the full library. From a filtered view you can **select all → summarize** to get a verified synthesis of the whole cluster in a few clicks. When uncertain papers are hidden, the count badge shows the visible (assigned + manual) total, and clicking it filters the Library to that same assigned-only set (the banner reads "… · assigned only") — so what you see on the card is exactly what you summarize.

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

<!-- section: reading-queue -->
## Reading queue (your to-read list)
The **Queue** tab — the third tab of the left-pane AXES section, beside Axes and Tags — is a personal, ordered list of papers you mean to read. It is **not** an axis: there is no scoring, ranking, or AI judgment, just the papers you chose, in the order you chose.

To add a paper:

- **Drag** a library card onto the Queue panel, or
- Open a paper's **Details** and click **+ Reading queue**.

Adding a paper that's already queued does nothing (no duplicates).

The queue is **grouped by priority** — **High / Normal / Low / Unprioritized** — using the same priority you set on a library card (papers you haven't prioritised sit under *Unprioritized*). **Drag a row by its ⠿ grip** to reorder it within its group, or **drag it onto another group to change its priority** — drop it on *Unprioritized* to clear the priority. Your order and priority are saved, and the new priority also shows on the paper's card.

To work through it:

- Click a row to **open the paper**.
- Click **✓** when you've **read** it, or **×** to **remove** it. Both take the paper off the queue (it stays in your library).

Trashed papers don't appear in the queue. The queue lives only on this machine.

<!-- section: reading-markers -->
## Read/unread & priority markers
Each library card carries two personal markers you set **by hand** — they're your labels, never an AI score or judgment about the paper:

- **Read / unread:** a toggle on the card (○ unread → ✓ read). Marking a paper read is a manual choice — opening a PDF does **not** auto-mark it. (This is separate from the reading queue, where ✓ *removes* a paper.)
- **Priority:** a **Priority ▾** badge on the card opens a small picker — **High / Normal / Low**, or **Clear**. Priority is your triage order, not a quality rating: a paper can be low-priority and excellent, or high-priority because it's due tomorrow.

You can then **filter** the library to **Unread**/**Read** or to a priority level (the **Read** and **Priority** dropdowns in the library header), and/or **sort** by **"By priority"** (high → normal → low → unset) or **"Unread first"**. Both markers live only on this machine.

Callosum can gather your own papers into a pinned **My Publications** axis at the top of the Axes panel.

Set it up in Settings (⚙) → **My Publications**: enter your name, any other published-name variants (initials, maiden name), and — recommended — your **ORCID** (which gives an exact match). Then click **Refresh my papers**. (If the optional account is configured on your instance, **Settings → Account → Sign in with ORCID** fills in your verified ORCID + name for you — see "Optional account" under Privacy.)

Callosum resolves your identity against **OpenAlex** (a public scholarly database) and matches its record of your works against your library:

- Papers matched by **DOI or ORCID** are **confirmed** — they appear as members of the axis.
- Papers matched only by **name** (e.g. a scanned PDF with no DOI) appear as **candidates** to review — click **✓** to confirm one as yours, or **✕** to reject it. Your choices stick: a rejected paper is never proposed again, and a confirmed one stays a member.

The card shows a publication count and doubles as a "show only my papers" filter (click the count badge). Newly imported papers that match are added automatically. The 🗑 button dismisses the card (your profile and confirm/reject choices are kept — Refresh rebuilds it). A no-match shows an honest "No OpenAlex author found for [name] — check the name/ORCID."

**The impact dashboard.** Open **My Publications** from the menu bar. At the top is a collapsible **Overview** — headline metrics from your OpenAlex record (total **citations**, **h-index**, **i10-index**, **indexed work count**) beside a year chart you can **flip between publications and citations** (last 10 years). These are OpenAlex's own authoritative figures over your *whole* indexed record (not just your library), shown as-is. The dashboard reads cached data and updates when you refresh from Settings or click **Refresh from OpenAlex** on the **OpenAlex card** at the bottom (which also carries the "as of [date]" provenance, your 2-year mean citedness, affiliation, and a link to your OpenAlex profile). Below the Overview is an **AI-generated research summary**: click **Generate** for a one-paragraph draft describing your work, drawn from your publication titles and abstracts; edit it and **Save**. The draft is yours to rewrite — a starting point, not an authoritative claim. To focus the summary on your most important work, **star** key publications (the ☆ button on each paper in the My Publications sidebar card) and tick **⭐ only** before clicking Generate (the toggle appears once you have starred papers).

**Your publications, as cards.** Below the summary, the dashboard lists every one of your in-library publications as library-style cards you can **search** and **sort**. Tick papers' checkboxes to **summarize** them into a verified synthesis, **export** their citations (BibTeX/RIS/CSL-JSON), download a formatted **bibliography**, or move them to Trash — the same actions as the main library. Double-click a card to open its PDF.

**Citation counts & citing articles.** Each own-pub card shows its **cited-by count** — OpenAlex's own figure, shown as-is (not a Callosum score), as of your last refresh — and you can **Sort → Most cited**. Click the count to open the **citing articles** for that paper: the works OpenAlex records as citing it (a discovery list — OpenAlex's coverage, not exhaustive). **Import** any of them (or **Import all**) to add them to your library as metadata records — they go into your general library, not My Publications, and the PDF is a separate **Acquire OA copy** step. If the counts aren't clickable yet, click **Refresh from OpenAlex** once to fetch the citation data.

**Research domains.** From the publications controls row, click **Break down by domain** to group your confirmed publications into research areas (clustered locally by similarity). Each domain shows its paper count and total citations — your **impact by area** — and clicking a domain re-filters the chart to just that domain's papers (the chart locks to **publications by year** while a domain is selected, and the Citations view returns when you clear it; click a domain again to clear, or select several to combine). Domains are a lens, not a fixed taxonomy: each is labeled from its papers' distinctive terms, and **Re-decompose** recomputes them. This is **LLM-free** local clustering.

Turn on **Group by domain** (in the Publications controls, and independently in the My Publications sidebar card) to lay your publications out **under domain headings** — starred papers first, then the rest, with a final **Other** group for any paper not in a domain. You can **rename** a domain with the **✎** beside it; the rename box suggests the closest-matching name from your existing **Axes**, so your domains and axes can share vocabulary. Renamed domains **keep their names across a Re-decompose** (matched to the new clustering by paper overlap).

**Works not in your library.** The OpenAlex card shows how many works OpenAlex indexes for you versus how many are in your library; click **Review N →** (or **Dismissed (N) →**) on that card to open the review modal. Each entry shows its title, year, citations, and DOI. Click **Import** to add one to your library (it's fetched as a metadata record from Crossref and joins My Publications automatically — only works OpenAlex attributes to *you* can be imported), or **Dismiss** to drop it from the list (useful when OpenAlex over-attributes works that aren't yours). Import brings in the record only; use a paper's **Acquire OA copy** button afterward if you also want the PDF. Changed your mind about a dismissal? The same modal lists **previously dismissed** works with a **Restore** button to send one back to the review queue.

Resolving your publications and the dashboard metrics are **LLM-free** and work offline — only your name/ORCID and public identifiers go to OpenAlex (the same kind of public lookup as resolving a DOI). The one exception is the optional research-summary **Generate**, which sends your own publication titles/abstracts to Gemini and therefore works only with the data-egress gate (`CALLOSUM_ALLOW_DATA_EGRESS`) on; with it off, the charts and metrics still render and Generate shows a consent note.

<!-- section: synthesis-overview -->
## Synthesize: asking questions and critiquing sources
The **Synthesize** workspace has two tabs: **Ask** for citation-grounded answers over your library, and **Critique** for a skeptical read of the selected paper. Ask is best for questions where you want a compact reading guide, not a final conclusion.

There are two ways to run a synthesis:

- **Ask a question.** Open **Synthesize → Ask**, type a question in **Ask a synthesis question about the library...**, click **Synthesize**, and Callosum retrieves the most relevant chunks across your library, generates an answer, and verifies each citation. Read the result under **Verified** and **Flagged · needs review**.
- **Summarize a selection.** Check the papers you want in the **Library**, then click **summarize** in the selection bar. Callosum opens **Synthesize → Ask** and generates a verified synthesis of just those papers (showing a "N selected papers" note), spreading its attention across all the papers you picked. **Optionally type a question in the "Focus on…" box** in the selection bar first: with a focus, the synthesis is *query-ranked* on that question across your selection ("…focused on …"); leave it blank for a general summary.

Use the section buttons (**Methods**, **Results**, **Data availability**, and so on) when you want synthesis to search only particular parts of section-aware PDFs. No section selected means the normal all-chunks behavior. A section filter narrows retrieval only; it does not change verification thresholds or make a claim more certain. Older chunks without section metadata will not match a section filter until the PDF is reprocessed.

Each cited sentence carries a status pill: **verified** (green — the source supports it), **flagged** (amber — it could not be fully verified), or **contradicted** (red, "⚠ source disagrees") — the most consequential case, where the cited passage *actively disagrees* with the claim. A contradicted citation still shows its quote, page, and confidence like any other evidence — it is a **signal to look, not a verdict** that the claim is false. Read the quote and decide.

Saved syntheses appear in **History** (a question shows its text; a selection shows "N papers"), where you can reload or delete them.

If AI features are not enabled, synthesis will not run. **Synthesize → Ask** shows a short **"AI summaries are off"** nudge with an **Enable in Settings →** button that takes you straight to the AI-features section (where you set a key + turn on data egress). The nudge clears once AI is on.

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

Click an evidence quote to open its source. Exact-coordinate citations draw the passage highlight in the PDF; region-level citations only open the page and show an approximate-location note.

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
In the **METHODS** pane (the right-hand panel), open the **Statistics** section; under **This paper** — with a paper selected — there's a **Check statistics** button. It scans the paper's extracted text for inline APA-style statistical tests — `t(28) = 2.10, p = .04`, `F(2, 45) = 3.1, p < .05`, `r(30) = .42, p = .01`, `χ²(1) = 5.2, p = .02`, `z = 2.1, p = .03` — **recomputes** the p-value from the reported test statistic and degrees of freedom, and shows where the reported and recomputed values disagree. It's the statcheck method: a "spellchecker for statistics."

This runs **entirely on your machine** — pure computation over the already-extracted text, no AI and no network. Each result shows the **verbatim matched text**, nearby extracted-text context with the matched statistic highlighted, and its **recomputed p**, with a status pill: **consistent** (green), **inconsistent** (amber — the values disagree), or **decision error** (amber — the disagreement flips significance at p = .05). A count summary reads "N checked · M inconsistent · K decision errors" — these are plain counts, never a hidden "reproducibility score." Click any result to open the PDF source. When Callosum can locally locate the exact statistic in the PDF on the expected page, it draws an exact passage highlight; otherwise it opens the page at region precision.

Read it as a **prompt to look, never a verdict**:

- An inconsistency is usually innocent — a typo, rounding, a one-tailed test, or an adjusted value. It is **not** an accusation of error or misconduct. The recomputation already accounts for the statistic's rounding and tries the one-tailed reading, so correctly-reported results are not flagged. It also reads test statistics reported as a bound rather than an exact value — `F(1, 44) < 1, p > .05`, a common way to report a clearly-null result — and only flags one as inconsistent when **no** value consistent with the reported bound could produce the reported p; an ambiguous case (where some values would and some wouldn't) is left unflagged rather than guessed at.
- It reads only **inline APA-format** tests — it cannot see statistics in tables, Bayesian reporting, or confidence-interval-only reporting. **A clean result is not a clean bill** — it means nothing was surfaced by this specific check.
- It needs the paper's **extracted text**, so it's available once a PDF has been processed (the button explains this otherwise). PDF-to-text conversion can garble symbols like `<`/`>`/`=`, which is why the exact matched text is always shown — so you can see an artifact for what it is.

Evidence snippets show their source precision before you click: **exact highlight**, **region**, **page only**, or **no source page**. Open **Evidence trail** under a Methods evidence item to see the detector name, matched text, page, anchor note, and the boundary/caveat for that detector. The Bayesian, mixed-model, meta-analysis, and transparency auditors use the same source-jump contract for their evidence snippets: if the matched text can be locally located in the PDF on the expected page, Callosum opens with an exact highlight; otherwise it opens the source page at region precision. A region jump is navigation help, not an exact passage claim.

Many method panels include a small source-credit line. Its **＋ add missing to library** button checks DOI-backed sources first, imports only the sources not already in your library, and changes to **✓ added to library** when the full credited set is present.

**Across your whole library:** in the same **METHODS → Statistics** section, under **Whole library**, click **Check all papers**. Callosum runs statcheck over every paper and reports "N papers with statistics checked · M with inconsistencies." If any are flagged, a **⚠ N flagged** chip also appears in the Library header as a shortcut. Either click that chip or **Show flagged papers** in the section to filter the Library to just them (a banner appears; **clear** to return) — then open any one to see its specific tests. This is a **list to review, not a ranking**: papers aren't scored or ordered by inconsistency, and the same caveats apply (usually innocent; inline-APA only; absence isn't a clean bill). Re-run the check after editing papers to refresh it.

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
- The modal credits the method (Simonsohn, Nelson & Simmons, 2014) and offers a one-click **add missing to library**.

<!-- section: data-consistency-grim -->
## Data consistency (GRIM / GRIMMER)
GRIM (Brown & Heathers, 2017) and GRIMMER (Anaya 2016 / Allard 2018) check whether a reported **mean** (and **SD**) of **integer-scale** data — counts, or Likert-type items — is mathematically *possible* for the stated sample size. A mean of N integers must equal a whole number divided by N, so at a given decimal precision only certain means can occur; GRIMMER extends the same logic to the standard deviation.

It's an **assisted calculator**, not a scanner: in the **METHODS** pane, open **Data**, then type a value you're reading — the **mean** (and optionally **SD**), **N**, and **items** (the number of scale items averaged per score; leave 1 for a single integer measure) — and click **Check**. You get:

- **GRIM:** consistent, or **impossible** with the **nearest possible** means shown (so you can see how far off it is).
- **GRIMMER** (when you enter an SD): consistent or impossible, for single- or multi-item scales (set **items**).
- A **no-power** note when N is large for the precision (then almost any mean is achievable, so GRIM can't say much).

Read it as a prompt, not a judgment:

- It only applies to **integer-scale** data — not continuous measures (reaction times, proportions). An inconsistency is usually a typo or a misreported N; it is **a prompt to look, never a verdict or an accusation**.
- Because *you* enter a specific value, it never scans, ranks, or labels papers or people.
- The section credits the methods (Brown & Heathers; Anaya / Allard) and offers a one-click **add missing to library**.

<!-- section: bayesian-statistics -->
## Checking Bayes factors (the Bayesian auditor)
The Bayesian auditor is the Bayesian sibling of statcheck. For a paper that reports **default Bayes factors** inline — for a t-test (e.g. “t(19) = 2.53, BF₁₀ = 3.4”) or a Pearson correlation (e.g. “r(58) = .42, BF₁₀ = 37”) — it recomputes the **default Bayes factor** (the JZS t-test BF of Rouder et al. 2009, or the default correlation BF of Ly et al. 2016 — the closed forms JASP and the *BayesFactor* R package use) from the reported statistic and *df*, and flags where the reported value doesn't reproduce. It's local, deterministic, and uses no AI — nothing leaves your machine.

In the **METHODS** pane, open **Checklists → Bayesian statistics** with a paper selected. It reads the paper's extracted text and recomputes each inline t-test or correlation Bayes factor, showing the **reported** value, the **recomputed** value, and whether it **reproduces** or **couldn't reproduce**.

Read it honestly — it's a signal, not a verdict:

- A Bayes factor depends on the **prior** the authors chose. The auditor recomputes under the *default* prior — for a t-test, under both a paired and a two-sample reading; for a correlation, the single value that *r(df)* determines — and calls a value “reproduced” if it matches within about a factor of 2. **If the paper used a different prior or a design the text can't reveal (e.g. an ANOVA, whose default BF isn't recoverable from F and df alone), a mismatch is expected** — it means “couldn't reproduce under the default prior”, never “wrong” and never an accusation.
- It reads only **inline** t-test and correlation Bayes factors (a BF in a table, or without an adjacent statistic, is invisible), so a clean result is **not** a clean bill.
- There is **no score and no rank** — only per-result outcomes with the recomputed number shown, so you can judge for yourself. Each result opens its page in the PDF.
- The section credits Rouder et al. (2009) and Ly et al. (2016) and offers a one-click **add to library**.

Below the recompute, for a paper that reports Bayesian analysis, a **Reporting checklist** flags whether the core reporting elements from the Bayesian guidelines (BARG, WAMBS, and the JASP guidelines) are present in the text: whether the **prior** is stated (family and scale), whether **convergence diagnostics** (R-hat, effective sample size) are reported, and whether a **prior sensitivity / robustness analysis** is reported. Each item shows the matched sentence (which opens its page) so you can see the evidence.

Read the checklist as a prompt, not a report card:

- It runs **only** on a paper that actually reports Bayesian analysis — a non-Bayesian paper is never checked.
- **“Not found” means we didn't detect it in the extracted text**, not that it's missing — tables aren't read, so check the paper. It is never an accusation.
- **Convergence diagnostics show “n/a”** when the paper uses a closed-form Bayes factor (there are no MCMC chains to diagnose) — that's not a gap.
- The **⚠ check** flag appears only when a *reported* value breaches a convention (e.g. an R-hat above 1.1, or an effective sample size below 400); those thresholds are widely-used **conventions**, cited as such, not laws.
- The credit block (only shown once a paper is confirmed applicable) credits Rouder et al. (2009) and Ly et al. (2016).

**Whole library.** Above the per-paper view, click **Audit all papers** to batch-check your whole library at once; a red **B Bayes · N** chip appears in the library header for papers where a Bayes factor didn't reproduce OR the reporting checklist found a gap — click it to filter the library to just those papers. (Viewing a single paper's panel already keeps that paper's own count current — the batch just catches up every paper you haven't opened yet.)

<!-- section: auditing-mixed-model-reporting -->
## Auditing mixed-model reporting
Papers that fit a **linear mixed model** (a mixed-effects / multilevel model — `lmer`, `nlme`, and the like) rely on choices a careful reader needs to see. The LMM-reporting auditor reads a paper's extracted text and flags whether it *reports* seven such things — it never runs a model, an imputation, or a sensitivity analysis, and never touches raw data. It's local, deterministic, and uses no AI.

In the **METHODS** pane, open **Checklists → Mixed-model reporting** with a paper selected. If the paper detectably uses a mixed model it shows a **Reporting checklist**; each check is **present**, **not found**, or **n/a**:

- **Random-effects structure** — which grouping factors carry random intercepts/slopes (Barr et al. 2013; Matuschek et al. 2017).
- **Degrees-of-freedom / inference method** — Satterthwaite, Kenward-Roger, Wald, or a likelihood-ratio test (Luke 2017).
- **Convergence / singular fit** — did the model converge; was the fit singular (Bates et al. 2015, *lme4*).
- **Estimation method** — REML vs ML.
- **ICC** — the intraclass correlation, shown only when the paper claims a multilevel/clustering structure.
- **Marginal vs conditional R²** — variance explained by fixed vs fixed + random effects (Nakagawa & Schielzeth 2013).
- **Missing-data sensitivity analysis** — shown only for a longitudinal design with evident dropout; whether the paper checked robustness to the missing-at-random assumption (FDA ICH E9(R1); Troendle et al. 2025; Cro et al. 2020; Moreno-Betancur & Chavance 2016).

Read it as a prompt, not a report card:

- It audits **reporting completeness, not analysis correctness** — a paper can report everything and still model badly, or omit an item and be fine. It flags what a careful reader should check, not what's wrong.
- **“Not found” means we didn't detect it in the extracted text** — tables aren't fully read, so check the paper. It is never “missing” and never an accusation.
- **ICC and the missing-data check show “n/a”** unless their precondition holds (a clustering claim; a longitudinal design with dropout) — a flag that fired on every mixed model would be noise.
- There is **no score, no rank, and no verdict** — each fired flag carries a grounded, cited recommendation, and a present check opens its evidence in the PDF.
- The section credits each check's source (only once a paper is confirmed to use a mixed model) and offers a one-click **add missing to library**.

**Whole library.** Above the per-paper checklist, click **Audit all papers** to batch-check your whole library at once; a red **🔗 LMM · N** chip appears in the library header for papers with an incomplete checklist — click it to filter the library to just those papers. (Viewing a single paper's checklist already keeps that paper's own count current — the batch just catches up every paper you haven't opened yet.)

<!-- section: auditing-meta-analysis-reporting -->
## Auditing meta-analysis reporting
A **meta-analysis** pools results across studies, and the reader needs to see the choices behind the pooled number. The meta-analysis reporting auditor reads a *published* meta-analysis's extracted text and flags whether it *reports* seven such things — it never pools, models heterogeneity, re-computes an effect size, or does bias inference (that's metafor / JASP / RevMan territory). It's local, deterministic, and uses no AI.

In the **METHODS** pane, open **Checklists → Meta-analysis reporting** with a paper selected. If the paper detectably reports a meta-analysis it shows a **Reporting checklist**; each check is **present**, **not found**, or **n/a**:

- **Effect-size metric** — the index the study effects were converted to (Hedges' g, log odds ratio, Fisher's z, …) — Borenstein et al. 2009; Viechtbauer 2010 (*metafor*).
- **Model (fixed vs random-effects)** — and the between-study variance estimator (DerSimonian-Laird, REML, Hartung-Knapp) — DerSimonian & Laird 1986; IntHout et al. 2014.
- **Heterogeneity** — I² / τ² / Cochran's Q (Higgins, Thompson, Deeks & Altman 2003).
- **Publication-bias assessment** — funnel plot, Egger's test, trim-and-fill, PET-PEESE (Egger et al. 1997; Duval & Tweedie 2000; Sterne et al. 2011).
- **Sensitivity / influence analysis** — leave-one-out, outlier/influence diagnostics, robustness to an included study (Viechtbauer & Cheung 2010).
- **Number of studies (k) and participants** — the first thing needed to weigh the pooled result (PRISMA 2020).
- **Search & selection reporting** — databases searched, inclusion/eligibility criteria, a PRISMA flow, a registered protocol; shown **n/a** for a within-study "mini meta-analysis" that isn't a systematic review (PRISMA 2020).

Read it as a prompt, not a report card:

- It audits **reporting completeness, not analysis correctness** — a meta-analysis can report everything and still pool badly, or omit an item and be fine. It flags what a careful reader should check, not what's wrong.
- **“Not found” means we didn't detect it in the extracted text** — tables/figures aren't fully read, so check the paper. It is never “missing” and never an accusation.
- The publication-bias note points out that for fewer than ~10 studies a funnel-based check is underpowered, so absence there may be appropriate; the search & selection check is **n/a** for a within-study meta-analysis.
- There is **no score, no rank, and no verdict** — each fired flag carries a grounded, cited recommendation, and a present check opens its evidence in the PDF.
- The section credits each check's source (only once a paper is confirmed to report a meta-analysis) and offers a one-click **add missing to library**.

**Whole library.** Above the per-paper checklist, click **Audit all papers** to batch-check your whole library at once; a red **∑ Meta · N** chip appears in the library header for papers with an incomplete checklist — click it to filter the library to just those papers. (Viewing a single paper's checklist already keeps that paper's own count current — the batch just catches up every paper you haven't opened yet.)

<!-- section: auditing-transparency-signals -->
## Auditing transparency signals
Before relying on a paper it helps to see what it *discloses* — where its data and code live, whether it declares conflicts and funding, and whether a trial or review was registered. The transparency-signals auditor reads a paper's extracted text and detects whether it *reports* seven open-science artifacts. It's local, rule-based (derived from the published **ODDPub** and **rtransparent** tools), and uses no AI.

In the **METHODS** pane, open **Checklists → Transparency signals** with a paper selected. The section shows **Open-science disclosures**; each check is **detected**, **not detected**, or **n/a**:

- **Data availability** — a data-availability statement and/or a repository link (OSF, Zenodo, Dryad, figshare) — ODDPub (Riedel et al. 2020).
- **Code / software availability** — an analysis-code statement and/or a repository (GitHub, GitLab, Code Ocean) — ODDPub.
- **Conflict-of-interest statement** — a competing-interests / conflict-of-interest declaration — rtransparent (Serghiou et al. 2021).
- **Funding statement** — the funding sources reported (or a statement that none was received) — rtransparent.
- **Protocol / trial registration** — a registry ID or registration statement (ClinicalTrials.gov, PROSPERO, OSF Registries); shown **n/a** unless the paper looks like a trial/review where a registration is expected.
- **Preregistration** — the hypotheses/analysis plan preregistered before data collection (AsPredicted, OSF) — Nosek et al. 2018.
- **“Available upon request”** — a weaker availability signal than an open link; shown as a note, not a concern in itself.

Read it as a prompt, not a report card:

- It detects **reported disclosures in the text** — it does not judge a paper's openness, and it never runs anything.
- **“Not detected” means we didn't find it in the extracted text, NOT that the artifact is absent** — a data-availability statement can live in an appendix, a footnote, or the journal's structured metadata this reader doesn't fully see. It's a prompt to look, never an accusation of the authors.
- There is **no transparency score, no rank, and no verdict**; a present check opens its evidence in the PDF.
- The section credits each detector's source and offers a one-click **add missing to library**.

**Checking the whole library.** In the same section, **Whole library → Check all papers** runs the auditor over every paper. Each paper's *detected* disclosures become evidence-carrying marks in its **Review** section. When the data disclosure list isn't empty, the Library header shows a **🔎 Open Data · N** chip that jumps to papers where the auditor detected an open-data disclosure. The section also fills review queues for disclosures *not detected* in extracted text; those queues are prompts to look — *the paper may still share artifacts elsewhere* — never claims that it hides anything, and there is no score or ranking.

<!-- section: converting-effect-sizes -->
## Converting effect sizes
When you're preparing a meta-analysis, studies report their results in different currencies — some give group means and SDs, some a *t* or *F*, some a 2×2 table, some a correlation. The **Effect-Size converter** turns *one study's* reported statistics into a common metric you can pool downstream, and shows its work.

In **Work → Meta-Analyze**, scroll to the **Effect-size calculator** subsection and pick a family:

- **SMD → Hedges' g** — from group means + SDs + Ns, or from a *t* + group Ns, or a two-group one-way *F*.
- **SD derivation** — recover a standard deviation from an SE, a 95% CI, or an IQR (each derivation is recorded, because *how* you got the SD is a decision worth auditing).
- **Correlation → Fisher's z**.
- **Binary 2×2** — a log odds ratio, log risk ratio, or risk difference (a zero cell triggers the Haldane–Anscombe continuity correction, and that's recorded).
- **Cross-metric** — d↔r or log OR→d, clearly flagged as **approximations**.

Every result shows the metric + its **variance** + a **95% CI**, the step-by-step **conversion path**, the **formula source** (Borenstein et al. 2009 and the primary papers), and any **choices** it had to make. A **copy value + variance** button gives you a tab-separated pair to paste into a metafor/JASP row.

It **converts one study at a time — it never pools studies, models heterogeneity (I²/τ²), meta-regresses, or does publication-bias inference.** Those are your synthesis tool's job (metafor, JASP, RevMan); Callosum hands off the converted dataset with its provenance.

<!-- section: extraction-workspace -->
## Extracting a meta-analysis dataset (Work → Meta-Analyze)
The **Meta-Analyze** tab (under **Work** in the menu bar, alongside Cite, Meta-Reference, and CRediT) is where you assemble a meta-analysis dataset from your library and keep every number tied to its source.

- **Create a project** and pick a **design** (two-group continuous, binary 2×2, or correlation). The design seeds the columns the effect-size converter needs; you can add your own **moderator/notes columns** with **+ col**.
- **Add rows** — one row per effect/comparison. **+ Add paper** links a row to a library paper (a paper can appear in several rows, one per outcome); **+ Add row** makes an unlinked row.
- **Enter each value**, or **capture it from the PDF**: on a linked row click a cell's **📎 anchor → ◎ Select the value in the PDF**, then highlight the reported number on the page. The selected text drops into the cell **verbatim and stays editable** (nothing is parsed or guessed — you still check and can overwrite it), and the exact spot you highlighted becomes the cell's anchor. You can also anchor a cell by hand (type a page + quote) when you'd rather not open the PDF.
- **Open at anchor** (the 📎 hub, once a cell is anchored) jumps to the source so you or a co-author can re-check it. A value **captured from the PDF** opens with the exact passage highlighted; a value anchored only by a **hand-typed page** opens at that page with an approximate-location note (no highlight) — the app only draws an exact box when it actually has exact coordinates.
- **Drafting cells with AI (you verify each one).** If you've turned on AI features (Settings → *Allow AI features*), a paper-linked row shows **Draft from PDF**. It asks the model to read the paper and **propose** values for that row's still-empty structured cells — a head start, never an answer. For a longer paper, Callosum first embeds the empty fields' labels and the paper's text **locally**, then sends only the 12 most relevant page-tagged passages to the provider (still under the 50,000-character safety cap); if local retrieval is unavailable, drafting falls back to bounded document-order text. **Draft all un-filled rows** runs that same proposal step sequentially across every eligible paper-linked row, shows row-by-row progress, skips rows whose candidates are already waiting for review, and continues if one paper cannot be drafted. Each proposal appears as an **amber candidate** beside its cell (not a saved value) with the **verbatim quote** it was read from and an **anchor badge**: **exact** (Callosum found that quote *and* the value in the PDF — *Open at anchor* draws the exact passage), **region** (the quote was found but not the literal value — opens the page, no box), or **couldn't verify** (the quote wasn't found — nothing is drawn). For each candidate you **Accept** it, **edit the number then accept** (if the model misread it — this drops the anchor to region, so no exact box is ever claimed for a number you changed), or **Reject** it. There is no bulk accept: **nothing enters your dataset until you accept each candidate** — un-accepted candidates never reach the cell value, Convert, or any export. If AI features are off, both drafting controls are disabled and tell you so; a fully-filled row is left alone (nothing is sent). This is the funnel: **the AI narrows the search, you stay the filter.**
- **Convert →** on a row runs the effect-size converter and shows the result (e.g. Hedges' g + its variance) as a column. If you later change one of a row's cells, its effect size is cleared — so you never keep a silently-stale number; just Convert again. **Convert all →** in the header runs the converter over every row at once; the header shows a **"k of N converted"** readout, and any row whose inputs aren't complete is left un-converted and named — never filled with a guessed number.
- **Export** the dataset for your synthesis tool:
  - **CSV** — the general dataset (your columns + the converted effect size + variance).
  - **metafor** — a clean `yi/vi` table (one row per study: effect + variance + SE + 95% CI + your moderator columns), ready for `read.csv(...)` then `rma(yi, vi, data=dat)` in R. A row you haven't converted exports blank yi/vi (an honest gap, not a zero).
  - **RevMan** — the *raw* study data in RevMan's import columns for your design (continuous: mean/SD/total per group; dichotomous: events/total per group; correlation: a generic-inverse-variance effect + SE). RevMan computes the effect from the raw numbers itself.
  - **Provenance JSON** — the per-cell page and quote (your audit trail).

Every value is **yours to enter and anchor** — the workspace extracts, structures, converts, and exports the dataset; it does not pool studies, weight them, or run the meta-analysis, and no export carries a synthesized/summary estimate. Hand the exported dataset to metafor / JASP / RevMan for the synthesis.

<!-- section: critically-reading -->
## Critically reading a paper

Open **Synthesize → Critique** with a paper selected. It assembles a *scrutiny surface* — what a skeptical reader should check before citing. It is a **signal, never a verdict**: there is no quality score, and it critiques the work's claims and methods, never the authors.

It has two tiers, kept deliberately distinct:

- **Tier 1 — facts (local, no AI, runs automatically).** It gathers what the app already knows: the paper's method-check flags (statcheck, GRIM, LMM-reporting, transparency, retraction…) and **claims the rest of your corpus contests** — sentences from this paper that another paper in your library takes a confident *contrasting* stance toward, shown with the contradicting passage (verbatim, with its page) and a confidence. This surfaces disagreement your own library already contains; it never resolves it for you.
- **Tier 2 — AI-suggested critiques (opt-in, off by default).** Only when you've enabled AI features, a **Suggest critiques (AI)** button asks the model to propose concerns. Each suggestion is a **candidate you confirm** (shown in amber, distinct from the Tier-1 facts): it is admitted only if it quotes the paper **verbatim** (an ungrounded suggestion is dropped), and it carries a stance + confidence. You **Accept** the ones worth keeping and **Reject** the rest — a rejected suggestion is never proposed again. With AI off, Tier 1 still works fully.

"Nothing surfaced by these checks" is **not** a clean bill of health — it means these particular signals found nothing to flag. The reading judgment is always yours.

<!-- section: critically-reading-a-set -->
## Critically reviewing a set of papers together

When you're citing several papers **together** — the sources behind a synthesis, or a batch you've selected — you can review them as a set. Open it two ways: from a finished synthesis, click **Critically review these sources** (it reviews the papers that synthesis actually cited); or select 2–12 papers in the library and click **critical read** in the selection bar. Like the single-paper read, it's a **signal, never a verdict** — no score, no ranking, and it critiques the work, never the authors.

The modal has three parts:

- **A fact-matrix (local, no AI).** One row per paper, one column per method check (statcheck, GRIM, transparency, retraction…), plus a count of how many of its claims another paper *in the set* contests. A cell shows what that check surfaced, or "—" — and **an empty cell means that check found nothing on that paper, not that it's clean**. It is a table of facts each check surfaced, deliberately **not** a score or a league table.
- **Where these papers disagree (local, no AI).** The claims one paper in the set takes a confident *contrasting* stance toward in another — each shown with the contradicting passage (verbatim, with its page). Click one to open the contradicting paper at that page. This surfaces disagreement your chosen set already contains; it never resolves it for you.
- **AI cross-paper critiques (opt-in, off by default).** With AI features enabled, **Suggest cross-paper critiques (AI)** asks the model for concerns that span the set — a shared limitation, or a claim in one paper contradicted by another. Each is a **candidate you confirm** (amber): it's admitted only if it quotes one of the papers **verbatim** (an ungrounded suggestion is dropped), and it says which paper it anchors to, with a stance + confidence. If it names other papers it "relates" to, that's shown as **the model's framing, not a verified link** — only the quote is checked. You **Accept** or **Reject** each; a rejected suggestion is never proposed again.

<!-- section: reviewing-findings -->
## Reviewing findings
A paper can carry **findings** — short, sourced notes about it. Select a paper and open **Synthesize → Critique** to see them. Findings come in two kinds, shown differently on purpose:

- A **fact** is something established about the paper (for example, that it has been retracted). It's one row in Critique's **"What the checks surfaced"** list — a label + a status, not something for you to act on.
- A **candidate** is a *prompt to look*, not a verdict. It shows as a card in Critique's **"Needs your review"** section you can resolve: **Confirmed** (you checked and agree), **Accepted** (you're recording it as relevant — a short reason is required), or **Noted** (acknowledged). A candidate that points at a page has a **show in paper** link that opens that page.

In the library, a card shows a small **◆ fact** mark when a paper has a fact, and an **"N to review"** badge counting its unreviewed candidates. The badge tracks **your review work**, not paper quality — it's never a score or a ranking, and it disappears once you've reviewed everything. Nothing is ever decided for you, and nothing labels a paper or its authors; you stay the filter.

The library header also shows a **"📋 N to review"** chip counting *all* the papers with findings you haven't reviewed yet; click it to filter to them, then open each and Confirm or Note its findings — they drop out of the queue as you go. The **statistics check** feeds this queue: when its batch flags a paper's reporting, that becomes a candidate to review here (separate from the "⚠ flagged" statistics chip, which simply marks that inconsistencies exist — reviewing the candidate doesn't change that fact).

<!-- section: retraction-checks -->
## Checking for retractions
Citing a retracted paper is a real hazard, so Callosum can check your library against public registries. In the **Library** header, click **Retractions ↻**: Callosum refreshes the local **Retraction Watch** mirror when available, then checks each paper's DOI against Retraction Watch, **Crossref**, and **OpenAlex** (public metadata, no AI). If the Retraction Watch refresh is unavailable, the check still runs against the existing local mirror and the other registries, and the result says so.

How results show up:

- A retracted paper gets a **"Retraction status"** row in **Synthesize → Critique**'s "What the checks surfaced" list, with a link to the **retraction notice** and the source(s) that reported it, plus a red **RETRACTED** badge on its library card and Details pane — a registry record to **verify before citing**, never an accusation of the authors.
- A red **"⚠ N retracted"** chip appears in the library header; click it to filter to just those papers.
- A retracted paper's fact also shows up as a **"Retracted"** entry in the sidebar's **Tags** tab, under its own "System facts" group — a second, always-available way to browse to (or filter by) every retracted paper. It behaves like the header chip's filter, not like a tag you added: it can't be colored, locked, or removed, since it's a registry fact, not a label.
- A paper that was checked and **nothing** was found still gets its own "Retraction status" row (so silence is never presented as "clean"); a paper with **no DOI** has no such row, since it was never checked.

New papers are also checked **automatically as they're imported** (a scan or a citation-file import), so a freshly added retracted paper flags right away without waiting for a batch run.

Re-run the check anytime (retractions can happen years after publication); it updates each paper and removes a mark if a record is ever withdrawn.

For the most complete coverage, Callosum can download the **Retraction Watch database** (a free, openly-licensed registry of retractions) into a local copy. It's the richest source (it adds the *reason* and date), and once downloaded the check matches your library against it offline. In **Settings → Local maintenance**, the **Retraction Watch database** line shows how many records you have and the date of your copy (with a nudge once it's more than 30 days old — the data isn't wrong, just old); **Refresh database** updates it. (Downloading needs a **contact email** — set one under **Settings → Metadata access**; it's the polite-pool contact that public metadata services like Crossref and OpenAlex use, and it enables this download.) The **Auto-refresh when stale** checkbox next to it is **optional and off by default**: turn it on and Callosum refreshes the database and re-checks your whole library automatically when you launch or return to the app, but only once your copy is more than 30 days old (or was never downloaded) — a fresh copy is left alone.

<!-- section: duplicates -->
## Finding possible duplicates
The **Duplicates** scan helps you find likely duplicate records without automatically deleting or merging anything.

To use it:

- Click **Duplicates** in the Library header.
- Wait while Callosum scans your library.
- Review each **Possible duplicates** group.
- Click **open** to inspect a paper.
- Click **merge** to combine the group into one record (recommended for true duplicates — see below).
- Click **delete** on the redundant copy if you'd rather just remove it.
- Click **dismiss** if the group is not a duplicate.

Deleted duplicates go to Trash and can be restored. Dismissing a group marks those papers as "not a duplicate" and **persists** — future scans will not flag that group again, even across restarts.

Changed your mind? Open the **Duplicates** scan and expand **Previously dismissed** at the bottom — each dismissed pair has an **un-dismiss** button that lets the scan flag it again.

### Merging duplicates (keeps everything)

When two records really are the same paper — for example a **preprint and its published version** — **merge** them instead of deleting one. Merging is **non-destructive**: it combines everything onto one surviving record and never throws anything away.

- Launch it from a duplicate group's **merge** button, or select two or more papers in the library (tick their checkboxes) and click **merge** in the selection bar.
- In the dialog, pick which record to **keep as the main record**, resolve any **differing fields** (title, year, DOI, link, …) with the radio buttons, and choose the **primary PDF**.
- **Both PDFs are kept** (so you can keep the preprint's file *and* the published one), every **link, tag, and highlight** moves onto the surviving record, and a **"Merged from…" note** records the other copies' identifiers (DOI, OSF/URL, PMID, arXiv) — so a link can never be silently lost.
- The other copies become **merged-away** — they leave the live library (and don't clutter Trash). Nothing is hard-deleted and no file is removed from disk.

**Changed your mind? Un-merge.** A merge is **fully reversible**. Open the surviving record's **Details** — a **"Merged from … — Un-merge"** banner sits at the top. Click **Un-merge** and every merged-away copy comes back to the library with its own PDFs, tags, and highlights, and the survivor's record reverts to exactly what it was before. (This is why merged-away copies aren't offered as ordinary Trash restores — restoring one that way would give you an empty shell, since its data was moved onto the survivor. Un-merge puts it all back correctly.)

How to think about confidence:

- Very high confidence often means shared identifiers or near-identical title/author/year information.
- Lower confidence can still be useful, but you should inspect both records.
- Similar-topic papers can look close by embedding, so do not delete based on confidence alone.

Gotcha: a merge composes the surviving record from the choices you make in the dialog; the merged-away copies remain in Trash (with their original metadata) until you empty it.

<!-- section: finding-gaps -->
## Finding gaps in your library
The **Gaps** button in **Discover → Search** finds works **related to several of your papers** that aren't in your library yet — in two directions you can toggle between:

- **Works you cite** (backward): works that **several of your papers cite** but you don't have — often the foundational references your collection leans on.
- **Works citing you** (forward): newer works that **cite several of your papers** but you don't have — recent work building on your collection.

You can scope the scan to a single **axis** (the dropdown), or leave it on **All papers**. Click **Refresh** to scan (via OpenAlex); results are then **cached**, so re-opening or switching direction/axis shows them instantly without re-scanning — the "Last refreshed …" line tells you how fresh each scope is.

Each candidate shows **"cited by N of your papers"** (backward) or **"cites N of your papers"** (forward) — that's simply how many of *your own* papers it relates to, **not** a measure of importance or quality, and never a ranking of what you "should" read. For each one you can **Add** it (imports the metadata into your library — the PDF stays the separate "Acquire OA copy" step) or **Dismiss** it (so it won't come back).

After a Refresh it tells you how many papers it scanned ("scanned M of N — the rest have no DOI"), and the coverage is partial (it depends on what OpenAlex has), so this is a prompt to look, not an exhaustive list. Public metadata only — no AI, and nothing leaves the machine but the OpenAlex/Crossref lookups.

<!-- section: overlooked-lens -->
## Finding work the field overlooked
The **Overlooked** button in **Discover → Search** looks, **per axis**, for external works that are **relevant to that axis but under-cited for their year** — work you may be missing because the field overlooked it, not because it's weak. (This is different from the **Find overlooked work** action on a single paper's citation-concentration audit, which is about that one reference list's omissions; this one is a library-wide discovery lens tied to an axis.)

Choose an **axis**, then click **Refresh** to scan (via OpenAlex for that axis's topic). Each candidate shows **two separate signals, side by side — never blended into one score**:

- **relevance** — how close the work is to your axis, by a **local** embedding-similarity match (computed on your machine; the abstract is never sent anywhere).
- **cited N · Nth-percentile for {year}** — its raw citation count and where that sits among **same-year** work on the topic. A low percentile means it's been cited less than most of its vintage.

Read the two together: relevant **and** under-cited for its year = *possibly* overlooked — or *possibly* just low-impact. **Your call.** Only works with enough same-year peers to rank fairly are shown, and an empty result isn't evidence that nothing was overlooked. There's **no composite "hidden-gem" score, no ranking by anyone's identity, and nothing is added automatically.** Click a title to open the work (via its DOI); **Add** imports the metadata into your library (the PDF stays the separate "Acquire OA copy" step), and **Dismiss** hides it for good. Public metadata only — no AI; only the axis label and its topic id leave the machine. Inspired by the *Matthew effect in science* (Merton, 1968).

<!-- section: citation-equity -->
## Checking citation concentration
The **Citation concentration** subsection of **Work → Meta-Reference**, with a paper selected, describes the **structural shape** of a paper's reference list — how much it leans on a few sources or on established power — and it's deliberately a *mirror, not a report card*. Select a paper, open Meta-Reference, and click **Run audit**; it resolves the paper's references via OpenAlex (public metadata — only the DOIs leave your machine; not the AI/Gemini setting) and shows four descriptive signals, each next to a sample of the paper's **field** (its OpenAlex topic):

- **Self-citation** — how many references include an author of the paper (King et al. 2017).
- **Reliance on highly-cited work** — how much the list leans on already-famous papers, against the field (the Matthew effect; Merton 1968 / Perc 2014).
- **Venue concentration** — how spread across journals the references are.
- **Institutional concentration** — how much the references cluster on a few institutions (a way to see deference to elite affiliations — a power *structure*, not a property of any person).

Every signal shows its **basis** (expand to see the exact references / venues / institutions) and an honest **coverage** line (how many references it could resolve — a reference with no data is shown as *unknown*, never assumed). A signal computed over **fewer than half** of the references is still shown but carries a **⚠ low coverage** badge — read it as a thin, possibly-skewed hint, not a reliable comparison to the field. The field value is **context for you to interpret, not a target or a score**, and there's no composite score, no ranking, and no accusation. It looks only at the shape of **what** you cite (your own work, famous work, a few venues, a few elite institutions), never at who the authors are.

**Find overlooked work.** Click **Find overlooked work** (a separate, opt-in action) and Callosum surfaces topically-relevant papers the reference list **omits** — candidates the author may have missed. It pools the focal paper's OpenAlex *related works* and a sample of its field, drops anything already cited, and ranks the rest by a **local** scientific-paper embedding cosine to the focal paper's title + abstract; only clearly-relevant matches (cosine ≥ 0.55) are shown. Each candidate carries its **topical-match score** and the **shared topics** behind it (the inspectable "why"), plus its abstract to read before deciding. You decide what's worth citing — **＋ Add to library** saves a candidate (metadata only, no PDF download), and one already in your library is marked **✓ in library**. The ranking is **topical relevance, never an author's identity** (no identity is read or shown), there is **no "drop this citation" path**, and it never asks you to add *N* to hit a quota — better coverage is the point, not a target.

<!-- section: citation-context -->
## Seeing how a paper is cited (and how it cites)
The **How it's cited** subsection of **Work → Meta-Reference**, with a DOI'd paper selected, has a two-way toggle:
- **How it's cited** — how the *later literature* responded to this paper: do subsequent papers **support** it, **contrast** it, or just **mention** it?
- **How it cites its sources** — how *this paper* uses each of its own references: does it support, contrast, or mention each cited work?

Pick a direction and click **Fetch citations** / **Fetch references**: Callosum sends only the paper's DOI to **Semantic Scholar** (public metadata) to get the actual **citing sentences** — Semantic Scholar has already linked each in-text citation to its reference, so nothing about your PDFs is parsed or uploaded — then classifies each sentence's stance **on your machine** with its own NLI model. Your library text never leaves.

You get a **count** breakdown (N supporting · M contrasting · K mentioning) and, below it, the individual citing sentences: each with its **stance** label, a **confidence**, the citing paper (with a link), and an "influential" marker where Semantic Scholar flags a high-impact citation. It's deliberately **not a score** — there's no single "smart-citation number", no ranking, and no verdict. **The sentence is the evidence:** read it and decide. A "contrast" describes what *that sentence* says, never an accusation about an author, and the stance is an approximate signal (an NLI reading of the citing sentence against the paper's own claim), not a judgment. Coverage is honest — some citations have no sentence Semantic Scholar could provide, and those are counted but not classified. This echoes **scite** (credited in the panel, one-click added to your library).

<!-- section: meta-reference-list -->
## Checking reference signals
The **Meta Reference List** subsection of **Work → Meta-Reference** is a pre-flight reference check for the selected paper. It surfaces only three negative signals: **Could not verify**, **Known retraction signal**, and **Previously flagged in your library**. These are prompts to inspect evidence, never a verdict on the paper or on the citation.

Click **Check references** to fetch the paper's linked reference list from Semantic Scholar using the paper DOI; if that linked list is unavailable, Callosum falls back to OpenAlex's referenced-work records for the same DOI. The run shows determinate progress while it works, then records when the paper was last checked. It also exposes **Source coverage for last run** so you can see which sources succeeded, returned no records, were not searched, or failed. One source failure does not erase results from another source; use **Retry reference check** when coverage is partial or failed.

For library triage, select multiple papers in the Library and use **check refs** in the bulk bar. This runs the same Meta Reference List checker for each selected paper that has a DOI, skips selected papers without a DOI, refreshes the paper warning badges, and then filters the Library to papers with active reference signals so you can review them immediately. The filter is clearable. It does not run automatically on import and does not create a background watcher.

When a paper card shows a **ref signal** badge, click it to select that paper and open **Work → Meta-Reference** directly, scrolled to the Meta Reference List subsection. The badge is only a jump to the evidence surface; the count means active unreviewed or confirmed-concern reference signals, not a paper-quality verdict.

Callosum then resolves cited works through the existing metadata sources where possible. A search miss is shown cautiously as **Could not verify with available sources**; it is not a claim that the work is absent from the literature. Retraction signals are shown separately and more strongly, with their source evidence. Local propagation means the same referenced entity has an active signal elsewhere in your own library.

Each flagged citation instance has three review states: **Requires review**, **Reviewed and dismissed**, or **Reviewed and confirmed as a concern**. The check button means reviewed and dismissed; the X button means reviewed and confirmed as a concern. Dismissal is scoped to that paper's citation instance, so dismissing a retracted work cited critically in one paper does not suppress the same reference in another paper.

Unreviewed and confirmed concerns keep the paper's reference-warning count active. Dismissed items do not. Clearing every reference signal only means these checks have nothing active after review; it does not mean the references are correct, the claims are supported, or the paper is positively verified. If fresh detector data materially changes the signal set, a prior dismissal is reopened for review.

<!-- section: funding-discovery -->
## Funding Discovery
The **Funding** tab (in the **Discover** workspace) looks for plausible funding prospects from observed funding behavior and scholarly funding lineage, then separately checks whether a current application route is visible. It is not an open-grant search box and it is not a recommendation engine.

Use either a **selected library paper** or **Describe research** with a pasted abstract/description plus a short field context. Callosum builds a local multi-facet funding profile from title, abstract, keywords, and deterministic concept rules where available. It does not send full PDFs, notes, private annotations, or protected applicant facts to funding providers by default.

Results are shown in three separate lanes:

- **Open Opportunities** — a current provider-backed application surface was found, such as an open or forecasted Grants.gov opportunity.
- **Recurring Schemes** — a repeated funding mechanism was observed in historical cycles, but no current application window was verified.
- **Funding Prospects** — historical awards, funding lineage, or portfolio evidence suggest a funder or scheme may be relevant, with no current application surface verified.

The cards explain **why this surfaced** using inspectable signals such as portfolio overlap, support-strategy fit, recipient neighborhood, co-funding proximity, scholarly lineage, and scheme recurrence. Open **Signal trail** on an item to inspect the signal type, categorical strength, matched research facets, attached evidence rows and sources, observed years where available, and the interpretation boundary for that signal. The **Historical evidence** rows show source kind/provider, record IDs, award numbers, amounts, scheme cues, extraction basis, and source links where provenance includes them. Individual 990-PF recipient details remain withheld in the default UI. These are categorical signals, not chance estimates. Callosum avoids recommendation, funder-intent, and reopening-forecast language. A historical award is never treated as an open opportunity, and a recurring scheme is not a forecast.

When the same funder, scheme, or provider opportunity is surfaced through multiple exact evidence paths, the result lane may show one grouped card with a compact note such as "same funder surfaced through 3 evidence paths." Open **Why grouped?** to see the grouped record IDs and signal types. This grouping is display-only. Open opportunities, recurring schemes, and prospects remain separate evidence classes, distinct schemes/application routes are not collapsed together, and the run/export records stay separate.

The **Funding Prospects** lane hides lower-signal prospects by default when every attached signal is weak or unresolved and no application surface was found. Use **Show lower-signal prospects** to reveal them. This is only a display filter: it does not delete records, change ranking, alter exports, or affect open opportunities and recurring schemes.

The **Source coverage** panel matters: one source can fail or be unavailable while another source still contributes evidence. Each coverage row now states what that provider's status means for interpretation, such as OpenAlex/Crossref funding metadata being incomplete by source design, Grants.gov covering supported federal opportunities but not private or society mechanisms, or local 990-PF history being limited to indexed filings. Open **What was not covered** to see major gaps in the current open-data path, including commercial/licensed databases and funder website/newsletter calls that are not exhaustively crawled. Current open-data coverage includes cached ROR identity lookup, OpenAlex and Crossref funding metadata where present, selected-paper OpenAlex related-work funding lineage, local historical-award evidence, and Grants.gov current federal opportunity search. "No matching records were surfaced from the sources searched" is not evidence that no funding mechanism exists.

You can optionally check **Ask AI to triage apparent fit after discovery**, or run the same review after results appear with **Evaluate apparent fit with AI**. This sends only the bounded title/abstract or pasted research description plus compact summaries of surfaced funding cards to your configured model, using the same AI-features/data-egress gate as other library-text model calls. The model can add review annotations such as closer apparent fit, possible fit, uncertain, or lower apparent fit. It does not create funding records, verify eligibility, prove fit, remove records, alter saved items, or make recommendations. After a successful triage you can switch between **All surfaced** and **LLM-triaged** views. AI-fit annotations are stored with that Funding Discovery run, including the prompt version and rationale, so reloaded runs and CSV exports can show what was evaluated without turning the label into a global opportunity judgment. If the underlying opportunity or prospect evidence changes after the label was stored, Callosum marks the AI-fit label as based on earlier run evidence rather than silently treating it as current.

When Callosum has route evidence, cards show an **Application route** block. That may say a current provider found an open or forecasted opportunity, or it may show historical/application posture text such as unsolicited applications not being accepted. Route evidence does not change latent fit into a verdict.

Use **Export CSV** after a run to download a table of the surfaced opportunity, scheme, and prospect evidence. The export keeps the three item classes separate and includes source/status fields, deadline fields where available, application-route text, summarized signals, and any persisted AI-fit label/rationale for that run. It does not include chance-estimate or recommendation columns.

Use **Recent runs** to reload a completed Funding Discovery run after refreshing or returning to the app. Reloading restores the persisted evidence, source coverage, saved markers, and any per-run AI-fit labels without re-running discovery or changing the underlying funding records.

You can **Save** an opportunity, scheme, or prospect for later review. In the **Saved funding** list, open a saved row to review its status/deadline snapshot, linked current opportunity when one has been found, source link when available, workflow state, your notes, and recent refresh history. Saved-list filters let you focus on all items, needs review, current opportunity found, provider issue, no current window, applying/planning, or archived items; their counts are local list counts and do not alter the evidence. **Save changes** persists the workflow marker and notes; **Refresh saved funding** re-checks saved Grants.gov opportunities by exact provider ID where supported, then re-snapshots saved items and reports status/deadline changes. For saved prospects and schemes, refresh uses only bounded organization/scheme terms against supported provider indexes; if a conservative current-opportunity match is found, Callosum stores that as a separate linked opportunity rather than converting the prospect into an opportunity. The refresh summary distinguishes current opportunity found, status changed, deadline changed, no current application window verified, and provider unavailable outcomes with compact text labels plus the detailed explanation. The row history keeps the recent manual refresh outcomes so "provider unavailable today" stays distinct from "no current application window verified." **Unsave** removes the item from the saved list when it no longer belongs there. Saved items are lightweight workflow markers, not a grant CRM; unsaving removes only that marker, not the underlying funding evidence or search run.

<!-- section: where-to-submit -->
## Where to submit (choosing a journal)
The **Journals** tab (in the **Discover** workspace; formerly "Where to submit") matches your work against candidate journals and shows a **uniform, fully-sourced factual profile** for each — fit, open-access color, APC (fee) + waiver policy, license, DOAJ Seal, open impact — so you can weigh them yourself. It **never computes a verdict**: there's no composite score, no "predatory" label, and **every** candidate is shown (including closed-access journals). When open-aligned journals rank higher, that means *these carry goods worth underscoring* (e.g. diamond OA, a DOAJ Seal) — never that the others are bad.

**First use asks you to set two preferences** — an **open-science weighting** (how much a journal's openness moves the ranking: Off / Balanced / Strongly favor open) and a **result breadth** (Focused / Broad). Nothing is pre-selected: ranking by topical fit alone is itself a value choice, so neither "on" nor "off" is a neutral default — you decide. Both are asked together so the weighting is one choice among peers, not a singled-out purity test. They're **stored on your machine only and never transmitted**, and you can change them anytime here or in Settings → Where to submit.

Give it a **selected library paper** (with a DOI) or **paste an abstract + a subject** keyword, then **Find journals**. Your abstract is embedded **locally and never leaves the machine** — only a coarse topic/subject term is used to gather the candidate pool. Each result links to its sources (the journal homepage, OpenAlex, DOAJ). The results view always shows your **open-science weighting's current state** with a control to adjust it right there (it re-runs), so the setting never operates unseen. High APC is shown as **cost information, not a flag**; impact metrics carry the caveat that they inherit a Matthew-effect bias; and a journal with no legitimacy signals still appears with its facts (absence is common for new + regional journals and is not a mark against them).

Recent Journals searches are also stored in this browser only. Use **Recent journal searches** to re-run a selected-paper or pasted-abstract search input, and **Clear history** to forget that local list.

Once you've picked a target, a link near the top ("Once you've picked a journal, build your CRediT statement →") jumps straight to **Work → CRediT** — most journals now ask for a contribution statement alongside your manuscript.

<!-- section: credit-statement -->
## Building a CRediT contribution statement
When a paper is ready to submit, most journals ask for a **CRediT contribution statement** — who contributed what, using the 14 standard **NISO CRediT** roles (Conceptualization, Methodology, Software, … Writing – review & editing). The **Work → CRediT** tab builds one for you.

It is an **authoring aid, not a verifier.** Callosum formats the contributions **you assert** — it never infers, scores, or judges who did what. You are the source of truth; there's no confidence number and no verdict.

How to use it:

- With a paper selected, click **⤵ pull authors from this paper** to seed the grid with its author names (non-destructive — it appends, keeping any rows you've already added). Or type authors in yourself with **＋ add author**; **✕** removes one.
- For each author, click the roles they contributed. An active role can optionally carry a **degree** — **lead**, **equal**, or **supporting** — from the little selector that appears; leave it blank if you don't distinguish degrees.
- **Role bundles** — click **First author bundle**, **PI bundle**, or **Collaborator bundle** to toggle several common roles at once for that author. It's a shortcut for clicking each chip yourself, nothing more: every role it adds is an ordinary, editable chip afterward, and clicking the same bundle again removes exactly what it added. It's a convention-based starting point, never Callosum's determination of what that author actually did — check and adjust it like any other row.
- The statement generates as you go, in **two layouts**: **By author** (a line per person listing their roles) and **By role** (a line per role listing the people). Flip between them with the toggle to match what your journal wants — both come from the same data, so switching is instant. In **By role**, an optional checkbox adds an "and" before the last name in each role's contributor list (e.g. "Smith, Jones, and Lee" instead of "Smith, Jones, Lee") — off by default, purely a formatting choice.

Getting it into your manuscript:

- **Copy** (the primary button) puts the statement on the clipboard to paste anywhere (Word, Google Docs, the submission portal — the universal path).
- **Send to LibreOffice** stages it for the **LibreOffice** Callosum add-on: then in Writer run **Callosum → Insert CRediT statement** and it's inserted at your cursor as plain text. (If you edit the grid afterward, re-send — the staged copy is cleared so you never inject a stale statement.)

The panel credits the standard it follows — the **CRediT / NISO taxonomy** (Brand et al. 2015) and the prior tool **tenzing** (Holcombe et al. 2020) — with a one-click **＋ add missing to library** so you can cite them.

<!-- section: discover-search -->
## Finding new papers (Discover)
The **Discover → Search** tab searches the wider literature by keyword, title, or author — so you can find papers *outside* your library and pull them in. It searches public bibliographic metadata across **Crossref** (which also covers bioRxiv/medRxiv preprints) and **PubMed** (biomedical). Leave the source dropdown on **All sources** to merge results from every provider, or choose a single provider such as **Crossref** or **PubMed** when you deliberately want that source only. A paper indexed in more than one searched source shows multiple source pills. The only thing that leaves the machine is your search terms — this is **not** the AI/Gemini egress.

Type a query and press **Enter** (or **Search**). Results come back as a dense list you can triage fast:

- **j / k** (or the arrow keys) move the highlight up and down; **s** saves the highlighted result; **Enter** toggles its abstract. You can also click **Save** / **Abstract** on any row.
- Each row shows the title, authors, year, journal, and a **source** pill (e.g. `crossref`). A result you already have is marked **✓ in library** instead of a Save button.

**The complete list is always shown — nothing is filtered or re-ordered by a relevance score.** If a result is a likely match to one of your **axes**, it gets a small **"likely: &lt;axis&gt; · match 0.NN"** badge (the same similarity number an axis card shows) — a *hint* drawn on top of the full list; a result with no badge isn't "irrelevant," just not a strong axis match, and it's shown and savable like any other. Saving a result adds its **metadata** to your library (deduped, so you can't create a duplicate) — it does **not** download a PDF (that stays the separate "Acquire OA copy" step). The saved paper appears in your Library immediately; tidy its metadata or run **Acquire OA copy** from there.

Choosing a source controls **where Search asks**, not what Callosum is allowed to hide: **All sources** shows the complete merged list from all enabled search providers; **Crossref** or **PubMed** shows the complete returned list from that provider.

Recent Search queries are stored in this browser only. Use **Recent searches** to re-run one with its saved source setting, **Clear history** to forget that list, or **Clear ×** to empty the active query and results without touching saved papers.

<!-- section: following-sources-feed -->
## Following sources (Feed)
The **Discover → Feed** tab is for *keeping up* rather than searching: you **follow** a source, and Callosum collects its recent items for you to triage. It is **pull-only and opt-in** — nothing subscribes you automatically and nothing notifies you; you add a source, then click **Refresh** to poll it. The only thing that leaves the machine is the poll to the public source (bioRxiv) — this is **not** the AI/Gemini egress.

To use it:

- **Follow a source** — the default source type is **Journal**: type a **journal title** like `Nature Neuroscience` and, as you type, the box suggests **journals already in your library**. Click **Follow** to add it (Callosum finds the journal's recent articles for you). Prefer to browse? Click **Suggest** to open a list of every journal you already have papers from — ranked by how many papers you have from each — and Follow one in a click. You can also switch the source type to **bioRxiv category** / **medRxiv category** (a subject like `neuroscience`) or **PubMed search** (a query like `CRISPR off-target`). Each followed source shows as a chip (with its source tag) you can remove with its **×**.
- **Refresh** polls every followed source and adds any new items (re-polling never duplicates an item or resets what you've already read).
- Filter by **All / Unread / Starred**; **Mark all read** clears the unread count.
- Each item shows an unread dot, the title, authors, posted date, and journal. **Click a row to mark it read**; **★** stars it for later; **Save** adds its metadata to your library (deduped, no PDF — like Discover); a paper you already have is marked **✓ in library**. **Abstract** expands the summary.

The complete polled list is shown — read/starred are your own state, never an AI judgment about what matters.

**Auto-refresh (optional).** Tick **Auto-refresh on open** to have Callosum refresh your feed automatically when you open the Feed tab and a source hasn't been polled in a while (about 6 hours). It's off by default and stays pull-first — there's no background polling and nothing leaves your machine except the on-demand source lookups.

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
- Confirm. This removes the paper, its extracted text, highlights, search index, and attachment files stored in Callosum's managed library folder. Files linked from elsewhere on your computer are left in place. Permanent deletion **cannot be undone**.
- Permanent delete is only reachable from Trash — a paper must be moved to Trash first, so a live paper can never be purged in one click.

Gotchas:

- Permanent delete is final — there is no undo. Restore from Trash if you are unsure.
- Trash selection does not carry back and forth between Library and Trash.
- Trashed papers are excluded from **new** synthesis retrieval, so a paper you move to Trash will not be cited in syntheses you generate afterward. Syntheses you generated *before* trashing it are a saved record and are left unchanged.

<!-- section: settings-and-connection -->
## Settings and connection status
Settings are intentionally small right now. Open **Settings** from the **menu bar** (top-right of the center pane).

Available settings include:

- **Dark mode:** switches the app chrome between light and dark themes. The PDF page itself stays light so paper rendering remains readable.
- **AI features (bring your own key):** the AI section is **one editable list of model providers**. Four are **pre-seeded** — Google Gemini, OpenAI, Anthropic, and a **local model** — and you can **add your own** (the **+ Add provider** button): give it a name, a base URL, an **API format** (*Anthropic messages* `/v1/messages`, *Chat completions* `/v1/chat/completions`, or *Responses* `/v1/responses` — this is how the provider expects the request, e.g. an OpenAI-compatible service like DeepSeek uses *Chat completions*), and a list of model names. Pick the provider you want to use with **Use**, and choose its model. Set each provider's key on its card, instead of editing environment variables. Keys are stored only on this machine — in your **OS keychain** (Windows Credential Manager / macOS Keychain / Linux Secret Service) if you've installed the optional `keyring` package, otherwise in a file in your home folder (outside the app and any synced folder) — and are **never shown back to you** (Settings only reports whether a key is set, per provider). For a cloud provider, **Allow AI features** is **off by default**; turning it on lets summary generation send the relevant library text to that provider (every sentence is still verified locally against your PDFs). Clearing the key or turning the toggle off stops all egress. Whether a provider needs that consent is decided **by its address**: a **local model** (Ollama, LM Studio, or any OpenAI-compatible server at a loopback address like `http://127.0.0.1:11434`) — including a *custom* provider you point at a loopback URL — is the privacy-maximal option (**nothing leaves your machine**, so no data-egress consent is needed; a non-loopback address on the built-in *Local* provider is refused so that promise stays honest), while any custom provider at a real internet address is gated exactly like Gemini. Once a provider is configured, a **Test key / Test connection** button confirms it works (for a cloud provider it only runs when AI is on; it sends only a tiny test request, never your library). Environment variables (`GOOGLE_API_KEY` / `OPENAI_API_KEY` / `ANTHROPIC_API_KEY`, and `CALLOSUM_ALLOW_DATA_EGRESS=1`) still work as the fallback.
- **Metadata access (contact email):** an email address sent as the polite-pool contact for public metadata services — **Crossref**, **OpenAlex**, and the **Retraction Watch** database — so they can reach you about heavy use. It's optional for everyday metadata enrichment but **required to download the Retraction Watch database** (Library → Retractions ↻, or Settings → Local maintenance → Refresh database). It is **not** an AI feature — no library text or PDF is sent — and, unlike an API key, it isn't a secret, so Settings shows it back to you. (The `CALLOSUM_CROSSREF_MAILTO` / `CALLOSUM_OPENALEX_MAILTO` environment variables still work as the fallback.)

The Callosum logo also carries connection status:

- Connected: the logo shows the connected state, and its tooltip says **Connected** with the verifier version when available.
- Connecting: the app is still checking the local backend.
- Disconnected: the app could not reach the local backend.

If the Library fails to load, the app will show an error and a backend start command. Once the backend is running, reload the page.

<!-- section: ai-help-assistant -->
## Asking the help assistant
The help assistant — the **Ask the help assistant…** box at the top of this Help window — answers questions about using Callosum in plain language and links its answer to the relevant help sections. Click a reference chip under an answer to jump to and highlight that section below. It is conversational, so follow-up questions keep the thread.

It is **optional and off by default**, with its **own** switch — separate from the synthesis data-egress gate. That separation is deliberate: the help assistant only ever sends your question and the **public help text** — never your library, PDFs, or metadata — so you can use it even when data egress for your library is turned off. It uses whichever **model provider** you've configured (Gemini / OpenAI / Anthropic / local).

To enable it, flip **AI help assistant** in **Settings → AI features** (or set `CALLOSUM_HELP_ASSISTANT_ENABLED=1` in the environment), with a key configured for your chosen provider. When it is off, the box tells you how to turn it on, and the written help below still works normally.

Tips:

- Use it to find the right section fast, then read that section for the details.
- If a question is not covered by the help, it will say so — the written docs below are the source of truth.

<!-- section: work-in-progress -->
## Work in progress
**Library** contains published research sources. **WIP**, directly beside Library, contains unpublished research
products you are creating. They share familiar selection and tab behavior but remain different records.

Add a watched location from **Library → WIP → Add location**. Choose whether the selected folder is one manuscript
or whether each immediate subfolder is a manuscript. Callosum scans on launch and when the app regains focus.
Missing folders and files are marked missing; manuscript metadata is preserved.

Double-click a WIP card to open its manuscript workspace:

- **Overview** edits its display title, stage, type, target journal, deadline, and notes.
- **Structure** tracks explicit section status. Content detection never means a section is complete.
- **Tasks** records manuscript work and can scope a task to a section.
- **Files** assigns roles and lets you explicitly choose one primary manuscript.
- **References** links existing Library papers without copying their bibliographic records.
- **Activity** records important workspace changes.

WIP is local-only. It is hidden from read-only/remote views, excluded from cross-device sync, and never sent to an
AI provider by these workspace features. A teal treatment plus a visible **WIP** badge distinguishes unpublished
manuscripts from papers in tabs, Details, and Synthesize/Discover/Work context cues.

<!-- section: privacy-and-data-egress -->
## Privacy and data egress
Callosum is local-first by design. Your PDFs, extracted text, chunks, embeddings, search, axis scoring, duplicate scanning, clustering, and citation verification run on your machine.

The app remains useful offline after import and processing. You can browse, read PDFs, edit details, score axes, manage highlights, scan duplicates, and inspect saved syntheses without sending library text to a remote service.

The features that can use an LLM are optional and off by default:

- **Synthesis generation:** sends selected source text needed to generate a draft answer.
- **Search related terms:** sends axis text so the model can suggest possible terms.
- **Suggested axis label polishing:** may send a small set of representative paper titles when egress is enabled; otherwise it falls back locally.

To enable AI features, pick a provider in **Settings → AI features** (Gemini / OpenAI / Anthropic / a local model) and set its key, then turn on **Allow AI features** — or, equivalently, start Callosum with the environment variables (`CALLOSUM_ALLOW_DATA_EGRESS=1` plus the provider's key env var). A value set in Settings is stored locally (in your home folder, outside the app and any synced folder) and overrides the environment fallback; for a **cloud** provider, AI stays off until you explicitly turn it on. A **local** model (a loopback OpenAI-compatible server) needs no egress consent at all — nothing leaves the machine — and a non-loopback "local" address is refused so that stays true.

Important distinctions:

- Crossref DOI re-resolve sends only the DOI to Crossref.
- Gemini synthesis can send library text, so it is behind the explicit egress gate.
- Axis term suggestions can send your axis wording, so they are also behind the egress gate.
- Verification of citations runs locally after generation; Gemini is not treated as citation evidence.

### Remote access (for the Google Docs add-on)
**Off by default.** Citing from Google Docs requires your library to be reachable from the internet (a Google Docs add-on runs in Google's cloud and can't reach your computer directly). **Settings → Remote access** is the opt-in: turning it on generates an **access token** (shown once — copy it into the add-on) and requires that token on every request, so only you (and your add-on) can reach your library. You then run a tunnel (`python tools/run_tunnel.py`, which runs `cloudflared`) so the add-on can connect — and the tunnel is **cite-only**, forwarding just the citation endpoints (everything else returns 404 over the tunnel). The **Google Docs add-on itself** lives in `adapters/googledocs/` (a sidebar you add to a Doc via Apps Script); see `adapters/googledocs/README.md` for the full setup. While Remote access is off, nothing is exposed and local use is unchanged. **If you lose the token and get locked out**, callosum notices the failed requests and shows a **recovery panel** right in the app: paste the token to get straight back in, or choose *turn Remote access off* — which writes a one-time code to a file on the computer running callosum (proving you're at the machine, not reaching in over the tunnel), and you paste that code back to switch Remote access off and return to local-only. As a last resort you can still restart with `CALLOSUM_DISABLE_REMOTE_ACCESS=1` set.

### Optional account — sign in (ORCID, Google, or email)
**Opt-in and additive — Callosum needs no account.** **Settings → Account → Sign in** (via a callosum account service the maintainer configures) lets you sign in with **ORCID, Google, or email** — you pick the method on the account service's page. It is **identity-only**: signing in verifies who you are — and signing in with **ORCID** also pre-fills **My Publications** with your authoritative author record — but it does **not** send your library, PDFs, notes, or any text anywhere. The app works fully offline with no account, and signing out clears only the session (your data is untouched). On an instance where the account service hasn't been set up, the Account section simply says so and nothing changes. (Cross-device **sync** — the only thing that *would* move library data off your machine — is a separate, explicitly-consented step; see the next section.)

### Cross-device sync
**Opt-in and off by default — the only thing here that moves library data off your machine, and it does so end-to-end encrypted.** **Settings → Cross-device sync** walks through a short setup, in order:

1. **Choose a passphrase.** It encrypts your synced data end-to-end — Callosum never sees or transmits the passphrase itself, only a key derived from it locally.
2. **Save the recovery code — shown once.** It's the only way to unlock your data if you forget your passphrase later. **There is no server-side reset**: losing both the passphrase and the recovery code means the encrypted data can't be recovered. Save it somewhere safe before continuing.
3. **Sign in** (see Account, above) — sync is tied to your signed-in identity.
4. **Set a sync server URL** and **turn Sync on.** The server only ever receives opaque, encrypted ciphertext — never your passphrase, your key, or plaintext.

Once on, **Run sync now** re-encrypts and exchanges changes with the server — you re-enter your passphrase each time (it's never remembered between runs, so it's never held in memory longer than one sync). **What syncs:** papers, tags, axes, notes, and highlights. **What doesn't:** your PDF files (they stay local — only metadata syncs), and anything derived locally (embeddings, search indexes, method-check results), which each device rebuilds on its own.

**Conflicts are never picked for you.** If two devices edited the same thing before syncing, both versions are kept and surfaced under **Conflicts to review** — a "N conflicts to review" link appears whenever any are outstanding. For each one you see **Mine** (what this device had) side by side with **Current** (what's already applied, the other device's edit) and choose **Keep mine** or **Keep theirs**. Nothing is resolved automatically.

### Using Callosum from an AI agent (MCP)
Callosum ships a small [MCP](https://modelcontextprotocol.io) server (`mcp_server/`) so an AI agent (Claude Desktop, Cursor, etc.) can use your library **through Callosum** — keeping Callosum the source of provenance and grounding rather than letting the agent treat your files as a dumb store. It runs locally as a stdio subprocess the agent host spawns; it has no network listener. **Read tools are always on:** the agent can **search**, **read a paper's details**, **search the verbatim text** inside your PDFs, **retrieve grounded passages** (each with its quote and page, so the agent can cite the source), and **format citations**. It reads from the running app, so start Callosum first; see `mcp_server/README.md` for the host setup.

**Letting an agent edit your library (writes) — off by default.** **Settings → AI agent → Allow agent writes** is the opt-in. While it's on, the agent gains four extra tools — **add a tag**, **add a paper to one of your axes** (not My Publications — authorship is yours to assert), **save a reference by DOI** (resolved against Crossref; an unresolvable DOI is refused, never fabricated; metadata only, no PDF), and **add a note**. Every agent write is **additive, reversible, and stamped `ai-agent`**: the AI-agent panel lists recent agent writes with a one-click **Revert** (and **Revert all**), and reverting a saved reference moves a newly-created paper to Trash (a re-found existing paper is left alone). The agent can **never** delete, overwrite, merge, or scan — those stay human-only. Your agent host also shows its own confirmation prompt before each tool call, so nothing happens without you in the loop. Turn the setting off (or set `CALLOSUM_DISABLE_AGENT_WRITES=1`) and the write tools disappear; reads are unaffected.

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
