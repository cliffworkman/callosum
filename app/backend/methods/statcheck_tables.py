"""Conservative reconstruction of one NHST result from an explicitly headed table row."""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.backend.document_tables import TableRowEvidence

_NUM = r"-?\d*\.?\d+"
_STAT_COMP = r"([<>=≤≥])"
_TABLE_TEST_PATTERNS: tuple[tuple[str, re.Pattern], ...] = (
    (
        "F",
        re.compile(
            rf"^\s*F\s*\(\s*(\d+(?:\.\d+)?)\s*[,;/]\s*(\d+(?:\.\d+)?)\s*\)"
            rf"\s*(?:{_STAT_COMP}\s*({_NUM}))?\s*$",
            re.IGNORECASE,
        ),
    ),
    (
        "chi2",
        re.compile(
            rf"^\s*(?:χ²|χ2|chi[\s-]*square|chi2|X²|X2)\s*\(\s*(\d+(?:\.\d+)?)\s*\)"
            rf"\s*(?:{_STAT_COMP}\s*({_NUM}))?\s*$",
            re.IGNORECASE,
        ),
    ),
    (
        "t",
        re.compile(
            rf"^\s*t\s*\(\s*(\d+(?:\.\d+)?)\s*\)\s*(?:{_STAT_COMP}\s*({_NUM}))?\s*$",
            re.IGNORECASE,
        ),
    ),
    (
        "r",
        re.compile(
            rf"^\s*r\s*\(\s*(\d+(?:\.\d+)?)\s*\)\s*(?:{_STAT_COMP}\s*({_NUM}))?\s*$",
            re.IGNORECASE,
        ),
    ),
    ("z", re.compile(rf"^\s*z\s*(?:{_STAT_COMP}\s*({_NUM}))?\s*$", re.IGNORECASE)),
)
_TABLE_P_VALUE = re.compile(rf"^\s*(?:p\s*)?([<>=≤≥]?)\s*({_NUM})\s*[*†‡]?\s*$", re.IGNORECASE)
_TABLE_STAT_VALUE = re.compile(rf"^\s*([<>=≤≥]?)\s*({_NUM})\s*[*†‡]?\s*$")
_TABLE_DF_VALUE = re.compile(r"\d+(?:\.\d+)?")


@dataclass(frozen=True)
class TableStatCandidate:
    test_type: str
    stat: str
    stat_comparator: str
    p_value: str
    p_comparator: str
    df1: float
    df2: float | None
    headers: tuple[str, ...]
    cells: tuple[str, ...]


def parse_table_stat(row: TableRowEvidence) -> TableStatCandidate | None:
    headers = tuple(_table_text(header) for header in row.headers)
    cells = tuple(_table_text(cell) for cell in row.cells)
    width = min(len(headers), len(cells))
    if width < 2:
        return None
    headers = headers[:width]
    cells = cells[:width]
    p_columns = [index for index, header in enumerate(headers) if _is_p_header(header)]
    if len(p_columns) != 1:
        return None
    p_index = p_columns[0]
    p_match = _TABLE_P_VALUE.fullmatch(cells[p_index])
    if not p_match:
        return None
    p_comp = _normalize_comparator(p_match.group(1) or "=")
    p_value_s = p_match.group(2)

    expression = _find_table_test_expression(headers, cells, excluded={p_index})
    if expression is not None:
        test_type, df1, df2, expr_stat_comp, expr_stat_s, expression_index = expression
    else:
        typed_columns = [
            (index, _test_type_label(header))
            for index, header in enumerate(headers)
            if index != p_index and _test_type_label(header)
        ]
        typed_columns = [(index, kind) for index, kind in typed_columns if kind is not None]
        if len(typed_columns) != 1:
            return None
        expression_index, test_type = typed_columns[0]
        df_values = _table_df_values(headers, cells, excluded={p_index, expression_index})
        df1, df2 = _dfs_for_test(test_type, df_values)
        if df1 is None:
            return None
        expr_stat_comp, expr_stat_s = None, None

    if expr_stat_s is not None:
        stat_comp = _normalize_comparator(expr_stat_comp or "=")
        stat_s = expr_stat_s
    else:
        stat_columns = [
            index
            for index, header in enumerate(headers)
            if index not in {p_index, expression_index} and _is_stat_header(header)
        ]
        if not stat_columns and _is_numeric_stat_cell(cells[expression_index]):
            stat_columns = [expression_index]
        if len(stat_columns) != 1:
            return None
        stat_match = _TABLE_STAT_VALUE.fullmatch(cells[stat_columns[0]])
        if not stat_match:
            return None
        stat_comp = _normalize_comparator(stat_match.group(1) or "=")
        stat_s = stat_match.group(2)

    return TableStatCandidate(
        test_type=test_type,
        stat=stat_s,
        stat_comparator=stat_comp,
        p_value=p_value_s,
        p_comparator=p_comp,
        df1=df1,
        df2=df2,
        headers=headers,
        cells=cells,
    )


