"""Support for valid runs: a fixed, verified library copy, a clean code tree, and a runtime that needs no Q2.5 when unused."""

import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from experiments.ask_cli_revised import e2e, provenance
from experiments.ask_cli_revised import library_copy as lib
from experiments.ask_cli_revised import runtime as runtime_mod


def make_db(path, *, papers=3, chunks=5):
    con = sqlite3.connect(path)
    con.execute("create table papers (id integer primary key, deleted_at text)")
    con.execute("create table attachments (id integer primary key)")
    con.execute("create table chunks (id integer primary key)")
    con.execute("create table chunk_structure (id integer primary key)")
    con.execute("create table embeddings (id integer primary key)")
    con.execute("create table cluster_node_papers (id integer primary key)")
    con.executemany(
        "insert into papers (id, deleted_at) values (?, ?)",
        [(i, "x" if i == 1 else None) for i in range(1, papers + 1)],
    )
    con.executemany("insert into chunks (id) values (?)", [(i,) for i in range(1, chunks + 1)])
    con.commit()
    con.close()


class LibraryCopyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.db = Path(self.tmp.name) / "copy.sqlite"
        self.frozen = Path(self.tmp.name) / "copy.fingerprint.json"
        make_db(self.db)

    def test_the_fingerprint_records_counts_ids_and_a_whole_file_hash(self):
        fp = lib.fingerprint(self.db)
        self.assertEqual(fp["counts"]["papers"], 3)
        self.assertEqual(fp["counts"]["chunks"], 5)
        self.assertEqual(fp["deleted_papers"], 1)
        self.assertEqual(fp["max_chunk_id"], 5)
        self.assertEqual(len(fp["sha256"]), 64)
        self.assertEqual(fp["wal_bytes"], 0)

    def test_the_fingerprint_is_stable_across_readings(self):
        self.assertEqual(lib.fingerprint(self.db), lib.fingerprint(self.db))

    def test_a_frozen_copy_verifies_and_any_change_is_detected(self):
        lib.freeze(self.db, self.frozen)
        lib.verify(self.db, self.frozen)
        con = sqlite3.connect(self.db)
        con.execute("insert into chunks (id) values (99)")
        con.commit()
        con.close()
        with self.assertRaises(lib.LibraryCopyDrift):
            lib.verify(self.db, self.frozen)

    def test_verification_never_writes_to_the_copy(self):
        lib.freeze(self.db, self.frozen)
        before = self.db.read_bytes()
        lib.verify(self.db, self.frozen)
        self.assertEqual(self.db.read_bytes(), before)

    def test_a_missing_copy_or_fingerprint_fails_closed(self):
        with self.assertRaises(lib.LibraryCopyDrift):
            lib.verify(Path(self.tmp.name) / "absent.sqlite", self.frozen)
        with self.assertRaises(lib.LibraryCopyDrift):
            lib.verify(self.db, Path(self.tmp.name) / "absent.json")

    def test_the_stored_fingerprint_holds_no_text_and_no_paths(self):
        lib.freeze(self.db, self.frozen)
        text = self.frozen.read_text(encoding="utf-8")
        self.assertNotIn(self.tmp.name, text)
        self.assertEqual(
            set(json.loads(text)),
            {"counts", "deleted_papers", "max_chunk_id", "max_paper_id", "size_bytes", "sha256", "wal_bytes"},
        )


class LibraryCopyCliTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.db = Path(self.tmp.name) / "copy.sqlite"
        make_db(self.db)

    def test_freeze_then_verify_succeeds_and_defaults_the_fingerprint_next_to_the_copy(self):
        self.assertEqual(lib.main(["freeze", "--db", str(self.db)]), 0)
        self.assertTrue(Path(f"{self.db}.fingerprint.json").is_file())
        self.assertEqual(lib.main(["verify", "--db", str(self.db)]), 0)

    def test_verify_exits_nonzero_on_drift(self):
        lib.main(["freeze", "--db", str(self.db)])
        con = sqlite3.connect(self.db)
        con.execute("insert into chunks (id) values (77)")
        con.commit()
        con.close()
        self.assertEqual(lib.main(["verify", "--db", str(self.db)]), 1)


