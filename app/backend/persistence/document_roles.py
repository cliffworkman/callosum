"""Controlled document roles and legacy-compatible attachment scope predicates.

The stored ``attachments.role`` column predates document-scoped retrieval and contains legacy values such as
``primary`` and ``supplementary-text``.  This module gives every reader one non-destructive interpretation of those
rows.  New features use the canonical vocabulary; old libraries keep working without a rewrite migration.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Literal, cast

from sqlalchemy import String, and_, case, func
from sqlalchemy import cast as sql_cast
from sqlalchemy.sql.elements import ColumnElement
from sqlalchemy.sql.schema import Table

from app.backend.persistence.schema import attachments

DocumentRole = Literal["article-fulltext", "supplement", "preregistration", "protocol", "other"]

ARTICLE_FULLTEXT: DocumentRole = "article-fulltext"
SUPPLEMENT: DocumentRole = "supplement"
PREREGISTRATION: DocumentRole = "preregistration"
PROTOCOL: DocumentRole = "protocol"
OTHER: DocumentRole = "other"

DOCUMENT_ROLES: tuple[DocumentRole, ...] = (
    ARTICLE_FULLTEXT,
    SUPPLEMENT,
    PREREGISTRATION,
    PROTOCOL,
    OTHER,
)
ARTICLE_DOCUMENT_ROLES: tuple[DocumentRole, ...] = (ARTICLE_FULLTEXT,)
ARTICLE_AND_SUPPLEMENT_DOCUMENT_ROLES: tuple[DocumentRole, ...] = (ARTICLE_FULLTEXT, SUPPLEMENT)
ALL_DOCUMENT_ROLES: tuple[DocumentRole, ...] = DOCUMENT_ROLES

# Raw SQLite FTS queries cannot embed a SQLAlchemy expression. This fixed-alias CASE is the same normalization used
# by ``document_role_expression`` below; values are module constants only, never client input.
SQLITE_DOCUMENT_ROLE_CASE_FOR_A = """
CASE
  WHEN lower(trim(coalesce(a.role, ''))) IN
       ('article-fulltext', 'supplement', 'preregistration', 'protocol', 'other')
    THEN lower(trim(a.role))
  WHEN lower(trim(coalesce(a.role, ''))) = 'primary' THEN 'article-fulltext'
  WHEN lower(trim(coalesce(a.role, ''))) IN ('supplementary', 'supplementary-text') THEN 'supplement'
  WHEN lower(trim(coalesce(a.role, ''))) IN ('secondary', 'attachment') THEN 'other'
  WHEN lower(trim(coalesce(a.role, ''))) = ''
       AND lower(trim(coalesce(a.attachment_type, ''))) IN ('supplement', 'supplementary', 'supplementary-material')
    THEN 'supplement'
  WHEN lower(trim(coalesce(a.role, ''))) = ''
       AND lower(trim(coalesce(a.attachment_type, ''))) IN ('preregistration', 'registration')
    THEN 'preregistration'
  WHEN lower(trim(coalesce(a.role, ''))) = ''
       AND lower(trim(coalesce(a.attachment_type, ''))) = 'protocol'
    THEN 'protocol'
  WHEN lower(trim(coalesce(a.role, ''))) = '' THEN 'article-fulltext'
  ELSE 'other'
END
""".strip()

_LEGACY_ROLE_MAP: dict[str, DocumentRole] = {
    "primary": ARTICLE_FULLTEXT,
    "supplementary": SUPPLEMENT,
    "supplementary-text": SUPPLEMENT,
    "secondary": OTHER,  # OCR keeps its unsearchable original as secondary; including it could duplicate the article.
    "attachment": OTHER,
}
_TYPE_HINTS: dict[str, DocumentRole] = {
    "supplement": SUPPLEMENT,
    "supplementary": SUPPLEMENT,
    "supplementary-material": SUPPLEMENT,
    "preregistration": PREREGISTRATION,
    "registration": PREREGISTRATION,
    "protocol": PROTOCOL,
}


def validate_document_roles(document_roles: Iterable[str]) -> tuple[DocumentRole, ...]:
    """Return a stable, de-duplicated canonical role tuple; reject ambiguous/empty scopes."""
    roles: list[DocumentRole] = []
    for raw in document_roles:
        value = str(raw).strip().casefold()
        if value not in DOCUMENT_ROLES:
            raise ValueError(f"Unknown document role: {raw!r}")
        role = cast(DocumentRole, value)
        if role not in roles:
            roles.append(role)
    if not roles:
        raise ValueError("At least one document role is required")
    return tuple(roles)


def normalized_document_role(row: Mapping[str, object]) -> DocumentRole:
    """Interpret one attachment row using the canonical vocabulary, without mutating stored metadata."""
    raw_role = str(row.get("role") or "").strip().casefold()
    if raw_role in DOCUMENT_ROLES:
        return cast(DocumentRole, raw_role)
    if raw_role in _LEGACY_ROLE_MAP:
        return _LEGACY_ROLE_MAP[raw_role]
    if raw_role:
        return OTHER

    attachment_type = str(row.get("attachment_type") or "").strip().casefold()
    if attachment_type in _TYPE_HINTS:
        return _TYPE_HINTS[attachment_type]
    # Null-role legacy attachments were the paper's only/primary document. Preserve that behavior for PDFs and
    # text documents alike unless attachment metadata explicitly says otherwise.
    return ARTICLE_FULLTEXT


def document_role_expression(table: Table = attachments) -> ColumnElement[str]:
    """SQL expression equivalent to :func:`normalized_document_role` for attachment joins."""
    role = func.lower(func.trim(func.coalesce(table.c.role, "")))
    attachment_type = func.lower(func.trim(func.coalesce(table.c.attachment_type, "")))
    return sql_cast(
        case(
            (role.in_(DOCUMENT_ROLES), role),
            (role == "primary", ARTICLE_FULLTEXT),
            (role.in_(("supplementary", "supplementary-text")), SUPPLEMENT),
            (role.in_(("secondary", "attachment")), OTHER),
            (
                and_(role == "", attachment_type.in_(("supplement", "supplementary", "supplementary-material"))),
                SUPPLEMENT,
            ),
            (and_(role == "", attachment_type.in_(("preregistration", "registration"))), PREREGISTRATION),
            (and_(role == "", attachment_type == "protocol"), PROTOCOL),
            (role == "", ARTICLE_FULLTEXT),
            else_=OTHER,
        ),
        String,
    )


def attachment_document_role_clause(document_roles: Iterable[str], table: Table = attachments) -> ColumnElement[bool]:
    """A bound SQLAlchemy predicate selecting only attachments in the requested canonical roles."""
    roles = validate_document_roles(document_roles)
    return document_role_expression(table).in_(roles)
