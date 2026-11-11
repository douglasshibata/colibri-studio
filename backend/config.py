"""
Configuration management for Colibri Studio.
Handles application settings, environment variables, default paths, and JSON persistence.
"""

import os
import json
from pathlib import Path
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field


class StudioConfig(BaseModel):
    colibri_exec_path: str = Field(default="coli", description="Path to colibri executable or launcher")
    model_dir: str = Field(default="./models", description="Directory where model files are stored")
    api_host: str = Field(default="127.0.0.1", description="Local API host binding")
    api_port: int = Field(default=8000, description="Local API port")
    colibri_serve_host: str = Field(default="127.0.0.1", description="Host where coli serve runs")
    colibri_serve_port: int = Field(default=8080, description="Port where coli serve runs")
    api_key: Optional[str] = Field(default=None, description="Optional authentication key for API access")
    default_model: str = Field(default="", description="Default active model identifier")
    gpu_settings: Dict[str, Any] = Field(
        default_factory=lambda: {"use_cuda": True, "vram_gb": "auto", "pipe_mode": 1}
    )
    ram_storage_preferences: Dict[str, Any] = Field(
        default_factory=lambda: {"ram_budget_gb": 32, "use_direct_io": True, "numa": False}
    )
    ui_preferences: Dict[str, Any] = Field(
        default_factory=lambda: {"theme": "dark", "density": "compact", "enable_brain_viz": True}
    )


class ConfigManager:
    def __init__(self, config_filepath: Optional[str] = None):
        if config_filepath:
            self.config_filepath = Path(config_filepath)
        else:
            base_dir = Path(__file__).parent.parent
            self.config_filepath = base_dir / "config.json"

        self.config = self._load_config()

    def _load_config(self) -> StudioConfig:
        config_data = {}
        if self.config_filepath.exists():
            try:
                with open(self.config_filepath, "r", encoding="utf-8") as f:
                    config_data = json.load(f)
            except Exception as e:
                print(f"[Warning] Failed to load config file {self.config_filepath}: {e}")

        # Override with environment variables if present
        if env_exec := os.getenv("COLIBRI_EXEC_PATH"):
            config_data["colibri_exec_path"] = env_exec
        if env_model_dir := os.getenv("COLIBRI_MODEL_DIR"):
            config_data["model_dir"] = env_model_dir
        if env_host := os.getenv("COLIBRI_STUDIO_HOST"):
            config_data["api_host"] = env_host
        if env_port := os.getenv("COLIBRI_STUDIO_PORT"):
            config_data["api_port"] = int(env_port)
        if env_serve_port := os.getenv("COLIBRI_SERVE_PORT"):
            config_data["colibri_serve_port"] = int(env_serve_port)
        if env_api_key := os.getenv("COLIBRI_API_KEY"):
            config_data["api_key"] = env_api_key

        return StudioConfig(**config_data)

    def save_config(self, new_config: Optional[StudioConfig] = None) -> None:
        if new_config:
            self.config = new_config

        self.config_filepath.parent.mkdir(parents=True, exist_ok=True)
        with open(self.config_filepath, "w", encoding="utf-8") as f:
            json.dump(self.config.model_dump(), f, indent=2)

    def update(self, updates: Dict[str, Any]) -> StudioConfig:
        current_dict = self.config.model_dump()
        current_dict.update(updates)
        self.config = StudioConfig(**current_dict)
        self.save_config()
        return self.config


_config_manager_instance = None

def get_config_manager(filepath: Optional[str] = None) -> ConfigManager:
    global _config_manager_instance
    if _config_manager_instance is None or filepath is not None:
        _config_manager_instance = ConfigManager(filepath)
    return _config_manager_instance
