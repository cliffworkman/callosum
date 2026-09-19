"""connector/identity.json is the single source of truth for browser-capture identity (#61 Phase 2,
steering point 1) -- these tests guard the things that would otherwise silently drift: the dev
extension id against the key it's derived from, the extension's hardcoded host-name constant
against identity.json, the NSIS generator's output against identity.json, and the extension's
permission set against creep. Nothing here talks to a browser or a real store.

Store-readiness additions (#61 Phase 1): the identity MECHANISM is proven with synthetic ids (real store ids
do not exist yet and none may be invented here) -- validation, exact `allowed_origins` generation, duplicate
and dev-leak rejection, one shared manifest for both browsers, and CI wiring that checks the built manifest
against identity.json instead of assuming it is empty.
"""

from __future__ import annotations

import base64
import functools
import hashlib
import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
IDENTITY_PATH = ROOT / "app" / "desktop-shell" / "connector" / "identity.json"
EXTENSION_DIR = ROOT / "app" / "desktop-shell" / "extension"
PACKAGING_DIR = ROOT / "app" / "desktop-shell" / "packaging"
GENERATOR_PATH = PACKAGING_DIR / "generate_connector_nsh.py"
INSTALLER_HOOKS = ROOT / "app" / "desktop-shell" / "src-tauri" / "windows" / "installer-hooks.nsh"
WORKFLOWS = ROOT / ".github" / "workflows"

_EXTENSION_ID_RE = re.compile(r"^[a-p]{32}$")

# Deliberate-change tripwire, NOT a release policy: the production allowlist must never be populated by a
# refactor or with a guessed id. When the stores confirm real ids, this list is updated in the SAME reviewed change
# that edits identity.json. (Release policy -- may a public release ship with none? -- is a separate decision.)
PINNED_PRODUCTION_EXTENSION_IDS: list[str] = []

# Synthetic ids: a-p alphabet only, distinct from the real dev id.
CHROME_STORE_ID = "c" * 32
EDGE_STORE_ID = "e" * 32


def _identity() -> dict:
    return json.loads(IDENTITY_PATH.read_text(encoding="utf-8"))


