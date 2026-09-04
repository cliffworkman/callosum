# Callosum Mobile Architecture Research Report

Research date: 2026-09-03  
Repository state inspected: `main` at `96a6098c31dd75fc105a302a2558e391dddd6577`  
Study type: read-only architecture research; no application files were modified

## 1. Executive Recommendation

**RECOMMENDATION —** Build Callosum Mobile as a separate Tauri v2 mobile shell in the same repository, sharing selected UI components, domain types, protocol code, and tests with desktop. Do not compile the existing desktop Tauri entry point for mobile.

Use this execution model:

- Mobile owns browsing, caching, PDF presentation, offline queues, annotations, share-sheet ingestion, notifications, and other phone-native interactions.
- Desktop remains the authoritative library and runs Python, imports, local/cloud AI, extraction, synthesis, critique, and computationally intensive jobs.
- A narrow, versioned Mobile API sits between them.
- Connectivity uses LAN discovery/direct transfer when possible and a Callosum-managed, end-to-end-encrypted relay as the reliable remote fallback.
- Pairing is accountless by default, based on a QR-delivered, single-use invitation and per-device cryptographic identities.
- A later per-user desktop agent should keep mobile connectivity available while the desktop UI is closed. Sleep and power-off remain honest offline states.

```text
┌──────────────── Callosum Mobile ────────────────┐
│ Tauri mobile UI                                 │
│ Cached library / PDFs / results                 │
│ Share extension / offline action queue          │
│ Device identity + scoped capabilities           │
└───────────────┬─────────────────┬───────────────┘
                │ LAN direct      │ E2EE relay fallback
                │ mDNS discovery  │ outbound WSS
                ▼                 ▼
         ┌────────────────────────────────┐
         │ Versioned Mobile Protocol v1   │
         │ authentication / jobs / files │
         └────────────────┬───────────────┘
                          ▼
┌──────────────── Callosum Desktop ───────────────┐
│ Optional background Callosum Agent              │
│ Narrow mobile facade                            │
│ Existing Python backend + SQLite library        │
│ PDFs / imports / extraction / AI / computation │
└─────────────────────────────────────────────────┘
```

The relay should see routing metadata and ciphertext, not scholarly content. Full ICE/WebRTC NAT traversal is not justified for V1: relay reliability is needed anyway behind difficult NAT/CGNAT, while LAN direct avoids needless relay traffic for PDFs.

**Runner-up —** E2EE relay-only. It is simpler and highly reliable, but needlessly relays same-LAN PDFs and creates greater bandwidth cost.

**Decision:** Tauri v2 is suitable, provided Callosum treats mobile as a related client—not as the desktop bundle running on a phone.

Evidence labels used below:

- **VERIFIED FROM CODE** — current repository behavior.
- **VERIFIED FROM DOCUMENTATION** — current primary external documentation.
- **INFERENCE** — a conclusion drawn from those facts.
- **RECOMMENDATION** — proposed future architecture.

## 2. Current Callosum Architecture

**VERIFIED FROM CODE — Desktop process model**

`app/desktop-shell/src-tauri/src/lib.rs` launches a desktop-oriented process tree:

1. Resolve/provision the persistent CPython runtime.
2. Start the managed llama.cpp runtime when Local AI is active.
3. Start the FastAPI/Uvicorn Python backend on loopback.
4. Open the frontend served by that backend.
5. Optionally run Word HTTPS and Cloudflare Quick-Tunnel children.
6. Terminate those children when the Tauri process exits.

`backend.rs` uses a loopback port, application-local data paths, Windows Job Objects or Unix process groups, and controlled shutdown. There is no independent background Callosum agent today.

**VERIFIED FROM CODE — Frontend**

The frontend is modular JSX assembled into a single served application by `tools/build_frontend.py` and the backend frontend assembler. React and some PDF.js resources are presently loaded through CDN paths. Responsive behavior below approximately 760 pixels changes the application into a single-column mobile-style layout.

This offers useful reusable presentation code, but is not yet a self-contained mobile bundle. Store applications should package React, PDF.js, fonts, and required assets rather than depend on CDN availability.

**VERIFIED FROM CODE — Backend**

The backend is a local FastAPI application using SQLite and a large set of routers. It implements:

- library and paper records;
- PDFs, attachments, chunks, annotations, tags, axes, and queue state;
- imports and ingestion;
- synthesis, Overview, critique, and other AI workflows;
- discovery, funding, journals, feeds, and My Publications;
- WIP/manuscript functions;
- research-method diagnostics and workbench features;
- provider credentials, application settings, status, and maintenance.

The current frontend knows many internal route shapes directly. That is undesirable for a long-lived mobile client, because internal refactors would become mobile protocol breaking changes.

**VERIFIED FROM CODE — Jobs**

`JobStore` and the status aggregation code expose pending/running/done/error state, progress, stages, elapsed time, and ETA. Job stores are process-local and largely in-memory. There is HTTP polling/long-polling, but no general durable mobile job ledger or WebSocket/SSE job protocol.

A mobile user cannot safely assume a submitted job survives a backend restart.

**VERIFIED FROM CODE — Files**

PDFs are served from trusted attachment records using `FileResponse`. Current desktop ingestion commonly takes filesystem paths or bounded text payloads. There is no general phone-to-desktop binary PDF inbox with chunking, resumability, hashing, and atomic promotion.

**VERIFIED FROM CODE — Desktop distribution**

The Tauri configuration is desktop-focused:

- product version 0.5.4 at inspection;
- Windows and macOS signed updater metadata;
- Linux `.deb` distribution with release notification rather than the same updater behavior;
- desktop-only CI matrices;
- no generated Android Gradle project;
- no generated Apple mobile/Xcode project;
- no Kotlin or Swift mobile integration.

The Rust crate contains `#[cfg_attr(mobile, tauri::mobile_entry_point)]`, but its actual initialization remains desktop-specific. A mobile attribute alone does not make the project mobile-compatible.

## 3. Existing Mobile Architecture

**VERIFIED FROM CODE —** `adapters/mobile` is a responsive browser companion, not a native application.

Its current model is:

```text
Phone browser
    -> HTTPS tunnel
    -> dedicated read-only Uvicorn process
    -> same SQLite library
```

Strengths worth preserving:

- Same responsive Callosum UI vocabulary.
- Server-side read-only enforcement.
- Access to papers, metadata, abstracts, PDFs, annotations, summaries, axes, tags, and queue state.
- Bearer authentication with constant-time comparison.
- Rate limiting.
- Cloudflare ingress path allowlisting.
- Local-only guards for dangerous filesystem/system routes.
- Tests demonstrating that mutation methods are rejected.
- A tunnel-target fail-closed mode.

`CALLOSUM_READ_ONLY=1` rejects non-GET/HEAD/OPTIONS requests before route execution. This is substantially stronger than hiding buttons. `local_only.py` independently rejects forwarded or non-loopback access for sensitive functions.

Constraints:

- Setup is still technical: tunnel/account/domain/token/runtime details remain visible in the documented path.
- The browser stores its bearer token in local storage.
- The browser client lacks hardware-backed device identity.
- Cloudflare terminates public TLS unless Callosum adds application-layer encryption; therefore the current tunnel is not an E2EE content architecture.
- The read-only API intentionally cannot submit synthesis, critique, imports, annotations, or other mutations.
- The browser uses internal backend endpoints rather than a stable mobile protocol.
- It requires the desktop process and read-only backend instance to remain running.
- It has no offline application cache or native share integration.

There are two related but distinct Cloudflare mechanisms:

