"""Run the cloudflared tunnel for callosum.clffwrkmn.net (inc 169, Google Docs SP1).

The bridge that lets the Google Docs add-on reach your LOCAL callosum: cloudflared runs here, dials OUT to
Cloudflare's edge (no inbound port), and serves ``https://callosum.clffwrkmn.net`` with a **cite-only** ingress
(only the citation endpoints reach localhost:8080; everything else → 404). The bearer token (Settings → Remote
access) is callosum's boundary; the ingress allowlist is the tunnel's.

One-time setup (see ``adapters/googledocs/README.md``): a free Cloudflare account with ``callosum.clffwrkmn.net``
added (the root domain on a free plan), ``cloudflared login``, ``cloudflared tunnel create callosum`` (copy
``cloudflared-config.yml`` → the gitignored ``cloudflared-config.local.yml`` and fill in the printed tunnel id +
credentials path; this runner prefers the ``.local.yml`` copy), and ``cloudflared tunnel route dns callosum
callosum.clffwrkmn.net``. Then run this. callosum must be running locally (uvicorn on :8080) with **Remote access ON**.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
# The committed config is a placeholder TEMPLATE (no secret committed). Your filled copy lives beside it as
# cloudflared-config.local.yml (gitignored) and wins when present — so your tunnel id + creds path never get committed.
CONFIG_TEMPLATE = ROOT / "adapters" / "googledocs" / "cloudflared-config.yml"
CONFIG_LOCAL = ROOT / "adapters" / "googledocs" / "cloudflared-config.local.yml"
_WIN_DEFAULT = r"C:\Program Files (x86)\cloudflared\cloudflared.exe"


def _config() -> Path:
    return CONFIG_LOCAL if CONFIG_LOCAL.is_file() else CONFIG_TEMPLATE


def _cloudflared() -> str | None:
    exe = shutil.which("cloudflared")
    if exe:
        return exe
    if sys.platform.startswith("win") and Path(_WIN_DEFAULT).is_file():
        return _WIN_DEFAULT
    return None


def main() -> int:
    cf = _cloudflared()
    if cf is None:
        print("cloudflared not found. Install it once:\n\n    winget install Cloudflare.cloudflared\n", file=sys.stderr)
        return 1
    config = _config()
    if not config.is_file():
        print(f"Missing tunnel config: {config}", file=sys.stderr)
        return 1
    if "<TUNNEL_ID>" in config.read_text(encoding="utf-8"):
        print(
            f"Fill in your tunnel id + credentials path in a local copy:\n"
            f"    copy {CONFIG_TEMPLATE.name} -> {CONFIG_LOCAL.name}  (in adapters/googledocs/, gitignored)\n"
            "Run `cloudflared tunnel create callosum` first — see adapters/googledocs/README.md.",
            file=sys.stderr,
        )
        return 1
    print("Starting the cloudflared tunnel for callosum.clffwrkmn.net (cite-only). Ctrl-C to stop.")
    return subprocess.call([cf, "tunnel", "--config", str(config), "run"])


if __name__ == "__main__":
    raise SystemExit(main())
