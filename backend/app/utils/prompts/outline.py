"""Prompt helpers split from app.utils.prompt_manager."""
from __future__ import annotations

from typing import Any, Dict, List, Tuple
from .core import _json, get_full_bid_rulebook
from .outline_templates import get_generic_service_plan_outline_template


def _compact_text(value: Any, limit: int = 360) -> str:
    text = str(value or "").strip()
    if len(text) <= limit:
        return text
    return f"{text[:limit].rstrip()}……"


def _compact_item(item: Any, keys: tuple[str, ...], text_limit: int = 360) -> Dict[str, Any]:
    if not isinstance(item, dict):
        return {}
    compact: Dict[str, Any] = {}
    for key in keys:
        value = item.get(key)
        if value in (None, "", [], {}):
            continue
        if isinstance(value, str):
            compact[key] = _compact_text(value, text_limit)
        elif isinstance(value, list):
            compact[key] = [
                _compact_text(part, 180) if not isinstance(part, dict) else _compact_item(part, ("id", "title", "name", "requirement", "source_ref"), 160)
                for part in value[:8]
            ]
        elif isinstance(value, dict):
            compact[key] = _compact_item(
                value,
                ("id", "title", "name", "order", "source_ref", "requirement", "chapter_type", "volume_id"),
                180,
            )
        else:
            compact[key] = value
    return compact


def _compact_list(items: Any, keys: tuple[str, ...], limit: int = 40, text_limit: int = 360) -> List[Dict[str, Any]]:
    if not isinstance(items, list):
        return []
    return [
        compact
        for compact in (_compact_item(item, keys, text_limit) for item in items[:limit])
        if compact
    ]


def _compact_bid_document_requirements(bid_doc: Any) -> Dict[str, Any]:
    if not isinstance(bid_doc, dict):
        return {}
    composition_keys = (
        "id", "order", "title", "volume_id", "chapter_type", "generation_scope",
        "source_ref", "requirement_summary", "children",
    )
    selected_keys = (
        "target_id", "target_title", "parent_composition_id", "target_source",
        "target_source_type", "generation_scope", "use_as_outline_basis",
        "base_outline_strategy", "confidence", "base_outline_items",
    )
    scheme_keys = (
        "id", "order", "title", "requirement", "source_ref", "derived_from",
        "must_preserve_title", "children",
    )
    return {
        "composition": _compact_list(bid_doc.get("composition"), composition_keys, limit=30, text_limit=220),
        "selected_generation_target": _compact_item(bid_doc.get("selected_generation_target"), selected_keys, 260),
        "scheme_or_technical_outline_requirements": _compact_list(
            bid_doc.get("scheme_or_technical_outline_requirements"),
            scheme_keys,
            limit=30,
            text_limit=260,
        ),
    }


def _compact_response_matrix(matrix: Any) -> Dict[str, Any]:
    if not isinstance(matrix, dict):
        return {}
    item_keys = (
        "id", "category", "title", "requirement_summary", "response_strategy",
        "scoring_item_id", "requirement_id", "source_ref", "priority",
    )
    return {
        "coverage_summary": _compact_text(matrix.get("coverage_summary"), 500),
        "items": _compact_list(matrix.get("items"), item_keys, limit=120, text_limit=240),
    }


def _compact_reference_profile(profile: Any) -> Dict[str, Any]:
    if not isinstance(profile, dict):
        return {}
    outline_keys = (
        "id", "title", "level", "source_type", "scoring_purpose",
        "expected_depth", "tables_required", "image_slots",
    )
    blueprint_keys = (
        "chapter_title", "applies_when", "writing_function",
        "recommended_structure", "tender_fact_slots", "enterprise_fact_slots",
        "tables_to_insert", "assets_to_insert", "do_not_copy",
    )
    return {
        "profile_name": _compact_text(profile.get("profile_name"), 120),
        "document_scope": _compact_text(profile.get("document_scope"), 120),
        "recommended_use_case": _compact_text(profile.get("recommended_use_case"), 240),
        "source_history_case": _compact_item(
            profile.get("source_history_case"),
            ("project_title", "file_name", "document_category", "primary_domain", "node_title", "node_path", "profile_source"),
            180,
        ),
        "outline_template": _compact_list(profile.get("outline_template"), outline_keys, limit=18, text_limit=180),
        "chapter_blueprints": _compact_list(profile.get("chapter_blueprints"), blueprint_keys, limit=10, text_limit=220),
        "quality_risks": _compact_list(profile.get("quality_risks"), ("risk", "location", "fix_rule"), limit=8, text_limit=220),
    }


