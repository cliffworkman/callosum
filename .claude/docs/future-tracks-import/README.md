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

The **auto-on-session-start watch rule** (so a fresh session notices a non-empty inbox without being told) is
tracked as **Phase 8** of the release-readiness arc; until it lands, point the assistant at this folder when
you've dropped something in.
