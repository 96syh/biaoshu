"""本地项目草稿 JSON 存储服务。"""
from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


class ProjectService:
    """用单个 JSON 文件保存项目草稿，避免运行时生成本地数据库文件。"""

    STORE_PATH = Path(
        os.getenv(
            "YIBIAO_PROJECT_STORE_PATH",
            str(Path(__file__).resolve().parents[3] / "artifacts" / "runtime" / "projects.json"),
        )
    )

    @classmethod
    def _read_store(cls) -> Dict[str, Any]:
        if not cls.STORE_PATH.exists():
            return {"active_project_id": "", "projects": []}
        try:
            payload = json.loads(cls.STORE_PATH.read_text(encoding="utf-8"))
        except Exception:
            return {"active_project_id": "", "projects": []}
        if not isinstance(payload, dict):
            return {"active_project_id": "", "projects": []}
        projects = payload.get("projects")
        return {
            "active_project_id": str(payload.get("active_project_id") or ""),
            "projects": projects if isinstance(projects, list) else [],
        }

    @classmethod
    def _write_store(cls, payload: Dict[str, Any]) -> None:
        cls.STORE_PATH.parent.mkdir(parents=True, exist_ok=True)
        cls.STORE_PATH.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def _new_id() -> str:
        return f"project-{uuid.uuid4().hex[:12]}"

    @staticmethod
    def _clean_title(value: Any) -> str:
        title = str(value or "").strip()
        if not title:
            return ""
        if "media/image" in title.lower():
            return ""
        return title[:160]

    @classmethod
    def _draft_title(cls, draft: Dict[str, Any]) -> str:
        outline_data = draft.get("outlineData") or {}
        analysis = draft.get("analysisReport") or {}
        project = analysis.get("project") or {}
        return (
            cls._clean_title(outline_data.get("project_name"))
            or cls._clean_title(project.get("name"))
            or cls._clean_title(draft.get("uploadedFileName"))
            or cls._clean_title(project.get("number"))
            or "未命名标书"
        )

    @staticmethod
    def _stats(draft: Dict[str, Any]) -> Dict[str, int]:
        outline = ((draft.get("outlineData") or {}).get("outline") or [])
        completed = 0
        total = 0
        word_count = 0

        def walk(items: List[Dict[str, Any]]) -> None:
            nonlocal completed, total, word_count
            for item in items:
                children = item.get("children") or []
                if children:
                    walk(children)
                    continue
                total += 1
                content = str(item.get("content") or "")
                if content.strip():
                    completed += 1
                word_count += len(content)

        if isinstance(outline, list):
            walk(outline)
        return {"completed": completed, "total": total, "word_count": word_count}

    @staticmethod
    def _record_from_project(project: Dict[str, Any], include_draft: bool = True) -> Dict[str, Any]:
        record = {
            "id": str(project.get("id") or ""),
            "title": str(project.get("title") or "未命名标书"),
            "createdAt": str(project.get("createdAt") or ""),
            "updatedAt": str(project.get("updatedAt") or ""),
            "completed": int(project.get("completed") or 0),
            "total": int(project.get("total") or 0),
            "wordCount": int(project.get("wordCount") or 0),
        }
        if include_draft:
            draft = project.get("draft")
            record["draft"] = draft if isinstance(draft, dict) else {}
        return record

    @classmethod
    def get_active_project_id(cls) -> Optional[str]:
        project_id = cls._read_store().get("active_project_id") or ""
        return str(project_id) if project_id else None

    @classmethod
    def set_active_project_id(cls, project_id: str) -> None:
        store = cls._read_store()
        store["active_project_id"] = str(project_id or "")
        cls._write_store(store)

    @classmethod
    def list_projects(cls, limit: int = 20) -> List[Dict[str, Any]]:
        projects = cls._read_store().get("projects", [])
        records = [cls._record_from_project(item, include_draft=True) for item in projects if isinstance(item, dict)]
        records.sort(key=lambda item: item.get("updatedAt") or "", reverse=True)
        return records[:limit]

    @classmethod
    def get_project(cls, project_id: str) -> Optional[Dict[str, Any]]:
        for project in cls._read_store().get("projects", []):
            if isinstance(project, dict) and project.get("id") == project_id:
                return cls._record_from_project(project, include_draft=True)
        return None

    @classmethod
    def get_active_project(cls) -> Optional[Dict[str, Any]]:
        project_id = cls.get_active_project_id()
        if not project_id:
            return None
        return cls.get_project(project_id)

    @classmethod
    def upsert_project(cls, draft: Dict[str, Any], project_id: Optional[str] = None, activate: bool = True) -> Dict[str, Any]:
        store = cls._read_store()
        projects = [item for item in store.get("projects", []) if isinstance(item, dict)]
        now = cls._now()
        stats = cls._stats(draft)
        title = cls._draft_title(draft)
        project_id = project_id or store.get("active_project_id") or cls._new_id()

        existing = next((item for item in projects if item.get("id") == project_id), None)
        created_at = str(existing.get("createdAt") or now) if existing else now
        record = {
            "id": project_id,
            "title": title,
            "draft": draft or {},
            "completed": stats["completed"],
            "total": stats["total"],
            "wordCount": stats["word_count"],
            "createdAt": created_at,
            "updatedAt": now,
        }

        projects = [item for item in projects if item.get("id") != project_id]
        projects.append(record)
        projects.sort(key=lambda item: item.get("updatedAt") or "", reverse=True)
        store["projects"] = projects
        if activate:
            store["active_project_id"] = project_id
        cls._write_store(store)
        return cls.get_project(project_id) or {}

    @classmethod
    def create_project(cls, draft: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        return cls.upsert_project(draft or {}, project_id=cls._new_id(), activate=True)

    @classmethod
    def activate_project(cls, project_id: str) -> Optional[Dict[str, Any]]:
        record = cls.get_project(project_id)
        if record:
            cls.set_active_project_id(project_id)
        return record

    @classmethod
    def delete_project(cls, project_id: str) -> bool:
        store = cls._read_store()
        projects = [item for item in store.get("projects", []) if isinstance(item, dict)]
        before = len(projects)
        projects = [item for item in projects if item.get("id") != project_id]
        if len(projects) == before:
            return False
        store["projects"] = projects
        if store.get("active_project_id") == project_id:
            store["active_project_id"] = projects[0].get("id", "") if projects else ""
        cls._write_store(store)
        return True
