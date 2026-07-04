"""Shared SQLAlchemy ``MetaData`` (+ CHECK-constraint helpers) for the persistence schema.

Split out (inc 137) so ``schema.py`` and its sibling ``schema_*.py`` modules can all register their tables on one
``metadata`` without a circular import: each imports ``metadata`` from here, and ``schema.py`` re-exports the
sibling tables for backward-compatibility. This keeps ``schema.py`` under the 600-line cap (rule #1). The
``enum_check`` / ``non_empty_check`` helpers + the ``CITATION_MAPPING_STATUSES`` value set live here too (inc 262,
the summaries split) so both ``schema.py`` and ``schema_summaries.py`` share one definition without importing from
``schema.py``.
"""

from __future__ import annotations

from sqlalchemy import CheckConstraint, MetaData

NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

metadata = MetaData(naming_convention=NAMING_CONVENTION)

CITATION_MAPPING_STATUSES = ("verified", "weak", "contradicted", "unverified")


def enum_check(column_name: str, values: tuple[str, ...], name: str) -> CheckConstraint:
    quoted = ", ".join(f"'{value}'" for value in values)
    return CheckConstraint(f"{column_name} IN ({quoted})", name=name)


def non_empty_check(column_name: str, name: str) -> CheckConstraint:
    return CheckConstraint(f"length(trim({column_name})) > 0", name=name)
