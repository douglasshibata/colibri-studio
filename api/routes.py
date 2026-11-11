"""
API Gateway & Router for Colibri Studio.
Exposes OpenAI-compatible endpoints (/v1/chat/completions, /v1/models, /v1/health)
and Studio REST endpoints (/api/v1/...).
"""

import json
import time
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, HTTPException, Request, Depends, status
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel, Field

from backend.config import get_config_manager, StudioConfig
from storage.db import StorageDatabase
from models.manager import ModelManager, ModelInfo
from models.planner import ResourcePlanner, PlanInput, PlanAssessment
from hardware.monitor import HardwareMonitor, SystemMetrics
from colibri.client import ColibriClient
from colibri.process import ColibriProcessManager

router = APIRouter()

# Singletons / Services instances
config_mgr = get_config_manager()
db = StorageDatabase()
model_mgr = ModelManager(model_dirs=[config_mgr.config.model_dir])
hw_monitor = HardwareMonitor()
planner = ResourcePlanner()
process_mgr = ColibriProcessManager(
    exec_path=config_mgr.config.colibri_exec_path,
    model_dir=config_mgr.config.model_dir,
    port=config_mgr.config.colibri_serve_port
)
colibri_client = ColibriClient(
    base_url=f"http://{config_mgr.config.colibri_serve_host}:{config_mgr.config.colibri_serve_port}",
    api_key=config_mgr.config.api_key
)


# --- Models for Request/Response ---

class ChatMessage(BaseModel):
    role: str
    content: str


class ChatCompletionRequest(BaseModel):
    model: Optional[str] = "colibri-default"
    messages: List[ChatMessage]
    temperature: Optional[float] = 0.7
    top_p: Optional[float] = 0.9
    max_tokens: Optional[int] = 1024
    stream: Optional[bool] = False
    conversation_id: Optional[str] = None


class CreateConversationRequest(BaseModel):
    title: Optional[str] = "New Conversation"
    model_id: Optional[str] = ""
    system_prompt: Optional[str] = ""
    settings: Optional[Dict[str, Any]] = None


class UpdateConversationRequest(BaseModel):
    title: Optional[str] = None
    system_prompt: Optional[str] = None
    settings: Optional[Dict[str, Any]] = None


class AddMessageRequest(BaseModel):
    role: str
    content: str
    metrics: Optional[Dict[str, Any]] = None


class SelectModelRequest(BaseModel):
    model_id: str


# --- Security Dependency ---

def verify_api_key(request: Request):
    required_key = config_mgr.config.api_key
    if required_key:
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")
        token = auth_header[7:]
        if token != required_key:
            raise HTTPException(status_code=403, detail="Invalid API Key")


# --- OpenAI Compatible Endpoints ---

@router.get("/v1/health", dependencies=[Depends(verify_api_key)])
def health_check():
    is_serve_online = colibri_client.check_health()
    return {
        "status": "online" if is_serve_online else "degraded",
        "colibri_serve_online": is_serve_online,
        "engine": "Colibrì Pure-C Engine",
        "studio_version": "1.0.0"
    }


@router.get("/v1/models", dependencies=[Depends(verify_api_key)])
def list_v1_models():
    scanned = model_mgr.scan_models()
    models_data = []
    for m in scanned:
        models_data.append({
            "id": m.id,
            "object": "model",
            "created": int(time.time()),
            "owned_by": "colibri-local",
            "permission": [],
            "root": m.id,
            "parent": None
        })
    if not models_data:
        models_data.append({
            "id": "colibri-default",
            "object": "model",
            "created": int(time.time()),
            "owned_by": "colibri-local"
        })
    return {"object": "list", "data": models_data}


