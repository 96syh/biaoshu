"""Pydantic schemas split from app.models.schemas."""
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from enum import Enum
from .analysis import AnalysisReport
from .outline import OutlineItem
from .review import ReviewReport


class ErrorResponse(BaseModel):
    """错误响应"""
    error: str
    detail: Optional[str] = None


class WordExportRequest(BaseModel):
    """Word导出请求"""
    project_name: Optional[str] = Field(None, description="项目名称")
    project_overview: Optional[str] = Field(None, description="项目概述")
    outline: List[OutlineItem] = Field(..., description="目录结构，包含内容")
    analysis_report: Optional[AnalysisReport] = Field(None, description="结构化标准解析报告")
    review_report: Optional[ReviewReport] = Field(None, description="导出前审校报告")
    reference_bid_style_profile: Dict[str, Any] = Field(default_factory=dict, description="成熟样例写作模板和 Word 样式")
    document_blocks_plan: Dict[str, Any] = Field(default_factory=dict, description="图表、承诺书、图片、附件等文档块规划")
    asset_library: Dict[str, Any] = Field(default_factory=dict, description="已生成或已上传的图片素材库")
    manual_review_confirmed: bool = Field(False, description="是否已完成人工复核确认")
    export_dir: Optional[str] = Field(None, description="可选：由本地后端直接保存 Word 的目录")
