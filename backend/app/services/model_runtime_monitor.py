"""Runtime model-call monitor for local development visibility."""
from __future__ import annotations

from datetime import datetime, timezone
from threading import Lock
from time import monotonic
from typing import Any, Dict
from uuid import uuid4


class ModelRuntimeMonitor:
    """Track active model requests and expose a small serializable snapshot."""

    _lock = Lock()
    _active: dict[str, dict[str, Any]] = {}
    _last_event: dict[str, Any] = {
        "status": "idle",
        "message": "模型空闲",
        "updated_at": "",
    }

    @classmethod
    def _now(cls) -> str:
        return datetime.now(timezone.utc).isoformat()

    @classmethod
    def _log(cls, message: str) -> None:
        print(f"[model-runtime] {datetime.now().strftime('%H:%M:%S')} {message}", flush=True)

    @classmethod
    def start(
        cls,
        *,
        provider: str,
        model_name: str,
        api_mode: str,
        base_url: str,
    ) -> str:
        request_id = uuid4().hex[:10]
        now = cls._now()
        record = {
            "request_id": request_id,
            "provider": provider,
            "model_name": model_name,
            "api_mode": api_mode,
            "base_url": base_url,
            "status": "connecting",
            "message": "正在连接模型",
            "chunk_count": 0,
            "started_at": now,
            "updated_at": now,
            "_started_monotonic": monotonic(),
        }
        with cls._lock:
            cls._active[request_id] = record
            cls._last_event = {key: value for key, value in record.items() if not key.startswith("_")}
        cls._log(f"开始请求 id={request_id} model={model_name} base_url={base_url or '-'}")
        return request_id

    @classmethod
    def mark_attempt(cls, request_id: str, *, base_url: str) -> None:
        cls._update(request_id, status="connecting", message=f"正在连接 {base_url or '默认模型端点'}", base_url=base_url)

    @classmethod
    def mark_streaming(cls, request_id: str) -> None:
        with cls._lock:
            record = cls._active.get(request_id)
            if not record:
                return
            record["chunk_count"] = int(record.get("chunk_count") or 0) + 1
            record["status"] = "streaming"
            record["message"] = "模型正在返回内容"
            record["updated_at"] = cls._now()
            cls._last_event = {key: value for key, value in record.items() if not key.startswith("_")}
        if int(record.get("chunk_count") or 0) == 1:
            cls._log(f"收到首个模型输出 id={request_id}")

    @classmethod
    def finish(cls, request_id: str) -> None:
        with cls._lock:
            record = cls._active.pop(request_id, None)
            if not record:
                return
            elapsed_ms = int((monotonic() - float(record.get("_started_monotonic") or monotonic())) * 1000)
            record["status"] = "success"
            record["message"] = "模型调用完成"
            record["elapsed_ms"] = elapsed_ms
            record["updated_at"] = cls._now()
            cls._last_event = {key: value for key, value in record.items() if not key.startswith("_")}
        cls._log(f"请求完成 id={request_id} chunks={record.get('chunk_count')} elapsed_ms={record.get('elapsed_ms')}")

    @classmethod
    def fail(cls, request_id: str, error: Exception | str) -> None:
        with cls._lock:
            record = cls._active.pop(request_id, None) or {"request_id": request_id, "started_at": cls._now()}
            elapsed_ms = int((monotonic() - float(record.get("_started_monotonic") or monotonic())) * 1000)
            record["status"] = "error"
            record["message"] = str(error)
            record["elapsed_ms"] = elapsed_ms
            record["updated_at"] = cls._now()
            cls._last_event = {key: value for key, value in record.items() if not key.startswith("_")}
        cls._log(f"请求失败 id={request_id} error={str(error)[:300]}")

    @classmethod
    def _update(cls, request_id: str, **patch: Any) -> None:
        with cls._lock:
            record = cls._active.get(request_id)
            if not record:
                return
            record.update(patch)
            record["updated_at"] = cls._now()
            cls._last_event = {key: value for key, value in record.items() if not key.startswith("_")}

    @classmethod
    def snapshot(cls) -> Dict[str, Any]:
        with cls._lock:
            active = [
                {key: value for key, value in record.items() if not key.startswith("_")}
                for record in cls._active.values()
            ]
            last_event = dict(cls._last_event)
        return {
            "active": bool(active),
            "active_count": len(active),
            "active_requests": active,
            "last_event": last_event,
        }
