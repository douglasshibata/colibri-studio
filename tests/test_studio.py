"""
Automated unit & integration test suite for Colibri Studio.
Tests configuration, SQLite database persistence, model discovery, hardware monitoring,
resource planner, ColibriClient, and REST/OpenAI-compatible API endpoints.
"""

import pytest
import os
import sys
import json
from pathlib import Path

# Add colibri-studio to sys.path
studio_path = Path(__file__).parent.parent
sys.path.insert(0, str(studio_path))

from backend.config import ConfigManager, StudioConfig
from storage.db import StorageDatabase
from models.manager import ModelManager, ModelInfo
from models.planner import ResourcePlanner, PlanInput
from hardware.monitor import HardwareMonitor
from colibri.client import ColibriClient
from colibri.process import ColibriProcessManager
from fastapi.testclient import TestClient
from backend.main import app


def test_config_manager(tmp_path):
    config_file = tmp_path / "test_config.json"
    cm = ConfigManager(config_filepath=str(config_file))
    assert cm.config.api_port == 8000

    cm.update({"api_port": 9090, "default_model": "GLM-5.2"})
    assert cm.config.api_port == 9090
    assert cm.config.default_model == "GLM-5.2"
    assert config_file.exists()


def test_storage_database():
    db = StorageDatabase(":memory:")
    conv = db.create_conversation(title="Test Conv", model_id="GLM-5.2", system_prompt="You are helpful.")
    assert conv["title"] == "Test Conv"
    assert conv["model_id"] == "GLM-5.2"

    msg = db.add_message(conv["id"], "user", "Hello Colibri!")
    assert msg["role"] == "user"
    assert msg["content"] == "Hello Colibri!"

    retrieved = db.get_conversation(conv["id"])
    assert len(retrieved["messages"]) == 1
    assert retrieved["messages"][0]["content"] == "Hello Colibri!"

    conv_list = db.list_conversations()
    assert len(conv_list) == 1

    db.delete_conversation(conv["id"])
    assert len(db.list_conversations()) == 0


def test_model_manager(tmp_path):
    # Create mock model directory with config.json
    model_dir = tmp_path / "glm-5.2-test"
    model_dir.mkdir(parents=True)
    with open(model_dir / "config.json", "w") as f:
        json.dump({"model_name": "GLM-5.2 Int4 Test", "architectures": ["ChatGLMForConditionalGeneration"]}, f)

    mm = ModelManager(model_dirs=[str(tmp_path)])
    models = mm.scan_models()
    assert len(models) == 1
    assert models[0].id == "glm-5.2-test"
    assert models[0].family == "GLM-5.2 / 5.3"
    assert models[0].total_params == "744B"


def test_resource_planner():
    rp = ResourcePlanner()

    # Test comfortable rating
    plan1 = rp.evaluate(PlanInput(
        model_family="glm",
        ram_gb=64,
        vram_gb=24,
        disk_free_gb=500,
        storage_type="NVMe"
    ))
    assert plan1.rating == "Comfortable"
    assert plan1.score > 80

    # Test insufficient RAM / storage
    plan2 = rp.evaluate(PlanInput(
        model_family="glm",
        ram_gb=8,
        vram_gb=0,
        disk_free_gb=100,
        storage_type="HDD"
    ))
    assert plan2.rating == "Not practical"
    assert len(plan2.bottlenecks) >= 2


def test_hardware_monitor():
    hm = HardwareMonitor()
    metrics = hm.get_current_metrics()
    assert metrics.ram_total_gb > 0
    assert metrics.disk_total_gb > 0
    assert "ram" in metrics.model_residency


def test_colibri_client_and_process():
    client = ColibriClient(base_url="http://127.0.0.1:9999")
    assert client.check_health() is False

    pm = ColibriProcessManager(exec_path="coli", port=9999)
    assert pm.is_running() is False


def test_api_endpoints():
    client = TestClient(app)

    # Root UI test
    r_root = client.get("/")
    assert r_root.status_code == 200

    # OpenAI Health endpoint
    r_health = client.get("/v1/health")
    assert r_health.status_code == 200
    assert "status" in r_health.json()

    # OpenAI Models list
    r_models = client.get("/v1/models")
    assert r_models.status_code == 200
    assert r_models.json()["object"] == "list"

    # OpenAI Chat completion fallback stream
    r_chat = client.post("/v1/chat/completions", json={
        "messages": [{"role": "user", "content": "Hello"}],
        "stream": False
    })
    assert r_chat.status_code == 200
    assert "choices" in r_chat.json()

    # Studio REST endpoints
    r_cfg = client.get("/api/v1/config")
    assert r_cfg.status_code == 200

    r_hw = client.get("/api/v1/hardware")
    assert r_hw.status_code == 200

    r_brain = client.get("/api/v1/brain")
    assert r_brain.status_code == 200
    assert r_brain.json()["total_experts"] == 19456
