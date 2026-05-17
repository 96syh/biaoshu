"""Reference-style and visual-asset routes."""

from fastapi import APIRouter, File, HTTPException, UploadFile

from ..models.schemas import (
    DocumentBlocksPlanRequest,
    FileUploadResponse,
    VisualAssetGenerationRequest,
    VisualAssetGenerationResponse,
)
from ..services.file_service import FileService
from ..services.openai_service import OpenAIService
from ..services.visual_asset_service import generate_visual_asset_response
from ..utils.config_manager import config_manager
from ..utils.provider_registry import get_provider_auth_error
from ..utils.streaming_json import stream_json_task
from ..utils.sse import sse_response


class AssetController:
    """成熟样例、图表规划和视觉素材控制器。"""

    def __init__(self) -> None:
        self.router = APIRouter(prefix="/api/document", tags=["图表素材"])
        self.router.post("/reference-style-upload")(self.reference_style_upload)
        self.router.post("/generate-visual-asset", response_model=VisualAssetGenerationResponse)(self.generate_visual_asset)
        self.router.post("/document-blocks-plan-stream")(self.document_blocks_plan_stream)

    @staticmethod
    def _validate_model_auth() -> None:
        config = config_manager.load_config()
        auth_error = get_provider_auth_error(config.get("provider"), config.get("api_key"))
        if auth_error:
            raise HTTPException(status_code=400, detail=auth_error)

    @staticmethod
    def _merge_parser_images_into_profile(profile: dict, parser_info: dict) -> None:
        image_assets = parser_info.get("image_assets") if isinstance(parser_info, dict) else []
        image_slots = profile.get("image_slots") if isinstance(profile, dict) else []
        if isinstance(image_assets, list) and isinstance(image_slots, list):
            for index, slot in enumerate(image_slots):
                if not isinstance(slot, dict) or index >= len(image_assets):
                    continue
                asset = image_assets[index] if isinstance(image_assets[index], dict) else {}
                if asset.get("url") and not slot.get("image_url"):
                    slot["image_url"] = asset.get("url")
                if asset.get("alt") and not slot.get("image_alt"):
                    slot["image_alt"] = asset.get("alt")
                if asset.get("source_path") and not slot.get("source_ref"):
                    slot["source_ref"] = asset.get("source_path")

    async def reference_style_upload(self, file: UploadFile = File(...)):
        """上传成熟投标文件样例并生成可复用风格剖面"""
        try:
            file_kind = FileService.detect_upload_file_kind(file)
            if file_kind in (None, "doc"):
                return FileUploadResponse(success=False, message=FileService.get_upload_validation_message(file))

            parse_result = await FileService.process_uploaded_file_with_metadata(file)
            file_content = parse_result.get("file_content", "")
            parser_info = parse_result.get("parser_info", {})
            self._validate_model_auth()

            profile = await OpenAIService().generate_reference_bid_style_profile(file_content)
            self._merge_parser_images_into_profile(profile, parser_info)
            return FileUploadResponse(
                success=True,
                message=f"样例文件 {file.filename} 已通过 {parser_info.get('parser') or '文档解析器'} 解析，并生成写作模板剖面",
                file_content=file_content,
                parser_info=parser_info,
                reference_bid_style_profile=profile,
            )
        except HTTPException as e:
            return FileUploadResponse(success=False, message=e.detail)
        except Exception as e:
            return FileUploadResponse(success=False, message=f"样例解析失败: {str(e)}")

    async def generate_visual_asset(self, request: VisualAssetGenerationRequest):
        """调用图片模型生成投标文件图表素材。"""
        return await generate_visual_asset_response(request)

    async def document_blocks_plan_stream(self, request: DocumentBlocksPlanRequest):
        """生成图表、表格、图片、承诺书和附件规划"""
        try:
            self._validate_model_auth()

            async def generate():
                service = OpenAIService()
                async for event in stream_json_task(
                    service.generate_document_blocks_plan(
                        outline=[item.model_dump(mode="json") for item in request.outline],
                        analysis_report=request.analysis_report.model_dump(mode="json") if request.analysis_report else None,
                        response_matrix=request.response_matrix.model_dump(mode="json") if request.response_matrix else None,
                        reference_bid_style_profile=request.reference_bid_style_profile,
                        enterprise_materials=[item.model_dump(mode="json") for item in request.enterprise_materials],
                        asset_library=request.asset_library,
                    ),
                    "图表素材规划失败",
                ):
                    yield event

            return sse_response(generate())
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"图表素材规划失败: {str(e)}")


controller = AssetController()
router = controller.router
