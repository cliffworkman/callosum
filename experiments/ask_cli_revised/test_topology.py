"""The six approved Wave-1 topologies as pinned role bindings (W / R / C / P), validated, with no inference."""

import unittest

from experiments.ask_cli_revised import execution_policy as policy
from experiments.ask_cli_revised import topology as topo

Q25 = topo.Binding("managed_local", "callosum-managed-local")


def summary(name):
    """(kind, model) per role, the shape the approved plan tabulates."""
    profile = topo.WAVE1[name]
    return {
        role: (b.kind, b.model) for role, b in (("W", profile.W), ("R", profile.R), ("C", profile.C), ("P", profile.P))
    }


class Wave1BindingTests(unittest.TestCase):
    def test_the_six_arms_and_no_others(self):
        self.assertEqual(list(topo.WAVE1), ["T0", "T1", "T2", "T3", "T4", "T5"])

    def test_t0_repaired_q25_baseline(self):
        self.assertEqual(
            summary("T0"),
            {
                "W": ("managed_local", "callosum-managed-local"),
                "R": ("managed_local", "callosum-managed-local"),
                "C": ("det", None),
                "P": ("legacy", None),
            },
        )

    def test_t1_q25_plus_qwen35_uses_qwen35_only_where_earned(self):
        self.assertEqual(
            summary("T1"),
            {
                "W": ("managed_local", "callosum-managed-local"),
                "R": ("ollama", "qwen3.5:9b"),
                "C": ("det", None),
                "P": ("ollama", "qwen3.5:9b"),
            },
        )

    def test_t2_changes_only_the_worker_relative_to_t1(self):
        t1, t2 = summary("T1"), summary("T2")
        self.assertEqual(t2["W"], ("ollama", "qwen3.5:9b"))
        self.assertEqual({r: t2[r] for r in "RCP"}, {r: t1[r] for r in "RCP"})

    def test_t3_and_t4_change_only_the_supervisory_model_relative_to_t2(self):
        t2 = summary("T2")
        for name, model in (("T3", "gemma3:12b"), ("T4", "gpt-oss:20b")):
            with self.subTest(arm=name):
                arm = summary(name)
                self.assertEqual(arm["W"], t2["W"])
                self.assertEqual(arm["C"], ("det", None))  # neither Gemma's failed C nor an unqualified C is bound
                self.assertEqual(arm["R"], ("ollama", model))
                self.assertEqual(arm["P"], ("ollama", model))

    def test_t5_star_role_specialist_gives_the_c_and_p_specialists_a_worker_that_yields_evidence(self):
        # Amended 2026-09-24: the repaired Q2.5 gate discards ~95% of packets, leaving phi4 nothing to audit.
        self.assertEqual(topo.WAVE1["T5"].name, "T5*")  # Windows-safe key "T5"; the manifest names it T5*
        self.assertEqual(
            summary("T5"),
            {
                "W": ("ollama", "qwen3.5:9b"),
                "R": ("off", None),
                "C": ("ollama", "phi4:14b"),
                "P": ("ollama", "gemma3:12b"),
            },
        )
        self.assertEqual(
            {b.endpoint for b in (topo.WAVE1["T5"].W, topo.WAVE1["T5"].C, topo.WAVE1["T5"].P)}, {"isolated"}
        )

    def test_no_arm_binds_qwen35_to_coverage_audit(self):
        for name, profile in topo.WAVE1.items():
            with self.subTest(arm=name):
                self.assertFalse(profile.C.model and profile.C.model.startswith("qwen3.5"))

    def test_no_noncausal_r_is_bound_where_a_model_audits_coverage(self):
        for name, profile in topo.WAVE1.items():
            if profile.C.kind == "ollama":
                self.assertEqual(profile.R.kind, "off", name)

    def test_every_det_coverage_arm_has_a_causal_r(self):
        for name, profile in topo.WAVE1.items():
            if profile.C.kind == "det":
                self.assertNotEqual(profile.R.kind, "off", name)

    def test_qwen35_workers_run_with_thinking_off(self):
        for name in ("T2", "T3", "T4", "T5"):
            self.assertIs(topo.WAVE1[name].W.think, False)

    def test_supervisory_models_use_their_native_reasoning_default(self):
        self.assertIs(topo.WAVE1["T1"].R.think, True)  # qwen3.5
        self.assertEqual(topo.WAVE1["T4"].R.think, "medium")  # gpt-oss
        self.assertIsNone(topo.WAVE1["T3"].R.think)  # gemma (no thinking capability)
        self.assertIsNone(topo.WAVE1["T5"].C.think)  # phi4

    def test_only_qwen35_recovery_planning_gets_the_larger_allowance(self):
        for name, profile in topo.WAVE1.items():
            if profile.P.kind != "ollama":
                continue
            with self.subTest(arm=name):
                allowance = policy.generation_allowance(
                    topo.SUPERVISOR_BASE_OPTIONS, profile.P.model, policy.RECOVERY_PLANNING
                )
                self.assertEqual(allowance, 8192 if profile.P.model.startswith("qwen3.5") else 4096)

    def test_the_base_options_match_the_bakeoff_envelope_without_importing_it(self):
        self.assertEqual(
            topo.SUPERVISOR_BASE_OPTIONS,
            {"num_ctx": 12288, "num_predict": 4096, "temperature": 0, "seed": 42, "num_thread": 6, "num_batch": 512},
        )

    def test_the_profiles_hold_no_secrets_or_paths(self):
        text = repr(topo.WAVE1) + repr(topo.ENDPOINTS)
        for forbidden in ("password", "token", "C:\\", "sk-"):
            self.assertNotIn(forbidden, text)

    def test_endpoints_are_loopback_only(self):
        for url in topo.ENDPOINTS.values():
            self.assertTrue(url.startswith("http://127.0.0.1:"), url)


