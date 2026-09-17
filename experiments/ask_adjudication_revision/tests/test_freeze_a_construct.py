import pytest

from experiments.ask_adjudication_revision.core import BoundaryError, sha
from experiments.ask_adjudication_revision.freeze_a_construct import verify_bound_files


def test_bound_file_hash_size_and_path(tmp_path):
    data = b"fabricated fixture only"
    (tmp_path / "fixture.txt").write_bytes(data)
    records = {"fixture.txt": {"sha256": sha(data), "bytes": len(data)}}
    verify_bound_files(tmp_path, records)
    (tmp_path / "fixture.txt").write_bytes(b"fabricated mutation")
    with pytest.raises(BoundaryError, match="FINAL_ARTIFACT_HASH"):
        verify_bound_files(tmp_path, records)
    with pytest.raises(BoundaryError, match="BOUND_ARTIFACT_PATH"):
        verify_bound_files(tmp_path, {"../outside.txt": {"sha256": "", "bytes": 0}})
