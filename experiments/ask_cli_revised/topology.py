"""Role bindings for the Wave-1 E2E topologies (see E2E_TOPOLOGY_PLAN.md).

The roles are separately bindable: W (bounded extraction: context gate, evidence selection, claim formation, recovery
query), R (claim responsiveness), C (coverage audit) and P (recovery planning). A binding is where a role runs, not who
the "supervisor" is, so one model can hold several roles or none. Pure data plus validation; no I/O.

Two rules the validator enforces because they are causal, not stylistic:
  * ``C = det`` consumes R's mappings, so R must be bound; and
  * a model-bound C is the coverage authority and never sees R, so R must be off (a noncausal R would cost inference for
    no effect on the answer).
"""

from __future__ import annotations

from dataclasses import dataclass

# Loopback only: the JUNO Ollamas are reached through the standing SSH forwards. `shared` hosts the Qwen2.5-1.5B
# worker (`callosum-managed-local`); `isolated` hosts the bakeoff candidates and is where every Ollama-native
# binding runs.
ENDPOINTS = {"shared": "http://127.0.0.1:11434", "isolated": "http://127.0.0.1:11435"}

# Ordinary generation options for supervisory / native-worker calls. These mirror the bakeoff envelope's *values*
# (so an E2E call is comparable to the qualified evidence) without importing the frozen registry: the runtime owns
# its own configuration, and the execution policy changes only the evidence-supported allowance.
SUPERVISOR_BASE_OPTIONS = {
    "num_ctx": 12288,
    "num_predict": 4096,
    "temperature": 0,
    "seed": 42,
    "num_thread": 6,
    "num_batch": 512,
}
KEEP_ALIVE = "30m"
WALL_TIMEOUT_SECONDS = 1200.0

_KINDS = {"managed_local", "ollama", "det", "legacy", "off"}


@dataclass(frozen=True)
class Binding:
    kind: str  # managed_local | ollama | det | legacy | off
    model: str | None = None
    endpoint: str | None = None  # key into ENDPOINTS for ollama bindings
    think: bool | str | None = None  # the model's native reasoning setting; False = thinking off


@dataclass(frozen=True)
class Profile:
    name: str
    W: Binding
    R: Binding
    C: Binding
    P: Binding


def _ollama(model: str, think=None) -> Binding:
    return Binding("ollama", model, endpoint="isolated", think=think)


_Q25 = Binding("managed_local", "callosum-managed-local", endpoint="shared")
_QWEN35 = "qwen3.5:9b"


def validate(profile: Profile) -> None:
    roles = {"W": profile.W, "R": profile.R, "C": profile.C, "P": profile.P}
    for role, binding in roles.items():
        if binding.kind not in _KINDS:
            raise ValueError(f"{profile.name}.{role}: unknown binding kind {binding.kind!r}")
        if binding.kind == "ollama":
            if not binding.model:
                raise ValueError(f"{profile.name}.{role}: an ollama binding needs a model tag")
            if binding.endpoint not in ENDPOINTS:
                raise ValueError(f"{profile.name}.{role}: unknown endpoint {binding.endpoint!r}")
    if profile.W.kind not in {"managed_local", "ollama"}:
        raise ValueError(f"{profile.name}: the worker must run somewhere (got {profile.W.kind!r})")
    if profile.C.kind not in {"det", "ollama"}:
        raise ValueError(f"{profile.name}: C must be det or a model")
    if profile.P.kind not in {"legacy", "ollama"}:
        raise ValueError(f"{profile.name}: P must be legacy or a model")
    if profile.R.kind not in {"off", "managed_local", "ollama"}:
        raise ValueError(f"{profile.name}: R must be off or a model")
    if profile.C.kind == "det" and profile.R.kind == "off":
        raise ValueError(f"{profile.name}: deterministic coverage consumes R's mappings, so R cannot be off")
    if profile.C.kind == "ollama" and profile.R.kind != "off":
        raise ValueError(f"{profile.name}: a model-bound C never sees R, so a bound R would be a noncausal stage")


WAVE1 = {
    # Repaired/common-base Q2.5 baseline. NOT the untouched historical 0.6 pipeline.
    "T0": Profile("T0", W=_Q25, R=_Q25, C=Binding("det"), P=Binding("legacy")),
    # Q2.5 worker + Qwen3.5 only in the jurisdictions it has earned (R, P@8K); coverage stays deterministic.
    "T1": Profile("T1", W=_Q25, R=_ollama(_QWEN35, think=True), C=Binding("det"), P=_ollama(_QWEN35, think=True)),
    # T1 -> T2 changes the worker only.
    "T2": Profile(
        "T2",
        W=_ollama(_QWEN35, think=False),
        R=_ollama(_QWEN35, think=True),
        C=Binding("det"),
        P=_ollama(_QWEN35, think=True),
    ),
    # T2 -> T3 changes the supervisory model. Control-like: Gemma's earned jurisdictions are clear-positive recall and
    # bounded recovery; its nearest-category R errors are a known weakness and det coverage has no auditor.
    "T3": Profile(
        "T3",
        W=_ollama(_QWEN35, think=False),
        R=_ollama("gemma3:12b"),
        C=Binding("det"),
        P=_ollama("gemma3:12b"),
    ),
    # T2 -> T4 changes the supervisory model to gpt-oss (conservative, order-robust R; fails A1/A7 recall).
    "T4": Profile(
        "T4",
        W=_ollama(_QWEN35, think=False),
        R=_ollama("gpt-oss:20b", think="medium"),
        C=Binding("det"),
        P=_ollama("gpt-oss:20b", think="medium"),
    ),
    # T5* role-specialist topology (NOT an upper bound): the only tested C-passer + the cheap clean recovery passer; R is
    # noncausal under model-C, so off. Amended 2026-09-24 from a Q2.5 worker: the repaired Q2.5 gate discards ~95% of packets,
    # which would leave phi4's whole-ledger audit almost nothing to test. The key stays "T5" (an asterisk is not path-safe).
    "T5": Profile(
        "T5*", W=_ollama(_QWEN35, think=False), R=Binding("off"), C=_ollama("phi4:14b"), P=_ollama("gemma3:12b")
    ),
}

for _profile in WAVE1.values():
    validate(_profile)
