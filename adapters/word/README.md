# callosum — Microsoft Word add-in (Office.js)

Cite while you write in **desktop Microsoft Word** (Windows/Mac), backed by your local callosum library. Like the
LibreOffice adapter, this is a thin *field-placer* — it never formats citations itself; it searches your library
and inserts what callosum's citation engine renders. **Everything stays on your machine** (see *How it works*).

> **SP3** completed desktop Word parity: **search → insert a live citation**, **Suggest** citations from the
> sentence you're writing (relevance-from-the-sentence, with stance + a quote), **Refresh** (re-render + renumber
> every citation in document order + rebuild the bibliography), a **one-click whole-document style switch** (the
> style dropdown re-renders everything + is remembered per document), and **Flatten** (live → static text). Built
> on `/papers/export`, `/citations/render-document`, `/citations/suggest`, `/citations/styles` — all local.
> **SP4** adds **Word on the web** (see below) — the identical task pane, reached through the same relay tunnel
> the Google Docs add-on already uses, since Word-on-the-web can't reach your machine directly. **Inc 509** adds
> a real citation composer: **grouped citations** (combine several works into one), per-work **locator/label/
> prefix/suffix/suppress-author**, and **Edit/Delete citation at cursor** — closing the P0 gap named in
> callosum's LibreOffice-adapter parity roadmap.

