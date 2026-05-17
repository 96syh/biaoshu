"""Document upload and source-preview routes."""
from fastapi import APIRouter, File, HTTPException, UploadFile

from ..models.schemas import FileUploadResponse
from ..services.file_service import FileService


class DocumentUploadController:
    """文档上传、文本解析和源文件预览控制器。"""

    def __init__(self) -> None:
        self.router = APIRouter(prefix="/api/document", tags=["文档上传"])
        self.router.post("/upload", response_model=FileUploadResponse)(self.upload_file)
        self.router.post("/upload-text", response_model=FileUploadResponse)(self.upload_file_text)
        self.router.get("/source-preview/{source_preview_id}", response_model=FileUploadResponse)(self.get_source_preview)

    @staticmethod
    def _validate_upload(file: UploadFile) -> FileUploadResponse | None:
        file_kind = FileService.detect_upload_file_kind(file)
        if file_kind in (None, "doc"):
            return FileUploadResponse(
                success=False,
                message=FileService.get_upload_validation_message(file),
            )
        return None

    @staticmethod
    def _parser_suffix(parser_info: dict) -> tuple[str, str]:
        parser_name = parser_info.get("parser") or "unknown"
        fallback_note = "（已降级到内置解析器）" if parser_info.get("fallback_used") else ""
        return parser_name, fallback_note

    async def upload_file(self, file: UploadFile = File(...)):
        """上传文档文件并提取文本内容"""
        try:
            invalid = self._validate_upload(file)
            if invalid:
                return invalid

            parse_result = await FileService.process_uploaded_file_with_metadata(file)
            file_content = parse_result.get("file_content", "")
            parser_info = parse_result.get("parser_info", {})
            parser_name, fallback_note = self._parser_suffix(parser_info)

            return FileUploadResponse(
                success=True,
                message=f"文件 {file.filename} 上传成功，解析器：{parser_name}{fallback_note}，已在上传阶段转换为 {parser_info.get('format') or '文本'}",
                file_content=file_content,
                source_preview_status=parse_result.get("source_preview_status") or "unavailable",
                source_preview_html=parse_result.get("source_preview_html") or "",
                source_preview_pages=parse_result.get("source_preview_pages") or [],
                parser_info=parser_info,
            )
        except HTTPException:
            raise
        except Exception as e:
            return FileUploadResponse(success=False, message=f"文件处理失败: {str(e)}")

    async def upload_file_text(self, file: UploadFile = File(...)):
        """上传文档文件并只提取文本，源文件预览由独立接口异步获取。"""
        try:
            invalid = self._validate_upload(file)
            if invalid:
                return invalid

            parse_result = await FileService.process_uploaded_file_with_metadata(
                file,
                include_preview=False,
                cleanup_saved_file=False,
            )
            parser_info = parse_result.get("parser_info", {})
            parser_name, fallback_note = self._parser_suffix(parser_info)

            return FileUploadResponse(
                success=True,
                message=f"文件 {file.filename} 文本解析完成，解析器：{parser_name}{fallback_note}，原文预览将后台生成",
                file_content=parse_result.get("file_content", ""),
                source_preview_id=parse_result.get("source_preview_id"),
                source_preview_status=parse_result.get("source_preview_status") or "unavailable",
                parser_info=parser_info,
            )
        except HTTPException:
            raise
        except Exception as e:
            return FileUploadResponse(success=False, message=f"文件处理失败: {str(e)}")

    async def get_source_preview(self, source_preview_id: str):
        """为已上传 DOCX 单独生成源文件预览，避免拖慢主上传链路。"""
        try:
            preview_result = FileService.build_source_preview_for_saved_file(source_preview_id)
            return FileUploadResponse(
                success=True,
                message="源文件预览生成完成" if preview_result.get("source_preview_status") == "ready" else "该文件暂无可用源文件预览",
                source_preview_status=preview_result.get("source_preview_status") or "unavailable",
                source_preview_html=preview_result.get("source_preview_html") or "",
                source_preview_pages=preview_result.get("source_preview_pages") or [],
                parser_info=preview_result.get("parser_info") or {},
            )
        except Exception as e:
            return FileUploadResponse(
                success=False,
                message=f"源文件预览生成失败: {str(e)}",
                source_preview_status="unavailable",
            )


controller = DocumentUploadController()
router = controller.router
