# Future-tracks import — inbox

**Watched inbox.** Drop partially-developed future-track idea `.md` files here; they get **audited, folded
into the backlog, then moved to [`../future-tracks/`](../future-tracks/)** — with `INCREMENT-BACKLOG.md` and
the `future-tracks/README.md` index updated to reference the new location. This folder normally sits **empty**;
a non-empty inbox means there is unprocessed input.

Handling rule:
- A dropped file that is a genuine **future-track** → folded into the backlog + the `future-tracks/` index,
  then **moved** to `../future-tracks/`.
- A dropped file that is a **meta / CLAUDE.md directive** (not a track) → **actioned directly**, then removed.
- The fold-in is always **surfaced to the user** (reported, never silent) and run through the
  Principles + `APPROACH-AVOIDANCE.md` gate framing, like any future track.

The **auto-on-session-start watch rule** landed in **Phase 8**: a session-kickoff step in `../../CLAUDE.md`
(Session kickoff #9) makes a fresh session check this folder on its own, so you can just drop a file in and the
next session surfaces it — no need to point the assistant here.

## Parked (do not auto-process)
Counsel-gated / sensitive drops live here on purpose — they are **not** folded or published, and the
session-kickoff watch **skips** them:
- `opus4.8_future-tracks_acquisitiondeferred.md` — the legally-ambiguous acquisition lane (entitled / browser
  connector / GetFTR–LibKey / ILL / paid delivery). Deferred pending counsel; never build, scaffold, or publish it.

This folder is **gitignored** (local-only), so parked material never reaches the public repo.
