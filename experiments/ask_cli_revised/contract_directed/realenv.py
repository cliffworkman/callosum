"""Shared lazy handles on the real disposable library + embedding retriever for integration tests (built once per process)."""

from __future__ import annotations

import os

os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

from experiments.ask_cli_revised.contract_directed import freeze  # noqa: E402
from experiments.ask_cli_revised.contract_directed.retriever import Retriever  # noqa: E402
from experiments.ask_cli_revised.contract_directed.store import Library  # noqa: E402

DB = freeze.SLICE_ROOT / "library.sqlite"
_CACHE: dict = {}


def available() -> bool:
    return DB.is_file() and (freeze.AB_ROOT / "runB" / "out" / "01_request_contract.json").is_file()


def library() -> Library:
    if "library" not in _CACHE:
        _CACHE["library"] = Library(DB)
    return _CACHE["library"]


def retriever() -> Retriever:
    if "retriever" not in _CACHE:
        _CACHE["retriever"] = Retriever(library())
    return _CACHE["retriever"]


def substrate():
    if "substrate" not in _CACHE:
        _CACHE["substrate"] = freeze.load_frozen()
    return _CACHE["substrate"]
