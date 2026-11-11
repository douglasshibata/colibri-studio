"""
Model Manager for Colibri Studio.
Discovers, parses, and manages local Colibrì model families (GLM, Inkling, Kimi K3, DeepSeek, Qwen, OLMoE).
"""

import os
import json
from pathlib import Path
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field


class ModelInfo(BaseModel):
    id: str
    name: str
    family: str
    path: str
    total_params: str
    active_params: str
    quantization: str
    disk_size_gb: float
    required_ram_gb: float
    required_vram_gb: float
    is_loaded: bool = False
    warning: Optional[str] = None
    huggingface_url: Optional[str] = None


MODEL_FAMILIES_METADATA = {
    "glm": {
        "family_name": "GLM-5.2 / 5.3",
        "total_params": "744B",
        "active_params": "40B",
        "default_quant": "int4-gs64",
        "base_disk_gb": 372.0,
        "base_ram_gb": 16.0,
        "base_vram_gb": 0.0,
        "hf_url": "https://huggingface.co/mastouri/GLM-5.2-colibri-int4-g64-with-int8-mtp"
    },
    "glm53": {
        "family_name": "GLM-5.3-Flash",
        "total_params": "321B",
        "active_params": "40B",
        "default_quant": "int4-gs64",
        "base_disk_gb": 195.0,
        "base_ram_gb": 25.0,
        "base_vram_gb": 0.0,
        "hf_url": "https://huggingface.co/zai-org/GLM-5.3-Flash"
    },
    "inkling": {
        "family_name": "Inkling",
        "total_params": "975B",
        "active_params": "41B",
        "default_quant": "int4",
        "base_disk_gb": 469.0,
        "base_ram_gb": 25.0,
        "base_vram_gb": 0.0,
        "hf_url": "https://huggingface.co/nbeerbower/Inkling-colibri-int4"
    },
    "kimi_k3": {
        "family_name": "Kimi K3",
        "total_params": "2.8T",
        "active_params": "104B",
        "default_quant": "MXFP4",
        "base_disk_gb": 1600.0,
        "base_ram_gb": 32.0,
        "base_vram_gb": 0.0,
        "hf_url": "https://huggingface.co/moonshotai/Kimi-K3"
    },
    "deepseek_v4": {
        "family_name": "DeepSeek V4 Flash",
        "total_params": "284B",
        "active_params": "13B",
        "default_quant": "FP4 / FP8",
        "base_disk_gb": 167.0,
        "base_ram_gb": 16.0,
        "base_vram_gb": 0.0,
        "hf_url": "https://huggingface.co/puwaer/DeepSeek-V4-Flash-0731-reap-150b"
    },
    "qwen38": {
        "family_name": "Qwen3.8-Flash-Next",
        "total_params": "125B",
        "active_params": "6B",
        "default_quant": "FP8",
        "base_disk_gb": 185.5,
        "base_ram_gb": 16.0,
        "base_vram_gb": 0.0,
        "hf_url": "https://huggingface.co/Qwen/Qwen3.8-Flash-Next-FP8"
    },
    "qwen36": {
        "family_name": "Qwen3.6-35B-A3B",
        "total_params": "35B",
        "active_params": "3B",
        "default_quant": "int4-gs64",
        "base_disk_gb": 20.0,
        "base_ram_gb": 24.0,
        "base_vram_gb": 0.0,
        "hf_url": "https://huggingface.co/Kreuzzelg/qwen36-35b-a3b-colibri-i4-gs64"
    },
    "olmoe": {
        "family_name": "OLMoE",
        "total_params": "7B",
        "active_params": "1B",
        "default_quant": "int8",
        "base_disk_gb": 7.0,
        "base_ram_gb": 8.0,
        "base_vram_gb": 0.0,
        "hf_url": "https://huggingface.co/allenai/OLMoE-1B-7B-0924"
    }
}


class ModelManager:
    def __init__(self, model_dirs: Optional[List[str]] = None):
        self.model_dirs = [Path(d) for d in (model_dirs or ["./models"])]
        self.active_model_id: Optional[str] = None

    def _calculate_dir_size_gb(self, path: Path) -> float:
        total_bytes = 0
        if not path.exists():
            return 0.0
        for root, _, files in os.walk(path):
            for f in files:
                fp = Path(root) / f
                if not fp.is_symlink():
                    total_bytes += fp.stat().st_size
        return round(total_bytes / (1024 ** 3), 2)

    def _detect_family_from_config(self, path: Path, config_data: Dict[str, Any]) -> str:
        model_type = str(config_data.get("model_type", "")).lower()
        architectures = [str(a).lower() for a in config_data.get("architectures", [])]
        combined = model_type + " " + " ".join(architectures)

        if "glm53" in combined or "glm-5.3" in combined:
            return "glm53"
        elif "glm" in combined or "chatglm" in combined:
            return "glm"
        elif "inkling" in combined:
            return "inkling"
        elif "kimi" in combined or "k3" in combined:
            return "kimi_k3"
        elif "deepseek" in combined:
            return "deepseek_v4"
        elif "qwen3.8" in combined or "qwen38" in combined:
            return "qwen38"
        elif "qwen" in combined:
            return "qwen36"
        elif "olmoe" in combined:
            return "olmoe"

        # Fallback based on directory name
        dirname = path.name.lower()
        for key in MODEL_FAMILIES_METADATA:
            if key in dirname:
                return key

        return "glm"

    def scan_models(self) -> List[ModelInfo]:
        models = []
        for model_dir in self.model_dirs:
            if not model_dir.exists():
                continue

            # Check if model_dir itself contains a model config
            candidate_dirs = [d for d in model_dir.iterdir() if d.is_dir()]
            if (model_dir / "config.json").exists():
                candidate_dirs.append(model_dir)

            for d in candidate_dirs:
                config_path = d / "config.json"
                if config_path.exists():
                    try:
                        with open(config_path, "r", encoding="utf-8") as f:
                            cfg = json.load(f)
                    except Exception:
                        cfg = {}

                    family_key = self._detect_family_from_config(d, cfg)
                    meta = MODEL_FAMILIES_METADATA.get(family_key, MODEL_FAMILIES_METADATA["glm"])

                    actual_disk_gb = self._calculate_dir_size_gb(d)
                    disk_gb = actual_disk_gb if actual_disk_gb > 0 else meta["base_disk_gb"]

                    model_id = d.name
                    model_info = ModelInfo(
                        id=model_id,
                        name=cfg.get("model_name", d.name),
                        family=meta["family_name"],
                        path=str(d.resolve()),
                        total_params=meta["total_params"],
                        active_params=meta["active_params"],
                        quantization=cfg.get("quantization", meta["default_quant"]),
                        disk_size_gb=disk_gb,
                        required_ram_gb=meta["base_ram_gb"],
                        required_vram_gb=meta["base_vram_gb"],
                        is_loaded=(self.active_model_id == model_id),
                        huggingface_url=meta["hf_url"]
                    )
                    models.append(model_info)
        return models

    def set_active_model(self, model_id: str) -> bool:
        self.active_model_id = model_id
        return True
