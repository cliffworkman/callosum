"""Vector-store interfaces and sqlite-vec implementation."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Protocol

from sqlalchemy import Connection


@dataclass(frozen=True)
class VectorHit:
    embedding_id: int
    distance: float


class VectorStore(Protocol):
    kind: str

    def ensure_ready(self, conn: Connection, dimension: int) -> None:
        """Ensure storage exists for this vector dimension."""

    def add(self, conn: Connection, *, embedding_id: int, vector: list[float]) -> str:
        """Store a vector and return a vector-store reference string."""

    def delete(self, conn: Connection, *, embedding_id: int, dimension: int) -> None:
        """Remove a stored vector by embedding id (no-op if absent). Used by permanent paper delete."""

    def search(
        self,
        conn: Connection,
        *,
        vector: list[float],
        top_k: int,
        candidate_embedding_ids: set[int] | None = None,
    ) -> list[VectorHit]:
        """Return nearest vector hits."""


class SQLiteVecVectorStore:
    kind = "sqlite-vec"
    max_knn_k = 4096

    def ensure_ready(self, conn: Connection, dimension: int) -> None:
        raw = conn.connection.driver_connection
        raw.enable_load_extension(True)
        try:
            import sqlite_vec

            sqlite_vec.load(raw)
        finally:
            raw.enable_load_extension(False)
        conn.exec_driver_sql(
            f"CREATE VIRTUAL TABLE IF NOT EXISTS {_table_name(dimension)} "
            f"USING vec0(embedding float[{dimension}] distance_metric=cosine)"
        )

    def add(self, conn: Connection, *, embedding_id: int, vector: list[float]) -> str:
        self.ensure_ready(conn, len(vector))
        from sqlite_vec import serialize_float32

        table_name = _table_name(len(vector))
        conn.exec_driver_sql(
            f"INSERT OR REPLACE INTO {table_name}(rowid, embedding) VALUES (?, ?)",
            (embedding_id, serialize_float32(vector)),
        )
        return f"{table_name}:{embedding_id}"

    def delete(self, conn: Connection, *, embedding_id: int, dimension: int) -> None:
        # The sqlite-vec virtual table is keyed by rowid == embedding_id; bound param + constant table name.
        self.ensure_ready(conn, dimension)
        conn.exec_driver_sql(
            f"DELETE FROM {_table_name(dimension)} WHERE rowid = ?",
            (int(embedding_id),),
        )

    def search(
        self,
        conn: Connection,
        *,
        vector: list[float],
        top_k: int,
        candidate_embedding_ids: set[int] | None = None,
    ) -> list[VectorHit]:
        self.ensure_ready(conn, len(vector))
        from sqlite_vec import serialize_float32

        table_name = _table_name(len(vector))
        if candidate_embedding_ids is not None:
            if not candidate_embedding_ids or top_k <= 0:
                return []
            return self._search_candidates(
                conn,
                table_name=table_name,
                serialized_vector=serialize_float32(vector),
                top_k=top_k,
                candidate_embedding_ids=candidate_embedding_ids,
            )

        if top_k <= 0:
            return []
        rows = conn.exec_driver_sql(
            f"""
            SELECT rowid, distance
            FROM {table_name}
            WHERE embedding MATCH ?
            ORDER BY distance
            LIMIT ?
            """,
            (
                serialize_float32(vector),
                self._search_limit(top_k, candidate_embedding_ids),
            ),
        ).fetchall()
        return [VectorHit(embedding_id=int(row[0]), distance=float(row[1])) for row in rows]

    def _search_candidates(
        self,
        conn: Connection,
        *,
        table_name: str,
        serialized_vector: bytes,
        top_k: int,
        candidate_embedding_ids: set[int],
    ) -> list[VectorHit]:
        conn.exec_driver_sql(
            """
            CREATE TEMP TABLE IF NOT EXISTS callosum_vec_candidate_embedding_ids(
                id INTEGER PRIMARY KEY
            )
            """
        )
        conn.exec_driver_sql("DELETE FROM callosum_vec_candidate_embedding_ids")
        conn.exec_driver_sql(
            "INSERT INTO callosum_vec_candidate_embedding_ids(id) VALUES (?)",
            [(int(embedding_id),) for embedding_id in sorted(candidate_embedding_ids)],
        )
        try:
            rows = conn.exec_driver_sql(
                f"""
                SELECT rowid, distance
                FROM {table_name}
                WHERE embedding MATCH ?
                  AND rowid IN (SELECT id FROM callosum_vec_candidate_embedding_ids)
                ORDER BY distance
                LIMIT ?
                """,
                (
                    serialized_vector,
                    self._search_limit(top_k, candidate_embedding_ids),
                ),
            ).fetchall()
        finally:
            conn.exec_driver_sql("DELETE FROM callosum_vec_candidate_embedding_ids")
        return [VectorHit(embedding_id=int(row[0]), distance=float(row[1])) for row in rows]

    def _search_limit(self, top_k: int, candidate_embedding_ids: set[int] | None) -> int:
        if candidate_embedding_ids is None:
            return min(top_k, self.max_knn_k)
        return min(len(candidate_embedding_ids), top_k, self.max_knn_k)


class InMemoryVectorStore:
    kind = "memory"

    def __init__(self) -> None:
        self.vectors: dict[int, list[float]] = {}

    def ensure_ready(self, conn: Connection, dimension: int) -> None:
        return None

    def add(self, conn: Connection, *, embedding_id: int, vector: list[float]) -> str:
        self.vectors[embedding_id] = list(vector)
        return f"memory:{embedding_id}"

    def delete(self, conn: Connection, *, embedding_id: int, dimension: int = 0) -> None:
        self.vectors.pop(int(embedding_id), None)

    def search(
        self,
        conn: Connection,
        *,
        vector: list[float],
        top_k: int,
        candidate_embedding_ids: set[int] | None = None,
    ) -> list[VectorHit]:
        ids = candidate_embedding_ids if candidate_embedding_ids is not None else set(self.vectors)
        hits = [
            VectorHit(embedding_id=embedding_id, distance=_cosine_distance(vector, stored))
            for embedding_id, stored in self.vectors.items()
            if embedding_id in ids
        ]
        hits.sort(key=lambda hit: hit.distance)
        return hits[:top_k]


def _table_name(dimension: int) -> str:
    if dimension <= 0:
        raise ValueError("Vector dimension must be positive")
    return f"callosum_vec_embeddings_{dimension}"


def _cosine_distance(left: list[float], right: list[float]) -> float:
    if len(left) != len(right):
        return 1.0
    dot = sum(a * b for a, b in zip(left, right, strict=False))
    left_norm = math.sqrt(sum(a * a for a in left))
    right_norm = math.sqrt(sum(b * b for b in right))
    if left_norm == 0 or right_norm == 0:
        return 1.0
    return 1.0 - (dot / (left_norm * right_norm))
