"""目录相关API路由"""
from fastapi import APIRouter, HTTPException
from ..models.schemas import OutlineRequest, OutlineResponse
from ..services.openai_service import OpenAIService
from ..utils.config_manager import config_manager
from ..utils.provider_registry import get_provider_auth_error
from ..utils.sse import sse_response
import json
import asyncio

router = APIRouter(prefix="/api/outline", tags=["目录管理"])


@router.post("/generate")
async def generate_outline(request: OutlineRequest):
    """生成标书目录结构（以SSE流式返回）"""
    try:
        # 加载配置
        config = config_manager.load_config()
        auth_error = get_provider_auth_error(config.get("provider"), config.get("api_key"))
        if auth_error:
            raise HTTPException(status_code=400, detail=auth_error)

        # 创建OpenAI服务实例
        openai_service = OpenAIService()
        
        async def generate():
            try:
                # 后台计算主任务
                compute_task = asyncio.create_task(openai_service.generate_outline_v2(
                    overview=request.overview,
                    requirements=request.requirements,
                    analysis_report=(
                        request.analysis_report.model_dump(mode="json")
                        if request.analysis_report else None
                    ),
                    bid_mode=request.bid_mode.value if request.bid_mode else None,
                ))

                # 在等待计算完成期间发送心跳，保持连接（发送空字符串chunk）
                while not compute_task.done():
                    yield f"data: {json.dumps({'chunk': ''}, ensure_ascii=False)}\n\n"
                    await asyncio.sleep(1)

                # 计算完成
                result = await compute_task

                # 确保为字符串
                if isinstance(result, dict):
                    result_str = json.dumps(result, ensure_ascii=False)
                else:
                    result_str = str(result)

                # 分片发送实际数据
                chunk_size = 128
                chunk_delay = 0.1  # 每个分片之间增加一点点延迟，增强SSE逐步展示效果
                for i in range(0, len(result_str), chunk_size):
                    piece = result_str[i:i+chunk_size]
                    yield f"data: {json.dumps({'chunk': piece}, ensure_ascii=False)}\n\n"
                    await asyncio.sleep(chunk_delay)
                # 发送结束信号
                yield "data: [DONE]\n\n"
            except Exception as e:
                # 捕获后台任务中的异常，通过 SSE 友好返回给前端
                error_message = f"目录生成失败: {str(e)}"
                payload = {
                    "chunk": "",
                    "error": True,
                    "message": error_message,
                }
                yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
                yield "data: [DONE]\n\n"

        return sse_response(generate())
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"目录生成失败: {str(e)}")


@router.post("/generate-stream")
async def generate_outline_stream(request: OutlineRequest):
    """流式生成标书目录结构"""
    try:
        # 加载配置
        config = config_manager.load_config()
        auth_error = get_provider_auth_error(config.get("provider"), config.get("api_key"))
        if auth_error:
            raise HTTPException(status_code=400, detail=auth_error)

        # 创建OpenAI服务实例
        openai_service = OpenAIService()

        async def generate():
            try:
                merged_requirements = request.requirements
                if request.uploaded_expand and request.old_outline:
                    merged_requirements = (
                        f"{request.requirements}\n\n"
                        f"用户已有目录参考：\n{request.old_outline}"
                    )

                compute_task = asyncio.create_task(
                    openai_service.generate_outline_v2(
                        overview=request.overview,
                        requirements=merged_requirements,
                        analysis_report=(
                            request.analysis_report.model_dump(mode="json")
                            if request.analysis_report else None
                        ),
                        bid_mode=request.bid_mode.value if request.bid_mode else None,
                    )
                )

                while not compute_task.done():
                    yield f"data: {json.dumps({'chunk': ''}, ensure_ascii=False)}\n\n"
                    await asyncio.sleep(1)

                outline_json = json.dumps(await compute_task, ensure_ascii=False)
                chunk_size = 256
                for index in range(0, len(outline_json), chunk_size):
                    piece = outline_json[index:index + chunk_size]
                    yield f"data: {json.dumps({'chunk': piece}, ensure_ascii=False)}\n\n"
            except Exception as e:
                payload = {
                    "chunk": "",
                    "error": True,
                    "message": f"目录生成失败: {str(e)}",
                }
                yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"

            yield "data: [DONE]\n\n"
        
        return sse_response(generate())
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"目录生成失败: {str(e)}")
