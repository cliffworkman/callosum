#!/usr/bin/env bash
# Builds app/desktop-shell/resources/python-runtime/ for Linux (x86_64) — a portable CPython 3.11 +
# this project's real dependencies. Runs ONLY in CI (.github/workflows/desktop-shell-linux.yml) on an
# ubuntu-latest runner. See build_python_macos.sh for the matching macOS build; the shape is
# identical, only the release asset and interpreter layout differ.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
RESOURCES_DIR="$SCRIPT_DIR/../resources"
RUNTIME_DIR="$RESOURCES_DIR/python-runtime"
ASSET="cpython-3.11.15+20260718-x86_64-unknown-linux-gnu-install_only.tar.gz"
EXPECTED_SHA256="c2082e977138e307e3da4ea2c65421d3cb6b80f4890890b28b96fc6b422d4f0d"
URL="https://github.com/astral-sh/python-build-standalone/releases/download/20260718/${ASSET// /%20}"

rm -rf "$RUNTIME_DIR"
mkdir -p "$RESOURCES_DIR"

echo "Downloading portable CPython (linux x86_64)..."
curl -L -o "$RESOURCES_DIR/python-runtime.tar.gz" "$URL"
echo "${EXPECTED_SHA256}  $RESOURCES_DIR/python-runtime.tar.gz" | sha256sum -c -

echo "Extracting..."
tar -xzf "$RESOURCES_DIR/python-runtime.tar.gz" -C "$RESOURCES_DIR"
mv "$RESOURCES_DIR/python" "$RUNTIME_DIR"
rm "$RESOURCES_DIR/python-runtime.tar.gz"

PYTHON_BIN="$RUNTIME_DIR/bin/python3"
RESOLVED_REQUIREMENTS="$RESOURCES_DIR/python-runtime-requirements.lock"

echo "Exporting the exact runtime dependency set from uv.lock..."
uv export --frozen --no-dev --extra keyring --no-emit-project --no-hashes \
  --format requirements-txt --output-file "$RESOLVED_REQUIREMENTS"
# uv.lock also represents the default PyPI torch branch, whose Linux dependency closure includes
# CUDA/triton packages. This runtime deliberately installs the exact CPU wheel first; remove only
# that alternate accelerator branch from the otherwise exact export before the --no-deps install.
sed -i -E '/^(cuda-|nvidia-|triton==)/d' "$RESOLVED_REQUIREMENTS"

echo "Installing real project dependencies (torch is large)..."
# See build_python_windows.ps1's matching comment: callosum never uses GPU acceleration, so the
# CPU-only torch build goes in first. On Linux this isn't just size — the default CUDA build declares
# a hard dynamic-link dependency on the NVIDIA driver's libcuda.so.1, which doesn't exist at all on
# this GPU-less runner; linuxdeploy insists on resolving every dependency before bundling and hard-
# fails on it (a real run confirmed this: "ERROR: Could not find dependency: libcuda.so.1").
"$PYTHON_BIN" -m pip install --no-cache-dir "torch==2.13.0" --index-url https://download.pytorch.org/whl/cpu
# The frozen export contains every direct/transitive dependency. --no-deps preserves the selected
# CPU-only torch wheel rather than letting pip resolve a second platform-specific graph.
"$PYTHON_BIN" -m pip install --no-cache-dir --no-deps -r "$RESOLVED_REQUIREMENTS"
rm "$RESOLVED_REQUIREMENTS"

# See build_python_windows.ps1's matching comment: torch vendors ~100 deeply-nested license copies
# for its internal C++ profiler's (kineto) own vendored build/test tools — pure attribution text,
# no functional code. Pruned here too for consistency with the Windows/macOS builds.
find "$RUNTIME_DIR" -type d -path "*/dist-info/licenses/third_party" -print -exec rm -rf {} + 2>/dev/null || true

# torch/bin/ ships internal C++ test-suite executables (test_api, TCPStoreTest, test_lazy, ...), but it
# ALSO contains torch_shm_manager, which `import torch` requires. Linux-only linuxdeploy insists on
# resolving every test binary's dependency closure; a real run found one test binary's broken/relative
# rpath. Delete only named test shapes and prove the runtime helper remains — never prune the directory.
TORCH_BIN=$(find "$RUNTIME_DIR/lib/python3.11/site-packages/torch" -maxdepth 1 -type d -name "bin" || true)
if [ -n "$TORCH_BIN" ]; then
  echo "Pruning torch's internal C++ test binaries while preserving runtime helpers: $TORCH_BIN"
  find "$TORCH_BIN" -maxdepth 1 -type f \( -name 'test_*' -o -name '*Test' \) -print -delete
  test -x "$TORCH_BIN/torch_shm_manager"
fi

echo "Smoke-testing the bundle (required, blocking)..."
python3 "$SCRIPT_DIR/smoke_test_backend.py" \
  --python "$PYTHON_BIN" \
  --source "$SCRIPT_DIR/../resources/callosum-src"

echo "Done: $RUNTIME_DIR"
