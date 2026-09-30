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

from dataclasses import dataclass, replace

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
    S: Binding = Binding(
        "off"
    )  # researcher-facing overview synthesis; off in every Wave-1 profile (see OVERVIEW_PROFILES)


def _ollama(model: str, think=None) -> Binding:
    return Binding("ollama", model, endpoint="isolated", think=think)


_Q25 = Binding("managed_local", "callosum-managed-local", endpoint="shared")
_QWEN35 = "qwen3.5:9b"


def validate(profile: Profile) -> None:
    roles = {"W": profile.W, "R": profile.R, "C": profile.C, "P": profile.P, "S": profile.S}
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
    if profile.S.kind not in {"off", "ollama"}:
        raise ValueError(f"{profile.name}: S must be off or an Ollama-native model")
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

# ---- overview-enabled profiles: NOT Wave 1 ---------------------------------------------------------------------------------
# WAVE1 stays exactly T0..T5 and T5* is unchanged. An overview profile is DERIVED from a Wave-1 profile (so its W/R/C/P cannot
# drift) and adds only the S role. S runs once, after the last coverage stage, over the sealed ledger.
#
# S is Qwen3.5 with thinking ON. Its envelope is explicit, fixed and recorded; nothing falls back or changes after a failed call.
#   num_ctx 20,480 / num_predict 16,384: thinking + answer share the allowance. Recorded Qwen3.5 thinking-on calls spent ~all
#     their tokens reasoning (final JSON ~85-190): 12 finished under 3.9K, 4 needed 5.5-7.1K, and 3 of 19 hit 8,192 with no
#     output, including both whole-ledger audits. 16,384 is ~2x the largest budget at which any call finished. The prompt cap
#     (12,000 chars, ~4,096 estimated tokens) + the allowance = num_ctx exactly. UNMEASURED on JUNO (8 GB): residency at this
#     context, and whether 16K tokens finish inside the 1,200 s watchdog (needs >= ~14 tok/s; measured 32-34 at 12,288 ctx).
#   Sampling is the Qwen3.5 model card's thinking-mode recommendation for general tasks (temperature 1.0, top_p 0.95, top_k 20,
#     min_p 0, presence_penalty 1.5), with the harness seed. The harness's temperature 0 is the setting under which 3 of 19
#     thinking-on calls capped with no output; the card recommends presence_penalty against endless repetition. This is a
#     deliberate, recorded deviation for S only. Validation protects the answer either way, so this affects whether the call
#     finishes, not what may be shown.
OVERVIEW_S_OPTIONS = {
    "num_ctx": 20480,
    "num_predict": 16384,
    "temperature": 1.0,
    "top_p": 0.95,
    "top_k": 20,
    "min_p": 0.0,
    "presence_penalty": 1.5,
    "seed": 42,
    "num_thread": SUPERVISOR_BASE_OPTIONS["num_thread"],
    "num_batch": SUPERVISOR_BASE_OPTIONS["num_batch"],
}
OVERVIEW_PROFILES = {"T5O": replace(WAVE1["T5"], name="T5*+O", S=_ollama(_QWEN35, think=True))}
for _profile in OVERVIEW_PROFILES.values():
    validate(_profile)

# ---- child-overview profile (Stage B, 2026-09-29 authorization): NOT Wave 1, NOT OVERVIEW_PROFILES ------------------------
# T5O (above) stays exactly as it is -- its own live run (gate-integration-live-002) remains the only currently-
# EVALUATED Overview configuration. T5C is a SEPARATE, ADDITIONAL profile for Stage B's per-child Overview calls:
# same W/R/C/P as T5 (derived, so they cannot drift, same as T5O), S = Qwen3.5 with thinking OFF.
#
# Generation options: CHILD_OVERVIEW_S_OPTIONS reuses SUPERVISOR_BASE_OPTIONS unchanged -- the SAME options every
# other thinking-off Qwen3.5 role binding in this topology already uses (T2-T5's own W role), not a bespoke,
# untested options set invented for this one call. This is deliberate, not merely convenient: OVERVIEW_S_OPTIONS's
# large num_predict (16,384) and thinking-mode sampling (temperature 1.0, presence_penalty 1.5, ...) are
# specifically justified above by RECORDED THINKING-ON call behavior ("thinking + answer share the allowance");
# none of that applies with thinking off, and reusing it here would carry an unexamined assumption into a
# genuinely different regime. SUPERVISOR_BASE_OPTIONS's num_predict (4,096) is still generous for the SAME
# schema_overview JSON answer thinking-on calls needed only ~85-190 tokens for (per OVERVIEW_S_OPTIONS's own
# comment) -- a thinking-off call spends nothing on reasoning, so there is no analogous budget pressure to
# provision for.
#
# T5C has NOT been run live. Its evidence status is `Testing`, never `Evaluated`, until it has -- the existing
# thinking-on T5O run and its artifacts are unaffected and remain the only live evidence this arm currently has.
CHILD_OVERVIEW_S_OPTIONS = dict(SUPERVISOR_BASE_OPTIONS)
CHILD_OVERVIEW_PROFILES = {"T5C": replace(WAVE1["T5"], name="T5*+C", S=_ollama(_QWEN35, think=False))}
for _profile in CHILD_OVERVIEW_PROFILES.values():
    validate(_profile)


def profile_names() -> list[str]:
    return [*WAVE1, *OVERVIEW_PROFILES, *CHILD_OVERVIEW_PROFILES]


def resolve_profile(name: str) -> Profile:
    if name in WAVE1:
        return WAVE1[name]
    if name in OVERVIEW_PROFILES:
        return OVERVIEW_PROFILES[name]
    return CHILD_OVERVIEW_PROFILES[name]
