"""Review and consistency-revision routes."""
from fastapi import APIRouter, HTTPException

from ..models.schemas import ComplianceReviewRequest, ConsistencyRevisionRequest
from ..services.openai_service import OpenAIService
from ..utils.config_manager import config_manager
from ..utils.provider_registry import get_provider_auth_error
from ..utils.streaming_json import stream_json_task
from ..utils.sse import sse_response


class ReviewController:
    """一致性修订和导出前合规审校控制器。"""

    def __init__(self) -> None:
        self.router = APIRouter(prefix="/api/document", tags=["审校"])
        self.router.post("/consistency-revision-stream")(self.consistency_revision_stream)
        self.router.post("/review-compliance-stream")(self.review_compliance_stream)

    @staticmethod
    def _validate_model_auth() -> None:
        config = config_manager.load_config()
        auth_error = get_provider_auth_error(config.get("provider"), config.get("api_key"))
        if auth_error:
            raise HTTPException(status_code=400, detail=auth_error)

    async def consistency_revision_stream(self, request: ConsistencyRevisionRequest):
        """生成全文一致性修订报告"""
        try:
            self._validate_model_auth()

            async def generate():
                service = OpenAIService()
                async for event in stream_json_task(
                    service.generate_consistency_revision_report(
                        full_bid_draft=[item.model_dump(mode="json") for item in request.full_bid_draft],
                        analysis_report=request.analysis_report.model_dump(mode="json") if request.analysis_report else None,
                        response_matrix=request.response_matrix.model_dump(mode="json") if request.response_matrix else None,
                        reference_bid_style_profile=request.reference_bid_style_profile,
                        document_blocks_plan=request.document_blocks_plan,
                    ),
                    "全文一致性修订失败",
                ):
                    yield event

            return sse_response(generate())
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"全文一致性修订失败: {str(e)}")

    async def review_compliance_stream(self, request: ComplianceReviewRequest):
        """导出前执行覆盖性、缺料、废标风险和虚构风险审校"""
        try:
            self._validate_model_auth()
            openai_service = OpenAIService()

            async def generate():
                async for event in stream_json_task(
                    openai_service.generate_compliance_review(
                        outline=[item.model_dump(mode="json") for item in request.outline],
                        analysis_report=(
                            request.analysis_report.model_dump(mode="json")
                            if request.analysis_report else None
                        ),
                        response_matrix=(
                            request.response_matrix.model_dump(mode="json")
                            if request.response_matrix else None
                        ),
                        project_overview=request.project_overview or "",
                        reference_bid_style_profile=request.reference_bid_style_profile,
                        document_blocks_plan=request.document_blocks_plan,
                    ),
                    "导出前合规审校失败",
                ):
                    yield event

            return sse_response(generate())
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"导出前合规审校失败: {str(e)}")


controller = ReviewController()
router = controller.router