@functools.cache
def _connector_identity_module():
    spec = importlib.util.spec_from_file_location("connector_identity", PACKAGING_DIR / "connector_identity.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _chrome_extension_id(public_key_der_b64: str) -> str:
    der = base64.b64decode(public_key_der_b64)
    digest = hashlib.sha256(der).digest()[:16]
    return "".join(chr(ord("a") + (b >> 4)) + chr(ord("a") + (b & 0x0F)) for b in digest)


def _run_generator(tmp_path: Path, identity: dict) -> tuple[subprocess.CompletedProcess, Path]:
    """Run the REAL generator (no source patching) against a synthetic identity."""
    identity_path = tmp_path / "identity.json"
    out_path = tmp_path / "out" / "connector-identity.generated.nsh"
    identity_path.write_text(json.dumps(identity), encoding="utf-8")
    result = subprocess.run(
        [sys.executable, str(GENERATOR_PATH), "--identity", str(identity_path), "--out", str(out_path)],
        capture_output=True,
        text=True,
    )
    return result, out_path


def _identity_with(production: list[str], **overrides) -> dict:
    identity = _identity()
    identity["production_extension_ids"] = production
    identity.update(overrides)
    return identity


def test_identity_json_has_the_required_shape() -> None:
    identity = _identity()
    assert identity["protocol_version"] == 1
    assert isinstance(identity["native_host_name"], str) and identity["native_host_name"]
    assert isinstance(identity["dev_native_host_name"], str) and identity["dev_native_host_name"]
    assert identity["native_host_name"] != identity["dev_native_host_name"]
    assert isinstance(identity["production_extension_ids"], list)
    for ext_id in identity["production_extension_ids"]:
        assert _EXTENSION_ID_RE.match(ext_id), f"{ext_id!r} is not a valid 32-char Chrome/Edge extension id"


def test_shipped_identity_is_well_formed() -> None:
    assert _connector_identity_module().validate_identity(_identity()) == []


def test_production_extension_ids_match_the_deliberately_pinned_list() -> None:
    """Guards against silently promoting a placeholder into the wire/install contract.

    If this ever legitimately changes (a store confirms a real id), update PINNED_PRODUCTION_EXTENSION_IDS in the
    same reviewed change as identity.json -- it must never be flipped by accident. See identity.json's own
    `_production_extension_ids_comment` for the original reasoning, and the store-release runbook for later corrections.
    (Interim by design: the settled release policy -- a `released` flag with a previous-tag ratchet -- will replace this
    tripwire rather than coexist with it as a second authority.)
    """
    identity = _identity()
    assert identity["production_extension_ids"] == PINNED_PRODUCTION_EXTENSION_IDS


def test_dev_extension_id_matches_its_own_public_key() -> None:
    """The id isn't just a random-looking string -- it's REQUIRED to be exactly what Chrome/Edge
    derive from dev_extension_public_key_base64, since that's what makes 'Load unpacked' with this
    key produce this id in the first place."""
    identity = _identity()
    assert _chrome_extension_id(identity["dev_extension_public_key_base64"]) == identity["dev_extension_id"]
    assert identity["dev_extension_id"] not in identity["production_extension_ids"]


def test_extension_manifest_matches_the_minimal_permission_set() -> None:
    """Guards against permission creep: exactly this set, nothing broader, ever (README.md's table)."""
    manifest = json.loads((EXTENSION_DIR / "manifest.json").read_text(encoding="utf-8"))
    assert set(manifest["permissions"]) == {"nativeMessaging", "activeTab", "scripting"}
    assert manifest["host_permissions"] == ["http://127.0.0.1/*"]
    assert "key" not in manifest, (
        "the repository manifest is keyless; no production key belongs here -- see identity.json"
    )
    for forbidden in ("cookies", "webRequest", "<all_urls>", "tabs"):
        assert forbidden not in manifest.get("permissions", []) + manifest.get("host_permissions", [])


def test_background_js_native_host_name_matches_identity_json() -> None:
    identity = _identity()
    background = (EXTENSION_DIR / "background.js").read_text(encoding="utf-8")
    assert f'const NATIVE_HOST_NAME = "{identity["native_host_name"]}";' in background


# ---- validation rules (shared by the generator, the package builder and the Rust unit tests) ----------------


def test_validate_identity_accepts_an_empty_or_populated_production_list() -> None:
    validate = _connector_identity_module().validate_identity
    assert validate(_identity_with([])) == []
    assert validate(_identity_with([CHROME_STORE_ID])) == []
    assert validate(_identity_with([CHROME_STORE_ID, EDGE_STORE_ID])) == []


@pytest.mark.parametrize(
    ("production", "expected_fragment"),
    [
        ([CHROME_STORE_ID, CHROME_STORE_ID], "duplicate"),
        (["C" * 32], "not a valid 32-char"),
        (["c" * 31], "not a valid 32-char"),
        (["c" * 33], "not a valid 32-char"),
        (["q" * 32], "not a valid 32-char"),  # outside the a-p alphabet
        (["1" * 32], "not a valid 32-char"),
        ([""], "not a valid 32-char"),
        ([None], "not a valid 32-char"),
        (["c" * 32, "not-an-id"], "not a valid 32-char"),
    ],
)
def test_validate_identity_rejects_malformed_or_duplicated_production_ids(production, expected_fragment) -> None:
    problems = _connector_identity_module().validate_identity(_identity_with(production))
    assert any(expected_fragment in problem for problem in problems), problems


def test_validate_identity_rejects_the_dev_id_in_the_production_list() -> None:
    dev_id = _identity()["dev_extension_id"]
    problems = _connector_identity_module().validate_identity(_identity_with([CHROME_STORE_ID, dev_id]))
    assert any("dev extension id must never appear" in problem for problem in problems), problems


@pytest.mark.parametrize(
    "overrides",
    [
        {"dev_native_host_name": "org.callosum.connector"},  # same as production
        {"native_host_name": "Org.Callosum.Connector"},  # uppercase
        {"native_host_name": "org.callosum..connector"},  # empty segment
        {"native_host_name": ".org.callosum"},  # leading dot
        {"native_host_name": "org.callosum."},  # trailing dot
        {"native_host_name": ""},
    ],
)
def test_validate_identity_rejects_invalid_or_colliding_host_names(overrides) -> None:
    assert _connector_identity_module().validate_identity(_identity_with([], **overrides)) != []


def test_allowed_origins_are_exact_and_keep_configured_order() -> None:
    origins = _connector_identity_module().allowed_origins([EDGE_STORE_ID, CHROME_STORE_ID])
    assert origins == [f"chrome-extension://{EDGE_STORE_ID}/", f"chrome-extension://{CHROME_STORE_ID}/"]
    assert _connector_identity_module().allowed_origins([]) == []


# ---- the NSIS generator: run for real against synthetic identities -------------------------------------------


@pytest.mark.parametrize(
    "production",
    [[], [CHROME_STORE_ID], [CHROME_STORE_ID, EDGE_STORE_ID], [EDGE_STORE_ID, CHROME_STORE_ID]],
)
def test_generator_emits_exactly_the_configured_origins_in_order(tmp_path: Path, production: list[str]) -> None:
    identity = _identity_with(production, native_host_name="org.example.testhost")
    result, out_path = _run_generator(tmp_path, identity)
    assert result.returncode == 0, result.stderr
    generated = out_path.read_text(encoding="utf-8")

    assert "!define CONNECTOR_NATIVE_HOST_NAME org.example.testhost" in generated
    # EXACTLY the configured origins, in order: nothing extra, and never the dev id.
    emitted = re.findall(r"chrome-extension://([a-z]+)/", generated)
    assert emitted == production
    assert identity["dev_extension_id"] not in generated
    if production:
        assert "FileWrite $1 '[$\\r$\\n'" in generated
        assert "FileWrite $1 '  ]$\\r$\\n'" in generated
        assert "'[]$" not in generated
    else:
        assert "FileWrite $1 '[]$\\r$\\n'" in generated
        assert "chrome-extension://" not in generated


@pytest.mark.parametrize(
    ("production", "extra", "fragment"),
    [
        (["not-a-valid-id"], {}, "not a valid 32-char"),
        (["C" * 32], {}, "not a valid 32-char"),
        ([CHROME_STORE_ID, CHROME_STORE_ID], {}, "duplicate"),
        ([_identity()["dev_extension_id"]], {}, "dev extension id must never appear"),
        ([], {"dev_native_host_name": "org.callosum.connector"}, "must differ"),
        ([], {"native_host_name": "Not A Host"}, "not a valid native-messaging host name"),
    ],
)
def test_generator_refuses_a_bad_identity_and_writes_nothing(tmp_path: Path, production, extra, fragment) -> None:
    result, out_path = _run_generator(tmp_path, _identity_with(production, **extra))
    assert result.returncode != 0
    assert fragment in result.stderr, result.stderr
    assert not out_path.exists(), "a refused identity must not leave a generated include behind"


def test_generator_output_for_the_shipped_identity_is_consistent_with_identity_json(tmp_path: Path) -> None:
    result, out_path = _run_generator(tmp_path, _identity())
    assert result.returncode == 0, result.stderr
    identity = _identity()
    emitted = re.findall(r"chrome-extension://([a-z]+)/", out_path.read_text(encoding="utf-8"))
    assert emitted == identity["production_extension_ids"]


# ---- installer: one manifest, both browser keys, no second copy of the identity -------------------------------


def _installer_hooks() -> str:
    return INSTALLER_HOOKS.read_text(encoding="utf-8")


def test_installer_points_both_browser_keys_at_one_shared_manifest() -> None:
    hooks = _installer_hooks()
    assert 'Software\\Google\\Chrome\\NativeMessagingHosts\\${CONNECTOR_NATIVE_HOST_NAME}"' in hooks
    assert 'Software\\Microsoft\\Edge\\NativeMessagingHosts\\${CONNECTOR_NATIVE_HOST_NAME}"' in hooks

    manifest_value = r'"$INSTDIR\connector\${CONNECTOR_NATIVE_HOST_NAME}.json"'
    assert f'WriteRegStr HKCU "${{CONNECTOR_CHROME_KEY}}" "" {manifest_value}' in hooks
    assert f'WriteRegStr HKCU "${{CONNECTOR_EDGE_KEY}}" "" {manifest_value}' in hooks
    # ONE manifest is generated, so both stores' ids live in one allowed_origins list.
    assert hooks.count('FileOpen $1 "$INSTDIR\\connector\\${CONNECTOR_NATIVE_HOST_NAME}.json" w') == 1
    assert hooks.count('"allowed_origins"') == 1


def test_installer_takes_allowed_origins_only_from_the_generated_identity() -> None:
    hooks = _installer_hooks()
    assert "!insertmacro CONNECTOR_WRITE_ALLOWED_ORIGINS_JSON" in hooks
    assert "chrome-extension://" not in hooks, "no extension id may be hand-written into the installer hook"
    assert '!include "${__FILEDIR__}\\connector-identity.generated.nsh"' in hooks


def test_installer_update_mode_uninstall_keeps_the_registration_and_ownership_is_exact_path() -> None:
    hooks = _installer_hooks()
    assert "${If} $UpdateMode <> 1" in hooks
    # Registry removal only when the value still equals THIS install's manifest path.
    assert hooks.count("${If} $8 == $9") == 2


# ---- CI wiring: authored here, proven only when GitHub actually runs it ---------------------------------------


def test_windows_ci_checks_the_built_manifest_against_identity_json_not_a_hardcoded_empty_list() -> None:
    workflow = (WORKFLOWS / "desktop-shell-windows.yml").read_text(encoding="utf-8")
    assert "expected an empty allowed_origins" not in workflow
    step_start = workflow.index("Verify: browser-capture connector registration is correct after install")
    step = workflow[step_start : workflow.index("Verify: update-mode uninstall preserves connector registration")]
    assert "connector/identity.json" in step
    assert "production_extension_ids" in step
    assert "allowed_origins" in step


def test_connector_extension_and_shell_tests_are_wired_into_workflows() -> None:
    ci = (WORKFLOWS / "ci.yml").read_text(encoding="utf-8")
    assert "cargo test" in ci and "connector-host" in ci
    assert "node --test" in ci and "app/desktop-shell/extension/background.test.mjs" in ci
    windows = (WORKFLOWS / "desktop-shell-windows.yml").read_text(encoding="utf-8")
    assert "cargo test" in windows and "src-tauri" in windows and "connector-host" in windows
