"""Pydantic schemas split from app.models.schemas."""
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from enum import Enum
from .analysis import AnalysisReport, BidMode, ResponseMatrix


class OutlineItem(BaseModel):
    """目录项"""
    id: str
    title: str
    description: str
    volume_id: str = Field("", description="所属卷册ID")
    chapter_type: str = Field("", description="章节类型，如 technical/business/price/form/material/review/service_plan/supply/construction")
    source_type: str = Field("", description="章节来源类型，如 tender_direct_response/scoring_response/profile_expansion/enterprise_showcase")
    fixed_format_sensitive: bool = Field(False, description="是否涉及固定格式")
    price_sensitive: bool = Field(False, description="是否涉及报价")
    anonymity_sensitive: bool = Field(False, description="是否受暗标/匿名要求约束")
    expected_word_count: int = Field(0, description="建议篇幅")
    expected_depth: str = Field("medium", description="建议深度 short/medium/long/very_long")
    expected_blocks: List[str] = Field(default_factory=list, description="预期内容块 paragraph/table/image/org_chart/workflow_chart/commitment_letter/material_attachment")
    enterprise_required: bool = Field(False, description="是否依赖企业资料")
    asset_required: bool = Field(False, description="是否依赖图片、证书、截图或其他素材")
    scoring_item_ids: List[str] = Field(default_factory=list, description="关联技术/商务/价格评分项ID列表")
    requirement_ids: List[str] = Field(default_factory=list, description="关联资格/响应要求ID列表")
    risk_ids: List[str] = Field(default_factory=list, description="关联风险ID列表")
    material_ids: List[str] = Field(default_factory=list, description="关联材料ID列表")
    response_matrix_ids: List[str] = Field(default_factory=list, description="关联响应矩阵ID列表")
    children: Optional[List['OutlineItem']] = None
    content: Optional[str] = None
    content_html: Optional[str] = None
    patch_operations: List[Dict[str, Any]] = Field(default_factory=list)
    history_reference: Dict[str, Any] = Field(default_factory=dict)



# 解决循环引用
OutlineItem.model_rebuild()


class OutlineResponse(BaseModel):
    """目录响应"""
    outline: List[OutlineItem]
    response_matrix: Optional[ResponseMatrix] = Field(None, description="响应矩阵")
    reference_bid_style_profile: Dict[str, Any] = Field(default_factory=dict, description="成熟投标文件样例反向建模结果")
    document_blocks_plan: Dict[str, Any] = Field(default_factory=dict, description="图表、承诺书、图片、附件等文档块规划")
    coverage_summary: str = Field("", description="目录映射覆盖摘要")


class OutlineRequest(BaseModel):
    """目录生成请求"""
    overview: str = Field(..., description="项目概述")
    requirements: str = Field(..., description="技术评分要求")
    file_content: Optional[str] = Field(None, description="招标文件全文，用于目录阶段补齐方案纲要子项")
    uploaded_expand: Optional[bool] = Field(False, description="是否已上传方案扩写文件")
    old_outline: Optional[str] = Field(None, description="上传的方案扩写文件解析出的旧目录JSON")
    old_document: Optional[str] = Field(None, description="上传的方案扩写文件解析出的旧文档")
    analysis_report: Optional[AnalysisReport] = Field(None, description="结构化标准解析报告")
    bid_mode: Optional[BidMode] = Field(None, description="标书生成模式")
    reference_bid_style_profile: Dict[str, Any] = Field(default_factory=dict, description="可选：成熟投标文件样例风格剖面")
    document_blocks_plan: Dict[str, Any] = Field(default_factory=dict, description="可选：图表与素材规划")
