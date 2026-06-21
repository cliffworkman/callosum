"""OpenAlex integration: OA-location resolution (acquisition) + author resolution (My Publications)."""

from integrations.openalex.adapter import OPENALEX_PROVIDER, OpenAlexClient, OpenAlexFetcher
from integrations.openalex.author import (
    AuthorFetcher,
    AuthorWork,
    OpenAlexAuthorClient,
    ResolvedAuthor,
)

__all__ = [
    "OPENALEX_PROVIDER",
    "OpenAlexClient",
    "OpenAlexFetcher",
    "OpenAlexAuthorClient",
    "AuthorFetcher",
    "AuthorWork",
    "ResolvedAuthor",
]