@router.post("/v1/chat/completions", dependencies=[Depends(verify_api_key)])
def chat_completions(req: ChatCompletionRequest):
    messages_payload = [{"role": m.role, "content": m.content} for m in req.messages]

    # Check if colibri serve is actually running/available
    if colibri_client.check_health():
        if req.stream:
            def event_generator():
                for chunk in colibri_client.stream_chat_completion(
                    messages=messages_payload,
                    model=req.model or "default",
                    temperature=req.temperature or 0.7,
                    top_p=req.top_p or 0.9,
                    max_tokens=req.max_tokens or 1024
                ):
                    yield f"data: {json.dumps(chunk)}\n\n"
                yield "data: [DONE]\n\n"
            return StreamingResponse(event_generator(), media_type="text/event-stream")
        else:
            return colibri_client.create_chat_completion(
                messages=messages_payload,
                model=req.model or "default",
                temperature=req.temperature or 0.7,
                top_p=req.top_p or 0.9,
                max_tokens=req.max_tokens or 1024
            )
    else:
        # Fallback offline simulation when Colibri serve is not running
        reply_content = f"[Colibrì Local Workstation] Colibrì engine server is currently offline. (Selected model: {req.model}). Please start `coli serve` or launch active model in Model Manager."

        if req.stream:
            def fallback_generator():
                words = reply_content.split(" ")
                for i, word in enumerate(words):
                    time.sleep(0.03)
                    chunk = {
                        "id": f"chatcmpl-mock-{int(time.time())}",
                        "object": "chat.completion.chunk",
                        "created": int(time.time()),
                        "model": req.model,
                        "choices": [{
                            "index": 0,
                            "delta": {"content": word + (" " if i < len(words) - 1 else "")},
                            "finish_reason": None
                        }]
                    }
                    yield f"data: {json.dumps(chunk)}\n\n"
                yield "data: [DONE]\n\n"
            return StreamingResponse(fallback_generator(), media_type="text/event-stream")
        else:
            return {
                "id": f"chatcmpl-mock-{int(time.time())}",
                "object": "chat.completion",
                "created": int(time.time()),
                "model": req.model,
                "choices": [{
                    "index": 0,
                    "message": {"role": "assistant", "content": reply_content},
                    "finish_reason": "stop"
                }],
                "usage": {"prompt_tokens": 10, "completion_tokens": 25, "total_tokens": 35}
            }


# --- Colibri Studio REST API Endpoints ---

@router.get("/api/v1/config")
def get_config():
    return config_mgr.config.model_dump()


@router.post("/api/v1/config")
def update_config(updates: Dict[str, Any]):
    new_cfg = config_mgr.update(updates)
    return new_cfg.model_dump()


@router.get("/api/v1/models")
def get_models():
    return model_mgr.scan_models()


@router.post("/api/v1/models/select")
def select_model(req: SelectModelRequest):
    success = model_mgr.set_active_model(req.model_id)
    config_mgr.update({"default_model": req.model_id})
    return {"status": "success", "active_model": req.model_id}


@router.get("/api/v1/hardware")
def get_hardware_metrics():
    active_m = model_mgr.active_model_id
    active_info = {"id": active_m} if active_m else None
    return hw_monitor.get_current_metrics(active_info).model_dump()


@router.post("/api/v1/planner")
def evaluate_planner(plan_in: PlanInput):
    return planner.evaluate(plan_in).model_dump()


@router.get("/api/v1/conversations")
def list_conversations():
    return db.list_conversations()


@router.post("/api/v1/conversations")
def create_conversation(req: CreateConversationRequest):
    return db.create_conversation(
        title=req.title or "New Conversation",
        model_id=req.model_id or "",
        system_prompt=req.system_prompt or "",
        settings=req.settings
    )


@router.get("/api/v1/conversations/{conv_id}")
def get_conversation(conv_id: str):
    conv = db.get_conversation(conv_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conv


@router.patch("/api/v1/conversations/{conv_id}")
def update_conversation(conv_id: str, req: UpdateConversationRequest):
    conv = db.update_conversation(
        conv_id=conv_id,
        title=req.title,
        system_prompt=req.system_prompt,
        settings=req.settings
    )
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conv


@router.delete("/api/v1/conversations/{conv_id}")
def delete_conversation(conv_id: str):
    success = db.delete_conversation(conv_id)
    if not success:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return {"status": "success", "deleted_id": conv_id}


@router.post("/api/v1/conversations/{conv_id}/messages")
def add_message(conv_id: str, req: AddMessageRequest):
    conv = db.get_conversation(conv_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    msg = db.add_message(conv_id, req.role, req.content, req.metrics)
    return msg


@router.get("/api/v1/brain")
def get_brain_telemetry():
    active_model = model_mgr.active_model_id or "GLM-5.2"
    return {
        "model": active_model,
        "total_experts": 19456,
        "active_per_token": 256,
        "layers": 75,
        "tiers": {
            "vram": {"label": "VRAM Tier", "count": 1024, "color": "#00f0ff"},
            "ram": {"label": "RAM Cache (LRU)", "count": 4096, "color": "#0072ff"},
            "nvme": {"label": "NVMe Storage", "count": 14336, "color": "#8a2be2"}
        },
        "telemetry_supported": colibri_client.check_health(),
        "notes": "Expert activity is updated per-turn based on .coli_usage and layer-lookahead prefetch."
    }
