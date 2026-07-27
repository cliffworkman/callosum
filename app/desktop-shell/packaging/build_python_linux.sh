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
URL="https://github.com/astral-sh/python-build-standalone/releases/download/20260718/${ASSET// /%20}"

rm -rf "$RUNTIME_DIR"
mkdir -p "$RESOURCES_DIR"

echo "Downloading portable CPython (linux x86_64)..."
curl -L -o "$RESOURCES_DIR/python-runtime.tar.gz" "$URL"

echo "Extracting..."
tar -xzf "$RESOURCES_DIR/python-runtime.tar.gz" -C "$RESOURCES_DIR"
mv "$RESOURCES_DIR/python" "$RUNTIME_DIR"
rm "$RESOURCES_DIR/python-runtime.tar.gz"

PYTHON_BIN="$RUNTIME_DIR/bin/python3"

echo "Installing real project dependencies (torch is large)..."
# See build_python_windows.ps1's matching comment: callosum never uses GPU acceleration, so the
# CPU-only torch build goes in first. On Linux this isn't just size — the default CUDA build declares
# a hard dynamic-link dependency on the NVIDIA driver's libcuda.so.1, which doesn't exist at all on
# this GPU-less runner; linuxdeploy insists on resolving every dependency before bundling and hard-
# fails on it (a real run confirmed this: "ERROR: Could not find dependency: libcuda.so.1").
"$PYTHON_BIN" -m pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu
"$PYTHON_BIN" -m pip install --no-cache-dir -r "$PROJECT_ROOT/requirements.txt"
"$PYTHON_BIN" -m pip install --no-cache-dir keyring  # hard dependency in the packaged build

# See build_python_windows.ps1's matching comment: torch vendors ~100 deeply-nested license copies
# for its internal C++ profiler's (kineto) own vendored build/test tools — pure attribution text,
# no functional code. Pruned here too for consistency with the Windows/macOS builds.
find "$RUNTIME_DIR" -type d -path "*/dist-info/licenses/third_party" -print -exec rm -rf {} + 2>/dev/null || true

# torch/bin/ ships its own internal C++ test-suite executables (test_api, TCPStoreTest, test_lazy,
# ...) — never invoked by `import torch`, and Linux-only linuxdeploy insists on resolving every
# binary's full dynamic-link dependency closure before it'll bundle anything. A real run confirmed
# one of these test binaries has a broken/relative rpath linuxdeploy can't follow ("ERROR: Could not
# find dependency: libtorch.so"). Pruned on Linux only — Windows/macOS bundling never walks the
# dependency graph this way, so it's not a problem there and there's no reason to touch a working build.
TORCH_BIN=$(find "$RUNTIME_DIR/lib/python3.11/site-packages/torch" -maxdepth 1 -type d -name "bin" || true)
if [ -n "$TORCH_BIN" ]; then
  echo "Pruning torch's internal C++ test binaries: $TORCH_BIN"
  rm -rf "$TORCH_BIN"
fi

echo "Smoke-testing the bundle (required, blocking)..."
python3 "$SCRIPT_DIR/smoke_test_backend.py" \
  --python "$PYTHON_BIN" \
  --source "$SCRIPT_DIR/../resources/callosum-src"

echo "Done: $RUNTIME_DIR"
