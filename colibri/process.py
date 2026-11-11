"""
Subprocess lifecycle manager for running `coli serve`.
Safely starts, monitors, and stops Colibrì inference servers.
"""

import os
import sys
import time
import subprocess
import httpx
from typing import Optional, Dict, Any


class ColibriProcessManager:
    def __init__(self, exec_path: str = "coli", model_dir: str = "", port: int = 8080):
        self.exec_path = exec_path
        self.model_dir = model_dir
        self.port = port
        self.process: Optional[subprocess.Popen] = None
        self.host = "127.0.0.1"

    def is_running(self) -> bool:
        if self.process is None:
            return False
        return self.process.poll() is None

    def check_health(self) -> bool:
        url = f"http://{self.host}:{self.port}/v1/models"
        try:
            r = httpx.get(url, timeout=2.0)
            return r.status_code == 200
        except Exception:
            return False

    def start_server(self, model_path: str, extra_env: Optional[Dict[str, str]] = None) -> bool:
        if self.is_running():
            self.stop_server()

        cmd = [self.exec_path, "serve", "--model", model_path, "--port", str(self.port)]

        env = os.environ.copy()
        if extra_env:
            env.update(extra_env)

        try:
            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=env,
                text=True
            )
            # Give process a moment and check health
            time.sleep(1.0)
            return True
        except Exception as e:
            print(f"[Error] Failed to launch colibri server process: {e}")
            return False

    def stop_server(self) -> None:
        if self.process:
            try:
                self.process.terminate()
                self.process.wait(timeout=3.0)
            except Exception:
                self.process.kill()
            finally:
                self.process = None