class E2eCliTests(unittest.TestCase):
    def parse(self, *extra):
        return e2e.parse_args(["--profile", "T0", "--question", "aib", "--db", "lib.sqlite", "--out", "out", *extra])

    def test_a_scored_run_is_the_default_and_the_fingerprint_defaults_next_to_the_copy(self):
        args = self.parse()
        self.assertFalse(args.smoke)
        self.assertEqual(args.library_frozen, "lib.sqlite.fingerprint.json")

    def test_smoke_selects_bounded_limits_that_leave_the_contract_alone(self):
        self.assertTrue(self.parse("--smoke").smoke)
        self.assertEqual(
            set(e2e.SMOKE_LIMITS),
            {"per_subq_paper_cap", "within_paper_top_k", "max_initial_subquestions", "max_recovery_gaps"},
        )

    def test_an_unknown_profile_or_question_is_rejected(self):
        with self.assertRaises(SystemExit):
            e2e.parse_args(["--profile", "T9", "--question", "aib", "--db", "x", "--out", "y"])
        with self.assertRaises(SystemExit):
            e2e.parse_args(["--profile", "T0", "--question", "nope", "--db", "x", "--out", "y"])


class GitStateTests(unittest.TestCase):
    def runner(self, outputs):
        def run(cmd, **kwargs):
            return SimpleNamespace(stdout=outputs[tuple(cmd[:3])], returncode=0)

        return run

    def state(self, status):
        outputs = {
            ("git", "rev-parse", "HEAD"): "abc123\n",
            ("git", "rev-parse", "--abbrev-ref"): "experiment/ask-e2e\n",
            ("git", "status", "--porcelain"): status,
        }
        return provenance.git_state(Path("."), runner=self.runner(outputs))

    def test_a_clean_tree_reports_the_exact_sha_and_branch(self):
        state = self.state("")
        self.assertEqual(state, {"sha": "abc123", "branch": "experiment/ask-e2e", "dirty_paths": []})
        provenance.assert_clean(state)

    def test_modified_or_untracked_source_makes_the_tree_dirty_and_blocks_a_scored_run(self):
        state = self.state(" M experiments/ask_cli_revised/qwen.py\n?? experiments/ask_cli_revised/new.py\n")
        self.assertEqual(
            state["dirty_paths"], ["experiments/ask_cli_revised/qwen.py", "experiments/ask_cli_revised/new.py"]
        )
        with self.assertRaises(provenance.DirtyTreeError):
            provenance.assert_clean(state)


class RuntimeWithoutQwenTests(unittest.TestCase):
    def build(self, **kwargs):
        with (
            patch.object(runtime_mod, "make_engine", return_value=MagicMock()),
            patch.object(runtime_mod, "ModelRuntimeRegistry", return_value=MagicMock()),
            patch.object(runtime_mod, "ProviderClientRuntime", return_value=MagicMock()),
            patch.object(runtime_mod, "SQLiteVecVectorStore", return_value=MagicMock()),
            patch.object(runtime_mod, "_resolve_qwen", return_value="QWEN") as resolve,
        ):
            rt = runtime_mod.build_runtime("copy.sqlite", want_verifier=False, **kwargs)
        return rt, resolve

    def test_the_default_still_resolves_managed_local_qwen(self):
        rt, resolve = self.build()
        resolve.assert_called_once()
        self.assertEqual(rt.qwen_config, "QWEN")

    def test_a_topology_with_no_managed_local_role_does_not_require_it(self):
        rt, resolve = self.build(want_qwen=False)
        resolve.assert_not_called()
        self.assertIsNone(rt.qwen_config)


if __name__ == "__main__":
    unittest.main()