def _find_table_test_expression(
    headers: tuple[str, ...],
    cells: tuple[str, ...],
    *,
    excluded: set[int],
) -> tuple[str, float, float | None, str | None, str | None, int] | None:
    found: list[tuple[str, float, float | None, str | None, str | None, int]] = []
    for index, (header, cell) in enumerate(zip(headers, cells, strict=False)):
        if index in excluded:
            continue
        for value in (cell, header):
            parsed = _parse_table_test_expression(value)
            if parsed is not None:
                found.append((*parsed, index))
                break
        if _is_test_header(header):
            label = _test_type_label(cell)
            if label:
                df_values = _table_df_values(headers, cells, excluded=excluded | {index})
                df1, df2 = _dfs_for_test(label, df_values)
                if df1 is not None:
                    found.append((label, df1, df2, None, None, index))
    unique = {
        (kind, df1, df2, comp, stat, index): (kind, df1, df2, comp, stat, index)
        for kind, df1, df2, comp, stat, index in found
    }
    return next(iter(unique.values())) if len(unique) == 1 else None


def _parse_table_test_expression(
    value: str,
) -> tuple[str, float, float | None, str | None, str | None] | None:
    for test_type, pattern in _TABLE_TEST_PATTERNS:
        match = pattern.fullmatch(value)
        if not match:
            continue
        groups = match.groups()
        if test_type == "F":
            df1_s, df2_s, comp, stat_s = groups
            return test_type, float(df1_s), float(df2_s), comp, stat_s
        if test_type == "z":
            comp, stat_s = groups
            return test_type, 0.0, None, comp, stat_s
        df1_s, comp, stat_s = groups
        return test_type, float(df1_s), None, comp, stat_s
    return None


def _table_df_values(headers: tuple[str, ...], cells: tuple[str, ...], *, excluded: set[int]) -> list[float]:
    values: list[float] = []
    df_columns = [index for index, header in enumerate(headers) if index not in excluded and _is_df_header(header)]
    for index in df_columns:
        values.extend(float(value) for value in _TABLE_DF_VALUE.findall(cells[index]))
    return values


def _dfs_for_test(test_type: str, values: list[float]) -> tuple[float | None, float | None]:
    if test_type == "z":
        return 0.0, None
    if test_type == "F":
        return (values[0], values[1]) if len(values) == 2 else (None, None)
    return (values[0], None) if len(values) == 1 else (None, None)


def _header_key(value: str) -> str:
    return re.sub(r"[^a-z0-9χ²]+", " ", value.casefold()).strip()


def _is_p_header(value: str) -> bool:
    key = _header_key(value)
    return key in {"p", "p value", "pvalue", "probability", "sig", "significance"} or key.startswith("p value ")


def _is_df_header(value: str) -> bool:
    key = _header_key(value)
    return key in {"df", "df1", "df2", "degrees freedom", "degrees of freedom"} or key.startswith("df ")


def _is_test_header(value: str) -> bool:
    return _header_key(value) in {"test", "test type", "statistical test"}


def _is_stat_header(value: str) -> bool:
    key = _header_key(value)
    return key in {"statistic", "test statistic", "stat", "value"} or _test_type_label(value) is not None


def _test_type_label(value: str) -> str | None:
    key = _header_key(value)
    if key in {"t", "t value", "t statistic"}:
        return "t"
    if key in {"f", "f value", "f statistic"}:
        return "F"
    if key in {"r", "r value", "correlation r"}:
        return "r"
    if key in {"z", "z value", "z statistic"}:
        return "z"
    if key in {"χ²", "χ2", "x²", "x2", "chi2", "chi square", "chi squared"}:
        return "chi2"
    return None


def _is_numeric_stat_cell(value: str) -> bool:
    return _TABLE_STAT_VALUE.fullmatch(value) is not None


def _normalize_comparator(comp: str) -> str:
    return {"≤": "<", "≥": ">"}.get(comp, comp)


def _table_text(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()
