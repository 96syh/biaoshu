"""本地项目数据库服务。"""
from __future__ import annotations

import json
import os
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


class ProjectService:
    """用 SQLite 保存项目草稿，替代浏览器缓存作为主存储。"""

    DB_PATH = Path(
        os.getenv(
            "YIBIAO_PROJECT_DB_PATH",
            str(Path(__file__).resolve().parents[3] / "artifacts" / "data" / "projects.sqlite3"),
        )
    )

    @classmethod
    def _connect(cls) -> sqlite3.Connection:
        cls.DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(cls.DB_PATH))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        cls._ensure_schema(conn)
        return conn

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def _new_id() -> str:
        return f"project-{uuid.uuid4().hex[:12]}"

    @classmethod
    def _ensure_schema(cls, conn: sqlite3.Connection) -> None:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS projects (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                draft_json TEXT NOT NULL,
                completed INTEGER NOT NULL DEFAULT 0,
                total INTEGER NOT NULL DEFAULT 0,
                word_count INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS app_meta (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
            """
        )
        conn.commit()

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
    def _row_to_record(row: sqlite3.Row, include_draft: bool = True) -> Dict[str, Any]:
        record = {
            "id": row["id"],
            "title": row["title"],
            "createdAt": row["created_at"],
            "updatedAt": row["updated_at"],
            "completed": row["completed"],
            "total": row["total"],
            "wordCount": row["word_count"],
        }
        if include_draft:
            try:
                record["draft"] = json.loads(row["draft_json"])
            except Exception:
                record["draft"] = {}
        return record

    @classmethod
    def get_active_project_id(cls) -> Optional[str]:
        with cls._connect() as conn:
            row = conn.execute("SELECT value FROM app_meta WHERE key='active_project_id'").fetchone()
            return str(row["value"]) if row else None

    @classmethod
    def set_active_project_id(cls, project_id: str) -> None:
        with cls._connect() as conn:
            conn.execute(
                "INSERT INTO app_meta(key, value) VALUES('active_project_id', ?) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (project_id,),
            )
            conn.commit()

    @classmethod
    def list_projects(cls, limit: int = 20) -> List[Dict[str, Any]]:
        with cls._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM projects ORDER BY updated_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
            return [cls._row_to_record(row, include_draft=True) for row in rows]

    @classmethod
    def get_project(cls, project_id: str) -> Optional[Dict[str, Any]]:
        with cls._connect() as conn:
            row = conn.execute("SELECT * FROM projects WHERE id=?", (project_id,)).fetchone()
            return cls._row_to_record(row, include_draft=True) if row else None

    @classmethod
    def get_active_project(cls) -> Optional[Dict[str, Any]]:
        project_id = cls.get_active_project_id()
        if not project_id:
            return None
        return cls.get_project(project_id)

    @classmethod
    def upsert_project(cls, draft: Dict[str, Any], project_id: Optional[str] = None, activate: bool = True) -> Dict[str, Any]:
        now = cls._now()
        stats = cls._stats(draft)
        title = cls._draft_title(draft)
        project_id = project_id or cls.get_active_project_id() or cls._new_id()
        draft_json = json.dumps(draft or {}, ensure_ascii=False)

        with cls._connect() as conn:
            existing = conn.execute("SELECT created_at FROM projects WHERE id=?", (project_id,)).fetchone()
            created_at = existing["created_at"] if existing else now
            conn.execute(
                """
                INSERT INTO projects(id, title, draft_json, completed, total, word_count, created_at, updated_at)
                VALUES(?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    title=excluded.title,
                    draft_json=excluded.draft_json,
                    completed=excluded.completed,
                    total=excluded.total,
                    word_count=excluded.word_count,
                    updated_at=excluded.updated_at
                """,
                (
                    project_id,
                    title,
                    draft_json,
                    stats["completed"],
                    stats["total"],
                    stats["word_count"],
                    created_at,
                    now,
                ),
            )
            if activate:
                conn.execute(
                    "INSERT INTO app_meta(key, value) VALUES('active_project_id', ?) "
                    "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                    (project_id,),
                )
            conn.commit()

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
        with cls._connect() as conn:
            cursor = conn.execute("DELETE FROM projects WHERE id=?", (project_id,))
            active = conn.execute("SELECT value FROM app_meta WHERE key='active_project_id'").fetchone()
            if active and active["value"] == project_id:
                next_row = conn.execute(
                    "SELECT id FROM projects ORDER BY updated_at DESC LIMIT 1"
                ).fetchone()
                if next_row:
                    conn.execute(
                        "UPDATE app_meta SET value=? WHERE key='active_project_id'",
                        (next_row["id"],),
                    )
                else:
                    conn.execute("DELETE FROM app_meta WHERE key='active_project_id'")
            conn.commit()
            return cursor.rowcount > 0
