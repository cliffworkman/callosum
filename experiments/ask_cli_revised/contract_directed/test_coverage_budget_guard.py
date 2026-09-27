import json
import socket
import tempfile
import unittest
from pathlib import Path

from experiments.ask_cli_revised.contract_directed import budget, coverage, endpoint_guard, freeze

DATA_PRESENT = (freeze.AB_ROOT / "runB" / "out" / "01_request_contract.json").is_file()


def usable(pid, child_id="c5", **units):
    per_unit = {
        uid: {"status": status, "missing": [], "reasons": [], "polarity": pol} for uid, (status, pol) in units.items()
    }
    return {
        "state": "usable",
        "packet_id": pid,
        "child_id": child_id,
        "route_relation": "own_route",
        "per_unit": per_unit,
    }


SEARCH = {
    "papers_nominated": 25,
    "papers_inspected": 6,
    "neighborhoods_read": 18,
    "budget_capped": 0,
    "no_answer_calls": 0,
}


@unittest.skipUnless(DATA_PRESENT, "frozen private run data not present on this machine")
class CoverageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sub = freeze.load_frozen()
        cls.c5 = cls.sub.child("c5")

    def rows(self, eligibility, search=None):
        return {r["unit_id"]: r for r in coverage.coverage_rows(self.c5, eligibility, search=search or SEARCH)}

    def test_a_closing_packet_attaches_the_unit_and_a_partial_one_does_not(self):
        rows = self.rows(
            [
                usable("k1", M5=("directly_establishes", "association"), M6=("not_addressed", None)),
                usable("k2", M5=("partially_establishes", None), M6=("partially_establishes", None)),
            ]
        )
        self.assertEqual(rows["M5"]["state"], coverage.ATTACHED)
        self.assertEqual(rows["M5"]["closing_packet_ids"], ["k1"])
        self.assertEqual(rows["M6"]["state"], coverage.PARTIAL_ONLY)
        self.assertEqual(rows["M6"]["partial_packet_ids"], ["k2"])

    def test_partial_evidence_never_resolves_a_unit(self):
        rows = self.rows([usable("k2", M5=("partially_establishes", None), M6=("partially_establishes", None))])
        self.assertNotEqual(rows["M5"]["state"], coverage.ATTACHED)

    def test_the_four_unresolved_causes_stay_distinct(self):
        none = [usable("k1", M5=("not_addressed", None), M6=("not_addressed", None))]
        self.assertEqual(self.rows(none)["M5"]["state"], coverage.UNRESOLVED_SEARCHED)
        self.assertEqual(self.rows(none, {**SEARCH, "budget_capped": 4})["M5"]["state"], coverage.UNRESOLVED_BUDGET)
        failed = none + [{"state": "no_answer", "packet_id": "k9", "outcome": "capped_at_allowance"}]
        self.assertEqual(self.rows(failed)["M5"]["state"], coverage.UNRESOLVED_MECHANICAL)
        self.assertEqual(
            self.rows(none, {**SEARCH, "no_answer_calls": 2})["M5"]["state"], coverage.UNRESOLVED_MECHANICAL
        )

    def test_conditions_mirror_their_parent_and_are_never_closed_alone(self):
        rows = coverage.coverage_rows(
            self.c5, [usable("k1", M5=("directly_establishes", "none"), M6=("not_addressed", None))], search=SEARCH
        )
        conditions = [r for r in rows if r["row_type"] == "condition"]
        self.assertEqual({r["unit_id"] for r in conditions}, {"C4", "C5"})
        for r in conditions:
            self.assertEqual(r["parent_unit_id"], "M5")
            self.assertEqual(r["state"], coverage.ATTACHED)
            self.assertEqual(r["polarity_values_seen"], ["none"])
            self.assertEqual(r["completeness"], "not_certified")

    def test_completeness_is_never_certified(self):
        for row in coverage.coverage_rows(self.c5, [], search=SEARCH):
            self.assertEqual(row["completeness"], "not_certified")

    def test_a_child_is_given_closing_packets_first_then_partial_and_never_unrelated_ones(self):
        elig = [
            usable("kp", M5=("partially_establishes", None), M6=("not_addressed", None)),
            usable("kc", M5=("directly_establishes", "association"), M6=("not_addressed", None)),
            usable("kn", M5=("not_addressed", None), M6=("not_addressed", None)),
        ]
        packets = {pid: {"packet_id": pid, "paper_id": 1} for pid in ("kp", "kc", "kn")}
        self.assertEqual([p["packet_id"] for p in coverage.child_evidence(self.c5, packets, elig)], ["kc", "kp"])

    def test_the_assignment_matrix_records_route_relation_and_mechanical_failures(self):
        good = usable("k1", M5=("directly_establishes", "association"), M6=("not_addressed", None))
        good["route_relation"] = "cross_child"
        bad = {"state": "no_answer", "packet_id": "k1", "outcome": "unparseable"}
        matrix = coverage.assignment_matrix(["c5", "c6"], {"c5": [good], "c6": [bad]})
        self.assertEqual(matrix["k1"]["c5"]["route_relation"], "cross_child")
        self.assertEqual(matrix["k1"]["c6"]["outcome"], "unparseable")


