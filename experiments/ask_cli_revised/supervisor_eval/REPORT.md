# Ask 0.7 supervisor bakeoff — first tranche: **paused before any scored observation** (decision needed on the NVIDIA driver)

Date: 2026-09-23. The harness and frozen battery are complete and verified. An isolated Ollama is running on JUNO with two of the four candidates pulled. **No candidate has been run through Stage 0 or the battery, so no semantic, gate, or performance result exists.** The freeze (`FREEZE.txt`, committed as `3d12610d`) is intact and unchanged.

## 1. Bottom line

| | |
|---|---|
| Models tested | **none** (no Stage-0 or battery call has been made under the final runtime) |
| Why paused | Cliff ruled out running under **Vulkan** (a backend confound). The isolated Ollama v0.34.3 selects Vulkan because JUNO's NVIDIA driver is **535.309.01** and current Ollama's CUDA runners require **≥ 550**. Upgrading the driver cleanly needs a change that is broader than "a normal driver update", which was the agreed stop condition. |
| The blocker in one line | Every NVIDIA-repo driver ≥ 550 (R550/570/575/580, proprietary or open) conflicts with the Debian **CUDA 11.8 toolkit** installed on JUNO (`libnppc11` `Conflicts: nvidia-libopencl1`). The narrowest resolution removes **13 unrelated toolkit packages** (`nvidia-cuda-toolkit` = `nvcc`, `nvidia-cuda-dev` = headers, and 11 `libnpp*` NPP libraries). With those removed, the full R580 transaction resolves cleanly in simulation (53 installs, 25 removals). Debian bookworm/backports cannot supply ≥ 550 (backports has only 535.216.03). |
| Decision needed | §7 |

## 2. Candidate identities (intended) and pull status

From the Ollama library on 2026-09-23. Quantization/context/license are re-confirmed from `/api/show` at Stage 0.

| Candidate | Tag | Download | Ctx cap | Pull status (isolated store) |
|---|---|---|---|---|
| Qwen3.5-9B | `qwen3.5:9b` | 6.6 GB | 256K | complete |
| Gemma 3 12B | `gemma3:12b` | 8.1 GB | 128K | complete |
| Phi-4 14B | `phi4:14b` | 9.1 GB | 16K | interrupted at Cliff's request; ~9 GB of partial blobs kept for resume |
| gpt-oss 20B | `gpt-oss:20b` | 14 GB | 128K | not started |

Pulling stopped at Cliff's instruction before any observation, because the runtime (Vulkan) was not acceptable. Nothing was deleted; the registry ran at ~80 MB/s.

## 3. Runtime and hardware observations (measured 2026-09-23)

**Shared JUNO Ollama** (untouched throughout): v0.12.3, default store `/usr/share/ollama/.ollama/models` on the OS disk (7.6 GB free; 94% used), no `OLLAMA_MODELS`; models `callosum-managed-local`, `llava:7b`, `moondream`, `qwen3:8b`. Its store cannot hold the candidates and the directive is to use `/media/brain/JUNO` (460 GB free).

**Isolated bakeoff Ollama** (Cliff-approved; the shared service, models, tunnel and configuration are untouched):
- Upstream release v0.34.3 (2026-09-19), `ollama-linux-amd64.tar.zst`, sha256 `e83a089f…` verified against the published digest; binary sha256 `825106b5…`.
- Runs as user `brain`, PID 8629, `127.0.0.1:11435`; `OLLAMA_MODELS=/media/brain/JUNO/ollama-models/ask-070-bakeoff`, `OLLAMA_MAX_LOADED_MODELS=1`, `OLLAMA_NUM_PARALLEL=1`; install/HOME/TMP under `/media/brain/JUNO/ollama-bakeoff/`. Second SSH forward: Windows `127.0.0.1:11435` → JUNO `127.0.0.1:11435`.
- **GPU backend: Vulkan.** Server log: `NVIDIA driver too old … driver=535 required_driver="550 or newer"`; Ollama's own docs list driver ≥ 550 for CUDA and Vulkan as the fallback.

