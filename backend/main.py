"""
Main FastAPI Server & Entry Point for Colibri Studio.
Mounts API endpoints, serves frontend workstation assets, and configures Uvicorn.
"""

import os
from pathlib import Path
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from backend.config import get_config_manager
from api.routes import router as api_router

config_mgr = get_config_manager()
app = FastAPI(
    title="Colibri Studio — Local AI Workstation",
    description="Enterprise Local AI Workstation for Colibrì Inference Engine",
    version="1.0.0"
)

# Register API Router
app.include_router(api_router)

# Static files mounting
base_dir = Path(__file__).parent.parent
static_dir = base_dir / "frontend"

if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    @app.get("/", include_in_schema=False)
    def read_root():
        return FileResponse(static_dir / "index.html")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "backend.main:app",
        host=config_mgr.config.api_host,
        port=config_mgr.config.api_port,
        reload=False
    )