1. `adapters/mobile` documents the restricted read-only companion.
2. `quick_tunnel.rs` manages an explicit Quick Tunnel for browser-based Office integrations. It still requires `cloudflared`, uses a random URL, and does not constitute consumer mobile pairing.

Cloudflare explicitly describes Quick Tunnels as development/testing functionality, with a random hostname, a 200-request limit, and no SSE support. [Cloudflare Quick Tunnel documentation](https://developers.cloudflare.com/cloudflare-one/networks/connectors/cloudflare-tunnel/do-more-with-tunnels/trycloudflare/)

**RECOMMENDATION —** Keep the companion supported as a read-only fallback. Preserve its method gate, route allowlist, rate limits, and local-only protections. Do not make its bearer-token/tunnel arrangement the native mobile security model.

## 4. Tauri v2 Mobile Feasibility

Tauri v2 is feasible, but the clean boundary is a second shell package using shared code—not the desktop shell with increasingly elaborate `cfg` branches.

**VERIFIED FROM DOCUMENTATION —** Tauri produces native Android Studio and Xcode projects, allows Kotlin/Swift mobile plugin implementations, supports Android/iOS capability configuration, and documents mobile support for HTTP, WebSocket, deep links, notifications, filesystem access, SQL, and Stronghold. [Tauri mobile plugin development](https://v2.tauri.app/develop/plugins/develop-mobile/)

| Area | Feasibility | Material caveat |
|---|---|---|
| React presentation components | High | Current globals/CDN build must become self-contained |
| Responsive CSS/layout | Moderate-high | Navigation and dense desktop views need mobile-specific shells |
| Domain display logic | High | Separate transport from direct internal endpoint calls |
| Desktop Rust startup code | Low | Python, llama.cpp, updater, child processes, and external browser startup are desktop-only |
| Shared Rust protocol/types/crypto | High | Best major reuse boundary |
| HTTP/WebSocket transport | High | Mobile lifecycle and background suspension differ |
| Deep links | High | Universal/App Links require platform/domain configuration |
| Notifications | High | APNs/FCM infrastructure and permissions are separate work |
| Secure storage | Moderate-high | Stronghold needs a focused usability/security spike; native Keychain/Keystore bridges may be preferable |
| File import/opening | Moderate | Mobile sandbox and content URI/security-scoped URL handling apply |
| Share target | Native work required | Android intent handling and an iOS Share Extension are needed |
| Background connection | Low | Neither platform permits an unrestricted permanent background socket |
| Desktop updater reuse | None | Mobile releases must use store-controlled distribution |

Current desktop plugins also expose a useful incompatibility warning:

- `single-instance` and the desktop updater are desktop concepts.
- The current updater dependency/configuration is desktop-conditioned.
- Mobile must not receive desktop updater commands or desktop child-process permissions.
- Mobile needs its own narrowly scoped capability files.

**INFERENCE —** Approximately 50–70% of presentation/domain UI may be reusable after transport and asset-loading seams are introduced. The shell, navigation, pairing, files, lifecycle, storage, and job interaction will be substantially mobile-specific. This estimate should be tested with a two-screen prototype, not treated as a commitment.

**RECOMMENDATION —** Create a related `app/mobile-shell` package with its own Tauri configuration, capabilities, icons, bundle IDs, mobile dependencies, generated native projects, and release workflows.

## 5. Feature Placement Matrix

| Actual capability | Placement | Architectural reason |
|---|---|---|
| Library browsing | MOBILE LOCAL | Cache an encrypted index; desktop supplies snapshots/deltas |
| Library search | MOBILE LOCAL | Search cached metadata offline; desktop handles authoritative/full-text refresh |
| Paper metadata | MOBILE LOCAL | Small, useful offline dataset |
| Abstracts | MOBILE LOCAL | Cacheable and low-risk |
| PDF reading | MOBILE LOCAL | Native/mobile PDF presentation; fetch from desktop and optionally pin offline |
| Full-text/chunks | MOBILE LOCAL + DESKTOP REFRESH | Cache selected text; extraction remains desktop work |
| Existing annotations | MOBILE LOCAL | Display from cache |
| Add/edit annotations | MOBILE-NATIVE EXTENSION | Touch/Pencil interaction is valuable; synchronize through scoped commands |
| Notes | MOBILE-NATIVE EXTENSION | Offline drafting is useful; versioned conflict handling required |
| Tags | MOBILE-NATIVE EXTENSION | Small reversible mutation; queue offline |
| Reading queue/status | MOBILE-NATIVE EXTENSION | Natural phone interaction and mergeable state |
| Zotero browsing/link metadata | MOBILE LOCAL | Display imported metadata; desktop remains integration authority |
| Zotero import/conversion | DESKTOP ONLY | Credentials, files, folders, attachments, and bulk processing |
| Mendeley/EndNote imports | DESKTOP ONLY | OAuth/library archives and attachment extraction belong on desktop |
| Folder/watch-folder import | DESKTOP ONLY | Phone cannot meaningfully supply a desktop filesystem path |
| DOI ingestion | MOBILE-NATIVE EXTENSION | “Share to Callosum” queues DOI; desktop resolves/imports |
| URL ingestion | MOBILE-NATIVE EXTENSION | Browser share target; desktop retrieves and processes |
| PDF ingestion | MOBILE-NATIVE EXTENSION + DESKTOP EXECUTION | Phone stages bounded upload; desktop verifies, stores, extracts |
| Metadata correction | DEFER | Add later through optimistic concurrency; not necessary for initial mobile |
| Synthesis Ask | MOBILE UI + DESKTOP EXECUTION | Existing Python/provider pipeline and library evidence stay desktop-side |
| Supplementary Overview | MOBILE UI + DESKTOP EXECUTION | Desktop computes; mobile presents output and references |
| Primary synthesis | MOBILE UI + DESKTOP EXECUTION | Same |
| Critical Read/critique | MOBILE UI + DESKTOP EXECUTION | Same; preserve evidence/provenance |
| Meta-preregistration and other LLM actions | MOBILE UI + DESKTOP EXECUTION | No mobile model/provider credentials needed |
| Local AI | MOBILE UI + DESKTOP EXECUTION | Managed llama.cpp/Qwen remains desktop-owned |
| Cloud AI | MOBILE UI + DESKTOP EXECUTION | Desktop owns provider selection and keys; mobile must display locality/privacy class |
| Discover search/feed/journals | MOBILE LOCAL + DESKTOP EXECUTION | Cache results; desktop performs external queries and persistence |
| Funding triage | MOBILE UI + DESKTOP EXECUTION | Heavy provider and deterministic pipelines stay desktop-side |
| My Publications | MOBILE LOCAL + DESKTOP REFRESH | Browsing is cacheable; enrichment remains desktop |
| Axes | MOBILE LOCAL | Browse locally; complex reorganization can remain desktop initially |
| Axis/tag assignment | MOBILE-NATIVE EXTENSION | Scoped, reversible mutation |
| Axis generation/rescoring | MOBILE UI + DESKTOP EXECUTION | Model/service execution remains desktop |
| GRIM/DEBIT/statcheck/method checks | MOBILE UI + DESKTOP EXECUTION | Results display well; data parsing/computation stays desktop |
| Bayes/LMM/meta-analysis tooling | MOBILE UI + DESKTOP EXECUTION or DEFER | Results are mobile-readable; data-entry interfaces require dedicated UX |
| Cite/Meta-Reference/statements/CRediT | DEFER | Mobile viewing/copying may be useful, but document-authoring integrations remain desktop |
| WIP/manuscript workspaces | DEFER | Current routes are explicitly local-only and can touch local files; require a designed facade |
| Word/LibreOffice/Google Docs integration | DESKTOP ONLY | Host application integration and companion processes |
| Exports | SPLIT | Small citation/text exports mobile-local; library/bundle/filesystem exports desktop-only |
| Job history/status | MOBILE LOCAL + DESKTOP STREAM | Cache status; desktop remains authoritative |
| Job cancellation | MOBILE-NATIVE EXTENSION | Permit only jobs submitted by the paired device unless separately authorized |
| Help | MOBILE LOCAL | Bundle help corpus |
| Diagnostics/status | MOBILE LOCAL + DESKTOP READ | Mobile should explain desktop/relay/job states without exposing secrets |
| Provider credentials/settings | DESKTOP ONLY | High-impact secrets and configuration |
| Local AI setup/model repair | DESKTOP ONLY | Runtime lifecycle belongs on compute host |
| Database maintenance/backup/restore | DESKTOP ONLY | High-impact operation |
| Permanent deletion/trash emptying | DESKTOP ONLY in V1 | Destructive; reversible removal can be considered later |
| Background jobs | DESKTOP EXECUTION | Mobile may submit/observe, not execute Python pipeline |
| Offline AI | DEFER | Contrary to the narrow client architecture and resource constraints |

## 6. Connectivity Architecture Comparison

Scores use 1 = poor and 5 = strong/favorable. For burden, cost, complexity, lock-in, and maintenance, 5 means lower burden.

- **A:** LAN direct using mDNS/Bonjour and authenticated application transport.
- **B:** ICE/STUN peer-to-peer without guaranteed relay.
- **C:** Callosum-managed E2EE relay only.
- **D:** LAN direct plus E2EE relay fallback.
- **E:** Programmatically managed Cloudflare Tunnel.
- **F:** Embedded Tailscale/WireGuard-style mesh VPN.

| Criterion | A | B | C | D | E | F |
|---|---:|---:|---:|---:|---:|---:|
| End-user simplicity | 4 | 4 | 5 | 5 | 3 | 2 |
| Overall reliability | 3 | 3 | 5 | 5 | 4 | 4 |
| LAN behavior | 5 | 4 | 3 | 5 | 2 | 4 |
| Remote behavior | 1 | 4 | 5 | 5 | 5 | 5 |
| CGNAT behavior | 1 | 2 | 5 | 5 | 5 | 4 |
| Security potential | 4 | 4 | 5 | 5 | 3 | 5 |
| Privacy potential | 5 | 5 | 4 | 5 | 3 | 4 |
| Infrastructure burden | 5 | 3 | 3 | 2 | 4 | 2 |
| Bandwidth efficiency | 5 | 5 | 2 | 4 | 2 | 4 |
| Expected operating cost | 5 | 4 | 2 | 3 | 3 | 2 |
| Implementation simplicity | 4 | 1 | 4 | 2 | 3 | 1 |
| Windows fit | 4 | 3 | 5 | 4 | 3 | 4 |
| macOS fit | 4 | 3 | 5 | 4 | 3 | 4 |
| Linux fit | 4 | 3 | 5 | 4 | 3 | 4 |
| Android fit | 4 | 3 | 5 | 4 | 4 | 2 |
| iOS fit | 3 | 3 | 5 | 4 | 4 | 2 |
| App Store risk | 5 | 4 | 4 | 4 | 3 | 1 |
| Play Store risk | 5 | 4 | 5 | 5 | 4 | 2 |
| Vendor lock-in | 5 | 4 | 5 | 5 | 1 | 3 |
| Long-term maintainability | 4 | 2 | 4 | 3 | 3 | 1 |

### Findings

**A — LAN-only:** Secure and inexpensive but fails the remote-use requirement. iOS Local Network permission, Bonjour declarations, firewalls, guest Wi-Fi isolation, and changing network conditions prevent it being the sole transport.

**B — ICE/STUN:** Direct connections are attractive, but symmetric NAT and CGNAT still require TURN. Once TURN is required for reliability, Callosum operates a relay anyway while also carrying WebRTC/ICE complexity. [ICE specification](https://www.rfc-editor.org/info/rfc8445), [TURN specification](https://www.rfc-editor.org/info/rfc8656)

**C — Relay-only:** The strongest implementation runner-up. Every endpoint makes outbound TLS connections, so NAT traversal is predictable. E2EE prevents relay content access. Its weakness is bandwidth: locally reading a 100 MB PDF should not travel through Callosum infrastructure.

**D — Hybrid:** Best product outcome. LAN direct handles large/local transfers; the relay makes remote and CGNAT behavior boring and reliable. The complexity is justified because each transport has a clear role, and both share one authentication/encryption protocol.

**E — Cloudflare:** Quick Tunnels are explicitly non-production. Named tunnel provisioning requires account/tunnel permissions and commonly DNS/account configuration. Hiding that inside Callosum would transfer vendor credentials and lifecycle problems into the product rather than eliminate them. [Cloudflare API tunnel requirements](https://developers.cloudflare.com/cloudflare-one/networks/connectors/cloudflare-tunnel/get-started/create-remote-tunnel-api/)

**F — Mesh/VPN:** Technically capable, but disproportionate. Tailscale’s managed coordination service is proprietary, while its clients/DERP components have mixed open-source boundaries; ordinary use normally involves a tailnet/account. Embedding a packet tunnel on iOS invokes specialized Network Extension responsibilities. [Tailscale open-source architecture](https://tailscale.com/opensource), [Apple packet-tunnel guidance](https://developer.apple.com/documentation/technotes/tn3120-expected-use-cases-for-network-extension-packet-tunnel-providers)

## 7. Recommended Connectivity Architecture

Use hybrid direct/relay transport without full ICE in V1:

```text
                        ┌─────────────────────────┐
                        │ Callosum relay/control  │
                        │                         │
                        │ opaque pair routing     │
                        │ connection presence     │
                        │ ciphertext forwarding   │
                        │ push dispatch           │
                        └───────▲─────────▲───────┘
                                │ WSS     │ WSS
                         ciphertext     ciphertext
                                │         │
┌─────────────┐  direct LAN  ┌──┴─────────┴──────┐
│ Mobile app  │◄════════════►│ Callosum Agent    │
│ device key  │ app-layer    │ desktop device key│
└─────────────┘ E2EE/auth     └───────────────────┘
```

Transport selection:

1. Mobile checks an already-paired LAN service discovered with mDNS/Bonjour.
2. It authenticates the desktop using the pinned paired identity—not the advertised hostname.
3. If direct connection succeeds, use it.
4. Otherwise both sides’ outbound relay connections carry encrypted frames.
5. Retry direct periodically without interrupting the session.
6. Preserve one logical session and job ID space during path changes.

The application encryption and authentication protocol must be identical over both paths. The relay must never become a trusted TLS terminator for scholarly payloads.

Large-transfer policy:

- Prefer direct LAN for PDFs.
- Permit bounded, resumable relay PDF transfers only after measurements establish acceptable cost.
- Apply per-device quotas and size limits.
- Consider “remote PDF transfer unavailable; available when near your computer” before creating unlimited relay exposure.
- Metadata, job commands, progress, and textual results are inexpensive enough for normal relay use.

**Runner-up:** Relay-only, if direct discovery proves unreliable enough to delay release. The protocol should retain room to add direct transport later.

## 8. Pairing and Device Identity

Recommended flow:

1. Desktop creates an expiring, single-use pairing invitation.
2. QR encodes:
   - protocol version;
   - relay/rendezvous locator;
   - random invitation identifier;
   - desktop ephemeral/public pairing key;
   - high-entropy one-time secret;
   - expiration.
3. Mobile generates its persistent device key locally.
4. Mobile contacts the desktop through LAN or relay and proves possession of the QR secret.
5. Desktop displays “Vasiliki’s iPhone wants to connect.”
6. Both screens show a short verification phrase or digits derived from the transcript.
7. User selects **Allow** on desktop.
8. Desktop records the mobile public identity and granted capability set.
9. The invitation becomes unusable.
10. Future sessions authenticate mutually with the established device keys and fresh ephemeral session keys.

The QR must not contain a reusable bearer credential.

**RECOMMENDATION — Cryptography**

Use an audited, standard handshake pattern rather than designing one:

- Noise XX for first pairing;
- Noise IK or equivalent authenticated resumption after identities are known;
- X25519 key agreement;
- HKDF-SHA-256 key derivation;
- ChaCha20-Poly1305 or AES-GCM authenticated encryption;
- fresh session keys and replay-protected counters.

[Noise Protocol Framework](https://noiseprotocol.org/noise.html), [X25519](https://www.rfc-editor.org/info/rfc7748), [HKDF](https://www.rfc-editor.org/info/rfc5869)

Store device secrets in:

- iOS Keychain, optionally protected by device authentication;
- Android Keystore or a Keystore-wrapped encrypted seed;
- desktop OS keychain;
- only non-secret device names, public keys, capabilities, and revocation state in SQLite.

There is a real implementation tradeoff: a cross-platform X25519 secret is easy to use in Rust but may not be hardware-nonexportable on all supported phones. Native P-256 keys can receive stronger hardware protection but require platform bridges and a compatible protocol design. Resolve this with a small cryptographic storage spike before selecting libraries.

Required device management:

- list paired devices;
- last-seen time;
- capability summary;
- rename;
- revoke;
- revoke all;
- rotate credentials over an authenticated channel;
- expire never-completed pairing sessions;
- require re-pairing after local credential loss.

## 9. Security Threat Model

| Threat | Mitigation | Residual risk |
|---|---|---|
| Attacker on same Wi-Fi | Mutual device authentication and application E2EE; discovery data grants no authority | Traffic timing and device presence may be observable |
| Malicious public Wi-Fi/MITM | Pinned paired identity; authenticated transcript; no trust in LAN DNS or relay TLS alone | Denial of service remains possible |
| Stolen phone | OS lock, Keychain/Keystore, scoped capabilities, desktop revocation, minimal offline cache | Already-decrypted offline content cannot be remotely guaranteed erased |
| Stolen desktop | OS encryption/keychain and device revocation | A fully compromised library host can read its own library |
| Compromised relay | E2EE payloads, replay protection, no keys server-side | Relay sees IPs, timing, byte counts, and opaque routing IDs |
| Compromised rendezvous | Pairing transcript authentication and desktop confirmation | Can deny or delay pairing |
| QR interception | High entropy, short expiry, single use, explicit desktop confirmation | Attacker can create a visible nuisance pairing request |
| Brute-force pairing | At least 128 bits of randomness and rate limiting | Availability attacks remain |
| Replay | Session transcript binding, counters/nonces, invitation consumption | Corrupt local state could require re-pairing |
| Leaked logs | Never log secrets, payloads, full URLs, PDF text, prompts, or outputs | Diagnostic metadata still needs review |
| Leaked relay URL | URL is routing information, not authorization | Traffic analysis remains |
| Malicious web content | Strict CSP, no arbitrary navigation, Rust transport facade, scoped Tauri capabilities | WebView vulnerabilities remain part of patching risk |
| CSRF/arbitrary API calls | Native bridge and signed/scoped commands; never expose general FastAPI externally | Protocol implementation bugs |
| Device impersonation | Proof of possession of paired private key | Key extraction from a compromised phone |
| Formerly authorized phone | Immediate server-side revocation and relay denial; local revocation list | Offline phone retains data already cached |
| Old/downgraded client | Protocol minimums, capability negotiation, reject insecure versions | Store rollout lag |
| Exposed desktop port | Expose only narrow mobile protocol; authentication before commands; firewall guidance | LAN denial-of-service |
| Malicious mobile import | MIME/size checks, quarantine/staging, hash, parser isolation, no phone-supplied desktop paths | Malicious PDF/parser risk remains |
| Mobile triggers desktop cloud AI unexpectedly | Advertise execution class and active provider before submission; preserve desktop cloud consent | User may still misunderstand data egress without clear copy |

Current browser defenses—method gating, route allowlisting, rate limits, local-only route protection, and fail-closed tunnel mode—should survive as defense-in-depth concepts.

## 10. Mobile API and Job Protocol

Create `mobile-protocol-v1`, separate from the broad internal FastAPI surface.

The protocol should expose capabilities, not arbitrary route paths:

- `library.read`
- `paper.read`
- `paper.pdf.read`
- `result.read`
- `annotation.write`
- `note.write`
- `tag.write`
- `queue.write`
- `inbox.submit_doi`
- `inbox.submit_url`
- `inbox.submit_pdf`
- `job.submit.<kind>`
- `job.read`
- `job.cancel.own`

It should not expose provider credentials, database maintenance, filesystem paths, arbitrary settings, plugins, or arbitrary backend endpoints.

Every envelope should include:

- protocol version;
- request ID;
- idempotency key for mutations;
- paired device ID;
- required capability;
- counter/replay state;
- operation and typed payload;
- trace ID;
- structured success/error result.

Session negotiation should return:

- desktop and mobile versions;
- protocol min/max;
- granted capabilities;
- supported job types;
- selected execution provider and privacy class;
- desktop availability state;
- transfer limits;
- cache/snapshot version.

Jobs require a durable desktop-facing ledger:

- stable job ID;
- submitting device;
- operation;
- created/started/completed timestamps;
- queued/running/succeeded/failed/cancelled state;
- progress/stage;
- retryability;
- stable error code;
- result/provenance locator;
- expiry.

Do not expose the current in-memory `JobStore` directly as a protocol contract. Adapt it behind a persistent facade.

For V1, a WebSocket can carry job events and normal request/response frames. Mobile reconnects with its last acknowledged sequence. HTTP polling can remain a compatibility fallback. WebSocket itself is standardized by [RFC 6455](https://www.rfc-editor.org/info/rfc6455).

Binary ingestion should use:

- declared size and MIME;
- maximum size;
- chunk sequence or ranged upload;
- resumable transfer ID;
- content SHA-256;
- staging directory;
- atomic promotion only after verification;
- idempotent finalization;
- cancellation and expiry.

Never accept a phone-supplied path as a desktop filesystem path.

## 11. Desktop Agent and Availability

**VERIFIED FROM CODE —** Closing the current Tauri application terminates the Python backend, local AI, and other managed children. The existing architecture cannot serve mobile while its UI is closed.

**RECOMMENDATION —** A per-user Callosum Agent is warranted for the mature product:

- owns the Python backend lifecycle;
- owns the persistent mobile relay connection;
- owns Mobile API authentication and the durable job ledger;
- starts local AI as required;
- exposes a local authenticated control channel to the visible desktop UI;
- runs only with explicit user consent;
- does not require administrative privileges;
- has an obvious “Allow mobile access while Callosum is closed” setting.

Platform approach:

- Windows: per-user startup registration.
- macOS: `SMAppService`/approved login-item mechanism where supported. `SMAppService` begins at macOS 13, so Callosum’s current macOS 12 floor creates a compatibility decision. [Apple SMAppService](https://developer.apple.com/documentation/servicemanagement/smappservice)
- Linux: systemd user service where available, with desktop-autostart fallback.

Do not use a privileged system daemon unless a future requirement proves it necessary.

Product states must be explicit:

- **Connected**
- **Computer reachable; Callosum starting**
- **Computer offline**
- **Computer asleep**
- **Callosum Mobile access disabled**
- **Computer version requires update**

A background agent does not solve suspend, hibernation, power-off, or lost connectivity. Wake-on-LAN is unreliable across routers, Wi-Fi adapters, sleep modes, CGNAT, and platforms. It can be an optional advanced optimization, never a V1 promise.

A staged beta may require “Keep Callosum open,” but the public zero-configuration experience should include the agent.

## 12. Offline and Synchronization Model

### Necessary for V1

- Encrypted local cache of library index, metadata, abstracts, recent results, and compact provenance.
- Optional user-selected offline PDFs.
- Recent-paper cache with a configurable cap.
- Offline library search over cached metadata.
- Queued DOI and URL submissions.
- Queued notes, annotations, tags, and reading-state changes.
- Clear per-action “Waiting for your computer” state.
- Snapshot/delta cursors from the Mobile API.
- Logout/unpair removes keys and app-accessible cache.

### Valuable soon after V1

- Resumable background PDF pinning.
- Job submission queues.
- Generic “job complete” push notifications.
- Cached extracted text for selected papers.
- Conflict UI for notes/annotations.
- Multiple paired desktops.

### Probably overengineering

- Full replication of the desktop SQLite schema.
- Offline copies of embeddings/model caches/signals.
- CRDT treatment of every table.
- Full PDF-library mirroring by default.
- Mobile execution of desktop AI runtimes.
- Treating mobile and desktop as equal multi-writer database nodes.

Conflict rules:

- Tag addition, queue changes, and read state can use idempotent merge operations.
- Notes and annotations should use optimistic versions; on conflict, preserve both edits and ask the user.
- Destructive changes should not queue offline in V1.
- Revocation prevents future synchronization but cannot cryptographically erase already-viewed content from a stolen offline phone.

The existing E2EE sync system is relevant precedent: it already uses encrypted records and device/library identities. However, its `SYNCABLE` set excludes PDFs and many derived artifacts, and its account/passphrase model should not silently become mobile pairing. Reuse audited concepts and perhaps crypto utilities, not the trust domain.

## 13. Android Implementation Constraints

**VERIFIED FROM DOCUMENTATION —**

- Tauri supports Android 7/API 24 as its technical minimum. [Tauri Google Play guide](https://v2.tauri.app/distribute/google-play/)
- As of August 31, 2026, new Play submissions and updates must target Android 16/API 36. [Google target API requirements](https://developer.android.com/google/play/requirements/target-sdk)
- Android network service discovery uses `NsdManager`. [Android NSD](https://developer.android.com/reference/android/net/nsd/NsdManager)
- Background execution and foreground services are restricted; persistent invisible networking is not a safe assumption. [Foreground-service restrictions](https://developer.android.com/develop/background-work/services/fgs/restrictions-bg-start)
- App-distributed self-updates and downloaded native executable code are prohibited. [Google Device and Network Abuse policy](https://support.google.com/googleplay/android-developer/answer/16559646?hl=en)

**RECOMMENDATION —**

- Minimum practical product floor: Android 10/API 29, subject to user telemetry and test-device availability.
- Target API 36.
- Request `INTERNET`; design for evolving local-network permissions, including Android’s new Local Network permission direction.
- Use `NsdManager` for LAN discovery.
- Receive URLs/text/PDFs with `ACTION_SEND` and explicit intent filters.
- Consume `content://` URIs immediately or persist their granted access when allowed.
- Implement share handling in a small Kotlin Tauri plugin rather than trusting an unreviewed community plugin as a production dependency.
- Use Android Keystore for device-secret protection.
- Use WorkManager/user-initiated transfer APIs for resumable uploads.
- Do not keep a permanent foreground service solely to maintain relay connectivity.
- Persist connection/job state because Android may kill the process.
- Use FCM only as a generic wake/result signal; do not include paper metadata or AI text in push payloads.
- Request notification permission only when introducing notifications.
- Ship AABs through Play; preserve store signing keys and CI credentials separately.

Battery optimization and process death must be normal tested states, not exceptional errors.

## 14. iOS Implementation Constraints

**VERIFIED FROM DOCUMENTATION —**

- Tauri’s default minimum iOS version is configurable; the current ecosystem supports mobile builds and native Swift plugin work.
- Local service discovery requires `NSLocalNetworkUsageDescription`, and Bonjour service types require `NSBonjourServices`. [Local Network permission](https://developer.apple.com/documentation/BundleResources/Information-Property-List/NSLocalNetworkUsageDescription), [Bonjour services](https://developer.apple.com/documentation/BundleResources/Information-Property-List/NSBonjourServices)
- Local Network privacy requires real-device testing; simulator behavior is not sufficient. [Apple TN3179](https://developer.apple.com/documentation/technotes/tn3179-understanding-local-network-privacy)
- App Transport Security restricts insecure network behavior. [Apple ATS guidance](https://developer.apple.com/documentation/security/preventing-insecure-network-connections)
- Background execution is limited to specific modes and finite tasks; silent push delivery is not guaranteed. [Background strategy guidance](https://developer.apple.com/documentation/backgroundtasks/choosing-background-strategies-for-your-app)
- Share functionality requires an App Extension with its own lifecycle and restrictions. [Apple Share Extension guide](https://developer.apple.com/library/archive/documentation/General/Conceptual/ExtensibilityPG/Share.html)

**RECOMMENDATION —**

- Minimum product floor: iOS 16, unless the intended user base materially requires older versions.
- Use Bonjour only for discovery; never trust the advertised identity.
- Use Keychain for device credentials.
- Use a native/Rust authenticated channel rather than exposing cleartext LAN FastAPI to the WebView.
- Build a Swift Share Extension target for URLs, DOI text, and PDFs.
- Use an App Group container to pass staged share items from the extension to the main application.
- The extension should save a bounded local queue quickly; it must not depend on completing a remote desktop upload before the extension timeout.
- Use document picker/security-scoped URL handling for user-selected PDFs.
- Use Universal Links and a custom deep-link fallback for invitation/recovery flows.
- Reconnect in foreground; use APNs for generic job-complete notifications.
- Never promise continuous relay connectivity while suspended.
- Complete Apple encryption/export-compliance declarations. [Apple export compliance overview](https://developer.apple.com/help/app-store-connect/manage-app-information/overview-of-export-compliance)

The product should not depend on Secure Enclave specifically until the cross-platform key-algorithm decision is settled.

## 15. Mobile-Native Opportunities

### Share to Callosum

This is the highest-value native extension.

```text
Browser / PDF viewer / Files
    -> Share
    -> Callosum
    -> Review detected DOI, URL, citation, or PDF
    -> Add to desktop inbox
    -> Desktop imports/extracts
    -> Mobile reports progress/result
```

Android requirements:

- `ACTION_SEND` and potentially `ACTION_SEND_MULTIPLE`;
- MIME and URI validation;
- `FileProvider`/content URI support;
- temporary grant handling;
- a small Kotlin/Tauri bridge.

iOS requirements:

- Swift Share Extension;
- activation rules for URL, text, and PDF;
- `NSItemProvider`;
- App Group storage;
- bounded staging and cleanup;
- main-app handoff.

Other strong mobile opportunities:

- camera-based QR pairing;
- DOI/ISBN/barcode capture;
- Apple Pencil/touch PDF annotation;
- read-later triage;
- offline reading queue;
- notification-driven review of completed synthesis/critique;
- share selected evidence or citation text back to another app;
- voice dictation into notes using normal OS input;
- compact “verify this claim” workflows while reading;
- quick capture of a paper from a conference slide or poster.

These provide independent mobile value and help distinguish Callosum Mobile from a remote desktop/thin client.

## 16. First-Run and Pairing UX

### Phone

1. **Welcome to Callosum**
   - “Connect this phone to Callosum on your computer.”
   - Primary action: **Connect my computer**
   - Secondary action: **Try offline demo**

2. **On desktop**
   - “Open Callosum → Settings → Mobile Devices → Connect a device.”
   - **Scan QR code**

3. **Permission**
   - Camera permission only after the scan action.
   - Local Network permission explained as: “Find your computer when both devices are nearby.”

4. **Connecting**
   - “Finding your Callosum…”
   - The app silently tries LAN and relay.

5. **Desktop confirmation**
   - Phone: “Check your computer and choose Allow.”
   - Desktop: “Vasiliki’s iPhone wants to connect.”
   - Both show the same short verification phrase.

6. **Success**
   - “Connected.”
   - “Your library will now be available on this phone.”
   - Optional: **Keep selected papers available offline**

### Desktop

1. Settings → Mobile Devices.
2. **Connect a phone or tablet**.
3. QR appears with countdown.
4. Pairing request appears with device name and verification phrase.
5. **Allow** or **Deny**.
6. Choose initial capabilities using a safe default:
   - Browse library and PDFs.
   - Run analyses.
   - Add notes/annotations/tags.
   - Send papers to inbox.
7. Success screen lists device, last seen, and **Revoke access**.

### Recovery states

- **Computer offline:** “Your computer is offline. Cached papers remain available; new work will wait.”
- **Computer asleep:** “Wake your computer to run this task.”
- **Pair expired:** “This code expired. Create a new one on your computer.”
- **Local Network denied:** “Remote connection still works. Enable Nearby Computer Access in Settings for faster PDF loading at home.”
- **Relay unavailable:** “Callosum’s connection service is temporarily unavailable. Nearby connections may still work.”
- **Desktop too old:** “Update Callosum on your computer before connecting.”
- **Lost/replaced phone:** revoke it from desktop and pair the replacement.
- **No desktop access after phone loss:** existing desktop remains source of authority; there is no accountless cloud recovery of device keys.

This meets the stated usability bar without showing tunnels, hosts, ports, or certificates.

## 17. Privacy and Infrastructure

The managed service needs four bounded responsibilities:

1. Rendezvous for active pairing sessions.
2. Presence and routing for paired devices.
3. Forwarding opaque encrypted frames.
4. Optional APNs/FCM dispatch for content-free status notifications.

It does not need:

- the Callosum database;
- provider credentials;
- decrypted PDF content;
- prompts;
- LLM output;
- library metadata;
- permanent relay storage.

| Data | Relay visibility |
|---|---|
| PDF bytes | Ciphertext only |
| Prompt/evidence | Ciphertext only |
| LLM output | Ciphertext only |
| Library metadata | Ciphertext only |
| Notes/annotations | Ciphertext only |
| Source/destination IP | Visible |
| Opaque pair/device routing IDs | Visible |
| Connection timing/duration | Visible |
| Byte counts | Visible |
| Protocol/application version | Likely visible for routing/compatibility |
| Push token mapping | Visible to notification service |
| Device private keys | Never sent |
| User name/email | Not required in accountless design |

Do not describe this as “zero knowledge.” Network metadata remains visible.

Infrastructure shape:

- stateless or lightly stateful WebSocket relay nodes;
- small routing/revocation/quota database;
- push dispatcher;
- no payload logs;
- short-lived in-memory buffering;
- bounded ciphertext queue only if offline delivery is deliberately added;
- per-pair and per-IP rate/transfer limits;
- aggregate operational telemetry without scholarly content.

Bandwidth is the main cost driver. Job commands and textual results are small; PDFs can dominate. A small beta may run for tens of dollars per month, but broader use with relayed PDFs could grow to hundreds or more. That is a cost-driver estimate, not a vendor quote. Measure bytes per paired user before committing to remote PDF limits.

If relay infrastructure fails:

- desktop remains fully functional;
- same-LAN direct access may continue;
- phone retains cached content;
- queued phone actions remain locally encrypted;
- remote actions show an honest service-unavailable state.

## 18. App Store and Play Store Considerations

### Apple

Apple requires native iOS signing/provisioning and App Store/TestFlight distribution. [Tauri iOS signing guide](https://v2.tauri.app/distribute/sign/ios/)

Important risks:

- Guideline 2.5.2 prohibits downloading executable code that changes app functionality. Callosum Mobile should download data/results only, never mobile code or model binaries.
- Guideline 4.2 expects meaningful app-like functionality.
- Guideline 4.2.7 places LAN-only restrictions on certain specific-software remote desktop clients and rejects cloud thin clients. [Apple App Review Guidelines](https://developer.apple.com/app-store/review/guidelines/)

**INFERENCE —** Callosum Mobile should fall outside remote-desktop treatment because it:

- does not mirror the host screen;
- renders structured library data using its own mobile UI;
- works offline for cached reading and queued actions;
- uses native sharing, files, notifications, annotations, and camera functions;
- does not stream arbitrary desktop applications.

This is still a material review risk. App Review notes should explain the architecture, provide a sample QR/demo host, and emphasize that the phone is a native scholarly client to a user-owned data store—not a mirrored desktop interface.

Apple also requires privacy disclosures, a privacy policy, explicit purpose strings, and export-compliance answers for encryption. Mobile releases must use App Store/TestFlight mechanisms, not Tauri’s desktop updater.

### Google Play

Google requires:

- target API compliance;
- AAB signing and Play Console setup;
- Data Safety disclosures;
- no external self-update or downloaded native executable code;
- declared permissions and background-service behavior.

Remote computation on a user-owned computer is not itself prohibited, provided access is authorized and the app does not abuse devices/networks. The app must not expose a general network tunnel or arbitrary remote-control primitive.

Both stores will need:

- privacy policy;
- support URL;
- retention/deletion explanation;
- review/demo process that works without reviewers possessing the developer’s personal library;
- synthetic demonstration data;
- store-specific versioning and release workflows.

## 19. Repository and Build Architecture

Recommended organization:

```text
app/
  desktop-shell/                 existing desktop Tauri shell
  mobile-shell/                  proposed Android/iOS Tauri shell
    src/
    src-tauri/
      tauri.conf.json
      capabilities/
      gen/android/
      gen/apple/

app/frontend/
  shared/                        reusable domain views/components
  desktop/                       desktop navigation/shell
  mobile/                        mobile navigation/pairing/offline shell

crates/
  callosum-mobile-protocol/      proposed schemas, versioning, errors
  callosum-mobile-crypto/        proposed pairing/session primitives
  callosum-mobile-transport/     proposed direct/relay abstraction

app/backend/api/routers/
  mobile_v1/                     proposed narrow local facade

services/
  mobile-relay/                  proposed rendezvous/relay service
```

Names are recommendations, not created paths.

Why separate shells:

- desktop currently starts Python, llama.cpp, updater, and child processes;
- mobile must not;
- capabilities and permissions differ radically;
- release/signing mechanisms differ;
- mobile needs native projects and extensions;
- keeping one giant configuration would increase accidental privilege and platform regressions.

Shared boundaries:

- protocol schemas and conformance fixtures;
- cryptographic transcript test vectors;
- domain view models;
- selected React presentation components;
- errors/diagnostic codes;
- design tokens and accessibility primitives.

Native modules:

- Android Kotlin: share intents, content URI handling, perhaps Keystore/NSD integration.
- iOS Swift: Share Extension, App Group handoff, Keychain integration where needed, lifecycle/deep-link handling.

CI needs:

- Android debug/release compilation and unit/instrumentation tests;
- iOS simulator build and Swift tests on macOS;
- Rust protocol tests on all desktop/mobile targets;
- frontend unit/accessibility tests;
- protocol compatibility tests against desktop versions;
- signed internal/alpha builds;
- secrets isolated by environment;
- no untrusted pull request access to signing material.

## 20. Incremental Shipping Plan

### Stage 0 — Architecture falsification

User-visible capability: internal prototype only.

Work:

- ADRs for transport, pairing, capability model, agent, and offline scope.
- Self-contained Tauri Android/iOS hello app.
- Shared paper-list/detail prototype.
- Real-device Bonjour/NSD test.
- E2EE relay latency/bandwidth prototype.
- iOS Share Extension spike.
- App Review classification risk assessment.
- Threat-model review and protocol test vectors.

Kill obvious architectural mistakes before application work.

### Stage 1 — Native read-only LAN beta

Capability:

- QR pair;
- browse/search papers;
- view metadata, abstracts, existing results, and PDFs while desktop app is open.

Work:

- versioned read-only facade;
- LAN discovery;
- device identity and revocation;
- mobile cache;
- self-contained frontend;
- no arbitrary FastAPI exposure.

### Stage 2 — Remote relay and production pairing

Capability:

- same read-only experience away from home.

Work:

- relay/rendezvous;
- shared E2EE transport;
- quotas/abuse controls;
- connection switching;
- privacy disclosures;
- external TestFlight/Play internal beta.

Desktop may still need to remain open at this stage.

### Stage 3 — Desktop agent and jobs

Capability:

- submit synthesis/Overview/critique;
- watch progress;
- cancel own jobs;
- receive completion notifications while the UI is closed.

Work:

- per-user agent;
- durable mobile job ledger;
- provider/locality disclosure;
- push service;
- stable error codes;
- Windows/macOS/Linux lifecycle testing.

### Stage 4 — Share to Callosum

Capability:

- share DOI, URL, text citation, or PDF from another app.

Work:

- Android Kotlin intent receiver;
- iOS Swift Share Extension/App Group;
- resumable inbox protocol;
- staging, size limits, MIME/hash validation;
- import progress.

### Stage 5 — Scoped mobile writing and offline use

Capability:

- add/edit annotations, notes, tags, and queue state;
- pin PDFs offline;
- queue safe actions while disconnected.

Work:

- optimistic versions/conflicts;
- encrypted mobile database;
- cache management;
- revocation handling.

### Stage 6 — Store release and broader capability polish

Capability:

- public Android/iOS release;
- refined tablets/large screens;
- broadened computational job catalogue.

Work:

- accessibility;
- localized permission copy;
- privacy and store submissions;
- performance/energy testing;
- support diagnostics;
- compatibility matrix;
- staged rollout and rollback.

## 21. Risks, Failure Modes, and Kill Criteria

| Risk | Kill criterion or required response |
|---|---|
| Apple classifies the app under restrictive remote-desktop/thin-client rules | Do not ship WAN execution on iOS until the product demonstrates native independent value and review risk is resolved |
| Relay costs dominated by PDFs | Cap remote PDFs, require LAN for large transfers, or add explicit user-funded storage/relay policy |
| Accountless relay abuse is unmanageable | Introduce a minimal service account or installation attestation only after proving anonymous quotas inadequate |
| mDNS is unreliable across common home networks | Keep it as an optimization, never the sole connection method |
| ICE cannot traverse CGNAT reliably | Do not use ICE without relay fallback |
| Relay can decrypt content | Reject the design; application-layer E2EE is mandatory |
| Mobile client needs arbitrary FastAPI access | Stop and create a narrow protocol facade |
| Pairing relies on a reusable QR bearer token | Reject and redesign around single-use invitation plus device identity |
| Desktop agent needs administrator/root privileges | Re-scope to a per-user agent |
| Mobile job state remains process-local | Do not claim restart-safe remote jobs |
| Phone background socket is required for correctness | Redesign around reconnectable sessions, persisted queues, and push notifications |
| iOS Share Extension cannot stage target PDF sizes reliably | Fall back to opening the main app with a staged security-scoped reference or narrow accepted sizes |
| Offline synchronization develops full distributed-database semantics | Reduce V1 scope to cached reads and reversible/versioned mutations |
| Provider selection causes unexpected cloud egress | Require execution-class disclosure and desktop-side consent before remote job submission |
| Mobile cache cannot be adequately protected | Reduce cached fields and make offline PDFs opt-in |
| Platform UI diverges beyond shared-code value | Keep shared protocol/domain models; allow native shell divergence rather than force false uniformity |
| Agent consumes excessive idle resources | Disconnect/suspend intelligently and measure; do not hide continuous heavy Python/model activity |
| Desktop sleeping is perceived as a bug | Make offline/asleep state central to UX; never promise reliable remote wake |
| Relay outage disables local access | Treat that as an architectural defect; LAN direct must remain independent |

## 22. Open Questions

These answers could materially change architecture:

1. Must the first public mobile release work remotely, or can a LAN-only native beta precede it?
2. May large PDFs traverse the relay, and what monthly bandwidth budget is acceptable?
3. What App Review feedback can be obtained on native structured interaction with paired desktop computation?
4. Should desktop macOS support remain at 12, or can the agent require/drive a move to macOS 13?
5. What minimum Android/iOS versions match Callosum’s actual users?
6. Must submitted jobs survive a desktop reboot, or only UI closure/backend restart?
7. Does mobile execute using whatever provider desktop currently selected, or should remote cloud execution require a separate explicit consent?
8. Should one phone pair with multiple desktops and vice versa in V1?
9. Can accountless relay quotas withstand abuse without app attestation or user accounts?
10. What maximum PDF size must the iOS Share Extension accept?
11. Which existing WIP/workspace operations merit a new safe mobile facade?
12. Is offline full-text search a V1 requirement or a post-launch optimization?
13. Which region, retention period, and hosting provider are acceptable for relay metadata?
14. Should existing OIDC/E2EE sync remain entirely separate from paired mobile transport?
15. How should device revocation interact with offline cached content and existing sync identities?

## 23. Files and Modules Likely to Change

No files were modified during the research pass. Likely later touch points include:

### Existing desktop/Tauri

- `app/desktop-shell/src-tauri/tauri.conf.json`
- `app/desktop-shell/src-tauri/Cargo.toml`
- `app/desktop-shell/src-tauri/src/lib.rs`
- `app/desktop-shell/src-tauri/src/backend.rs`
- `app/desktop-shell/src-tauri/src/updater.rs`
- `app/desktop-shell/src-tauri/src/quick_tunnel.rs`
- `app/desktop-shell/src-tauri/capabilities/default.json`

### Existing backend/security

- `app/backend/api/access_control.py`
- `app/backend/api/local_only.py`
- `app/backend/api/wip_security.py`
- `app/backend/api/status.py`
- `app/backend/api/paper_files.py`
- `app/backend/api/annotations.py`
- `app/backend/api/library.py`
- synthesis/critique/job routers and stores
- backend application assembly/router registration

### Existing frontend

- `app/frontend/js/00_lib.jsx`
- `app/frontend/js/00_bootstrap.jsx`
- `app/frontend/js/02_mobilenav.jsx`
- `app/frontend/js/04_layout.jsx`
- `app/frontend/js/40_app.jsx`
- responsive CSS and paper/PDF/result views
- `tools/build_frontend.py`

### Existing mobile/browser companion

- `adapters/mobile/README.md`
- `adapters/mobile/cloudflared-config.yml`
- `tests/test_mobile_ingress.py`
- `tests/test_access_control.py`

### Existing sync precedent

- `app/backend/sync/crypto.py`
- `app/backend/sync/identity.py`
- `app/backend/sync/changeset.py`
- `sync_server/`

### Build/release

- `.github/workflows/`
- desktop packaging/release scripts
- future mobile signing-secret configuration

### Proposed additions

- `app/mobile-shell/`
- shared mobile protocol/crypto/transport Rust crates
- a `mobile_v1` backend facade
- a Callosum Agent module/process
- a Callosum relay service
- mobile protocol conformance/security fixtures

## 24. Recommended Next Planning Step

Run a bounded **Mobile Architecture Falsification and ADR pass** before producing an implementation backlog.

It should lock five decisions:

1. `mobile-protocol-v1` operations and default device capabilities.
2. Noise/key-storage design, including X25519 versus native hardware-backed P-256.
3. LAN-direct plus relay framing and switching rules.
4. Desktop-agent lifecycle and the macOS 12/13 decision.
5. Apple review positioning and V1 independent/offline functionality.

Then build exactly four disposable proofs:

- Tauri Android/iOS paper-list/detail shell with all assets bundled.
- Real-device Android/iOS LAN discovery and authenticated connection.
- Two-device E2EE relay carrying synthetic metadata and a large synthetic PDF.
- Android share intent plus iOS Share Extension staging a synthetic PDF.

Predeclare go/no-go measurements:

- pairing success without technical input;
- remote success behind two unrelated consumer networks/CGNAT;
- reconnect after phone process death;
- relay inability to decrypt test payloads;
- acceptable battery/idle impact;
- quantified relay bytes and transfer time;
- iOS share completion within extension constraints;
- no general desktop API exposure.

Only after those pass should the planning pass decompose production stages into commits and releases.

## 25. Sources

### Tauri

- [Tauri distribution overview](https://v2.tauri.app/distribute/)
- [Tauri prerequisites](https://v2.tauri.app/start/prerequisites/)
- [Tauri configuration reference](https://v2.tauri.app/reference/config/)
- [Tauri mobile plugin development](https://v2.tauri.app/develop/plugins/develop-mobile/)
- [Tauri Android/Google Play distribution](https://v2.tauri.app/distribute/google-play/)
- [Tauri iOS signing](https://v2.tauri.app/distribute/sign/ios/)
- [Tauri capabilities and permissions](https://v2.tauri.app/security/permissions/)
- [Tauri HTTP plugin](https://v2.tauri.app/plugin/http-client/)
- [Tauri WebSocket plugin](https://v2.tauri.app/plugin/websocket/)
- [Tauri deep-link plugin](https://v2.tauri.app/plugin/deep-linking/)
- [Tauri notification plugin](https://v2.tauri.app/plugin/notification/)
- [Tauri filesystem plugin](https://v2.tauri.app/plugin/file-system/)
- [Tauri Stronghold plugin](https://v2.tauri.app/plugin/stronghold/)
- [Community Tauri mobile share-target reference](https://github.com/IT-ess/tauri-plugin-mobile-sharetarget)

### Apple

- [App Review Guidelines](https://developer.apple.com/app-store/review/guidelines/)
- [App privacy and data use](https://developer.apple.com/app-store/user-privacy-and-data-use/)
- [Local Network purpose string](https://developer.apple.com/documentation/BundleResources/Information-Property-List/NSLocalNetworkUsageDescription)
- [Bonjour service declarations](https://developer.apple.com/documentation/BundleResources/Information-Property-List/NSBonjourServices)
- [TN3179: Local Network privacy](https://developer.apple.com/documentation/technotes/tn3179-understanding-local-network-privacy)
- [App Transport Security](https://developer.apple.com/documentation/security/preventing-insecure-network-connections)
- [Allowing local networking under ATS](https://developer.apple.com/documentation/bundleresources/information-property-list/nsapptransportsecurity/nsallowslocalnetworking)
- [Keychain key storage](https://developer.apple.com/documentation/security/storing-keys-in-the-keychain)
- [CryptoKit keys and Keychain](https://developer.apple.com/documentation/cryptokit/storing-cryptokit-keys-in-the-keychain)
- [Secure Enclave key protection](https://developer.apple.com/documentation/security/protecting-keys-with-the-secure-enclave)
- [Share Extension programming guide](https://developer.apple.com/library/archive/documentation/General/Conceptual/ExtensibilityPG/Share.html)
- [Background execution modes](https://developer.apple.com/documentation/xcode/configuring-background-execution-modes)
- [Choosing background strategies](https://developer.apple.com/documentation/backgroundtasks/choosing-background-strategies-for-your-app)
- [Background push updates](https://developer.apple.com/documentation/usernotifications/pushing-background-updates-to-your-app)
- [Export compliance](https://developer.apple.com/help/app-store-connect/manage-app-information/overview-of-export-compliance)
- [SMAppService](https://developer.apple.com/documentation/servicemanagement/smappservice)
- [Packet-tunnel provider](https://developer.apple.com/documentation/networkextension/packet-tunnel-provider)
- [TN3120: Packet-tunnel use cases](https://developer.apple.com/documentation/technotes/tn3120-expected-use-cases-for-network-extension-packet-tunnel-providers)

### Android and Google Play

- [Google Play target API requirements](https://developer.android.com/google/play/requirements/target-sdk)
- [Wi-Fi and network connectivity](https://developer.android.com/develop/connectivity/wifi)
- [Network Service Discovery](https://developer.android.com/reference/android/net/nsd/NsdManager)
- [Local Network permission](https://developer.android.com/privacy-and-security/local-network-permission)
- [Foreground-service restrictions](https://developer.android.com/develop/background-work/services/fgs/restrictions-bg-start)
- [Foreground-service timeouts](https://developer.android.com/develop/background-work/services/fgs/timeout)
- [User-initiated data transfer](https://developer.android.com/develop/background-work/background-tasks/uidt)
- [Intents and intent filters](https://developer.android.com/guide/components/intents-filters)
- [Secure file sharing](https://developer.android.com/training/secure-file-sharing)
- [Android Keystore](https://developer.android.com/privacy-and-security/keystore)
- [Google Play Data Safety](https://support.google.com/googleplay/android-developer/answer/10787469?hl=en)
- [Google Play Device and Network Abuse policy](https://support.google.com/googleplay/android-developer/answer/16559646?hl=en)

### Cloudflare and networking

- [Cloudflare Quick Tunnels](https://developers.cloudflare.com/cloudflare-one/networks/connectors/cloudflare-tunnel/do-more-with-tunnels/trycloudflare/)
- [Cloudflare Tunnel API setup](https://developers.cloudflare.com/cloudflare-one/networks/connectors/cloudflare-tunnel/get-started/create-remote-tunnel-api/)
- [ICE — RFC 8445](https://www.rfc-editor.org/info/rfc8445/)
- [TURN — RFC 8656](https://www.rfc-editor.org/info/rfc8656/)
- [WebSocket — RFC 6455](https://www.rfc-editor.org/info/rfc6455/)
- [QUIC — RFC 9000](https://www.rfc-editor.org/rfc/rfc9000.html)
- [Noise Protocol Framework](https://noiseprotocol.org/noise.html)
- [X25519 — RFC 7748](https://www.rfc-editor.org/info/rfc7748/)
- [HKDF — RFC 5869](https://www.rfc-editor.org/info/rfc5869/)
- [Tailscale open-source architecture](https://tailscale.com/opensource)
