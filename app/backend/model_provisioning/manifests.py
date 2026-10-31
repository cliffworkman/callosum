"""Pinned artifact manifests for automatically provisioned models (inc 615).

A manifest is the exact byte-level identity of one qualified checkpoint: the Hub repository, the pinned git
revision, and every file the loader reads, each with its size and SHA-256. The file set is the one the research
runs actually loaded with ``local_files_only=True`` (Arctic S in the G2 worker receipt, DeBERTa in G1), so a
verified snapshot is known to be loadable offline. A file the Hub serves at the same revision but with different
bytes fails verification; nothing is ever "close enough".

The static contract checks read only small JSON files. Provisioning never loads model weights: memory-heavy
loading belongs to the inference paths, which still run their own load-time contract checks (``verify_nli_checkpoint``
for NLI, pooling/sequence-length enforcement for embeddings).
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

from app.backend.model_runtime import PINNED_MODEL_REVISIONS

ARCTIC_S_TRACK = "arctic-s"
DEBERTA_TRACK = "deberta-v3-base"


@dataclass(frozen=True)
class ArtifactFile:
    path: str  # relative to the snapshot root, POSIX separators
    size: int
    sha256: str


@dataclass(frozen=True)
class ModelManifest:
    track: str
    repo_id: str
    revision: str
    files: tuple[ArtifactFile, ...]
    contract: dict[str, object]  # static expectations checked against the downloaded JSON files

    @property
    def total_bytes(self) -> int:
        return sum(f.size for f in self.files)

    @property
    def digest(self) -> str:
        """One value naming the whole manifest; a verified receipt is valid only for the digest it was made under."""
        body = json.dumps(
            [self.repo_id, self.revision, [[f.path, f.size, f.sha256] for f in self.files], self.contract],
            sort_keys=True,
        )
        return hashlib.sha256(body.encode("utf-8")).hexdigest()


_ARCTIC_REPO = "Snowflake/snowflake-arctic-embed-s"
_DEBERTA_REPO = "MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli"

MANIFESTS: dict[str, ModelManifest] = {
    ARCTIC_S_TRACK: ModelManifest(
        track=ARCTIC_S_TRACK,
        repo_id=_ARCTIC_REPO,
        revision=PINNED_MODEL_REVISIONS[_ARCTIC_REPO],
        files=(
            ArtifactFile(".gitattributes", 1519, "11ad7efa24975ee4b0c3c3a38ed18737f0658a5f75a0a96787b576a78a023361"),
            ArtifactFile(
                "1_Pooling/config.json", 296, "83eeb6d0c128b377a452f121f8c5a19bbbf9322092a87b856ef782f4ad2326b9"
            ),
            ArtifactFile("README.md", 85025, "6f231741560fd8e2ba338b705918553f819f6848adcd5ee9293fc87990685e38"),
            ArtifactFile("config.json", 703, "4e519aa92ec40943356032afe458c8829d70c5766b109e4a57490b82f72dcfb7"),
            ArtifactFile(
                "config_sentence_transformers.json",
                252,
                "26a4caecbc808973e5b3b3a04484db1389078b0458254e4dd617ff361e2f378a",
            ),
            ArtifactFile(
                "model.safetensors", 132870584, "0350e62666ee2403db0223fc7cef6293c951cc63d1d2e71468da9a5aea3b544a"
            ),
            ArtifactFile("modules.json", 349, "84e40c8e006c9b1d6c122e02cba9b02458120b5fb0c87b746c41e0207cf642cf"),
            ArtifactFile(
                "sentence_bert_config.json", 107, "4dfc17a899f3ea25b5c8e9034a1d0d9ebd96eca0868b015a89d1d748c38e4b2f"
            ),
            ArtifactFile(
                "special_tokens_map.json", 695, "5d5b662e421ea9fac075174bb0688ee0d9431699900b90662acd44b2a350503a"
            ),
            ArtifactFile("tokenizer.json", 711649, "91f1def9b9391fdabe028cd3f3fcc4efd34e5d1f08c3bf2de513ebb5911a1854"),
            ArtifactFile(
                "tokenizer_config.json", 1433, "9ca59277519f6e3692c8685e26b94d4afca2d5438deff66483db495e48735810"
            ),
            ArtifactFile("vocab.txt", 231508, "07eced375cec144d27c900241f3e339478dec958f92fddbc551f295c992038a3"),
        ),
        contract={"model_type": "bert", "pooling": "cls", "max_seq_length": 512, "dimension": 384},
    ),
    DEBERTA_TRACK: ModelManifest(
        track=DEBERTA_TRACK,
        repo_id=_DEBERTA_REPO,
        revision=PINNED_MODEL_REVISIONS[_DEBERTA_REPO],
        files=(
            ArtifactFile("added_tokens.json", 23, "dc046d04c9b0ada7ae6f1dc89c465801799acdf0c9a6aab8c15a1b2d5ca4e91f"),
            ArtifactFile("config.json", 1090, "a6c616d6dabeacf90fd0e776c741d3f0f30a05533ccf0bd3b5b62e94cfaa8d57"),
            ArtifactFile(
                "model.safetensors", 368877646, "06d6fd89edd4f97816831626daafbdb0b029cf63bae8edc0bccab1d64e2e7707"
            ),
            ArtifactFile(
                "special_tokens_map.json", 286, "9463f61e1b109a8eb4688b829260d7c6b1e6dff04c98ff7269bb89e2b92369b9"
            ),
            ArtifactFile("spm.model", 2464616, "c679fbf93643d19aab7ee10c0b99e460bdbc02fedf34b92b05af343b4af586fd"),
            ArtifactFile("tokenizer.json", 8656646, "05402ffae6dd382a8491b1d29bfc139bec5d332662e86a026f433ce54c25c202"),
            ArtifactFile(
                "tokenizer_config.json", 1284, "557b3d33d3f41b81ad769244e506549e98a1857d41dd58160aacd4d98d710b5a"
            ),
        ),
        # Must agree with nli_profiles.NLI_PROFILES["deberta-v3-base"]; a test pins the two together.
        contract={
            "model_type": "deberta-v2",
            "architecture": "DebertaV2ForSequenceClassification",
            "id2label": {"0": "entailment", "1": "neutral", "2": "contradiction"},
            "tokenizer_class_prefix": "DebertaV2",
        },
    ),
}

# Track -> the model name its consumers load (embedding profile / NLI profile ``model_name``).
TRACK_FOR_MODEL: dict[str, str] = {m.repo_id: track for track, m in MANIFESTS.items()}


class ContractMismatch(ValueError):
    pass


def _json(root: Path, name: str) -> dict:
    try:
        return json.loads((root / name).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ContractMismatch(f"{name}: unreadable ({type(exc).__name__})") from None


def check_static_contract(manifest: ModelManifest, root: Path) -> None:
    """Architecture, labels, tokenizer and pooling read from the checkpoint's own JSON, without loading weights."""
    c = manifest.contract
    config = _json(root, "config.json")
    if config.get("model_type") != c["model_type"]:
        raise ContractMismatch(f"model_type {config.get('model_type')!r}, expected {c['model_type']!r}")
    if manifest.track == DEBERTA_TRACK:
        if c["architecture"] not in (config.get("architectures") or []):
            raise ContractMismatch(f"architectures {config.get('architectures')!r}, expected {c['architecture']!r}")
        labels = {str(k): str(v).lower() for k, v in (config.get("id2label") or {}).items()}
        if labels != c["id2label"]:
            raise ContractMismatch(f"label order {labels}, expected {c['id2label']}")
        tokenizer = str(_json(root, "tokenizer_config.json").get("tokenizer_class") or "")
        if not tokenizer.startswith(str(c["tokenizer_class_prefix"])):
            raise ContractMismatch(f"tokenizer {tokenizer!r}, expected {c['tokenizer_class_prefix']}*")
    else:
        pooling = _json(root, "1_Pooling/config.json")
        if not pooling.get("pooling_mode_cls_token") or pooling.get("pooling_mode_mean_tokens"):
            raise ContractMismatch("pooling is not CLS-only")
        if pooling.get("word_embedding_dimension") != c["dimension"]:
            raise ContractMismatch(f"dimension {pooling.get('word_embedding_dimension')}, expected {c['dimension']}")
        if _json(root, "sentence_bert_config.json").get("max_seq_length") != c["max_seq_length"]:
            raise ContractMismatch("max_seq_length differs from the pinned contract")