def _compact_document_blocks_plan(plan: Any) -> Dict[str, Any]:
    if not isinstance(plan, dict):
        return {}
    block_keys = (
        "id", "chapter_id", "chapter_title", "block_type", "title",
        "purpose", "source_ref", "required_assets", "required_enterprise_data",
    )
    return {
        "document_blocks": _compact_list(plan.get("document_blocks"), block_keys, limit=50, text_limit=220),
        "missing_assets": _compact_list(plan.get("missing_assets"), ("id", "name", "reason", "chapter_title"), limit=20, text_limit=180),
        "missing_enterprise_data": _compact_list(plan.get("missing_enterprise_data"), ("id", "name", "reason", "chapter_title"), limit=20, text_limit=180),
    }


def _compact_outline_analysis_report(report: Dict[str, Any] | None) -> Dict[str, Any]:
    if not isinstance(report, dict):
        return {}
    project_keys = (
        "name", "number", "purchaser", "agency", "project_type",
        "service_scope", "service_period", "service_location",
        "quality_requirements", "maximum_price", "submission_method",
    )
    scoring_keys = (
        "id", "name", "score", "weight", "standard", "requirement",
        "criterion", "logic", "response_strategy", "source_ref",
        "required_materials", "evidence_requirements",
    )
    requirement_keys = (
        "id", "name", "review_type", "target", "score", "standard",
        "requirement", "criterion", "logic", "source_ref",
    )
    material_keys = ("id", "name", "title", "requirement", "source_ref", "purpose")
    return {
        "project": _compact_item(report.get("project"), project_keys, 320),
        "bid_mode_recommendation": report.get("bid_mode_recommendation", ""),
        "bid_document_requirements": _compact_bid_document_requirements(report.get("bid_document_requirements")),
        "volume_rules": _compact_list(report.get("volume_rules"), ("id", "title", "scope", "requirement", "source_ref"), limit=20, text_limit=220),
        "anonymity_rules": _compact_list(report.get("anonymity_rules"), ("id", "title", "requirement", "source_ref"), limit=20, text_limit=220),
        "bid_structure": _compact_item(report.get("bid_structure"), ("mode", "volumes", "notes"), 240),
        "technical_scoring_items": _compact_list(report.get("technical_scoring_items"), scoring_keys, limit=60, text_limit=260),
        "business_scoring_items": _compact_list(report.get("business_scoring_items"), scoring_keys, limit=40, text_limit=240),
        "price_scoring_items": _compact_list(report.get("price_scoring_items"), scoring_keys, limit=20, text_limit=220),
        "qualification_review_items": _compact_list(report.get("qualification_review_items"), requirement_keys, limit=50, text_limit=240),
        "qualification_requirements": _compact_list(report.get("qualification_requirements"), requirement_keys, limit=50, text_limit=240),
        "formal_review_items": _compact_list(report.get("formal_review_items"), requirement_keys, limit=30, text_limit=220),
        "responsiveness_review_items": _compact_list(report.get("responsiveness_review_items"), requirement_keys, limit=40, text_limit=220),
        "mandatory_clauses": _compact_list(report.get("mandatory_clauses"), requirement_keys, limit=40, text_limit=220),
        "rejection_risks": _compact_list(report.get("rejection_risks"), ("id", "risk", "fix_rule", "source_ref"), limit=40, text_limit=240),
        "required_materials": _compact_list(report.get("required_materials"), material_keys, limit=60, text_limit=220),
        "fixed_format_forms": _compact_list(report.get("fixed_format_forms"), material_keys, limit=40, text_limit=220),
        "signature_requirements": _compact_list(report.get("signature_requirements"), material_keys, limit=30, text_limit=180),
        "price_rules": _compact_item(
            report.get("price_rules"),
            ("score", "quote_method", "maximum_price_rule", "abnormally_low_price_rule", "missing_item_rule", "source_ref"),
            260,
        ),
        "response_matrix": _compact_response_matrix(report.get("response_matrix")),
    }


