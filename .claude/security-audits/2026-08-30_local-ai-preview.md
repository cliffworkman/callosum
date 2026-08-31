# Security Audit: Local AI Preview

Date: 2026-08-31
Status: PASS

## Scope

Productionize the existing Tauri-owned managed llama.cpp runtime as the first-class `managed_local` generative provider, acquire the exact pinned Qwen2.5-1.5B-Instruct Q4_K_M artifact, and expose setup/status controls without weakening provider egress or scientific lifecycle behavior. The existing user-managed `local` endpoint remains semantically unchanged.

## Security invariants

- Model and runtime downloads use exact, immutable identities and SHA-256 verification before atomic promotion.
- Partial or corrupt artifacts never become eligible execution inputs.
- Tauri remains the sole inference-process owner; Python never launches or supervises llama-server.
- Inference binds only to literal `127.0.0.1` and requires a random per-launch bearer token stored outside argv.
- The token, model path, prompts, outputs, and scholarly content are absent from frontend-visible descriptors and ordinary logs.
- A managed target is published only after authenticated readiness and requested-versus-observed execution verification.
- Selecting Local AI cannot invoke Gemini, OpenAI, Anthropic, or another non-loopback endpoint as fallback.
- Existing purpose-built local embedding, NLI, reranking, OCR, and parser components remain unchanged.
- User-controlled paths, URLs, model identities, and runtime argv are not accepted by the primary managed setup flow.

## Audit checklist

- [x] Pin authoritative model source, revision, byte size, license, and SHA-256.
- [x] Define the allowlisted runtime distribution and immutable bundle identity.
- [x] Bound downloads by host, redirects, byte count, timeout, and destination.
- [x] Use a private partial path, streaming digest, fsync where practical, and atomic promotion.
- [x] Reject symlink/reparse-point destinations and path traversal.
- [x] Verify strict loopback and no-proxy behavior remains intact.
- [x] Verify bearer authentication remains required for inference.
- [x] Verify child output remains consumed and discarded without prompt/output persistence.
- [x] Verify provider resolution fails closed when Local AI is selected but unavailable.
- [x] Verify local failure cannot cause cloud egress.
- [x] Verify status endpoints and frontend payloads contain no secret or private filesystem path.
- [x] Verify cleanup removes transient credentials/descriptors and no child survives app exit.
- [x] Run secret/private-path scan and dependency/static checks.

## Threat notes

The highest-risk additions are remote artifact acquisition and the promotion of a developer-only descriptor into an ordinary provider path. Download integrity must not depend on a mutable filename or provider metadata, and provider availability must remain distinct from an endpoint chosen by the user. The managed provider will therefore consume only Tauri-published, readiness-gated descriptors whose exact artifact and runtime identities match the shipped manifest.

## Disposition

PASS for the bounded Windows x64 Local AI Preview. Focused security/provider/lifecycle tests, the complete Rust
suite, strict Clippy, Ruff, Bandit, Tach, line-budget, and a live Windows CPU/0 smoke passed. The live smoke removed
the transient descriptor and bearer-token file and left zero `llama-server` processes. The exact model/runtime
install remains as verified app data for restart reuse. macOS/Linux acquisition is deliberately unsupported rather
than falling back to an unverified package. A production NSIS build and packaged-executable launch/restart/forced-exit
check passed. In a packaged unavailable-target test, Local AI remained selected, no cloud key was present, the repair
response explicitly reported that no cloud provider was contacted, the backend had no non-loopback connection, and
no llama-server or backend child survived close. Visual download/interruption UI checks remain Tuesday QA items.
