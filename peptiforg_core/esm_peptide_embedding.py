from __future__ import annotations

"""Optional lightweight ESM-2 sequence embedding adapter for Pepforge V5.

The adapter is deliberately optional and does not make ESM a core dependency.
It uses a small Hugging Face ESM-2 checkpoint when ``torch`` + ``transformers``
are installed.  ESM embeddings describe canonical amino-acid sequence context;
they do not encode D stereochemistry, non-natural residues, linkers, labels, or
other modified chemistry.
"""

from dataclasses import asdict, dataclass
from typing import Any, Iterable
import importlib.util
import re

ESM_EMBEDDING_VERSION = "5.0.0-rc2"
DEFAULT_ESM2_MODEL = "facebook/esm2_t6_8M_UR50D"
CANONICAL_AA = set("ARNDCQEGHILKMFPSTWYV")


@dataclass(frozen=True)
class ESMSequencePreparation:
    original_construct: str
    canonical_sequence: str
    status: str
    ignored_nonresidue_modifiers: tuple[str, ...]
    unsupported_residue_tokens: tuple[str, ...]
    claim_guard: str


@dataclass(frozen=True)
class ESMEmbeddingConfig:
    model_name: str = DEFAULT_ESM2_MODEL
    device: str = "auto"
    local_files_only: bool = False
    normalize: bool = False


def backend_readiness(model_name: str = DEFAULT_ESM2_MODEL) -> dict[str, Any]:
    torch_ok = importlib.util.find_spec("torch") is not None
    transformers_ok = importlib.util.find_spec("transformers") is not None
    return {
        "version": ESM_EMBEDDING_VERSION,
        "model_name": model_name,
        "torch_available": torch_ok,
        "transformers_available": transformers_ok,
        "ready_for_inference": bool(torch_ok and transformers_ok),
        "status": "READY" if torch_ok and transformers_ok else "OPTIONAL_DEPENDENCY_MISSING",
        "claim_guard": "ESM embedding is an ML representation, not a folding probability or validated structure.",
    }


def prepare_sequence_for_esm(sequence: str) -> ESMSequencePreparation:
    """Prepare a canonical polymer sequence without silently erasing chemistry.

    Terminal/non-residue modifiers may be ignored *with an explicit disclosure*.
    D residues, non-natural residues, linkers, and side-chain-modified residues
    block direct ESM embedding because their identity/stereochemistry would be
    lost by mapping them to the 20-letter alphabet.
    """
    from peptiforg_core.pymol_structure_builder import classify_tokens

    construct = str(sequence or "").strip()
    if not construct:
        raise ValueError("Peptide construct is empty.")
    tokens = classify_tokens(construct)
    residues: list[str] = []
    ignored: list[str] = []
    unsupported: list[str] = []
    for token in tokens:
        cls = str(token.cls or "")
        raw = str(token.raw or token.token or "").strip()
        if cls == "std_aa" and len(raw) == 1 and raw.upper() in CANONICAL_AA:
            residues.append(raw.upper())
        elif cls in {"n_terminal_modifier", "c_terminal_modifier", "c_terminal", "label", "chemical", "tag_expansion"}:
            ignored.append(raw)
        elif cls in {"d_std_aa", "non_natural_aa", "linker", "side_chain_modified_residue"}:
            unsupported.append(raw)
        elif not raw:
            continue
        else:
            unsupported.append(raw)
    canonical = "".join(residues)
    if unsupported:
        status = "UNSUPPORTED_MODIFIED_BACKBONE_FOR_DIRECT_ESM"
    elif not canonical:
        status = "NO_CANONICAL_RESIDUES"
    elif ignored:
        status = "CANONICAL_BACKBONE_WITH_UNMODELED_MODIFIERS"
    else:
        status = "CANONICAL_SEQUENCE_READY"
    return ESMSequencePreparation(
        original_construct=construct,
        canonical_sequence=canonical,
        status=status,
        ignored_nonresidue_modifiers=tuple(ignored),
        unsupported_residue_tokens=tuple(unsupported),
        claim_guard=(
            "ESM-2 receives only the canonical amino-acid sequence. Any ignored modifier is not represented in the embedding; "
            "D/non-natural/linker/side-chain-modified residue chemistry is not silently canonicalized."
        ),
    )


def _validate_plain_sequence(sequence: str) -> str:
    seq = re.sub(r"\s+", "", str(sequence or "").upper())
    if not seq or any(ch not in CANONICAL_AA for ch in seq):
        raise ValueError("ESM embedding input must contain only the 20 canonical one-letter amino-acid codes.")
    return seq


def embed_canonical_sequences(
    sequences: Iterable[str],
    config: ESMEmbeddingConfig | None = None,
) -> dict[str, Any]:
    """Run real ESM-2 inference through Hugging Face Transformers.

    No fallback embedding is fabricated.  Missing optional dependencies raise a
    clear RuntimeError so the caller can expose an unavailable state in the UI.
    """
    cfg = config or ESMEmbeddingConfig()
    readiness = backend_readiness(cfg.model_name)
    if not readiness["ready_for_inference"]:
        raise RuntimeError(
            "ESM embedding backend is unavailable. Install optional torch + transformers dependencies; "
            "Pepforge will not fabricate substitute embeddings."
        )
    import torch
    from transformers import AutoModel, AutoTokenizer

    seqs = [_validate_plain_sequence(s) for s in sequences]
    if not seqs:
        raise ValueError("No sequences supplied for ESM embedding.")
    if cfg.device == "auto":
        device = "cuda" if torch.cuda.is_available() else "cpu"
    else:
        device = str(cfg.device)
    tokenizer = AutoTokenizer.from_pretrained(cfg.model_name, local_files_only=bool(cfg.local_files_only))
    model = AutoModel.from_pretrained(cfg.model_name, local_files_only=bool(cfg.local_files_only))
    model = model.to(device)
    model.eval()
    encoded = tokenizer(
        seqs,
        return_tensors="pt",
        padding=True,
        truncation=True,
        return_special_tokens_mask=True,
    )
    special_mask = encoded.pop("special_tokens_mask")
    encoded = {k: v.to(device) for k, v in encoded.items()}
    special_mask = special_mask.to(device)
    with torch.no_grad():
        output = model(**encoded)
    hidden = output.last_hidden_state
    attention = encoded["attention_mask"].bool()
    usable = attention & ~special_mask.bool()
    denom = usable.sum(dim=1, keepdim=True).clamp(min=1)
    pooled = (hidden * usable.unsqueeze(-1)).sum(dim=1) / denom
    if cfg.normalize:
        pooled = torch.nn.functional.normalize(pooled, p=2, dim=1)
    array = pooled.detach().cpu().float().numpy()
    return {
        "version": ESM_EMBEDDING_VERSION,
        "model_name": cfg.model_name,
        "device": device,
        "embedding_dimension": int(array.shape[1]),
        "sequences": seqs,
        "embeddings": array,
        "config": asdict(cfg),
        "claim_guard": "Sequence embeddings are ML features only; they are not native-state probabilities, docking scores, or experimental measurements.",
    }


__all__ = [
    "ESM_EMBEDDING_VERSION",
    "DEFAULT_ESM2_MODEL",
    "ESMSequencePreparation",
    "ESMEmbeddingConfig",
    "backend_readiness",
    "prepare_sequence_for_esm",
    "embed_canonical_sequences",
]
