# Design — accounts SP3: opt-in, end-to-end-encrypted, multi-device sync

**Date:** 2026-06-29
**Status:** DESIGN — pending maintainer review. **No code until this spec is approved.**
**Arc:** accounts SP3 (after SP1 inc 194 ORCID sign-in, SP2 inc 196 email/Google). The big one — the **only** step
that moves library data off the machine. Parent spec: `…/2026-06-29-accounts-optional-identity-design.md`.

## Locked decisions (from the brainstorm)

1. **Multi-device, kept in step** (not just backup) → needs conflict handling.
2. **End-to-end encrypted** — the server stores only ciphertext it can't read.
3. **Metadata-first** — papers/axes/tags/annotations/notes/syntheses; **PDFs deferred**.
4. **Account-authenticated callosum sync endpoint** — your callosum account (Authentik/OIDC) *is* your sync identity;
   a small endpoint the maintainer runs stores per-record ciphertext, gated by the OIDC token.
5. **Opt-in, default-off** — sync is off until you turn it on and set a passphrase.

## The Principles / A-A gate (run before design — this is the invariant-touching feature)

- **Touches:** PRINCIPLES **#10** (local-first; external calls bounded/on-demand/behind swappable seams) + value
  **A5** (local-first, *sovereignty over what leaves the machine* — the central one) + value **A4** (the user owns
  every irreversible act; data never silently overwritten). It is an **emergent value** ("adopt deliberately, don't
  drift" — A-A Part III / heuristic 7).
- **The misaligned easy paths, declined:** (a) a **server-readable** sync (server holds plaintext → inverts A5,
  makes callosum a custodian of everyone's library) — already declined (E2E chosen); (b) **silent last-write-wins**
  that clobbers a concurrent edit made on another device — violates **A4** ("no silent destruction") + A-A's
  no-silent-clobber refusal.
- **The aligned design:** E2E (plaintext never leaves; only ciphertext, keyed by a key only the user holds) +
  **opt-in/default-off through a consent surface** (A5 sovereignty; PRINCIPLES #10 bounded/on-demand) +
  **conflict-surfacing, recoverable merge** (A4 — LWW *with the overwritten version kept in a local conflict log*,
  never a silent data loss) + AGPL stays (A8 — a hosted sync service must offer its source; already AGPL). Heuristic
  5: a new external dependency must route through the consent gate + justify why it can't be local — sync's whole
  point is cross-device, so it can't be local, and it routes through an explicit opt-in.
- **Non-triggering for #1–#9/#2** (no claim/signal/judgment about the literature; sync moves the user's own data, it
  doesn't produce findings). **No A-A veto in play** (no paywall circumvention / other-tool stores / accusation).
- **Finding:** sync is buildable in a fully principle-aligned way **iff** (i) E2E is real (server never sees a key),
  (ii) it's opt-in/default-off, and (iii) conflicts are surfaced + recoverable, never silently resolved. Those three
  are non-negotiable acceptance criteria, not nice-to-haves.

## Architecture

Three layers; only the first two are callosum code, the third the maintainer operates.

### 1. Client crypto + key management (on the user's machine)
- **Key:** a user-chosen **sync passphrase** → a symmetric key via a KDF (**`scrypt`** from `cryptography.hazmat`,
  already present via `PyJWT[crypto]` — **no new dependency**). Records encrypted with **AES-256-GCM** (authenticated;
  per-record random nonce). The key + passphrase **never leave the machine** and are **never sent to the endpoint**.
- **Recovery:** at setup, callosum shows a **one-time recovery code** (a high-entropy string that re-derives/escrows
  the key locally) so a forgotten passphrase isn't total loss — but **there is no server-side reset** (that's the E2E
  guarantee; stated plainly in the UI). Per-device: enroll a new device by entering the passphrase (or recovery code).
- **What's encrypted:** each syncable record → `AES-GCM(plaintext_json)` → an opaque blob. The server sees only
  `{collection, record_id, version, ciphertext, nonce}` + a tombstone flag — never field names or values.

### 2. Client sync engine + local change-tracking (callosum backend, local)
- **Syncable set (v1, metadata):** the **user-authored + bibliographic** rows — `papers` (incl. `csl_json`),
  `tags`/`paper_tags`, `axes` + **manual** `cluster_node_papers` (the `confidence IS NULL` human overrides only —
  scored memberships are *derived*, re-scored locally), `annotations` (user/synthesis), `notes`, `summaries` +
  `profile`. **NOT synced (derived → recomputed/re-fetched locally on each device):** `embeddings` + sqlite-vec
  vectors (large; re-embed from synced chunks/text), `llm_cache`, `open_science_signals`/`paper_findings`/
  `gap_candidates` (recompute), and **PDF files/attachments bytes** (deferred — sync the attachment *metadata* +
  checksum so the other device can re-link/re-acquire, not the bytes). *Chunks:* TBD in SP3a — either sync chunk text
  (needed to re-embed) or re-extract from a re-linked PDF; the spec's SP3a resolves this.
- **Change-tracking:** a per-row **`version`** (monotonic, bumped on write) + **`updated_at`** + soft **tombstones**
  for deletes, on the syncable tables (a small additive migration — a `sync_state` side-table keyed by
  `(collection, record_id)`, so the domain tables are untouched). The engine pulls remote blobs `since` the last
  server sequence, decrypts, and **merges per-record by version (last-write-wins)**; on a true conflict (both sides
  changed the same record since the last common version) it **keeps the loser in a local `sync_conflicts` log** and
  surfaces it (A4) rather than dropping it.
- **Injectable** (a `SyncTransport` Protocol → a fake in tests, mirroring the OIDC-client + provider-registry seams),
  so the whole engine is hermetically testable with no network/crypto-service.

### 3. The sync endpoint (the maintainer operates; holds only ciphertext)
- A small **account-authenticated** service (the OIDC token from SP1 gates it; runs alongside Authentik). Endpoints:
  `GET /sync/pull?since=<seq>` → `[{collection, record_id, version, seq, nonce, ciphertext, deleted}]`;
  `POST /sync/push` → store blobs, assign sequences, return them (reject a stale-version push → client re-pulls +
  merges). **Stateless re: plaintext** — it's an opaque, per-user, append-mostly blob store. (In-repo: a client of
  this endpoint + the contract; the endpoint impl is a thin service spec in the runbook, like the Authentik standup.)

## Consent / UI

A **Settings → Sync** section (opt-in, default-off; mirrors the Account/AI sections): "Turn on sync" → set a
passphrase → **show the recovery code once** → enroll. While on: a status line (last synced, pending, conflicts), a
**Conflicts** review (the `sync_conflicts` log — pick which version wins; never silent), and a clear "what syncs /
what doesn't (PDFs stay local for now) / no server-side passphrase reset" note. Requires being **signed in** (the
account is the sync identity) — so it's gated behind SP1/SP2.

