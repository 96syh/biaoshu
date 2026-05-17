"""内容相关API路由"""
from fastapi import APIRouter, HTTPException
from ..models.schemas import ContentGenerationRequest, ChapterContentRequest
from ..services.history_case_service import HistoryCaseService
from ..services.openai_service import OpenAIService
from ..utils.config_manager import config_manager
from ..utils.provider_registry import get_provider_auth_error
from ..utils.sse import sse_response
import json


class ChapterContentController:
    """章节正文生成控制器。"""

    def __init__(self) -> None:
        self.router = APIRouter(prefix="/api/content", tags=["内容管理"])
        self.router.post("/generate-chapter")(self.generate_chapter_content)
        self.router.post("/generate-chapter-stream")(self.generate_chapter_content_stream)

    @staticmethod
    def _chapter_log_name(chapter: dict | None) -> str:
        if not isinstance(chapter, dict):
            return "unknown 未命名章节"
        chapter_id = str(chapter.get("id") or "unknown").strip() or "unknown"
        title = str(chapter.get("title") or "未命名章节").strip() or "未命名章节"
        return f"{chapter_id} {title}"

    def _log_flow(self, chapter: dict | None, message: str) -> None:
        print(f"[正文生成流程图] {self._chapter_log_name(chapter)} | {message}", flush=True)

    @staticmethod
    def _analysis_report_with_enterprise_profile(request: ChapterContentRequest):
        report = request.analysis_report.model_dump(mode="json") if request.analysis_report else None
        profile = request.enterprise_material_profile.model_dump(mode="json") if request.enterprise_material_profile else {}
        if report is not None and profile.get("requirements"):
            report["enterprise_material_profile"] = profile
        return report

    @staticmethod
    def _response_matrix(request: ChapterContentRequest):
        return request.response_matrix.model_dump(mode="json") if request.response_matrix else None

    def _validate_model_auth(self, request: ChapterContentRequest):
        config = config_manager.load_config()
        auth_error = get_provider_auth_error(config.get("provider"), config.get("api_key"))
        if auth_error:
            self._log_flow(request.chapter, f"D=校验模型配置和 API Key：失败 -> N=返回错误；原因={auth_error}")
            raise HTTPException(status_code=400, detail=auth_error)
        self._log_flow(
            request.chapter,
            f"D=校验模型配置和 API Key：成功；provider={config.get('provider') or 'unknown'}",
        )

    def _history_reference_drafts(
        self,
        request: ChapterContentRequest,
        analysis_report,
        response_matrix,
    ):
        if request.history_reference_drafts:
            self._log_flow(
                request.chapter,
                f"E=检索历史相似章节：使用前端/上游已传入候选；count={len(request.history_reference_drafts)}",
            )
            return request.history_reference_drafts
        try:
            self._log_flow(request.chapter, "E=检索历史相似章节：后端开始按当前章节检索历史库")
            drafts = HistoryCaseService.find_chapter_reference_drafts(
                chapter=request.chapter,
                parent_chapters=request.parent_chapters or [],
                sibling_chapters=request.sibling_chapters or [],
                analysis_report=analysis_report or {},
                response_matrix=response_matrix or {},
                limit=3,
            )
            levels = [
                str(draft.get("match_level") or "unknown")
                for draft in drafts
                if isinstance(draft, dict)
            ]
            self._log_flow(
                request.chapter,
                f"E=检索历史相似章节：完成；count={len(drafts)}；match_levels={levels[:5]}",
            )
            return drafts
        except Exception as exc:
            self._log_flow(request.chapter, f"E=检索历史相似章节：失败 -> F=无历史候选 -> J=回退自主正文生成；原因={exc}")
            return []

    async def _chapter_chunks(
        self,
        openai_service: OpenAIService,
        request: ChapterContentRequest,
        analysis_report,
        response_matrix,
        history_reference_drafts,
    ):
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
            yield chunk

    def _prepare_generation(self, request: ChapterContentRequest):
        self._validate_model_auth(request)
        analysis_report = self._analysis_report_with_enterprise_profile(request)
        response_matrix = self._response_matrix(request)
        history_reference_drafts = self._history_reference_drafts(request, analysis_report, response_matrix)
        return OpenAIService(), analysis_report, response_matrix, history_reference_drafts

    async def generate_chapter_content(self, request: ChapterContentRequest):
        """为单个章节生成内容"""
        try:
            self._log_flow(request.chapter, "C=POST /api/content/generate-chapter：收到非流式正文生成请求")
            openai_service, analysis_report, response_matrix, history_reference_drafts = self._prepare_generation(request)

            content = ""
            async for chunk in self._chapter_chunks(
                openai_service,
                request,
                analysis_report,
                response_matrix,
                history_reference_drafts,
            ):
                content += chunk
            render = getattr(openai_service, "_last_chapter_render", {}) or {}
            content = openai_service._strip_generated_markdown_headings(content)
            self._log_flow(
                request.chapter,
                f"O=去掉章节标题/Markdown heading：完成；P=返回 completed；content_chars={len(content)}",
            )
            return {"success": True, "content": content, **render}
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"章节内容生成失败: {str(e)}")

    async def generate_chapter_content_stream(self, request: ChapterContentRequest):
        """流式为单个章节生成内容"""
        try:
            self._log_flow(request.chapter, "C=POST /api/content/generate-chapter-stream：收到流式正文生成请求")
            openai_service, analysis_report, response_matrix, history_reference_drafts = self._prepare_generation(request)

            async def generate():
                try:
                    self._log_flow(request.chapter, "P=SSE 返回 started：开始生成章节内容")
                    yield f"data: {json.dumps({'status': 'started', 'message': '开始生成章节内容...'}, ensure_ascii=False)}\n\n"

                    full_content = ""
                    async for chunk in self._chapter_chunks(
                        openai_service,
                        request,
                        analysis_report,
                        response_matrix,
                        history_reference_drafts,
                    ):
                        full_content += chunk
                        safe_full_content = openai_service._strip_generated_markdown_headings(full_content)
                        yield f"data: {json.dumps({'status': 'streaming', 'content': chunk, 'full_content': safe_full_content}, ensure_ascii=False)}\n\n"

                    if not full_content.strip():
                        self._log_flow(request.chapter, "K=按 prompt 流式生成正文：模型返回空内容 -> N=返回错误")
                        raise Exception("模型返回空内容，可能是配额限制、内容拦截或兼容模式异常")

                    render = getattr(openai_service, "_last_chapter_render", {}) or {}
                    payload = {'status': 'completed', 'content': openai_service._strip_generated_markdown_headings(full_content), **render}
                    self._log_flow(
                        request.chapter,
                        f"O=去掉章节标题/Markdown heading：完成；P=SSE 返回 completed；content_chars={len(payload['content'])}",
                    )
                    yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
                except Exception as e:
                    self._log_flow(request.chapter, f"N=返回错误；P=SSE 返回 error；原因={e}")
                    yield f"data: {json.dumps({'status': 'error', 'message': str(e)}, ensure_ascii=False)}\n\n"

                self._log_flow(request.chapter, "P=SSE 返回 [DONE]：本章流程结束")
                yield "data: [DONE]\n\n"

            return sse_response(generate())
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"章节内容生成失败: {str(e)}")


controller = ChapterContentController()
router = controller.router