**Hardware:** RTX 3050 8 GB, 15.9 GB RAM, 18 GB swap, i7-8700. Debian 12.15 (bookworm), kernel 6.1.0-52-amd64, EFI with **Secure Boot disabled**. Driver 535.309.01 from **Debian packages** (`nvidia-driver 535.309.01-0+deb12u1`, DKMS `nvidia-current` built for kernels 6.1.0-50 and 6.1.0-52); a Sep 2025 NVIDIA `.run` installer attempt failed harmlessly (X was running). JUNO also runs Plex, Jellyfin, Docker (authentik), Tailscale, cloudflared and a lightdm/Xorg session; no compute process holds the GPU.

## 4. Driver-upgrade assessment (read-only; nothing on JUNO was changed)

- **Debian route:** bookworm main/security = 535.x; bookworm-backports = 535.216.03 only. There is no ≥ 550 in Debian for bookworm, and Trixie/Sid packages were not considered.
- **NVIDIA's official Debian 12 repo** (`developer.download.nvidia.com/compute/cuda/repos/debian12/x86_64`, index dated 2026-09-22) offers branches 550 … 615. R580 is the long-term-support production branch (newest 580.178.04-1); it supports Ampere and the 6.1 kernel and satisfies Ollama's ≥ 550 for both CUDA runners.
- **Simulated with isolated apt state** (own sources/lists/cache under `/media/brain/JUNO`; no change to `/etc/apt` or `/var/lib/apt`): every candidate set fails to resolve — `cuda-drivers-{550,570,575,580}` and `nvidia-open-{570,575,580}` — with `libnppc11 : Conflicts: nvidia-libopencl1`. NVIDIA's `nvidia-opencl-icd` (R570+) `Provides: nvidia-libopencl1`; Debian's 535 packaging does not, which is why the two coexist today.
- **The exact minimal resolution (simulated, isolated apt state):** removing only the 11 installed `libnpp*` libraries cascades to `nvidia-cuda-toolkit` (the `nvcc` compiler and tools) and `nvidia-cuda-dev` (headers/static libs) — **13 packages** of Debian's CUDA 11.8 *developer* toolkit. The CUDA 11.8 runtime libraries (`libcudart11.0`, `libcublas11`, `libcufft10`, …), Nsight and the profilers are not in the cascade. With those 13 out, `cuda-drivers-580` resolves cleanly: **53 installs/upgrades and 25 removals**. The 25 removals are those 13 plus 12 Debian nvidia-packaging packages that NVIDIA's packaging replaces (`nvidia-alternative`, `nvidia-driver-bin`, `nvidia-smi`, `nvidia-kernel-common`, `nvidia-support`, `nvidia-egl-common`, `nvidia-vulkan-common`, `libgl1-nvidia-glvnd-glx`, `nvidia-opencl-common`, `nvidia-suspend-common`, `nvidia-legacy-check`, `nvidia-installer-cleanup`). The installs are the R580 driver stack and its GL/Vulkan/encode libraries, `nvidia-settings`, `nvidia-persistenced`, and `dkms` (already present). No non-NVIDIA package is otherwise touched.
- **Why it still stops here:** removing `nvcc` and the CUDA headers is unrelated developer-tooling churn, beyond "a normal driver installation/update" and against "do not change unrelated packages". (NVIDIA's own repo also offers `cuda-toolkit-11-8`, which would restore `nvcc` under `/usr/local/cuda-11.8` if wanted, at a few GB of a `/` that has 7.6 GB free.)
- Disk headroom on `/` is 7.6 GB, enough for a driver install but tight.

## 5. The frozen supervisory battery (unchanged since the freeze commit)

19 calls per model built from real run9 data; every prompt shows the user's original request. Task A (15 calls): claim → obligation, claim-only — A1 attitudes → s1 (s2 allowed); A2 cross-cultural → s4; A7 EBQ → s3; **A3 dmPFC, A4 mentalizing, A5 years-of-school → no obligation**; A6 diagnostic; A1/A2/A3/A7 in 3 orderings. Task B (2): coverage audit — p3 supports s1; p5/p6 support nothing; s4/s6 stay unresolved. Task C (2): bounded recovery under a stated policy. Gates G1–G8, no weighted score (`README.md`). Pre-freeze judgment calls (original request in prompts; A7 added; Task C s4 a disclosed reconstruction; prompts name the JSON fields) are listed in the freeze commit and `README.md`. The runtime change does not alter any of it.

## 6. Per-candidate results, gates, performance

Not evaluated. No model has been run under the final runtime.

## 7. Decision needed from Cliff

Cliff's instruction was to upgrade the NVIDIA driver and stop if the safe route is materially broader than a normal driver update. It is. Options:

1. **Approve the 13-package removal (`nvidia-cuda-toolkit`, `nvidia-cuda-dev`, 11 `libnpp*`) and install NVIDIA R580** (`cuda-drivers-580` from NVIDIA's Debian 12 repo: proprietary DKMS modules, the same flavor as today; simulated 53 installs / 25 removals), then reboot. Impact: `nvcc` 11.8 and the CUDA headers disappear from the system (pip wheels such as torch bundle their own CUDA runtime and are unaffected; anything compiling CUDA against the system toolkit needs NVIDIA's `cuda-toolkit-11-8` afterwards). Rollback: remove the NVIDIA-repo driver and reinstall Debian's 535 set (its DKMS builds exist for both kernels). The reboot briefly interrupts Plex, Jellyfin, authentik, Tailscale and cloudflared, all of which came back by themselves after JUNO's last boot. After reboot I would verify CUDA is selected in the isolated Ollama's log before resuming any pulls.
2. **Keep the driver; use the newest Ollama release that still runs CUDA on driver 535** (and supports the four models — `qwen3.5` needs roughly ≥ v0.17). No host change, but it is not "current Ollama" and needs a short compatibility probe before pulling more.
3. Run under Vulkan — declined by Cliff.
4. NVIDIA's `.run` installer — not recommended: it bypasses dpkg and collides with the Debian-packaged driver.

## 8. When unblocked

```powershell
python -m experiments.ask_cli_revised.supervisor_eval.build_battery verify   # must print "freeze intact"
python -m experiments.ask_cli_revised.supervisor_eval.run_eval setup-isolated  # if the isolated server needs (re)starting
python -m experiments.ask_cli_revised.supervisor_eval.run_eval preflight       # confirm the log says library=CUDA, not Vulkan
python -m experiments.ask_cli_revised.supervisor_eval.run_eval stage0  qwen3.5-9b   # repeat per candidate
python -m experiments.ask_cli_revised.supervisor_eval.run_eval battery qwen3.5-9b
python -m experiments.ask_cli_revised.supervisor_eval.run_eval report
```

Every Stage-0 receipt records the Ollama version, binary sha256, server environment, model-store path, GPU backend, and driver version. Remaining pulls (`phi4:14b` resumes, `gpt-oss:20b`) are ~23 GB.

## 9. Verification of the harness

- 241 offline tests pass; ruff clean. Five deliberate scorer mutations were each caught by the tests. The battery's constants are re-verified byte-for-byte against the real run9 files; no source quote appears in any public file.
- Live paths exercised without a model: both tunnels, `/api/version|tags|ps` on both servers, host snapshots, store assessment, isolated install with checksum verification, streaming pulls with coarse progress logging.
- Bugs found live and fixed: `juno.ps1` is unsigned and cannot run under Windows PowerShell 5.1 (the helper now uses `pwsh`); the model-calling path is covered by fake-client tests but has not been run live.
- Frozen files (`cases`, `prompts`, `schemas`, `scoring`, `models`, `ollama_client`, `freeze`, manifest, `FREEZE.txt`) are byte-identical to the freeze commit.

## 10. Repository state

The freeze commit `3d12610d` was made with `--no-verify` as authorized (repository-wide pre-commit is blocked by an unrelated pre-existing 615-line `20_synthesis.jsx` and a stash `WinError 5`; all applicable checks passed directly on the package). Everything since — `isolated_ollama.py`, `run_eval`/`stage0` updates, tests, this report — is uncommitted.