## Sub-decomposition (SP3 is big — build in safe, independently-shippable slices, each its own plan + gates)

- **SP3a — crypto + local change-tracking foundation (no server).** The encryption layer (passphrase→scrypt key,
  AES-GCM encrypt/decrypt, recovery code) + the `sync_state`/`sync_conflicts` tables + per-row version/tombstone
  tracking + a local "compute the change-set / merge by version" core. **Fully local + hermetically testable**; ships
  no egress. This is the bulk of the hard, security-critical logic — proven before any data leaves.
- **SP3b — the sync endpoint + push/pull engine.** The `SyncTransport` client + the pull/merge/push loop against the
  account-authenticated endpoint; the endpoint service spec in the runbook (maintainer stands it up). The first slice
  where ciphertext actually leaves — its own audit.
- **SP3c — conflict-surfacing + the Settings → Sync UI.** The opt-in surface, passphrase/recovery-code flow,
  per-device enroll, sync status, and the Conflicts review.

## Gates (every slice)

- **Security audit (heavy):** the crypto (KDF params, AES-GCM nonce uniqueness, key never logged/transmitted, the
  recovery-code escrow), the new endpoint + auth, SSRF/abuse, the E2E guarantee (server-can't-read — assert it in
  tests), tombstone/merge correctness (no silent data loss), resource caps. New external store/egress.
- **Principles + A-A:** the three acceptance criteria above (real E2E, opt-in/default-off, conflicts surfaced) are
  the audit's pass conditions. Sync is the emergent value adopted deliberately.
- **QA route + rule-#11 experience pass** (a "two-laptop researcher" persona for SP3c). **README/help privacy
  rewrite:** the promise becomes "local-first; an optional account; optional **E2E** sync you turn on — the server
  can't read your library."
- **No new dependency** (`cryptography` is present via `PyJWT[crypto]`); **a migration** for `sync_state`/
  `sync_conflicts` (additive/guarded).

## Verification

Hermetic: encrypt→decrypt round-trips; **a wrong passphrase fails closed**; the server blob is opaque (assert no
plaintext field/value appears in it — the E2E guarantee, as a test); two simulated devices converge via the
fake transport; a concurrent edit produces a **surfaced** conflict (not a silent overwrite); tombstones propagate
deletes; derived data (embeddings) is re-built locally, not synced. The **live multi-device round-trip** (two real
machines + the stood-up endpoint) is the maintainer's manual check.

## Out of scope (deferred)

PDF-file sync (a later opt-in — sync attachment metadata + checksum now, bytes later); real-time/push sync (pull on
open + manual, like the watched-folder rescan); **CRDTs** (per-record LWW + conflict-surfacing is the v1; CRDTs only
if real concurrent-field-editing pain shows up); **sharing/collaboration** (SP4 — its own design); bring-your-own
cloud storage (the alternative backend — could be added behind the same `SyncTransport` seam later).
