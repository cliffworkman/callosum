"""Shared SQLAlchemy ``MetaData`` for the persistence schema.

Split out (inc 137) so ``schema.py`` and ``schema_findings.py`` can both register their tables on one
``metadata`` without a circular import: each imports ``metadata`` from here, and ``schema.py`` re-exports the
findings tables for backward-compatibility. This keeps ``schema.py`` under the 600-line cap (rule #1).
"""

from __future__ import annotations

from sqlalchemy import MetaData

NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

metadata = MetaData(naming_convention=NAMING_CONVENTION)
