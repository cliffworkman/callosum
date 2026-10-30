# User-visible recovery states (inc 610)

Shown in **Settings → Library behavior → Retrieval model**, under each non-baseline profile, and in the global
**Status** popover ("Retrieval index build", Local AI, clicks to Settings). Every number is re-derived from stored
vectors: `Index: N of M passages (P%)`. Messages are fixed strings chosen by code: no exception text, no file path,
no passage. The bounded technical diagnostic is under a collapsed **Technical details**.

Whenever a non-baseline index is incomplete, the panel also says: *"Arctic S is not yet available for Ask because
indexing is incomplete."* Its radio stays disabled, and Ask keeps failing closed if it was active.

| State | Message | Actions | In Status |
|---|---|---|---|
| queued | Indexing will start shortly. | Pause, Cancel | running row |
| running | Indexing passages. Completed work is saved as it goes. | Pause, Cancel | running, real current/total |
| running (after a resource or kill exit) | Indexing resumed with a smaller batch size (N passages at a time). | Pause, Cancel | running |
| pausing | Stopping after the current batch. Completed work is saved. | — | running |
| paused | Paused. Completed work is saved. Resume when you're ready. | Resume, Cancel | finished |
| waiting_resources | Indexing paused because available memory is low. Completed work is saved. Callosum will resume automatically when safe. | Pause, Cancel | running row with this label |
| retrying | Indexing was interrupted. Completed work is saved. Callosum will retry automatically. | Pause, Cancel | running row with this label |
| retrying (after app exit) | Indexing stopped when Callosum closed. Completed work is saved and indexing will resume. | Pause, Cancel | running |
| interrupted | Indexing was interrupted (cause unknown). Completed work is saved. Resume when you're ready. (`app_closed`: "…stopped when Callosum closed…") | Resume, Cancel | finished |
| failed — no progress | Indexing stopped after repeated unsuccessful attempts. Your existing index is preserved. You can retry manually. | Resume | error |
| failed — memory floor | Not enough free memory to index even one passage at a time. Your existing index is preserved. | Resume | error |
| failed — model | The retrieval model could not be loaded or does not match its pinned recipe. Nothing was retried automatically. | Resume | error |
| failed — version changed | The retrieval model's pinned version changed. Start the build again. | Resume | error |
| cancelled | Cancelled. Completed work is saved; starting again resumes from it. | Resume | finished |
| completed | Index complete. | — | done |

Attempts, failures without progress, and "automatic retry scheduled" appear under the message once there has been
more than one attempt or any failure. The ProgressBar is `managedBy="backend-job"`, so Status shows one row, not two.

**A frozen progress bar is never the only signal.** If the worker dies, the next supervisor tick (2 s) observes the
exit and the row changes to `retrying`. If the whole app died, the next launch reconciles before serving. If a
worker hangs without dying, the 600-second heartbeat stall terminates it and retries.

Help corpus: the Retrieval model entry now describes the background process, Pause/Resume/Cancel durability,
low-memory waiting, interruption recovery and the manual-resume stop.

**Not done:** a browser/visual check of the panel. Playwright MCP failed to connect this session; the panel is
verified by static and bundle tests and by API tests of the states it renders.
