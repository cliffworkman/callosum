"""AJOL (African Journals Online) integration -- a third-party CC-BY-4.0 compiled snapshot (Alonso-Álvarez 2025,
Zenodo DOI 10.5281/zenodo.14899380), not an AJOL-official feed. Mirrors integrations/top_factor's
download-parse-replace shape: AJOL's own live OAI-PMH endpoint is article-indexed (one "set" per journal, ~750
sets) and not usable for a per-ISSN legitimacy lookup without a heavy full harvest of uncertain ISSN coverage --
see integrations/ajol/adapter.py's module docstring for the full reasoning.
"""

from __future__ import annotations

from integrations.ajol.adapter import AjolClient, AjolUnavailable

__all__ = ["AjolClient", "AjolUnavailable"]
