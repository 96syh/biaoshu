"""Small JSON cache for expensive generation steps."""
from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path
from typing import Any


class GenerationCacheService:
    """Cache deterministic generation payloads by task, model, prompt version and input."""

    CACHE_DIR = Path(
        os.getenv(
            "YIBIAO_GENERATION_CACHE_DIR",
            str(Path(__file__).resolve().parents[3] / "artifacts" / "data" / "generation_cache"),
        )
    )
    PROMPT_VERSION = os.getenv("YIBIAO_PROMPT_VERSION", "2026-05-10-outline-contract-v2")

    @staticmethod
    def enabled() -> bool:
        value = os.getenv("YIBIAO_ENABLE_GENERATION_CACHE", "1")
        return value.strip().lower() not in {"0", "false", "no", "off", ""}

    @classmethod
    def build_key(cls, task: str, model_name: str, payload: Any) -> str:
        normalized = json.dumps(
            {
                "task": task,
                "model": model_name or "",
                "prompt_version": cls.PROMPT_VERSION,
                "payload": payload,
            },
            ensure_ascii=False,
            sort_keys=True,
            default=str,
        )
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()

    @classmethod
    def _path(cls, task: str, key: str) -> Path:
        safe_task = "".join(char if char.isalnum() or char in {"-", "_"} else "_" for char in task)
        return cls.CACHE_DIR / safe_task / f"{key}.json"

    @classmethod
    def get(cls, task: str, key: str) -> Any | None:
        if not cls.enabled():
            return None
        path = cls._path(task, key)
        try:
            if not path.exists():
                return None
            with path.open("r", encoding="utf-8") as handle:
                cached = json.load(handle)
            return cached.get("value")
        except Exception as exc:
            print(f"生成缓存读取失败 {task}/{key[:8]}: {exc}", flush=True)
            return None

    @classmethod
    def set(cls, task: str, key: str, value: Any) -> None:
        if not cls.enabled():
            return
        path = cls._path(task, key)
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            temp_path = path.with_suffix(".tmp")
            with temp_path.open("w", encoding="utf-8") as handle:
                json.dump(
                    {
                        "task": task,
                        "key": key,
                        "prompt_version": cls.PROMPT_VERSION,
                        "created_at": time.time(),
                        "value": value,
                    },
                    handle,
                    ensure_ascii=False,
                )
            temp_path.replace(path)
        except Exception as exc:
            print(f"生成缓存写入失败 {task}/{key[:8]}: {exc}", flush=True)
