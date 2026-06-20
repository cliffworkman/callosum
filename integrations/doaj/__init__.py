"""DOAJ integration: gold open-access article resolution (the legally-clear acquisition lane)."""

from integrations.doaj.adapter import DOAJ_PROVIDER, DoajClient, DoajFetcher

__all__ = ["DOAJ_PROVIDER", "DoajClient", "DoajFetcher"]
