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
Get-ChildItem $RuntimeDir -Recurse -Directory -Filter "third_party" -ErrorAction SilentlyContinue |
    Where-Object { $_.FullName -match '\\dist-info\\licenses\\third_party$' } |
    ForEach-Object {
        Write-Host "Pruning deeply-nested vendored license tree: $($_.FullName)"
        Remove-Item -Recurse -Force $_.FullName
    }

Write-Host "Smoke-testing the bundle..."
python (Join-Path $PSScriptRoot "smoke_test_backend.py") --python $PythonExe --source (Join-Path $ProjectRoot "app/desktop-shell/resources/callosum-src")

Write-Host "Done: $RuntimeDir"
