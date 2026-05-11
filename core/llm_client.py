"""Cliente Ollama unificado: chat (streaming/non-streaming), JSON, visión, embeddings.

Ollama corre 100% local en este equipo. Es nuestro "servidor" de IA.
Esta clase es la única vía de acceso al modelo — todo el resto del código depende de ella.
"""
from __future__ import annotations

import base64
import json
from pathlib import Path
from typing import Any, Callable, Dict, Iterator, List, Optional

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from config import settings
from core.logger import logger


class OllamaClient:
    def __init__(self, base_url: Optional[str] = None, timeout: Optional[int] = None) -> None:
        self.base_url = (base_url or settings.llm.base_url).rstrip("/")
        self.timeout = timeout or settings.llm.request_timeout
        self._client = httpx.Client(timeout=self.timeout)

    def close(self) -> None:
        self._client.close()

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=8))
    def chat(
        self,
        messages: List[Dict[str, Any]],
        model: Optional[str] = None,
        format_json: bool = False,
        temperature: Optional[float] = None,
        num_ctx: Optional[int] = None,
        images: Optional[List[str]] = None,
    ) -> str:
        payload: Dict[str, Any] = {
            "model": model or settings.llm.planner_model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": temperature if temperature is not None else settings.llm.temperature,
                "num_ctx": num_ctx or settings.llm.num_ctx,
            },
        }
        if format_json:
            payload["format"] = "json"
        if images:
            payload["messages"][-1]["images"] = images
            payload["model"] = model or settings.llm.vision_model

        logger.debug(f"Ollama chat model={payload['model']} msgs={len(messages)} json={format_json}")
        r = self._client.post(f"{self.base_url}/api/chat", json=payload)
        r.raise_for_status()
        return r.json().get("message", {}).get("content", "")

    def chat_stream(
        self,
        messages: List[Dict[str, Any]],
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        num_ctx: Optional[int] = None,
        on_token: Optional[Callable[[str], None]] = None,
    ) -> str:
        """Streaming: invoca on_token(delta) por cada chunk y retorna texto completo."""
        payload = {
            "model": model or settings.llm.router_model,
            "messages": messages,
            "stream": True,
            "options": {
                "temperature": temperature if temperature is not None else settings.llm.temperature,
                "num_ctx": num_ctx or settings.llm.num_ctx,
            },
        }
        full = []
        try:
            with self._client.stream("POST", f"{self.base_url}/api/chat", json=payload) as r:
                r.raise_for_status()
                for line in r.iter_lines():
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    delta = data.get("message", {}).get("content", "")
                    if delta:
                        full.append(delta)
                        if on_token:
                            on_token(delta)
                    if data.get("done"):
                        break
        except Exception as e:
            logger.error(f"stream falló: {e}")
        return "".join(full)

    def chat_json(self, messages: List[Dict[str, Any]], model: Optional[str] = None) -> Dict[str, Any]:
        text = self.chat(messages, model=model, format_json=True)
        try:
            return json.loads(text)
        except json.JSONDecodeError as e:
            logger.warning(f"JSON inválido del LLM, intento rescate: {e}")
            start = text.find("{")
            end = text.rfind("}")
            if start >= 0 and end > start:
                return json.loads(text[start : end + 1])
            raise

    def vision(self, prompt: str, image_path: Path, model: Optional[str] = None) -> str:
        b64 = base64.b64encode(Path(image_path).read_bytes()).decode("utf-8")
        msgs = [{"role": "user", "content": prompt, "images": [b64]}]
        payload = {
            "model": model or settings.llm.vision_model,
            "messages": msgs,
            "stream": False,
            "options": {"temperature": settings.llm.temperature},
        }
        r = self._client.post(f"{self.base_url}/api/chat", json=payload)
        r.raise_for_status()
        return r.json().get("message", {}).get("content", "")

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=8))
    def embed(self, text: str, model: Optional[str] = None) -> List[float]:
        payload = {"model": model or settings.llm.embed_model, "prompt": text}
        r = self._client.post(f"{self.base_url}/api/embeddings", json=payload)
        r.raise_for_status()
        return r.json().get("embedding", [])

    def ping(self) -> bool:
        try:
            r = self._client.get(f"{self.base_url}/api/tags", timeout=3)
            return r.status_code == 200
        except Exception:
            return False

    def list_models(self) -> List[str]:
        try:
            r = self._client.get(f"{self.base_url}/api/tags", timeout=5)
            r.raise_for_status()
            return [m["name"] for m in r.json().get("models", [])]
        except Exception as e:
            logger.warning(f"list_models falló: {e}")
            return []

    def warmup(self, model: str) -> bool:
        """Pre-carga un modelo en VRAM enviando una petición trivial.
        Acorta dramáticamente la latencia del primer prompt en la demo."""
        try:
            logger.info(f"Warm-up modelo: {model}")
            self._client.post(
                f"{self.base_url}/api/generate",
                json={"model": model, "prompt": "ok", "stream": False, "keep_alive": "30m"},
                timeout=120,
            )
            return True
        except Exception as e:
            logger.warning(f"warmup {model} falló: {e}")
            return False
