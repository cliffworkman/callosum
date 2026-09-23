"""JUNO resource sampling: pure command-building and parsing. No network, no credentials.

The password convention lives only in juno.ps1; nothing this module builds may contain a credential or a
double quote (double quotes do not survive PowerShell -> plink -> remote shell intact).
"""

import base64
import unittest

from experiments.ask_cli_revised.supervisor_eval import juno_resources as jr

SNAPSHOT = """4210, 8192, 37
               total        used        free      shared  buff/cache   available
Mem:           15990        4100        6200         200        5690       11300
Swap:           2047         120        1927
5120"""


class RemoteDirTests(unittest.TestCase):
    def test_scratch_lives_on_the_big_disk_as_directed(self):
        self.assertTrue(jr.REMOTE_DIR.startswith("/media/brain/JUNO/"))


class ParseSnapshotTests(unittest.TestCase):
    def test_parses_gpu_ram_swap_and_ollama_rss(self):
        s = jr.parse_snapshot(SNAPSHOT)
        self.assertEqual(
            s,
            {
                "gpu_mem_used_mib": 4210,
                "gpu_mem_total_mib": 8192,
                "gpu_util_pct": 37,
                "ram_used_mib": 4100,
                "ram_available_mib": 11300,
                "swap_used_mib": 120,
                "ollama_rss_mib": 5120,
            },
        )

    def test_garbage_yields_an_empty_snapshot_not_a_crash(self):
        self.assertEqual(jr.parse_snapshot("plink: connection refused"), {})


class SamplerCsvTests(unittest.TestCase):
    CSV = (
        "100.0,1000,10,3000,12000,0,900\n"
        "100.4,6800,90,3500,11500,0,1500\n"
        "100.8,7100,95,3600,11400,64,1600\n"
        "torn line with no commas\n"
        "101.2,7000,88,3550,11450,64,1550\n"
    )

    def test_summarizes_peaks_and_troughs(self):
        s = jr.summarize_samples(self.CSV)
        self.assertEqual(s["n_samples"], 4)
        self.assertEqual(s["peak_gpu_mem_mib"], 7100)
        self.assertEqual(s["peak_ram_used_mib"], 3600)
        self.assertEqual(s["min_ram_available_mib"], 11400)
        self.assertEqual(s["peak_swap_used_mib"], 64)
        self.assertEqual(s["peak_ollama_rss_mib"], 1600)

    def test_window_selects_only_samples_inside_it(self):
        s = jr.summarize_samples(self.CSV, start=100.3, end=100.9)
        self.assertEqual(s["n_samples"], 2)
        self.assertEqual(s["peak_gpu_mem_mib"], 7100)

    def test_empty_input_is_reported_honestly(self):
        self.assertEqual(jr.summarize_samples("")["n_samples"], 0)


class CommandSafetyTests(unittest.TestCase):
    def _all_commands(self):
        return [
            jr.SNAPSHOT_COMMAND,
            jr.deploy_command(),
            jr.start_command("qwen3.5-9b"),
            jr.stop_command(4242),
            jr.fetch_command("qwen3.5-9b"),
            jr.STORE_COMMAND,
        ]

    def test_no_command_contains_a_double_quote_or_a_credential_flag(self):
        for cmd in self._all_commands():
            self.assertNotIn('"', cmd)
            self.assertNotIn("-pw", cmd)
            self.assertNotIn("password", cmd.lower())

    def test_deploy_command_ships_the_sampler_script_as_base64(self):
        cmd = jr.deploy_command()
        payload = cmd.split("echo ", 1)[1].split(" |", 1)[0]
        self.assertEqual(base64.b64decode(payload).decode(), jr.sampler_script())
        self.assertIn("base64 -d", cmd)
        self.assertIn(jr.REMOTE_DIR, cmd)

    def test_start_command_detaches_and_reports_a_pid(self):
        cmd = jr.start_command("gemma3-12b")
        self.assertIn("setsid", cmd)
        self.assertIn("gemma3-12b", cmd)
        self.assertTrue(cmd.rstrip().endswith("echo $!"))

    def test_stop_command_kills_only_the_named_pid(self):
        self.assertEqual(jr.stop_command(4242), "kill 4242")
        with self.assertRaises(ValueError):
            jr.stop_command("4242; rm -rf /")

    def test_a_tag_cannot_smuggle_shell_syntax_into_a_path(self):
        for bad in ("x; rm -rf /", "../etc", "a b", "x$(id)"):
            with self.assertRaises(ValueError):
                jr.start_command(bad)

    def test_sampler_script_appends_one_csv_row_per_tick(self):
        script = jr.sampler_script()
        self.assertIn("nvidia-smi", script)
        self.assertIn("free -m", script)
        self.assertIn(">>", script)


STORE_OK = """Environment=OLLAMA_HOST=127.0.0.1:11434 OLLAMA_MODELS=/media/brain/JUNO/ollama/models
OLLAMA_MODELS=/media/brain/JUNO/ollama/models
---DF---
Filesystem     1G-blocks  Used Available Use% Mounted on
/dev/sdd1           118G   95G       18G  85% /
/dev/sda1          4700G 3600G     1100G  77% /media/brain/JUNO
---DU---
120G	/media/brain/JUNO/ollama/models"""