def generate_level1_outline_prompt(
    overview: str,
    requirements: str,
    analysis_report: Dict[str, Any] | None,
    bid_mode: str | None,
    schema_json: str,
    reference_bid_style_profile: Dict[str, Any] | None = None,
    document_blocks_plan: Dict[str, Any] | None = None,
) -> Tuple[str, str]:
    report = analysis_report or {}
    compact_report = _compact_outline_analysis_report(report)
    response_matrix = _compact_response_matrix(report.get("response_matrix") or compact_report.get("response_matrix"))
    compact_profile = _compact_reference_profile(reference_bid_style_profile or report.get("reference_bid_style_profile") or {})
    compact_blocks_plan = _compact_document_blocks_plan(document_blocks_plan or report.get("document_blocks_plan") or {})
    rulebook = get_full_bid_rulebook()
    service_template = _json(get_generic_service_plan_outline_template(), indent=2)
    system_prompt = f"""你是资深投标文件目录规划专家。目标是根据 AnalysisReport、ResponseMatrix、用户目标和可选样例风格生成一级目录 JSON。

输出契约：
1. 只输出合法 JSON，不输出 markdown，不生成正文。
2. 不重新解析招标文件，只使用传入的 AnalysisReport 和 ResponseMatrix。
3. 每个一级节点必须包含 schema 要求字段；scoring_item_ids 用 T/B/P，requirement_ids 用 E/Q/F/C，risk_ids 用 R，material_ids 用 M/X/EV/FF/SIG。

范围判断：
1. full_bid：按 bid_document_requirements.composition 顺序生成整本投标文件目录。
2. technical_only、technical_service_plan、service_plan 或 selected_generation_target.use_as_outline_basis=true：只生成目标方案分册/章节。
3. price_volume、qualification_volume、business_volume：只生成对应卷册。
4. 方案分册不得生成投标函、报价、保证金、资格审查资料、偏差表等完整投标文件正文；这些只进 excluded、描述或 coverage_summary。

标题优先级：
1. selected_generation_target.base_outline_items 中 must_preserve_title=true 的标题，以及 bid_document_requirements.composition 中技术标/服务方案/设计方案节点的 children。
2. bid_document_requirements.scheme_or_technical_outline_requirements。
3. 技术/服务评分项 technical_scoring_items。
4. ReferenceBidStyleProfile 的目录层级、章节功能、表格/承诺/图片位置。
5. 通用服务/技术方案保底目录。

质量要求：
1. 目录服从 bid_document_requirements、selected_generation_target、volume_rules、bid_structure、报价隔离、暗标和固定格式要求。
2. 组成章节确认对象，格式章节提供标题/表格/签章，评分章节补充响应重点。
3. 分值高、阻塞风险高、证据链复杂的章节应有更高 expected_word_count 和更细 children。
4. 样例只能迁移结构和风格，不得带入历史项目事实或覆盖招标文件硬约束。
5. 如果招标文件已列明技术标/服务方案/设计方案“应包括/目录/children”标题，必须按原顺序保留这些标题，不得用通用服务方案模板替代。

通用服务/技术方案保底目录参考，仅在招标文件适合服务/技术方案分册且无更明确格式时参考：
{service_template}

{rulebook}

输出 JSON schema：
{schema_json}
"""
    user_prompt = f"""请生成一级目录 JSON。允许每个一级目录直接携带 children；如果有成熟样例目录，请在符合招标文件的前提下吸收其结构。

<overview>{overview}</overview>
<requirements>{requirements}</requirements>
<bid_mode>{bid_mode or report.get('bid_mode_recommendation') or ''}</bid_mode>
<analysis_report_json>{_json(compact_report, indent=2)}</analysis_report_json>
<response_matrix_json>{_json(response_matrix, indent=2)}</response_matrix_json>
<reference_bid_style_profile_json>{_json(compact_profile, indent=2)}</reference_bid_style_profile_json>
<document_blocks_plan_json>{_json(compact_blocks_plan, indent=2)}</document_blocks_plan_json>

直接返回 JSON 对象或 JSON 数组。"""
    return system_prompt, user_prompt


