"""内容相关API路由"""
from fastapi import APIRouter, HTTPException
from ..models.schemas import ContentGenerationRequest, ChapterContentRequest
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
        
        # 生成单章节内容
        content = ""
        async for chunk in openai_service._generate_chapter_content(
            chapter=request.chapter,
            parent_chapters=request.parent_chapters,
            sibling_chapters=request.sibling_chapters,
            project_overview=request.project_overview,
            analysis_report=(
                request_analysis_report_with_enterprise_profile(request)
            ),
            response_matrix=(
                request.response_matrix.model_dump(mode="json")
                if request.response_matrix else None
            ),
            bid_mode=request.bid_mode.value if request.bid_mode else None,
            reference_bid_style_profile=request.reference_bid_style_profile,
            document_blocks_plan=request.document_blocks_plan,
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
        
        return {"success": True, "content": content}
        
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
                    analysis_report=(
                        request_analysis_report_with_enterprise_profile(request)
                    ),
                    response_matrix=(
                        request.response_matrix.model_dump(mode="json")
                        if request.response_matrix else None
                    ),
                    bid_mode=request.bid_mode.value if request.bid_mode else None,
                    reference_bid_style_profile=request.reference_bid_style_profile,
                    document_blocks_plan=request.document_blocks_plan,
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
                yield f"data: {json.dumps({'status': 'completed', 'content': full_content}, ensure_ascii=False)}\n\n"
                
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