class AssessStoreTests(unittest.TestCase):
    def test_a_store_on_the_big_disk_with_room_is_ok(self):
        s = jr.assess_store(STORE_OK, needed_gb=14.0)
        self.assertTrue(s["ok"])
        self.assertEqual(s["store_path"], "/media/brain/JUNO/ollama/models")
        self.assertEqual(s["free_gb"], 1100.0)

    def test_a_store_that_is_too_full_for_the_model_is_not_ok(self):
        s = jr.assess_store(STORE_OK, needed_gb=1200.0)
        self.assertFalse(s["ok"])
        self.assertIn("free", s["reason"])

    def test_no_override_means_the_default_store_on_the_os_disk_and_is_not_ok(self):
        text = STORE_OK.replace("OLLAMA_MODELS=/media/brain/JUNO/ollama/models", "")
        s = jr.assess_store(text, needed_gb=9.0)
        self.assertFalse(s["ok"])
        self.assertIn("/media/brain/JUNO", s["reason"])

    def test_a_store_on_another_disk_violates_the_directive(self):
        text = STORE_OK.replace("/media/brain/JUNO/ollama/models", "/media/brain/HDD/ollama")
        s = jr.assess_store(text, needed_gb=9.0)
        self.assertFalse(s["ok"])
        self.assertEqual(s["store_path"], "/media/brain/HDD/ollama")

    def test_the_longest_matching_mount_decides_the_free_space(self):
        # /media/brain/JUNO has 1100G free; the root filesystem's 18G must not be used for it
        self.assertEqual(jr.assess_store(STORE_OK, needed_gb=20.0)["free_gb"], 1100.0)

    def test_unparseable_output_is_not_ok_and_says_why(self):
        s = jr.assess_store("plink: connection refused", needed_gb=9.0)
        self.assertFalse(s["ok"])
        self.assertIn("could not", s["reason"].lower())


class JunoSamplerTests(unittest.TestCase):
    CSV = (
        "100.0,1000,10,3000,12000,0,900\n100.4,6800,90,3500,11500,0,1500\n"
        "100.8,7100,95,3600,11400,64,1600\n101.2,7000,88,3550,11450,64,1550\n"
    )

    def _runner(self, log, fail_on=None):
        def run(cmd, **kw):
            log.append(cmd)
            if fail_on and cmd.startswith(fail_on):
                raise RuntimeError("remote command failed (255): connection refused")
            if cmd.startswith("setsid"):
                return "warning: something\n4242\n"
            if cmd.startswith("cat "):
                return self.CSV
            return ""

        return run

    def test_start_deploys_then_detaches_and_stop_kills_only_its_own_pid_and_summarizes(self):
        import tempfile
        from pathlib import Path

        log = []
        with tempfile.TemporaryDirectory() as tmp:
            s = jr.JunoSampler(run=self._runner(log), out_dir=Path(tmp))
            s.start("m-1b")
            summary = s.stop()
            self.assertEqual(log[0], jr.deploy_command())
            self.assertTrue(log[1].startswith("setsid"))
            self.assertIn("kill 4242", log)
            self.assertEqual(summary["n_samples"], 4)
            self.assertEqual(summary["peak_gpu_mem_mib"], 7100)
            self.assertEqual((Path(tmp) / "m-1b.csv").read_text(encoding="utf-8"), self.CSV)

    def test_a_sampler_that_cannot_start_degrades_to_an_honest_note_and_does_not_abort_the_run(self):
        log = []
        s = jr.JunoSampler(run=self._runner(log, fail_on="mkdir"))
        s.start("m-1b")  # must not raise
        summary = s.stop()
        self.assertEqual(summary["n_samples"], 0)
        self.assertIn("connection refused", summary["error"])
        self.assertFalse(any(c.startswith("kill") for c in log))  # nothing was started, so nothing is killed

    def test_stop_without_start_is_a_harmless_noop(self):
        self.assertEqual(jr.JunoSampler(run=self._runner([])).stop()["n_samples"], 0)


class ShellChoiceTests(unittest.TestCase):
    """juno.ps1 is unsigned: it runs under pwsh (RemoteSigned) but not under this machine's Windows PowerShell 5.1."""

    def test_prefers_pwsh_and_falls_back_to_windows_powershell(self):
        self.assertEqual(jr.shell_executable(which=lambda n: "C:/pwsh.exe" if n == "pwsh" else None), "pwsh")
        self.assertEqual(jr.shell_executable(which=lambda n: None), "powershell")


class RunRemoteTests(unittest.TestCase):
    def test_invokes_juno_ps1_and_returns_stdout(self):
        seen = {}

        class Done:
            returncode, stdout, stderr = 0, "ok\n", ""

        def runner(args, **kw):
            seen["args"] = args
            return Done()

        out = jr.run_remote("nvidia-smi", runner=runner, ps1="C:/x/juno.ps1")
        self.assertEqual(out, "ok\n")
        self.assertEqual(seen["args"][-2:], ["C:/x/juno.ps1", "nvidia-smi"])
        self.assertIn("-File", seen["args"])
        self.assertEqual(seen["args"][0], jr.shell_executable())

    def test_a_failing_remote_command_raises_with_stderr(self):
        class Bad:
            returncode, stdout, stderr = 255, "", "connection refused"

        with self.assertRaises(RuntimeError) as ctx:
            jr.run_remote("x", runner=lambda a, **k: Bad(), ps1="p")
        self.assertIn("connection refused", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
