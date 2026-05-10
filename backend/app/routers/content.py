"""内容相关API路由"""
from fastapi import APIRouter, HTTPException
from ..models.schemas import ContentGenerationRequest, ChapterContentRequest
from ..services.history_case_service import HistoryCaseService
from ..services.openai_service import OpenAIService
from ..utils.config_manager import config_manager
from ..utils.provider_registry import get_provider_auth_error
from ..utils.sse import sse_response
import json

router = APIRouter(prefix="/api/content", tags=["内容管理"])


def request_analysis_report_with_enterprise_profile(request: ChapterContentRequest):
    report = request.analysis_report.model_dump(mode="json") if request.analysis_report else None
    profile = request.enterprise_material_profile.model_dump(mode="json") if request.enterprise_material_profile else {}
    if report is not None and profile.get("requirements"):
        report["enterprise_material_profile"] = profile
    return report


def request_response_matrix(request: ChapterContentRequest):
    return request.response_matrix.model_dump(mode="json") if request.response_matrix else None


def request_history_reference_drafts(
    request: ChapterContentRequest,
    analysis_report,
    response_matrix,
):
    if request.history_reference_drafts:
        return request.history_reference_drafts
    try:
        return HistoryCaseService.find_chapter_reference_drafts(
            chapter=request.chapter,
            parent_chapters=request.parent_chapters or [],
            sibling_chapters=request.sibling_chapters or [],
            analysis_report=analysis_report or {},
            response_matrix=response_matrix or {},
            limit=3,
        )
    except Exception as exc:
        print(f"历史章节参考检索失败，继续直接生成正文：{exc}")
        return []


@router.post("/generate-chapter")
async def generate_chapter_content(request: ChapterContentRequest):
    """为单个章节生成内容"""
    try:
        # 加载配置
        config = config_manager.load_config()
        auth_error = get_provider_auth_error(config.get("provider"), config.get("api_key"))
        if auth_error:
            raise HTTPException(status_code=400, detail=auth_error)

        # 创建OpenAI服务实例
        openai_service = OpenAIService()
        analysis_report = request_analysis_report_with_enterprise_profile(request)
        response_matrix = request_response_matrix(request)
        history_reference_drafts = request_history_reference_drafts(request, analysis_report, response_matrix)
        
        # 生成单章节内容
        content = ""
        async for chunk in openai_service._generate_chapter_content(
            chapter=request.chapter,
            parent_chapters=request.parent_chapters,
            sibling_chapters=request.sibling_chapters,
            project_overview=request.project_overview,
            analysis_report=analysis_report,
            response_matrix=response_matrix,
            bid_mode=request.bid_mode.value if request.bid_mode else None,
            reference_bid_style_profile=request.reference_bid_style_profile,
            document_blocks_plan=request.document_blocks_plan,
            history_reference_drafts=history_reference_drafts,
            generated_summaries=[
                item.model_dump(mode="json") for item in request.generated_summaries
            ],
            enterprise_materials=[
                item.model_dump(mode="json") for item in request.enterprise_materials
            ],
            missing_materials=[
                item.model_dump(mode="json") for item in request.missing_materials
            ],
        ):
            content += chunk
        render = getattr(openai_service, "_last_chapter_render", {}) or {}
        return {"success": True, "content": content, **render}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"章节内容生成失败: {str(e)}")


@router.post("/generate-chapter-stream")
async def generate_chapter_content_stream(request: ChapterContentRequest):
    """流式为单个章节生成内容"""
    try:
        # 加载配置
        config = config_manager.load_config()
        auth_error = get_provider_auth_error(config.get("provider"), config.get("api_key"))
        if auth_error:
            raise HTTPException(status_code=400, detail=auth_error)

        # 创建OpenAI服务实例
        openai_service = OpenAIService()
        analysis_report = request_analysis_report_with_enterprise_profile(request)
        response_matrix = request_response_matrix(request)
        history_reference_drafts = request_history_reference_drafts(request, analysis_report, response_matrix)
        
        async def generate():
            try:
                # 发送开始信号
                yield f"data: {json.dumps({'status': 'started', 'message': '开始生成章节内容...'}, ensure_ascii=False)}\n\n"
                
                # 流式生成章节内容
                full_content = ""
                async for chunk in openai_service._generate_chapter_content(
                    chapter=request.chapter,
                    parent_chapters=request.parent_chapters,
                    sibling_chapters=request.sibling_chapters,
                    project_overview=request.project_overview,
                    analysis_report=analysis_report,
                    response_matrix=response_matrix,
                    bid_mode=request.bid_mode.value if request.bid_mode else None,
                    reference_bid_style_profile=request.reference_bid_style_profile,
                    document_blocks_plan=request.document_blocks_plan,
                    history_reference_drafts=history_reference_drafts,
                    generated_summaries=[
                        item.model_dump(mode="json") for item in request.generated_summaries
                    ],
                    enterprise_materials=[
                        item.model_dump(mode="json") for item in request.enterprise_materials
                    ],
                    missing_materials=[
                        item.model_dump(mode="json") for item in request.missing_materials
                    ],
                ):
                    full_content += chunk
                    # 实时发送内容片段
                    yield f"data: {json.dumps({'status': 'streaming', 'content': chunk, 'full_content': full_content}, ensure_ascii=False)}\n\n"

                if not full_content.strip():
                    raise Exception("模型返回空内容，可能是配额限制、内容拦截或兼容模式异常")
                
                # 发送完成信号
                render = getattr(openai_service, "_last_chapter_render", {}) or {}
                payload = {'status': 'completed', 'content': full_content, **render}
                yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
                
            except Exception as e:
                # 发送错误信息
                yield f"data: {json.dumps({'status': 'error', 'message': str(e)}, ensure_ascii=False)}\n\n"
            
            # 发送结束信号
            yield "data: [DONE]\n\n"
        
        return sse_response(generate())
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"章节内容生成失败: {str(e)}")
