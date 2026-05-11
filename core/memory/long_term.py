"""Memoria de largo plazo: SQLite (episódica) + Chroma (semántica con embeddings).

Guarda tareas completadas, hechos del usuario, preferencias.
"""
from __future__ import annotations

import sqlite3
import uuid
from pathlib import Path
from time import time
from typing import List, Optional

from config import settings
from core.logger import logger


class LongTermMemory:
    def __init__(self, llm) -> None:
        self.llm = llm
        self.sql_path: Path = settings.root / settings.memory.sql_db_path
        self.sql_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_sql()

        self._chroma = None
        self._collection = None
        try:
            import chromadb

            chroma_path = settings.root / settings.memory.vector_db_path
            self._chroma = chromadb.PersistentClient(path=str(chroma_path))
            self._collection = self._chroma.get_or_create_collection(
                name="jarvan_memory", metadata={"hnsw:space": "cosine"}
            )
        except Exception as e:
            logger.warning(f"Chroma no disponible, memoria semántica desactivada: {e}")

    def _init_sql(self) -> None:
        with sqlite3.connect(self.sql_path) as c:
            c.execute(
                """
                CREATE TABLE IF NOT EXISTS episodes (
                    id TEXT PRIMARY KEY,
                    ts REAL NOT NULL,
                    kind TEXT NOT NULL,
                    title TEXT,
                    body TEXT,
                    success INTEGER
                )
                """
            )
            c.execute(
                """
                CREATE TABLE IF NOT EXISTS facts (
                    id TEXT PRIMARY KEY,
                    ts REAL NOT NULL,
                    key TEXT UNIQUE,
                    value TEXT
                )
                """
            )

    def remember_task(self, title: str, body: str, success: bool) -> None:
        rid = uuid.uuid4().hex
        with sqlite3.connect(self.sql_path) as c:
            c.execute(
                "INSERT INTO episodes VALUES (?,?,?,?,?,?)",
                (rid, time(), "task", title, body, int(success)),
            )
        self._index(rid, f"{title}\n{body}", meta={"kind": "task", "success": str(success)})

    def remember_fact(self, key: str, value: str) -> None:
        rid = uuid.uuid4().hex
        with sqlite3.connect(self.sql_path) as c:
            c.execute(
                "INSERT OR REPLACE INTO facts VALUES (?,?,?,?)",
                (rid, time(), key, value),
            )
        self._index(rid, f"{key}: {value}", meta={"kind": "fact", "key": key})

    def _index(self, rid: str, text: str, meta: dict) -> None:
        if not self._collection:
            return
        try:
            emb = self.llm.embed(text)
            self._collection.add(ids=[rid], embeddings=[emb], documents=[text], metadatas=[meta])
        except Exception as e:
            logger.warning(f"No se pudo indexar memoria: {e}")

    def recall(self, query: str, k: int = 3) -> List[str]:
        if not self._collection:
            return []
        try:
            emb = self.llm.embed(query)
            res = self._collection.query(query_embeddings=[emb], n_results=k)
            docs = res.get("documents", [[]])[0]
            return docs
        except Exception as e:
            logger.warning(f"Recall falló: {e}")
            return []

    def get_fact(self, key: str) -> Optional[str]:
        with sqlite3.connect(self.sql_path) as c:
            row = c.execute("SELECT value FROM facts WHERE key=?", (key,)).fetchone()
        return row[0] if row else None
