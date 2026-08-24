# Security audit — developer managed local AI sidecar POC

Date: 2026-08-24
Scope: Tauri-owned developer-supplied llama-server and Python Overview-only descriptor resolution

## Boundary and threat review

- **Activation:** exact `CALLOSUM_LOCAL_AI_ENABLED=1` plus valid runtime/GGUF paths. There is no Settings or frontend
  control, no bundled binary/model, and every descriptor must state `DEVELOPER_TEST_ONLY`.
- **Process injection:** runtime/model values are canonicalized existing files; the model must end in `.gguf`.
  `std::process::Command` receives separate argv entries. No shell, arbitrary flag string, or frontend input exists.
  Optional threads and GPU layers are parsed bounded integers.
- **Network exposure / SSRF:** Tauri hard-codes `127.0.0.1`; Python accepts only literal HTTP `127.0.0.1` with an
  explicit port and no credentials, path, query, or fragment. `localhost`, `::1`, `0.0.0.0`, HTTPS, LAN names, and
  redirects encoded into the descriptor are rejected. Tauri readiness and Python's managed HTTP pool both disable
  environment-proxy inheritance.
- **Authentication:** each launch uses 256 bits from the OS cryptographic RNG. The token is written to a private
  file, never argv or descriptor. Unix uses 0700/0600; Windows removes inherited ACLs and grants full access only
  to the current user SID. Inference requires bearer auth; health/model discovery may remain public on loopback.
- **Secret handling:** the descriptor contains a credential reference, never the token. `LLMConfig.api_key` is
  excluded from repr. Errors/logs expose only bounded categories; neither token nor raw runtime/model path is
  emitted by managed lifecycle logging. Tauri also removes the raw developer runtime/model configuration from the
  Python child environment; Python receives only the readiness-gated descriptor path.
- **Content logging:** llama-server starts with `--log-disable`, stdout/stderr are discarded, the web UI is disabled,
  and the runtime is offline. Tauri persists no runtime log. Python usage logging retains existing numeric behavior.
- **Model-path disclosure:** `/v1/models` must advertise the expected `callosum-managed-local` alias; readiness fails
  otherwise. The private `/props` response is consumed only to hash the chat template and is never exposed to
  Python/frontend.
- **Readiness / confused endpoint:** `/health` alone is insufficient. Eligibility additionally requires the expected
  alias, authenticated `/props`, and an authenticated one-token Chat Completions response with the expected shape.
- **Egress / fallback:** while the developer gate is active, invalid/unavailable local state returns no Overview
  generator before normal provider settings are resolved. A local error becomes the existing supplementary
  Overview failure; it cannot invoke cloud or roll back the verified primary synthesis.
- **Lifecycle:** Tauri is the sole supervisor. Windows uses a kill-on-close Job Object; Unix uses a process group.
  Descriptor/token eligibility is removed before bounded graceful shutdown, then forced tree cleanup. A crash
  monitor removes both files after unexpected child exit.
- **Resource bounds:** fixed context 4096, output cap 256, temperature 0, seed 42, bounded readiness/shutdown waits,
  and bounded thread/GPU-layer inputs. No download, retry storm, auto-restart, or startup provider traffic exists.
- **Supply chain:** no runtime/model enters the repository or installer. The POC records runtime version, executable
  SHA-256, model SHA-256, chat-template SHA-256, backend setting, and generation settings. `getrandom` and `sha2`
  are new direct Rust declarations but were already pinned transitively in Cargo.lock.

## Negative-path and live checks

- Missing descriptor/runtime/model, non-GGUF model, malformed/oversized descriptor, misplaced credential, symlink,
  wrong qualification, and non-strict-loopback endpoints fail closed.
- Missing and wrong bearer tokens receive HTTP 401; the authenticated request succeeds.
- Malformed Chat Completions output marks Overview failed while the verified primary remains done and readable.
- Unexpected child death invalidates descriptor/token; bounded normal and direct forced cleanup terminate the child.
- A short readiness deadline leaves no descriptor/token and terminates the unready process.
- The Windows live POC used official llama.cpp b10516 (`b95502ba9`), CPU-only, with a public 0.5B GGUF instrument.
  The existing Python Overview generator/parser completed through the Tauri descriptor. `/v1/models` exposed only
  the alias, managed runtime logging produced no files, and shutdown left no llama-server process.

## Accepted boundaries

- Direct lifecycle validation is Windows-only in this phase. Unix process-group code compiles but has not been run
  on macOS/Linux hardware.
- The developer model is unqualified. A single valid POC response is transport/lifecycle evidence only.
- The ephemeral-port allocation retains a small bind TOCTOU window; authenticated readiness prevents a different
  process from becoming eligible, so the consequence is a fail-closed startup rather than content disclosure.
- A malicious process running as the same OS user can read same-user resources or invoke loopback; this POC does not
  claim localhost is a sandbox. Per-launch auth protects against accidental/unauthenticated invocation and other
  local users under normal OS ACL enforcement.

## Result

**Security Audit: PASS**
