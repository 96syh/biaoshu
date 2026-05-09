"""Prompt helpers split from app.utils.prompt_manager."""
from __future__ import annotations

from typing import Any, Dict, Tuple
from .core import _json, _schema_contract, get_full_bid_rulebook
from .schemas import get_analysis_report_schema, get_response_matrix_schema


def generate_analysis_report_prompt(file_content: str, *, include_schema_in_prompt: bool = True) -> Tuple[str, str]:
    schema_json = _json(get_analysis_report_schema(), indent=2)
    rulebook = get_full_bid_rulebook()
    system_prompt = f"""你是资深招标文件解析专家。目标是把招标文件解析成后续目录、正文、素材规划和导出审校都能复用的 AnalysisReport JSON。

输出契约：
1. 只输出合法 JSON；缺失信息填空字符串、空数组或 null。
2. 关键字段尽量填写 source/source_ref，至少包含章节名、条款号、页码、表格名或短原文之一。
3. 普通数组保留最高信号 10 项；评分表和 bid_document_requirements.composition 要尽量完整，最多 40 项。

必须覆盖：
1. 前端九类页签：基础信息、资格审查、技术评分、商务评分、其他评分、无效标与废标项、投标文件要求、开评定标流程、补充信息归纳。
2. 高风险条款：★、*、▲、实质性、不允许偏离、废标、投标无效、否决、资格不通过、必须、不得、应当。
3. 固定格式、签字盖章、报价文件、偏离表、承诺函、授权委托书、资格证明材料、暗标要求。
4. 评分项按原评分表逐行提取到 technical_scoring_items、business_scoring_items、price_scoring_items；每行保留 name、score、standard/source，不得只写“详见招标文件”。
5. 资格/形式/响应性评审、无效标与废标项、开评定标流程、付款/样品/份额/数量/合同时间等补充信息要单独归类。

投标文件要求解析：
1. 定位“投标文件、投标文件格式、投标文件组成、投标文件编制、方案应包括”等章节，并写入 bid_document_requirements。
2. composition 反映卷册顺序、必交/可选/不适用、固定格式、签章、附件、报价相关、暗标敏感属性。
3. 生成 selected_generation_target：若存在服务/设计/技术/实施/施工组织/供货等方案类项且用户未要求 full_bid，默认选为目录正文对象。
4. 同一对象出现在组成章节和格式章节时合并：组成章节确认对象，格式章节提取 base_outline_items；没有子项时 base_outline_strategy="technical_scoring_items"。
5. “应包括但不限于/服务纲要应包括”等方案子项写入 scheme_or_technical_outline_requirements，并作为后续目录硬约束。
6. 推荐 bid_mode_recommendation：full_bid、technical_only、technical_service_plan、service_plan、business_volume、qualification_volume、price_volume；存在方案 target 时默认推荐方案/技术范围。
7. 如果目标只是方案分册，商务、报价、资格内容不得进入技术目录，只保留为 excluded_composition_titles、volume_rules 或审校信息。

企业资料与初稿矩阵：
1. enterprise_material_profile.requirements 写本项目需要的企业资料；provided_materials 只放输入明确提供的资料；missing_materials 和 verification_tasks 写待补/待核验项。
2. 不得把招标文件“要求提供”误写成“企业已提供”；未见明确企业资料时 status=missing 或 unknown，verification_status=unverified。
3. 同步生成 response_matrix 初稿，覆盖高分值、高风险、阻塞项和投标文件格式硬约束。

{rulebook}

{_schema_contract("AnalysisReport JSON", schema_json, include_schema_in_prompt)}
"""
    user_prompt = f"""请解析以下招标文件内容，输出 AnalysisReport JSON。

<tender_file_content>
{file_content}
</tender_file_content>

直接返回 JSON。"""
    return system_prompt, user_prompt


def generate_response_matrix_prompt(
    analysis_report: Dict[str, Any],
    reference_bid_style_profile: Dict[str, Any] | None = None,
    *,
    include_schema_in_prompt: bool = True,
) -> Tuple[str, str]:
    schema_json = _json(get_response_matrix_schema(), indent=2)
    rulebook = get_full_bid_rulebook()
    system_prompt = f"""你是投标响应矩阵规划专家。目标是把 AnalysisReport 转成可驱动目录、正文、素材块和审校的 ResponseMatrix JSON。

输出契约：
1. 只输出合法 JSON。
2. 不新增 AnalysisReport 中不存在的强制条款 ID；样例扩展只能标记为 profile_expansion。
3. source_item_id 规则：评分项用 T/B/P；评审、资格、形式、实质性条款用 E/Q/F/C；风险用 R；固定格式、签章、证据链、材料用 FF/SIG/EV/M/X。

矩阵必须回答：
1. 每个评分项、资格项、形式项、响应性条款、实质性条款、废标风险、固定格式、签章、报价规则、证明材料如何响应。
2. 哪些内容可生成正文，哪些必须填表，哪些必须附材料，哪些必须人工确认，哪些只允许出现在报价卷。
3. blocking=true 的风险对应哪个章节、材料或人工动作。

范围边界：
1. 必须纳入 bid_document_requirements.composition、scheme_or_technical_outline_requirements 和 selected_generation_target。
2. full_bid 时，composition 中 required=true 且 applicability != not_applicable 的项目必须有矩阵条目。
3. 方案/技术分册时，selected_generation_target.base_outline_items 和 scheme_or_technical_outline_requirements 是正文主线；投标函、保证金、报价、资格资料等只作为 excluded、material 或 human_confirm。
4. 固定格式、签章、盖章、日期、附件、偏差表、报价表等 response_method 应为 fill_form、material_attachment 或 human_confirm，并说明不得自由改写。
5. 报价、金额、税率缺失时不得生成具体数值。

{rulebook}

{_schema_contract("ResponseMatrix JSON", schema_json, include_schema_in_prompt)}
"""
    user_prompt = f"""请基于以下 AnalysisReport 和 ReferenceBidStyleProfile 生成 ResponseMatrix。

<analysis_report_json>
{_json(analysis_report or {}, indent=2)}
</analysis_report_json>

<reference_bid_style_profile_json>
{_json(reference_bid_style_profile or {}, indent=2)}
</reference_bid_style_profile_json>

直接返回 JSON。"""
    return system_prompt, user_prompt
