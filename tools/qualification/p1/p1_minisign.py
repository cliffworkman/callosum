"""Verify the runtime manifest's Minisign signature against the key the desktop shell trusts.

The public key is read from ``python_runtime.rs`` (the constant the installer itself uses), never retyped here. The
``.sig`` file is accepted plain or base64-wrapped, as ``tauri signer sign`` writes it. Both Minisign algorithms are
accepted: ``Ed`` (signature over the file) and ``ED`` (signature over its BLAKE2b-512 prehash). The trusted comment is
covered by the global signature and is verified too.

Run with the hash-verified packaged interpreter (``python.exe -I -B``); it needs only ``cryptography``. The pinned
archive SHA-256 remains the primary trust anchor; this is an additional, independent check.

Exit 0 and ``SIGNATURE OK`` on success; exit 1 with the reason otherwise.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import re
import sys
from pathlib import Path

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey


def public_key_from_rust(source: str) -> tuple[bytes, bytes]:
    match = re.search(r'const PUBLIC_KEY: &str = "untrusted comment: [^"\\]*\\n([A-Za-z0-9+/=]+)\\n";', source)
    if not match:
        raise ValueError("PUBLIC_KEY constant not found in python_runtime.rs")
    raw = base64.b64decode(match.group(1), validate=True)
    if len(raw) != 42 or raw[:2] != b"Ed":
        raise ValueError("public key is not a Minisign Ed25519 key")
    return raw[2:10], raw[10:]


def signature_lines(blob: bytes) -> list[str]:
    text = blob.decode("utf-8").strip()
    if not text.startswith("untrusted comment:"):
        text = base64.b64decode(text, validate=True).decode("utf-8").strip()
    lines = text.splitlines()
    if len(lines) != 4 or not lines[0].startswith("untrusted comment:") or not lines[2].startswith("trusted comment: "):
        raise ValueError("signature is not a four-line Minisign document")
    return lines


def verify(message: bytes, signature_blob: bytes, rust_source: str) -> str:
    key_id, key = public_key_from_rust(rust_source)
    lines = signature_lines(signature_blob)
    sig = base64.b64decode(lines[1], validate=True)
    if len(sig) != 74:
        raise ValueError("signature block has the wrong length")
    algorithm, sig_key_id, signature = sig[:2], sig[2:10], sig[10:]
    if sig_key_id != key_id:
        raise ValueError("signature was made with a different key")
    if algorithm == b"ED":
        signed = hashlib.blake2b(message, digest_size=64).digest()
    elif algorithm == b"Ed":
        signed = message
    else:
        raise ValueError(f"unknown signature algorithm {algorithm!r}")
    public = Ed25519PublicKey.from_public_bytes(key)
    public.verify(signature, signed)
    trusted = lines[2][len("trusted comment: ") :].encode("utf-8")
    public.verify(base64.b64decode(lines[3], validate=True), signature + trusted)
    return trusted.decode("utf-8")


def main() -> int:
    message, signature, rust = (Path(p) for p in sys.argv[1:4])
    try:
        trusted = verify(message.read_bytes(), signature.read_bytes(), rust.read_text(encoding="utf-8"))
    except (InvalidSignature, ValueError, binascii.Error, UnicodeDecodeError) as exc:
        print(f"SIGNATURE INVALID: {type(exc).__name__}: {exc}")
        return 1
    print(f"SIGNATURE OK trusted comment: {trusted}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
