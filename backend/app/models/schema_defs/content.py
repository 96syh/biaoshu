"""Pydantic schemas split from app.models.schemas."""
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from enum import Enum
from .analysis import AnalysisReport, BidMode, EnterpriseMaterialProfile, MissingCompanyMaterial, RequiredMaterial, ResponseMatrix
from .config import ConfigRequest


class ContentGenerationRequest(BaseModel):
    """内容生成请求"""
    outline: Dict[str, Any] = Field(..., description="目录结构")
    project_overview: str = Field("", description="项目概述")


class GeneratedSummary(BaseModel):
    """已生成章节摘要"""
    chapter_id: str = Field(..., description="章节ID")
    summary: str = Field("", description="章节摘要")


class ChapterContentRequest(BaseModel):
    """单章节内容生成请求"""
    chapter: Dict[str, Any] = Field(..., description="章节信息")
    parent_chapters: Optional[List[Dict[str, Any]]] = Field(None, description="上级章节列表")
    sibling_chapters: Optional[List[Dict[str, Any]]] = Field(None, description="同级章节列表")
    project_overview: str = Field("", description="项目概述")
    analysis_report: Optional[AnalysisReport] = Field(None, description="结构化标准解析报告")
    response_matrix: Optional[ResponseMatrix] = Field(None, description="响应矩阵")
    bid_mode: Optional[BidMode] = Field(None, description="标书生成模式")
    reference_bid_style_profile: Dict[str, Any] = Field(default_factory=dict, description="可选：样例风格剖面")
    document_blocks_plan: Dict[str, Any] = Field(default_factory=dict, description="可选：图表与素材规划")
    history_reference_drafts: List[Dict[str, Any]] = Field(default_factory=list, description="可选：历史标书相似章节参考草稿")
    generated_summaries: List[GeneratedSummary] = Field(default_factory=list, description="已生成章节摘要")
    enterprise_materials: List[RequiredMaterial] = Field(default_factory=list, description="已提供企业材料")
    enterprise_material_profile: EnterpriseMaterialProfile = Field(default_factory=EnterpriseMaterialProfile, description="独立企业资料解析画像")
    missing_materials: List[MissingCompanyMaterial] = Field(default_factory=list, description="待补企业资料")
    asset_library: Dict[str, Any] = Field(default_factory=dict, description="可选：图片、证书、截图、效果图等素材库")


class AnalysisReportRequest(BaseModel):
    """结构化解析报告生成请求"""
    file_content: str = Field(..., description="招标文件内容")
    config: Optional[ConfigRequest] = Field(None, description="可选：本次解析使用的运行时模型配置")


class AnalysisTaskControlRequest(BaseModel):
    """标准解析任务控制请求"""
    action: str = Field(..., description="pause/resume/stop")


class AnalysisTaskControlResponse(BaseModel):
    """标准解析任务控制响应"""
    success: bool
    message: str
    task_id: str = ""
    status: str = ""
