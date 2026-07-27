# Builds app/desktop-shell/resources/python-runtime/ — a portable CPython 3.11 + this project's
# real dependencies, for the Tauri shell to spawn directly (no PyInstaller/Nuitka freezing).
#
# Usage (from the project root): pwsh app/desktop-shell/packaging/build_python_windows.ps1
#
# NOTE: `uv pip install` hit a reproducible TLS/SNI mismatch against files.pythonhosted.org's
# Fastly CDN in the dev sandbox this was built in (schannel: SEC_E_WRONG_PRINCIPAL) while plain
# `pip` worked fine against the same URL — this script uses pip deliberately, not uv, for that
# reason. Worth re-testing with uv on a real machine; it may be sandbox-specific.

$ErrorActionPreference = "Stop"

$ProjectRoot = Resolve-Path "$PSScriptRoot/../../.."
$ResourcesDir = Join-Path $PSScriptRoot "../resources"
$RuntimeDir = Join-Path $ResourcesDir "python-runtime"
$PythonVersion = "3.11.15+20260718"
$Asset = "cpython-3.11.15%2B20260718-x86_64-pc-windows-msvc-install_only.tar.gz"
$Url = "https://github.com/astral-sh/python-build-standalone/releases/download/20260718/$Asset"

if (Test-Path $RuntimeDir) {
    Write-Host "Removing existing $RuntimeDir"
    Remove-Item -Recurse -Force $RuntimeDir
}
New-Item -ItemType Directory -Force -Path $ResourcesDir | Out-Null

$Archive = Join-Path $ResourcesDir "python-runtime.tar.gz"
Write-Host "Downloading portable CPython $PythonVersion (win_amd64)..."
Invoke-WebRequest -Uri $Url -OutFile $Archive

Write-Host "Extracting..."
tar -xzf $Archive -C $ResourcesDir
Move-Item (Join-Path $ResourcesDir "python") $RuntimeDir
Remove-Item $Archive

$PythonExe = Join-Path $RuntimeDir "python.exe"
$Requirements = Join-Path $ProjectRoot "requirements.txt"

Write-Host "Installing real project dependencies (this takes a while — torch is large)..."
# callosum never uses GPU acceleration anywhere (the embedding models are small enough to run fine
# on CPU, and this is a desktop app for an arbitrary user's machine, not a GPU workstation) — install
# the CPU-only torch build FIRST so the resolver treats it as already satisfying sentence-
# transformers' bare `torch>=1.11.0` and never reaches for the CUDA default. This isn't just smaller
# (~120MB vs 700MB+): the default build also declares a hard dynamic-link dependency on the NVIDIA
# driver's libcuda.so.1, which doesn't exist at all on a GPU-less machine — harmless on Windows
# (nothing resolves it ahead of time) but it hard-fails Linux's linuxdeploy bundling step, which
# insists on resolving every dependency before it'll even try to run. One index picked for all three
# platform build scripts, not patched in only where it happened to break.
& $PythonExe -m pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu
& $PythonExe -m pip install --no-cache-dir -r $Requirements
& $PythonExe -m pip install --no-cache-dir keyring  # hard dependency in the packaged build — see CLAUDE.md rule #2 / BYOK

# torch vendors license copies for its internal C++ profiler's (kineto) OWN vendored build/test
# tools — kineto -> libkineto -> dynolog -> {DCGM's Python test fixtures, prometheus-cpp -> civetweb
# -> duktape/googletest/cJSON, ...}. None of it is functional runtime code; it's pure legal
# attribution text, but the nesting is deep enough (250+ char relative paths) that makensis's file-
# inclusion step hit a Windows path-length limit and aborted the whole build on a real run. Pruning
# this subtree specifically (torch's own top-level LICENSE in dist-info is untouched) is the fix —
# flagged here rather than done silently, since it IS a real (if narrow) licensing-completeness
# tradeoff, not just cleanup.
# Target the known shape directly (site-packages/torch-*.dist-info/licenses/third_party) with a
# SHALLOW, single-level listing rather than Get-ChildItem -Recurse over the whole runtime tree — a
# real run showed the recursive scan silently missing this on Windows (almost certainly the same
# class of path-length issue this prune exists to fix in the first place: enumerating 250+ char paths
# is exactly where a deep recursive walk is most likely to trip). This only ever needs to look one
# level into site-packages, so there's no need to walk deep at all.
$SitePackages = Join-Path $RuntimeDir "Lib\site-packages"
Get-ChildItem $SitePackages -Directory -Filter "torch-*.dist-info" | ForEach-Object {
    $ThirdParty = Join-Path $_.FullName "licenses\third_party"
    if (Test-Path $ThirdParty) {
        Write-Host "Pruning deeply-nested vendored license tree: $ThirdParty"
        # The \\?\ extended-length-path prefix is the actual documented Windows mechanism for
        # bypassing MAX_PATH, regardless of tool — use it explicitly rather than hoping a plain
        # Remove-Item silently succeeds on paths this deep (a real run showed it doesn't).
        Remove-Item -LiteralPath "\\?\$ThirdParty" -Recurse -Force
        if (Test-Path $ThirdParty) {
            throw "failed to prune $ThirdParty — the NSIS build will hit the same path-length abort"
        }
    }
}

Write-Host "Smoke-testing the bundle..."
python (Join-Path $PSScriptRoot "smoke_test_backend.py") --python $PythonExe --source (Join-Path $ProjectRoot "app/desktop-shell/resources/callosum-src")

Write-Host "Done: $RuntimeDir"
