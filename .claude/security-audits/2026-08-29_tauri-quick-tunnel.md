# Security audit — packaged Quick Tunnel lifecycle (increment 533)

Status: **PASS — fail-closed design and isolated live Windows acceptance complete; editor-host QA remains manual**

## Scope

An explicit packaged Settings action starts/stops an installed Cloudflare `cloudflared` Quick Tunnel for Google
Docs and Word on the web. Tauri owns cloudflared and a separate tunnel-only Uvicorn origin. Existing Remote-access
bearer authentication remains the data boundary; no provider/model request, schema, or editor document behavior
changes.

## Boundaries to prove

- No connector starts until the persisted Remote-access opt-in is true.
- cloudflared never targets the ordinary local-trust backend.
- The dedicated origin requires the existing bearer while ON and denies all non-health traffic while OFF.
- A Quick Tunnel has no cite-only ingress; Settings must disclose that the bearer is the sole boundary.
- No token, existing named-tunnel credentials, scholarly request, private path, or URL header enters logs/status.
- Only strict `https://<safe-label>.trycloudflare.com` output becomes user-visible.
- Tauri owns and cleans both process trees on explicit stop, observed crash, and app exit.
- Existing source Quick Tunnel and named-tunnel workflows remain unchanged.

## Findings / disposition

| Finding | Severity | Disposition |
|---|---:|---|
| Pointing cloudflared at the main backend would fail open if Remote access turned off while the connector lived, because forwarded requests appear loopback. | Critical | Avoided. A separate child marked `CALLOSUM_TUNNEL_TARGET=1` returns 403 for every non-health request while the setting is off; middleware tests pin OFF/ON/recovery-hatch combinations. |
| Quick Tunnels cannot enforce the named tunnel's cite-only ingress allowlist. | High | Accepted only as explicit, non-default convenience. UI states every route is exposed and the bearer is the sole boundary. Stable named-tunnel instructions remain the hardened option. |
| Existing `~/.cloudflared` config could inject named credentials and expose their path in logs. | High | Fixed. Tauri passes an app-owned non-secret config; live acceptance asserts no `credentials-file` or `.cloudflared` reference appears in connector logs. |
| Debug cloudflared logging can include request URLs and headers. | High | Fixed at direct-argv `--loglevel info`; Uvicorn access logging is disabled on the dedicated target. No prompt, response, token, or scholarly content is logged by this lifecycle. |
| A malicious/incorrect process could print an arbitrary URL. | High | Fixed with a narrow parser: HTTPS only, exact `.trycloudflare.com` suffix, non-empty lowercase/digit/hyphen label, no path/query/port. Unknown output fails closed. |
| Connector or target can crash independently or survive app shutdown. | High | Tauri holds both handles. Status observation tears down the pair if either dies; explicit stop and RunEvent exit stop connector then target. Windows Job Objects and Unix process groups preserve tree cleanup. Live Windows acceptance left no new process. |
| Remote opt-out through a path other than the Settings toggle could leave cloudflared running. | Medium | The connector may remain until status/exit, but the dedicated origin immediately changes to 403-closed. Normal Settings opt-out additionally stops both first. Residual public URL then exposes no data. |
| PATH could resolve a user-controlled executable. | Medium | Known package-manager locations are preferred before PATH. PATH remains a documented external-tool fallback; a same-user attacker able to replace executable search paths already has equivalent code execution. No shell participates. |
| Cloudflare may issue a URL before its public edge is reachable. | Low/product | Disclosed. Cloudflare documents no uptime guarantee for Quick Tunnels. Callosum reports URL issuance/live process, not guaranteed public availability; a failed edge does not weaken local auth or expose data. |

## Live evidence

On Windows with `cloudflared 2026.5.2`, isolated synthetic state and an empty temporary database:

- dedicated origin health returned 200;
- unauthenticated settings returned 401 while enabled;
- the same request returned 403 immediately after changing the isolated setting to OFF;
- cloudflared produced a strict throwaway URL using the isolated config;
- its info log contained no inherited named-tunnel credential field/path;
- stop left no newly-created Python or cloudflared process.

One exploratory public-edge run returned public health 200 and public settings 401. A later issued/registered URL
did not propagate within 90 seconds, consistent with Cloudflare's documented no-guarantee posture. Public edge
availability is therefore external operational evidence, not a Callosum auth/readiness primitive.

## Residual/manual boundary

The actual Google Docs and Word-web add-in host flows still require the maintainer's consolidated manual check.
The live acceptance proves process/auth/config/cleanup semantics with synthetic data; it does not claim Cloudflare
availability, editor-host behavior, or multi-tenant hardening.
