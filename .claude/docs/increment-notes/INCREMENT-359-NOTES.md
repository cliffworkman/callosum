# Increment 359 — LibreOffice document lifecycle observer

## Context

P1 roadmap item #13 persisted citation/bibliography dirty flags, but Writer restored their Infobar only when the
next Callosum command ran. Native Writer operations could also reorder or edit live citation fields without the
adapter observing the change. LibreOffice provides document jobs for open events and `XModifyListener` for model
changes, so both gaps belong to one bounded lifecycle slice.

## Implemented

- Added a packaged `DocumentLifecycleJob` (`XJob`) and `Jobs.xcu` registration for the documented document-open
  events. It receives the event's Writer `XModel`, restores the persisted Infobar, and attaches observation.
- One listener is owned per Writer `RuntimeUID` and removed from the adapter registry when the document disposes.
- The listener snapshots only Callosum-managed structure: recognized citation mark identity/order/rendered text
  and the bounded bibliography state/text.
- Citation-structure changes mark citation formatting and bibliography pending; bibliography-only changes mark
  only the bibliography pending. Unrelated prose edits leave both flags untouched.
- Observation only persists flags and synchronizes Writer's native Infobar. It never formats, mutates citation
  text, contacts the Callosum server, or starts background work.
- Callosum-dispatched operations suspend observer judgments while their existing transactional mutations and
  exact dirty-state policy run. Their listener baseline still advances, preventing a later false warning.
- A command failure that actually changes managed structure conservatively marks both surfaces pending.
- Extension version bumped 0.8.0 → 0.9.0; `Jobs.xcu` is packaged and declared in the extension manifest.

## Verification

- Targeted adapter/OXT/install suite: **83 passed**.
- `python adapters/libreoffice/run_roundtrip.py`: **SELFTEST OK** with the installed OXT and real Writer.
  The lifecycle fixture saves a citation-dirty document, closes it, and opens a visible Writer view without
  dispatching any Callosum command. The Infobar is already present. It then proves a native ReferenceMark move
  sets `(citations, bibliography) = (True, True)` while an ordinary prose edit leaves `(False, False)`.
- The same run completed every pre-existing LibreOffice spike after the listener was active.
- Full project suite: `1468 passed, 1 skipped in 772.18s (0:12:52)`.

## Gates

- **Principles / governance:** non-triggering. This is deterministic local document state, not a scholarly claim,
  signal, ranking, recommendation, or worker assessment.
- **Security:** `2026-07-23_libreoffice-document-observer.md` is **PASS**.
- **QA:** no web API or frontend surface changed. Pure tests cover state mapping, listener deduplication, dispatch
  suppression, OXT packaging, and job wiring; real UNO proves lifecycle delivery and Writer callbacks.

## Manual verification debt

Cliff should install 0.9.0, save a document with pending citation work, close and reopen it, then confirm the
warning is visible immediately. Moving one live citation past another with Writer cut/paste should show both
surfaces pending. The prior menu/panel appearance click-through debt remains open.

## Next

The remaining #13 performance controls are progress/cancellation and incremental rendering. Both require changes
to the render protocol and transaction model rather than another isolated Writer command.
