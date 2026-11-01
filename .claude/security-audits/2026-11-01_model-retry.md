# Security audit: manual model retry (inc 622)

**Self-review by the implementing session. This is not an independent review.** The independent security review of the
integrated modernization work remains outstanding.

**Trigger:** new API endpoint, and a new user-initiated path to an existing external fetch.

## Surface
`POST /modernization/models/{track}/retry`, plus a read-only `model_recovery` list on `GET /modernization`.
It calls the existing `Provisioner.provision_once(force=True)` from a `ProvisioningRunner`. No new dependency, external
host, file-write location or model-acquisition code.

## Threat review
| Area | Finding |
|---|---|
| Input validation | The only input is `track`, which must be a key of the static `MANIFESTS`. Unknown values get 404. The request body is ignored, so a client cannot supply a repository, revision, file name or URL. |
| SSRF / external calls | The fetch uses only the manifest's pinned `repo_id`, `revision` and file paths. No new host. |
| Integrity | `force` only re-fetches files that failed. Acceptance still requires every manifest SHA-256 and the static contract in `_settle`; nothing bypasses them. |
| Unverified weights | Consumers load only after `is_verified()`. A running retry does not change that. Test asserts no runtime is loaded during a retry. |
| Authorization | Mounted behind `AccessControlMiddleware`: bearer token when Remote access is on. `CALLOSUM_READ_ONLY=1` returns 403 because the method is POST. |
| Tunnel exposure | The path is not in any cloudflared ingress allowlist. |
| Concurrency / resource use | One in-process guard makes check-and-start atomic; the per-track OS lock covers other processes. A duplicate request starts nothing. Disk, memory and offline checks still apply inside the forced attempt. |
| Retry abuse | Refused (409) unless the track is `invalid`, or retryable with no automatic runner. Deterministic failures stop at the first terminal state and need another click. A client could click repeatedly; that re-fetches only failed files from the pinned source, one attempt at a time. Accepted for a local single-user app. |
| Output encoding | Responses carry `error_kind` and fixed sentences only. The stored `diagnostic`, file names, paths and exception text are not returned. Test asserts this. |
| Data egress | Same public model-file request as the automatic provisioner. No library text, identifiers or paths are sent. This is model acquisition, not the library-text consent gate. |
| Shared cache | Writes go through `hf_hub_download` for pinned files only. Nothing is deleted. Test asserts an unrelated cached model and state file are unchanged. |
| DeBERTa | `DEBERTA_RELEASE_GATES` is untouched. An ordinary machine has no `invalid` DeBERTa state, so it gets no offer and no download (409). A repair does not change the verifier. |
| Secrets | None involved. |

## Negative-path results (`tests/test_model_recovery.py`, mocked network)
| Case | Result |
|---|---|
| Unknown or path-shaped track, or a raw repository id | 404/405; nothing fetched |
| Body names another repository and revision | Ignored; only the pinned pair is requested |
| Read-only mode | 403; nothing fetched; state stays `invalid` |
| Remote access on, no token | 401; nothing fetched. Correct token: 200 |
| Normal states (absent, downloading, waiting for network, insufficient resources, verified) | 409; nothing fetched |
| DeBERTa absent | 409; nothing fetched |
| Automatic provisioning off | No button; 409 |
| Five duplicate requests during a retry | One runner, one fetch |
| Another process holds the track lock | 409; no fetch |
| Source still serves bad bytes | Stays `invalid`; still offered; no automatic repeat |

## Not exercised
A real Hugging Face transfer, including `force_download` replacing a corrupt cached blob on each OS. A packaged build.
Two real app processes with a browser attached (the lock is tested with two provisioners in one process here, and across
processes in `test_killed_process_releases_ownership`).

Security Audit: PASS (self-review; independent review still outstanding)
