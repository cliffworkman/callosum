"""Process-local offline guard. No claim about unrelated host processes."""

import os
import sys
from collections import Counter
from contextlib import contextmanager
from unittest.mock import patch

COUNTERS = Counter()
_active = False
_installed = False
_allow_app_definitions = False
MODEL_MODULES = (
    "torch",
    "transformers",
    "sentence_transformers",
    "google.genai",
    "app.backend.model_runtime",
    "app.backend.llm.providers",
)


def _audit(event, args):
    if not _active:
        return
    if event in ("socket.connect", "socket.getaddrinfo", "socket.gethostbyname", "subprocess.Popen", "os.system"):
        COUNTERS[event] += 1
        raise RuntimeError("OFFLINE_GUARD_DENIED:" + event)
    modules = tuple(m for m in MODEL_MODULES if not (_allow_app_definitions and m.startswith("app.")))
    if event == "import" and any(args[0] == m or args[0].startswith(m + ".") for m in modules):
        COUNTERS["model_import"] += 1
        raise RuntimeError("OFFLINE_GUARD_DENIED:model_import")


@contextmanager
def offline_guard(*, allow_app_definitions=False):
    global _active, _installed, _allow_app_definitions
    if not _installed:
        sys.addaudithook(_audit)
        _installed = True
    previous = _active
    previous_definitions = _allow_app_definitions
    _allow_app_definitions = allow_app_definitions
    _active = True
    previous_profile = sys.getprofile()

    def block_live_calls(frame, event, arg):
        if event != "call":
            return
        filename = frame.f_code.co_filename.replace("\\", "/")
        name = frame.f_code.co_name
        blocked = filename.endswith("app/backend/llm/providers.py") and name == "complete"
        blocked |= filename.endswith("app/backend/model_runtime.py") and name in (
            "get",
            "_load_sentence_transformer",
            "_load_cross_encoder",
        )
        if blocked:
            COUNTERS["live_model_entrypoint"] += 1
            raise RuntimeError("OFFLINE_GUARD_DENIED:live_model_entrypoint")

    env = {
        "HF_HUB_OFFLINE": "1",
        "TRANSFORMERS_OFFLINE": "1",
        "HF_DATASETS_OFFLINE": "1",
        "CALLOSUM_ALLOW_DATA_EGRESS": "0",
        "PYTHONDONTWRITEBYTECODE": "1",
    }
    try:
        sys.setprofile(block_live_calls)
        with patch.dict(os.environ, env):
            yield COUNTERS
    finally:
        sys.setprofile(previous_profile)
        _active = previous
        _allow_app_definitions = previous_definitions