class ValidationTests(unittest.TestCase):
    def profile(self, **roles):
        base = {"W": Q25, "R": Q25, "C": topo.Binding("det"), "P": topo.Binding("legacy")}
        base.update(roles)
        return topo.Profile(name="X", **base)

    def test_a_valid_profile_passes(self):
        topo.validate(self.profile())

    def test_the_worker_cannot_be_off(self):
        with self.assertRaises(ValueError):
            topo.validate(self.profile(W=topo.Binding("off")))

    def test_a_model_coverage_audit_with_a_causal_r_is_rejected_as_a_wasted_stage(self):
        with self.assertRaises(ValueError):
            topo.validate(self.profile(C=topo.Binding("ollama", "phi4:14b", endpoint="isolated")))

    def test_det_coverage_without_r_is_rejected(self):
        with self.assertRaises(ValueError):
            topo.validate(self.profile(R=topo.Binding("off")))

    def test_unknown_kinds_are_rejected(self):
        with self.assertRaises(ValueError):
            topo.validate(self.profile(P=topo.Binding("cloud", "gemini")))

    def test_an_ollama_binding_needs_a_model_and_a_known_endpoint(self):
        with self.assertRaises(ValueError):
            topo.validate(self.profile(P=topo.Binding("ollama", None, endpoint="isolated")))
        with self.assertRaises(ValueError):
            topo.validate(self.profile(P=topo.Binding("ollama", "gemma3:12b", endpoint="elsewhere")))


