"""Export routes."""
from fastapi import APIRouter

from ..models.schemas import WordExportRequest
from ..services.word_export_service import create_word_export_response


class ExportController:
    """Word 导出控制器。"""

    def __init__(self) -> None:
        self.router = APIRouter(prefix="/api/document", tags=["导出"])
        self.router.post("/export-word")(self.export_word)

    async def export_word(self, request: WordExportRequest):
        """根据目录数据导出Word文档"""
        return await create_word_export_response(request)


controller = ExportController()
router = controller.router
