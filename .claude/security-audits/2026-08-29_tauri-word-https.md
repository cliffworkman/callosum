# Security audit — packaged Word HTTPS companion (increment 532)

Status: **PASS — code/static/isolated-live validation complete; OS trust UI + Word host remain manual**

## Scope

Packaged desktop support for the existing Microsoft Word add-in: explicit per-user certificate trust, a
Tauri-owned fixed-port HTTPS Uvicorn companion, and Settings lifecycle controls. No provider, model, tunnel,
or non-loopback network behavior is added.

## Boundaries to prove

- Certificate identity is limited to `localhost` and literal `127.0.0.1`; it is an end-entity certificate,
  not a CA capable of signing arbitrary hosts.
- The private key is generated locally, never returned by an API, and receives owner-only permissions/ACLs.
- Trust installation targets only the current user's trust store and occurs only after an explicit Enable.
- Disable removes trust before deleting local certificate material; failure is reported and does not pretend
  cleanup succeeded.
- The companion binds only `127.0.0.1:8443`, uses direct argv, and is supervised/terminated by Tauri with the
  same process-tree guarantees as the main backend.
- The companion alone receives `CALLOSUM_DISABLE_REMOTE_ACCESS=1`; the tunnel-facing/main process does not.
- No new egress path, scholarly-content logging, credential exposure, or provider behavior is introduced.
- Web/demo/non-Tauri surfaces do not claim the managed companion exists.

## External contracts checked

- Microsoft Office add-in guidance requires/recommends HTTPS and permits a locally trusted self-signed
  certificate for local testing.
- Microsoft documents `Import-Certificate` into `Cert:\CurrentUser\Root`; `certutil` is explicitly cautioned
  against for production code and is therefore not used.
- macOS `security` supports per-user `add-trusted-cert` / `remove-trusted-cert`; live macOS behavior remains
  unverified until hardware QA.

## Findings / disposition

| Finding | Severity | Disposition |
|---|---:|---|
| Cross-origin simple forms could otherwise invoke loopback trust mutation. | High | Fixed before ship: mutations require literal loopback, no forwarding headers, and non-safelisted `X-Callosum-Local-Action: settings-ui-v1`. A cross-origin form cannot set it and preflight receives no permissive CORS response. This is a local-action proof, not a secret. |
| Trusting a localhost CA would let key compromise sign other certificates. | High | Avoided: the generated certificate is an end entity (`BasicConstraints.ca=false`, `keyCertSign=false`) with only `localhost` and `127.0.0.1` SANs and server-auth use. |
| Another local process can call a predictable fixed port. | Medium | Accepted residual local-process boundary: TLS identity prevents network impersonation, API access control remains authoritative, mutations have the Settings header, and the server binds only literal loopback. Localhost is not represented as a perfect boundary. |
| Private-key files could inherit broad Windows ACLs. | High | Fixed: atomic owner-readable/writeable creation plus a fixed-script DACL replacement granting only the current user, with a verified protected/one-rule postcondition. Paths are passed in a child-only environment value and never interpolated into PowerShell. The helper pins the inbox Windows PowerShell module root so a PowerShell 7 parent cannot break ACL/PKI module loading. Unix mode is `0600`. |
| Launch-time auto-start and a Settings action could race into two children. | Medium | Fixed: one atomic startup owner performs readiness; concurrent callers wait for that result. Tauri remains the only process owner. |
| A partial disable could claim success while trust remains. | High | Fixed: trust is removed and rechecked before files and opt-in state are removed. Failure preserves enabled/retry state and certificate material. |
| The HTTPS child could inherit tunnel-facing Remote-access state. | High | Fixed: only that child receives `CALLOSUM_DISABLE_REMOTE_ACCESS=1`; it is strict-loopback and has no cloud/tunnel fallback. |
| macOS trust could target an admin/system domain. | High | Fixed statically: `security add-trusted-cert` targets the login keychain and omits `-d`; removal uses its per-user counterpart. Live macOS behavior remains release QA. |

## Validation boundary

Automated tests cover certificate constraints/reuse, Windows command/ACL construction, macOS command scope,
trust publication/removal ordering, API response privacy, loopback/forwarded-header/action-header denial, Tauri
fixed argv/config gating, and frontend assembly. A local HTTPS smoke uses the generated leaf without installing
it into the OS store and verifies the endpoint with that exact leaf. No provider call or external request is
part of the lifecycle. Actual Windows trust-store mutation, macOS trust behavior, and the Office.js host are
deferred to the consolidated manual verification pass and are not represented as live-verified.