class BudgetTests(unittest.TestCase):
    def test_worst_case_is_computed_from_the_caps_and_within_the_ceilings(self):
        pilot = budget.run_budget(list(budget.PILOT_CHILDREN), budget.PILOT_CAPS, budget.PILOT_CEILINGS)
        wc = pilot["worst_case"]
        self.assertEqual((wc["triage"], wc["localization"], wc["eligibility"], wc["answers"]), (125, 135, 200, 5))
        self.assertEqual(wc["worst_case_total_calls"], 465)
        self.assertTrue(pilot["within_ceilings"])
        full = budget.run_budget(list(freeze.CHILD_IDS), budget.FULL_CAPS, budget.FULL_CEILINGS)
        self.assertEqual(full["worst_case"]["worst_case_total_calls"], 275 + 297 + 660 + 11)
        self.assertTrue(full["within_ceilings"])

    def test_neighborhood_cap_is_derived_not_chosen(self):
        caps = budget.Caps()
        self.assertEqual(caps.neighborhoods, caps.inspected_papers * (1 + 2))

    def test_a_run_whose_worst_case_exceeds_its_ceiling_is_flagged(self):
        b = budget.run_budget(list(budget.PILOT_CHILDREN), budget.PILOT_CAPS, {"max_calls": 100, "wall_seconds": 60})
        self.assertFalse(b["within_ceilings"])


class AuthorizationTests(unittest.TestCase):
    def setUp(self):
        self.budget = budget.run_budget(list(budget.PILOT_CHILDREN), budget.PILOT_CAPS, budget.PILOT_CEILINGS)
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "auth.json"

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, **over):
        auth = budget.authorization_template("pilot-1", self.budget) | over
        self.path.write_text(json.dumps(auth), encoding="utf-8")

    def check(self):
        return budget.check_authorization(self.path, self.budget, experiment_id="pilot-1")

    def test_a_template_is_refused_until_the_brief_is_confirmed_and_signed(self):
        self.write()
        with self.assertRaises(budget.AuthorizationRefused) as ctx:
            self.check()
        self.assertIn("brief_confirmed", str(ctx.exception))

    def test_a_confirmed_file_covering_exactly_this_run_is_accepted(self):
        self.write(brief_confirmed=True, authorized_by="Cliff", authorized_at="2026-09-27T00:00:00-04:00")
        self.assertEqual(self.check()["experiment_id"], "pilot-1")

    def test_a_different_experiment_more_children_or_higher_caps_are_refused(self):
        signed = {"brief_confirmed": True, "authorized_by": "Cliff", "authorized_at": "now"}
        self.write(**signed, experiment_id="another")
        with self.assertRaises(budget.AuthorizationRefused):
            self.check()
        self.write(**signed, children=["c5"])
        with self.assertRaises(budget.AuthorizationRefused):
            self.check()
        self.write(**signed, ceilings={"max_calls": 10, "wall_seconds": 10})
        with self.assertRaises(budget.AuthorizationRefused):
            self.check()

    def test_no_file_is_refused(self):
        with self.assertRaises(budget.AuthorizationRefused):
            budget.check_authorization(Path(self.tmp.name) / "missing.json", self.budget, experiment_id="pilot-1")


class EndpointGuardTests(unittest.TestCase):
    def attempt(self, address):
        s = socket.socket()
        s.settimeout(0.2)
        try:
            s.connect(address)
        finally:
            s.close()

    def test_isolated_only_refuses_the_shared_endpoint_and_every_other_host(self):
        with endpoint_guard.isolated_only():
            for address in (("127.0.0.1", 11434), ("10.0.0.123", 22), ("93.184.216.34", 443), ("localhost", 11434)):
                with self.assertRaises(endpoint_guard.EndpointRefused):
                    self.attempt(address)
            with self.assertRaises(endpoint_guard.EndpointRefused):
                socket.getaddrinfo("example.com", 443)

    def test_isolated_only_lets_the_isolated_endpoint_through_to_the_real_socket(self):
        with endpoint_guard.isolated_only():
            try:
                self.attempt(("127.0.0.1", 11435))
            except endpoint_guard.EndpointRefused:
                self.fail("the isolated endpoint must not be refused by the guard")
            except OSError:
                pass  # nothing listening here (or a real Ollama): not the guard's business

    def test_refuse_all_refuses_even_loopback_and_the_patch_is_removed_on_exit(self):
        with endpoint_guard.refuse_all():
            with self.assertRaises(endpoint_guard.EndpointRefused):
                self.attempt(("127.0.0.1", 11435))
        try:
            self.attempt(("127.0.0.1", 9))
        except endpoint_guard.EndpointRefused:
            self.fail("the guard must be removed on exit")
        except OSError:
            pass


if __name__ == "__main__":
    unittest.main()
