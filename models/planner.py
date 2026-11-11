"""
Machine Resource Planner for Colibri Studio.
Estimates model suitability against available host RAM, VRAM, NVMe disk, and GPU configuration.
"""

from typing import Dict, Any, Optional
from pydantic import BaseModel, Field


class PlanInput(BaseModel):
    model_family: str = Field(..., description="Model family name or key (e.g., glm, inkling, kimi_k3, deepseek_v4, qwen36, olmoe)")
    ram_gb: float = Field(..., description="Available system RAM in GB")
    vram_gb: float = Field(default=0.0, description="Available GPU VRAM in GB")
    num_gpus: int = Field(default=0, description="Number of GPUs")
    disk_free_gb: float = Field(..., description="Free disk/NVMe storage in GB")
    storage_type: str = Field(default="NVMe", description="Storage type: NVMe, SSD, or HDD")


class PlanAssessment(BaseModel):
    rating: str  # "Comfortable", "Possible but slow", "Marginal", "Not practical"
    score: int   # 0 to 100
    reasoning: str
    bottlenecks: list[str]
    recommended_configs: list[str]


MODEL_REQUIREMENTS = {
    "glm": {"disk_gb": 372.0, "min_ram_gb": 16.0, "rec_ram_gb": 32.0, "name": "GLM-5.2/5.3 (744B)"},
    "glm53": {"disk_gb": 195.0, "min_ram_gb": 16.0, "rec_ram_gb": 25.0, "name": "GLM-5.3-Flash (321B)"},
    "inkling": {"disk_gb": 469.0, "min_ram_gb": 25.0, "rec_ram_gb": 48.0, "name": "Inkling (975B)"},
    "kimi_k3": {"disk_gb": 1600.0, "min_ram_gb": 32.0, "rec_ram_gb": 64.0, "name": "Kimi K3 (2.8T)"},
    "deepseek_v4": {"disk_gb": 167.0, "min_ram_gb": 16.0, "rec_ram_gb": 32.0, "name": "DeepSeek V4 Flash (284B)"},
    "qwen38": {"disk_gb": 185.5, "min_ram_gb": 16.0, "rec_ram_gb": 24.0, "name": "Qwen3.8-Flash-Next (125B)"},
    "qwen36": {"disk_gb": 20.0, "min_ram_gb": 16.0, "rec_ram_gb": 24.0, "name": "Qwen3.6-35B-A3B (35B)"},
    "olmoe": {"disk_gb": 7.0, "min_ram_gb": 8.0, "rec_ram_gb": 16.0, "name": "OLMoE (7B)"}
}


class ResourcePlanner:
    def evaluate(self, inputs: PlanInput) -> PlanAssessment:
        req = MODEL_REQUIREMENTS.get(
            inputs.model_family.lower(),
            MODEL_REQUIREMENTS.get("glm")
        )

        bottlenecks = []
        recommendations = []
        score = 100

        # Check disk space
        if inputs.disk_free_gb < req["disk_gb"]:
            bottlenecks.append(
                f"Storage capacity insufficient: model needs ~{req['disk_gb']} GB, but only {inputs.disk_free_gb:.1f} GB is free."
            )
            score -= 60
        elif inputs.disk_free_gb < req["disk_gb"] * 1.1:
            bottlenecks.append(
                f"Storage space is tight: model needs ~{req['disk_gb']} GB; remaining space after install will be under 10%."
            )
            score -= 10

        # Check storage drive speed
        if inputs.storage_type.upper() in ["HDD", "SATA SSD"]:
            bottlenecks.append(
                f"Storage speed limit ({inputs.storage_type}): MoE expert streaming requires high random read throughput. High-speed PCIe Gen4 NVMe is strongly recommended."
            )
            score -= 25
            recommendations.append("Upgrade model directory to a Gen4/Gen5 NVMe SSD or setup dual-SSD striping (COLI_MODEL_MIRROR).")

        # Check RAM
        if inputs.ram_gb < req["min_ram_gb"]:
            bottlenecks.append(
                f"RAM below absolute minimum: model requires at least {req['min_ram_gb']} GB for dense layers and KV cache, host has {inputs.ram_gb:.1f} GB."
            )
            score -= 50
        elif inputs.ram_gb < req["rec_ram_gb"]:
            bottlenecks.append(
                f"RAM is limited: {inputs.ram_gb:.1f} GB available vs {req['rec_ram_gb']} GB recommended for comfortable expert cache hit rate."
            )
            score -= 15

        # Check VRAM offloading possibilities
        if inputs.vram_gb > 0:
            recommendations.append(
                f"GPU VRAM detected ({inputs.vram_gb:.1f} GB across {inputs.num_gpus} GPU(s)). Enable CUDA/Metal/Vulkan tier (COLI_CUDA_PIPE=1) to offload dense projections and hot experts for up to 5-10x speedup."
            )
        else:
            recommendations.append("Running on CPU-only. Streaming expert offload will rely entirely on RAM cache and NVMe read speed.")

        # Determine rating
        if score < 30 or inputs.disk_free_gb < req["disk_gb"] or inputs.ram_gb < req["min_ram_gb"]:
            rating = "Not practical"
            reasoning = f"The host machine currently lacks sufficient RAM or disk storage to run {req['name']} safely. Attempting inference will likely result in out-of-memory errors or storage starvation."
        elif score < 60:
            rating = "Marginal"
            reasoning = f"Inference with {req['name']} is technically possible, but severe disk or RAM bottlenecks will restrict throughput to fractional tokens per second (< 0.5 tok/s)."
        elif score < 85:
            rating = "Possible but slow"
            reasoning = f"{req['name']} can run reliably on this system. Performance will depend heavily on NVMe read speeds and expert cache hit rates (expect ~1 - 3 tok/s)."
        else:
            rating = "Comfortable"
            reasoning = f"Hardware configuration is well-suited for {req['name']}. Sizable RAM/VRAM capacity and fast NVMe storage will deliver smooth local inference."

        return PlanAssessment(
            rating=rating,
            score=max(0, score),
            reasoning=reasoning,
            bottlenecks=bottlenecks,
            recommended_configs=recommendations
        )
