"""Run callosum over HTTPS on :8443 for the Microsoft Word add-in (inc 164).

Office.js task panes require HTTPS and cannot reach http://localhost, so the Word add-in is served by callosum over
TLS, **same-origin** with its API (Architecture A — nothing leaves the machine). This locates the dev certificate
created by ``npx office-addin-dev-certs install`` (run once) and starts uvicorn with it.

HTTP on :8080 remains the default for normal use; HTTPS is only needed while using the Word add-in.

    npx office-addin-dev-certs install     # one time — trusts a local CA
    python tools/run_https.py              # serves https://localhost:8443

Override the port with CALLOSUM_HTTPS_PORT (the manifest expects 8443).

**inc 511 — desktop Word never needs the Remote Access token, even when it's on for a tunnel.** This process
sets ``CALLOSUM_DISABLE_REMOTE_ACCESS=1`` in its OWN environment before starting uvicorn — a real, already-
shipped recovery hatch (``app_settings.stored_remote_access()``, inc 168/254) that force-disables the token gate
for whichever process has it set. Since ``run_https.py`` runs as a genuinely separate OS process from whichever
one serves ``cloudflared``'s tunnel target (the checked-in ``adapters/googledocs/cloudflared-config.yml``
ingress only ever forwards to the plain HTTP dev port, never :8443 — see that file's own warning comment),
setting this here affects ONLY desktop Word's dedicated HTTPS server; the tunnel-facing process, running
separately with its own environment, stays exactly as strict as the Remote Access setting says. This is safe
specifically BECAUSE this port structurally can't receive tunnel-relayed traffic — trusting loopback origin in
general is NOT safe (see access_control.py's own docstring: cloudflared's local forward makes tunnel and local
traffic indistinguishable by IP), but a process that's never the tunnel's target is a different, sound claim.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# uvicorn.run("app.backend.api.app:app", ...) below resolves that dotted path via a DEFERRED import inside
# uvicorn itself, not a direct `from app...` here -- so this file never triggered Python's own import
# machinery to fail loudly at parse time. Running exactly as documented (`python tools/run_https.py`, script
# mode) puts this file's own directory (tools/) on sys.path, NOT the project root, so uvicorn's later import
# of `app.backend...` raises `ModuleNotFoundError: No module named 'app'` -- a real bug, caught live
# (2026-08-28) the first time this script was ever actually run, since Word was never installed before. Same
# fix every other tools/ script needing a sibling `app` import already uses (e.g. build_frontend.py).
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def _dev_cert_paths() -> tuple[str, str] | tuple[None, None]:
    home = Path.home() / ".office-addin-dev-certs"
    crt, key = home / "localhost.crt", home / "localhost.key"
    if crt.is_file() and key.is_file():
        return str(crt), str(key)
    return None, None


def main() -> int:
    crt, key = _dev_cert_paths()
    if crt is None:
        print(
            "No local dev certificate found.\nRun this once, then re-run:\n\n    npx office-addin-dev-certs install\n",
            file=sys.stderr,
        )
        return 1
    port = int(os.environ.get("CALLOSUM_HTTPS_PORT", "8443"))
    # This process is dedicated to desktop Word and is never the port cloudflared's ingress targets (see the
    # module docstring) -- unconditionally exempt it from the Remote Access token gate in its OWN environment
    # only, so desktop Word works regardless of whether Remote Access happens to be on for a tunnel elsewhere.
    os.environ["CALLOSUM_DISABLE_REMOTE_ACCESS"] = "1"
    import uvicorn

    print(f"Serving callosum over HTTPS at https://localhost:{port}  (Ctrl-C to stop)")
    uvicorn.run("app.backend.api.app:app", host="localhost", port=port, ssl_certfile=crt, ssl_keyfile=key)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
