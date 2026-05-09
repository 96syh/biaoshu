"""Pydantic schemas split from app.models.schemas."""
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from enum import Enum


class FileUploadResponse(BaseModel):
    """文件上传响应"""
    success: bool
    message: str
    file_content: Optional[str] = None
    source_preview_html: Optional[str] = Field(None, description="上传源文件的样式化 HTML 预览片段")
    source_preview_pages: List[Dict[str, Any]] = Field(default_factory=list, description="上传源文件的 Office/PDF 渲染页图和文本块坐标")
    old_outline: Optional[str] = None
    parser_info: Dict[str, Any] = Field(default_factory=dict, description="文档解析器、输出格式和降级信息")
    reference_bid_style_profile: Dict[str, Any] = Field(default_factory=dict, description="样例投标文件风格剖面")
    document_blocks_plan: Dict[str, Any] = Field(default_factory=dict, description="图表、承诺书、图片、附件等文档块规划")
