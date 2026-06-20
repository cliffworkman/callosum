"""Citation-grounded summarization pipeline."""

from app.backend.summarization.generators import (
    CandidateCitation,
    CandidateSummarySentence,
    FakeSummaryGenerator,
    SourceChunk,
    SummaryGenerator,
)
from app.backend.summarization.pipeline import (
    CitationPersistenceResult,
    SummaryPersistenceResult,
    SummaryScope,
    SummarySentencePersistenceResult,
    summarize_scope,
)
from app.backend.summarization.verification import (
    EmbeddingSupportScorer,
    LocalCitationVerifier,
    NLISupportScorer,
    SupportScorer,
    VerificationConfig,
    VerificationResult,
)

__all__ = [
    "CandidateCitation",
    "CandidateSummarySentence",
    "FakeSummaryGenerator",
    "SourceChunk",
    "SummaryGenerator",
    "CitationPersistenceResult",
    "SummaryPersistenceResult",
    "SummaryScope",
    "SummarySentencePersistenceResult",
    "summarize_scope",
    "EmbeddingSupportScorer",
    "LocalCitationVerifier",
    "NLISupportScorer",
    "SupportScorer",
    "VerificationConfig",
    "VerificationResult",
]
