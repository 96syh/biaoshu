"""Generation policy switches shared by model-backed workflows."""
from __future__ import annotations

import os
import re
from typing import Callable


def generation_fallbacks_enabled() -> bool:
    """Whether model-backed generation may return deterministic fallback results."""
    return os.getenv("YIBIAO_ENABLE_GENERATION_FALLBACKS", "0").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def force_local_fallback() -> bool:
    """Local smoke-test fallback only takes effect when fallbacks are explicitly enabled."""
    return generation_fallbacks_enabled() and os.getenv("YIBIAO_FORCE_LOCAL_FALLBACK") == "1"


def compact_text(text: str, limit: int = 120) -> str:
    """Compress long error text for user-facing failure messages."""
    normalized = re.sub(r"\s+", " ", str(text or "")).strip()
    return normalized[:limit]


def fallback_disabled_error(
    stage: str,
    reason: str,
    compact: Callable[[str, int], str] = compact_text,
) -> Exception:
    """Build a consistent error when fallback results are not allowed."""
    return Exception(
        f"{stage}失败，未返回兜底结果。当前 YIBIAO_ENABLE_GENERATION_FALLBACKS=0；"
        f"如需临时启用兜底，请显式设置为 1。原因：{compact(reason, 220)}"
    )