def generate_level23_outline_prompt(
    current_outline_json: Dict[str, Any],
    other_outline: str,
    overview: str,
    requirements: str,
    analysis_report: Dict[str, Any] | None,
    bid_mode: str | None,
    response_matrix: Dict[str, Any] | None,
    reference_bid_style_profile: Dict[str, Any] | None = None,
    document_blocks_plan: Dict[str, Any] | None = None,
) -> Tuple[str, str]:
    schema_json = _json(current_outline_json, indent=2)
    rulebook = get_full_bid_rulebook()
    compact_report = _compact_outline_analysis_report(analysis_report or {})
    compact_response_matrix = _compact_response_matrix(response_matrix or compact_report.get("response_matrix") or {})
    compact_profile = _compact_reference_profile(reference_bid_style_profile or (analysis_report or {}).get("reference_bid_style_profile") or {})
    compact_blocks_plan = _compact_document_blocks_plan(document_blocks_plan or (analysis_report or {}).get("document_blocks_plan") or {})
    system_prompt = f"""你是标书二级目录设计专家。目标是补全当前一级章节的 children、description、映射字段和预期内容块。

输出契约：
1. 不生成正文，不生成三级目录；每个二级节点 children 必须为空数组。
2. 禁止修改当前一级章节 id、title、volume_id、chapter_type。
3. 不得新增 AnalysisReport 和 ResponseMatrix 中不存在的强制条款 ID。

覆盖优先级：
1. 先覆盖 selected_generation_target.base_outline_items、bid_document_requirements.composition、scheme_or_technical_outline_requirements 中映射到本一级章的要求。
2. current_level1_node.children 已有标题时，优先保留其语义、顺序和覆盖范围，可润色但不得替换成泛化模板。
3. 一级标题可拆分时，按并列概念、工作对象、管理内容和“及/和/与/包括/顿号/逗号/括号”拆成二级标题。
4. 一级标题不可拆分时，用评分项、技术要求、响应要求和评审关注点提炼二级标题。
5. 样例 chapter_blueprints 只用于补 description、表格、素材和段落深度，不得引入行业错配或历史项目事实。

标题质量：
1. 二级标题用短语型标题，一般 4-12 个字；避免空泛、套话、重复和无评分支撑的标题。
2. 不把一级标题原样复制为二级标题；同义标题应合并，例如合并为“质量控制与保障措施”。
3. 价格敏感内容只出现在允许价格的卷册；暗标章节不得设计暴露身份的标题或素材位。
4. 证明材料类章节设计材料清单、证明用途、核验要点、页码索引；固定格式表单类章节只设计填报项和核验项。
5. current_level1_node.source_type=selected_outline_item 时，该一级标题本身已来自招标文件规定目录；只在招标文件或 ResponseMatrix 明确支持时补二级，否则保持 children=[]，不要套“总体实施思路/流程/保障措施”等通用拆分。

description 要说明：
1. 本节写什么、对应哪些评分项或招标要求。
2. 需要哪些表格、流程图、承诺、证明材料或图片占位。
3. 哪些事实必须来自招标文件或企业资料，哪些内容不得编造。

{rulebook}

输出 JSON schema：
{schema_json}
"""
    user_prompt = f"""请补全当前一级章节的二级目录。不要生成三级目录，所有二级节点的 children 都必须为空数组。

<current_level1_node>{_json(current_outline_json, indent=2)}</current_level1_node>
<other_outline>{other_outline}</other_outline>
<overview>{overview}</overview>
<requirements>{requirements}</requirements>
<bid_mode>{bid_mode or ''}</bid_mode>
<analysis_report_json>{_json(compact_report, indent=2)}</analysis_report_json>
<response_matrix_json>{_json(compact_response_matrix, indent=2)}</response_matrix_json>
<reference_bid_style_profile_json>{_json(compact_profile, indent=2)}</reference_bid_style_profile_json>
<document_blocks_plan_json>{_json(compact_blocks_plan, indent=2)}</document_blocks_plan_json>

直接返回 JSON。"""
    return system_prompt, user_prompt
