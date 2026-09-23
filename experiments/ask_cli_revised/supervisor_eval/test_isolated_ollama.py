"""The isolated bakeoff Ollama: its commands must never touch the shared service or leave /media/brain/JUNO.

Pure command-building and parsing only. The shared Ollama (port 11434, /usr/share/ollama, systemd) is off
limits: no sudo, no systemctl, no shared port, no shared store.
"""

import unittest

from experiments.ask_cli_revised.supervisor_eval import isolated_ollama as iso

SHA = "e8" * 32
RELEASE = {
    "tag_name": "v0.34.3",
    "prerelease": False,
    "draft": False,
    "assets": [
        {
            "name": "ollama-linux-amd64-rocm.tar.zst",
            "size": 1,
            "browser_download_url": "https://github.com/ollama/ollama/releases/download/v0.34.3/ollama-linux-amd64-rocm.tar.zst",
            "digest": "sha256:" + "0b" * 32,
        },
        {
            "name": "ollama-linux-amd64.tar.zst",
            "size": 1427400000,
            "browser_download_url": "https://github.com/ollama/ollama/releases/download/v0.34.3/ollama-linux-amd64.tar.zst",
            "digest": "sha256:" + SHA,
        },
        {
            "name": "ollama-linux-amd64-mlx.tar.zst",
            "size": 2,
            "browser_download_url": "https://github.com/ollama/ollama/releases/download/v0.34.3/ollama-linux-amd64-mlx.tar.zst",
            "digest": "sha256:" + "1d" * 32,
        },
    ],
}


def _asset():
    return iso.pick_asset(RELEASE)


class PickAssetTests(unittest.TestCase):
    def test_picks_the_plain_linux_amd64_build_not_rocm_or_mlx(self):
        a = _asset()
        self.assertEqual(a["name"], "ollama-linux-amd64.tar.zst")
        self.assertEqual(a["tag"], "v0.34.3")
        self.assertEqual(a["sha256"], SHA)
        self.assertEqual(a["size"], 1427400000)

    def test_a_prerelease_or_draft_is_refused(self):
        for flag in ("prerelease", "draft"):
            with self.assertRaises(ValueError):
                iso.pick_asset({**RELEASE, flag: True})

    def test_an_asset_without_a_published_digest_is_refused(self):
        bad = {**RELEASE, "assets": [{**RELEASE["assets"][1], "digest": None}]}
        with self.assertRaises(ValueError):
            iso.pick_asset(bad)

    def test_a_download_url_off_the_ollama_release_path_is_refused(self):
        evil = dict(RELEASE["assets"][1], browser_download_url="https://evil.example.com/ollama-linux-amd64.tar.zst")
        with self.assertRaises(ValueError):
            iso.pick_asset({**RELEASE, "assets": [evil]})

    def test_a_non_stable_tag_is_refused(self):
        with self.assertRaises(ValueError):
            iso.pick_asset({**RELEASE, "tag_name": "v0.34.3; rm -rf /"})


class LayoutTests(unittest.TestCase):
    def test_the_store_is_the_dedicated_path_under_the_big_disk(self):
        self.assertEqual(iso.MODELS_DIR, "/media/brain/JUNO/ollama-models/ask-070-bakeoff")

    def test_it_listens_on_its_own_loopback_port_not_the_shared_one(self):
        self.assertEqual(iso.PORT, 11435)
        self.assertNotEqual(iso.PORT, 11434)

    def test_the_install_dir_is_versioned_so_a_new_release_cannot_replace_a_running_binary(self):
        self.assertTrue(iso.install_dir("v0.34.3").endswith("/ollama-v0.34.3"))
        self.assertTrue(iso.binary_path("v0.34.3").endswith("/ollama-v0.34.3/bin/ollama"))


