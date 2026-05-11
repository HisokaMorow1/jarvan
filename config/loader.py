"""Carga settings.yaml en un objeto pydantic validado y singleton."""
from __future__ import annotations

from pathlib import Path
from typing import List

import yaml
from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT / "config" / "settings.yaml"


class AppCfg(BaseModel):
    name: str = "Jarvan"
    language: str = "es"
    log_level: str = "INFO"
    data_dir: str = "data"
    screenshots_dir: str = "data/screenshots"
    logs_dir: str = "logs"


class LLMCfg(BaseModel):
    provider: str = "ollama"
    base_url: str = "http://localhost:11434"
    planner_model: str = "qwen3-coder:30b"
    router_model: str = "qwen3:8b"
    vision_model: str = "qwen2.5vl:7b"
    embed_model: str = "nomic-embed-text"
    temperature: float = 0.2
    num_ctx: int = 8192
    request_timeout: int = 120


class STTCfg(BaseModel):
    engine: str = "faster-whisper"
    model_size: str = "large-v3"
    device: str = "cuda"
    compute_type: str = "float16"
    language: str = "es"
    vad_filter: bool = True
    beam_size: int = 5
    sample_rate: int = 16000


class TTSCfg(BaseModel):
    engine: str = "piper"
    voice: str = "es_ES-davefx-medium"
    rate: int = 180
    fallback: str = "pyttsx3"


class VisionCfg(BaseModel):
    primary: str = "vlm"
    ocr_engine: str = "paddleocr"
    ocr_lang: str = "es"
    screenshot_scale: float = 1.0
    cache_ttl_seconds: int = 2


class MemoryCfg(BaseModel):
    short_term_window: int = 20
    vector_db_path: str = "data/memory/chroma"
    sql_db_path: str = "data/memory/jarvan.db"
    embed_dim: int = 768


class AgentCfg(BaseModel):
    max_steps: int = 15
    max_retries_per_step: int = 3
    require_confirmation_for: List[str] = Field(default_factory=list)
    enable_planner: bool = True
    enable_vision: bool = True


class WakeWordCfg(BaseModel):
    enabled: bool = False
    phrase: str = "jarvan"


class Settings(BaseModel):
    app: AppCfg = AppCfg()
    llm: LLMCfg = LLMCfg()
    stt: STTCfg = STTCfg()
    tts: TTSCfg = TTSCfg()
    vision: VisionCfg = VisionCfg()
    memory: MemoryCfg = MemoryCfg()
    agent: AgentCfg = AgentCfg()
    wake_word: WakeWordCfg = WakeWordCfg()
    root: Path = ROOT


def _load() -> Settings:
    if CONFIG_PATH.exists():
        raw = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8")) or {}
    else:
        raw = {}
    s = Settings(**raw)
    (ROOT / s.app.data_dir).mkdir(parents=True, exist_ok=True)
    (ROOT / s.app.screenshots_dir).mkdir(parents=True, exist_ok=True)
    (ROOT / s.app.logs_dir).mkdir(parents=True, exist_ok=True)
    (ROOT / s.memory.vector_db_path).mkdir(parents=True, exist_ok=True)
    return s


settings: Settings = _load()
