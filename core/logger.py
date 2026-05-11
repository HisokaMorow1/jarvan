"""Logger central (loguru). Importar `from core.logger import logger`."""
from __future__ import annotations

from pathlib import Path
from loguru import logger

from config import settings

LOG_DIR = settings.root / settings.app.logs_dir
LOG_DIR.mkdir(parents=True, exist_ok=True)

logger.remove()
logger.add(
    lambda m: print(m, end=""),
    level=settings.app.log_level,
    colorize=True,
    format="<green>{time:HH:mm:ss}</green> | <level>{level: <7}</level> | <cyan>{name}</cyan> - {message}",
)
logger.add(
    LOG_DIR / "jarvan_{time:YYYY-MM-DD}.log",
    rotation="10 MB",
    retention="14 days",
    level="DEBUG",
    encoding="utf-8",
)
