"""Immutable content contracts, separate from future runtime observations."""

from dataclasses import asdict, dataclass

from .hashing import digest, text_hash

REQUIRED = "REQUIRED_FINAL_FREEZE_VALUE"


class ContractError(ValueError):
    pass


@dataclass(frozen=True)
class ModelConfiguration:
    candidate_id: str
    family: str
    artifact_repository: str
    artifact_revision: str
    artifact_filename: str
    expected_sha256: str
    local_hash_status: str
    runtime: str
    runtime_identity: str
    weight_quantization: str = "Q4_K_M"
    kv_k: str = "f16"
    kv_v: str = "f16"
    template_identity: str = "REQUIRES_PREFLIGHT"
    thinking: str = "REQUIRED_FINAL_FREEZE_VALUE"
    gpu_layers: int = 999
    threads: int = 6
    batch: int = 512
    microbatch: int = 512
    seed: int = 42
    temperature: float = 0.0
    placement: str = "GPU_WITH_EXPLICIT_OFFLOAD"


@dataclass(frozen=True)
class HardwareConfiguration:
    hardware_id: str
    configuration_hash: str


@dataclass(frozen=True)
class FrozenTask:
    task_id: str
    kind: str
    split: str
    text: str
    input_refs: tuple[tuple[str, str], ...] = ()
    trial_id: str = "primary"

    @property
    def hash(self):
        return digest(asdict(self))

    @property
    def question_hash(self):
        return text_hash(self.text)


@dataclass(frozen=True)
class RepresentationPackageIdentity:
    package_id: str
    package_hash: str


@dataclass(frozen=True)
class OutputBudgetPolicy:
    mode: str = REQUIRED
    common_cap: int | None = None
    package_caps: tuple[tuple[str, int], ...] = ()

    def resolve(self, package_id):
        if self.mode == "COMMON" and not self.package_caps:
            cap = self.common_cap
        elif self.mode == "PACKAGE_SPECIFIC" and self.common_cap is None:
            cap = dict(self.package_caps).get(package_id)
        else:
            raise ContractError("OUTPUT_BUDGET_REQUIRES_FINAL_FREEZE")
        if type(cap) is not int or cap <= 0:
            raise ContractError("OUTPUT_BUDGET_REQUIRES_FINAL_FREEZE")
        return cap


@dataclass(frozen=True)
class CellSpec:
    model: ModelConfiguration
    package: RepresentationPackageIdentity
    hardware: HardwareConfiguration
    task: FrozenTask
    context: int = 12288
    output_budget: OutputBudgetPolicy = OutputBudgetPolicy()

    @property
    def identity(self):
        if self.context != 12288 and self.task.kind != "neutral_mechanical":
            raise ContractError("SEMANTIC_CONTEXT_MUST_BE_REALISTIC")
        return {
            "version": 1,
            "model": asdict(self.model),
            "package": asdict(self.package),
            "hardware": asdict(self.hardware),
            "context": self.context,
            "task_hash": self.task.hash,
            "output_budget": asdict(self.output_budget),
        }

    @property
    def cell_id(self):
        return digest(self.identity)


@dataclass(frozen=True)
class PreparedRequest:
    body_json: bytes
    prerequisites_json: bytes
    model_configuration_hash: str
    context: int


@dataclass(frozen=True)
class RuntimeObservation:
    raw_text: str
    raw_provider_bytes: bytes
    finish_reason: str | None = None
    truncated: bool | None = None
    error_code: str | None = None
    actual_model_configuration_hash: str | None = None
    actual_context: int | None = None
    performance_json: bytes = b"{}"
