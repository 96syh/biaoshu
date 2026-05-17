"""Helpers for JSON-producing SSE endpoints."""
import asyncio
import json
from typing import Any, Awaitable, AsyncIterator


async def stream_json_task(
    compute: Awaitable[Any],
    error_prefix: str,
    chunk_size: int = 256,
    heartbeat_seconds: float = 1.0,
) -> AsyncIterator[str]:
    """Run a JSON-producing coroutine and stream heartbeats plus result chunks."""
    try:
        compute_task = asyncio.create_task(compute)
        while not compute_task.done():
            yield f"data: {json.dumps({'chunk': ''}, ensure_ascii=False)}\n\n"
            await asyncio.sleep(heartbeat_seconds)

        result_json = json.dumps(await compute_task, ensure_ascii=False)
        for index in range(0, len(result_json), chunk_size):
            yield f"data: {json.dumps({'chunk': result_json[index:index + chunk_size]}, ensure_ascii=False)}\n\n"
    except Exception as e:
        payload = {
            "chunk": "",
            "error": True,
            "message": f"{error_prefix}: {str(e)}",
        }
        yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"

    yield "data: [DONE]\n\n"
