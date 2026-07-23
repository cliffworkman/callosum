# Increment 343 — Backlog #21: Tauri desktop-shell feasibility research + spike

## Context
Last item in Cliff's 12-item decision queue. #21 ("Packaging & distribution, post-V1") was always marked
exploratory, not a build-it-now item. Asked Cliff how far to take "explore": research-doc-only, a research doc
plus a throwaway spike, or the real scaffold. He chose the middle option — a doc plus a small hands-on spike
answering the single riskiest question ("can a Tauri shell actually launch and show the real callosum UI") —
without committing to the much larger sidecar-packaging build.

## Implemented
- **`.claude/docs/future-tracks/desktop-packaging-tauri.md`** (new): feasibility research. Key findings —
  (1) the OS-keychain half of #21 is **already mostly done** (inc 152's optional `keyring` + file fallback for
  BYOK secrets); the packaging-time gap is just making `keyring` a hard dependency in a real desktop build, not
  new design. (2) The real open question is how the Python/FastAPI backend + its ML stack gets into a Tauri
  app at all — Tauri doesn't run Python, so the shell has to launch callosum's backend as a **sidecar**
  process (frozen via PyInstaller/Nuitka, or a bundled portable CPython) and point its webview at the
  resulting local port. (3) **`torch` alone is 1.19 GB on disk** (measured on this machine) before
  `sentence-transformers`/`scikit-learn` — a real distribution-size problem for a "download this app"
  story, independent of Tauri itself. Recommends evaluating an **ONNX Runtime** embedding backend (much
  smaller than full PyTorch; `sentence-transformers` supports it) as its own scoped decision *before*
  committing to the packaging build, not folded silently into it. (4) Platform notes: Windows 11 ships
  WebView2 by default (no extra runtime); macOS uses the system WKWebView; Linux needs a `webkit2gtk` system
  package (the one platform where "just install our app" isn't quite true). Tauri is MIT/Apache-2.0 — no
  AGPL-3.0 conflict (it's a launcher process, not a modification of callosum's own source).
- **The spike itself:** installed the Rust toolchain (`winget install Rustlang.Rustup`; this machine already
  had Visual Studio 2022's C++ tools, avoiding the much bigger Build Tools install that a from-scratch machine
  would need). Scaffolded a minimal Tauri v2 app (`npm create tauri-app@latest`, vanilla template) and set its
  window's `url` directly to `http://127.0.0.1:8888` — callosum's own backend, already running on this machine.
  **Confirmed working**: Cliff watched the native window open showing the real, live callosum library UI. Not
  committed to the repo — genuinely throwaway, per Cliff's own chosen scope; lives outside the repo at
  `C:\tauri-spike\callosum-shell-spike` if he wants to poke at it further, otherwise safe to delete.
- **`.claude/docs/future-tracks/README.md`**: added an index row for the new doc.

## Key technical detail
The first build attempt failed with a Windows linker error (`LNK1104: cannot open file ...`) — Rust's nested
build-artifact paths pushed a real path to **263 characters**, just over the Windows 260-char `MAX_PATH`
limit, because the default scratchpad directory is nested under a long session-ID path. Fix: build Rust/Tauri
projects from a short root path (`C:\tauri-spike\`, not deep inside a scratch/session directory) — worth
remembering for any future Rust work in this environment, not specific to Tauri.

## Principles/A-A gate (rule #9)
Doesn't touch a literature claim/signal/judgment surface — packaging/distribution infrastructure, not
application behavior. No gate trigger.

## Tests
No source changes to callosum itself; pytest count unchanged (1398 passed, 1 skipped, per inc 342).

## Backlog
**#21 stays open** (this was exploration, not a build) — but the open question changed shape: the desktop
shell itself is now a known-tractable Rust/Tauri build; the actual work is the Python-backend-sidecar problem
(and, upstream of that, whether to shrink the ML dependency footprint via ONNX first). Recorded in
`INCREMENT-BACKLOG.md`'s #21 entry.

## Next
Nothing queued — this closes the last item in the 12-item decision queue that opened this multi-session arc.
If #21 comes back up, the recommended next slice is the ONNX Runtime embedding-backend evaluation (its own
scoped increment, judged on size/speed/accuracy), independent of and prior to any actual sidecar-packaging
build.
