"""Prompt helpers split from app.utils.prompt_manager."""
from __future__ import annotations

import json
from typing import Any


def _json(data: Any, *, indent: int | None = None) -> str:
    return json.dumps(data, ensure_ascii=False, indent=indent, separators=None if indent else (",", ":"))


def _schema_contract(schema_name: str, schema_json: str, include_schema: bool) -> str:
    if include_schema:
        return f"JSON schema：\n{schema_json}"
    return f"输出必须符合 {schema_name} 结构；结构由 API response_format/json_schema 约束。"


def get_full_bid_rulebook() -> str:
    """跨行业标书风控规则，供所有阶段复用。"""
    return """按照上述要求生成正文内容："""