class ChildOverviewProfileTests(unittest.TestCase):
    """Stage B (child Overview, 2026-09-29 authorization): T5C is a distinct, additional profile;
    T5O stays exactly as it was."""

    def test_t5c_has_thinking_off_t5o_has_thinking_on_unchanged(self):
        self.assertFalse(topo.CHILD_OVERVIEW_PROFILES["T5C"].S.think)
        self.assertTrue(topo.OVERVIEW_PROFILES["T5O"].S.think)

    def test_t5c_and_t5o_share_the_same_w_r_c_p_as_t5(self):
        for role in ("W", "R", "C", "P"):
            self.assertEqual(getattr(topo.CHILD_OVERVIEW_PROFILES["T5C"], role), getattr(topo.WAVE1["T5"], role))
            self.assertEqual(getattr(topo.OVERVIEW_PROFILES["T5O"], role), getattr(topo.WAVE1["T5"], role))

    def test_t5c_uses_the_same_model_as_t5o_only_thinking_differs(self):
        self.assertEqual(topo.CHILD_OVERVIEW_PROFILES["T5C"].S.model, topo.OVERVIEW_PROFILES["T5O"].S.model)
        self.assertEqual(topo.CHILD_OVERVIEW_PROFILES["T5C"].S.endpoint, topo.OVERVIEW_PROFILES["T5O"].S.endpoint)

    def test_child_overview_options_reuse_the_tested_thinking_off_supervisory_options_not_the_thinking_on_ones(self):
        """CHILD_OVERVIEW_S_OPTIONS must NOT be OVERVIEW_S_OPTIONS -- that set's large num_predict and
        thinking-mode sampling are specifically justified for thinking-ON calls only (see topology.py's
        own comment); reusing them for thinking-off would carry an unexamined assumption forward."""
        self.assertEqual(topo.CHILD_OVERVIEW_S_OPTIONS, topo.SUPERVISOR_BASE_OPTIONS)
        self.assertNotEqual(topo.CHILD_OVERVIEW_S_OPTIONS["num_predict"], topo.OVERVIEW_S_OPTIONS["num_predict"])
        self.assertNotEqual(topo.CHILD_OVERVIEW_S_OPTIONS["temperature"], topo.OVERVIEW_S_OPTIONS["temperature"])

    def test_t5c_passes_validation(self):
        topo.validate(topo.CHILD_OVERVIEW_PROFILES["T5C"])


class ProfileResolutionTests(unittest.TestCase):
    """Release-gate step 5 (2026-09-30): CHILD_OVERVIEW_PROFILES existed and validated, but the shared
    discovery/resolution path -- what e2e.py's --profile argparse choices and e2e.main() itself both
    consult -- never learned about it, so T5C was unreachable by name despite being fully defined and
    correct. profile_names()/resolve_profile() must cover WAVE1, OVERVIEW_PROFILES, AND
    CHILD_OVERVIEW_PROFILES generically, with no special-casing of any one profile name."""

    def test_profile_names_includes_every_registry_including_child_overview(self):
        names = topo.profile_names()
        self.assertEqual(set(names), set(topo.WAVE1) | set(topo.OVERVIEW_PROFILES) | set(topo.CHILD_OVERVIEW_PROFILES))
        self.assertIn("T5C", names)

    def test_resolve_profile_returns_the_actual_child_overview_profile_object(self):
        self.assertIs(topo.resolve_profile("T5C"), topo.CHILD_OVERVIEW_PROFILES["T5C"])

    def test_resolve_profile_t5c_has_the_expected_s_binding(self):
        resolved = topo.resolve_profile("T5C")
        self.assertEqual(resolved.S.kind, "ollama")
        self.assertEqual(resolved.S.model, "qwen3.5:9b")
        self.assertIs(resolved.S.think, False)

    def test_existing_resolution_is_unchanged_for_every_prior_profile(self):
        for name, profile in {**topo.WAVE1, **topo.OVERVIEW_PROFILES}.items():
            with self.subTest(name=name):
                self.assertIs(topo.resolve_profile(name), profile)

    def test_t5o_thinking_on_is_unaffected_by_the_fix(self):
        self.assertIs(topo.resolve_profile("T5O").S.think, True)

    def test_an_unknown_name_still_raises(self):
        with self.assertRaises(KeyError):
            topo.resolve_profile("NOT-A-REAL-PROFILE")


if __name__ == "__main__":
    unittest.main()
