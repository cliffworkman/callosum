"""Run a cloudflared tunnel so the Google Docs add-on can reach your LOCAL callosum (inc 169 / inc 193).

cloudflared runs here, dials OUT to Cloudflare's edge (no inbound port). Two modes:

* ``--quick`` (inc 193, the EASY path): a **Cloudflare Quick Tunnel** — ``cloudflared tunnel --url
  http://localhost:<port>`` with **zero setup** (no account, no domain, no config). It prints a throwaway
  ``https://<random>.trycloudflare.com`` URL; paste that into the add-on's Connection settings (with your token).
  TRADEOFF: the URL changes each launch, and a quick tunnel can't enforce the cite-only ingress allowlist — so the
  **bearer token is the SOLE boundary** (it is already the primary one; cite-only was defense-in-depth). Best for
  trying it out fast.

* default (named tunnel, inc 169, the STABLE path): serves ``https://callosum-tunnel.clffwrkmn.net`` with a **cite-only**
  ingress (only the citation endpoints reach localhost; everything else → 404). Needs the one-time setup in
  ``adapters/googledocs/README.md`` (Cloudflare account + domain on Cloudflare, ``cloudflared login`` / ``tunnel
  create`` / ``route dns``, and the filled ``cloudflared-config.local.yml`` this runner prefers).

EITHER way callosum must be running locally with **Remote access ON** (Settings → Remote access — the token gate).
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
# The committed config is a placeholder TEMPLATE (no secret committed). Your filled copy lives beside it as
# cloudflared-config.local.yml (gitignored) and wins when present — so your tunnel id + creds path never get committed.
CONFIG_TEMPLATE = ROOT / "adapters" / "googledocs" / "cloudflared-config.yml"
CONFIG_LOCAL = ROOT / "adapters" / "googledocs" / "cloudflared-config.local.yml"
# B5 (inc 237): the read-only mobile-reading ingress (a separate hostname + allowlist).
MOBILE_TEMPLATE = ROOT / "adapters" / "mobile" / "cloudflared-config.yml"
MOBILE_LOCAL = ROOT / "adapters" / "mobile" / "cloudflared-config.local.yml"
_WIN_DEFAULT = r"C:\Program Files (x86)\cloudflared\cloudflared.exe"


def _config(mobile: bool = False) -> Path:
    template, local = (MOBILE_TEMPLATE, MOBILE_LOCAL) if mobile else (CONFIG_TEMPLATE, CONFIG_LOCAL)
    return local if local.is_file() else template


def _cloudflared() -> str | None:
    exe = shutil.which("cloudflared")
    if exe:
        return exe
    if sys.platform.startswith("win") and Path(_WIN_DEFAULT).is_file():
        return _WIN_DEFAULT
    return None


def _run_quick(cf: str, port: int) -> int:
    print(
        f"Starting a Cloudflare QUICK tunnel → http://localhost:{port}  (Ctrl-C to stop).\n"
        "  • Make sure callosum is running on that port with Remote access ON (Settings → Remote access).\n"
        "  • cloudflared prints a https://<random>.trycloudflare.com URL below — paste it (with your access\n"
        "    token) into the Google Docs add-on's Connection settings. The URL changes each launch.\n"
        "  • NOTE: a quick tunnel forwards every path (no cite-only allowlist) — your bearer token is the only\n"
        "    boundary, so keep it secret + turn Remote access off when you're done.\n",
        file=sys.stderr,
    )
    return subprocess.call([cf, "tunnel", "--url", f"http://localhost:{port}"])


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a cloudflared tunnel for the Google Docs add-on.")
    parser.add_argument("--quick", action="store_true", help="zero-setup Cloudflare Quick Tunnel (throwaway URL)")
    parser.add_argument(
        "--mobile", action="store_true", help="read-only mobile-reading ingress (B5) instead of cite-only"
    )
    parser.add_argument("--port", type=int, default=8080, help="local callosum port for --quick (default 8080)")
    args = parser.parse_args()

    cf = _cloudflared()
    if cf is None:
        print("cloudflared not found. Install it once:\n\n    winget install Cloudflare.cloudflared\n", file=sys.stderr)
        return 1
    if args.quick:
        return _run_quick(cf, args.port)
    config = _config(mobile=args.mobile)
    subdir = "adapters/mobile" if args.mobile else "adapters/googledocs"
    if not config.is_file():
        print(f"Missing tunnel config: {config}", file=sys.stderr)
        return 1
    if "<TUNNEL_ID>" in config.read_text(encoding="utf-8"):
        print(
            f"Fill in your tunnel id + credentials path in a local copy:\n"
            f"    copy {config.name} -> {config.stem}.local.yml  (in {subdir}/, gitignored)\n"
            f"Run `cloudflared tunnel create callosum` first — see {subdir}/README.md.",
            file=sys.stderr,
        )
        return 1
    if args.mobile:
        print("Starting the READ-ONLY mobile tunnel. Make sure the tunnel-facing callosum runs with", file=sys.stderr)
        print(
            "CALLOSUM_READ_ONLY=1 + Remote access ON (see adapters/mobile/README.md). Ctrl-C to stop.", file=sys.stderr
        )
    else:
        print("Starting the cloudflared tunnel for callosum-tunnel.clffwrkmn.net (cite-only). Ctrl-C to stop.")
    return subprocess.call([cf, "tunnel", "--config", str(config), "run"])


if __name__ == "__main__":
    raise SystemExit(main())
