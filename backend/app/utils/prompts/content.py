"""Prompt helpers split from app.utils.prompt_manager."""
from __future__ import annotations

from typing import Any, Dict, List, Tuple
from .core import _json, get_full_bid_rulebook


def generate_chapter_content_prompt(
    chapter: Dict[str, Any],
    parent_chapters: List[Dict[str, Any]] | None,
    sibling_chapters: List[Dict[str, Any]] | None,
    project_overview: str,
    analysis_report: Dict[str, Any] | None = None,
    bid_mode: str | None = None,
    generated_summaries: List[Dict[str, Any]] | None = None,
    enterprise_materials: List[Dict[str, Any]] | None = None,
    missing_materials: List[Dict[str, Any]] | None = None,
    response_matrix: Dict[str, Any] | None = None,
    reference_bid_style_profile: Dict[str, Any] | None = None,
    document_blocks_plan: Dict[str, Any] | None = None,
    bidder_name: str = "{bidder_name}",
    bid_date: str = "{bid_date}",
) -> Tuple[str, str]:
    report = analysis_report or {}
    project = report.get("project") or {}
    response_matrix = response_matrix or report.get("response_matrix") or {}
    rulebook = get_full_bid_rulebook()
    system_prompt = f"""你是资深投标文件编制专家。目标是为当前叶子章节生成可直接放入投标文件的正文。

输出契约：
1. 只输出当前章节正文；不输出标题、markdown 代码块、AI 自述或生成过程。
2. 不重新解析招标文件，只使用传入的 AnalysisReport、ResponseMatrix、目录节点、样例风格、图表规划和企业资料画像。
3. 正文不写死页码，统一用 〖页码待编排〗。

事实边界：
1. 不得编造资质、人员、证书、电话、软件、设备数量、业绩、图片、日期、金额、报价、税率、期限或承诺。
2. enterprise_material_profile 标记 missing/unknown/unverified 的资料必须占位，不能写成已具备或已提供。
3. 当前项目围绕 AnalysisReport.project.name 展开；不得残留历史项目、历史日期或样例事实。
4. 服务范围、供货/施工范围、交付内容、期限、工期、质量要求、响应时限必须引用 AnalysisReport 或本章映射条目；缺失时写 〖以招标文件要求为准〗。

章节边界：
1. 命中 selected_generation_target.base_outline_items、scheme_or_technical_outline_requirements、bid_document_requirements.composition 或 fixed_forms 时，严格按对应要求写作。
2. 方案分册正文不得混入投标函、报价、保证金、资格审查资料等非目标卷正文。
3. 固定格式、承诺函、偏离表、报价表、材料索引等不得改表头、列名、固定文字和行列结构。
4. 暗标章节不得出现投标人名称、人员姓名、联系方式、Logo、商标、可识别案例名或图片。

写作方式：
1. 技术/服务/设计/实施方案采用“目标—措施—流程—保障—承诺”，逐项覆盖映射评分点和招标要求。
2. 表单、承诺、偏离、价格、资格、材料附件、审校类章节按固定格式、填报项、核验要点、签章/附件要求或占位说明输出。
3. 组织机构、设备软件、图片证书、截图案例等只能依据企业资料或素材库；缺失时输出职责说明、表格占位或图片占位。
4. 样例 profile 只迁移段落顺序、句式骨架、表格/图片位置和风格；不得照抄样例原句或继承样例事实。
5. 与同级章节避免重复；高分、阻塞风险和证据链章节写细，低风险说明性章节简洁准确。

{rulebook}
"""
    user_prompt = f"""请生成当前章节正文。

<project_variables>
{_json({
    "project_name": project.get("name") or "{project_name}",
    "tenderer_name": project.get("purchaser") or "{tenderer_name}",
    "bidder_name": bidder_name,
    "bid_date": bid_date,
    "service_scope": project.get("service_scope", ""),
    "service_period": project.get("service_period", ""),
    "service_location": project.get("service_location", ""),
    "quality_requirements": project.get("quality_requirements", ""),
}, indent=2)}
</project_variables>
<bid_mode>{bid_mode or report.get('bid_mode_recommendation') or ''}</bid_mode>
<current_chapter>{_json(chapter or {}, indent=2)}</current_chapter>
<parent_chapters>{_json(parent_chapters or [], indent=2)}</parent_chapters>
<sibling_chapters>{_json(sibling_chapters or [], indent=2)}</sibling_chapters>
<generated_summaries>{_json(generated_summaries or [], indent=2)}</generated_summaries>
<project_overview>{project_overview}</project_overview>
<analysis_report>{_json(report, indent=2)}</analysis_report>
<response_matrix>{_json(response_matrix, indent=2)}</response_matrix>
<reference_bid_style_profile>{_json(reference_bid_style_profile or report.get('reference_bid_style_profile') or {}, indent=2)}</reference_bid_style_profile>
<document_blocks_plan>{_json(document_blocks_plan or report.get('document_blocks_plan') or {}, indent=2)}</document_blocks_plan>
<enterprise_material_profile>{_json(report.get('enterprise_material_profile') or {}, indent=2)}</enterprise_material_profile>
<enterprise_materials>{_json(enterprise_materials or [], indent=2)}</enterprise_materials>
<missing_materials>{_json(missing_materials or report.get('missing_company_materials') or [], indent=2)}</missing_materials>

直接输出当前章节正文，不要输出标题。"""
    return system_prompt, user_prompt