## Why the setup is different from LibreOffice
A Word add-in is a **web page** that runs inside Word, and Office requires it to be served over **HTTPS** — it
**cannot reach `http://localhost`**. On **desktop**, callosum serves the add-in over HTTPS *on your machine*,
same-origin with its API: nothing leaves your computer, but you trust a local certificate once. **Word-on-the-web
runs in Microsoft's cloud and can't reach your machine at all** — that's what the relay in "Word on the web"
below is for (the same tunnel `adapters/googledocs/` already uses, just relaying more than one add-in's assets).

## One-time setup

### Packaged Callosum app (recommended)

1. In **Settings → Microsoft Word add-in (desktop)**, click **Enable Word Support**. Callosum creates and trusts
   one localhost-only certificate for your OS account, then supervises the fixed `127.0.0.1:8443` HTTPS companion
   whenever the app runs. Disable it from the same place to remove that trust and the local key material.
2. **Sideload the manifest** using step 3 below. No terminal or certificate tooling is needed.

### Source/developer checkout

1. **Trust a development certificate** (so Word accepts `https://localhost`):
   ```
   npx office-addin-dev-certs install
   ```
   (Run from anywhere; installs a local CA into your OS trust store. Run via `npx` — it is not a committed
   dependency.)
2. **Run callosum** — use the combined launcher so the HTTP server (normal browser use) and the HTTPS server
   (Word) are always the same process pair, sharing the same database, started/stopped together (inc 514 —
   running them as two separately-started commands let them silently drift apart: different `CALLOSUM_DB_URL`,
   different code versions, or one simply not running with nothing to notice until Word throws "ADD-IN ERROR"):
   ```
   python tools/run_dev.py
   ```
   This serves plain HTTP on :8888 (normal use) **and** HTTPS on :8443 (Word) from one command — HTTPS is
   skipped with a note if you haven't done step 1 yet. Open the app at **https://localhost:8443** if you want a
   browser tab too (the same trusted cert → no warning; Chrome/Edge trust the OS cert store, Firefox needs its
   own one-time trust step). Prefer running the two servers separately? `python tools/run_https.py` still works
   standalone — just make sure `CALLOSUM_DB_URL` matches whatever your other callosum process is using, or
   they'll disagree with each other exactly like this did before.
### Sideload the manifest (both workflows)

3. **Sideload the manifest** into Word:
   - In callosum: **Settings → Microsoft Word add-in → Download manifest** (saves `manifest.xml`), or grab it from
     `adapters/word/manifest.xml` (Settings → **Open add-in folder**).
   - **Windows — corrected 2026-08-28 (live-verified; the Trust Center's "Catalog Url" field genuinely rejects a
     bare local path — confirmed against Microsoft's own current docs, not just this project's earlier
     assumption):** Word's Trusted Add-in Catalogs needs a **network share path**, not a plain `C:\...` folder
     path, even for a folder on your own machine:
     1. In File Explorer, right-click the `adapters/word` folder (containing `manifest.xml`) → **Properties** →
        **Sharing** tab → **Share…** button.
     2. In the *Network access* dialog, add yourself with **Read/Write** permission → **Share**. Note the exact
        network path shown (e.g. `\\YOUR-PC-NAME\word`) — this is the value Word needs, not the local path.
     3. In Word: **File → Options → Trust Center → Trust Center Settings → Trusted Add-in Catalogs**, paste that
        `\\...` network path into **Catalog Url**, click **Add catalog**, tick **Show in Menu**, OK, OK. Close and
        reopen Word.
     4. **Home → Add-ins → Advanced** (not "Shared Folder" directly — that tab lives *inside* this dialog) →
        choose the **SHARED FOLDER** tab at the top of the Office Add-ins dialog → select **Callosum Citations** →
        **Add**.
   - **Mac:** copy `manifest.xml` to `~/Library/Containers/com.microsoft.Word/Data/Documents/wef/` (create it if
     needed), restart Word, then **Home → Add-ins → Callosum Citations**.

## Use
Open Word → **Home → Callosum → Show Citations**. In the task pane (callosum must be running in HTTPS mode):

- **Add works to a citation** — pick a citation **style**, search (or click **Suggest from the sentence** — see
  below) and click a result: it's added to the **citation you're building**, not inserted immediately, so several
  works can be combined into one grouped citation (e.g. `(Smith, 2020; Jones, 2021)`). Each added work gets its
  own optional **Options…** (⋯): a **locator** (page, chapter, figure, …) + value, **prefix**/**suffix** text, and
  mutually-exclusive **suppress author**/**author only**. Reorder with ↑/↓, remove with ✕.
- **Insert citation** — once the assembly has at least one work, inserts it as a **live** citation (a Content
  Control) at the cursor. The control's short tag points to document-local Custom XML storage carrying every
  work's CSL-JSON plus its own locator/prefix/suffix; scholarly metadata is no longer packed into the tag itself.
- **Note styles** — choosing a CSL note style reveals **New note citations: Footnotes / Endnotes**. From the main
  document, Insert creates a real native Word note and places the live citation inside it. From an existing note,
  Insert adds at the cursor when its type matches the document preference. Refresh uses Word's native one-based
  note order (ordinary notes leave real gaps; multiple citations in one note share its index), enabling citeproc's
  first/subsequent/ibid behavior. Callosum deliberately refuses mixed inline/note or footnote/endnote placement;
  changing style or preference never silently converts existing citations.
- **Suggest from the sentence** — place the cursor in (or select) the sentence you're writing, click **Suggest from
  the sentence** → Callosum ranks **your library** by relevance and shows candidates with **stance** (supports /
  contrasts / mentions) + a **quote** (the reason). **Details…** shows the complete matched passage, full
  support/mention/contrast breakdown, why it surfaced, a warning when neither signal is strong, and an editable
  page locator pre-filled from the match. **Open in PDF** jumps to the source page at honest region precision.
  Inserting a suggestion stores only a whitespace-normalized 150-character evidence snippet plus its page/chunk
  locator inside the Word document; **Citations in this document… → View evidence…** makes that audit record
  inspectable later. Pick repeatedly to add several suggestions to one grouped assembly. *(The first run loads
  the local relevance + stance models, so it can take a few seconds.)*
- **Insert saved evidence…** — search any paper, choose one of its saved PDF highlights, review the exact quote
  and your saved note, and explicitly insert it as quote-only, quote + citation, saved note + citation, or a
  quote/note card + citation. An optional **Check stance** action compares a claim with the passage through the
  existing local NLI model and labels the result as a signal, never a verdict; it never runs while you type.
  Cited formats reuse the same live citation/native-note path and retain only annotation/page identity plus a
  150-character audit snippet. Quote-only is deliberately labelled **no citation** and inserts ordinary text.
- **Edit citation at cursor** — place the cursor inside an existing Callosum citation and click this to reopen the
  composer pre-populated with its works/locators; **Insert citation** becomes **Update citation**.
- **Delete citation at cursor** — fully removes the citation at the cursor (unlike Flatten, this drops it — no
  static text is kept).
- **Convert Zotero citations…** — scans Zotero's current first-party `ADDIN ZOTERO_ITEM CSL_CITATION` Word
  fields, previews exact counts, and—only after confirmation—converts verified inline fields through Callosum's
  existing local resolver, Custom-XML citation storage, parser, and Refresh lifecycle. Grouped citations and
  per-item locator/prefix/suffix/author overrides survive. Existing papers are matched first; unmatched embedded
  records become metadata-only local library papers. Note-style fields, Bookmark-mode citations, malformed or
  oversized fields, and ambiguous bibliographies remain untouched and are disclosed. A lone Zotero bibliography
  is replaced only when no unsupported Zotero material remains. Use **File → Save As** first: Office.js cannot
  create a backup or promise one-step rollback, and Word Undo cannot remove any local library rows created before
  document mutation.
- **Refresh / renumber + bibliography** — re-render every citation in document order + rebuild the **References**
  block at the document end (run after edits/moves; numeric styles renumber by position).
- **Bibliography categories** — open **Citations in this document…**, choose **Set category…** beside a work,
  and type or reuse a document-local label. Named groups sort alphabetically while the citation style's order stays
  intact inside each group; unassigned works remain under **Other references**. Blank or **Remove category**
  clears the assignment. For a batch, check works individually or filter then use **Select visible**, choose **Set
  selected category…**, and save once; **Clear** resets the selection. A mixed-category batch requires an explicit
  label choice or **Remove category**. With at least two active groups, **Category order…** provides Move up/down,
  Reset alphabetical, Save, and Cancel; new/unranked groups follow configured groups alphabetically and **Other
  references** remains last. Category labels and order survive save/reopen.
- **Current-section bibliographies** — place the cursor anywhere under a Word heading and choose **Insert
  current-section bibliography here**. The live block contains works cited from the nearest preceding heading
  through its nested lower-level headings, stopping before the next peer/ancestor heading. Multiple section
  blocks can coexist with the full bibliography; Refresh updates all of them from the same full-document
  citeproc result, and **Remove bibliography for current section** removes only the block owned by that heading.
  This first Word slice requires WordApi 1.6 and an in-text citation style; native note-to-heading membership is
  deliberately refused until Word footnote/endnote anchors can be mapped without guessing.
- **Link bibliography titles/DOIs to the web** — an opt-in document setting makes DOI/URL text already emitted
  by the active CSL style clickable. If a style omits the identifier, Callosum may link one uniquely rendered
  single-source title to that source's DOI (preferred) or URL. Full, categorized, and current-section
  bibliographies share the setting. It never adds or changes visible text; unsafe, malformed, shifted, or
  ambiguous metadata remains plain. Clearing the option rebuilds only Callosum-managed bibliography blocks as
  plain text and leaves hyperlinks in ordinary prose untouched.
- **Insert open-science statement…** — choose data/code availability, preregistration, funding, conflict of
  interest, ethics, or AI-use wording; start from one of the same canned phrases available in **Work →
  Statements**, then review or edit every word. **Insert at cursor** places exact ordinary editable prose at the
  end of the current selection—never a citation field and never an AI-generated or Callosum-verified assertion.
  **Stage for other editors** uses the existing transient local `/statements/pending` handoff shared with
  LibreOffice and another Word session; **Clear staged** affects only that handoff, not the document.
- **Citation coverage audit…** — locally scan the main document for stretches of three or more consecutive
  substantive paragraphs (15+ words each) without a Callosum citation anchor. Inline citations and native
  footnote/endnote references count at their actual main-text paragraph; headings, short transitions, tables,
  and Callosum-managed bibliography blocks break a stretch. The report is a structural prompt to review, never
  a claim that a citation is required or that prose is unsupported. It is read-only, makes no backend/model call,
  and requires WordApi 1.6 for session-local paragraph correlation.
- **Citation style** — changing the dropdown re-renders the whole document in the new style (the choice is
  remembered per document).
- **Flatten to static text** — convert the live citation + bibliography fields to plain text for hand-off
  (two-click confirm; **one-way**). The first click shows exactly how many citations (and whether the
  bibliography) will be affected before you confirm; after flattening, Callosum re-scans the document to
  confirm nothing is left live rather than just assuming the operation worked. Office.js has no way for an
  add-in to save a copy of your document on your behalf (confirmed, not a missed feature) — the confirm
  message reminds you to use **File → Save As** first if you want to keep the live version too. An optional
  **"Also clear Callosum's saved citation settings"** checkbox removes the style, note-placement preference, and
  bibliography categories/link preference for a cleaner hand-off copy.

## How it works (for the curious)
The task pane is served by callosum at `https://localhost:8443/integrations/word/taskpane.html` and its API calls
(`/papers?q=`, `/papers/export`, exact read-only `/integrations/word/evidence/{id}`,
`/citations/classify-stance`,
`/citations/render-document`, the bounded `/citations/zotero/resolve`, `/statements/pending`) are **same-origin** — so they reach your local
library directly, with **no egress** and no CORS exception. Each citation is a Word **Content Control** whose
`.tag` carries only a short opaque reference to a document-local **Custom XML Part**. That part carries one or
more cited works' CSL-JSON, each with its own optional locator/label/prefix/suffix/suppress-author/author-only.
This avoids making Word's tag property scale with full titles, author lists, abstracts, and grouped-citation size.
Older Callosum documents whose tags directly embed base64 CSL-JSON remain readable and migrate on Refresh/Edit;
duplicate references created by copy/paste are separated on Refresh so later edits stay citation-local. **Refresh**
scans the controls **in document order**, resolves their XML parts, POSTs them to `/citations/render-document`,
and writes back the position-aware in-text + a managed **References** Content Control (tagged
`CALLOSUM_BIBLIOGRAPHY`) at the document end. A section bibliography uses a strict pair of Content Controls with
one random shared identity: a hidden scope control wraps its heading and a second bounded control owns only the
generated bibliography text. Word's session-local paragraph ids are used only during one Refresh to calculate
the live outline subtree; they are never persisted. Bibliography links reuse the renderer's bounded per-entry
HTTP(S) spans, convert its Unicode code-point offsets explicitly, and apply only to an exact paragraph-local
single match through WordApi 1.3; citeproc's plain text remains authoritative. Delete removes an unshared citation part; Flatten removes all
referenced citation parts while keeping rendered text. The only external load is **office.js** from Microsoft's
CDN: that is the Office platform SDK every add-in must load (it cannot use Subresource Integrity because Microsoft
updates it in place); it is not callosum sending your data anywhere. All formatting happens in callosum's bundled
citeproc engine, so the output matches the in-app "Cite as…" and the LibreOffice adapter.

**Bibliography-write safety (verified, inc 515):** the References block is a Word Content Control, an
inherently bounded range — Refresh's `insertText(..., replace)` only ever touches text *inside* that control,
never anything past it. This is a structurally different (and safer) data model than a bookmark-delimited
range, which is why Word never needed the dedicated hardening work the LibreOffice adapter's own bibliography
implementation did (incs 374-384) — Word gets the same safety property for free from Content Controls.

## Credit
The live-field / embedded-CSL-JSON cite design follows the **Zotero `CSL_CITATION` field convention** (reused as a
*pattern*, not code); Word stores that payload in a Custom XML Part behind a short field reference. callosum's
rendering is built on **citeproc-js** + the **CSL** project — see the project's `THIRD-PARTY-NOTICES.md`.
**office.js** is Microsoft's Office Add-ins SDK.

## Word on the web (SP4)

Word-on-the-web runs in Microsoft's cloud and can never reach `https://localhost:8443` — the desktop setup above
doesn't apply. Instead, this same task pane rides the **same cloudflared relay the Google Docs add-on already
uses** (`adapters/googledocs/`), extended to also forward the task-pane's own static files (Office itself has to
fetch those from somewhere reachable, since Word-on-the-web can't load them from your machine).

**One-time setup** (skip if you've already done this for Google Docs — it's the same tunnel):
1. Follow `adapters/googledocs/README.md`'s tunnel setup (the packaged app's **Start Quick Tunnel** mode works
   too, but its URL changes every launch — a **named tunnel** is worth it if you'll use this regularly). You already need this for the
   Google Docs add-on to work, so if that's set up, you're done with this step.
2. **callosum:** Settings → **Remote access** → turn it **ON**, copy the access token.
3. **Sideload the web manifest:** Settings → Microsoft Word add-in (web) → **Download web manifest**, then in
   Word on the web: the ribbon's **Add-ins** → **Upload My Add-in** → pick the downloaded
   `callosum-word-manifest-web.xml`.
4. **Connect:** open the task pane (**Home → Callosum → Show Citations**) — since it's now loading from the
   tunnel's own address, a small **Access token** field appears at the top. Paste your token → **Save token**.
   (Saved per-browser via `localStorage`, scoped to the tunnel's own origin — separate from anything you've
   entered for the main app or the Google Docs add-on.)

Everything else — search/insert, Suggest, Refresh (true document-order scanning, unchanged from desktop), style
switch, Flatten — works identically to desktop; every fetch just carries the Bearer token automatically once
saved. The task-pane files themselves (HTML/JS/CSS/icon) carry no library data, so relaying them through the
tunnel needs no token — only your `/papers`, `/citations/*` calls do, exactly like the Google Docs add-on.

**Using desktop Word at the same time?** No extra setup needed (inc 511) — `python tools/run_https.py`
deliberately exempts its own dedicated :8443 process from the Remote Access token requirement, since
`cloudflared`'s ingress can only ever forward tunnel traffic to the plain HTTP dev port (never :8443 — see
`adapters/googledocs/cloudflared-config.yml`'s own warning comment). So Remote Access can be on for a Google
Docs/Word-on-the-web collaborator while you use desktop Word at the same time, with no token needed on the
desktop side at all. If desktop's task pane ever *does* show a revealed **Access token** field (a 401 got
through — e.g. `run_https.py` wasn't used, or the tunnel was ever misconfigured to point at :8443), paste the
same Remote Access token from Settings and **Save**; that's a signal something's off, not the expected flow.

For note styles, Refresh scans every native footnote/endnote body and passes each citation's actual one-based
note position as `noteIndex`. Callosum supports one native note type per document and does not auto-convert
existing inline citations when a note style is selected (or vice versa); incompatible placement fails closed with
an actionable message rather than producing plausible but incorrect position-dependent output.

## Limitations
The full bibliography lives at the document end; heading-scoped blocks require WordApi 1.6 and currently support
in-text citation styles only. Word categories do not yet support uncited-work membership;
Suggest covers papers **already in
your library** (beyond-library discovery is a separate track);
desktop requires the HTTPS run-mode + the trusted dev cert. Word-on-the-web needs the relay above; Google Docs
has its own adapter (`adapters/googledocs/`). Office.js has no `saveAs` — Flatten can't save a copy of your
document for you before converting it, only tell you to (a real platform limitation, confirmed via Microsoft's
own API surface, not a missed feature).

Existing **Mendeley Cite** and **EndNote Cite While You Write** fields are not converted. Their vendors document
the outer Word mechanism (content controls for Mendeley Cite; `ADDIN EN.CITE` fields for EndNote), but not a
complete, versioned payload contract that Callosum could safely rewrite without risking citation data. Keep those
live fields under their originating tool. Vendor-supported flatten/remove-field-code workflows create static text
on a document copy; they are not editable citation migration. The evidence boundary and requirements for revisiting
it are recorded in `.claude/docs/research/2026-08-21_word_citation_migration_formats.md`.

> **Verification note:** there is no headless Word, so the in-Word behavior of the Office.js parts
> (`taskpane.js`) is **not exercised by an automated test**. The Custom-XML storage change is therefore **not yet
> live-verified in Word**; native note insertion/scanning and heading-scoped bibliography controls are likewise
> **not yet live-verified**. Zotero field scanning/mutation is also not yet live-verified. They ship
> best-effort-correct per the Office.js docs until that manual check occurs.
> The **pure logic** (`taskpane_core.js`: tag/reference/XML encode/decode, evidence normalization/bounds, the
> render-document request/response mapping) is unit-tested with `node --test`, and the `/citations/render-document`
> contract it calls is covered by the Python suite. Treat the in-Word flow as untested until you run it in Word.
