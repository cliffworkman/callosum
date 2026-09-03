#!/usr/bin/env bash
# Builds app/desktop-shell/resources/python-runtime/ for macOS — a native portable CPython 3.11
# plus this project's real dependencies. Runs only on the native arm64/x86_64 CI jobs; never build
# one architecture under translation and label it as the other.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
RESOURCES_DIR="$SCRIPT_DIR/../resources"
RUNTIME_DIR="$RESOURCES_DIR/python-runtime"
case "$(uname -m)" in
  arm64|aarch64)
    PYTHON_ARCH="aarch64"
    DISPLAY_ARCH="arm64"
    ;;
  x86_64)
    PYTHON_ARCH="x86_64"
    DISPLAY_ARCH="x86_64"
    ;;
  *)
    echo "Unsupported macOS architecture: $(uname -m)" >&2
    exit 1
    ;;
esac
ASSET="cpython-3.11.15+20260718-${PYTHON_ARCH}-apple-darwin-install_only.tar.gz"
URL="https://github.com/astral-sh/python-build-standalone/releases/download/20260718/${ASSET// /%20}"

rm -rf "$RUNTIME_DIR"
mkdir -p "$RESOURCES_DIR"

echo "Downloading portable CPython (macOS ${DISPLAY_ARCH})..."
curl -L -o "$RESOURCES_DIR/python-runtime.tar.gz" "$URL"

echo "Extracting..."
tar -xzf "$RESOURCES_DIR/python-runtime.tar.gz" -C "$RESOURCES_DIR"
mv "$RESOURCES_DIR/python" "$RUNTIME_DIR"
rm "$RESOURCES_DIR/python-runtime.tar.gz"

PYTHON_BIN="$RUNTIME_DIR/bin/python3"

echo "Installing real project dependencies (torch is large)..."
# See build_python_windows.ps1's matching comment: callosum never uses GPU acceleration, so the
# CPU-only torch build goes in first (smaller, and avoids a hard dynamic-link dependency on the
# NVIDIA driver that doesn't exist on a GPU-less machine at all).
"$PYTHON_BIN" -m pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu
"$PYTHON_BIN" -m pip install --no-cache-dir -r "$PROJECT_ROOT/requirements.txt"
"$PYTHON_BIN" -m pip install --no-cache-dir keyring  # hard dependency in the packaged build

# See build_python_windows.ps1's matching comment: torch vendors ~100 deeply-nested license copies
# for its internal C++ profiler's (kineto) own vendored build/test tools — pure attribution text,
# no functional code. This broke Windows' NSIS build on a real run (a path-length limit); pruned
# here too for consistency, even though macOS's DMG tooling is less likely to hit the same limit.
find "$RUNTIME_DIR" -type d -path "*/dist-info/licenses/third_party" -print -exec rm -rf {} + 2>/dev/null || true

echo "Smoke-testing the bundle (required, blocking — see smoke_test_backend.py's own docstring for why)..."
python3 "$SCRIPT_DIR/smoke_test_backend.py" \
  --python "$PYTHON_BIN" \
  --source "$SCRIPT_DIR/../resources/callosum-src"

echo "Done: $RUNTIME_DIR"
