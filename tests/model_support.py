"""Helpers for integration tests that require real, registered model weights."""

import json
from pathlib import Path


def has_all_active_model_checkpoints() -> bool:
    repo_root = Path(__file__).resolve().parents[1]
    registry_dir = repo_root / "models" / "registry"
    try:
        manifest = json.loads((registry_dir / "registry_manifest.json").read_text())
    except (OSError, json.JSONDecodeError):
        return False

    required = {
        "chest_xray_vision",
        "tabular_risk_mlp",
        "multimodal_late_fusion",
    }
    models = manifest.get("models", {})
    if not required.issubset(models):
        return False

    for name in required:
        entry = models[name]
        version = entry.get("active_version")
        metadata = entry.get("versions", {}).get(version) if version else None
        if not metadata:
            return False
        artifact = metadata.get("artifact_filename")
        if not artifact or not (registry_dir / artifact).is_file():
            return False
    return True
