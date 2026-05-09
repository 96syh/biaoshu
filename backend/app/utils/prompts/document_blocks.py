"""Prompt helpers split from app.utils.prompt_manager."""
from __future__ import annotations

from typing import Any, Dict, List, Tuple
from .core import _json, _schema_contract
from .schemas import get_document_blocks_schema


def generate_document_blocks_prompt(
    analysis_report: Dict[str, Any] | None,
    outline: List[Dict[str, Any]] | Dict[str, Any],
    response_matrix: Dict[str, Any] | None = None,
    reference_bid_style_profile: Dict[str, Any] | None = None,
    enterprise_materials: List[Dict[str, Any]] | None = None,
    asset_library: List[Dict[str, Any]] | Dict[str, Any] | None = None,
    include_schema_in_prompt: bool = True,
) -> Tuple[str, str]:
    schema_json = _json(get_document_blocks_schema(), indent=2)
    system_prompt = f"""你是技术标图表与素材规划专家。目标是为目录章节规划表格、流程图、组织架构图、图片、承诺书、证明材料或页码占位。

输出契约：
1. 只输出合法 JSON。
2. 不编造图片、证书、截图、人员、设备、软件或案例；没有素材时输出 placeholder。
3. 素材库有匹配图片或附件时输出 asset_id；没有则输出 fallback placeholder。

规划规则：
1. 匹配 ReferenceBidStyleProfile.table_models 或 chapter_blueprints.tables_to_insert 时可继承表格模型，但列名和行内容必须映射到当前招标文件和企业资料。
2. 表格必须给出表名、列名、行生成规则和数据来源。
3. 承诺书必须给出致函对象、承诺事项、署名变量、日期变量；样例只继承版式和事项类别，不继承项目事实、日期和承诺时限。
4. 组织机构图、流程图输出结构化 nodes/edges，供后端渲染或人工替换。
5. Word 目录页码由 Word 自动更新，不由模型生成。

{_schema_contract("DocumentBlocksPlan JSON", schema_json, include_schema_in_prompt)}
"""
    user_prompt = f"""请输出图表与素材规划 JSON。

<analysis_report_json>{_json(analysis_report or {}, indent=2)}</analysis_report_json>
<response_matrix_json>{_json(response_matrix or (analysis_report or {}).get('response_matrix') or {}, indent=2)}</response_matrix_json>
<reference_bid_style_profile_json>{_json(reference_bid_style_profile or (analysis_report or {}).get('reference_bid_style_profile') or {}, indent=2)}</reference_bid_style_profile_json>
<outline_json>{_json(outline or [], indent=2)}</outline_json>
<enterprise_materials_json>{_json(enterprise_materials or [], indent=2)}</enterprise_materials_json>
<asset_library_json>{_json(asset_library or [], indent=2)}</asset_library_json>

直接返回 JSON。"""
    return system_prompt, user_prompt
