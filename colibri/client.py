"""
Colibri Client abstraction layer for OpenAI-compatible REST API exposed by `coli serve`.
Handles health checks, model discovery, chat completions, streaming SSE responses, and timeouts.
"""

import json
import httpx
from typing import Generator, Dict, Any, List, Optional


class ColibriClient:
    def __init__(self, base_url: str = "http://127.0.0.1:8080", api_key: Optional[str] = None, timeout: float = 60.0):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout

    def _get_headers(self) -> Dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    def check_health(self) -> bool:
        try:
            r = httpx.get(f"{self.base_url}/v1/models", headers=self._get_headers(), timeout=3.0)
            return r.status_code == 200
        except Exception:
            return False

    def list_models(self) -> List[Dict[str, Any]]:
        try:
            r = httpx.get(f"{self.base_url}/v1/models", headers=self._get_headers(), timeout=5.0)
            if r.status_code == 200:
                data = r.json()
                return data.get("data", [])
        except Exception as e:
            print(f"[Warning] ColibriClient failed to list models: {e}")
        return []

    def create_chat_completion(
        self,
        messages: List[Dict[str, str]],
        model: str = "default",
        temperature: float = 0.7,
        top_p: float = 0.9,
        max_tokens: int = 1024,
        stream: bool = False
    ) -> Dict[str, Any]:
        url = f"{self.base_url}/v1/chat/completions"
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "top_p": top_p,
            "max_tokens": max_tokens,
            "stream": stream
        }

        r = httpx.post(url, json=payload, headers=self._get_headers(), timeout=self.timeout)
        r.raise_for_status()
        return r.json()

    def stream_chat_completion(
        self,
        messages: List[Dict[str, str]],
        model: str = "default",
        temperature: float = 0.7,
        top_p: float = 0.9,
        max_tokens: int = 1024
    ) -> Generator[Dict[str, Any], None, None]:
        url = f"{self.base_url}/v1/chat/completions"
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "top_p": top_p,
            "max_tokens": max_tokens,
            "stream": True
        }

        with httpx.stream("POST", url, json=payload, headers=self._get_headers(), timeout=self.timeout) as response:
            response.raise_for_status()
            for line in response.iter_lines():
                if not line:
                    continue
                line = line.strip()
                if line.startswith("data: "):
                    data_str = line[6:]
                    if data_str == "[DONE]":
                        break
                    try:
                        chunk = json.loads(data_str)
                        yield chunk
                    except json.JSONDecodeError:
                        continue
