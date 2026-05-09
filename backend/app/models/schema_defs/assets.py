"""Pydantic schemas split from app.models.schemas."""
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from enum import Enum
from .analysis import AnalysisReport, EnterpriseMaterialProfile, RequiredMaterial, ResponseMatrix
from .outline import OutlineItem


class DocumentBlocksPlanRequest(BaseModel):
    """图表与素材规划请求"""
    outline: List[OutlineItem] = Field(..., description="目录结构")
    analysis_report: Optional[AnalysisReport] = Field(None, description="结构化标准解析报告")
    response_matrix: Optional[ResponseMatrix] = Field(None, description="响应矩阵")
    reference_bid_style_profile: Dict[str, Any] = Field(default_factory=dict, description="成熟投标文件样例反向建模结果")
    enterprise_materials: List[RequiredMaterial] = Field(default_factory=list, description="企业资料")
    enterprise_material_profile: EnterpriseMaterialProfile = Field(default_factory=EnterpriseMaterialProfile, description="独立企业资料解析画像")
    asset_library: Dict[str, Any] = Field(default_factory=dict, description="素材库")


class VisualAssetGenerationRequest(BaseModel):
    """图表素材图片生成请求"""
    chapter_id: str = Field("", description="章节编号")
    chapter_title: str = Field("", description="章节标题")
    project_name: str = Field("", description="项目名称")
    block: Dict[str, Any] = Field(default_factory=dict, description="图表素材规划块")
    reference_bid_style_profile: Dict[str, Any] = Field(default_factory=dict, description="成熟样例风格剖面")
    size: str = Field("1536x1024", description="图片尺寸")


class VisualAssetGenerationResponse(BaseModel):
    """图表素材图片生成响应"""
    success: bool
    message: str
    prompt: str = ""
    image_url: str = ""
    b64_json: str = ""


class ConsistencyRevisionRequest(BaseModel):
    """全文一致性修订请求"""
    full_bid_draft: List[OutlineItem] = Field(..., description="包含正文内容的目录结构")
    analysis_report: Optional[AnalysisReport] = Field(None, description="结构化标准解析报告")
    response_matrix: Optional[ResponseMatrix] = Field(None, description="响应矩阵")
    reference_bid_style_profile: Dict[str, Any] = Field(default_factory=dict, description="成熟投标文件样例反向建模结果")
    document_blocks_plan: Dict[str, Any] = Field(default_factory=dict, description="图表、承诺书、图片、附件等文档块规划")
