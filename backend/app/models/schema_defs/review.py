"""Pydantic schemas split from app.models.schemas."""
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from enum import Enum
from .analysis import AnalysisReport, BidMode, ResponseMatrix
from .outline import OutlineItem


class ReviewCoverageItem(BaseModel):
    """评分项覆盖检查结果"""
    item_id: str = Field("", description="评分项或要求ID")
    target_type: str = Field("", description="检查对象类型")
    covered: bool = Field(False, description="是否已覆盖")
    chapter_ids: List[str] = Field(default_factory=list, description="覆盖该项的章节ID")
    issue: str = Field("", description="问题说明")
    evidence: str = Field("", description="覆盖证据")
    fix_suggestion: str = Field("", description="修复建议")


class ReviewMissingMaterialItem(BaseModel):
    """缺失材料检查结果"""
    material_id: str = Field("", description="材料ID")
    material_name: str = Field("", description="材料名称")
    used_by: List[str] = Field(default_factory=list, description="被哪些要求引用")
    chapter_ids: List[str] = Field(default_factory=list, description="相关章节ID")
    placeholder: str = Field("", description="建议占位文本")
    placeholder_found: bool = Field(False, description="正文是否已有占位")
    fix_suggestion: str = Field("", description="修复建议")


class ReviewRiskItem(BaseModel):
    """废标风险检查结果"""
    risk_id: str = Field("", description="风险ID")
    handled: bool = Field(False, description="是否已处理")
    issue: str = Field("", description="问题说明")


class ReviewDuplicationIssue(BaseModel):
    """重复内容检查结果"""
    chapter_ids: List[str] = Field(default_factory=list, description="重复章节ID")
    issue: str = Field("", description="问题说明")


class ReviewFabricationRisk(BaseModel):
    """疑似虚构风险检查结果"""
    chapter_id: str = Field("", description="章节ID")
    text: str = Field("", description="疑似风险文本")
    reason: str = Field("", description="判断原因")
    fix_suggestion: str = Field("", description="修复建议")


class ReviewContractIssue(BaseModel):
    """导出前审校通用问题"""
    item_id: str = Field("", description="关联项ID")
    chapter_ids: List[str] = Field(default_factory=list, description="相关章节ID")
    issue: str = Field("", description="问题说明")
    evidence: str = Field("", description="审校证据")
    fix_suggestion: str = Field("", description="修复建议")
    severity: str = Field("warning", description="问题等级，如 blocking/warning")
    blocking: bool = Field(False, description="是否阻塞导出")


class RevisionPlanAction(BaseModel):
    """修订计划动作"""
    id: str = Field(..., description="动作ID，如 RP-01")
    target_chapter_ids: List[str] = Field(default_factory=list, description="目标章节")
    action_type: str = Field("", description="补写/替换/删减/补材料/人工确认")
    instruction: str = Field("", description="修订指令")
    priority: str = Field("normal", description="high/normal/low")
    related_issue_ids: List[str] = Field(default_factory=list, description="关联问题ID")
    blocking: bool = Field(False, description="是否处理后才能导出")


class RevisionPlan(BaseModel):
    """审校后的修订计划"""
    actions: List[RevisionPlanAction] = Field(default_factory=list, description="修订动作")
    summary: str = Field("", description="修订摘要")


class ReviewSummary(BaseModel):
    """审校汇总"""
    ready_to_export: bool = Field(False, description="是否可导出")
    blocking_issues: int = Field(0, description="阻塞问题数量")
    warnings: int = Field(0, description="警告数量")
    blocking_issues_count: int = Field(0, description="阻塞问题数量")
    warnings_count: int = Field(0, description="警告数量")
    coverage_rate: float = Field(0, description="覆盖率")
    blocking_summary: str = Field("", description="阻塞摘要")
    next_actions: List[str] = Field(default_factory=list, description="下一步处理建议")


class ReviewReport(BaseModel):
    """导出前合规审校报告"""
    coverage: List[ReviewCoverageItem] = Field(default_factory=list, description="评分项/要求覆盖检查")
    missing_materials: List[ReviewMissingMaterialItem] = Field(default_factory=list, description="缺失材料检查")
    rejection_risks: List[ReviewRiskItem] = Field(default_factory=list, description="废标风险检查")
    duplication_issues: List[ReviewDuplicationIssue] = Field(default_factory=list, description="重复内容检查")
    fabrication_risks: List[ReviewFabricationRisk] = Field(default_factory=list, description="虚构风险检查")
    fixed_format_issues: List[ReviewContractIssue] = Field(default_factory=list, description="固定格式问题")
    signature_issues: List[ReviewContractIssue] = Field(default_factory=list, description="签字盖章问题")
    price_rule_issues: List[ReviewContractIssue] = Field(default_factory=list, description="报价规则问题")
    evidence_chain_issues: List[ReviewContractIssue] = Field(default_factory=list, description="证据链问题")
    page_reference_issues: List[ReviewContractIssue] = Field(default_factory=list, description="页码/索引问题")
    anonymity_issues: List[ReviewContractIssue] = Field(default_factory=list, description="暗标/匿名问题")
    blocking_issues: List[ReviewContractIssue] = Field(default_factory=list, description="阻塞项清单")
    warnings: List[ReviewContractIssue] = Field(default_factory=list, description="警告项清单")
    revision_plan: Optional[RevisionPlan] = Field(None, description="修订计划")
    summary: ReviewSummary = Field(default_factory=ReviewSummary, description="审校汇总")


class ComplianceReviewRequest(BaseModel):
    """导出前合规审校请求"""
    outline: List[OutlineItem] = Field(..., description="包含正文内容的目录结构")
    project_overview: Optional[str] = Field("", description="项目概述")
    analysis_report: Optional[AnalysisReport] = Field(None, description="结构化标准解析报告")
    response_matrix: Optional[ResponseMatrix] = Field(None, description="响应矩阵")
    reference_bid_style_profile: Dict[str, Any] = Field(default_factory=dict, description="成熟投标文件样例反向建模结果")
    document_blocks_plan: Dict[str, Any] = Field(default_factory=dict, description="图表、承诺书、图片、附件等文档块规划")
    bid_mode: Optional[BidMode] = Field(None, description="标书生成模式")