class CommandSafetyTests(unittest.TestCase):
    def _all(self):
        a = _asset()
        return [
            iso.download_command(a),
            iso.sha256_command(a),
            iso.extract_command(a),
            iso.start_command(a["tag"]),
            iso.stop_command(4242),
            iso.env_probe_command(4242),
            iso.store_probe_command(),
            iso.identity_command(a["tag"]),
            iso.log_tail_command(),
            iso.pid_command(),
        ]

    def test_no_command_touches_the_shared_service_or_needs_privilege(self):
        for cmd in self._all():
            for forbidden in ("sudo", "systemctl", "service ", "/usr/share/ollama", ":11434", "/etc/", "chown"):
                self.assertNotIn(forbidden, cmd, f"{forbidden!r} in {cmd[:60]}")

    def test_no_command_contains_a_double_quote(self):
        for cmd in self._all():
            self.assertNotIn('"', cmd)

    def test_every_absolute_path_stays_under_the_big_disk(self):
        import re

        for cmd in self._all():
            filesystem_only = re.sub(r"https://\S+", "", cmd)  # a download URL is not a filesystem path
            for path in re.findall(r"(?<![\w.:])/[A-Za-z0-9_./-]+", filesystem_only):
                allowed = path.startswith("/media/brain/JUNO") or path == "/dev/null" or path.startswith("/proc/")
                self.assertTrue(allowed, f"{path} in {cmd[:80]}")

    def test_start_command_builds_a_fully_isolated_server_environment(self):
        cmd = iso.start_command("v0.34.3")
        for needle in (
            "OLLAMA_HOST=127.0.0.1:11435",
            f"OLLAMA_MODELS={iso.MODELS_DIR}",
            "OLLAMA_MAX_LOADED_MODELS=1",
            "OLLAMA_NUM_PARALLEL=1",
            f"HOME={iso.HOME_DIR}",
            f"TMPDIR={iso.TMP_DIR}",
            "setsid nohup",
            iso.binary_path("v0.34.3") + " serve",
        ):
            self.assertIn(needle, cmd)
        self.assertTrue(cmd.rstrip().endswith("tee " + iso.PID_FILE))

    def test_download_uses_the_verified_asset_url_and_a_bounded_path(self):
        a = _asset()
        cmd = iso.download_command(a)
        self.assertIn(a["url"], cmd)
        self.assertIn(f"{iso.DL_DIR}/{a['name']}", cmd)

    def test_extract_decompresses_with_zstd_into_the_versioned_dir(self):
        cmd = iso.extract_command(_asset())
        self.assertIn("zstd -dc", cmd)
        self.assertIn(iso.install_dir("v0.34.3"), cmd)

    def test_stop_command_kills_only_an_integer_pid(self):
        self.assertEqual(iso.stop_command(4242), "kill 4242")
        for bad in ("4242; rm -rf /", None, "abc"):
            with self.assertRaises(ValueError):
                iso.stop_command(bad)

    def test_an_unsafe_tag_cannot_reach_a_shell(self):
        for bad in ("v0.34.3; id", "../x", "v 1"):
            with self.assertRaises(ValueError):
                iso.start_command(bad)


class ParseTests(unittest.TestCase):
    def test_verify_digest_compares_the_hash_sha256sum_reports(self):
        a = _asset()
        self.assertTrue(iso.verify_digest(a, f"{SHA}  {iso.DL_DIR}/{a['name']}\n"))
        self.assertFalse(iso.verify_digest(a, f"{'00' * 32}  {iso.DL_DIR}/{a['name']}\n"))
        self.assertFalse(iso.verify_digest(a, "sha256sum: no such file"))

    def test_parse_env_keeps_only_ollama_variables(self):
        env = iso.parse_env("OLLAMA_HOST=127.0.0.1:11435\nOLLAMA_MODELS=/media/brain/JUNO/x\nSECRET=hunter2\nHOME=/h\n")
        self.assertEqual(env, {"OLLAMA_HOST": "127.0.0.1:11435", "OLLAMA_MODELS": "/media/brain/JUNO/x"})

    def test_parse_identity_extracts_version_binary_hash_and_driver(self):
        text = (
            "ollama version is 0.34.3\n---\n"
            + f"{SHA}  /media/brain/JUNO/ollama-bakeoff/ollama-v0.34.3/bin/ollama\n---\n535.309.01\n"
        )
        ident = iso.parse_identity(text)
        self.assertEqual(ident["binary_version"], "0.34.3")
        self.assertEqual(ident["binary_sha256"], SHA)
        self.assertEqual(ident["nvidia_driver"], "535.309.01")

    def test_unparseable_identity_is_empty_not_a_crash(self):
        self.assertEqual(iso.parse_identity("boom"), {})

    def test_gpu_backend_is_read_from_the_server_log(self):
        log = 'time=... level=INFO source=types.go msg="inference compute" id=GPU-abc library=CUDA compute=8.6 name=CUDA0 total="8.0 GiB" available="7.6 GiB"\n'
        self.assertEqual(iso.parse_gpu_backend(log)["library"], "CUDA")
        self.assertEqual(iso.parse_gpu_backend("no gpu lines here"), {})


if __name__ == "__main__":
    unittest.main()
